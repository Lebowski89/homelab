"""Run rendered NIC scripts against fake hardware, ethtool and service commands."""

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from ansible.plugins.filter.core import FilterModule
from jinja2 import Environment, StrictUndefined

REPO = Path(__file__).resolve().parents[2]
TEMPLATES = REPO / "ansible/roles/system/templates"
pytestmark = pytest.mark.integration


def render(name, interfaces):
    env = Environment(undefined=StrictUndefined, trim_blocks=True)
    env.filters.update(FilterModule().filters())
    return env.from_string((TEMPLATES / name).read_text()).render(system_nic_interfaces=interfaces)


@pytest.fixture
def nic_host(tmp_path):
    tools = tmp_path / "bin"
    tools.mkdir()
    state = tmp_path / "state.json"
    calls = tmp_path / "calls.jsonl"
    net = tmp_path / "net"
    net.mkdir()
    hardware = {}
    for index, name in enumerate(["p0", "p1", "v0", "unselected"]):
        bus = f"0000:0{index + 1}:00.0"
        device = tmp_path / "devices" / bus
        device.mkdir(parents=True)
        (device / "vendor").write_text("0x8086\n")
        interface = net / name
        interface.mkdir()
        (interface / "device").symlink_to(device)
        hardware[name] = {"driver": "i40e", "bus": bus, "lldp": "off", "forwarding": "off", "list": "on"}
    program = f"""#!{sys.executable}
import json, sys
from pathlib import Path
state = Path({str(state)!r})
calls = Path({str(calls)!r})
args = sys.argv[1:]
with calls.open('a') as log:
    log.write(json.dumps([Path(sys.argv[0]).name, *args]) + '\\n')
data = json.loads(state.read_text())
command = Path(sys.argv[0]).name
if command == 'systemctl':
    sys.exit(0)
if command == 'lspci':
    bus = args[args.index('-s') + 1]
    device = next(d for d in data.values() if d['bus'] == bus)
    print(bus, 'Ethernet controller: Intel Corporation', device.get('model', 'X710'), '[8086:1572]')
    sys.exit(0)
d = data[args[1]]
if args[0] == '-i':
    print('driver:', d['driver'])
    print('bus-info:', d['bus'])
elif args[0] == '--show-priv-flags':
    if not d.get('missing_private'):
        print('disable-fw-lldp:', d['lldp'])
elif args[0] == '-k':
    print('rx-udp-gro-forwarding:', d['forwarding'], '[fixed]' if d.get('fixed') else '')
    if not d.get('missing_gro'):
        print('rx-gro-list:', d['list'])
elif args[0] == '--set-priv-flags':
    assert args[2:] == ['disable-fw-lldp', 'on']
    if not d.get('ignore_write'):
        d['lldp'] = 'on'
elif args[0] == '-K':
    assert args[2:] == ['rx-udp-gro-forwarding', 'on', 'rx-gro-list', 'off']
    if not d.get('ignore_write'):
        d.update(forwarding='on', list='off')
else:
    sys.exit(99)
state.write_text(json.dumps(data))
"""
    for tool in ["ethtool", "lspci", "systemctl"]:
        path = tools / tool
        path.write_text(program)
        path.chmod(0o755)

    def run(interfaces, *args, changes=None, missing=None, vf=None, dispatcher=False):
        snapshot = hardware.copy()
        snapshot = {key: value.copy() for key, value in snapshot.items()}
        for key, updates in (changes or {}).items():
            snapshot[key].update(updates)
        state.write_text(json.dumps(snapshot))
        calls.unlink(missing_ok=True)
        if missing:
            (net / missing / "device").unlink()
            (net / missing).rmdir()
        if vf:
            (net / vf / "device" / "physfn").symlink_to(tmp_path / "devices" / hardware["p0"]["bus"])
        source = render("nic-dispatcher.sh.j2" if dispatcher else "nic-settings.sh.j2", interfaces)
        assert source.count("export PATH=/usr/sbin:/usr/bin:/sbin:/bin") == 1
        source = source.replace(
            "export PATH=/usr/sbin:/usr/bin:/sbin:/bin", f"export PATH={shlex.quote(str(tools) + os.pathsep + os.defpath)}"
        )
        source = source.replace("sysfs=/sys/class/net", f"sysfs={shlex.quote(str(net))}")
        script = tmp_path / "script"
        script.write_text(source)
        result = subprocess.run(["bash", str(script), *args], capture_output=True, text=True, check=False)
        recorded = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
        return result, recorded, json.loads(state.read_text())

    return run


def writes(calls):
    return [args for args in calls if args[0] == "ethtool" and args[1] in {"-K", "--set-priv-flags"}]


