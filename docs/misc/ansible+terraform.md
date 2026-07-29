# Ansible <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/ansible.svg" alt="Ansible" width="24" /> + Terraform <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/hashicorp-terraform.svg" alt="Terraform" width="24" />

<img width="60%" height="50%" alt="apkdh8" src="https://github.com/user-attachments/assets/2a84ff34-5974-4809-9820-0e4fcde7f7ae" />

## Introduction

Recently, I finally added Terraform (OpenTofu to be specific) into my homelab setup. One thing I noticed in my very brief research on Terraform in the past is people trying to compare Ansible + Terraform like it's a question of one or the other. But in reality, it's a case of **why not both?**

They both have strengths in automating different things, and in my homelab they work side-by-side to achieve my needs.

<img width="220" height="164" alt="both-taco" src="https://github.com/user-attachments/assets/14974aba-6c01-42c8-92d9-76e0951533fe" />

## Teamwork makes the dream work

### 1. Using Ansible to automate the setup of Terraform

I use Ansible to install Terraform on my management VM using the `OpenTofu` role. I then use tasks in this role to create the Proxmox Terraform token, user, and role with the required privileges for the BPG Terraform Provider.

### 2. Using Terraform to configure Proxmox and create VMs

- Using the BPG Terraform Provider, I create hardware mappings, configure network settings, configure VM templates, and automate the creation of multiple VMs, including UnRaid and Postgres cluster VMs.
- Via a snippet, I install and configure Tailscale on the VMs, with Tailscale being the primary connection method for my Ansible hosts.

### 3. Ansible takes the torch

After Terraform creates the VM, I then hand it over to Ansible to automate everything, including filesystem config and runtime installation. Service deployment now flows through the runtime-aware service catalog: `service_prepare` owns application-specific preparation, `service_common` owns shared configuration and integrations, and `docker_services` or `podman_services` owns the selected runtime lifecycle.

## The delineation point

When using both Ansible + Terraform, it's important to think about the strengths of each tool. In reality, both tools are capable of automating many of the same tasks, but one tool is often going to fit a particular use case better than the other.

