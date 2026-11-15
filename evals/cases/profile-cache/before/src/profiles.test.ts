import { describe, expect, it } from "vitest";
import { MemoryStore } from "./memoryStore";
import { getProfile, updateProfile } from "./profiles";

const ann = { tenantId: "acme", userId: "u1", displayName: "Ann", email: "ann@acme.test", preferences: {} };

describe("profiles", () => {
  it("reads and updates", async () => {
    const store = new MemoryStore();
    store.seed(ann);
    await updateProfile(store, "acme", "u1", { displayName: "Ann B" });
    expect((await getProfile(store, "acme", "u1"))?.displayName).toBe("Ann B");
  });
});
