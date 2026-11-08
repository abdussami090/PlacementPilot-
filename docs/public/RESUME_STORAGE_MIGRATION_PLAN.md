# Resume Storage Migration Plan

**Status:** Generic preparation guidance; no existing resume is authorized for
inspection, copying, upload, update, or deletion by this document.

## Preparation

1. Select an object-storage provider and region after reviewing privacy,
   institutional policy, TLS, access controls, retention, versioning, and
   recovery.
2. Inventory resume metadata-to-file associations in a restricted work record.
   Do not publish filenames, local paths, hashes, student identifiers, or
   file contents.
3. Inventory all database, filesystem, and object-store writers and obtain
   explicit approval for a paired backup, maintenance window, and migration
   operator.
4. Rehearse on copies with synthetic files and a disposable database/bucket.
   Verify owner/admin authorization, unauthorized denial, metadata, file size,
   and checksum equality.

## Cutover outline

With writers paused, copy—not move—the source objects, verify each copy
against its source using SHA-256, and update the corresponding database
references through a controlled and auditable procedure. Verify authorized
downloads and record associations before reopening writes. Keep the originals
and verified backup until acceptance and the rollback-retention period expire.

If upload, verification, database update, or authorization checks fail, do not
remove originals or switch references blindly. Preserve both states and follow
the approved recovery/reconciliation plan. Cleanup requires separate approval.
