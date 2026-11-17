import type { IncomingMessage, ServerResponse } from "node:http";
import { listForUser, markRead } from "./repo.ts";
import { renderText } from "./render.ts";

type Handler = (req: IncomingMessage & { userId: string; body?: any }, res: ServerResponse) => void;

function json(res: ServerResponse, status: number, body: unknown) {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
}

// GET /api/notifications?unread=1
export const listNotifications: Handler = (req, res) => {
  const url = new URL(req.url ?? "/", "http://x");
  const rows = listForUser(req.userId, { unreadOnly: url.searchParams.get("unread") === "1" });
  json(res, 200, { items: rows.map((n) => ({ ...n, text: renderText(n) })) });
};

// POST /api/notifications/read  {ids: string[]}
export const markNotificationsRead: Handler = (req, res) => {
  const ids = Array.isArray(req.body?.ids) ? req.body.ids.filter((x: unknown) => typeof x === "string") : [];
  json(res, 200, { updated: markRead(req.userId, ids) });
};
