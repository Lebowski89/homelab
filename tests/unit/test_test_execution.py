"""Keep CI partitions complete and their required result gate fail-closed."""

import importlib.util
import os
import re
import subprocess
import time
from fnmatch import fnmatchcase
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GROUPS = load("tests/conftest.py", "test_group_contract")
CLOCK = load("tests/fixtures/ansible/retry_playbook.py", "test_retry_clock")


def test_module_shards_are_disjoint_complete_and_keep_parameter_cases_together():
    items = [SimpleNamespace(path=Path(name), get_closest_marker=lambda marker: True) for name in ["a.py", "b.py", "a.py", "c.py", "d.py"]]
    partitions = []
    for index in range(3):
        removed = []
        config = SimpleNamespace(
            getoption=lambda option, index=index: f"{index}/3",
            hook=SimpleNamespace(pytest_deselected=lambda items, removed=removed: removed.extend(items)),
        )
        selected = items.copy()
        GROUPS.pytest_collection_modifyitems(config, selected)
        assert len(selected) + len(removed) == len(items)
        partitions.append(selected)
    assert sorted(id(item) for partition in partitions for item in partition) == sorted(map(id, items))
    assert next(i for i, group in enumerate(partitions) if items[0] in group) == next(
        i for i, group in enumerate(partitions) if items[2] in group
    )


@pytest.mark.parametrize("value", ["bad", "1/0", "2/2", "-1/2", "0/-2"])
def test_bad_shards_are_rejected(value):
    with pytest.raises(pytest.UsageError, match="INDEX/COUNT"):
        GROUPS.pytest_collection_modifyitems(SimpleNamespace(getoption=lambda option: value), [])


def test_sharding_cannot_silently_discard_unit_tests():
    item = SimpleNamespace(get_closest_marker=lambda marker: None)
    with pytest.raises(pytest.UsageError, match="only -m integration"):
        GROUPS.pytest_collection_modifyitems(SimpleNamespace(getoption=lambda option: "0/2"), [item])


def test_unit_process_boundary_rejects_an_unmarked_process():
    with pytest.raises(AssertionError, match="mark this regression integration"):
        subprocess.run(["must-not-execute-nonproduction"])


def test_retry_clock_only_shortens_synthetic_backoffs(tmp_path, monkeypatch):
    log = tmp_path / "sleeps.jsonl"
    monkeypatch.setenv("ANSIBLE_TEST_RETRY_LOG", str(log))
    observed = []
    monkeypatch.setattr(CLOCK.time, "sleep", observed.append)
    clock = CLOCK.RetryClock()
    clock.sleep(2)
    assert observed == [0.001] and log.read_text() == "2\n"
    assert clock.monotonic is time.monotonic


@pytest.mark.integration
@pytest.mark.parametrize(
    "quality,tests",
    [
        ("success", "success"),
        ("failure", "success"),
        ("cancelled", "success"),
        ("skipped", "success"),
        ("success", "failure"),
        ("success", "cancelled"),
        ("success", "skipped"),
    ],
)
def test_existing_required_lint_gate_propagates_all_group_failures(quality, tests):
    workflow = yaml.safe_load((ROOT / ".github/workflows/lint.yml").read_text())
    gate = workflow["jobs"]["lint"]
    assert gate["if"] == "always()" and set(gate["needs"]) == {"quality", "tests"}
    assert workflow["jobs"]["tests"]["strategy"]["fail-fast"] is False
    step = gate["steps"][0]
    assert step["env"] == {"QUALITY_RESULT": "${{ needs.quality.result }}", "TEST_RESULT": "${{ needs.tests.result }}"}
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", step["run"]],
        env={**os.environ, "QUALITY_RESULT": quality, "TEST_RESULT": tests},
        capture_output=True,
        text=True,
    )
    assert (result.returncode == 0) is (quality == tests == "success")


def test_workflow_filters_feature_pushes_but_keeps_pr_updates_and_main_validation():
    # BaseLoader preserves the GitHub YAML key "on" rather than YAML 1.1's boolean.
    workflow = yaml.load((ROOT / ".github/workflows/lint.yml").read_text(), Loader=yaml.BaseLoader)
    triggers = workflow["on"]
    assert set(triggers) == {"push", "pull_request"}
    assert triggers["push"]["branches"] == ["main"]
    assert set(triggers["pull_request"]) == {"paths"}  # Includes synchronize/reopened by default.
    assert triggers["push"]["paths"] == triggers["pull_request"]["paths"]
    for event, branch, path, expected in [
        ("push", "feat/mgt-podman-migration", "ansible/playbook.yml", False),
        ("pull_request", "feat/mgt-podman-migration", "ansible/playbook.yml", True),
        ("push", "main", "ansible/playbook.yml", True),
        ("pull_request", "other-feature", "tests/unit/test_test_execution.py", True),
        ("pull_request", "other-feature", ".github/workflows/lint.yml", True),
        ("push", "main", "unrelated.txt", False),
    ]:
        trigger = triggers[event]
        selected = ("branches" not in trigger or branch in trigger["branches"]) and any(
            fnmatchcase(path, pattern) for pattern in trigger["paths"]
        )
        assert selected is expected, (event, branch, path)


def test_superseded_runs_share_a_concurrency_group_without_cancelling_other_prs():
    workflow = yaml.safe_load((ROOT / ".github/workflows/lint.yml").read_text())
    concurrency = workflow["concurrency"]
    assert concurrency["cancel-in-progress"] is True

    def group(ref, pr=None, name=workflow["name"], sha="first-revision"):
        values = {"github.workflow": name, "github.event.pull_request.number": pr, "github.ref": ref, "github.sha": sha}

        # Evaluate only the dotted-context fallback expressions used by this key;
        # unknown contexts fail instead of silently modelling them incorrectly.
        def expand(match):
            return next(str(values[key.strip()]) for key in match[1].split("||") if values[key.strip()])

        return re.sub(r"\$\{\{(.*?)\}\}", expand, concurrency["group"])

    assert group("refs/pull/680/merge", 680) == group("refs/pull/680/head", 680)
    assert group("refs/pull/680/merge", 680) != group("refs/pull/681/merge", 681)
    assert group("refs/heads/main") == group("refs/heads/main", sha="next-revision")
    assert group("refs/heads/main") != group("refs/heads/feature")
    assert group("refs/heads/main") != group("refs/pull/680/merge", 680)
    assert group("refs/pull/680/merge", 680) != group("refs/pull/680/merge", 680, "Other workflow")
