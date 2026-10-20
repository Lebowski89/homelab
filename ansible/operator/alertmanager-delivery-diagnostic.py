#!/usr/bin/env python3
"""Read-only, value-free projection for the existing rootless delivery path.

No secret file is read, notification sent, policy audited, or runtime changed.
Only sanitized projections are persisted; command stderr/source is withheld.
"""

import argparse
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import yaml
from jinja2 import Environment, StrictUndefined

SPEC = importlib.util.spec_from_file_location("delivery_utility", Path(__file__).with_name("utility-preparation.py"))
u = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(u)
LIMIT = 4194304
TOKEN_FILE = "/run/secrets/alertmanager_gotify_token_secret"


class DiagnosticError(RuntimeError):
    """Only locally constructed, value-free error messages may be printed."""


def run(argv, phase, *, both_streams=False):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=45, check=False)
    except subprocess.TimeoutExpired:
        raise DiagnosticError(f"{phase}: timed out after 45s; source/stderr withheld") from None
    if result.returncode:
        raise DiagnosticError(f"{phase}: exit={result.returncode}; source/stderr withheld")
    if len(result.stdout) + len(result.stderr) > LIMIT:
        raise ValueError(f"{phase}: bounded output exceeded")
    return result.stdout + ("\n" + result.stderr if both_streams else "")


def canonical():
    text = (u.REPO / "ansible/roles/service_common/templates/configs/alertmanager.yml.j2").read_text()
    return yaml.safe_load(
        Environment(undefined=StrictUndefined)
        .from_string(text)
        .render(
            service_common_infisical_values=dict(
                smtp_email="fake@example.test", smtp_host="smtp.example.test", smtp_port="587", smtp_username="fake@example.test"
            ),
            services_internal_zone="internal.example",
            services_private_https_port=8443,
        )
    )


def config_projection(config):
    expected = canonical()

    def route_defaults(route):
        # The status API serializes Continue even when false. Compare its
        # effective default, while retaining every other field and child.
        result = deepcopy(route)
        result.setdefault("continue", False)
        if "routes" in result:
            result["routes"] = [route_defaults(child) for child in result["routes"]]
        return result

    receivers = []
    for index, receiver in enumerate(config.get("receivers", [])):
        for position, webhook in enumerate(receiver.get("webhook_configs", [])):
            auth = webhook.get("http_config", {}).get("authorization", {})
            receivers.append(
                {
                    "receiver_index": index,
                    "webhook_index": position,
                    "receiver_is_email_gotify": receiver.get("name") == "email-gotify",
                    "destination": u.destination_metadata(webhook.get("url")),
                    "authorization_is_application_bearer_file": auth == {"type": "Bearer", "credentials_file": TOKEN_FILE},
                    "send_resolved": webhook.get("send_resolved") is True,
                    "payload_is_old_mapping": isinstance(webhook.get("payload"), dict),
                    "payload_matches_fixed_canonical": webhook.get("payload") == expected["receivers"][0]["webhook_configs"][0]["payload"],
                    "email_present": bool(receiver.get("email_configs")),
                }
            )
    return {
        "routing_matches_canonical": route_defaults(config.get("route", {})) == route_defaults(expected["route"]),
        "inhibition_matches_canonical": config.get("inhibit_rules") == expected["inhibit_rules"],
        "canonical_delays": {key: expected["route"][key] for key in ("group_wait", "group_interval", "repeat_interval")},
        "webhooks": receivers,
    }


def verify_payload_only(before, after):
    """Permit only the canonical body fix, preserving email and credentials."""
    comparison = deepcopy(before)
    for config in (comparison, after):
        receivers = [row for row in config.get("receivers", []) if row.get("name") == "email-gotify"]
        if len(receivers) != 1 or len(receivers[0].get("webhook_configs", [])) != 1:
            raise DiagnosticError("email-gotify webhook missing or ambiguous; no differences emitted")
    expected = canonical()["receivers"][0]["webhook_configs"][0]["payload"]
    webhook = next(row for row in after["receivers"] if row["name"] == "email-gotify")["webhook_configs"][0]
    if webhook.get("payload") != expected:
        raise DiagnosticError("fixed payload differs from canonical template")
    next(row for row in comparison["receivers"] if row["name"] == "email-gotify")["webhook_configs"][0]["payload"] = expected
    if comparison != after:
        raise DiagnosticError("configuration changed beyond webhook payload; source and differences withheld")


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value
    except ValueError:
        return None


