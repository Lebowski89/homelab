# Repository test execution

Use `/opt/ansible/ansible-venv/bin/python -m pytest tests/unit` for the complete
suite. Tests use synthetic inventories, fake external I/O and private temporary
state. They do not establish live application or firewall acceptance.

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

The dominant HAProxy operator module has its own runner. Other integration tests
are assigned by a stable hash of the module filename. All parameters and
module-scoped immutable fixtures stay on the same runner. No third-party pytest
scheduler is needed. Without selection arguments, pytest still runs every test.

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
backoff clock only for fake-I/O firewall/reload tests. Retry conditions, attempt
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
costs. No scenarios were removed: completed migration helpers still ship, and
their distinct ownership, identity, delegation, tags, rollback, interruption and
failure-status cases remain relevant. Real advisory-lock coverage is retained.

Local raw profiles and CI log excerpts are retained outside Git in
`.pytest_cache/performance-495efb1/`. Changed-runner CI timing remains unmeasured
until the workflow is published; local parallel wall time is not a claimed
GitHub speedup. Duration reporting remains in every CI pytest invocation for
future decisions.

Final validation collected 2,671 cases: all 2,655 previous cases remain, with 16
new cases for partition/gate behaviour, clock isolation and immutable-input
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
