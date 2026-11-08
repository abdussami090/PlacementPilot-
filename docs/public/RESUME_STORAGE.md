# Resume Storage

Resume documents are sensitive personal data. Serve them only through
authenticated, authorized API operations; never expose storage objects as
public static files or unauthenticated URLs.

## Storage controls

- Generate opaque server-side object keys; treat client filenames as metadata,
  not as filesystem paths or object keys.
- Validate file type, size, and content on the server. Enforce request limits
  at both the application and hosting edge.
- Keep the object bucket private and deny anonymous reads. Use TLS and a
  backend-only service identity scoped to the required object operations.
- Authorize student access to their own documents and restrict administrative
  access to the placement roles that require it.
- Do not put storage credentials, resume contents, or unnecessary personal
  information in frontend bundles, source control, or logs.

## Consistency and recovery

Database metadata and object storage do not share an atomic transaction.
Design upload, replacement, and deletion flows to report failures explicitly,
retain recoverable copies until success is verified, and provide a
reconciliation process for orphaned objects or references.

Back up database metadata and resume objects as one coordinated recovery set.
Verify hashes and file associations in an isolated restore. A successful
database restore alone does not prove that referenced documents are available.

Real provider privacy, access policy, durability, and recovery must be tested
before production use. Local development storage is not a production backup
strategy.
