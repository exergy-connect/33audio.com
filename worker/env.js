export const STOCK_KEY = "stock";

export const DEMO_MESSAGE = "Checkout is a demo, not yet active. Nothing will be charged.";

export function checkoutEnabled(env) {
  return String(env.CHECKOUT_ENABLED ?? "false").trim().toLowerCase() === "true";
}

export function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...headers },
  });
}

// Workers clocks only advance across I/O, so these durations measure awaited I/O such as KV and cache calls.
export function serverTiming(entries) {
  return entries
    .map(([name, dur, desc]) => `${name}${desc ? `;desc="${String(desc).replace(/"/g, "'")}"` : ""};dur=${Math.max(0, Number(dur) || 0)}`)
    .join(", ");
}

export async function readStock(env) {
  if (!env.STOCK) return null;
  return env.STOCK.get(STOCK_KEY, "json");
}

export function stockCacheKey(request) {
  return new Request(new URL("/api/stock", request.url).toString(), { method: "GET" });
}

// TODO: send Mark an order email once an email service is chosen
// (for example Cloudflare Email Routing send_email binding, Resend, or Postmark).
export async function notifyOrder(env, order) {
  console.log("order paid", JSON.stringify(order));
}
