# Workflows

lint.yml          -> Runs ansible-lint, yamllint, ruff
checkov.yml       -> Runs Terraform/GitHub Actions/Dockerfile security scan
secrets-check.yml -> Runs forbidden private files + gitleaks detection
tofu-check.yml    -> Runs tofu fmt/init/validate
docs workflows    -> Runs ansible and terraform auto-generated docs