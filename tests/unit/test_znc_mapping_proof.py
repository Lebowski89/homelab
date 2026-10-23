"""Exercise the selected mapping probe with inventory/runtime access replaced by fixtures."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("znc_mapping_proof", ROOT / "ansible/operator/znc-mapping-proof.py")
proof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof)


@pytest.mark.parametrize(
    "observed,success",
    [
        (" 0   1410720 1000\n1000\t1020\t1\n1001 1411720 64536\n", True),
        ("0 1410720 1000\n1000 1021 1\n1001 1411720 64536\n", False),
        ("0 1410720\n", False),
        ("0 1410720 0\n", False),
    ],
)
def test_numeric_map_comparison_cli_never_projects_inventory(tmp_path, monkeypatch, observed, success):
    saved, current = tmp_path / "saved", tmp_path / "observed"
    saved.write_text("0 1410720 1000\n1000 1020 1\n1001 1411720 64536\n")
    current.write_text(observed)
    monkeypatch.setattr(proof.sys, "argv", ["proof", "--compare-maps", str(saved), str(current)])
    monkeypatch.setattr(proof, "project", lambda: pytest.fail("comparison must be offline"))
    if success:
        proof.main()
    else:
        with pytest.raises(ValueError):
            proof.main()


def test_projection_resolves_real_selected_declaration_without_secret_preparation(monkeypatch):
    import ansible.inventory.manager as inventory_module
    from ansible.parsing.dataloader import DataLoader
    from ansible.plugins import loader as plugins
    from ansible.vars.manager import VariableManager

    monkeypatch.setattr(plugins, "init_plugin_loader", lambda: None)
    host = SimpleNamespace(name="mgt")
    monkeypatch.setattr(
        inventory_module,
        "InventoryManager",
        lambda **kw: SimpleNamespace(groups={"tags_service_controller": SimpleNamespace(hosts=[host])}),
    )
    monkeypatch.setattr(VariableManager, "__init__", lambda self, **kw: None)
    monkeypatch.setattr(
        VariableManager,
        "get_vars",
        lambda self, **kw: {
            "container_host_puid": 2345,
            "container_host_pgid": 3456,
            "container_host_appdata_root": "/opt",
            "unrelated_secret": "FAKE_NOT_PRODUCTION_DO_NOT_PROJECT",
        },
    )
    monkeypatch.setattr(proof.socket, "gethostname", lambda: "mgt")
    selected = proof.project()
    canonical = DataLoader().load_from_file(str(ROOT / "ansible/group_vars/all/services/znc.yml"))["znc"]
    assert selected["image"] == canonical["image"]
    assert (selected["uid"], selected["gid"], selected["user"], selected["source"]) == (2345, 3456, "0:0", "/opt/znc")
    assert "FAKE_NOT_PRODUCTION" not in json.dumps(selected)
    monkeypatch.setattr(proof.socket, "gethostname", lambda: "wrong-host")
    with pytest.raises(ValueError, match="inventory controller"):
        proof.project()


def fixture(report):
    report.mkdir()
    (report / "account.txt").write_text("podman-znc:x:1020:1020::/var/lib/podman-znc:/usr/sbin/nologin\n")
    for key in ["uid", "gid"]:
        (report / f"znc.sub{key}").write_text("podman-znc:1410720:65536\n")
        (report / f"docker-znc.{key}_map").write_text("0 0 4294967295\n")
    (report / "docker-znc-identity.json").write_text(
        json.dumps({"owner_view": "host", "processes": [{"comm": "znc", "uid": 1000, "gid": 1000}]})
    )
    (report / "znc-ownership.acl").write_text(
        "# file: /opt/znc\n# owner: 1000\n# group: 1000\nuser::rwx\ngroup::r-x\nother::r-x\n\n# file: /opt/znc/space name\n# owner: 1000\n# group: 1000\nuser::rw-\ngroup::r--\nother::---\n"
    )
    return {
        "inventory_host": "mgt",
        "account": "podman-znc",
        "image": "FAKE_ZNC_IMAGE@sha256:" + "f" * 64,
        "user": "0:0",
        "source": "/opt/znc",
        "uid": 1000,
        "gid": 1000,
    }


@pytest.mark.parametrize("failure", [None, "account", "range", "missing_image", "replacement", "bad_mapping"])
def test_probe_uses_selected_store_and_cleans_only_its_container(tmp_path, monkeypatch, failure):
    report, output = tmp_path / "report", tmp_path / "output"
    selected = fixture(report)
    output.mkdir()
    calls = []
    cid = "a" * 64
    count = 0

    def command(argv, **kwargs):
        nonlocal count
        calls.append(argv)
        if argv[:2] == ["getent", "passwd"]:
            return (
                (report / "account.txt").read_text().strip().replace(":1020:", ":1021:", 1)
                if failure == "account"
                else (report / "account.txt").read_text().strip()
            )
        if argv[:2] == ["sudo", "awk"]:
            return "changed" if failure == "range" else "podman-znc:1410720:65536"
        if argv[:2] == ["sudo", "cat"]:
            if argv[-1].endswith("/stat"):
                return "20 (sleep) " + " ".join(["S"] + ["0"] * 18 + ["100"])
            return "0 1410720 1000\n1000 " + ("1021" if failure == "bad_mapping" else "1020") + " 1\n1001 1411720 64536"
        marker = argv.index("--remote=false")
        q = argv[marker + 1 :]
        # The wrapper must leave a private operator cwd before Podman starts.
        assert 'cd "$HOME" || exit; exec "$@"' in argv
        assert "HOME=/var/lib/podman-znc" in argv and "XDG_RUNTIME_DIR=/run/user/1020" in argv
        if q[:2] == ["image", "exists"]:
            if failure == "missing_image":
                raise proof.CommandFailure("ZNC account image existence check", 1, "")
            return ""
        if q[0] == "run":
            assert "--userns=keep-id:uid=1000,gid=1000" in q and "--network=none" in q
            assert "--pull=never" in q and "--rm" in q and "--entrypoint=/bin/sleep" in q
            assert not any(x in q for x in ["--volume", "--publish", "--env", "--env-file"])
            return cid
        if q[:2] == ["container", "inspect"]:
            assert ".ID" in q[q.index("--format") + 1]
            count += 1
            return json.dumps({"id": cid, "pid": 21 if failure == "replacement" and count == 2 else 20, "running": True})
        assert q == ["rm", "--force", cid]
        return ""

    monkeypatch.setattr(proof, "command", command)
    if failure:
        with pytest.raises((ValueError, RuntimeError)):
            proof.prove(report, output, selected)
        assert not (output / "ownership-commands.sh").exists()
    else:
        proof.prove(report, output, selected)
        rows = json.loads((output / "translations.json").read_text())
        assert all(r["old"] == [1000, 1000] and r["new"] == [1020, 1020] for r in rows)
        script = (output / "ownership-commands.sh").read_text()
        assert "--from=1000:1000 1020:1020" in script and "'/opt/znc/space name'" in script
    removals = [a for a in calls if "rm" in a]
    assert len(removals) == (failure not in ["account", "range", "missing_image"])
    assert not any("chown" in a or "pull" in a or "znc.service" in a for a in calls)


def test_translation_rejects_unmapped_owners_and_named_acls(tmp_path):
    selected = fixture(tmp_path / "report")
    report = tmp_path / "report"
    mapping = "0 1410720 1000\n1000 1020 1\n1001 1411720 64536"
    manifest = report / "znc-ownership.acl"
    original = manifest.read_text()
    manifest.write_text(original.replace("# owner: 1000", "# owner: 5678"))
    with pytest.raises(ValueError, match="unreviewed old owner"):
        proof.translations(report, selected, mapping, mapping)
    manifest.write_text(original.replace("user::rwx", "user:5678:rwx\nuser::rwx"))
    with pytest.raises(ValueError, match="named/default ACL"):
        proof.translations(report, selected, mapping, mapping)


@pytest.mark.integration
def test_account_shell_leaves_private_operator_cwd_and_preserves_arguments(tmp_path):
    import os
    import subprocess

    private = tmp_path / "private-operator"
    home = tmp_path / "account-home"
    private.mkdir(mode=0o700)
    home.mkdir()
    result = subprocess.run(
        [
            "/bin/sh",
            "-c",
            'cd "$HOME" || exit; exec "$@"',
            "skynet-znc-mapping",
            "/bin/sh",
            "-c",
            'pwd; printf "%s\\n" "$1"',
            "child",
            "literal $(false) space",
        ],
        cwd=private,
        env={**os.environ, "HOME": str(home)},
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout.splitlines() == [str(home), "literal $(false) space"]


@pytest.mark.parametrize("case", ["missing", "stage", "store-error", "wrapper-error", "pull-error", "present"])
@pytest.mark.integration
def test_actual_subprocess_image_status_and_explicit_staging(tmp_path, monkeypatch, case):

    report, output = tmp_path / "report", tmp_path / "output"
    selected = fixture(report)
    output.mkdir()
    binary = tmp_path / "bin"
    binary.mkdir()
    getent = binary / "getent"
    getent.write_text('#!/bin/sh\ncat "$MAP_FIXTURE/report/account.txt"\n')
    sudo = binary / "sudo"
    sudo.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = awk ]; then printf 'podman-znc:1410720:65536\\n'; exit; fi\n"
        '[ "$1" = runuser ] || exit 97\nshift 4\n'
        # Replace only the Podman executable and inaccessible fixture HOME.
        f"exec '{sys.executable}' '{tmp_path / 'account.py'}' \"$@\"\n"
    )
    home = tmp_path / "account-home"
    home.mkdir()
    (tmp_path / "account.py").write_text(
        "import os,sys\nfrom pathlib import Path\na=sys.argv[1:]\n"
        "root=Path(os.environ['MAP_FIXTURE'])\n"
        "a=[('HOME='+str(root/'account-home')) if x.startswith('HOME=') else str(root/'bin/podman') if x=='/usr/bin/podman' else x for x in a]\n"
        "os.execvp(a[0],a)\n"
    )
    podman = binary / "podman"
    podman.write_text(
        "#!/bin/sh\n"
        'printf \'%s\\n\' "$PWD" >"$MAP_FIXTURE/probe-cwd"\n'
        'printf \'%s\\n\' "$*" >>"$MAP_FIXTURE/podman-calls"\n'
        'case "$1:$2:$3" in\n'
        "  --remote=false:image:exists)\n"
        "    if [ \"$MAP_CASE\" = store-error ]; then echo 'storage blocked' >&2; exit 125; fi\n"
        "    if [ \"$MAP_CASE\" = wrapper-error ]; then echo 'account execution denied' >&2; exit 1; fi\n"
        '    [ "$MAP_CASE" = present ] || [ -f "$MAP_FIXTURE/staged" ]; exit $? ;;\n'
        "  --remote=false:pull:*)\n"
        "    if [ \"$MAP_CASE\" = pull-error ]; then echo 'pull failed' >&2; exit 125; fi\n"
        '    touch "$MAP_FIXTURE/staged"; exit ;;\n'
        "  --remote=false:run:*) echo 'fixture stopped before runtime' >&2; exit 77 ;;\n"
        "  *) exit 97 ;;\nesac\n"
    )
    for file in [getent, sudo, podman]:
        file.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binary}:/usr/bin:/bin")
    monkeypatch.setenv("MAP_FIXTURE", str(tmp_path))
    monkeypatch.setenv("MAP_CASE", case)
    monkeypatch.chdir(output)
    reason = {
        "missing": "exact pinned ZNC image is absent from podman-znc",
        "stage": r"start isolated ZNC namespace probe failed \(77\)",
        "present": r"start isolated ZNC namespace probe failed \(77\)",
        "store-error": r"ZNC account image existence check failed \(125\): storage blocked",
        "wrapper-error": r"ZNC account image existence check failed \(1\): account execution denied",
        "pull-error": r"stage exact pinned ZNC image failed \(125\): pull failed",
    }[case]
    with pytest.raises(RuntimeError, match=reason):
        proof.prove(report, output, selected, stage_image=case != "missing")
    assert (tmp_path / "probe-cwd").read_text().strip() == str(home)
    assert not (output / "ownership-commands.sh").exists()
    calls = (tmp_path / "podman-calls").read_text().splitlines()
    pulls = [call for call in calls if call.startswith("--remote=false pull ")]
    assert len(pulls) == (case in ["stage", "pull-error"])
    assert all(call.endswith(selected["image"]) for call in pulls)
    if case in ["missing", "store-error", "wrapper-error", "pull-error"]:
        assert not any(call.startswith("--remote=false run ") for call in calls)


@pytest.mark.parametrize("stage", [False, True])
def test_cli_requires_explicit_staging_option_and_retains_reports(tmp_path, monkeypatch, stage):
    report = tmp_path / "report"
    selected = fixture(report)
    report.chmod(0o700)
    before = {p.name: p.read_bytes() for p in report.iterdir()}
    monkeypatch.setattr(proof, "project", lambda: selected)
    calls = []
    monkeypatch.setattr(proof, "prove", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(proof.sys, "argv", ["znc-mapping-proof.py", *(["--stage-image"] if stage else []), str(report)])
    old_mask = proof.os.umask(0o077)
    try:
        proof.main()
    finally:
        proof.os.umask(old_mask)
    assert calls[0][0][0] == report and calls[0][1]["stage_image"] is stage
    assert {p.name: p.read_bytes() for p in report.iterdir()} == before
    output = calls[0][0][1]
    assert output.stat().st_mode & 0o777 == 0o700
    assert (output / "selected.json").stat().st_mode & 0o777 == 0o600
