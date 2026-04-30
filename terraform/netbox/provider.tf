provider "netbox" {
  server_url           = var.netbox_server_url
  api_token            = var.netbox_api_token
  allow_insecure_https = var.netbox_allow_insecure_https
  request_timeout      = var.netbox_request_timeout
  skip_version_check   = var.netbox_skip_version_check
}