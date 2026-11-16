import { validateCart } from "../../worker/cart.js";
import { DEMO_MESSAGE, checkoutEnabled, json, readStock } from "../../worker/env.js";
import { createCheckoutSession } from "../../worker/stripe.js";

export async function onRequestGet({ env }) {
  const enabled = checkoutEnabled(env);
  return json({ enabled, message: enabled ? "Checkout is active." : DEMO_MESSAGE });
}

export async function onRequestPost({ request, env }) {
  if (!checkoutEnabled(env)) {
    return json({ enabled: false, error: "checkout_disabled", message: DEMO_MESSAGE }, 503);
  }
  if (!env.STRIPE_SECRET_KEY) {
    return json({ error: "not_configured", message: "Checkout is switched on but STRIPE_SECRET_KEY is not set." }, 500);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: "bad_request", message: "Send JSON like {\"items\":[{\"id\":\"MM177-4.32K\",\"qty\":2}]}." }, 400);
  }

  const doc = await readStock(env);
  if (!doc) return json({ error: "stock_unavailable", message: "Stock is unavailable. Try again shortly." }, 503);

  const cart = validateCart(body?.items, doc);
  if (!cart.ok) {
    return json({ error: "invalid_cart", message: "Some items need attention.", problems: cart.errors }, 409);
  }

  try {
    const origin = new URL(request.url).origin;
    const session = await createCheckoutSession(env, cart, origin);
    return json({ url: session.url });
  } catch (error) {
    console.error("stripe checkout session failed", error);
    return json({ error: "stripe_error", message: "Checkout could not start. Please try again or email mark@33audio.com." }, 502);
  }
}
