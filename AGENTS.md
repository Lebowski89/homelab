# Homelab Repository Instructions

These instructions apply to the entire repository.

A more specific `AGENTS.md` may add rules for its directory, but it must not weaken the safety, architecture, compatibility, or secret-handling boundaries defined here.

This file is a shared repository contract for implementation agents and review agents. Instructions that apply only to one mode are labelled accordingly.

## Instruction Precedence

1. Explicit instructions for the current task define its scope and intended outcome.
2. This file defines repository-wide architecture, safety, compatibility, and quality requirements.
3. A nested `AGENTS.md` may provide additional directory-specific guidance.
4. Existing repository architecture, tests, documentation, and recent history must be inspected before assuming that an unusual implementation is accidental.

Do not reinterpret a deliberate architecture or ownership decision as a regression merely because an older implementation behaved differently.

## Shared Working Principles

All agents must:

* Preserve the established architecture unless the current task explicitly changes it.
* Prefer concrete evidence from the current branch over assumptions based on naming or prior conventions.
* Distinguish repository invariants from implementation details.
* Avoid speculative cleanup, stylistic churn, and unrelated redesign.
* Avoid claims about live behaviour that repository-level inspection or static checks cannot prove.
* Treat generated files according to their established generator workflow.
* Report uncertainty when repository evidence is incomplete or conflicting.

## Implementation Agents

Implementation agents include Codex and other agents that edit files or execute repository commands.

Implementation agents must:

* Work only on the requested phase, issue, or explicitly agreed follow-up.
* Prefer the smallest complete change that satisfies the request.
* Do not broaden focused work into a repository-wide cleanup, migration, rename, formatting pass, or redesign.
* Do not silently fix unrelated findings. Report them separately.
* Inspect the relevant implementation, tests, documentation, configuration, and recent history before editing.
* Preserve unrelated user-owned modifications and untracked files.
* Validate before mutating whenever practical.
* Stop and explain when the requested change conflicts with an established architecture or safety boundary.
* Do not describe an incomplete phase as complete.

### Live-System Safety

Unless explicitly authorised for the current task, implementation agents must not:

* Run Ansible against a live inventory or host.
* Invoke deployment, update, removal, bootstrap, reconcile, or drift operations through `skynet`.
* Access Infisical, PostgreSQL, NetBox APIs, Proxmox APIs, Docker, Podman, systemd, Traefik, or other live services.
* Run `tofu plan`, `tofu apply`, `tofu destroy`, imports, state operations, or provider upgrades.
* Create, retrieve, rotate, display, validate, or test real secrets.
* Delete, reset, clean, overwrite, or otherwise discard user-owned working-tree changes.
* Commit, amend, rebase, merge, push, force-push, open or modify a pull request, reply to reviews, or resolve review threads unless explicitly requested.

Repository-only validation is allowed.

Ansible syntax checks must use a localhost-only or otherwise non-live inventory.

OpenTofu formatting and offline validation are allowed when the directory is already initialised and the commands will not contact providers or alter state.

### Working-Tree Safety

Before editing, implementation agents should:

1. Inspect the current branch and working-tree state.
2. Inspect the relevant diff.
3. Inspect recent history for the affected implementation.
4. Identify which files belong to the requested phase.
5. Treat existing modifications and untracked files as user-owned.

Never use destructive Git commands such as:

```text
git reset --hard
git clean
git checkout --
git restore .
```

Do not use broad restore, checkout, formatting, or replacement operations when targeted changes are sufficient.

If requested work overlaps an existing modification and the intended ownership is unclear, stop and explain the conflict before editing.

## Review Agents

Review agents include CodeRabbit and other agents that analyse pull requests without implementing the changes themselves.

Review agents must review every changed line and the directly affected behaviour for:

* correctness;
* regressions;
* security problems;
* secret exposure;
* data loss;
* unsafe live-system behaviour;
* idempotence failures;
* invalid state transitions;
* compatibility breaks;
* incorrect ownership boundaries;
* missing or ineffective validation;
* tests that do not prove their stated behaviour.

Before posting a finding, review agents must:

* Inspect the current branch implementation, not only the isolated diff line.
* Inspect nearby code and directly related call sites.
* Check relevant tests, documentation, configuration, and recent history.
* Determine whether the change is deliberate and consistent with repository architecture.
* Identify a concrete failure mode or violated repository invariant.
* Distinguish blocking defects from optional improvements.
* Avoid presenting assumptions as facts.

Review agents should be thorough, but they must not:

