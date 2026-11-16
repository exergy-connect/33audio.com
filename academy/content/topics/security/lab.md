---
title: Security at the edge · Lab
summary: Validate and dry-run the WAF and rate-limit rules, trigger the Workers Rate Limiting binding with capped traffic against your own local Worker, and verify rules on your deployed zone.
---

## Ground rules

All traffic in this lab goes to `localhost` or to a deployment you own. The load tool enforces that.

## 1. Validate and dry-run the WAF rules

```bash
node security/waf/apply.mjs | tail -1
```

```output
Dry run of security/waf/rules.json: 2 requests, 6 of 8 rules enabled. Nothing was sent. Re-run with --apply to change the zone.
```

The two disabled rules are the Enterprise-only bot-score rule and the second rate-limiting rule that needs Pro. Read the full requests:

```bash
node security/waf/apply.mjs | head -30
```

```output
PUT https://api.cloudflare.com/client/v4/zones/<CLOUDFLARE_ZONE_ID>/rulesets/phases/http_request_firewall_custom/entrypoint
{
  "description": "33audio WAF custom rules",
  "rules": [
    {
      "ref": "allow_ai_crawlers_discovery",
      "description": "Let verified AI crawlers read the discovery files without later custom rules interfering",
      "expression": "(cf.verified_bot_category eq \"AI Crawler\" and http.request.uri.path in {\"/llms.txt\" …})",
      "action": "skip",
      …
```

## 2. Start the Academy Worker

```bash
npm run dev --prefix academy
```

The Worker runs on port 8787 with `env.LAB_LIMITER (20 requests/60 seconds)` enforced locally by Miniflare.

## 3. Send a controlled burst

```bash
node academy/tools/loadtest.mjs --url http://localhost:8787/api/lab/echo --rps 5 --seconds 8 --out academy/data/real/ratelimit-burst.json
```

```output
Sending 5 req/s for 8 s to http://localhost:8787/api/lab/echo
s 1  2xx 5  429 0  other 0
s 2  2xx 5  429 0  other 0
s 3  2xx 5  429 0  other 0
s 4  2xx 5  429 0  other 0
s 5  2xx 0  429 5  other 0
s 6  2xx 0  429 5  other 0
s 7  2xx 0  429 5  other 0
s 8  2xx 0  429 5  other 0
wrote academy/data/real/ratelimit-burst.json
```

The first 20 requests pass, then every request in the 60-second window gets 429. If you ran other lab requests in the last minute, the switch happens sooner. Rebuild to put your measurement on the Explore page with a REAL TELEMETRY badge:

```bash
python -m academy build
```

The guard refuses hosts you have not claimed:

```bash
node academy/tools/loadtest.mjs --url https://example.com/
```

```output
Refusing to send test traffic to example.com. Use localhost, or pass --confirm-own example.com if it is your own deployment.
```

## 4. Watch the limiter from the browser

This widget sends 30 requests to this Academy's own `/api/lab/echo`:

::: live burst

## 5. Look at a 429

```bash
for i in $(seq 1 22); do curl -s -o /dev/null -w '%{http_code} ' http://localhost:8787/api/lab/echo; done; echo
curl -s http://localhost:8787/api/lab/echo
```

```output
200 200 … 429 429
{
  "error": "rate_limited",
  "limit": "20 requests per 60 s per client and path (LAB_LIMITER)"
}
```

## 6. Apply and verify on your zone

Needs the shop on a custom domain in your Cloudflare zone, and a token with Zone WAF Edit.

```bash
export CLOUDFLARE_API_TOKEN=... CLOUDFLARE_ZONE_ID=...
node security/waf/apply.mjs --apply
node security/waf/apply.mjs --show | head -20
SHOP=https://shop.example.com   # your domain
curl -s -o /dev/null -w 'probe %{http_code}\n' $SHOP/wp-login.php
curl -s -o /dev/null -w 'webhook GET %{http_code}\n' $SHOP/api/stripe-webhook
curl -s -o /dev/null -w 'stock POST %{http_code}\n' -X POST $SHOP/api/stock
for i in $(seq 1 15); do curl -s -o /dev/null -w '%{http_code} ' "$SHOP/api/search?q=4.32K"; done; echo
```

Expect `403` for the probe, the webhook GET, and the stock POST, and `429` after about ten searches within ten seconds. Then open **Security → Events** to see each match with its rule `ref`, or query `firewallEventsAdaptiveGroups` in the GraphQL API and save the counts as `academy/data/real/waf-events.json` to replace the simulated chart.

## 7. Simulate it in lab.net (pending)

::: pending 03-filter-waf Run the enabled WAF rules against a simulated edge.

::: pending 06-rate-limit Show 429s per source at the edge node.

::: pending 07-traffic-source Drive the edge with a seeded multi-source flood.

## 8. Clean up

To remove the rules, apply an empty rule list for each phase, or delete the rules in the dashboard. Local rate-limit counters reset when you restart `wrangler dev`.
