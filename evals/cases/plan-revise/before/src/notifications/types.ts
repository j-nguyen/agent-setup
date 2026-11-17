// Notification kinds (plan D1). Adding a kind means adding it here and a
// renderer in render.ts.
export const NOTIFICATION_KINDS = [
  "task.assigned",
  "task.commented",
  "task.due_soon",
  "mention",
] as const;

export type NotificationKind = (typeof NOTIFICATION_KINDS)[number];

export type Notification = {
  id: string;
  userId: string;
  kind: NotificationKind;
  // Small JSON payload; enough to render without extra lookups (plan D2).
  payload: Record<string, string>;
  createdAt: string;
  readAt: string | null;
};
