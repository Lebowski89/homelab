# Checkov Cheatsheet

Useful Checkov commands and patterns for this homelab repo.

## Main files

```text
.checkov.yml
.github/workflows/checkov.yml
```

`.checkov.yml` controls Checkov scan behaviour.

`.github/workflows/checkov.yml` controls when GitHub Actions runs Checkov and how results are uploaded.

## Recommended `.checkov.yml`

```yaml
quiet: true
compact: true

framework:
  - terraform
  - github_actions
  - dockerfile
  - ansible

skip-path:
  - "^\\.git/"
  - "^\\.ansible/"
  - "^ansible/collections/"
  - "^terraform/.*/\\.terraform/"
  - "^opentofu/.*/\\.terraform/"
  - "^.*/\\.terraform/"
  - "^.*/venv/"
  - "^.*/__pycache__/"
  - "^.*/node_modules/"
```

Keep broad repo config here instead of duplicating framework flags in the workflow.

## Run Checkov on the repo

```bash
checkov --directory .
```

Short form:

```bash
checkov -d .
```

## Run Checkov using the repo config

```bash
checkov --directory . --config-file .checkov.yml
```

## Show effective Checkov config

```bash
checkov --show-config
```

Useful when you are not sure whether `.checkov.yml`, CLI flags, or defaults are being used.

## Scan one file

```bash
checkov \
  --file ansible/roles/docker_services/tasks/sub_tasks/drift/image.yml \
  --framework ansible
```

Short form:

```bash
checkov -f ansible/roles/docker_services/tasks/sub_tasks/drift/image.yml --framework ansible
```

## Scan one file with compact output

```bash
checkov \
  --file ansible/roles/docker_services/tasks/sub_tasks/drift/image.yml \
  --framework ansible \
  --compact
```

## Scan one framework

```bash
checkov --directory . --framework ansible
```

```bash
checkov --directory . --framework terraform
```

```bash
checkov --directory . --framework github_actions
```

```bash
checkov --directory . --framework dockerfile
```

## Scan multiple frameworks

```bash
checkov \
  --directory . \
  --framework terraform \
  --framework github_actions \
  --framework dockerfile \
  --framework ansible
```

Prefer putting frameworks in `.checkov.yml` instead.

## Run only one check

```bash
checkov \
  --directory . \
  --check CKV2_GHA_1
```

Useful for debugging one alert.

## Run only one check against one file

```bash
checkov \
  --file .github/workflows/checkov.yml \
  --framework github_actions \
  --check CKV2_GHA_1
```

## Skip one check for a run

```bash
checkov \
  --directory . \
  --skip-check CKV_GIT_1
```

## Skip multiple checks for a run

```bash
checkov \
  --directory . \
  --skip-check CKV_GIT_1,CKV_GIT_5,CKV_GIT_6
```

## Run with soft fail

```bash
checkov \
  --directory . \
  --soft-fail
```

`--soft-fail` still runs checks and reports findings, but exits with code `0`.

This is good while introducing Checkov. Later, remove `--soft-fail` when you want CI to fail on findings.

## Run with CLI and SARIF output

```bash
checkov \
  --directory . \
  --output cli \
  --output sarif \
  --output-file-path console,checkov.sarif
```

Use SARIF for GitHub code scanning.

## Recommended local Checkov pass

```bash
checkov \
  --directory . \
  --config-file .checkov.yml \
  --output cli \
  --soft-fail
```

## CI-style local Checkov pass

```bash
checkov \
  --directory . \
  --config-file .checkov.yml \
  --output cli \
  --output sarif \
  --output-file-path console,checkov.sarif \
  --soft-fail
```

## List available checks

```bash
checkov --list
```

## List checks for a framework

```bash
checkov --list --framework ansible
```

```bash
checkov --list --framework terraform
```

```bash
checkov --list --framework github_actions
```

## Debug Checkov config and parsing

```bash
LOG_LEVEL=debug checkov \
  --directory . \
  --framework ansible \
  --soft-fail
```

Useful when Checkov behaves strangely or does not appear to respect config.

## Terraform inline skip

Use this inside the affected resource block.

```hcl
resource "github_repository" "blog" {
  #checkov:skip=CKV_GIT_1:Hugo/static site repository is intentionally public.

  name       = "blog"
  visibility = "public"
}
```

Important formatting:

```text
#checkov:skip=CHECK_ID:Reason
```

