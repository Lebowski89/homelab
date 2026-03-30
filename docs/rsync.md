# Rsync Cheat Sheet

## What rsync is for

`rsync` is a safe and flexible tool for copying or syncing files between hosts while preserving metadata and minimizing repeated transfer work.

Good for:

- migrating app data between nodes
- syncing directories over SSH or Tailscale
- previewing destructive changes before applying them
- resuming large file transfers

---

## Safe default for app data

```bash
rsync -aHAXvi --delete /source/ user@host:/dest/
```

### What the flags mean

- `-a` archive mode
- `-H` preserve hard links
- `-A` preserve ACLs
- `-X` preserve extended attributes
- `-v` verbose
- `-i` itemized changes
- `--delete` remove files on destination that no longer exist on source

This is a strong default for Docker bind-mount data, config directories, and most homelab migrations.

---

## Very important trailing slash rule

These are **not** the same:

```bash
rsync -a /opt/znc/ user@host:/opt/znc/
```

Copies the **contents** of `/opt/znc/` into `/opt/znc/` on the destination.

```bash
rsync -a /opt/znc user@host:/opt/
```

Copies the **directory itself**, so the destination becomes `/opt/znc`.

When in doubt, use the trailing slash on the source if you want the directory contents.

---

## Most useful commands

### Dry run first

```bash
rsync -aHAXvin --delete /source/ user@host:/dest/
```

Use this before the real sync to preview what will change.

---

### Real sync

```bash
rsync -aHAXvi --delete /source/ user@host:/dest/
```

This is the usual “make destination match source” command.

---

### Show progress for large transfers

```bash
rsync -aHAXv --info=progress2 /source/ user@host:/dest/
```

Useful for large datasets and slower links.

---

### Resume interrupted transfers

```bash
rsync -aHAXv --partial --append-verify /source/ user@host:/dest/
```

Good for very large files when the connection may drop.

---

### Preserve numeric UID/GID exactly

```bash
rsync -aHAXv --numeric-ids /source/ user@host:/dest/
```

Useful when Docker app data ownership matters and both systems use matching numeric IDs.

---

### Limit bandwidth

```bash
rsync -aHAXv --bwlimit=50M /source/ user@host:/dest/
```

Prevents saturating the link.

---

### Use a specific SSH key

```bash
rsync -aHAXv -e "ssh -i ~/.ssh/id_ed25519" /source/ user@host:/dest/
```

Useful when you do not want to rely on the default SSH identity.

---

### Exclude files or directories

```bash
rsync -aHAXv --exclude='*.tmp' --exclude='cache/' /source/ user@host:/dest/
```

Useful for skipping junk, temp data, or caches.

---

### Pull from remote to local

```bash
rsync -aHAXv user@host:/source/ /dest/
```

Same idea, reversed direction.

---

### Itemized output to see exactly what changed

```bash
rsync -aHAXvi /source/ user@host:/dest/
```

Very useful for understanding what rsync is doing.

---

## Best practice for app-data migration

For live services, do it in two passes:

### First sync while the service is still running

```bash
rsync -aHAXv --info=progress2 /opt/app/ user@host:/opt/app/
```

### Stop the service

### Final sync after stopping it

```bash
rsync -aHAXvi --delete /opt/app/ user@host:/opt/app/
```

This minimizes downtime while ensuring the destination is clean and current.

---

## Good commands for common homelab use

### Migrate Docker bind-mount data

```bash
rsync -aHAXvi --delete /opt/appdata/ user@host:/opt/appdata/
```

### Migrate media or large datasets

```bash
rsync -aHAXv --info=progress2 --partial --append-verify /mnt/data/ user@host:/mnt/data/
```

### Preview a destructive sync

```bash
rsync -aHAXvin --delete /opt/app/ user@host:/opt/app/
```

### Sync over Tailscale

```bash
rsync -aHAXvi /opt/app/ user@100.x.y.z:/opt/app/
```

---

## When to use `--delete`

Use `--delete` when you want the destination to become a true mirror of the source.

Good for:

- replacing app data on a new node
- keeping a target directory identical

Be careful with it because files present only on the destination will be removed.

Always dry run first if you are not completely sure:

```bash
rsync -aHAXvin --delete /source/ user@host:/dest/
```

---

## Ownership and permissions notes

If ownership matters, check the destination after syncing:

```bash
ls -lah /dest
```

If needed, verify numeric ownership:

```bash
ls -ln /dest
```

For Docker app data, matching UID/GID is often more important than matching usernames.

---

## Common mistakes

### Forgetting the trailing slash
This changes whether rsync copies the directory itself or only its contents.

### Using `--delete` without a dry run
This can remove files you did not expect.

### Syncing live app data once and assuming it is clean
For databases or active services, do a final sync after stopping the service.

### Not preserving metadata
For app data, prefer:

```bash
-aHAX
```

rather than plain `-r`.

---

## Recommended defaults

### Safest preview

```bash
rsync -aHAXvin --delete /source/ user@host:/dest/
```

### Safest real migration

```bash
rsync -aHAXvi --delete /source/ user@host:/dest/
```

### Best for huge transfers

```bash
rsync -aHAXv --info=progress2 --partial --append-verify /source/ user@host:/dest/
```

---

## Quick reference

```bash
# Dry run
rsync -aHAXvin --delete /source/ user@host:/dest/

# Real sync
rsync -aHAXvi --delete /source/ user@host:/dest/

# Large transfer with progress
rsync -aHAXv --info=progress2 /source/ user@host:/dest/

# Resume interrupted transfer
rsync -aHAXv --partial --append-verify /source/ user@host:/dest/

# Preserve numeric IDs
rsync -aHAXv --numeric-ids /source/ user@host:/dest/

# Pull remote to local
rsync -aHAXv user@host:/source/ /dest/
```