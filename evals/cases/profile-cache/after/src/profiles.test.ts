import { beforeEach, describe, expect, it } from "vitest";
import { MemoryStore } from "./memoryStore";
import { clearProfileCache, getProfile, updateProfile } from "./profiles";

const ann = { tenantId: "acme", userId: "u1", displayName: "Ann", email: "ann@acme.test", preferences: {} };

describe("profiles", () => {
  beforeEach(() => clearProfileCache());

  it("reads and updates", async () => {
    const store = new MemoryStore();
    store.seed(ann);
    await updateProfile(store, "acme", "u1", { displayName: "Ann B" });
    expect((await getProfile(store, "acme", "u1"))?.displayName).toBe("Ann B");
  });

  it("serves repeat reads from the cache", async () => {
    const store = new MemoryStore();
    store.seed({ ...ann, userId: "u2" });
    await getProfile(store, "acme", "u2");
    await getProfile(store, "acme", "u2");
    expect(store.calls).toBe(1);
  });

  it("returns the new profile after an update", async () => {
    const store = new MemoryStore();
    store.seed(ann);
    await getProfile(store, "acme", "u1");
    await updateProfile(store, "acme", "u1", { displayName: "Ann C" });
    expect((await getProfile(store, "acme", "u1"))?.displayName).toBe("Ann C");
  });
});
