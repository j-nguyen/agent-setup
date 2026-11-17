import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { isDue, registerJob, resetJobs, tick } from "../src/scheduler/index.ts";

beforeEach(() => resetJobs());

test("dailyAt fires once at the matching UTC minute", async () => {
  let runs = 0;
  registerJob({ name: "d", schedule: { dailyAt: "03:15" }, run: () => void (runs += 1) });
  await tick(new Date("2026-03-01T03:14:00Z"));
  await tick(new Date("2026-03-01T03:15:00Z"));
  await tick(new Date("2026-03-01T03:15:30Z"));
  assert.equal(runs, 1);
});

test("weeklyAt matches day and time", () => {
  const s = { weeklyAt: { day: 1, time: "07:00" } };
  assert.equal(isDue(s, new Date("2026-03-02T07:00:00Z")), true); // Monday
  assert.equal(isDue(s, new Date("2026-03-03T07:00:00Z")), false);
});

test("a failing job doesn't stop the others", async () => {
  const ran: string[] = [];
  registerJob({ name: "bad", schedule: { every: "minute" }, run: () => { throw new Error("boom"); } });
  registerJob({ name: "good", schedule: { every: "minute" }, run: () => void ran.push("good") });
  const origError = console.error;
  console.error = () => {};
  try {
    await tick(new Date("2026-03-01T10:00:00Z"));
  } finally {
    console.error = origError;
  }
  assert.deepEqual(ran, ["good"]);
});
