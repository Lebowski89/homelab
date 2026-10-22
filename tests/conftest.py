"""Keep process-level regressions explicit and CI shards disjoint by module."""

import hashlib
import subprocess

import pytest


def integration_shard(path, count):
    # Keep module-scoped immutable fixtures together, independent of test ordering
    # or parametrization. Each CI shard has its own VM, environment and files.
    return int.from_bytes(hashlib.sha256(path.name.encode()).digest()[:4], "big") % count


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
        (selected if integration_shard(item.path, count) == index else deselected).append(item)
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
