# Repository test execution

Use `/opt/ansible/ansible-venv/bin/python -m pytest tests/unit` for the complete
suite. Tests use synthetic inventories, fake external I/O and private temporary
state. They do not establish live application or firewall acceptance.

## Post-merge redundancy audit

Separate branch from `origin/main` at `393d0aca`, containing PR #726's merge
`9398db78`. This proposal was recorded before pruning. Production code,
CI selections, markers and generated documentation remain unchanged.

| Test/cases removed or consolidated | Retained replacement | Behavior preserved | Coverage limitation | Runtime evidence |
| --- | --- | --- | --- | --- |
| `test_workstation.py::test_main_playbook_accepts_each_workstation_tag_with_synthetic_inventory`: `workstation` and six tooling tags | `test_actual_main_bootstrap_without_netbox_or_application_inputs` and all six `test_inline_bootstrap_inventory_and_granular_tools` cases | Real main-entry selection without application inputs/collections; inline cases now require account lookup to prove role execution | Installation I/O remains synthetic; the other five granular listing probes stay | Seven Ansible processes eliminated; 3.862s cumulative baseline time |
| `test_service_catalog_filter.py::test_valid_target_runtime_override_is_allowed` | `test_canonical_target_merge_contract` and `test_target_runtime_and_deploy_override_select_dispatch_host` | Docker-to-Podman override through catalog, effective merge and dispatch placement | No live acceptance; inherited/invalid runtime and portability cases stay | One pure filter call; negligible duration |
| Four `test_service_definition_style.py::test_correctly_ordered_runtime_service_is_accepted` parameters become one ordered document | That single case and `test_all_repository_service_definitions_follow_canonical_layout` | Synthetic and real base/target key ordering | Layout ignores runtime/enabled values; catalog semantic and malformed-layout cases stay | Three equivalent traversals eliminated; negligible duration |
| Task counts in `test_workstation_tooling.py::test_workstation_dynamic_includes_propagate_selection_without_unrelated_components` | All five `test_granular_tag_executes_validation_and_only_the_selected_tool` cases and granular platform/package execution | Selected payload plus validation; retain applied tags, clone-prerequisite wiring/opt-in guard and local OpenTofu ownership | Installation payloads are sentinels; cloning prerequisites retain wiring coverage because these cases do not opt into cloning | No case removed; delete the unused local count accumulator |

Deferred: the five remaining listing probes need equivalent main-entry execution.
Rootless firewall identity, transactions, rollback and retained protection remain:
the VM lane is documented as disabled pending its protected controller and
requires explicit enablement (server-side state was not queried). Its protected
suite certifies Docker callers, not protected rootless Podman callers. Historical
VM passes cannot replace routine coverage of each contract/failure mode.
RomM/Bazarr/Authelia settings and data migration tests also stay; generic lifecycle
success does not establish those preservation contracts.

The unchanged environment uses Python 3.13.5, pytest 9.1.1, Ansible 2.21.5 and
Ruff 0.17.2; nothing was installed/upgraded. Current pins differ for pytest
(9.2.0), Ruff (0.17.3), Infisical SDK (installed/pinned 1.0.18/1.1.0), pytz
(2026.5/2026.6), community.general (13.5.0/13.5.1) and community.postgresql
(5.1.0/5.1.1). CI's Python 3.14.9 environment remains unverified locally.
Raw argv, versions, phase durations, JUnit and collection/outcome audits are in
ignored `.ansible/test-prune-393d0aca/`.

The four affected modules were measured alone, with fresh private fixture trees
and unchanged dependencies/parallelism; OS caches were not reset:

```bash
python -m pytest tests/unit/test_workstation.py tests/unit/test_workstation_tooling.py \
  tests/unit/test_service_catalog_filter.py tests/unit/test_service_definition_style.py \
  -q --tb=short --durations=0 --basetemp=... --junitxml=...
```

Before/final after: 181/170 passed; process wall 147.53s/144.98s; summed JUnit durations
(including setup/teardown) 146.993s/144.436s. Eliminated baseline work is 3.862s;
other variation is not attributed to pruning. No GitHub CI speedup is established.
Baseline fast unit also passed 2,210 cases in 42.57s pytest time.

Retained costs include repeated role-copy setup (up to 0.14s), Ansible dispatch,
deb822 migrations (8.42s/8.16s), collection discovery (6.21s/6.13s), operator
shared preparation (24.77s) and capture reuse (41.50s). Existing compiler and
prepared-state caches preserve private mutable fixtures; no cache changes were made.

