"""Keep process-level regressions explicit and CI shards disjoint by module."""

import json
import subprocess
from pathlib import Path

import pytest


def integration_shards(paths, count):
    # Estimates affect placement only: every collected module, including new
    # modules without history, is assigned. Keep module-scoped caches together.
    estimates = json.loads(Path(__file__).with_name("integration-durations.json").read_text())["modules"]
    costs = {path: estimates.get(path.name, 1.0) for path in set(paths)}
    loads = [0.0] * count
    assignments = {}
    for path in sorted(costs, key=lambda path: (-costs[path], path.as_posix())):
        index = min(range(count), key=lambda index: (loads[index], index))
        assignments[path] = index
        loads[index] += costs[path]
    return assignments


def pytest_addoption(parser):
    parser.addoption("--integration-shard", metavar="INDEX/COUNT", help="Select one zero-based module shard with -m integration")


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    value = config.getoption("--integration-shard")
    if not value:
        return
    try:
        index, count = map(int, value.split("/"))
        if not 0 <= index < count:
            raise ValueError
    except ValueError as error:
        raise pytest.UsageError("--integration-shard must be INDEX/COUNT with 0 <= INDEX < COUNT") from error
    selected, deselected = [], []
    for item in items:
        if item.get_closest_marker("integration") is None:
            raise pytest.UsageError("--integration-shard requires selecting only -m integration")
    assignments = integration_shards((item.path for item in items), count)
    for item in items:
        (selected if assignments[item.path] == index else deselected).append(item)
    items[:] = selected
    config.hook.pytest_deselected(items=deselected)


@pytest.fixture(autouse=True)
def unit_process_boundary(request, monkeypatch):
    if request.node.get_closest_marker("integration") is not None:
        return

    def forbidden(*args, **kwargs):
        raise AssertionError("Fast unit tests cannot launch processes; mark this regression integration")

    monkeypatch.setattr(subprocess, "Popen", forbidden)


@pytest.fixture(scope="session")
def go_cache(tmp_path_factory):
    # Share compiler output, never a test's mutable inputs, process or result.
    return tmp_path_factory.mktemp("go-build-cache")
