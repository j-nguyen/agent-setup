## Report format

Return **only** this report, in Markdown. Leave out any section that has no
content except where marked "always".

~~~markdown
# Debug report: <TICKET-ID> <ticket title>

**Verdict:** <Reproduced | Not reproduced | Already fixed | Not a bug | Blocked> (verify-fix mode: <Fixed | Not fixed | Partially fixed | Can't verify>) (always)
**Confidence:** <0.0–1.0> (always)
**Tested on:** <repo @ branch/commit short sha, OS, runtime versions> (always)
**Summary:** <2–3 sentences: what the ticket claims and what you found> (always)

## The claim (always)
- **Expected:** …
- **Actual (reported):** …
- **Steps (from ticket / inferred):** …

## Reproduction
<the minimal steps that show the bug; exact commands in a code block>

```text
<trimmed output that shows the failure, failing line included>
```

## Root cause
<`file:line`, the mechanism in 2–4 sentences, the introducing commit if it's a regression,
and the blast radius>

## Suggested fix
<the specific change to make and why; a short diff sketch if helpful; not applied>

## Attempts (always)
| # | What I tried | Command / where | Result |
|---|---|---|---|
| 1 | Ran existing tests for `orders` | `pytest tests/orders -q` | 42 passed, baseline OK |
| 2 | Repro test with ticket's input | `pytest tests/test_eng_123_repro.py` | **Fails**: KeyError 'sku' |

## Files I added (always; write "None" if none)
- `tests/test_eng_123_repro.py`: failing regression test (keep it with the fix)
- `.debug/ENG-123/`: scratch scripts and logs (safe to delete)

`git status` confirms nothing else changed. <or list anything unexpected>

## Not verified / open questions
- <anything you couldn't check, and what would settle it>

## Draft ticket comment
<3–6 lines the user can post to the ticket: the verdict, the minimal repro,
the suspected cause and the next step. Written for teammates, without internal
paths that only exist on this machine.>
~~~
