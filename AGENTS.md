# agent-setup: instructions for AI agents

This repo is the single source for the user's skills, subagents and MCP servers.
`bin/agent-setup` installs them globally into Claude Code, Codex, OpenCode and
`~/.agents/skills`. The human manual is `INSTALL.md`, and the formats are in `README.md`.

## Setting up (when asked to install, set up, or update this)

Follow these steps exactly. Don't improvise the install.

1. **Check prerequisites.** Run `./bin/agent-setup doctor`. If Python 3.11+ or git
   is missing, stop and tell the user. Missing agent CLIs are fine.
2. **Preview.** Run `./bin/agent-setup validate`, then
   `./bin/agent-setup sync --dry-run`. Show the user a short summary of what will
   be installed.
3. **Handle conflicts.** If the preview has any `CONFLICT` lines, **stop and ask**.
   Something with that name already exists and isn't managed by agent-setup.
   Never use `--adopt` unless the user explicitly says to take over that MCP
   server. Never delete their files to make room.
4. **Ask about trackers.** Ask the user which ticket trackers they use:
   `github`, `jira`, `gitlab`, `linear`, or none (they'll paste tickets). If they
   use self-managed GitLab, also ask for the host. Don't guess.
5. **Ask what to install.** Ask whether they want everything or a subset of the
   skills, subagents and MCP servers. List the names with `./bin/agent-setup select`
   if they ask. For a subset, pass `--only=a,b` (just these) or `--skip=a,b`
   (everything but these) to `install.sh`. A skill also installs the subagents it
   needs, and the `memory` and `devservers` instruction blocks follow their MCP servers.
6. **Install.** Once the preview is clean and the user has asked for the install,
   run `./install.sh --yes --trackers=<their answer>` (`--trackers=none` for none),
   plus `--only=...` or `--skip=...` if they chose a subset.
   For a self-managed GitLab host, run
   `./bin/agent-setup trackers --set gitlab --gitlab-host <host>` first. The
   installer re-checks, installs, links `agent-setup` into `~/.local/bin` and
   runs `doctor`. If the user doesn't want the PATH link, add `--no-path`.
7. **Hand off the manual steps.** OAuth sign-ins open a browser, so you can't do
   them. Tell the user which ones `doctor` flagged (`todo`): Claude Code `/mcp`,
   `codex mcp login <name>`, `opencode mcp auth <name>`. Also tell them to restart
   open agent sessions.
8. **Report.** Say what was installed, any skipped items, and what's left for the user.

To update: `git pull`, then steps 2, 3 and 6 (the tracker choice and the item choice are kept).
`sync --yes` never asks. It skips items that are new in the repo and prints how to add them
with `./bin/agent-setup select --add <name>`. Tell the user about any skipped new items.
To change trackers later: `./bin/agent-setup trackers --set <list>`, then `./bin/agent-setup sync`.
To change the chosen items later: `./bin/agent-setup select --add|--remove <list>` (or `--only`,
`--skip`, `--all`, `--ask`), then `./bin/agent-setup sync`.
To remove everything: `./bin/agent-setup uninstall`, and only if the user asks.

## Changing this repo

- Skills go in `skills/<name>/SKILL.md`, following the Agent Skills standard.
  `name` must match the directory. `description` says what the skill does and
  *when to use it*: agents choose skills from this text alone, so list the
  phrasings users actually say.
- Subagents go in `agents/<name>.md`, in the neutral format described in
  README.md. Never edit the generated copies in `~/.claude`, `~/.codex` or
  `~/.config/opencode`.
- MCP servers go in `mcp/<name>.json`. Never put secret values there.
  Reference env vars with `env_from`, `bearer_token_env` or `headers_from_env`.
- Keep skills and subagents tool-agnostic. Don't name tools that only one agent
  has (e.g. "use the Grep tool"). Say what to do ("search the codebase for…").
  If something has to be tool-specific, put it in a per-tool frontmatter block.
- When a skill starts a subagent, add that link to `requires.json` (for example
  `"skills/review-changes": ["agents/code-reviewer"]`). `validate` checks that the names exist.
  It cannot check that no link is missing.
- Subagent bodies can pull in shared files with `<!-- include: path/from/repo/root -->`.
  Edit the included file rather than duplicating its text. Safety rules live in
  `shared/untrusted-content.md` and per-repo rules handling in
  `shared/repo-rules.md`; include them in any new subagent that reads
  user-provided content.
- Subagents end their reports with a fixed sign-off line, which their skill
  checks for. Keep it when you edit them.
- After changes run `./bin/agent-setup validate`, then `./bin/agent-setup sync`.
  For changes to an existing skill or subagent, run its evals
  (`python3 evals/run.py --cases …`; see `evals/README.md`) and compare with the
  previous results.
- `bin/agent-setup` and `evals/run.py` use only the Python standard library. Keep it that way.
- Commit only when the user asks.
