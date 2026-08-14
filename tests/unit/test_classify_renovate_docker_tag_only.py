from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.ci.classify_renovate_docker_tag_only import RENOVATE_AUTHOR, classify, main

QUI_PATH = "ansible/group_vars/all/services/qui.yml"
DOZZLE_PATH = "ansible/group_vars/all/services/dozzle.yml"

SERVICE_YAML = """---
service:
  image: ghcr.io/autobrr/qui:v1.20.0
  environment:
    PUID: "1000"
    PGID: "1000"
  ports:
    - "7476:7476"
  volumes:
    - "/data:/data"
  labels:
    traefik.enable: "true"
  secrets:
    - qui_token
"""


def _git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()


def _commit(repository: Path, message: str, changes: dict[str, str | None]) -> str:
    for relative_path, content in changes.items():
        path = repository / relative_path
        if content is None:
            path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    _git(repository, "add", "-A")
    _git(repository, "commit", "-m", message)
    return _git(repository, "rev-parse", "HEAD")


@pytest.fixture
def git_repository(tmp_path: Path) -> tuple[Path, str]:
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.name", "Renovate classifier tests")
    _git(tmp_path, "config", "user.email", "renovate-classifier@example.invalid")
    base_sha = _commit(tmp_path, "base", {QUI_PATH: SERVICE_YAML})
    return tmp_path, base_sha


def _classify(repository: Path, base_sha: str, head_sha: str, *, author: str = RENOVATE_AUTHOR):
    return classify(
        event_name="pull_request",
        pr_author=author,
        base_sha=base_sha,
        head_sha=head_sha,
        repository=repository,
    )


def test_single_service_tag_change_uses_fast_path(git_repository: tuple[Path, str]) -> None:
    repository, base_sha = git_repository
    head_sha = _commit(repository, "update qui", {QUI_PATH: SERVICE_YAML.replace("v1.20.0", "v1.25.0")})

    classification = _classify(repository, base_sha, head_sha)

    assert classification.renovate_docker_tag_only is True
    assert classification.changed_files == (QUI_PATH,)


def test_multiple_service_tag_changes_use_fast_path(git_repository: tuple[Path, str]) -> None:
    repository, base_sha = git_repository
    dozzle_base = SERVICE_YAML.replace("ghcr.io/autobrr/qui:v1.20.0", "amir20/dozzle:v10.6.15")
    base_sha = _commit(repository, "add dozzle", {DOZZLE_PATH: dozzle_base})
    head_sha = _commit(
        repository,
        "update service images",
        {
            QUI_PATH: SERVICE_YAML.replace("v1.20.0", "v1.25.0"),
            DOZZLE_PATH: dozzle_base.replace("v10.6.15", "v10.7.1"),
        },
    )

    classification = _classify(repository, base_sha, head_sha)

    assert classification.renovate_docker_tag_only is True
    assert set(classification.changed_files) == {QUI_PATH, DOZZLE_PATH}


def test_digest_only_change_uses_fast_path(git_repository: tuple[Path, str]) -> None:
    repository, _ = git_repository
    base_content = SERVICE_YAML.replace("v1.20.0", f"v1.20.0@sha256:{'a' * 64}")
    base_sha = _commit(repository, "pin digest", {QUI_PATH: base_content})
    head_sha = _commit(repository, "update digest", {QUI_PATH: base_content.replace("a" * 64, "b" * 64)})

    assert _classify(repository, base_sha, head_sha).renovate_docker_tag_only is True


def test_multiple_target_image_changes_in_one_service_use_fast_path(git_repository: tuple[Path, str]) -> None:
    repository, _ = git_repository
    base_content = """---
service:
  runtime: docker
  targets:
    agent:
      image: example/agent:1.0.0
    main:
      image: example/main:2.0.0
"""
    base_sha = _commit(repository, "add multi-target service", {QUI_PATH: base_content})
    head_content = base_content.replace("example/agent:1.0.0", "example/agent:1.1.0").replace("example/main:2.0.0", "example/main:2.1.0")
    head_sha = _commit(repository, "update target images", {QUI_PATH: head_content})

    assert _classify(repository, base_sha, head_sha).renovate_docker_tag_only is True


def test_podman_runtime_image_change_uses_fast_path(git_repository: tuple[Path, str]) -> None:
    repository, _ = git_repository
    base_content = """---
service:
  runtime: podman
  image: example/app:1.0.0
"""
    base_sha = _commit(repository, "add podman service", {QUI_PATH: base_content})
    head_sha = _commit(repository, "update podman image", {QUI_PATH: base_content.replace("1.0.0", "1.1.0")})

    assert _classify(repository, base_sha, head_sha).renovate_docker_tag_only is True


def test_cli_emits_true_github_output_contract(git_repository: tuple[Path, str], capsys: pytest.CaptureFixture[str]) -> None:
    repository, base_sha = git_repository
    head_sha = _commit(repository, "update qui", {QUI_PATH: SERVICE_YAML.replace("v1.20.0", "v1.25.0")})

    exit_code = main(
        [
            "--event-name",
            "pull_request",
            "--pr-author",
            RENOVATE_AUTHOR,
            "--base-sha",
            base_sha,
            "--head-sha",
            head_sha,
            "--repository",
            str(repository),
        ]
    )
    output_lines = capsys.readouterr().out.splitlines()

    assert exit_code == 0
    assert "renovate_docker_tag_only=true" in output_lines
    assert f"comparison_base={base_sha}" in output_lines
    changed_files_header = next(line for line in output_lines if line.startswith("changed_files<<"))
    changed_files_footer = changed_files_header.removeprefix("changed_files<<")
    header_index = output_lines.index(changed_files_header)
    footer_index = output_lines.index(changed_files_footer)
    assert QUI_PATH in output_lines[header_index + 1 : footer_index]


