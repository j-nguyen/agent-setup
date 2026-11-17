import { test } from "node:test";
import assert from "node:assert/strict";
import { InMemoryProfileRepo } from "./repo.ts";
import { ProfileService } from "./service.ts";

function seed() {
  const repo = new InMemoryProfileRepo();
  repo.rows.set("u1", { id: "u1", displayName: "Ada", avatarUrl: null, updatedAt: "2026-01-01T00:00:00Z" });
  return repo;
}

test("returns a profile", async () => {
  const svc = new ProfileService(seed());
  assert.equal((await svc.getProfile("u1"))?.displayName, "Ada");
});

test("rejects empty display names", async () => {
  const svc = new ProfileService(seed());
  await assert.rejects(svc.updateProfile("u1", { displayName: " " }));
});
