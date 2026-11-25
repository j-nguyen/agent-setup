# Plan: Dev-server manager MCP server

**Status:** Accepted
**Date:** 2026-11-24
**Scope:** Large tier. New stdio server `mcp/servers/devservers.py`, `mcp/devservers.json`, a second instruction block, tests, docs.

## Goal
One local MCP server lets Claude Code, Codex and OpenCode set up, start, watch and stop dev servers per worktree, running only
commands from a trusted project config, for any stack.

## Requirements
- R1: Tools `start`, `status`, `logs`, `wait_ready`, `stop`, `restart` and a `setup` step; stdlib Python, stdio, one file in `mcp/servers/`.
- R2: Processes run detached in their own process group and outlive the session; `stop` kills the whole group.
- R3: One registry shared by all agents and sessions; starting a running server returns it; each worktree has its own instances.
- R4: No config: `start` only proposes; on confirmation write `.agents/devservers.json` or `.agents/devservers.local.json`
  (personal, overrides); then only file commands run.
- R5: A new or changed config needs one user approval, remembered by content hash, in all three agents.
- R6: `logs`: raw lines, `since` cursor, `grep`, line cap; `status` gives the log path.
- R7: `setup` delegates to a project command, else a default: slot N (main 0), copy ignored files from main, install,
  `after_install`, env file with base+N ports and `COMPOSE_PROJECT_NAME`.
- R8: `ports_from`; `preflight` (optionally in main); `max_running`; ready by log regex or port. R9: clean env per worktree.
- R10: Reap dead entries on read; idle timeout off by default; `instructions` plus a managed block.
- R11: Same on macOS, Linux, WSL2, no OS branches; state in the Linux home. R12: no Codex auto-approval. R13: stack examples.

**Non-goals:** creating/removing worktrees; deploys; per-worktree Postgres; remote machines; Windows-native agents.
**Assumptions:**
- A1: `ps -o lstart= -p <pid>` gives a stable start-time string on macOS and Linux (checked on Linux only).
- A2: The server inherits a PATH that finds the project's toolchain in all three clients (unverified for Codex).
- A3: Claude Code and OpenCode prompt before an MCP tool call unless the user allowed it (unverified).
- A4: `docs/plans/shared-memory-mcp.md` is missing here; precedent is the memory code.

## Current state
- `mcp/servers/memory.py:106-121` project root = parent of the git common dir, key via `slugify_path` (101).
- `memory.py:222` `write_atomic`; `ensure_dir` (130); `NAME_RE` (28); JSON-RPC loop, `instructions`, `ToolError` (373-435).
- `bin/agent-setup:335` fills `{repo}`; `mcp_codex` merges `codex` keys (493) via `toml_inline` (520): nested per-tool tables work as is.
- `bin/agent-setup:719-810` one block from `shared/memory-instructions.md`, markers 720-721; doctor 1025, WSL `/mnt` warning 1042.
- `bin/agent-setup:945` "kept in sync by hand" helper; `tests/test_memory_server.py:11-18` loads the server by path, temp git repos.

## Options considered
| Option | Summary | Pros | Cons |
|---|---|---|---|
| A. Detached groups | Spawn/inspect `setsid` groups; JSON state | Stdlib, no daemon | No exit codes for non-children |
| B. Daemon | Supervisor behind a Unix socket | Exit codes, timers | Lifecycle, socket auth: 2x code |
| C. External | overmind/pm2/tmux/systemd/launchd | Mature | Not stdlib; per-OS |
**Chosen:** A: least moving parts for R2/R3/R11; D1's exit marker closes the exit-code gap.

## Decisions
- **D1:** Spawn `/bin/sh -c '<cmd>; echo "[devservers] exited $?"'`, `start_new_session=True`, cwd = worktree, stdin `/dev/null`,
  stdout+stderr into one log. *Why:* own group (R2), ordered lines, exit code for later readers. *Rejected:* split files; pipes.
- **D2:** State dir `$DEVSERVERS_DIR`, else `$XDG_STATE_HOME/devservers`, else `~/.local/state/devservers`; per project key:
  `instances/`, `logs/`, `slots.json`, `setup/`, `trust.json`. *Why:* R3, R11. *Rejected:* slots in the git common dir
  (second lock); repo-local state (a clone could pre-seed it).
- **D3:** Per-project `mkdir` lock with an `owner` file (pid + A1 token); dead owner taken over; 10 s wait; held only for
  read-modify-write, never while a command runs or waits. *Why:* borderpass's proven pattern.