def test_features_are_independent_and_only_selected_ports_change(nic_host):
    interfaces = {"p0": {"disable_fw_lldp": True}, "p1": {"udp_gro_forwarding": True}, "v0": {"udp_gro_forwarding": True}}
    result, calls, state = nic_host(interfaces, "--apply", changes={"v0": {"driver": "virtio_net"}})
    assert result.returncode == 0, result.stderr
    assert writes(calls) == [
        ["ethtool", "--set-priv-flags", "p0", "disable-fw-lldp", "on"],
        ["ethtool", "-K", "p1", "rx-udp-gro-forwarding", "on", "rx-gro-list", "off"],
        ["ethtool", "-K", "v0", "rx-udp-gro-forwarding", "on", "rx-gro-list", "off"],
    ]
    assert state["unselected"]["lldp"] == "off"
    assert not any("unselected" in args for args in calls)
    assert not any(args[:3] == ["ethtool", "-k", "p0"] for args in calls)
    assert not any(args[:3] == ["ethtool", "--show-priv-flags", "p1"] for args in calls)


def test_combined_request_uses_separate_commands_and_reads_back_both(nic_host):
    result, calls, state = nic_host({"p0": {"disable_fw_lldp": True, "udp_gro_forwarding": True}}, "--apply", "p0")
    assert result.returncode == 0, result.stderr
    assert len(writes(calls)) == 2
    assert state["p0"]["lldp"] == state["p0"]["forwarding"] == "on" and state["p0"]["list"] == "off"
    last_write = max(index for index, args in enumerate(calls) if args in writes(calls))
    assert ["ethtool", "--show-priv-flags", "p0"] in calls[last_write + 1 :]
    assert ["ethtool", "-k", "p0"] in calls[last_write + 1 :]


@pytest.mark.parametrize(
    ("changes", "missing", "vf"),
    [
        ({"driver": "virtio_net"}, None, None),
        ({"driver": "iavf"}, None, None),
        ({}, None, "p1"),
        ({"model": "XL710"}, None, None),
        ({"missing_private": True}, None, None),
        ({}, "p1", None),
        ({"missing_gro": True}, None, None),
        ({"fixed": True}, None, None),
    ],
)
def test_invalid_selected_device_or_capability_blocks_all_writes(nic_host, changes, missing, vf):
    interfaces = {"p0": {"disable_fw_lldp": True}, "p1": {"disable_fw_lldp": True, "udp_gro_forwarding": True}}
    result, calls, _ = nic_host(interfaces, "--apply", changes={"p1": changes}, missing=missing, vf=vf)
    assert result.returncode != 0
    assert "p1" in result.stderr
    assert not writes(calls)


def test_inspection_is_read_only_and_already_correct_settings_are_not_rewritten(nic_host):
    interfaces = {"p0": {"disable_fw_lldp": True, "udp_gro_forwarding": True}}
    result, calls, _ = nic_host(interfaces, "--check")
    assert result.returncode == 0 and "SYSTEM_NIC_CHANGE=p0" in result.stdout
    assert not writes(calls)
    result, calls, _ = nic_host(interfaces, "--apply", changes={"p0": {"lldp": "on", "forwarding": "on", "list": "off"}})
    assert result.returncode == 0 and not writes(calls)


def test_readback_failure_is_not_reported_as_success(nic_host):
    result, _, _ = nic_host({"p0": {"disable_fw_lldp": True}}, "--apply", changes={"p0": {"ignore_write": True}})
    assert result.returncode != 0 and "verification" in result.stderr


def test_networkmanager_events_only_schedule_the_same_selected_interface_unit(nic_host):
    selected = {"p0": {"udp_gro_forwarding": True}}
    for interface, event, expected in [("unselected", "up", False), ("p0", "down", False), ("p0", "up", True), ("p0", "reapply", True)]:
        result, calls, _ = nic_host(selected, interface, event, dispatcher=True)
        assert result.returncode == 0
        assert calls == ([["systemctl", "--no-block", "restart", "skynet-system-nic@p0.service"]] if expected else [])


@pytest.mark.skipif(shutil.which("systemd-analyze") is None, reason="systemd-analyze is unavailable")
def test_generated_device_bound_unit_passes_offline_systemd_validation(tmp_path):
    script = tmp_path / "fake-nic-apply"
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(0o755)
    unit = tmp_path / "skynet-system-nic@p0.service"
    unit.write_text(render("nic-settings.service.j2", {}).replace("/usr/local/sbin/skynet-system-nic", str(script)))
    result = subprocess.run(["systemd-analyze", "verify", str(unit)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
