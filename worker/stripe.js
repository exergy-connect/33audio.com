// Minimal Stripe REST calls over fetch, so the Worker needs no SDK.

const API = "https://api.stripe.com/v1";

function form(params) {
  const body = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) body.append(key, String(value));
  }
  return body;
}

async function stripeRequest(env, method, path, params) {
  const response = await fetch(API + path, {
    method,
    headers: {
      Authorization: `Bearer ${env.STRIPE_SECRET_KEY}`,
      ...(params ? { "Content-Type": "application/x-www-form-urlencoded" } : {}),
    },
    body: params ? form(params) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = data?.error?.message || `Stripe request failed (${response.status})`;
    throw new Error(message);
  }
  return data;
}

export function checkoutSessionParams(cart, origin) {
  const params = {
    mode: "payment",
    success_url: `${origin}/checkout/success/?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${origin}/checkout/cancel/`,
    "shipping_address_collection[allowed_countries][0]": "US",
    "shipping_options[0][shipping_rate_data][type]": "fixed_amount",
    "shipping_options[0][shipping_rate_data][display_name]": "Flat shipping, any quantity",
    "shipping_options[0][shipping_rate_data][fixed_amount][amount]": cart.shippingCents,
    "shipping_options[0][shipping_rate_data][fixed_amount][currency]": "usd",
    "metadata[source]": "33audio-catalog",
  };
  cart.lines.forEach((line, index) => {
    const prefix = `line_items[${index}]`;
    params[`${prefix}[quantity]`] = line.qty;
    params[`${prefix}[price_data][currency]`] = "usd";
    params[`${prefix}[price_data][unit_amount]`] = line.unitCents;
    params[`${prefix}[price_data][product_data][name]`] = line.name;
    params[`${prefix}[price_data][product_data][metadata][part_id]`] = line.id;
  });
  return params;
}

export async function createCheckoutSession(env, cart, origin) {
  return stripeRequest(env, "POST", "/checkout/sessions", checkoutSessionParams(cart, origin));
}

export async function sessionLineItems(env, sessionId) {
  const path = `/checkout/sessions/${encodeURIComponent(sessionId)}/line_items?limit=100&expand[]=data.price.product`;
  const data = await stripeRequest(env, "GET", path);
  return (data.data ?? []).map((item) => ({
    id: item?.price?.product?.metadata?.part_id ?? "",
    qty: item.quantity ?? 0,
  }));
}

const encoder = new TextEncoder();

function hex(buffer) {
  return [...new Uint8Array(buffer)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function safeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export async function signPayload(payload, secret, timestamp) {
  const key = await crypto.subtle.importKey("raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return hex(await crypto.subtle.sign("HMAC", key, encoder.encode(`${timestamp}.${payload}`)));
}

// Implements Stripe's documented v1 signature scheme for the Stripe-Signature header.
export async function verifyStripeSignature(payload, header, secret, { toleranceSec = 300, nowSec } = {}) {
  if (!header || !secret) return false;
  let timestamp = "";
  const signatures = [];
  for (const piece of header.split(",")) {
    const [key, value] = piece.split("=", 2).map((part) => part?.trim());
    if (key === "t") timestamp = value;
    if (key === "v1" && value) signatures.push(value);
  }
  if (!/^\d+$/.test(timestamp) || signatures.length === 0) return false;
  const now = nowSec ?? Math.floor(Date.now() / 1000);
  if (Math.abs(now - Number(timestamp)) > toleranceSec) return false;
  const expected = await signPayload(payload, secret, timestamp);
  return signatures.some((signature) => safeEqual(signature, expected));
}
