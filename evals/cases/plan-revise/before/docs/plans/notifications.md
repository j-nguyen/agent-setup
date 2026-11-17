# Plan: In-app notifications

**Status:** Accepted
**Date:** 2026-09-08
**Scope:** In-app notifications for task events and mentions: storage, producing, listing, read state, muting and retention. Email delivery is out of scope for this version.

## Goal
Tell users about activity that concerns them (assignments, comments, due dates, mentions) inside teamboard, so they don't have to poll their tasks.

## Requirements
- R1: Users get a notification when a task is assigned to them, commented on, due within 24 h, or when they're mentioned.
- R2: Users see a list of their notifications, newest first, and can filter to unread.
- R3: Users can mark notifications as read.
- R4: Users can mute notification kinds they don't care about.
- R5: Notifications are deleted after 90 days.
**Non-goals:** email or push delivery; real-time updates (the client polls every 60 s); per-task subscriptions.
**Assumptions:** fewer than ~500 notifications per user per 90 days; polling load is fine at current scale.

## Current state
- Persistence goes through `src/db.ts` (`Table<T>`), with an in-memory store in dev and Postgres in prod.
- Per-user settings live in `src/users/settings.ts` (`UserSettings`), created lazily with defaults.
- Recurring work uses the scheduler in `src/scheduler/index.ts`, with jobs registered in `src/scheduler/jobs.ts`.

## Options considered
| Option | Summary | Pros | Cons |
|---|---|---|---|
| A | Notifications table written by a `notify()` service, read by a polling endpoint | Simple, fits `db.ts` and the existing HTTP layer | 60 s latency |
| B | Event bus + WebSocket push | Real time | New infrastructure, connection management, not needed for R1–R5 |
**Chosen:** A, because it meets every requirement with existing building blocks.

## Decisions
- **D1:** A fixed set of notification kinds in `src/notifications/types.ts` (`NOTIFICATION_KINDS`). *Why:* renderers and muting need a closed set. *Rejected:* free-form kinds (can't be muted or rendered reliably).
- **D2:** Store a small denormalized payload with each notification (actor name, task title, due date), enough to render without lookups. *Why:* the list endpoint stays a single query. *Rejected:* rendering from task joins (N+1 per page).
- **D3:** Producers only call `notify()` in `src/notifications/service.ts`; it applies the rules (deactivated users, muting) and is the only writer of the table. *Why:* one place for delivery rules. *Rejected:* producers writing rows directly.
- **D4:** Retention is a daily scheduler job (`notifications.retention`) deleting rows older than 90 days. *Why:* keeps the table bounded using the existing scheduler. *Rejected:* deleting on read (unbounded growth for inactive users).

## Design
### Components
| Component | Path | New/changed | Responsibility |
|---|---|---|---|
| Types | `src/notifications/types.ts` | new | Kinds and the `Notification` shape |
| Repo | `src/notifications/repo.ts` | new | Insert, list, mark read, delete old |
| Service | `src/notifications/service.ts` | new | `notify()`: delivery rules |
| Renderer | `src/notifications/render.ts` | new | One-line text per kind |
| Routes | `src/notifications/routes.ts` | new | `GET /api/notifications`, `POST /api/notifications/read` |
| Settings | `src/users/settings.ts` | changed | `notifications.mutedKinds` |
| Jobs | `src/scheduler/jobs.ts` | changed | Register retention job |
### Boundaries
- Only `src/notifications/service.ts` imports `insertNotification`.
- Routes don't import `src/db.ts`.
### Interfaces
```ts
notify(userId: string, kind: NotificationKind, payload: Record<string, string>): Notification | null
GET  /api/notifications?unread=1  -> 200 { items: (Notification & { text: string })[] }
POST /api/notifications/read { ids: string[] } -> 200 { updated: number }
```
### Data model
`notifications(id, user_id, kind, payload jsonb, created_at, read_at null)`, index on `(user_id, created_at desc)`.
### Flow and failure handling
1. A producer calls `notify()`. It returns `null` for unknown or deactivated users, and for muted kinds.
2. The client polls the list endpoint; marking read only affects the caller's own rows.

## Implementation steps
1. Types, repo and renderer: `types.ts`, `repo.ts`, `render.ts`. *Done when:* repo tests pass.
2. `notify()` service and producers call it: `service.ts`. *Done when:* assigning a task creates a notification.
3. Routes: `routes.ts`, `server.ts`. *Done when:* list and mark-read work over HTTP.
4. Muting: `settings.ts`, `service.ts`. *Done when:* a muted kind is not stored.
5. Retention job: `jobs.ts`. *Done when:* rows older than 90 days are removed by the daily job.

## Test plan
- Unit: repo ordering and filtering, mark-read ownership, rendering per kind, muting, retention cutoff.

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Polling load grows with users | Low | Index on `(user_id, created_at)`; revisit push later |

## Open questions
- **Q1:** Should mentions bypass muting? *Recommended:* no, mute applies to all kinds. *If not:* special-case `mention` in `notify()`.

## Conformance checklist
- [ ] C1: Notification kinds are the closed set `NOTIFICATION_KINDS` in `src/notifications/types.ts` (D1, step 1)
- [ ] C2: `renderText()` handles every kind in `NOTIFICATION_KINDS` from the stored payload only, with no lookups (D2, step 1)
- [ ] C3: `notify()` in `service.ts` is the only caller of `insertNotification`, and it skips unknown and deactivated users (D3, step 2)
- [ ] C4: `GET /api/notifications` returns the caller's notifications newest first, with an `unread=1` filter (step 3)
- [ ] C5: `POST /api/notifications/read` only marks the caller's own notifications (step 3)
- [ ] C6: Routes access data through `repo.ts`, never `src/db.ts` directly (step 3)
- [ ] C7: `notify()` doesn't store kinds listed in the user's `settings.notifications.mutedKinds` (D3, step 4)
- [ ] C8: A daily scheduler job `notifications.retention` deletes notifications older than 90 days (D4, step 5)

## Deviation log
- 2026-10-02 · C8 · Retention job runs at 03:15 UTC instead of midnight to avoid the backup window · accepted
