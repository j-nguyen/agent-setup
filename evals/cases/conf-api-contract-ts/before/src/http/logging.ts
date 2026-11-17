import type { Middleware } from "./router.ts";

export type LogSink = (line: string) => void;

export function requestLogger(sink: LogSink = (l) => process.stdout.write(l + "\n")): Middleware {
  return async (req, next) => {
    const started = performance.now();
    const res = await next();
    sink(JSON.stringify({ method: req.method, path: req.path, status: res.status,
                          ms: Math.round(performance.now() - started) }));
    return res;
  };
}
