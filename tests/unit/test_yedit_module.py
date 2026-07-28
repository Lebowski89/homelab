from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "ansible/roles/service_prepare/library/yedit.py"


def load_module():
    spec = importlib.util.spec_from_file_location("yedit", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)

    assert spec.loader is not None

    spec.loader.exec_module(module)
    return module


def test_put_nested_key_and_repeated_put_is_idempotent():
    module = load_module()
    yamlfile = module.Yedit(content={})

    changed, result = yamlfile.put("app.settings.enabled", True)

    assert changed is True
    assert result == {
        "app": {
            "settings": {
                "enabled": True,
            },
        },
    }

    changed, result = yamlfile.put("app.settings.enabled", True)

    assert changed is False
    assert result == {
        "app": {
            "settings": {
                "enabled": True,
            },
        },
    }


def test_append_creates_missing_list_and_appends_value():
    module = load_module()
    yamlfile = module.Yedit(content={})

    changed, result = yamlfile.append("servers", "pg95")

    assert changed is True
    assert result == {
        "servers": ["pg95"],
    }

    changed, result = yamlfile.append("servers", "pg96")

    assert changed is True
    assert result == {
        "servers": ["pg95", "pg96"],
    }


def test_update_dict_merges_values():
    module = load_module()
    yamlfile = module.Yedit(
        content={
            "service": {
                "environment": {
                    "PUID": "1000",
                },
            },
        }
    )

    changed, result = yamlfile.update(
        "service.environment",
        {
            "PGID": "1000",
        },
    )

    assert changed is True
    assert result == {
        "service": {
            "environment": {
                "PUID": "1000",
                "PGID": "1000",
            },
        },
    }


def test_update_list_replaces_current_value_and_appends_missing_value():
    module = load_module()
    yamlfile = module.Yedit(
        content={
            "items": ["old"],
        }
    )

    changed, result = yamlfile.update("items", "new", curr_value="old")

    assert changed is True
    assert result == {
        "items": ["new"],
    }

    changed, result = yamlfile.update("items", "extra")

    assert changed is True
    assert result == {
        "items": ["new", "extra"],
    }


def test_delete_removes_list_index():
    module = load_module()
    yamlfile = module.Yedit(
        content={
            "items": ["first", "second", "third"],
        }
    )

    changed, result = yamlfile.delete("items[1]")

    assert changed is True
    assert result == {
        "items": ["first", "third"],
    }


def test_pop_removes_dict_key():
    module = load_module()
    yamlfile = module.Yedit(
        content={
            "environment": {
                "PUID": "1000",
                "PGID": "1000",
            },
        }
    )

    changed, result = yamlfile.pop("environment", "PGID")

    assert changed is True
    assert result == {
        "environment": {
            "PUID": "1000",
        },
    }


def test_parse_value_converts_yaml_scalar_and_rejects_invalid_bool():
    module = load_module()

    assert module.Yedit.parse_value("true", "bool") is True
    assert module.Yedit.parse_value("1000", "") == 1000
    assert module.Yedit.parse_value("1000", "str") == "1000"

    with pytest.raises(module.YeditException, match="Not a boolean type"):
        module.Yedit.parse_value("maybe", "bool")


def test_run_ansible_processes_multiple_content_edits():
    module = load_module()

    result = module.Yedit.run_ansible(
        {
            "src": None,
            "content": "service:\n  image: old\n  ports: []\n",
            "content_type": "yaml",
            "state": "present",
            "key": "",
            "value": None,
            "value_type": "",
            "update": False,
            "append": False,
            "insert": False,
            "index": None,
            "curr_value": None,
            "curr_value_format": "yaml",
            "backup": False,
            "backup_ext": ".bak",
            "separator": ".",
            "edits": [
                {
                    "key": "service.image",
                    "value": "new",
                },
                {
                    "key": "service.ports",
                    "value": "8080",
                    "action": "append",
                },
            ],
        }
    )

    assert result == {
        "changed": True,
        "result": [
            {
                "key": "service.image",
                "edit": {
                    "service": {
                        "image": "new",
                        "ports": [8080],
                    },
                },
            },
            {
                "key": "service.ports",
                "edit": {
                    "service": {
                        "image": "new",
                        "ports": [8080],
                    },
                },
            },
        ],
        "state": "present",
    }


def test_write_round_trips_existing_yaml_file(tmp_path: Path):
    module = load_module()
    target = tmp_path / "config.yml"
    target.write_text("service:\n  image: old\n")

    yamlfile = module.Yedit(filename=str(target))
    changed, _ = yamlfile.put("service.image", "new")

    assert changed is True

    write_changed, data = yamlfile.write()

    assert write_changed is True
    assert data["service"]["image"] == "new"

    reloaded = module.Yedit(filename=str(target))

    assert reloaded.get("service.image") == "new"
