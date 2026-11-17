export interface Config {
  emailFrom: string;
  smtpTimeoutMs: number;
}

function intFromEnv(env: Record<string, string | undefined>, key: string, fallback: number): number {
  const raw = env[key];
  if (raw === undefined || raw === "") return fallback;
  const value = Number.parseInt(raw, 10);
  if (!Number.isFinite(value) || value <= 0) throw new Error(`${key} must be a positive integer`);
  return value;
}

export function loadConfig(env: Record<string, string | undefined> = process.env): Config {
  return {
    emailFrom: env.EMAIL_FROM ?? "no-reply@example.com",
    smtpTimeoutMs: intFromEnv(env, "SMTP_TIMEOUT_MS", 10000),
  };
}
