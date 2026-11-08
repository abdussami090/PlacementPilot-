# Hosted Deployment Risks

| Risk | Required control |
|---|---|
| Excessive database privilege | Separate non-admin runtime and migration identities; test effective grants and denied DDL in isolation. |
| Public or unverified database access | Use private networking where possible, verified TLS, and narrow ingress; never expose PostgreSQL broadly. |
| Resume exposure | Keep buckets private, deny anonymous access, enforce API authorization, and test cross-user denial. |
| Database/file inconsistency | Coordinate writes, back up database and resumes together, verify hashes and associations, and rehearse recovery. |
| Provider quota or term changes | Recheck official terms, eligibility, quotas, suspension, overages, and support before launch. |
| Missing recovery evidence | Perform an isolated restore and verify application-level workflows before production use. |
| Secrets or personal data in logs/source | Use backend-only secret management and sanitized, access-controlled logging. |
| Unproven migration or rollback | Rehearse migrations against a disposable target and define recovery/reconciliation before cutover. |

These are general release risks, not findings about a specific provider account
or production deployment. The zero-budget decision record is in
[ZERO_COST_HOSTED_DEPLOYMENT.md](./ZERO_COST_HOSTED_DEPLOYMENT.md).
