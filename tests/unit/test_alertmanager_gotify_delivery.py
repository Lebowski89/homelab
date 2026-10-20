"""Pinned webhook scalar promotion, real Go templates and sanitized diagnostics."""

import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]


def canonical():
    return yaml.safe_load(
        Environment(undefined=StrictUndefined)
        .from_string((ROOT / "ansible/roles/service_common/templates/configs/alertmanager.yml.j2").read_text())
        .render(
            service_common_infisical_values=dict(
                smtp_email="fake@example.test", smtp_host="smtp.example.test", smtp_port="587", smtp_username="fake@example.test"
            ),
            services_internal_zone="internal.example",
            services_private_https_port=8443,
        )
    )


@pytest.fixture(scope="module")
def go_renderer(tmp_path_factory):
    go = shutil.which("go")
    if not go:
        pytest.skip("Go unavailable: cannot execute the actual Go payload templates offline")
    directory = tmp_path_factory.mktemp("gotify-go-template")
    binary = directory / "render"
    subprocess.run(
        [go, "build", "-o", str(binary), str(ROOT / "tests/fixtures/alertmanager/render.go")],
        env={**os.environ, "GOPROXY": "off", "GOSUMDB": "off", "GOTOOLCHAIN": "local"},
        check=True,
        capture_output=True,
    )
    return binary


def payload_body(binary, payload, data):
    rendered = json.loads(
        subprocess.run(
            [str(binary)], input=json.dumps({"Payload": payload, "Data": data}), text=True, capture_output=True, check=True
        ).stdout
    )

    # v0.34.1 DeepCopyWithTemplate YAML-decodes each rendered string. A decoded
    # string stays verbatim; structured values are normalized without re-parsing
    # their leaves. PyYAML models that promotion; this is not AM image execution.
    def promote(value):
        if isinstance(value, dict):
            return {key: promote(item) for key, item in value.items()}
        if not isinstance(value, str):
            return value
        try:
            decoded = yaml.safe_load(value)
        except yaml.YAMLError:
            return value
        return value if isinstance(decoded, str) else decoded

    return promote(rendered)


def test_captured_mapping_reproduces_object_title(go_renderer):
    legacy = {
        "title": '{{ if eq .Status "firing" }}FIRING{{ else }}RESOLVED{{ end }}: {{ .CommonLabels.alertname }}',
        "message": '{{ range .Alerts }}{{ .Annotations.summary }}{{ "\\n" }}{{ end }}',
        "priority": 8,
    }
    body = payload_body(
        go_renderer,
        legacy,
        {"Status": "firing", "CommonLabels": {"alertname": "Probe"}, "Alerts": [{"Annotations": {"summary": "Controlled notification"}}]},
    )
    assert body["title"] == {"FIRING": "Probe"}  # Gotify's string title cannot decode this object.


@pytest.mark.parametrize("status", ["firing", "resolved"])
@pytest.mark.parametrize("summary", ["Controlled notification", 'Error: value "quoted"\\path\nsecond line', "true", "null", "[x]", "☃"])
def test_current_payload_preserves_gotify_strings(go_renderer, status, summary):
    payload = canonical()["receivers"][0]["webhook_configs"][0]["payload"]
    body = payload_body(
        go_renderer,
        payload,
        {
            "Status": status,
            "CommonLabels": {"alertname": "Probe"},
            "Alerts": [{"Annotations": {"summary": summary, "description": "description: quoted"}}],
        },
    )
    assert body == {"title": status.upper() + ": Probe", "message": summary + " - description: quoted\n", "priority": 8}
    # Gotify requires string message/title and an integer priority, with normal JSON escaping.
    assert json.loads(json.dumps(body)) == body


@pytest.fixture
def diagnostic():
    spec = importlib.util.spec_from_file_location("delivery_test", ROOT / "ansible/operator/alertmanager-delivery-diagnostic.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_diagnostic_projections_never_emit_fake_credentials(diagnostic):
    config = canonical()
    webhook = config["receivers"][0]["webhook_configs"][0]
    webhook["url"] = "https://FAKEUSER:FAKEPASS@gotify.internal.example:8443/message?token=FAKE-TOKEN"
    webhook["http_config"]["authorization"]["credentials"] = "FAKE-INLINE-TOKEN"
    projection = diagnostic.config_projection(config)
    text = json.dumps(projection)
    for secret in ["FAKEUSER", "FAKEPASS", "FAKE-TOKEN", "FAKE-INLINE-TOKEN"]:
        assert secret not in text
    assert projection["webhooks"][0]["destination"]["sensitive_components_present"] is True
    assert projection["webhooks"][0]["authorization_is_application_bearer_file"] is False
    logs = 'level=error receiver=email-gotify integration=webhook[0] err="unexpected status code 400: cannot unmarshal object into Go struct field CreateMessage.title of type string https://example/?token=FAKE-TOKEN"'
    events = diagnostic.log_projection(logs, "alertmanager")
    assert events == [
        {
            "integration": "webhook",
            "receiver_is_email_gotify": True,
            "http_status": 400,
            "controlled_alert": None,
            "time": None,
            "error_class": "JSON field type mismatch",
        }
    ]
    assert "FAKE-TOKEN" not in json.dumps(events)


def test_diagnostic_retains_suppression_and_expiry_without_annotations(diagnostic):
    alert = {
        "labels": {"alertname": "SkynetUtilityMigration_fixture", "severity": "info", "password": "FAKE-SECRET"},
        "annotations": {"summary": "FAKE-SECRET"},
        "receivers": [{"name": "email-gotify"}],
        "status": {"state": "suppressed", "silencedBy": ["a"], "inhibitedBy": ["b"]},
        "startsAt": "2026-10-12T00:00:00Z",
        "endsAt": "2026-10-12T00:15:00Z",
        "fingerprint": "a" * 16,
    }
    row = diagnostic.alerts_projection([alert, {"labels": {"alertname": "unrelated"}}])[0]
    assert row["silence_count"] == row["inhibition_count"] == 1
    assert row["selected_receivers"] == ["email-gotify"]
    assert row["endsAt"] == alert["endsAt"]
    assert "FAKE-SECRET" not in json.dumps(row)


def test_logs_include_stderr_but_command_errors_withhold_it(diagnostic, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(diagnostic.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr="notification error"))
    assert diagnostic.run(["fake"], "log", both_streams=True).strip() == "notification error"
    monkeypatch.setattr(diagnostic.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="FAKE-TOKEN"))
    with pytest.raises(diagnostic.DiagnosticError, match="exit=1") as failure:
        diagnostic.run(["fake"], "log")
    assert "FAKE-TOKEN" not in str(failure.value)


