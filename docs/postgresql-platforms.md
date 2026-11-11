# PostgreSQL host platforms

The `postgres` role retains the same inventory membership, Patroni/etcd cluster
settings and backup operations. Platform compatibility does not enrol a VM in
an existing cluster or establish database migration readiness. NetBox's
`tags_postgres`, node names, primary addresses and existing host variables remain
authoritative. No service definitions need duplicated OS settings.

| Platform | Installation source and boundary |
| --- | --- |
| Debian 12/13; Ubuntu 22.04/24.04/26.04/26.10 | Existing PGDG APT/deb822 path |
| Fedora 43/44, AMD64 | PGDG stable version, common and extras repositories; DNF4/DNF5 |
| Rocky 9.7+ within 9; 10.1+ within 10, AMD64/ARM64 | PGDG stable repositories for the observed OS minor release; DNF4/DNF5 |

Linux and systemd are required. Atomic/OSTree, other derivatives and older OS
releases are rejected before changes. The default PostgreSQL major remains 18;
the role accepts supported PGDG majors 14–18, subject to the selected repository's
package availability. Fedora 45 is deliberately deferred: PGDG's published
[common package tree](https://download.postgresql.org/pub/repos/yum/common/fedora/)
does not yet provide its stable binary repository. Another Fedora release's
repository is never substituted. PGDG has
[retired its 9.6 and 10.0 repositories](https://www.postgresql.org/about/news/rhel-100-and-96-repositories-are-being-retired-3411/);
archived or testing repositories are not enabled.

RPM installation uses versioned `postgresql<major>`, server and contrib packages,
`patroni`, `patroni-etcd`, `python3-psycopg2` and `etcd`. These follow
[Patroni's RPM installation guidance](https://patroni.readthedocs.io/en/latest/installation.html#installing-on-redhat-derivatives).
PGDG extras is restricted to etcd. Package and repository metadata signatures are
verified, with the PGDG signing-key fingerprint pinned by the role. Repository
root and signing-key overrides support reviewed mirrors. Packages use `present`;
the role does not erase another server, request `latest` or perform a major upgrade.
The server packages are requested with the host architecture and their installed
identities are verified. Fedora's unversioned packages can satisfy or obsolete
bare PGDG package names, but use different binary paths and service units.
On Rocky, prepare the required supported EPEL/CRB availability for Patroni and
Restic dependencies through the host's repository policy; this role does not
enable those repositories implicitly. Restic is available from Fedora and
[EPEL](https://packages.fedoraproject.org/pkgs/restic/restic/).
Use an Ansible interpreter with the distribution DNF, psycopg2 and SELinux
bindings; the role does not modify arbitrary controller/host virtual environments.

## Paths and service ownership

| Resource | APT default | PGDG RPM default |
| --- | --- | --- |
| Server and backup binaries | `/usr/lib/postgresql/<major>/bin` | `/usr/pgsql-<major>/bin` |
| Patroni data | `/var/lib/postgresql/<major>/main` | `/var/lib/pgsql/<major>/data` |
| Patroni configuration | `/etc/patroni/config.yml` | Same; a systemd drop-in selects it |
| Standalone server unit | `postgresql` | `postgresql-<major>` |
| etcd environment | `/etc/default/etcd` | `/etc/etcd/etcd.conf` |

Explicit data, binary and Patroni configuration overrides remain authoritative.
Backups and restore validation consume the same binary directory. Existing
PG_VERSION/binary-major mismatches, changed Patroni data/bin paths, alternate
RPM Patroni configuration and relocated etcd member storage fail before changes.
A running standalone RPM server is rejected before Patroni configuration can
stop or adopt it. Keep its paths and arrange a deliberate ownership/migration procedure.
Changing an override is not a migration command. Debian reset behavior remains;
RPM reset, nuke and reinitialisation tags fail explicitly in this phase.

RPM Patroni uses the packaged service account and unit with only its ExecStart
configuration path overridden; notification, kill and restart policies are kept.
Custom unit fragments, a different effective configuration path, Patroni
environment overrides and an existing `/etc/patroni_env.conf` require explicit
review before adoption. They are rejected before unit/label/service changes,
since they can override the YAML's data and cluster settings.
The etcd package unit consumes its native environment path. The existing
membership flags and `etcd3` DCS configuration remain unchanged. Review etcd
minor-version upgrade/join compatibility and Patroni/PostgreSQL compatibility
before adding a newly packaged node to an existing cluster. Installation does
not upgrade an already installed Patroni/etcd package for you.

SELinux stays in its current mode. The role applies scoped PostgreSQL data and
server-executable contexts on enabled RPM hosts, restores labels without crossing
data mounts, and labels the managed isolated restore-validation work root.
etcd and ordinary configuration files retain distribution default labels. No
booleans, firewall permissions or host-wide policy are loosened. Custom ports,
non-local storage and additional confinement requirements need their own reviewed
policy. Firewalld reachability, SELinux AVCs, real failover and data/restore access
remain live acceptance checks.

## Operation selection and validation

```bash
skynet limit <postgres-host> run postgres install
```

This selects `postgres_install`: repositories and packages only. The existing
`skynet limit <postgres-host> run postgres apt` command remains an alias for the
same platform-selected installation. Neither executes service configuration or
lifecycle tasks, changes membership or runs backups. APT package startup is
suppressed with `policy_rc_d`; normal RPM package presets still apply.
Package installation does not call
initdb or postgresql-setup; Patroni retains the existing bootstrap lifecycle when
its configuration/deploy operation is explicitly selected.

Existing `postgres deploy`, `etcd`, `patroni`, backup and administrative commands
remain. Do not use a broad deploy as an installation test. In Ansible check mode,
platform metadata and existing data/configuration are validated; package and
account-dependent setup is deferred, along with service lifecycle and runtime
verification that requires installation. No secret store, database or cluster API
is contacted by installation/check-mode planning.

Repository fixtures simulate target I/O. Before production use, validate an
isolated guest with the intended existing repository policy: package-only check
and installation, a second converged run, enforcing SELinux, correct unit/config
consumption, database and etcd ownership, narrow network reachability, backup and
isolated restore validation. Cluster bootstrap/join, failover, reset and data
migration each require separate deliberate live validation.

Fedora 44 and Rocky 10.2 AMD64 have passed isolated PGDG 18 installation and
zero-change repeats, enforcing-SELinux single-node etcd/Patroni bootstrap,
admin/monitor roles, exporter queries, logical backup checksums and a restore into a separate test
database. SQL queries through an isolated rootless HAProxy reached the test primary,
and both the primary and restored row remained healthy after reboot. No production
cluster was joined. Multi-node failover, remote Restic credentials/storage and RPM
destructive recovery were not validated by these tests.
