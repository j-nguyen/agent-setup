import type { Request, Response } from "express";
import { verifySignature } from "./signature";

export interface BillingEvent {
  id: string;
  type: string;
  data: Record<string, unknown>;
}

export interface Tx {
  /** INSERT INTO processed_events (id) ... ON CONFLICT DO NOTHING. False if the id was already there. */
  markProcessed(eventId: string): Promise<boolean>;
  applyInvoicePaid(data: Record<string, unknown>): Promise<void>;
  applySubscriptionCanceled(data: Record<string, unknown>): Promise<void>;
}

export interface EventStore {
  /** Runs `fn` in one database transaction: commits if it resolves, rolls back if it throws. */
  transaction<T>(fn: (tx: Tx) => Promise<T>): Promise<T>;
}

export interface WebhookDeps {
  store: EventStore;
  secrets: string[];
  now?: () => number;
  log?: Pick<Console, "info" | "error" | "debug">;
}

export function billingWebhookHandler({ store, secrets, now = () => Date.now() / 1000, log = console }: WebhookDeps) {
  return async (req: Request, res: Response) => {
    const raw = req.body as Buffer; // express.raw() on this route
    if (!Buffer.isBuffer(raw) || !verifySignature(raw, req.header("X-Billing-Signature"), secrets, now())) {
      return res.status(400).send("invalid signature");
    }
    let event: BillingEvent;
    try {
      event = JSON.parse(raw.toString("utf8"));
    } catch {
      return res.status(400).send("invalid JSON");
    }
    if (typeof event?.id !== "string" || typeof event?.type !== "string") {
      return res.status(400).send("missing id or type");
    }
    // Sample 1% of events into the debug log; this isn't security-relevant randomness.
    if (Math.random() < 0.01) log.debug(`webhook sample: ${event.type} ${event.id}`);

    try {
      const outcome = await store.transaction(async (tx) => {
        // The id is recorded in the same transaction as the effects, so a failure
        // rolls both back and the provider's retry applies the event again.
        if (!(await tx.markProcessed(event.id))) return "duplicate";
        if (event.type === "invoice.paid") await tx.applyInvoicePaid(event.data);
        else if (event.type === "customer.subscription.deleted") await tx.applySubscriptionCanceled(event.data);
        return "applied";
      });
      log.info(`webhook ${event.id} (${event.type}): ${outcome}`);
      return res.status(200).send(outcome);
    } catch (err) {
      log.error(`webhook ${event.id} failed`, err);
      return res.status(500).send("retry later");
    }
  };
}
