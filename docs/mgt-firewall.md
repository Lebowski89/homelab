# Mgt service firewall profile

Canonical implementation ownership: [service_firewall](service-firewall.md).
Installed paths and operator inputs remain compatible; no reinstall is needed for the source reorganisation.

The mgt profile owns narrowly scoped protection for declared mgt host publications,
alongside the distinct [workers profile](worker-backend-firewall.md). Current
service/target definitions and explicit operational requirements select the
applicable ports and callers. Installation is not evidence of live enforcement
and never sets application ACL/data acknowledgements.

Per-batch acceptance histories and migration handoffs are archived outside the
repository under `/opt/ansible/migration/`; retain the matching private policy,
backups and rollback records. For future caller/provider changes use the
[reusable HAProxy guide](../migrator/guides/haproxy.md) and current runtime facts.

## Coverage from declarations

All mgt private endpoints share `/etc/skynet-mgt-firewall/policy.json`.
Installation replaces its active endpoint set; adding an application is not an
implicit union. Forgejo has no separate firewall deployment in its service
definition. Extend the current installed policy rather than a historical
handoff's selection. `installed_policy_inputs` requires its generated IDs,
retains aliases and every caller binding/confirmation, and appends only the
requested IDs. The normal prospective validation and live identity resolution
remain required. Refuse a prospective update that omits an existing active
endpoint, and check source-policy continuity before installation. No application acknowledgement is set by this process.

`mgt_firewall_plan` uses the canonical base-plus-target merger, projects only
value-free metadata, and reads production NetBox/Infisical Podman declarations
from their role defaults. It never templates application environments, secret
declarations or credential defaults. The namespaced catalog loader ignores the
services README; malformed `.yml` still fails. No second port list is maintained.
Generate the current endpoint set from effective declarations; do not freeze
a migration-era count or port list. Duplicate receiver/backend declarations
share a policy and either generated ID selects the whole record.

| Declared endpoint purpose | Intended direct callers |
| --- | --- |
| Traefik HTTP backends and Authelia forward-auth | Traefik |
| Separate metrics and the standalone metrics-only backend | Prometheus |
| Prometheus receiver/backend | Traefik; Prometheus self scrape |
| Loki receiver/backend | Traefik; collectors push through internal HTTPS |
| Redis | The corresponding application, across its account boundary |
| NetBox PostgreSQL | NetBox; explicitly authorized recovery |
| HAProxy PostgreSQL | Declared PostgreSQL applications, controller database preparation, recovery |
| NetBox/Infisical direct recovery/lookup listeners | Traefik; explicitly authorized controller and recovery |
| ZNC IRC (`znc/irc`, 16502→6502) | Autobrr only, using its exact accepted caller binding; separate from Traefik's ZNC web access |

The plan shows generated IDs, published and container ports, caller candidates,
future accounts and exclusions. Traefik metrics are included through their
`metrics` publication. Application clients retain Technitium internal HTTPS;
Traefik backends and protocol metrics use direct endpoints, avoiding proxy loops.
Receiver collectors are not given direct backend access merely because they
use the receiver's HTTPS route. Additional direct receiver consumers require a
declared caller contract before activation.

The ZNC IRC publication follows the operator-confirmed Autobrr dependency. It
uses the same effective-port resolution, identity discovery, both-family rule
guards and strict confirmations as the other protected TCP endpoints. Naming
another service's publication `irc` does not confer this permission. Existing
Autobrr Docker evidence is retained; no future Podman account is automatically
authorized and no source/subnet exemption is added. Internal DNS supplies an
address, while the protected TCP publication supplies reachability; the ZNC
HTTPS route does not proxy IRC. Preserve the separately protected direct IRC
publication and its qualified caller binding.

HTTPS ingress, Forgejo SSH, DNS, SSH, Swarm, UniFi and unrelated media/database
publications retain existing policy. This guards host publications, including
their DNAT paths; unpublished overlay/container-address access remains under
existing policy. Rocky and the final consolidated-host firewall remain deferred.

## Caller identities and staging

Private `mgt_firewall_active_endpoints` selects **generated endpoint IDs**, not
ports or application tags. Empty defaults are a safe plan and cannot install.
Only selected publications are restricted. Leave HAProxy, NetBox and Infisical
inactive until every existing control-plane/database caller is accounted for.
Record a known-good private input file for each accepted stage; removing an ID
through a validated update withdraws just that endpoint's managed restriction.

