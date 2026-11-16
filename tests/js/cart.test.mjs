import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { test } from "node:test";

import { applySale, publicStock, toCents, validateCart } from "../../worker/cart.js";
import { checkoutSessionParams, signPayload, verifyStripeSignature } from "../../worker/stripe.js";

const require = createRequire(import.meta.url);
const client = require("../../catalog/templates/cart.js");

const doc = {
  version: 1,
  currency: "USD",
  shipping: "6.35",
  parts: [
    { id: "MM177-4.32K", series: "MM177", part_number: "MM177-4.32K", value: "4.32 kΩ", qty: 63, price: "10.00" },
    { id: "MS151-33.2K", series: "MS151", part_number: "MS151-33.2K", value: "33.2 kΩ", qty: 2, price: "10.00" },
    { id: "MS176-10K", series: "MS176", part_number: "MS176-10K", value: "10 kΩ", qty: 0, price: "10.00" },
  ],
  applied_sessions: ["cs_old"],
};

test("client cart total adds flat shipping once per order", () => {
  const parts = { "MM177-4.32K": { price: "10.00", qty: 63 }, "MS151-33.2K": { price: "10.00", qty: 2 } };
  const totals = client.cartTotals({ "MM177-4.32K": 3, "MS151-33.2K": 1 }, parts, "6.35");
  assert.equal(totals.subtotalCents, 4000);
  assert.equal(totals.shippingCents, 635);
  assert.equal(totals.totalCents, 4635);
  assert.equal(totals.count, 4);
});

test("client cart caps quantity at stock and drops unknown or sold-out parts", () => {
  const parts = { "MS151-33.2K": { price: "10.00", qty: 2 }, "MS176-10K": { price: "10.00", qty: 0 } };
  const totals = client.cartTotals({ "MS151-33.2K": 9, "MS176-10K": 1, "NOPE-1": 2 }, parts, "6.35");
  assert.deepEqual(totals.lines.map((line) => [line.id, line.qty]), [["MS151-33.2K", 2]]);
  assert.equal(totals.totalCents, 2635);
});

test("empty client cart has no shipping", () => {
  assert.equal(client.cartTotals({}, {}, "6.35").totalCents, 0);
  assert.equal(client.clampQty(0, 5), 1);
  assert.equal(client.clampQty(12, 5), 5);
});

test("server validation uses stock prices and merges duplicate lines", () => {
  const result = validateCart(
    [{ id: "MM177-4.32K", qty: 2, price: "0.01" }, { id: "MM177-4.32K", qty: 1 }],
    doc,
  );
  assert.equal(result.ok, true);
  assert.deepEqual(result.lines.map((line) => [line.id, line.qty, line.unitCents]), [["MM177-4.32K", 3, 1000]]);
  assert.equal(result.subtotalCents, 3000);
  assert.equal(result.shippingCents, 635);
  assert.equal(result.totalCents, 3635);
});

test("server validation rejects bad carts", () => {
  assert.equal(validateCart([], doc).errors[0].code, "empty_cart");
  assert.equal(validateCart("nope", doc).ok, false);
  assert.equal(validateCart([{ id: "MM177-4.32K", qty: 0 }], doc).errors[0].code, "bad_item");
  assert.equal(validateCart([{ id: "MM177-4.32K", qty: 1.5 }], doc).errors[0].code, "bad_item");
  assert.equal(validateCart([{ id: "XX1-1K", qty: 1 }], doc).errors[0].code, "unknown_part");
  assert.equal(validateCart([{ id: "MS176-10K", qty: 1 }], doc).errors[0].code, "out_of_stock");
  const short = validateCart([{ id: "MS151-33.2K", qty: 3 }], doc);
  assert.equal(short.errors[0].code, "insufficient_stock");
  assert.equal(short.errors[0].available, 2);
});

test("server validation caps the number of lines", () => {
  const big = { ...doc, parts: Array.from({ length: 101 }, (_, i) => ({ id: `P${i}`, qty: 5, price: "1.00" })) };
  const items = big.parts.map((part) => ({ id: part.id, qty: 1 }));
  assert.equal(validateCart(items, big).errors[0].code, "too_many_lines");
});

test("applying a sale decrements stock once per session", () => {
  const first = applySale(doc, [{ id: "MS151-33.2K", qty: 2 }], "cs_1");
  assert.equal(first.changed, true);
  assert.equal(first.doc.parts.find((p) => p.id === "MS151-33.2K").qty, 0);
  assert.equal(doc.parts.find((p) => p.id === "MS151-33.2K").qty, 2);
  const again = applySale(first.doc, [{ id: "MS151-33.2K", qty: 2 }], "cs_1");
  assert.equal(again.changed, false);
  const oversold = applySale(first.doc, [{ id: "MS151-33.2K", qty: 1 }], "cs_2");
  assert.deepEqual(oversold.oversold, [{ id: "MS151-33.2K", qty: 1, available: 0 }]);
  assert.equal(oversold.doc.parts.find((p) => p.id === "MS151-33.2K").qty, 0);
  assert.equal("applied_sessions" in publicStock(first.doc), false);
});

test("checkout session params carry server prices, US shipping, and flat rate", () => {
  const cart = validateCart([{ id: "MM177-4.32K", qty: 2 }], doc);
  const params = checkoutSessionParams(cart, "https://example.test");
  assert.equal(params["line_items[0][price_data][unit_amount]"], 1000);
  assert.equal(params["line_items[0][quantity]"], 2);
  assert.equal(params["line_items[0][price_data][product_data][metadata][part_id]"], "MM177-4.32K");
  assert.equal(params["shipping_address_collection[allowed_countries][0]"], "US");
  assert.equal(params["shipping_options[0][shipping_rate_data][fixed_amount][amount]"], 635);
  assert.match(params.success_url, /\/checkout\/success\/\?session_id=\{CHECKOUT_SESSION_ID\}$/);
});

test("Stripe signature verification accepts valid and rejects tampered or stale payloads", async () => {
  const secret = "whsec_test";
  const payload = JSON.stringify({ type: "checkout.session.completed" });
  const t = 1_800_000_000;
  const sig = await signPayload(payload, secret, t);
  const header = `t=${t},v1=${sig}`;
  assert.equal(await verifyStripeSignature(payload, header, secret, { nowSec: t + 10 }), true);
  assert.equal(await verifyStripeSignature(payload + " ", header, secret, { nowSec: t + 10 }), false);
  assert.equal(await verifyStripeSignature(payload, header, "whsec_other", { nowSec: t + 10 }), false);
  assert.equal(await verifyStripeSignature(payload, header, secret, { nowSec: t + 1000 }), false);
  assert.equal(await verifyStripeSignature(payload, "", secret), false);
});

test("money parsing rejects malformed amounts", () => {
  assert.equal(toCents("6.35"), 635);
  assert.equal(toCents("10"), 1000);
  assert.throws(() => toCents("-1"));
  assert.equal(client.toCents("abc"), null);
});
