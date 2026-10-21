"""Remote implementation of scoped lifecycle transactions; no application mutation.

Only value-free policy/identity fields enter this process. Runtime adapters own
all starts/stops. The existing profile helper owns packet rules and locks.
"""

import hashlib
import json
import os
import pwd
import shlex
import stat
import subprocess
import tempfile
from pathlib import Path

# Injected by the controller from the same bundled policy transaction module.
policy_engine = None


def require(condition, message):
    if not condition:
        raise ValueError(message)


def command(argv, missing=False):
    result = subprocess.run(argv, text=True, capture_output=True, timeout=20, check=False)
    if result.returncode:
        if missing and ("no such" in result.stderr.lower() or "not found" in result.stderr.lower()):
            return None
        # Never echo streamed Python, projected source or arbitrary CLI stderr.
        raise ValueError(
            f"{Path(argv[0]).name} {argv[1] if len(argv) > 1 else ''} failed ({result.returncode}); inspect that operation locally"
        )
    return result.stdout


def runtime_command(record):
    binding = record["binding"]
    if binding["runtime"] == "docker":
        base = ["docker", "--host", "unix:///var/run/docker.sock"]
        selectors = (
            [
                "--filter",
                "label=com.docker.compose.project=" + binding["compose"]["project"],
                "--filter",
                "label=com.docker.compose.service=" + binding["compose"]["service"],
            ]
            if "compose" in binding
            else ["--filter", "label=com.docker.swarm.service.name=" + binding["selector"]]
        )
        return base, selectors
    prefix = []
    if binding["mode"] == "rootless":
        user = pwd.getpwnam(binding["account"])
        require(user.pw_uid > 0 and user.pw_shell.endswith("/nologin"), "dedicated account identity differs")
        prefix = [
            "runuser",
            "-u",
            user.pw_name,
            "--",
            "env",
            "HOME=" + user.pw_dir,
            f"XDG_RUNTIME_DIR=/run/user/{user.pw_uid}",
            f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{user.pw_uid}/bus",
            "/bin/sh",
            "-c",
            'cd "$HOME" || exit; exec "$@"',
            "skynet-firewall-status",
        ]
    return prefix + ["/usr/bin/podman", "--remote=false"], ["--filter", "name=^" + binding["selector"] + "$"]


def runtime_check(record, expected, run=command):
    """Inspect exact local runtime identities; tolerate starting health only boundedly."""
    base, selectors = runtime_command(record)
    ids = run(base + ["ps", "--no-trunc", *selectors, "--format", "{{.ID}}"]).split()
    if expected == "absent":
        require(not ids, "selected runtime still has a running writer; protection retained")
        return
    if expected == "baseline" and not ids:
        return {"ports": {}}
    require(len(ids) == 1, "selected runtime is missing or ambiguous")
    template = (
        '{"id":{{json .ID}},"running":{{json .State.Running}},"pid":{{json .State.Pid}},'
        '"image":{{json .Config.Image}},"state":{{json .State}},"ports":{{json .HostConfig.PortBindings}}}'
    )
    # Docker's inspect template uses Id; Podman's documented template uses ID.
    if record["binding"]["runtime"] == "docker":
        template = template.replace(".ID", ".Id")
    observed = json.loads(run(base + ["container", "inspect", "--format", template, ids[0]]))
    require(
        observed["id"] == ids[0] and observed["running"] is True and type(observed["pid"]) is int and observed["pid"] > 0,
        "runtime changed during inspection",
    )
    if expected == "baseline":
        return observed
    require(
        observed["image"] == record["image"] or observed["image"].startswith(record["image"] + "@"),
        "runtime image differs from canonical declaration",
    )
    health = observed.get("state", {}).get("Health") or {}
    require(isinstance(health, dict) and (bool(health) or not record.get("health_required")), "declared container health check is absent")
    require(health.get("Status", health.get("status", "healthy")) == "healthy", "container has not become healthy")
    required_ports = sorted(tuple(p) for p in record.get("publications", []))
    actual_ports = sorted(
        {
            (int(value["HostPort"]), int(key.split("/")[0]), key.split("/")[1])
            for key, values in (observed.get("ports") or {}).items()
            for value in values or []
        }
    )
    require(actual_ports == required_ports, "running publications differ from the declared endpoint")
    again = json.loads(run(base + ["container", "inspect", "--format", template, ids[0]]))
    require(
        all(again[k] == observed[k] for k in ["id", "pid", "running", "image", "ports"]),
        "runtime changed during health/publication inspection",
    )
    return observed


