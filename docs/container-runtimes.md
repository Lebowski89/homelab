# Docker and Podman host installation

`ansible/roles/docker` and `ansible/roles/podman` install hosts independently.
Installation support does not establish application migration or firewall readiness.
The following conventional Linux releases are explicitly accepted (reviewed
2026-11-01); unlisted derivatives, future releases and Atomic/OSTree hosts are rejected.
Both roles require systemd and the matching APT or DNF/DNF5 facts.

| Distribution | Docker CE repository | Podman distribution packages |
| --- | --- | --- |
| Debian | 12 Bookworm, 13 Trixie; Docker Debian repository | 13 Trixie (5.4.2 baseline) |
| Ubuntu | 22.04 Jammy, 24.04 Noble, 26.04 Resolute, 26.10 Stonking; Docker Ubuntu repository | 26.04 and 26.10; enable normal distribution Universe availability beforehand |
| LMDE | 7 only; Docker Debian repository, explicitly `trixie` | 7 only, retaining existing Debian 13 based support |
| Fedora | 43–45; Docker Fedora repository | 43–45, standard repositories |
| Rocky Linux | 9 and 10; Docker **RHEL** repository | 9.7+ within 9, 10.1+ within 10, standard repositories |

Docker's [Debian](https://docs.docker.com/engine/install/debian/),
[Ubuntu](https://docs.docker.com/engine/install/ubuntu/),
[Fedora](https://docs.docker.com/engine/install/fedora/) and
[RHEL](https://docs.docker.com/engine/install/rhel/) instructions define its
package availability. [Rocky's Docker guidance](https://docs.rockylinux.org/gemstones/containers/docker/)
also selects the RHEL repository. LMDE Docker support is a repository-specific
upstream-suite mapping, not an upstream Docker endorsement of derivatives.

[Podman's installation guidance](https://podman.io/docs/installation) describes
using distribution packages. The runtime contract remains **Podman >=5.4.2**,
cgroup v2 and an executable system Quadlet generator. Availability alone on older
releases is insufficient: [Debian 13](https://packages.debian.org/trixie/podman)
ships 5.4.2; [Ubuntu 26.04](https://packages.ubuntu.com/resolute/podman) and
[current Fedora](https://packages.fedoraproject.org/pkgs/podman/podman/) exceed
that floor. Rocky's [9.7](https://download.rockylinux.org/vault/rocky/9.7/AppStream/x86_64/os/Packages/p/)
and [10.1](https://download.rockylinux.org/vault/rocky/10.1/AppStream/x86_64/os/Packages/p/)
repositories provide 5.6.0. Rocky 9.6/10.0's initial Podman 5.4.0 is insufficient;
update the OS through its ordinary maintenance process first. Ubuntu 24.04 and
Debian 12 remain unsupported for this Podman role. No experimental repositories,
backports or OS upgrades are enabled by either role. An installed older Podman
still fails capability validation; `present` deliberately does not upgrade it.

## Installation-only operations

Use the existing NetBox host identity and tags: Docker requires `docker` plus
`docker_install`; Podman accepts `podman` or `podman_install`. The wrapper's
existing role/action mappings select only installation:

```bash
skynet limit <host> check docker install
skynet limit <host> run docker install
skynet limit <host> check podman install
skynet limit <host> run podman install
```

`docker` alone also selects Swarm work; use `docker install` for installation
only. Unraid's `/etc/unraid-version` marker preserves its externally managed
engine even if `docker_install` is assigned accidentally.

Installation selections do not initialise/join Swarm, label nodes, create the
Swarm overlay or central Podman bridge, prune resources, or create application
accounts. Swarm and pruning remain separate Docker operations. `podman_network`
remains the explicit central bridge/DNS operation; application networks and
rootless users/subordinate IDs remain owned by the service adapter.

## Packages, overrides and coexistence

Docker preserves the Ubuntu deb822/keyring setup, architecture mapping, exact
matching legacy-source cleanup and cache refresh after repository changes.
Debian uses that same APT workflow with its own repository. LMDE uses `trixie`
rather than its derivative codename. `docker_repo_suite` can explicitly override
the upstream suite. Repository URL/channel/filename, keyring, prerequisites,
package list and Docker user/group options retain their override precedence.
The default package state is `present`. The previously unused
`docker_install_compose_plugin` flag now controls Compose in the **default**
package list; its default stays true. An explicit `docker_packages` list is
installed as supplied, including explicit version pins. False does not uninstall
an existing Compose plugin. Docker is enabled and started, with no requested
restart on an already running daemon.

RPM hosts use native `yum_repository`, `rpm_key` and `dnf` modules with the
DNF4/DNF5 backend selected from facts, Docker's pinned key fingerprint and package
signature verification. `docker_repo_url`, `docker_repo_channel` and
`docker_repo_filename` also apply on RPM; `docker_rpm_baseurl`,
`docker_rpm_key_url` and `docker_rpm_key_fingerprint` support an explicit mirror.
APT paths and `python3-debian` are absent from the RPM workflow.

Podman retains `podman_install_enable`, `podman_state`, `podman_packages`,
`podman_install_extra_packages` and cache settings. Cache lifetime applies only
to APT; DNF accepts cache refresh without an APT lifetime. Debian-family defaults
retain CNI/slirp compatibility packages and add explicit crun, Netavark and
Aardvark providers. RPM uses crun, Netavark, Aardvark, passt, fuse-overlayfs,
container-selinux, shadow-utils (UID/GID mapping helpers), dbus-broker and
systemd-pam for user sessions. Fedora's [shadow-utils file list](https://packages.fedoraproject.org/pkgs/shadow-utils/shadow-utils/fedora-43.html)
identifies `newuidmap` and `newgidmap`. Fedora's [dbus-broker file list](https://packages.fedoraproject.org/pkgs/dbus-broker/dbus-broker/fedora-43.html)
includes its user service; Rocky 10's [BaseOS package catalog](https://dl.rockylinux.org/pub/rocky/10/BaseOS/x86_64/os/Packages/d/)
supplies dbus-broker rather than a dbus-daemon package. RPM defaults use pasta; installations
needing legacy slirp must explicitly supply its available distribution package.
No API socket or Podman daemon is enabled. Disabling installation still checks
the supplied runtime; removing packages is not a supported runtime-ready outcome.

Preflight package facts reject `podman-docker`, which replaces the Docker CLI.
Docker also rejects distribution Docker/Moby, containerd and runc packages that
conflict with Docker CE/containerd.io. Podman uses crun to coexist with Docker;
installed or explicitly requested runc/containerd alongside containerd.io is rejected. Review dependent
workloads and choose an explicit migration before retrying. The roles never
uninstall the other runtime or enable automatic dependency erasure; package
solvers still arbitrate version/dependency conflicts. SELinux enforcement,
firewalld's existing state and host iptables alternatives are preserved. Host
firewall installation and policy remain a separate provisioning responsibility.
Starting Docker can create Docker's own normal networking/firewall state.

Docker container SELinux confinement requires the daemon's
[`selinux-enabled` setting](https://docs.docker.com/reference/cli/dockerd/),
independently of the host's enforcing state. Installation preserves the existing
daemon configuration. Before accepting Docker storage-label tests, verify that
`docker info` advertises SELinux and the container has a SELinux process label.
Enabling daemon support requires a separately reviewed configuration and restart;
a successful bind-mount write alone does not verify confinement.

Package coexistence also needs a compatible forwarding policy. Docker can set
the host's [default forwarding policy to DROP](https://docs.docker.com/engine/network/packet-filtering-firewalls/).
With bridge filtering enabled, this can block rootful Podman peer traffic even
when container DNS resolves correctly. Validate peer HTTP/TCP traffic separately
from DNS, and test rootful and rootless networks independently. Any required
forwarding permission needs a scoped ownership decision; neither installer changes
the global forwarding policy or adds blanket permissions to make tests pass.

## Rocky 10 kernel networking prerequisite

Minimal/cloud images can omit `xt_addrtype`, which Docker's bridge/NAT setup
requires. Before configuring Docker repositories or starting the daemon, the
role checks module availability and, if missing, installs
`kernel-modules-extra-uname-r = <running-kernel-release>` from Rocky's normal
repositories. It verifies the matching installed package and module before
continuing. The exact capability also handles a newer supplement already being
installed: that package cannot supply modules for the running kernel.

Check mode reports the missing supplement and defers installation/verification.
If the exact provider is unavailable or verification fails, installation stops
with an OS maintenance explanation. Inspect the package files/module index if
it is installed; otherwise arrange maintenance and a reboot into a kernel with
matching packages available. The role does not upgrade kernels, reboot or
change firewall backends to work around missing modules.

## Check mode and remaining validation

Check mode validates platform, options, installed-package conflicts and Podman's
host cgroup v2 requirement, then reports the planned package/repository state.
It skips repository/key/cache/package operations, so fresh hosts need neither
repository metadata nor the as-yet-uninstalled python3-debian dependency.
Docker service actions are deferred. Podman's read-only version probe still runs:
an existing runtime must pass version and generator checks; an absent runtime
explicitly defers those checks until installation. This preview does not resolve
a package transaction or prove that a runtime is upgraded, running or usable.
Disabling Podman installation retains the same existing-runtime checks. Normal runs verify the version and executable system generator at
`/usr/lib/systemd/system-generators/` or `/lib/systemd/system-generators/`.

Runtime installation remains separate from Fedora/Rocky application readiness:

- The [service firewall](service-firewall.md#fedora-and-rocky-prerequisites)
  accepts conventional Fedora 43–45 and Rocky 10 with explicit coexistence
  prerequisites. Enforcement, firewalld reload and enforcing SELinux still need
  isolated live validation. Native listener ACLs remain deferred.
- Application bind mounts support an [explicit SELinux storage policy](service-storage-selinux.md).
  Existing services still require a deliberate storage and ownership review;
  externally managed/shared data and protected ingress are not migrated automatically.
- The [central rootful bridge/DNS owner](podman-services.md#mgt-shared-bridge-and-bootstrap)
  validates RPM platforms, local rootful Netavark and existing network compatibility,
  and protects running bridge users during DNS port changes. Actual DNS traffic,
  SELinux domains and Netavark/firewalld integration still need isolated validation.
- Overlay networking, pruning and fresh-host package installation still need
  isolated validation. The existing Rocky VM's installation and drained-manager
  join have passed live execution and second-run convergence checks.

## Optional Rocky manager test

Rocky is a compatibility-test host and has no Swarm tags in the OpenTofu NetBox
source by default. Keep `mgt` as `docker_swarm_primary_manager`. To deliberately
repeat the manager test, assign Rocky the NetBox tags `swarm` and `swarm-manager`
(slugs `swarm` and `swarm_manager`), then use:

```bash
skynet limit rocky check docker swarm-join
skynet limit rocky run docker swarm-join
```

Rocky's host variables set `docker_swarm_join_availability: drain` so joining
cannot automatically schedule global services or migrate applications onto it.
This setting applies at join time only; it does not change an existing node's
scheduling. Other nodes retain the existing `active` join default. Check mode
inspects membership without fetching tokens. Execution rejects conflicting
membership or roles rather than replacing an existing cluster.

After testing, remove both Swarm tags from live NetBox and any matching source
entries before future provisioning. Through a healthy surviving manager, demote
the drained, task-free Rocky node; have Rocky leave without `--force`; then remove
its inactive node record from the surviving manager. Runtime installation is
retained. Swarm enrollment does not need to remain enabled for compatibility tests.

A two-manager Swarm requires both managers for quorum and tolerates no manager
failure. Plan a third manager for one-manager failure tolerance. Installation
and manager membership do not establish Rocky application/firewall readiness.
