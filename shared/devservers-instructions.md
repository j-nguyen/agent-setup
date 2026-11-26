## Dev servers

You can run, watch and stop this project's dev servers through the `devservers` MCP server. Every coding agent on this machine shares one registry, so a server another agent started shows up in `status`.

- Pass `project_path` set to the absolute path of the worktree you work in. Each worktree has its own instance, ports and log.
- Start with `status`. Use `start` with `setup_if_needed=true` to run required setup and start the server. If setup is still running, wait with `task="setup"` and repeat `start` once it succeeds. Use `wait_ready` for the server and repeat it when it reports `waiting`.
- Read output with `logs`. Keep the `next since=` cursor it returns and pass it as `since` next time to get only new lines. Use `grep` to narrow them.
- Use `restart` after a change that needs it and `stop` when you are done. Do not start servers by hand with `npm run dev` or similar, so the registry stays accurate.
- Only commands from the project's config run (`.agents/devservers.json`, or the personal `.agents/devservers.local.json`). When the config is new or changed, `start` and `setup` refuse and show the commands and a hash. Show them to the user. Call `trust` with that hash only after the user approves, never on your own.
- With no config, `start` proposes one. Show the proposal to the user. Call `configure` only after they agree, with scope `team` (committed) or `local` (personal).
