"""Build a value-free worker firewall plan from canonical effective services."""

from __future__ import annotations

import importlib.util
import ipaddress
from collections.abc import Mapping
from pathlib import Path

from ansible.errors import AnsibleActionFail, AnsibleFilterError
from ansible.plugins.action import ActionBase

_SPEC = importlib.util.spec_from_file_location(
    "worker_firewall_catalog", Path(__file__).resolve().parents[1] / "filter_plugins/service_catalog.py"
)
_CATALOG = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CATALOG)


def address(value):
    """Accept one explicit unicast address, never a subnet or wildcard."""
    if not isinstance(value, str) or "/" in value or "%" in value:
        raise ValueError("source and inventory addresses must be bare IP addresses")
    parsed = ipaddress.ip_address(value)
    if parsed.is_unspecified or parsed.is_multicast or parsed.is_loopback:
        raise ValueError("source and inventory addresses must be non-loopback unicast addresses")
    return str(parsed)


def build_plan(services, workers, controller_address, template, inventory_groups):
    """Resolve only endpoint metadata, without templating secrets or application data.

    The temporary policy covers host-mode TCP ``web_backend``, ``probe`` and allocated metrics
    publications in the migration allocation. Other protocol/media listeners
    remain under existing policy. Placement and routed backend identity must
    agree; batch tags are deliberately irrelevant.
    """
    if not isinstance(services, Mapping) or not isinstance(workers, list) or not workers:
        raise ValueError("a service mapping and explicit worker inventory names are required")
    if len(set(workers)) != len(workers):
        raise ValueError("worker inventory names must be distinct")
    source = address(controller_address)
    result = {host: {"ports": [], "endpoints": [], "sources": [source]} for host in workers}
    for key, base in services.items():
        if not isinstance(base, Mapping):
            raise ValueError(f"{key}: service must be a mapping")
        if type(base.get("enabled", True)) is not bool:
            raise ValueError(f"{key}: enabled must be boolean")
        for target in base.get("targets", {None: {}}):
            cfg = _CATALOG.service_catalog_merge_target(base, target)
            if type(cfg.get("enabled", True)) is not bool:
                raise ValueError(f"{key}: effective enabled must be boolean")
            if not base.get("enabled", True) or not cfg.get("enabled", True):
                continue
            if "worker_backends" not in cfg.get("operational_requirements", {}).get("acl", []):
                continue
            ports = cfg.get("ports", {})
            protected = {
                name: port
                for name, port in ports.items()
                if name in {"web_backend", "probe", "metrics"}
                or (
                    isinstance(port, Mapping)
                    and isinstance(port.get("published"), int)
                    and not isinstance(port.get("published"), bool)
                    and 22601 <= port["published"] <= 22623
                )
            }
            if not protected:
                continue
            # Never pass the complete service to the templar: its environment
            # may contain lookups even during a supposedly read-only plan.
            metadata = template(
                {
                    "hosts": cfg.get("deploy", {}).get("hosts"),
                    "backend": cfg.get("traefik", {}).get("backend_host_inventory"),
                    "ports": protected,
                }
            )
            try:
                hosts = _CATALOG.service_catalog_resolve_hosts(metadata["hosts"], inventory_groups)
            except AnsibleFilterError as error:
                raise ValueError(str(error)) from error
            host = hosts[0] if len(hosts) == 1 else hosts
            if isinstance(host, list):
                if (
                    not host
                    or any(not isinstance(value, str) or value not in result for value in host)
                    or len(set(host)) != len(host)
                    or cfg.get("deploy", {}).get("type") != "swarm"
                    or cfg.get("deploy", {}).get("mode") != "global"
                ):
                    raise ValueError(f"{key}: multiple protected hosts require an explicit global Swarm worker set")
                hosts = host
            else:
                hosts = [host] if isinstance(host, str) and host in result else []
            if cfg.get("runtime", "docker") != "docker" or not hosts:
                raise ValueError(f"{key}: protected publication must use Docker on declared workers")
            if metadata["backend"] is not None and hosts != [metadata["backend"]]:
                raise ValueError(f"{key}: placement and Traefik backend inventory host disagree")
            for name, port in metadata["ports"].items():
                published, destination = port.get("published"), port.get("target")
                if (not isinstance(published, int) or isinstance(published, bool)) or not 22601 <= published <= 22623:
                    raise ValueError(f"{key}.{name}: published port must be in the temporary 22601..22623 allocation")
                if (not isinstance(destination, int) or isinstance(destination, bool)) or not 1 <= destination <= 65535:
                    raise ValueError(f"{key}.{name}: target must be a TCP port")
                if port.get("mode") != "host" or port.get("protocol", "tcp") != "tcp":
                    raise ValueError(f"{key}.{name}: only host-mode TCP publications are supported")
                for host in hosts:
                    if published in result[host]["ports"]:
                        raise ValueError(f"{host}: duplicate protected published port {published}")
                    result[host]["ports"].append(published)
                    result[host]["endpoints"].append({"service": key, "target": target, "publication": name, "port": published})
    for policy in result.values():
        policy["ports"].sort()
    return result


class ActionModule(ActionBase):
    """Controller-only planning; no inventory plugin, secret or runtime access."""

    _VALID_ARGS = frozenset({"source_var", "workers", "controller_address"})
    _supports_check_mode = True

    def run(self, tmp=None, task_vars=None):
        task_vars = task_vars or {}
        result = super().run(tmp, task_vars)
        try:
            plan = build_plan(
                task_vars[self._task.args["source_var"]],
                self._task.args["workers"],
                self._task.args["controller_address"],
                lambda value: self._templar.template(value, fail_on_undefined=True),
                task_vars["groups"],
            )
        except (ValueError, KeyError, TypeError) as error:
            raise AnsibleActionFail(str(error)) from error
        result.update(changed=False, ansible_facts={"worker_backend_firewall_plan": plan}, _ansible_facts_cacheable=False)
        return result
