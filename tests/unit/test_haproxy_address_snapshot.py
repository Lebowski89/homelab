"""Exercise address-only collection and failure preservation without live access."""

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("address_snapshot_test", ROOT / "ansible/operator/haproxy-address-snapshot.py")
SNAPSHOT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SNAPSHOT)


def observation(host, suffix):
    def link(name, *addresses):
        return {
            "ifname": name,
            "addr_info": [{"local": address, "scope": "global", "family": "inet6" if ":" in address else "inet"} for address in addresses],
        }

    return {
        "identity": {"hostname": host, "boot_id": host + "-fixture-boot"},
        "links": [
            link("lo", "127.0.0.1", "::1"),
            link("eth0", "192.0.2." + suffix, *(["192.0.2.53"] if host == "mgt" else [])),
            link("tailscale0", "100.64.0." + suffix, "fd00::" + suffix),
        ],
    }


@pytest.mark.parametrize("missing", ["", "alternate", "mgt-ts4", "mgt-ts6", "peer-ts6", "root-loopback", "root-slice"])
def test_each_category_and_optional_unconfigured_lan_ipv6(missing):
    mgt, peer = observation("mgt", "48"), observation("plex", "20")
    cgroup = "0::/user.slice/fixture.service"
    if missing == "alternate":
        mgt["links"][1]["addr_info"].pop()
    if missing in {"mgt-ts4", "mgt-ts6", "peer-ts6"}:
        target = peer if missing == "peer-ts6" else mgt
        target["links"][2]["addr_info"].pop(0 if missing == "mgt-ts4" else 1)
    if missing == "root-loopback":
        mgt["links"][0]["addr_info"].pop()
    if missing == "root-slice":
        cgroup = "0::/skynet_pg_recovery.slice/fixture.service"
    rows = SNAPSHOT.classify(mgt, peer, "192.0.2.48", "192.0.2.20", cgroup)
    assert len(rows) == 6
    lan6 = next(row for row in rows if row["category"] == "LAN IPv6")
    assert lan6["required"] is False and lan6["status"] == "unconfigured"
    assert "optional, no denial claimed" in lan6["reason"]
    failures = [row for row in rows if row["required"] and row["status"] != "selected"]
    assert len(failures) == bool(missing)
    if failures:
        assert failures[0]["reason"]
    else:
        assert next(row for row in rows if row["category"] == "Tailscale IPv6")["selected"] == [
            {"address": "fd00::48", "interface": "tailscale0", "peer_address": "fd00::20", "peer_interface": "tailscale0"}
        ]
    root = next(row for row in rows if row["category"] == "Unrelated local root")
    assert all("peer_address" not in address for address in root["selected"])


@pytest.mark.parametrize("unusable", ["link-local", "tentative", "deprecated", "expired", "missing-scope", "ambiguous"])
def test_tailscale_ipv6_uses_global_unicast_not_link_local(unusable):
    mgt, peer = observation("mgt", "48"), observation("plex", "20")
    for report in [mgt, peer]:
        report["links"][2]["addr_info"].append({"local": "fe80::123", "scope": "link", "family": "inet6"})
    selected = mgt["links"][2]["addr_info"][1]
    if unusable == "tentative":
        selected["tentative"] = True
    if unusable == "deprecated":
        selected["flags"] = ["deprecated"]
    if unusable == "expired":
        selected["preferred_life_time"] = 0
    if unusable == "missing-scope":
        del selected["scope"]
    if unusable == "ambiguous":
        mgt["links"][2]["addr_info"].append({"local": "fd00::99", "scope": "global", "family": "inet6"})
    rows = SNAPSHOT.classify(mgt, peer, "192.0.2.48", "192.0.2.20", "0::/user.slice/fixture")
    row = next(row for row in rows if row["category"] == "Tailscale IPv6")
    assert (row["status"] == "selected") == (unusable == "link-local")
    if unusable == "link-local":
        assert row["selected"][0]["address"] == "fd00::48"
        assert row["selected"][0]["peer_address"] == "fd00::20"
        assert all(not address["address"].startswith("fe80:") for address in rows[-1]["selected"])


