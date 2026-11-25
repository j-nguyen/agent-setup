---
name: agent-setup
description: >
  Manage the user's shared skills, subagents and MCP servers that are installed into
  every coding agent (Claude Code, Codex, OpenCode, and agents that read ~/.agents/skills).
  Use when the user asks to install, add, create, update, remove or list a skill,
  subagent or MCP server "for all my agents" / "globally" / "in agent-setup", asks to
  sync or check their agent setup, or asks why a shared skill or subagent isn't showing up.
---

# Manage agent-setup

The user keeps one source repo for the skills, subagents and MCP servers that all
of their coding agents share. A `sync` command installs everything into each
tool's global config. **Never hand-edit the installed copies** (in `~/.claude`,
`~/.codex`, `~/.config/opencode` or `~/.agents`). Change the source repo, then sync.

## Find the repo

This skill lives inside that repo, so its directory is a symlink into it. Resolve the real path:

```sh
repo=$(cd "$(dirname "$(realpath <path to this SKILL.md>)")/../.." && pwd)
"$repo/bin/agent-setup" status
```

If `agent-setup` is on PATH, `agent-setup status` prints the source path too.
Read the repo's `AGENTS.md` before changing anything. It has the conventions and
the file formats.

## Common tasks

| User wants | Do |
|---|---|
| A new skill | `agent-setup new skill <name>`, write `skills/<name>/SKILL.md`, then validate + sync |
| A new subagent | `agent-setup new agent <name>`, write `agents/<name>.md` (set `access:`), then validate + sync |
| A new MCP server | `agent-setup new mcp <name>`, edit `mcp/<name>.json` (env var *names* only, never secret values), then validate + sync |
| Change an existing one | edit its source file in the repo, then validate + sync |
| Remove one | delete its source, then `agent-setup sync` (sync prunes what it installed) |
| Choose ticket trackers | ask the user which ones they use, then `agent-setup trackers --set github,jira` (or `none`), then sync |
| Install only some items | ask which ones, then `agent-setup select --only a,b` (or `--skip a,b`), then sync. A skill also installs the subagents it needs (`requires.json`) |
| Stop installing one item | `agent-setup select --remove <name>`, then sync. Sync removes only what it installed for that item |
| Start installing one item | `agent-setup select --add <name>`, then sync |
| Sync without questions | `agent-setup sync --yes`. It skips new items and prints the `select --add` command. Tell the user about them |
| Check the setup | `agent-setup doctor` |
| See what's installed | `agent-setup status` |

Always run these in order: `agent-setup validate`, then `agent-setup sync
--dry-run`, then show the user the preview. Run `agent-setup sync` once it
looks right.

## Rules

- **Conflicts**: if the dry run shows `CONFLICT`, something with that name
  already exists and isn't managed by agent-setup. Stop and ask the user. Only
  use `sync --adopt` (MCP servers only) when they say to take it over.
- **Sign-ins**: OAuth logins (`/mcp` in Claude Code, `codex mcp login <name>`,
  `opencode mcp auth <name>`) open a browser. Tell the user to run them; don't try yourself.
- **Secrets** never go in the repo. Reference environment variables (`env_from`,
  `bearer_token_env`, `headers_from_env`).
- **Commits**: the repo is the user's; commit only when asked.
- After a sync, remind the user to restart open agent sessions to pick up new skills or subagents.
