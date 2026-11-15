import type { Profile, ProfileStore } from "./types";

/** In-memory ProfileStore for tests and local dev. Counts round trips. */
export class MemoryStore implements ProfileStore {
  calls = 0;
  private rows = new Map<string, Profile>();

  seed(p: Profile): void {
    this.rows.set(`${p.tenantId}/${p.userId}`, structuredClone(p));
  }

  async get(tenantId: string, userId: string): Promise<Profile | null> {
    this.calls++;
    const row = this.rows.get(`${tenantId}/${userId}`);
    return row ? structuredClone(row) : null;
  }

  async update(tenantId: string, userId: string, patch: Partial<Profile>): Promise<Profile> {
    this.calls++;
    const key = `${tenantId}/${userId}`;
    const row = this.rows.get(key);
    if (!row) throw new Error(`no profile ${key}`);
    const next = { ...row, ...patch, tenantId, userId };
    this.rows.set(key, next);
    return structuredClone(next);
  }
}
