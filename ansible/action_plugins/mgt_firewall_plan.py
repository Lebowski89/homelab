"""Value-free effective mgt endpoints and a self-contained local policy helper."""

from __future__ import annotations

import importlib.util
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path

from ansible.errors import AnsibleActionFail
from ansible.plugins.action import ActionBase

ANSIBLE = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CATALOG = load(ANSIBLE / "filter_plugins/service_catalog.py", "mgt_firewall_catalog")
HELPER = load(ANSIBLE / "roles/mgt_firewall/files/mgt-firewall.py", "mgt_firewall_validation")


def bootstrap_metadata(role, defaults, template):
    """Project fields before templating; do not evaluate role secret defaults."""
    result = []
    for cfg in defaults[f"{role}_podman_services"]:
        result.append(
            template(
                {
                    "name": cfg["name"],
                    "ports": cfg.get("ports", {}),
                    "account": cfg["deploy"]["execution"]["host_user"],
                    "host": cfg["deploy"]["host"],
                    "bootstrap": role,
                },
                defaults,
            )
        )
    return result


def build_plan(services, controller, template, bootstrap):
    """Derive all private endpoints/callers independently of selector tags.

    Raw application environments and secrets never enter the templar. Named
    publication semantics and the existing Traefik/PostgreSQL declarations own
    this mapping; unsupported mgt private publications fail rather than vanish.
    """
    if not isinstance(services, Mapping):
        raise ValueError("service catalog must be a mapping")
    records, principals = [], {}
    database_callers = set()
    for key, base in services.items():
        if not isinstance(base, Mapping) or type(base.get("enabled", True)) is not bool:
            raise ValueError(f"{key}: service/enabled is invalid")
        for target in base.get("targets", {None: {}}):
            cfg = CATALOG.service_catalog_merge_target(base, target)
            if type(cfg.get("enabled", True)) is not bool:
                raise ValueError(f"{key}: effective enabled must be boolean")
            if not base.get("enabled", True) or not cfg.get("enabled", True):
                continue
            pg = cfg.get("postgres", {}).get("enable", False)
            if type(pg) is not bool:
                raise ValueError(f"{key}: PostgreSQL enable must be boolean")
            metadata = template(
                {
                    "name": cfg.get("name", key),
                    "host": cfg.get("deploy", {}).get("host"),
                    "account": cfg.get("deploy", {}).get("execution", {}).get("host_user"),
                    "ports": cfg.get("ports", {}),
                    "proxy_port": cfg.get("traefik", {}).get("port"),
                    "forward_auth": cfg.get("application_prepare", {}).get("handler") == "authelia",
                    "private_required": bool(
                        set(cfg.get("operational_requirements", {}).get("acl", [])) & {"mgt_backends", "mgt_receivers", "bootstrap"}
                    ),
                    "runtime": cfg.get("runtime", "docker"),
                },
                {},
            )
            name = metadata["name"]
            principals[name] = {
                "inventory_hosts": metadata["host"],
                "future_account": metadata["account"],
                "future_runtime": metadata["runtime"],
            }
            if pg:
                database_callers.add(name)
            if metadata["host"] == controller:
                records.append(metadata)
    for record in bootstrap:
        if record["host"] != controller:
            raise ValueError("bootstrap declarations must address the selected controller")
        principals[record["name"]] = {"inventory_hosts": controller, "future_account": record["account"], "future_runtime": "podman"}
        records.append(record)
        # The production Infisical declaration uses the external HAProxy
        # database; NetBox uses its separately declared PostgreSQL publication.
        if record.get("bootstrap") == "infisical" and "lookup" in record["ports"]:
            database_callers.add(record["name"])
    endpoints = {}
    bootstrap_apps = {record["bootstrap"]: record["name"] for record in bootstrap if set(record["ports"]) & {"recovery", "lookup"}}
    excluded = []
    for record in records:
        name = record["name"]
        ports = record["ports"]
        if isinstance(ports, list):
            ports = {
                ("backend" if port.get("published") == record.get("proxy_port") else f"protocol-{index}"): port
                for index, port in enumerate(ports)
            }
        if not isinstance(ports, Mapping):
            raise ValueError(f"{name}: policy planning requires normalized named publications")
        for publication, port in ports.items():
            # ZNC's declared Autobrr IRC path is a protected protocol endpoint;
            # other protocol listeners and private HTTPS retain their policy.
            znc_irc = name == "znc" and publication == "irc"
            if (
                publication not in {"backend", "web", "metrics", "receiver", "postgres", "database", "cache", "recovery", "lookup"}
                and not znc_irc
            ):
                if record.get("private_required") and publication != "web_secure_private":
                    raise ValueError(f"{name}.{publication}: unclassified required private publication")
                excluded.append({"service": name, "publication": publication, "port": port.get("published")})
                continue
            published, destination = port.get("published"), port.get("target")
            if (
                any(not HELPER.integer(value) or not 1 <= value <= 65535 for value in [published, destination])
                or port.get("protocol", "tcp") != "tcp"
            ):
                raise ValueError(f"{name}.{publication}: only explicit TCP publications are supported")
            if znc_irc:
                if "autobrr" not in principals:
                    raise ValueError("znc.irc: Autobrr caller is not declared")
                callers = {"autobrr"}
                purpose = "Autobrr IRC client"
            elif publication == "metrics" or (
                publication == "backend" and record.get("proxy_port") is None and not record.get("forward_auth")
            ):
                callers = {"prometheus"}
                purpose = "metrics"
            elif publication == "cache":
                callers = {bootstrap_apps[record["bootstrap"]] if "bootstrap" in record else name.removesuffix("-redis")}
                purpose = "application cache"
            elif publication == "database":
                callers = {bootstrap_apps[record["bootstrap"]], "recovery"}
                purpose = "bootstrap database"
            elif publication == "postgres":
                callers = database_callers | {"controller", "recovery"}
                purpose = "declared PostgreSQL applications and recovery"
            elif publication in {"recovery", "lookup"}:
                callers = {"traefik", "controller", "recovery"}
                purpose = "bootstrap proxy/controller/recovery"
            elif publication == "web" and record.get("proxy_port") is None:
                raise ValueError(f"{name}.{publication}: direct content publication has no declared proxy")
            else:
                callers = {"traefik"}
                purpose = "proxy/backend; receiver clients use internal HTTPS"
                if name == "prometheus":
                    callers.add(name)  # declared loopback self scrape
            if not callers:
                raise ValueError(f"{name}.{publication}: intended callers are not declared")
            endpoint_id = f"{name}/{publication}"
            if published in endpoints:
                endpoint = endpoints[published]
                if endpoint["service"] != name or endpoint["destination"] != destination:
                    raise ValueError(f"duplicate mgt protected publication {published}")
                endpoint["ids"].append(endpoint_id)
                endpoint["callers"] = sorted(set(endpoint["callers"]) | callers)
            else:
                endpoints[published] = {
                    "ids": [endpoint_id],
                    "service": name,
                    "port": published,
                    "destination": destination,
                    "callers": sorted(callers),
                    "purpose": purpose,
                }
    principals.update(
        {"controller": {"inventory_hosts": controller}, "recovery": {"inventory_hosts": "explicit authorized operator inventory host(s)"}}
    )
    return {"endpoints": sorted(endpoints.values(), key=lambda endpoint: endpoint["port"]), "principals": principals, "excluded": excluded}


