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
4. Shows a **preview** of every file and config entry it will create. Nothing is changed yet.
5. Asks `Install the above? [y/N]`. Use `./install.sh --yes` to skip both questions.
6. Installs (`agent-setup sync`) and links `agent-setup` into `~/.local/bin`
   (skip that with `--no-path`).
7. Runs `agent-setup doctor` to verify.

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
