# Plan: Selective install

**Status:** Accepted
**Date:** 2026-11-24
**Scope:** Typical tier. `bin/agent-setup` (new `select` command, selection-aware `sync`/`doctor`/`status`), new `requires.json`,
`install.sh`, docs, one new test file.

## Goal
Users pick which skills, subagents and MCP servers agent-setup installs. The choice is saved per machine and `sync` installs
only the chosen items, removes what it installed for items that were deselected, and asks about items added to the repo later.

## Requirements
- R1: `install.sh` shows each skill, subagent and MCP server as a checklist and saves the choice (user answer).
- R2: `sync` installs only the saved items. Deselecting an installed item removes what agent-setup installed for it (brief).
- R3: A `select` command changes the choice later (user answer).
- R4: When the repo gains an item the saved choice does not mention, `sync` lists it and asks to add it.
  With `--yes` it skips it (user answer).
- R5: Non-interactive runs work: flags select items without a prompt, and no TTY never blocks (brief).
- R6: Dependencies are honored: a skill gets the subagents it delegates to. The memory and devservers instruction blocks
  follow their MCP servers (brief).
- R7: Existing installs keep working after upgrade (brief).
- R8: Stdlib-only Python. `--trackers` and `trackers --set` keep working. AGENTS.md and INSTALL.md match the new flow (brief).

**Non-goals:** changing skill, subagent or MCP source formats. Selecting tracker servers in `mcp/optional/` (trackers own them).
Per-target selection (`--targets` already covers tools).
**Assumptions:**
- A1: Skill-to-subagent links are only those named in the skills' "start the subagent" sections (see Current state).
- A2: A numbered list with `[x]` marks that the user toggles by number counts as the "checklist" (same style as `trackers --ask`).

## Current state
- `cmd_sync` loads every skill, subagent and server and installs all of them (`bin/agent-setup:855`, `:870-909`, `:668`).
- Pruning is already manifest-driven: anything in the old manifest but not installed this run is removed
  (`bin/agent-setup:911-921`, stale MCP `:700-702`). Filtering the sources is enough to get removal on deselect.
- Instruction blocks are named after their servers (`INSTR_NAMES = ("memory", "devservers")`, `:719`). `sync_instructions`
  writes every block (`:793-822`). `remove_block` removes all of them (`:825-835`).
- Tracker servers come from `mcp/optional/` (`load_mcp`, `:354-365`). User choices live in `config.json` (`:374`).
- `cmd_trackers` is the existing pattern for `--ask` / `--set` / show-current and EOF handling (`:400-453`).
- `doctor` flags every repo item that is not installed (`:1041-1067`) and checks sign-in for every server (`:1117-1138`).
- Delegation: plan-architecture -> architect, plan-reviewer. review-changes -> code-reviewer, finding-verifier.
  debug-ticket -> debugger. implement-plan -> implementer. record-feature -> browser-recorder (`skills/*/SKILL.md` grep).
- Subagent includes are expanded from repo files at render time (`:188-203`), so shared files need no selection.

## Decisions
- **D1:** Save the choice in the existing user config under `"selection": {"skills": {name: bool}, "agents": {...}, "mcp": {...}}`.
  A name missing from its map is "new". *Why:* one file already holds per-machine choices, and true/false records both
  "chosen" and "declined" so R4 can tell new items apart. *Rejected:* a separate selection file (second config to find and
  back up). A plain list of chosen names (cannot tell a declined item from a new one).
- **D2:** No `selection` key means "everything selected" and `sync` never prompts. *Why:* that is exactly today's behavior, so
  upgrades change nothing (R7). *Rejected:* deriving the choice from the manifest (manifest drops CONFLICT items, which
  would turn into silent deselections).
- **D3:** Declare dependencies in a new repo file `requires.json`, keyed `"skills/<name>": ["agents/<name>", ...]`, next to
  `trackers.json`. `validate` checks references exist. *Why:* source formats stay unchanged (non-goal).
  *Rejected:* a `requires:` frontmatter key (changes the format). Scanning skill text for names (fragile).
