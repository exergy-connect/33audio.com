#!/usr/bin/env node
// Runs the lab checks against a running shop (and optionally the Academy Worker) and prints PASS/FAIL.
//   node academy/tools/lab-check.mjs --shop http://localhost:8788 [--academy http://localhost:8787]
//     [--webhook-secret whsec_lab_local] [--topics deploy,discovery,ai,observability,academy] [--burst]

import { pathToFileURL } from "node:url";

import { signPayload } from "../../worker/stripe.js";
import { parseArgs, parseServerTiming, timedRequest } from "./lib/http.mjs";

const results = [];

async function check(topic, name, fn) {
  try {
    const detail = await fn();
    results.push({ topic, name, ok: true });
    console.log(`PASS  ${topic.padEnd(13)} ${name}${detail ? `  (${detail})` : ""}`);
  } catch (error) {
    results.push({ topic, name, ok: false });
    console.log(`FAIL  ${topic.padEnd(13)} ${name}  → ${error.message}`);
  }
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function get(base, path, options) {
  return timedRequest(new URL(path, base).toString(), options);
}

function jsonOf(res) {
  try {
    return JSON.parse(res.body);
  } catch {
    throw new Error(`expected JSON, got ${res.body.slice(0, 80)}`);
  }
}

export async function deployChecks(shop, secret) {
  await check("deploy", "GET /api/stock returns the KV stock document", async () => {
    const res = await get(shop, "/api/stock");
    assert(res.status === 200, `status ${res.status}; seed local KV first (see the lab)`);
    const doc = jsonOf(res);
    assert(Array.isArray(doc.parts) && doc.parts.length > 0, "no parts");
    assert(!("applied_sessions" in doc), "applied_sessions must stay private");
    assert(/max-age=30/.test(res.headers["cache-control"] ?? ""), "missing Cache-Control max-age=30");
    return `${doc.parts.length} parts`;
  });
  await check("deploy", "second /api/stock is served by the Cache API", async () => {
    const res = await get(shop, "/api/stock");
    const cache = parseServerTiming(res.headers["server-timing"]).find((e) => e.name === "cache");
    assert(cache, "no Server-Timing cache entry");
    assert(cache.desc === "HIT", `cache ${cache.desc}`);
    return "Server-Timing cache HIT";
  });
  await check("deploy", "GET /api/checkout reports the feature flag", async () => {
    const body = jsonOf(await get(shop, "/api/checkout"));
    assert(body.enabled === false, `enabled is ${body.enabled}; CHECKOUT_ENABLED should be "false" in the lab`);
    return body.message;
  });
  await check("deploy", "POST /api/checkout is refused while the flag is off", async () => {
    const res = await get(shop, "/api/checkout", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ items: [{ id: "MM177-4.32K", qty: 1 }] }) });
    assert(res.status === 503, `status ${res.status}`);
    assert(jsonOf(res).error === "checkout_disabled", "wrong error code");
    return "503 checkout_disabled";
  });
  await check("deploy", "webhook rejects a bad Stripe-Signature", async () => {
    const res = await get(shop, "/api/stripe-webhook", { method: "POST", headers: { "Stripe-Signature": "t=1,v1=00" }, body: "{}" });
    assert(res.status === 400, `status ${res.status}`);
    return "400 bad_signature";
  });
  if (secret) {
    await check("deploy", "webhook accepts a correctly signed event", async () => {
      const payload = JSON.stringify({ id: "evt_lab", type: "customer.created", data: { object: {} } });
      const t = Math.floor(Date.now() / 1000);
      const v1 = await signPayload(payload, secret, t);
      const res = await get(shop, "/api/stripe-webhook", { method: "POST", headers: { "Stripe-Signature": `t=${t},v1=${v1}`, "Content-Type": "application/json" }, body: payload });
      assert(res.status === 200, `status ${res.status}; is STRIPE_WEBHOOK_SECRET in .dev.vars the same secret?`);
      return res.body.trim();
    });
  }
}

