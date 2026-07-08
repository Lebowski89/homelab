# Git History Cleanup Cheat Sheet

A practical checklist for cleaning up a noisy Git history with interactive rebases, batching, backup branches, and force-push verification.

> Assumption: you are the solo maintainer or you have coordinated with collaborators. This rewrites `main` history.

---

## Golden Rules

- Do not run `git pull` during a history rewrite.
- Use `git push --force-with-lease origin main`, not plain `--force`.
- Create a `backup/before-batch-N` branch before each batch.
- Verify the final file tree is unchanged before pushing.
- During conflicts, do **not** use `git add .`; add only the specific resolved files.
- Ignore untracked generated folders, such as `.ansible/`, unless you intentionally created them and know they belong in Git.
- The actual `git-rebase-todo` can differ from a generated `git log --reverse` list. Edit the real todo Git opens.
- In an interactive rebase, `ours` means the already-rebased current state; `theirs` means the commit currently being replayed.

---

## One-Time Editor Setup

Use Nano for reliability:

```bash
git config --global core.editor "nano"
```

Or override per command:

```bash
GIT_EDITOR=nano git rebase -i <range>
```

For VS Code:

```bash
git config --global core.editor "code --wait"
```

---

## Verify Current State Before Starting a Batch

```bash
git fetch origin

git rev-parse HEAD
git rev-parse origin/main

git status --short
```

`HEAD` and `origin/main` should match before starting the next batch.

If you just completed a batch, verify the final tree matches the backup:

```bash
git diff backup/before-batch-N..HEAD --stat

git rev-parse backup/before-batch-N^{tree}
git rev-parse HEAD^{tree}
```

The diff should be empty. The tree hashes should match.

---

## Create the Next Batch Boundary

After batch `N` is complete, use its backup branch to find the oldest cleaned commit from that batch:

```bash
BOUNDARY="$(git log --reverse --format='%H' backup/before-batch-N..HEAD | head -n 1)"
echo "$BOUNDARY"
git show -s --oneline "$BOUNDARY"
```

Then create the next backup branch:

```bash
git branch backup/before-batch-$((N + 1))
```

If the branch may already exist:

```bash
git show-ref --verify --quiet refs/heads/backup/before-batch-$((N + 1)) || git branch backup/before-batch-$((N + 1))
```

---

## Generate Prep Files for Review

Normal batch:

```bash
BATCH_SIZE=120

git log --reverse --no-merges --format='pick %h %s' "$BOUNDARY"~$BATCH_SIZE.."$BOUNDARY" > /tmp/batchNEXT-picks.txt

git log --reverse --no-merges --name-status --oneline "$BOUNDARY"~$BATCH_SIZE.."$BOUNDARY" > /tmp/batchNEXT-files.txt

cat /tmp/batchNEXT-picks.txt
```

Upload or inspect both files:

```text
/tmp/batchNEXT-picks.txt
/tmp/batchNEXT-files.txt
```

The `picks` file shows commit order. The `files` file shows what each commit actually changed, which makes grouping much safer.

---

## When You Are Near the Root Commit

If this fails:

```bash
git log --reverse --no-merges --format='pick %h %s' "$BOUNDARY"~120.."$BOUNDARY"
```

with:

```text
fatal: ambiguous argument '<hash>~120..<hash>'
```

then there are not 120 parents behind that commit. Use a root batch.

Generate root prep files:

```bash
git log --reverse --no-merges --format='pick %h %s' "$BOUNDARY" > /tmp/batchNEXT-picks.txt

git log --reverse --no-merges --name-status --oneline "$BOUNDARY" > /tmp/batchNEXT-files.txt

cat /tmp/batchNEXT-picks.txt
```

Start root rebase:

```bash
git rebase -i --root
```

In the actual todo, edit only the old/root section and leave the already-cleaned commits unchanged.

---

## Start the Actual Interactive Rebase

Normal batch:

```bash
git rebase -i "$BOUNDARY"~$BATCH_SIZE
```

Root batch:

