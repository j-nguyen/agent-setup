## Pass 3 — Architecture, best practices and readability

Goal: judge whether the change is well designed and maintainable by industry
standards and *by this codebase's own conventions*. Unlike Pass 0, this pass
does consider design and readability. It still needs evidence, though, not taste.

### 3.1 Ground rules

- **The repo's conventions come first.** Before calling something wrong, check
  how the codebase already solves the same problem. Consistency with an
  established local pattern beats a generic "best practice". Flag a deviation
  from a local pattern only when it adds real cost, and cite the existing
  example (`file:line`).
- **Justify every point.** Name the principle, standard or concrete cost:
  harder to test, duplicated logic that will drift, a leaky abstraction, a
  change that now needs N edits.
- **Proportionality.** Don't ask a 20-line bug fix to restructure a module.
  Don't propose abstractions for one use (YAGNI).
- **Keep it short.** Report the 5–8 most valuable points. Leave out nitpicks a
  formatter or linter would handle.

### 3.2 Design and architecture

- **Separation of concerns and layering**: business logic leaking into
  controllers, views or SQL; I/O mixed into pure logic; skipped layers (a UI
  component calling the DB directly); circular dependencies.
- **Cohesion and coupling**: god functions or classes; feature envy; one change
  forcing edits across many modules; reaching through objects (Law of Demeter).
- **SOLID where it earns its keep**: single responsibility; depending on
  abstractions at real boundaries (DB, network, clock, filesystem) so the code
  can be tested; interfaces sized to what callers actually use.
- **Over-engineering (speculative generality)**: complexity the change doesn't
  need yet. Examples: an interface, base class, factory, registry or plugin
  hook with one implementation; config options, parameters or flags no caller
  sets; a generic layer or framework built for formats, providers or cases
  nobody asked for; wrappers that only forward calls. Flag it when you can
  name the cost (more code to read and test, indirection on the hot path, a
  wider public surface to keep compatible), and suggest the simpler shape.
  Don't flag a seam at a real boundary (DB, network, clock) that tests use,
  or an abstraction the repo already uses for the same thing.
- **DRY, judiciously**: duplicated *knowledge* (business rules, constants,
  validation) that will drift apart. Similar-looking code that has different
  reasons to change is fine.
- **API and contract design**: clear inputs and outputs; consistent naming and
  error shapes across endpoints; correct HTTP status codes; idempotency for
  retried operations; versioning and backwards compatibility; no boolean flag
  parameters that change what a function does.
- **Error handling**: errors swallowed or logged and then ignored; overly broad
  catches; resources not cleaned up on error paths (missing
  `finally`/`with`/`defer`/`using`); errors that lose context; user-facing
  errors that leak internals.
- **State and concurrency**: shared mutable state, missing transactions around
  multi-step writes, non-idempotent retries, unawaited promises or futures, blocking calls in async code.
- **Transactions** (any database, any ORM):
  - *Keep them short.* No network calls (HTTP APIs, payments, email, publishing
    to a queue or broker), file I/O, sleeps or heavy CPU inside a transaction,
    least of all while it holds row locks. Make the external call before the
    transaction (with an idempotency key) or after it commits. Long-open
    transactions also block other writers and stop vacuum from cleaning up (bloat).
  - *Side effects wait for the commit.* Emails, jobs and events that must
    reflect committed data go in an after-commit hook (`transaction.on_commit`,
    `after_commit`, `afterCommit`) or a transactional outbox, never inline
    before the commit, where they still fire if the transaction rolls back.
    The outbox is needed when losing the side effect is not acceptable.
  - *Nest only for partial failure.* Use a savepoint (Django nested `atomic()`,
    SQLAlchemy `begin_nested()`, `SAVEPOINT`) when an inner step may fail
    while the outer transaction carries on. Catching a database error inside a
    transaction without one leaves it aborted (Postgres: "current transaction
    is aborted"). When the steps must succeed or fail together, use one
    transaction and no nesting. Watch for frameworks that silently join an
    inner "transaction" to the outer one (Rails `transaction` without
    `requires_new: true`, Spring `REQUIRED`), so an inner rollback doesn't do
    what the code expects.
  - *Locks.* Take row locks in a consistent order (e.g. by primary key) to avoid
    deadlocks, take the most restrictive lock you'll need first, and lock only
    rows you will change. Prefer an atomic
    `UPDATE … SET x = x + …` to read-then-write. Use `SKIP LOCKED` for
    work-queue tables.
  - *Isolation and retries.* Under SERIALIZABLE or REPEATABLE READ, and for
    deadlocks, the whole transaction must be retried on SQLSTATE 40001/40P01,
    with a bounded number of attempts. Retry the complete transaction, including
    the code that decides what to write, and make it safe to run again.
  - *Always finished.* Every transaction is committed or rolled back on every
    path (`with`, `defer tx.Rollback()`, `finally`). Every statement meant to
    be in it uses the transaction handle, not the pool or another connection.
- **Configuration and environment**: hardcoded environment-specific values
  (URLs, paths, timeouts) that belong in config (12-factor); feature flags with
  no cleanup plan.
- **Testability and tests**: is new behavior covered at the right level (unit
  for logic, integration at boundaries)? Do tests assert behavior rather than
  implementation details? Report missing tests only for non-trivial new logic
  or a bug fix with no regression test.
- **Language and framework idioms**: use the standard idioms of the language
  and framework in use (e.g. context managers in Python, `const`/immutability in
  TS, `?`-propagation in Rust, hooks rules in React). Don't use deprecated APIs.

### 3.3 Readability

Code is read far more often than it's written. Check that a new teammate could follow the change:

- **Naming**: names say what something *is* or *does*, at the right level of
  abstraction. No misleading names, unexplained abbreviations, `data2`/`tmp`/`handle`.
- **Function shape**: each function does one thing at one level of abstraction.
  Deep nesting is flattened with guard clauses or early returns. Long parameter
  lists are grouped.
- **Clarity over cleverness**: no dense one-liners, nested ternaries or
  surprising operator tricks where plain code would do. Magic numbers and
  strings get named constants.
- **Comments**: explain *why*, not *what*. Flag comments that are stale or
  contradict the code, commented-out code, and TODOs with no owner or ticket.
  Public APIs have doc comments where the project's convention expects them.
- **Dead code**: unused functions, parameters, imports, variables and unreachable branches.
- **Consistency**: matches the surrounding file's style and structure.

### 3.4 Severity for this pass

- **High**: a design flaw that will cause defects or block near-term work, e.g.
  a missing transaction that leaves inconsistent state, or a layering break
  that leaks a security boundary.
- **Medium**: a meaningful maintainability cost worth fixing before merge.
- **Suggestion**: worth doing, but fine as a follow-up. List these separately.

Category values: `architecture`, `api-design`, `error-handling`, `concurrency`, `testing`,
`readability`, `idiom`, `duplication`, `dead-code`.
