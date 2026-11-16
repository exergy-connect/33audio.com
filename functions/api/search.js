import { json, serverTiming } from "../../worker/env.js";
import { MAX_QUERY, normalizeQuery, searchCatalog } from "../../worker/search.js";

const CACHE_SECONDS = 300;
let catalogPromise = null;

async function loadCatalog(env, request) {
  catalogPromise ??= env.ASSETS.fetch(new URL("/catalog.json", request.url)).then((response) => {
    if (!response.ok) throw new Error(`catalog.json returned ${response.status}`);
    return response.json();
  });
  try {
    return await catalogPromise;
  } catch (error) {
    catalogPromise = null;
    throw error;
  }
}

function cacheKey(request, query) {
  const url = new URL("/api/search", request.url);
  url.searchParams.set("q", query.toLowerCase());
  return new Request(url.toString(), { method: "GET" });
}

export async function onRequestGet({ request, env, waitUntil }) {
  const raw = new URL(request.url).searchParams.get("q") ?? "";
  if (raw.length > MAX_QUERY * 2) return json({ error: "query_too_long", max: MAX_QUERY }, 414);
  const query = normalizeQuery(raw);

  const cache = caches.default;
  const key = cacheKey(request, query);
  const t0 = Date.now();
  const hit = query ? await cache.match(key) : null;
  const lookup = Date.now() - t0;
  if (hit) {
    const response = new Response(hit.body, hit);
    response.headers.set("X-Search-Cache", "HIT");
    response.headers.set("Server-Timing", serverTiming([["cache", lookup, "HIT"]]));
    return response;
  }

  let catalog;
  const t1 = Date.now();
  try {
    catalog = await loadCatalog(env, request);
  } catch (error) {
    console.error("search catalog load failed", String(error));
    return json({ error: "catalog_unavailable" }, 503);
  }

  const catalogMs = Date.now() - t1;
  const result = await searchCatalog({ q: query, catalog, env });
  env.SEARCH_EVENTS?.writeDataPoint({
    blobs: [result.mode, result.fallback_reason ? "fallback" : "ok", query.toLowerCase().slice(0, 96)],
    doubles: [result.took_ms, result.results.length],
    indexes: [result.mode],
  });
  console.log(JSON.stringify({ event: "search", mode: result.mode, took_ms: result.took_ms, results: result.results.length, fallback: result.fallback_reason }));

  const cacheable = query && result.mode === "ai";
  const response = json(result, 200, {
    "Cache-Control": cacheable ? `public, max-age=${CACHE_SECONDS}` : "no-store",
    "X-Search-Mode": result.mode,
    "X-Search-Cache": "MISS",
  });
  if (cacheable) waitUntil(cache.put(key, response.clone()));
  response.headers.set("Server-Timing", serverTiming([["cache", lookup, "MISS"], ["catalog", catalogMs, "ASSETS catalog.json"], ["search", result.took_ms, result.mode]]));
  return response;
}
