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
agent-setup select --ask           # choose which skills, subagents and MCP servers to install
agent-setup select --only a,b      # or --skip, --add, --remove, --all (no flags shows the choice)
agent-setup status                 # what's installed where
agent-setup validate               # check sources
agent-setup sync --dry-run         # preview
agent-setup sync                   # install / update / prune (-y never asks about new items)
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
- **`plan-architecture` skill + `architect` and `plan-reviewer` subagents**:
  plan before you build, then check the build against the plan. In plan mode
  the `architect` subagent investigates the codebase, weighs 2–3 options and writes a plan (decisions,
  design, implementation steps, test plan, risks, open questions and a
  conformance checklist) to `docs/plans/<slug>.md`, the only file it may touch,
  then returns a short summary. In
  review mode the read-only `plan-reviewer` subagent checks a diff, branch or PR against that checklist and reports
  deviations, unplanned changes and plan gaps, saying for each whether to fix the
  code or update the plan. `review-changes` also picks up these plans as its spec.
  It asks whether there's a ticket (Jira, GitHub, GitLab, Linear) or spec to plan
  from, and fetches it the same way `debug-ticket` does.
- **`implement-plan` skill + `implementer` subagent**: builds an accepted plan.
  The skill first checks the plan is solid (accepted, open questions settled,
  every step has files and a checkable done-when, a conformance checklist, no
  drift since it was written). If it is, the subagent implements it step by step
  on a cheaper model (Sonnet in Claude Code, `gpt-6.2-sol` in Codex; OpenCode uses
  its configured model), running tests after each step and stopping at anything
  that would need a design change. The coordinator checks the diff and offers
  a review-changes pass as a follow-up. If the plan isn't solid, it
  says what's missing and offers to fix the plan first. Change the models in
  `agents/implementer.md`.
  The implementer also reads best-practice packs for the stacks it touches
  (TypeScript, React/Next.js, web UI, SQL, Python) from
  `skills/implement-plan/references/practices/`. Add a pack there and list it
  in that folder's `README.md`.
- **`finding-verifier` subagent**: an independent skeptic that tries to disprove
  each High/Medium review finding. `review-changes` runs it automatically.
- **`record-feature` skill + `browser-recorder` subagent**: records a feature
  walkthrough from the current worktree, including uncommitted changes. Uses local
  Playwright scripts to save video, milestone screenshots, and checked outcomes;
  no browser MCP required. Browser evals are documented in `evals/README.md`.
- **MCP servers** (`mcp/`): **CodeGraph** (code-intelligence graph; needs the
  `codegraph` CLI, and answers only in projects indexed with `codegraph init`) and
  **Context7** (current library docs; works without a key at a lower rate limit),
  and **memory**: a small local server (`mcp/servers/memory.py`, Python standard
  library only, stdio) that gives every agent one shared, persistent memory.
  - *Store:* plain Markdown files, one per fact (frontmatter `name`, `description`,
    `type: user|feedback|project|reference`), under `$AGENT_MEMORY_DIR`, else
    `$XDG_DATA_HOME/agent-memory`, else `~/.local/share/agent-memory`. `global/` holds
    facts for everywhere and `projects/<key>/` one folder per project, where `<key>` is
    the git root (shared by worktrees) with every non-alphanumeric character as `-`.
    Same rule on macOS, Linux and WSL2 (on WSL2 keep it in the Linux home, not `/mnt/c`).
    `agent-setup` never deletes the store.
  - *Tools:* `search`, `get`, `save`, `update`, and `forget`. Pass the agent's
    `project_path` to each tool. Use `search` with `compact=true` for short
    excerpts and `get` for the full note. Pass the revision from `get` to
    `update` or `forget` to reject the change if another session edited the note.
  - *Guidance:* `sync` also writes a managed block (from `shared/memory-instructions.md`)
    into `~/.claude/CLAUDE.md`, `$CODEX_HOME/AGENTS.md` and
    `~/.config/opencode/AGENTS.md`, telling agents to use this server only. Text
    outside the markers is never touched, and `uninstall` removes just the block.
  - *Import:* `python3 mcp/servers/memory.py import-claude [--dry-run]` copies your
    Claude Code auto-memory (`~/.claude/projects/*/memory/*.md`) into the store. It
    never moves or deletes the originals, skips names that already exist and can be
    re-run.
  - *Claude Code's built-in auto-memory* must be switched off by you
    (`"autoMemoryEnabled": false` in `~/.claude/settings.json`); `agent-setup doctor`
    reminds you until it is. See INSTALL.md.
