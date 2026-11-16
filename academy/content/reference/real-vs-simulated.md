---
title: Real vs. simulated data
summary: Badge policy.
---

## The rule

Every metric, chart, and lab.net run on this site shows exactly one of two badges:

- <span>**REAL TELEMETRY**</span>, followed by the source (tool and target, or API and dataset), the collection timestamp, and, where it matters, the environment, such as "wrangler pages dev on a GitHub Actions runner".
- **SIMULATED / EXAMPLE DATA**, followed by a "How to switch this to real telemetry" list.

Example numbers are never presented as measurements. Local measurements are real, but they measure the local runtime, and their environment text says so.

## How it is enforced

1. Datasets must declare `kind`. Real ones need `source` and `collected_at`; simulated ones need `make_real`. `academy/charts.py` rejects anything else and the build fails.
2. The renderer always emits the badge in the figure caption, and `validate_site()` fails the build if any chart or lab.net figure lacks one.
3. Real datasets are never committed. They are generated into `academy/data/real/` by `measure.mjs`, `loadtest.mjs`, and `telemetry.mjs`, so a stale measurement cannot linger as if it were current. CI generates them on each run.
4. Live widgets label browser-measured round trips as real, and label `request.cf` values from `wrangler dev` as simulated because Miniflare fills them with placeholders.
5. Request paths come from [lab.net](/reference/labnet/) runs. They are deterministic simulations of topology files in this repository, so they always carry the SIMULATED badge with the lab.net commit and seed, never REAL TELEMETRY.
6. `/api/telemetry` returns `kind: "unconfigured"` with the missing settings instead of numbers when it has no credentials.

## What is real in a CI-built Academy

| Dataset | Real when | Source |
| --- | --- | --- |
| `local-latency` | Always in CI builds | `measure.mjs` against `wrangler pages dev` on the runner |
| `ratelimit-burst` | Always in CI builds | `loadtest.mjs` against the Academy Worker in `wrangler dev` |
| `search-modes`, `lab-requests` | `ANALYTICS_API_TOKEN` and the account id are set and there is traffic | Analytics Engine SQL API |
| All others | When you follow their "switch to real" steps | Zone analytics, GraphQL, lab.net |
