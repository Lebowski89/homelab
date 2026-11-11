"""Exercise the actual inline SARIF upload transformation without running scanners."""

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
STEPS = yaml.safe_load((ROOT / ".github/workflows/checkov.yml").read_text())["jobs"]["checkov"]["steps"]
TRANSFORM = next(step for step in STEPS if step.get("id") == "prepare_sarif")
pytestmark = pytest.mark.integration


def sarif(results):
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "Checkov", "version": "3.4.3", "rules": [{"id": "unused"}, {"id": "fixture"}]}},
                "automationDetails": {"id": "existing-analysis/"},
                "artifacts": [{"location": {"uri": "fixture.yml"}}],
                "results": results,
            }
        ],
    }


def finding(level, **extra):
    return {
        "ruleId": "fixture",
        "ruleIndex": 1,
        "level": level,
        "message": {"text": "Same finding text, independent of suppression state"},
        "locations": [{"physicalLocation": {"artifactLocation": {"index": 0, "uri": "fixture.yml"}, "region": {"startLine": 1}}}],
        "partialFingerprints": {"primaryLocationLineHash": "nonproduction-fingerprint"},
        "fingerprints": {"fixture/v1": "nonproduction-fingerprint"},
        **extra,
    }


def transform(directory):
    return subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", TRANSFORM["run"]],
        cwd=directory,
        env={**os.environ, "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"]},
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_upload_copy_removes_only_explicit_suppressions_and_preserves_metadata(tmp_path):
    suppressed = {"kind": "inSource", "justification": "Reviewed synthetic endpoint"}
    kept = [
        finding("warning"),
        finding("error"),
        finding("warning", suppressions=[suppressed | {"status": "rejected"}]),
        finding("error", suppressions=[suppressed | {"status": "underReview"}]),
        finding("warning", suppressions=[suppressed, suppressed | {"status": "rejected"}]),
        finding("warning", suppressions=[{"kind": "inSource"}]),
        finding("warning", suppressions=[suppressed | {"justification": ""}]),
        finding("warning", suppressions=[suppressed | {"properties": {"reviewPending": True}}]),
        finding("warning", suppressions=[]),
    ]
    original = sarif([finding("warning", suppressions=[suppressed]), *kept])
    # Multiple runs and explicit accepted suppressions retain their rule tables too.
    original["runs"].append(sarif([finding("error", suppressions=[suppressed | {"kind": "external", "status": "accepted"}])])["runs"][0])
    original["runs"][1]["automationDetails"]["id"] = "another-analysis/"
    raw = tmp_path / "checkov.sarif"
    raw.write_text(json.dumps(original))
    before = raw.read_bytes()
    expected = deepcopy(original)
    expected["runs"][0]["results"] = kept
    expected["runs"][1]["results"] = []

    for _ in range(2):
        result = transform(tmp_path)
        assert result.returncode == 0, result.stderr
        assert json.loads((tmp_path / "checkov-upload.sarif").read_text()) == expected
        assert raw.read_bytes() == before


def test_empty_results_still_produce_the_upload_report(tmp_path):
    original = sarif([finding("warning", suppressions=[{"kind": "inSource", "justification": "Reviewed"}])])
    (tmp_path / "checkov.sarif").write_text(json.dumps(original))
    result = transform(tmp_path)
    assert result.returncode == 0, result.stderr
    original["runs"][0]["results"] = []
    assert json.loads((tmp_path / "checkov-upload.sarif").read_text()) == original
    upload = next(step for step in STEPS if step.get("uses", "").startswith("github/codeql-action/upload-sarif@"))
    assert upload["with"]["sarif_file"] == "checkov-upload.sarif"
    assert "steps.prepare_sarif.outcome == 'success'" in upload["if"]
    assert "results" not in upload["if"]  # Zero findings must reconcile old alerts.


@pytest.mark.parametrize(
    "contents,error",
    [
        (None, "FileNotFoundError"),
        ("{", "JSONDecodeError"),
        ("null", "TypeError"),
        ("{}", "KeyError"),
        ('{"version":"2.1.0","runs":{}}', "ValueError"),
        (json.dumps(sarif({})), "ValueError"),
        (json.dumps(sarif([{}])), "ValueError"),
    ],
)
def test_bad_or_missing_report_fails_without_an_empty_fallback(tmp_path, contents, error):
    if contents is not None:
        (tmp_path / "checkov.sarif").write_text(contents)
    result = transform(tmp_path)
    assert result.returncode != 0
    assert error in result.stderr
    assert not (tmp_path / "checkov-upload.sarif").exists()


def test_output_failure_is_not_hidden(tmp_path):
    (tmp_path / "checkov.sarif").write_text(json.dumps(sarif([])))
    (tmp_path / "checkov-upload.sarif").mkdir()
    result = transform(tmp_path)
    assert result.returncode != 0 and "IsADirectoryError" in result.stderr