- **Ansible** is the *config king*. It's great at filesystem tasks, templating, configs, and procedurally performing tasks gated with various conditionals, across a wide variety of hosts (often in a single play). It has modules for just about everything. It does not need to keep track of state, and it's suited to both major and minute automations. It's the driving force behind my homelab.
- **Terraform** is stateful. It focuses on a pre-defined final state for infrastructure, services, and configuration. If there is drift from this state, it will act to bring things back into line (You can ignore changes to some elements, but then you'll leave yourself manually configuring those things instead, or using Ansible for them). I've found it suited for orchestrating VMs (in Proxmox) and external infrastructure/services.

**TL;DR:** there are infrastructure, service, and config tasks that benefit from Terraform's stateful nature, and others that do not.

## Example: Cloudflare DNS

The creation of DNS records is something I used Ansible for until very recently, but now use Terraform for.

### The Ansible Process

#### 1. Service var toggles are used to indicate whether a service needs a Cloudflare DNS record (the conditional)

```yaml
cloudflare:
  enable: true
```

<details>
<summary>Show Ansible include task</summary>

```yaml
- name: Ensure Cloudflare DNS record exists
  when:
    - inventory_hostname == docker_services_primary_manager
    - docker_services_svc.cloudflare is defined
    - (docker_services_svc.cloudflare.enable | default(false)) | bool
  ansible.builtin.include_tasks:
    file: sub_tasks/cloudflare/tasker.yml
    apply:
      tags: [deploy, update, recreate]
  tags: [deploy, update, recreate]
```

</details>

#### 2. The 'tasker' retrieves the public IP and Cloudflare credentials

<details>
<summary>Show full Ansible tasker</summary>

```yaml
---

################################
# PUBLIC IP (ONLY IF NEEDED)
################################

- name: Cloudflare | Normalize record values for public IP check
  when:
    - docker_services_svc.cloudflare.records is defined
    - docker_services_svc.cloudflare.records is sequence
    - docker_services_svc.cloudflare.records is not string
  ansible.builtin.set_fact:
    docker_services_cf_record_values_normalized: >-
      {{
        docker_services_svc.cloudflare.records
        | map(attribute='value')
        | map('default', '')
        | map('string')
        | map('trim')
        | list
      }}

- name: Cloudflare | Determine whether public IP lookup is needed
  ansible.builtin.set_fact:
    docker_services_cf_needs_public_ip: >-
      {{
        (
          docker_services_svc.cloudflare.records is not defined
          and (
            (docker_services_svc.cloudflare.value is not defined)
            or ((docker_services_svc.cloudflare.value | default('') | string | trim) == '')
          )
        )
        or
        (
          docker_services_svc.cloudflare.records is defined
          and (
            (
              docker_services_svc.cloudflare.records is mapping
              and (
                (docker_services_svc.cloudflare.records.value is not defined)
                or ((docker_services_svc.cloudflare.records.value | default('') | string | trim) == '')
              )
            )
            or
            (
              docker_services_svc.cloudflare.records is sequence
              and docker_services_svc.cloudflare.records is not string
              and (
                (docker_services_cf_record_values_normalized | reject('equalto', '') | list | length)
                < (docker_services_cf_record_values_normalized | length)
              )
            )
          )
        )
      }}

- name: Cloudflare | Gather public IP facts
  when: docker_services_cf_needs_public_ip | bool
  block:
    - name: Gather IP geolocation data
      community.general.ipinfoio_facts:

    - name: Gather public IP data
      community.general.ipify_facts:
        api_url: https://api64.ipify.org
        timeout: 20
      register: docker_services_public_ip_result

    - name: Public IP output
      ansible.builtin.debug:
        msg: "{{ ansible_facts['ipify_public_ip'] }}"

    - name: Set public_ip fact
      ansible.builtin.set_fact:
        docker_services_public_ip: "{{ ansible_facts['ipify_public_ip'] }}"

################################
# API (VIA INFISICAL)
################################

- name: Cloudflare | Detect if API is missing
  ansible.builtin.set_fact:
    docker_services_cf_api_missing: >-
      {{
        (cloudflare_api | default('') | string | trim | length == 0)
      }}

- name: Cloudflare | Fetch cloudflare_api from Infisical (only if missing)
  when: docker_services_cf_api_missing | bool
  ansible.builtin.include_tasks: >-
    {{ role_path }}/tasks/sub_tasks/prep/infisical/_fetch.yml
  vars:
    infisical_fail_on_empty: true
    infisical_flatten: true
    secrets_map:
      - var: cloudflare_api
        path: "/Cloudflare"
        name: API

################################
# ZONE (VIA INFISICAL)
################################

- name: Cloudflare | Detect if zone is missing
  ansible.builtin.set_fact:
    docker_services_cf_zone_missing: >-
      {{
        (cloudflare_zone | default('') | string | trim | length == 0)
      }}

- name: Cloudflare | Fetch cloudflare_zone from Infisical (only if missing)
  when: docker_services_cf_zone_missing | bool
  ansible.builtin.include_tasks: >-
    {{ role_path }}/tasks/sub_tasks/prep/infisical/_fetch.yml
  vars:
    infisical_fail_on_empty: true
    infisical_flatten: true
    secrets_map:
      - var: cloudflare_zone
        path: "/Cloudflare"
        name: ZONE

################################
# CREDS (ASSERT)
################################

- name: Cloudflare | Assert creds are now present
  ansible.builtin.assert:
    that:
      - (cloudflare_api | default('') | string | trim | length) > 0
      - (cloudflare_zone | default('') | string | trim | length) > 0
    fail_msg: >-
      cloudflare_api/cloudflare_zone are still empty after Infisical fetch.
      api_len={{ (cloudflare_api | default('') | string | trim | length) }},
      zone='{{ cloudflare_zone | default('') | string | trim }}'

################################
# DOCKER SECRET
################################

- name: Create Cloudflare API secret  ## Used by Traefik
  when: (docker_services_stack_deploy_type | default('container', true)) == 'swarm'
  community.docker.docker_secret:
    name: cloudflare_api_secret
    data: "{{ cloudflare_api }}"
    state: present

################################
# DNS TASKER
################################

- name: Build Cloudflare records list (single or multiple)
  ansible.builtin.set_fact:
    docker_services_cloudflare_records_effective: >-
      {{
        (
          [docker_services_svc.cloudflare.records]
          if (
            docker_services_svc.cloudflare.records is defined
            and docker_services_svc.cloudflare.records is mapping
          )
          else (
            docker_services_svc.cloudflare.records
            if (
              docker_services_svc.cloudflare.records is defined
              and docker_services_svc.cloudflare.records is sequence
              and docker_services_svc.cloudflare.records is not string
            )
            else [
              {
                'record': (
                  docker_services_svc.cloudflare.record
                  | default(docker_services_svc.name | default(docker_services_service_name, true), true)
                ),
                'value': (
                  docker_services_svc.cloudflare.value
                  | default(docker_services_public_ip, true)
                ),
                'type': (
                  docker_services_svc.cloudflare.type
                  | default('A', true)
                ),
                'proxy': (
                  docker_services_svc.cloudflare.proxy
                  | default(false, true)
                ),
                'solo': (
                  docker_services_svc.cloudflare.solo
                  | default(true, true)
                )
              }
            ]
          )
        )
      }}

- name: Configure Cloudflare DNS records
  ansible.builtin.include_tasks: _dns.yml
  vars:
    cloudflare_record: "{{ docker_services_cf_record.record }}"
    cloudflare_record_value: "{{ docker_services_cf_record.value | default(docker_services_public_ip, true) }}"
    cloudflare_record_type: "{{ docker_services_cf_record.type | default('A', true) }}"
    cloudflare_proxy: "{{ (docker_services_cf_record.proxy | default(false, true)) | bool }}"
    cloudflare_solo: "{{ (docker_services_cf_record.solo | default(true, true)) | bool }}"
  loop: "{{ docker_services_cloudflare_records_effective }}"
  loop_control:
    loop_var: docker_services_cf_record
    label: >-
      {{
        (docker_services_cf_record.type | default('A', true))
        ~ ' '
        ~ docker_services_cf_record.record
        ~ ' -> '
        ~ (
          docker_services_cf_record.value
          | default(docker_services_public_ip, true)
          | string
        )
      }}
```

</details>

#### 3. Cloudflare DNS module creates the record

<details>
<summary>Show DNS record task</summary>

```yaml
---

- name: Cloudflare DNS | Normalize inputs
  ansible.builtin.set_fact:
    docker_services_cf_record_name: "{{ cloudflare_record | default('@', true) | string | trim }}"
    docker_services_cf_record_type: "{{ cloudflare_record_type | default('A', true) | string | trim }}"
    docker_services_cf_record_value: "{{ cloudflare_record_value | string | trim }}"
    docker_services_cf_record_proxy: "{{ (cloudflare_proxy | default(false, true)) | bool }}"
    docker_services_cf_record_solo: "{{ (cloudflare_solo | default(true, true)) | bool }}"

- name: Cloudflare DNS | Debug normalized inputs
  ansible.builtin.debug:
    msg:
      zone: "{{ cloudflare_zone }}"
      record: "{{ docker_services_cf_record_name }}"
      type: "{{ docker_services_cf_record_type }}"
      value: "{{ docker_services_cf_record_value }}"
      proxied: "{{ docker_services_cf_record_proxy }}"
      solo: "{{ docker_services_cf_record_solo }}"

- name: Cloudflare DNS | Assert normalized inputs look sane
  ansible.builtin.assert:
    that:
      - cloudflare_zone | string | trim | length > 0
      - (cloudflare_zone | string | trim | regex_search('\\.')) is not none
      - docker_services_cf_record_name | string | trim | length > 0
    fail_msg: >-
      Invalid Cloudflare DNS inputs:
      zone='{{ cloudflare_zone | default("") }}'
      record='{{ docker_services_cf_record_name | default("") }}'

- name: Cloudflare DNS | Add or update record
  community.general.cloudflare_dns:
    api_token: "{{ cloudflare_api }}"
    zone: "{{ cloudflare_zone }}"
    state: present
    solo: "{{ docker_services_cf_record_solo }}"
    proxied: "{{ docker_services_cf_record_proxy }}"
    type: "{{ docker_services_cf_record_type }}"
    value: "{{ docker_services_cf_record_value }}"
    record: "{{ docker_services_cf_record_name }}"
  register: docker_services_cf_result

- name: Cloudflare DNS | Display status
  when: docker_services_cf_result is succeeded
  ansible.builtin.debug:
    msg: >-
      DNS {{ docker_services_cf_record_type }} record for
      "{{
        (docker_services_cf_record_name in ['@', cloudflare_zone])
        | ternary(cloudflare_zone, docker_services_cf_record_name ~ '.' ~ cloudflare_zone)
      }}"
      set to "{{ docker_services_cf_record_value }}". Proxy: {{ docker_services_cf_record_proxy }}
```

</details>

#### End Result:
- These tasks successfully create DNS records that are in place before a service deploys
- Because it is not tracking the full desired state, I would end up with useless or redundant records whenever I changed the name of a service, such as when I moved from `radarr4k` and `sonarr4k` to `radarr-4k` and `sonarr-4k`, or simply stopped using a service.
- Since Cloudflare is not a site I regularly access, I would end up with quite a drift.

### The Terraform way

<a href="https://github.com/Lebowski89/homelab/tree/main/terraform/cloudflare/homelab">See terraform/cloudflare/homelab for full module</a>

<details>
<summary>Show Terraform example</summary>

```tf
locals {
  ipv4_records = [
    "authelia",
    "infisical",
    "opencloud",
    "traefik",
    "vaultwarden",
  ]
}

resource "cloudflare_dns_record" "service_a" {
  for_each = toset(local.ipv4_records)

  zone_id = var.cloudflare_zone_id
  name    = each.value
  type    = "A"
  content = var.public_ipv4
  ttl     = 1
  proxied = false
}
```

</details>

Using Terraform, I've explicitly defined which records should exist, and anything outside of this gets removed.

## Conclusion

Ansible and Terraform are great tools that are both valuable in a homelab. The question should not be whether you should use one or the other, but where you should use each tool in your setup in a way that makes the most of the strengths each brings.
