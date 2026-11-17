const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function isEmail(value: unknown): value is string {
  return typeof value === "string" && value.length <= 254 && EMAIL_RE.test(value);
}

/** Parses ?limit=, defaulting to 20 and clamping to 1..100. */
export function parseLimit(raw: string | null, fallback = 20, max = 100): number {
  if (raw === null) return fallback;
  const n = Number.parseInt(raw, 10);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(1, Math.min(n, max));
}

export function encodeCursor(id: string): string {
  return Buffer.from(id, "utf8").toString("base64url");
}

export function decodeCursor(cursor: string | null): string | null {
  return cursor ? Buffer.from(cursor, "base64url").toString("utf8") : null;
}