* Treat an intentional ownership change as a regression solely because an older guard or condition was removed.
* Request unrelated repository-wide cleanup in a focused pull request.
* Treat personal style preferences as correctness issues.
* Recommend new variables, abstractions, or compatibility layers without a demonstrated need.
* Request manual edits to generated files when the source or generator should be changed.
* Report generic project-wide docstring, documentation, or test-coverage targets unless the changed code introduces a concrete maintainability or correctness problem.
* Re-report pre-existing issues as though they were introduced by the pull request.
* Infer live-system behaviour from static tests alone.
* Assume that OpenTofu provisioning implies exclusive ownership of ongoing guest configuration.

Genuinely unrelated or pre-existing findings may be reported separately as non-blocking observations when they are important, but they must not be presented as required changes for the current pull request.

## Architecture Boundaries

### `service_common`

`service_common` contains runtime-neutral behaviour only.

It may own:

* service contract validation and normalisation;
* Infisical declaration validation and value lookup;
* runtime-neutral environment resolution;
* common filesystem paths;
* static copies and templates;
* Traefik dynamic configuration;
* PostgreSQL declaration validation;
* PostgreSQL database reconciliation.

It must not:

* call `community.docker` modules;
* call `containers.podman` modules;
* render Compose files;
* render Quadlets;
* start, stop, restart, pull, or remove containers;
* create Docker native secrets;
* create Podman native secrets;
* contain `docker_services_*` adapter variables;
* contain `podman_services_*` adapter variables;
* silently ignore unsupported runtime fields.

### Application Preparation

`service_prepare` owns application-specific validation, generated values, template derivation, and configuration preparation.

As a narrow exception to permanent runtime ownership, it may run short-lived preparation containers when the container:

* performs only application preparation or value generation;
* uses the service's selected Docker or Podman runtime;
* is never part of Compose, Quadlets, or deployed service state;
* is removed before service rendering and deployment, including after failures;
* is never started in check mode.

Application handlers must use the selected-runtime execution layer rather than calling Docker or Podman modules directly. Native secret materialisation and permanent container lifecycle remain runtime-adapter responsibilities.

### Runtime Adapters

`docker_services` and `podman_services` retain ownership of runtime-specific behaviour.

This includes:

* runtime-specific validation and normalisation;
* Compose or Quadlet rendering;
* image handling;
* runtime-native secret materialisation;
* runtime networks and volumes;
* deployed container lifecycle;
* systemd lifecycle;
* runtime-specific drift behaviour;
* runtime-specific removal behaviour.

Each runtime adapter must reset its per-service transient state before resolving another service.

Values returned by `service_common` that are required later must be copied into a runtime-prefixed adapter fact and explicitly passed into subsequent common-role calls.

Do not rely on generic facts surviving implicitly across separate role invocations.

Values, secrets, declarations, or state from one service must never satisfy another service.

### PostgreSQL

Common PostgreSQL preparation may:

* validate PostgreSQL declarations;
* normalise database declarations;
* resolve explicitly declared credential references;
* idempotently ensure that declared databases exist.

It must not:

* create Docker secrets;
* create Podman secrets;
* generate application-specific configuration;
* reintroduce runtime-specific PostgreSQL lookup paths;
* infer credentials from unrelated service state.

Database credentials must come from the current service's normalised Infisical declarations.

Host addressing should use explicit configuration or NetBox inventory data.

## Service Definitions and Compatibility

* Maintain one canonical service definition rather than separate Docker and Podman copies.
* Use `runtime: docker` or `runtime: podman` to select the runtime adapter.
* Follow `docs/service-definition-style.md` for the canonical immediate key order in base service and target mappings, and always keep `targets` last.
* For a portable service, changing only the runtime should preserve its intended:

  * image;
  * environment;
  * ports;
  * mounts;
  * health check;
  * security settings;
  * secrets;
  * Traefik route;
  * persistent data.
* Preserve existing Docker behaviour unless the current phase explicitly changes or migrates it.
* Keep compatibility adapters until repository service definitions have been deliberately migrated and tested.
* Do not modify service YAML during an infrastructure-only phase unless the infrastructure change explicitly requires it.
* During a service-schema or runtime-portability migration, modify only the named services or agreed migration batch.
* Preserve existing behaviour during migrations unless a behaviour change is explicitly intended and documented.
* Validate real base-plus-target service configurations before expanding a migration.
* Reject unsupported fields clearly instead of ignoring them.
* Do not invent variables, defaults, or compatibility paths merely to satisfy a test.
* Do not duplicate service definitions to avoid fixing shared normalisation or adapter wiring.

When changing a schema, tests must exercise real repository service files and effective base-plus-target merges where relevant. Synthetic fixtures alone are insufficient for repository-wide compatibility claims.

## NetBox and Inventory

NetBox is the source of truth for host identity and inventory-derived values where available.

