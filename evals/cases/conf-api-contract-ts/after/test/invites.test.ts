import { test } from "node:test";
import assert from "node:assert/strict";
import { buildApp } from "../src/app.ts";
import { InMemoryInviteStore } from "../src/invites/store.ts";

const quiet = () => {};

test("creates an invite that expires in 7 days", async () => {
  const app = buildApp({ invites: new InMemoryInviteStore(), logSink: quiet });
  const before = Date.now();
  const res = await app.handle("POST", "/v1/invites", { email: "Sam@Example.com" });
  assert.equal(res.status, 200);
  const body = res.body as { id: string; email: string; expires_at: string };
  assert.deepEqual(Object.keys(body).sort(), ["email", "expires_at", "id"]);
  assert.equal(body.email, "sam@example.com");
  const days = (Date.parse(body.expires_at) - before) / 86_400_000;
  assert.ok(days > 6.99 && days <= 7.01);
});

test("rejects an invalid email", async () => {
  const app = buildApp({ invites: new InMemoryInviteStore(), logSink: quiet });
  const res = await app.handle("POST", "/v1/invites", { email: "not-an-email" });
  assert.equal(res.status, 400);
  assert.deepEqual(res.body, { error: "invalid_email" });
});

test("lists invites page by page", async () => {
  const store = new InMemoryInviteStore();
  for (let i = 0; i < 5; i++) await store.create(`user${i}@example.com`, "admin", new Date(2026, 0, 1, 0, i));
  const app = buildApp({ invites: store, logSink: quiet });
  const first = await app.handle("GET", "/v1/invites?limit=3&page=1");
  const second = await app.handle("GET", "/v1/invites?limit=3&page=2");
  const b1 = first.body as { items: { email: string }[]; total: number };
  const b2 = second.body as { items: { email: string }[] };
  assert.equal(b1.total, 5);
  assert.deepEqual(b1.items.map((i) => i.email), ["user0@example.com", "user1@example.com", "user2@example.com"]);
  assert.deepEqual(b2.items.map((i) => i.email), ["user3@example.com", "user4@example.com"]);
});
