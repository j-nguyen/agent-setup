## Report format

Return **only** this report, in Markdown. Number findings across all passes
(F1, F2, …), list them most severe first within each section, and leave out any
section that has no content except where marked "always".

```markdown
# Code review: <one-line summary of the change>

**Target:** <what was reviewed, e.g. `feature/x` vs `main` @ <merge-base short sha>, 12 files>
**Spec source:** <brief | PR #123 | docs/spec.md | inferred, no spec found>
**Verdict:** <Approve | Approve with suggestions | Changes requested> (always)
**Summary:** <2–4 sentences: what the change does and the overall assessment> (always)

## Spec conformance (always)
| # | Requirement | Status | Evidence | Tested |
|---|---|---|---|---|
| R1 | … | Met | `src/api/users.ts:42` | yes |

## Findings (always; write "No blocking findings." if empty)

### F1 · High · security/sql_injection · `src/db/users.py:88`
**Problem:** <what's wrong, in one or two sentences>
**Scenario:** <the concrete input, state or call path that triggers it; for security, the exploit>
**Fix:** <specific change; a short code snippet if it helps>
**Confidence:** 0.9

## Suggestions
- **F7 · architecture · `src/services/order.ts:120`:** <one or two lines: issue, then fix>

## Performance notes
<which perf sections applied, EXPLAIN results or the commands to run, and anything measured>

## Coverage (always)
- Passes run: baseline, spec, security, architecture/readability, performance (<sections applied>)
- Checks run: <command → result, e.g. `tsc --noEmit` → pass; `pytest tests/orders` → 2 failed (F3)>
- Not checked / limits: <e.g. couldn't run EXPLAIN (no dev DB); generated files skipped>
```

Verdict rules:
- **Changes requested**: any High finding, any requirement that's Missing or
  Contradicted, or any Medium security finding.
- **Approve with suggestions**: only Medium non-security findings or Suggestions.
- **Approve**: nothing beyond trivial suggestions.

Severity labels: High / Medium for findings; Suggestion for the suggestions list.
Each finding appears **once**, under the pass it fits best.
