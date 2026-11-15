## Pass 0 — Baseline review (adapted from Anthropic's code-review)

Adapted from Anthropic's `code-review` command (Apache-2.0); see `NOTICE.md`.
Run this pass first. It sets the evidence bar every later pass must meet.

### 0.1 Establish the target and context

1. Resolve exactly what is under review: uncommitted changes, a branch against
   its base, a PR, a commit or commit range, or specific paths. For a branch,
   diff against the merge base (`git merge-base HEAD <base>`) instead of the
   branch tip, so you review only what would actually merge.
2. Read the complete diff, not just the first files. Then read enough of the
   surrounding code (callers, callees, types, tests) to understand each changed path.
3. Gather the project's instruction files that apply to the changed files:
   `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.cursor/rules`, `CONTRIBUTING.md`, and
   lint/format configs, plus the project's `.agents/review.md` and `.agents/rules.md`
   (see "Project-specific rules"). A rule applies to a file only when the instruction
   file sits in that file's directory or one of its parents.
4. Write a short summary of the change (what it does, which areas it touches) for
   the report header.

### 0.2 Find high-signal defects

Look for two things:

- **Bugs introduced by the change**: code that won't compile or parse (syntax
  errors, type errors, missing imports, unresolved references), logic that
  definitely gives wrong results, broken error handling, wrong API usage, and
  edge cases the code clearly mishandles.
- **Instruction-file violations**: clear, unambiguous breaks of a rule in an
  applicable instruction file. Quote the exact rule you're citing.

### 0.2a Run the project's own checks (when it's cheap and safe)

Real tool output is stronger evidence than reading. If the project defines them,
run the **type checker** and the **tests that cover the changed code**. Find
them in `package.json` scripts, `Makefile`/`justfile`, `pyproject.toml`/`tox.ini`,
`Cargo.toml`, `go.mod` or the CI config. Typical examples: `tsc --noEmit`,
`mypy`, `pyright`, `cargo check`, `go vet ./...`, `pytest <paths>`,
`npm test -- <pattern>`.

Rules:
- Use only commands the project already defines or that are standard for its
  toolchain. Never install dependencies, never use `--fix`/`--write`/auto-update
  flags, and never edit files to make a check run.
- Avoid leaving build artifacts: prefer flags that don't write caches or output
  (`PYTHONDONTWRITEBYTECODE=1`, `pytest -p no:cacheprovider`, `tsc --noEmit`,
  `mypy --no-incremental`). If a check creates a cache folder anyway, mention it in
  Coverage. Don't delete anything to clean up.
- Keep each check to a few minutes at most. Prefer narrowing it to the changed
  files or packages.
- If dependencies aren't installed, the toolchain is missing, or the sandbox
  blocks it, skip the check and list it under "Not checked" in Coverage. A
  missing check isn't a finding.
- **Attribute failures to the change.** A failure is a finding only if this
  change caused it. If that isn't obvious (the failing test or file isn't part
  of the diff), run the same check on the base version in a temporary copy
  outside the repo, without touching the working tree. For example:
  `d=$(mktemp -d) && git archive <merge-base> | tar -x -C "$d"`, then run the
  check in `$d`. If it fails there too, it's pre-existing, so mention it in
  Coverage, not as a finding.
- Report a check-based finding with the exact command and the key lines of
  output. Linter and formatter style complaints are still not findings (see 0.4).

### 0.3 Evidence bar (applies to every pass)

Flag something only when all of these hold:

- It was **introduced by this change**. Pre-existing problems are out of scope,
  unless the change makes them worse or newly reachable.
- It's **discrete and actionable**: there's a specific location and a specific fix.
- You can **demonstrate it from the code**: name the input, state or call path
  that triggers it.
- A senior engineer on this team would **want it fixed** if they knew about it.

### 0.4 Not findings (false positives to drop)

- Pre-existing issues.
- Code that looks wrong but is actually correct once you read the context.
- Pedantic nitpicks a senior engineer wouldn't raise.
- Style issues a linter or formatter in the project already catches. Don't run
  the linter to check them. (Type errors and failing tests caused by the change
  *are* findings; see 0.2a.)
- Issues an instruction file mentions but the code explicitly silences (e.g. a lint-ignore comment
  with a reason).
- Speculative "this could break if…" concerns with no plausible trigger.

### 0.5 Validate before reporting

Before the final report, revisit **every** candidate finding from **every** pass.
Re-open the code and confirm the issue is real. For example, for "variable is
undefined", confirm it really is undefined in that scope. For a cited rule,
confirm the rule applies to this file and is actually broken. Then give each
surviving finding a confidence from 0.0 to 1.0. Drop anything below **0.8**,
except in Pass 3 (architecture/readability), where suggestions down to **0.7**
may be listed under "Suggestions". If you're not sure an issue is real, leave
it out. False positives erode trust.
