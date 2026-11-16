---
title: Build and deploy the shop · Explore
summary: How the 33audio shop runs on Cloudflare Pages with Pages Functions, one Workers KV document, the Cache API, Stripe Checkout, and signed webhooks.
---

## What runs where

The shop is a static site plus four small serverless endpoints. `python -m catalog build` writes about a hundred HTML pages into `docs/`. Cloudflare Pages serves those files from its edge cache, and every file under `functions/` becomes a route that runs on Cloudflare's network next to the visitor.

::: diagram shop-architecture

| Route | File | What it does |
| --- | --- | --- |
| `GET /api/stock` | [functions/api/stock.js](repo:functions/api/stock.js) | Returns live quantities from KV, cached for 30 s per data center |
| `GET, POST /api/checkout` | [functions/api/checkout.js](repo:functions/api/checkout.js) | Reports the feature flag, or validates a cart and creates a Stripe Checkout Session |
| `POST /api/stripe-webhook` | [functions/api/stripe-webhook.js](repo:functions/api/stripe-webhook.js) | Verifies Stripe's signature and decrements stock after payment |
| `GET /api/search` | [functions/api/search.js](repo:functions/api/search.js) | Natural-language part search (topic 3) |

Pages Functions use file-based routing: `functions/api/stock.js` exporting `onRequestGet` answers `GET /api/stock`. Shared code lives in `worker/` and is bundled by Wrangler at deploy time.

::: pending 02-http-service lab.net hosts do not serve HTTP yet, so the delivery topic's lab.net labs stop at the anycast address and cannot model the Function and origin hops.

::: pending 04-load-balancer An origin pool behind the edge needs a lab.net load balancer node.

## Configuration is code

`wrangler.toml` is the source of truth for the Pages project: its name, the output directory, the compatibility date, and every binding. When a Pages project has this file, the dashboard's binding settings are read-only, so a pull request is the only way to change them.

::: embed wrangler.toml

Two details matter here. Bindings are not inherited by named environments, so `[env.production]` repeats the KV and Analytics Engine bindings. And the Workers AI binding exists only in production, because Workers AI always runs remotely and a top-level `[ai]` block makes `wrangler pages dev` demand an API token. [ADR 0004](/reference/adr/0004-ai-binding-production-only/) records that choice.

## One KV document for stock

All 85 parts and their quantities live in one KV key, `stock`, as a 12 KB JSON document. The catalog generator builds it:

::: embed catalog/stock.py "def stock_doc"

The Functions read it with a single call:

::: embed worker/env.js "export async function readStock"

Why one document instead of one key per part? A page that shows the whole catalog needs one read, not 85. The document is small, read far more often than written, and changes only when an order is paid or the daily refresh runs. KV is built for exactly that: reads are served from the edge, and writes propagate globally within about a minute. [ADR 0002](/reference/adr/0002-single-kv-stock-document/) covers the alternatives.

## Caching the stock endpoint

KV reads are fast at the edge, but a cached response is faster and costs nothing. `/api/stock` stores its response in the data center's cache for 30 seconds with the Cache API, and reports what happened in a `Server-Timing` header:

::: embed functions/api/stock.js

The webhook deletes that cache entry after a sale, so the data center that processed the order shows the new quantity at once. Other data centers can show the old number for up to 30 seconds, and the server checks stock again before any payment.

## Checkout behind a feature flag

Checkout is off until `CHECKOUT_ENABLED` is `"true"`. While it is off, `GET /api/checkout` says so and `POST` returns `503 checkout_disabled`, so the front end can show a demo state without any Stripe keys.

::: diagram checkout-flow

When it is on, the server never trusts prices or quantities from the browser. It rebuilds the cart from the KV document:

::: embed worker/cart.js "export function validateCart"

## Webhooks: signature and idempotency

Stripe calls `/api/stripe-webhook` after payment. Anyone can send a request to that URL, so the Function verifies the `Stripe-Signature` header with HMAC-SHA256 over the raw body, using the Web Crypto API that Workers provide. No Stripe SDK is needed.

::: embed worker/stripe.js "export async function verifyStripeSignature"

Stripe retries deliveries, so applying a sale must be idempotent. The stock document keeps the last 500 applied Checkout Session ids, and a repeated session changes nothing:

::: embed worker/cart.js "export function applySale"

## Trade-offs

::: warn Read-modify-write on KV can race
KV has no transactions. Two webhooks for different orders that arrive in the same instant can both read the old document, and the second write wins. At this shop's order volume that risk is small, and the oversold check logs any mismatch. If volume grows, move the decrement into a Durable Object (one object serializes writes) or D1 (a SQL `UPDATE … WHERE qty >= ?`).
:::

| Option | Reads | Writes | Fits this shop because | Would switch when |
| --- | --- | --- | --- | --- |
| One KV document (chosen) | One edge read for everything | Last write wins, about 60 s to propagate | Tiny, read-heavy, rare writes | Orders arrive concurrently |
| KV key per part | 85 reads for a catalog page | Smaller conflicts | – | Never, for this catalog size |
| Durable Object | One hop to the object's location | Serialized, strongly consistent | – | Concurrent orders or reservations |
| D1 | SQL query | Transactions | – | Order history or reporting is needed |

## Measured

::: chart local-latency

The chart above is real when CI or you have run `academy/tools/measure.mjs` against `wrangler pages dev`. It measures the local runtime, not Cloudflare's edge, and its badge says so. Edge numbers come from the deployed shop in [Observability](/explore/observability/).
