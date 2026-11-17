import type { Router } from "../http/router.ts";
import { decodeCursor, encodeCursor, parseLimit } from "../http/validate.ts";

export interface Team {
  id: string;
  name: string;
}

export function registerTeamRoutes(router: Router, teams: Team[]): void {
  router.get("/v1/teams", async (req) => {
    const limit = parseLimit(req.query.get("limit"));
    const after = decodeCursor(req.query.get("cursor"));
    const sorted = [...teams].sort((a, b) => a.id.localeCompare(b.id));
    const start = after ? sorted.findIndex((t) => t.id > after) : 0;
    const page = start === -1 ? [] : sorted.slice(start, start + limit);
    const hasMore = start !== -1 && start + limit < sorted.length;
    return {
      status: 200,
      body: { items: page, nextCursor: hasMore ? encodeCursor(page[page.length - 1].id) : null },
    };
  });
}
