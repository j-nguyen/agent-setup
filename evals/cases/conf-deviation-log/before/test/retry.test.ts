import { test } from "node:test";
import assert from "node:assert/strict";
import { retry, DEFAULT_ATTEMPTS } from "../src/lib/retry.ts";

const noSleep = async () => {};

test("retries until success", async () => {
  let calls = 0;
  const result = await retry(async () => {
    calls++;
    if (calls < 3) throw new Error("flaky");
    return "ok";
  }, { sleep: noSleep });
  assert.equal(result, "ok");
  assert.equal(calls, 3);
});

test("gives up after the default number of attempts", async () => {
  let calls = 0;
  await assert.rejects(retry(async () => { calls++; throw new Error("down"); }, { sleep: noSleep }));
  assert.equal(calls, DEFAULT_ATTEMPTS);
});
