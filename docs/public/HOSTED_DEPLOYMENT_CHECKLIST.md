# Hosted Deployment Checklist

This checklist is a release gate, not evidence that resources are configured.

## Approval and service selection

- [ ] Approve institution/account ownership, providers, regions, data
  residency, budget, workload, availability, retention, and recovery objectives.
- [ ] Assign deployment, database, storage, incident, and restore owners.
- [ ] Confirm provider terms permit the intended institutional workload.
- [ ] Separate staging from production; use synthetic data for tests.

## Application and security

- [ ] Configure HTTPS for frontend and API and exact allowed CORS origins.
- [ ] Keep database, JWT, and object-store credentials in backend/release
  secret management only.
- [ ] Use separate least-privilege runtime and migration database identities.
- [ ] Require verified database TLS and restrict database network access.
- [ ] Keep resume objects private; test anonymous denial and authorized access.
- [ ] Configure request/body limits, rate controls, sanitized logging, health
  checks, monitoring, and alerts.

## Data safety and release

- [ ] Rehearse Alembic migrations and application workflows on a disposable
  target.
- [ ] Create a coordinated database/resume backup and restore it to an
  isolated target; verify revisions, constraints, sequences, hashes, and
  associations.
- [ ] Approve data transfer and maintenance timing separately; inventory and
  pause all writers for consistent capture/cutover.
- [ ] Document artifact rollback and data reconciliation; never automatically
  restore over production.
- [ ] Recheck current provider terms, quotas, pricing, and billing controls.

Do not treat passing SQLite tests, a provider dashboard backup indicator, or
a healthy endpoint as a substitute for PostgreSQL and restore verification.
