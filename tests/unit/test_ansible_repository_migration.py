"""Exercise repository format migrations using real modules in temporary directories."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
ANSIBLE = str(Path(sys.executable).with_name("ansible-playbook"))
pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "role,architecture,overrides,expected_architectures,legacy_layout",
    [
        ("docker", "x86_64", {}, "amd64", "canonical"),
        ("docker", "aarch64", {}, "arm64", "annotated"),
        (
            "docker",
            "x86_64",
            {
                "docker_repo_filename": "operator-docker",
                "docker_repo_url": "https://packages.example.test/docker",
                "docker_repo_channel": "test",
                "docker_apt_arch": "amd64,arm64",
                "docker_keyring_file": "/etc/apt/keyrings/operator-docker.asc",
            },
            "amd64 arm64",
            "other-file",
        ),
        ("docker", "x86_64", {}, "amd64", "main-file"),
        ("docker", "x86_64", {}, "amd64", "symlink"),
        ("postgres", "x86_64", {}, None, "canonical"),
        ("postgres", "x86_64", {}, None, "annotated"),
        ("postgres", "x86_64", {}, None, "other-file"),
        ("postgres", "x86_64", {}, None, "main-file"),
        ("postgres", "x86_64", {}, None, "symlink"),
    ],
)
def test_repository_migration_preserves_sources_overrides_and_cache_order(
    tmp_path, role, architecture, overrides, expected_architectures, legacy_layout
):
    dependency = subprocess.run(["/usr/bin/python3", "-c", "import debian.deb822"], capture_output=True, check=False)
    if dependency.returncode:
        pytest.skip("the real deb822 module requires existing python3-debian; do not install test dependencies")
    from ansible.modules import deb822_repository

    sources = tmp_path / "sources"
    sources.mkdir()
    library = tmp_path / "library"
    library.mkdir()
    # Change only the real module's destination directory; package operations and
    # downloads are replaced below and never reach the controller or any host.
    source = Path(deb822_repository.__file__).read_text()
    assert source.count("'/etc/apt/sources.list.d'") == 1
    (library / "fixture_deb822_repository.py").write_text(source.replace("'/etc/apt/sources.list.d'", repr(str(sources))))
    plugins = tmp_path / "action_plugins"
    plugins.mkdir()
    record = tmp_path / "calls.jsonl"
    (plugins / "fixture_operation.py").write_text(
        "import json\nfrom pathlib import Path\nfrom ansible.plugins.action import ActionBase\n"
        "class ActionModule(ActionBase):\n"
        "    def run(self, tmp=None, task_vars=None):\n"
        "        module, options = self._task.args['module'], self._task.args['options']\n"
        f"        with Path({str(record)!r}).open('a') as stream:\n"
        "            stream.write(json.dumps(self._task.args) + '\\n')\n"
        "        if module == 'find':\n"
        f"            options['paths'] = {str(sources)!r}\n"
        "            return self._execute_module(module_name='ansible.builtin.find', module_args=options, task_vars=task_vars)\n"
        "        if module == 'lineinfile':\n"
        f"            options['path'] = options['path'].replace('/etc/apt/sources.list', {str(tmp_path / 'sources.list')!r})\n"
        f"            if Path(options['path']).is_relative_to({str(tmp_path)!r}):\n"
        "                return self._execute_module(module_name='ansible.builtin.lineinfile', module_args=options, task_vars=task_vars)\n"
        "        return {'changed': False}\n"
    )
    role_dir = ROOT / "ansible/roles" / role
    tasks = yaml.safe_load(
        (role_dir / ("tasks/sub_tasks/install.yml" if role == "docker" else "tasks/sub_tasks/install/apt.yml")).read_text()
    )
    for task in tasks:
        if "ansible.builtin.deb822_repository" in task:
            task["fixture_deb822_repository"] = task.pop("ansible.builtin.deb822_repository")
        else:
            for module in ("apt", "file", "get_url", "group", "user", "lineinfile", "find"):
                if f"ansible.builtin.{module}" in task:
                    task["fixture_operation"] = {"module": module, "options": task.pop(f"ansible.builtin.{module}")}
    # Load defaults as role defaults so play/host overrides retain real precedence.
    fixture_role = tmp_path / "roles" / role
    (fixture_role / "tasks").mkdir(parents=True)
    (fixture_role / "defaults").mkdir()
    (fixture_role / "tasks/main.yml").write_text(yaml.safe_dump(tasks, sort_keys=False))
    (fixture_role / "defaults/main.yml").write_text((role_dir / "defaults/main.yml").read_text())
    variables = {
        "ansible_facts": {"os_family": "Debian", "distribution": "Ubuntu", "distribution_release": "noble", "architecture": architecture},
        **overrides,
    }
    play = tmp_path / "play.yml"
    play.write_text(
        yaml.safe_dump(
            [
                {
                    "hosts": "localhost",
                    "connection": "local",
                    "gather_facts": False,
                    "vars": variables,
                    "roles": [role],
                }
            ],
            sort_keys=False,
        )
    )
    cfg = tmp_path / "ansible.cfg"
    cfg.write_text("[defaults]\ninject_facts_as_vars = false\n")
    env = {
        **os.environ,
        "ANSIBLE_CONFIG": str(cfg),
        "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
        "ANSIBLE_INVENTORY_ENABLED": "host_list",
        "ANSIBLE_LOG_PATH": str(tmp_path / "ansible.log"),
    }
    filename = overrides.get("docker_repo_filename", "docker") if role == "docker" else "pgdg"
    uri = (
        overrides.get("docker_repo_url", "https://download.docker.com/linux/ubuntu")
        if role == "docker"
        else "https://apt.postgresql.org/pub/repos/apt"
    )
    key = (
        overrides.get("docker_keyring_file", "/etc/apt/keyrings/docker.asc")
        if role == "docker"
        else "/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc"
    )
    suite = "noble" if role == "docker" else "noble-pgdg"
    components = overrides.get("docker_repo_channel", "stable") if role == "docker" else "main"
    arch = f"arch={overrides.get('docker_apt_arch', expected_architectures)} " if role == "docker" else ""
    legacy_entry = f"deb [{arch}signed-by={key}] {uri} {suite} {components}\n"
    if legacy_layout == "annotated":
        legacy_entry = "  " + legacy_entry.rstrip("\n").replace(" ", "\t") + "  # operator annotation\n"
    # Near-matches must survive: a different component, suite, signing key or
    # architecture is a different declaration even when the URL is identical.
    unrelated = (
        "# Operator-owned source\ndeb https://other.example.test/debian stable main\n"
        f"deb [{arch}signed-by={key}] {uri} {suite} {components} extra\n"
        f"deb [{arch}signed-by={key}] {uri} other-suite {components}\n"
        f"deb [{arch}signed-by=/operator-key.asc] {uri} {suite} {components}\n"
        f"# {legacy_entry.strip()}\n"
    )
    if role == "docker":
        unrelated += f"deb [arch=other signed-by={key}] {uri} {suite} {components}\n"
    legacy = sources / f"{filename}.list"
    if legacy_layout == "other-file":
        legacy = sources / "operator.list"
    elif legacy_layout == "main-file":
        legacy = tmp_path / "sources.list"
    elif legacy_layout == "symlink":
        legacy.symlink_to(tmp_path / "linked-source")
    destination = sources / f"{filename}.sources"

    def run(*args):
        record.unlink(missing_ok=True)
        result = subprocess.run([ANSIBLE, "-i", "localhost,", str(play), *args], cwd=tmp_path, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "DEPRECATION WARNING" not in result.stdout + result.stderr
        return [json.loads(line) for line in record.read_text().splitlines()]

    def refreshed(calls):
        return any(call["module"] == "apt" and call["options"] == {"update_cache": True} for call in calls)

    # Check mode predicts the migration without changing the legacy file or
    # creating the deb822 source. All external operations remain mocked.
    legacy.write_text(unrelated + legacy_entry)
    run("--check")
    assert not destination.exists()
    assert legacy.read_text() == unrelated + legacy_entry

    # Existing installation: retain other entries and refresh before installing.
    calls = run()
    assert legacy.read_text() == unrelated
    if legacy_layout == "symlink":
        assert legacy.is_symlink()
    fields = dict(line.split(": ", 1) for line in destination.read_text().splitlines())
    assert fields.items() >= {"URIs": uri, "Suites": suite, "Components": components, "Signed-By": key}.items()
    if expected_architectures:
        assert fields["Architectures"] == expected_architectures
    assert destination.stat().st_mode & 0o777 == 0o644
    assert any("python3-debian" in call["options"].get("name", []) for call in calls if call["module"] == "apt")
    refresh = next(i for i, call in enumerate(calls) if call["module"] == "apt" and call["options"] == {"update_cache": True})
    assert calls[refresh + 1]["module"] == "apt" and calls[refresh + 1]["options"]["state"] == "present"

    before = destination.read_bytes(), destination.stat().st_mtime_ns
    assert not refreshed(run())
    assert (destination.read_bytes(), destination.stat().st_mtime_ns) == before

    # A legacy-only change still needs a cache refresh.
    legacy.write_text(unrelated + legacy_entry)
    assert refreshed(run())
    assert legacy.read_text() == unrelated
    assert (destination.read_bytes(), destination.stat().st_mtime_ns) == before

    # Fresh installation uses the same source and never creates a .list file.
    destination.unlink()
    legacy.unlink()
    assert refreshed(run())
    assert destination.read_bytes() == before[0]
    assert not legacy.exists()
