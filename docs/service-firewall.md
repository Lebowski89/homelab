# Service firewall and manual operations

Normal application maintenance uses the canonical catalog and existing runtime
adapters: `skynet deploy <service>`, `skynet update <service>` and
`skynet recreate <service>`. Managed prerequisites are audited before secrets,
files or runtime stops. First cutovers and unproved ownership changes retain
explicit acknowledgements; no command infers application acceptance or installs
firewall policy automatically. See [Podman lifecycle](podman-services.md).

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
Install requires review of the complete current union and all applicable
confirmations; remove touches owned chains/jumps/hooks only. Keep consistent
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
