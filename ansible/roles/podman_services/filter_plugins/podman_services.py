from __future__ import annotations

import shlex
from collections.abc import Mapping
from typing import Any

from ansible.errors import AnsibleFilterError


def podman_env_quote(value: Any) -> str:
    return shlex.quote(str(value))


def podman_secret_policy(secret: Mapping[str, Any], state: str) -> dict[str, bool]:
    replace = bool(secret.get("replace", False))
    mutable_replace = state in {"update", "recreate"} and replace
    return {"force": mutable_replace, "skip_existing": not mutable_replace}


def podman_image_reference_drift(current: Mapping[str, Any], desired: str) -> dict[str, Any]:
    rc = int(current.get("rc", 1))
    stdout = str(current.get("stdout", "")).strip()
    if rc != 0:
        return {"drift": True, "missing": True, "message": f"Podman image reference drift: inspect failed; desired={desired}"}
    if stdout != desired:
        return {"drift": True, "missing": False, "message": f"Podman image reference drift: desired={desired}, current={stdout}"}
    return {"drift": False, "missing": False, "message": f"No Podman image reference drift detected; desired={desired}"}


def _validate_numeric_id(value: Any, *, name: str) -> None:
    text = str(value).strip()
    if not text.isdigit() or int(text) < 0:
        raise AnsibleFilterError(f"{name} must be a numeric, non-negative container ID")


def podman_service_normalize(cfg: Mapping[str, Any], name: str) -> dict[str, Any]:
    if not isinstance(cfg, Mapping):
        raise AnsibleFilterError(f"{name} must be a mapping")
    if str(cfg.get("runtime", "docker")) != "podman":
        raise AnsibleFilterError(f"{name}.runtime must be podman for podman_services")
    container = cfg.get("container", {})
    if not isinstance(container, Mapping):
        raise AnsibleFilterError(f"{name}.container must be a mapping")
    image = str(container.get("image", "")).strip()
    if not image or image.endswith(":latest") or ":" not in image.split("/")[-1]:
        raise AnsibleFilterError(f"{name}.container.image must be an exact, non-latest image tag")
    if "user" in container:
        raise AnsibleFilterError(f"{name}.container.user is not supported; use container.uid and container.gid")
    if "uid" in container or "gid" in container:
        if "uid" not in container or "gid" not in container:
            raise AnsibleFilterError(f"{name}.container.uid and {name}.container.gid must be defined together")
        _validate_numeric_id(container["uid"], name=f"{name}.container.uid")
        _validate_numeric_id(container["gid"], name=f"{name}.container.gid")
    ports = container.get("ports", []) or []
    for port in ports:
        if not isinstance(port, Mapping):
            raise AnsibleFilterError(f"{name}.container.ports entries require host and container ports")
        try:
            host_port = int(port.get("host", 0))
            container_port = int(port.get("container", 0))
        except (ValueError, TypeError):
            raise AnsibleFilterError(f"{name}.container.ports entries require numeric host and container ports")
        if host_port < 1 or container_port < 1:
            raise AnsibleFilterError(f"{name}.container.ports entries require host and container ports")
        if "host_ip" in port and str(port.get("host_ip", "")).strip() == "":
            raise AnsibleFilterError(f"{name}.container.ports.host_ip must not be empty when supplied")
    secrets = cfg.get("secrets", []) or []
    for secret in secrets:
        if not isinstance(secret, Mapping) or not secret.get("name") or not secret.get("infisical_path") or not secret.get("infisical_key"):
            raise AnsibleFilterError(f"{name}.secrets entries require name, infisical_path, and infisical_key")
        if bool(secret.get("immutable", False)) and bool(secret.get("replace", False)):
            raise AnsibleFilterError(f"{name}.secrets.{secret.get('name')} cannot be both immutable and replaceable")
    paths = cfg.get("host_paths", []) or []
    for path in paths:
        host_path = str(path.get("path", "")) if isinstance(path, Mapping) else ""
        if not host_path.startswith("/opt/"):
            raise AnsibleFilterError(f"{name}.host_paths paths must be absolute /opt paths by default; got {host_path!r}")
    volumes = cfg.get("volumes", []) or []
    for volume in volumes:
        if not isinstance(volume, Mapping) or not volume.get("name") or not volume.get("target"):
            raise AnsibleFilterError(f"{name}.volumes entries require name and target")
    network = cfg.get("network")
    if network is not None:
        if not isinstance(network, Mapping):
            raise AnsibleFilterError(f"{name}.network must be a mapping when supplied")
        if not network.get("name"):
            raise AnsibleFilterError(f"{name}.network.name is required when network is supplied")
        if not bool(network.get("delete_on_stop", False)):
            raise AnsibleFilterError(
                f"{name}.network is managed by podman_services and must be dedicated; "
                "set network.delete_on_stop: true. External/shared networks are not managed yet."
            )
    return {
        "name": name,
        "unit_name": container.get("name", name),
        "description": container.get("description", cfg.get("description", f"{name} Podman service")),
        "image": image,
        "container": dict(container),
        "env": dict(cfg.get("env", {}) or {}),
        "secrets": list(secrets),
        "host_paths": list(paths),
        "network": network,
        "volumes": list(volumes),
        "postgres": dict(cfg.get("postgres", {}) or {}),
        "traefik": dict(cfg.get("traefik", {}) or {}),
    }


class FilterModule:
    def filters(self) -> dict[str, Any]:
        return {
            "podman_service_normalize": podman_service_normalize,
            "podman_env_quote": podman_env_quote,
            "podman_image_reference_drift": podman_image_reference_drift,
            "podman_secret_policy": podman_secret_policy,
        }
