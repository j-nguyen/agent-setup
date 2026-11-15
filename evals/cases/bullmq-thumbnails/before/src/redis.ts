import IORedis from "ioredis";

// Shared connection for the web process (rate limiting, sessions). Commands fail
// fast (3 retries) so an HTTP request never hangs on a Redis outage.
export const redis = new IORedis(process.env.REDIS_URL ?? "redis://localhost:6379", {
  maxRetriesPerRequest: 3,
});
