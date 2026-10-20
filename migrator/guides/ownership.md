# Persistent-data ownership during a runtime migration

Record private numeric ownership, permissions, ACLs, file identities and consistent
backups for every approved data root. Obtain host identity, roots and application
UID/GID from inventory and actual processes, not guessed account numbers.

1. Prepare only the selected account/store through the existing execution-only
   role operation. Do not deploy files, images, secrets or listeners during this
   step. A selected mapping probe requires its own authorized scope.
2. Prove the actual old container/process mapping and exact selected new keep-id
   mapping. Compare integer mapping triples, ignoring whitespace. Default
   `podman unshare` is not proof of the selected container's mapping.
3. Stop only the old writer and prove it exited. Create a NEW consistent paired
   database/files/ACL baseline and verify restoration before changing ownership.
   Refresh the stopped manifest; reject unexpected paths/owners/identities.
4. Translate UID and GID separately through the observed maps for each exact path.
   Preserve mixed root/application ownership, symlinks, mount boundaries and ACL
   identities. No blanket recursive chown. Resolve unsupported ACL cases explicitly.
5. Group hard-linked regular files by device/inode, retaining all names. Require
   collected names to account for link count wholly within the approved roots,
   consistent translations across members and unchanged identities. Change owner
   once per inode, then verify every name, topology, mode/ACL and content.
6. Verify data/secret traversal and application read/write access. Complete
   `services_rootless_data_ready` only for the actual service name after observed
   transition proof. Account-only preparation/check mode needs no ownership
   acknowledgement; deployment does. Selection tags never activate this safeguard.
7. For rollback stop the replacement writer first, retain post-cutover material,
   restore the matching paired database/files/ownership/ACL baseline, then restore
   only the recorded Docker application. Explain loss of post-backup changes.

Use `utility-preparation.py` ownership inventory/apply/verify/archive helpers and
`znc-mapping-proof.py` numeric-map functions where their actual input contracts
apply. Those helpers retain stable paths for existing recovery recipes. The
[migrator workspace](../README.md) provides a private plan/evidence layout; it
does not automatically approve a mapping, mutate data or widen collector support.
