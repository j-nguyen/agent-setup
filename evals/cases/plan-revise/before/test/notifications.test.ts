import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { usersTable } from "../src/users/users.ts";
import { notificationsTable, listForUser, markRead, deleteOlderThan } from "../src/notifications/repo.ts";
import { notify } from "../src/notifications/service.ts";
import { renderText } from "../src/notifications/render.ts";

beforeEach(() => {
  usersTable.clear();
  notificationsTable.clear();
  usersTable.insert({ id: "u1", email: "a@example.com", name: "Ann", teamId: "t1", deactivated: false });
  usersTable.insert({ id: "u2", email: "b@example.com", name: "Bo", teamId: "t1", deactivated: true });
});

test("notify stores a notification for active users only (C3)", () => {
  assert.ok(notify("u1", "mention", { actor: "Bo", taskTitle: "Ship it" }));
  assert.equal(notify("u2", "mention", { actor: "Ann", taskTitle: "x" }), null);
  assert.equal(listForUser("u1").length, 1);
});

test("list is newest first and filters unread (C4)", () => {
  notify("u1", "mention", { actor: "A", taskTitle: "one" }, new Date("2026-01-01T00:00:00Z"));
  const second = notify("u1", "task.assigned", { actor: "A", taskTitle: "two" }, new Date("2026-01-02T00:00:00Z"))!;
  assert.equal(listForUser("u1")[0].id, second.id);
  markRead("u1", [second.id]);
  assert.deepEqual(listForUser("u1", { unreadOnly: true }).map((n) => n.payload.taskTitle), ["one"]);
});

test("markRead ignores other users' notifications (C5)", () => {
  const n = notify("u1", "mention", { actor: "A", taskTitle: "x" })!;
  assert.equal(markRead("someone-else", [n.id]), 0);
});

test("renderText covers every kind (C2)", () => {
  const n = notify("u1", "task.due_soon", { taskTitle: "Report", due: "tomorrow" })!;
  assert.equal(renderText(n), '"Report" is due tomorrow');
});

test("retention deletes old notifications (C8)", () => {
  notify("u1", "mention", { actor: "A", taskTitle: "old" }, new Date("2025-01-01T00:00:00Z"));
  notify("u1", "mention", { actor: "A", taskTitle: "new" }, new Date("2026-06-01T00:00:00Z"));
  assert.equal(deleteOlderThan(new Date("2026-01-01T00:00:00Z")), 1);
});
