import { applySale } from "../../worker/cart.js";
import { STOCK_KEY, json, notifyOrder, readStock, stockCacheKey } from "../../worker/env.js";
import { sessionLineItems, verifyStripeSignature } from "../../worker/stripe.js";

export async function onRequestPost({ request, env }) {
  const payload = await request.text();
  const valid = await verifyStripeSignature(payload, request.headers.get("Stripe-Signature"), env.STRIPE_WEBHOOK_SECRET);
  if (!valid) return json({ error: "bad_signature" }, 400);

  const event = JSON.parse(payload);
  if (event.type !== "checkout.session.completed") return json({ received: true, ignored: event.type });

  const session = event.data?.object ?? {};
  if (session.payment_status !== "paid") return json({ received: true, ignored: `payment_status ${session.payment_status}` });

  const sold = (await sessionLineItems(env, session.id)).filter((item) => item.id && item.qty > 0);
  const doc = await readStock(env);
  if (!doc) {
    console.error("paid order but stock document is missing", session.id);
    return json({ error: "stock_unavailable" }, 500);
  }

  // Single-key read-modify-write. KV has no transactions, so two webhooks at once can race.
  const result = applySale(doc, sold, session.id);
  if (result.changed) {
    await env.STOCK.put(STOCK_KEY, JSON.stringify(result.doc));
    await caches.default.delete(stockCacheKey(request));
  }
  if (result.oversold.length) console.error("oversold", session.id, JSON.stringify(result.oversold));

  await notifyOrder(env, {
    session: session.id,
    email: session.customer_details?.email ?? null,
    total: session.amount_total,
    items: sold,
    oversold: result.oversold,
    duplicate: !result.changed,
  });
  return json({ received: true });
}