```bash
git rebase -i --root
```

When Git opens the todo, save the actual todo somewhere if needed:

```bash
cat .git/rebase-merge/git-rebase-todo > /tmp/actual-git-rebase-todo.txt
```

View progress:

```bash
git status
cat .git/rebase-merge/done
cat .git/rebase-merge/git-rebase-todo
```

Edit the todo during an active rebase:

```bash
git rebase --edit-todo
```

---

## Todo Editing Pattern

Typical squash group:

```text
reword abc1234 meaningful first commit in group
fixup def5678 small follow-up
fixup 1112223 linting
fixup 3334445 fixes
```

Use:

- `reword` for the first commit in a logical group, so you can write a clean final message.
- `fixup` for noisy follow-ups, linting, formatting, dependency pin noise, and repair commits.
- `pick` for commits that should remain separate or for already-cleaned history.
- Avoid changing order unless necessary; grouping contiguous commits is safer.

---

## Reword Message Style

Examples:

```text
feat(ansible): add Docker and Ubuntu roles
refactor(docker_services): restructure service helper tasks
fix(docker_services): stabilize swarm config templating
chore(maintenance): update service and runtime pins
docs(ansible): regenerate role documentation
ci(ansible): tighten linting and workflow paths
```

Good prefixes:

```text
feat
fix
refactor
chore
docs
ci
```

---

## Continue Through Reword Prompts

After saving the todo, Git will stop at each `reword` commit. Replace the commit message with the prepared message, save, and continue.

If you need to amend manually:

```bash
git commit --amend
```

Then:

```bash
git rebase --continue
```

---

## Conflict Triage

When Git stops:

```bash
git status --short --untracked-files=no
git show --stat --oneline REBASE_HEAD
```

This tells you which commit is being replayed and which tracked files are conflicted.

After resolving a conflict:

```bash
git add path/to/resolved-file.yml
git rebase --continue
```

Never use this during conflicts:

```bash
git add .
```

---

## Ours vs Theirs During Rebase

During a rebase:

```bash
# keep already-rebased current state
git checkout --ours path/to/file

# take the commit currently being replayed
git checkout --theirs path/to/file
```

Then:

```bash
git add path/to/file
git rebase --continue
```

Use this carefully. Do not blindly take one side for a large file unless you know that is correct.

---

## Skipping Duplicate Commits

Sometimes a duplicate commit collides with changes already included in an earlier squash group.

Inspect first:

```bash
git show --stat --oneline REBASE_HEAD
git status --short --untracked-files=no
```

If it is clearly duplicate noise already represented in the squashed result:

```bash
git rebase --skip
```

After the whole batch finishes, verify with:

```bash
git diff backup/before-batch-N..HEAD --stat
```

If the diff is empty, the skip did not change the final tree.

---

## Empty Commit During Fixup

You may see:

```text
You asked to amend the most recent commit, but doing so would make it empty.
```

This often happens with early README churn or add/remove/re-add sequences.

If the next fixup will re-add or complete the logical commit, allow the temporary empty state:

```bash
git commit --amend --allow-empty --no-edit
git rebase --continue
```

If the commit is truly redundant and should disappear:

```bash
git rebase --skip
```

---

## Abort a Batch

Abort the active rebase:

```bash
git rebase --abort
```

Check you are back to the pre-rebase state:

```bash
git status --short
git diff backup/before-batch-N..HEAD --stat
```

---

## Recover From a Bad Batch

Reset to the backup branch:

```bash
git reset --hard backup/before-batch-N
```

Or inspect reflog:

```bash
git reflog --date=local --oneline | head -50
```

Reset to a known good reflog entry:

```bash
git reset --hard <hash>
```

---

## Final Batch Verification

After the rebase completes:

```bash
git status --short

git diff backup/before-batch-N..HEAD --stat

git rev-parse backup/before-batch-N^{tree}
git rev-parse HEAD^{tree}
```

Expected:

- `git diff ... --stat` is empty.
- Tree hashes match.
- No tracked changes in `git status --short`.

