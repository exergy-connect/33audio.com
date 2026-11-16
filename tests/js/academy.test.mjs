import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import worker, { echo } from "../../academy/worker/index.js";
import { aeSql, summarizeTelemetry } from "../../academy/worker/telemetry.js";
import { parseArgs, parseServerTiming, percentile } from "../../academy/tools/lib/http.mjs";
import { checkTarget, clampPlan, toDataset } from "../../academy/tools/loadtest.mjs";
import { dataset, summarize } from "../../academy/tools/measure.mjs";
import { hopView, routeView } from "../../academy/tools/labnet-path.mjs";
import { toDatasets } from "../../academy/tools/telemetry.mjs";
import { requests, send, validate } from "../../security/waf/apply.mjs";

const json = async (path) => JSON.parse(await readFile(new URL(path, import.meta.url), "utf8"));

test("WAF and cache rule files validate and map to Rulesets API calls", async () => {
  const waf = await json("../../security/waf/rules.json");
  const cache = await json("../../delivery/cache-rules.json");
  assert.deepEqual(validate(waf), []);
  assert.deepEqual(validate(cache), []);
  const plan = requests(waf, "zone1");
  assert.equal(plan.length, 2);
  assert.match(plan[0].url, /zones\/zone1\/rulesets\/phases\/http_request_firewall_custom\/entrypoint$/);
  const cachePlan = requests(cache, "zone1");
  assert.equal(cachePlan.filter((r) => r.method === "PATCH").length, 2);
  const broken = structuredClone(waf);
  broken.phases.http_ratelimit.rules[0].ratelimit.characteristics = ["ip.src"];
  broken.phases.http_request_firewall_custom.rules[1].action = "explode";
  assert.equal(validate(broken).length, 2);
});

test("Rulesets API errors surface", async () => {
  const fail = async () => new Response(JSON.stringify({ success: false, errors: [{ code: 10000, message: "Authentication error" }] }), { status: 403 });
  await assert.rejects(send({ method: "PUT", url: "https://x", body: {} }, "t", fail), /10000: Authentication error/);
  const ok = async (url, init) => {
    assert.equal(init.headers.Authorization, "Bearer t");
    return new Response(JSON.stringify({ success: true, result: { id: "rs1", version: "2" } }));
  };
  assert.deepEqual(await send({ method: "PUT", url: "https://x", body: {} }, "t", ok), { id: "rs1", version: "2" });
});

test("load test only targets localhost or a claimed host, with caps", () => {
  assert.equal(checkTarget("http://localhost:8787/x").ok, true);
  assert.equal(checkTarget("https://shop.example.com/").ok, false);
  assert.equal(checkTarget("https://shop.example.com/", "shop.example.com").ok, true);
  assert.equal(checkTarget("https://evil.example.com/", "shop.example.com").ok, false);
  assert.deepEqual(clampPlan(500, 999), { rps: 20, seconds: 30 });
  const data = toDataset("http://localhost/x", [{ second: 1, ok: 1, limited: 0, other: 0 }], { local: true, now: new Date(0) });
  assert.equal(data.kind, "real");
  assert.equal(data.collected_at, "1970-01-01T00:00:00.000Z");
});

test("measurement summaries and datasets", () => {
  const samples = [3, 5, 9].map((ttfb) => ({ status: 200, headers: { "server-timing": 'cache;desc="HIT";dur=1' }, timings: { ttfb_ms: ttfb } }));
  const row = summarize("/api/stock", samples);
  assert.equal(row.p50, 5);
  assert.equal(row.p95, 9);
  assert.equal(row.cache, "HIT×3");
  const data = dataset("http://localhost:8788", [row], { environment: "test", now: new Date(0) });
  assert.equal(data.kind, "real");
  assert.match(data.source, /measure\.mjs against http:\/\/localhost:8788/);
});

test("HTTP helpers", () => {
  assert.deepEqual(parseServerTiming('cache;desc="MISS";dur=1, kv;desc="STOCK get";dur=3'), [
    { name: "cache", dur: 1, desc: "MISS" },
    { name: "kv", dur: 3, desc: "STOCK get" },
  ]);
  assert.equal(percentile([1, 2, 3, 4], 50), 2);
  assert.deepEqual(parseArgs(["a", "--n", "3", "--flag", "--x=y"]), { _: ["a"], n: "3", flag: true, x: "y" });
});

test("telemetry summaries are labeled real with a source and time", async () => {
  const fetchImpl = async (url, init) => {
    assert.match(url, /accounts\/acc\/analytics_engine\/sql$/);
    assert.match(init.body, /FROM caddock_search/);
    return new Response(JSON.stringify({ data: [{ mode: "ai", searches: "4", p50_ms: "600", p95_ms: "900" }] }));
  };
  const rows = await aeSql({ CF_ACCOUNT_ID: "acc", ANALYTICS_API_TOKEN: "t" }, "SELECT 1 FROM caddock_search", fetchImpl);
  const summary = summarizeTelemetry({ search_modes: rows, lab_requests: [] }, new Date(0));
  assert.equal(summary.kind, "real");
  assert.deepEqual(summary.search_modes, [{ label: "ai", searches: 4, p50_ms: 600, p95_ms: 900 }]);
  const datasets = toDatasets(summary);
  assert.equal(datasets["search-modes"].kind, "real");
  assert.equal(datasets["search-modes"].collected_at, "1970-01-01T00:00:00.000Z");
});

test("Academy Worker: health, telemetry without credentials, rate limit, provenance", async () => {
  const ctx = { waitUntil() {} };
  const env = { ASSETS: { fetch: async () => new Response("asset") }, LAB_LIMITER: { limit: async () => ({ success: false }) } };
  const health = await worker.fetch(new Request("http://x/api/health"), env, ctx);
  assert.equal((await health.json()).ok, true);
  const tele = await (await worker.fetch(new Request("http://x/api/telemetry"), env, ctx)).json();
  assert.equal(tele.kind, "unconfigured");
  assert.deepEqual(tele.missing, ["ANALYTICS_API_TOKEN", "CF_ACCOUNT_ID"]);
  const limited = await worker.fetch(new Request("http://x/api/lab/echo"), env, ctx);
  assert.equal(limited.status, 429);
  const asset = await worker.fetch(new Request("http://x/labs/"), env, ctx);
  assert.equal(await asset.text(), "asset");
  assert.equal(echo(new Request("http://x/api/lab/echo"), { DEPLOYMENT: "local" }, 0).kind, "simulated");
  assert.equal(echo(new Request("http://x/api/lab/echo"), { DEPLOYMENT: "production" }, 0).kind, "real");
});

test("lab.net run views keep only lab.net's fields", () => {
  assert.deepEqual(routeView({ prefix: "192.0.2.0", length: 24, type: "bgp", nexthop: "10.1.0.1", aspath: "13335", ifname: "eth2" }), {
    prefix: "192.0.2.0/24", protocol: "bgp", nexthop: "10.1.0.1", aspath: "13335", ifname: "eth2",
  });
  assert.deepEqual(hopView({ kind: "forward", at: "isp_hou", from: "a", to: "b", ttl: 63, periodic: false, seq: 4 }), { kind: "forward", at: "isp_hou", from: "a", to: "b", ttl: 63, seq: 4 });
});