- **D4:** Alive = `os.killpg(pgid, 0)` succeeds and the leader's start token matches if it lives; `waitpid(WNOHANG)` own children first.
  Every read reaps: dead -> `last_exit` (marker code, time, log), not counted; gone worktree -> record deleted, slot freed.
- **D5:** `stop` sends `stop_signal` (default TERM) to the group, waits `stop_timeout` (10 s), then KILL and says so.
  `restart` = stop + start. *Why:* R2; INT suits Compose/foreman.
- **D6:** Config = team file merged with local: top-level keys replace, `servers` merge by name. Strict schema. No config ->
  proposal (D12). `configure(config, scope)` validates, writes the file, excludes the local file via `<common>/info/exclude`,
  and trusts what it wrote (the user just confirmed it). *Why:* R4.
- **D7:** Trust = SHA-256 of the merged config's canonical JSON, stored with a copy in `trust.json`. Untrusted: command tools return
  the commands, a diff from the trusted copy, the hash and "ask the user; call `trust` only after they approve". `trust(hash)` must
  match the files; `devservers.py trust <path>` asks y/N in a terminal. *Why:* R5 through each client's own tool prompt.
  *Rejected:* MCP elicitation (client support unverified); per-command hashes.
- **D8:** `setup` string = delegated; object = default {`copy`, `install`, `after_install`}. Runs detached as task `setup`
  (logs/wait_ready work; no tool timeout). Success writes a marker (lockfile digest + config hash); `start` refuses when it is missing
  or stale (Q3: refuse), and its error names the next calls: `setup(path)`, then `wait_ready(path, task="setup")`, then `start`. Default: take slot, copy from main only if absent (relative, no `..`; skipped in main), install, after_install, write
  `.env.devservers` and exclude it. *Why:* R7 with no edits to project files.
- **D9:** Child env: server env minus built-ins (port keys, `COMPOSE_PROJECT_NAME`, `DEVSERVERS_*`, `VIRTUAL_ENV`, `BUNDLE_GEMFILE`,
  `INIT_CWD`, `npm_*`), minus `ports_from.env_file` keys and `env_strip`; plus `env`, `DEVSERVERS_SLOT`, `DEVSERVERS_WORKTREE`, ports,
  and for slot >= 1 `COMPOSE_PROJECT_NAME=<repo>-wt<N>` (`[a-z0-9_-]`). Injection is the mechanism; the file is for IDEs/shells.
- **D10:** `ports` {KEY: base} -> base + slot (slots 0-49; bases < 50 apart is an error); `ports_from.env_file` for delegated setups;
  `ready.log` named groups record self-chosen ports. Known ports are test-bound on 127.0.0.1 first; busy -> error naming the holder.
- **D11:** `wait_ready` polls `ready.log` and/or `ready.port` (TCP); default 60 s, max 240 s per call; returns ready, waiting or
  exited (last 30 lines). *Why:* stay under client tool timeouts (Codex 300 s).
- **D12:** Proposals hold literal commands, so the hash covers what runs: install from the lockfile's tool (npm ci, bundle install,
  uv sync, mix deps.get, …); servers from `package.json` `dev*`, Procfiles, `bin/dev`, `bin/setup --skip-server`, `mix.exs`,
  `manage.py`, `artisan`, `go.mod`, `Cargo.toml`, compose files.
- **D13:** One log per run (previous kept as `.1`); cursor `"<run_id>:<offset>"`, old-run cursor restarts at 0; no `since` = tail;
  `max_lines` 200 (max 2000); ANSI stripped in output only.
- **D14:** `max_running` counts live servers (not tasks) per project, under the lock. `idle_timeout_minutes` (0 = off): stop an
  instance untouched by tool calls that long, at the next reap.
- **D15:** Copy `project_root`, `slugify_path`, `ensure_dir`, `write_atomic` and the JSON-RPC loop from `memory.py`, marked
  "kept in sync". *Rejected:* a shared module (breaks the one-file rule).
