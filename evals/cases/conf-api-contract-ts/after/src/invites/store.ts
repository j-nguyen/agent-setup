import { randomUUID } from "node:crypto";

export interface Invite {
  id: string;
  email: string;
  expiresAt: Date;
  createdBy: string;
  createdAt: Date;
}

export interface InviteStore {
  create(email: string, createdBy: string, now?: Date): Promise<Invite>;
  list(offset: number, limit: number): Promise<{ invites: Invite[]; total: number }>;
}

const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000;

export class InMemoryInviteStore implements InviteStore {
  private invites: Invite[] = [];

  async create(email: string, createdBy: string, now: Date = new Date()): Promise<Invite> {
    const invite: Invite = {
      id: `inv_${randomUUID()}`,
      email: email.toLowerCase(),
      expiresAt: new Date(now.getTime() + SEVEN_DAYS_MS),
      createdBy,
      createdAt: now,
    };
    this.invites.push(invite);
    return invite;
  }

  async list(offset: number, limit: number): Promise<{ invites: Invite[]; total: number }> {
    const sorted = [...this.invites].sort((a, b) => a.createdAt.getTime() - b.createdAt.getTime());
    return { invites: sorted.slice(offset, offset + limit), total: sorted.length };
  }
}
