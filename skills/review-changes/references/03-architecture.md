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
