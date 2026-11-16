import { publicStock } from "../../worker/cart.js";
import { json, readStock, stockCacheKey } from "../../worker/env.js";

export async function onRequestGet({ request, env, waitUntil }) {
  const cache = caches.default;
  const key = stockCacheKey(request);
  const cached = await cache.match(key);
  if (cached) return cached;

  const doc = await readStock(env);
  if (!doc) return json({ error: "stock_unavailable" }, 503);

  const response = json(publicStock(doc), 200, { "Cache-Control": "public, max-age=30" });
  waitUntil(cache.put(key, response.clone()));
  return response;
}
