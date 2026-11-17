import { Redis } from "ioredis";
import type { Profile } from "../profiles/repo.ts";
import type { ProfileCache } from "../profiles/types.ts";

export class RedisProfileCache implements ProfileCache {
  private readonly client: Redis;

  constructor(client: Redis) {
    this.client = client;
  }

  async get(key: string): Promise<Profile | undefined> {
    const raw = await this.client.get(key);
    return raw === null ? undefined : (JSON.parse(raw) as Profile);
  }

  async set(key: string, value: Profile, ttlSeconds: number): Promise<void> {
    await this.client.set(key, JSON.stringify(value), "EX", ttlSeconds);
  }

  async delete(key: string): Promise<void> {
    await this.client.del(key);
  }
}

export function connectRedis(url = process.env.REDIS_URL ?? "redis://localhost:6379"): Redis {
  return new Redis(url, { maxRetriesPerRequest: 2, enableOfflineQueue: false });
}
