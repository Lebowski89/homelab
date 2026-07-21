import importlib.util
from pathlib import Path

import pytest
from ansible.errors import AnsibleFilterError

MODULE_PATH = Path(__file__).resolve().parents[2] / "ansible" / "roles" / "podman_services" / "filter_plugins" / "podman_services.py"
spec = importlib.util.spec_from_file_location("podman_services", MODULE_PATH)
podman_services = importlib.util.module_from_spec(spec)
spec.loader.exec_module(podman_services)


def valid_cfg():
    return {
        "runtime": "podman",
        "container": {"image": "docker.io/n8nio/n8n:2.31.4", "ports": [{"host": 5678, "container": 5678}]},
        "host_paths": [{"path": "/opt/n8n"}],
        "secrets": [{"name": "postgres_user_secret", "infisical_path": "/Postgres", "infisical_key": "USER"}],
    }


def test_normalize_accepts_n8n_like_service():
    svc = podman_services.podman_service_normalize(valid_cfg(), "n8n")
    assert svc["image"] == "docker.io/n8nio/n8n:2.31.4"
    assert svc["secrets"][0]["name"] == "postgres_user_secret"


@pytest.mark.parametrize("image", ["docker.io/n8nio/n8n:latest", "docker.io/n8nio/n8n", ""])
def test_image_must_be_exact_non_latest(image):
    cfg = valid_cfg()
    cfg["container"]["image"] = image
    with pytest.raises(AnsibleFilterError, match="exact, non-latest"):
        podman_services.podman_service_normalize(cfg, "n8n")


def test_unsafe_path_fails():
    cfg = valid_cfg()
    cfg["host_paths"] = [{"path": "/root/.ssh"}]
    with pytest.raises(AnsibleFilterError, match="/opt"):
        podman_services.podman_service_normalize(cfg, "n8n")


def test_bad_secret_fails():
    cfg = valid_cfg()
    cfg["secrets"] = [{"name": "x"}]
    with pytest.raises(AnsibleFilterError, match="infisical"):
        podman_services.podman_service_normalize(cfg, "n8n")


def test_immutable_secret_cannot_be_replaceable():
    cfg = valid_cfg()
    cfg["secrets"] = [
        {
            "name": "n8n_encryption_key_secret",
            "infisical_path": "/N8N",
            "infisical_key": "ENCRYPTION_KEY",
            "immutable": True,
            "replace": True,
        }
    ]
    with pytest.raises(AnsibleFilterError, match="immutable"):
        podman_services.podman_service_normalize(cfg, "n8n")


def test_volume_requires_target():
    cfg = valid_cfg()
    cfg["volumes"] = [{"name": "n8n-data"}]
    with pytest.raises(AnsibleFilterError, match="name and target"):
        podman_services.podman_service_normalize(cfg, "n8n")


def test_container_user_string_rejected():
    cfg = valid_cfg()
    cfg["container"]["user"] = "1000:1000"
    with pytest.raises(AnsibleFilterError, match="container.user"):
        podman_services.podman_service_normalize(cfg, "n8n")


def test_container_uid_gid_must_be_numeric():
    cfg = valid_cfg()
    cfg["container"]["uid"] = "abc"
    cfg["container"]["gid"] = "1000"
    with pytest.raises(AnsibleFilterError, match="numeric"):
        podman_services.podman_service_normalize(cfg, "n8n")


def test_managed_network_must_be_dedicated_delete_on_stop():
    cfg = valid_cfg()
    cfg["network"] = {"name": "shared", "driver": "bridge", "delete_on_stop": False}
    with pytest.raises(AnsibleFilterError, match="dedicated"):
        podman_services.podman_service_normalize(cfg, "sharedsvc")


def test_dedicated_managed_network_is_accepted():
    cfg = valid_cfg()
    cfg["network"] = {"name": "dedicated", "driver": "bridge", "delete_on_stop": True}
    svc = podman_services.podman_service_normalize(cfg, "dedicatedsvc")
    assert svc["network"]["delete_on_stop"] is True


def test_image_reference_drift_matching():
    result = podman_services.podman_image_reference_drift({"rc": 0, "stdout": "docker.io/n8nio/n8n:2.31.4"}, "docker.io/n8nio/n8n:2.31.4")
    assert result["drift"] is False
    assert "No Podman image reference drift" in result["message"]


def test_image_reference_drift_mismatching():
    result = podman_services.podman_image_reference_drift({"rc": 0, "stdout": "docker.io/n8nio/n8n:2.31.3"}, "docker.io/n8nio/n8n:2.31.4")
    assert result["drift"] is True
    assert result["missing"] is False


def test_image_reference_drift_missing_container():
    result = podman_services.podman_image_reference_drift({"rc": 125, "stdout": ""}, "docker.io/n8nio/n8n:2.31.4")
    assert result["drift"] is True
    assert result["missing"] is True


def test_secret_policy_deploy_preserves_existing_secret():
    policy = podman_services.podman_secret_policy({"replace": True}, "deploy")
    assert policy == {"force": False, "skip_existing": True}


def test_secret_policy_update_replaces_mutable_secret():
    policy = podman_services.podman_secret_policy({"replace": True}, "update")
    assert policy == {"force": True, "skip_existing": False}


def test_secret_policy_recreate_preserves_immutable_secret():
    policy = podman_services.podman_secret_policy({"replace": False}, "recreate")
    assert policy == {"force": False, "skip_existing": True}
