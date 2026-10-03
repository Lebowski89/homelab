"""Validate service-reference examples without pinning documentation wording."""

import re
from pathlib import Path

import yaml

REFERENCE_PATH = Path(__file__).resolve().parents[2] / "ansible/group_vars/all/services/README.md"


def example_services():
    reference = REFERENCE_PATH.read_text()
    examples = reference.split("## Examples", maxsplit=1)[1].split("## Removed and unsupported fields", maxsplit=1)[0]
    documents = re.findall(r"```yaml\n(.*?)```", examples, flags=re.DOTALL)
    assert documents, "The reference must provide service examples"
    return [yaml.safe_load(document) for document in documents]


def test_reference_examples_parse_without_embedded_credentials():
    forbidden_secret_markers = (
        "AKIA",
        "BEGIN PRIVATE KEY",
        "ghp_",
        "glpat-",
        "sk-",
    )

    for document in example_services():
        assert isinstance(document, dict)
        assert len(document) == 1
        service = next(iter(document.values()))
        assert isinstance(service, dict)

        rendered = yaml.safe_dump(document)
        assert not any(marker in rendered for marker in forbidden_secret_markers)
        assert not re.search(r"(?im)^\s*(password|token|value):\s+\S", rendered)
