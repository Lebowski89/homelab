# Shared system baseline

The `system` role replaces `ubuntu` and incorporates the optional `resolved`
feature. It supports conventional Debian/Ubuntu with APT, Rocky Linux 10 with
DNF, and Fedora with DNF or DNF5. Selection uses the target host's facts;
unsupported distributions, package managers and Atomic/OSTree hosts fail before
baseline changes. SSH, Python 3 and sudo must already work.

OpenTofu/cloud-init retains interface, address, route and DNS configuration for
VMs. The role neither renders Netplan nor manages NetworkManager profiles, and leaves
existing Netplan files and cloud-init networking disablement untouched.
Workstation development tools, repositories and credentials remain in
`workstation`; runtimes and applications retain their own dependencies.

## Operations

After updating the checkout, refresh the installed wrapper with
`skynet run workstation skynet` (or the independent
[workstation bootstrap](cheat_sheets/workstation-setup.md) when NetBox is unavailable).
Confirm the new mapping with `skynet targets` before using these commands.

```bash
skynet limit <host> check system packages
skynet limit <host> run system packages
skynet limit <host> run system sysctl
skynet limit <host> run system limits
skynet limit <host> check system updates
skynet limit <host> run system updates
```

`system` (the default action) runs the baseline and enabled features, plus narrow
legacy cleanup. It never selects maintenance. `system updates` upgrades installed
packages; dependency removal and APT cache cleanup require explicit
`system_updates_autoremove: true` / `system_updates_autoclean: true` inputs.
Use `skynet targets` and `skynet help` for discovery, rather than service
`update all` for OS maintenance.

Unfiltered playbook runs preserve the previous Ubuntu host scope. Other supported
hosts can opt in with `system_enabled: true` in host/group inventory variables.
Targeted system runs select the requested hosts regardless of distribution;
platform validation then rejects unsupported hosts. Use an explicit host limit.
`system_enabled: false` excludes a host even from targeted runs.

## Static bootstrap without NetBox

Use the workstation's SSH agent and the guest's LAN address. Confirm the guest's
SSH host key through your normal trusted channel. For example, create an operator
inventory outside the repository (substitute the verified address):

```yaml
all:
  hosts:
    rocky:
      ansible_host: <guest-lan-ip>
      ansible_user: rocky
      # Other supported hosts can use their own login and feature flags here.
```

Then run from the checkout:

```bash
export INVENTORY=/absolute/path/to/system-inventory.yml
export ANSIBLE_CONFIG="$PWD/ansible/bootstrap.cfg"
skynet limit rocky check system packages
skynet limit rocky run system packages
# Inspect the other features before selecting the complete baseline:
skynet limit rocky check system
unset INVENTORY ANSIBLE_CONFIG  # Restore normal discovery for later operations.
```

For an overridden inventory, the system wrapper uses `bootstrap.cfg` by default
(unless `ANSIBLE_CONFIG` is explicitly overridden) and sets `system_hosts=all`.
This configuration disables NetBox plugins and automatic application group-vars,
including Vault loading. Put required feature overrides directly in the static
inventory or supply a private vars file through direct Ansible. Existing
host_vars remain available; no NetBox/controller/storage topology is required.
A direct equivalent is:

```bash
ANSIBLE_CONFIG=ansible/bootstrap.cfg ansible-playbook \
  -i /absolute/path/to/system-inventory.yml ansible/playbook.yml \
  -e system_hosts=all --limit rocky --tags system_packages --check --diff
```

The role does not configure SSH credentials or sudo authentication. Supply the
normal become password file or `--ask-become-pass` when needed. Independent
[workstation bootstrap](cheat_sheets/workstation-setup.md) is unchanged.

## Optional features and compatibility

- `system_packages_enabled`, `system_sysctl_enabled`, `system_limits_enabled`
  and `system_guest_agent_enabled` default to true. `system_extra_packages`
  adds native package names. Baseline packages are installed with `state: present`.
  DNF baseline packages do not request full `curl`, preserving `curl-minimal`;
  installers retain responsibility for their own curl requirements.