Untracked generated folders can be ignored or removed if you are sure they are not needed:

```bash
rm -rf .ansible
```

Only do that if they are truly generated leftovers and not real project files in your current tree.

---

## Push Rewritten Main

```bash
git push --force-with-lease origin main
```

Verify:

```bash
git fetch origin

git rev-parse HEAD
git rev-parse origin/main
```

The two hashes should match.

Count commits:

```bash
git rev-list --count HEAD
```

Show recent cleaned history:

```bash
git log --oneline --decorate -40
```

---

## Useful Inspection Commands

Show branch graph:

```bash
git log --oneline --decorate --graph --all -40
```

Show oldest commits:

```bash
git log --reverse --oneline | head -50
```

Show newest commits:

```bash
git log --oneline -50
```

Show changed files in a commit:

```bash
git show --stat --oneline <commit>
```

Show name-status changes in a range:

```bash
git log --reverse --no-merges --name-status --oneline <range>
```

Find root commit:

```bash
git rev-list --max-parents=0 --oneline HEAD
```

Count commits behind a boundary:

```bash
git rev-list --count "$BOUNDARY"
```

---

## Standard Batch Template

Replace `N` and `NEXT`.

```bash
# verify current state
git fetch origin
git rev-parse HEAD
git rev-parse origin/main
git status --short
git diff backup/before-batch-N..HEAD --stat

# find boundary from previous batch
BOUNDARY="$(git log --reverse --format='%H' backup/before-batch-N..HEAD | head -n 1)"
echo "$BOUNDARY"
git show -s --oneline "$BOUNDARY"

# backup before next rewrite
git show-ref --verify --quiet refs/heads/backup/before-batch-NEXT || git branch backup/before-batch-NEXT

# prep files
BATCH_SIZE=120

git log --reverse --no-merges --format='pick %h %s' "$BOUNDARY"~$BATCH_SIZE.."$BOUNDARY" > /tmp/batchNEXT-picks.txt

git log --reverse --no-merges --name-status --oneline "$BOUNDARY"~$BATCH_SIZE.."$BOUNDARY" > /tmp/batchNEXT-files.txt

cat /tmp/batchNEXT-picks.txt

# actual rebase
git rebase -i "$BOUNDARY"~$BATCH_SIZE

# after rebase
git status --short
git diff backup/before-batch-NEXT..HEAD --stat
git rev-parse backup/before-batch-NEXT^{tree}
git rev-parse HEAD^{tree}

# push
git push --force-with-lease origin main

# verify remote
git fetch origin
git rev-parse HEAD
git rev-parse origin/main
git rev-list --count HEAD
```

---

## Standard Root Batch Template

Use when `BOUNDARY~BATCH_SIZE` does not exist.

```bash
# verify current state
git fetch origin
git rev-parse HEAD
git rev-parse origin/main
git status --short

# find boundary from previous batch
BOUNDARY="$(git log --reverse --format='%H' backup/before-batch-N..HEAD | head -n 1)"
echo "$BOUNDARY"
git show -s --oneline "$BOUNDARY"

git rev-list --count "$BOUNDARY"
git rev-list --max-parents=0 --oneline "$BOUNDARY"

# backup
git show-ref --verify --quiet refs/heads/backup/before-batch-NEXT || git branch backup/before-batch-NEXT

# prep root section
git log --reverse --no-merges --format='pick %h %s' "$BOUNDARY" > /tmp/batchNEXT-picks.txt

git log --reverse --no-merges --name-status --oneline "$BOUNDARY" > /tmp/batchNEXT-files.txt

cat /tmp/batchNEXT-picks.txt

# actual root rebase
git rebase -i --root

# after rebase
git status --short
git diff backup/before-batch-NEXT..HEAD --stat
git rev-parse backup/before-batch-NEXT^{tree}
git rev-parse HEAD^{tree}

# push
git push --force-with-lease origin main

# verify
git fetch origin
git rev-parse HEAD
git rev-parse origin/main
git rev-list --count HEAD
```