export async function discoveryChecks(shop) {
  await check("discovery", "robots.txt allows AI crawlers and lists the sitemap", async () => {
    const text = (await get(shop, "/robots.txt")).body;
    for (const bot of ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended"]) assert(text.includes(`User-agent: ${bot}\nAllow: /`), `${bot} not allowed`);
    assert(/Sitemap: https?:\/\/\S+\/sitemap\.xml/.test(text), "no Sitemap line");
    return "4 AI crawlers allowed";
  });
  await check("discovery", "llms.txt lists series and part pages", async () => {
    const res = await get(shop, "/llms.txt");
    assert(res.status === 200, `status ${res.status}`);
    assert(res.body.startsWith("# "), "llms.txt must start with an H1");
    const links = (res.body.match(/\/parts\//g) ?? []).length;
    assert(links >= 80, `only ${links} part links`);
    return `${links} part links`;
  });
  await check("discovery", "part page has Product and FAQPage JSON-LD", async () => {
    const html = (await get(shop, "/parts/mm177-4.32k/")).body;
    const blocks = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map((m) => JSON.parse(m[1]));
    const types = new Set();
    const walk = (node) => {
      if (Array.isArray(node)) return node.forEach(walk);
      if (node && typeof node === "object") {
        if (node["@type"]) [].concat(node["@type"]).forEach((t) => types.add(t));
        Object.values(node).forEach(walk);
      }
    };
    walk(blocks);
    assert(types.has("Product"), "no Product");
    assert(types.has("FAQPage"), "no FAQPage");
    assert(types.has("Offer"), "no Offer");
    return [...types].slice(0, 6).join(", ");
  });
  await check("discovery", "catalog.json points at its xYang schema and context", async () => {
    const doc = jsonOf(await get(shop, "/catalog.json"));
    assert(doc.$schema?.endsWith("/schema/catalog.schema.json"), "no $schema");
    assert(doc["@context"]?.endsWith("/schema/context.jsonld"), "no @context");
    const schema = await get(shop, "/schema/catalog.schema.json");
    assert(schema.status === 200, `schema status ${schema.status}`);
    return `${doc.parts.length} parts`;
  });
  await check("discovery", "sitemap lists every page", async () => {
    const xml = (await get(shop, "/sitemap.xml")).body;
    const count = (xml.match(/<loc>/g) ?? []).length;
    assert(count >= 90, `only ${count} URLs`);
    return `${count} URLs`;
  });
}

export async function aiChecks(shop) {
  await check("ai", "/api/search answers the tube amp question", async () => {
    const res = await get(shop, "/api/search?q=" + encodeURIComponent("I need a 10M resistor for a tube amp"));
    assert(res.status === 200, `status ${res.status}`);
    const body = jsonOf(res);
    assert(body.results.length > 0, "no results");
    assert(body.intent.ohms === 10e6, `parsed ohms ${body.intent.ohms}`);
    assert(body.results[0].voltage_rating >= 500, "top result is under 500 V");
    if (body.mode === "keyword") assert(body.fallback_reason, "keyword mode must say why");
    return `mode ${body.mode}, top ${body.results[0].part_number}`;
  });
  await check("ai", "/ask/ page is served", async () => {
    const res = await get(shop, "/ask/");
    assert(res.status === 200 && res.body.includes("data-ask-form"), `status ${res.status}`);
  });
}

export async function observabilityChecks(shop) {
  await check("observability", "API responses carry Server-Timing", async () => {
    const stock = await get(shop, "/api/stock");
    const search = await get(shop, "/api/search?q=4.32K");
    assert(stock.headers["server-timing"], "/api/stock has no Server-Timing");
    assert(search.headers["server-timing"], "/api/search has no Server-Timing");
    assert(search.headers["x-search-mode"], "no X-Search-Mode");
    return search.headers["server-timing"];
  });
  await check("observability", "TTFB is measurable", async () => {
    const samples = [];
    for (let i = 0; i < 3; i += 1) samples.push((await get(shop, "/api/stock")).timings.ttfb_ms);
    return `TTFB ${samples.join(" / ")} ms`;
  });
}

export async function academyChecks(academy, burst) {
  await check("academy", "/api/health", async () => {
    const body = jsonOf(await get(academy, "/api/health"));
    assert(body.ok === true, "not ok");
    return `deployment ${body.deployment}`;
  });
  await check("academy", "home and a lab page render", async () => {
    for (const path of ["/", "/labs/deploy/", "/explore/security/"]) {
      const res = await get(academy, path);
      assert(res.status === 200, `${path} status ${res.status}`);
    }
  });
  await check("academy", "/api/lab/echo labels its provenance", async () => {
    const body = jsonOf(await get(academy, "/api/lab/echo"));
    assert(["real", "simulated"].includes(body.kind), `kind ${body.kind}`);
    return `kind ${body.kind}`;
  });
  await check("academy", "/api/lab/cache goes MISS then HIT", async () => {
    const key = `lab${Date.now()}`;
    const a = await get(academy, `/api/lab/cache?key=${key}`);
    const b = await get(academy, `/api/lab/cache?key=${key}`);
    assert(a.headers["x-academy-cache"] === "MISS", `first ${a.headers["x-academy-cache"]}`);
    assert(b.headers["x-academy-cache"] === "HIT", `second ${b.headers["x-academy-cache"]}`);
    return "MISS → HIT";
  });
  await check("academy", "/api/telemetry says what it needs", async () => {
    const body = jsonOf(await get(academy, "/api/telemetry"));
    assert(["unconfigured", "real"].includes(body.kind), `kind ${body.kind}`);
    return body.kind === "real" ? "real" : `unconfigured, missing ${body.missing.join(", ")}`;
  });
  if (burst) {
    await check("academy", "LAB_LIMITER returns 429 after the limit", async () => {
      let limited = 0;
      for (let i = 0; i < 30; i += 1) {
        const res = await get(academy, "/api/lab/echo");
        if (res.status === 429) limited += 1;
      }
      assert(limited > 0, "no 429 after 30 requests");
      return `${limited} of 30 limited`;
    });
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2), { shop: "http://localhost:8788" });
  const topics = new Set(String(args.topics ?? "deploy,discovery,ai,observability" + (args.academy ? ",academy" : "")).split(","));
  if (topics.has("deploy")) await deployChecks(args.shop, typeof args["webhook-secret"] === "string" ? args["webhook-secret"] : null);
  if (topics.has("discovery")) await discoveryChecks(args.shop);
  if (topics.has("ai")) await aiChecks(args.shop);
  if (topics.has("observability")) await observabilityChecks(args.shop);
  if (topics.has("academy") && args.academy) await academyChecks(args.academy, Boolean(args.burst));
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) await main();