- QEMU Guest Agent is installed, enabled and started only for KVM/QEMU guests.
  Check mode does not start it. This does not grant `guest-exec` permission or
  bypass Rocky SELinux restrictions; Tailscale's explicit SSH transport remains
  available for those guests.
- `system_swap_enabled` defaults to false. PostgreSQL inventory explicitly enables
  its existing 2048 MiB `/swapfile`. Existing active or persistent alternate swap
  (including zram) is preserved. Existing unrelated/unformatted files are refused;
  a correctly sized formatted file can recover after interruption without being
  reformatted. Check mode only discovers swap and reports the proposed work.
  Interrupted allocation/formatting failures require operator inspection.
- The sysctl and PAM files retain their previous role-owned paths
  (`99-ubuntu-tuning.conf` and `99-ubuntu.conf`) to avoid competing configuration.
  Shared kernel settings and the nofile login limit remain configurable through
  `system_sysctl_settings` and `system_limits`. Blanket unlimited login memlock,
  obsolete `tcp_adv_win_scale`, `fs.file-max` cleanup and universal NIC queue
  tuning are retired from those files. Removing persisted settings does not reset
  current kernel/session values. Service and user-manager limits belong in their
  owning systemd units. No separate `netdev_budget_usecs` hook remains; explicit
  host tuning belongs in `system_sysctl_settings`.
- Git remains a baseline utility for the existing Hugo theme workflow. Retired
  profiles do not cause installed packages to be uninstalled.


`system_resolved_enabled` defaults to false in the role; the ordinary repository
inventory preserves its existing Ubuntu enablement. `system resolved` is an
optional Debian/Ubuntu feature for NSS split DNS/MagicDNS and resolved lifecycle.
It does not force resolved onto DNF hosts. `system_resolved_disable_stub` remains
explicitly scoped to `tags_dns` so Technitium can bind port 53; only this opt-in
also defaults `system_resolved_manage_resolv_conf` to true. Ordinary baseline
provisioning does not repoint resolv.conf. Technitium's native application-owned
resolver drop-in remains unchanged. Existing `resolved` and `systemd-resolved`
wrapper aliases select this same feature; Ubuntu command/tag aliases are retired,
including network/netplan commands. Old `ubuntu_*` / `resolved_*` private variable
overrides must be re-expressed using the retained `system_*` inputs. Package
profiles have been replaced by native baseline lists and `system_extra_packages`.

PostgreSQL owns ACL backup prerequisites and installs them before backup setup or
execution under the existing PostgreSQL operation tags. Empty runtime package
profiles, workstation Python/build profiles, UFW and vnStat provisioning, implicit
upgrades and global package cleanup have been removed from the baseline.

## Selected NIC settings

X710-DA4 PFs passed through to VMs can use the same `i40e` workaround as physical
hosts. In that host's ordinary `ansible/host_vars/<host>.yml`, replace the
placeholders below with interface names verified **inside that host**:

```yaml
system_nic_interfaces:
  "<verified-x710-port-0>":
    disable_fw_lldp: true
  "<verified-x710-port-1>":
    disable_fw_lldp: true
  "<verified-forwarding-interface>":
    udp_gro_forwarding: true
# Only when replacing the exact former Ubuntu role's script/unit:
# system_nic_migrate_legacy: true
```

Both settings default off; `system_nic_interfaces` defaults to `{}`. A port may
request either setting or both. Remove its mapping entry to stop managing it;
false does not undo previously applied firmware/offload state. No actual host's
interfaces are selected by this change because no per-port override was present.

- LLDP disablement requires a real Intel X710 PCI PF, `i40e`, agreement between
  sysfs and the driver's PCI identity, and the `disable-fw-lldp` private flag.
  Device identity is checked using the selected bus only, with `lspci -nn` and
  the distribution's PCI IDs database. If the database cannot identify X710,
  validation fails rather than guessing. A VF (`iavf`/`i40evf` or `physfn`) and
  VirtIO cannot own firmware LLDP. For SR-IOV, configure the PF owner instead.
