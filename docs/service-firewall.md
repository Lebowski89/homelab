# Service firewall and manual operations

Normal service operations use `skynet deploy <service>`, `skynet update <service>`,
`skynet recreate <service>` and `skynet remove <service>`. New publications declare
`exposure: public` or `exposure: private` beside their port numbers. Private
publications also list logical `callers`; targets use `service:target`.

For declaration-backed services, the dispatcher checks inventory, collisions,
current protection and storage before secret preflight. The runtime adapter
prepares its account, asks this role to stage the current policy union, then
changes its application. After startup it reconciles identities before waiting for application health, verifies the image, running process and publications, and performs bounded
TCP handshakes from current caller network namespaces with owned RETURN-counter
increases. Both kernel families are audited. No browser, SQL, notification,
external-denial or application acceptance is inferred, and no historical
acknowledgement is promoted.

Existing managed declarations without exposure metadata are adopted through the existing value-free planners, after verifying their exact runtime/publication contract. Fresh or changed unclassified publications are rejected. Wallos and Whisparr exercise explicit declarations in the real catalog. Retained native/remote caller bindings are audited unchanged; they are not reprobed as ordinary root. Independent bootstrap/recovery gates remain separate.
Existing-data ownership changes still need consistent backups, stopped writers,
proved translations and the actual service-name ownership acknowledgement.
Absent/empty writable roots can be prepared automatically after a complete
read-only storage inspection.

`ansible/roles/service_firewall` is the only firewall implementation owner. It
has two explicit profiles, not interchangeable identity models:

| Profile | Protection | Supported operations |
| --- | --- | --- |
| `mgt` | Exact local account/cgroup and container identities; authorised controller/recovery contexts | install, check, observe, remove |
| `workers` | Verified exact remote mgt sources, protecting declared worker publications | install, check, remove |

`service_firewall_profile` and `service_firewall_operation` select direct role
use. Unknown profiles/operations, worker observe, conflicting operation tags and
cross-profile tags fail before mutation. Existing `mgt_firewall_*` and
`worker_backend_firewall_*` inputs remain the public compatibility API. Profile
facts retain those namespaces deliberately, including their narrow naming-lint
annotations. Do not set readiness/verification inputs simply because a plan ran.

Task output uses `Service firewall | Mgt | …` or `Service firewall | Workers | …` to
identify the profile. A **reconciler** periodically checks and reapplies managed rules;
the mgt profile also resolves current caller identities. A read-only **audit** reports
compliance without repairing anything.

The role layout is:

- `tasks/mgt/`, `templates/mgt/` and `files/mgt-firewall.py`: mgt identity,
  lifecycle ordering, policy audit and scoped removal.
- `tasks/workers/`, `templates/workers/` and `files/worker-backend-firewall.py`:
  worker sources, Plex systemd and Unraid boot/restart reconciliation.
- `tasks/operations/`: inventory contracts and manual profile orchestration.
- `files/transactions.py`: shared save parser, owned jumps, no-flush table
  transactions and writer locking. Each profile binds its own chains/marker/lock;
  mgt never imports an implementation owned by the worker role.
- `files/bundle.py`: embeds those primitives in each installed helper. Deployed
  helpers remain self-contained, including worker removal and watcher startup.

There is no new endpoint catalog. Existing effective service/inventory and
bootstrap declarations drive the existing planners. Policy unions, strict
confirmations, both-family dry tests, collision checks, sparse nft compatibility,
pre/post-DNAT guards and recovery behavior remain in their existing algorithms.

## Adding and operating a service

This example assumes an image whose application uses UID/GID 1000 and port 8080.
Choose an actual pinned image and an unused host port. Host account IDs are
allocated by the existing adapter, never copied from this example.

```yaml
example:
  enabled: true
  runtime: podman
  tags: [example]
  name: example
  image: registry.example.invalid/example:1.0.0
  user: "1000:1000"
  named_networks:
    example:
      driver: bridge
      external: false
  ports:
    backend:
      exposure: private
      callers: [traefik]
      host_ip: "{{ local_ip }}"
      published: 18500
      target: 8080
  deploy:
    type: container
    host: "{{ services_controller_host }}"
    execution:
      mode: rootless
      host_user: podman-example
      userns:
        mode: keep-id
        uid: "1000"
        gid: "1000"
```

