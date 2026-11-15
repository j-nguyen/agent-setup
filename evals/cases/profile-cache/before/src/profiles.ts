import type { Profile, ProfileStore } from "./types";

export async function getProfile(store: ProfileStore, tenantId: string, userId: string): Promise<Profile | null> {
  return store.get(tenantId, userId);
}

export async function updateProfile(
  store: ProfileStore,
  tenantId: string,
  userId: string,
  patch: Partial<Omit<Profile, "tenantId" | "userId">>,
): Promise<Profile> {
  return store.update(tenantId, userId, patch);
}
