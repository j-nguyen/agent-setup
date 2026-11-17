# teamboard

Small team task board. TypeScript run directly by Node (type stripping), no build step.

- Run tests: `npm test` (Node's built-in test runner).
- Use only erasable TypeScript syntax: no enums, no parameter properties, no namespaces.
- Import local files with the `.ts` extension.
- Persistence goes through `src/db.ts` (an in-memory table store in dev; swapped for Postgres in prod
  behind the same interface). Never touch storage directly from routes.
- Recurring work is registered with the scheduler in `src/scheduler/`; don't add setInterval calls
  elsewhere.
- All outgoing email goes through `src/email/mailer.ts`.
- Design docs and plans live in `docs/plans/`. Keep plan IDs stable when revising a plan.
