"""Pure shared network validation; no inventory, DNS or remote connections."""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "network_validation", Path(__file__).resolve().parents[2] / "ansible/filter_plugins/network_validation.py"
)
NETWORK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NETWORK)


@pytest.mark.parametrize(
    "address, accepted",
    [
        ("192.0.2.10", True),
        ("192.168.1.10", True),
        ("100.64.0.10", True),
        ("2001:db8::10", True),
        ("::ffff:c000:20a", True),
        ("127.0.0.1", False),
        ("127.255.255.254", False),
        ("::1", False),
        ("::ffff:127.0.0.1", False),
        ("::ffff:7f00:1", False),
        ("localhost", False),
        ("localhost.localdomain", False),
        ("application.example", False),
        ("0.0.0.0", False),
        ("::", False),
        ("::ffff:0.0.0.0", False),
        ("255.255.255.255", False),
        ("::ffff:255.255.255.255", False),
        ("224.0.0.1", False),
        ("[2001:db8::10]", False),
        ("192.0.2.10/32", False),
        ("fe80::10%eth0", False),
        (" 192.0.2.10", False),
        (None, False),
        (True, False),
    ],
)
def test_numeric_remote_address_contract(address, accepted):
    assert NETWORK.valid_remote_ip(address) is accepted


@pytest.mark.parametrize(
    "zone, accepted",
    [
        ("example.internal", True),
        ("Example.INTERNAL.", True),
        ("lan", True),
        ("", False),
        ("REPLACE_WITH_INTERNAL_ZONE", False),
        ("https://example.internal", False),
        ("example.internal/path", False),
        ("bad..internal", False),
        ("-bad.internal", False),
        ("bad .internal", False),
        ("x" * 64 + ".internal", False),
        (None, False),
    ],
)
def test_shared_private_dns_zone_contract(zone, accepted):
    assert NETWORK.valid_dns_zone(zone) is accepted


@pytest.mark.parametrize(
    "port, accepted",
    [
        (1, True),
        (65535, True),
        ("8443", True),
        (0, False),
        (65536, False),
        (True, False),
        (8443.0, False),
        ("8443 ", False),
        ("REPLACE_WITH_PORT", False),
    ],
)
def test_shared_tcp_port_contract(port, accepted):
    assert NETWORK.valid_tcp_port(port) is accepted
