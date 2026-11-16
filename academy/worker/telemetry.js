// Reads Workers Analytics Engine through the SQL API. Shared by the Worker and tools/telemetry.mjs.
// SUM(_sample_interval) counts events correctly when Analytics Engine samples at high volume.

export const telemetryQueries = {
  lab_requests: `SELECT blob1 AS path, blob2 AS status, SUM(_sample_interval) AS requests, quantileWeighted(0.5)(double1, _sample_interval) AS p50_ms
FROM academy_lab WHERE timestamp > NOW() - INTERVAL '1' DAY
GROUP BY path, status ORDER BY requests DESC LIMIT 20`,
  search_modes: `SELECT blob1 AS mode, SUM(_sample_interval) AS searches, quantileWeighted(0.5)(double1, _sample_interval) AS p50_ms, quantileWeighted(0.95)(double1, _sample_interval) AS p95_ms
FROM caddock_search WHERE timestamp > NOW() - INTERVAL '1' DAY
GROUP BY mode ORDER BY searches DESC`,
};

export async function aeSql(env, sql, fetchImpl = fetch) {
  const response = await fetchImpl(`https://api.cloudflare.com/client/v4/accounts/${env.CF_ACCOUNT_ID}/analytics_engine/sql`, {
    method: "POST",
    headers: { Authorization: `Bearer ${env.ANALYTICS_API_TOKEN}` },
    body: sql,
  });
  const text = await response.text();
  if (!response.ok) throw new Error(`Analytics Engine SQL API ${response.status}: ${text.slice(0, 200)}`);
  return JSON.parse(text).data ?? [];
}

// Turns SQL rows into the dataset shape the Academy charts use.
export function summarizeTelemetry(results, now) {
  const num = (v) => (v == null ? null : Math.round(Number(v) * 10) / 10);
  return {
    kind: "real",
    source: "Workers Analytics Engine SQL API (datasets academy_lab, caddock_search), last 24 h",
    collected_at: now.toISOString(),
    lab_requests: (results.lab_requests ?? []).map((r) => ({ label: `${r.path} ${r.status}`, requests: num(r.requests), p50_ms: num(r.p50_ms) })),
    search_modes: (results.search_modes ?? []).map((r) => ({ label: r.mode, searches: num(r.searches), p50_ms: num(r.p50_ms), p95_ms: num(r.p95_ms) })),
  };
}
