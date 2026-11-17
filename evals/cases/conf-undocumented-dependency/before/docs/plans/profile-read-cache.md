# Plan: Cache profile reads

**Status:** Accepted
**Date:** 2026-11-02
**Scope:** Read-through caching for `GET /profiles/:id` in the profiles API.

## Goal
Profile reads are ~80% of database load and almost never change between reads. Serve repeated reads
from memory so the database sees far fewer `findById` calls.

## Requirements
- R1: Repeated reads of the same profile within a minute don't hit the database.
- R2: Memory use stays bounded.
- R3: Unknown profile ids keep returning 404 and must not fill the cache.
**Non-goals:** No new services or dependencies (no Redis, no Memcached); cross-instance consistency.
**Assumptions:** A profile being up to 60 s stale on other instances is acceptable.

## Current state
- `src/lib/cache.ts:14` already has an `LruCache` with TTL, used for config and flags.
- `src/profiles/service.ts:10` reads straight from the repo on every request.
- `src/server.ts:5` builds the service once per process.

## Options considered
| Option | Summary | Pros | Cons |
|---|---|---|---|
| A | Reuse `LruCache` in `ProfileService` | No new infra, already tested | Per-instance cache |
| B | Redis cache shared by all instances | Shared, survives restarts | New service to run and monitor, new dependency, network hop |
**Chosen:** A, because the per-instance staleness is acceptable (see Assumptions) and it adds no infrastructure.

## Decisions
- **D1:** Cache with the existing `LruCache` from `src/lib/cache.ts`. *Why:* already tested, no new infra. *Rejected:* Redis (B), see above.
- **D2:** Key `profile:<id>`, TTL 60 s, at most 5,000 entries, configured where the service is built in `src/server.ts`. *Why:* bounds memory (~5 MB).
- **D3:** Don't cache `null` (not found). *Why:* random ids would otherwise evict real entries.
- **D4:** Inject the cache through the `ProfileService` constructor. *Why:* tests can use a small cache with a fake clock.

## Design
### Components
| Component | Path | New/changed | Responsibility |
|---|---|---|---|
| `ProfileService` | `src/profiles/service.ts` | changed | Read-through lookup in the cache before the repo |
| Wiring | `src/server.ts` | changed | Build `LruCache({ maxEntries: 5000, ttlMs: 60_000 })` |
### Flow and failure handling
1. `getProfile(id)` checks `profile:<id>` in the cache; a hit returns it.
2. On a miss it calls `repo.findById`; a non-null result is stored, `null` is returned uncached.
3. Repo errors propagate unchanged and nothing is cached.

## Implementation steps
1. Bump the `typescript` devDependency to 5.8 so `erasableSyntaxOnly` is available: `package.json`. *Done when:* `tsc --noEmit` passes.
2. Add the cache to `ProfileService`: `src/profiles/service.ts`. *Done when:* hit, miss and not-found behave as in Flow.
3. Wire it up: `src/server.ts`. *Done when:* the server builds the cache with D2's limits.
4. Tests: `src/profiles/service.test.ts`. *Done when:* the cases in the Test plan pass.

## Test plan
- Unit: second read is a cache hit (repo read count stays at 1).
- Unit: not-found is not cached (two reads of an unknown id hit the repo twice).
- Unit: entry expires after the TTL (fake clock).

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Stale reads up to 60 s on other instances | High | Accepted (see Assumptions) |

## Conformance checklist
- [ ] C1: `ProfileService.getProfile` reads through the `LruCache` from `src/lib/cache.ts` (D1, step 2)
- [ ] C2: No new runtime dependencies or external services are added (D1, step 2)
- [ ] C3: The cache is built in `src/server.ts` with TTL 60 s and at most 5,000 entries (D2, step 3)
- [ ] C4: Cache keys are `profile:<id>` (D2, step 2)
- [ ] C5: `null` results are never cached (D3, step 2)
- [ ] C6: The cache is passed in through the `ProfileService` constructor (D4, step 2)
- [ ] C7: Tests cover a hit, not-found-not-cached and TTL expiry (step 4)

## Deviation log
