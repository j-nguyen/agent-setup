# ledgerly

Multi-tenant invoicing SaaS. Go 1.22, standard library `net/http` routing, PostgreSQL.

- Every query on tenant data goes through a repository that reads the tenant from the
  request context (`auth.FromContext`). Never accept a tenant ID from the client.
- Role checks use `auth.RequireRole` on the route.
- Anything that can take more than a couple of seconds runs as a background job
  (`internal/jobs`), not in the request handler.
- Files we generate for customers go to object storage through `internal/storage` and are
  shared with short-lived signed URLs.
- User-visible actions on billing data are written to the audit log (`internal/audit`).
- Tests: `go test ./...` (needs `DATABASE_URL` for the repo tests).
