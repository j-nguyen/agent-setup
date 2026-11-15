# agent-setup

One place to write **skills**, **subagents** and **MCP servers** once, then install them into every
coding agent: Claude Code, Codex and OpenCode, plus any agent that reads the
shared `~/.agents/skills` directory (Cursor, Gemini CLI, Amp, and others).

## Quick start

```sh
git clone <this repo> ~/agent-setup && cd ~/agent-setup
./install.sh
```

`install.sh` checks prerequisites (Python 3.11+, git), asks which ticket
trackers you use (GitHub, Jira, GitLab, Linear, or none), previews what it'll
install, asks before changing anything, installs, adds `agent-setup` to
`~/.local/bin`, and runs `agent-setup doctor`. Then restart your agent sessions. The full manual is
**[INSTALL.md](INSTALL.md)**: updating, uninstalling, conflicts, troubleshooting.

> **AI agents:** if you're asked to set this up, follow the "Setting up" section
> of [AGENTS.md](AGENTS.md). Don't improvise the install.

## Commands

```sh
agent-setup doctor                 # check prerequisites, install state, trackers, MCP sign-ins
agent-setup trackers --ask         # choose ticket trackers (saved per machine)
agent-setup status                 # what's installed where
agent-setup validate               # check sources
agent-setup sync --dry-run         # preview
agent-setup sync                   # install / update / prune
agent-setup uninstall              # remove everything it installed
agent-setup new skill|agent|mcp <name>   # scaffold a new source file
```

Use `./bin/agent-setup` if it isn't on your PATH. No packages are needed beyond the
Python standard library.

## What's included

- **`review-changes` skill + `code-reviewer` subagent**: a multi-pass code review.
  The skill works out the target and the spec, then delegates. The read-only
  subagent runs an Anthropic-style baseline, then spec conformance, a security
  audit, architecture/readability, and performance (PostgreSQL `EXPLAIN ANALYZE`,
  NoSQL, Big-O). It validates every finding and returns one report. The
  checklists live in `skills/review-changes/references/`.
- **`debug-ticket` skill + `debugger` subagent**: give it a bug ticket: a Linear,
  GitHub, Jira or GitLab ID/URL, or just paste the text. The skill fetches the ticket
  and its comments (MCP server, CLI or API, whichever is available) and briefs the
  subagent. The subagent reproduces the bug locally (a failing test, a script, or the
  running app) and returns a verdict (Reproduced / Not reproduced / Already fixed /
  Not a bug / Blocked) with the exact commands, output, root cause and a suggested
  fix. It only *adds* files (a repro test, `.debug/<ID>/`) and never edits existing
  code or posts to the tracker unless you ask. It also has a verify-fix mode.
- **`finding-verifier` subagent**: an independent skeptic that tries to disprove
  each High/Medium review finding. `review-changes` runs it automatically.
- **`record-feature` skill + `browser-recorder` subagent**: records a feature
  walkthrough from the current worktree, including uncommitted changes. Uses local
  Playwright scripts to save video, milestone screenshots, and checked outcomes;
  no browser MCP required. Browser evals are documented in `evals/README.md`.
- **MCP servers** (`mcp/`): **CodeGraph** (code-intelligence graph; needs the
  `codegraph` CLI, and answers only in projects indexed with `codegraph init`) and
  **Context7** (current library docs; works without a key at a lower rate limit).