def alerts_projection(alerts):
    result = []
    for alert in alerts:
        labels = alert.get("labels", {})
        name = labels.get("alertname", "")
        if not re.fullmatch(r"SkynetUtilityMigration_[a-zA-Z0-9_-]{1,80}", name):
            continue
        status = alert.get("status", {})
        result.append(
            {
                "alertname": name,
                "severity_is_info": labels.get("severity") == "info",
                "selected_receivers": [
                    "email-gotify" if r.get("name") == "email-gotify" else "(other receiver withheld)" for r in alert.get("receivers", [])
                ],
                "state": status.get("state") if status.get("state") in {"active", "suppressed", "unprocessed"} else "unknown",
                "silence_count": len(status.get("silencedBy", [])),
                "inhibition_count": len(status.get("inhibitedBy", [])),
                "silence_ids": [
                    value for value in status.get("silencedBy", []) if isinstance(value, str) and re.fullmatch(r"[a-f0-9-]{36}", value)
                ],
                "inhibiting_fingerprints": [
                    value for value in status.get("inhibitedBy", []) if isinstance(value, str) and re.fullmatch(r"[a-f0-9]{16}", value)
                ],
                "startsAt": timestamp(alert.get("startsAt")),
                "endsAt": timestamp(alert.get("endsAt")),
                "fingerprint": alert.get("fingerprint") if re.fullmatch(r"[a-f0-9]{16}", alert.get("fingerprint", "")) else None,
            }
        )
    return result


def error_class(text):
    value = text.lower()
    for fragments, name in [
        (("cannot unmarshal object", "field createmessage.title", "field createmessage.message"), "JSON field type mismatch"),
        (("failed to render custom payload",), "payload rendering failure"),
        (("certificate", "x509:", "tls handshake"), "TLS/certificate failure"),
        (("no such host", "name resolution"), "DNS failure"),
        (("permission denied", "credentials file"), "file/permission failure"),
        (("connection refused",), "connection refused"),
        (("deadline exceeded", "timed out", "timeout"), "timeout"),
        (("unauthorized", "invalid token"), "authorization rejected"),
        (("required", "validation"), "request validation failure"),
    ]:
        if any(part in value for part in fragments):
            return name
    return "unclassified (source withheld)"


def log_projection(text, service):
    events = []
    for line in text.splitlines():
        if service == "gotify":
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("method") != "POST" or str(row.get("path", "")).split("?", 1)[0] != "/message":
                continue
            events.append(
                {
                    "http_status": row.get("status") if type(row.get("status")) is int else None,
                    "time": timestamp(row.get("time")),
                    "error_class": error_class(str(row.get("errors", ""))),
                }
            )
        elif "webhook" in line.lower() or "notify" in line.lower() or "notification" in line.lower():
            match = re.search(r"(?:status code[:= ]*|HTTP status[:= ]*|HTTP/\d(?:\.\d)?\s+)([1-5]\d{2})", line, re.I)
            alert = re.search(r"SkynetUtilityMigration_[a-zA-Z0-9_-]{1,80}", line)
            when = re.search(r'(?:time|ts)="?([0-9T:.+Z-]+)', line)
            events.append(
                {
                    "integration": "webhook" if "webhook" in line.lower() else "other notification",
                    "receiver_is_email_gotify": "email-gotify" in line,
                    "controlled_alert": alert[0] if alert else None,
                    "time": timestamp(when[1]) if when else None,
                    "http_status": int(match[1]) if match else None,
                    "error_class": error_class(line),
                }
            )
    return events[-80:]


