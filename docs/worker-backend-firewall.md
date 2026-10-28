# Worker backend policy

Canonical implementation ownership: [service_firewall](service-firewall.md).
Installed paths and operator inputs remain compatible; no reinstall is needed for the source reorganisation.

This policy protects inventory worker host publications for mgt callers. It is
independent of the [mgt policy](mgt-firewall.md); neither installation promotes
application acknowledgements or proves live enforcement. Per-batch migration and
acceptance histories are retained outside Git under `/opt/ansible/migration/`.
Keep verified policy and unchanged acceptance evidence; collect fresh source,
listener, route and counter proof for changed paths. No application deployment,
secret lookup or dependency installation is implied by policy-only operations.
Rocky Linux and consolidated host firewall design remain separate work.

## Scope and ownership

The controller action uses the canonical base-plus-target merger and templates
only value-free endpoint metadata. Physical placement comes from `deploy.hosts`,
not the Swarm manager that dispatches a stack. The controller/storage groups and
`services_plex_host` use the existing NetBox inventory contract; `local_ip` is
NetBox's primary address, which may differ from the Tailscale `ansible_host`.

Services requiring `operational_requirements.acl: [worker_backends]` contribute
host-mode TCP `web_backend`/`probe`/`metrics` ports and any other publication in the
reserved migration allocation 22601–22623. Known backend declarations outside
that allocation, ingress/UDP publications, inconsistent Traefik placement,
unknown workers and duplicate host ports fail validation. Batch tags do not
participate. The current effective catalog yields:

| Worker | Publications | Intended mgt callers |
| --- | --- | --- |
| Unraid | 22601–22618, 22620–22623 | Traefik to HTTP backends; Prometheus to blackbox-exporter 22622 and worker HAProxy metrics relay 22623 |
| Plex | Tautulli 22619→8181; worker HAProxy 22623→8405 | Traefik for Tautulli; mgt Prometheus for metrics |

The explicit global Swarm HAProxy worker target contributes 22623 on both
inventory workers. Multi-host protected declarations must name a nonempty,
unique worker set and use Docker global Swarm mode. Unknown/controller hosts,
non-global lists and duplicate publications fail closed. The shared worker
source contract remains an exact observed mgt address, never a remote UID or
subnet allowance. The table describes canonical declarations; confirm actual
listener and installed-policy continuity before changing paths. Install a scoped
policy extension before publishing a new endpoint, prove the intended runtime
source, and retain the matching scoped rollback. Do not replay an old relay
rollout merely because its migration history is no longer in the repository.

These are direct backend ports. Client URLs remain internal HTTPS on mgt.
SSH, Swarm, DNS, Plex/media, database and other publications retain existing
policy. The role rejects an empty worker policy rather than silently installing
an ineffective restriction. When retiring the last backend, explicitly remove
this temporary policy before removing its inventory identity.

The helper owns only `SKY-WBACK-PRE` in mangle, `SKY-WBACK-IN` and `SKY-WBACK-FWD`
in filter, and exact jumps marked `skynet-worker-backends`. Unmarked collisions
or foreign references cause refusal. It never flushes a built-in/Docker/Tailscale
chain, changes policies, switches backends or disables Docker's firewall.

A position-one mangle PREROUTING jump drops unauthorized TCP destined to a local
host address before destination NAT and filter-table accepts. `addrtype LOCAL`
covers secondary LAN, Tailscale, link-local and global IPv6 addresses, including
new addresses before reconciliation. INPUT and FORWARD/DOCKER-USER jumps are
also first; after DNAT, conntrack matches the **original destination address and
port**, rather than the container port. All current interface addresses are
read locally to populate these post-DNAT matches, with inventory `local_ip`
included during early boot. IPv4 and IPv6 are mandatory; IPv6 remote sources
are denied unless an exact verified IPv6 mgt source is declared. Missing tools
or unexpected backends fail rather than leave one family unprotected.

The pre-DNAT gate returns verified mgt sources to subsequent hooks. Filter
rules explicitly accept those exact sources only for protected local/original
destination endpoints; they do not allow a subnet or unrelated ports. Loopback
ingress and conntrack reply-direction traffic return to existing policy;
there is no established original-direction bypass. Unrelated traffic returns. Application database or
media connections whose reply destination happens to be a protected port are
preserved. Remote host-network containers are remote callers too. Restricting
unpublished overlay/container-address access is outside this host-publication
policy.

Updates use `iptables-restore --noflush` transactions touching only owned
chains/jumps. Both families are syntax-tested before either is applied; each
table transaction is atomic, but the two families/tables are not one atomic
transaction. A failed application is not successful acceptance. Repeated apply,
audit and removal preserve unrelated rules and are idempotent.

