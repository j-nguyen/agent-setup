## Memory

You have a shared, persistent memory through the `memory` MCP server. Every coding agent on this machine reads and writes the same store. Use it instead of any built-in memory files.

- Call `search` only when earlier context would change what you do: before non-trivial work in a project (its conventions, past decisions, how to run things), when the user refers to something from before ("like last time", "what did we decide"), or before asking the user something a memory might answer. Skip it for quick, self-contained questions.
- Pass the absolute `project_path` to each tool. Search with `compact=true` to see short excerpts. Use `get` with the name and scope to read a full note. Omit the query to list note names and descriptions.
- When you learn something durable, call `save`. Good candidates are the user's preferences and role (`user`), corrections and confirmed approaches (`feedback`), decisions and constraints of the current work (`project`), and where to find things (`reference`). Give each a short lowercase-hyphenated `name` and a one-line `description`.
- Update an existing note if it already covers the fact. Forget a note when it is stale or wrong. Before either action, call `get` and pass its `revision` to `update` or `forget`. If the note changed, read it again and review the new content before retrying.
- Never save secrets, tokens, passwords or personal data you were not asked to keep.
- Do not write to built-in memory files (such as an auto-memory directory or `MEMORY.md`). This server is the only memory.
- Subagents only call `search` and `get`.