The four CI selections below ran with profiling flags as above. Collection and
JUnit confirm one outcome per selected case, with complete, disjoint coverage:

| Group | Before collected | After collected | Final validation / pytest elapsed |
| --- | ---: | ---: | --- |
| Fast unit | 2,210 | 2,206 | 2,206 passed / 46.67s |
| HAProxy operator | 73 | 73 | 73 passed / 522.61s |
| Integration 0 | 495 | 495 | 486 passed, nine skipped / 636.78s |
| Integration 1 | 757 | 750 | 749 passed, one skipped / 1,886.74s |

`tests/unit` collection: **3,535 → 3,524** (net minus 11; 3,523 node IDs unchanged,
four layout parameters replaced by one case). Total: **3,514 passed, ten existing
environment-dependent skips**: four promtool, three local `postgres` OS-account
and three ShellCheck checks. No helper/fixture became unused. The unit group was
rechecked after refining the clone guard, briefly overlapping integration 0;
the operator ran alone. Full-group timings are validation, not a before/after
performance comparison.
Ruff check/format passed all 100 unit-test Python files; `git diff --check` passed.

## Fixture preparation and integration balancing

Follow-up on `f8b8acd9` retains all 3,524 cases from the pruning change. Saved
JUnit/duration reports show 636.78s versus 1,886.74s integration jobs: module-name
hashing placed native services (389.35s), firewall preflight (258.31s), container
installation (153.11s), repository migration (124.30s), workstation (113.90s) and
system tests (112.02s) together. Reported setup/call costs were 77.63s/557.01s
and 148.06s/1,736.17s respectively; teardown was below reporting resolution.

The shared system fixture's consumers accounted for roughly 190s of setup,
repeatedly copying and parsing/rewriting seven roles. A session fixture now
prepares those immutable inputs once. Every case gets physical copies, fresh
configuration, inventory, state, action/filter paths and Ansible processes.
No loader, environment, runtime state or mutable task tree is shared. A regression
check poisons copied role/plugin/filter files and verifies the source stays intact.

The identical 23-case before/after sample passed in **150.29s/141.66s process wall
time**. Shared-fixture consumers' reported setup fell **11.42s → 1.46s**, with
execution **12.35s → 12.23s**. The sample includes native-service and repository
migration controls and Bazarr's after-removal recovery. Eleven focused main-entry,
isolation and partition checks also passed. Same Python 3.13.5, pytest 9.1.1,
Ansible 2.21.5, dependencies and serial execution; fresh private fixture trees,
OS caches not reset. No installations, new skips or removed cases.

The two integration jobs now greedily balance measured module costs, keeping
modules together. Estimates were generated by summing prior JUnit case times
by module; unknown modules still run, and obsolete estimates cannot select tests.
The two new regressions cover independent copies and deterministic balancing with
unknown/stale module names. Collection is 3,526: unit 2,207, operator 73,
integration 0/1 604/642; the four selections are complete and disjoint.

Retained costs are deliberate: repository migration launches five independent
Ansible runs per case for check mode, migration, convergence, legacy-only changes
and fresh installation. Saved task timestamps attribute about 0.9s per real
deb822 module call, not just startup. Native execution spends time loading the
real catalog and planning namespaces; Bazarr's Swarm build/attach tasks take
roughly 10–11s/7–9s per invocation. These real entry/rendering paths, recovery,
ownership and secret isolation remain; none were replaced with YAML assertions
or shortened waits. The disabled VM lane and missing protected rootless Podman
certification do not replace any Python coverage. Production code is unchanged.

Raw focused argv, reports and final collection evidence are retained locally in
ignored `.ansible/test-performance-f8b8acd9/`. Existing dependency/pin differences
and unavailable tools listed above remain. Published CI wall time is unmeasured.

One final, serial four-group round passed **3,516 cases with ten existing skips**.
JUnit outcomes match the complete, disjoint collection exactly once; all 3,524
original cases remain. The skips are four promtool, three local `postgres`
OS-account and three ShellCheck checks. Ruff check/format (101 files), JSON
parsing, whitespace and the existing workflow/gate regressions passed.

| Group | Reported baseline | Final local pytest elapsed | Final result |
| --- | ---: | ---: | --- |
| Unit | 46.67s | 41.67s | 2,207 passed |
| Operator | 522.61s | 438.54s | 73 passed |
| Integration 0 | 636.78s | 1,181.84s | 595 passed, nine skipped |
| Integration 1 | 1,886.74s | 1,121.94s | 641 passed, one skipped |

