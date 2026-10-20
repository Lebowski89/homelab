# Reusable service migration workspace

Follow the repository AGENTS.md. This directory organizes future named batches;
it grants no live authorization and does not reopen completed migrations.

- Keep canonical service definitions and runtime ownership in the existing roles.
  Do not duplicate Docker/Podman definitions or introduce a second deploy engine.
- `migrate.py init/seal/verify` are offline only. Never add implicit inventory,
  secret lookup, account creation, image staging, probes or lifecycle operations.
- Store runtime observations, inputs, backups and manifests in private per-batch
  directories outside Git. Never copy environments or credentials into plans.
- Read the actual helper interfaces before selecting collection commands. Existing
  service-specific allowlists are safety contracts, not generic plug-in support.
- Routine checks need authorization for the named batch. Before disruption,
  present one complete plan with exact recipes, checksums, backups, ownership,
  caller/policy transitions, acceptance and scoped rollback. Once approved,
  execute included steps without repeated permission requests.
- Reuse valid observations; refresh changed host/task/PID/namespace/caller evidence.
  Declarations alone prove neither current runtime nor successful application use.
- Preserve current installed policy unions and explicit operational requirements.
  Sealing a plan never promotes acknowledgement flags or approves execution.
- Keep stopped-writer guards, proved numeric mappings, contained hardlink groups,
  paired database/files restoration, failure statuses and exact cleanup ownership.
- Leave helper paths stable while saved rollback recipes import them. Extraction
  requires compatibility imports and behavioral tests before retiring old paths.
- New tests should exercise selection, safety and execution boundaries with fake
  inputs and isolated fixtures, never merely freeze plan wording or image tags.