Do not use:

```text
# checkov:skip=CHECK_ID: Reason
```

The strict form is cleaner and more reliable.

## Terraform branch protection skips

Put branch-protection skips on the branch-protection resource, not the repository resource.

```hcl
resource "github_branch_protection" "blog" {
  #checkov:skip=CKV_GIT_5:Personal homelab repo; two approvals are not practical.
  #checkov:skip=CKV_GIT_6:Signed commits are not currently enforced.

  repository_id = github_repository.blog.node_id
}
```

## Ansible inline skip

Put the skip directly on the affected task.

```yaml
- name: Patroni dynamic pg_hba | Query Patroni cluster state
  #checkov:skip=CKV2_ANSIBLE_1:Internal homelab service endpoint over trusted management network.
  ansible.builtin.uri:
    url: "http://{{ inventory_hostname }}:8008/cluster"
```

Use this for real accepted risks, not for things that are easy to fix cleanly.

## Ansible block skip warning

Checkov currently has, or recently had, a bug where inline skips on Ansible `block:` tasks are ignored for block graph checks such as:

```text
CKV2_ANSIBLE_3
```

Until that is fixed and released, avoid relying on inline skip comments for Ansible block resources.

Prefer one of these:

```text
1. Remove the block if it is only grouping tasks.
2. Add a real rescue section if the block is critical.
3. Dismiss the GitHub alert as accepted risk.
4. Temporarily skip the check globally only if it becomes too noisy.
```

Do not contort good Ansible just to satisfy a broken scanner.

## Dockerfile inline skip

```dockerfile
#checkov:skip=CKV_DOCKER_2:Healthcheck is provided by Docker Compose/Swarm instead.
FROM alpine:3.20
```

## Global skip in `.checkov.yml`

Use this sparingly.

```yaml
skip-check:
  - CKV_GIT_1
  - CKV_GIT_5
  - CKV_GIT_6
```

Prefer inline skips when the exception is resource-specific.

Global skips are useful only when a check is consistently irrelevant to the repo.

## Useful Checkov examples for this repo

### Check GitHub Actions permissions

```bash
checkov \
  --directory .github/workflows \
  --framework github_actions \
  --check CKV2_GHA_1
```

### Check Ansible only

```bash
checkov \
  --directory ansible \
  --framework ansible \
  --soft-fail
```

### Check Terraform only

```bash
checkov \
  --directory terraform \
  --framework terraform \
  --soft-fail
```

### Check Dockerfiles only

```bash
checkov \
  --directory . \
  --framework dockerfile \
  --soft-fail
```

### Re-test one known finding

```bash
checkov \
  --file terraform/github/hugo/main.tf \
  --framework terraform \
  --check CKV_GIT_1 \
  --soft-fail
```

## Recommended GitHub Actions permissions for Checkov

In `.github/workflows/checkov.yml`:

```yaml
permissions:
  contents: read
  security-events: write
  actions: read
```

`security-events: write` is needed when uploading SARIF to GitHub code scanning.

## Recommended GitHub Actions concurrency

In `.github/workflows/checkov.yml`:

```yaml
concurrency:
  group: checkov-${{ github.ref }}
  cancel-in-progress: true
```

This prevents stale Checkov runs from piling up.

## Example Checkov workflow shape

```yaml
---
name: Security (Checkov)

on:
  push:
    paths:
      - ".github/workflows/**"
      - "ansible/**"
      - "terraform/**"
      - "opentofu/**"
      - "**/*.tf"
      - "**/*.tfvars"
      - "**/Dockerfile"
      - "**/*.dockerfile"
      - ".checkov.yml"

  pull_request:
    paths:
      - ".github/workflows/**"
      - "ansible/**"
      - "terraform/**"
      - "opentofu/**"
      - "**/*.tf"
      - "**/*.tfvars"
      - "**/Dockerfile"
      - "**/*.dockerfile"
      - ".checkov.yml"

  workflow_dispatch:

permissions:
  contents: read
  security-events: write
  actions: read

concurrency:
  group: checkov-${{ github.ref }}
  cancel-in-progress: true

jobs:
  checkov:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v7

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: "3.12"

      - name: Install Checkov
        run: python -m pip install --upgrade checkov

      - name: Run Checkov
        run: |
          checkov \
            --directory . \
            --config-file .checkov.yml \
            --output cli \
            --output sarif \
            --output-file-path console,checkov.sarif \
            --soft-fail

      - name: Upload Checkov SARIF
        uses: github/codeql-action/upload-sarif@v4
        if: always()
        with:
          sarif_file: checkov.sarif
```

