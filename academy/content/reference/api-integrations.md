---
title: Cloudflare API integrations
summary: Each call this repository makes to Cloudflare, and the permission it needs.
---

| Caller | Call | Permission |
| --- | --- | --- |
| `catalog/stock.py` (`python -m catalog stock --seed`) | `wrangler kv key put stock --namespace-id …` (Workers KV API) | Workers KV Storage: Edit |
| `security/waf/apply.mjs` | `PUT /zones/{zone}/rulesets/phases/http_request_firewall_custom/entrypoint` | Zone WAF: Edit |
| `security/waf/apply.mjs` | `PUT /zones/{zone}/rulesets/phases/http_ratelimit/entrypoint` | Zone WAF: Edit |
| `security/waf/apply.mjs --file delivery/cache-rules.json` | `PUT …/phases/http_request_cache_settings/entrypoint` | Cache Rules: Edit |
| Same | `PATCH /zones/{zone}/argo/tiered_caching`, `PATCH /zones/{zone}/cache/tiered_cache_smart_topology_enable` | Zone Settings: Edit |
| `academy/worker/telemetry.js`, `academy/tools/telemetry.mjs` | `POST /accounts/{account}/analytics_engine/sql` | Account Analytics: Read |
| `academy/worker/crawlers.js` (`GET /api/crawler-analytics`) | `POST /accounts/{account}/analytics_engine/sql`, fixed last-24-hour crawler aggregates, cached 60 s | Account Analytics: Read |
| `observability/queries/*.graphql` | `POST /client/v4/graphql` | Account Analytics: Read, Zone Analytics: Read |
| `academy.yml` deploy | `wrangler deploy` (Workers Scripts and static assets upload) | Workers Scripts: Edit |
| `shop-deploy.yml` | `wrangler pages project create`, `wrangler pages deploy` | Cloudflare Pages: Edit |

## Rulesets API

::: embed security/waf/apply.mjs "export async function send"

## Analytics Engine SQL API

::: embed academy/worker/telemetry.js "export async function aeSql"

Both are plain `fetch` calls with a bearer token. No SDK is involved, so they run unchanged in Node and in a Worker.
