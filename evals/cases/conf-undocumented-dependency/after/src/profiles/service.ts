import type { Profile, ProfileRepo } from "./repo.ts";
import type { ProfileCache, ProfilePatch } from "./types.ts";

const TTL_SECONDS = 60;

const cacheKey = (id: string) => `profile:${id}`;

export class ProfileService {
  private readonly repo: ProfileRepo;
  private readonly cache: ProfileCache;

  constructor(repo: ProfileRepo, cache: ProfileCache) {
    this.repo = repo;
    this.cache = cache;
  }

  async getProfile(id: string): Promise<Profile | null> {
    const cached = await this.cache.get(cacheKey(id));
    if (cached) return cached;
    const profile = await this.repo.findById(id);
    if (profile) await this.cache.set(cacheKey(id), profile, TTL_SECONDS);
    return profile;
  }

  async updateProfile(id: string, patch: ProfilePatch): Promise<Profile | null> {
    if (patch.displayName !== undefined && patch.displayName.trim() === "") {
      throw new Error("displayName must not be empty");
    }
    const updated = await this.repo.update(id, patch);
    await this.cache.delete(cacheKey(id));
    return updated;
  }
}
