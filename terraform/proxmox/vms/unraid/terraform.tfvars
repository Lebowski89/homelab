pm_api_url      = "https://192.168.80.80:8006/"
pm_tls_insecure = true

target_node = "pve1"

unraid_vmid      = 100
unraid_name      = "UnRaid"
unraid_cores     = 8
unraid_sockets   = 1
unraid_cpu_flags = ["+pcid"]
unraid_memory    = 32045

unraid_machine    = "q35"
unraid_bios       = "seabios"
unraid_boot_order = ["usb0"]
unraid_scsihw     = "virtio-scsi-single"
unraid_qemu_os    = "l26"
unraid_vga_type   = "qxl"

unraid_uuid = "ebfa68e3-e312-42de-8c08-a3c400754edb"

unraid_boot_mapping  = "UnRaid-Boot"
unraid_hba_mapping   = "UnRaid-HBA"
unraid_nic_mapping   = "UnRaid-NIC"
unraid_cache_mapping = "UnRaid-Cache"

unraid_kvm_arguments = "-device amd-iommu"