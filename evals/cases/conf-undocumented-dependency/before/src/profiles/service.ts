import type { Profile, ProfileRepo } from "./repo.ts";

export class ProfileService {
  private readonly repo: ProfileRepo;

  constructor(repo: ProfileRepo) {
    this.repo = repo;
  }

  async getProfile(id: string): Promise<Profile | null> {
    return this.repo.findById(id);
  }

  async updateProfile(
    id: string,
    patch: Partial<Pick<Profile, "displayName" | "avatarUrl">>,
  ): Promise<Profile | null> {
    if (patch.displayName !== undefined && patch.displayName.trim() === "") {
      throw new Error("displayName must not be empty");
    }
    return this.repo.update(id, patch);
  }
}
