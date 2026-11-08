# Zero-Cost Hosted Deployment Assessment

**Decision recorded:** **ZERO-COST DEPLOYMENT NOT FEASIBLE** for the intended
real college placement platform based on the provider assessment documented
for this project. This is a dated decision record, not a guarantee that every
provider or future plan is ineligible.

No provider accounts, cloud resources, data transfers, or public deployment
are implied by this assessment.

## Why ₹0/month is not an established production target

- The reviewed Render free service documentation states that free instances
  are not intended for production; cold starts and ephemeral local storage
  also make them unsuitable for the intended API/data role.
- The reviewed Vercel Hobby terms restrict use to non-commercial personal
  projects; do not assume institutional placement operations qualify.
- An expiring database is not acceptable for persistent student/application
  records.
- A static frontend can be hosted separately, but that does not provide a
  suitable API, persistent database, private resume store, independent
  backups, or production recovery.
- Quota-limited database and object-storage plans do not by themselves provide
  an availability commitment or an independently verified backup/restore
  process. Usage overages may incur charges.

Specific quotas and terms can change and were not revalidated as part of this
publication review. Check the linked official provider documentation in
[CLOUD_PROVIDER_COMPARISON.md](./CLOUD_PROVIDER_COMPARISON.md) and obtain
written institutional/provider confirmation before relying on any plan.

## Safe evaluation use

Static hosting, a non-expiring development database plan, or private object
storage allowances may be evaluated with synthetic data if provider terms
permit. Do not use real student records or resumes until the full service
chain, privacy controls, backup, restore, monitoring, and institutional
approvals are satisfied.

Never store resumes on ephemeral application filesystems or expose them
through public buckets. Do not put database, JWT-signing, or storage secrets
in frontend variables.

## Conditions to revisit

Reassess if the institution provides eligible infrastructure at no additional
cost, the platform's scope changes to an approved non-production prototype,
or the budget changes. Include API hosting, persistent PostgreSQL, private
resume storage, independent backups, monitoring, domains, taxes, and overages
in the cost decision. Do not describe the service as production-ready until
recovery has been tested.
