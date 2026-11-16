#!/usr/bin/env node
// Controlled burst test for rate limiting. It only targets localhost, or a host you name with
// --confirm-own <hostname> to state that you own that deployment. Rate and duration are capped.
//   node academy/tools/loadtest.mjs --url http://localhost:8787/api/lab/echo --rps 5 --seconds 10
//   node academy/tools/loadtest.mjs --url https://exergy-academy.example.workers.dev/api/lab/echo --confirm-own exergy-academy.example.workers.dev

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

import { parseArgs } from "./lib/http.mjs";

export const MAX_RPS = 20;
export const MAX_SECONDS = 30;
const LOCAL = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);

export function checkTarget(url, confirmOwn) {
  const target = new URL(url);
  if (LOCAL.has(target.hostname)) return { ok: true, local: true };
  if (typeof confirmOwn === "string" && confirmOwn === target.hostname) return { ok: true, local: false };
  return {
    ok: false,
    reason: `Refusing to send test traffic to ${target.hostname}. Use localhost, or pass --confirm-own ${target.hostname} if it is your own deployment.`,
  };
}

export function clampPlan(rps, seconds) {
  return {
    rps: Math.min(MAX_RPS, Math.max(1, Math.floor(Number(rps) || 5))),
    seconds: Math.min(MAX_SECONDS, Math.max(1, Math.floor(Number(seconds) || 10))),
  };
}

export function toDataset(url, buckets, { local, now = new Date() }) {
  return {
    kind: "real",
    title: "Rate-limit burst: answers per second",
    source: `academy/tools/loadtest.mjs against ${url}`,
    collected_at: now.toISOString(),
    environment: local ? "local wrangler dev (Miniflare enforces the Rate Limiting binding locally)" : "your own Cloudflare deployment",
    chart: "line",
    unit: "requests",
    x: "second",
    x_label: "Second",
    series: [
      { key: "ok", label: "2xx" },
      { key: "limited", label: "429 rate limited" },
      { key: "other", label: "Other" },
    ],
    rows: buckets,
    description: "Requests were sent at a fixed rate from one client. A rise in 429s shows the limiter engaging.",
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2), { url: "http://localhost:8787/api/lab/echo" });
  const check = checkTarget(args.url, args["confirm-own"]);
  if (!check.ok) {
    console.error(check.reason);
    process.exit(2);
  }
  const { rps, seconds } = clampPlan(args.rps, args.seconds);
  console.error(`Sending ${rps} req/s for ${seconds} s to ${args.url}`);
  const buckets = Array.from({ length: seconds }, (_, i) => ({ second: i + 1, ok: 0, limited: 0, other: 0 }));
  const pending = [];
  for (let s = 0; s < seconds; s += 1) {
    for (let r = 0; r < rps; r += 1) {
      const bucket = buckets[s];
      pending.push(
        fetch(args.url, { headers: { "User-Agent": "exergy-academy-loadtest/1.0" } })
          .then((res) => {
            res.body?.cancel();
            if (res.status === 429) bucket.limited += 1;
            else if (res.ok) bucket.ok += 1;
            else bucket.other += 1;
          })
          .catch(() => (bucket.other += 1)),
      );
      await new Promise((resolve) => setTimeout(resolve, 1000 / rps));
    }
  }
  await Promise.all(pending);
  for (const b of buckets) console.error(`s${String(b.second).padStart(2)}  2xx ${b.ok}  429 ${b.limited}  other ${b.other}`);
  const data = toDataset(args.url, buckets, { local: check.local });
  const text = JSON.stringify(data, null, 2) + "\n";
  if (typeof args.out === "string") {
    await mkdir(path.dirname(args.out), { recursive: true });
    await writeFile(args.out, text);
    console.error(`wrote ${args.out}`);
  } else process.stdout.write(text);
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) await main();
