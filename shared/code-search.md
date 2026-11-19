## Finding and reading code fast

Each tool call costs a model turn, so use as few as you can.

- **Use a code graph first when one exists.** If the repository has a
  `.codegraph/` directory and you have a CodeGraph tool, ask it about the
  symbols, files or flow you need before you search or open files. One call
  returns the source of the relevant symbols and the call paths between them.
  Treat the source it shows as read. Fall back to search and file reads for
  what it doesn't cover.
- **Batch reads.** Read several files or line ranges in one call, or run
  independent reads and searches in parallel in one turn. Don't read files one
  at a time when you already know which ones you need.
- **Read each file once.** Don't print a file again that you already have.
  Cite line numbers from what you already read.

## Running tests fast

- **Use the repo's `## Tests` section** from the project rules files, if one
  exists (see "Project-specific rules").
- **Run the narrowest command**: one test file, or one test name. If the repo
  has no `## Tests` section, work out the single-file command once, from
  `package.json` scripts, the Makefile or the test config. Then reuse it.
- **Run tests in the foreground**, with a timeout long enough for the run.
  Never start a test run in the background and then poll it with `sleep`
  loops. Each poll costs a model turn.
- **Run the full suite at most once**, at the end, and only if your
  instructions or the plan's test plan ask for it.
- **Note what worked.** Keep the commands that worked and roughly how long each
  took, for the "Test commands" part of your report.