- UDP GRO forwarding is independent: it requests `rx-udp-gro-forwarding on` and
  `rx-gro-list off` only where both features are available. A feature fixed in
  the wrong state fails validation. This is a
  [Tailscale forwarding optimisation](https://tailscale.com/docs/reference/best-practices/performance#linux-optimizations-for-subnet-routers-and-exit-nodes),
  especially for subnet routers/exit nodes; installing Tailscale does not enable it.
- [Intel's current i40e documentation](https://github.com/intel/ethernet-linux-i40e)
  specifies `--set-priv-flags` for firmware LLDP, separately from `-K` offloads.
  The script reads back `--show-priv-flags` / `-k` after application. Intel
  describes per-port persistence, but driver/NVM/HII differences still require
  checking the actual state after reboot; no firmware or driver update is performed.

Use `skynet limit <host> check system nic` to preview inputs/files, then
`skynet limit <host> run system nic` only when live NIC changes are authorized.
APT/DNF installs `ethtool` and `pciutils`, using the target's backend (including
DNF5). Check mode does not execute hardware inspection or change services/settings;
capability verification requires the tools and a later authorized run. During that
run all selected interfaces are inspected before any NIC settings change.

Persistence uses one `skynet-system-nic@<escaped-interface>.service` per port,
ordered after its device exists and enabled for boot. Device/job and execution
waits are bounded. A changed managed script/unit/dispatcher or detected drift
causes explicit reapplication. The oneshot returns inactive on success, allowing
future starts; successful application means verified ethtool state, not an active
service flag. Removed selections are disabled without resetting current hardware.
A NetworkManager `up`/`reapply` dispatcher schedules the **same unit** for the
selected port. It does not install/restart NetworkManager or alter profiles,
addresses, routes, DNS or cloud-init. With a non-NetworkManager renderer, an
in-session driver/device reset requires an explicit reapplication and verification;
boot application is still device-bound.

Legacy `/usr/local/sbin/nic-tuning.sh` and `nic-tuning.service` are preserved by
default, including their X710 intent. A new selection refuses to coexist with
these artifacts until `system_nic_migrate_legacy: true` explicitly requests a
transition. Only the exact former generated script/unit pair is stopped, disabled
and removed, after successful new hardware preflight. Modified/administrator
versions block transition and remain untouched. `system cleanup` alone cannot
retire a legacy tuner without that preflight. Review other administrator-provided
ethtool/NM/networkd hooks before enabling this feature to avoid competing writers.

Read-only checks before selection and again after an authorized reboot (substitute
one verified interface and repeat for each port):

```bash
interface='<verified-interface>'
sudo ethtool -i "$interface"
readlink -f "/sys/class/net/$interface/device"
test ! -e "/sys/class/net/$interface/device/physfn"  # Expected for a PF.
sudo lspci -D -s '<bus-info-from-ethtool>' -nn
sudo ethtool --show-priv-flags "$interface"  # disable-fw-lldp: on, if selected.
sudo ethtool -k "$interface"               # GRO forwarding: on; GRO list: off, if selected.
unit=$(systemd-escape --template=skynet-system-nic@.service -- "$interface")
systemctl show "$unit" -p Result -p ExecMainStatus
journalctl -b -u "$unit" --no-pager
```

Confirm `Result=success` / `ExecMainStatus=0` together with the actual selected
ethtool values. NetworkManager activation requests are asynchronous, so inspect
the unit journal and read-back state after reactivation as well.

## Rocky migration follow-up

Validate an isolated guest with check mode first, then explicitly authorize and
inspect package/service changes, resolver behavior and a rerun. Repository tests
mock host operations and cannot prove live package availability or kernel support.
The production `podman` role still permits only Ubuntu 26.04+ or LMDE 7 with
systemd; its DNF/runtime support is a separate migration. The mgt firewall policy
explicitly requires Ubuntu 26.04; native Alloy, Technitium and Keepalived also
remain Debian-family only. These owners need separate Rocky preparation.
Do not use a full homelab deployment as Rocky's baseline test or change SELinux/firewall/networking to work around these limits.
