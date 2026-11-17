# workspace-api

Public REST API (`/v1`) for workspaces. Node 24 runs the TypeScript directly; no dependencies.

API conventions (the mobile and web clients and the public SDK rely on these):
- JSON field names are camelCase.
- `POST` that creates a resource returns `201` with the resource.
- Lists use cursor pagination: `?cursor=<opaque>&limit=<n>` → `{ "items": [...], "nextCursor": string | null }`.

Run the tests with `npm test`.
