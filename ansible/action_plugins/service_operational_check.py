"""Read-only bridge from service lifecycle guards to installed firewall audits.

No acceptance registry, policy installation or replacement-runtime requirement.
Only value-free declarations enter this action; diagnostic output is bounded.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import os
from pathlib import Path

import yaml
from ansible.errors import AnsibleActionFail
from ansible.plugins.action import ActionBase

ANSIBLE = Path(__file__).resolve().parents[1]


def load(relative, name):
    spec = importlib.util.spec_from_file_location(name, ANSIBLE / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MGT = load("action_plugins/mgt_firewall_plan.py", "maintenance_mgt_plan")
WORKER = load("action_plugins/worker_backend_firewall_plan.py", "maintenance_worker_plan")
WORKER_INPUTS = load("action_plugins/worker_backend_firewall_validate.py", "maintenance_worker_inputs")
PODMAN = load("roles/podman_services/filter_plugins/podman_services.py", "maintenance_podman")
UNRAID_ROOT = "/boot/config/skynet-worker-backend-firewall"
UNRAID_FILES = {UNRAID_ROOT + "/policy.json", UNRAID_ROOT + "/policy.py"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def publications(metadata):
    ports = metadata.get("ports", {})
    return list(ports.values()) if isinstance(ports, dict) else ports


def docker_contract(metadata, observed, check_ports=True):
    """A manager-owned service is managed even with no running task."""
    spec = observed["Spec"]
    stack = metadata.get("stack", metadata["name"])
    require(
        spec.get("Name") == stack + "_" + metadata["name"] and spec.get("Labels", {}).get("com.docker.stack.namespace") == stack,
        "Docker stack ownership differs",
    )
    desired = sorted((p["published"], p["target"], p.get("protocol", "tcp"), p.get("mode", "ingress")) for p in publications(metadata))
    actual = sorted(
        (p["PublishedPort"], p["TargetPort"], p.get("Protocol", "tcp"), p.get("PublishMode", "ingress"))
        for p in observed.get("ports") or []
    )
    require(
        not check_ports or desired == actual,
        "protected publication changed; reconcile the declared endpoint and installed firewall before deployment",
    )
    require(
        sorted(spec.get("TaskTemplate", {}).get("Placement", {}).get("Constraints") or [])
        == sorted(metadata.get("deploy", {}).get("constraints", [])),
        "placement changed; reconcile worker placement and installed policy before deployment",
    )
    return {"managed": True, "ownership_transition": False}


def quadlet_contract(normalized, body, check_ports=True):
    """Compare mapping and data bindings, never environment/secret values."""
    section = None
    values = {}
    for line in body.splitlines():
        if line.startswith("["):
            section = line
        elif section == "[Container]" and "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            if key in {"ContainerName", "UserNS", "User", "Group", "Volume", "PublishPort"}:
                values.setdefault(key, []).append(value)
    require(values.get("ContainerName") == [normalized["unit_name"]], "Quadlet container ownership differs")
    ports = []
    for port in normalized["container"].get("ports", []):
        ports.append(
            (str(port["host_ip"]) + ":" if "host_ip" in port else "") + f"{port['host']}:{port['container']}/{port.get('protocol', 'tcp')}"
        )
    require(
        not check_ports or sorted(values.get("PublishPort", [])) == sorted(ports),
        "protected publication changed; reconcile the installed endpoint before deployment",
    )
    execution = normalized["execution"]
    userns = execution.get("userns")
    expected_mapping = [] if not userns else [f"{userns['mode']}:uid={userns['uid']},gid={userns['gid']}"]
    mounts = [
        f"{v['source']}:{v['target']}" + (":ro" if v.get("read_only", False) else "") for v in normalized["container"].get("mounts", [])
    ]
    mounts += [f"{v['name']}.volume:{v['target']}" + (":ro" if v.get("read_only", False) else "") for v in normalized["volumes"]]
    user = normalized["container"].get("uid")
    group = normalized["container"].get("gid")
    return (
        values.get("UserNS", []) == expected_mapping
        and sorted(values.get("Volume", [])) == sorted(mounts)
        and values.get("User", []) == ([] if user is None else [str(user)])
        and values.get("Group", []) == ([] if group is None else [str(group)])
    )


def mgt_contract(metadata, policy, plan, host, address):
    MGT.HELPER.validate_policy(policy)
    require(
        policy.get("inventory_host") == host and policy.get("inventory_address") == address,
        "installed mgt policy inventory identity differs",
    )
    desired = [e for e in plan["endpoints"] if e["service"] == metadata["name"]]
    require(bool(desired), "selected service has no classified protected endpoint")
    for endpoint in desired:
        matches = [e for e in policy["endpoints"] if set(e.get("ids", [])) & set(endpoint["ids"])]
        require(
            len(matches) == 1 and matches[0] == endpoint,
            "selected endpoint port or authorised callers differ; extend/reconcile the current policy union explicitly",
        )
    # A caller binding records the allowed runtime identity. Compare its current
    # account and placement declarations so old bindings cannot authorise a move.
    names = {metadata["name"]} | {n for e in desired for n in e["callers"]}
    for name in names:
        principal = plan["principals"].get(name, policy.get("principals", {}).get(name, {}))
        for binding in policy["callers"].get(name, []):
            if principal.get("future_account") and binding.get("phase") == "podman" and binding.get("kind") == "local":
                require(binding.get("account") == principal["future_account"], "authorised caller account differs from its declaration")
        if name in plan["principals"]:
            require(
                policy.get("principals", {}).get(name) == plan["principals"][name],
                "caller placement/account requirements changed; reconcile the current policy union explicitly",
            )


def worker_contract(policy, plan, host, address, sources):
    WORKER_INPUTS.validate(policy, True)
    require(
        policy.get("inventory_host") == host and policy.get("inventory_address") == address,
        "installed worker policy inventory identity differs",
    )
    require(
        set(policy["sources"]) == set(sources), "verified mgt source differs; observe and reconcile exact worker source inputs explicitly"
    )
    require(
        bool(plan[host]["ports"]) and set(plan[host]["ports"]) <= set(policy["ports"]),
        "selected publication is missing/stale; reconcile worker backend policy before deployment",
    )


class ActionModule(ActionBase):
    _VALID_ARGS = frozenset({"phase", "metadata", "inventory_host"})
    _supports_check_mode = True

    def run(self, tmp=None, task_vars=None):
        variables = task_vars or {}
        result = super().run(tmp, variables)
        self.variables = variables
        try:
            if self._task.check_mode:
                return dict(result, changed=False, skipped=True)
            metadata = self._task.args["metadata"]
            if self._task.args["phase"] in {"runtime", "ownership", "placement"}:
                if self._task.args["phase"] == "placement" and metadata.get("runtime", "docker") == "docker":
                    # Cleanup operates on a Docker project/stack. Check its real
                    # membership as well as the catalog before any such action.
                    docker = ["docker", "--host", "unix:///var/run/docker.sock"]
                    stack = metadata.get("stack", metadata["name"])
                    if metadata.get("deploy", {}).get("type", "swarm") == "swarm":
                        rows = self.command(
                            docker + ["service", "ls", "--filter", "label=com.docker.stack.namespace=" + stack, "--format", "{{.Name}}"]
                        )
                        require(
                            all(name == stack + "_" + metadata["name"] for name in rows.splitlines()),
                            "Docker stack has other services; split it or use scoped recovery before this operation",
                        )
                    else:
                        host = metadata["deploy"]["host"]
                        require(isinstance(host, str) and bool(host.strip()), "standalone deploy.host must be a non-empty string")
                        project = stack + "-" + host
                        rows = self.command(
                            docker
                            + [
                                "ps",
                                "--all",
                                "--filter",
                                "label=com.docker.compose.project=" + project,
                                "--format",
                                '{{.ID}}\t{{.Label "com.docker.compose.service"}}',
                            ]
                        )
                        require(
                            all(row.partition("\t")[2] == metadata["name"] for row in rows.splitlines()),
                            "Compose project has other containers; split it or use scoped recovery before this operation",
                        )
                evidence = self.runtime(metadata, self._task.args["phase"] == "runtime")
                if self._task.args["phase"] == "ownership" and not evidence.get("ownership_transition"):
                    sources = [
                        v["source"]
                        for v in metadata.get("volumes", {}).values()
                        if v.get("type", "bind") == "bind" and not v.get("read_only", False)
                    ]
                    # A different runtime's named volume is not an inspected
                    # empty bind directory. Keep its explicit transition gate.
                    empty = all(v.get("type", "bind") == "bind" or v.get("read_only", False) for v in metadata.get("volumes", {}).values())
                    for source in sources:
                        info = self.module("ansible.builtin.stat", {"path": source, "follow": False})["stat"]
                        if not info.get("exists"):
                            continue
                        require(info.get("isdir") and not info.get("islnk"), "fresh data root is not a directory")
                        rows = self.module(
                            "ansible.builtin.find", {"paths": [source], "hidden": True, "recurse": False, "file_type": "any"}
                        )
                        require(not rows.get("skipped_paths"), "fresh storage inspection was incomplete")
                        empty = empty and rows.get("matched") == 0
                    evidence["ownership_transition"] = empty
            elif self._task.args["phase"] == "protection":
                self.protection(metadata, self._task.args["inventory_host"])
                evidence = {}
            else:
                raise ValueError("unsupported prerequisite inspection phase")
            return dict(result, changed=False, **evidence)
        except yaml.YAMLError:
            raise AnsibleActionFail(
                "Installed execution metadata is malformed; no mutation performed. Repair its owned metadata through the scoped recovery workflow."
            ) from None
        except (ValueError, KeyError, TypeError, OSError) as error:
            raise AnsibleActionFail(
                f"{self._task.args.get('metadata', {}).get('name', 'service')}: {error}. No service mutation was performed; use the explicit first-cutover/ownership workflow for a real transition."
            ) from error

    def module(self, name, args):
        result = self._execute_module(module_name=name, module_args=args, task_vars=self.variables)
        require(
            not result.get("failed") and not result.get("unreachable"),
            "read-only prerequisite operation failed (" + name + "); inspect that operation on the declared inventory host",
        )
        return result

    def command(self, argv, missing=None):
        result = self._execute_module(module_name="ansible.builtin.command", module_args={"argv": argv}, task_vars=self.variables)
        if result.get("rc") != 0:
            if missing and missing in result.get("stderr", "").lower():
                return None
            raise ValueError("read-only audit failed: " + " ".join(argv[:3]) + "; reconcile installed policy/runtime before retrying")
        return result.get("stdout", "")

    def unraid_flash_device(self):
        """Trust only the root-owned Unraid VFAT flash, with no shadow mounts.

        A shadow mount hides a path inside /boot behind another mount. Reject
        those mounts so device checks describe the policy files actually read.
        VFAT modes are synthetic. Device identity, mount ownership and every
        fixed path component replace the POSIX write-bit test on these two files.
        """
        self.owned("/etc/unraid-version")
        snapshot = base64.b64decode(self.module("ansible.builtin.slurp", {"src": "/proc/self/mountinfo"})["content"]).decode()
        flash = []
        for line in snapshot.splitlines():
            before, after = line.split(" - ", 1)
            fields, backing = before.split(), after.split()
            require(len(fields) >= 6 and len(backing) >= 3, "incomplete Unraid mount metadata")
            mountpoint = fields[4]
            if mountpoint == "/boot":
                flash.append((fields, backing))
            elif mountpoint.startswith("/boot/"):
                require(
                    not any(path == mountpoint or path.startswith(mountpoint + "/") for path in UNRAID_FILES),
                    "unexpected mount shadows the Unraid policy path",
                )
        require(len(flash) == 1, "expected exactly one Unraid /boot flash mount")
        fields, backing = flash[0]
        require(
            fields[3] == "/" and backing[0] == "vfat" and backing[1].startswith("/dev/"),
            "Unraid policy requires a whole VFAT filesystem mounted at /boot from a block device",
        )
        options = dict(option.split("=", 1) for option in (fields[5] + "," + backing[2]).split(",") if "=" in option)
        require(
            int(options.get("uid", "0")) == 0 and int(options.get("gid", "0")) == 0,
            "Unraid flash mount must assign ownership to root",
        )
        major, minor = map(int, fields[2].split(":"))
        device = os.makedev(major, minor)
        block = self.module("ansible.builtin.stat", {"path": backing[1], "follow": True})["stat"]
        require(block.get("isblk") and block.get("device_type") == device, "Unraid flash backing device differs from its mount")
        for path in ["/boot", "/boot/config", UNRAID_ROOT]:
            info = self.module("ansible.builtin.stat", {"path": path, "follow": False})["stat"]
            require(
                info.get("isdir") and not info.get("islnk") and info.get("uid") == 0 and info.get("gid") == 0 and info.get("dev") == device,
                "Unraid flash directory identity differs: " + path,
            )
        return device

    def owned(self, path, owner=0, optional=False, flash_device=None):
        info = self.module("ansible.builtin.stat", {"path": path, "follow": False})["stat"]
        if not info.get("exists"):
            require(optional, "required installed metadata is absent: " + path)
            return None
        flash = flash_device is not None
        require(not flash or (path in UNRAID_FILES and owner == 0), "unexpected Unraid flash metadata path: " + path)
        require(
            info.get("isreg")
            and not info.get("islnk")
            and info.get("uid") == owner
            and (int(info["mode"], 8) & 0o022 == 0 if not flash else info.get("dev") == flash_device and info.get("gid") == 0),
            "installed metadata ownership/mode differs: " + path,
        )
        return info

    def read(self, path, owner=0, optional=False, flash_device=None):
        if self.owned(path, owner, optional, flash_device) is None:
            return None
        return base64.b64decode(self.module("ansible.builtin.slurp", {"src": path})["content"]).decode()

    def runtime(self, metadata, check_ports=True):
        if not metadata.get("deploy", {}).get("host"):
            return {"managed": False}
        if metadata.get("runtime") == "docker":
            if metadata["deploy"].get("type", "swarm") != "swarm":
                # Existing standalone services need exact Compose ownership too.
                host = metadata["deploy"]["host"]
                require(isinstance(host, str) and bool(host.strip()), "standalone deploy.host must be a non-empty string")
                stack = metadata.get("stack", metadata["name"]) + "-" + host
                docker = ["docker", "--host", "unix:///var/run/docker.sock"]
                ids = self.command(
                    docker
                    + [
                        "ps",
                        "--all",
                        "--filter",
                        f"label=com.docker.compose.project={stack}",
                        "--filter",
                        f"label=com.docker.compose.service={metadata['name']}",
                        "--format",
                        "{{.ID}}",
                    ]
                )
                require(len(ids.splitlines()) <= 1, "ambiguous managed Compose service")
                if not ids.strip():
                    return {"managed": False}
                fmt = '{"project":{{json (index .Config.Labels "com.docker.compose.project")}},"service":{{json (index .Config.Labels "com.docker.compose.service")}},"ports":{{json .HostConfig.PortBindings}}}'
                observed = json.loads(self.command(docker + ["container", "inspect", "--format", fmt, ids.strip()]))
                require(
                    observed["project"] == stack and observed["service"] == metadata["name"], "Compose identity changed during inspection"
                )
                actual = sorted(
                    (int(v["HostPort"]), int(key.split("/")[0]), key.split("/")[1])
                    for key, values in (observed["ports"] or {}).items()
                    for v in values or []
                )
                desired = sorted((v["published"], v["target"], v.get("protocol", "tcp")) for v in publications(metadata))
                require(
                    not check_ports or actual == desired,
                    "protected Compose publications changed; reconcile installed endpoint policy before deployment",
                )
                return {"managed": True, "ownership_transition": False}
            name = metadata.get("stack", metadata["name"]) + "_" + metadata["name"]
            # Project only required public fields: never environments, secrets or full inspect.
            fmt = '{"Spec":{"Name":{{json .Spec.Name}},"Labels":{"com.docker.stack.namespace":{{json (index .Spec.Labels "com.docker.stack.namespace")}}},"TaskTemplate":{"Placement":{{json .Spec.TaskTemplate.Placement}}}},"ports":{{json .Endpoint.Spec.Ports}}}'
            body = self.command(
                ["docker", "--host", "unix:///var/run/docker.sock", "service", "inspect", "--format", fmt, name], "no such service"
            )
            return {"managed": False} if body is None else docker_contract(metadata, json.loads(body), check_ports)
        require(metadata.get("runtime") == "podman", "unsupported managed runtime")
        normalized = PODMAN.podman_service_normalize(metadata, metadata["name"])
        unit = normalized["unit_name"]
        state_root = self.variables.get("podman_services_execution_state_dir", "/var/lib/podman-services")
        body = self.read(f"{state_root}/{unit}.yml", optional=True)
        if body is None:
            return {"managed": False}
        state = yaml.safe_load(body)
        require(isinstance(state, dict), "saved execution metadata must be a mapping")
        require(
            state.get("managed_by") == "podman_services"
            and state.get("service") == unit
            and state.get("version") in {None, 2}
            and state.get("unit_name", unit + ".service") == unit + ".service",
            "saved execution ownership/version differs",
        )
        execution = normalized["execution"]
        same = state.get("mode") == execution["mode"]
        if execution["mode"] == "rootless":
            account = execution["host_user"]
            same = same and state.get("host_user") == account
            if not same:
                return {"managed": True, "ownership_transition": False}
            require(
                all(str(state.get(key, "")).isdigit() and int(state[key]) > 0 for key in ["uid", "gid"]),
                "saved rootless IDs must be positive non-root identities",
            )
            marker = yaml.safe_load(self.read(f"{state_root}/accounts/{account}.yml"))
            require(isinstance(marker, dict), "account ownership marker must be a mapping")
            require(
                marker.get("managed_by") == "podman_services"
                and marker.get("service") == unit
                and all(str(marker.get(k)) == str(state.get(k)) for k in ["host_user", "uid", "gid", "home"]),
                "dedicated account ownership marker differs",
            )
            passwd = self.command(["getent", "passwd", account]).strip().split(":")
            require(
                len(passwd) == 7
                and passwd[0] == account
                and passwd[2:4] == [str(state["uid"]), str(state["gid"])]
                and passwd[5] == state["home"]
                and passwd[6].endswith("/nologin"),
                "dedicated account identity changed",
            )
            directory = self.variables.get("podman_services_rootless_home_root", "/var/lib") + "/" + account + "/.config/containers/systemd"
            owner = int(state["uid"])
        else:
            directory = self.variables.get("podman_services_system_quadlet_dir", "/etc/containers/systemd")
            owner = 0
        require(state.get("quadlet_dir", directory) == directory, "managed Quadlet location changed")
        quadlet = self.read(f"{directory}/{unit}.container", owner)
        unchanged = state.get("version") == 2 and same and quadlet_contract(normalized, quadlet, check_ports)
        if unchanged and metadata["operational_requirements"]["ownership_transition"]:
            for mount in normalized["container"].get("mounts", []):
                info = self.module("ansible.builtin.stat", {"path": mount["source"], "follow": False})["stat"]
                require(
                    info.get("isdir") and not info.get("islnk"),
                    "managed data bind is absent/replaced; restore consistent data before maintenance",
                )
        return {"managed": True, "ownership_transition": unchanged}

    def protection(self, metadata, host):
        hosts = self.variables["hostvars"]
        require(host in hosts, "endpoint host is absent from inventory")
        scopes = set(metadata["operational_requirements"]["acl"])
        # Remote recovery binds this identity after validating its explicit
        # target. Installed policy must agree; it cannot select the audit host.
        address = hosts[host]["local_ip"]
        controller = self.variables["services_controller_host"]
        addresses = json.loads(self.command(["ip", "-json", "address", "show"]))
        require(
            address in {a.get("local") for iface in addresses for a in iface.get("addr_info", [])},
            "observed endpoint host does not carry its verified inventory address",
        )
        if "worker_backends" in scopes:
            workers = [self.variables["services_storage_host"], self.variables["services_plex_host"]]
            plan = WORKER.build_plan({metadata["name"]: metadata}, workers, hosts[controller]["local_ip"], lambda value: value)
            unraid = host == self.variables["services_storage_host"]
            root = "/boot/config/skynet-worker-backend-firewall" if unraid else "/etc/skynet-worker-backend-firewall"
            flash_device = self.unraid_flash_device() if unraid else None
            policy = json.loads(self.read(root + "/policy.json", flash_device=flash_device))
            require(
                policy.get("backend") == ("legacy" if unraid else "nf_tables"), "worker firewall backend differs from its declared platform"
            )
            sources = self.variables.get("worker_backend_firewall_source_addresses", [hosts[controller]["local_ip"]])
            worker_contract(policy, plan, host, address, sources)
            self.owned(root + "/policy.py", flash_device=flash_device)
            audit = json.loads(
                self.command(
                    [
                        hosts[host].get("ansible_facts", {}).get("discovered_interpreter_python", "/usr/bin/python3"),
                        root + "/policy.py",
                        "check",
                        "--config",
                        root + "/policy.json",
                    ]
                )
            )
            require(
                audit.get("compliant") is True and audit.get("families") == [4, 6],
                "worker kernel protection is not compliant in both families",
            )
            if unraid:
                require(audit.get("watch_running") is True, "Unraid policy reconciler is not running")
            else:
                for operation in ["is-enabled", "is-active"]:
                    self.command(["systemctl", operation, "skynet-worker-backend-firewall.timer"])
        if scopes & {"mgt_backends", "mgt_receivers", "bootstrap"}:
            require(host == controller, "mgt protection must address the controller inventory host")

            def template(value, defaults):
                return self._templar.copy_with_new_env(available_variables={**defaults, **self.variables}).template(
                    value, fail_on_undefined=True
                )

            # Bootstrap has no catalog/provider dependency. Its metadata comes from role defaults/overrides.
            services = self.variables.get("svcfiles", {}) if "bootstrap" not in scopes else {}
            bootstrap = []
            for role in ["netbox", "infisical"]:
                defaults = self._loader.load_from_file(str(ANSIBLE / f"roles/{role}/defaults/main.yml"), trusted_as_template=True)
                defaults = {
                    **defaults,
                    f"{role}_podman_services": self.variables.get(f"{role}_podman_services", defaults[f"{role}_podman_services"]),
                }
                bootstrap.extend(MGT.bootstrap_metadata(role, defaults, template))
            # The selected effective declaration is authoritative, including target overrides.
            if "bootstrap" not in scopes:
                flattened = {}
                for key, base in services.items():
                    for target in base.get("targets", {None: {}}):
                        effective = MGT.CATALOG.service_catalog_merge_target(base, target)
                        flattened[effective.get("name", key if target is None else key + "-" + target)] = effective
                services = {**flattened, metadata["name"]: metadata}
            plan = MGT.build_plan(services, controller, template, bootstrap)
            policy = json.loads(self.read("/etc/skynet-mgt-firewall/policy.json"))
            mgt_contract(metadata, policy, plan, controller, address)
            self.owned("/etc/skynet-mgt-firewall/policy.py")
            audit = json.loads(self.command(["/usr/bin/python3", "/etc/skynet-mgt-firewall/policy.py", "check"]))
            require(
                audit.get("compliant") is True and not audit.get("pending") and audit.get("families") == [4, 6],
                "installed mgt protection or caller reconciliation is not compliant",
            )
            for operation, unit in [
                ("is-enabled", "skynet-mgt-firewall.service"),
                ("is-enabled", "skynet-mgt-firewall-reconcile.timer"),
                ("is-active", "skynet-mgt-firewall-reconcile.timer"),
            ]:
                self.command(["systemctl", operation, unit])
