locals {
  netbox_dns_ips       = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.dns_ips, {}) : {}
  netbox_internal_zone = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.internal_zone, "") : ""

  dns_ips = merge(
    var.dns_ips,
    local.netbox_dns_ips,
  )

  container_dns_servers = (var.enable_netbox_remote_state || length(var.container_dns_servers) == 0) ? [
    local.dns_ips["dns_vip_a"],
    local.dns_ips["dns_vip_b"],
  ] : var.container_dns_servers

  container_dns_domain = (var.enable_netbox_remote_state || trimspace(var.container_dns_domain) == "") ? local.netbox_internal_zone : var.container_dns_domain
}

resource "proxmox_virtual_environment_container" "dns03" {
  node_name   = var.target_node
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
    hostname = var.container_hostname

    dns {
      domain  = local.container_dns_domain
      servers = local.container_dns_servers
    }

    ip_config {
      ipv4 {
        address = var.container_ip
        gateway = var.container_gateway
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

  connection {
    type  = "ssh"
    host  = var.pm_ssh_host
    user  = var.pm_ssh_username
    port  = 22
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
    host  = var.pm_ssh_host
    user  = var.pm_ssh_username
    port  = 22
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
      "pct exec ${var.container_vmid} -- bash -lc \"tailscale status >/dev/null 2>&1 || tailscale up --authkey=file:/root/ts-authkey --hostname='${var.container_hostname}' --ssh\"",
      "pct exec ${var.container_vmid} -- rm -f /root/ts-authkey",
    ]
  }
}