## Soft fail versus GitHub alerts

`--soft-fail` only affects the Checkov exit code.

It does not mean findings disappear.

If SARIF is uploaded, GitHub can still show code scanning alerts.

Use one of these to remove noisy alerts:

```text
1. Fix the finding.
2. Add a valid inline skip.
3. Add a global skip in .checkov.yml.
4. Dismiss the alert in GitHub as accepted risk or false positive.
```

## Good reasons to inline skip

* Public repo is intentionally public.
* Personal repo does not require two approvals.
* Internal HTTP endpoint is only on a trusted management network.
* Scanner rule does not match the homelab threat model.
* Upstream scanner bug causes a false positive.

## Bad reasons to inline skip

* The finding is easy to fix.
* The workflow really is over-permissioned.
* A secret might actually be exposed.
* The service is accidentally internet-facing.
* The skip reason is vague, like `not needed`.

## Good skip reason examples

```text
Personal homelab repository; two approvals are not practical.
Hugo/static site repository is intentionally public.
Internal homelab service endpoint over trusted management network.
Healthcheck is defined at Compose/Swarm level instead of Dockerfile.
Accepted risk for personal infrastructure repository.
```

## Bad skip reason examples

```text
ignore
false positive
not needed
doesn't matter
homelab
```

## Checkov findings worth fixing

Usually fix these instead of skipping:

* GitHub Actions workflow has write-all permissions.
* GitHub Actions job has unnecessary `contents: write`.
* Secrets appear in plaintext.
* Dockerfile runs as root when it does not need to.
* Terraform resource exposes something publicly by accident.
* Ansible task disables certificate validation against an internet endpoint.

## Checkov findings often acceptable in this repo

Often skip or dismiss these after review:

* Public GitHub repo for a public Hugo/static site.
* Two required PR approvals for a personal repo.
* Signed commits required for a personal repo.
* Internal HTTP calls to trusted homelab services.
* Scanner noise around Ansible block/rescue structure.

## Quick triage flow

```text
1. Is the finding real?
   - Yes: fix it.
   - No: skip or dismiss it.

2. Is it repo-wide policy noise?
   - Yes: consider .checkov.yml skip-check.
   - No: prefer inline skip.

3. Is the finding from SARIF on GitHub but fixed locally?
   - Merge to main.
   - Let Checkov run on main.
   - Wait for SARIF processing.
   - If still stale, dismiss manually.

4. Is the finding from an old deleted workflow?
   - Remove stale code scanning configuration in GitHub.
   - Do not re-add deleted workflows just to close old alerts.
```

## Current recommended local gate

```bash
ruff check --fix \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit

ruff format \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit

python -m pytest tests/unit

skynet check all

checkov \
  --directory . \
  --config-file .checkov.yml \
  --output cli \
  --soft-fail
```

## Current recommended CI-style gate

```bash
ruff check \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit

ruff format --check --diff \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit

python -m pytest tests/unit

checkov \
  --directory . \
  --config-file .checkov.yml \
  --output cli \
  --output sarif \
  --output-file-path console,checkov.sarif \
  --soft-fail
```

## Useful one-liners

### Show Checkov version

```bash
checkov --version
```

### Debug config source

```bash
checkov --show-config
```

### Scan only Ansible drift file

```bash
checkov \
  --file ansible/roles/docker_services/tasks/sub_tasks/drift/image.yml \
  --framework ansible \
  --soft-fail
```

### Scan only GitHub Actions

```bash
checkov \
  --directory .github/workflows \
  --framework github_actions \
  --soft-fail
```

### Scan only Terraform GitHub module

```bash
checkov \
  --directory terraform/github \
  --framework terraform \
  --soft-fail
```

### Check one rule everywhere

```bash
checkov \
  --directory . \
  --check CKV2_GHA_1 \
  --soft-fail
```

### Skip one noisy rule temporarily

```bash
checkov \
  --directory . \
  --skip-check CKV2_ANSIBLE_3 \
  --soft-fail
```

## Personal rule

Fix real issues.

Inline skip accepted risks.

Globally skip only when a rule is broadly irrelevant or broken.

Do not make the repo worse just to please Checkov.
