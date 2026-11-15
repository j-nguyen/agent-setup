---
name: record-feature
description: >
  Record a feature walkthrough from the current repository worktree,
  with a video and milestone screenshots. Use for "record this feature",
  "show what you built", "capture a walkthrough", or "take screenshots and a
  video of these changes". Uses local Playwright scripts, without browser MCP. Browser recording is implemented; desktop recording is
  a researched future backend, not yet supported.
---

# Record a feature

Identify whether the target is a browser or desktop app. For browser features,
follow the workflow below. For desktop-only features, explain that capture is
not implemented yet; consult `references/desktop-options.md` for researched
options. Do not silently record a web substitute for desktop-specific behavior.

Resolve the exact worktree (including uncommitted changes), feature scenario,
app startup command, local URL and expected outcomes from the current task and
repository instructions. Ask only for missing information that prevents a useful
walkthrough. Never substitute the main checkout for the requested worktree.

Delegate to the `browser-recorder` subagent with those details, screenshot
checkpoints, output directory, and any known test-data/authentication constraints.
Give it the absolute path to this skill's `scripts/record.mjs` and
`references/recording.md`. Default output is a fresh directory under
`.browser-recordings/` in the target worktree. Don't commit recordings.

Check its report for `Recorded by the browser-recorder subagent.` and verify the
reported artifact paths exist before presenting links. Preserve its verdict and
limitations. If delegation isn't available, follow the same recording reference
inline and explicitly disclose that fallback; don't fabricate a subagent stamp.

A recording made after implementation is a fresh demonstration, not footage of
past work. Recording isn't authorization to submit payments, publish, delete
real data, or upload artifacts. Use local test data for mutations.