def atomic(path, content, mode):
    path = Path(path)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        name = temporary.name
        try:
            if mode is not None:
                os.fchmod(temporary.fileno(), mode)
            temporary.write(content.encode())
            temporary.flush()
            os.fsync(temporary.fileno())
            os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def nat_publications(native, read=None, legacy=False):
    """Read only existing NAT tables; never initialize an absent nft table.

    Standard iptables rules use their compatibility view. Native Netavark DNAT
    uses literal TCP destination-port matches. Opaque maps/ranges fail closed;
    this is collision detection, not a second NAT implementation.
    """
    read = read or command
    publications = set()
    tables = {(entry["table"]["family"], entry["table"]["name"]) for entry in native.get("nftables", []) if "table" in entry}
    for family, tool in [("ip", "iptables-save"), ("ip6", "ip6tables-save")]:
        if legacy or (family, "nat") in tables:
            for line in read([tool, "-t", "nat"]).splitlines():
                tokens = shlex.split(line)
                if "-j" not in tokens or tokens[tokens.index("-j") + 1] != "DNAT":
                    continue
                if "-p" in tokens and tokens[tokens.index("-p") + 1] == "udp":
                    continue
                require(
                    "--dport" in tokens and tokens[tokens.index("--dport") + 1].isdecimal(),
                    "cannot classify an existing NAT port range/map; use the explicit transition workflow",
                )
                publications.add(int(tokens[tokens.index("--dport") + 1]))
    for entry in native.get("nftables", []):
        rule = entry.get("rule", {})
        if rule.get("table") == "nat":
            continue  # Inspected through its existing compatibility view above.
        expressions = rule.get("expr", [])
        if not any("dnat" in expression for expression in expressions):
            continue
        ports = []
        udp = False
        for expression in expressions:
            match = expression.get("match", {})
            payload = match.get("left", {}).get("payload", {})
            udp = udp or payload.get("protocol") == "udp"
            if payload.get("field") == "dport":
                require(
                    type(match.get("right")) is int and match.get("op") == "==",
                    "cannot classify a native DNAT map/range; inspect it before assigning private ports",
                )
                ports.append(match["right"])
        if udp:
            continue
        require(bool(ports), "cannot classify an unscoped native DNAT rule; inspect it before assigning private ports")
        publications.update(ports)
    return publications


