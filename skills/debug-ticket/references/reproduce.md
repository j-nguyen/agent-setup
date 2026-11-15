## Reproduction playbook

Goal: settle with evidence whether the problem in the ticket **really happens
locally**, and if so, why. Your verdict is only as good as the commands and
output behind it.

### Safety rules (always)

- **Only add files. Never modify or delete existing tracked files.** You may
  only create:
  - a new test file in the project's normal test location, named so its
    purpose is obvious (e.g. `tests/test_eng_123_repro.py`,
    `src/foo/eng-123.repro.test.ts`);
  - scratch scripts, data and logs under `.debug/<ticket-id>/` at the repo root.
- **Don't fix the bug.** Describe the fix instead; the coordinator applies it only if the user asks.
- **Local or test resources only.** Never connect to production databases,
  APIs or queues, and never use real customer data. If reproducing would need
  them, stop and report `Blocked`.
- **Never print secrets.** Read config from the environment or the project's
  existing `.env.example`/test fixtures. Don't print secret values into logs or the report.
- **Dependencies**: you may run the project's own install from its lockfile
  (`npm ci`, `pnpm install --frozen-lockfile`, `uv sync`, `pip install -r
  requirements.txt` into the project venv, `bundle install`, `go mod download`)
  if the brief allows it. Never install globally, upgrade packages or edit lockfiles.
- **Long-running processes**: if you start a dev server or container, run it in the
  background, give it a timeout, and stop it before you finish.
- **Git**: don't commit, push, stash, reset or change branches in the user's
  working tree. To test another commit, use a separate worktree
  (`git worktree add .debug/<ticket-id>/wt <ref>`) and remove it when done.

### Step 1. Pin down the claim

From the ticket, write down:
- **Expected** behavior and **actual** behavior, in one line each.
- **Steps** to reproduce (as given, or inferred; mark which).
- **Environment**: app version or commit, OS, browser, runtime, feature flags,
  account or role, data shape, and how often it happens.
- **Evidence** in the ticket: error messages, stack traces, logs, screenshots described in text.

If the ticket is too vague to test, say exactly what's missing, but still try
the most likely interpretation before you report `Blocked`.

### Step 2. Locate the code

- Search the codebase for the error text, log lines, endpoint paths, component
  names and identifiers from the ticket.
- Read the code path end to end, from the entry point to where the failure appears.
- Check recent history around it (`git log -p --since=<a few weeks before the ticket> -- <paths>`).
  A suspicious recent change is a lead, not proof.
- Form one or more **hypotheses**, each with the observable symptom it predicts.

### Step 3. Learn how to run it

Read the project's `.agents/debug.md` and `.agents/rules.md` first, if they exist.
They may tell you where repro tests go and which commands to use. Then read
`README`, `CONTRIBUTING`, `AGENTS.md`/`CLAUDE.md`, `Makefile`/`justfile`,
`package.json` scripts, `pyproject.toml`, `docker-compose.yml` and the CI
config to find the real test and run commands. Run the existing tests for the
area first. That establishes a baseline and tells you whether the toolchain
works at all.

### Step 4. Reproduce, cheapest first

Go from fastest and most isolated to most faithful, and stop at the first
level that shows the bug clearly:

1. **A failing automated test** that captures the ticket's steps against the
   real code: a unit test if the bug lives in one function, an integration
   test if it crosses a boundary (DB, HTTP, queue). This is the best artifact,
   because it becomes the regression test.
2. **A small script** in `.debug/<ticket-id>/` that calls the code directly with the ticket's inputs.
3. **Run the app locally** and replay the steps: `curl`/HTTP calls, a CLI
   invocation, or a headless browser if one is already available.

For every attempt, record the **exact command**, the **relevant output** (trimmed,
with the failing line kept), and what it shows.

If it doesn't reproduce, vary one thing at a time, at least three meaningful
variations before giving up:
- the exact inputs or data shape from the ticket (empty, large, unicode, nulls, boundaries);
- the reported version: check out the commit or tag the reporter was on in a
  worktree. If it reproduces there but not on `HEAD`, find the commit that fixed
  it (`git log`, or `git bisect` in the worktree);
- config, feature flags, role or permissions, locale or timezone, concurrency or timing;
- dependency or runtime versions named in the ticket.

### Step 5. Root cause (when reproduced)

- Trace the failure to the responsible `file:line` and explain the mechanism in two to four sentences.
- Show that your explanation is right. For example: the repro fails for the
  reason you predicted, and a one-line local experiment in your scratch copy
  makes it pass. Never apply such an experiment to tracked files.
- If it's a regression, identify the introducing commit (`git log -S`, `git blame`, or bisect).
- Note the **blast radius**: other callers or features that hit the same code path.
- Give a confidence from 0.0 to 1.0.

### Step 6. Decide the verdict

| Verdict | Use when |
|---|---|
| **Reproduced** | You triggered the reported behavior locally and have the command + output to prove it |
| **Not reproduced** | You followed the steps faithfully plus at least 3 meaningful variations and it behaves correctly |
| **Already fixed** | Reproduces on the reported version but not on current `HEAD`; name the fixing commit |
| **Not a bug** | The behavior is intended. Cite the spec, docs, tests or code that says so |
| **Blocked** | Can't be tested locally (needs prod data, a third-party account, specific hardware); say exactly what would unblock it |

`Not reproduced` is a real result, not a failure, but it needs the attempts table to back it up.

### Verify-fix mode

If the brief asks you to verify a fix (a branch, PR or commit):
1. Build or keep the repro on the **base** and confirm it fails there. Use a
   worktree if the base isn't checked out.
2. Run the same repro on the **fix**.
3. Run the existing tests for the affected area on the fix.
4. Verdict: **Fixed** (fails on base, passes on fix, nothing else breaks),
   **Not fixed**, **Partially fixed** (say which cases still fail), or
   **Can't verify** (the repro couldn't be built; say why).

### Before you finish

Stop any process you started. Remove any worktree you added. Run `git status
--porcelain` and confirm that the only changes are the new files you list in
the report.
