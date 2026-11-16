---
title: Bindings, variables, and secrets
summary: Every binding for the shop and the Academy.
---

## Shop: Pages project `caddock-33audio`

| Name | Kind | Where | Purpose |
| --- | --- | --- | --- |
| `STOCK` | Workers KV | `wrangler.toml`, top level and `[env.production]` | One key, `stock`, with the stock document |
| `SEARCH_EVENTS` | Analytics Engine, dataset `caddock_search` | Both | One data point per search |
| `AI` | Workers AI | `[env.production.ai]` only | Intent extraction for `/api/search` |
| `ASSETS` | Pages assets | Automatic | Lets `/api/search` read `catalog.json` |
| `CHECKOUT_ENABLED` | Variable | `[vars]` and `[env.production.vars]` | `"false"` until Stripe is live |
| `SEARCH_MODEL` | Variable (optional) | Pages settings | Overrides the Workers AI model |
| `STRIPE_SECRET_KEY` | Secret | `wrangler pages secret put` | Creates Checkout Sessions, reads line items |
| `STRIPE_WEBHOOK_SECRET` | Secret | `wrangler pages secret put`; `.dev.vars` locally | Verifies `Stripe-Signature` |

::: embed wrangler.toml "[env.production.vars]" "binding = \"AI\""

## Academy: Worker `exergy-academy`

| Name | Kind | Where | Purpose |
| --- | --- | --- | --- |
| `ASSETS` | Static assets from `academy/dist` | `[assets]` | Serves the site; `/api/*` runs the Worker first |
| `LAB_LIMITER` | Rate Limiting, 20 per 60 s | `[[ratelimits]]` | Limits `/api/lab/*` per client and path |
| `LAB_EVENTS` | Analytics Engine, dataset `academy_lab` | `[[analytics_engine_datasets]]` | One data point per API request |
| `DEPLOYMENT` | Variable | `[vars]` (`local`), `--var DEPLOYMENT:production` on deploy | Labels `request.cf` data real or simulated |
| `COMMIT_SHA` | Variable | `--var` on deploy | Reported by `/api/health` |
| `CF_ACCOUNT_ID` | Variable or secret | `[vars]` or `wrangler secret put` | Account for the Analytics Engine SQL API |
| `ANALYTICS_API_TOKEN` | Secret | `wrangler secret put` | Account Analytics Read token for `/api/telemetry` |

::: embed academy/wrangler.toml

## GitHub repository secrets

| Secret | Used by | Token permissions |
| --- | --- | --- |
| `CLOUDFLARE_API_TOKEN` | `academy.yml` deploy, `shop-deploy.yml`, `refresh.yml` KV seed | Workers Scripts Edit, Cloudflare Pages Edit, Workers KV Storage Edit, Account Analytics Read |
| `CLOUDFLARE_ACCOUNT_ID` | Same | – |
| `ANALYTICS_API_TOKEN` | `academy.yml` telemetry step (optional) | Account Analytics Read |
| `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET` | `refresh.yml` | – |
