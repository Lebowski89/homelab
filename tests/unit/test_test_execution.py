"""Keep CI partitions complete and their required result gate fail-closed."""

import importlib.util
import os
import subprocess
import time
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
    [("success", "success"), ("failure", "success"), ("success", "failure"), ("success", "cancelled"), ("skipped", "success")],
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
