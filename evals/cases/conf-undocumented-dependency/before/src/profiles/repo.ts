export interface Profile {
  id: string;
  displayName: string;
  avatarUrl: string | null;
  updatedAt: string;
}

export interface ProfileRepo {
  findById(id: string): Promise<Profile | null>;
  update(id: string, patch: Partial<Pick<Profile, "displayName" | "avatarUrl">>): Promise<Profile | null>;
}

// Stand-in for the Postgres-backed repo used in production.
export class InMemoryProfileRepo implements ProfileRepo {
  readonly rows = new Map<string, Profile>();
  reads = 0;

  async findById(id: string): Promise<Profile | null> {
    this.reads++;
    const row = this.rows.get(id);
    return row ? { ...row } : null;
  }

  async update(id: string, patch: Partial<Pick<Profile, "displayName" | "avatarUrl">>): Promise<Profile | null> {
    const row = this.rows.get(id);
    if (!row) return null;
    const next = { ...row, ...patch, updatedAt: new Date().toISOString() };
    this.rows.set(id, next);
    return { ...next };
  }
}
