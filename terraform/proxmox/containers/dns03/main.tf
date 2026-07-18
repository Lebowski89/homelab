locals {
  netbox_dns_ips       = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.dns_ips, {}) : {}
  netbox_host_ips      = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.host_primary_ipv4, {}) : {}
  netbox_internal_zone = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.internal_zone, "") : ""

  node_name          = trimspace(var.target_node)
  container_hostname = trimspace(var.container_hostname)

  # NetBox takes precedence when available. var.dns_ips fills missing keys or
  # provides fallback values when remote state is disabled.
  dns_ips = merge(
    var.dns_ips,
    local.netbox_dns_ips,
  )

  pm_node_ip = trimspace(
    lookup(local.netbox_host_ips, local.node_name, "")
  )

  explicit_pm_api_url = trimspace(var.pm_api_url)

  pm_api_url = local.explicit_pm_api_url != "" ? local.explicit_pm_api_url : (
    local.pm_node_ip != ""
    ? "https://${local.pm_node_ip}:${var.pm_api_port}/"
    : ""
  )

  pm_ssh_host = trimspace(var.pm_ssh_host) != "" ? trimspace(var.pm_ssh_host) : local.pm_node_ip

  container_primary_ipv4 = trimspace(
    lookup(local.netbox_host_ips, local.container_hostname, "")
  )

  explicit_container_ip = trimspace(var.container_ip)

  container_ip = local.explicit_container_ip != "" ? local.explicit_container_ip : (
    local.container_primary_ipv4 != ""
    ? "${local.container_primary_ipv4}/${var.container_prefix_length}"
    : ""
  )

  explicit_container_gateway = trimspace(var.container_gateway)

  derived_container_gateway = local.container_ip != "" ? try(
    cidrhost(local.container_ip, var.container_gateway_host_number),
    ""
  ) : ""

  container_gateway = local.explicit_container_gateway != "" ? local.explicit_container_gateway : local.derived_container_gateway

  dns_vip_servers = distinct(compact([
    trimspace(lookup(local.dns_ips, "dns_vip_a", "")),
    trimspace(lookup(local.dns_ips, "dns_vip_b", "")),
  ]))

  configured_container_dns_servers = distinct(compact([
    for server in var.container_dns_servers : trimspace(server)
  ]))

  # Preserve the existing behaviour:
  # - use DNS VIPs while NetBox remote state is enabled;
  # - otherwise use explicitly configured servers when supplied;
  # - fall back to var.dns_ips VIPs when no explicit servers are supplied.
  use_dns_vips = var.enable_netbox_remote_state || length(local.configured_container_dns_servers) == 0

  container_dns_servers = local.use_dns_vips ? local.dns_vip_servers : local.configured_container_dns_servers

  container_dns_domain_source = trimspace(local.netbox_internal_zone) != "" ? local.netbox_internal_zone : var.container_dns_domain
  container_dns_domain        = trim(trimspace(local.container_dns_domain_source), ".")
}

resource "proxmox_virtual_environment_container" "dns03" {
  node_name   = local.node_name
  vm_id       = var.container_vmid
  description = var.container_description

  started       = true
  start_on_boot = true
  protection    = var.container_protection
  unprivileged  = false

  lifecycle {
    ignore_changes = [
      features,
    ]

    precondition {
      condition     = local.node_name != ""
      error_message = "target_node must not be empty."
    }

    precondition {
      condition     = local.container_hostname != ""
      error_message = "container_hostname must not be empty."
    }

    precondition {
      condition     = can(cidrhost(local.container_ip, 0))
      error_message = "Unable to determine a valid IPv4 CIDR for dns03. Set container_ip explicitly or ensure NetBox outputs.host_primary_ipv4 contains the container_hostname entry."
    }

    precondition {
      condition     = can(cidrhost("${local.container_gateway}/32", 0))
      error_message = "Unable to determine a valid IPv4 gateway for dns03. Set container_gateway explicitly or provide a valid container IP and gateway host number."
    }

    precondition {
      condition = (
        local.use_dns_vips
        ? length(local.dns_vip_servers) == 2
        : length(local.configured_container_dns_servers) > 0
      )

      error_message = "Unable to determine valid DNS servers for dns03. Ensure NetBox outputs.dns_ips contains distinct dns_vip_a and dns_vip_b values, provide them through dns_ips, or set container_dns_servers when NetBox remote state is disabled."
    }

    precondition {
      condition     = local.container_dns_domain != ""
      error_message = "Unable to determine the dns03 search domain. Set container_dns_domain explicitly or ensure NetBox exports internal_zone."
    }
  }

  tags = [
    "dns",
    "technitium",
    "keepalived",
    "terraform",
    "skynet",
  ]

  cpu {
    cores = var.container_cores
  }

  memory {
    dedicated = var.container_memory
    swap      = var.container_swap
  }

  disk {
    datastore_id = var.container_storage
    size         = var.container_disk_size
  }

  initialization {
    hostname = local.container_hostname

    dns {
      domain  = local.container_dns_domain
      servers = local.container_dns_servers
    }

    ip_config {
      ipv4 {
        address = local.container_ip
        gateway = local.container_gateway
      }
    }

    user_account {
      keys = [
        trimspace(file(pathexpand(var.ssh_public_key_path)))
      ]
    }
  }

  network_interface {
    name   = "eth0"
    bridge = var.container_bridge
  }

  operating_system {
    template_file_id = var.template_file_id
    type             = "ubuntu"
  }

  startup {
    order      = 1
    up_delay   = 10
    down_delay = 10
  }

  wait_for_ip {
    ipv4 = true
  }
}