def network_projection(podman, cid, integrations):
    zone, port = integrations["zone"], integrations["private_https_port"]
    if not re.fullmatch(r"[a-zA-Z0-9.-]+", zone) or type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("recorded HTTPS addressing malformed")
    # Execute within the application container: its DNS, CA store, process
    # user and namespace apply. HEAD /health reads no token and sends no message.
    argv = [*podman, "exec", cid, "/bin/wget", "--spider", "--server-response", "--timeout=10", f"https://gotify.{zone}:{port}/health"]
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "delivery_proved": False}
    text = result.stdout + result.stderr
    if len(text) > LIMIT:
        raise ValueError("network projection exceeds bound")
    statuses = [int(value) for value in re.findall(r"HTTP/\d(?:\.\d)?\s+([1-5]\d{2})", text)]
    return {
        "command_exit": result.returncode,
        "http_statuses": statuses,
        "redirect_observed": bool(re.search(r"(?im)^\s*Location:", text)),
        "error_class": error_class(text) if result.returncode else None,
        "context": "actual Alertmanager container user/DNS/network/CA store; unauthenticated Gotify health",
        "delivery_proved": False,
    }


def api_projection(port):
    import urllib.error
    import urllib.request

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def get(path):
        try:
            with opener.open(f"http://127.0.0.1:{port}{path}", timeout=8) as response:
                body = response.read(LIMIT + 1)
        except urllib.error.HTTPError as error:
            raise DiagnosticError(f"local API {path}: HTTP {error.code}; response body withheld") from None
        except urllib.error.URLError as error:
            raise DiagnosticError(f"local API {path}: {type(error.reason).__name__}; source withheld") from None
        if len(body) > LIMIT:
            raise ValueError("API response bound exceeded")
        return body

    status = json.loads(get("/api/v2/status"))
    config = yaml.safe_load(status["config"]["original"])
    metrics = []
    for line in get("/metrics").decode().splitlines():
        if re.fullmatch(r"alertmanager_(?:notifications(?:_failed)?_total|config_last_reload_successful)(?:\{[^\n]*\})? [0-9.eE+-]+", line):
            metric, value = line.rsplit(" ", 1)
            metrics.append(
                {
                    "metric": metric.split("{", 1)[0],
                    "integration": "webhook" if 'integration="webhook"' in metric else "other",
                    "value": float(value),
                }
            )
    return {
        "loaded_config": config_projection(config),
        "test_alerts": alerts_projection(json.loads(get("/api/v2/alerts"))),
        "metrics": metrics,
        "absence_is_not_proof_of_prior_submission_or_delivery": True,
    }