## Source preflight and operator inputs

Before exposing the new worker listeners, observe traffic from the **currently
running intended mgt callers** at the worker and record the runtime/context of
each observation. Podman Traefik and Prometheus are not deployed yet, so their
future egress sources cannot be observed at this stage. The observed host route prefers
192.168.80.48, but mgt also has .53; neither a route lookup nor NetBox's primary
IP proves the source emitted by Docker, rootless Podman/pasta or Tailscale.
The default candidate is mgt's inventory `local_ip`. Override it only with exact
mgt addresses actually observed on that worker; never use the LAN subnet.

Before cutover, probes from an existing Docker Traefik/Prometheus container, if
running and equipped with a suitable client, can establish that container's
current source. A host-native probe establishes only the host-native source;
another already running rootless application establishes only its own account
and network context. Neither proves the future Traefik/Prometheus Podman source.
Account-only preparation creates no application container and provides no such
egress observation. Use an existing approved worker listener for these probes
when the new backend publication is not running; adjust the capture port below
to that listener. Record the source from the actual worker-side packet headers.
Normal requests through the existing Traefik route and existing Prometheus
scrapes can also produce traffic to capture, without needing a client binary
inside those containers.

On the worker, capture packet headers only (do not use `-A`/`-X` or capture
application payloads):

```bash
# Before cutover, use an existing safe listener at this worker to observe egress;
# repeat on the actual backend port after it is running. Denied SYNs are visible.
sudo tcpdump -n -i any 'tcp dst port 22619 and tcp[tcpflags] & tcp-syn != 0'
# On Unraid, use the relevant 226xx backend, including 22622 for Prometheus.
```

**Once the Podman containers are deployed and running**, repeat the observations
from Traefik's and Prometheus's actual container network contexts. The dedicated
accounts have nologin shells; `sudo -iu` is unsuitable. Execute Podman directly
as the account, with its NSS-recorded home and UID-derived runtime/bus paths,
as the adapter does. These are operator instructions for that later stage,
not commands that can test the undeployed containers now. Substitute the actual
container name from its Quadlet and the worker's inventory address:

```bash
probe_uid=$(id -u podman-traefik)
probe_home=$(getent passwd podman-traefik | cut -d: -f6)
test -n "$probe_home"
sudo -u podman-traefik -- env HOME="$probe_home" \
  XDG_RUNTIME_DIR="/run/user/$probe_uid" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$probe_uid/bus" \
  /usr/bin/podman exec <traefik-container> \
  curl --noproxy '*' --connect-timeout 3 --max-time 5 \
  -o /dev/null -w '%{http_code}\n' http://<plex-local_ip>:22619/

probe_uid=$(id -u podman-prometheus)
probe_home=$(getent passwd podman-prometheus | cut -d: -f6)
test -n "$probe_home"
sudo -u podman-prometheus -- env HOME="$probe_home" \
  XDG_RUNTIME_DIR="/run/user/$probe_uid" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$probe_uid/bus" \
  /usr/bin/podman exec <prometheus-container> \
  wget -q -O /dev/null http://<unraid-local_ip>:22622/metrics
```

Images may lack these clients. Capture the traffic from a normal proxy request
or scheduled scrape, or use another **already available** client in that same
network context and document it; a shell on mgt is not equivalent evidence.
Use an existing approved listener if the new backend has not yet been published;
do not expose the backend just to discover a source. Repeat the observations
for all necessary paths and retain evidence privately. If no equivalent safe
probe is available, leave verification for that caller pending. Keep
`worker_backend_firewall_sources_verified` false when the intended current
caller source has not been observed; check-mode planning remains possible.
Verification for a currently running Docker caller covers that recorded phase
only. Repeat source and allow/deny checks for both Podman containers once they
run, before continuing their cutover. If a new source differs, capture its SYNs
at the worker, then have the operator explicitly review/update the exact source
inputs and reapply/audit the policy. Do not widen the allow list speculatively.

Create a separate private input file for each worker; keep acknowledgements and
real credentials out of this repository. Example **only after** the capture
proves .48 on that worker:

```yaml
---
worker_backend_firewall_source_addresses: [192.168.80.48]
worker_backend_firewall_sources_verified: true
```

The verification flag is strictly boolean. Missing/false/string confirmations
block live installation before policy files or rules change. Check mode can
plan an unconfirmed boolean candidate, but still rejects malformed inputs.
Removal does not need source confirmation, a catalog or the installed helper;
it runs the repository helper temporarily to recover owned rules. Audits never
set source verification or application ACL flags. Source confirmation and
`services_worker_backend_acl_ready` remain separate, explicit operator inputs;
neither is automatically set by a probe, planning, installation or this runbook.

