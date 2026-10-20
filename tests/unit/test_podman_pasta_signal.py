"""Exercise the proposed host-policy edit on private files; never load a profile."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PLAY = ROOT / "ansible/operations.yml"
BEFORE = b"profile pasta /fixture/pasta flags=(attach_disconnected) {\n}\n"
BLOCK = b"# BEGIN SKYNET PODMAN PASTA TERM\n  signal (receive) set=(term) peer=podman,\n# END SKYNET PODMAN PASTA TERM\n"
AFTER = BEFORE.replace(b"{\n", b"{\n" + BLOCK)


@pytest.mark.parametrize("scenario", ["apply_repeat", "check", "stale", "invalid_rule", "reload_failure"])
def test_exact_profile_edit_idempotence_read_only_guards_and_rollback(tmp_path, scenario):
    binary = Path(os.sys.executable).parent / "ansible-playbook"
    if not binary.is_file() or not Path("/usr/sbin/apparmor_parser").is_file():
        pytest.skip("local Ansible/profile syntax parser unavailable")
    fixture = tmp_path / "pasta.profile"
    fixture.write_bytes(BEFORE + (b"# unexpected edit\n" if scenario == "stale" else b""))
    fixture.chmod(0o644)
    original = fixture.read_bytes()
    counter = tmp_path / "reload-count"
    reload = tmp_path / "reload.py"
    reload.write_text(
        "from pathlib import Path\nimport sys\n"
        f"p=Path({str(counter)!r}); n=int(p.read_text())+1 if p.exists() else 1; p.write_text(str(n))\n"
        f"sys.exit(1 if {scenario == 'reload_failure'!r} and n==1 else 0)\n"
    )
    play = [entry for entry in yaml.safe_load(PLAY.read_text()) if "podman_pasta_signal" in entry["tasks"][0]["tags"]]
    play[0]["tasks"] = yaml.safe_load((ROOT / "ansible/operations/podman-pasta-signal.yml").read_text())
    play[0].update(hosts="localhost", connection="local", become=False)
    play[0].pop("vars_files")

    def fixture_only(value):
        if isinstance(value, list):
            if value == ["/usr/sbin/apparmor_parser", "--replace", "/etc/apparmor.d/usr.bin.pasta"]:
                return [os.sys.executable, str(reload)]
            return [fixture_only(item) for item in value]
        if isinstance(value, dict):
            return {
                key: (str(os.getuid()) if key == "owner" else str(os.getgid())) if key in {"owner", "group"} else fixture_only(item)
                for key, item in value.items()
            }
        if isinstance(value, str):
            return (
                value.replace("/etc/apparmor.d/usr.bin.pasta", str(fixture))
                .replace(".stat.uid == 0", f".stat.uid == {os.getuid()}")
                .replace(".stat.gid == 0", f".stat.gid == {os.getgid()}")
            )
        return value

    play = fixture_only(play)
    if scenario == "invalid_rule":
        play[0]["tasks"][3]["block"][0]["ansible.builtin.blockinfile"]["block"] = "invalid apparmor syntax,"
    playfile = tmp_path / "fixture.yml"
    playfile.write_text(yaml.safe_dump(play))
    inputs = tmp_path / "inputs.json"
    inputs.write_text(
        json.dumps(
            {
                "services_controller_inventory_group": "all",
                "podman_pasta_signal_before_sha256": hashlib.sha256(BEFORE).hexdigest(),
                "podman_pasta_signal_after_sha256": hashlib.sha256(AFTER).hexdigest(),
            }
        )
    )
    config = tmp_path / "ansible.cfg"
    config.write_text("[defaults]\ninventory=localhost,\nretry_files_enabled=False\n")
    argv = [str(binary), "-i", "localhost,", str(playfile), "-e", "@" + str(inputs)]
    if scenario == "check":
        argv.append("--check")

    def run():
        return subprocess.run(argv, env={**os.environ, "ANSIBLE_CONFIG": str(config)}, capture_output=True, text=True, timeout=60)

    result = run()
    assert "UNREACHABLE!" not in result.stdout, result.stdout + result.stderr
    if scenario == "apply_repeat":
        assert result.returncode == 0, result.stdout + result.stderr
        assert fixture.read_bytes() == AFTER and counter.read_text() == "1"
        repeated = run()
        assert repeated.returncode == 0, repeated.stdout + repeated.stderr
        assert fixture.read_bytes() == AFTER and counter.read_text() == "1"
    elif scenario == "check":
        assert result.returncode == 0, result.stdout + result.stderr
        assert fixture.read_bytes() == original and not counter.exists()
    else:
        assert result.returncode != 0
        assert fixture.read_bytes() == original
        assert counter.read_text() == "2" if scenario == "reload_failure" else not counter.exists()
