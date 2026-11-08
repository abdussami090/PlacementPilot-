# Deployment Guide

This guide describes a deployment sequence; it does not assert that a provider
is selected or any resource is configured. The current zero-budget decision is
summarized in [ZERO_COST_HOSTED_DEPLOYMENT.md](./ZERO_COST_HOSTED_DEPLOYMENT.md).

## Configuration boundaries

The frontend needs only the public HTTPS API base URL, such as
`VITE_API_BASE_URL`. Vite variables are included in browser assets and must not
contain secrets.

Configure backend settings through a protected environment or secret manager:

- Production environment mode and a unique, strong JWT signing secret.
- PostgreSQL URL using a non-owner runtime role and verified TLS.
- Exact HTTPS CORS origins.
- Private object-storage endpoint, bucket, and narrowly scoped credentials.
- Any provider-specific logging, health, request-size, and timeout settings.

Do not include real credentials in `.env.example`, source control, build logs,
or support tickets. Use separate staging and production credentials.

## Release sequence

1. Build and test the frontend and backend in CI.
2. Deploy to an isolated staging environment and verify the health endpoint,
   authentication, authorization, CORS, and request limits.
3. Apply reviewed Alembic migrations through a protected migration process;
   never run migrations implicitly at API startup.
4. Verify PostgreSQL access using the runtime identity and test denied DDL.
5. Test private resume upload and authorized access using synthetic files.
6. Verify monitoring, alerting, independent backups, isolated restore, and
   rollback procedures.
7. Obtain explicit owner approval before any production data transfer or
   traffic cutover.

## Provider eligibility

Existing hosting configuration in the repository is not an approval to use
that provider or its free plan. Confirm current terms, quotas, regions,
security controls, and total cost directly with the provider and institution.
