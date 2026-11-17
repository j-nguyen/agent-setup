import { createServer } from "node:http";
import { InMemoryProfileRepo } from "./profiles/repo.ts";
import { ProfileService } from "./profiles/service.ts";

const service = new ProfileService(new InMemoryProfileRepo());

const server = createServer(async (req, res) => {
  const match = req.url?.match(/^\/profiles\/([\w-]+)$/);
  if (!match) {
    res.writeHead(404).end();
    return;
  }
  const id = match[1];
  if (req.method === "GET") {
    const profile = await service.getProfile(id);
    if (!profile) {
      res.writeHead(404).end();
      return;
    }
    res.writeHead(200, { "content-type": "application/json" }).end(JSON.stringify(profile));
    return;
  }
  if (req.method === "PATCH") {
    let body = "";
    for await (const chunk of req) body += chunk;
    try {
      const updated = await service.updateProfile(id, JSON.parse(body));
      if (!updated) {
        res.writeHead(404).end();
        return;
      }
      res.writeHead(200, { "content-type": "application/json" }).end(JSON.stringify(updated));
    } catch (err) {
      res.writeHead(400, { "content-type": "application/json" }).end(JSON.stringify({ error: String(err) }));
    }
    return;
  }
  res.writeHead(405).end();
});

server.listen(Number(process.env.PORT ?? 3000));
