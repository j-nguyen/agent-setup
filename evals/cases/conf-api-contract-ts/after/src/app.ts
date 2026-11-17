import { Router } from "./http/router.ts";
import { requestLogger, type LogSink } from "./http/logging.ts";
import { registerTeamRoutes, type Team } from "./teams/routes.ts";
import { registerInviteRoutes } from "./invites/routes.ts";
import { InMemoryInviteStore, type InviteStore } from "./invites/store.ts";

export interface AppDeps {
  teams?: Team[];
  invites?: InviteStore;
  logSink?: LogSink;
}

export function buildApp(deps: AppDeps = {}): Router {
  const router = new Router();
  router.use(requestLogger(deps.logSink));
  registerTeamRoutes(router, deps.teams ?? []);
  registerInviteRoutes(router, deps.invites ?? new InMemoryInviteStore());
  return router;
}
