import { createServer } from "node:http";
import { listNotifications, markNotificationsRead } from "./notifications/routes.ts";
import { tick } from "./scheduler/index.ts";
import { registerAllJobs } from "./scheduler/jobs.ts";

registerAllJobs();
setInterval(() => void tick(), 60_000);

createServer((req, res) => {
  const userId = String(req.headers["x-user-id"] ?? "");
  if (!userId) {
    res.writeHead(401).end();
    return;
  }
  const r = Object.assign(req, { userId });
  if (req.method === "GET" && req.url?.startsWith("/api/notifications")) return listNotifications(r, res);
  if (req.method === "POST" && req.url === "/api/notifications/read") {
    let buf = "";
    req.on("data", (c) => (buf += c));
    req.on("end", () => markNotificationsRead(Object.assign(r, { body: JSON.parse(buf || "{}") }), res));
    return;
  }
  res.writeHead(404).end();
}).listen(Number(process.env.PORT ?? 3000));
