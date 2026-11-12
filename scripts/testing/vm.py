#!/usr/bin/env python3
"""Serial disposable-VM controller. Provisioning and guest execution are separate commands.

prepare is offline. provision/retire require an approved allocation and a scoped
Proxmox API token in PROXMOX_VE_API_TOKEN. Test subprocesses receive neither.
Failure leaves the exact run and evidence in place; retirement is explicit.
"""

import argparse
import contextlib
import fcntl
import hashlib
import ipaddress
import json
import os
import re
import secrets
import shutil
import signal
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMAGES = json.loads((ROOT / "molecule/vm/images.json").read_text())
SUITES = ("rocky_node_exporter", "runtime_install", "application_lifecycle", "protected_network")
GUEST_PYTHON = "/opt/homelab-molecule-ansible/bin/python"
MAX_DISK_GB = 32  # Existing approved per-disk ceiling, not a minimum.


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write_json(path, data):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")
    path.chmod(0o600)


def allocation(path):
    value = json.loads(path.read_text())
    require(type(value.get("approved_disposable")) is bool, "Allocation requires an explicit boolean approval")
    require(re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", value["allocation_id"]), "Invalid allocation ID")
    endpoint = urllib.parse.urlsplit(value["endpoint"])
    require(endpoint.scheme == "https" and endpoint.hostname and not endpoint.username, "Use a TLS-verified API endpoint")
    require(not endpoint.query and not endpoint.fragment and endpoint.path in ("", "/"), "Use the API origin, without /api2/json")
    require(type(value.get("allow_nf_tables_alternatives", False)) is bool, "The disposable alternatives exception must be boolean")
    require(type(value.get("allow_image_preparation", False)) is bool, "Image preparation approval must be boolean")
    ids = value["vm_ids"]
    require(
        len(ids) == 2 and len(set(ids)) == 2 and all(type(i) is int and 100 <= i <= 999999999 for i in ids),
        "Allocate exactly two distinct VMIDs: stopped template and one running subject",
    )
    addresses = [ipaddress.IPv4Interface(a) for a in value["addresses"]]
    require(len(addresses) == 1, "Allocate exactly one IPv4 address")
    gateway = ipaddress.IPv4Address(value["gateway"])
    require(
        all(
            gateway in a.network
            and a.ip not in (gateway, a.network.network_address, a.network.broadcast_address)
            and gateway not in (a.network.network_address, a.network.broadcast_address)
            and not (a.ip.is_loopback or a.ip.is_multicast or a.ip.is_unspecified or a.ip.is_link_local)
            for a in addresses
        ),
        "Invalid guest/gateway allocation",
    )
    require(value["dns"] and all(ipaddress.ip_address(d) for d in value["dns"]), "Explicit DNS is required")
    for key in ("node", "bridge", "storage", "image_storage", "snippet_storage"):
        require(re.fullmatch(r"[a-zA-Z0-9_.-]+", value[key]), f"Invalid {key}")
    for platform, file_id in value.get("image_file_ids", {}).items():
        require(
            platform in IMAGES
            and isinstance(file_id, str)
            and re.fullmatch(re.escape(value["image_storage"]) + r":iso/[A-Za-z0-9_.-]+", file_id),
            "A cached image must be an explicit read-only ISO-store file ID",
        )
    return value


def guest_environment(run_dir):
    """Allowlist, rather than trying to enumerate every production credential."""
    home = run_dir / "guest-home"
    home.mkdir(exist_ok=True, mode=0o700)
    # Molecule's host/user socket name exceeds sockaddr_un limits under a long
    # private run path. Keep only its SSH sockets in a short, run-unique directory.
    control = Path("/tmp") / ("hm-" + run_dir.name)
    if control.exists():
        require(
            not control.is_symlink() and control.stat().st_uid == os.getuid() and control.stat().st_mode & 0o077 == 0,
            "Foreign SSH control directory; refusing reuse",
        )
    else:
        control.mkdir(mode=0o700)
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "ANSIBLE_INJECT_FACT_VARS": "false",
        "ANSIBLE_HOST_KEY_CHECKING": "true",
        "ANSIBLE_SSH_CONTROL_PATH_DIR": str(control),
        "ANSIBLE_CONFIG": str(run_dir / "ansible.cfg"),
        "ANSIBLE_HOME": str(home / ".ansible"),
        "ANSIBLE_LOCAL_TEMP": str(home / "tmp"),
        "ANSIBLE_LOG_PATH": str(run_dir / "guest-ansible.log"),
        "HOMELAB_MOLECULE_INVENTORY": str(run_dir / "inventory.yml"),
        "HOMELAB_MOLECULE_VARS": str(run_dir / "guest-vars.json"),
        "HOMELAB_MOLECULE_SECRET_FILE": str(run_dir / "synthetic-credential.json"),
        "ANSIBLE_COLLECTIONS_PATH": ":".join(
            [
                str(ROOT / "molecule/shared/collections"),
                str(ROOT / "ansible/collections"),
                str(Path.home() / ".local/share/homelab/collections"),
                str(Path.home() / ".ansible/collections"),
            ]
        ),
        "MOLECULE_EPHEMERAL_DIRECTORY": str(run_dir / "molecule-state"),
    }


def command(argv, directory, log, env, timeout=1800):
    start = time.monotonic()
    # No shell, inherited stdin or secret arguments. Logs stay private.
    with log.open("a", encoding="utf-8") as output:
        process = subprocess.Popen(
            argv, cwd=directory, env=env, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, start_new_session=True
        )
        try:
            code = process.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
            code = 124
    log.chmod(0o600)
    return code, round(time.monotonic() - start, 2)


