# Database Migration Plan

**Status:** Preparation guidance only. It does not authorize access to, export
from, or changes to any live database.

## Compatibility review

Before choosing a managed PostgreSQL target, record the source and target
PostgreSQL versions, current Alembic revision, schema/object inventory,
required extensions, constraints, sequences, database size, and a
privacy-preserving record-count baseline. Do not include production
identifiers, credentials, or personal data in a public report.

Check SQLAlchemy/psycopg connection behavior, Alembic compatibility, TLS
verification, role ownership, collation/encoding, extensions, connection
pooling, and provider limits using an isolated target first.

## Controlled transfer

1. Obtain data-owner approval for the target, transfer scope, window, operator,
   retention, and recovery objectives.
2. Inventory every database and file writer; pause and prevent reconnects
   throughout capture and cutover.
3. Create a protected database backup and a coordinated resume-file backup.
   Record source identity, revision, timestamps, sizes, and cryptographic
   hashes in a restricted manifest.
4. Restore copies into a separately named disposable target. Verify schema,
   revision, constraints, sequence values, authorized workflows, and file
   associations before any production transfer.
5. Perform production transfer only after a separate approval, with writers
   paused and a documented rollback/reconciliation plan.
6. Retain the source and verified backups until acceptance and retention
   requirements are met. Cleanup requires separate authorization.

Database and object-store changes are not one transaction. If target writes
begin, switching back to the source may lose or fork data; pause writers and
reconcile explicitly rather than automatically restoring over either system.