def select_policy(plan, active, callers, verified, address, host, inventory_addresses):
    if not isinstance(active, list) or any(not isinstance(value, str) for value in active) or len(set(active)) != len(active):
        raise ValueError("active endpoints must be a unique list of generated endpoint IDs")
    known = {identity for endpoint in plan["endpoints"] for identity in endpoint["ids"]}
    if set(active) - known:
        raise ValueError("unknown active endpoint IDs: " + ", ".join(sorted(set(active) - known)))
    endpoints = [deepcopy(endpoint) for endpoint in plan["endpoints"] if set(endpoint["ids"]) & set(active)]
    policy = {
        "schema": 1,
        "backend": "nf_tables",
        "inventory_host": host,
        "inventory_address": address,
        "inputs_verified": verified,
        "endpoints": endpoints,
        "callers": deepcopy(callers),
        "principals": deepcopy(plan["principals"]),
    }
    # Remote recovery/controller addresses come from an explicit inventory host.
    # Do not accept arbitrary addresses or source overrides for app SNAT paths.
    for values in policy["callers"].values():
        if not isinstance(values, list):
            raise ValueError("each caller needs a list of identity bindings")
        for binding in values:
            if isinstance(binding, dict) and binding.get("kind") == "remote":
                inventory_host = binding.get("inventory_host")
                if inventory_host not in inventory_addresses:
                    raise ValueError("authorized remote operator host needs inventory local_ip")
                binding["address"] = inventory_addresses[inventory_host]
                if "observed_address" in binding:
                    if type(binding.get("address_override_verified")) is not bool:
                        raise ValueError("address_override_verified must be a boolean")
                    binding["address"] = HELPER.exact_address(binding["observed_address"])
    for name, values in policy["callers"].items():
        for binding in values:
            if isinstance(binding, dict) and binding.get("kind") == "local" and binding.get("phase") == "podman":
                expected = plan["principals"].get(name, {}).get("future_account")
                if binding.get("account") != expected:
                    raise ValueError(f"{name}: future Podman account must match its effective service declaration")
    return policy