Run `skynet check example` for a side-effect-free plan, then `skynet deploy example`.
No private policy JSON or separate firewall installation is needed on a supported
prepared host. Add the usual Traefik/filesystem declarations when the application
needs routing or persistence. Public exposure leaves traffic to existing host
policy; it never installs a broad ACCEPT rule. Publication metadata is not passed
to Compose or Quadlets.

Declared rootless caller accounts are allocated/validated without starting user managers or applications. New clients may remain inactive while their provider starts: their traffic stays denied until an exact runtime identity appears. An absent previously managed or legacy accepted Docker caller remains a failed guard. Pending activation is reported, not accepted.

Each policy update rereads the installed union under the same writer lock as the
periodic reconciler. It reserves only the selected service, retains old ports
through recreation, and withdraws obsolete entries only after runtime verification.
Administrative installs also merge the current union and reject conflicting/stale
entries instead of overwriting them. They cannot overwrite an unfinished service
operation. Saved whole-policy snapshots are never rollback inputs to this path.

Remove checks declared runtime dependencies, reserves only installed ownership, verifies the selected runtime has stopped and its listeners/NAT publications are absent,
then removes only its endpoints and unreferenced automatically added bindings. Authorised ACL callers are not treated as shared-state dependencies. Active same-host dependents must be retired explicitly first; configured dependents on other hosts require an explicit retirement before removal. Missing installed protection fails with a repair instruction before runtime removal; removal never creates missing policy infrastructure.
Accepted operator/rollback bindings, data, shared hooks and other services remain.
Removal polls for asynchronous writer/listener/NAT withdrawal before cleanup.
A cleanup failure leaves a durable operation record and safe protection; a matching
remove retry can finish without recreating the application. Failed starts attempt
only adapter-owned replacement stops, retain staged protection and the original
failure, and release their reservation only after proving writer absence. Inspect
an interrupted operation before recovery; never replace the union with an old file.

### Client access to protected providers

The same operation also reconciles the selected client's access to existing
providers. PostgreSQL clients use the existing `postgres.enable`, host/inventory
and port contract; its default is the controller's protected PostgreSQL
publication. Other integrations use the provider publication's logical `callers`
list, including `service:target` for split targets. Only the selected client is
added, even if the provider declares other clients. No permission is inferred
from a successful connection or from application environment values.

Before application preparation can connect, the role prepares the client's
stable dedicated account, audits the existing provider policy and verifies the
provider's current runtime/image/publications. It contributes the exact client
binding under the existing writer lock. The provider is neither deployed nor
restarted. A missing provider, changed publication/placement or incompatible
installed identity fails before application mutation. A new Docker client stays
pending and denied until its current container identity resolves; pending access
is not successful access. Startup reconciliation precedes health checks, then
qualified handshakes require owned RETURN-counter increases.

Contribution ownership lives under the client's existing `managed_services`
record, alongside its publication ownership. Each affected host commits under
its own policy lock. Partial failures retain protection/contributions, report the
failed host, and record the completed contribution as failed for a guarded retry;
there is no cross-host snapshot rollback. Ordinary retries read the current union.
On client removal, stopped-writer proof permits removal of only its contributed
caller entries and mechanical bindings. Pre-existing/shared permissions, accepted
operator and rollback bindings survive. Provider maintenance preserves active
client contributions. A worker endpoint retains its verified remote-source model;
a local account UID is never exported as a worker identity. Established
worker-local PostgreSQL/elsewhere contracts are left intact.

For example, add the usual PostgreSQL/Infisical declarations to a new application
with `postgres: {enable: true, databases: [example]}`. With the declared provider
already running and protected, `skynet deploy example` prepares its identity,
adds its provider access, prepares the database through the normal credential
contract, stages its own endpoints and starts/verifies the application.
`skynet recreate example` follows the same checks before stopping its old runtime.
`skynet remove example` proves writer/listener withdrawal and removes its owned
publications and contributed access. No provider deployment or policy JSON step
is required. Explicit destinations outside the protected controller boundary
retain their existing database preparation contract.

