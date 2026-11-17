import { Table, newId } from "../db.ts";
import type { Notification, NotificationKind } from "./types.ts";

export const notificationsTable = new Table<Notification>();

export function insertNotification(
  userId: string,
  kind: NotificationKind,
  payload: Record<string, string>,
  now: Date = new Date(),
): Notification {
  return notificationsTable.insert({
    id: newId("ntf"),
    userId,
    kind,
    payload,
    createdAt: now.toISOString(),
    readAt: null,
  });
}

export function listForUser(userId: string, opts: { unreadOnly?: boolean; limit?: number } = {}): Notification[] {
  const rows = notificationsTable
    .where((n) => n.userId === userId && (!opts.unreadOnly || n.readAt === null))
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  return rows.slice(0, opts.limit ?? 50);
}

export function markRead(userId: string, ids: string[], now: Date = new Date()): number {
  let n = 0;
  for (const id of ids) {
    const row = notificationsTable.get(id);
    if (row && row.userId === userId && row.readAt === null) {
      notificationsTable.update(id, { readAt: now.toISOString() });
      n += 1;
    }
  }
  return n;
}

export function deleteOlderThan(cutoff: Date): number {
  const old = notificationsTable.where((n) => n.createdAt < cutoff.toISOString());
  for (const n of old) notificationsTable.delete(n.id);
  return old.length;
}
