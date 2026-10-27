# Ansible compatibility audit — 2026-10-28

This repository-only audit covered Ansible configuration, task and template
references, module documentation, collection metadata and repository plugins,
prioritising workstation, system and service deployment paths. It does not prove
that every runtime path is free of deprecation warnings.

## Supported versions inspected

The controller requirements pin `ansible-core==2.21.5` and
`ansible-lint==26.10.1`. The existing workstation environment has those versions
and all the collection versions below; nothing was installed or upgraded.

| Collection | Pin |
| --- | --- |
| containers.podman | 1.21.1 |
| ansible.posix | 2.2.2 |
| community.docker | 5.4.0 |
| community.general | 13.5.0 |
| community.library_inventory_filtering_v1 | 1.1.5 |
| community.postgresql | 5.0.0 |
| community.proxmox | 2.1.0 |
| infisical.vault | 1.2.3 |
| netbox.netbox | 3.23.1 |

The installed Ruff is 0.17.1 rather than the requirements pin of 0.17.2;
Infisical SDK is 1.0.17 rather than 1.0.18. Validation used the existing tools;
no secret-store lookup or SDK integration was exercised.

## Corrections

- Docker installation and its architecture default, the PGDG suite, and
  keepalived's default interface now read `ansible_facts`. Role-level overrides
  retain their existing precedence and the supported OS gates are unchanged.
  The [core 2.20 porting guide](https://docs.ansible.com/projects/ansible-core/2.20/porting_guides/porting_guide_core_2.20.html)
  documents injected-fact and internal `vars` cache deprecations, both targeting
  core 2.24. The workstation and system paths already use explicit facts.
- NetBox bootstrap uses the `ansible.builtin.vars` lookup instead of the internal
  `vars` cache. Shared fallbacks and defined host overrides, including null,
  false, zero and empty containers or strings, keep their values and types.
  See the [official lookup documentation](https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/vars_lookup.html).
- Docker and PGDG installation use `deb822_repository`. Their URLs, suites,
  channels, signing-key paths and Docker architecture overrides are preserved,
  including comma-separated architecture lists. Complete matching declarations
  are removed from standard legacy source files; unrelated sources stay intact. APT is
  refreshed after source creation or legacy-line removal, before package
  installation. The prerequisites include `python3-debian` for the replacement
  module. `apt_repository` is deprecated for removal in core 2.25;
  [its documentation](https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/apt_repository_module.html)
  names [deb822_repository](https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/deb822_repository_module.html)
  as its replacement. Both were checked against the installed core 2.21.5 docs.
- PostgreSQL monitor membership uses `memberships` instead of deprecated
  top-level `groups` (removal in community.postgresql 6). `granted_by_any: true`
  retains the previous grantor-independent behavior, including PostgreSQL 16+
  installations where another administrator already granted membership. This is
  documented in the [official 5.0.0 module source](https://github.com/ansible-collections/community.postgresql/blob/5.0.0/plugins/modules/postgresql_membership.py).

No service definitions, runtime ownership boundaries, inventory data, dependency
pins or global fact-injection settings were changed. Generated role READMEs are
left to the documentation workflow.

## Remaining observations

Full-repository lint emits filter/test `PluginLoader` alias deprecations. With
`ANSIBLE_DISPLAY_TRACEBACK=deprecated`, the trace runs through the existing Docker
deploy filter's `deepcopy` into core's lazy-container `__deepcopy__`, which copies
its templar and reconstructs core's loaders with their saved aliases. Repository
code does not construct these loaders. This is still a real emitted deprecation;
changing the pinned dependency or redesigning independent copies was deferred.

PATH adjustment, directory expansion and the unmatched `tags_skynet` group in a
localhost-only syntax check are ordinary warnings, not deprecated behavior.
The INI lookup's inline argument parser remains supported in installed core
2.21.5; its deprecation hook is a no-op, so it was not changed for style alone.

The complete non-integration suite exposes two failures in unchanged
`test_utility_preparation.py`:

- `test_stable_configuration_read_rejects_writer_or_identity_changes[contents]`
- `test_ownership_hardlink_apply_rejects_changed_identity_before_chown[mode]`

The follow-up base comparison below establishes that both failures predate the
compatibility commit, including the mode case's test-order dependency.

## Changed files

- Fact and repository compatibility: `ansible/roles/docker/defaults/main.yml`,
  `ansible/roles/docker/tasks/sub_tasks/install.yml`,
  `ansible/roles/postgres/tasks/sub_tasks/install/apt.yml`, and
  `ansible/roles/keepalived/defaults/main.yml`.
- Variable lookup and collection API compatibility:
  `ansible/tasks/netbox_bootstrap.yml` and
  `ansible/roles/postgres/tasks/sub_tasks/admin/pg_monitor.yml`.
- Behavioral coverage: `tests/unit/test_ansible_repository_migration.py`,
  `tests/unit/test_netbox_bootstrap.py`, and
  `tests/unit/test_postgres_membership_compatibility.py`.
- Human-maintained audit record: this document.

## Initial implementation checks and results

Commands used the existing binaries under
`/home/john/.local/share/homelab/ansible-venv/bin` from the repository root, with
`ANSIBLE_CONFIG=ansible/ansible.cfg`, `ANSIBLE_HOME=/tmp/homelab-audit-home`, and
`ANSIBLE_LOCAL_TEMP=/tmp/homelab-audit-local`. Lint caches were redirected to
`/tmp` and lint ran offline. Ansible fixture tests needed permission to create
their local RPC sockets outside the sandbox; all host operations remained
replaced. No dependencies were installed.

| Check | Result |
| --- | --- |
| `python -m pytest tests/unit -m 'not integration' -q` | 2078 passed, 2 unrelated failures above, 919 deselected |
| `python -m pytest tests/unit/test_ansible_repository_migration.py tests/unit/test_netbox_bootstrap.py tests/unit/test_workstation.py tests/unit/test_workstation_tooling.py tests/unit/test_workstation_venv.py tests/unit/test_system.py tests/unit/test_system_nic.py -m integration -q` | 191 passed, 17 deselected |
| `python -m pytest tests/unit/test_postgres_membership_compatibility.py -q` | 6 passed; also included in the full unit result |
| `ansible-lint --offline --format=pep8 ansible` | Passed production profile; 537 files processed, with the loader deprecations described above |
| `ansible-playbook -i localhost, ansible/playbook.yml --syntax-check` | Passed; expected unmatched inventory-group warning |
| `ruff check` on the CI workflow's configured Python paths | Passed |
| `ruff format --check` on the same paths | Passed; 118 files formatted correctly |
| `yamllint ansible/roles/docker/defaults/main.yml ansible/roles/docker/tasks/sub_tasks/install.yml ansible/roles/keepalived/defaults/main.yml ansible/roles/postgres/tasks/sub_tasks/admin/pg_monitor.yml ansible/roles/postgres/tasks/sub_tasks/install/apt.yml ansible/tasks/netbox_bootstrap.yml` | Passed |
| `git diff --check` | Passed |

The Ruff paths match `.github/workflows/lint.yml`: `ansible/action_plugins`,
`ansible/filter_plugins`, `ansible/library`, the Docker, Podman, common and
preparation roles' `filter_plugins` directories, `service_prepare/library`,
`scripts/ci`, `tests/unit`, `tests/conftest.py`,
`tests/fixtures/haproxy_operator/commands.py`, and
`tests/fixtures/ansible/retry_playbook.py`.

Pre-change focused unit checks passed (95 cases). The initial NetBox fixture run
was blocked by the sandbox RPC restriction and passed after escalation. One new
migration fixture initially loaded role defaults with play-var precedence; the
fixture was corrected to use actual role defaults, then all migration cases
passed. These were validation-environment and test-fixture corrections.

## Validation limits and next steps

The migration tests execute the installed deb822 and lineinfile modules against
temporary source directories, with downloads, package operations and other host
mutations replaced by fixtures. They cover fresh installation, migration,
unrelated sources, repeat-run stability, legacy-only changes, check mode and
Docker overrides with fact injection disabled. NetBox tests use synthetic Vault
data and replace the lifecycle boundary. Membership tests use the installed
collection's normalization and grant logic with database I/O replaced, covering
PostgreSQL 15, 16 and 18 version branches and existing grants by another role.

Actual package availability, APT signature verification and refresh, PostgreSQL
connections and permissions, keepalived interface selection, and Docker/Podman
deployment still need an explicitly authorized runtime check on suitable hosts.
A fresh-host check-mode run needs `python3-debian` already visible to an eligible
interpreter; check mode cannot install it. Hosts overriding Docker prerequisites
must also make that module dependency available. Legacy source entries with a
different complete declaration are deliberately retained, even when they share
a URL with a managed repository.

No live inventory, host, provider, API, database or credential store was used.
Only public documentation was fetched externally. Nothing was committed,
pushed, deployed, applied or posted to a pull request.

## Follow-up review of the committed changes

The review compared `ansible/fixes` at `1b160f360fe24e4e22105deac81e1a1ecadd3f9d`
with `main`/`origin/main` and their merge base at
`c019d9da8e4cbe15b0b2ccfc030495b79fc911b1`. The current checkout and index were
preserved. Both commits were exported with `git archive` into separate temporary
directories; no branch switch, reset or worktree metadata change was needed.

### P2 correction: incomplete legacy repository cleanup

The committed cleanup compared the entire line literally in only the nominal
`docker.list` or `pgdg.list` file. The old `apt_repository` module accepts existing
entries with comments and whitespace, and reuses matching entries in other
`.list` files or `/etc/apt/sources.list`. The new deb822 entry therefore left
duplicate active declarations in these supported cases. Adding an inline comment
to the existing migration fixture reproduced this failure for both roles.

`ansible/roles/docker/tasks/sub_tasks/install.yml` and
`ansible/roles/postgres/tasks/sub_tasks/install/apt.yml` now discover standard
legacy source files, including symlinks, and remove only complete matching active
declarations. Each token is escaped before constructing an anchored expression;
whitespace and trailing comments are allowed. Disabled entries and declarations
with different suites, components, signing keys or architectures remain intact.
No repository definition or OS gate changed. Legacy removal still contributes
to the cache-refresh condition, including when the `.sources` file is unchanged.

Coverage in `tests/unit/test_ansible_repository_migration.py` now includes
annotated/whitespace entries, alternate files, the main source list and symlinks,
alongside the existing override, fresh-install, check-mode and idempotence cases.
`tests/unit/test_netbox_bootstrap.py` also checks positive integers, floats and
numeric strings without type conversion.

### Non-blocking for this branch: reproduced base failures

Both exports used the same Python 3.13.5 executable, installed packages
(`ansible-core` 2.21.5, pytest 9.1.1 and PyYAML 6.0.3), process environment and
temporary filesystem. Implementation, test and requirements hashes also matched.
The actual test execution, rather than those hashes alone, established the result:

| Invocation | Branch | Unchanged base |
| --- | --- | --- |
| The two exact failing nodes, three alternating runs per revision | Each run: contents failed, mode passed | Each run: contents failed, mode passed |
| Entire utility test module, non-integration selection | 2 failed, 163 passed, 4 deselected | 2 failed, 163 passed, 4 deselected |

The module comparison preloaded `ansible.plugins.action`, as full-suite collection
does, before invoking pytest. Without this preload, cold Ansible imports attempt
libc discovery under the unit subprocess guard and cause additional import errors
on both revisions. Neither inventory nor credentials were loaded.

The decisive invocation, run from each export with the same environment, was:

```bash
/home/john/.local/share/homelab/ansible-venv/bin/python -c 'import ansible.plugins.action; import pytest; raise SystemExit(pytest.main(["tests/unit/test_utility_preparation.py", "-m", "not integration", "-q", "-p", "no:cacheprovider"]))'
```

The mode failure is order-dependent: earlier utility CLI tests call `main()`,
which sets process umask `077` without restoring it. The later hardlink fixture
then creates its file as `0600`, so the test's `chmod(0600)` does not change its
permissions. The contents-race failure reproduces in isolation on both commits.
Neither utility implementation nor its tests were changed during this review.

### Loader warning attribution and unchanged contracts

A standalone temporary filter containing only `deepcopy(dict(value))`, invoked
through core's `Templar` with nested synthetic data, reproduced both filter/test
loader alias deprecations without importing repository code. The traceback is
core `_lazy_containers.py:364` copying the templar, then
`plugins/loader.py:411` reconstructing the loader with saved aliases. The repository
filter uses normal Python copying to keep outputs independent. Removing shallow
redundant copies would not remove the necessary nested-copy trigger; changing
that contract or introducing a custom clone mechanism was not justified.
No warnings were suppressed and installed dependencies were not patched.

Fact replacements remain on the host whose facts are gathered immediately before
the Docker, PostgreSQL and keepalived role calls; none of these changed expressions
introduces delegation. NetBox lookup still resolves the current recovery host's
variables. The pinned PostgreSQL 5.0.0 documentation explicitly identifies
`memberships` with `granted_by_any: true` as equivalent to the old `groups` behavior;
the six existing collection-logic cases passed without database I/O.

### Review validation

Only focused tests and affected-path lint were run; the full suite was not repeated.
The base/branch comparison results are above. The NetBox override/fallback checks
and membership checks passed (18 cases). The initial corrected migration run
exposed an overescaped regex delimiter, which was fixed and checked through the
installed templating engine before rerunning the migration cases.
The final `python -m pytest tests/unit/test_ansible_repository_migration.py -q
--tb=short` run passed all 10 cases. The combined focused invocation was
`python -m pytest tests/unit/test_ansible_repository_migration.py
tests/unit/test_netbox_bootstrap.py
tests/unit/test_postgres_membership_compatibility.py -k 'migration_preserves or
loads_shared or falsy or monitor_membership' -q --tb=short`; its 18 NetBox and
membership cases passed before the migration expression correction, and were
not repeated afterward because their inputs and implementation did not change.

Affected-role `ansible-lint --offline --format=pep8` passed for Docker, PostgreSQL
and NetBox bootstrap; a final run on the two changed installation task files also
passed. `ruff check` and `ruff format --check` passed for the two changed test
files; `yamllint` passed for the two changed task files; `git diff --check` passed.
Generated READMEs, staging, commits and remote operations were left untouched.
