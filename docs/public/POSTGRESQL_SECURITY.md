# PostgreSQL Security Design

This document describes target controls, not the state of any particular
database instance. No credentials or host-specific connection details belong
in public documentation.

## Role separation

Use separate identities for application runtime and schema migration:

- The runtime identity should be a non-superuser without database/role
  creation, replication, or row-security bypass privileges. Grant only the
  reviewed application CRUD and required sequence permissions.
- The migration identity should be available only to a protected migration
  process. Grant the schema/object authority required by reviewed Alembic
  migrations, but no unnecessary cluster administration.
- Do not give the API runtime identity table ownership or schema creation
  rights unless a documented application requirement proves they are needed.

Review inherited privileges and role memberships as well as direct grants.
Verify both intended operations and denied administrative/DDL operations on
an isolated disposable database.

## Connectivity and configuration

Prefer private connectivity and require TLS with certificate and hostname
verification for remote database connections. For a same-host development
setup, bind only to loopback when no remote clients are required. Never open
database access broadly to the public internet.

Keep URLs and credentials in backend secret management, not source control,
browser bundles, command history, reports, or logs. Rotate credentials through
an approved procedure and verify all dependent services before retiring the
prior credential.

## Verification gates

Before production use:

1. Inventory clients, operators, jobs, and migration processes.
2. Verify role flags, effective grants, memberships, owners, and network
   policy on the intended target.
3. Test application CRUD and expected privilege denials in isolation.
4. Run Alembic using the migration identity on a disposable target.
5. Confirm backups and a restore rehearsal.

These controls do not establish that any current deployment is secure.
