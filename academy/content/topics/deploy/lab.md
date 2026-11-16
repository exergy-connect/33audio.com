---
title: Build and deploy the shop · Lab
summary: Build the catalog, run the shop locally with wrangler pages dev and a seeded KV namespace, exercise checkout and the signed webhook, then deploy to Cloudflare Pages.
---

## What you will do

Run the full shop on your machine, including Pages Functions and a local KV namespace, then check every endpoint. Steps 1 to 7 need no Cloudflare account. Step 8 deploys for real.

## 1. Build the static site

```bash
python -m catalog build
```

```output
Stock KV seed skipped: CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID not set.
Built 85 part pages in /path/to/33audio.com/docs
```

The build regenerates `docs/` from `data/catalog.json` and `data/site.json`, and keeps `docs/schema/`.

## 2. Seed local KV and start the shop

`dev-shop.mjs` writes `data/stock.json` into the local `STOCK` namespace, then starts `wrangler pages dev docs` on port 8788.

::: embed academy/tools/dev-shop.mjs "const seeded"

Create a local webhook secret first, so step 6 can sign events. `.dev.vars` is git-ignored.

```bash
printf 'STRIPE_WEBHOOK_SECRET="whsec_lab_local"\n' > .dev.vars
npm run dev:shop --prefix academy
```

```output
Writing the contents of data/stock.json to the key "stock" on namespace binding: "STOCK" (id: "REPLACE_WITH_STOCK_KV_NAMESPACE_ID").
✨ Compiled Worker successfully
Using secrets defined in .dev.vars
Your Worker has access to the following bindings:
Binding                                   Resource                      Mode
env.STOCK (REPLACE_WITH_STOCK_KV_NAMESPACE_ID)   KV Namespace           local
env.SEARCH_EVENTS (caddock_search)        Analytics Engine Dataset      local
env.CHECKOUT_ENABLED ("false")            Environment Variable          local
env.STRIPE_WEBHOOK_SECRET ("(hidden)")    Environment Variable          local
[wrangler:info] Ready on http://127.0.0.1:8788
```

There is no `env.AI` locally. That is intentional (see [ADR 0004](/reference/adr/0004-ai-binding-production-only/)).

## 3. Read the stock document

```bash
curl -si http://127.0.0.1:8788/api/stock | head -8
```

```output
HTTP/1.1 200 OK
Content-Length: 12628
Content-Type: application/json; charset=utf-8
Cache-Control: public, max-age=30
Server-Timing: cache;desc="MISS";dur=1, kv;desc="STOCK get";dur=2
```

The body has 85 parts. `applied_sessions` is stripped by `publicStock()` so session ids never leave the server.

## 4. See the Cache API answer

Run the same request again within 30 seconds:

```bash
curl -si http://127.0.0.1:8788/api/stock | grep -i -E 'server-timing|age'
```

```output
Age: 0
Server-Timing: cache;desc="HIT";dur=1
```

The `kv` entry is gone: the Function answered from `caches.default` without touching KV.

## 5. Checkout stays off until you turn it on

```bash
curl -s http://127.0.0.1:8788/api/checkout
curl -s -X POST http://127.0.0.1:8788/api/checkout \
  -H 'content-type: application/json' \
  -d '{"items":[{"id":"MM177-4.32K","qty":1}]}' -w '\nHTTP %{http_code}\n'
```

```output
{"enabled":false,"message":"Checkout is a demo, not yet active. Nothing will be charged."}
{"enabled":false,"error":"checkout_disabled","message":"Checkout is a demo, not yet active. Nothing will be charged."}
HTTP 503
```

## 6. Send a signed webhook

Sign a test event with the same code the Function uses to verify it:

```bash
PAYLOAD='{"id":"evt_lab","type":"customer.created","data":{"object":{}}}'
SIG=$(node --input-type=module -e "import {signPayload} from './worker/stripe.js'; const t=Math.floor(Date.now()/1000); console.log('t='+t+',v1='+await signPayload(process.argv[1],'whsec_lab_local',t))" "$PAYLOAD")
curl -s -X POST http://127.0.0.1:8788/api/stripe-webhook -H "Stripe-Signature: $SIG" -d "$PAYLOAD"; echo
curl -s -X POST http://127.0.0.1:8788/api/stripe-webhook -H "Stripe-Signature: t=1,v1=00" -d "$PAYLOAD" -w ' HTTP %{http_code}\n'
```

```output
{"received":true,"ignored":"customer.created"}
{"error":"bad_signature"} HTTP 400
```

The valid event is accepted and ignored because only `checkout.session.completed` changes stock. A real paid session also needs `STRIPE_SECRET_KEY`, because the webhook fetches the line items from Stripe.

## 7. Run the automated check

```bash
node academy/tools/lab-check.mjs --shop http://127.0.0.1:8788 --webhook-secret whsec_lab_local --topics deploy
```

```output
PASS  deploy        GET /api/stock returns the KV stock document  (85 parts)
PASS  deploy        second /api/stock is served by the Cache API  (Server-Timing cache HIT)
PASS  deploy        GET /api/checkout reports the feature flag  (Checkout is a demo, not yet active. Nothing will be charged.)
PASS  deploy        POST /api/checkout is refused while the flag is off  (503 checkout_disabled)
PASS  deploy        webhook rejects a bad Stripe-Signature  (400 bad_signature)
PASS  deploy        webhook accepts a correctly signed event  ({"received":true,"ignored":"customer.created"})

6 passed, 0 failed
```

CI runs this same command on every push (see [Deployment pipelines](/reference/pipelines/)).

## 8. Deploy to Cloudflare Pages

This step needs your Cloudflare account. Output is not reproduced here because it depends on your account.

```bash
npx wrangler@4.162.0 login
npx wrangler@4.162.0 kv namespace create STOCK
# paste the id into wrangler.toml in both [[kv_namespaces]] blocks
npx wrangler@4.162.0 pages project create caddock-33audio --production-branch main
npx wrangler@4.162.0 pages deploy docs --project-name caddock-33audio --branch main
python -m catalog stock --seed      # needs CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID
```

Then confirm the deployment with the same check:

```bash
node academy/tools/lab-check.mjs --shop https://caddock-33audio.pages.dev --topics deploy,discovery
```

Connecting the repository in the dashboard (Workers & Pages → Create → Pages → Connect to Git, output directory `docs`, no build command) gives the same result and redeploys on every push to `main`. The [go-live checklist](/reference/go-live/) lists the secrets.

::: details Clean up
Stop the dev server with Ctrl+C. Local KV data lives in `.wrangler/state/` and can be deleted.
:::