- **D16:** Own block: generalise the block code to `("memory", "devservers")`, markers derived from the name (memory's unchanged).
  *Rejected:* sharing the memory block (markers say memory); `instructions` field only.
- **D17:** Codex block `{"tools": {"status"|"logs"|"wait_ready": {"approval_mode": "approve"}}}` (Q1); every other tool prompts.
  Annotations: `status`, `logs`, `wait_ready` `readOnlyHint: true`; `stop`, `restart` `destructiveHint`.

## Design
### Interfaces
All tools take `project_path` (absolute worktree path); `name` defaults to the server with `"default": true`.
```
status(project_path?, all_projects?)  start(name?)  setup()  stop(name?)  restart(name?)  trust(hash)
logs(name?, since?, grep?, max_lines?) -> lines + next cursor     wait_ready(name?, timeout_sec?) -> ready|waiting|exited
configure(config, scope: "team"|"local")
```
```json
{"setup": "yarn wt setup" | {"copy": [".env"], "install": "npm ci", "after_install": "..."},
 "preflight": [{"run": "...", "in": "main", "hint": "..."}], "ports": {"PORT": 3000}, "ports_from": {"env_file": ".env.yarn"},
 "env": {}, "env_strip": [], "max_running": 3, "idle_timeout_minutes": 0,
 "servers": {"dev": {"run": "...", "default": true, "stop_signal": "TERM", "ready": {"log": "re", "port": "PORT", "timeout_sec": 120}}}}
```
### Flow of `start`
1. Resolve worktree and project key; no config -> proposal; untrusted -> trust request (D7).
2. Check setup marker (D8); run `preflight` (30 s each) and fail with its hint.
3. Under lock: reap; live record -> return it; `max_running`; port check; spawn; write record atomically after spawn; release.

## Stack examples
Commands run through `sh`, so `$PORT` reaches servers that take the port as an argument.

| Stack | setup | servers.run (ready) | ports |
|---|---|---|---|
| borderpass | `"yarn wt setup"`; preflight MiniStack, in main | `yarn dev`, `yarn dev:no-worker` (log `Ready in`) | `ports_from .env.yarn`; max 3 |
| hockey-simulation | `{install: npm ci}` | `npm run dev` (log `Local:.*:(?P<VITE_PORT>\d+)`) | captured; max 1 |
| financial-planner | `{copy: [.env], install: npm ci}`; preflight db in main | `npm run dev:all` (port SERVER_PORT) | SERVER_PORT 3000 |
| dingdong-discord | `{copy: [.env], install: npm ci}` | `npm run dev` (log only) | none; max 1 |
| Rails 7.1+ | `{copy: [.env, config/master.key], install: bundle install, after_install: bin/rails db:prepare}` | see trap | PORT 3000 |
| Django + uv | `{copy: [.env], install: uv sync, after_install: uv run python manage.py migrate}` | see trap | PORT 8000 |
| Go | `{install: go mod download}` | `go run ./cmd/api` (port PORT) | PORT 8080 |
| Rust | `{install: cargo fetch}` | `cargo run` (port PORT, timeout_sec 900) | PORT 8080 |
| Phoenix | `{install: mix deps.get, after_install: mix ecto.create && mix ecto.migrate}` | `mix phx.server` | PORT 4000 |
| Laravel | `{copy: [.env], install: composer install, after_install: php artisan migrate}` | `php artisan serve --port=$PORT` | PORT 8000 |
| Compose only | `{}` (slot + env file) | `docker compose up`, stop_signal INT | WEB_PORT 8080 |

| Stack | Trap | Handled by |
|---|---|---|
| borderpass | Agent env holds another worktree's `.env.yarn` values; `yarn dev` forks 3 children | D9 strip, Yarn re-injects; D5 group kill |
| hockey-simulation | Fixed userData + `requestSingleInstanceLock` (`electron/main/index.ts:69,82`) | max_running 1 |
| hockey-simulation | better-sqlite3 ABI flips node/electron (`prepare-dev.ts:66,77`); WSL2 needs WSLg | Own `node_modules`; local preflight on `$DISPLAY` |
| financial-planner, dingdong | Compose binds host 5432 in both repos, 6379; Vite bumps 5173 | Share main's db; D10 names holder; log capture |
| dingdong-discord | Two bots on one `BOT_TOKEN` both answer | max_running 1 |
| Rails | `bin/setup` runs `bin/dev`, foreman sets PORT (unverified); stale pid file | run `rm -f tmp/pids/server.pid && exec bin/rails s -p $PORT` |
| Django | runserver takes port as argument (unverified); stale `VIRTUAL_ENV` | run `uv run python manage.py runserver 127.0.0.1:$PORT`; D9 |
| Go | `go run` runs the binary as a child; killing `go run` orphans it | D5 group kill |
| Rust | Cold `target/` per worktree takes minutes; shared target churns (unverified) | Long `timeout_sec`; `waiting` replies |
| Phoenix | `mix setup` reruns seeds; dev.exs may hardcode the DB (unverified) | Split install/after_install; DB shared |
| Laravel | `key:generate` only on first setup (unverified) | Copied `.env` carries `APP_KEY` |
| Compose only | Shared project name; KILL leaves containers; fixed host ports | D9 name; INT + `down` hint; `${WEB_PORT:-8080}:80` |

## Implementation steps
1. Skeleton: `mcp/servers/devservers.py`, `mcp/devservers.json`; JSON-RPC, state dir, identity, config, annotations, `status`
   (D2, D6, D15, D17). *Done when:* `agent-setup validate` passes and `tools/list` returns 9 tools.
2. Trust, `configure`, CLI `trust`, proposals (D6, D7, D12). *Done when:* an untrusted config never spawns.
3. Lifecycle: lock, records, env, start/stop/restart, reaping, limits (D1, D3-D5, D9, D14). *Done when:* a child survives server
   exit and `stop` kills its grandchild.
4. `logs`, `wait_ready`, ports (D10, D11, D13). *Done when:* cursor polls return only new lines.
5. `setup`: delegated and default, slots, copy, env file, marker (D8). *Done when:* two worktrees get slots 1 and 2.
6. Installer: generalised blocks, `shared/devservers-instructions.md`, doctor state-dir line (D16). *Done when:* old block tests pass.
7. Docs: README and INSTALL sections. 8. Manual: all three clients on Linux; the user repeats on macOS and WSL2 (A1, A2).

## Test plan
- Unit (`tests/test_devservers_server.py`, temp repo + worktree and `DEVSERVERS_DIR`, tearDown stops all groups): merge/schema,
  hash per edit, stale-hash trust, proposals. Process (`python3 -c` children): survival, same record, grandchild killed, TERM->KILL,
  zombies, reaping, `max_running`, idle, lock takeover. Env: A's values absent in B. Logs/ready: cursor, grep, ANSI, regex, port.
- Installer: two blocks add/update/remove; memory markers byte-identical.

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Client strips PATH (exit 127) | Medium (Codex) | Hint; add `env_from: ["PATH"]` if step 8 needs it |
| Injected agent calls `trust` | Low-Med | Client prompts (`trust` never pre-approved), instructions, diff shown |
| A1 fails on macOS | Low | pgid check only; test in step 8 |

## Open questions
None. Answered 2026-11-24:
- **Q1:** Pre-approve `status`, `logs`, `wait_ready` in Codex (D17).
- **Q2:** Both: the `trust` tool and the `devservers.py trust <path>` CLI (D7).
- **Q3:** `start` refuses an unset-up worktree and points to `setup` (D8).

## Conformance checklist
- [ ] C1: One stdlib-only file, no import from `memory.py` or `bin/agent-setup` (D15, step 1)
- [ ] C2: `mcp/devservers.json` uses `{repo}`; Codex pre-approves only `status`, `logs`, `wait_ready` (D17, step 1)
- [ ] C3: `tools/list` has 9 tools with D17 annotations (D17, step 1)
- [ ] C4: Merge, strict schema, `NAME_RE` server names (D6, step 1)
- [ ] C5: Nothing runs unless the current hash is trusted; `trust` rejects a stale hash (D7, step 2)
- [ ] C6: `configure` writes only the two config files and `info/exclude` (D6, step 2)
- [ ] C7: Proposals are never executed and hold literal commands (D12, step 2)
- [ ] C8: Spawn: new session, `/dev/null` stdin, merged log, exit marker (D1, step 3)
- [ ] C9: State paths per D2, `write_atomic`, dirs 0700 (D2, step 3)
- [ ] C10: `mkdir` lock with takeover, never held while a command runs (D3, step 3)
- [ ] C11: Zombies reaped before liveness; start token checked; reap on every read (D4, step 3)
- [ ] C12: Second `start` returns the existing record (R3, step 3)
- [ ] C13: `stop` signals the group, KILLs after timeout and reports it (D5, step 3)
- [ ] C14: Env built in D9 order; test shows another worktree's values absent (D9, step 3)
- [ ] C15: `max_running` and idle enforced under the lock; idle off by default (D14, step 3)
- [ ] C16: `logs` and `wait_ready` limits per D11/D13 (step 4)
- [ ] C17: Port assignment, `ports_from`, captures, busy check per D10 (step 4)
- [ ] C18: `setup` runs as a task; never overwrites or writes outside the worktree (D8, step 5)
- [ ] C19: Memory markers unchanged; devservers block synced, doctored, uninstalled (D16, step 6)
- [ ] C20: No `sys.platform` or OS branches in the server (R11, steps 1-5)

## Deviation log

## Noticed along the way
- `mcp/memory.json:5` sets Codex `default_tools_approval_mode = "approve"`, which the brief says the user has not decided.
