# Plan: Workspace invites API

**Status:** Accepted
**Date:** 2026-11-03
**Scope:** Create and list pending workspace invites through the public `/v1` API.

## Goal
Admins can invite people by email and see pending invites. The web app, mobile app and public SDK
will all call these endpoints, so the contract below is fixed before anyone builds against it.

## Requirements
- R1: Create an invite for an email address; it expires after 7 days.
- R2: List pending invites, paginated like every other `/v1` list.
- R3: Reject invalid email addresses.
**Non-goals:** sending the invite email (separate plan), accepting invites, revoking invites.
**Assumptions:** in-memory storage behind an interface is fine until the persistence plan lands.

## Current state
- API conventions: camelCase fields, `201` on create, cursor pagination (`README.md:5`).
- `GET /v1/teams` is the reference list implementation (`src/teams/routes.ts:10`).
- `isEmail`, `parseLimit`, `encodeCursor`/`decodeCursor` exist in `src/http/validate.ts`.
- Every route already passes through `requestLogger` (`src/app.ts:12`).

## Options considered
| Option | Summary | Pros | Cons |
|---|---|---|---|
| A | Follow the `/v1/teams` pattern | Consistent; SDK generator already handles it | None significant |
| B | Offset pagination | Simple page numbers in the UI | Breaks the `/v1` convention and the SDK's list helper |
**Chosen:** A.

## Decisions
- **D1:** `POST /v1/invites` returns `201` with exactly `{id, email, expiresAt}`; `expiresAt` is an
  ISO-8601 string 7 days after creation. Internal fields (e.g. who created it) are not exposed.
- **D2:** `GET /v1/invites` uses cursor pagination like `/v1/teams`: `?cursor=&limit=` (limit via
  `parseLimit`: default 20, max 100) → `{items, nextCursor}`; items have the same shape as D1.
- **D3:** Validate with the existing `isEmail`; invalid input is `400 {"error": "invalid_email"}`.
- **D4:** Storage is an `InviteStore` in `src/invites/store.ts`, injected through `buildApp`.

## Design
### Components
| Component | Path | New/changed | Responsibility |
|---|---|---|---|
| Invite store | `src/invites/store.ts` | new | `create`, `listAfter(cursorId, limit)` |
| Invite routes | `src/invites/routes.ts` | new | Handlers for D1–D3 |
| App wiring | `src/app.ts` | changed | Register routes after `requestLogger` |
### Interfaces
```
POST /v1/invites            {"email": "a@b.co"}
201 {"id": "inv_…", "email": "a@b.co", "expiresAt": "2026-11-10T12:00:00.000Z"}
400 {"error": "invalid_email"}
GET /v1/invites?cursor=<opaque>&limit=20
200 {"items": [{"id", "email", "expiresAt"}], "nextCursor": "<opaque>" | null}
```

## Implementation steps
1. Store (D4): `src/invites/store.ts`. *Done when:* create and list work in memory.
2. Create endpoint (D1, D3): `src/invites/routes.ts`, `src/app.ts`. *Done when:* 201 with the D1 shape.
3. List endpoint (D2): `src/invites/routes.ts`. *Done when:* two pages walk the whole list.
4. Tests: `test/invites.test.ts`. *Done when:* the test plan passes.

## Test plan
- Create returns 201 and exactly `{id, email, expiresAt}`.
- Invalid email returns 400.
- Listing walks two pages via `nextCursor` and ends with `null`.

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Contract drift breaks the SDK | Medium | Contract fixed here; reviewed against this plan |

## Open questions
None.

## Conformance checklist
- [ ] C1: Invalid email returns `400 {"error": "invalid_email"}` using `isEmail` (D3, step 2)
- [ ] C2: `POST /v1/invites` returns `201` with exactly `{id, email, expiresAt}`, `expiresAt` 7 days out (D1, step 2)
- [ ] C3: `GET /v1/invites` takes `?cursor=&limit=` (via `parseLimit`) and returns `{items, nextCursor}` (D2, step 3)
- [ ] C4: List items have the same `{id, email, expiresAt}` shape as the create response (D1, D2, step 3)
- [ ] C5: Invites are stored through `InviteStore` in `src/invites/store.ts`, injected via `buildApp` (D4, step 1)
- [ ] C6: Invite routes are registered in `src/app.ts` behind the existing `requestLogger` (step 2)
- [ ] C7: `test/invites.test.ts` covers the 201 create shape, invalid email and two-page cursor listing (step 4)

## Deviation log
