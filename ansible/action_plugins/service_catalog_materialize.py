"""Materialize selected service configurations in an Ansible host context.

The action plugin receives lightweight service-catalog entries, resolves each
entry through the repository's canonical target merge, and templates the
result with variables belonging to the current dispatch host. It returns the
materialized batch as a non-cacheable Ansible fact without reporting a change.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable, Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from ansible.errors import AnsibleActionFail, AnsibleError
from ansible.plugins.action import ActionBase

_SERVICE_CATALOG_PATH = Path(__file__).resolve().parents[1] / "filter_plugins/service_catalog.py"
_VALID_RUNTIMES = {"docker", "podman"}


def _load_canonical_merge():
    """Load the shared target-merge function without duplicating its behavior."""
    spec = importlib.util.spec_from_file_location("service_catalog_action", _SERVICE_CATALOG_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load canonical service catalog filter from {_SERVICE_CATALOG_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.service_catalog_merge_target


_CANONICAL_MERGE_TARGET = _load_canonical_merge()


def materialize_selected(
    services: Any,
    selected: Any,
    template_config: Callable[[dict[str, Any]], dict[str, Any]],
    merge_target: Callable[[Mapping[str, Any], str | None], dict[str, Any]] = _CANONICAL_MERGE_TARGET,
) -> list[dict[str, Any]]:
    """Resolve and template selected lightweight catalog entries.

    Each selected entry must name an existing service, declare a supported
    runtime, and omit ``config``. The canonical merge is called once per entry,
    after which ``template_config`` resolves host-local Ansible values. Input
    order is preserved.

    Args:
        services: Mapping of raw service names to service definitions.
        selected: List of lightweight catalog entry mappings.
        template_config: Callable that templates one merged configuration in
            the current dispatch host's variable context.
        merge_target: Callable used to merge a base service and optional target.
            Defaults to the repository's canonical service-catalog merger.

    Returns:
        Deep-copied catalog entries with one concrete ``config`` mapping added
        to each entry.

    Raises:
        AnsibleActionFail: If input shapes, names, runtimes, or targets are
            invalid, an entry already contains ``config``, or canonical merge or
            Ansible templating raises an ``AnsibleError``.

    Note:
        ``services`` and ``selected`` are not mutated.
    """
    if not isinstance(services, Mapping):
        raise AnsibleActionFail(f"services source must be a mapping, got {type(services).__name__}")
    if not isinstance(selected, list):
        raise AnsibleActionFail(f"selected entries must be a list, got {type(selected).__name__}")

    materialized: list[dict[str, Any]] = []
    for index, entry in enumerate(selected):
        if not isinstance(entry, Mapping):
            raise AnsibleActionFail(f"selected entry {index} must be a mapping, got {type(entry).__name__}")
        if "config" in entry:
            raise AnsibleActionFail(f"selected entry {index} must not already contain config")

        raw_name = entry.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise AnsibleActionFail(f"selected entry {index}.name must be a non-empty string, got {raw_name!r}")
        service_name = raw_name.strip()
        if service_name not in services:
            raise AnsibleActionFail(f"selected entry {index} references unknown service {service_name!r}")

        raw_runtime = entry.get("runtime")
        if not isinstance(raw_runtime, str) or raw_runtime.strip().lower() not in _VALID_RUNTIMES:
            raise AnsibleActionFail(
                f"selected entry {index} ({service_name!r}).runtime must be one of: docker, podman; got {raw_runtime!r}"
            )

        target_name: str | None = None
        if "target" in entry:
            raw_target = entry["target"]
            if not isinstance(raw_target, str) or not raw_target.strip():
                raise AnsibleActionFail(f"selected entry {index}.target must be a non-empty string, got {raw_target!r}")
            target_name = raw_target.strip()

        try:
            merged = merge_target(services[service_name], target_name)
            concrete = template_config(merged)
        except AnsibleError as error:
            raise AnsibleActionFail(f"Unable to materialize selected entry {index} ({service_name!r}): {error}") from error

        materialized_entry = deepcopy(dict(entry))
        materialized_entry["config"] = concrete
        materialized.append(materialized_entry)

    return materialized


class ActionModule(ActionBase):
    """Expose host-local service materialization as an Ansible action plugin."""

    _VALID_ARGS = frozenset({"source_var", "selected"})
    _supports_check_mode = True

    def run(self, tmp=None, task_vars=None):
        """Materialize the requested entries and publish a host-owned fact.

        Args:
            tmp: Optional temporary path supplied by Ansible's action executor.
            task_vars: Variables for the current inventory host. The task's
                ``source_var`` argument identifies the raw service mapping.

        Returns:
            The standard action result containing the non-cacheable
            ``service_catalog_host_materialized`` fact and ``changed: false``.

        Raises:
            AnsibleActionFail: If ``source_var`` is absent, empty, or undefined,
                or if selected entries cannot be materialized.

        Note:
            The action supports check mode and does not mutate ``task_vars``.
        """
        task_vars = task_vars or {}
        result = super().run(tmp, task_vars)

        source_var = self._task.args.get("source_var")
        if not isinstance(source_var, str) or not source_var.strip():
            raise AnsibleActionFail("source_var must be a non-empty string")
        source_var = source_var.strip()
        if source_var not in task_vars:
            raise AnsibleActionFail(f"source variable {source_var!r} is not defined")

        materialized = materialize_selected(
            task_vars[source_var],
            self._task.args.get("selected"),
            lambda config: self._templar.template(config, fail_on_undefined=True),
        )

        result["ansible_facts"] = {"service_catalog_host_materialized": materialized}
        result["_ansible_facts_cacheable"] = False
        result["changed"] = False
        return result
