"""Provide runtime-neutral helpers for Ansible application preparation.

The ``service_prepare`` role uses these filters to select the runtime-specific
temporary-container task file, derive bounded collision-resistant container
names, and extract explicitly prefixed values from preparation output.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from ansible.errors import AnsibleFilterError

_RUNTIMES = {"docker", "podman"}
_RUNTIME_PHASES = {"start", "remove"}
_INVALID_NAME = re.compile(r"[^a-z0-9_.-]+")


def service_prepare_runtime_executor(runtime: Any, phase: Any) -> str:
    """Return the task path for one temporary-container runtime phase.

    Args:
        runtime: Runtime name, normalized to lowercase. Supported values are
            ``docker`` and ``podman``.
        phase: Lifecycle phase, normalized to lowercase. Supported values are
            ``start`` and ``remove``.

    Returns:
        A role-relative task path such as
        ``runtimes/docker/temporary_container_start.yml``.

    Raises:
        AnsibleFilterError: If the runtime or phase is unsupported or empty.
    """
    runtime_name = str(runtime or "").strip().lower()
    phase_name = str(phase or "").strip().lower()
    if runtime_name not in _RUNTIMES:
        raise AnsibleFilterError(
            f"temporary preparation runtime must be one of {', '.join(sorted(_RUNTIMES))}; got {runtime_name or '<empty>'}"
        )
    if phase_name not in _RUNTIME_PHASES:
        raise AnsibleFilterError(
            f"temporary preparation phase must be one of {', '.join(sorted(_RUNTIME_PHASES))}; got {phase_name or '<empty>'}"
        )
    return f"runtimes/{runtime_name}/temporary_container_{phase_name}.yml"


def service_prepare_temporary_name(service_name: Any, target: Any, purpose: Any) -> str:
    """Build a deterministic runtime-safe temporary container name.

    The optional target participates in both the readable slug and the digest.
    Unsafe characters are collapsed to hyphens, the slug is bounded to 44
    characters, and a ten-character SHA-256 prefix protects distinct long or
    similarly sanitized identities from collisions.

    Args:
        service_name: Required service identity.
        target: Optional selected target identity.
        purpose: Required description of the preparation operation.

    Returns:
        A name beginning with ``prepare-`` and ending in a stable digest.

    Raises:
        AnsibleFilterError: If service or purpose is empty, or sanitization
            leaves no runtime-safe characters.
    """
    components = [str(service_name or "").strip(), str(target or "").strip(), str(purpose or "").strip()]
    if not components[0] or not components[2]:
        raise AnsibleFilterError("temporary preparation names require non-empty service and purpose values")

    identity = "-".join(component for component in components if component)
    slug = _INVALID_NAME.sub("-", identity.lower()).strip("-._")
    if not slug:
        raise AnsibleFilterError("temporary preparation name did not contain any runtime-safe characters")
    digest = hashlib.sha256(identity.encode()).hexdigest()[:10]
    return f"prepare-{slug[:44].rstrip('-._')}-{digest}"


def service_prepare_extract_output(output: Any, prefix: Any) -> str:
    """Extract the first preparation-output line with an expected prefix.

    Args:
        output: A list of line-like values or any value converted to text and
            split into lines.
        prefix: Required literal prefix marking the value-bearing line.

    Returns:
        The trimmed text following the first matching prefix, or an empty string
        when no line matches.

    Raises:
        AnsibleFilterError: If ``prefix`` is empty.

    Note:
        The supplied output list is not mutated.
    """
    expected_prefix = str(prefix or "")
    if not expected_prefix:
        raise AnsibleFilterError("temporary preparation output prefix must be non-empty")
    lines = output if isinstance(output, list) else str(output or "").splitlines()
    for line in lines:
        text = str(line)
        if text.startswith(expected_prefix):
            return text.removeprefix(expected_prefix).strip()
    return ""


class FilterModule:
    """Register application-preparation filters with Ansible."""

    def filters(self) -> dict[str, Any]:
        """Return all Jinja filters exposed by this plugin.

        Returns:
            A mapping exposing ``service_prepare_runtime_executor``,
            ``service_prepare_temporary_name``, and
            ``service_prepare_extract_output``.
        """
        return {
            "service_prepare_runtime_executor": service_prepare_runtime_executor,
            "service_prepare_temporary_name": service_prepare_temporary_name,
            "service_prepare_extract_output": service_prepare_extract_output,
        }
