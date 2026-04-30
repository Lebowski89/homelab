provider "netbox" {
  server_url           = var.netbox_server_url
  api_token            = var.netbox_api_token
  allow_insecure_https = var.netbox_allow_insecure_https
}