import { createHmac } from "node:crypto";
import { describe, expect, it } from "vitest";
import { parseSignatureHeader, verifySignature } from "./signature";

const body = Buffer.from('{"id":"evt_1","type":"invoice.paid","data":{}}');
const sign = (secret: string, t: number, b = body) =>
  createHmac("sha256", secret).update(Buffer.concat([Buffer.from(`${t}.`), b])).digest("hex");

describe("verifySignature", () => {
  const now = 1_800_000_000;
  it("accepts a valid signature", () => {
    expect(verifySignature(body, `t=${now},v1=${sign("s1", now)}`, ["s1"], now)).toBe(true);
  });
  it("accepts the new secret during rotation", () => {
    expect(verifySignature(body, `t=${now},v1=${sign("s2", now)}`, ["s1", "s2"], now)).toBe(true);
  });
  it("rejects a tampered body", () => {
    expect(verifySignature(Buffer.from("{}"), `t=${now},v1=${sign("s1", now)}`, ["s1"], now)).toBe(false);
  });
  it("rejects old timestamps", () => {
    expect(verifySignature(body, `t=${now - 301},v1=${sign("s1", now - 301)}`, ["s1"], now)).toBe(false);
  });
  it("rejects malformed headers", () => {
    expect(parseSignatureHeader("t=abc,v1=00")).toBe(null);
    expect(verifySignature(body, undefined, ["s1"], now)).toBe(false);
  });
});
