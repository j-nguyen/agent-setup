// Every outgoing email goes through sendEmail(). In dev/tests the transport
// just records messages; prod swaps in the SMTP transport at startup.
import { createHmac } from "node:crypto";

export type EmailList = "product-updates" | "weekly-report";

export type Email = {
  to: string;
  subject: string;
  text: string;
  html: string;
  headers: Record<string, string>;
};

export type Transport = (email: Email) => Promise<void>;

export const sent: Email[] = [];
let transport: Transport = async (e) => {
  sent.push(e);
};

export function setTransport(t: Transport): void {
  transport = t;
}

const SECRET = process.env.UNSUBSCRIBE_SECRET ?? "dev-secret";
const BASE_URL = process.env.APP_BASE_URL ?? "http://localhost:3000";

// Signed one-click unsubscribe link for a mailing list (RFC 8058 style).
export function unsubscribeUrl(userId: string, list: EmailList): string {
  const sig = createHmac("sha256", SECRET).update(`${userId}:${list}`).digest("hex").slice(0, 32);
  return `${BASE_URL}/unsubscribe?u=${encodeURIComponent(userId)}&l=${list}&s=${sig}`;
}

export function verifyUnsubscribe(userId: string, list: string, sig: string): boolean {
  const expected = createHmac("sha256", SECRET).update(`${userId}:${list}`).digest("hex").slice(0, 32);
  return expected === sig;
}

export async function sendEmail(opts: {
  to: string;
  subject: string;
  text: string;
  html: string;
  list?: { userId: string; name: EmailList };
}): Promise<void> {
  const headers: Record<string, string> = {};
  if (opts.list) {
    const url = unsubscribeUrl(opts.list.userId, opts.list.name);
    headers["List-Unsubscribe"] = `<${url}>`;
    headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click";
  }
  await transport({ to: opts.to, subject: opts.subject, text: opts.text, html: opts.html, headers });
}
