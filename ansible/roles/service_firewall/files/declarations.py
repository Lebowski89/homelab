"""Value-free endpoint declarations shared by lifecycle planning and helpers."""

import re
from copy import deepcopy

NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def publication(value):
    require(isinstance(value, dict), "publication must be a mapping")
    exposure = value.get("exposure")
    require(exposure in {"public", "private"}, "each publication needs exposure: public or private")
    callers = value.get("callers", [])
    require(
        isinstance(callers, list) and all(isinstance(v, str) and v for v in callers),
        "publication callers must be logical service identities",
    )
    require(len(callers) == len(set(callers)), "publication callers must be unique")
    require(
        bool(callers) if exposure == "private" else not callers,
        "private publications need callers; public publications cannot have callers",
    )
    for key in ["published", "target"]:
        require(type(value.get(key)) is int and 1 <= value[key] <= 65535, "publication needs explicit numeric host and container ports")
    if exposure == "private":
        require(value.get("protocol", "tcp") == "tcp", "private UDP publications are unsupported by the current firewall profiles")
        require(value.get("mode", "host") == "host", "private Swarm ingress/routing-mesh publications are unsupported; use host mode")
    return exposure, callers


def identity(name, cfg, controller):
    hosts = cfg.get("deploy", {}).get("host", controller)
    hosts = [hosts] if isinstance(hosts, str) else hosts
    require(isinstance(hosts, list) and hosts and all(isinstance(h, str) for h in hosts), f"{name}: explicit inventory placement required")
    runtime = cfg.get("runtime", "docker")
    execution = cfg.get("deploy", {}).get("execution", {})
    actual = cfg.get("name", name.replace(":", "-"))
    require(isinstance(actual, str) and NAME.fullmatch(actual), "invalid runtime service name")
    binding = {"kind": "service", "runtime": runtime, "phase": runtime, "selector": actual}
    if runtime == "podman":
        mode = execution.get("mode", "rootful")
        require(mode in {"rootful", "rootless"}, "unsupported Podman execution mode")
        binding["mode"] = mode
        if mode == "rootless":
            account = execution.get("host_user")
            require(
                isinstance(account, str) and account.startswith("podman-") and NAME.fullmatch(account),
                "rootless caller requires a dedicated Podman account",
            )
            binding["account"] = account
    else:
        require(runtime == "docker", "unsupported firewall caller runtime")
        stack = cfg.get("stack", actual)
        require(isinstance(stack, str) and NAME.fullmatch(stack), "invalid Docker project/stack")
        if cfg.get("deploy", {}).get("type", "swarm") == "container":
            require(len(hosts) == 1, "Compose requires exactly one deployment host")
            binding.pop("selector")
            binding["compose"] = {"project": stack + "-" + hosts[0], "service": actual}
        else:
            binding["selector"] = stack + "_" + actual
    return {
        "name": name,
        "service": actual,
        "hosts": hosts,
        "binding": binding,
        "image": cfg.get("image"),
        "health_required": cfg.get("_health_required", False),
        "all_publications": [
            (v["published"], v["target"], v.get("protocol", "tcp"))
            for v in (cfg.get("ports", {}).values() if isinstance(cfg.get("ports", {}), dict) else cfg.get("ports", []))
        ],
        "network_mode": cfg.get("network_mode"),
        "swarm_mode": cfg.get("deploy", {}).get("mode", "replicated"),
        "publications": [
            (v["published"], v["target"], v.get("protocol", "tcp"))
            for v in (cfg.get("ports", {}).values() if isinstance(cfg.get("ports", {}), dict) else cfg.get("ports", []))
            if runtime != "docker" or cfg.get("deploy", {}).get("type", "swarm") != "swarm" or v.get("mode", "ingress") == "host"
        ],
    }


