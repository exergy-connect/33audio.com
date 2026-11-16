#!/usr/bin/env node
// Seeds the local STOCK KV namespace from data/stock.json and starts the shop with `wrangler pages dev`.
//   npm run dev:shop --prefix academy            (port 8788)
//   node academy/tools/dev-shop.mjs --port 8790

import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { parseArgs } from "./lib/http.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..", "..");
const local = path.join(root, "academy", "node_modules", ".bin", process.platform === "win32" ? "wrangler.cmd" : "wrangler");
const wrangler = existsSync(local) ? [local] : ["npx", "--yes", "wrangler@4.162.0"];
const args = parseArgs(process.argv.slice(2), { port: "8788" });

function run(extra) {
  const [cmd, ...rest] = wrangler;
  return spawnSync(cmd, [...rest, ...extra], { cwd: root, stdio: "inherit", env: { ...process.env, CI: process.env.CI ?? "1" } });
}

const seeded = run(["kv", "key", "put", "stock", "--path", "data/stock.json", "--binding", "STOCK", "--local"]);
if (seeded.status !== 0) process.exit(seeded.status ?? 1);

const [cmd, ...rest] = wrangler;
const child = spawn(cmd, [...rest, "pages", "dev", "docs", "--port", String(args.port), "--ip", "127.0.0.1"], { cwd: root, stdio: "inherit", env: { ...process.env, CI: process.env.CI ?? "1" } });
child.on("exit", (code) => process.exit(code ?? 0));
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