### Swarm failure containment

Replicated services retain selected-service scale-to-zero containment. Global
services cannot be scaled: the Docker adapter containment helper verifies the exact immutable service ID
and declared mode, adds a service-only constraint against a verified nonexistent
node ID, and polls both saved and newly observed tasks for terminal states.
Only after that proof does it remove the selected global service. Native configs,
networks, data and other services remain. The next ordinary deployment recreates
it from the canonical declaration. No node is drained and no daemon is stopped.

Containment failure is reported separately from the original deployment failure.
The operation reservation is released only after per-host writer absence is also
proved. A failed stop leaves protection and a failed-containment record. Once
manager containment and local absence are proved, a matching ordinary deployment
can retry. An inconclusive manager result requires scoped remove/recovery even
when local containers have exited. If the writer is
still present, use the supported scoped `skynet remove <service>` recovery before
`skynet deploy <service>`; removal preserves persistent application data. Do not
manually remove a reservation or restore an old policy snapshot. An unexpected
mode/identity is a failed guard, not permission to affect another service.

### Supported boundaries

- The mgt profile retains its Ubuntu 26.04/nf_tables contract. Workers support the established Ubuntu/Plex and Unraid profiles; Rocky Linux is not supported by this lifecycle. One-service Docker standalone projects
  (exact project AND service) and Swarm stacks with private host-mode TCP
  publications, and rootful/rootless Podman on mgt use their existing adapters. Swarm supports one replica or one global task per declared host.
- Rootless caller rules use the dedicated account; bridged Docker/rootful Podman
  callers resolve current PID/namespace/bridge/IP/MAC/veth identities. They never
  authorise a shared subnet or root UID. Host-network/native operator callers
  still require their existing explicit, verified cgroup/socket contracts; new
  automatic host-network callers are rejected.
- Private UDP, duplicate publication aliases, Swarm private routing-mesh ingress, cross-worker application
  identities and automatic changes to shared Docker projects/stacks are rejected before
  mutation. Existing opaque NAT maps or port ranges cannot be classified automatically and require a reviewed port-ownership transition. A changed placement outside the current supported profile requires
  an explicit transition; no firewall backend or host networking is changed.
- Workers reuse the installed, verified exact mgt source set and existing startup
  mechanism. An unprovisioned worker, a verified source no longer assigned to mgt, an explicitly changed source set or an absent reconciler is a
  preflight failure: establish the source/persistence boundary before onboarding services. A source change needs its own reviewed transition; normal deploy does not assert new source verification. A namespace handshake plus an audited source
  guard proves access through the existing allow set; it does not identify a new
  translated source or set `sources_verified` automatically.
- The automatic path does not restore databases/files or reverse image upgrades.
  Genuine data migrations retain the existing reviewed paired-backup/ownership
  procedure and scoped recovery. Application acceptance remains a separate human
  observation.

## Supported operator commands

Use the current reviewed playbook/config explicitly when working in a worktree.
Changing directory does not change the installed `skynet` default. The existing
commands and `MGT_FIREWALL_PLAYBOOK`/`WORKER_BACKEND_FIREWALL_PLAYBOOK`, `PLAYBOOK`,
`INVENTORY`, `ANSIBLE_CONFIG`, `MGT_FIREWALL_VARS_FILE`,
`WORKER_BACKEND_FIREWALL_VARS_FILE` and tooling overrides are preserved.