Every active principal needs a list of bindings in `mgt_firewall_callers`.
`mgt_firewall_inputs_verified`, each `verified` and `restart_verified`, and the
applicable hook/route/override confirmation must be actual booleans. Missing,
false or incorrectly typed live confirmations fail before persistent writes.
The live install then resolves accounts/runtime identities and dry-tests both
families, including ownership collisions, before policy files or rules change.
Check mode accepts incomplete plans while preserving strict input types.
Application gate booleans acknowledge first-cutover prerequisites. For an
already managed service, routine operations instead compare its effective
endpoints and authorised callers with the installed policy and run the existing
strict read-only audit before any runtime stop or application mutation. Missing,
stale or noncompliant protection requires explicit reconciliation of the current
policy union; a historical boolean cannot override it. Pre-stop proofs are scoped
to one operation and exact service metadata so recreate does not depend on a
replacement already running. Application acceptance remains a separate process;
no readiness input or acceptance record is automatically promoted.

* `local`: exact NSS account and observed numeric socket UID. Future Podman
  accounts must match the effective declaration. Dedicated `podman-*` accounts
  qualify local sockets; native/shared accounts and UID 0 additionally require
  an exclusive persistent cgroup slice path. Confirm both UID and cgroup at
  OUTPUT; a process UID or a host route alone is insufficient.
* `container`, `path: bridge`: an exact **local** Swarm service selector for
  Docker, exact Compose `compose.project` **and** `compose.service` labels, or
  rootful Podman container name. Compose bindings omit `selector`; labels are
  collected from metadata, never inferred from a name. The helper projects container
  IDs/PIDs only, enters that network namespace to read link/address metadata,
  and binds its current source IP, MAC, host bridge and physical veth together.
  `physdev_verified` confirms those identities at PREROUTING, INPUT and FORWARD.
  It never authorizes a whole bridge/subnet or evaluates UID owner in forwarding.
* `container`, `path: local`: a host-network Docker/rootful Podman caller.
  The stable runtime selector resolves its current cgroup v2 path, verifies the
  host network namespace, and combines that path with the separately observed
  `socket_uid`. `socket_hook_verified` confirms both at OUTPUT. This is not an
  unqualified root/Docker-daemon exemption.
* `remote`: only authorized **controller/recovery** host paths, never remote
  application SNAT. Address comes from the named inventory host's `local_ip`
  and an exact observed ingress interface. An alternate observed LAN/Tailscale
  IPv4/IPv6 source requires `observed_address` plus strict
  `address_override_verified`; it cannot be a prefix or wildcard.
  `exclusive_verified` must establish a dedicated trusted operator source,
  without application SNAT sharing it. A shared worker/host address cannot
  become an operator exception just by labelling it recovery.
* `elsewhere`: a declared Docker worker database client verified to use
  worker-local HAProxy, rather than mgt. The inventory host must match its
  effective placement, `route_verified` must be true, and its only selected
  purpose must be the HAProxy database endpoint. This grants **no mgt access**.
* `disabled`: explicit omission of an unused controller/recovery path, requiring
  the same confirmations. Application callers cannot be disabled this way.

Each real binding explicitly records `phase: docker`, `podman` or `native`.
Keep currently needed Docker and verified future Podman bindings together during
transition. Retained Swarm rollback bindings grant no permission when their exact
service is stably at zero replicas and the independently verified replacement is
currently running in its declared dedicated rootless store and user manager.
The resolver verifies the replacement account, active unit, full container ID,
PID/start time and network namespace before accepting retirement. Changed host
placement, missing services, incomplete confirmations or a
missing replacement remain unresolved. Boot discovery deferral is unchanged.
Restoring a running Docker task re-resolves its exact bridge identity; a stale
container ID, shared subnet or root UID is never substituted.

