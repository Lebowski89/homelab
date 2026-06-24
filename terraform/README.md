# Terraform

## OpenTofu

I use OpenTofu rather than Terraform. It's essentially a community-driven drop-in replacement for Terraform.

The `required_version` in each module’s `versions.tf` reflects the OpenTofu version I use. If you are using Terraform instead, you should adjust that version constraint to match your Terraform version. No other changes are required that I know.

## Scripts

### tofu-all.sh

This bash script allows for quick tofu init, upgrade, validate, plan and apply.

Commands:

```
tofu-all.sh init
tofu-all.sh upgrade
tofu-all.sh validate
tofu-all.sh plan
tofu-all.sh apply
```

Make script executable:

```
chmod +x tofu-all.sh
```

As always, take care running the apply command. Only run it when you want to change things.
