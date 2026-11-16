---
title: Product discovery · Lab
summary: Inspect robots.txt, llms.txt, JSON-LD, catalog.json, and the xYang schema on the running shop, validate them, and check them the way a crawler would.
---

## Before you start

Start the shop as in the [deploy lab](/labs/deploy/), steps 1 and 2:

```bash
npm run dev:shop --prefix academy
```

All commands below use `http://127.0.0.1:8788`. After you deploy, replace it with your Pages URL and every step works the same.

## 1. robots.txt allows the AI crawlers

```bash
curl -s http://127.0.0.1:8788/robots.txt | grep -A1 -E 'GPTBot|ClaudeBot'
curl -s http://127.0.0.1:8788/robots.txt | tail -1
```

```output
User-agent: GPTBot
Allow: /
--
User-agent: ClaudeBot
Allow: /
Sitemap: https://caddock-33audio.pages.dev/sitemap.xml
```

The sitemap URL uses `canonical_origin` from `data/site.json`, not the local address.

## 2. Read llms.txt as an agent would

```bash
curl -s http://127.0.0.1:8788/llms.txt | head -12
```

```output
# 33audio

> 33audio in Houston, TX sells NOS Caddock Micronox film resistors in the MM177, MM215, MS151, and MS176 series. These resistors are liquidation stock from a Caddock stocking distributor that closed in the 1980s. Price is $10.00 each. $6.35 flat shipping for any quantity, USA only. USA orders only, no international at this time

Seller: Mark (mark@33audio.com). eBay store: https://www.ebay.com/str/33audiomarko. …

Caddock marks Type MM Not Recommended for New Designs and points new designs to Type MS.

## Catalog files

- [All parts (Markdown)](https://caddock-33audio.pages.dev/catalog.md): Table of every value, tolerance, quantity, and price
- [All parts (JSON)](https://caddock-33audio.pages.dev/catalog.json): The same catalog as JSON
```

## 3. Extract the JSON-LD from a part page

```bash
curl -s http://127.0.0.1:8788/parts/mm177-4.32k/ | python3 -c "
import re, sys, json
html = sys.stdin.read()
for block in re.findall(r'<script type=\"application/ld\+json\">(.*?)</script>', html, re.S):
    node = json.loads(block)
    print(node.get('@type'), node.get('name') or node.get('@id', ''))
"
```

```output
Product Caddock MM177-4.32K Micronox resistor
None https://caddock-33audio.pages.dev/catalog.json
FAQPage 
BreadcrumbList 
```

The second block has no `@type` at the top: it is the shop-vocabulary node, typed through the xYang context. Caddock pages describe reference products and FAQs without an `Offer` or `BuyAction`; availability must be confirmed with Mark. eBay listings have their own purchase links in the separate eBay section.

## 4. Validate catalog.json against the model

```bash
curl -s http://127.0.0.1:8788/catalog.json | python3 -c "import sys, json; d = json.load(sys.stdin); print(d['\$schema']); print(d['@context']); print(len(d['parts']), 'parts')"
python -m catalog schema --check
```

```output
https://caddock-33audio.pages.dev/schema/catalog.schema.json
https://caddock-33audio.pages.dev/schema/context.jsonld
85 parts
Model, schema, and catalogs agree.
```

`--check` validates `docs/catalog.json` with xYang and with the generated JSON Schema, and fails if `docs/schema/` is stale.

## 5. Fetch like a crawler

Send the same request with an AI crawler's user agent. Locally there is no bot filtering, so this proves the content, not the edge policy:

```bash
curl -s -o /dev/null -w '%{http_code} %{content_type}\n' -A 'Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)' http://127.0.0.1:8788/llms.txt
```

```output
200 text/plain; charset=utf-8
```

On the deployed zone, a spoofed user agent is not a verified bot. Cloudflare identifies real crawlers by IP and signature (`cf.verified_bot_category`), which is what the WAF skip rule matches.

## 6. Run the automated check

```bash
node academy/tools/lab-check.mjs --shop http://127.0.0.1:8788 --topics discovery
```

```output
PASS  discovery     robots.txt allows AI crawlers and lists the sitemap  (4 AI crawlers allowed)
PASS  discovery     llms.txt lists series and part pages  (85 part links)
PASS  discovery     part page has Product and FAQPage JSON-LD  (Product, Brand, PropertyValue, FAQPage, Question, Answer)
PASS  discovery     catalog.json points at its xYang schema and context  (85 parts)
PASS  discovery     sitemap lists every page  (97 URLs)

5 passed, 0 failed
```

## 7. After deploying

1. In the Cloudflare dashboard, open **AI Crawl Control** for the zone and make sure the crawlers you want are allowed.
2. Submit `sitemap.xml` in Google Search Console and Bing Webmaster Tools (see the README).
3. Watch crawler traffic: query `httpRequestsAdaptiveGroups` filtered on `userAgent` and `clientRequestPath` with [observability/queries/zone-http.graphql](repo:observability/queries/zone-http.graphql) as a starting point, and replace the simulated crawler chart with a real dataset.
