import type { Config } from "../config.ts";
import type { Logger } from "../lib/logger.ts";
import { retry, DEFAULT_ATTEMPTS } from "../lib/retry.ts";
import { signPayload } from "./sign.ts";
import type { DeliveryStore } from "./store.ts";

export interface Endpoint {
  id: string;
  url: string;
  secret: string;
}

export interface WebhookEvent {
  id: string;
  type: string;
  payload: unknown;
}

export interface DeliverDeps {
  store: DeliveryStore;
  log: Logger;
  config: Pick<Config, "webhookRequestTimeoutMs">;
  fetchImpl?: typeof fetch;
  sleep?: (ms: number) => Promise<void>;
}

export class HttpStatusError extends Error {
  status: number;
  constructor(status: number) {
    super(`endpoint responded ${status}`);
    this.status = status;
  }
}

export function isRetryable(err: unknown): boolean {
  if (err instanceof HttpStatusError) {
    return err.status >= 500 || err.status === 408 || err.status === 429;
  }
  return true; // network errors and timeouts
}

export async function deliverWebhook(
  endpoint: Endpoint,
  event: WebhookEvent,
  deps: DeliverDeps,
): Promise<"delivered" | "failed"> {
  const fetchImpl = deps.fetchImpl ?? fetch;
  const body = JSON.stringify({ id: event.id, type: event.type, payload: event.payload });
  const signature = signPayload(endpoint.secret, body);
  const started = Date.now();
  let attempts = 0;
  let lastStatus: number | undefined;

  try {
    await retry(
      async (attempt) => {
        attempts = attempt;
        const res = await fetchImpl(endpoint.url, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Signature": signature },
          body,
          signal: AbortSignal.timeout(deps.config.webhookRequestTimeoutMs),
        });
        lastStatus = res.status;
        if (!res.ok) throw new HttpStatusError(res.status);
      },
      { attempts: DEFAULT_ATTEMPTS, shouldRetry: isRetryable, sleep: deps.sleep },
    );
  } catch (err) {
    deps.log.warn("webhook.delivery_failed", {
      endpointId: endpoint.id,
      eventId: event.id,
      attempts,
      status: lastStatus ?? null,
      durationMs: Date.now() - started,
    });
    await deps.store.markFailed(event.id, endpoint.id, String(err));
    return "failed";
  }

  await deps.store.markDelivered(event.id, endpoint.id);
  return "delivered";
}
