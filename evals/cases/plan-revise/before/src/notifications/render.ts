import type { Notification } from "./types.ts";

// One-line text for a notification, used by the in-app list (plan D2).
export function renderText(n: Notification): string {
  switch (n.kind) {
    case "task.assigned":
      return `${n.payload.actor} assigned you "${n.payload.taskTitle}"`;
    case "task.commented":
      return `${n.payload.actor} commented on "${n.payload.taskTitle}"`;
    case "task.due_soon":
      return `"${n.payload.taskTitle}" is due ${n.payload.due}`;
    case "mention":
      return `${n.payload.actor} mentioned you in "${n.payload.taskTitle}"`;
  }
}
