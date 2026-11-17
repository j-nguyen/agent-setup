import { test } from "node:test";
import assert from "node:assert/strict";
import { InMemoryProfileRepo, type Profile } from "./repo.ts";
import { ProfileService } from "./service.ts";
import type { ProfileCache } from "./types.ts";

class FakeCache implements ProfileCache {
  readonly store = new Map<string, { value: Profile; expiresAt: number }>();
  now = 0;

  async get(key: string) {
    const e = this.store.get(key);
    if (!e || e.expiresAt <= this.now) return undefined;
    return e.value;
  }

  async set(key: string, value: Profile, ttlSeconds: number) {
    this.store.set(key, { value, expiresAt: this.now + ttlSeconds * 1000 });
  }

  async delete(key: string) {
    this.store.delete(key);
  }
}

function seed() {
  const repo = new InMemoryProfileRepo();
  repo.rows.set("u1", { id: "u1", displayName: "Ada", avatarUrl: null, updatedAt: "2026-01-01T00:00:00Z" });
  return repo;
}

test("returns a profile", async () => {
  const svc = new ProfileService(seed(), new FakeCache());
  assert.equal((await svc.getProfile("u1"))?.displayName, "Ada");
});

test("second read is served from the cache", async () => {
  const repo = seed();
  const svc = new ProfileService(repo, new FakeCache());
  await svc.getProfile("u1");
  await svc.getProfile("u1");
  assert.equal(repo.reads, 1);
});

test("not-found is not cached", async () => {
  const repo = seed();
  const svc = new ProfileService(repo, new FakeCache());
  assert.equal(await svc.getProfile("nope"), null);
  assert.equal(await svc.getProfile("nope"), null);
  assert.equal(repo.reads, 2);
});

test("entries expire after the ttl", async () => {
  const repo = seed();
  const cache = new FakeCache();
  const svc = new ProfileService(repo, cache);
  await svc.getProfile("u1");
  cache.now = 60_000;
  await svc.getProfile("u1");
  assert.equal(repo.reads, 2);
});

test("update invalidates the cached profile", async () => {
  const svc = new ProfileService(seed(), new FakeCache());
  await svc.getProfile("u1");
  await svc.updateProfile("u1", { displayName: "Grace" });
  assert.equal((await svc.getProfile("u1"))?.displayName, "Grace");
});

test("rejects empty display names", async () => {
  const svc = new ProfileService(seed(), new FakeCache());
  await assert.rejects(svc.updateProfile("u1", { displayName: " " }));
});
