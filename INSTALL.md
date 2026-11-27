# Installing and using agent-setup

This repo installs one shared set of skills, subagents and MCP servers into
every coding agent on your machine: Claude Code, Codex and OpenCode, plus
agents that read `~/.agents/skills` (Cursor, Gemini CLI, Amp and others).
Everything is installed **globally** for your user, so it works in every
project. This repo is the source you edit.

## 1. Prerequisites

| Need | Check | Notes |
|---|---|---|
| Python 3.11+ | `python3 -V` | standard library only, no `pip install` |
| git | `git --version` | |
| At least one agent CLI | `claude --version`, `codex --version`, `opencode --version` | missing tools are fine; their files are written anyway and work once you install the tool |

## 2. Install

```sh
git clone <this repo> ~/agent-setup
cd ~/agent-setup
./install.sh
```

What `install.sh` does, in order:
1. Checks Python and git, and lists which agent CLIs it found.
2. Validates every skill, subagent and MCP definition in the repo.
3. Asks which ticket trackers you use (see step 3). Skip the question with
   `--trackers=github,jira` or `--trackers=none`.
4. Asks which skills, subagents and MCP servers to install (see [Choose what to install](#3a-choose-what-to-install)).
   Skip the question with `--only=a,b` or `--skip=a,b`.
5. Shows a **preview** of every file and config entry it will create. Nothing is changed yet.
6. Asks `Install the above? [y/N]`. Use `./install.sh --yes` to skip both questions.
7. Installs (`agent-setup sync`) and links `agent-setup` into `~/.local/bin`
   (skip that with `--no-path`).
8. Runs `agent-setup doctor` to verify.

If the preview shows **CONFLICT** lines, it stops without changing anything. See [Conflicts](#conflicts).

## 3. Ticket trackers

`install.sh` asks which trackers you use, so `debug-ticket` can fetch tickets
itself. Pasted ticket text always works, even with none chosen.

| Choice | What gets set up | You do once |
|---|---|---|
| `github` | nothing extra, it uses the `gh` CLI | `gh auth login` |
| `jira` | Atlassian's official MCP server (`mcp.atlassian.com/v2/mcp`, Atlassian Cloud) | OAuth sign-in (below) |
| `gitlab` | GitLab's official MCP server (`<host>/api/v4/mcp`; asks for your host, default gitlab.com) | OAuth sign-in, or `glab auth login` |
| `linear` | Linear's official read-only MCP server | OAuth sign-in |

> **GitLab tokens:** prefer `glab auth login` (stored in glab's own config) or
> `GITLAB_API_TOKEN`. Avoid exporting `GITLAB_TOKEN` globally, because OpenCode
> treats it as a GitLab Duo login and can switch its AI provider.

> **Codex:** its sandbox blocks network by default, so Codex can't `curl` tracker APIs.
> It can still use MCP servers (they run outside the sandbox), so in Codex choose the
> MCP-based option for Jira, GitLab and Linear.

Your choice is stored on this machine only, in `~/.config/agent-setup/config.json`,
so people sharing the repo can choose differently. To change it later:

```sh
agent-setup trackers --ask              # or: agent-setup trackers --set github,jira
agent-setup sync                        # installs/removes the matching MCP servers
```

**OAuth sign-in** (once per tool, opens a browser): Claude Code `/mcp`, Codex
`codex mcp login <name>`, OpenCode `opencode mcp auth <name>`. The `<name>` is
`atlassian`, `gitlab` or `linear`. `agent-setup doctor` lists which are still pending.

## 3a. Choose what to install

By default `sync` installs every skill, subagent and MCP server in the repo.
To install only some, save a choice:

```sh
agent-setup select                      # show the current choice
agent-setup select --ask                # checklist: toggle numbers or names, 'all', 'none', Enter saves
agent-setup select --only review-changes,memory   # just these
agent-setup select --skip record-feature          # everything except these
agent-setup select --add debug-ticket             # change the saved choice
agent-setup select --remove memory
agent-setup select --all                          # back to everything
agent-setup sync                        # installs the chosen items, removes what it installed for the rest
```

Names are bare (`architect`) or prefixed (`agents/architect`). Use the prefix when
a bare name matches two kinds. `install.sh` takes `--only=LIST` and `--skip=LIST`
and runs the same command.

- **Needs.** A skill also installs the subagents it starts, even if you did not pick them.
  `sync`, `status` and `doctor` print a line like
  `also installs agents/architect (needed by skills/plan-architecture)`.
  The links are in `requires.json`. Your saved choice is not changed.
- **Instruction blocks.** The `memory` and `devservers` blocks in each tool's instruction
  file follow their MCP servers. Deselect a server and `sync` removes its block.
- **Trackers.** Tracker servers (`jira`, `gitlab`, `linear`) are not part of this choice.
  `agent-setup trackers` controls them.
- **New items.** When a `git pull` adds an item that your choice does not mention, `sync`
  lists it. In a terminal it asks `Add them? [y/N or numbers/names]`. Enter skips them.
  With `--yes`, `sync --dry-run` or no terminal, it skips them, records nothing and
  prints the `select --add` command. The next interactive `sync` asks again.
- **Existing installs.** Without a saved choice nothing changes: `sync` installs everything
  and never asks.

The choice is stored on this machine only, under `selection` in `~/.config/agent-setup/config.json`.

## 3b. Shared memory

`sync` installs a `memory` MCP server (`mcp/servers/memory.py`) in all three agents,
plus a short managed block of guidance in `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`
and `~/.config/opencode/AGENTS.md` (only the text between its markers is touched).
Memories are Markdown files in `~/.local/share/agent-memory`
(`$XDG_DATA_HOME/agent-memory`, or `$AGENT_MEMORY_DIR` if set): `global/` plus one
`projects/<key>/` folder per git repo. The same path is used on macOS, Linux and
WSL2; on WSL2 keep it in the Linux home, not under `/mnt/c`. `uninstall` never
deletes it. Needs `python3` on the agents' PATH, and a re-sync if you move this repo.

1. **Import your existing Claude memories** (optional; the originals stay untouched,
   and it can be re-run):

   ```sh
   python3 mcp/servers/memory.py import-claude --dry-run   # preview
   python3 mcp/servers/memory.py import-claude
   ```

   `type: user` files go to `global/`, the rest to the folder of the same project.
2. **Turn off Claude Code's built-in auto-memory**, so it doesn't compete with the
   server. Add `"autoMemoryEnabled": false` to `~/.claude/settings.json` (or toggle it
   with `/memory`). agent-setup never writes that file. Setting
   `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` also works, but `=0` forces it back on and
   outranks the setting. Reference:
   <https://code.claude.com/docs/en/settings-reference> (`autoMemoryEnabled`) and
   <https://code.claude.com/docs/en/env-vars>. `agent-setup doctor` shows `todo` until it's off.
3. Restart open agent sessions, then ask each CLI to search memory; it should list the
   imported memories.

## 3c. Dev servers

`sync` also installs a `devservers` MCP server (`mcp/servers/devservers.py`) in all
three agents, and a second managed block of guidance next to the memory one. It starts,
watches and stops dev servers per git worktree (see the README for the config format).
State lives in `~/.local/state/devservers` (`$XDG_STATE_HOME/devservers`, or
`$DEVSERVERS_DIR` if set); on WSL2 keep it in the Linux home, not under `/mnt/c`.
`uninstall` never deletes it. Needs `python3` on the agents' PATH, plus whatever
toolchain the project's commands use (node, bundle, uv, ...).

1. **Nothing to approve at install time.** A project opts in with
   `.agents/devservers.json` (or the personal `.agents/devservers.local.json`). The agent
   proposes one when there is none, and you confirm it.
2. **Approving a config.** A new or changed config does not run until you approve it.
   The agent shows you the commands and a hash and calls `trust` once you agree (your
   client asks you before that call). Or do it yourself from a terminal:

   ```sh
   python3 mcp/servers/devservers.py trust /path/to/worktree
   ```
3. **Codex** pre-approves only `status`, `logs` and `wait_ready`; it asks for the rest.
   Claude Code and OpenCode ask before each tool call unless you allow the tools.
4. **PATH.** Servers inherit the PATH of the agent client. If a command exits 127
   (not found) in Codex, tell your client to pass PATH on, or start it from a shell
   that has it.
5. Restart open agent sessions, then ask one to run `status` from a project.

## 3d. Postgres (read-only)

`sync` also installs a `postgres` MCP server (`mcp/servers/postgres.py`) in all three
agents. It lets an agent look at a worktree's **development** database through the `psql`
CLI (12 or newer; `agent-setup doctor` shows whether it is on PATH). It has no managed
instruction block. A project that is not configured gets a `NOT CONFIGURED:` answer with
these steps. Codex pre-approves `schema`, `query` and `explain`. Deselect it with
`agent-setup select --remove postgres` if you do not want it.

1. **Create a read-only role** on the dev database (never production). The server refuses
   a role that can write:

   ```sql
   CREATE ROLE agent_ro LOGIN PASSWORD '<password>';
   GRANT CONNECT ON DATABASE <database> TO agent_ro;
   GRANT USAGE ON SCHEMA public TO agent_ro;
   -- PostgreSQL 14 and newer:
   GRANT pg_read_all_data TO agent_ro;
   -- PostgreSQL 12 and 13 (repeat per schema; <owner> is the role that creates your tables):
   GRANT SELECT ON ALL TABLES IN SCHEMA public TO agent_ro;
   ALTER DEFAULT PRIVILEGES FOR ROLE <owner> IN SCHEMA public GRANT SELECT ON TABLES TO agent_ro;
   -- PostgreSQL 14 and older let every role create objects in public (this affects all roles):
   REVOKE CREATE ON SCHEMA public FROM PUBLIC;
   ```
2. **Write the personal config** `.agents/postgres.local.json` in the worktree (or the main
   checkout; not committed, list it in `.git/info/exclude`). Exactly one of:

   ```json
   {"service": "myapp_ro"}
   ```
   a libpq service from `~/.pg_service.conf`, with the password in `~/.pgpass`; or

   ```json
   {"url_env": "AGENT_DATABASE_URL", "env_file": ".env"}
   ```
   an environment variable that holds `postgres://agent_ro:<password>@localhost/<database>`,
   looked up in `env_file` (default `.env`) of the worktree, then of the main checkout, then
   in the process environment. Do not point it at the app's `DATABASE_URL`: that is
   usually the owner role. Optional keys: `allow_remote` (default false: only a Unix socket,
   `localhost`, `127.0.0.0/8` and `::1` are accepted), `max_rows` (100, up to 1000),
   `timeout_ms` (10000, up to 60000). Unknown keys are refused.

   `env_file` can also be a list of files, tried in order in each place. Set
   `worktree_env_only: true` when each worktree has its own database: then only the
   worktree's files are read, never the main checkout's files or the process environment.

   For a local dev database only, `role_check: false` lets the server use the app's own
   role, for example `{"url_env": "DATABASE_URL", "env_file": ["server/.env",
   ".agents/postgres.local.env"], "worktree_env_only": true, "role_check": false}`. The
   server still runs the role check and still refuses remote hosts, but it does not refuse a
   role that can write. Then the read-only transaction, the one-statement rule and the
   SELECT-only rule are the only guards. A role that can write can still call functions
   whose effects a rollback does not undo, such as `pg_terminate_backend`,
   `pg_cancel_backend`, `pg_reload_conf` and the server file functions. `role_check: false`
   cannot be combined with `allow_remote: true`. URL parameters other than
   `sslmode`, `sslrootcert`, `sslcert`, `sslkey`, `connect_timeout`, `host` and `port` are
   refused (`options` could undo the read-only settings).
3. **Check it** from a terminal: `python3 mcp/servers/postgres.py check /path/to/worktree`
   prints the resolved config, the host, the role check and the warnings below.
4. Restart open agent sessions, then ask one to run `schema` from the project.

**Refusals you may hit.** The server fails closed when it cannot prove a setting is yours:

- `.agents/postgres.local.json` must be a real, untracked file: not a symlink (nor under a
  symlinked directory), not tracked by git (also under another letter case), and not inside a
  submodule or nested repository. If git itself fails inside a repository, it refuses too.
  List the file in `.git/info/exclude`.
- With `allow_remote: true`, the `env_file` must pass the same test, because otherwise repo
  content could choose the database.
- In service mode the service must be found in `$PGSERVICEFILE` (or `~/.pg_service.conf`) or
  in the system service file, and its `host` and `hostaddr` must be loopback or a socket
  unless `allow_remote` is true. A service that uses `ldap` or has a syntax error is refused.
- On Linux without `pg_config` (Debian: `libpq-dev`), the system service file location is
  unknown: set `PGSYSCONFDIR` if a service is defined only there.

**What the role check does not cover.** It checks the role, not everything the role can
reach: SECURITY DEFINER functions owned by a role that can write, the `dblink` and
`postgres_fdw` extensions, temporary tables (every role has TEMP on the database), and
`set_config('statement_timeout', ...)` inside a query (the server kills `psql`, but the
backend may keep running). Keep the dev database free of those, or do not use this server.

## 4. Verify

```sh
agent-setup doctor
```

You want `ok` on every line. `todo`/`info` lines tell you about sign-ins
you haven't done yet, and `FIX` lines say exactly what to run.

Then **restart any open agent sessions** and try it in a real repo:
- "review my changes before I merge" → `review-changes` skill → `code-reviewer` subagent
- "does issue #123 reproduce?" (or paste a bug report) → `debug-ticket` skill → `debugger` subagent

## 5. Day to day

| Task | Command |
|---|---|
| Pull updates and reinstall | `git pull && agent-setup sync` |
| See what's installed | `agent-setup status` |
| Check health | `agent-setup doctor` |
| Preview a change | `agent-setup sync --dry-run` |
| Choose what gets installed | `agent-setup select --ask`, then `agent-setup sync` |
| Add or remove one item | `agent-setup select --add <name>` or `--remove <name>`, then `agent-setup sync` |
| Sync without any question | `agent-setup sync --yes` (skips new items) |
| Install for some tools only | `agent-setup sync --targets claude,codex` |
| Remove everything it installed | `agent-setup uninstall` |

When do you need to re-sync?
- **Editing an existing skill:** no. Skills are symlinks into this repo, so edits are live.
- **After adding, renaming or removing a skill:** yes.
- **After editing a subagent, an MCP server, or anything in `shared/` or a skill's `references/`:**
  yes. These are rendered into each tool's own format.

## 6. Add your own

```sh
agent-setup new skill my-skill      # skills/my-skill/SKILL.md
agent-setup new agent my-agent      # agents/my-agent.md
agent-setup new mcp my-server       # mcp/my-server.json
# edit the file, then:
agent-setup validate && agent-setup sync --dry-run && agent-setup sync
```

Formats and options are in [README.md](README.md) (subagent format, MCP format,
shared includes). You can also just ask any agent: "add a skill to agent-setup
that…". The `agent-setup` skill knows the workflow.

**Per-project tweaks:** add `.agents/review.md`, `.agents/debug.md` or
`.agents/rules.md` *inside a project's repo* to give the shared agents
project-specific rules. See README, "Per-repo rules".

## Conflicts

`sync` only overwrites or removes things it created; it keeps a manifest of
those in `~/.local/state/agent-setup/manifest.json`. If a skill, subagent or
MCP server with the same name already exists and wasn't created by
agent-setup, you'll see `CONFLICT` and that item is skipped. Fix it one of these ways:
- rename yours, or delete the existing one if you don't need it;
- for MCP servers only, take the existing entry over with `agent-setup sync --adopt`.
  It's replaced by the repo's version. Uninstalling later removes it completely.

## Troubleshooting

| Symptom | Fix |
|---|---|
| A skill or subagent doesn't show up | restart the agent session; run `agent-setup doctor` |
| `doctor` says "out of date" | `agent-setup sync` |
| An MCP server shows "needs authentication" | do that tool's sign-in (step 3) |
| OpenCode config not updated | `~/.config/opencode/opencode.json` must be plain JSON (no comments) for agent-setup to edit it |
| Codex `config.toml` looks wrong | agent-setup only edits the block between its `>>> agent-setup` markers; a backup is at `config.toml.agent-setup.bak` |
| Debugger can't install dependencies in Codex | Codex's sandbox blocks network by default; the debugger reports `Blocked`. Run it in Claude Code or OpenCode, or install the dependencies yourself |

## Uninstall

```sh
agent-setup uninstall     # removes every skill link, subagent file and MCP entry it created
rm ~/.local/bin/agent-setup
```

Your own skills, agents and MCP servers are never touched.
