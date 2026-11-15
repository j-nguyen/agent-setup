import { describe, expect, it } from "vitest";
import { highlight } from "./highlight";

describe("highlight", () => {
  it("escapes the payload", () => {
    expect(highlight('<img src=x onerror="alert(1)">', "")).toBe("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;");
  });
  it("escapes the term and marks matches", () => {
    expect(highlight("a <b> a", "<b>")).toBe("a <mark>&lt;b&gt;</mark> a");
    expect(highlight("price (USD)", "(usd)")).toBe("price <mark>(USD)</mark>");
  });
});
