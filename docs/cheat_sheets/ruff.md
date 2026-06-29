# Ruff Cheatsheet

Useful Ruff commands for this homelab repo.

## Main paths

```bash
RUFF_PATHS="\
ansible/filter_plugins \
ansible/roles/docker_services/filter_plugins \
ansible/roles/docker_services/library \
tests/unit"
```

Or use the paths directly in commands.

## Check and auto-fix lint issues

```bash
ruff check --fix \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit
```

Use this for most day-to-day fixes. It handles safe automatic fixes.

## Format files

```bash
ruff format \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit
```

Use this after `ruff check --fix`.

## Check only, no changes

```bash
ruff check \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit
```

Useful before committing or in CI.

## Format check only, no changes

```bash
ruff format --check --diff \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit
```

Shows what Ruff would format without modifying files.

## Full local Ruff pass

```bash
ruff check --fix \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit

ruff format \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit
```

## CI-style Ruff pass

```bash
ruff check \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit

ruff format --check --diff \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit
```

Use this when you want to match what CI should enforce.

## Run Ruff on one file

```bash
ruff check --fix ansible/roles/docker_services/filter_plugins/docker_services_stack_resources.py
ruff format ansible/roles/docker_services/filter_plugins/docker_services_stack_resources.py
```

Useful when working on a single filter.

## Run Ruff on one test file

```bash
ruff check --fix tests/unit/test_docker_services_stack_resources_filter.py
ruff format tests/unit/test_docker_services_stack_resources_filter.py
```

## Show detailed error explanation

```bash
ruff rule SIM108
```

Example:

```bash
ruff rule I001
ruff rule SIM118
ruff rule PLR0912
```

Useful when Ruff gives a rule code and you want to know what it means.

## Apply unsafe fixes

```bash
ruff check --fix --unsafe-fixes \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit
```

Use carefully. Ruff will apply fixes that may change behaviour in edge cases.

Prefer reviewing the diff afterwards:

```bash
git diff
```

## Show fixes without applying them

```bash
ruff check --diff \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit
```

## Fix only import sorting

```bash
ruff check --fix --select I \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit
```

Useful when imports are the only problem.

## Check only specific rule families

```bash
ruff check --select I,SIM,F,UP \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit
```

Common useful groups:

| Prefix   | Meaning                     |
| -------- | --------------------------- |
| `F`      | Pyflakes correctness checks |
| `E`, `W` | pycodestyle errors/warnings |
| `I`      | import sorting              |
| `UP`     | pyupgrade                   |
| `SIM`    | simplify code               |
| `B`      | bugbear bug-prone patterns  |
| `PL`     | pylint-style rules          |
| `RUF`    | Ruff-specific rules         |

## Ignore one rule temporarily on a line

```python
value = some_complex_expression()  # noqa: SIM108
```

Use sparingly. Prefer fixing the issue if the Ruff suggestion is reasonable.

## Ignore multiple rules on a line

```python
value = some_complex_expression()  # noqa: SIM108,PLR2004
```

## Ignore all Ruff checks on a line

```python
value = some_complex_expression()  # noqa
```

Avoid this unless there is a very good reason.

## Exclude a file from Ruff in `pyproject.toml`

```toml
[tool.ruff]
exclude = [
  "some/generated/file.py",
]
```

## Per-file ignores in `pyproject.toml`

```toml
[tool.ruff.lint.per-file-ignores]
"tests/unit/*.py" = ["PLR2004"]
```

Useful when tests intentionally use magic values or patterns that production code should avoid.

## Current recommended local gate

```bash
ruff check --fix \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit

ruff format \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit

python -m pytest tests/unit

skynet check all
```

## Current recommended CI-style gate

```bash
ruff check \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit

ruff format --check --diff \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit

python -m pytest tests/unit
```

## Typical workflow

```bash
# 1. Make code changes

# 2. Auto-fix lint
ruff check --fix \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit

# 3. Format
ruff format \
  ansible/filter_plugins \
  ansible/roles/docker_services/filter_plugins \
  ansible/roles/docker_services/library \
  tests/unit

# 4. Run tests
python -m pytest tests/unit

# 5. Run Ansible repo check
skynet check all

# 6. Review changes
git diff
```

## When Ruff suggests a bad change

Do not blindly accept it. Either keep the clearer code and add a targeted `noqa`, or adjust `pyproject.toml`.

Example:

```python
if value is None:
    return []

# noqa is better than making this unreadable
```

Use:

```python
# noqa: SIM108
```

only on the specific line that needs it.