class Store:
    def __init__(self, helper, request, source, units):
        self.helper, self.request, self.source, self.units = helper, request, source, units
        self.profile = request["profile"]
        self.root = Path(request["root"])
        self.flash = self.root.as_posix().startswith("/boot/")
        self.policy_path = self.root / "policy.json"

    def trusted(self, path, optional=False, directory=False):
        path = Path(path)
        for parent in [*reversed(path.parents), path]:
            try:
                info = parent.lstat()
            except FileNotFoundError:
                require(optional and parent == path, "required owned path is missing: " + str(parent))
                return False
            require(not stat.S_ISLNK(info.st_mode) and info.st_uid == 0, "untrusted path identity: " + str(parent))
            if self.flash and str(parent).startswith("/boot"):
                require(info.st_dev == self.flash_device, "Unraid path leaves the verified flash mount")
            else:
                require(not info.st_mode & 0o022, "writable policy path: " + str(parent))
        require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode), "owned path has an unexpected file type")
        return True

    def flash_boundary(self):
        # Match the existing supported flash contract, including shadow mounts.
        rows = [line.split(" - ", 1) for line in Path("/proc/self/mountinfo").read_text().splitlines()]
        mounted = [(a.split(), b.split()) for a, b in rows if a.split()[4] == "/boot"]
        require(len(mounted) == 1, "expected one Unraid flash mount")
        before, after = mounted[0]
        require(before[3] == "/" and after[0] == "vfat" and after[1].startswith("/dev/"), "unexpected Unraid flash filesystem")
        options = dict(x.split("=", 1) for x in (before[5] + "," + after[2]).split(",") if "=" in x)
        require(int(options.get("uid", "0")) == 0 and int(options.get("gid", "0")) == 0, "flash mount is not root-owned")
        self.flash_device = os.makedev(*map(int, before[2].split(":")))
        require(Path(after[1]).stat().st_rdev == self.flash_device, "flash block-device identity differs")
        for a, _ in rows:
            mount = a.split()[4]
            require(
                not (mount.startswith("/boot/") and (str(self.root) == mount or str(self.root).startswith(mount + "/"))),
                "a mount shadows the worker policy path",
            )
        require(Path("/etc/unraid-version").is_file(), "Unraid platform marker is missing")

    def lock(self):
        return self.helper.OWNED.writer_lock() if self.profile == "mgt" else self.helper.writer_lock()

    def read(self):
        if self.flash:
            self.flash_boundary()
        if not self.policy_path.exists():
            require(self.profile == "mgt", "initial worker source/persistence verification is required before onboarding services")
            require(not self.root.is_symlink(), "unowned policy directory")
            if self.root.exists():
                self.trusted(self.root, directory=True)
                require(
                    set(p.name for p in self.root.iterdir()) <= {"policy.py"},
                    "partial policy directory has unknown files; inspect before recovery",
                )
                if (self.root / "policy.py").exists():
                    self.trusted(self.root / "policy.py")
                    require((self.root / "policy.py").read_text() == self.source, "partial helper differs; inspect before recovery")
            self.was_new = True
            return {
                "schema": 1,
                "backend": "nf_tables",
                "inventory_host": self.request["host"],
                "inventory_address": self.request["address"],
                "inputs_verified": False,
                "endpoints": [],
                "callers": {},
                "principals": {},
                "lifecycle": True,
            }
        self.trusted(self.policy_path)
        self.trusted(self.root / "policy.py")
        self.baseline = json.loads(self.policy_path.read_text())
        return self.baseline

    def validate(self, policy):
        if self.profile == "mgt":
            release = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)
            require(
                release.get("ID", "").strip('"') == "ubuntu" and release.get("VERSION_ID", "").strip('"') == "26.04",
                "automatic mgt protection currently supports Ubuntu 26.04 only",
            )
        self.helper.validate_policy(policy)
        if self.profile == "workers" and self.request["action"] != "install":
            require(
                set(policy["sources"]) <= set(self.request.get("source_addresses", [])),
                "a verified worker source is no longer assigned to mgt; repeat the scoped source verification",
            )
        require(
            policy["inventory_address"] in self.helper.OWNED.local_addresses(self.helper.OWNED.execute)
            if self.profile == "mgt"
            else policy["inventory_address"] in self.helper.local_addresses(self.helper.execute),
            "inventory address is not assigned to this endpoint host",
        )

    def audit(self, policy, recovering=False):
        if not self.policy_path.exists():
            return
        selected = policy.get("managed_services", {}).get(self.request["service"], {})
        recovering = (
            recovering or selected.get("failed_stage", False) or (self.request["action"] == "remove" and selected.get("removing", False))
        )
        result = self.helper.reconcile(policy, "check")
        pending = {
            name.split(":")[0] for name, value in policy.get("managed_services", {}).items() if value.get("pending") or value.get("failed")
        }
        pending_ok = all(
            message.split(":", 1)[0] in pending or policy_engine.deferred_caller(policy, message) for message in result.get("pending", [])
        )
        require(
            (recovering or result.get("rules_compliant", result["compliant"])) and pending_ok,
            "current installed firewall/caller audit failed; repair before changing a service",
        )
        if self.profile == "mgt":
            require(not self.helper.audit_persistence(policy), "installed firewall persistence audit failed")
            if not recovering:
                command(["systemctl", "is-active", "skynet-mgt-firewall.service"])
        elif self.flash:
            require(self.helper.watching(), "Unraid policy reconciler is unavailable")
        else:
            for operation in ["is-enabled", "is-active"]:
                command(["systemctl", operation, "skynet-worker-backend-firewall.timer"])

    def persistence_preflight(self, policy):
        if self.profile != "mgt":
            return
        policy["guard_units"] = self.helper.guard_units(policy, pwd.getpwnam)
        for unit in policy["guard_units"]:
            path = "/etc/systemd/system/" + unit + ".d/45-skynet-mgt-firewall.conf"
            self.units[path] = (
                "# Managed by skynet mgt endpoints\n[Unit]\nRequires=skynet-mgt-firewall.service\nAfter=skynet-mgt-firewall.service\n"
            )
        expected = getattr(self, "baseline", {}).get("persistence", {})
        for filename, content in self.units.items():
            path = Path(filename)
            parent = path.parent if path.parent.exists() else path.parent.parent
            self.trusted(parent, directory=True)
            if path.exists() or path.is_symlink():
                self.trusted(path)
                body = path.read_text()
                require(
                    hashlib.sha256(body.encode()).hexdigest() == expected.get(filename) or body == content,
                    "unowned or changed persistence collision: " + filename,
                )

    def test(self, policy, request, phase):
        if phase == "stage":
            owned = set(policy.get("managed_services", {}).get(request["service"], {}).get("ports", []))
            new_ports = {e["port"] for e in request["endpoints"]} - owned
            if new_ports:
                for port in sorted(new_ports):
                    for family in ["-4", "-6"]:
                        require(
                            not command(["ss", family, "-H", "-lnt", "sport", "=", ":" + str(port)]).strip(),
                            f"private port {port} already has an unowned listener; stop/resolve that writer through the first-cutover workflow",
                        )
                legacy = policy["backend"] == "legacy"
                native = {} if legacy else json.loads(command(["nft", "--json", "list", "ruleset"]))
                require(
                    not (new_ports & nat_publications(native, legacy=legacy)),
                    "a new private port overlaps an existing NAT publication; resolve its owner before deploying",
                )
        self.persistence_preflight(policy)
        if self.profile == "mgt":
            result = self.helper.reconcile(policy, dry_run=True, allow_pending=True)
            allowed = {request["runtime"]["service"], request["service"]}
            # Other in-flight operations may have stopped their own old callers.
            allowed.update(name.split(":")[0] for name, value in policy.get("managed_services", {}).items() if value.get("pending"))
            require(
                all(message.split(":", 1)[0] in allowed or policy_engine.deferred_caller(policy, message) for message in result["pending"]),
                "an unrelated required caller is unresolved; no policy change applied",
            )
            if phase == "finish":
                require(
                    all(policy_engine.deferred_caller(policy, message) for message in result["pending"]),
                    "post-start caller reconciliation is incomplete",
                )
        else:
            self.helper.reconcile(policy, "validate")

    def prepare(self, policy):
        self.changed_files = False
        if self.flash:
            self.flash_boundary()
        self.trusted(self.root if self.root.exists() else self.root.parent, directory=True)
        self.root.mkdir(mode=0o700, exist_ok=True)
        helper_path = self.root / "policy.py"
        if helper_path.exists() or helper_path.is_symlink():
            self.trusted(helper_path)
        if not helper_path.exists() or helper_path.read_text() != self.source:
            self.changed_files = True
            atomic(helper_path, self.source, None if self.flash else 0o600 if self.profile == "mgt" else 0o644)
        if self.profile != "mgt":
            return
        policy["guard_units"] = self.helper.guard_units(policy, pwd.getpwnam)
        for unit in policy["guard_units"]:
            path = "/etc/systemd/system/" + unit + ".d/45-skynet-mgt-firewall.conf"
            self.units[path] = (
                "# Managed by skynet mgt endpoints\n[Unit]\nRequires=skynet-mgt-firewall.service\nAfter=skynet-mgt-firewall.service\n"
            )
        # Existing base units remain byte-for-byte unchanged. New dependencies
        # use the same owned drop-in destination and persistence manifest.
        for filename, content in self.units.items():
            path = Path(filename)
            if path.exists():
                self.trusted(path)
                continue
            require(not path.is_symlink(), "unowned persistence collision")
            parent = path.parent if path.parent.exists() else path.parent.parent
            self.trusted(parent, directory=True)
            path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            self.changed_files = True
            atomic(path, content, 0o644)
        policy["persistence"] = {
            path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in self.helper.persistence_paths(policy)
        }
        self.reload_needed = self.changed_files

    def write(self, policy):
        atomic(
            self.policy_path,
            json.dumps(policy, sort_keys=True, indent=2) + "\n",
            None if self.flash else 0o600 if self.profile == "mgt" else 0o644,
        )

    def apply(self, policy, request, phase):
        if getattr(self, "reload_needed", False):
            command(["systemctl", "daemon-reload"])
            command(["systemctl", "enable", "skynet-mgt-firewall.service", "skynet-mgt-firewall-reconcile.timer"])
        if self.profile == "mgt":
            command(["systemctl", "start", "skynet-mgt-firewall-reconcile.timer"])
        if self.profile == "mgt":
            result = self.helper.reconcile(policy, allow_pending=True)
            if phase != "stage":
                require(
                    all(policy_engine.deferred_caller(policy, message) for message in result.get("pending", [])),
                    "post-start identity reconciliation failed; staged protection retained",
                )
            return result
        else:
            return self.helper.reconcile(policy)


