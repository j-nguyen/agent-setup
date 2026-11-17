import { createHmac } from "node:crypto";

/** Returns the X-Signature header value for a request body. */
export function signPayload(secret: string, body: string): string {
  return "sha256=" + createHmac("sha256", secret).update(body, "utf8").digest("hex");
}
