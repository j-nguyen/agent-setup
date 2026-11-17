import { test } from "node:test";
import assert from "node:assert/strict";
import { LruCache } from "./cache.ts";

test("evicts least recently used", () => {
  const c = new LruCache<number>({ maxEntries: 2, ttlMs: 1000 });
  c.set("a", 1);
  c.set("b", 2);
  c.get("a");
  c.set("c", 3);
  assert.equal(c.get("b"), undefined);
  assert.equal(c.get("a"), 1);
});

test("expires entries after ttl", () => {
  let t = 0;
  const c = new LruCache<number>({ maxEntries: 10, ttlMs: 100, now: () => t });
  c.set("a", 1);
  t = 100;
  assert.equal(c.get("a"), undefined);
});
