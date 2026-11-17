import type { Profile } from "./repo.ts";

export type ProfilePatch = Partial<Pick<Profile, "displayName" | "avatarUrl">>;

export interface ProfileCache {
  get(key: string): Promise<Profile | undefined>;
  set(key: string, value: Profile, ttlSeconds: number): Promise<void>;
  delete(key: string): Promise<void>;
}