- **D4:** `sync` installs the effective set: selected items plus the closure of their requirements. It prints
  `also installs agents/architect (needed by skills/plan-architecture)`. The saved choice is not rewritten. *Why:* a skill
  never breaks because a needed subagent was unticked. *Rejected:* refusing to save a broken choice (more prompts, same result).
- **D5:** Instruction block `<name>` is written only when MCP server `<name>` is in the effective set. For a tool in the run,
  blocks of unselected servers are removed with `without_block`. *Why:* R6. It only touches our markers.
- **D6:** Selection covers `mcp/*.json` only. Servers from `mcp/optional/` stay controlled by `trackers` and are always kept
  by the filter. *Why:* R8, one owner per server.
- **D7:** New command `agent-setup select`, modeled on `cmd_trackers`. No flags shows the current choice. `--ask` is the
  checklist. `--only LIST` and `--skip LIST` set the whole choice from "all". `--add LIST` and `--remove LIST` change the
  saved choice. `--all` selects everything. It saves and tells the user to run `sync`. Names are bare (`architect`) or
  prefixed (`agents/architect`). A bare name that matches two kinds is an error. *Why:* agents need non-interactive edits
  (R5). *Rejected:* curses arrow-key UI (more code and terminal edge cases, harder to test, different from `trackers --ask`).
- **D8:** Checklist: items grouped by kind, numbered, `[x]`/`[ ]`, short description, and `needs: ...` for skills. Input toggles
  numbers or names. `all` and `none` work. Enter saves. EOF keeps the current choice. With no saved choice all start ticked.
- **D9:** `sync` gets `-y/--yes`. When a choice exists and items are new: dry run lists them as `new (not selected)` and does not ask.
  With a TTY and no `--yes` it asks once: `Add them? [y/N or numbers]`, then records each answer as true/false. With `--yes`
  or no TTY it skips them, prints how to add them, and records nothing, so a later interactive sync asks again. *Why:* R4, R5.
- **D10:** `doctor`, `status` and the sign-in checks use the effective set. `status` also lists unselected items.
  *Why:* otherwise `doctor` reports FIX for every deselected item.
- **D11:** `install.sh` adds `--only=LIST` and `--skip=LIST`. A "Choose what to install" step runs after trackers:
  flags -> `select --only/--skip`. Interactive -> `select --ask`. Otherwise it keeps the saved choice (or all).
  The real install runs `sync --yes` when `--yes` was given.

## Design
### Interfaces
```
agent-setup select [--ask | --only LIST | --skip LIST | --add LIST | --remove LIST | --all]   (mutually exclusive)
agent-setup sync [-y/--yes] ...existing flags
./install.sh [--only=LIST | --skip=LIST] ...existing flags
requires.json: {"$comment": "...", "skills/plan-architecture": ["agents/architect", "agents/plan-reviewer"], ...}
```
### Functions (in `bin/agent-setup`, near the trackers section)
- `load_requires() -> dict[str, list[str]]`, `catalog(skills, agents, servers) -> dict[kind, list[name]]` (excludes `mcp/optional`).
- `effective_selection(cfg, cat) -> (dict[kind, set[name]], notes)`: D2 + D4. Unknown names in the config are ignored.
- `new_items(cfg, cat) -> dict[kind, list[name]]`: empty when there is no `selection` key.
- `filter_sources(skills, agents, servers, eff)`: used by `cmd_sync`, `cmd_doctor`, `cmd_status`. Never by `cmd_validate`.
- `cmd_sync` still loads and validates everything before any write (`:855-860`), then prompts (D9), then filters.

- Readability: prompts follow `cmd_trackers` (`EOFError` handling, whole-config save). Say "selected" for the saved choice
  and "effective" for D4's set. One LIST parser serves the flags and the checklist input.

## Implementation steps
1. Selection core: `requires.json`, `load_requires`, `catalog`, `effective_selection`, `new_items`, `filter_sources`,
   requires checks in `cmd_validate`. Files: `requires.json`, `bin/agent-setup`. *Done when:* `validate` passes and fails on a
   bad reference. Unit tests for closure and new-item detection pass.
