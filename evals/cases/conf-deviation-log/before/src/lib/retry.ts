export interface RetryOptions {
  attempts?: number;
  baseDelayMs?: number;
  sleep?: (ms: number) => Promise<void>;
  shouldRetry?: (err: unknown) => boolean;
}

export const DEFAULT_ATTEMPTS = 4;

const realSleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** Calls fn until it succeeds, with exponential backoff between attempts. */
export async function retry<T>(fn: (attempt: number) => Promise<T>, opts: RetryOptions = {}): Promise<T> {
  const attempts = opts.attempts ?? DEFAULT_ATTEMPTS;
  const baseDelayMs = opts.baseDelayMs ?? 200;
  const sleep = opts.sleep ?? realSleep;
  const shouldRetry = opts.shouldRetry ?? (() => true);
  let lastError: unknown;
  for (let attempt = 1; attempt <= attempts; attempt++) {
    try {
      return await fn(attempt);
    } catch (err) {
      lastError = err;
      if (attempt === attempts || !shouldRetry(err)) break;
      await sleep(baseDelayMs * 2 ** (attempt - 1));
    }
  }
  throw lastError;
}
