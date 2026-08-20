# Terraform Cheat Sheet

## Typical workflow

```bash
terraform fmt
terraform init
terraform validate
terraform plan
terraform apply
```

Main workflow commands: `init`, `validate`, `plan`, `apply`, and `destroy`.

## Most useful commands

### Format and validate

```bash
terraform fmt
terraform fmt -recursive
terraform validate
```

+ `terraform fmt` - reformats Terraform files to standard style
+ `terraform validate` - checks whether the configuration is valid.

### Initialize a working directory

```bash
terraform init
terraform init -upgrade
terraform init -reconfigure
```

+ `terraform init` - downloads providers and prepares the directory
+ `terraform init -upgrade` - upgrades providers/modules within your version constraints
+ `terraform init -reconfigure` - reinitializes backend/provider settings.

### See what Terraform will do

```bash
terraform plan
terraform plan -out=tfplan
terraform show tfplan
```

+ `terraform plan` - shows the proposed changes
+ `terraform plan -out=tfplan` - saves the exact plan to a file
+ `terraform show tfplan` - displays a saved plan.

### Apply changes

```bash
terraform apply
terraform apply tfplan
```

+ `terraform apply` - creates or updates infrastructure
+ `terraform apply tfplan` - Applying a saved plan file ensures you execute exactly what was planned.

### Destroy infrastructure

```bash
terraform destroy
```
Destroys resources managed by the current state.

## Helpful day-to-day commands

### Show outputs

```bash
terraform output
terraform output postgres_vm_ips
terraform output -json
```

Prints output values from the root module.

### See installed/required providers

```bash
terraform providers
```

Shows the providers required by the configuration.

### Inspect current state

```bash
terraform state list
terraform state show proxmox_vm_qemu.postgres["pg95"]
terraform show
```

+ `terraform state` - list lists resources in state
+ `terraform state` - show shows one resource from state
+ `terraform show` - displays the current state or a saved plan.

### Import an existing resource into state

```bash
terraform import <resource_address> <real_world_id>
```

**Example:**

```bash
terraform import 'proxmox_vm_qemu.postgres["pg95"]' 9205
```

+ `terraform import` - associates an existing real resource with a Terraform resource address.

### Open the Terraform console

```bash
terraform console
```

**Useful for testing expressions:**

```bash
keys(var.postgres_vms)
file(var.ssh_public_key_path)
```

+ `terraform console` - opens an interactive expression console.

## Useful targeting and debugging commands

### Target a single resource

```bash
terraform plan -target='proxmox_vm_qemu.postgres["pg95"]'
terraform apply -target='proxmox_vm_qemu.postgres["pg95"]'
```

Good for first-pass testing, but avoid relying on -target for normal ongoing workflow.

### Replace a resource

```bash
terraform apply -replace='proxmox_vm_qemu.postgres["pg95"]'
```

Useful when you want Terraform to recreate a specific resource.

### Refresh and inspect

```bash
terraform refresh
terraform show
```

+ `refresh` - updates state to match remote systems.

## Workspace commands

```bash
terraform workspace list
terraform workspace show
terraform workspace new dev
terraform workspace select dev
terraform workspace delete dev
```

Terraform supports managing workspaces from the CLI. Be careful with workspaces: they change which state you are operating against. Remote backends can also affect workspace behavior.

## Module commands

```bash
terraform modules
terraform modules -json
```

+ `terraform modules` - shows declared modules in the current working directory.
+ Requires Terraform v1.10.0 or later.

## Common file layout

```bash
.
├── versions.tf
├── provider.tf
├── variables.tf
├── main.tf
├── outputs.tf
├── terraform.tfvars
├── secrets.auto.tfvars   # gitignored
└── .terraform.lock.hcl
```

**Typical purpose of each file:**
+ `versions.tf` — Terraform and provider version constraints
+ `provider.tf` — provider configuration
+ `variables.tf` — input variable declarations
+ `main.tf` — resources, data sources, modules
+ `outputs.tf` — output values
+ `terraform.tfvars` — normal variable values
+ `secrets.auto.tfvars` — local secret values, not committed
+ `.terraform.lock.hcl` — provider dependency lock file

## Useful flags

### Save the plan

```bash
terraform plan -out=tfplan
terraform apply tfplan
```

### Upgrade providers/modules

```bash
terraform init -upgrade
```

### Output JSON

```bash
terraform output -json
terraform show -json tfplan
terraform modules -json
```

### Disable color for logs/CI

```bash
terraform plan -no-color
terraform apply -no-color
```

## Variables and secrets

### Good pattern

**Commit normal config:**

```bash
# terraform.tfvars
pm_api_url      = "https://192.168.80.80:8006/api2/json"
target_node     = "pve01"
clone_template  = "ubuntu-2604-lts-cloudinit-template"
vm_storage      = "local-zfs"

```

**Keep secrets local and gitignored:**

```bash
# secrets.auto.tfvars
pm_api_token_id     = "terraform@pve!terraform"
pm_api_token_secret = "REDACTED"
```

**Important note:**

Marking a variable as `sensitive = true` hides it from normal CLI output... 
...but sensitive values can still end up in state and plan files. Protect your state files.

## State safety

**Files to protect or ignore:**

```bash
.terraform/
*.tfstate
*.tfstate.*
crash.log
crash.*.log
secrets.auto.tfvars
```

Terraform state contains what Terraform believes exists, and it can contain sensitive values. Terraform recommends securing state appropriately and often using a remote backend for shared/team use.

## Commands I’d use most in a homelab

```bash
terraform fmt
terraform init -upgrade
terraform validate
terraform plan
terraform apply
terraform output
terraform state list
terraform state show <resource>
terraform destroy
```

**For one-resource testing:**

```bash
terraform plan -target='proxmox_vm_qemu.postgres["pg95"]'
terraform apply -target='proxmox_vm_qemu.postgres["pg95"]'
```

## Practical workflow for your homelab

### First run

```bash
terraform fmt
terraform init -upgrade
terraform validate
terraform plan
terraform apply -target='proxmox_vm_qemu.postgres["pg95"]'
```

### After the first VM works

```bash
terraform plan
terraform apply
```

### Inspect what Terraform knows

```bash
terraform state list
terraform state show 'proxmox_vm_qemu.postgres["pg95"]'
terraform output postgres_vm_ips
```

### Tear down when done

```bash
terraform destroy
```

## Easy mistakes to avoid
+ Forgetting terraform init after changing provider versions
+ Committing *.tfstate or secret tfvars files
+ Using -target as the normal workflow instead of as a temporary debugging tool
+ Editing real infrastructure manually and forgetting Terraform state will drift
+ Trusting sensitive = true as if it encrypts secrets
+ Using docs/examples for a different provider version than the one actually installed


## Quick mental model
+ `fmt` = clean formatting
+ `init` = download/setup
+ `validate` = syntax/schema check
+ `plan` = preview
+ `apply` = do it
+ `output` = read outputs
+ `state` = inspect Terraform’s memory
+ `destroy` = remove managed infra
