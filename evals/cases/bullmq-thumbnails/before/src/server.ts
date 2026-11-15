import express from "express";
import { putObject } from "./storage";

const app = express();

// Clients send a client-generated uploadId and retry the same request on timeouts.
app.put("/uploads/:uploadId", express.raw({ type: "image/*", limit: "20mb" }), async (req, res) => {
  const { uploadId } = req.params;
  if (!/^[a-z0-9-]{8,64}$/.test(uploadId)) return res.status(400).send("bad upload id");
  const key = `uploads/${uploadId}/original`;
  await putObject(key, req.body as Buffer, req.header("content-type") ?? "application/octet-stream");
  res.status(201).json({ uploadId, key });
});

app.listen(Number(process.env.PORT ?? 3000));
