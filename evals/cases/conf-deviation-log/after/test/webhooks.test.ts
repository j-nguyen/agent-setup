import { test } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { deliverWebhook } from "../src/webhooks/deliver.ts";
import { InMemoryDeliveryStore } from "../src/webhooks/store.ts";
import { createLogger } from "../src/lib/logger.ts";
import { DEFAULT_ATTEMPTS } from "../src/lib/retry.ts";

const endpoint = { id: "ep_1", url: "https://hooks.example.test/in", secret: "whsec_test" };
const event = { id: "evt_1", type: "invoice.paid", payload: { amount: 4200 } };
const config = { webhookRequestTimeoutMs: 5000 };
const noSleep = async () => {};

function fakeFetch(statuses: number[]) {
  const calls: { url: string; init: RequestInit }[] = [];
  const impl = (async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    const status = statuses[Math.min(calls.length - 1, statuses.length - 1)];
    return new Response(null, { status });
  }) as unknown as typeof fetch;
  return { impl, calls };
}

function capture() {
  const lines: string[] = [];
  return { log: createLogger((l) => lines.push(l)), lines };
}

test("signs the body with HMAC-SHA256", async () => {
  const { impl, calls } = fakeFetch([200]);
  const store = new InMemoryDeliveryStore();
  await deliverWebhook(endpoint, event, { store, log: capture().log, config, fetchImpl: impl, sleep: noSleep });
  const init = calls[0].init;
  const headers = init.headers as Record<string, string>;
  const expected = "sha256=" + createHmac("sha256", endpoint.secret).update(String(init.body)).digest("hex");
  assert.equal(init.method, "POST");
  assert.equal(headers["Content-Type"], "application/json");
  assert.equal(headers["X-Signature"], expected);
  assert.deepEqual(store.records, [{ eventId: "evt_1", endpointId: "ep_1", outcome: "delivered" }]);
});

test("does not retry a 400", async () => {
  const { impl, calls } = fakeFetch([400]);
  const store = new InMemoryDeliveryStore();
  const result = await deliverWebhook(endpoint, event, { store, log: capture().log, config, fetchImpl: impl, sleep: noSleep });
  assert.equal(result, "failed");
  assert.equal(calls.length, 1);
});

test("retries a 503 and then delivers", async () => {
  const { impl, calls } = fakeFetch([503, 200]);
  const store = new InMemoryDeliveryStore();
  const result = await deliverWebhook(endpoint, event, { store, log: capture().log, config, fetchImpl: impl, sleep: noSleep });
  assert.equal(result, "delivered");
  assert.equal(calls.length, 2);
});

test("logs and records the final failure without the secret", async () => {
  const { impl, calls } = fakeFetch([500]);
  const store = new InMemoryDeliveryStore();
  const { log, lines } = capture();
  const result = await deliverWebhook(endpoint, event, { store, log, config, fetchImpl: impl, sleep: noSleep });
  assert.equal(result, "failed");
  assert.equal(calls.length, DEFAULT_ATTEMPTS);
  assert.equal(lines.length, 1);
  const entry = JSON.parse(lines[0]);
  assert.equal(entry.event, "webhook.delivery_failed");
  assert.equal(entry.attempts, DEFAULT_ATTEMPTS);
  assert.equal(entry.status, 500);
  assert.ok(!lines[0].includes(endpoint.secret));
  assert.equal(store.records[0].outcome, "failed");
});
