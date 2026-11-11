#!/usr/bin/env python3
"""Real bounded HTTP/denial probe; connection refusal is never firewall proof."""

import errno
import json
import socket
import sys

address, port, expectation = sys.argv[1], int(sys.argv[2]), sys.argv[3]
family = socket.AF_INET6 if ":" in address else socket.AF_INET
with socket.socket(family, socket.SOCK_STREAM) as client:
    client.settimeout(3)
    try:
        client.connect((address, port))
    except OSError as error:
        if expectation != "deny" or not (isinstance(error, TimeoutError) or error.errno == errno.ETIMEDOUT):
            raise RuntimeError("Probe failed without proving firewall denial: " + str(error.errno)) from None
        print(json.dumps({"address": address, "port": port, "denied_by_timeout": True}))
    else:
        if expectation == "deny":
            raise RuntimeError("Unexpected permitted connection")
        client.sendall(b"GET / HTTP/1.0\r\nHost: molecule.invalid\r\n\r\n")
        data = b""
        while chunk := client.recv(4096):
            data += chunk
        if b"200 OK" not in data.partition(b"\r\n")[0] or b"molecule-network" not in data:
            raise RuntimeError("A live listener did not return the expected HTTP response")
        print(json.dumps({"address": address, "port": port, "http_ok": True}))
