## Workflows

| Workflow | Purpose |
|---|---|
| `lint.yml` | Runs `ansible-lint`, `yamllint`, and `ruff`. |
| `checkov.yml` | Runs security scanning for Terraform, GitHub Actions, and Dockerfiles. |
| `secrets-check.yml` | Checks for forbidden private files and runs Gitleaks detection. |
| `tofu-check.yml` | Runs `tofu fmt`, `tofu init`, and `tofu validate`. |
| `alerting-config-validation.yml` | Validates Prometheus alert rules and Alertmanager configuration. |
| Docs workflows | Regenerates Ansible role docs and Terraform/OpenTofu module docs. |