```bash
MGT_FIREWALL_VARS_FILE=/private/reviewed-policy-inputs.json skynet check mgt-firewall
MGT_FIREWALL_VARS_FILE=/private/reviewed-policy-inputs.json skynet run mgt-firewall observe
MGT_FIREWALL_VARS_FILE=/private/reviewed-policy-inputs.json skynet install mgt-firewall
MGT_FIREWALL_VARS_FILE=/private/reviewed-policy-inputs.json skynet run mgt-firewall check
skynet remove mgt-firewall
WORKER_BACKEND_FIREWALL_VARS_FILE=/private/reviewed-worker-inputs.json skynet check worker-backend-firewall
WORKER_BACKEND_FIREWALL_VARS_FILE=/private/reviewed-worker-inputs.json skynet install worker-backend-firewall
WORKER_BACKEND_FIREWALL_VARS_FILE=/private/reviewed-worker-inputs.json skynet run worker-backend-firewall check
skynet remove worker-backend-firewall
```

These are live operator operations, not offline validation commands. Normal role
commands accept private inputs through the environment overrides above, not
arbitrary `-e` arguments. `skynet check mgt-firewall` and
`skynet check worker-backend-firewall` select **Ansible check-mode installation
planning**, without policy writes or runtime discovery; they do not audit the
installed protection. `skynet run mgt-firewall check` and
`skynet run worker-backend-firewall check` perform the **read-only installed
policy/kernel/persistence audit**, without Ansible check mode or repairs.
Mgt observe resolves identity metadata without promoting confirmations.
Administrative install requires reviewed inputs and merges the current union; conflicting existing entries must be reconciled through their service lifecycle. Existing manual confirmations remain strict; remove touches owned chains/jumps/hooks only. Keep consistent
private rollback inputs.

Routine worker maintenance retains strict root ownership and POSIX permissions
on Ubuntu/Plex. Unraid's two fixed policy/helper files instead require the
root-owned VFAT block-device filesystem mounted at `/boot`, matching device
identities and non-symlink directories, with no shadow mounts on those paths.
Its synthetic mount-defined write bits are not independently configurable file
permissions. Other paths and files retain strict POSIX checks; no mount or file
permissions are changed by validation.

Detailed boundaries: [mgt](mgt-firewall.md), [workers](worker-backend-firewall.md).

## Manual workflows and compatibility

`ansible/tasks/` contains main-playbook host contracts/defaults, catalog selection,
preflight and runtime dispatch. Standalone manual lists live under
`ansible/operations/`, selected explicitly through `ansible/operations.yml`;
none run by default or with `--tags all`. See its [operation list](../ansible/operations/README.md).
`bootstrap.yml` remains independent provider recovery. Executable support tools
stay in `operator/`; neither directory is another deployment engine.

Compatibility remains intentionally narrow:

- `roles/mgt_firewall` and `roles/worker_backend_firewall` task entries forward
  to the canonical role for retained role/tasks_from imports. Old helper and
  template paths are relative symlinks to their canonical source for saved
  rollback/import callers; no second implementation is kept.
- The four old `tasks/` manual entry paths forward to `operations/` for retained
  task imports. Root `mgt-firewall.yml`/`worker-backend-firewall.yml` remain for
  already installed skynet wrappers. New calls use operations.yml.
- Installed `/etc/skynet-mgt-firewall`, worker `/etc/` or `/boot/config/` policy
  directories, `policy.py` destinations, chain/comment names, drop-ins and systemd
  units are unchanged. Reorganisation alone needs no reinstall or migration replay.
- Completed Swarm-only Loki ruler and Prometheus Alertmanager/HAProxy/Scraparr
  configuration workflows are removed from normal operation selection. Their
  exact pre-removal source/tests are in the existing private review archive under
  `/opt/ansible/migration/mgt-completed-20261019-kibomgve/firewall-layout.2e7sqdij`.
  Old tags now fail explicitly. Docker adapter handlers/filters and behavioral
  regressions remain as compatibility code: saved external rollback references
  cannot all be established offline. They are not the update path for rootless
  Loki/Prometheus. Change canonical configuration and use its runtime adapter.

Saved self-contained installed helpers and accepted rollback snapshots remain
untouched. Very old external scripts that build helpers by concatenating raw
source instead of using the bundler may need review; path aliases preserve
imports, not an undocumented source-concatenation interface. No live cleanup is
implied. Docsible owns generated role READMEs; this guide is human-maintained.
