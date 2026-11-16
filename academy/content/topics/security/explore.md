---
title: Security at the edge · Explore
summary: DDoS protection, WAF custom rules, rate limiting with zone rules and the Workers binding, bot management, and how each one applies to the 33audio shop.
---

## Layers, in the order traffic meets them

::: diagram security-layers

1. **DDoS protection** is always on and unmetered, at the network layer and for HTTP. There is nothing to deploy. The HTTP DDoS managed ruleset can be tuned (sensitivity and action) if it ever flags legitimate traffic, but the default is the right starting point.
2. **WAF custom rules** run your own expressions on every request.
3. **Rate-limiting rules** count requests per client and data center, and block or challenge above a threshold.
4. **Bot management** scores automation. Bot Fight Mode is free, Super Bot Fight Mode is on Pro and Business, and per-request bot scores (`cf.bot_management.score`) need Enterprise Bot Management.
5. **Application controls** in the code: Stripe signature checks, server-side cart validation, the checkout feature flag, and the Academy's Rate Limiting binding.

## WAF custom rules for this shop

Every rule matches something specific about this application. The shop is static plus four API routes, so anything else that looks like an application endpoint is a scanner:

::: embed security/waf/rules.json "block_exploit_probes" "\"enabled\": true"

The webhook only ever receives POSTs from Stripe, with a signature header. Everything else is noise, so it never reaches the Function:

::: embed security/waf/rules.json "webhook_post_only" "\"enabled\": true"

Orders ship to the USA only, so checkout attempts from other countries get a managed challenge instead of a block. A traveler can still pass it:

::: embed security/waf/rules.json "checkout_outside_us" "\"enabled\": true"

::: pending 03-filter-waf A lab.net filter node would let these rules be checked in simulation before they are applied to a zone.

The rule that uses bot scores ships disabled, with a note, because it needs Enterprise Bot Management. Committing it disabled documents the intent without pretending the plan has the feature.

## Rate limiting: two mechanisms

Pages Functions cannot use the Workers Rate Limiting binding. Wrangler 4.162.0's Pages configuration validator lists the supported fields, and `ratelimits` is not among them ([ADR 0005](/reference/adr/0005-rate-limiting-split/)). So the shop uses a **zone rate-limiting rule**, and the Academy's own Worker uses the **binding**.

The zone rule protects `/api/search`, the one route that spends money on every call. It fits the Free plan's limits (10-second period and timeout):

::: embed security/waf/rules.json "search_rate_limit" "\"enabled\": true"

The Academy Worker limits its live lab endpoints in code. The binding counts per key in the data center, so the key combines the client IP and the path:

::: embed academy/worker/index.js "if (url.pathname.startsWith(\"/api/lab/\") && env.LAB_LIMITER)"

::: embed academy/wrangler.toml "[[ratelimits]]"

::: pending 06-rate-limit A lab.net rate-limit node would show where in the path the limit applies and how it keys sources.

| | Zone rate-limiting rule | Workers Rate Limiting binding |
| --- | --- | --- |
| Runs | Before the Worker or Function | Inside the Worker, when `limit()` is called |
| Key | Rule characteristics (IP, colo, headers, and more by plan) | Any string you build |
| Works on Pages Functions | Yes | No |
| Works in `wrangler dev` | No | Yes, Miniflare enforces it |
| Counts | Per data center | Per data center, eventually consistent |
| Best for | Blunt per-IP floods, any origin | Per-user or per-feature limits in code |

## Applying rules as code

`security/waf/apply.mjs` validates `rules.json` and replaces each phase entrypoint through the Rulesets API. Without `--apply` it only prints what it would send:

::: embed security/waf/apply.mjs "export function requests"

A dashboard edit is quicker once, but it leaves no review, no history, and no way to rebuild the zone. Terraform would also work. A 100-line script with no state file was enough for one zone ([ADR 0006](/reference/adr/0006-edge-config-as-code/)).

## Bots and AI crawlers

The shop wants AI crawlers (see [Product discovery](/explore/discovery/)), so the first custom rule skips the rest for verified AI crawlers reading discovery files. Bot Fight Mode can still be turned on: verified bots are exempt. The trade-off is explicit: content is open to crawlers in exchange for being cited.

## Testing ethically

::: warn Only test what you own
Send test traffic only to `localhost` or to a deployment you own. `academy/tools/loadtest.mjs` refuses any other host unless you name it with `--confirm-own`, and it caps the rate at 20 requests per second for 30 seconds. Never point load tools at the live 33audio shop or anyone else's site, and never try to test DDoS protection with real attack traffic.
:::

::: pending 07-traffic-source A seeded traffic source in lab.net would let the Academy show DDoS and bot mitigation on a model instead of with real traffic.

## Measured

::: chart ratelimit-burst

::: chart waf-events
