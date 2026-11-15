import express from "express";

export function createApp() {
  const app = express();
  app.use(express.json({ limit: "100kb" }));
  app.get("/healthz", (_req, res) => res.send("ok"));
  return app;
}
