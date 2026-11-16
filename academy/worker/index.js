// exergy-academy Worker: serves academy/dist and the live lab endpoints under /api/.
// Static files never reach this code; [assets] answers them first (see run_worker_first).

import { aeSql, summarizeTelemetry, telemetryQueries } from "./telemetry.js";

const JSON_HEADERS = { "Content-Type": "application/json; charset=utf-8" };

export function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data, null, 2), { status, headers: { ...JSON_HEADERS, "Cache-Control": "no-store", ...headers } });
}

export function isLocal(env) {
  return String(env.DEPLOYMENT ?? "local") !== "production";
}

function clientKey(request) {
  return request.headers.get("CF-Connecting-IP") ?? "local";
}

// The cf object in `wrangler dev` is a Miniflare placeholder, so it is labeled simulated there.
export function echo(request, env, receivedAt) {
  const cf = request.cf ?? {};
  const local = isLocal(env);
  return {
    kind: local ? "simulated" : "real",
    source: local ? "wrangler dev (request.cf is Miniflare's placeholder object)" : "request.cf on the exergy-academy Worker",
    collected_at: new Date(receivedAt).toISOString(),
    edge: {
      colo: cf.colo ?? null,
      country: cf.country ?? null,
      asn: cf.asn ?? null,
      http_protocol: cf.httpProtocol ?? null,
      tls_version: cf.tlsVersion ?? null,
      client_tcp_rtt_ms: cf.clientTcpRtt ?? null,
    },
    request: {
      method: request.method,
      path: new URL(request.url).pathname,
      ray: request.headers.get("CF-Ray"),
      user_agent: request.headers.get("User-Agent"),
    },
  };
}

async function cacheDemo(request, ctx) {
  const url = new URL(request.url);
  const key = (url.searchParams.get("key") || "default").replace(/[^\w-]/g, "").slice(0, 32) || "default";
  const ttl = Math.min(300, Math.max(5, Number(url.searchParams.get("ttl")) || 30));
  const cacheUrl = new URL(`/api/lab/cache?key=${key}`, url.origin);
  const cache = caches.default;
  const t0 = Date.now();
  const hit = await cache.match(cacheUrl);
  const lookup = Date.now() - t0;
  if (hit) {
    const response = new Response(hit.body, hit);
    response.headers.set("X-Academy-Cache", "HIT");
    response.headers.set("Server-Timing", `cache;desc="HIT";dur=${lookup}`);
    return response;
  }
  const body = { key, ttl, generated_at: new Date().toISOString(), note: "Generated on a cache MISS. Call again within the TTL to get a HIT." };
  const response = json(body, 200, { "Cache-Control": `public, max-age=${ttl}`, "X-Academy-Cache": "MISS", "Server-Timing": `cache;desc="MISS";dur=${lookup}` });
  ctx.waitUntil(cache.put(cacheUrl, response.clone()));
  return response;
}

async function telemetry(env, ctx, request) {
  const missing = ["ANALYTICS_API_TOKEN", "CF_ACCOUNT_ID"].filter((name) => !env[name]);
  if (missing.length) {
    return json({
      kind: "unconfigured",
      missing,
      steps: [
        "Create an API token with Account → Account Analytics → Read.",
        "npx wrangler secret put ANALYTICS_API_TOKEN (from academy/)",
        "Set CF_ACCOUNT_ID under [vars] in academy/wrangler.toml, or as a secret, and redeploy.",
        "Reload this page: the chart switches to REAL TELEMETRY with the query time as its timestamp.",
      ],
    });
  }
  const cacheKey = new Request(new URL("/api/telemetry", request.url).toString());
  const cached = await caches.default.match(cacheKey);
  if (cached) return cached;
  try {
    const results = {};
    for (const [name, sql] of Object.entries(telemetryQueries)) {
      results[name] = await aeSql(env, sql);
    }
    const response = json(summarizeTelemetry(results, new Date()), 200, { "Cache-Control": "public, max-age=60" });
    ctx.waitUntil(caches.default.put(cacheKey, response.clone()));
    return response;
  } catch (error) {
    console.error(JSON.stringify({ event: "telemetry_error", message: String(error?.message ?? error) }));
    return json({ kind: "error", message: "Analytics Engine query failed. Check the token permission and account id." }, 502);
  }
}

export default {
  async fetch(request, env, ctx) {
    const started = Date.now();
    const url = new URL(request.url);
    let response;
    let limited = false;

    if (url.pathname.startsWith("/api/lab/") && env.LAB_LIMITER) {
      const { success } = await env.LAB_LIMITER.limit({ key: `${clientKey(request)}:${url.pathname}` });
      if (!success) {
        limited = true;
        response = json({ error: "rate_limited", limit: "20 requests per 60 s per client and path (LAB_LIMITER)" }, 429, { "Retry-After": "60" });
      }
    }

    if (!response) {
      switch (url.pathname) {
        case "/api/health":
          response = json({ ok: true, worker: "exergy-academy", deployment: env.DEPLOYMENT ?? "local", commit: env.COMMIT_SHA ?? null, time: new Date().toISOString() });
          break;
        case "/api/lab/echo":
          response = json(echo(request, env, started));
          break;
        case "/api/lab/cache":
          response = await cacheDemo(request, ctx);
          break;
        case "/api/telemetry":
          response = await telemetry(env, ctx, request);
          break;
        default:
          response = url.pathname.startsWith("/api/") ? json({ error: "not_found" }, 404) : await env.ASSETS.fetch(request);
      }
    }

    const duration = Date.now() - started;
    if (url.pathname.startsWith("/api/")) {
      env.LAB_EVENTS?.writeDataPoint({
        blobs: [url.pathname, String(response.status), request.cf?.colo ?? "local", limited ? "limited" : "ok"],
        doubles: [duration, 1],
        indexes: [url.pathname],
      });
      console.log(JSON.stringify({ event: "api", path: url.pathname, status: response.status, duration_ms: duration, limited, colo: request.cf?.colo ?? null }));
    }
    return response;
  },
};
