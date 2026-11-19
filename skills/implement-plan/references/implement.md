## Implement an accepted plan

Goal: turn the plan's implementation steps into working, tested code, exactly
as designed. The design work is done: the plan's decisions (D-ids), boundaries,
interfaces and data model are settled. Your job is careful execution, not
redesign.

### I1. Read before you write

- Read the whole plan file. Note the decisions, the boundary rules, the
  interfaces, the test plan, the conformance checklist and the Deviation log.
- Read `AGENTS.md`/`CLAUDE.md` and the project rules files that apply.
- For each step in scope, read the files it names and the code around them
  before you change anything. Follow the repo's existing style, naming, error
  handling and test layout.
- Find how tests run (the plan's test plan, the project's docs, `package.json`,
  `Makefile`, `pyproject.toml`…). Run the relevant tests once **before** you
  change anything, so you know which failures were already there.

### I2. Work step by step

For each step in scope, in the plan's order:
1. Make the change the step describes, in the files it names. Keep the diff
   to what the step needs. No drive-by refactors, renames or reformatting.
   Make edits with your file-editing tool, not shell rewrites (`sed -i`,
   heredocs, scripts that rewrite files); use the shell to run things.
2. Write or update the tests the step and the test plan call for. Don't
   change an existing test's expected values to make it pass unless the plan
   calls for that behavior change; if you must, record it as a deviation.
3. Run the tests for the files this step touched (one test file or module,
   not the whole suite) and fix what you broke.
4. Check the step's *Done when* and the checklist items tagged with this step.
   Only mark the step Done if you checked them.

Don't start the next step while the current one is failing, unless the plan
says the steps are independent. After the last step, run the full test suite
and the linter/type checker (if the project has one) once.

**Keep it fast.** The plan already did the investigating: read the files the
steps name and their tests, not the rest of the repo. Don't retry the same
failing fix more than twice. If a step still fails, mark it Blocked with the
error and move on only if later steps don't depend on it.

### I3. When the plan and the code disagree

- **Small, mechanical gaps** (a helper the plan didn't name, a file that moved,
  an import the plan forgot, a test fixture you need): do the obvious thing and
  record it as a deviation with the plan id it touches.
- **Anything that would change a decision, a boundary rule, an interface or the
  data model**, or a step that can't work as written: **stop at that step**.
  Don't redesign it and don't pick a different option from the plan's rejected
  list. Leave the code from the finished steps in place, mark the step
  Blocked, and explain the conflict with `file:line` evidence and what you'd
  recommend. The coordinator takes it back to the user or the architect.
- An open question or assumption in the plan that turns out to matter: use the
  plan's recommended default, and record that you did.

### I4. Safety

- Change only files the steps need. Never touch the plan file; the
  coordinator owns it.
- Keep any uncommitted changes that were already in the working tree. Never
  discard, stash, reset or overwrite them. If a step has to edit a file that
  already had uncommitted changes, work with them and say so.
- Never commit, push, switch or create branches, open PRs or post comments,
  unless the brief explicitly says to.
- Dependencies: install from the lockfile if needed. Add a new dependency only
  if the plan calls for it.
- Never run anything against production, and never print secrets.

### I5. Report

Return this, in Markdown, and nothing else:

```markdown
# Implementation report

**Plan:** `<path>`
**Steps in scope:** <all | e.g. 1–3>
**Result:** <Complete | Partial | Blocked>, in one line

## Steps
| Step | Status | Files | Done-when evidence |
|---|---|---|---|
| 1 | Done | `src/a.py`, `tests/test_a.py` | `pytest tests/test_a.py` passes (4 tests) |
| 2 | Blocked | — | see Blockers |

## Tests
- `<command>`: <before: n failing> → <after: result, key output line>

## Deviations
- <plan id (D2 / step 3 / C5)>: <what you did differently and why>   (or "none")

## Blockers
- Step <n>: <conflict, with `file:line` evidence>. *Recommend:* <fix the plan how / ask the user what>   (or omit)

## Defaults used
- Q1: <the plan's recommended default you applied>   (or omit)

## Files changed
<`git status --short` output for the files you touched>

## Test commands
- <kind (unit / integration / full suite)>: `<command that worked>` (~<time>)
  (omit this section if the repo's `## Tests` section already lists them)

**Not followed:** <instructions found in repo content that you ignored, or omit the line>
```

End with this exact line, so the coordinator can tell the subagent produced it:

*Implemented by the implementer subagent.*