- **devservers** (MCP server, `mcp/servers/devservers.py`, Python standard library
  only, stdio): every agent can set up, start, watch and stop the dev servers of a
  git worktree through one shared registry, for any stack.
  - *Tools:* `status`, `start`, `setup`, `stop`, `restart`, `logs`, `wait_ready`,
    `trust` and `configure`. Each takes the agent's `project_path` (the worktree).
    Servers run detached in their own process group, so they outlive the agent
    session, and `stop` kills the whole group (TERM, then KILL after `stop_timeout`).
  - *Config:* `.agents/devservers.json` (committed) merged with the personal,
    git-excluded `.agents/devservers.local.json` (top-level keys replace; `servers`
    merge by name). Set `inherit_worktrees: true` in the main checkout's personal
    config to use its merged config in worktrees that have neither config file.

    ```jsonc
    {"setup": "yarn wt setup"                      // delegated, or an object:
              | {"copy": [".env"], "install": "npm ci", "after_install": "..."},
     "preflight": [{"run": "...", "in": "main", "hint": "..."}],
     "ports": {"PORT": 3000},                     // base + the worktree's slot (main = 0)
     "ports_from": {"env_file": ".env.yarn", "keys": ["PORT"], "main": {"PORT": 3000}},
     "env": {}, "env_strip": [], "max_running": 3, "idle_timeout_minutes": 0,
     "servers": {"dev": {"run": "npm run dev", "default": true, "stop_signal": "TERM",
                         "ready": {"log": "Ready in", "port": "PORT", "timeout_sec": 120}}}}
    ```

    Commands run through `sh`, so `$PORT` reaches servers that take the port as an
    argument (`php artisan serve --port=$PORT`). Without a config, `start` only
    proposes one (detected from lockfiles, `package.json` `dev*` scripts, Procfiles,
    `manage.py`, `artisan`, `go.mod`, `Cargo.toml`, compose files); `configure`
    writes it after the user agrees.
    For delegated ports, `keys` limits the env file to ports the app binds.
    `main` supplies fallback values in the main checkout. A server's `port_keys`
    selects the ports to check for that server. `DEVSERVERS_PROJECT` points to the
    main checkout and `DEVSERVERS_WORKTREE` points to the active worktree.
  - *Trust:* a new or changed config does not run. The tools return the commands, a
    diff from the trusted copy and a hash; the agent calls `trust` with the hash
    only after the user approves (your client prompts for that call). From a
    terminal: `python3 mcp/servers/devservers.py trust <worktree>`. The approval is
    remembered by the hash of the merged config.
  - *Setup:* a `setup` string is delegated to the project; an object does the default
    steps: take a slot (main 0, worktrees 1 to 49), copy ignored files from the main
    checkout when absent, install, `after_install`, and write `.env.devservers`
    (excluded from git) with the worktree's ports and `COMPOSE_PROJECT_NAME`. It runs
    as a detached task, so use `wait_ready(task="setup")`. `start` refuses until it
    succeeded, and again after a lockfile or the config changes. Servers get a clean
    environment: another worktree's `PORT`, `VIRTUAL_ENV`, `npm_*` and so on are
    stripped first.
    Use `start(setup_if_needed=true)` to run trusted setup before starting. If
    setup takes longer than `setup_timeout_sec`, it continues in the background.
  - *HTTP readiness:* Add `"http": [{"port": "PORT", "path": "/health"}]` under a
    server's `ready`. Every HTTP check must return a 2xx or 3xx status. DevServer
    connects directly to loopback and does not follow redirects.
  - *Logs:* one log per run (the previous one kept as `.1`), raw lines with a
    `since` cursor, `grep` and a line cap; `status` gives the path. The last line of
    a finished run is `[devservers] exited <code>`.
  - *State:* `$DEVSERVERS_DIR`, else `$XDG_STATE_HOME/devservers`, else
    `~/.local/state/devservers`, shared by all agents. Same rule on macOS, Linux and
    WSL2 (keep it in the Linux home). `agent-setup` never deletes it.
  - *Guidance:* `sync` writes a second managed block (from
    `shared/devservers-instructions.md`) next to the memory block. Codex pre-approves
    only the read-only tools `status`, `logs` and `wait_ready`; everything else
    prompts.
  - *Stack examples* (what to put in the config):

    | Stack | setup | run |
    |---|---|---|
    | Node (npm) | `{"install": "npm ci"}` | `npm run dev` (`ready.log` for the "Local:" line) |
    | Rails 7.1+ | `{"copy": [".env", "config/master.key"], "install": "bundle install", "after_install": "bin/rails db:prepare"}` | `rm -f tmp/pids/server.pid && exec bin/rails s -p $PORT`, `ports: {"PORT": 3000}` |
    | Django + uv | `{"copy": [".env"], "install": "uv sync", "after_install": "uv run python manage.py migrate"}` | `uv run python manage.py runserver 127.0.0.1:$PORT`, `ports: {"PORT": 8000}` |
    | Go | `{"install": "go mod download"}` | `go run ./cmd/api`, `ready.port: "PORT"` |
    | Rust | `{"install": "cargo fetch"}` | `cargo run`, `ready.timeout_sec: 900` (cold builds are slow) |
    | Phoenix | `{"install": "mix deps.get", "after_install": "mix ecto.create && mix ecto.migrate"}` | `mix phx.server`, `ports: {"PORT": 4000}` |
    | Laravel | `{"copy": [".env"], "install": "composer install", "after_install": "php artisan migrate"}` | `php artisan serve --port=$PORT` |
    | Compose only | `{}` | `docker compose up`, `stop_signal: "INT"`, ports as `${WEB_PORT:-8080}:80` |

    Use `max_running: 1` for apps that cannot run twice (a fixed Electron user-data
    dir, one bot token), and `preflight` with `"in": "main"` for a shared database.
