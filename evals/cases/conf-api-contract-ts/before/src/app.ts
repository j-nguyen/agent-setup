import { Router } from "./http/router.ts";
import { requestLogger, type LogSink } from "./http/logging.ts";
import { registerTeamRoutes, type Team } from "./teams/routes.ts";

export interface AppDeps {
  teams?: Team[];
  logSink?: LogSink;
}

export function buildApp(deps: AppDeps = {}): Router {
  const router = new Router();
  router.use(requestLogger(deps.logSink));
  registerTeamRoutes(router, deps.teams ?? []);
  return router;
}