def installed_policy_inputs(policy, additions):
    """Extend installed endpoint selection without dropping accepted identities.

    Installed runtime policy is not an Ansible extra-vars file. Require its
    generated IDs rather than guessing an endpoint from a port number.
    Confirmation values are copied unchanged; the normal planner/install gates
    still validate the prospective policy and re-resolve current identities.
    """
    HELPER.validate_policy(policy, False)
    if not isinstance(additions, list) or any(not isinstance(value, str) or not value for value in additions):
        raise ValueError("additional endpoint IDs must be nonempty strings")
    active = []
    for endpoint in policy["endpoints"]:
        identities = endpoint.get("ids")
        if not isinstance(identities, list) or not identities or any(not isinstance(value, str) or not value for value in identities):
            raise ValueError("installed endpoint lacks unambiguous generated IDs; reconcile it before extension")
        for identity in identities:
            if identity in active:
                raise ValueError("installed endpoint IDs are ambiguous across records")
            active.append(identity)
    for identity in additions:
        if identity not in active:
            active.append(identity)
    return {
        "mgt_firewall_active_endpoints": active,
        "mgt_firewall_callers": deepcopy(policy["callers"]),
        "mgt_firewall_inputs_verified": policy["inputs_verified"],
    }


def bundled_helper():
    source = (ANSIBLE / "roles/worker_backend_firewall/files/worker-backend-firewall.py").read_text()
    helper = (ANSIBLE / "roles/mgt_firewall/files/mgt-firewall.py").read_text()
    return helper.replace(
        "from __future__ import annotations", "from __future__ import annotations\n\nWORKER_ENGINE_SOURCE = " + repr(source), 1
    )


class ActionModule(ActionBase):
    _VALID_ARGS = frozenset({"source_var", "controller", "inventory_address", "active", "callers", "verified", "require_verified"})
    _supports_check_mode = True

    def run(self, tmp=None, task_vars=None):
        task_vars = task_vars or {}
        result = super().run(tmp, task_vars)
        args = self._task.args

        def template(metadata, defaults):
            # Templar receives raw defaults only as lazy variable declarations.
            # Application values are never passed to template().
            templar = self._templar.copy_with_new_env(available_variables={**defaults, **task_vars})
            return templar.template(metadata, fail_on_undefined=True)

        try:
            bootstrap = []
            for role in ["netbox", "infisical"]:
                defaults = self._loader.load_from_file(str(ANSIBLE / f"roles/{role}/defaults/main.yml"), trusted_as_template=True)
                bootstrap.extend(bootstrap_metadata(role, defaults, template))
            plan = build_plan(task_vars[args["source_var"]], args["controller"], template, bootstrap)
            addresses = {host: values.get("local_ip") for host, values in task_vars["hostvars"].items()}
            policy = select_policy(
                plan, args["active"], args["callers"], args["verified"], args["inventory_address"], args["controller"], addresses
            )
            HELPER.validate_policy(policy, args["require_verified"])
        except (ValueError, KeyError, TypeError) as error:
            raise AnsibleActionFail(str(error)) from error
        result.update(
            changed=False,
            ansible_facts={"mgt_firewall_plan": plan, "mgt_firewall_policy": policy, "mgt_firewall_helper_source": bundled_helper()},
            _ansible_facts_cacheable=False,
        )
        return result
