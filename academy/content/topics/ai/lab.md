---
title: AI-assisted search · Lab
summary: Run the part finder locally with the keyword fallback, test the AI path with a mocked binding, then switch on real Workers AI with wrangler pages dev --ai.
---

## 1. Ask without AI

Start the shop ([deploy lab](/labs/deploy/), step 2), then ask the question from the brief:

```bash
curl -s "http://127.0.0.1:8788/api/search?q=I+need+a+10M+resistor+for+a+tube+amp" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d['mode'], '|', d['fallback_reason'])
print(d['summary'])
for r in d['results'][:3]:
    print(r['part_number'], r['resistance'], str(r['voltage_rating']) + ' V', r['why'])
"
```

```output
keyword | Workers AI is not bound (env.AI missing), so the keyword parser answered
No 10 MΩ part is in stock. These are the closest values. Ranked for tube amplifier.
MS176-2.5M 2.5 MΩ 500 V ['75% from the requested value', '500 V rating']
MM215-2.15M 2.15 MΩ 800 V ['79% from the requested value', '800 V rating']
MM177-1.89M 1.89 MΩ 500 V ['81% from the requested value', '500 V rating']
```

Open `http://127.0.0.1:8788/ask/` in a browser and try the example buttons. The note above the results says which path answered.

## 2. Inspect the response headers

```bash
curl -si "http://127.0.0.1:8788/api/search?q=4.32K" | grep -i -E '^x-search|server-timing|cache-control'
```

```output
Cache-Control: no-store
Server-Timing: cache;desc="MISS";dur=0, catalog;desc="ASSETS catalog.json";dur=0, search;desc="keyword";dur=0
X-Search-Cache: MISS
X-Search-Mode: keyword
```

Keyword answers are `no-store`. AI answers get `public, max-age=300` and a Cache API entry.

## 3. Test the AI path with a mock

The unit tests swap in a fake `env.AI` to prove the AI path, the fallback on failure, and output sanitizing:

::: embed tests/js/search.test.mjs "test(\"AI intent is used when the binding answers\""

```bash
node --test tests/js/search.test.mjs
```

```output
✔ parses resistance notations
✔ keyword intent for the tube amp question
✔ ranking prefers exact values and in-stock parts
✔ tube amp search without AI falls back and explains why
✔ AI intent is used when the binding answers
✔ AI failure falls back to the keyword parser
✔ AI output is sanitized
✔ formats ohms
✔ the tighter tolerance hint wins unless a percentage is typed
ℹ tests 9
ℹ pass 9
ℹ fail 0
```

## 4. Use real Workers AI locally

This needs a Cloudflare account with Workers AI. `--ai AI` adds the binding for this dev session only, and Wrangler proxies the calls to Cloudflare, so they are billed.

```bash
export CLOUDFLARE_API_TOKEN=...   # token with Workers AI: Read
export CLOUDFLARE_ACCOUNT_ID=...
npx wrangler@4.162.0 pages dev docs --port 8788 --ai AI
curl -s "http://127.0.0.1:8788/api/search?q=two+point+one+five+meg+for+a+preamp+plate" | python3 -m json.tool | head -12
```

Expect `"mode": "ai"`, `"model": "@cf/meta/llama-3.1-8b-instruct-fast"`, and an `intent` with `ohms` near 2150000 and `min_voltage` around 500. The exact intent depends on the model, which is why ranking stays in code. Change the model with a `SEARCH_MODEL` variable.

## 5. Deploy with the AI binding

The binding is declared under `[env.production.ai]` in `wrangler.toml`, so production deployments get it and preview deployments use the keyword parser. After deploying (deploy lab, step 8):

```bash
node academy/tools/lab-check.mjs --shop https://caddock-33audio.pages.dev --topics ai
```

The check passes in either mode. The `mode` it prints tells you whether Workers AI answered.

## 6. Watch it in production

Each search writes a data point to the `caddock_search` dataset. Query it with [observability/queries/search-modes.sql](repo:observability/queries/search-modes.sql), or follow the [observability lab](/labs/observability/) to turn the simulated chart on the Explore page into a real one.
