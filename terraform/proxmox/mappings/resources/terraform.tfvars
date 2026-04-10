pm_api_url      = "https://192.168.80.80:8006/"
pm_tls_insecure = true

target_node = "pve1"

unraid_hba_mapping_name      = "UnRaid-HBA"
unraid_nic_mapping_name      = "UnRaid-NIC"
unraid_cache_mapping_name    = "UnRaid-Cache"
unraid_boot_usb_mapping_name = "UnRaid-Boot"

unraid_hba_map_id      = "9005:028c"
unraid_hba_map_path    = "0000:04:00.0"
unraid_hba_iommu_group = 22
unraid_hba_subsystem_id   = "9005:0501"

unraid_nic_map_id      = "8086:1572"
unraid_nic_map_path    = "0000:0a:00.1"
unraid_nic_iommu_group = 26
unraid_nic_subsystem_id   = "8086:0000"

unraid_cache_map_id      = "1bb1:5018"
unraid_cache_map_path    = "0000:01:00.0"
unraid_cache_iommu_group = 14
unraid_cache_subsystem_id = "1bb1:5018"

unraid_boot_usb_map_id   = "18a5:0243"
unraid_boot_usb_map_path = "6-3"