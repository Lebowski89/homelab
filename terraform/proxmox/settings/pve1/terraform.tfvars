pm_api_url      = "https://192.168.80.80:8006/"
pm_tls_insecure = true

target_node  = "pve1"
local_domain = "home.arpa"

node_management_ip = "192.168.80.80"

network_vmbr0_name      = "vmbr0"
network_vmbr0_address   = "192.168.80.80/24"
network_vmbr0_gateway   = "192.168.80.1"
network_vmbr0_ports     = ["enp5s0"]
network_vmbr0_autostart = true

network_vmbr1_name      = "vmbr1"
network_vmbr1_ports     = ["enp10s0f2np2"]
network_vmbr1_autostart = true

dns_domain  = "home.arpa"
dns_servers = ["192.168.80.48", "192.168.80.59"]

timezone = "Australia/Melbourne"