@pytest.mark.parametrize("failure", ["", "missing-ts6", "wrong-host", "query-failure", "invalid-address", "timeout"])
def test_actual_snapshot_preserves_both_stdout_files_before_classification(tmp_path, monkeypatch, capsys, failure):
    output = tmp_path / "snapshot"
    output.mkdir(mode=0o700)
    batch = tmp_path / "batch"
    metadata = batch / "worker-offline-20261009T200449Z-2609904/worker-only.json.metadata.json"
    metadata.parent.mkdir(parents=True)
    mgt, peer = observation("mgt", "48"), observation("plex", "20")
    metadata.write_text(
        json.dumps(
            [
                {"host": "mgt", "inventory_address": "192.0.2.48", "identity": mgt["identity"]},
                {"host": "plex", "inventory_address": "192.0.2.20", "identity": peer["identity"]},
            ]
        )
    )
    peer_path = tmp_path / "peer.json"
    peer_path.write_text(
        json.dumps({"inventory_host": "plex", "inventory_address": "192.0.2.20", "operator": {"uid": output.stat().st_uid}})
    )
    if failure == "missing-ts6":
        mgt["links"][2]["addr_info"].pop()
    if failure == "wrong-host":
        peer["identity"]["hostname"] = "wrong-fixture-host"
    if failure == "invalid-address":
        peer["links"][2]["addr_info"][0]["local"] = "invalid-fixture-address"
    calls = []

    def execute(argv, **kwargs):
        calls.append(argv)
        assert kwargs == {"text": True, "capture_output": True, "check": False, "timeout": 20}
        is_peer = argv[0] == "fixture-ssh"
        assert argv[-1].endswith(SNAPSHOT.QUERY + "'") if is_peer else argv[-1] == SNAPSHOT.QUERY
        if is_peer and failure == "query-failure":
            return subprocess.CompletedProcess(argv, 7, "partial fixture output", "fixture ip failed")
        if is_peer and failure == "timeout":
            raise subprocess.TimeoutExpired(argv, 20, output=b"partial fixture output")
        return subprocess.CompletedProcess(argv, 0, json.dumps(peer if is_peer else mgt), "")

    monkeypatch.setattr(SNAPSHOT.CUTOVER, "negative_peer_ssh", lambda saved: ["fixture-ssh"])
    monkeypatch.setattr(SNAPSHOT.os, "geteuid", lambda: 0)
    monkeypatch.setattr(SNAPSHOT.os, "chown", lambda *args: None)
    monkeypatch.setattr(SNAPSHOT.subprocess, "run", execute)
    status = SNAPSHOT.snapshot(batch, peer_path, output)
    assert status == bool(failure)
    assert len(calls) == 2
    assert json.loads((output / "mgt.json").read_text()) == mgt
    if failure in {"query-failure", "timeout"}:
        assert (output / "plex.json").read_text() == "partial fixture output"
    else:
        assert json.loads((output / "plex.json").read_text()) == peer
    report = json.loads((output / "coverage.json").read_text())
    assert report["denial_tested"] is False and report["ports"] == [5432, 18405]
    assert len(report["coverage"]) == 6
    for path in output.iterdir():
        assert path.stat().st_mode & 0o777 == 0o600
    messages = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert {row["category"] for row in messages if "category" in row} == {row["category"] for row in report["coverage"]}
    if failure == "wrong-host":
        assert all("hostname/boot identity differs" in row["reason"] for row in report["coverage"])


@pytest.mark.parametrize("status", [0, 23])
def test_actual_shell_runner_logs_early_failure_and_uses_only_snapshot(tmp_path, status):
    batch = tmp_path / "private batch"
    batch.mkdir(mode=0o700)
    binaries = tmp_path / "bin"
    binaries.mkdir()
    sudo = binaries / "sudo"
    sudo.write_text(
        '#!/bin/bash\nif [[ "$1" = -v ]]; then echo "fixture visible sudo prompt"; exit 0; fi\n'
        '[[ "$1" = -n && "$3" = -B && "$4" = */haproxy-address-snapshot.py ]] || exit 99\n'
        'echo "fixture snapshot status"\nexit ' + str(status) + "\n"
    )
    sudo.chmod(0o700)
    environment = dict(
        os.environ, PATH=str(binaries) + ":" + os.environ["PATH"], PLAYBOOK=str(ROOT / "ansible/playbook.yml"), VIRTUAL_ENV="/fixture-venv"
    )
    result = subprocess.run(
        ["/bin/bash", str(ROOT / "ansible/operator/haproxy-address-snapshot.sh"), str(batch), str(tmp_path / "saved-peer.json")],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == status
    assert result.stdout.index("Private log:") < result.stdout.index("fixture visible sudo prompt")
    directories = list(batch.iterdir())
    assert len(directories) == 1 and directories[0].stat().st_mode & 0o777 == 0o700
    log = directories[0] / "operator.log"
    assert log.stat().st_mode & 0o777 == 0o600
    assert f"exited with status {status}" in log.read_text()
