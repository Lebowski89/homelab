from __future__ import annotations

import posixpath
import re
from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from typing import Any

from ansible.errors import AnsibleFilterError

_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_RESOURCE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_MODE_RE = re.compile(r"^0[0-7]{3}$")


def _mapping(value: Any, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AnsibleFilterError(f"{name} must be a mapping")
    return value


def _text(value: Any) -> str:
    return str(value or "").strip()


def _strict_bool(value: Any, *, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in {0, 1}:
            return bool(value)
        raise AnsibleFilterError(f"{name} must be a boolean or integer 0/1, got {value!r}")
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "on", "1"}:
            return True
        if normalized in {"false", "no", "off", "0"}:
            return False
    raise AnsibleFilterError(f"{name} must be a strict boolean value, got {value!r}")


def _nonempty_text(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AnsibleFilterError(f"{name} must be a non-empty string")
    return value.strip()


def _resource_name(value: Any, *, name: str) -> str:
    result = _nonempty_text(value, name=name)
    if not _RESOURCE_NAME_RE.fullmatch(result):
        raise AnsibleFilterError(f"{name} must be a valid runtime resource name matching {_RESOURCE_NAME_RE.pattern}")
    return result


def _numeric_id(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip().isdigit():
        raise AnsibleFilterError(f"{name} must be a numeric string")
    return value.strip()


def _mode(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not _MODE_RE.fullmatch(value):
        raise AnsibleFilterError(f'{name} must be a quoted four-digit octal mode such as "0400"')
    return value


def _absolute_target(value: Any, *, name: str, default: str) -> str:
    target = default if value is None else _nonempty_text(value, name=name)
    if not posixpath.isabs(target):
        raise AnsibleFilterError(f"{name} must be an absolute path")
    return target


def _podman_options(value: Any, *, name: str) -> dict[str, bool]:
    options = _mapping(value, name=name)
    unsupported = set(options) - {"immutable", "replace"}
    if unsupported:
        raise AnsibleFilterError(f"{name} contains unsupported fields: {', '.join(sorted(unsupported))}")
    result = {
        "immutable": _strict_bool(options.get("immutable", False), name=f"{name}.immutable"),
        "replace": _strict_bool(options.get("replace", False), name=f"{name}.replace"),
    }
    if result["immutable"] and result["replace"]:
        raise AnsibleFilterError(f"{name} cannot set both immutable and replace to true")
    return result


def _runtime_options(value: Any, *, name: str) -> dict[str, Any]:
    options = _mapping(value, name=name)
    unsupported = set(options) - {"podman"}
    if unsupported:
        raise AnsibleFilterError(f"{name} contains unsupported runtimes: {', '.join(sorted(unsupported))}")
    result: dict[str, Any] = {}
    if "podman" in options:
        result["podman"] = _podman_options(options["podman"], name=f"{name}.podman")
    return result


def _canonical_secret(value: Any, *, var: str, name: str) -> dict[str, Any]:
    secret = _mapping(value, name=name)
    unsupported = set(secret) - {"name", "target", "uid", "gid", "mode", "runtime_options"}
    if unsupported:
        raise AnsibleFilterError(f"{name} contains unsupported fields: {', '.join(sorted(unsupported))}")
    resource_name = _resource_name(secret.get("name"), name=f"{name}.name")
    result: dict[str, Any] = {
        "name": resource_name,
        "var": var,
        "target": _absolute_target(
            secret.get("target"),
            name=f"{name}.target",
            default=f"/run/secrets/{resource_name}",
        ),
        "runtime_options": _runtime_options(secret.get("runtime_options", {}), name=f"{name}.runtime_options"),
        "origins": ["canonical"],
    }
    for field, converter in (("uid", _numeric_id), ("gid", _numeric_id), ("mode", _mode)):
        if field in secret:
            result[field] = converter(secret[field], name=f"{name}.{field}")
    return result


def _legacy_podman_secret(value: Any, *, name: str) -> tuple[dict[str, str], dict[str, Any]]:
    secret = _mapping(value, name=name)
    supported = {"name", "infisical_path", "infisical_key", "target", "uid", "gid", "mode", "immutable", "replace"}
    unsupported = set(secret) - supported
    if unsupported:
        raise AnsibleFilterError(f"{name} contains unsupported fields: {', '.join(sorted(unsupported))}")
    resource_name = _resource_name(secret.get("name"), name=f"{name}.name")
    lookup = {
        "var": resource_name,
        "path": _nonempty_text(secret.get("infisical_path"), name=f"{name}.infisical_path"),
        "name": _nonempty_text(secret.get("infisical_key"), name=f"{name}.infisical_key"),
    }
    declaration: dict[str, Any] = {
        "name": resource_name,
        "var": resource_name,
        "target": _absolute_target(secret.get("target"), name=f"{name}.target", default=f"/run/secrets/{resource_name}"),
        "runtime_options": {
            "podman": _podman_options(
                {"immutable": secret.get("immutable", False), "replace": secret.get("replace", False)},
                name=f"{name}.policy",
            )
        },
        "origins": ["legacy_podman"],
    }
    for field, converter in (("uid", _numeric_id), ("gid", _numeric_id), ("mode", _mode)):
        if field in secret:
            declaration[field] = converter(secret[field], name=f"{name}.{field}")
    return lookup, declaration


def _docker_attachments(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, str):
        entries: list[Any] = [value]
    elif isinstance(value, Iterable) and not isinstance(value, Mapping):
        entries = list(value)
    else:
        raise AnsibleFilterError("service_common_legacy_docker_secrets must be a string or list")
    result: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        item_name = f"service_common_legacy_docker_secrets[{index}]"
        if isinstance(entry, str):
            source = _resource_name(entry, name=item_name)
            result.append(
                {
                    "name": source,
                    "target": f"/run/secrets/{source}",
                    "runtime_options": {},
                    "origins": ["legacy_docker_attachment"],
                }
            )
            continue
        attachment = _mapping(entry, name=item_name)
        unsupported = set(attachment) - {"source", "target", "uid", "gid", "mode"}
        if unsupported:
            raise AnsibleFilterError(f"{item_name} contains unsupported fields: {', '.join(sorted(unsupported))}")
        source = _resource_name(attachment.get("source"), name=f"{item_name}.source")
        raw_target = _nonempty_text(attachment.get("target"), name=f"{item_name}.target")
        target = raw_target if posixpath.isabs(raw_target) else f"/run/secrets/{raw_target}"
        declaration: dict[str, Any] = {
            "name": source,
            "target": target,
            "runtime_options": {},
            "origins": ["legacy_docker_attachment"],
        }
        for field in ("uid", "gid", "mode"):
            if field in attachment:
                declaration[field] = str(attachment[field])
        result.append(declaration)
    return result


def _merge_declaration(current: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    if current["name"] != incoming["name"]:
        raise AnsibleFilterError(f"conflicting secret declaration: name differs ({current['name']!r} vs {incoming['name']!r})")
    result = dict(current)
    for field in ("var", "target", "uid", "gid", "mode"):
        if field in result and field in incoming and result[field] != incoming[field]:
            raise AnsibleFilterError(f"conflicting secret declaration for {result['name']!r}: {field} differs")
        if field not in result and field in incoming:
            result[field] = incoming[field]
    current_options = result.get("runtime_options", {})
    incoming_options = incoming.get("runtime_options", {})
    if current_options and incoming_options and current_options != incoming_options:
        raise AnsibleFilterError(f"conflicting secret declaration for {result['name']!r}: runtime_options differ")
    result["runtime_options"] = current_options or incoming_options
    result["origins"] = list(dict.fromkeys([*result.get("origins", []), *incoming.get("origins", [])]))
    return result


def _identifier(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AnsibleFilterError(f"{name} must be a non-empty identifier")
    result = value.strip()
    if not _IDENTIFIER_RE.fullmatch(result):
        raise AnsibleFilterError(f"{name} must match {_IDENTIFIER_RE.pattern}")
    return result


def _environment_key(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not _ENV_KEY_RE.fullmatch(value):
        raise AnsibleFilterError(f"{name} must match {_ENV_KEY_RE.pattern}")
    return value


def _environment_scalar(value: Any, *, name: str) -> Any:
    if value is None or isinstance(value, (bool, int)):
        return value
    if not isinstance(value, str):
        raise AnsibleFilterError(f"{name} must be a string, integer, boolean, null, or a supported typed mapping")
    if any(character in value for character in ("\r", "\n", "\0")):
        raise AnsibleFilterError(f"{name} must not contain carriage returns, line feeds, or NUL bytes")
    return value


def _declared_infisical_vars(config: Any) -> set[str]:
    config_mapping = _mapping(config, name="service_common_infisical_config")
    secrets_map = config_mapping.get("secrets_map", [])
    if not isinstance(secrets_map, list):
        raise AnsibleFilterError("service_common_infisical_config.secrets_map must be a list")
    declared: set[str] = set()
    for index, entry in enumerate(secrets_map):
        item_name = f"service_common_infisical_config.secrets_map[{index}]"
        entry_mapping = _mapping(entry, name=item_name)
        var = _identifier(entry_mapping.get("var"), name=f"{item_name}.var")
        if var in declared:
            raise AnsibleFilterError(f"duplicate Infisical var {var!r}")
        declared.add(var)
    return declared


def _template_parts(value: Any, *, name: str) -> list[tuple[str, str]]:
    if not isinstance(value, str):
        raise AnsibleFilterError(f"{name} must be a string")
    parts: list[tuple[str, str]] = []
    literal: list[str] = []
    index = 0
    while index < len(value):
        character = value[index]
        if character != "$":
            literal.append(character)
            index += 1
            continue
        if index + 1 < len(value) and value[index + 1] == "$":
            literal.append("$")
            index += 2
            continue
        if index + 1 >= len(value) or value[index + 1] != "{":
            raise AnsibleFilterError(f"{name} contains an unescaped dollar sign; use $$ for a literal dollar")
        closing = value.find("}", index + 2)
        if closing < 0:
            raise AnsibleFilterError(f"{name} contains a malformed ${{...}} reference")
        reference = value[index + 2 : closing]
        reference = _identifier(reference, name=f"{name} reference")
        if literal:
            parts.append(("literal", "".join(literal)))
            literal = []
        parts.append(("reference", reference))
        index = closing + 1
    if literal:
        parts.append(("literal", "".join(literal)))
    return parts


def _referenced_value(var: str, values: Mapping[str, Any], config: Mapping[str, Any], *, name: str) -> Any:
    if var not in values:
        raise AnsibleFilterError(f"{name} references declared Infisical var {var!r}, but no fetched value is available")
    value = values[var]
    _environment_scalar(value, name=f"{name} resolved value")
    if config.get("fail_on_empty", True) and not str(value if value is not None else "").strip():
        raise AnsibleFilterError(f"{name} resolved to an empty value while fail_on_empty is enabled")
    return value


def service_common_environment_normalize(environment: Any, config: Any) -> dict[str, Any]:
    environment_mapping = _mapping(environment, name="service_common_environment")
    declared = _declared_infisical_vars(config)
    result: dict[str, Any] = {}
    for raw_key, raw_value in environment_mapping.items():
        key = _environment_key(raw_key, name="service_common_environment key")
        item_name = f"service_common_environment.{key}"
        if not isinstance(raw_value, Mapping):
            result[key] = _environment_scalar(raw_value, name=item_name)
            continue
        fields = set(raw_value)
        if fields == {"value_from"}:
            value_from = _mapping(raw_value["value_from"], name=f"{item_name}.value_from")
            if set(value_from) != {"infisical"}:
                unsupported = sorted(set(value_from) - {"infisical"})
                if unsupported:
                    raise AnsibleFilterError(f"{item_name}.value_from contains unsupported sources: {unsupported}")
                raise AnsibleFilterError(f"{item_name}.value_from must contain exactly one infisical source")
            var = _identifier(value_from["infisical"], name=f"{item_name}.value_from.infisical")
            if var not in declared:
                raise AnsibleFilterError(f"{item_name} references undeclared Infisical var {var!r}")
            result[key] = {"value_from": {"infisical": var}}
            continue
        if fields == {"value_template"}:
            template = raw_value["value_template"]
            parts = _template_parts(template, name=f"{item_name}.value_template")
            references = [content for kind, content in parts if kind == "reference"]
            if not references:
                raise AnsibleFilterError(f"{item_name}.value_template must contain at least one ${{variable_name}} reference")
            undeclared = [var for var in references if var not in declared]
            if undeclared:
                raise AnsibleFilterError(f"{item_name} references undeclared Infisical var {undeclared[0]!r}")
            result[key] = {"value_template": template}
            continue
        if "value_from" in fields and "value_template" in fields:
            raise AnsibleFilterError(f"{item_name} cannot contain both value_from and value_template")
        allowed = {"value_from", "value_template"}
        unsupported = sorted(fields - allowed)
        if unsupported:
            raise AnsibleFilterError(f"{item_name} contains unsupported fields: {unsupported}")
        raise AnsibleFilterError(f"{item_name} must contain exactly one of value_from or value_template")
    return result


def service_common_environment_resolve(environment: Any, values: Any, config: Any) -> dict[str, Any]:
    config_mapping = _mapping(config, name="service_common_infisical_config")
    values_mapping = _mapping(values, name="service_common_infisical_values")
    normalized = service_common_environment_normalize(environment, config_mapping)
    result: dict[str, Any] = {}
    for key, entry in normalized.items():
        item_name = f"service_common_environment.{key}"
        if not isinstance(entry, Mapping):
            result[key] = deepcopy(entry)
            continue
        if "value_from" in entry:
            var = entry["value_from"]["infisical"]
            result[key] = deepcopy(_referenced_value(var, values_mapping, config_mapping, name=item_name))
            continue
        rendered: list[str] = []
        for kind, content in _template_parts(entry["value_template"], name=f"{item_name}.value_template"):
            if kind == "literal":
                rendered.append(content)
                continue
            value = _referenced_value(content, values_mapping, config_mapping, name=item_name)
            if value is None:
                rendered.append("")
            elif isinstance(value, bool):
                rendered.append("true" if value else "false")
            else:
                rendered.append(str(value))
        result[key] = "".join(rendered)
    return result


def service_common_infisical_check_values(config: Any) -> dict[str, str]:
    declared = sorted(_declared_infisical_vars(config))
    return {var: ("check-mode.invalid" if var == "cloudflare_zone" else f"__CHECK_MODE_REDACTED_INFISICAL_{var}__") for var in declared}


def service_common_infisical_normalize(
    secrets_map: Any,
    fail_on_empty: Any = True,
    legacy_docker_secrets: Any = None,
    legacy_podman_secrets: Any = None,
) -> dict[str, Any]:
    if not isinstance(secrets_map, list):
        raise AnsibleFilterError("service_common_infisical_secrets_map must be a list")

    normalized: list[dict[str, str]] = []
    declarations: dict[str, dict[str, Any]] = {}
    lookup_by_var: dict[str, dict[str, str]] = {}
    seen_vars: set[str] = set()
    for index, entry in enumerate(secrets_map):
        item_name = f"service_common_infisical_secrets_map[{index}]"
        if not isinstance(entry, Mapping):
            raise AnsibleFilterError(f"{item_name} must be a mapping")
        item: dict[str, str] = {}
        unsupported_entry = set(entry) - {"var", "path", "name", "secret", "docker_secret"}
        if unsupported_entry:
            raise AnsibleFilterError(f"{item_name} contains unsupported fields: {', '.join(sorted(unsupported_entry))}")
        for field in ("var", "path", "name"):
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                raise AnsibleFilterError(f"{item_name}.{field} must be a non-empty string")
            item[field] = value.strip()
        item["var"] = _identifier(item["var"], name=f"{item_name}.var")
        if item["var"] in seen_vars:
            raise AnsibleFilterError(f"duplicate Infisical var {item['var']!r}")
        seen_vars.add(item["var"])
        normalized.append(item)

        declaration = None
        if "secret" in entry:
            declaration = _canonical_secret(entry["secret"], var=item["var"], name=f"{item_name}.secret")
        if "docker_secret" in entry:
            docker_name = _resource_name(entry["docker_secret"], name=f"{item_name}.docker_secret")
            legacy_declaration = {
                "name": docker_name,
                "var": item["var"],
                "target": f"/run/secrets/{docker_name}",
                "runtime_options": {},
                "origins": ["legacy_docker_secret"],
            }
            declaration = legacy_declaration if declaration is None else _merge_declaration(declaration, legacy_declaration)
        if declaration is not None:
            existing = declarations.get(declaration["name"])
            declarations[declaration["name"]] = declaration if existing is None else _merge_declaration(existing, declaration)
        lookup_by_var[item["var"]] = item

    for declaration in _docker_attachments(legacy_docker_secrets):
        existing = declarations.get(declaration["name"])
        declarations[declaration["name"]] = declaration if existing is None else _merge_declaration(existing, declaration)

    if legacy_podman_secrets is not None:
        if isinstance(legacy_podman_secrets, (str, Mapping)) or not isinstance(legacy_podman_secrets, Iterable):
            raise AnsibleFilterError("service_common_legacy_podman_secrets must be a list")
        for index, raw_secret in enumerate(legacy_podman_secrets):
            lookup, declaration = _legacy_podman_secret(
                raw_secret,
                name=f"service_common_legacy_podman_secrets[{index}]",
            )
            existing = declarations.get(declaration["name"])
            if existing is not None and "canonical" in existing.get("origins", []):
                canonical_lookup = lookup_by_var.get(existing["var"])
                if canonical_lookup is None or canonical_lookup["path"] != lookup["path"] or canonical_lookup["name"] != lookup["name"]:
                    raise AnsibleFilterError(f"conflicting secret declaration for {declaration['name']!r}: lookup differs")
                declaration["var"] = existing["var"]
            elif lookup["var"] in lookup_by_var:
                if lookup_by_var[lookup["var"]] != lookup:
                    raise AnsibleFilterError(f"duplicate Infisical var {lookup['var']!r} has conflicting lookup")
            else:
                normalized.append(lookup)
                lookup_by_var[lookup["var"]] = lookup
            declarations[declaration["name"]] = declaration if existing is None else _merge_declaration(existing, declaration)

    return {
        "secrets_map": normalized,
        "secret_declarations": list(declarations.values()),
        "fail_on_empty": _strict_bool(
            fail_on_empty,
            name="service_common_infisical_fail_on_empty",
        ),
    }


def service_common_infisical_finalize(values: Any, config: Any) -> dict[str, Any]:
    values = _mapping(values, name="service_common_infisical_values")
    config = _mapping(config, name="service_common_infisical_config")
    normalized = service_common_infisical_normalize(
        config.get("secrets_map"),
        config.get("fail_on_empty"),
    )
    result: dict[str, Any] = {}
    for entry in normalized["secrets_map"]:
        value = values.get(entry["var"], "")
        if normalized["fail_on_empty"] and not str(value if value is not None else "").strip():
            raise AnsibleFilterError("Infisical returned an empty required secret value")
        result[entry["var"]] = value
    return result


def _target_hosts(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise AnsibleFilterError("service_common_target_hosts must be a list")
    return [_text(item) for item in value if _text(item)]


def service_common_traefik_context(
    service: Mapping[str, Any],
    name: str,
    target_hosts: Sequence[str],
    base_zone: str,
    inventory_hosts: Mapping[str, Any],
) -> dict[str, Any]:
    service = _mapping(service, name="service_common_service")
    traefik = _mapping(service.get("traefik", {}), name="service_common_service.traefik")
    inventory_hosts = _mapping(inventory_hosts, name="hostvars")
    name = _text(name)
    if not name:
        raise AnsibleFilterError("service_common_name must be non-empty")

    exposure = _text(traefik.get("exposure", "public")) or "public"
    if exposure not in {"private", "public"}:
        raise AnsibleFilterError("traefik.exposure must be private or public")
    private = exposure == "private"

    configured_zone = _text(traefik.get("zone"))
    base_zone = _text(base_zone)
    if not configured_zone and not base_zone:
        raise AnsibleFilterError("service_common_traefik_base_zone or traefik.zone is required")
    zone = configured_zone or (f"int.{base_zone}" if private else base_zone)
    address = f"{_text(traefik.get('subdomain')) or name}.{zone}"

    try:
        port = int(traefik.get("port"))
    except (TypeError, ValueError):
        raise AnsibleFilterError("traefik.port must be a positive integer") from None
    if port < 1:
        raise AnsibleFilterError("traefik.port must be a positive integer")

    backend_mode = _text(traefik.get("backend_mode", "service")) or "service"
    if backend_mode not in {"host", "service"}:
        raise AnsibleFilterError("traefik.backend_mode must be host or service")
    backend_url = _text(traefik.get("backend_url"))
    backend_host = ""

    if not backend_url:
        if backend_mode == "host":
            backend_host = _text(traefik.get("backend_host"))
            if not backend_host:
                hosts = _target_hosts(target_hosts)
                backend_inventory = _text(traefik.get("backend_host_inventory"))
                if not backend_inventory and hosts:
                    backend_inventory = hosts[0]
                if not backend_inventory:
                    raise AnsibleFilterError(
                        "host backend requires traefik.backend_host, traefik.backend_host_inventory, or a common target host"
                    )
                if backend_inventory not in inventory_hosts:
                    raise AnsibleFilterError(f"Traefik backend inventory host {backend_inventory!r} is not in hostvars")
                backend_host_vars = _mapping(
                    inventory_hosts[backend_inventory],
                    name=f"hostvars[{backend_inventory!r}]",
                )
                backend_host = _text(backend_host_vars.get("local_ip"))
                if not backend_host:
                    raise AnsibleFilterError(f"hostvars[{backend_inventory!r}].local_ip is required for a host backend")
        else:
            backend_host = name
        backend_scheme = _text(traefik.get("backend_scheme", "http")) or "http"
        backend_url = f"{backend_scheme}://{backend_host}:{port}"

    themepark = traefik.get("themepark", {}) or {}
    themepark = _mapping(themepark, name="service_common_service.traefik.themepark")
    theme_app = _text(themepark.get("app"))
    theme = _text(themepark.get("theme"))
    theme_enabled = bool(theme_app and theme)
    internal_api_rules = traefik.get("internal_api_rules", []) or []
    if not isinstance(internal_api_rules, Sequence) or isinstance(internal_api_rules, str):
        raise AnsibleFilterError("traefik.internal_api_rules must be a list")

    return {
        "name": name,
        "private": private,
        "entrypoint": _text(traefik.get("entrypoint")) or ("https_private" if private else "https"),
        "address": address,
        "authelia_enabled": _text(traefik.get("sso")) == "authelia",
        "middleware_chain": _text(traefik.get("middleware_chain")) or f"{name}-{'private-' if private else ''}ui-chain",
        "internal_api": bool(traefik.get("internal_api", False)),
        "internal_api_rules": list(internal_api_rules),
        "headers_middleware": _text(traefik.get("headers_middleware")) or "secure-headers@file",
        "theme_enabled": theme_enabled,
        "theme_app": theme_app,
        "theme": theme,
        "backend_url": backend_url,
    }


class FilterModule:
    def filters(self) -> dict[str, Any]:
        return {
            "service_common_environment_normalize": service_common_environment_normalize,
            "service_common_environment_resolve": service_common_environment_resolve,
            "service_common_infisical_check_values": service_common_infisical_check_values,
            "service_common_infisical_finalize": service_common_infisical_finalize,
            "service_common_infisical_normalize": service_common_infisical_normalize,
            "service_common_traefik_context": service_common_traefik_context,
        }