- **`agent-setup` skill**: lets any agent manage this repo for you ("add a skill
  for X to all my agents", "why isn't my subagent showing up?").
- `.agents/review.md`: extra review rules and conventions (also read by the finding verifier)
- `.agents/architecture.md`: planning conventions (where plans live, architectural rules)
- `.agents/debug.md`: debugging conventions (where repro tests go, which commands to run)
- `.agents/rules.md`: rules for all of the above
- `.agents/rules.local.md`: your personal rules, not committed (list it in
  `.git/info/exclude`). Read after `rules.md`, and found from any worktree.
  A `## Tests` section in any of these files tells agents how to run one test
  file, so they don't run the full suite. The implement-plan and debug-ticket
  skills offer to write that section for you.

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
mcp/servers/               code for MCP servers this repo ships (memory.py, devservers.py), run via {repo}
trackers.json              the tracker choices offered by `agent-setup trackers`
requires.json              which subagents a skill needs, so `agent-setup select` installs them too
bin/agent-setup            the installer
tests/                     unit tests: python3 -m unittest discover -s tests
evals/                     eval harness for the skills and subagents (see evals/README.md)
```

## Where things go

| Kind      | Claude Code                 | Codex                         | OpenCode                          |
|-----------|-----------------------------|-------------------------------|-----------------------------------|
| Skills    | `~/.claude/skills/<name>` → | `~/.agents/skills/<name>` →   | `~/.agents/skills/<name>` →       |
| Subagents | `~/.claude/agents/<name>.md`| `~/.codex/agents/<name>.toml` | `~/.config/opencode/agents/<name>.md` |
| MCP       | user scope via `claude mcp add-json` | managed block in `~/.codex/config.toml` | `mcp.servers` in `~/.config/opencode/opencode.json` |
| Memory guidance | managed block in `~/.claude/CLAUDE.md` | managed block in `~/.codex/AGENTS.md` | managed block in `~/.config/opencode/AGENTS.md` |

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

One file per server. The filename is the server name. In any value, `{repo}` is
replaced at sync time with the absolute path of this checkout (that is how
`mcp/memory.json` finds `mcp/servers/memory.py`); moving the repo needs a re-sync.

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
