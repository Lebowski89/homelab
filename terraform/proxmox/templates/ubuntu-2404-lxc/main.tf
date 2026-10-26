resource "proxmox_download_file" "ubuntu_lxc_template" {
  content_type = "vztmpl"
  datastore_id = var.template_datastore
  node_name    = var.template_node_name
  file_name    = var.template_file_name
  url          = var.template_url
  overwrite    = false
}
