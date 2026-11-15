import { createHmac, timingSafeEqual } from "node:crypto";

export const TOLERANCE_SECONDS = 300;

export interface ParsedSignature {
  timestamp: number;
  signatures: Buffer[];
}

/** Parse `t=<unix seconds>,v1=<hex>[,v1=<hex>...]`. Returns null if anything is malformed. */
export function parseSignatureHeader(header: string): ParsedSignature | null {
  let timestamp: number | undefined;
  const signatures: Buffer[] = [];
  for (const part of header.split(",")) {
    const eq = part.indexOf("=");
    if (eq <= 0) return null;
    const key = part.slice(0, eq).trim();
    const value = part.slice(eq + 1).trim();
    if (key === "t") {
      if (!/^\d{1,12}$/.test(value)) return null;
      timestamp = Number(value);
    } else if (key === "v1") {
      if (!/^[0-9a-f]{64}$/.test(value)) return null;
      signatures.push(Buffer.from(value, "hex"));
    }
    // Unknown schemes (e.g. a future v2) are ignored, as the provider documents.
  }
  if (timestamp === undefined || signatures.length === 0) return null;
  return { timestamp, signatures };
}

/**
 * True if `header` carries a valid signature of `rawBody` from any of `secrets`
 * (several during a rotation) and its timestamp is within the tolerance.
 */
export function verifySignature(rawBody: Buffer, header: string | undefined, secrets: string[], nowSeconds: number): boolean {
  if (!header || secrets.length === 0) return false;
  const parsed = parseSignatureHeader(header);
  if (!parsed || Math.abs(nowSeconds - parsed.timestamp) > TOLERANCE_SECONDS) return false;
  const signedPayload = Buffer.concat([Buffer.from(`${parsed.timestamp}.`), rawBody]);
  for (const secret of secrets) {
    const expected = createHmac("sha256", secret).update(signedPayload).digest();
    // Every candidate is 32 bytes (checked by the regex), so timingSafeEqual can't throw.
    if (parsed.signatures.some((sig) => sig.length === expected.length && timingSafeEqual(sig, expected))) {
      return true;
    }
  }
  return false;
}

export function secretsFromEnv(value: string | undefined): string[] {
  return (value ?? "").split(",").map((s) => s.trim()).filter(Boolean);
}
