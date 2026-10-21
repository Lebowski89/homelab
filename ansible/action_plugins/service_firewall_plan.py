"""Resolve firewall declarations without templating application secrets."""

import importlib.util
import uuid
from pathlib import Path

from ansible.errors import AnsibleActionFail
from ansible.plugins.action import ActionBase

ROOT = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DECL = load("roles/service_firewall/files/declarations.py", "firewall_declarations")
COMMON = load("roles/service_common/filter_plugins/service_common.py", "firewall_common")
MGT = load("action_plugins/mgt_firewall_plan.py", "lifecycle_legacy_mgt")
WORKERS = load("action_plugins/worker_backend_firewall_plan.py", "lifecycle_legacy_workers")
CATALOG = load("filter_plugins/service_catalog.py", "firewall_catalog")


class ActionModule(ActionBase):
    _VALID_ARGS = frozenset({"entry", "action"})
    _supports_check_mode = True

    def run(self, tmp=None, task_vars=None):
        variables = task_vars or {}
        result = super().run(tmp, variables)
        entry = self._task.args["entry"]
        selected = entry["name"] + (":" + entry["target"] if entry.get("target") else "")
        try:
            ports = entry["config"].get("ports", {})
            ports = list(ports.values()) if isinstance(ports, dict) else ports
            legacy = not any(isinstance(p, dict) and ("exposure" in p or "callers" in p) for p in ports)
            references = {selected, entry["config"].get("name", selected)}
            declared_caller = any(
                references & set(port.get("callers", []))
                for base in variables.get("svcfiles", {}).values()
                for target in base.get("targets", {None: {}})
                for cfg in [CATALOG.service_catalog_merge_target(base, target)]
                for values in [cfg.get("ports", {})]
                for port in (values.values() if isinstance(values, dict) else values)
                if isinstance(port, dict) and isinstance(port.get("callers", []), list)
            )
            if self._task.args["action"] == "drift" or (
                legacy and not ports and not declared_caller and entry["config"].get("network_mode") != "host"
            ):
                # Existing managed declarations keep their installed-policy
                # validation contract. Fresh publications must classify exposure.
                return dict(
                    result,
                    changed=False,
                    ansible_facts={
                        "service_firewall_lifecycle_plan": {
                            "managed": False,
                            "legacy_publications": bool(ports) or entry["config"].get("network_mode") == "host",
                            "metadata": COMMON.service_common_requirements_metadata(
                                entry["config"],
                                entry["config"].get("name", entry["name"] + ("-" + entry["target"] if entry.get("target") else "")),
                            ),
                        }
                    },
                )
            catalog = {}
            raw_configs = {}
            for name, base in variables["svcfiles"].items():
                for target in base.get("targets", {None: {}}):
                    key = name + (":" + target if target else "")
                    cfg = CATALOG.service_catalog_merge_target(base, target)
                    raw_configs[key] = cfg
                    # Project first. Templating a complete service would resolve
                    # environment/credential lookups belonging to other apps.
                    value = {
                        field: cfg[field]
                        for field in ["name", "runtime", "image", "stack", "network_mode", "ports", "depends_on"]
                        if field in cfg
                    }
                    if "systemd" in cfg:
                        value["systemd"] = {key: cfg["systemd"][key] for key in ["requires", "wants"] if key in cfg["systemd"]}
                    value["postgres"] = {"enable": cfg.get("postgres", {}).get("enable", False)}
                    value["traefik"] = {
                        k: v for k, v in cfg.get("traefik", {}).items() if k in {"enable", "port", "backend_host_inventory"}
                    }
                    value["application_prepare"] = {"handler": cfg.get("application_prepare", {}).get("handler")}
                    value["operational_requirements"] = cfg.get("operational_requirements", {})
                    value["deploy"] = {
                        field: cfg.get("deploy", {})[field]
                        for field in ["host", "type", "mode", "replicas", "execution"]
                        if field in cfg.get("deploy", {})
                    }
                    value["_health_required"] = bool(cfg.get("healthcheck")) and not cfg.get("healthcheck", {}).get("disable", False)
                    value["enabled"] = base.get("enabled", True) and cfg.get("enabled", True)
                    catalog[key] = self._templar.template(value, fail_on_undefined=True)
            catalog_keys = set(catalog)
            bootstrap = []
            for role in ["netbox", "infisical"]:
                defaults = self._loader.load_from_file(str(ROOT / f"roles/{role}/defaults/main.yml"), trusted_as_template=True)
                defaults = {
                    **defaults,
                    f"{role}_podman_services": variables.get(f"{role}_podman_services", defaults[f"{role}_podman_services"]),
                }

                def template_default(value, scope, defaults=defaults):
                    return self._templar.copy_with_new_env(available_variables={**defaults, **variables}).template(
                        value, fail_on_undefined=True
                    )

                bootstrap.extend(MGT.bootstrap_metadata(role, defaults, template_default))
                for definition in defaults[f"{role}_podman_services"]:
                    metadata = COMMON.service_common_requirements_metadata({"runtime": "podman", **definition}, definition["name"])
                    metadata = template_default(metadata, defaults)
                    name = metadata["name"]
                    if name not in catalog:
                        catalog[name] = metadata
                        raw_configs[name] = metadata
            selected_metadata = COMMON.service_common_requirements_metadata(
                entry["config"], entry["config"].get("name", entry["name"] + ("-" + entry["target"] if entry.get("target") else ""))
            )
            catalog[selected] = {
                **selected_metadata,
                "deploy": {
                    **selected_metadata.get("deploy", {}),
                    **{k: entry["config"].get("deploy", {})[k] for k in ["replicas"] if k in entry["config"].get("deploy", {})},
                },
                "enabled": True,
                "_health_required": bool(entry["config"].get("healthcheck"))
                and not entry["config"].get("healthcheck", {}).get("disable", False),
            }
            controller = variables["services_controller_host"]
            workers = [variables["services_storage_host"], variables["services_plex_host"]]
            legacy_endpoints = None
            if legacy:
                legacy_endpoints = []
                protected = MGT.build_plan(
                    {key: catalog[key] for key in catalog_keys}, controller, lambda value, defaults: value, bootstrap
                )
                actual = selected_metadata["name"]
                hosts = selected_metadata.get("deploy", {}).get("host", controller)
                hosts = [hosts] if isinstance(hosts, str) else hosts
                if hosts == [controller]:
                    legacy_endpoints = [e | {"host": controller} for e in protected["endpoints"] if e["service"] == actual]
                elif set(hosts) <= set(workers):
                    worker_plan = WORKERS.build_plan(
                        {selected: catalog[selected]}, workers, variables["hostvars"][controller]["local_ip"], lambda value: value
                    )
                    for host in hosts:
                        for endpoint in worker_plan[host]["endpoints"]:
                            port = catalog[selected]["ports"][endpoint["publication"]]
                            caller = "traefik" if endpoint["publication"] == "web_backend" else "prometheus"
                            legacy_endpoints.append(
                                {
                                    "ids": [actual + "/" + endpoint["publication"]],
                                    "service": actual,
                                    "port": port["published"],
                                    "destination": port["target"],
                                    "callers": [caller],
                                    "host": host,
                                    "purpose": "legacy declared worker backend",
                                }
                            )
            plan = DECL.plan(selected, catalog, controller, workers, variables["hostvars"], legacy_endpoints)
            plan["legacy_publications"] = legacy
            # Only declared runtime dependencies block removal. An ACL caller
            # is allowed to contact a provider; it does not imply shared state.
            plan["dependents"] = []
            if self._task.args["action"] == "remove":
                actual = plan["runtime"]["service"]
                for name, cfg in catalog.items():
                    if name == selected or not cfg.get("enabled", True):
                        continue
                    depends = cfg.get("depends_on", [])
                    systemd = cfg.get("systemd", {})
                    units = systemd.get("requires", []) + systemd.get("wants", [])
                    if (
                        selected in depends
                        or actual in depends
                        or cfg.get("network_mode") == "container:" + actual
                        or actual + ".service" in units
                    ):
                        plan["dependents"].append(DECL.identity(name, cfg, controller))
            for record in plan["callers"].values():
                binding = record.get("binding") or {}
                if binding.get("runtime") == "podman" and binding.get("mode") == "rootless":
                    record["metadata"] = self._templar.template(
                        COMMON.service_common_requirements_metadata(raw_configs[record["name"]], record["service"]), fail_on_undefined=True
                    )
            plan["metadata"] = selected_metadata
            plan["sources"] = variables.get("worker_backend_firewall_source_addresses")
            plan["action"] = self._task.args["action"]
            plan["token"] = str(uuid.uuid4())
            return dict(result, changed=False, ansible_facts={"service_firewall_lifecycle_plan": plan})
        except (ValueError, KeyError, TypeError) as error:
            raise AnsibleActionFail(f"Firewall declarations: {error}") from None
