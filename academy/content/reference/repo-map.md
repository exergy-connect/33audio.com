---
title: Repository map
summary: Every file the Academy teaches from.
---

Links open the file on GitHub at the commit this site was built from.

## The shop

| Path | Role |
| --- | --- |
| [wrangler.toml](repo:wrangler.toml) | Pages project `caddock-33audio`: KV, Analytics Engine, production-only Workers AI |
| [functions/api/](repo:functions/api/) | Pages Functions: `stock.js`, `checkout.js`, `stripe-webhook.js`, `search.js` |
| [worker/cart.js](repo:worker/cart.js) | Server-side cart validation and idempotent stock decrement |
| [worker/stripe.js](repo:worker/stripe.js) | Stripe REST calls and webhook signature verification over Web Crypto |
| [worker/search.js](repo:worker/search.js) | Natural-language search: Workers AI intent, keyword parser, ranking |
| [worker/env.js](repo:worker/env.js) | KV access, JSON responses, `Server-Timing`, cache keys |
| [catalog/](repo:catalog/) | Python generator: parse the listing, sync eBay, build `docs/`, stock document, schema |
| [catalog/templates/](repo:catalog/templates/) | Front-end scripts and CSS copied into `docs/` (cart, search, ask) |
| [data/](repo:data/) | `catalog.json`, `site.json`, `stock.json` |
| [docs/](repo:docs/) | Generated static site, committed by the refresh workflow |
| [model/](repo:model/) | YANG models of the catalog, turned into `docs/schema/` by xYang |

## Edge configuration

| Path | Role |
| --- | --- |
| [security/waf/rules.json](repo:security/waf/rules.json) | WAF custom rules and rate-limiting rules for the shop's zone |
| [delivery/cache-rules.json](repo:delivery/cache-rules.json) | Cache rules and Tiered Cache settings |
| [security/waf/apply.mjs](repo:security/waf/apply.mjs) | Validate, dry-run, and apply either file through the Rulesets API |
| [observability/queries/](repo:observability/queries/) | Analytics Engine SQL and GraphQL Analytics queries |
| [network/labnet/](repo:network/labnet/) | lab.net topologies for the request-path labs |
| [network/labnet/proposals/](repo:network/labnet/proposals/) | Drafted lab.net feature requests the Academy depends on |

## The Academy

| Path | Role |
| --- | --- |
| [academy/build.py](repo:academy/build.py) | Static generator: Markdown, embeds, diagrams, charts, validation |
| [academy/content/](repo:academy/content/) | Lessons, ADRs, reference pages, and `site.json` |
| [academy/data/simulated/](repo:academy/data/simulated/) | Example datasets, each with steps to make it real |
| [academy/worker/](repo:academy/worker/) | The `exergy-academy` Worker: live lab endpoints and `/api/telemetry` |
| [academy/wrangler.toml](repo:academy/wrangler.toml) | Static assets, Rate Limiting binding, Analytics Engine, Workers Logs |
| [academy/tools/](repo:academy/tools/) | `dev-shop`, `lab-check`, `measure`, `loadtest`, `telemetry`, `labnet-path` |
| [academy/data/labnet/](repo:academy/data/labnet/) | Recorded lab.net runs (JSON and PCAPNG) shown on the delivery pages |

## Pipelines and tests

| Path | Role |
| --- | --- |
| [.github/workflows/academy.yml](repo:.github/workflows/academy.yml) | Test, run labs against wrangler dev, measure, deploy the Academy |
| [.github/workflows/shop-deploy.yml](repo:.github/workflows/shop-deploy.yml) | Optional direct-upload deploy of the shop |
| [.github/workflows/refresh.yml](repo:.github/workflows/refresh.yml) | Daily catalog refresh, KV seed, rebuild |
| [.github/workflows/schema.yml](repo:.github/workflows/schema.yml) | Regenerate and check the xYang schema |
| [tests/](repo:tests/) | Python and Node tests for the shop, the Academy, and the tools |