class Proxmox:
    def __init__(self, config):
        self.config = config
        self.token = os.environ.get("PROXMOX_VE_API_TOKEN", "")
        require(self.token and "!" in self.token and "=" in self.token, "Supply a test-allocation-scoped PROXMOX_VE_API_TOKEN")
        self.context = ssl.create_default_context(cafile=config.get("ca_file"))

    def api(self, path, data=None, *, method=None):
        body = urllib.parse.urlencode(data, doseq=True).encode() if data is not None else None
        request = urllib.request.Request(
            self.config["endpoint"].rstrip("/") + "/api2/json/" + path,
            data=body,
            headers={"Authorization": "PVEAPIToken=" + self.token},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=30, context=self.context) as response:
                return json.load(response)["data"]
        except urllib.error.HTTPError as error:
            # Proxmox bodies may contain credentials; never echo them.
            raise ValueError(f"Proxmox request failed (HTTP {error.code})") from None

    def config_for(self, vm_id):
        return self.api(f"nodes/{self.config['node']}/qemu/{vm_id}/config")

    def ownership(self, manifest):
        present = {int(item["vmid"]) for item in self.api("cluster/resources?type=vm")}
        for role, vm_id in identities(manifest).items():
            if vm_id not in present:
                continue
            value = self.config_for(vm_id)
            require(
                value.get("name") == f"molecule-{manifest['id']}-{role}"
                and value.get("description") == f"homelab-molecule:{manifest['id']}:{role}"
                and set(value.get("tags", "").split(";")) == {"molecule", f"run-{manifest['id']}"},
                f"VMID {vm_id} ownership differs; refusing operation",
            )
            if role == "template":
                require(
                    value.get("template") == 1
                    and self.api(f"nodes/{self.config['node']}/qemu/{vm_id}/status/current").get("status") == "stopped",
                    "The run-owned image template must remain stopped",
                )
            for device, specification in value.items():
                if re.fullmatch(r"(?:scsi|sata|ide|virtio|efidisk|tpmstate|unused)[0-9]+", device):
                    volume = specification.split(",")[0]
                    require(
                        any(
                            volume.startswith(manifest["run"]["storage"] + f":{prefix}-{vm_id}-")
                            for prefix in (["vm", "base"] if role == "template" else ["vm"])
                        ),
                        f"VMID {vm_id} has a disk outside its allocation",
                    )


def identities(manifest):
    return {"template": manifest["run"]["template_id"], **{key: guest["vm_id"] for key, guest in manifest["run"]["guests"].items()}}