The prepared Compose retirement extension additionally requires
`retirement: {container_id: <recorded-full-ID>}` on its exact project/service
binding. The ID is a stopped-writer guard, never an allowed packet identity.
Both label filters must find only that retained exited container, with PID zero,
`Running=false`, `Restarting=false` and restart policy `no`. These records and
the verified rootless replacement are checked again before retirement succeeds.
Missing containers, a different project/service, replacement, duplicates or an
automatic restart policy fail closed. Without this explicit retirement record,
an absent Compose caller remains unresolved. The Infisical cutover must record
and restore its original restart policy on scoped rollback. This source change
is not installed merely by preparing the batch; preserve the CURRENT full policy
and existing caller confirmations when its approved installation is performed.
An operator-verified removal (for example, expiry of a stopped container) may
add strict boolean `retirement.removal_verified: true`. This preserves the exact
rollback binding and recorded ID. Both the exact project/service selector and
that full ID must be absent from **all** Docker containers before and after the
independent running-rootless-replacement checks. A recreated or relabelled
container, failed query, changed replacement or incomplete confirmation fails
closed. This absence never grants a Docker packet identity. Missing the field
retains the exited-container contract; false cannot pass live validation.
Runtime selectors are stable across task/container replacement; IP, MAC, veth
and cgroup references are re-resolved. Missing callers have no allow rules during
boot/reconciliation and make audits fail. New callers can be denied until the
next timer pass; old identities are withdrawn on that pass. Kernel identities
are not a defense against privileged code that can alter networking/firewalls.

If a worker app reaches mgt through a shared worker/SNAT address, this policy
cannot distinguish it from another app on that worker. Activation must wait for
a verified exclusive path or an explicit architecture decision. Do not replace
it with a blanket worker-IP or LAN allow. Likewise, shared userland-proxy socket
identity or missing physdev/cgroup metadata requires resolution, not an exemption.

## Operator preflight and commands

These commands are **operator steps**, not actions run during repository work.
First make the updated skynet wrapper and policy-only playbook available through
the established operator process; application deployment is not part of that
step. Use a separate private firewall input file, outside Git and separate from
secret-bearing bootstrap inputs:

```bash
export MGT_FIREWALL_VARS_FILE=/secure/mgt-firewall-stage.yml
skynet check mgt-firewall                 # read-only catalog/active-policy plan
skynet run mgt-firewall observe           # read-only local identity metadata
```

The first plan can use empty active endpoints/callers and boolean false. Then
select generated IDs and fill candidate bindings, keeping confirmations false
while observing. For example, `traefik/metrics` requires the `prometheus`
principal. A current Docker candidate uses this shape; replace the selector
with the observed exact Swarm service name before observation:

```yaml
---
mgt_firewall_active_endpoints: [traefik/metrics]
mgt_firewall_inputs_verified: false
mgt_firewall_callers:
  prometheus:
    - kind: container
      runtime: docker
      selector: REPLACE_WITH_CURRENT_SWARM_SERVICE
      phase: docker
      path: bridge
      verified: false
      restart_verified: false
      physdev_verified: false
```

`observe` prints available value-free bindings and pending identities without
setting flags. It does **not** prove packet-hook matching. To identify existing
selectors and paths without inspecting secret-bearing environments:

```bash
sudo docker ps --format '{{.ID}} {{.Names}} {{.Label "com.docker.swarm.service.name"}}'
sudo docker inspect --format '{{.State.Pid}}' "$CALLER_CONTAINER_ID"
sudo nsenter --target "$CALLER_PID" --net ip -j address show
ip -j link show
sudo readlink "/proc/$CALLER_PID/ns/net" /proc/1/ns/net
sudo cat "/proc/$CALLER_PID/cgroup"
getent passwd "$CALLER_ACCOUNT"
sudo nft --json list ruleset
```

Compare peer indexes, bridge, addresses, MAC, host namespace and cgroup with the
observation output. Inspect native rules for relevant bypass mechanisms; the
helper refuses activation/audit when nft flowtables exist, since offload can
bypass these hooks. It does not remove them or change Netavark/Tailscale policy.
For native controller/recovery jobs, observe the **actual delegated Ansible or
recovery connection context**, including become/PAM/cgroup effects. The shell
that launched skynet may have a different socket identity. Provide an existing
authorized persistent slice or account-session slice that actually matches;
this role does not change SSH/PAM or create a broad root exemption. The separate
[native operator preparation](mgt-native-operator.md) supplies two persistent
slices and narrowly scoped execution of the actual delegated PostgreSQL module
and explicit local recovery. Keep their new confirmations false until socket,
UID-and-cgroup hook and new-child evidence is accepted. No firewall matching
contract changes or whole-deployment/root exemptions are introduced.

