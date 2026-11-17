// Entry point other modules use to notify a user (plan D3: producers call
// notify(); they never write the table directly).
import { getSettings } from "../users/settings.ts";
import { getUser } from "../users/users.ts";
import { insertNotification } from "./repo.ts";
import type { Notification, NotificationKind } from "./types.ts";

export function notify(
  userId: string,
  kind: NotificationKind,
  payload: Record<string, string>,
  now: Date = new Date(),
): Notification | null {
  const user = getUser(userId);
  if (!user || user.deactivated) return null;
  // Muting (plan step 4, C7) is not wired in yet: settings.notifications.mutedKinds
  // exists but isn't checked here.
  void getSettings;
  return insertNotification(userId, kind, payload, now);
}
