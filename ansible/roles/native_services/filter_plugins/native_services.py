"""Validate the four native application contracts and preserve host overrides."""

from collections.abc import Mapping
from pathlib import PurePosixPath

from ansible.errors import AnsibleFilterError
from ansible.template import trust_as_template

PREFIXES = {"alloy": "alloy_native_", "node_exporter": "node_exporter_", "keepalived": "keepalived_", "technitium": "technitium_native_"}
FIELDS = {
    "alloy": {
        "service_name",
        "user",
        "repo_suite",
        "config_path",
        "loki_url",
        "keyring_file",
        "keyring_dir",
        "journal_groups",
        "repo_filename",
        "repo_url",
        "packages",
        "config_dir",
        "group",
    },
    "node_exporter": {
        "disabled_collectors",
        "user",
        "install_dir",
        "textfile_dir",
        "listen_address",
        "arch",
        "archive_name",
        "extra_args",
        "archive_path",
        "release_url",
        "download_url",
        "extract_dir",
        "group",
        "version",
        "enabled_collectors",
        "checksum",
    },
    "keepalived": {
        "host_interface",
        "dns_check_timeout",
        "script_interval",
        "script_fall",
        "dns_check_server",
        "check_script_path",
        "config_path",
        "dns_check_query",
        "dns_check_tries",
        "dns_check_type",
        "script_weight",
        "instances",
        "host_ip",
        "host_mode",
        "dns_group",
        "script_timeout",
        "script_rise",
    },
    "technitium": {
        "disable_resolved_stub",
        "install_script_url",
        "install_marker",
        "web_port",
        "resolved_dns_servers",
        "install_script_path",
        "service_name",
        "dns_port",
        "config_dir",
    },
}
NODE_DERIVED = {
    "release_url": "https://github.com/prometheus/node_exporter/releases/download/v{{ node_exporter_version }}",
    "archive_name": "node_exporter-{{ node_exporter_version }}.linux-{{ node_exporter_arch }}.tar.gz",
    "download_url": "{{ node_exporter_release_url }}/{{ node_exporter_archive_name }}",
    "archive_path": "/tmp/{{ node_exporter_archive_name }}",
    "extract_dir": "/tmp/node_exporter-{{ node_exporter_version }}.linux-{{ node_exporter_arch }}",
    "checksum": "sha256:{{ node_exporter_release_url }}/sha256sums.txt",
}


def native_services_inputs(native, inventory):
    if not isinstance(native, Mapping) or native.get("application") not in FIELDS or not isinstance(native.get("config"), Mapping):
        raise AnsibleFilterError("native needs a supported application and config mapping")
    app = native["application"]
    config = dict(native["config"])
    unknown = set(config) - FIELDS[app]
    if unknown:
        raise AnsibleFilterError(f"native.config has unsupported {app} settings: {', '.join(sorted(unknown))}")
    if app == "node_exporter":
        config = {**{key: trust_as_template(value) for key, value in NODE_DERIVED.items()}, **config}
    for key in FIELDS[app]:
        variable = PREFIXES[app] + key
        if variable in inventory:
            config[key] = inventory[variable]
    missing = FIELDS[app] - set(config)
    if missing:
        raise AnsibleFilterError(f"native.config is missing {app} settings: {', '.join(sorted(missing))}")
    return config


def native_services_normalize(native):
    app = native["application"]
    config = native_services_inputs(native, {})
    policy = native.get("update_policy")
    policies = {"node_exporter": {"pinned"}, "technitium": {"present"}, "alloy": {"present", "latest"}, "keepalived": {"present", "latest"}}
    if policy not in policies[app]:
        raise AnsibleFilterError(f"native.update_policy for {app} must be one of: {', '.join(sorted(policies[app]))}")
    lists = {"packages", "journal_groups", "enabled_collectors", "disabled_collectors", "extra_args", "resolved_dns_servers"}
    integers = {
        "web_port",
        "dns_port",
        "dns_check_timeout",
        "dns_check_tries",
        "script_interval",
        "script_timeout",
        "script_fall",
        "script_rise",
        "script_weight",
    }
    for key, value in config.items():
        if key in lists:
            if not isinstance(value, list) or any(not isinstance(item, str) or "\n" in item for item in value):
                raise AnsibleFilterError(f"native.config.{key} must be a list of strings")
        elif key in integers:
            if not isinstance(value, int) or isinstance(value, bool) or (key != "script_weight" and value <= 0):
                raise AnsibleFilterError(f"native.config.{key} must be an integer in its supported range")
            if key in {"web_port", "dns_port"} and value > 65535:
                raise AnsibleFilterError(f"native.config.{key} must be a valid port")
        elif key == "disable_resolved_stub":
            if type(value) is not bool:
                raise AnsibleFilterError("native.config.disable_resolved_stub must be a boolean")
        elif key == "instances":
            if not isinstance(value, Mapping):
                raise AnsibleFilterError("native.config.instances must be a mapping")
        elif not isinstance(value, str) or "\n" in value or (not value and key != "checksum"):
            raise AnsibleFilterError(f"native.config.{key} must be a non-empty string")
        if (
            key.endswith(("_path", "_dir", "_marker", "_file"))
            and key != "repo_filename"
            and (not isinstance(value, str) or not value.startswith("/") or ".." in PurePosixPath(value).parts or value == "/")
        ):
            raise AnsibleFilterError(f"native.config.{key} must be an absolute non-root path without traversal")
    if app == "alloy" and not config["packages"]:
        raise AnsibleFilterError("native.config.packages must not be empty")
    return config


class FilterModule:
    def filters(self):
        return {"native_services_normalize": native_services_normalize}
