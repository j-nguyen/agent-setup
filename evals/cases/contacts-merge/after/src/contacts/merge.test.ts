import { describe, expect, it } from "vitest";
import { mergeContacts } from "./merge";

const at = (d: string) => new Date(d);

describe("mergeContacts", () => {
  it("merges duplicates and unions tags", () => {
    const merged = mergeContacts([
      { id: "1", name: "Ann", email: "ann@x.com", tags: ["a"], createdAt: at("2024-01-02") },
      { id: "2", name: "Ann B", email: "ann@x.com ", tags: ["a", "b"], createdAt: at("2024-01-01") },
    ]);
    expect(merged).toHaveLength(1);
    expect(merged[0].tags).toEqual(["a", "b"]);
  });
});