def counters(helper, profile, ports):
    """Read owned pre-DNAT RETURN counters, without installing observation rules."""
    import re
    import shlex

    totals = {}
    chains = {"SKY-MGT-PRE", "SKY-MGT-OUT"} if profile == "mgt" else {"SKY-WBACK-PRE"}
    for family, tool in [(4, "iptables-save"), (6, "ip6tables-save")]:
        saved = command([tool, "-c", "-t", "mangle"])
        for line in saved.splitlines():
            match = re.match(r"\[(\d+):\d+\] (.*)", line)
            if not match:
                continue
            tokens = shlex.split(match[2])
            if (
                len(tokens) < 4
                or tokens[:1] != ["-A"]
                or tokens[1] not in chains
                or "--dport" not in tokens
                or tokens[-2:] != ["-j", "RETURN"]
            ):
                continue
            port = int(tokens[tokens.index("--dport") + 1])
            if port in ports:
                key = str(family) + ":" + str(port)
                totals[key] = totals.get(key, 0) + int(match[1])
    return totals


def qualified_probes(request, policy=None):
    """Handshake in each exact current caller network namespace, without data.

    The namespace source is recorded as such: it is not asserted to be the
    translated source observed by a remote worker. An audited source guard plus
    a completed handshake proves membership of its existing verified allow set.
    """
    results = []
    script = """import json,socket,sys
address,port=json.loads(sys.argv[1])
with socket.create_connection((address,port),timeout=3) as client:
    print(json.dumps({'namespace_source':client.getsockname()[0],'connected':True}))
"""
    for name, record in request["callers"].items():
        if record.get("binding") is None:
            results.append({"caller": name, "not_probed": "retained native/remote contract audited in the installed policy"})
            continue
        binding = record["binding"]
        if binding.get("runtime") == "podman" and binding.get("mode") == "rootless" and policy_engine.future_caller(policy or {}, name):
            user = pwd.getpwnam(binding["account"])
            if not Path(f"/run/user/{user.pw_uid}").is_dir():
                # Account-only preparation deliberately does not activate the
                # user's manager. No runtime socket/store query is safe yet.
                results.append(
                    {
                        "caller": name,
                        "pending_activation": True,
                        "not_probed": "declared client has no active user runtime; traffic remains guarded",
                    }
                )
                continue
        base, selectors = runtime_command(record)
        ids = command(base + ["ps", "--no-trunc", *selectors, "--format", "{{.ID}}"]).split()
        if not ids and policy_engine.future_caller(policy or {}, name):
            results.append(
                {"caller": name, "pending_activation": True, "not_probed": "declared client has not been deployed; traffic remains guarded"}
            )
            continue
        require(len(ids) == 1, "qualified caller is missing or ambiguous: " + name)
        pid = command(base + ["container", "inspect", "--format", "{{.State.Pid}}", ids[0]]).strip()
        require(pid.isdecimal() and int(pid) > 0, "qualified caller is not running: " + name)

        def continuity(pid=pid):
            stat = command(["cat", f"/proc/{pid}/stat"]).rsplit(")", 1)[-1].split()
            return (command(["readlink", f"/proc/{pid}/ns/net"]).strip(), stat[19])

        before = continuity()
        for endpoint in request["endpoints"]:
            if name not in endpoint["callers"]:
                continue
            result = json.loads(
                command(
                    [
                        "nsenter",
                        "--target",
                        pid,
                        "--net",
                        "--",
                        "/usr/bin/python3",
                        "-c",
                        script,
                        json.dumps([endpoint["address"], endpoint["port"]]),
                    ]
                )
            )
            results.append({"caller": name, "port": endpoint["port"], "destination": endpoint["address"], **result})
        require(
            pid == command(base + ["container", "inspect", "--format", "{{.State.Pid}}", ids[0]]).strip() and continuity() == before,
            "caller replaced during qualified handshakes: " + name,
        )
    return {"changed": False, "handshakes": results}


