"""Preserve monitor membership idempotence across the collection's grantor API change."""

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from ansible.module_utils.common.arg_spec import ArgumentSpecValidator
from ansible.plugins.loader import AnsibleCollectionConfig, init_plugin_loader
from jinja2.nativetypes import NativeEnvironment

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("server_version", [150000, 160000, 180000])
@pytest.mark.parametrize("existing", [False, True])
def test_monitor_membership_accepts_an_existing_grant_from_another_role(monkeypatch, server_version, existing):
    if not AnsibleCollectionConfig.collection_finder:
        init_plugin_loader()
    module = pytest.importorskip("ansible_collections.community.postgresql.plugins.modules.postgresql_membership")
    backend = pytest.importorskip("ansible_collections.community.postgresql.plugins.module_utils.membership")
    tasks = yaml.safe_load((ROOT / "ansible/roles/postgres/tasks/sub_tasks/admin/pg_monitor.yml").read_text())
    declaration = next(
        task["community.postgresql.postgresql_membership"] for task in tasks if "community.postgresql.postgresql_membership" in task
    )
    # Consume only value-free membership declarations, never connection credentials.
    params = {key: declaration[key] for key in ("memberships", "granted_by_any", "target_roles")}
    params["target_roles"] = [
        NativeEnvironment().from_string(role).render(postgres_monitor_role_name="fixture_monitor") for role in params["target_roles"]
    ]
    validated = ArgumentSpecValidator(
        {
            "memberships": {"type": "list", "elements": "dict", "options": module.MEMBERSHIP_ROW_SPEC},
            "granted_by_any": {"type": "bool", "default": False},
            "target_roles": {"type": "list", "elements": "str"},
        }
    ).validate(params)
    assert not validated.error_messages
    fixture = SimpleNamespace(
        params=validated.validated_parameters, warn=pytest.fail, fail_json=lambda **kwargs: pytest.fail(kwargs["msg"])
    )
    memberships = module.parse_memberships(fixture)
    group, role = memberships[0]["groups"][0], memberships[0]["target_roles"][0]

    monkeypatch.setattr(backend.PgMembershipBase, "_resolve_connection", lambda self: setattr(self, "derived_grantor", "current_admin"))
    monkeypatch.setattr(backend.PgMembershipBase, "_existing_roles", lambda self, roles: roles)
    grants = [{"grantor": "previous_admin", "ADMIN": False, "INHERIT": True, "SET": True}] if existing else []
    monkeypatch.setattr(backend.PgMembershipBase, "_role_grants", lambda self: {role: {group: grants}})
    queries = []

    def execute(obj, query, **kwargs):
        queries.append(query)
        return True

    monkeypatch.setattr(backend, "exec_sql", execute)
    handler = backend.PgMembershipByGrantor(fixture, None, memberships, server_version, granted_by_any=params["granted_by_any"])
    assert handler.grant() is not existing
    assert len(queries) == (0 if existing else 1)
    assert all(query.startswith("GRANT ") and "GRANTED BY" not in query for query in queries)
