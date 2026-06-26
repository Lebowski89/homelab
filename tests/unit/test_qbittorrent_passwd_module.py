from __future__ import annotations

import base64
import hashlib
import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "ansible/roles/docker_services/library/qbittorrent_passwd.py"


def load_module():
    spec = importlib.util.spec_from_file_location("qbittorrent_passwd", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)

    assert spec.loader is not None

    spec.loader.exec_module(module)
    return module


def parse_qbittorrent_hash(value: str) -> tuple[bytes, bytes]:
    assert value.startswith("@ByteArray(")
    assert value.endswith(")")

    payload = value.removeprefix("@ByteArray(").removesuffix(")")
    salt_b64, digest_b64 = payload.split(":", 1)

    return base64.b64decode(salt_b64), base64.b64decode(digest_b64)


def test_qbittorrent_passwd_generates_valid_pbkdf2_hash(monkeypatch: pytest.MonkeyPatch):
    module = load_module()
    salt = b"\x01" * 16

    monkeypatch.setattr(module.os, "urandom", lambda size: salt)

    result = module.qbittorrent_passwd("correct horse battery staple")
    decoded_salt, decoded_digest = parse_qbittorrent_hash(result)

    expected_digest = hashlib.pbkdf2_hmac(
        "sha512",
        b"correct horse battery staple",
        salt,
        100_000,
    )

    assert decoded_salt == salt
    assert decoded_digest == expected_digest


def test_qbittorrent_passwd_uses_16_byte_random_salt(monkeypatch: pytest.MonkeyPatch):
    module = load_module()
    calls: list[int] = []

    def fake_urandom(size: int) -> bytes:
        calls.append(size)
        return b"\x02" * size

    monkeypatch.setattr(module.os, "urandom", fake_urandom)

    result = module.qbittorrent_passwd("password")
    decoded_salt, _ = parse_qbittorrent_hash(result)

    assert calls == [16]
    assert decoded_salt == b"\x02" * 16


def test_qbittorrent_passwd_wraps_hashing_errors(monkeypatch: pytest.MonkeyPatch):
    module = load_module()

    def broken_urandom(_size: int) -> bytes:
        raise OSError("random unavailable")

    monkeypatch.setattr(module.os, "urandom", broken_urandom)

    with pytest.raises(ValueError, match="Error generating password hash: random unavailable"):
        module.qbittorrent_passwd("password")
