import { crawlers } from "../../worker/crawlers.js";
export { crawlers };

export async function queryCrawlers(env, fetchImpl = fetch, now = new Date()) {
  const until = now.toISOString();
  const since = new Date(now.getTime() - 86400000).toISOString();
  const host = env.CRAWLER_HOST ?? "33audio-com.pages.dev";
  if (!/^[a-zA-Z0-9.-]+$/.test(host)) throw new Error("Invalid crawler host");
  const sql = `SELECT blob1 AS crawler, blob2 AS surface, SUM(_sample_interval) AS requests
FROM caddock_crawlers
WHERE timestamp >= toDateTime('${since.slice(0, 19).replace("T", " ")}')
  AND timestamp < toDateTime('${until.slice(0, 19).replace("T", " ")}')
  AND blob3 = '${host}'
GROUP BY crawler, surface LIMIT 20`;
  const response = await fetchImpl(`https://api.cloudflare.com/client/v4/accounts/${env.CF_ACCOUNT_ID}/analytics_engine/sql`, {
    method: "POST",
    headers: { Authorization: `Bearer ${env.ANALYTICS_API_TOKEN}` },
    body: sql,
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error("Analytics Engine HTTP error");
  const result = await response.json();
  if (!Array.isArray(result.data)) throw new Error("Invalid analytics result");
  const rows = crawlers.map(label => ({ label, llms: 0, pages: 0 }));
  for (const entry of result.data) {
    const row = rows.find(r => r.label === entry.crawler);
    const count = Number(entry.requests);
    if (!row || !["llms", "pages"].includes(entry.surface) || entry.requests == null || !Number.isFinite(count) || count < 0) throw new Error("Invalid analytics count");
    row[entry.surface] += count;
  }
  return { kind: "real", source: "Workers Analytics Engine · shop Pages Functions · user-agent matches (not verified identities)",
    collected_at: until, since, until, rows,
    description: "Last 24 hours of successful GET/HEAD requests recorded since instrumentation was deployed. Analytics may be delayed and sampled; counts may be estimates. Responses are cached for 60 seconds." };
}

export async function crawlerAnalytics(request, env, ctx, cache = null, fetchImpl = fetch) {
  if (request.method !== "GET") return Response.json({ kind: "error", message: "Use GET." }, { status: 405, headers: { Allow: "GET" } });
  if (!env.CF_ACCOUNT_ID || !env.ANALYTICS_API_TOKEN) return Response.json({ kind: "unconfigured", message: "Live analytics is not configured. Showing the saved chart." }, { headers: { "Cache-Control": "no-store" } });
  cache ??= caches.default;
  const key = new Request(new URL("/api/crawler-analytics", request.url));
  const hit = await cache.match(key);
  if (hit) return hit;
  try {
    const data = await queryCrawlers(env, fetchImpl);
    const response = Response.json(data, { headers: { "Cache-Control": "public, max-age=60" } });
    ctx.waitUntil(cache.put(key, response.clone()));
    return response;
  } catch {
    return Response.json({ kind: "error", message: "Live analytics unavailable. Showing the last available chart. Check token permissions, account ID, and shop dataset binding." }, { status: 502, headers: { "Cache-Control": "no-store" } });
  }
}
