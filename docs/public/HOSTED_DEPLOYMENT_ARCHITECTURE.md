# Hosted Deployment Architecture

**Status:** Provider-neutral design; no hosted resources are represented as
configured or verified.

## Target

```text
Users
  └── HTTPS
      └── Static React/Vite frontend
          └── HTTPS API requests
              └── FastAPI service
                  ├── TLS/private connection to managed PostgreSQL
                  └── HTTPS access to private S3-compatible resume storage
```

The browser receives only the public API origin. The API is the only
application component that should receive database and object-store
credentials. Database and resume objects remain private.

## Service requirements

| Component | Requirements |
|---|---|
| Frontend | Static hosting, HTTPS, environment-specific builds, immutable releases, and rollback. Frontend build variables are public once bundled. |
| API | Supported Python/container runtime, health checks, bounded requests, graceful shutdown, secret management, logs/metrics, and controlled egress. |
| Database | Supported PostgreSQL, TLS certificate verification, restricted network access, monitored capacity, backups, and tested restore to a separate target. |
| Resume storage | Private bucket, anonymous access denied, TLS, narrowly scoped service identity, retention/versioning decisions, and recovery testing. |
| Operations | Separate runtime and migration identities, protected deployment credentials, sanitized logs, alerting, and documented incident/rollback owners. |

Use a private network between API and database where available. Otherwise,
restrict ingress to the API's verified network identity and require
certificate-verified TLS. CORS is not an authentication or network boundary.

## Release flow

1. Build and verify the frontend and API artifacts.
2. Provision isolated staging services with synthetic test data.
3. Apply reviewed Alembic migrations through a protected migration process,
   not API startup.
4. Verify the API with a non-owner runtime role and verify private resume
   access with synthetic files.
5. Complete paired backup and isolated restore checks before approved data
   transfer.
6. Route production traffic only after provider, budget, security, and data
   owner approvals.

Existing repository integration files are not evidence that a provider or
service is suitable, configured, or production-ready. The zero-monthly-budget
assessment is summarized in [ZERO_COST_HOSTED_DEPLOYMENT.md](./ZERO_COST_HOSTED_DEPLOYMENT.md).
