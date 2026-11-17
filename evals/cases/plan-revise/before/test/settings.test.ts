import { test } from "node:test";
import assert from "node:assert/strict";
import { getSettings, updateSettings } from "../src/users/settings.ts";
import { unsubscribeUrl, verifyUnsubscribe } from "../src/email/mailer.ts";

test("settings default and validate timezone", () => {
  assert.equal(getSettings("s1").timezone, "UTC");
  assert.equal(updateSettings("s1", { timezone: "Europe/Berlin" }).timezone, "Europe/Berlin");
  assert.throws(() => updateSettings("s1", { timezone: "Mars/Olympus" }));
});

test("unsubscribe links are signed per user and list", () => {
  const url = new URL(unsubscribeUrl("u1", "weekly-report"));
  assert.equal(verifyUnsubscribe("u1", "weekly-report", url.searchParams.get("s")!), true);
  assert.equal(verifyUnsubscribe("u2", "weekly-report", url.searchParams.get("s")!), false);
});
