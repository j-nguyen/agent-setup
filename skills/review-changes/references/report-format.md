## Report format

Return **only** this report, in Markdown. Number findings across all passes
(F1, F2, …), list them most severe first within each section, and leave out any
section that has no content except where marked "always".

Keep it short so it's quick to read. Every finding stays in, with its location
and fix, but each line says only what the reader needs. No preamble, no
restating the spec, and no closing remarks.

```markdown
# Code review: <one-line summary of the change>

**Target:** <what was reviewed, e.g. `feature/x` vs `main` @ <merge-base short sha>, 12 files>
**Scope:** <only for a scoped review: e.g. "security only" or "performance, limited to `src/payments/`". Not a full review.>
**Spec source:** <brief | PR #123 | docs/spec.md | inferred, no spec found>
**Verdict:** <Approve | Approve with suggestions | Changes requested> (always)
**Summary:** <2–3 sentences: what the change does and the overall assessment> (always)
**Removed:** <every write, event, job, notification or external call the change removes or stops running, in plain words, e.g. "the DynamoDB write of the broker record in `saveApplication`". Omit the line if none.>
**Worth fixing:** <ids of the findings and suggestions worth fixing before merge>. **Optional:** <the rest, or "none"> (always)

**Fix first:** <only when the verdict is "Changes requested": up to 5 lines, most important first,
each `F<n>`: <the problem in under 12 words>. Cover every High finding.>

## Spec conformance (always, unless the brief's Passes leave out spec)
| # | Requirement | Status | Evidence | Tested |
|---|---|---|---|---|
| R1 | … | Met | `src/api/users.ts:42` | yes |

Keep the Evidence cell to a location plus at most ~10 words.

## Findings (always; write "No blocking findings." if empty)

### F1 · High · security/sql_injection · `src/db/users.py:88`
**Problem:** <what's wrong, in one or two sentences>
**Scenario:** <one or two sentences: the concrete input, state or call path that triggers it; for security, the exploit>
**Fix:** <specific change, in one or two sentences, or a code snippet of at most ~8 lines>
**Confidence:** 0.9

## Suggestions
- **F7 · architecture · `src/services/order.ts:120`:** <one or two lines: issue, then fix>

At most 3 suggestions, the most useful first. A suggestion must change
behaviour, prevent drift or follow a written repo rule. Leave out the rest;
don't list them as "also minor".

## Performance notes
<only if a performance section applied, in at most 3 lines: what you measured or the EXPLAIN result, or
the command to run. A performance problem itself goes under Findings.>

## Coverage (always; at most 3 lines)
- Passes run: baseline, spec, security, architecture/readability, performance (<sections applied>), or only the ones the brief asked for
- Checks run: <command → result, e.g. `tsc --noEmit` → pass; `pytest tests/orders` → 2 failed (F3)>
- Not checked / limits: <e.g. couldn't run EXPLAIN (no dev DB); generated files skipped>
```

Verdict rules (for a scoped review, judge only what was reviewed; the Scope line says what that was):
- **Changes requested**: any High finding, any requirement that's Missing or
  Contradicted, or any Medium security finding.
- **Approve with suggestions**: only Medium non-security findings or Suggestions.
- **Approve**: nothing beyond trivial suggestions.

Severity labels: High / Medium for findings; Suggestion for the suggestions list.
Each finding appears **once**, under the pass it fits best.
