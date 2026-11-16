---
title: Go-live checklist
summary: Remaining steps to deploy both projects.
---

Nothing is deployed yet: no Cloudflare credentials are configured for this repository. Everything below is a one-time setup, after which deploys are a workflow run.

## 1. Cloudflare account and tokens

1. Create an API token (**My Profile → API Tokens → Create Token → Custom**) with: Account → Workers Scripts: Edit, Cloudflare Pages: Edit, Workers KV Storage: Edit, Account Analytics: Read. Add Zone → WAF: Edit, Cache Rules: Edit, Zone Settings: Edit, Zone: Read if you will apply the edge rules.
2. In GitHub, **Settings → Secrets and variables → Actions**, add `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`. Optionally add `ANALYTICS_API_TOKEN` (Account Analytics: Read only) for telemetry in CI.

## 2. Shop

1. Create the KV namespace and paste the id into **both** `[[kv_namespaces]]` blocks of `wrangler.toml` (a test checks they match):

   ```bash
   npx wrangler@4.162.0 kv namespace create STOCK
   ```

2. Deploy: connect the repo in **Workers & Pages → Create → Pages → Connect to Git** (output `docs`, no build command), or run the **Deploy shop (Pages direct upload)** workflow.
3. Workers AI: nothing to create. `[env.production.ai]` binds it on production deployments. Make sure Workers AI is available on the account.
4. Analytics Engine: nothing to create. The `caddock_search` dataset appears with the first write.
5. Seed stock: run the **Refresh catalog** workflow, or `python -m catalog stock --seed` with the token exported.
6. Stripe, when ready: `npx wrangler@4.162.0 pages secret put STRIPE_SECRET_KEY --project-name caddock-33audio`, the same for `STRIPE_WEBHOOK_SECRET`, add a webhook endpoint for `checkout.session.completed` at `/api/stripe-webhook`, then set `CHECKOUT_ENABLED = "true"` in both `[vars]` blocks.

## 3. Academy

1. Push to `main` or run the **Academy** workflow by hand. With the two secrets present, the deploy job runs `wrangler deploy` for `exergy-academy`; the Rate Limiting binding and Analytics Engine dataset need no setup.
2. Live telemetry: set `CF_ACCOUNT_ID` under `[vars]` in `academy/wrangler.toml` and run `npx wrangler secret put ANALYTICS_API_TOKEN` from `academy/`.
3. Set `"deployed": true` for the shop and Academy in `academy/content/site.json` once each is live, so the home page status line changes.

## 4. DNS and custom domains

1. Add the domain to Cloudflare as a zone (or use an existing one) and point its nameservers at Cloudflare.
2. Shop: **Pages project → Custom domains → Set up a domain** (for example `shop.33audio.com`). Cloudflare creates the proxied CNAME. Set `custom_domain` and `canonical_origin` in `data/site.json` and rebuild.
3. Academy: **Workers → exergy-academy → Settings → Domains & Routes → Add custom domain** (for example `academy.exergy.dev`).
4. With the zone in place, apply the edge rules: `CLOUDFLARE_ZONE_ID=… node security/waf/apply.mjs --apply` and `… --file delivery/cache-rules.json --apply`.
5. Check **AI Crawl Control** allows the crawlers listed in `robots.txt`.

## 5. Verify

```bash
node academy/tools/lab-check.mjs --shop https://caddock-33audio.pages.dev --academy https://exergy-academy.<your-subdomain>.workers.dev
```

Then follow the "switch to real" steps on each simulated chart.
