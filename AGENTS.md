# Homelab Repository Instructions

These instructions apply to the entire repository. A more specific `AGENTS.md`
may add rules for its directory, but it must not weaken the safety boundaries
in this file.

## Working Agreement

- Work only on the phase or issue explicitly requested.
- Prefer the smallest complete change that satisfies the request.
- Do not broaden a focused phase into a repository-wide cleanup, migration,
  rename, formatting pass, or redesign.
- Do not silently fix unrelated findings. Report them separately.
- Do not claim live behavior that repository-level checks cannot prove.
- If requirements conflict with the current architecture, stop and explain the
  conflict before editing.

## Repository Tooling Environment

Python and Ansible tooling is installed in:

`/opt/ansible/ansible-venv`

Do not assume `python`, `ruff`, `pytest`, `ansible-lint`, or
`ansible-playbook` are globally available.

Prefer invoking the virtual-environment binaries explicitly:

- `/opt/ansible/ansible-venv/bin/python`
- `/opt/ansible/ansible-venv/bin/ruff`
- `/opt/ansible/ansible-venv/bin/ansible-lint`
- `/opt/ansible/ansible-venv/bin/ansible-playbook`

If activating the environment instead, activation and all dependent commands
must run within the same shell invocation.

Before reporting validation success, confirm that the Ruff version matches the
version pinned in `ansible/requirements.txt`. If the environment is missing or
outdated, report that rather than installing or upgrading dependencies without
authorization.

## Absolute Safety Boundaries

Unless the user explicitly authorizes a specific action in the current request:

- Do not run Ansible against any live inventory or host.
- Do not invoke `skynet` deployment, update, removal, bootstrap, or drift
  operations.
- Do not access Infisical, PostgreSQL, NetBox APIs, Proxmox APIs, Docker,
  Podman, systemd, Traefik, or other live services.
- Do not run `tofu plan`, `tofu apply`, `tofu destroy`, imports, state
  operations, or provider upgrades.
- Do not create, rotate, retrieve, display, or test real secrets.
- Do not commit, amend, rebase, merge, push, force-push, open or modify a pull
  request, reply to reviews, or resolve review threads.
- Do not delete, restore, reset, checkout, clean, or stash user changes.

Repository-only validation is allowed. Ansible syntax checks must use a
localhost-only/non-live inventory.

## Preserve the Working Tree

Before editing:

1. Run `git status --short --branch`.
2. Inspect the relevant diff and recent history.
3. Treat every existing modification and untracked file as user-owned.
4. Identify which files belong to the requested phase.

Never use destructive Git commands such as `git reset --hard`, `git clean`,
`git checkout --`, or broad `git restore` operations. Do not discard or rewrite
unrelated work. If requested work overlaps an existing modification and intent
is unclear, stop and ask.

Do not run a repository-wide formatter when formatting only changed files is
sufficient.

## Architecture Boundaries

### `service_common`

`service_common` contains runtime-neutral behavior only. It may own:

- service contract validation and normalization;
- Infisical declaration validation and value lookup;
- runtime-neutral environment resolution;
- common paths, copies, and templates;
- Traefik dynamic configuration;
- PostgreSQL database reconciliation.

It must not:

- call `community.docker` or `containers.podman` modules;
- render Compose files or Quadlets;
- start, stop, restart, pull, or remove containers;
- create Docker or Podman native secrets;
- contain `docker_services_*` or `podman_services_*` adapter variables;
- silently ignore unsupported runtime fields.

### Runtime adapters

`docker_services` and `podman_services` retain ownership of:

- runtime-specific validation and normalization;
- Compose or Quadlet rendering;
- image handling;
- native secret materialization;
- runtime networks and volumes;
- container and systemd lifecycle;
- runtime-specific drift and removal behavior.

Each adapter must reset per-service transient state before resolving a service.
Values returned by `service_common` that are needed later must be copied into a
runtime-prefixed adapter fact and explicitly passed into subsequent common-role
calls. Never rely on generic facts surviving implicitly across separate role
invocations, and never permit values from one service to satisfy another.

### PostgreSQL

Common PostgreSQL preparation may validate declarations and idempotently ensure
declared databases exist. It must not create Docker secrets, Podman secrets, or
application configuration.

Database credentials must come from the current service's normalized Infisical
declarations. Host addressing should use explicit configuration or NetBox
inventory data. Do not reintroduce runtime-specific PostgreSQL lookup paths.

## Service Definitions and Compatibility

- Maintain one canonical service definition rather than separate Docker and
  Podman copies.
- `runtime: docker` or `runtime: podman` selects the adapter.
- For a canonical portable service, changing only the runtime should preserve
  its intended image, environment, ports, mounts, health check, security,
  secrets, Traefik route, and persistent data.
- Preserve existing Docker behavior unless the current phase explicitly
  migrates it.
- Keep compatibility adapters until repository service definitions have been
  deliberately migrated and tested.
- Do not modify service YAML during infrastructure-only phases unless the
  requested infrastructure change explicitly requires it.
- During an explicitly requested service-schema or runtime-portability
  migration, service YAML may be updated only for the named services or agreed
  migration batch.
- Preserve existing behavior during migrations and validate actual
  base-plus-target configurations before expanding to the next batch.
- Reject unsupported fields clearly instead of ignoring them.
- Do not invent new variables merely to make a test pass.

When changing a schema, test actual repository service files and effective
base-plus-target merges. Synthetic fixtures alone are insufficient for
compatibility claims.

## NetBox and Inventory