@contextlib.contextmanager
def locked(config):
    # Allocation-wide lock covers all runs on this controller. API existence
    # preflight additionally refuses collisions from other controllers.
    lock_dir = Path.home() / ".cache/homelab-molecule"
    lock_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (lock_dir / (config["allocation_id"] + ".lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def prepare(args):
    config = allocation(args.allocation)
    builder = getattr(args, "image_builder", False)
    require(
        not builder or (config.get("allow_image_preparation") is True and args.os == "ubuntu2604"),
        "Approve the disposable Ubuntu image builder explicitly",
    )
    prepared_image = prepared_fedora(args.state_root) if args.os == "fedora44" else None
    require(
        args.os != "fedora44" or prepared_image is not None or args.suite == "rocky_node_exporter",
        "Fedora Cloud bundles Podman. Run prepare-fedora-image first; never erase bundled runtimes to pass freshness checks",
    )
    image = IMAGES[args.os]
    if prepared_image:
        image = image | {
            "url": prepared_image["source"]["url"],
            "source": prepared_image["source"]["source"],
            "checksum": prepared_image["checksum"],
            "disk_gb": prepared_image["source"]["disk_gb"],
        }
    disk_gb = image["builder_disk_gb" if builder else "guest_disk_gb"]
    require(
        type(disk_gb) is int and image["disk_gb"] <= disk_gb <= MAX_DISK_GB,
        "Selected guest disk must fit the image template within the approved disk ceiling; shrinking is forbidden",
    )
    run_id = uuid.uuid4().hex
    directory = args.state_root.resolve() / run_id
    directory.mkdir(parents=True, mode=0o700)
    (directory / "evidence").mkdir(mode=0o700)
    run = {
        "id": run_id,
        **{key: config[key] for key in ("node", "bridge", "storage", "image_storage", "snippet_storage", "gateway", "dns", "ssh_host")},
        "template_id": config["vm_ids"][0],
        "image_file_id": None if prepared_image else config.get("image_file_ids", {}).get(args.os),
        "image": image | {"user": "molecule"},
        "disk_gb": disk_gb,
        "public_key": Path(config["public_key_path"]).expanduser().read_text().strip(),
        "python_requirements": guest_requirements(),
        "guests": {
            role: {"vm_id": config["vm_ids"][index + 1], "address": config["addresses"][index]} for index, role in enumerate(("subject",))
        },
    }
    if prepared_image:
        run["image_local_path"] = prepared_image["path"]
    require(run["public_key"].startswith(("ssh-ed25519 ", "ssh-rsa ", "ecdsa-sha2-")), "Supply a test SSH public key")
    manifest = {
        "id": run_id,
        "allocation": config,
        "os": args.os,
        "suite": args.suite,
        "order": args.order,
        "runtime": args.runtime,
        "run": run,
        "image_builder": builder,
        "prepared_image": prepared_image,
    }
    write_json(directory / "manifest.json", manifest)
    write_json(
        directory / "synthetic-credential.json", {"run_id": run_id, "credential": "molecule-" + run_id + "-" + secrets.token_hex(32)}
    )
    tofu_dir = directory / "tofu"
    shutil.copytree(ROOT / "molecule/vm/proxmox", tofu_dir)
    module_dir = tofu_dir / "cloudinit-vm"
    module_dir.mkdir()
    for source in (ROOT / "terraform/proxmox/modules/cloudinit-vm").glob("*.tf"):
        shutil.copy2(source, module_dir / source.name)
    # Give this guest a unique SSH host identity through authenticated cloud-init
    # delivery. No guest-exec capability or unverified keyscan is required.
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "molecule-" + run_id, "-f", str(directory / "guest-host-key")],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    write_json(
        tofu_dir / "run.auto.tfvars.json",
        {
            "run": run,
            "guest_ssh_host_key": {
                "private": (directory / "guest-host-key").read_text(),
                "public": (directory / "guest-host-key.pub").read_text().strip(),
            },
        },
    )
    write_json(
        directory / "guest-vars.json",
        {
            "molecule_vm_run_id": run_id,
            "molecule_vm_evidence_directory": str(directory / "evidence"),
            "molecule_vm_platform": args.os,
            "molecule_vm_suite": args.suite,
            "molecule_vm_prepared_image": prepared_image is not None,
            "molecule_vm_image_builder": builder,
            "molecule_vm_disk_gb": disk_gb,
            "molecule_vm_order": args.order,
            "molecule_vm_runtime": args.runtime,
            "molecule_vm_images": IMAGES,
            "molecule_vm_allow_nf_tables_alternatives": config.get("allow_nf_tables_alternatives", False),
            "molecule_vm_ipv6_prefix": f"fd{run_id[:2]}:{run_id[2:6]}:{run_id[6:10]}:",
            "docker_selinux_enable": image["selinux"],
            # Production opt-in for mixed-runtime bridge forwarding. Preserve the
            # role default; exercise the intended coexistence configuration here.
            "podman_docker_iptables_compatibility": args.suite != "rocky_node_exporter",
        },
    )
    (directory / "ansible.cfg").write_text(
        "[defaults]\ninject_facts_as_vars=false\nhost_key_checking=true\nprecedence=all_inventory,groups_inventory\n"
        f"roles_path={ROOT}/ansible/roles\naction_plugins={ROOT}/ansible/action_plugins\n"
        f"filter_plugins={ROOT}/ansible/filter_plugins:{ROOT}/ansible/roles/service_common/filter_plugins\n"
        f"collections_path={ROOT}/ansible/collections:{Path.home()}/.local/share/homelab/collections:{Path.home()}/.ansible/collections\n"
        "[inventory]\nenable_plugins=yaml,ini,host_list\n"
    )
    if not getattr(args, "quiet", False):
        print(directory)
    return directory


def image_recipe():
    return hashlib.sha256((ROOT / "molecule/vm/prepare-fedora.yml").read_bytes()).hexdigest()


def file_checksum(path, algorithm="sha256"):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def validate_prepared_image(value, state_root):
    """Derived images are private artifacts with explicit source/recipe provenance."""
    require(re.fullmatch(r"[a-f0-9]{32}", value["builder_id"]), "Invalid image builder identity")
    source = json.loads((ROOT / "molecule/vm/fedora-source.json").read_text())
    require(value["source"] == source and value["recipe"] == image_recipe(), "Prepared image source or recipe changed; rebuild it")
    require(
        value.get("virtual_size_bytes") == source["disk_gb"] * 1024**3,
        "Prepared image virtual size differs from the selected capacity",
    )
    path = Path(value["path"])
    require(path == state_root.resolve() / value["builder_id"] / "fedora44.qcow2", "Prepared image lies outside its builder run")
    require(
        not path.parent.is_symlink()
        and path.parent.stat().st_uid == os.getuid()
        and path.parent.stat().st_mode & 0o077 == 0
        and not path.is_symlink()
        and path.is_file(),
        "Prepared image must be a private owned artifact",
    )
    require(
        re.fullmatch(r"[a-f0-9]{64}", value["checksum"]) and file_checksum(path) == value["checksum"], "Prepared image checksum differs"
    )
    # QEMU QCOW2 header, big-endian bytes 24..31: virtual disk size.
    # Check the actual artifact as well as the builder's recorded qemu-img info.
    with path.open("rb") as stream:
        header = stream.read(32)
    require(
        len(header) == 32
        and header[:4] == b"QFI\xfb"
        and int.from_bytes(header[4:8], "big") in (2, 3)
        and int.from_bytes(header[24:32], "big") == value["virtual_size_bytes"],
        "Prepared image header differs from the selected virtual size",
    )
    return value


def prepared_fedora(state_root):
    index = state_root.resolve() / "fedora-image.json"
    if not index.exists():
        return None
    require(
        not index.is_symlink() and index.stat().st_uid == os.getuid() and index.stat().st_mode & 0o077 == 0,
        "Prepared image index must be private and owned",
    )
    return validate_prepared_image(json.loads(index.read_text()), state_root)


def prepare_fedora_image(args):
    require(
        allocation(args.allocation).get("allow_image_preparation") is True, "Approve image preparation in the disposable allocation first"
    )
    index = args.state_root.resolve() / "fedora-image.json"
    if index.exists() or index.is_symlink():
        require(
            not index.is_symlink() and index.stat().st_uid == os.getuid() and index.stat().st_mode & 0o077 == 0,
            "Prepared image index must be private and owned",
        )
    previous_index = index.read_bytes() if index.exists() else None
    if not args.rebuild and not args.resume_builder and prepared_fedora(args.state_root):
        print("The source, recipe and cached Fedora artifact are verified; no guest created")
        return
    directory = (
        args.resume_builder.resolve()
        if args.resume_builder
        else prepare(
            argparse.Namespace(
                **vars(args),
                os="ubuntu2604",
                suite="rocky_node_exporter",
                order="docker-first",
                runtime="rootless",
                image_builder=True,
                quiet=True,
            )
        )
    )
    manifest = load_run(directory)
    require(
        manifest.get("image_builder") is True
        and manifest["os"] == "ubuntu2604"
        and manifest["allocation"] == allocation(args.allocation)
        and directory.parent == args.state_root.resolve(),
        "Resume only the exact owned image builder in this allocation and state root",
    )
    attempt = 1
    while (directory / ("image-result" + (f"-{attempt}" if attempt > 1 else "") + ".json")).exists():
        attempt += 1
    suffix = f"-{attempt}" if attempt > 1 else ""
    log = directory / f"image-build{suffix}.log"
    print(f"Image builder: {directory}", flush=True)
    try:
        provision(directory, manifest)
        variables = json.loads((directory / "guest-vars.json").read_text()) | {
            "molecule_vm_fedora_source": json.loads((ROOT / "molecule/vm/fedora-source.json").read_text()),
            "molecule_vm_image_output": str(directory / "fedora44.qcow2"),
        }
        if (directory / "image-vars.json").exists():
            require(json.loads((directory / "image-vars.json").read_text()) == variables, "Builder inputs changed; create a fresh builder")
        else:
            write_json(directory / "image-vars.json", variables)
        recipe = image_recipe()
        shutil.copy2(ROOT / "molecule/vm/prepare-fedora.yml", directory / f"image-recipe{suffix}.yml")
        code, duration = command(
            [
                "ansible-playbook",
                "-i",
                str(directory / "inventory.yml"),
                str(ROOT / "molecule/vm/prepare-fedora.yml"),
                "-e",
                "@" + str(directory / "image-vars.json"),
            ],
            ROOT,
            log,
            guest_environment(directory),
            7200,
        )
        write_json(directory / f"image-result{suffix}.json", {"id": manifest["id"], "exit_code": code, "duration_seconds": duration})
        require(code == 0, f"Image preparation failed; inspect {log.name} and retain the builder for diagnosis")
        require(image_recipe() == recipe, "Image recipe changed during execution; retain evidence and rebuild")
        evidence = json.loads((directory / "evidence/prepared-image.json").read_text())
        provenance = {
            "builder_id": manifest["id"],
            "attempt": attempt,
            "source": variables["molecule_vm_fedora_source"],
            "recipe": recipe,
            "path": str(directory / "fedora44.qcow2"),
            "checksum": evidence["checksum"],
            "packages": evidence["packages"],
            "virtual_size_bytes": evidence["virtual_size_bytes"],
        }
        validate_prepared_image(provenance, args.state_root)
        # Publish only after the builder's retirement is confirmed. A failed
        # retirement still counts against the one-guest budget.
        retire(directory, manifest, manifest["id"])
        require(
            (index.read_bytes() if index.exists() else None) == previous_index, "Image index changed during the build; refusing overwrite"
        )
        new_index = directory / "image-provenance.json"
        write_json(new_index, provenance)
        if previous_index is not None:
            (directory / "previous-image-index.json").write_bytes(previous_index)
            (directory / "previous-image-index.json").chmod(0o600)
        shutil.copy2(new_index, directory / "image-index.pending")
        (directory / "image-index.pending").replace(index)
        print(f"Verified Fedora image cached; builder retired: {directory}", flush=True)
    except (ValueError, OSError, subprocess.SubprocessError):
        if (directory / "retired.json").exists():
            print(f"Builder retirement confirmed; inspect unpublished image evidence in {directory}", file=sys.stderr)
        else:
            # Never hide the original build/retirement failure.
            with contextlib.suppress(ValueError, OSError, subprocess.SubprocessError):
                diagnose(directory, manifest)
            print(
                f"Retire the exact retained builder: {sys.executable} scripts/testing/vm.py retire {directory} --confirm-run {directory.name}",
                file=sys.stderr,
            )
        raise


def guest_requirements():
    """Use existing controller pins for the guest modules, without secret-store clients."""
    wanted = {"docker", "jsondiff", "pyyaml", "requests"}
    pins = [
        line
        for line in (ROOT / "ansible/requirements.txt").read_text().splitlines()
        if re.fullmatch(r"(?:docker|jsondiff|pyyaml|requests)==[A-Za-z0-9.!+_-]+", line, re.IGNORECASE)
    ]
    require({line.partition("==")[0].lower() for line in pins} == wanted, "Missing pinned guest Python module requirements")
    return "\n".join(pins) + "\n"


def load_run(directory, retirement=False):
    require(not directory.is_symlink() and directory.stat().st_mode & 0o077 == 0, "Run directory must be private and not a symlink")
    manifest = json.loads((directory / "manifest.json").read_text())
    require(re.fullmatch(r"[a-f0-9]{32}", manifest["id"]) and directory.name == manifest["id"], "Invalid run identity")
    require(manifest["run"]["id"] == manifest["id"], "Run identity mismatch")
    require(manifest["allocation"]["approved_disposable"] is True, "Allocation is not explicitly approved")
    if not retirement:
        require(not (directory / "retired.json").exists(), "This run was retired; prepare a new disposable run")
        require(manifest["suite"] in SUITES and manifest["os"] in IMAGES, "Unknown scenario or platform")
        expected_image = IMAGES[manifest["os"]] | {"user": "molecule"}
        if manifest.get("prepared_image"):
            artifact = validate_prepared_image(manifest["prepared_image"], directory.parent)
            require(
                manifest["os"] == "fedora44" and manifest["run"].get("image_local_path") == artifact["path"], "Unexpected prepared image"
            )
            expected_image |= {
                "url": artifact["source"]["url"],
                "source": artifact["source"]["source"],
                "checksum": artifact["checksum"],
                "disk_gb": artifact["source"]["disk_gb"],
            }
        require(manifest["run"]["image"] == expected_image, "Image pin changed since preparation; make a new run")
        require(
            manifest["run"].get("disk_gb") == expected_image["builder_disk_gb" if manifest.get("image_builder") else "guest_disk_gb"],
            "Selected disk capacity changed since preparation; make a new run, never resize an existing guest",
        )
    # Old run manifests retain their original 32 GiB capacity for retirement.
    # They cannot resume provisioning through the new, differently sized root.
    disk_gb = manifest["run"].get("disk_gb", MAX_DISK_GB)
    require(
        type(disk_gb) is int and manifest["run"]["image"]["disk_gb"] <= disk_gb <= MAX_DISK_GB,
        "Run disk capacity is outside the image and approved disk bounds",
    )
    require(
        identities(manifest) == dict(zip(("template", "subject"), manifest["allocation"]["vm_ids"], strict=True)),
        "Resource IDs differ from the approved allocation",
    )
    require(
        [g["address"] for g in manifest["run"]["guests"].values()] == manifest["allocation"]["addresses"],
        "Guest addresses differ from the approved allocation",
    )
    require(
        all(
            manifest["run"][key] == manifest["allocation"][key]
            for key in ("node", "bridge", "storage", "image_storage", "snippet_storage", "gateway", "dns", "ssh_host")
        )
        and manifest["run"].get("image_file_id")
        == (None if manifest.get("prepared_image") else manifest["allocation"].get("image_file_ids", {}).get(manifest["os"])),
        "Run resources differ from the approved allocation",
    )
    return manifest


def provisioning_environment(manifest):
    # Infrastructure tokens never go in tfvars, manifests or guest subprocesses.
    # Keep an operator's trusted CLI mirror configuration, while refusing state,
    # workspace and variable overrides. The readonly lock still verifies pins.
    return {
        key: value
        for key, value in os.environ.items()
        if key == "TF_CLI_CONFIG_FILE" or not key.startswith(("ANSIBLE_", "HOMELAB_", "TF_"))
    } | {
        "PROXMOX_VE_ENDPOINT": manifest["allocation"]["endpoint"],
        "TF_IN_AUTOMATION": "1",
        "TF_INPUT": "0",
        "SSL_CERT_FILE": manifest["allocation"].get("ca_file", os.environ.get("SSL_CERT_FILE", "/etc/ssl/certs/ca-certificates.crt")),
    }


def inventory(manifest, directory):
    known = directory / "known_hosts"
    children = {}
    for role, guest in manifest["run"]["guests"].items():
        children["molecule_guests" if role == "subject" else "molecule_peers"] = {
            "hosts": {
                role: {
                    "ansible_host": str(ipaddress.ip_interface(guest["address"]).ip),
                    "local_ip": str(ipaddress.ip_interface(guest["address"]).ip),
                    "ansible_user": "molecule",
                    "ansible_connection": "ssh",
                    "ansible_port": 22,
                    "ansible_python_interpreter": GUEST_PYTHON,
                    "molecule_vm_disposable": True,
                    "molecule_node_exporter_disposable": True,
                    "docker_swarm_node_labels": {"docker_services_host": "molecule-" + manifest["id"][:12], "ansible_host": role},
                    "ansible_ssh_private_key_file": str(Path(manifest["allocation"]["private_key_path"]).expanduser()),
                    "ansible_ssh_common_args": (
                        f"-F /dev/null -o IdentitiesOnly=yes -o UserKnownHostsFile={known} "
                        "-o GlobalKnownHostsFile=/dev/null -o StrictHostKeyChecking=yes"
                    ),
                }
            }
        }
    for group in (
        "tags_skynet",
        "tags_docker",
        "tags_docker_install",
        "tags_podman",
        "tags_podman_install",
        "tags_node_exporter",
        "molecule_node_exporter",
        "services_controller",
        "services_storage",
    ):
        children[group] = {"hosts": {"subject": {}}}
    # The peer is only a traffic source; never a catalogue dispatch host.
    return {
        "all": {
            "children": children,
            "vars": {
                "services_controller_inventory_group": "services_controller",
                "services_storage_inventory_group": "services_storage",
                "services_plex_host": "subject",
                "services_log_root": "/var/log/molecule",
                "services_public_zone": "example.invalid",
                "services_internal_zone": "test.invalid",
                "services_lan_cidr": str(ipaddress.ip_interface(manifest["run"]["guests"]["subject"]["address"]).network),
                "services_private_https_port": 18443,
                "container_host_puid": "1000",
                "container_host_pgid": "1000",
                "container_host_appdata_root": "/opt/molecule-apps",
                "container_host_data_root": "/var/lib/molecule-data",
                "timezone": "Etc/UTC",
                "services_controller_host": "subject",
                "services_storage_host": "subject",
            },
        }
    }


def provision(directory, manifest):
    started = time.monotonic()
    config = manifest["allocation"]
    scratch = Path(os.environ.get("TMPDIR") or "/tmp")
    reserve = 64 * 1024 * 1024
    upload_bytes = Path(manifest["run"]["image_local_path"]).stat().st_size if manifest["run"].get("image_local_path") else 0
    require(
        shutil.disk_usage(directory).free >= reserve and shutil.disk_usage(scratch).free >= upload_bytes + reserve,
        "Insufficient controller state/upload space; use a disk-backed state root and TMPDIR before provisioning",
    )
    # The pinned provider rejects changed SSH keys but enrolls unknown hosts.
    # Prove strict trust against the same user known_hosts file before it can
    # upload sensitive cloud-init data, including when no cached image is used.
    verify_remote_files([], manifest, allow_missing=False)
    api = Proxmox(config)
    with locked(config):
        existing = {int(item["vmid"]) for item in api.api("cluster/resources?type=vm")}
        occupied = existing.intersection(identities(manifest).values())
        if occupied:
            state = json.loads(
                subprocess.check_output(
                    ["tofu", "show", "-json"], cwd=directory / "tofu", env=provisioning_environment(manifest), timeout=60
                )
            )
            known_roles = check_state(state, manifest)
            require(
                occupied <= {identities(manifest)[role] for role in known_roles},
                "Allocated VMID exists outside this run's state; never adopt or overwrite it",
            )
            api.ownership(manifest)
        if manifest["run"].get("image_file_id"):
            image = manifest["run"]["image"]
            verify_remote_files([[manifest["run"]["image_file_id"], image["algorithm"], image["checksum"]]], manifest, allow_missing=False)
        env = provisioning_environment(manifest)
        for argv in (["tofu", "init", "-input=false", "-lockfile=readonly"], ["tofu", "plan", "-out=run.tfplan", "-input=false"]):
            code, _ = command(argv, directory / "tofu", directory / "provision.log", env)
            require(code == 0, "Provisioning failed; retain run state and inspect private provision.log")
        plan_file = directory / "tofu/run.tfplan"
        plan_file.chmod(0o600)
        plan = json.loads(subprocess.check_output(["tofu", "show", "-json", str(plan_file)], cwd=directory / "tofu", env=env, timeout=60))
        check_plan(plan, manifest)
        code, _ = command(["tofu", "apply", "-input=false", str(plan_file)], directory / "tofu", directory / "provision.log", env)
        require(code == 0, "Provisioning failed; retain run state and inspect private provision.log")
        api.ownership(manifest)
        state = json.loads(subprocess.check_output(["tofu", "show", "-json"], cwd=directory / "tofu", env=env, timeout=60))
        check_state(state, manifest)
        verify_files(state, manifest)
        keys = []
        for guest in manifest["run"]["guests"].values():
            keys.append(str(ipaddress.ip_interface(guest["address"]).ip) + " " + (directory / "guest-host-key.pub").read_text().strip())
        expected_keys = "\n".join(keys) + "\n"
        known_hosts = directory / "known_hosts"
        if known_hosts.exists():
            require(known_hosts.read_text() == expected_keys, "Existing host-key trust differs; refusing overwrite")
        else:
            known_hosts.write_text(expected_keys)
            known_hosts.chmod(0o600)
        inventory_file = directory / "inventory.yml"
        if inventory_file.exists():
            require(
                json.loads(inventory_file.read_text()) == inventory(manifest, directory), "Existing inventory differs; refusing overwrite"
            )
        else:
            write_json(inventory_file, inventory(manifest, directory))  # JSON is a YAML subset.
        code, _ = command(
            [
                "ansible-playbook",
                "-i",
                str(directory / "inventory.yml"),
                str(ROOT / "molecule/shared/ready.yml"),
                "-e",
                "@" + str(directory / "guest-vars.json"),
            ],
            ROOT,
            directory / "ready.log",
            guest_environment(directory),
            900,
        )
        require(code == 0, "SSH/cloud-init readiness failed; retain the run for diagnosis")
        if not (directory / "provisioned.json").exists():
            write_json(directory / "provisioned.json", {"id": manifest["id"], "duration_seconds": round(time.monotonic() - started, 2)})


def source_state():
    """Fingerprint executable inputs, including unstaged work but excluding docs."""
    paths = (
        subprocess.check_output(
            [
                "git",
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
                "--",
                ".config/molecule",
                "ansible",
                "molecule",
                "scripts/testing",
                "terraform/proxmox/modules/cloudinit-vm",
            ],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    digest = hashlib.sha256()
    for name in sorted(set(paths) - {""}):
        path = ROOT / name
        if path.suffix == ".md":
            continue
        digest.update(name.encode() + b"\0")
        digest.update(b"file\0" + path.read_bytes() if path.is_file() else b"missing\0")
        digest.update(b"\0")
    return {"revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "sha256": digest.hexdigest()}


def test(directory, manifest):
    require(not manifest.get("image_builder"), "An image builder cannot be claimed as Molecule acceptance")
    require(json.loads((directory / "provisioned.json").read_text())["id"] == manifest["id"], "Provision this run first")
    require(not (directory / "result.json").exists(), "A fresh-host test needs a new run/VM, not reused retained data")
    env = guest_environment(directory)
    providers = subprocess.run(
        ["ansible-doc", "--type", "lookup", "--list_files", "infisical.vault"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    selected = [line.split() for line in providers.stdout.splitlines() if line.startswith("infisical.vault.read_secrets ")]
    expected = ROOT / "molecule/shared/collections/ansible_collections/infisical/vault/plugins/lookup/read_secrets.py"
    require(
        providers.returncode == 0 and len(selected) == 1 and Path(selected[0][-1]).resolve() == expected,
        "Synthetic provider did not resolve to the isolated fixture; refusing any secret lookup",
    )
    # Molecule must run on a controller without management credentials as well as
    # receiving a clean child environment. Never print inherited credentials.
    source_before = source_state()
    code, duration = command(
        ["molecule", "test", "-s", manifest["suite"]], ROOT, directory / "molecule.log", guest_environment(directory), 5400
    )
    source_after = source_state()
    molecule_code = code
    if source_before != source_after and code == 0:
        code = 125  # A passing command against changing sources is not acceptance.
    # Molecule can prune its ephemeral directory even after a failed test.
    # Collect bounded evidence in the run directory before any VM retirement;
    # a diagnostic failure must never hide or replace the scenario result.
    diagnostic_error = None
    try:
        diagnose(directory, manifest)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        diagnostic_error = type(error).__name__
    write_json(
        directory / "result.json",
        {
            "id": manifest["id"],
            "os": manifest["os"],
            "image": manifest["run"]["image"],
            "prepared_image": (
                {key: value for key, value in manifest["prepared_image"].items() if key != "path"}
                if manifest.get("prepared_image")
                else None
            ),
            "suite": manifest["suite"],
            "order": manifest["order"],
            "runtime": manifest["runtime"],
            "exit_code": code,
            "molecule_exit_code": molecule_code,
            "source_before": source_before,
            "source_after": source_after,
            "duration_seconds": duration,
            "diagnostics": "collected" if diagnostic_error is None else diagnostic_error,
        },
    )
    require(
        code == 0,
        "Molecule failed or its executable inputs changed; diagnostics and the VM are retained. Retirement is a separate explicit command",
    )


def diagnose(directory, manifest):
    evidence = directory / "evidence"
    evidence.mkdir(exist_ok=True, mode=0o700)
    code, _ = command(
        [
            "ansible-playbook",
            "-i",
            str(directory / "inventory.yml"),
            str(ROOT / "molecule/shared/diagnostics.yml"),
            "-e",
            "@" + str(directory / "guest-vars.json"),
        ],
        ROOT,
        directory / "diagnostics.log",
        guest_environment(directory),
        180,
    )
    require(code == 0, "Diagnostic collection failed; retain the run and inspect diagnostics.log")


def retire_orphan_snippets(directory, manifest, api, state):
    """Recover only byte-verified planned snippets absent from partial local state."""
    plan_path = directory / "tofu/run.tfplan"
    if not plan_path.exists():
        return
    plan = json.loads(
        subprocess.check_output(
            ["tofu", "show", "-json", str(plan_path)],
            cwd=directory / "tofu",
            env=provisioning_environment(manifest),
            timeout=60,
        )
    )
    check_plan(plan, manifest)

    def file_ids(module):
        return {
            resource["values"].get("id")
            for resource in module.get("resources", [])
            if resource["type"] == "proxmox_virtual_environment_file"
        } | set().union(*(file_ids(child) for child in module.get("child_modules", [])))

    declared = file_ids(state.get("values", {}).get("root_module", {}))
    run = manifest["run"]
    content_path = f"nodes/{run['node']}/storage/{run['snippet_storage']}/content"
    present = {item.get("volid") for item in api.api(content_path)}
    for change in plan.get("resource_changes", []):
        value = change["change"].get("after") or {}
        if (
            change["type"] != "proxmox_virtual_environment_file"
            or change["change"]["actions"] != ["create"]
            or value.get("content_type") != "snippets"
        ):
            continue
        source = value["source_raw"][0]
        volume = run["snippet_storage"] + ":snippets/" + source["file_name"]
        if volume in declared or volume not in present:
            continue
        digest = hashlib.sha256(source["data"].encode()).hexdigest()
        verify_remote_files([[volume, "sha256", digest]], manifest, allow_missing=False)
        receipt = directory / "orphan-retirement.log"
        with receipt.open("a") as stream:
            stream.write(json.dumps({"file": volume, "sha256": digest, "phase": "verified"}) + "\n")
        receipt.chmod(0o600)
        api.api(content_path + "/" + urllib.parse.quote(volume, safe=""), method="DELETE")
        deadline = time.monotonic() + 60
        while volume in {item.get("volid") for item in api.api(content_path)}:
            require(time.monotonic() < deadline, "Orphan snippet retirement is unconfirmed: " + volume)
            time.sleep(1)
        with receipt.open("a") as stream:
            stream.write(json.dumps({"file": volume, "phase": "removed"}) + "\n")


def stop_retiring_guests(api, manifest, roles):
    """Bound shutdown of verified state-owned guests before destroying their disks."""
    api.ownership(manifest)
    present = {int(item["vmid"]) for item in api.api("cluster/resources?type=vm")}
    for role in sorted(roles):
        vm_id = identities(manifest)[role]
        if vm_id not in present:
            continue
        path = f"nodes/{manifest['run']['node']}/qemu/{vm_id}/status"
        if api.api(path + "/current")["status"] == "stopped":
            continue
        # Retirement explicitly destroys this disposable guest. Abort only its
        # pending graceful shutdown, without bypassing unrelated configuration
        # locks or waiting for an unresponsive guest agent.
        api.api(path + "/stop", {"overrule-shutdown": 1})
        deadline = time.monotonic() + 60
        while api.api(path + "/current")["status"] != "stopped":
            require(time.monotonic() < deadline, f"Retirement power-off is unconfirmed for owned VMID {vm_id}")
            time.sleep(1)


def retire(directory, manifest, confirmation):
    started = time.monotonic()
    require(confirmation == manifest["id"], "Retirement requires the exact --confirm-run ID")
    api = Proxmox(manifest["allocation"])
    with locked(manifest["allocation"]):
        # Refresh and compare every VM, never a prefix query or wildcard delete.
        api.ownership(manifest)
        state = json.loads(
            subprocess.check_output(["tofu", "show", "-json"], cwd=directory / "tofu", env=provisioning_environment(manifest), timeout=60)
        )
        roles = check_state(state, manifest)
        verify_files(state, manifest)
        stop_retiring_guests(api, manifest, roles)
        code, _ = command(
            ["tofu", "destroy", "-auto-approve", "-input=false"],
            directory / "tofu",
            directory / "retire.log",
            provisioning_environment(manifest),
        )
        remaining_vms = {int(item["vmid"]) for item in api.api("cluster/resources?type=vm")}.intersection(identities(manifest).values())
        if code == 0 and not remaining_vms:
            retire_orphan_snippets(directory, manifest, api, state)
        survivors = ["VMID " + str(vmid) for vmid in sorted(remaining_vms)]
        for storage in {manifest["run"]["storage"], manifest["run"]["image_storage"], manifest["run"]["snippet_storage"]}:
            for item in api.api(f"nodes/{manifest['run']['node']}/storage/{storage}/content"):
                volume = item.get("volid", "")
                if item.get("vmid") in identities(manifest).values() or volume in {
                    f"{manifest['run']['image_storage']}:iso/molecule-{manifest['id']}.img",
                    f"{manifest['run']['snippet_storage']}:snippets/molecule-{manifest['id']}-bootstrap.yaml",
                    f"{manifest['run']['snippet_storage']}:snippets/molecule-{manifest['id']}-network.yaml",
                }:
                    survivors.append(volume)
        require(
            code == 0 and not survivors,
            "Retirement is unconfirmed; observed surviving resources: "
            + (", ".join(survivors) or "none")
            + ("; provider destruction failed, retain state for recovery" if code else ""),
        )
        marker = directory / "retired.json"
        if marker.exists():
            require(json.loads(marker.read_text())["id"] == manifest["id"], "Retirement marker belongs to another run")
        else:
            write_json(marker, {"id": manifest["id"], "duration_seconds": round(time.monotonic() - started, 2)})


def verify_files(state, manifest):
    """Verify exact run-owned image/snippet bytes over the trusted node SSH channel."""
    files = []
    for resource in state.get("values", {}).get("root_module", {}).get("resources", []):
        value = resource["values"]
        if resource["type"] == "proxmox_download_file":
            files.append([value["id"], manifest["run"]["image"]["algorithm"], manifest["run"]["image"]["checksum"]])
        elif resource["type"] == "proxmox_virtual_environment_file":
            checksum = (
                manifest["run"]["image"]["checksum"]
                if value.get("content_type") == "iso"
                else hashlib.sha256(value["source_raw"][0]["data"].encode()).hexdigest()
            )
            files.append([value["id"], "sha256", checksum])
    verify_remote_files(files, manifest, allow_missing=True)


def verify_remote_files(files, manifest, allow_missing):
    payload = """import hashlib,json,stat,subprocess
from pathlib import Path
files = FILES
for volume,algorithm,expected in files:
    path = subprocess.check_output(['pvesm','path',volume],text=True).strip()
    source = Path(path)
    if not source.exists():
        if ALLOW_MISSING: continue  # Partial retirement may already have removed it.
        raise SystemExit(13)
    if volume.endswith('-bootstrap.yaml'):
        metadata = source.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) != 0o600:
            raise SystemExit(14)
    digest=hashlib.new(algorithm)
    with source.open('rb') as stream:
        while block:=stream.read(1024*1024): digest.update(block)
    if digest.hexdigest()!=expected: raise SystemExit(12)
print('Trusted node SSH and requested file checks verified')
""".replace("FILES", repr(files), 1).replace("ALLOW_MISSING", repr(allow_missing))
    config = manifest["allocation"]
    result = subprocess.run(
        [
            "ssh",
            "-F",
            "/dev/null",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "UserKnownHostsFile=" + str(Path.home() / ".ssh/known_hosts"),
            "-o",
            "GlobalKnownHostsFile=/dev/null",
            "-o",
            "ConnectTimeout=10",
            "-i",
            str(Path(config.get("node_private_key_path", config["private_key_path"])).expanduser()),
            "root@" + config["ssh_host"],
            "python3",
            "-",
        ],
        input=payload,
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    require(
        result.returncode == 0,
        f"Trusted node SSH or requested file verification failed (exit {result.returncode}). "
        "Check the approved node key in ~/.ssh/known_hosts, SSH authentication and the selected image/snippet bytes; "
        "no provider mutation is authorized.",
    )


def check_plan(plan, manifest):
    """Refuse allocation, network or budget expansion before applying a saved plan."""
    expressions = {
        resource["address"]: resource.get("expressions", {})
        for resource in plan.get("configuration", {}).get("root_module", {}).get("resources", [])
    }
    for change in plan.get("resource_changes", []):
        require(change.get("mode") == "managed", "Unexpected data/provider access in disposable plan")
        value = change["change"].get("after") or change["change"].get("before")
        if not value:
            continue
        check_state({"values": {"root_module": {"resources": [{"type": change["type"], "values": value}]}}}, manifest, planned=True)
        if change["type"] == "proxmox_virtual_environment_vm":
            if value["vm_id"] == manifest["run"]["template_id"]:
                # bpg omits started from a template's planned values even when
                # explicitly configured. Require the literal false setting;
                # ownership() also checks the resulting stopped state remotely.
                stopped = value.get("started") is False or (
                    value.get("started") is None
                    and expressions.get(change["address"], {}).get("started", {}).get("constant_value") is False
                )
                require(
                    value.get("template") is True and stopped and value.get("on_boot") is False,
                    "The allocation permits only a stopped template alongside one running guest",
                )
            else:
                require(value.get("template") is False and value.get("on_boot") is False, "Unexpected guest lifecycle expansion")
                require(
                    len(value.get("clone", [])) == 1
                    and value["clone"][0]["vm_id"] == manifest["run"]["template_id"]
                    and value["clone"][0]["full"] is True
                    # bpg normalizes an unset source node to "" after creation.
                    and value["clone"][0].get("node_name") in (None, "", manifest["run"]["node"]),
                    "Guest must clone only this run's stopped image template",
                )
                initialization = value.get("initialization", [])
                guest = next(guest for guest in manifest["run"]["guests"].values() if guest["vm_id"] == value["vm_id"])
                network_file = (
                    f"{manifest['run']['snippet_storage']}:snippets/molecule-{manifest['id']}-network.yaml"
                    if manifest["os"] == "ubuntu2604"
                    else None
                )
                require(
                    len(initialization) == 1
                    and initialization[0]["datastore_id"] == manifest["run"]["storage"]
                    and initialization[0]["dns"] == [{"domain": "", "servers": manifest["run"]["dns"]}]
                    and initialization[0].get("network_data_file_id") == network_file
                    and initialization[0]["ip_config"]
                    == (
                        []
                        if network_file
                        else [{"ipv4": [{"address": guest["address"], "gateway": manifest["run"]["gateway"]}], "ipv6": []}]
                    ),
                    "Plan changes the approved guest address, gateway, DNS or cloud-init storage",
                )
            require(
                0 < value["cpu"][0]["cores"] <= 2
                and value["cpu"][0].get("sockets", 1) == 1
                and 0 < value["memory"][0]["dedicated"] <= 2048,
                "Plan exceeds the one-guest CPU/RAM budget",
            )
            require(
                len(value["network_device"]) == 1 and value["network_device"][0]["bridge"] == manifest["run"]["bridge"],
                "Plan changes the approved guest network",
            )
            require(
                len(value["disk"]) == 1
                and all(
                    disk["datastore_id"] == manifest["run"]["storage"]
                    and disk["size"]
                    == (
                        manifest["run"]["image"]["disk_gb"]
                        if value["vm_id"] == manifest["run"]["template_id"]
                        else manifest["run"].get("disk_gb", MAX_DISK_GB)
                    )
                    and 0 < disk["size"] <= MAX_DISK_GB
                    for disk in value["disk"]
                ),
                "Plan exceeds approved disk storage or size",
            )


def network_data(manifest):
    """Exact Ubuntu allocation without renaming an already active initrd link."""
    run = manifest["run"]
    return {
        "version": 2,
        "ethernets": {
            "ens18": {
                "match": {"name": "ens18"},
                "dhcp4": False,
                "addresses": [run["guests"]["subject"]["address"]],
                "routes": [{"to": "default", "via": run["gateway"]}],
                "nameservers": {"addresses": run["dns"]},
            }
        },
    }


def check_state(state, manifest, planned=False):
    seen = set()

    def visit(module):
        for resource in module.get("resources", []):
            values = resource["values"]
            if resource["type"] == "proxmox_virtual_environment_vm":
                role = next((r for r, i in identities(manifest).items() if str(i) == str(values["vm_id"])), None)
                require(
                    role
                    and values.get("node_name") == manifest["run"]["node"]
                    and values["name"] == f"molecule-{manifest['id']}-{role}"
                    and values["description"] == f"homelab-molecule:{manifest['id']}:{role}",
                    "State contains a foreign VM",
                )
                seen.add(role)
            elif resource["type"] in ("proxmox_download_file", "proxmox_virtual_environment_file"):
                upload = resource["type"] == "proxmox_virtual_environment_file" and values.get("content_type") == "iso"
                image = resource["type"] == "proxmox_download_file" or upload
                expected_names = {f"molecule-{manifest['id']}.img"} if image else {f"molecule-{manifest['id']}-bootstrap.yaml"}
                if not image and manifest["os"] == "ubuntu2604":
                    expected_names.add(f"molecule-{manifest['id']}-network.yaml")
                storage = manifest["run"]["image_storage" if image else "snippet_storage"]
                source = (values.get("source_file" if upload else "source_raw") or [{}])[0]
                name = values.get("file_name") if image and not upload else source.get("file_name")
                if upload:
                    require(
                        manifest.get("prepared_image") and source.get("path") == manifest["run"].get("image_local_path"),
                        "Foreign uploaded image in state",
                    )
                require(
                    name in expected_names
                    and values.get("node_name") == manifest["run"]["node"]
                    and values.get("datastore_id") == storage
                    and (planned or values.get("id") == storage + (":iso/" if image else ":snippets/") + name),
                    "Foreign file in state",
                )
                if planned:
                    require(values.get("overwrite") is False, "Run-owned file uploads must refuse adoption or overwrite")
                    if name.endswith("-bootstrap.yaml"):
                        require(values.get("file_mode") in ("0600", "600"), "Private bootstrap must be root-only before upload")
                if not image and name.endswith("-network.yaml"):
                    require(
                        json.loads(source["data"]) == network_data(manifest), "Custom network data differs from the approved allocation"
                    )
            else:
                raise ValueError("Unknown resource in test state; refusing retirement")
        for child in module.get("child_modules", []):
            visit(child)

    visit(state.get("values", {}).get("root_module", {}))
    require(seen <= set(identities(manifest)), "State contains a foreign VM")
    return seen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("prepare", help="Offline: write a private run, without providers or API calls")
    create.add_argument("--allocation", type=Path, required=True)
    create.add_argument("--state-root", type=Path, required=True)
    create.add_argument("--os", choices=IMAGES, required=True)
    create.add_argument("--suite", choices=SUITES, required=True)
    create.add_argument("--order", choices=("docker-first", "podman-first"), default="docker-first")
    create.add_argument("--runtime", choices=("compose", "swarm", "rootful", "rootless"), default="rootless")
    build = sub.add_parser("prepare-fedora-image", help="Approved disposable Ubuntu builder; cache a runtime-free cloud-init image")
    build.add_argument("--allocation", type=Path, required=True)
    build.add_argument("--state-root", type=Path, required=True)
    build.add_argument("--rebuild", action="store_true", help="Build a new image and retain the previous artifact/provenance")
    build.add_argument("--resume-builder", type=Path, help="Retry only an owned builder whose source image has not yet been modified")
    for action in ("provision", "test", "diagnose", "retire"):
        command_parser = sub.add_parser(action)
        command_parser.add_argument("run", type=Path)
        if action == "retire":
            command_parser.add_argument("--confirm-run", required=True)
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            prepare(args)
        elif args.action == "prepare-fedora-image":
            prepare_fedora_image(args)
        else:
            directory = args.run.resolve()
            manifest = load_run(directory, retirement=args.action == "retire")
            if args.action == "provision":
                provision(directory, manifest)
            elif args.action == "test":
                test(directory, manifest)
            elif args.action == "diagnose":
                diagnose(directory, manifest)
            else:
                retire(directory, manifest, args.confirm_run)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        # Exceptions from HTTP, commands and guest payloads must not dump tokens.
        print(
            f"VM controller stopped: {type(error).__name__}: {error if isinstance(error, ValueError) else 'inspect the private run log'}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
