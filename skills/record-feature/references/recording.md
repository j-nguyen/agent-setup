# Script-based recording

1. Read repo instructions and inspect the feature changes. Record the absolute
   worktree and HEAD; retain uncommitted changes. Find the app's documented startup
   command and installed Playwright package. If dependencies or a browser are
   absent, use the environment's normal installation permissions or report Blocked.
   Don't modify package manifests just to record a demo.
2. Start a dedicated local app instance from that worktree on an available port.
   Check readiness. An existing URL alone is not proof of worktree provenance.
3. Create a scenario module in the artifact area. It exports
   `async function run({ page, checkpoint })`. Navigate, interact with accessible
   locators, check expected results (throw on failure), and call
   `await checkpoint('meaningful-name')` at initial, interaction, and final states.
   Use condition-based waits, not arbitrary sleeps. Include viewport size and
   feature-specific assertions. Don't treat screenshots as proof of unchecked behavior.
4. Run `node <skill>/scripts/record.mjs <scenario.mjs> <new-output-dir>
   <absolute-playwright-entry>` from the worktree. The final argument is the
   installed Playwright module entry, resolved from the project or a dedicated
   tooling directory. The scenario can use the supplied page without importing
   Playwright. The runner captures video, screenshots, and a manifest even when
   a scenario fails. Each attempt needs a new output directory.
5. Inspect milestone images. Probe video with an available media inspector (for
   example ffprobe) or open it; existence alone isn't proof it is playable.
   Verify nonzero duration and that the feature scenario appears in the footage
   where video inspection is available. Report any inspection limitation.
6. Write a concise report with expected vs observed behavior and artifact paths.
   Keep partial artifacts on failure, and stop only your own app processes.

The runner records browser viewport content, not the desktop or browser chrome.
Multiple tabs can produce multiple videos; link each relevant file. A script is
preferred over repeated page snapshots sent to the model. Inspect only useful
checkpoints. Never upload artifacts by default.

Recordings enable Playwright's animated pointer, action labels, and blue target
highlights. This is a simulated pointer for automated actions, not the user's
desktop cursor. Use a Playwright version supporting `recordVideo.showActions`;
verify annotations in the output video when using a project's older installation.
