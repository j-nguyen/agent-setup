## Memory

You have a shared, persistent memory through the `memory` MCP server. Every coding agent on this machine reads and writes the same store. Use it instead of any built-in memory files.

- At the start of a task, call `search` with no query and `project_path` set to the absolute path of the project you are working in. That lists the global and project memories. Call `search` with a query to read the matching ones in full.
- When you learn something durable, call `save`. Good candidates are the user's preferences and role (`user`), corrections and confirmed approaches (`feedback`), decisions and constraints of the current work (`project`), and where to find things (`reference`). Give each a short lowercase-hyphenated `name` and a one-line `description`.
- If a memory already covers it, call `update` instead of saving a duplicate. Call `forget` when a memory is stale or wrong.
- Never save secrets, tokens, passwords or personal data you were not asked to keep.
- Do not write to built-in memory files (such as an auto-memory directory or `MEMORY.md`). This server is the only memory.
- Subagents only call `search`. They do not save, update or forget.
