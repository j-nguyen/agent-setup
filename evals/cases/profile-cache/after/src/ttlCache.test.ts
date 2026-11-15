import { describe, expect, it } from "vitest";
import { TtlCache } from "./ttlCache";

describe("TtlCache", () => {
  it("expires entries after the TTL", () => {
    let now = 0;
    const c = new TtlCache<string>(1000, 10, () => now);
    c.set("a", "x");
    now = 999;
    expect(c.get("a")).toBe("x");
    now = 1000;
    expect(c.get("a")).toBeUndefined();
  });

  it("evicts the oldest entry when full", () => {
    const c = new TtlCache<number>(60_000, 2);
    c.set("a", 1);
    c.set("b", 2);
    c.set("c", 3);
    expect(c.get("a")).toBeUndefined();
    expect(c.size).toBe(2);
  });
});