- **`agent-setup` skill**: lets any agent manage this repo for you ("add a skill
  for X to all my agents", "why isn't my subagent showing up?").
- `.agents/review.md`: extra review rules and conventions (also read by the finding verifier)
- `.agents/debug.md`: debugging conventions (where repro tests go, which commands to run)
- `.agents/rules.md`: rules for all of the above

Nested folders work too (`packages/api/.agents/review.md`); the deepest file
wins. These files can add checks and conventions, but they can't relax the
safety rules or suppress High security findings. When a PR edits a rules file,
the reviewer uses the base branch's version and reviews the edit itself. Example:

```markdown
# .agents/review.md
- We paginate with keyset cursors; flag any OFFSET pagination as Medium.
- Every new endpoint needs a test in tests/api/.
- Skip src/generated/**.
```

## Layout

```
install.sh                 one-command setup (see INSTALL.md)
skills/<name>/SKILL.md     Agent Skills standard; extra files (scripts/, references/) allowed
agents/<name>.md           neutral subagent definition (format below)
shared/*.md                text included into several subagents (safety rules, repo rules)
mcp/<name>.json            MCP server definition, always installed (format below)
mcp/optional/<name>.json   MCP servers installed only for the trackers you choose
trackers.json              the tracker choices offered by `agent-setup trackers`
bin/agent-setup            the installer
evals/                     eval harness for the skills and subagents (see evals/README.md)
```

## Where things go

| Kind      | Claude Code                 | Codex                         | OpenCode                          |
|-----------|-----------------------------|-------------------------------|-----------------------------------|
| Skills    | `~/.claude/skills/<name>` → | `~/.agents/skills/<name>` →   | `~/.agents/skills/<name>` →       |
| Subagents | `~/.claude/agents/<name>.md`| `~/.codex/agents/<name>.toml` | `~/.config/opencode/agents/<name>.md` |
| MCP       | user scope via `claude mcp add-json` | managed block in `~/.codex/config.toml` | `mcp.servers` in `~/.config/opencode/opencode.json` |

- **Skills are symlinks** back into this repo, so edits are live without re-syncing.
  Run `sync` again only after adding, renaming or removing a skill.
- **Subagents are rendered** into each tool's own format, because the formats differ.
  Re-run `sync` after every edit.
- Paths honor `CODEX_HOME`, `XDG_CONFIG_HOME` and `XDG_STATE_HOME`.
- `--targets claude,codex` limits a run to some tools.

## Safety

The installer keeps a manifest (`~/.local/state/agent-setup/manifest.json`) of
what it created. It only overwrites or removes those files. If a target path
already exists and isn't in the manifest, `sync` reports a `CONFLICT`, skips that
path and exits with status 1. Your other skills and agents are never touched.

## Subagent format

```markdown
---
name: code-reviewer            # must match the filename
description: >
  When the main agent should delegate to this subagent.
access: read-only              # read-only | edit | full (default full)
claude:                        # optional, per-tool frontmatter passed through as-is
  model: sonnet
codex:
  model_reasoning_effort: high
opencode:
  temperature: 0.1
---

The subagent's system prompt.
```

How `access` maps to each tool:

| access      | Claude Code                     | Codex                              | OpenCode                    |
|-------------|---------------------------------|------------------------------------|-----------------------------|
| `read-only` | `tools: Read, Grep, Glob, Bash` | `sandbox_mode = "read-only"`       | `permission: {edit: deny}`  |
| `edit`      | all tools (inherited)           | `sandbox_mode = "workspace-write"` | default                     |
| `full`      | all tools (inherited)           | inherited                          | default                     |

In Claude Code, a `read-only` subagent still has Bash so it can run things like
`git diff`. Its instructions should say not to change anything.

**Shared reference files.** A line like `<!-- include: skills/<skill>/references/x.md -->`
in a subagent body is replaced at sync time with that file's contents (the path is
relative to the repo root). This way a skill and its subagent share one copy of a
checklist, and every tool gets a self-contained subagent prompt. Re-run `sync`
after editing included files.

Frontmatter supports plain values, quoted strings, `>`/`|` blocks, `[a, b]`
lists and one level of nesting.

## MCP server format

One file per server. The filename is the server name.

```jsonc
// mcp/github.json: stdio server
{
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-github"],
  "env": {"LOG_LEVEL": "info"},          // literal values only, never secrets
  "env_from": ["GITHUB_TOKEN"]           // passed through from your environment
}

// mcp/context7.json: HTTP server
{
  "url": "https://mcp.context7.com/mcp",
  "bearer_token_env": "CONTEXT7_TOKEN",  // sent as "Authorization: Bearer $CONTEXT7_TOKEN"
  "headers": {"X-Client": "me"},
  "headers_from_env": {"X-Api-Key": "SOME_KEY_VAR"}
}
```

Optional: `"enabled": false`, plus `"claude"`, `"codex"` and `"opencode"` objects whose
keys are merged as-is into that tool's entry (e.g. `"opencode": {"codemode": false}`).
Source files must be plain JSON. The `//` comments above are only for this README.

How environment-variable references come out in each tool: Claude gets `${VAR}`,
Codex gets `env_vars` / `env_http_headers` / `bearer_token_env_var`, and OpenCode
gets `{env:VAR}`.

**Already-configured servers.** If a tool already has a server with the same
name, `sync` reports a conflict. `sync --adopt` replaces that entry with the
canonical one and manages it from then on. Uninstalling removes it entirely and
doesn't restore the original. Codex's `config.toml` is backed up to
`config.toml.agent-setup.bak` before each change, and the new file is checked
with a TOML parser before it's written. OpenCode is only edited when
`opencode.json` is plain JSON with no comments.

## Adding a new agent tool

Add an entry in `targets()` in `bin/agent-setup`, a `render_<tool>()` for its
subagent format and, for MCP, an `mcp_<tool>()` renderer plus a `McpBackend`
subclass registered in `MCP_BACKENDS`.