The longest measured group is now integration 0: **1,181.84s versus 1,886.74s**
previously. Integration jobs are 59.90s apart. This is measured job balancing,
not a claim about published CI end-to-end time, runner setup or quality jobs.
Cumulative reported integration setup fell **225.69s → 50.59s**; that is summed
phase cost, not parallel wall time. Cumulative execution was 2,293.18s/2,248.93s;
execution savings are not attributed to this setup-only change. The unchanged
operator also varied materially, so its faster run is not an optimization claim.
The 16 focused rejection cases recorded identical operations after normalizing
private paths. No production files, workflows or dependencies changed.

## Optional Molecule VM tests

The [disposable VM system](../molecule/README.md) shares a serial Proxmox/cloud-init
lifecycle across Debian 13, Fedora 44, Rocky 10.2 and Ubuntu 26.04. It prepares
private inventory and trusted SSH without NetBox or Tailscale. Native Node
Exporter, runtime installation/coexistence, representative catalogue lifecycles
and protected traffic are distinct scenario families. See the
[acceptance summary](../molecule/README.md#recorded-acceptance) for recorded live results; syntax and simulated
failure tests alone do not establish functional acceptance. Public PR CI has no
infrastructure credentials. A separately enabled, protected controller workflow
runs trusted VM cases within an explicitly approved allocation.
The optional-tooling CLI regressions in `tests/molecule` run in the quality job
with SSH blocked. The existing `tests/unit` commands do not require Molecule.

## Task fixtures and safety assertions

Prefer running a supported role/task entry point with external I/O replaced.
Assert its output, generated configuration, selected hosts, commands, failure
status, cleanup and unchanged data. Task display names, exact task counts and
complete phase sequences are not operating contracts.

This pass audits the HAProxy preflight/route-capture/projection fixtures, related
firewall preflight/recovery fixtures, and rootless planning/network assertions:

| Coupling found | Contract and treatment |
| --- | --- |
| HAProxy collection selected up to an optional projection name/condition | Execute collection through candidate evidence writes; identify the two boundaries by command operation and consumed result, independent of projection structure. Keep all five async scenarios and their output/failure assertions. |
| Projection and IPv6 fixtures selected only top-level tasks | Preserve parent guards, vars and tags when selecting the required validation/output section. Names and equivalent block grouping may change. |
| Delegation fixtures selected a play's first task or a named collection task | Find the operation tag and collector command; exercise effective connection, host identity, result aggregation and sanitized failures. |
| Firewall recovery replaced the second/last task's block | Find the block through its cancellation/containment action and run its actual rescue. Block ownership is meaningful here; list position is not. |
| Rootless check mode required a long list of skipped task names | Verify generated artifact kinds/paths, secret-free output, runtime-command sentinels, account and filesystem snapshots, and whether the removal adapter was reached. |
| Podman tests froze the complete phase order, old error wording and network-task count | Remove these snapshots. Keep narrow validation-before-write and stop-before-delete checks; execute the complete network-change entry point for update/recreate in normal/check mode with host commands forbidden. |
| Protocol JSON, policy union, namespace maps and hook results compared exactly | Retain: these are data/identity or enforcement contracts, not YAML/task snapshots. |

`tests/unit/ansible_task_cases.py` is a small test-only walker/section selector
for cases where a complete entry point cannot safely use the fixture hosts.
The async fixture uses local simulated workers, which cannot satisfy the real
SSH-only host contract. The projection must not invoke preceding live discovery;
the IPv6 fixture must not proceed into account preparation. Section selection
requires unique, ordered execution boundaries and fails clearly if incomplete.
It preserves enclosing block directives and refuses to slice recovery blocks;
those must be exercised through their entry point. Mutable task trees remain
case-local. No production test interface is exported.

Retain structural checks when they directly enforce a safety boundary:

- Applied tags prevent a selected include from silently skipping guards.
- Delegation and runtime ownership keep filesystem/runtime work on its owner.
- Check-mode guards and command sentinels prevent live mutations during planning.
- `no_log`/`diff` boundaries prevent credentials entering output.
- Validation before writes, stopping before cleanup, and rescue propagation
  prevent partial mutation, simultaneous writers and false success.

Use a narrow module/argument or result property for these checks rather than an
entire task dictionary. Comments should explain the concrete failure. The
existing isolated operator/kernel, policy-transaction and rollback tests remain
responsible for runtime isolation and recovery behaviour; task-source substring
checks cannot replace them.

Validation on base `a0578cde` plus this test-only patch used Python 3.14.4,
pytest 9.1.1 and `/opt/ansible/ansible-venv`. The final complete unit run passed
2,630 cases with three existing ShellCheck-unavailable skips in 853.79 seconds.
Three incidental static cases were removed and two network entry-point cases
added (2,633 collected, net minus one). No new skips were added. Temporary
renames/regrouping passed 23 selected cases in 69.26 seconds; dropping collected
reports from candidate input caused the existing success scenario to fail in
6.57 seconds. All temporary production edits were restored byte-for-byte.
Evidence is retained locally under `.pytest_cache/task-coupling-a0578cde/`.
These are serial local validation timings, not a claimed CI speedup. Ruff
0.16.8 passed affected checks/formatting; the repository pins 0.17.0, which was
not available locally. No dependencies or generated documentation changed.

## CI events and required checks

Feature branches validate on `pull_request` (including PR updates), not on
`push`. Push validation is restricted to `main`. Both events keep the existing
path filters. Concurrency uses the workflow name plus PR number, falling back to
the branch ref for pushes: a newer revision cancels its superseded run without
cancelling another PR or branch. The Renovate Docker tag-only fast path is
unchanged.

The final required `lint` job runs with `always()` and requires successful
`quality` and test-matrix results. Failed, cancelled or unexpectedly skipped
required jobs fail the gate. Intentional Renovate fast-path step skips still
finish their classifier jobs successfully.

## Fast tests and integration tests

Mark tests that start Ansible, a shell, compiler, subprocess or an isolated
operator workflow with `@pytest.mark.integration`. Mark consumers of fixtures
that launch those processes too. Pure production-function, parser, rendering and
fake-kernel tests stay unmarked. A function-scoped process guard rejects an
unmocked `subprocess.Popen` in fast tests; it does not replace the kernel
isolation used by operator tests.

CI runs these four groups concurrently on separate GitHub runners:

```bash
python -m pytest tests/unit -m 'not integration' --durations=30 --durations-min=1
python -m pytest tests/unit/test_haproxy_operator_workflow.py -m integration --durations=30 --durations-min=1
python -m pytest tests/unit -m integration --ignore=tests/unit/test_haproxy_operator_workflow.py --integration-shard=0/2 --durations=30 --durations-min=1
python -m pytest tests/unit -m integration --ignore=tests/unit/test_haproxy_operator_workflow.py --integration-shard=1/2 --durations=30 --durations-min=1
```

The dominant HAProxy operator module has its own runner. Other integration
modules are assigned largest-estimate-first to the least-loaded shard, with
module path and shard index breaking ties. `tests/integration-durations.json`
records summed JUnit case durations from the prior validated run. It is a load
estimate, not a selection allowlist: every collected module is assigned, and
unseen modules use a one-second estimate. Stale entries are ignored. All
parameters and module-scoped fixtures stay together. Both shards must use the
same collection/selection arguments. No third-party scheduler is needed;
without selection arguments, pytest still runs every test. Keep estimates fixed
through a validation round; refresh them from measured JUnit reports when load
changes materially, not from test counts.

The existing required `lint` check depends on both `quality` and the entire test
matrix. It runs even after failures/cancellation and rejects anything except
successful dependencies. Matrix fail-fast is disabled so one failing group does
not cancel evidence from others. The existing Renovate tag-only classifier still
permits its original fast path; normal code changes run both test categories.

Separate runners isolate environment, filesystem paths and processes. Within a
group tests remain sequential. Mutable inventories, files, kernel simulators,
ports and process state remain case-local. Local concurrent validation must also
use separate `--basetemp`, TMPDIR, Ansible temporary directories and log paths.
Tests using `/opt/codex-rootless-check-*` names include their pytest process PID.
No live runtime sockets or production secrets may be made available to fixtures.

## Reused setup and test clocks

The migration contract module caches parsed catalog data and compiled Jinja
objects. Each catalog call returns a deep copy; template renders create fresh
contexts. Tests still exercise every real base/target declaration and strict
negative input combination.

HAProxy fixtures compile Python dependencies once, then copy them into each
private case. Cached dependencies are not symlinked into an isolated child.
Preparation snapshots, journals, policy, rollback files and runtime state remain
independent. Python bytecode caching is allowed only within the existing kernel
filesystem boundary. Landlock/seccomp still deny production paths and sockets. A concurrent run
exposed intermittent denial of the old host-procfs UUID read used only for a
temporary-unit nonce. That benign nonce now comes from the command fixture; the
host proc-file exception was removed and direct access is explicitly tested as
denied. No filesystem/network permissions were broadened. Tests explicitly check dependency-copy independence and kernel denial.

Go projection tests share a session-scoped compiler cache, not their sources,
binaries, templates, inputs or results. Builds retain offline toolchain settings.

`tests/fixtures/ansible/retry_playbook.py` runs real Ansible with a short controller
backoff clock only for fake-I/O firewall lifecycle tests. Retry conditions, attempt
budgets, module execution, rescue and final failure status are unchanged. The
clock records requested sleeps; tests compare them with actual attempts. It does
not alter monotonic time, remote clocks, operation deadlines or the real watcher
lock tests. Never use this launcher for live operations.

## Performance evidence

Baseline source: `495efb1e61c3336e0ce8304bee1d03a9ecad716e`. Local profiling used
Linux x86_64, eight available CPUs, Python 3.14.4 and the existing
`/opt/ansible/ansible-venv`. No dependencies were installed or upgraded.

The prior GitHub run `39567777224`, source `f3b016a3`, reported 2,624 passed and
10 skipped in 1,786.36s on Python 3.14.8. Its module timestamp estimates motivated
profiling; they are not individual test timings or directly comparable to this
local environment or revision.

A fixed nine-case local sample covered two real HAProxy maintenance outcomes,
two catalog contract cases, both complete rootless check-mode paths, successful
and failed-start firewall orchestration, and real delegated preflight collection.
Both runs used identical node IDs and
`pytest <nodes> --durations=30 --durations-min=1 -q`, with an isolated report hook
recording setup/call/teardown separately, including phases below one second.

| Measured work | Before | After |
| --- | ---: | ---: |
| Nine-case elapsed time | 127.80s | 81.93s |
| Aggregate setup | 15.557s | 14.363s |
| Aggregate execution | 111.874s | 67.121s |
| Aggregate teardown | <0.01s | <0.01s |
| mgt catalog/Quadlet contracts | 17.94s | 0.59s |
| worker route contracts | 25.85s | 0.50s |
| HAProxy successful maintenance execution | 28.39s | 26.49s |
| HAProxy deployment-failure/rollback execution | 16.14s | 15.25s |
| Persistent firewall failure, separate fixed-case measurement | 62.33s | 2.35s |

The HAProxy sample setup includes its shared preparation run, not just directory
copying. Its modest improvement is why CI gives that module a dedicated runner.
Real Ansible module transfers and complete shell/rollback execution remain major
costs. That performance pass removed no scenarios. The focused pruning below
removes duplicated assertions; shipped helpers' distinct ownership, identity, delegation,
tags, rollback, interruption and failure-status cases remain relevant. Real
advisory-lock coverage is retained.

Local raw profiles and CI log excerpts are retained outside Git in
`.pytest_cache/performance-495efb1/`. Changed-runner CI timing remains unmeasured
until the workflow is published; local parallel wall time is not a claimed
GitHub speedup. Duration reporting remains in every CI pytest invocation for
future decisions.

That prior performance validation collected 2,671 cases: all 2,655 previous
cases remained, with 16 new cases for partition/gate behaviour, clock isolation and immutable-input
independence. Original parameter and skip decorators were preserved. The four
actual CI collection commands were checked for complete, disjoint coverage.

The local concurrent round finished in 443.07s, including three operator-fixture
UUID-read failures. Only that affected group was repeated after the stricter
fixture correction. Final results were 2,668 passed and the same three existing
Shellcheck skips; no new skips or xfails were introduced:

| Required group | Final passing cases | Existing skips | pytest elapsed |
| --- | ---: | ---: | ---: |
| Fast unit | 2,024 | 0 | 44.51s |
| HAProxy operator, corrected rerun | 85 | 0 | 374.99s |
| Integration 0 | 310 | 2 | 440.93s |
| Integration 1 | 249 | 1 | 327.09s |

These group times include local shared-host load; there was no second full
round. Remaining costs include rootless check-mode orchestration (107.53s of
execution across its cases), retained Prometheus scrape compatibility tests
(90.30s), and complete HAProxy shell/recovery workflows. Setup/teardown were
recorded separately; the longest non-operator case setup was 5.30s and the longest
teardown was 0.013s. These measurements do not include GitHub runner setup
or dependency installation, and do not claim a clean published CI speedup.

## Focused CI and test pruning

The follow-up starts from `8320dfeb8c7d97ee202515f01f59adfbf0f854ca`, using the
same local Python 3.14.4/pytest 9.1.1 environment. It removes 13 collected cases,
adds four CI event/concurrency/result-gate cases, and retains 2,658 existing
node IDs unchanged. No skips or xfails were added. The four group commands and
all quality/classifier/gate job implementations remain unchanged.

| Removed or consolidated behaviour | Cases removed | Coverage retained |
| --- | ---: | --- |
| Homepage's migrated declaration and removed Docker files/image-copy snapshot | 2 | Catalog-wide strict normalization and real Quadlet generation; generic rootless mount/account/cleanup tests. Homepage's allowed-host/environment/Traefik render remains. |
| Repeated Adminer/The Lounge catalog, namespace and literal port/mount snapshots | 5 | `test_real_podman_definitions_use_only_canonical_adapter_inputs`, the all-mgt generator test, generic Quadlet/keep-id/LinuxServer entrypoint and managed-file tests. The now-unused `real_rootless_service` renderer and Adminer-only catalog loader were removed. |
| Sonarr's literal migrated target snapshot | 1 | Effective target merge tests, all four arr credential/API inheritance cases, unique worker publications and inventory-backed Traefik rendering. |
| Romm's literal seed and migrated volume-layout snapshot | 1 | Real deployment/configuration tests still exercise the seed, retained settings, no overwrite, convergence, tags, check mode and invalid/legacy config rejection. Romm's supported preparation handler remains tested. |
| Scan for identifiers from an already removed compatibility implementation | 1 | Current catalog/adapter contract and secret-interface tests; the removed plugin/identifiers have no supported compatibility contract to preserve. |
| HAProxy-specific duplicate of generic ACL/ownership/selection gates | 1 | Strict missing/false/typed acknowledgement cases, real target merges, planning/recovery paths, and actual before-placement readiness/continuation tests. |
| Replay of the obsolete broken Gotify payload | 1 | Actual current Go payload rendering still exercises firing/resolved, colon-bearing titles, scalar-like summaries, quoting and Unicode. Sanitized diagnostic and partial-failure coverage remains. |
| Separate successful HAProxy prepare plus maintenance for Forgejo endpoint preservation | 1 | The shared installed-policy fixture now includes Forgejo. Preparation verifies the complete baseline and retained binding; existing maintenance/rollback scenarios verify the endpoint survives. No distinct failure scenario was removed. |

The fixed worker-publication census was also replaced by a nonempty check;
uniqueness, host transport, target-port rendering and worker placement guards
remain. Tests for demonstrated port-binding, template, secret and ownership
compatibility boundaries stay; fake image versions in parser/upgrade fixtures
are inputs, not assertions freezing current service pins.

At this initial pruning stage, Go renderers, shell command fixtures and the
kernel restrictor still served retained cases; production tools and path aliases
were unchanged. The subsequent explicit retirement below removes the obsolete
Swarm configuration-patching implementations after checking their repository
callers and rollback references.

The saved baseline attributes 5.343s setup, 43.600s execution and 0.002s teardown
to the removed cases, including 42.433s execution for the separate HAProxy success
run. This measures eliminated execution work, not a guaranteed elapsed-time
saving under different shared-host load. Four-way parallelism was already in the
baseline and is not counted as a gain from this change. Avoid comparing the old
29m46s serial GitHub run directly with local parallel wall time.

Current raw collection, suite-delta, phase profiles and complete-run results are
retained outside Git in `.pytest_cache/ci-pruning-8320dfeb/`. Collection uses the
four commands extracted from the workflow and asserts a complete, disjoint union.
Offline tests check the configured event/path cases and concurrency expression;
actual GitHub scheduling/cancellation remains unverified until publication.


The complete retained-suite round passed: **2,659 passed, three existing skips**
in **433.06s wall time**, with no failed groups. Actual per-test reports confirm
every retained node ran in exactly one group. The final CI-contract check also
passed all 18 cases after refining its changed-revision context.

| Required group | Before: cases / pytest elapsed | After: cases / pytest elapsed |
| --- | ---: | ---: |
| Fast unit | 2,024 / 44.51s | 2,015 / 42.20s |
| HAProxy operator | 85 / 374.99s | 84 / 359.10s |
| Integration 0 | 312 (two skips) / 440.93s | 312 (two skips) / 431.29s |
| Integration 1 | 250 (one skip) / 327.09s | 251 (one skip) / 313.88s |
| Complete collection | 2,671 | 2,662 |

These are local shared-host measurements, including previously retained baseline
results; differences in unchanged groups are measurement variability, not work
removed by this patch. The longest group remains integration 0. Its real Ansible
check-mode, reload and recovery paths remain intentional costs. Setup, execution
and teardown totals are saved separately in `final-validation.json`.

The three skips are the unchanged logical-backup, remote-backup and restore
validator Shellcheck checks: Shellcheck is unavailable. Workflow YAML lint,
Python parsing, all 108 CI-target Python files' Ruff check/format checks, and
`git diff --check` passed. Local Ruff is 0.16.8 versus pinned 0.17.0, so that
result is advisory for the pinned CI check; Ansible is 2.21.4 versus pinned
2.21.5. No dependencies were installed. `actionlint` is unavailable. GitHub
workflow execution and the exact pinned toolchain remain CI validation, not
claims from these offline checks.

## Retired Swarm configuration patching and HAProxy consolidation

This follow-up starts from the preceding 2,662-case working patch on
`8320dfeb8c7d97ee202515f01f59adfbf0f854ca`. It retires the unsupported
configuration-patching tasks, their identity/restore helpers, three patch filters
and the sole Swarm-specific reload handler. Repository references were limited
to these implementations, their tests and generated documentation; no retained
repository rollback recipe imports them. Private rollback material was neither
inspected nor changed. The old operation tags continue to reject execution.
See [retired paths and supported replacements](service-firewall.md#manual-workflows-and-compatibility).

The retired coverage is exactly 17 Docker HAProxy-scrape compatibility cases,
25 Alertmanager/Scraparr patch cases and 18 Loki ruler patch/rollout cases.
Both current HAProxy scrape-template cases (`docker` and `podman`) remain
unchanged. Their templates also remain included by canonical Prometheus
configuration. Embedded command fixtures and the test-only recovery helpers
inside the deleted cases leave with those cases. The synthetic retry launcher
remains used by current firewall lifecycle tests.

HAProxy input combinations now call the production `ready`, `deployment`,
`continuation_state`, `continuation_policy` and `hooks` functions with isolated
external I/O. Representative real-runner rejection cases remain for unaccepted
callers/ownership, invalid continuation state, stale installed policy and unsafe
mounts. Existing fast mount projection/overlap tests retain missing-RW and direct
consumer coverage. No production validation was extracted, simplified or bypassed.

All distinct placement, policy-write, deployment, probe-expiry, observation
cleanup, continuation, interruption, terminal-output and scoped-rollback scenarios
remain under the same kernel filesystem/socket restrictions. The six tests that
need a completed route capture now copy one module-scoped resumed baseline,
replacing six identical initial resume executions with one. Each copy has its
own policy, inputs, logs, journals, runtime state and rebased evidence paths;
a regression edits copied evidence and proves the shared baseline is unchanged.

The preceding local profile measured 213.77s aggregate execution in the retired
compatibility cases. Four-way CI parallelism is unchanged. Final group timings
and collection checks below distinguish eliminated execution from elapsed time.


Final collection is **2,627 cases**, down from 2,662: 60 obsolete cases were
retired, and 12 repeated operator parameter executions were replaced by fast
validation coverage. There are 36 new direct-validator cases and one additional
copy-isolation case. The operator module now has 73 cases instead of 84.
Four representative runner tests retain the execution boundary for combinations
moved to the fast tests; renamed node IDs are accounted for in `suite-delta.json`.
Two unused mount-scenario branches were removed from the command fixture after
the complete round, followed by a passing 23-case mount/projection/kernel recheck.

One complete four-group round passed: **2,624 passed and the same three
Shellcheck skips**, with **345.05s local wall time**. Both collection and actual
phase reports prove each retained case belongs to exactly one group. No skips,
xfails, dependencies or parallel groups were added.

| Required group | Previous cases / pytest elapsed | Retired/consolidated cases / pytest elapsed |
| --- | ---: | ---: |
| Fast unit | 2,015 / 42.20s | 2,030 / 42.18s |
| HAProxy operator | 84 / 359.10s | 73 / 343.62s |
| Integration 0 | 312 (two skips) / 431.29s | 287 (two skips) / 279.10s |
| Integration 1 | 251 (one skip) / 313.88s | 237 (one skip) / 260.07s |
| Complete collection / parallel wall | 2,662 / 433.06s | 2,627 / 345.05s |

Summed test execution fell from 1,108.20s to 886.82s; parallel wall time fell by
88.01s. Those are different measurements. Parallelism was already present, and
shared-host timing variability remains; no published GitHub CI timing is claimed.
The operator module is now the longest group. Its retained transaction, trap and
rollback scenarios account for most of its cost. Raw argv, collection sets,
phase reports, the initial working patch and results are retained outside Git in
`.pytest_cache/swarm-retirement-8320dfeb/`.

Additional validation passed: 98 focused function cases, the affected shell
cases (12 initially passed; the new copy test was corrected and passed), the
23-case post-cleanup recheck, remaining Docker-role syntax with a localhost-only
inventory, offline Docker-role Ansible lint, CI-target Ruff check/format, and
`git diff --check`. The first isolated lint attempt lacked repository filter
paths; the corrected isolated config passed without enabling dynamic inventory.
Ruff 0.16.8, Ansible 2.21.4 and ansible-lint 26.8.0 differ from the repository's
0.17.0/2.21.5/26.10.0 pins. Shellcheck and actionlint remain unavailable. Generated
Docker role README entries are intentionally left for the repository's Docsible
workflow; they are not retained executable imports or supported entry points.

## PR #726 CI repairs

The follow-up starts at reviewed head `d65fdd2e`. Its actual PR merge base is
`d3ad682e512132a8da714887bc82818491b5eb15`; `e49f085d` is a feature-branch
revision and cannot establish an unrelated baseline failure.

Independent `service_common` prerequisite entry points register canonical
inventory placement through their role-local `service_placement` plugin. They
do not depend on a runtime adapter or a global test-only filter path. The plugin
exports only placement resolution; runtime rendering and lifecycle remain with
the adapters. The existing independent preflight tests still require ownership
acknowledgements before any secrets, files or bootstrap interruption.

Fixture boundaries follow the current contracts:

| Family | Required fixture context and retained behaviour |
| --- | --- |
| Renovate | Extract effective Docker/Podman images after target merging; image-free native services are valid and malformed container images fail explicitly. |
| HAProxy projection/capture | Supply all catalogue placement hosts and their synthetic inventory identity; retain identity, aggregation and command-failure assertions. |
| Firewall dispatch | Isolate platform inspection with a read-only marker while exercising the real dispatcher and legacy wrappers; invalid selections cannot reach the marker. Platform tests retain the real gate. |
| Bootstrap | Pass inventory groups into planners, include copied role dependencies and declare valid placement; absent and unknown placement remain rejected. |
| RomM | Restore adapter-local filter discovery and normalized deployment type for extracted application tasks. Shared database/Compose preflight remains covered through the real adapter in `test_service_firewall_preflight.py`; file migration retains existing permissions independently of the controller umask. |
| Bazarr | Synthetic managed-host ownership follows the test process UID/GID; production defaults and lifecycle failure/recovery cases remain intact. |
| Workstation | Load synthetic container definitions and real selectors before requiring the missing inventory roles; workstation-only operations still avoid application dependencies. |

Copied-role fixtures retain the canonical filter file at its normal relative
location and reject skipped-plugin warnings, so successful cases cannot conceal
a failed common-role loader behind another discovered filter.

Checkov exceptions describe the boundary at each task/block. The eight HTTP
probes exercise the actual disposable HTTP application or verified loopback
metrics listener, without HTTP credentials. Fixed-choice VM workflow inputs
select acceptance tests and do not construct release artifacts; its disabled
state, trusted ref, environment and restricted runner requirements are unchanged.
The 15 reviewed blocks deliberately propagate failure, including existing
`always` cleanup. Checkov 3.4.3 builds their inline suppression context IDs as
`block..name` while graph IDs use `block.name`. Until upstream fixes that mismatch,
`.checkov.yml` limits the block-rule workaround to exact reviewed file paths;
other rules and files remain checked. Remove those path exceptions when block
annotations work. The equivalent cloud-init `format()` expression also lets the
scanner parse its nested HCL without changing the generated user data.

Gitleaks exclusions identify only the two historical public Docker CE and
Grafana Labs RPM signing-key findings. Validate the original CI range
`45bd39b8^..d65fdd2e` with `--no-merges --first-parent`; current-line edits alone
cannot remove historical matches. Do not rewrite history or broaden detection
exclusions. Detailed local commands, results and tooling limitations are retained
outside tracked documentation in `.ansible/pr726-ci/`.

For local Checkov validation, scan a tracked-source snapshot that includes the
working patch, rather than an operator checkout containing ignored private
inputs. Checkov automatically loads Terraform variable files; its normal
GitHub checkout has no such local files. Keep scanner reports private.
