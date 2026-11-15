export interface Profile {
  tenantId: string;
  userId: string;
  displayName: string;
  email: string;
  preferences: Record<string, string>;
}

/** Backed by Postgres in production. Every call is a round trip. */
export interface ProfileStore {
  get(tenantId: string, userId: string): Promise<Profile | null>;
  update(tenantId: string, userId: string, patch: Partial<Omit<Profile, "tenantId" | "userId">>): Promise<Profile>;
}
