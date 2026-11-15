import express from "express";
import { billingWebhookHandler, type EventStore } from "./webhooks/handler";
import { secretsFromEnv } from "./webhooks/signature";

export function createApp(store: EventStore) {
  const app = express();
  // The signature covers the exact bytes, so this route needs the raw body. Register it
  // before the JSON parser, which would otherwise consume and re-serialize it.
  app.post(
    "/webhooks/billing",
    express.raw({ type: "application/json", limit: "1mb" }),
    billingWebhookHandler({ store, secrets: secretsFromEnv(process.env.WEBHOOK_SECRETS) }),
  );
  app.use(express.json({ limit: "100kb" }));
  app.get("/healthz", (_req, res) => res.send("ok"));
  return app;
}
