import base64
import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "netbox_destinations", Path(__file__).resolve().parents[2] / "ansible/operator/netbox-config-destinations.py"
)
config = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(config)

BEFORE = {"database": ["netbox-postgres", 5432], "redis": ["netbox-redis", 6379]}
AFTER = {"database": ["192.0.2.48", 15432], "redis": ["192.0.2.48", 16380]}
# Match the observed LSIO layout and its PostgreSQL string / Redis integer ports.
SOURCE = b"""# Non-production fixture; preserve unrelated configuration and comments.
EMAIL = {'PORT': 587, 'PASSWORD': 'NONPRODUCTION-mail'}
DATABASES = {'default': {
    'NAME': 'netbox', 'USER': 'NONPRODUCTION-user', 'PASSWORD': 'NONPRODUCTION-database',
    'HOST': "netbox-postgres", 'PORT': '5432', 'CONN_MAX_AGE': 300,
}}
REDIS = {
    'tasks': {'HOST': 'netbox-redis', 'PORT': 6379, 'PASSWORD': 'NONPRODUCTION-cache', 'DATABASE': 0, 'SSL': False},
    'caching': {'HOST': 'netbox-redis', 'PORT': 6379, 'PASSWORD': 'NONPRODUCTION-cache', 'DATABASE': 1, 'SSL': False},
}
UNRELATED = 'netbox-postgres:5432 netbox-redis:6379'
"""


def masked(source):
    for _, start, end in sorted(config.literals(source).values(), key=lambda row: row[1], reverse=True):
        source = source[:start] + b"<destination>" + source[end:]
    return source


def test_rewrite_observed_schema_changes_only_six_literals_and_is_idempotent():
    source = SOURCE.replace(b"'HOST': \"netbox-postgres\"", "# café\n    'HOST': \"netbox-postgres\"".encode())
    changed, did_change = config.rewrite(source, BEFORE, AFTER)
    assert did_change and masked(changed) == masked(source)
    fields = config.literals(changed)
    assert fields[("DATABASES", "default", "PORT")][0] == "15432"
    assert fields[("REDIS", "tasks", "PORT")][0] == 16380
    assert fields[("REDIS", "caching", "HOST")][0] == "192.0.2.48"
    assert config.rewrite(changed, BEFORE, AFTER) == (changed, False)


@pytest.mark.parametrize(
    "source",
    [
        SOURCE.replace(b"'5432'", b"True"),
        SOURCE.replace(b"'5432'", b"'5433'"),
        SOURCE.replace(b"'PORT': '5432'", b"'PORT': '5432', 'PORT': '5432'"),
        SOURCE.replace(b"'PORT': '5432'", b"'PORT': os.getenv('PORT')"),
        SOURCE.replace(b"'PORT': '5432'", b"'PORT': '15432'"),
        SOURCE + b"\nDATABASES['default']['HOST'] = 'elsewhere'\n",
        SOURCE + b"\nglobals().update({})\n",
        SOURCE + b"\nfrom other import DATABASES\n",
        SOURCE + b"\nfrom other import *\n",
        SOURCE + b"\ndef REDIS(): pass\n",
        SOURCE.replace(b"DATABASES =", b"OTHER ="),
    ],
)
def test_rejects_incomplete_mixed_dynamic_or_overridden_destinations(source):
    with pytest.raises(ValueError):
        config.rewrite(source, BEFORE, AFTER)


def test_parser_does_not_expose_invalid_source_or_credentials():
    with pytest.raises(ValueError) as error:
        config.rewrite(b"SECRET = 'NONPRODUCTION-private'\nBROKEN = (", BEFORE, AFTER)
    assert "NONPRODUCTION-private" not in str(error.value)
    assert error.value.__suppress_context__


@pytest.mark.integration
def test_atomic_apply_preserves_metadata_acl_xattrs_and_supports_rollback(tmp_path):
    path = tmp_path / "configuration.py"
    path.write_bytes(SOURCE)
    path.chmod(0o640)
    os.setxattr(path, "user.skynet-test", b"NONPRODUCTION-xattr")
    if shutil.which("setfacl"):
        subprocess.run(["setfacl", "-m", "u:65534:r--", str(path)], check=True)
    source, snapshot = config.read_snapshot(path)
    metadata, changed = config.apply(path, snapshot, BEFORE, AFTER)
    assert changed
    assert path.read_bytes() == config.rewrite(source, BEFORE, AFTER)[0]
    assert all(metadata[k] == snapshot[k] for k in ("owner", "mode", "nlink", "xattrs"))
    assert metadata["identity"] != snapshot["identity"]
    assert config.apply(path, metadata, BEFORE, AFTER) == (metadata, False)
    # The existing cold-group rollback restores the exact archived original bytes.
    archive = tmp_path / "baseline.tar"
    original = tmp_path / "original"
    original.mkdir()
    baseline = original / "configuration.py"
    baseline.write_bytes(source)
    baseline.chmod(snapshot["mode"])
    for key, value in snapshot["xattrs"].items():
        os.setxattr(baseline, key, base64.b64decode(value))
    subprocess.run(
        ["tar", "--acls", "--xattrs", "--numeric-owner", "-cf", str(archive), "-C", str(original), "configuration.py"], check=True
    )
    subprocess.run(["tar", "--acls", "--xattrs", "--numeric-owner", "-xf", str(archive), "-C", str(tmp_path)], check=True)
    assert path.read_bytes() == source
    restored = config.read_snapshot(path)[1]
    assert all(restored[k] == snapshot[k] for k in ("owner", "mode", "nlink", "xattrs"))
    assert not list(tmp_path.glob(".skynet-netbox-destinations-*"))


@pytest.mark.parametrize("change", ["contents", "identity", "mode", "hardlink", "symlink", "parent-alias"])
def test_apply_rejects_changed_identity_metadata_or_aliases_before_writes(tmp_path, change):
    folder = tmp_path / "real"
    folder.mkdir()
    path = folder / "configuration.py"
    path.write_bytes(SOURCE)
    _, snapshot = config.read_snapshot(path)
    if change == "contents":
        path.write_bytes(SOURCE + b"# changed\n")
    elif change == "identity":
        path.rename(folder / "old")
        path.write_bytes(SOURCE)
    elif change == "mode":
        path.chmod(0o400)
    elif change == "hardlink":
        os.link(path, folder / "alias")
    elif change == "symlink":
        path.rename(folder / "old")
        path.symlink_to(folder / "old")
    else:
        (tmp_path / "alias").symlink_to(folder)
        path = tmp_path / "alias/configuration.py"
    retained = path.read_bytes()
    with pytest.raises(ValueError):
        config.apply(path, snapshot, BEFORE, AFTER)
    assert path.read_bytes() == retained
    assert not list(folder.glob(".skynet-netbox-destinations-*"))


def test_failed_atomic_commit_preserves_original_and_cleans_only_its_temporary_file(tmp_path, monkeypatch):
    path = tmp_path / "configuration.py"
    path.write_bytes(SOURCE)
    _, snapshot = config.read_snapshot(path)

    def fail_commit(*args):
        raise OSError("NONPRODUCTION simulated commit failure")

    monkeypatch.setattr(config.os, "replace", fail_commit)
    with pytest.raises(OSError, match="simulated commit failure"):
        config.apply(path, snapshot, BEFORE, AFTER)
    assert config.read_snapshot(path)[1] == snapshot
    assert path.read_bytes() == SOURCE
    assert not list(tmp_path.glob(".skynet-netbox-destinations-*"))
