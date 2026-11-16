#!/usr/bin/env node
// Applies a rules file to a zone with the Cloudflare Rulesets API (and zone settings for files that list them).
//   node security/waf/apply.mjs                                   dry run of security/waf/rules.json
//   node security/waf/apply.mjs --file delivery/cache-rules.json  dry run of the cache rules and Tiered Cache
//   node security/waf/apply.mjs --apply                           needs CLOUDFLARE_API_TOKEN and CLOUDFLARE_ZONE_ID
//   node security/waf/apply.mjs --show                            print the zone's current entrypoints
// Token permissions: Zone → WAF → Edit (custom and rate limiting rules), Zone → Cache Rules → Edit,
// Zone → Zone Settings → Edit (Tiered Cache), Zone → Zone → Read.

import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const API = "https://api.cloudflare.com/client/v4";
const ACTIONS = new Set(["block", "managed_challenge", "js_challenge", "challenge", "log", "skip", "set_cache_settings"]);
const here = path.dirname(fileURLToPath(import.meta.url));

export function validate(config) {
  const errors = [];
  for (const [phase, entry] of Object.entries(config.phases ?? {})) {
    const refs = new Set();
    for (const rule of entry.rules ?? []) {
      const where = `${phase}/${rule.ref ?? "?"}`;
      if (!rule.ref) errors.push(`${where}: missing ref`);
      if (refs.has(rule.ref)) errors.push(`${where}: duplicate ref`);
      refs.add(rule.ref);
      if (!rule.expression?.startsWith("(")) errors.push(`${where}: expression should be parenthesized`);
      if (!ACTIONS.has(rule.action)) errors.push(`${where}: unsupported action ${rule.action}`);
      if (phase === "http_ratelimit") {
        const rl = rule.ratelimit;
        if (!rl) errors.push(`${where}: rate limit rule needs ratelimit`);
        else {
          if (!rl.characteristics?.includes("cf.colo.id")) errors.push(`${where}: characteristics must include cf.colo.id`);
          for (const key of ["period", "requests_per_period", "mitigation_timeout"]) {
            if (!Number.isInteger(rl[key]) || rl[key] <= 0) errors.push(`${where}: ratelimit.${key} must be a positive integer`);
          }
        }
      }
      if (["skip", "set_cache_settings"].includes(rule.action) && !rule.action_parameters) errors.push(`${where}: ${rule.action} needs action_parameters`);
    }
  }
  for (const setting of config.settings ?? []) {
    if (!["PATCH", "PUT"].includes(setting.method) || !setting.path?.startsWith("/")) errors.push(`settings: bad entry ${JSON.stringify(setting)}`);
  }
  return errors;
}

export function requests(config, zoneId) {
  const settings = (config.settings ?? []).map((setting) => ({ method: setting.method, url: `${API}/zones/${zoneId}${setting.path}`, body: setting.body }));
  return settings.concat(Object.entries(config.phases ?? {}).map(([phase, entry]) => ({
    method: "PUT",
    url: `${API}/zones/${zoneId}/rulesets/phases/${phase}/entrypoint`,
    body: {
      description: entry.description,
      rules: entry.rules.map(({ ref, description, expression, action, action_parameters, ratelimit, logging, enabled }) => ({
        ref,
        description,
        expression,
        action,
        ...(action_parameters ? { action_parameters } : {}),
        ...(ratelimit ? { ratelimit } : {}),
        ...(logging ? { logging } : {}),
        enabled: enabled !== false,
      })),
    },
  })));
}

export async function send(req, token, fetchImpl = fetch) {
  const response = await fetchImpl(req.url, {
    method: req.method,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: req.body ? JSON.stringify(req.body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.success === false) {
    const message = (data.errors ?? []).map((e) => `${e.code}: ${e.message}`).join("; ") || `HTTP ${response.status}`;
    throw new Error(`${req.method} ${req.url} failed: ${message}`);
  }
  return data.result;
}

async function main() {
  const argv = process.argv.slice(2);
  const fileIndex = argv.indexOf("--file");
  const file = fileIndex >= 0 ? path.resolve(argv[fileIndex + 1]) : path.join(here, "rules.json");
  const config = JSON.parse(await readFile(file, "utf8"));
  const errors = validate(config);
  if (errors.length) {
    console.error(errors.join("\n"));
    process.exit(1);
  }
  const zoneId = process.env.CLOUDFLARE_ZONE_ID ?? "<CLOUDFLARE_ZONE_ID>";
  const token = process.env.CLOUDFLARE_API_TOKEN;
  if (argv.includes("--show")) {
    if (!token || !process.env.CLOUDFLARE_ZONE_ID) throw new Error("--show needs CLOUDFLARE_API_TOKEN and CLOUDFLARE_ZONE_ID");
    for (const phase of Object.keys(config.phases ?? {})) {
      const result = await send({ method: "GET", url: `${API}/zones/${zoneId}/rulesets/phases/${phase}/entrypoint` }, token).catch((e) => ({ error: e.message }));
      console.log(JSON.stringify({ phase, result }, null, 2));
    }
    return;
  }
  const plan = requests(config, zoneId);
  if (!argv.includes("--apply")) {
    for (const req of plan) console.log(`${req.method} ${req.url}\n${JSON.stringify(req.body, null, 2)}\n`);
    const rules = plan.flatMap((r) => r.body?.rules ?? []);
    const enabled = rules.filter((r) => r.enabled).length;
    console.log(`Dry run of ${path.relative(process.cwd(), file)}: ${plan.length} requests, ${enabled} of ${rules.length} rules enabled. Nothing was sent. Re-run with --apply to change the zone.`);
    return;
  }
  if (!token || !process.env.CLOUDFLARE_ZONE_ID) {
    console.error("--apply needs CLOUDFLARE_API_TOKEN and CLOUDFLARE_ZONE_ID");
    process.exit(2);
  }
  for (const req of plan) {
    const result = await send(req, token);
    const what = req.url.includes("/phases/") ? req.url.split("/phases/")[1] : req.url.split(`/zones/${zoneId}`)[1];
    console.log(`applied ${req.method} ${what}${result?.id ? ` → ${result.id}${result.version ? ` version ${result.version}` : ""}` : ""}`);
  }
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) await main();
