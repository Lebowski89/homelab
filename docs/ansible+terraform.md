# Ansible + Terraform

## Introduction

Recently, I finally added Terraform (OpenTofu to be specific) into my homelab setup. One thing I noticed in my very brief research on Terraform in the past (Very brief as in a quick google search and some reddit topics), is people trying to compare Ansible + Terraform, like it is a question of one or the other. But it really is a situation of 'Why not both?!?'. They both have strengths in automating different things, and in my homelab they work side-by-side to achieve what I need them to achieve.

## Teamwork makes the dream work

### 1. Using Ansible to automate the setup of Terraform

I use Ansible to install Terraform on my management VM, in the 'OpenTofu' role. I then have tasks in this role to create the Proxmox Terraform token/user/role with the required privleges for the BPG Terraform Provider.

### 2. Using Terraform to configure Proxmox and create VMs

Using the BPG Terraform Provider, I create hardware mappings, configure network settings, configure VM templates, and automate the creation of multiple VMs, including UnRaid and my postgres cluster VMs. Additionally, I use a snippet to install and configure Tailscale on the newly minted VMs, with Tailscale being the primary way my Ansible hosts connect to each other.

### 3. Ansible takes the torch

After Terraform creates the VM, I then hand it over to Ansible to automate everything from the configuring of the filesystem (ubuntu role), the install and configuring of Docker/Docker Swarm/Infisical, and most importantly - all the preparation and configuring and deployment of all my Docker containers and Swarm services (via the aptly named 'docker_services' role).

## The delineation point

When using both Ansible + Terraform, it's important to think about the strengths of each tool. In reality, both tools are capable of automating many of the same tasks, but one tool is going to fit your needs more than the other. 

- Ansible is the 'config king', it's great at filesystem tasks, templating, configs, procedurally performing tasks gated with various conditionals. It has modules for pretty much every topic around (Cue Jeff Geerling saying 'There's a module for that' in his Ansible tutorials). It doesn't need to keep track of state, and it's suited for both major and minute automations.

- Terraform is stateful, it focusses on a pre-defined final state for a VM or config. If there is drift from this state it will act destructively to bring the VM or service config back into line. You can ignore changes to the state of some elements in the VM or service, but then you'll leave yourself manually configuring those things (or using Ansible) instead. Some things will benefit from the stateful nature, especially where you want minimal to no drift, including orchestrating VMs and automating external infrastructure/services (including Cloudflare DNS records).

TLDR: There are infrastructure/services/config tasks that will benefit from Terraform's stateful nature and those that will not

### Example: Cloudflare DNS

The creation of DNS records is something I used ansible for until very recently:

1. The creation of the DNS records would be conditional on a toggle in each services group_vars/service_vars

```yaml
cloudflare:
  enable: true
```

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

2. In the tasker I would retrieve the public_ip and cloudflare credentials

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
    {{ role_path }}/tasks/prep/01_pre_filesystem/sub_tasks/infisical/_fetch.yml
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
    {{ role_path }}/tasks/prep/01_pre_filesystem/sub_tasks/infisical/_fetch.yml
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

3. I then used the Cloudflare DNS modules to create the record

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
      - (cloudflare_zone | string | trim | regex_search('\.')) is not none
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

This works great, creates DNS records that are in place before a service deploys. However, as it isn't tracking the state, I would end up with useless/redundant records whenever I would change the name of a service (i.e, when I moved from radarr4k/sonarr4k to radarr-4k/sonarr-4k) or simply stopped using a service. And since Cloudflare is not a site I reguarly access, I would end up with quite a drift. So that is a situation where I'm happy for Terraform to take over and manage it. 

4. The terraform way

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
```

In the terraform way, I've explicitly defined which records should be there and anything outside of this will be removed. 


## Conclusion

Ansible and Terraform are great tools that are valuable in a homelab. The question should not be whether you should use one or the other, but a question of where you'll use each tool in your setup in a way that utilises the strengths that each brings.