2. Selection-aware sync: filter in `cmd_sync`, per-name block handling in `sync_instructions` (D5), `--yes` and the new-item
   prompt (D9). File: `bin/agent-setup`. *Done when:* deselecting an installed skill, subagent or server and syncing removes
   only its files, config entry and block. With no `selection` key the output matches today.
3. `select` command (D7, D8) and selection-aware `doctor`/`status` (D10). File: `bin/agent-setup`. *Done when:* each flag saves the
   expected maps, `trackers` survives a `select`, and `doctor` is clean after syncing a partial choice.
4. `install.sh` flags and step (D11). *Done when:* `./install.sh --yes --only=review-changes --trackers=none` installs that skill
   plus code-reviewer and finding-verifier only. `./install.sh --yes` on an existing install keeps its choice.
5. Docs: AGENTS.md setup steps (ask "everything or a subset?", pass `--only/--skip`), INSTALL.md (new section, day-to-day
   rows, `install.sh` step list), README.md (`requires.json`, `select`), `skills/agent-setup/SKILL.md` rows for choosing and
   removing items. *Done when:* every flag in steps 3-4 is documented and `agent-setup validate` and `sync` run clean.

## Test plan
- New `tests/test_selection.py`, reusing the `TempHomeCase` temp-home pattern from `tests/test_instructions_block.py:28-62`.
  Run with `python3 -m unittest discover -s tests -p test_selection.py`. Full suite once: `python3 -m unittest discover -s tests`.
- Cases: no `selection` key installs all and never prompts (R7). `--only` plus closure (D4). Deselect after install removes
  the skill symlink, rendered subagent files and the MCP entry (R2). Deselecting `memory` removes only the memory block (D5).
  New item with `--yes` and with no TTY is skipped and not recorded. Dry run never prompts (D9). `trackers --set` after `select`
  keeps both keys (R8). Ambiguous bare name errors (D7). `validate` rejects an unknown name in `requires.json` (D3).
  `doctor` is clean after a partial sync (D10).
- Manual: run `./install.sh` in a terminal once. No eval cases exist for the agent-setup skill.

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| A user unticks a subagent and is confused that it stays | Medium | D4 note line in `sync` and `status` names the skill that needs it |
| `requires.json` misses a new skill->subagent link | Medium | A line in AGENTS.md "Changing this repo". `validate` catches bad names |
| Agents running `install.sh --yes` for updates never see new items | Medium | `sync --yes` prints each skipped item and the `select --add` command |

## Open questions
None. Answered 2026-11-24:
- **Q1:** Enter skips new items (`[y/N]`), as D9 says.
- A1 and A2 confirmed by the user.

## Conformance checklist
- [ ] C1: The choice is stored under `selection` in `~/.config/agent-setup/config.json` as per-kind name->bool maps (D1, step 3)
- [ ] C2: With no `selection` key, `sync` installs every item and never prompts (D2, step 2)
- [ ] C3: `requires.json` lists the five skill->subagent links, and `validate` fails on an unknown reference (D3, step 1)
- [ ] C4: `sync` installs required subagents of selected skills and prints a note. The saved choice is unchanged (D4, step 2)
- [ ] C5: Deselecting an item and syncing removes its installed files or MCP entry only via the manifest pruning path (R2, step 2)
- [ ] C6: Instruction blocks are written only for selected servers, and unselected blocks are removed by marker (D5, step 2)
- [ ] C7: `mcp/optional` servers are never filtered by the selection (D6, step 1)
- [ ] C8: `select` has `--ask/--only/--skip/--add/--remove/--all`, rejects ambiguous names, keeps `trackers` (D7, step 3)
- [ ] C9: New items: dry run lists them, `--yes` or no TTY skips without recording, interactive answers are recorded (D9, step 2)
- [ ] C10: `doctor` and `status` use the effective set. `validate` still checks every source (D10, step 3)
- [ ] C11: `install.sh` accepts `--only=`/`--skip=`, runs `select`, and passes `--yes` to `sync` (D11, step 4)
- [ ] C12: `tests/test_selection.py` covers the cases in the test plan. AGENTS.md, INSTALL.md, README.md and the agent-setup
  skill document `select` and the new flags (steps 1-5)

## Deviation log

