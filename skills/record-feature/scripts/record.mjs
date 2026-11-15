// Local Playwright driver; no agent-specific APIs or MCP.
import { mkdir, writeFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const [scenario, destination, entry] = process.argv.slice(2);
if (!scenario || !destination || !entry) {
  console.error('Usage: node record.mjs scenario.mjs NEW-output-dir playwright-entry');
  process.exit(2);
}
const out = path.resolve(destination);
await mkdir(out); // Refuse overwriting an earlier attempt.
const manifest = { started: new Date().toISOString(), worktree: process.cwd(),
  status: 'Blocked', screenshots: [], videos: [], checks: 'not completed' };
let browser, context;
try {
  const { chromium } = await import(pathToFileURL(path.resolve(entry)).href);
  const { run } = await import(pathToFileURL(path.resolve(scenario)).href);
  browser = await chromium.launch({ headless: true });
  context = await browser.newContext({ viewport: { width: 1280, height: 720 },
    recordVideo: { dir: out, size: { width: 1280, height: 720 },
      showActions: { cursor: 'pointer', duration: 800, position: 'top-right',
        style: { highlight: 'outline: 2px solid #2563eb; background: #2563eb22;' } } } });
  const page = await context.newPage();
  const checkpoint = async (name) => {
    const filename = `${String(manifest.screenshots.length + 1).padStart(2, '0')}-${String(name).replace(/[^a-z0-9-]/gi, '-').slice(0, 80)}.png`;
    await page.screenshot({ path: path.join(out, filename) });
    manifest.screenshots.push(filename);
  };
  manifest.status = 'Failed';
  await run({ page, checkpoint });
  manifest.checks = 'passed';
  manifest.status = 'Captured'; // Agent must inspect artifacts before Complete.
} catch (error) {
  manifest.error = String(error);
  process.exitCode = 1;
} finally {
  try { await context?.close(); } catch (error) {
    manifest.status = 'Partial'; manifest.finalizeError = String(error); process.exitCode = 1;
  }
  try { await browser?.close(); } catch (error) {
    manifest.status = 'Partial'; manifest.closeError = String(error); process.exitCode = 1;
  }
  manifest.videos = (await readdir(out)).filter(name => name.endsWith('.webm'));
  if (manifest.status === 'Captured' && (!manifest.videos.length || !manifest.screenshots.length)) {
    manifest.status = 'Partial'; process.exitCode = 1;
  }
  manifest.finished = new Date().toISOString();
  await writeFile(path.join(out, 'manifest.json'), JSON.stringify(manifest, null, 2));
  console.log(JSON.stringify(manifest));
}
