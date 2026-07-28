"""Build and attach Docker Swarm deploy configuration for Ansible.

The Docker role uses these filters to combine service deploy declarations with
named profile defaults, normalize placement and replica settings, and attach
the resulting Compose ``deploy`` mapping to an accumulated service dictionary.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from ansible.errors import AnsibleFilterError

_VALID_DEPLOY_MODES = {"replicated", "global"}


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _first_defined(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue

        if isinstance(value, str) and value.strip() == "":
            continue

        return value

    return None


def _as_str(value: Any, *, default: str = "") -> str:
    if value is None:
        return default

    return str(value).strip()


def _normalize_mode(value: Any) -> str:
    mode = _as_str(value, default="replicated")

    if mode not in _VALID_DEPLOY_MODES:
        raise AnsibleFilterError(f"deploy_mode must be 'replicated' or 'global' got {mode!r}.")

    return mode


def _normalize_replicas(value: Any) -> int:
    raw = _as_str(value, default="1")

    if not re.fullmatch(r"^[0-9]+$", raw):
        raise AnsibleFilterError(f"deploy_replicas must be a non-negative integer for replicated services. Got: {value!r}")

    return int(raw)


def _normalize_constraints(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        raw_items = value.split(",")
    elif isinstance(value, Iterable) and not isinstance(value, Mapping):
        raw_items = list(value)
    elif isinstance(value, Mapping):
        raise AnsibleFilterError("deploy_constraints must be a string or list, not a mapping.")
    else:
        raw_items = [value]

    return [str(item).strip() for item in raw_items if str(item).strip()]


def _normalize_profiles(value: Any) -> dict[str, Any]:
    if value is None:
        return {"none": {}}

    if not _is_mapping(value):
        raise AnsibleFilterError(f"docker_services_deploy_profiles must be a mapping, got {type(value).__name__}.")

    return deepcopy(dict(value))


def _normalize_profile_name(
    *,
    profile: Any,
    service_profile: Any,
    default_profile: Any,
) -> str:
    return _as_str(
        _first_defined(profile, service_profile, default_profile, "none"),
        default="none",
    )


def _validate_profile(
    *,
    profile_name: str,
    profiles: Mapping[str, Any],
) -> dict[str, Any]:
    if profile_name not in profiles:
        valid_profiles = ", ".join(sorted(str(key) for key in profiles))
        raise AnsibleFilterError(f"Unknown deploy profile {profile_name!r}. Valid profiles: {valid_profiles}")

    profile_defaults = profiles[profile_name]

    if not _is_mapping(profile_defaults):
        raise AnsibleFilterError(f"Deploy profile {profile_name!r} must be a mapping, got {type(profile_defaults).__name__}.")

    return deepcopy(dict(profile_defaults))


def _recursive_merge(base: Any, override: Any) -> Any:
    if _is_mapping(base) and _is_mapping(override):
        merged = deepcopy(dict(base))

        for key, value in override.items():
            if key in merged:
                merged[key] = _recursive_merge(merged[key], value)
            else:
                merged[key] = deepcopy(value)

        return merged

    return deepcopy(override)


def _subdict_from_profile(
    *,
    profile_defaults: Mapping[str, Any],
    explicit: Any,
    key: str,
) -> dict[str, Any]:
    default_value = profile_defaults.get(key, {})

    if default_value is None:
        default_value = {}

    if not _is_mapping(default_value):
        raise AnsibleFilterError(f"Deploy profile field {key!r} must be a mapping, got {type(default_value).__name__}.")

    if explicit is None:
        explicit_value = {}
    elif _is_mapping(explicit):
        explicit_value = explicit
    else:
        raise AnsibleFilterError(f"deploy_{key} override must be a mapping, got {type(explicit).__name__}.")

    return _recursive_merge(default_value, explicit_value)


def docker_services_build_deploy_config(
    deploy_cfg: Any = None,
    *,
    mode: Any = None,
    replicas: Any = None,
    constraints: Any = None,
    profile: Any = None,
    service_profile: Any = None,
    default_profile: Any = "none",
    profiles: Any = None,
    restart_policy: Any = None,
    update_config: Any = None,
    rollback_config: Any = None,
    resources: Any = None,
) -> dict[str, Any]:
    """Build a normalized Compose deploy mapping from defaults and overrides.

    Explicit function arguments take precedence over fields in ``deploy_cfg``.
    Profile selection falls back through the service profile, default profile,
    and ``none``. Profile mappings provide defaults for restart, update,
    rollback, and resource sections; explicit section mappings recursively
    override them. Global mode omits replicas.

    Args:
        deploy_cfg: Optional service-level deploy mapping.
        mode: Optional ``replicated`` or ``global`` override.
        replicas: Optional non-negative replica count.
        constraints: Optional comma-separated string or iterable of placement
            constraints.
        profile: Highest-precedence deploy profile name.
        service_profile: Service-level fallback profile name.
        default_profile: Repository fallback profile name.
        profiles: Mapping of profile names to deploy-section defaults. ``None``
            provides an empty ``none`` profile.
        restart_policy: Explicit restart-policy mapping override.
        update_config: Explicit update-config mapping override.
        rollback_config: Explicit rollback-config mapping override.
        resources: Explicit resources mapping override.

    Returns:
        A new Compose deploy mapping containing only populated sections.

    Raises:
        AnsibleFilterError: If modes, replicas, constraints, profiles, or deploy
            section mappings have unsupported values or shapes.

    Note:
        Input mappings are not mutated.
    """
    if deploy_cfg is None:
        deploy_cfg = {}

    if not _is_mapping(deploy_cfg):
        raise AnsibleFilterError(f"deploy config must be a mapping, got {type(deploy_cfg).__name__}.")

    deploy_cfg = dict(deploy_cfg)

    deploy_mode = _normalize_mode(_first_defined(mode, deploy_cfg.get("mode"), "replicated"))

    deploy_replicas = _normalize_replicas(_first_defined(replicas, deploy_cfg.get("replicas"), 1))

    deploy_constraints = _normalize_constraints(_first_defined(constraints, deploy_cfg.get("constraints")))

    deploy_profiles = _normalize_profiles(profiles)

    profile_name = _normalize_profile_name(
        profile=_first_defined(profile, deploy_cfg.get("profile")),
        service_profile=service_profile,
        default_profile=default_profile,
    )

    profile_defaults = _validate_profile(
        profile_name=profile_name,
        profiles=deploy_profiles,
    )

    deploy_restart_policy = _subdict_from_profile(
        profile_defaults=profile_defaults,
        explicit=_first_defined(restart_policy, deploy_cfg.get("restart_policy")),
        key="restart_policy",
    )

    deploy_update_config = _subdict_from_profile(
        profile_defaults=profile_defaults,
        explicit=_first_defined(update_config, deploy_cfg.get("update_config")),
        key="update_config",
    )

    deploy_rollback_config = _subdict_from_profile(
        profile_defaults=profile_defaults,
        explicit=_first_defined(rollback_config, deploy_cfg.get("rollback_config")),
        key="rollback_config",
    )

    deploy_resources = _subdict_from_profile(
        profile_defaults=profile_defaults,
        explicit=_first_defined(resources, deploy_cfg.get("resources")),
        key="resources",
    )

    deploy_dict: dict[str, Any] = {
        "mode": deploy_mode,
    }

    if deploy_mode == "replicated":
        deploy_dict["replicas"] = deploy_replicas

    if deploy_constraints:
        deploy_dict["placement"] = {
            "constraints": deploy_constraints,
        }

    if deploy_restart_policy:
        deploy_dict["restart_policy"] = deploy_restart_policy

    if deploy_update_config:
        deploy_dict["update_config"] = deploy_update_config

    if deploy_rollback_config:
        deploy_dict["rollback_config"] = deploy_rollback_config

    if deploy_resources:
        deploy_dict["resources"] = deploy_resources

    return deploy_dict


def docker_services_attach_deploy_config(
    compose_services: Any,
    service_name: Any,
    deploy_config: Any,
) -> dict[str, Any]:
    """Attach deploy configuration to one accumulated Compose service.

    Args:
        compose_services: Mapping of service names to Compose service mappings.
        service_name: Required service key after string conversion and trimming.
        deploy_config: Deploy mapping to recursively merge at ``deploy``.

    Returns:
        A new top-level mapping with an independently copied selected service;
        unrelated service entries are preserved.

    Raises:
        AnsibleFilterError: If the top-level mapping, selected service, deploy
            configuration, or service name is invalid.

    Note:
        Neither input mapping is mutated.
    """
    if not _is_mapping(compose_services):
        raise AnsibleFilterError(f"docker_services_compose_services must be a mapping, got {type(compose_services).__name__}.")

    normalized_service_name = _as_str(service_name)
    if not normalized_service_name:
        raise AnsibleFilterError("docker_services_service_name must be a non-empty string.")
    if not _is_mapping(deploy_config):
        raise AnsibleFilterError(f"deploy config must be a mapping, got {type(deploy_config).__name__}.")

    current_service = compose_services.get(normalized_service_name, {})
    if not _is_mapping(current_service):
        raise AnsibleFilterError(f"Compose service {normalized_service_name!r} must be a mapping, got {type(current_service).__name__}.")

    result = dict(compose_services)
    result[normalized_service_name] = _recursive_merge(
        current_service,
        {"deploy": deploy_config},
    )
    return result


class FilterModule:
    """Register Docker deploy-configuration filters with Ansible."""

    def filters(self) -> dict[str, Any]:
        """Return the Jinja filters exposed by this plugin.

        Returns:
            A mapping exposing ``docker_services_build_deploy_config`` and
            ``docker_services_attach_deploy_config``.
        """
        return {
            "docker_services_build_deploy_config": docker_services_build_deploy_config,
            "docker_services_attach_deploy_config": docker_services_attach_deploy_config,
        }
