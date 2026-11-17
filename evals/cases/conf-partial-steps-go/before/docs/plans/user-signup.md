# Plan: User signup

**Status:** Accepted
**Date:** 2026-11-06
**Scope:** Email + password signup for the accounts service, delivered in four steps.

## Goal
Let a new user create an account with an email address and password, then receive a welcome email.

## Requirements
- R1: Email addresses are unique, compared case-insensitively.
- R2: Passwords must be at least 12 characters.
- R3: Plaintext passwords are never stored or logged.
- R4: `POST /signup` returns 201 on success, 400 for invalid input, 409 for a duplicate email.
- R5: New users get a welcome email; a mail failure doesn't fail the signup.
**Non-goals:** email verification links; social login; persistence beyond the in-memory store (a SQL store is a later plan).
**Assumptions:** password hashing is provided by an injected `Hasher` (bcrypt in production).

## Current state
- `internal/httpapi/server.go:1` the HTTP layer; its package doc says it never touches storage directly.
- No user model or store exists yet.

## Options considered
| Option | Summary | Pros | Cons |
|---|---|---|---|
| A. Handler does everything | validation + storage in the HTTP handler | Fewest files | Breaks the layering in `httpapi`; hard to test without HTTP |
| B. Store + signup service + thin handler | domain service owns rules; handler maps errors | Testable; matches the package doc | Three packages |
**Chosen:** B.

## Decisions
- **D1:** `internal/store` defines `UserStore` (`Create`, `ByEmail`) with an in-memory, mutex-guarded `MemoryStore` that enforces unique emails and returns `ErrDuplicateEmail`. *Why:* R1; a SQL store can implement the same interface later.
- **D2:** `internal/signup.Service.Register(ctx, email, password)` owns all validation: trim and lowercase the email, validate it with `net/mail.ParseAddress` (`ErrInvalidEmail`), and require `len(password) >= 12` (`ErrWeakPassword`) before hashing. *Why:* R1, R2; one place for the rules.
- **D3:** `Register` stores only `Hasher.Hash(password)`. *Why:* R3.
- **D4:** `internal/httpapi` handles `POST /signup` through a small `Registerer` interface and maps errors: `ErrInvalidEmail`/`ErrWeakPassword` → 400, `ErrDuplicateEmail` → 409, success → 201 `{id, email}`. *Why:* R4 and the layering rule.
- **D5:** After a successful create, `Register` calls `Mailer.SendWelcome`; errors are logged, not returned. *Why:* R5.

## Design
### Components
| Component | Path | New/changed | Responsibility |
|---|---|---|---|
| Store | `internal/store/users.go` | new | `User`, `UserStore`, `MemoryStore`, `ErrDuplicateEmail`, `ErrNotFound` |
| Signup | `internal/signup/service.go` | new | `Service`, `Hasher`, `Register`, validation errors |
| Handler | `internal/httpapi/signup.go` | new | `POST /signup` |
| Mailer | `internal/signup/mailer.go` | new | `Mailer` interface, log-only dev implementation |
### Boundaries
- `internal/httpapi` must not import `internal/store`.
- `internal/store` imports nothing from this module.

## Implementation steps
1. Store: `internal/store/users.go` + tests. *Done when:* duplicate emails (any case) are rejected.
2. Signup service: `internal/signup/service.go` + tests. *Done when:* every validation rule is enforced and tested, and only hashes are stored.
3. HTTP handler: `internal/httpapi/signup.go`, wire in `NewServer` + tests. *Done when:* the status-code mapping is tested.
4. Welcome email: `internal/signup/mailer.go`, call from `Register` + tests. *Done when:* a mail failure still returns the user.

## Test plan
- Unit (store): duplicate email, case-insensitive duplicate, `ByEmail` not found.
- Unit (signup): email normalization, invalid email, short password, hash stored instead of plaintext.
- HTTP: 201/400/409 mapping. Mailer: failure doesn't fail signup.

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| In-memory store loses data on restart | Certain | acceptable until the SQL store plan |

## Conformance checklist
- [ ] C1: `internal/store` defines `UserStore` with `Create` and `ByEmail`, implemented by `MemoryStore` (D1, step 1)
- [ ] C2: `MemoryStore` rejects duplicate emails case-insensitively with `ErrDuplicateEmail` and guards its maps with a mutex (D1, step 1)
- [ ] C3: `Register` trims and lowercases the email before validating and storing it (D2, step 2)
- [ ] C4: `Register` rejects malformed emails with `ErrInvalidEmail` using `net/mail.ParseAddress` (D2, step 2)
- [ ] C5: `Register` rejects passwords shorter than 12 characters with `ErrWeakPassword`, before hashing (D2, step 2)
- [ ] C6: Only the `Hasher` output is stored; the plaintext password is never stored or logged (D3, step 2)
- [ ] C7: Store and signup tests cover duplicates (incl. case), normalization, invalid email and short password (steps 1–2)
- [ ] C8: `POST /signup` maps errors to 400/409 and success to 201 `{id, email}` (D4, step 3)
- [ ] C9: `internal/httpapi` uses a `Registerer` interface and never imports `internal/store` (D4, step 3)
- [ ] C10: `Register` sends the welcome email after a successful create; mail errors are logged, not returned (D5, step 4)
- [ ] C11: HTTP and mailer tests cover the status mapping and mail failure (steps 3–4)

## Deviation log
