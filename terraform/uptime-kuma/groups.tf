locals {
  groups = {
    apps = {
      name = "Apps"
    }

    arrs = {
      name       = "ARRs"
      parent_key = "apps"
    }

    gaming = {
      name       = "Gaming"
      parent_key = "apps"
    }

    infrastructure = {
      name = "Infrastructure"
    }

    media = {
      name       = "Media"
      parent_key = "apps"
    }

    monitoring = {
      name       = "Monitoring"
      parent_key = "apps"
    }

    network = {
      name       = "Network"
      parent_key = "apps"
    }

    networking = {
      name = "Networking"
    }

    plex = {
      name       = "Plex"
      parent_key = "apps"
    }

    torrents = {
      name       = "Torrents"
      parent_key = "apps"
    }

    usenet = {
      name       = "Usenet"
      parent_key = "apps"
    }

    utilities = {
      name       = "Utilities"
      parent_key = "apps"
    }
  }
}

locals {
  root_groups = {
    for key, group in local.groups :
    key => group
    if !contains(keys(group), "parent_key")
  }

  child_groups = {
    for key, group in local.groups :
    key => group
    if contains(keys(group), "parent_key")
  }
}

resource "uptimekuma_monitor_group" "root" {
  for_each = local.root_groups

  name = each.value.name
}

resource "uptimekuma_monitor_group" "child" {
  for_each = local.child_groups

  name   = each.value.name
  parent = uptimekuma_monitor_group.root[each.value.parent_key].id
}