## Install, plan, audit and rollback

The new role target selects `ansible/operations.yml`, never the
application playbook. Use the actual NetBox inventory names if they differ from
`plex`/`unraid`. These commands are **operator steps**, not checks executed by
Codex. The current installed skynet wrapper must contain this new routing first;
review/install that wrapper separately through the established Ubuntu workflow.
Alternatively invoke the dedicated playbook directly with the same inventory,
tags and private `-e @file` inputs.

```bash
# Read-only Ansible plan; no files, kernel rules or persistence changed.
WORKER_BACKEND_FIREWALL_VARS_FILE=/private/plex-worker-firewall.yml \
  skynet limit plex check worker-backend-firewall
WORKER_BACKEND_FIREWALL_VARS_FILE=/private/unraid-worker-firewall.yml \
  skynet limit unraid check worker-backend-firewall

# Install/update the policy only, before application backend publications.
WORKER_BACKEND_FIREWALL_VARS_FILE=/private/plex-worker-firewall.yml \
  skynet limit plex install worker-backend-firewall
WORKER_BACKEND_FIREWALL_VARS_FILE=/private/unraid-worker-firewall.yml \
  skynet limit unraid install worker-backend-firewall
# 'update worker-backend-firewall' reapplies the same idempotent policy operation.

# Read-only live audit: compare current service/inventory plan with installed
# JSON, check both families' owned rules/head jumps and timer/watch liveness.
WORKER_BACKEND_FIREWALL_VARS_FILE=/private/plex-worker-firewall.yml \
  skynet limit plex run worker-backend-firewall check
WORKER_BACKEND_FIREWALL_VARS_FILE=/private/unraid-worker-firewall.yml \
  skynet limit unraid run worker-backend-firewall check

# Removal plan; source confirmation and application ACL flags are unnecessary.
skynet check worker-backend-firewall remove
# Rollback: first stop/unpublish the new backends or establish replacement ACLs.
# Removing this policy otherwise reopens those publications to existing policy.
skynet remove worker-backend-firewall
```

Removal disables only owned Plex units, removes only the owned Docker drop-in
and Unraid boot block, stops the Unraid watcher and deletes only the owned
policy files/rules. It leaves directories, other boot content, Docker and
Tailscale intact. It does not restart Docker or restore a whole-host snapshot.
A missing persistent helper does not prevent kernel cleanup. Names/references
that cannot be proven owned require operator review; do not flush the ruleset
as a workaround.

## Persistence and startup ordering

Plex uses existing **iptables-nft** with an owned systemd oneshot and timer. Its
Docker drop-in orders the policy before Docker and reapplies it both before and
after every Docker start; the independent five-second timer repairs head jumps
and address changes. Docker is never restarted by installation. Policy failure
in the Docker startup hooks fails that Docker start, so verify existing Python,
IPv4/IPv6 tooling and policy syntax before the operator's restart. Audit the
installed ordering with `systemctl cat docker.service` and the three owned
units; the read-only operation checks timer enabled/active state, not a reboot.

Unraid uses existing **iptables legacy** and the supported `/boot/config/go`
mechanism. A clearly marked block is inserted immediately after the shell
shebang, before the existing emhttp/WebGUI launch and subsequent Docker
startup. The persistent launcher installs the pre-DNAT guard synchronously,
then starts a singleton Python watcher. The watcher reapplies only this policy
every five seconds, including when Docker recreates DOCKER-USER or host
addresses change. The pre-DNAT chain is outside Docker's generated filter/NAT
chains and remains the restriction during ordinary Docker restarts. Only
configuration/helper files are on flash; locks/stop state are in `/run`, and
errors/changes use syslog rather than a flash log.

The existing Docker-prune User Scripts convention requires an installed plugin
and an operator-selected schedule. This role deliberately has no plugin
requirement and installs no User Script. A boot-only User Scripts schedule would
not cover Docker restarts. Review the existing go file for any Docker/container
startup **before** the marked block, and ensure the selected existing Python
3.10+ executable and both firewall families are available at that boot stage.
Unraid may obtain Python through an existing plugin: its availability/order is
an operator preflight, not an installed dependency or verified fact here.
The go block logs startup failure and preserves the remaining boot script;
it does not disable Docker or the WebGUI. A failed early guard therefore blocks
cutover approval, not Unraid boot. There is no claim that a polling watcher can
make arbitrary whole-host firewall flushes safe; those are prohibited, and
ordering changes must be audited before exposure.

