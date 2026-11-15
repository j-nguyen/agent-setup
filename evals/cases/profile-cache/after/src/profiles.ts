import { TtlCache } from "./ttlCache";
import type { Profile, ProfileStore } from "./types";

const PROFILE_TTL_MS = 5 * 60_000;
const MISS_TTL_MS = 30_000;
const MAX_ENTRIES = 10_000;

const cache = new TtlCache<Profile>(PROFILE_TTL_MS, MAX_ENTRIES);
const notFound = new Set<string>();

/** Test helper: forget everything cached. */
export function clearProfileCache(): void {
  for (const key of notFound) cache.delete(key);
  notFound.clear();
}

export async function getProfile(store: ProfileStore, tenantId: string, userId: string): Promise<Profile | null> {
  const key = userId;
  if (notFound.has(key)) return null;
  const hit = cache.get(key);
  if (hit) return hit;

  const profile = await store.get(tenantId, userId);
  if (profile === null) {
    notFound.add(key);
    return null;
  }
  cache.set(key, profile);
  return profile;
}

export async function updateProfile(
  store: ProfileStore,
  tenantId: string,
  userId: string,
  patch: Partial<Omit<Profile, "tenantId" | "userId">>,
): Promise<Profile> {
  cache.delete(userId);
  notFound.delete(userId);
  return store.update(tenantId, userId, patch);
}

export const _limits = { PROFILE_TTL_MS, MISS_TTL_MS, MAX_ENTRIES };
