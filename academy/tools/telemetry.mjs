#!/usr/bin/env node
// Pulls the last 24 h of Analytics Engine data and writes REAL TELEMETRY datasets for the Academy build.
//   CF_ACCOUNT_ID=... ANALYTICS_API_TOKEN=... node academy/tools/telemetry.mjs --out-dir academy/data/real
// Without both variables it prints what is missing and exits 0, so CI can call it unconditionally.

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

import { aeSql, summarizeTelemetry, telemetryQueries } from "../worker/telemetry.js";
import { parseArgs } from "./lib/http.mjs";

export function toDatasets(summary) {
  const base = { kind: "real", source: summary.source, collected_at: summary.collected_at, environment: "production Analytics Engine" };
  return {
    "search-modes": {
      ...base,
      title: "Part search: answers by mode (last 24 h)",
      chart: "bar",
      unit: "ms",
      x: "label",
      x_label: "Mode",
      series: [
        { key: "p50_ms", label: "p50 latency" },
        { key: "p95_ms", label: "p95 latency" },
      ],
      extra_columns: [{ key: "searches", label: "Searches" }],
      rows: summary.search_modes,
    },
    "lab-requests": {
      ...base,
      title: "Academy lab API requests (last 24 h)",
      chart: "bar",
      unit: "requests",
      x: "label",
      x_label: "Path and status",
      series: [{ key: "requests", label: "Requests" }],
      extra_columns: [{ key: "p50_ms", label: "p50 ms" }],
      rows: summary.lab_requests,
    },
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2), { "out-dir": "academy/data/real" });
  const env = { CF_ACCOUNT_ID: process.env.CF_ACCOUNT_ID, ANALYTICS_API_TOKEN: process.env.ANALYTICS_API_TOKEN };
  const missing = Object.entries(env).filter(([, v]) => !v).map(([k]) => k);
  if (missing.length) {
    console.log(`Telemetry skipped: ${missing.join(", ")} not set. Charts stay SIMULATED.`);
    return;
  }
  const results = {};
  for (const [name, sql] of Object.entries(telemetryQueries)) results[name] = await aeSql(env, sql);
  const datasets = toDatasets(summarizeTelemetry(results, new Date()));
  await mkdir(args["out-dir"], { recursive: true });
  for (const [name, data] of Object.entries(datasets)) {
    if (!data.rows.length) {
      console.log(`${name}: no rows in the last 24 h, keeping the simulated dataset`);
      continue;
    }
    const file = path.join(args["out-dir"], `${name}.json`);
    await writeFile(file, JSON.stringify(data, null, 2) + "\n");
    console.log(`wrote ${file} (${data.rows.length} rows)`);
  }
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) await main();
