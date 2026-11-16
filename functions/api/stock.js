import { publicStock } from "../../worker/cart.js";
import { json, readStock, serverTiming, stockCacheKey } from "../../worker/env.js";

export async function onRequestGet({ request, env, waitUntil }) {
  const cache = caches.default;
  const key = stockCacheKey(request);
  const t0 = Date.now();
  const cached = await cache.match(key);
  const lookup = Date.now() - t0;
  if (cached) {
    const response = new Response(cached.body, cached);
    response.headers.set("Server-Timing", serverTiming([["cache", lookup, "HIT"]]));
    return response;
  }

  const t1 = Date.now();
  const doc = await readStock(env);
  const kv = Date.now() - t1;
  if (!doc) return json({ error: "stock_unavailable" }, 503);

  const response = json(publicStock(doc), 200, { "Cache-Control": "public, max-age=30" });
  waitUntil(cache.put(key, response.clone()));
  response.headers.set("Server-Timing", serverTiming([["cache", lookup, "MISS"], ["kv", kv, "STOCK get"]]));
  return response;
}