This includes:

* `ansible_host`;
* `ansible_user`;
* `ansible_port`;
* `local_ip`;
* host UID and GID values;
* application and data roots;
* infrastructure tags;
* device roles;
* host role membership.

The NetBox dynamic inventory requires hosts to have a primary IP and composes `local_ip` from that primary address.

Do not duplicate NetBox-owned host data in service files or generic `group_vars` merely to work around missing wiring.

Fix the inventory or variable handoff instead.

When introducing runtime-neutral host variables, provide an intentional compatibility path from existing `docker_host_*` fields where required.

Do not remove legacy fields until:

* their consumers have been migrated;
* their NetBox definitions have been migrated;
* compatibility behaviour has been tested;
* the removal is part of the requested phase.

### OpenTofu and Ansible Ownership

OpenTofu ownership describes infrastructure lifecycle and provisioning.

It does not automatically exclude a guest from ongoing Ansible configuration.

In particular:

* OpenTofu may provision a VM and provide initial cloud-init configuration.
* Ansible may own ongoing in-guest configuration after provisioning.
* The `opentofu_managed` tag must not be treated as a blanket Ansible exclusion.
* Use an explicit role feature flag or a narrowly defined platform condition when a host must opt out.
* Platform-specific exclusions, such as Proxmox LXC restrictions, must be expressed directly rather than inferred from OpenTofu ownership.

Do not reintroduce broad `opentofu_managed` exclusions without an explicit architecture decision.

### Internal Domains and Secret-Derived Values

Do not invent duplicate internal-domain variables.

Use the repository's established Infisical and inventory contracts.

Check-mode behaviour must use generic declaration-driven mechanisms rather than hard-coded knowledge of a particular secret name.

## Secrets and Sensitive Data

* Never place secret values in repository files.
* Never place secret values in test fixtures.
* Never expose secret values in logs, diffs, assertions, failure messages, or debug output.
* Never pass secret values through command arguments that may be visible in process listings.
* Tasks that carry, derive, materialise, or reference secret values must use:

  * `no_log: true`;
  * `diff: false`.
* Validate required values as non-empty without displaying them.
* Keep value-free secret declarations separate from resolved secret values.
* `service_common` may return declarations and resolved values through explicitly separate interfaces.
* Docker and Podman adapters must materialise their own runtime-native secrets.
* Preserve immutable-secret replacement policies.
* Check mode must not contact Infisical or create secrets.
* Safe check-mode stand-ins must be deterministic, syntax-valid, non-sensitive, and provided through a generic contract.
* Do not apply `no_log` to unrelated tasks when doing so would hide useful validation errors.

Any review finding involving possible secret exposure should be treated as high priority.

## Ansible Conventions

* Use fully qualified collection names for modules.
* Role-owned variables and facts must use the appropriate role prefix.
* Tasks must be idempotent.
* Use accurate `changed_when` and `failed_when` behaviour.
* Use explicit `loop_control.loop_var` names.
* Do not rely on nested implicit `item` variables.
* Quote file modes.
* Use strict boolean validation for schema inputs.
* Do not accept arbitrary truthy strings where a boolean is required.
* Normalise values once and consume the normalised values consistently.
* Validate inputs before mutating state.
* Keep delegation explicit.
* Keep controller hosts explicit.
* Keep deploy hosts explicit.
* Keep filesystem target hosts explicit.
* Avoid generic facts whose ownership or lifetime is ambiguous.
* Prefer effective, role-prefixed variables for values used by multiple tasks or templates.

### Dynamic Includes and Tags

For dynamic includes:

* Put operation tags needed to select the include on the outer task.
* Propagate tags needed by included tasks through `apply.tags`.
* The outer and applied tag sets do not need to be identical.
* Either set may legitimately contain additional tags.
* Add or update a regression test when missing `apply.tags` could skip a safety, validation, or lifecycle task.

Check mode must validate and show a safe plan while avoiding:

* external secret lookups;
* secret creation;
* database connections;
* image pulls;
* container lifecycle changes;
* service lifecycle changes;
* live host mutations;
* other external side effects.

## OpenTofu Conventions

* Keep providers and modules pinned according to repository policy.
* Prefer NetBox-derived infrastructure data over duplicated literals.
* Preserve explicit input precedence over derived fallbacks.
* Validate user-supplied and derived network inputs.
* Normalise names once and use the normalised locals consistently.
* Trim string identifiers before using them in lookups or resource/module names.
* Pin downloaded cloud images by checksum.
* Keep local-storage resources on the correct Proxmox node.
* Do not introduce forced replacement of a VM, container, template, disk, or other stateful resource without identifying it clearly.
* Do not conceal resource replacement behind an apparently unrelated refactor.
* Keep fallback behaviour explicit and testable.
* Do not access providers or state during repository-only validation without explicit authorisation.