See the primary [Docker firewall documentation](https://docs.docker.com/engine/network/firewall-iptables/),
[Netfilter match documentation](https://ipset.netfilter.org/iptables-extensions.man.html)
and [Unraid startup documentation](https://docs.unraid.net/unraid-os/troubleshooting/common-issues/boot-and-startup-failures/).

## Live acceptance matrix

Keep an independent administrative session open. Establish that a listener is
running and succeeds from its verified mgt container while testing denial;
a timeout against a stopped listener proves nothing.

1. From the real Traefik context, reach every HTTP worker backend. From the real
   Prometheus context, reach Unraid's 22622 metrics endpoint. Record worker packet
   headers proving the allowed source and HTTP/API result (401/403 can prove TCP
   reachability, but application acceptance still needs the intended response).
2. From another LAN machine, run
   `curl --noproxy '*' --connect-timeout 3 --max-time 5 http://<worker-address>:<protected-port>/`
   against every allocated worker backend: no TCP connection/HTTP response is
   allowed. Repeat against Plex .59 **and** .54, Unraid .20, worker Tailscale
   addresses from another tailnet machine, and every available IPv6 host address
   (IPv6 curl URLs need brackets). Reuse existing approved clients; do not install
   tools or reveal application tokens in commands.
3. From a normal permitted client, use the existing authenticated application
   workflow through `https://tautulli.<internal-zone>:<private-https-port>` and
   other worker internal-domain URLs. Verify DNS/TLS and the intended API/UI
   response. Prometheus must still scrape blackbox; unrelated SSH, Swarm,
   DNS, Plex/media and existing database connections must remain functional.
4. Inspect both firewall families on each worker:
   `iptables -t mangle -S PREROUTING`, `iptables -S INPUT`,
   `iptables -S FORWARD`, `iptables -S DOCKER-USER`, and equivalent `ip6tables`
   commands. Owned jumps must be first where the parent exists; inspect the
   three owned chains for original destination port matches and exact sources.
   IPv6 DOCKER-USER may be absent when Docker has no IPv6 filter chain;
   IPv6 PREROUTING/INPUT/FORWARD protection is still required.
5. Under a scheduled operator maintenance window, restart Docker, then reboot
   each worker separately. Repeat allowed, denied, internal-domain and unrelated
   connection tests, plus the read-only skynet audit after each event. On Plex,
   inspect owned timer/service status and Docker ordering. On Unraid, inspect the
   go block, syslog startup/reconciliation messages and the audit's watcher flag.
   Test the denied SYN path continuously across Docker restart to establish that
   the pre-DNAT restriction remains effective, rather than checking only later.

Before the first new application publication, use a controlled temporary
host listener on a **free** protected port to prove source allow/deny behavior:

```bash
# Operator on the worker, using its already installed Python. Serve an empty
# temporary directory, never an application/configuration tree. Keep foreground.
probe_dir=$(mktemp -d /tmp/skynet-worker-acl-probe.XXXXXX)
<existing-python> -m http.server 22619 --bind <worker-address> --directory "$probe_dir"
# Stop with Ctrl-C, then remove the empty probe directory: rmdir "$probe_dir"
# Use an allocated Unraid port on Unraid; repeat for relevant IPv6 addresses.
```

Test from a currently running intended mgt caller and another machine while
that listener is active; host-only success does not verify a container source.
Repeat from the actual Podman Traefik/Prometheus contexts once they run.
Repeat the native probe after the scheduled Docker restart/reboot and
inspect the live owned chains/head jumps before acknowledging the prepublication
ACL procedure. This proves INPUT/pre-DNAT behavior; it is **not** proof of actual
Docker DNAT/backend behavior. After the first bounded worker application update,
repeat the full matrix against its real forwarding/proxy path before continuing.

After source observation, policy audit, controlled prepublication allow/deny
checks and persistence checks, the operator may explicitly set
`services_worker_backend_acl_ready: true` for the first staged deployment.
Retain the distinction between that procedure acknowledgement and completed
application/live forwarding acceptance.
Installation never sets it. First-cutover acknowledgements remain independent
of batch tags. Managed service maintenance reuses the installed exact-source
policy and audits its selected publication and both kernel families, plus the
Unraid watcher or Plex timer, before mutation. A missing/stale policy or failed
audit blocks maintenance even with an old acknowledgement; reconcile policy
explicitly. It is never automatically installed by a service operation. Worker
Alloy operations follow the same scope rule.
**mgt backend, receiver and independent bootstrap ACL requirements are separate**;
this worker policy does not satisfy those gates.
