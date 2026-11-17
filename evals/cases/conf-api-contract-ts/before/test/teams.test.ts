import { test } from "node:test";
import assert from "node:assert/strict";
import { buildApp } from "../src/app.ts";

const teams = Array.from({ length: 5 }, (_, i) => ({ id: `team_${i}`, name: `Team ${i}` }));

test("lists teams with cursor pagination", async () => {
  const app = buildApp({ teams, logSink: () => {} });
  const first = await app.handle("GET", "/v1/teams?limit=3");
  const body = first.body as { items: { id: string }[]; nextCursor: string | null };
  assert.equal(first.status, 200);
  assert.deepEqual(body.items.map((t) => t.id), ["team_0", "team_1", "team_2"]);
  assert.ok(body.nextCursor);
  const second = await app.handle("GET", `/v1/teams?limit=3&cursor=${body.nextCursor}`);
  const body2 = second.body as { items: { id: string }[]; nextCursor: string | null };
  assert.deepEqual(body2.items.map((t) => t.id), ["team_3", "team_4"]);
  assert.equal(body2.nextCursor, null);
});