def test_cli_emits_false_github_output_contract(git_repository: tuple[Path, str], capsys: pytest.CaptureFixture[str]) -> None:
    repository, base_sha = git_repository
    head_sha = _commit(repository, "update qui", {QUI_PATH: SERVICE_YAML.replace("v1.20.0", "v1.25.0")})

    exit_code = main(
        [
            "--event-name",
            "pull_request",
            "--pr-author",
            "human",
            "--base-sha",
            base_sha,
            "--head-sha",
            head_sha,
            "--repository",
            str(repository),
        ]
    )
    output_lines = capsys.readouterr().out.splitlines()

    assert exit_code == 0
    assert "renovate_docker_tag_only=false" in output_lines
    assert "comparison_base=" in output_lines
    assert "changed_files=" in output_lines
    reason = next(line for line in output_lines if line.startswith("classification_reason="))
    assert reason.removeprefix("classification_reason=")


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("ghcr.io/autobrr/qui:v1.20.0", "evil/example:v1.20.0"),
        ('PGID: "1000"', 'PGID: "0"'),
        ('- "/data:/data"', '- "/tmp:/data"'),
        ('- "7476:7476"', '- "80:7476"'),
        ('traefik.enable: "true"', 'traefik.enable: "false"'),
        ("- qui_token", "- root_password"),
    ],
    ids=["repository", "environment", "volume", "port", "traefik", "secret"],
)
def test_non_tag_service_changes_use_full_ci(
    git_repository: tuple[Path, str],
    old: str,
    new: str,
) -> None:
    repository, base_sha = git_repository
    changed = SERVICE_YAML.replace(old, new)
    head_sha = _commit(repository, "unsafe service edit", {QUI_PATH: changed})

    assert _classify(repository, base_sha, head_sha).renovate_docker_tag_only is False


def test_added_configuration_uses_full_ci(git_repository: tuple[Path, str]) -> None:
    repository, base_sha = git_repository
    changed = SERVICE_YAML.replace("  environment:\n", "  privileged: true\n  environment:\n").replace("v1.20.0", "v1.25.0")
    head_sha = _commit(repository, "update image and privilege", {QUI_PATH: changed})

    assert _classify(repository, base_sha, head_sha).renovate_docker_tag_only is False


@pytest.mark.parametrize(
    ("path", "content"),
    [
        ("ansible/roles/example/tasks/main.yml", "---\n- name: Example\n  ansible.builtin.debug:\n"),
        ("ansible/roles/example/templates/config.yml.j2", "setting: value\n"),
        ("scripts/example.py", "print('changed')\n"),
        ("opentofu/example/main.tf", 'resource "example" "changed" {}\n'),
        (".github/workflows/example.yml", "---\nname: Changed\n"),
    ],
    ids=["task", "template", "python", "terraform", "workflow"],
)
def test_other_repository_change_alongside_tag_uses_full_ci(
    git_repository: tuple[Path, str],
    path: str,
    content: str,
) -> None:
    repository, base_sha = git_repository
    head_sha = _commit(
        repository,
        "update image and another file",
        {QUI_PATH: SERVICE_YAML.replace("v1.20.0", "v1.25.0"), path: content},
    )

    assert _classify(repository, base_sha, head_sha).renovate_docker_tag_only is False


def test_human_authored_image_change_uses_full_ci(git_repository: tuple[Path, str]) -> None:
    repository, base_sha = git_repository
    head_sha = _commit(repository, "human image update", {QUI_PATH: SERVICE_YAML.replace("v1.20.0", "v1.25.0")})

    assert _classify(repository, base_sha, head_sha, author="human").renovate_docker_tag_only is False


def test_multiple_commits_with_manual_change_use_full_ci(git_repository: tuple[Path, str]) -> None:
    repository, base_sha = git_repository
    _commit(repository, "renovate image update", {QUI_PATH: SERVICE_YAML.replace("v1.20.0", "v1.25.0")})
    manually_changed = SERVICE_YAML.replace("v1.20.0", "v1.25.0").replace("  environment:\n", "  privileged: true\n  environment:\n")
    head_sha = _commit(repository, "manual edit", {QUI_PATH: manually_changed})

    assert _classify(repository, base_sha, head_sha).renovate_docker_tag_only is False


def test_whitespace_change_alongside_tag_uses_full_ci(git_repository: tuple[Path, str]) -> None:
    repository, base_sha = git_repository
    changed = SERVICE_YAML.replace("v1.20.0", "v1.25.0").replace('    PUID: "1000"', '    PUID:  "1000"')
    head_sha = _commit(repository, "update image and whitespace", {QUI_PATH: changed})

    assert _classify(repository, base_sha, head_sha).renovate_docker_tag_only is False


def test_no_changed_files_uses_full_ci(git_repository: tuple[Path, str]) -> None:
    repository, base_sha = git_repository

    assert _classify(repository, base_sha, base_sha).renovate_docker_tag_only is False


def test_malformed_sha_uses_full_ci(git_repository: tuple[Path, str]) -> None:
    repository, base_sha = git_repository

    assert _classify(repository, base_sha, "not-a-sha").renovate_docker_tag_only is False


def test_non_pull_request_event_uses_full_ci(git_repository: tuple[Path, str]) -> None:
    repository, base_sha = git_repository

    classification = classify(
        event_name="push",
        pr_author=RENOVATE_AUTHOR,
        base_sha=base_sha,
        head_sha=base_sha,
        repository=repository,
    )

    assert classification.renovate_docker_tag_only is False