def plan(selected, catalog, controller, workers, hostvars, legacy_endpoints=None, provider_endpoints=None, include_providers=True):
    """Resolve logical callers, placement and collisions without secret fields."""
    require(selected in catalog, "selected service is absent from the effective catalog")
    records = {name: identity(name, cfg, controller) for name, cfg in catalog.items() if cfg.get("enabled", True)}
    require(selected in records, "selected service is disabled")
    aliases = {}
    for name, record in records.items():
        aliases.setdefault(record["service"], []).append(name)

    def resolve(name):
        if name in records:
            return name
        matches = aliases.get(name, [])
        require(len(matches) == 1, f"caller {name}: unknown or ambiguous; use service:target")
        return matches[0]

    collisions = {}
    endpoints = []
    selected_record = records[selected]
    accounts = {}
    for record in records.values():
        account = record["binding"].get("account")
        if account:
            for host in record["hosts"]:
                previous = accounts.setdefault((host, account), record["service"])
                require(previous == record["service"], "a rootless account is shared by different services")
    cfg = catalog[selected]
    ports = cfg.get("ports", {})
    ports = dict(enumerate(ports)) if isinstance(ports, list) else ports
    managed = legacy_endpoints is not None or (bool(ports) and any("exposure" in p or "callers" in p for p in ports.values()))
    for name, entry in catalog.items():
        if name not in records:
            continue
        values = entry.get("ports", {})
        values = dict(enumerate(values)) if isinstance(values, list) else values
        for port in values.values():
            if not isinstance(port, dict) or type(port.get("published")) is not int:
                continue
            for host in records[name]["hosts"]:
                key = (host, port.get("protocol", "tcp"), port["published"])
                require(key not in collisions or collisions[key] == name, f"publication collision on {host}:{port['published']}")
                collisions[key] = name
    if (
        legacy_endpoints is None
        and managed
        and any(p.get("exposure") == "private" for p in ports.values())
        and cfg.get("runtime") == "podman"
    ):
        require(
            selected_record["hosts"] == [controller], "automatic private Podman publications currently require the mgt identity profile"
        )
    if managed and legacy_endpoints is None:
        require(isinstance(cfg.get("image"), str) and bool(cfg["image"].strip()), "selected service requires an explicit image")
        seen = {}
        for value in ports.values():
            publication(value)
            key = (value.get("protocol", "tcp"), value["published"])
            require(key not in seen, "duplicate publication aliases must be consolidated before automatic management")
            seen[key] = True
    for label, port in ports.items():
        if not managed or legacy_endpoints is not None:
            continue
        exposure, callers = publication(port)
        if exposure == "public":
            continue
        caller_keys = sorted(resolve(name) for name in callers)
        callers = [records[name]["service"] for name in caller_keys]
        require(
            all(records[c]["network_mode"] != "host" for c in caller_keys),
            "new host-network callers require an explicit verified socket/cgroup binding; automatic shared host UID authorisation is unsupported",
        )
        for host in selected_record["hosts"]:
            require(host == controller or host in workers, f"{host}: unsupported private endpoint host")
            for caller in caller_keys:
                require(
                    records[caller]["hosts"] == [controller],
                    "private callers must use the mgt identity profile; cross-worker or shared remote application identities are unsupported",
                )
                require(host in hostvars and controller in hostvars, "endpoint/controller inventory identity missing")
            if cfg.get("runtime", "docker") == "docker" and cfg.get("deploy", {}).get("type", "swarm") == "swarm":
                require(port.get("mode") == "host", "private Swarm publications require explicit host mode")
            endpoints.append(
                {
                    "ids": [f"{selected}/{label}"],
                    "service": selected_record["service"],
                    "port": port["published"],
                    "destination": port["target"],
                    "callers": callers,
                    "purpose": "declared private publication",
                    "host": host,
                }
            )
    require(
        legacy_endpoints is not None or not managed or all("exposure" in port for port in ports.values()),
        "every publication must explicitly declare exposure",
    )
    if legacy_endpoints is not None:
        endpoints = deepcopy(legacy_endpoints)
        declared = {(v["published"], v["target"]) for v in ports.values()}
        require(
            all((e["port"], e["destination"]) in declared and e["host"] in selected_record["hosts"] for e in endpoints),
            "legacy protected endpoint differs from its effective publication",
        )
    if managed and cfg.get("runtime") == "docker":
        require(cfg.get("deploy", {}).get("type", "swarm") in {"swarm", "container"}, "unsupported Docker deployment type")
        if cfg.get("deploy", {}).get("type", "swarm") == "swarm":
            require(cfg.get("deploy", {}).get("mode", "replicated") in {"global", "replicated"}, "unsupported Swarm deployment mode")
            require(
                cfg.get("deploy", {}).get("mode", "replicated") == "global" or cfg.get("deploy", {}).get("replicas", 1) == 1,
                "automatic Swarm verification supports one replica or one global task per declared host",
            )
        stack = cfg.get("stack", selected_record["service"])
        peers = [
            n
            for n, c in catalog.items()
            if n != selected
            and n in records
            and c.get("runtime", "docker") == "docker"
            and c.get("stack", records.get(n, {}).get("service")) == stack
            and (cfg.get("deploy", {}).get("type", "swarm") == "swarm" or set(records[n]["hosts"]) & set(selected_record["hosts"]))
        ]
        require(
            not peers,
            "automatic protected operations on shared Docker projects/stacks are unsupported; split the project or use the scoped recovery workflow",
        )
    # Provider access is inverse publication ownership: only this selected
    # logical client is contributed, never the provider's entire desired ACL.
    providers = []
    if include_providers:
        for name, record in records.items():
            if name == selected:
                continue
            entry = catalog[name]
            values = entry.get("ports", {})
            values = list(values.values()) if isinstance(values, dict) else values
            explicit = any("exposure" in value or "callers" in value for value in values)
            if explicit and not any(selected == resolve(caller) for value in values for caller in value.get("callers", [])):
                continue
            if explicit:
                available = plan(name, catalog, controller, workers, hostvars, include_providers=False)["endpoints"]
            else:
                available = [e for e in (provider_endpoints or []) if e["service"] == record["service"] and e["host"] in record["hosts"]]
            wanted = []
            for endpoint in available:
                if selected_record["service"] in endpoint["callers"]:
                    if not explicit and any(value.endswith("/postgres") for value in endpoint["ids"]):
                        pg = cfg.get("postgres", {})
                        if selected_record["hosts"] != [controller] or not pg.get("enable", False):
                            continue  # Retain verified worker-local/elsewhere contracts.
                        destination_host = pg.get("host_inventory", controller)
                        if endpoint["port"] != pg.get("port", 5432) or (
                            pg.get("host") != hostvars[endpoint["host"]]["local_ip"]
                            if "host" in pg
                            else destination_host != endpoint["host"]
                        ):
                            continue
                    require(selected_record["hosts"] == [controller], "automatic provider access requires a local mgt client identity")
                    require(
                        selected_record["network_mode"] != "host",
                        "automatic provider access cannot authorise shared host-network identities",
                    )
                    wanted.append(deepcopy(endpoint) | {"callers": [selected_record["service"]]})
            if wanted:
                providers.append({"runtime": record, "endpoints": wanted})
        pg = cfg.get("postgres", {})
        if (
            pg.get("enable", False)
            and selected_record["hosts"] == [controller]
            and (pg.get("host") == hostvars[controller]["local_ip"] if "host" in pg else pg.get("host_inventory", controller) == controller)
        ):
            require(
                any(
                    e["port"] == pg.get("port", 5432) and any(i.endswith("/postgres") for i in e["ids"])
                    for p in providers
                    for e in p["endpoints"]
                ),
                "no declared protected PostgreSQL provider matches this client's host/port; declare and deploy the provider first",
            )
        managed = managed or bool(providers)
    access_hosts = {e["host"] for provider in providers for e in provider["endpoints"]}
    if selected_record["hosts"] == [controller]:
        access_hosts.add(controller)
    return {
        "providers": providers,
        "access_hosts": sorted(access_hosts),
        "managed": managed,
        "service": selected,
        "runtime": selected_record,
        "endpoints": endpoints,
        "callers": {
            name: next(
                (
                    record
                    for record in records.values()
                    if record["service"] == name and record["hosts"] == [controller] and record["network_mode"] != "host"
                ),
                {"binding": None, "legacy": True, "name": name},
            )
            for name in sorted({n for e in endpoints for n in e["callers"]})
        },
        "controller": controller,
        "hosts": selected_record["hosts"],
        "inventory": {h: hostvars[h]["local_ip"] for h in set(selected_record["hosts"] + [controller]) | access_hosts},
        "profile": {h: "mgt" if h == controller else "workers" for h in set(selected_record["hosts"]) | access_hosts},
        "metadata": deepcopy(cfg),
    }
