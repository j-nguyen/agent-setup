export interface Req {
  method: string;
  path: string;
  query: URLSearchParams;
  body: unknown;
  params: Record<string, string>;
}

export interface Res {
  status: number;
  body: unknown;
}

export type Handler = (req: Req) => Promise<Res>;
export type Middleware = (req: Req, next: () => Promise<Res>) => Promise<Res>;

interface Route {
  method: string;
  pattern: RegExp;
  keys: string[];
  handler: Handler;
}

export class Router {
  private routes: Route[] = [];
  private middleware: Middleware[] = [];

  use(mw: Middleware): void {
    this.middleware.push(mw);
  }

  get(path: string, handler: Handler): void {
    this.add("GET", path, handler);
  }

  post(path: string, handler: Handler): void {
    this.add("POST", path, handler);
  }

  private add(method: string, path: string, handler: Handler): void {
    const keys: string[] = [];
    const source = path.replace(/:(\w+)/g, (_m, key: string) => {
      keys.push(key);
      return "([^/]+)";
    });
    this.routes.push({ method, pattern: new RegExp(`^${source}$`), keys, handler });
  }

  async handle(method: string, url: string, body: unknown = undefined): Promise<Res> {
    const parsed = new URL(url, "http://localhost");
    const req: Req = { method, path: parsed.pathname, query: parsed.searchParams, body, params: {} };
    const route = this.routes.find((r) => r.method === method && r.pattern.test(parsed.pathname));
    const endpoint: Handler = async (r) => {
      if (!route) return { status: 404, body: { error: "not_found" } };
      const match = route.pattern.exec(r.path)!;
      route.keys.forEach((k, i) => (r.params[k] = decodeURIComponent(match[i + 1])));
      return route.handler(r);
    };
    const chain = this.middleware.reduceRight<() => Promise<Res>>(
      (next, mw) => () => mw(req, next),
      () => endpoint(req),
    );
    return chain();
  }
}
