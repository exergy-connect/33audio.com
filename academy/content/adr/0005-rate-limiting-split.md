---
title: Zone rate-limiting rules for the shop, the binding for the Academy
status: Accepted
date: 2026-11-16
summary: Zone rate-limiting rules for the shop, the binding for the Academy.
---

## Context

`/api/search` can call Workers AI on every request, so it needs a rate limit. The Workers Rate Limiting binding is not supported for Pages projects (Wrangler 4.162.0's Pages validator does not accept `ratelimits`).

## Decision

Protect the shop with a zone **rate-limiting rule** in `security/waf/rules.json` (10 requests per 10 s per IP and data center, which fits the Free plan). Use the **binding** (`LAB_LIMITER`, 20 per 60 s) in the Academy Worker, keyed by client IP and path.

## Consequences

- The shop's limit needs the custom domain on a Cloudflare zone; on `*.pages.dev` alone it is not enforced. The Cache API still absorbs repeated AI questions.
- The binding works locally, so the security lab can show real 429s without an account.

## Alternatives

- Count requests in KV or a Durable Object from the Function. More code and cost than a zone rule.