@pytest.mark.parametrize("failure", [False, True, "replacement"])
def test_actual_collection_preserves_partial_results_and_identity_checks(diagnostic, tmp_path, monkeypatch, failure):
    from types import SimpleNamespace

    facts, out = tmp_path / "facts", tmp_path / "output"
    deployment = facts / "stopped-backup.0JEhXR/deploy.217ndl"
    deployment.mkdir(parents=True)
    out.mkdir(mode=0o700)
    services = {}
    for service in ["alertmanager", "gotify"]:
        decl = yaml.safe_load((ROOT / f"ansible/group_vars/all/services/{service}.yml").read_text())[service]
        services[service] = {
            "name": service,
            "execution": decl["deploy"]["execution"],
            "image": decl["image"],
            "templates": [{"dest": "/FAKE/config"}],
            "ports": {"backend": {"target": 9093}},
        }
        (facts / f"{service}.json").write_text(json.dumps({"account": {"name": decl["deploy"]["execution"]["host_user"]}}))
    (deployment / "selected.json").write_text(
        json.dumps({"host": "fixture", "services": services, "integrations": {"zone": "internal.example", "private_https_port": 8443}})
    )
    monkeypatch.setattr(diagnostic.socket, "gethostname", lambda: "fixture")
    monkeypatch.setattr(diagnostic.u, "account_command", lambda name: ({"name": name}, ["FAKE-PODMAN"]))
    inspections = 0

    def container(prefix, cid):
        nonlocal inspections
        inspections += 1
        return {
            "id": cid,
            "pid": 123,
            "identity": {"birth": "2" if failure == "replacement" and inspections == 3 else "1"},
            "image_id": "fixture",
            "mounts": [],
            "maps": {},
            "ports": {},
        }

    monkeypatch.setattr(diagnostic.u, "container", container)
    monkeypatch.setattr(diagnostic.u, "validate_runtime", lambda *a: None)
    calls = []

    def run(argv, phase, **kwargs):
        calls.append((argv, phase))
        if phase.endswith("identity"):
            return "a" * 64
        if phase == "loaded-state" and failure is True:
            raise diagnostic.DiagnosticError("loaded-state: exit=1; source/stderr withheld")
        if phase.endswith("notification log"):
            assert kwargs.get("both_streams") is True
            return ""
        return "{}" if phase.endswith("state") else ""

    monkeypatch.setattr(diagnostic, "run", run)
    monkeypatch.setattr(diagnostic.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr="HTTP/1.1 200 OK\n"))
    if failure == "replacement":
        with pytest.raises(diagnostic.DiagnosticError, match="runtime replaced/changed"):
            diagnostic.collect(facts, out)
        assert (out / "file-state.json").exists()
        assert not (out / "result.json").exists()
        return
    if failure:
        with pytest.raises(diagnostic.DiagnosticError, match="incomplete"):
            diagnostic.collect(facts, out)
    else:
        diagnostic.collect(facts, out)
    result = json.loads((out / "result.json").read_text())
    assert result["completed"] is not failure and result["delivery_accepted"] is False
    assert (out / "gotify-notification-events.json").exists()
    assert (out / "file-state.json").exists()
    assert not any("kill" in argv or "restart" in argv for argv, _ in calls)
    assert any(phase == "token-file-readable-nonempty" and "test -r" in " ".join(argv) for argv, phase in calls)


def test_payload_only_verification_preserves_email_destination_and_auth(diagnostic):
    from copy import deepcopy

    after = canonical()
    before = deepcopy(after)
    before["receivers"][0]["webhook_configs"][0]["payload"] = {"title": "old", "message": "old", "priority": 8}
    diagnostic.verify_payload_only(before, after)
    for key in ["email_configs", "webhook_configs"]:
        changed = deepcopy(after)
        if key == "email_configs":
            changed["receivers"][0][key][0]["to"] = "changed@example.test"
        else:
            changed["receivers"][0][key][0]["http_config"]["authorization"]["credentials_file"] = "/FAKE/other"
        with pytest.raises(diagnostic.DiagnosticError, match="beyond webhook payload"):
            diagnostic.verify_payload_only(before, changed)


def test_loaded_status_serialized_continue_default_is_compared_semantically(diagnostic):
    from copy import deepcopy

    loaded = canonical()
    loaded["route"]["continue"] = False
    for child in loaded["route"]["routes"]:
        child["continue"] = False
    assert diagnostic.config_projection(loaded)["routing_matches_canonical"] is True
    changed = deepcopy(loaded)
    changed["route"]["routes"][0]["continue"] = True
    assert diagnostic.config_projection(changed)["routing_matches_canonical"] is False
    changed = deepcopy(loaded)
    changed["route"]["group_wait"] = "1s"
    assert diagnostic.config_projection(changed)["routing_matches_canonical"] is False