NetBox is the source of truth for host identity and inventory-derived values
where available, including:

- `ansible_host`, `ansible_user`, and `ansible_port`;
- `local_ip`;
- host UID/GID and application/data roots;
- infrastructure tags and role membership.

Do not duplicate NetBox-owned host data in service files or generic
`group_vars` merely to work around missing wiring.

When introducing runtime-neutral host variables, provide an intentional
compatibility path from existing `docker_host_*` fields. Do not remove legacy
fields until their consumers and NetBox definitions have been migrated.

OpenTofu ownership describes infrastructure lifecycle; it does not
automatically exclude a guest from Ansible configuration. Use an explicit role
feature flag for opt-out rather than inferring guest configuration ownership
from `opentofu_managed`.

Do not invent a second internal-domain variable. The existing
`cloudflare_zone` value is retrieved through the declared Infisical contract.
Check-mode behavior must use a generic declaration-driven mechanism, not
hard-coded knowledge of a particular secret name.

## Secrets and Sensitive Data

- Never place secret values in repository files, task arguments visible in
  process listings, test fixtures, logs, diffs, assertions, or debug output.
- Tasks that carry, derive, materialize, or reference secret values must use
  `no_log: true` and `diff: false`.
- Validate required values as non-empty before materialization without
  displaying them.
- Common code returns value-free secret declarations separately from secret
  values.
- Docker and Podman materialize their own native secrets.
- Preserve immutable-secret replacement policies.
- Check mode must not contact Infisical or create secrets. Use deterministic,
  syntax-valid, non-sensitive stand-ins through a generic contract.

Avoid applying `no_log` to unrelated tasks when it would hide useful validation
errors.

## Ansible Conventions

- Use fully qualified collection names for modules.
- Role-owned variables and facts must use the role prefix required by
  `ansible-lint`.
- Tasks must be idempotent and have accurate `changed_when` and `failed_when`
  behavior.
- Use explicit `loop_control.loop_var` names; do not rely on nested `item`.
- Quote file modes.
- Use strict boolean validation for schema inputs; do not accept arbitrary
  truthy strings.
- Normalize values once and render the normalized values.
- Validate before mutating.
- Delegation, controller hosts, deploy hosts, and filesystem target hosts must
  be explicit.

For dynamic includes:

- Put the operation tags needed to select the include on the outer task.
- Propagate the tags required by included tasks with `apply.tags`.
- The outer and applied tag sets do not have to be identical; either may
  legitimately include additional tags.
- Add or update a regression test when missing `apply.tags` could cause a
  safety or validation task to be skipped.

Check mode must validate and show a safe plan while avoiding external lookups,
secret creation, database connections, image pulls, service lifecycle changes,
and other live mutations.

## OpenTofu Conventions

- Keep providers and modules pinned according to repository policy.
- Prefer NetBox-derived infrastructure data over duplicated literals.
- Validate inputs and preserve explicit-value precedence over fallbacks.
- Normalize names once and use the normalized locals consistently.
- Pin downloaded cloud images by checksum.
- Keep local-storage resources on the correct Proxmox node.
- Do not introduce forced replacement of a VM or template without identifying
  it clearly in the final report.
- `tofu fmt` and offline `tofu validate` are permitted when relevant and already
  initialized. Anything that contacts providers or changes state requires
  explicit user authorization.

Do not manually edit generated Terraform documentation unless explicitly
requested. Use the repository's established documentation generator when
appropriate and inspect its diff for unrelated churn.

## Testing Requirements

Tests must prove behavior rather than merely duplicate implementation strings.
Static tests are useful for wiring and safety invariants but must not be the
only evidence for normalization or rendering behavior.

For changes affecting service portability or shared contracts, include:

- focused filter/normalization tests;
- adapter rendering tests;
- repository regression tests using real service YAML;
- base-plus-target merge coverage where targets are supported;
- negative tests for missing, conflicting, empty, or unsupported inputs;
- tests preventing per-service fact or secret leakage;
- compatibility tests for existing Docker services;
- tag-propagation tests for dynamic includes.

Run the relevant subset first, then the complete repository unit suite when
practical. Typical repository-only validation includes:

```text
python -m pytest tests/unit
ruff check .
ruff format --check .
ansible-lint <affected paths>
ansible-playbook -i localhost, ansible/playbook.yml --syntax-check
git diff --check
```

Use the repository's configured virtual environment and lint configuration.
Do not install or upgrade dependencies unless explicitly authorized. Report
commands that could not run rather than claiming they passed.

## Generated Files and Documentation

- Do not hand-edit generated role or Terraform READMEs unless that is the
  repository's established workflow.
- Update human-maintained architecture and deployment documentation when a
  contract or ownership boundary changes.
- Document deliberate compatibility changes and deferred limitations.
- Do not claim live Compose, Quadlet, Traefik, Infisical, PostgreSQL, NetBox, or
  Proxmox validation from static tests.

## Completion Report

At the end of every implementation:

1. Summarize the behavior changed.
2. List every changed file, grouped by purpose.
3. State compatibility preserved and intentional behavior differences.
4. List exactly which checks ran and their results.
5. State which checks could not run.
6. State explicitly whether live hosts or external services were contacted.
7. List remaining limitations and the next safe live-validation steps.
8. Confirm that nothing was committed, pushed, deployed, or applied unless the
   user explicitly requested it.
9. Suggest recommended commit titles that capture the nature of the changes.

Do not describe an incomplete phase as finished. Stop at the requested phase
boundary and leave deferred work documented rather than implementing it
implicitly.
