import { retry } from "../lib/retry.ts";
import type { Logger } from "../lib/logger.ts";

export interface SmtpClient {
  send(to: string, subject: string, body: string): Promise<void>;
}

export async function sendEmail(smtp: SmtpClient, log: Logger, to: string, subject: string, body: string) {
  try {
    await retry(() => smtp.send(to, subject, body));
  } catch (err) {
    log.warn("email.send_failed", { to, error: String(err) });
    throw err;
  }
}
