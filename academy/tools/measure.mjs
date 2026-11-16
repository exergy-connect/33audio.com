#!/usr/bin/env node
// Measures time to first byte per route and writes a REAL TELEMETRY dataset the Academy can chart.
//   node academy/tools/measure.mjs --base http://localhost:8788 --out academy/data/real/local-latency.json
// --environment describes where the target runs, for example "wrangler pages dev on a GitHub Actions runner".

import { mkdir, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

import { parseArgs, parseServerTiming, percentile, timedRequest } from "./lib/http.mjs";

export const DEFAULT_ROUTES = ["/", "/parts/mm177-4.32k/", "/llms.txt", "/catalog.json", "/api/stock", "/api/search?q=10M+tube+amp"];

export function summarize(route, samples) {
  const ttfb = samples.map((s) => s.timings.ttfb_ms);
  const statuses = [...new Set(samples.map((s) => s.status))].join("/");
  const cache = {};
  for (const s of samples) {
    const entry = parseServerTiming(s.headers["server-timing"]).find((e) => e.name === "cache");
    if (entry?.desc) cache[entry.desc] = (cache[entry.desc] ?? 0) + 1;
  }
  return {
    label: route,
    p50: percentile(ttfb, 50),
    p95: percentile(ttfb, 95),
    samples: samples.length,
    status: statuses,
    cache: Object.keys(cache).length ? Object.entries(cache).map(([k, v]) => `${k}×${v}`).join(" ") : null,
  };
}

export function dataset(base, rows, { environment, now = new Date() } = {}) {
  return {
    kind: "real",
    title: "Time to first byte by route",
    source: `academy/tools/measure.mjs against ${base}`,
    collected_at: now.toISOString(),
    environment: environment || `${new URL(base).hostname} measured from ${os.hostname()}`,
    chart: "bar",
    unit: "ms",
    x: "label",
    x_label: "Route",
    series: [
      { key: "p50", label: "TTFB p50" },
      { key: "p95", label: "TTFB p95" },
    ],
    extra_columns: [
      { key: "samples", label: "Samples" },
      { key: "status", label: "Status" },
      { key: "cache", label: "Server-Timing cache" },
    ],
    rows,
    description: `Each route was requested ${rows[0]?.samples ?? 0} times over a fresh connection. Cache column counts Server-Timing cache results (HIT or MISS) where the route reports them.`,
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2), { base: "http://localhost:8788", n: "10" });
  const n = Math.min(50, Math.max(1, Number(args.n)));
  const routes = typeof args.routes === "string" ? args.routes.split(",") : DEFAULT_ROUTES;
  const rows = [];
  for (const route of routes) {
    const samples = [];
    for (let i = 0; i < n; i += 1) samples.push(await timedRequest(new URL(route, args.base).toString()));
    const row = summarize(route, samples);
    rows.push(row);
    console.error(`${route.padEnd(32)} status ${row.status}  p50 ${row.p50} ms  p95 ${row.p95} ms${row.cache ? `  cache ${row.cache}` : ""}`);
  }
  const data = dataset(args.base, rows, { environment: typeof args.environment === "string" ? args.environment : undefined });
  const text = JSON.stringify(data, null, 2) + "\n";
  if (typeof args.out === "string") {
    await mkdir(path.dirname(args.out), { recursive: true });
    await writeFile(args.out, text);
    console.error(`wrote ${args.out}`);
  } else process.stdout.write(text);
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) await main();