For a bridge binding, temporarily count a narrowly matched existing endpoint
probe in each hook, using the identities and old listener observed above:

```bash
# No target: count then continue under the existing policy; no payload logging.
sudo iptables -t mangle -I PREROUTING 1 -p tcp -d "$MGT_ADDRESS" --dport "$CURRENT_PORT" -i "$BRIDGE" -s "$SOURCE_IP" -m physdev --physdev-in "$VETH" -m mac --mac-source "$MAC" -m comment --comment skynet-mgt-observe
sudo iptables -t mangle -L PREROUTING -n -v -x
# Trigger the intended real caller, then inspect the counter again.
sudo iptables -t mangle -D PREROUTING -p tcp -d "$MGT_ADDRESS" --dport "$CURRENT_PORT" -i "$BRIDGE" -s "$SOURCE_IP" -m physdev --physdev-in "$VETH" -m mac --mac-source "$MAC" -m comment --comment skynet-mgt-observe
```

Repeat with filter INPUT for host listeners and FORWARD for DNAT, matching
`-m conntrack --ctdir ORIGINAL --ctorigdst "$MGT_ADDRESS"
--ctorigdstport "$CURRENT_PORT"` instead of the post-DNAT destination/port.
Repeat with `ip6tables` and verified IPv6 identities for exposed IPv6 paths.
Count local sockets in mangle OUTPUT with `-m owner --uid-owner "$SOCKET_UID"`,
plus `-m cgroup --path "$CGROUP_PATH"` where required. Remove each observation
rule by its exact specification; never flush a chain. Trigger normal proxy
requests/scrapes when a caller image has no client binary. Packet-header-only
capture is also useful; do not log application payloads or credentials.

Dedicated Podman accounts have nologin shells. Once an intended rootless caller
is running, use direct execution with its own home/runtime environment:

```bash
CALLER_ENTRY=$(getent passwd "$CALLER_ACCOUNT")
IFS=: read -r _ _ CALLER_UID _ _ CALLER_HOME _ <<< "$CALLER_ENTRY"
sudo -u "$CALLER_ACCOUNT" -- env HOME="$CALLER_HOME" XDG_RUNTIME_DIR="/run/user/$CALLER_UID" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$CALLER_UID/bus" /usr/bin/podman exec "$CALLER_CONTAINER" curl --connect-timeout 3 --max-time 5 "$DIRECT_TEST_URL"
```

Use an available approved client inside that container, or trigger its normal
request, rather than installing/pulling a diagnostic dependency. Current
Docker and existing rootless Homepage observations establish only those
contexts. Podman Traefik/Prometheus are not yet deployed: account preparation
does not prove their future sockets. Verify the prepared account's transport
in an approved equivalent probe context before activation, then repeat actual
container observations and acceptance after cutover. Reboot/replacement tests
must confirm the stable selector resolves a new identity and the rules follow
it. Record results privately; manually confirm only the evidence obtained.

After complete caller/hook/restart preflight for the **active** stage:

```bash
skynet check mgt-firewall
skynet install mgt-firewall               # policy only; no applications
skynet update mgt-firewall                # re-resolve/reconcile the selected stage
skynet run mgt-firewall check             # read-only kernel + persistence audit
```

## Enforcement and persistence

Only mangle `SKY-MGT-PRE`/`SKY-MGT-OUT`, filter
`SKY-MGT-IN`/`SKY-MGT-FWD`/`SKY-MGT-LOCAL` and exact jumps marked
`skynet-mgt-endpoints` are owned. Their jumps are first in PREROUTING, OUTPUT,
INPUT, FORWARD and existing DOCKER-USER. `addrtype LOCAL` covers alternate LAN,
Tailscale and IPv6 addresses before DNAT; post-DNAT matches use original local
destination address **and port**. Local OUTPUT qualifies UID/cgroup before and
after DNAT. Only already-guarded loopback **endpoint tuples** return at incoming
hooks; there is no blanket loopback/account/source-IP exemption. Replies and
unrelated traffic return to existing rules. Authorized packets also return;
this role does not override an existing deny policy with blanket accepts.