resource "terraform_data" "dns03_prepare" {
  triggers_replace = [
    proxmox_virtual_environment_container.dns03.id,
  ]

  depends_on = [
    proxmox_virtual_environment_container.dns03,
  ]

  lifecycle {
    precondition {
      condition     = local.pm_ssh_host != ""
      error_message = "Unable to determine the Proxmox SSH host. Set pm_ssh_host explicitly or ensure NetBox contains the target_node management IP."
    }
  }

  connection {
    type  = "ssh"
    host  = local.pm_ssh_host
    user  = var.pm_ssh_username
    port  = var.pm_ssh_port
    agent = true
  }

  provisioner "remote-exec" {
    inline = [
      "set -eux",
      "pct stop ${var.container_vmid} || true",
      "pct set ${var.container_vmid} -features nesting=1",
      "pct set ${var.container_vmid} -onboot 1",
      "modprobe tun || true",
      "grep -q '^lxc.cgroup2.devices.allow: c 10:200 rwm$' /etc/pve/lxc/${var.container_vmid}.conf || echo 'lxc.cgroup2.devices.allow: c 10:200 rwm' >> /etc/pve/lxc/${var.container_vmid}.conf",
      "grep -q '^lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file$' /etc/pve/lxc/${var.container_vmid}.conf || echo 'lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file' >> /etc/pve/lxc/${var.container_vmid}.conf",
      "grep -q '^lxc.cap.drop:$' /etc/pve/lxc/${var.container_vmid}.conf || echo 'lxc.cap.drop:' >> /etc/pve/lxc/${var.container_vmid}.conf",
      "pct start ${var.container_vmid}",
      "sleep 5",
      "pct exec ${var.container_vmid} -- bash -lc 'export DEBIAN_FRONTEND=noninteractive; apt-get update'",
      "pct exec ${var.container_vmid} -- bash -lc 'export DEBIAN_FRONTEND=noninteractive; apt-get install -y ca-certificates curl openssh-server python3 sudo'",
      "pct exec ${var.container_vmid} -- bash -lc 'systemctl enable --now ssh'",
      "pct exec ${var.container_vmid} -- bash -lc 'if ! command -v tailscale >/dev/null 2>&1; then curl -fsSL https://tailscale.com/install.sh | sh; fi'",
      "pct exec ${var.container_vmid} -- bash -lc 'systemctl enable --now tailscaled'",
      "pct exec ${var.container_vmid} -- bash -lc 'tailscale version'",
      "pct config ${var.container_vmid}",
    ]
  }
}

resource "terraform_data" "dns03_tailscale_join" {
  triggers_replace = [
    terraform_data.dns03_prepare.id,
  ]

  depends_on = [
    terraform_data.dns03_prepare,
  ]

  connection {
    type  = "ssh"
    host  = local.pm_ssh_host
    user  = var.pm_ssh_username
    port  = var.pm_ssh_port
    agent = true
  }

  provisioner "file" {
    content     = var.tailscale_auth_key
    destination = "/tmp/ts-authkey-${var.container_vmid}"
  }

  provisioner "remote-exec" {
    inline = [
      "set -eu",
      "chmod 600 /tmp/ts-authkey-${var.container_vmid}",
      "pct push ${var.container_vmid} /tmp/ts-authkey-${var.container_vmid} /root/ts-authkey --perms 600",
      "rm -f /tmp/ts-authkey-${var.container_vmid}",
      "pct exec ${var.container_vmid} -- bash -lc \"tailscale status >/dev/null 2>&1 || tailscale up --authkey=file:/root/ts-authkey --hostname='${local.container_hostname}' --ssh\"",
      "pct exec ${var.container_vmid} -- rm -f /root/ts-authkey",
    ]
  }
}
