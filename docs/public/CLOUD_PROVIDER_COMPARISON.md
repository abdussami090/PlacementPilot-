# Cloud Provider Evaluation

This is a provider-neutral selection framework, not a current price quote or
endorsement. Provider eligibility, plans, quotas, regions, and terms change;
confirm them from official sources and the institution's governing policies
before selection.

## Existing integration points and alternatives

The repository contains configuration for Vercel static frontend hosting and
a Render API service. These are existing integration points only, not a
recommendation to use a particular plan. Other candidates include Cloudflare
Pages for static assets and managed container/API services from AWS, Azure,
Google Cloud, or an institution-approved provider.

For PostgreSQL, evaluate managed services for PostgreSQL and verify psycopg,
SQLAlchemy, Alembic, TLS, private connectivity, role/ownership controls,
backup retention, restore-to-new-target, connection limits, and region
availability.

For resumes, AWS S3 is a native boto3 target. S3-compatible services such as
Cloudflare R2 may fit the current API shape, but require verification of
endpoint/signing behavior, access policy, bucket privacy, metadata, costs, and
recovery. Azure Blob Storage and Google Cloud Storage are not assumed to be
drop-in boto3 replacements.

## Selection criteria

Compare:

- Written permission for the institution's intended use.
- Monthly cost at expected and peak usage, including backups, egress, logs,
  domains, taxes, and overages.
- Availability commitments, support, cold starts, quotas, suspension, and
  data-retention terms.
- Region, data residency, TLS, private networking, identity controls, and
  auditability.
- PostgreSQL compatibility, object durability, backup independence, restore
  access, and migration portability.
- Operational effort and a tested rollback path.

The recorded zero-budget assessment found no verified production-eligible
FastAPI hosting option at ₹0/month. Treat free services as candidates for
approved evaluation only; see
[ZERO_COST_HOSTED_DEPLOYMENT.md](./ZERO_COST_HOSTED_DEPLOYMENT.md).

## Official pages to recheck

- [Vercel plans](https://vercel.com/docs/plans)
- [Vercel fair-use guidelines](https://vercel.com/docs/limits/fair-use-guidelines)
- [Render free services](https://render.com/docs/free)
- [Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits/)
- [Neon plans](https://neon.com/docs/introduction/plans)
- [Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/)

These links are starting points, not proof of current eligibility or a quote.
