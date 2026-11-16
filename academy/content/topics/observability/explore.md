---
title: Observability · Explore
summary: Structured logs, Workers Logs and wrangler tail, Analytics Engine events and the SQL API, the GraphQL Analytics API, Server-Timing, and how the Academy turns them into labeled charts.
---

## Signals and where they go

::: diagram observability-pipeline

| Signal | Shop (Pages Functions) | Academy (Worker) | Read it with |
| --- | --- | --- | --- |
| Logs | `console.log` JSON lines | Same, plus Workers Logs (`[observability] enabled = true`) | `wrangler pages deployment tail`, `wrangler tail`, Workers Logs in the dashboard |
| Events and metrics | Analytics Engine `caddock_search` | Analytics Engine `academy_lab` | SQL API, `/api/telemetry`, `academy/tools/telemetry.mjs` |
| Request timing | `Server-Timing` on `/api/stock`, `/api/search` | `Server-Timing` on `/api/lab/cache` | `measure.mjs`, `curl -si`, browser devtools |
| Platform metrics | Pages analytics | `workersInvocationsAdaptive` | GraphQL Analytics API |
| Zone traffic | `httpRequestsAdaptiveGroups` (custom domain) | – | GraphQL Analytics API |

## Structured logs

A log line that is one JSON object can be filtered and aggregated. Free text can only be read. Both projects log one object per event:

::: embed functions/api/search.js "console.log(JSON.stringify({ event: \"search\""

Workers Logs is switched on for the Academy in `wrangler.toml`, with every request sampled:

::: embed academy/wrangler.toml "[observability]"

Pages projects do not accept the `observability` field (the same validator that rejects `ratelimits`), so the shop's logs come from `wrangler pages deployment tail` and the Pages dashboard.

## Analytics Engine: events you can query

`writeDataPoint` is fire-and-forget, does not slow the response, and is queryable with SQL within seconds. The search Function records the mode, outcome, latency, and result count:

::: embed functions/api/search.js "env.SEARCH_EVENTS?.writeDataPoint"

At high volume Analytics Engine samples, so every query weights by `_sample_interval`:

::: embed observability/queries/search-modes.sql

## From query to chart, honestly

The Academy Worker's `/api/telemetry` runs those queries when two settings exist, and says exactly what is missing when they do not. It never fills the gap with made-up numbers:

::: embed academy/worker/index.js "async function telemetry"

The build enforces the same rule for static charts. A dataset must declare `kind: "real"` with a source and timestamp, or `kind: "simulated"` with steps to make it real, or the build fails:

::: embed academy/charts.py "def validate_dataset"

## GraphQL Analytics API

Platform metrics such as invocations, errors, and CPU time come from GraphQL:

::: embed observability/queries/workers-invocations.graphql

::: chart worker-invocations

## Measured results

`measure.mjs` requests each route ten times over fresh connections and records time to first byte and the `Server-Timing` cache result. CI runs it against `wrangler pages dev` on every push, so the chart below is real in deployed builds, labeled with the runner and time:

::: chart local-latency

::: chart search-modes

::: chart lab-requests

::: live telemetry

## Trade-offs

| Choice | Why | Cost |
| --- | --- | --- |
| Analytics Engine for product events | Cheap, high-cardinality, SQL, no extra service | Sampled at volume; 3-month retention |
| JSON logs, not a log vendor | Works with tail, Workers Logs, and Logpush later | Querying old logs needs Workers Logs or Logpush |
| Server-Timing headers | Free per-request breakdown in any client | Workers clocks only move on I/O, so CPU work shows as 0 ms |
| Measure `wrangler pages dev` in CI | Real, repeatable numbers on every push | Local runtime, not edge latency; labeled as such |