def collect(facts, output):
    selected = json.loads((facts / "stopped-backup.0JEhXR/deploy.217ndl/selected.json").read_text())
    if socket.gethostname().split(".")[0] != selected["host"]:
        raise ValueError("run on the recorded inventory controller")
    boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    phases, runtimes = [], {}
    for service in ("alertmanager", "gotify"):
        cfg = selected["services"][service]
        declaration = yaml.safe_load((u.REPO / f"ansible/group_vars/all/services/{service}.yml").read_text())[service]
        if declaration["image"] != cfg["image"] or declaration["deploy"]["execution"] != cfg["execution"]:
            raise ValueError(f"{service}: canonical image/execution differs from retained declaration")
        account, prefix = u.account_command(cfg["execution"]["host_user"])
        saved_account = json.loads((facts / f"{service}.json").read_text())["account"]
        if account is None or account != saved_account:
            raise DiagnosticError(f"{service}: dedicated account differs from retained evidence")
        podman = [*prefix, "/usr/bin/podman", "--remote=false"]
        ids = run(
            [*podman, "ps", "--no-trunc", "--filter", f"name=^{re.escape(cfg['name'])}$", "--format", "{{.ID}}"], service + " identity"
        ).splitlines()
        if len(ids) != 1:
            raise ValueError(f"{service}: exact running container missing/ambiguous")
        current = u.container(podman, ids[0])
        u.validate_runtime(current, cfg)
        u.write(output, service + "-identity.json", {"account": account, "container": current})
        runtimes[service] = (podman, current)
    podman, current = runtimes["alertmanager"]
    cfg = selected["services"]["alertmanager"]
    network = network_projection(podman, current["id"], selected["integrations"])
    u.write(output, "delivery-network.json", network)
    print(json.dumps(network), flush=True)
    if network.get("command_exit") != 0 or network.get("http_statuses") != [200] or network.get("redirect_observed"):
        phases.append("delivery-network: HTTPS health unavailable or redirected; inspect sanitized projection")
    for name, argv in [
        (
            "loaded-state",
            [
                "sudo",
                "-n",
                "/usr/bin/nsenter",
                "--target",
                str(current["pid"]),
                "--net",
                sys.executable,
                str(Path(__file__).resolve()),
                "--api",
                str(cfg["ports"]["backend"]["target"]),
            ],
        ),
        ("file-state", ["sudo", "-n", sys.executable, str(Path(__file__).resolve()), "--config", cfg["templates"][0]["dest"]]),
        (
            "token-file-readable-nonempty",
            [*podman, "exec", current["id"], "/bin/sh", "-c", 'test -r "$1" && test -s "$1"', "skynet-token-metadata", TOKEN_FILE],
        ),
    ]:
        print("Read-only phase: " + name, flush=True)
        try:
            raw = run(argv, name)
            projection = json.loads(raw) if raw.strip() else {"readable_nonempty": True, "contents_read": False}
            u.write(output, name + ".json", projection)
            print(json.dumps({"phase": name, "observed": projection}), flush=True)
        except (DiagnosticError, ValueError) as error:
            phases.append(name + ": " + type(error).__name__)
            print(str(error) if isinstance(error, DiagnosticError) else name + ": projection rejected; source withheld", file=sys.stderr)
    for service, (podman, current) in runtimes.items():
        try:
            raw = run([*podman, "logs", "--since", "60m", "--tail", "500", current["id"]], service + " notification log", both_streams=True)
            events = log_projection(raw, service)
            u.write(output, service + "-notification-events.json", events)
            print(json.dumps({"service": service, "notification_events": events}), flush=True)
        except DiagnosticError as error:
            phases.append(service + ": log unavailable")
            print(str(error), file=sys.stderr)
        again = u.container(podman, current["id"])
        ids = run(
            [*podman, "ps", "--no-trunc", "--filter", f"name=^{re.escape(service)}$", "--format", "{{.ID}}"], service + " ending identity"
        ).splitlines()
        if ids != [current["id"]] or any(again[key] != current[key] for key in ("identity", "image_id", "mounts", "maps", "ports")):
            raise DiagnosticError(f"{service}: runtime replaced/changed during diagnostic; reject attribution")
    if Path("/proc/sys/kernel/random/boot_id").read_text().strip() != boot:
        raise ValueError("host boot changed during diagnostic")
    result = {
        "completed": not phases,
        "failed_phases": phases,
        "delivery_accepted": False,
        "token_application_association": "unproved; no token read",
        "notifications_sent": False,
    }
    u.write(output, "result.json", result)
    print(json.dumps(result), flush=True)
    if phases:
        raise DiagnosticError("incomplete diagnostic; partial sanitized observations retained")


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("facts", type=Path, nargs="?")
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--api", type=int)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--verify-payload-only", type=Path, nargs=2, metavar=("BEFORE", "AFTER"))
    args = parser.parse_args()
    if args.verify_payload_only:
        if args.facts is not None or args.output is not None or args.api is not None or args.config is not None:
            raise DiagnosticError("payload-only verification cannot be combined with collection")
        verify_payload_only(*[yaml.safe_load(u.read_stable_config(path)["body"]) for path in args.verify_payload_only])
        print("Only webhook payload changed; email, destinations and credential declarations preserved.")
        return
    if args.api is not None or args.config is not None:
        if args.facts is not None or args.output is not None or (args.api is not None and args.config is not None):
            raise ValueError("projection modes cannot be combined")
        value = (
            api_projection(args.api)
            if args.api is not None
            else config_projection(yaml.safe_load(u.read_stable_config(args.config)["body"]))
        )
        print(json.dumps(value))
        return
    if args.facts is None or args.output is None:
        raise ValueError("require retained facts and fresh private output")
    info = args.output.lstat()
    if args.output.is_symlink() or not args.output.is_dir() or info.st_uid != os.getuid() or info.st_mode & 0o777 != 0o700:
        raise ValueError("output must be operator-owned mode 0700")
    collect(args.facts, args.output)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as error:
        # API/YAML/command errors can carry bodies, credential URLs or source.
        message = str(error) if isinstance(error, DiagnosticError) else type(error).__name__ + "; source withheld"
        print("Alertmanager delivery diagnostic: " + message, file=sys.stderr)
        sys.exit(1)
