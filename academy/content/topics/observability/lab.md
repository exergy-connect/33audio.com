---
title: Observability · Lab
summary: Read structured logs from wrangler, measure the shop and publish a REAL TELEMETRY chart, read Server-Timing, query Analytics Engine, and tail a deployed Worker.
---

## 1. Structured logs, locally

With the shop running ([deploy lab](/labs/deploy/), step 2), send a search and watch the dev server's terminal:

```bash
curl -s "http://127.0.0.1:8788/api/search?q=10M+tube+amp" > /dev/null
```

```output
{"event":"search","mode":"keyword","took_ms":0,"results":6,"fallback":"Workers AI is not bound (env.AI missing), so the keyword parser answered"}
[wrangler:info] GET /api/search 200 OK (12ms)
```

The first line is the Function's own JSON log. The second is Wrangler's access log.

## 2. Measure and publish a real chart

```bash
node academy/tools/measure.mjs --base http://127.0.0.1:8788 --n 10 \
  --environment "wrangler pages dev on $(hostname)" \
  --out academy/data/real/local-latency.json
```

```output
/                                status 200  p50 5 ms  p95 39.5 ms
/parts/mm177-4.32k/              status 200  p50 4.2 ms  p95 6.3 ms
/llms.txt                        status 200  p50 3.6 ms  p95 4.4 ms
/catalog.json                    status 200  p50 4.5 ms  p95 5.5 ms
/api/stock                       status 200  p50 5.3 ms  p95 8.7 ms  cache HIT×10
/api/search?q=10M+tube+amp       status 200  p50 6.9 ms  p95 21.3 ms  cache MISS×10
wrote academy/data/real/local-latency.json
```

Your numbers will differ. Now rebuild the Academy:

```bash
python -m academy build
```

```output
Academy: 46 pages, 31 repo embeds, 1 real and 10 simulated datasets on pages.
```

Open `/explore/observability/` (with `npm run dev --prefix academy` running, at `http://localhost:8787`). The latency chart now has a green REAL TELEMETRY badge naming `academy/tools/measure.mjs against http://127.0.0.1:8788`, your environment text, and the time. Delete the file and rebuild, and the chart goes back to SIMULATED.

## 3. Read Server-Timing on one request

```bash
curl -s -o /dev/null -D - "http://127.0.0.1:8788/api/search?q=4.32K" | grep -i -E 'server-timing|x-search'
curl -s -o /dev/null -w 'ttfb %{time_starttransfer}s  total %{time_total}s\n' "http://127.0.0.1:8788/api/search?q=4.32K"
```

```output
Server-Timing: cache;desc="MISS";dur=0, catalog;desc="ASSETS catalog.json";dur=0, search;desc="keyword";dur=0
X-Search-Cache: MISS
X-Search-Mode: keyword
ttfb 0.004312s  total 0.004398s
```

Locally the server-side entries are near zero because no real network I/O happens. Against the deployed shop, `catalog` and `search` (in AI mode) show real time. Network paths to the edge are covered with lab.net in the [delivery topic](/explore/delivery/), not here.

## 4. Analytics Engine, locally

The Academy Worker writes an event per API request. Locally, Wrangler accepts the writes but there is nothing to query, so `/api/telemetry` reports what it needs:

```bash
curl -s http://localhost:8787/api/telemetry
```

```output
{
  "kind": "unconfigured",
  "missing": [
    "ANALYTICS_API_TOKEN",
    "CF_ACCOUNT_ID"
  ],
  "steps": [
    "Create an API token with Account → Account Analytics → Read.",
    "npx wrangler secret put ANALYTICS_API_TOKEN (from academy/)",
    "Set CF_ACCOUNT_ID under [vars] in academy/wrangler.toml, or as a secret, and redeploy.",
    "Reload this page: the chart switches to REAL TELEMETRY with the query time as its timestamp."
  ]
}
```

::: live telemetry

## 5. Run the automated check

```bash
node academy/tools/lab-check.mjs --shop http://127.0.0.1:8788 --academy http://localhost:8787 --topics observability,academy
```

```output
PASS  observability API responses carry Server-Timing  (cache;desc="MISS";dur=0, catalog;desc="ASSETS catalog.json";dur=0, search;desc="keyword";dur=0)
PASS  observability TTFB is measurable  (TTFB 5.7 / 4 / 3.8 ms)
PASS  academy       /api/health  (deployment local)
PASS  academy       home and a lab page render
PASS  academy       /api/lab/echo labels its provenance  (kind simulated)
PASS  academy       /api/lab/cache goes MISS then HIT  (MISS → HIT)
PASS  academy       /api/telemetry says what it needs  (unconfigured, missing ANALYTICS_API_TOKEN, CF_ACCOUNT_ID)

7 passed, 0 failed
```

`/api/lab/echo` reports `kind simulated` locally because `request.cf` in `wrangler dev` is a placeholder. On the deployed Worker it reports `real`.

## 6. In production

After deploying both projects ([go-live checklist](/reference/go-live/)):

```bash
# live logs
npx wrangler@4.162.0 tail exergy-academy --format json --status error
npx wrangler@4.162.0 pages deployment tail --project-name caddock-33audio --format pretty

# Analytics Engine over SQL
curl -s "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/analytics_engine/sql" \
  -H "Authorization: Bearer $ANALYTICS_API_TOKEN" \
  --data-binary @observability/queries/search-modes.sql

# write REAL datasets and rebuild
CF_ACCOUNT_ID=... ANALYTICS_API_TOKEN=... node academy/tools/telemetry.mjs --out-dir academy/data/real
python -m academy build
```

`telemetry.mjs` writes only datasets that returned rows. Empty results leave the simulated chart in place, still labeled.

For platform metrics, run [observability/queries/workers-invocations.graphql](repo:observability/queries/workers-invocations.graphql) in the GraphQL API explorer with `scriptName: "exergy-academy"`.
