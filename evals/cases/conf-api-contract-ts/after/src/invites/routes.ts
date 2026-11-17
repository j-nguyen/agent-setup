import type { Router } from "../http/router.ts";
import { isEmail, parseLimit } from "../http/validate.ts";
import type { Invite, InviteStore } from "./store.ts";

function toJson(invite: Invite) {
  return {
    id: invite.id,
    email: invite.email,
    expires_at: invite.expiresAt.toISOString(),
  };
}

export function registerInviteRoutes(router: Router, store: InviteStore): void {
  router.post("/v1/invites", async (req) => {
    const email = (req.body as { email?: unknown } | undefined)?.email;
    if (!isEmail(email)) {
      return { status: 400, body: { error: "invalid_email" } };
    }
    const invite = await store.create(email, "admin");
    return { status: 200, body: toJson(invite) };
  });

  router.get("/v1/invites", async (req) => {
    const limit = parseLimit(req.query.get("limit"));
    const page = Math.max(1, Number.parseInt(req.query.get("page") ?? "1", 10) || 1);
    const { invites, total } = await store.list((page - 1) * limit, limit);
    return {
      status: 200,
      body: { items: invites.map(toJson), page, total },
    };
  });
}