`tofu fmt` and offline `tofu validate` are allowed when relevant and already initialised.

Anything that contacts providers, refreshes remote state, changes state, or performs infrastructure actions requires explicit authorisation.

## Testing Requirements

Tests must prove behaviour rather than merely duplicate implementation strings.

Static tests are useful for:

* wiring;
* task ordering;
* safety invariants;
* tag propagation;
* presence of required conditions;
* ownership boundaries.

Static tests must not be the only evidence for:

* normalisation;
* rendering;
* merge behaviour;
* adapter portability;
* runtime contracts.

For changes affecting service portability or shared contracts, include relevant coverage for:

* focused filter and normalisation behaviour;
* adapter rendering;
* real repository service definitions;
* effective base-plus-target merges;
* missing inputs;
* conflicting inputs;
* empty inputs;
* unsupported inputs;
* per-service fact isolation;
* secret isolation;
* existing Docker compatibility;
* Podman compatibility where supported;
* dynamic include tag propagation.

For infrastructure and network changes, include relevant coverage for:

* input precedence;
* derived fallbacks;
* address and prefix validation;
* effective interface selection;
* platform-specific exclusions;
* generated configuration consumption;
* idempotent present and absent states.

Run the relevant focused checks first, then the complete repository unit suite when practical.

Typical repository-only validation may include:

```text
python -m pytest tests/unit
ruff check .
ruff format --check .
ansible-lint <affected paths>
ansible-playbook -i localhost, ansible/playbook.yml --syntax-check
tofu fmt -check
tofu validate
git diff --check
```

Use the repository's configured tooling and lint configuration.

Do not install, upgrade, or alter dependencies merely to make validation available unless explicitly authorised.

Report commands that could not run rather than claiming that they passed.

Passing static checks does not prove successful live deployment.

## Generated Files and Documentation

* Do not hand-edit generated Ansible role READMEs.
* Do not hand-edit generated Terraform or OpenTofu READMEs.
* Use the repository's established documentation generator.
* Inspect generated diffs for unrelated churn.
* Do not treat generated timestamps or metadata as application logic.
* Review agents should comment on the source or generator rather than requesting a manual generated-file edit.
* Update human-maintained architecture and deployment documentation when a contract or ownership boundary changes.
* Document deliberate compatibility changes.
* Document deferred limitations.
* Do not claim live Compose, Quadlet, Traefik, Infisical, PostgreSQL, NetBox, Proxmox, Docker, or Podman validation from static tests.

A generated-file difference should only block a change when it demonstrates:

* stale generated documentation;
* an incorrect generator input;
* unintended generator churn;
* a broken generation workflow;
* a real mismatch between documented and implemented contracts.

## Review Severity Guidance

Review agents should classify findings according to their demonstrated impact.

### Blocking or high priority

Examples include:

* secret exposure;
* destructive data or state behaviour;
* broken service lifecycle;
* invalid infrastructure replacement;
* loss of idempotence with operational impact;
* a regression affecting existing supported services;
* a configuration path that can disconnect or render a managed host unreachable;
* cross-service secret or fact leakage;
* silently ignored unsupported fields;
* a safety or validation task that can be skipped;
* incorrect runtime ownership that causes duplicate or conflicting operations.

### Normal actionable findings

Examples include:

* inconsistent normalisation;
* a reversible setting that only converges in one direction;
* an explicit override ignored by related consumers;
* missing validation for a supported input;
* tests that do not cover an affected behaviour;
* inconsistent use of normalised OpenTofu locals.

### Non-blocking observations

Examples include:

* optional naming improvements;
* unrelated pre-existing code;
* speculative refactors;
* broad documentation expansion;
* generic docstring coverage;
* style preferences already handled by formatters or linters.

Review comments should explain the failure mode, affected behaviour, and repository rule involved.

## Implementation Completion Report

At the end of an implementation task, the implementation agent must:

1. Summarise the behaviour changed.
2. List the changed files, grouped by purpose.
3. State which compatibility behaviour was preserved.
4. Identify intentional behaviour differences.
5. List exactly which checks ran and their results.
6. State which checks could not run.
7. State whether any live host, provider, API, database, secret store, or external service was contacted.
8. List remaining limitations and the next safe validation steps.
9. Confirm whether anything was committed, pushed, deployed, applied, or posted to a pull request.
10. Suggest appropriate commit titles when no commit was requested.

Do not describe a partial implementation as finished.

Stop at the requested phase boundary and document deferred work rather than implementing it implicitly.