def run_lifecycle(engine, helper, data):
    request, phase = data["request"], data["phase"]
    if phase == "addresses":
        addresses = sorted(helper.OWNED.local_addresses(helper.OWNED.execute))
        require(request["address"] in addresses, "controller inventory address is not present on the observed host")
        return {"changed": False, "addresses": addresses}
    if phase == "probe":
        current = Store(helper, request, data["helper"], data["units"])
        policy = current.read() if current.policy_path.exists() else {}
        return qualified_probes(request, policy)
    store = Store(helper, request, data["helper"], data["units"])
    if phase == "counters":
        current = store.read()
        store.validate(current)
        store.audit(current)
        return {"changed": False, "counters": counters(helper, request["profile"], {e["port"] for e in request["endpoints"]})}
    if phase == "install":
        proposed = data["policy"]
        store.validate(proposed)
        # Initial installation uses the explicitly supplied operator inputs;
        # ordinary service deployment never manufactures source confirmations.
        with store.lock():
            if store.policy_path.exists():
                current = store.read()
                store.validate(current)
                candidate = engine.install_union(current, proposed, store.profile)
            else:
                current = None
                candidate = proposed
            store.validate(candidate)
            helper.reconcile(candidate, "validate")
            store.persistence_preflight(candidate)
            store.prepare(candidate)
            store.write(candidate)
            applied = store.apply(candidate, request, "finish") or {}
            changed = current != candidate or store.changed_files or applied.get("changed", False)
        if store.profile == "mgt":
            command(["systemctl", "start", "skynet-mgt-firewall.service"])
            with store.lock():
                current = store.read()
                store.helper.reconcile(current)
                store.audit(current)
        return {"changed": changed, "helper_changed": store.changed_files, "families": [4, 6]}
    if not request["endpoints"] and not store.root.exists():
        if phase in {"finish", "remove"}:
            runtime_check(request["runtime"], "healthy" if phase == "finish" else "absent")
        return {"changed": False, "families": [4, 6]}
    if phase in {"inspect", "prepare_remove", "remove"} and request["action"] == "remove":
        require(
            store.policy_path.exists(), "installed policy is missing; inspect/repair its ownership before removing this protected service"
        )
    if phase == "inspect":
        current = store.read()
        store.validate(current)
        store.audit(current)
        for name, record in request["callers"].items():
            binding = record.get("binding")
            principal = current.get("principals", {}).get(name, {})
            if binding and principal:
                require(
                    not principal.get("future_account") or principal["future_account"] == binding.get("account"),
                    "caller account changed; reconcile that caller through its reviewed identity transition first",
                )
                require(
                    not principal.get("future_runtime") or principal["future_runtime"] == binding.get("runtime"),
                    "caller runtime changed; reconcile that caller through its reviewed transition first",
                )
        return {"changed": False, "families": [4, 6]}

    def runtime(expected):
        if isinstance(expected, tuple) and expected[0] == "obsolete_absent":
            for port in expected[1]:
                for family in ["-4", "-6"]:
                    require(
                        not command(["ss", family, "-H", "-lnt", "sport", "=", ":" + str(port)]).strip(),
                        "obsolete publication still has a listener; protection retained",
                    )
            legacy = request["profile"] == "workers" and store.read()["backend"] == "legacy"
            native = {} if legacy else json.loads(command(["nft", "--json", "list", "ruleset"]))
            require(
                not (set(expected[1]) & nat_publications(native, legacy=legacy)),
                "removed publication still has NAT rules; protection retained",
            )
            return
        if expected == "dependencies":
            if request["action"] == "remove":
                for dependent in request.get("dependents", []):
                    require(
                        dependent["hosts"] == [request["host"]],
                        "configured dependent on another host must be retired explicitly first: " + dependent["service"],
                    )
                    observed = runtime_check(dependent, "baseline")
                    require(not observed.get("running"), "active dependent must be retired explicitly first: " + dependent["service"])
            if request["profile"] == "workers":
                baseline = runtime_check(request["runtime"], "baseline")
                return {
                    "baseline_ports": [
                        int(value["HostPort"]) for values in (baseline.get("ports") or {}).values() for value in values or []
                    ]
                }
            return {}
        runtime_check(request["runtime"], expected)

    result = engine.transact(store, request, phase, data["token"], runtime)
    result["changed"] = result["changed"] or getattr(store, "changed_files", False)
    first_start = getattr(store, "was_new", False) or getattr(store, "baseline", {}).get("managed_services", {}).get(
        request["service"], {}
    ).get("failed_stage", False)
    if store.profile == "mgt" and phase == "stage" and first_start:
        # Start outside the writer lock: the boot guard takes that lock itself.
        # Only a new/failed first stage may activate it; existing operations
        # require an already active guard and never interrupt unrelated callers.
        command(["systemctl", "start", "skynet-mgt-firewall.service"])
        with store.lock():
            current = store.read()
            store.test(current, request, "stage")
            store.apply(current, request, "stage")
    if store.flash and getattr(store, "changed_files", False):
        # Do this after releasing the writer lock: stop-watch takes the same
        # lock and the old watcher may be waiting for it. No application stops.
        command(["/usr/bin/python3", str(store.root / "policy.py"), "stop-watch"])
        command(["/usr/bin/python3", str(store.root / "policy.py"), "start", "--config", str(store.policy_path)])
        require(helper.watching(), "replacement Unraid reconciler did not become active")
    return result