Mangle guards precede destination NAT and filter accepts. Native nft base-chain
accepts do not suppress a later DROP in another base chain. The unchanged
worker transaction engine is bundled into an isolated mgt module; worker
chains, comment markers, policy and persistence are untouched. The policy does
not match or assign packet/conntrack marks. No host snapshot, default-policy change, backend switch,
Docker-firewall disable or host ruleset flush is used. Both families are tested
before writes; atomicity is per table/family, not across all transactions. A
partial application failure requires audit and scoped rollback, not acceptance.
See [Netfilter hook priorities](https://wiki.nftables.org/wiki-nftables/index.php/Netfilter_hooks)
and the [owner/cgroup/physdev contracts](https://man7.org/linux/man-pages/man8/iptables-extensions.8.html).

The helper first inspects the native ruleset without changing it. Audits and
removal skip absent compatibility tables instead of initializing them through
xtables listing. Installation can create its guards in an absent table using
restore insertions, without declaring or changing default policies. For an
existing table, `iptables-save` is the compatibility view: it can advertise a
logical `:OUTPUT ACCEPT [0:0]` while native nft has never materialized OUTPUT.
That absence is legitimate. Installation retains the OUTPUT guard insertion,
which materializes the standard built-in; it does not omit local protection or
manually create/repair a shared chain. Missing logical built-in declarations,
user-chain policies and incompatible native hooks still fail, as do unowned
chain/reference collisions. Audit performs no restore; removal emits only
owned deletions and never creates missing tables or chains. Existing rules and
policies are preserved, and both families are dry-tested before application.
Newly materialized empty compatibility base chains remain after scoped removal. This distinction
matters because [xtables-nft listing can initialize an empty ruleset](https://man7.org/linux/man-pages/man8/xtables-nft.8.html).

The owned boot guard runs before Docker, rootful endpoint units and logind
(which orders user managers). Before network addresses/runtime callers exist,
it installs endpoint deny guards and any available qualified local bindings.
The boot guard and Docker ExecStartPre explicitly defer runtime discovery:
they do not query Docker, Podman or Docker socket activation. Docker
ExecStartPost and the timer discover Docker callers only when its service is
active; callers stay denied while the service is starting. All subprocesses
have a 15-second timeout. Runtime commands explicitly select the local Docker
socket or nonremote Podman, independent of inherited contexts. A five-second
systemd timer reconciles current caller/address identities and jump ordering,
including rootful/rootless Podman lifecycle changes. No Podman API service is
required for Quadlets. Native accepts cannot bypass the early guard; if another
manager removes/reorders that guard itself, exposure can last until reconciliation.
The timer is bounded reconciliation, not an instantaneous lifecycle guarantee.
Operator reboot/Docker/Podman replacement tests remain mandatory.

Owned drop-ins require the root guard for affected dedicated `user@UID.service`
managers and rootful endpoint units, so failed boot application cannot expose
those listeners. Native operator/SSH accounts receive no such dependency.
Earlier owned manager dependencies remain until full policy removal, even when
a stage withdraws a port. Disabling/removing policy never stops the boot guard
while these dependencies exist: that would propagate stops to applications.

Only the helper, declaration JSON, three owned units and marked dependency
drop-ins are persisted. The JSON includes checksums of those persistence files;
audit checks content, enabled boot/timer units and active timer. Stopping the
boot guard does not remove rules. Installation reloads systemd and starts only
its timer; it does not restart Docker/Podman or application units.

## Acceptance, offline recovery and rollback

Keep an SSH session and offline input/cached inventory available before adding
control-plane endpoints. For every selected endpoint prove allowed access from
the **intended current container/native context**, denied access from another
LAN machine and an unauthorized local account/container, and normal internal
HTTPS. Probe both observed LAN addresses (.48/.53), Tailscale addresses and all
exposed IPv6 addresses. A missing listener's refusal is not proof of filtering;
use an actual approved listener and require unauthorized SYNs to time out.

```bash
# Supply observed destinations and generated active port, not a second port list.
nc -z -w 3 "$MGT_ADDRESS" "$ACTIVE_PORT"       # intended context: succeeds
nc -z -w 3 "$MGT_ADDRESS" "$ACTIVE_PORT"       # other LAN/context: times out
nc -6 -z -w 3 "$MGT_IPV6_ADDRESS" "$ACTIVE_PORT"
curl --connect-timeout 3 --max-time 10 "$INTERNAL_HTTPS_URL"
sudo /usr/bin/python3 /etc/skynet-mgt-firewall/policy.py check
sudo journalctl -u skynet-mgt-firewall-reconcile.service --since today
```

Repeat after operator-scheduled reboot, Docker restart, and each affected
Podman caller replacement. Inspect `observe` before/after to prove identity
refresh, verify application/cache/database behavior, controller inventory and
secret-store routes, receiver delivery and existing HAProxy clients. Audit is
configuration evidence; it is not live ACL acceptance. Only then manually set
the applicable application ACL acknowledgements for the accepted scope.

The installed helper/policy use local NSS, runtime metadata, ip/nft/iptables and
systemd only. They need no NetBox, Infisical, DNS route, service catalog or secret.
For skynet audit/removal while NetBox is unavailable, set `INVENTORY` to a
private cached/offline inventory containing the same single controller in
`tags_ansible_manager` with a local connection; do not use the dynamic plugin.
Direct recovery on mgt works without any inventory:

```bash
sudo /usr/bin/python3 /etc/skynet-mgt-firewall/policy.py check
sudo /usr/bin/python3 /etc/skynet-mgt-firewall/policy.py remove --dry-run
sudo systemctl disable --now skynet-mgt-firewall-reconcile.timer
sudo systemctl stop skynet-mgt-firewall-reconcile.service
sudo systemctl disable skynet-mgt-firewall.service
# Remove only marked Docker/caller drop-ins, preserving applications and other drop-ins.
sudo /usr/bin/python3 /etc/skynet-mgt-firewall/policy.py remove --remove-dropins
sudo systemctl daemon-reload
```

Normal scoped removal is `skynet remove mgt-firewall`; it validates ownership
first, stops only its timer/reconciler, disables the guard without stopping
dependent applications, removes marked chains/jumps and owned
unit/drop-in files, and retains helper/JSON for repeatable recovery. Direct
rollback above deliberately retains disabled unit files/JSON. It requires no
ACL acknowledgements, catalog load or running Docker/Podman daemon. To roll
back only a stage, restore the last accepted private input file and run
`skynet update mgt-firewall`; unrelated host and verified worker policy remains.

## Firewall acceptance to rootless HAProxy

Use the [dedicated batched preflight, candidate generator and rollback procedure](../migrator/guides/haproxy.md)
for the current Compose/Swarm/Forgejo/controller/recovery callers. It preserves
the native worker config contract and records config references without contents.

1. Reuse accepted Homepage lifecycle evidence. Before interruption, resolve
   current caller/hook, controller/recovery and metrics identity, idle declared
   dependencies, configuration and per-path ownership preparation. Pre-stage
   the accepted helper/policy and direct rollback locally, outside Forgejo.
   Keep unproved confirmations false, including worker-only VIP routes.
2. In one maintenance window, add only the canonical mgt exclusion to the
   existing HAProxy service. Preserve workers, shared VIP and native config;
   do not redeploy worker config or change Swarm clients' database destinations.
3. Recollect/verify worker-only placement and application routes. Complete
   `elsewhere` confirmations only from that evidence; unresolved callers block
   policy installation. Keep current mgt Docker and existing Forgejo bindings.
4. Install the prepared `haproxy/postgres` **and `haproxy/metrics`** policy,
   preserving every current endpoint and binding. Audit and prove coverage before
   acknowledging backend ACLs for this narrow deployment. Ownership readiness
   remains keyed by `haproxy`; no installation sets acknowledgement flags.
5. Deploy only `mgt-haproxy`, then accept PostgreSQL clients, metrics,
   controller/recovery and firewall paths in one batch. Focus replacement checks
   on the new HAProxy unit; future Podman callers are accepted in their batches.
   Defer coordinated reboot acceptance to the final migration stage. Retain
   rollback state and current Docker caller bindings until their retirement.

The [HAProxy procedure](../migrator/guides/haproxy.md) supplies exact commands, expected
results and offline rollback at each transition. Check-mode planning remains
read-only; live confirmations and deployment gates are unchanged.

