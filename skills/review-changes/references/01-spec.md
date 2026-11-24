## Pass 1 — Spec conformance: does it do what we said it would?

Goal: confirm the change actually implements what was described, all of it,
and nothing unasked-for that changes behavior.

### 1.1 Find the spec (in priority order)

1. A spec, requirements or task description passed to you in the delegation
   brief. This is the user's own words, so it wins over every other source.
2. The PR title and description, plus any issues or tickets they link to (use
   `gh pr view`, `gh issue view` or the equivalent if available).
3. Spec or design documents in the repo that the change references or touches:
   `docs/`, `specs/`, ADRs, RFCs, `README` sections, OpenAPI/GraphQL schemas.
4. Commit messages on the branch.
5. Tests added or changed by the change. Treat them as an executable spec, but
   don't let a test that encodes a bug redefine the requirement.

If you find no spec at all, say so plainly at the top of this pass. Infer the
intended behavior from the change itself and mark every row "Inferred". Never
invent requirements.

### 1.2 Build the requirements list

Break the spec into numbered, testable requirements (R1, R2, …). Include implicit
requirements the spec clearly implies, such as "returns 404 when not found",
validation rules, permissions, backwards compatibility, migrations and stated
non-goals. Keep each requirement to one line.

### 1.3 Trace each requirement to the code

For each requirement, give a status with evidence (`file:line`):

| Status | Meaning |
|---|---|
| Met | Implemented correctly, and you can point to the code |
| Partial | Some cases handled, others not (name the missing case) |
| Missing | No implementation found |
| Contradicted | Implemented differently from the spec |
| Unverifiable | Depends on something outside the repo; say what |

Also note whether each requirement has a test that would fail if it broke.

### 1.4 Check the edges of the spec

- **Edge and error cases** the spec mentions or obviously implies: empty input,
  absent values, duplicates, limits, concurrency, partial failure, retries.
- **Scope creep**: behavior changes nobody asked for, such as changed defaults,
  renamed public APIs, altered response shapes or new side effects. Flag them
  as findings only when they could surprise a user or caller.
- **New parts the spec may not need**: list each new table, job, queue,
  service, page or endpoint the change adds. For each, say whether a
  requirement needs it, or whether an existing one could do the job. Flag it
  as a `spec` finding (Medium) when no requirement needs it. A requirement row
  is not Met when the change meets it with parts the spec did not ask for and
  the user would not expect.
- **Contract compatibility**: public APIs, CLI flags, config keys, DB schemas
  and event or message formats that existing consumers rely on.

### 1.5 Optional: run the tests

If the project has a quick, self-contained test command, you may run the tests
that cover the changed code. Only do this if it doesn't modify tracked files,
install dependencies or touch external services. Report the result. Never edit
tests or code to make them pass.

Findings in this pass use category `spec` and should say which requirement (Rn) they relate to.
