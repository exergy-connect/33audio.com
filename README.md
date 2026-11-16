# 33audio.com

Static catalog of NOS Caddock Micronox film resistors sold by Mark at 33audio, Houston, TX. Buyers can search part numbers such as `MM177 4.32K`, open one page per value, buy on eBay, email Mark, or (once switched on) pay through a Stripe cart.

The site is hosted on Cloudflare Pages. `docs/` is the generated static output. `functions/` holds the Pages Functions (`/api/stock`, `/api/checkout`, `/api/stripe-webhook`), with shared Worker code in `worker/`. Generator code and inventory data live outside `docs/`.

## License

The code in this repository is under the MIT license (see `LICENSE`).

Listing data, product text, and images belong to 33audio and are not covered by that license. That includes `data/catalog.json`, `data/ebay.json`, the catalog HTML fixture, datasheet scans, and the generated product pages.

## What’s here

- `catalog/parse.py` reads the existing listing at `https://www.33audio.com/enter/caddockmsmm.html` and writes `data/catalog.json`.
- `catalog/ebay.py` pulls active listings for seller `33audiomarko` from the official eBay Browse API. It does not scrape eBay HTML. If `EBAY_CLIENT_ID` or `EBAY_CLIENT_SECRET` is missing, it exits successfully and leaves any existing `data/ebay.json` alone.
- `catalog/stock.py` turns the catalog into the stock document (`data/stock.json`) and can push it to Workers KV.
- `catalog/build.py` renders `docs/`: the homepage, a catalog, one page per series, one page per part, the cart, checkout success and cancel pages, `search.json`, `sitemap.xml`, and `robots.txt`.
- `data/site.json` holds seller details, the flat shipping rate, the public site URL, and the buy-button mode.
- `wrangler.toml` configures the Cloudflare Pages project, the `STOCK` KV binding, and `CHECKOUT_ENABLED`.

Prices and quantities come from the listing page. The page states `$10.00` each and USA-only orders. Houston and the `$6.35` flat shipping rate are seller terms in `data/site.json`, not fields on that page. The generator does not invent stock.

## Edit inventory

1. Change a quantity, price, or value in `data/catalog.json`, or edit shipping, email, and buy mode in `data/site.json`.
2. Rebuild:

```bash
python -m catalog build
```

Part ids look like `MM177-4.32K`. A tolerance letter is added only when the source line marks one, so `MM177-665K` (series default) and `MM177-665K-F` stay distinct.

The scheduled workflow fetches the live listing again and overwrites `data/catalog.json`. A hand edit lasts until that run. Change the source page, or reapply the edit after a refresh, if it needs to stick.

## Buy buttons and cart

The site defaults to eBay. A checkout demo menu on every page switches among three flows and stores the choice in the browser.

- **eBay** (default): each part page links to its matched Browse API listing, or a search of `33audiomarko`. The cart is hidden.
- **Stripe (cart)**: part pages and listings get **Add to cart** with a quantity stepper capped at stock. `/cart/` shows line items, subtotal, $6.35 flat shipping per order, and the total, then **Check out with Stripe** calls `/api/checkout`. The cart lives in `localStorage`.
- **PayPal**: a per-part button from `payment_flows.paypal` in `data/site.json`. Set `url` to an `https` template (`{part_id}`, `{series}`, `{resistance}`, `{query}`), or use `parts` for a per-part link. An empty URL shows a disabled “demo, not yet active” control.

**Ask about this part** always emails `mark@33audio.com` with the part id in the subject.

Pages show stock as of the last build, then replace it with live quantities from `/api/stock` when that endpoint answers.

## AI and search crawlers

Every build writes these files at the site root:

- `llms.txt` follows the [llms.txt](https://llmstxt.org/) convention: who 33audio is, the $10.00 price, $6.35 flat USA shipping, the eBay store, and a link to every series and part page.
- `llms-full.txt` adds one plain-language sentence per part and the shared FAQ.
- `catalog.md` and `catalog.json` are the same inventory as a Markdown table and as JSON. The footer links to them.

Part pages start with that sentence and a short FAQ (Type MM versus Type MS, what NOS means on this site, and the uses named on the 1985 Caddock datasheets). The FAQ is also FAQPage JSON-LD. The answers stay inside the 33audio listing and those datasheets.

`robots.txt` allows `GPTBot`, `OAI-SearchBot`, `ChatGPT-User`, `ClaudeBot`, `Claude-SearchBot`, `PerplexityBot`, `Google-Extended`, `Applebot-Extended`, and `Bingbot`, and it still points at the sitemap. On Cloudflare, leave **Block AI bots** / **AI Crawl Control** off (allowed). That dashboard setting blocks these crawlers even when `robots.txt` allows them.

### Search Console and Bing

After the site is public:

1. In [Google Search Console](https://search.google.com/search-console), add the site (the Cloudflare Pages URL, or the custom domain once it is chosen) and verify it.
2. Open **Sitemaps** and submit `sitemap.xml` (the full URL is the one in `robots.txt`).
3. In [Bing Webmaster Tools](https://www.bing.com/webmasters), add the same site. You can import it from Search Console, or verify it directly and submit the same sitemap URL.

## Selling costs

`/fees/` compares published US rates for a $10 part plus $6.35 shipping, with a calculator. The rates and source URLs live in `data/site.json` under `selling_costs`. Update them there when the fee pages change.

## eBay secrets

The sync uses the client-credentials grant against `https://api.ebay.com`. In the GitHub repo settings, add:

- `EBAY_CLIENT_ID`
- `EBAY_CLIENT_SECRET`

Locally, export the same variables before `python -m catalog ebay`. A missing secret skips the sync. It does not fail the build.

## Deploy on Cloudflare Pages

The site no longer uses GitHub Pages. If Pages is still switched on in the GitHub repo settings, turn it off.

1. Create the stock namespace and paste its id into `wrangler.toml` under `[[kv_namespaces]]` (binding `STOCK`):

   ```bash
   npx wrangler@4.162.0 kv namespace create STOCK
   ```

2. In the Cloudflare dashboard, open **Workers & Pages → Create → Pages → Connect to Git**, pick this repository, and use:
   - Production branch: `main`
   - Framework preset: None
   - Build command: leave empty. `docs/` is generated and committed by the refresh workflow, so Cloudflare does not need Python.
   - Build output directory: `docs`

   Cloudflare reads `wrangler.toml` (project name `caddock-33audio`, `compatibility_date = "2026-11-16"`) and deploys `functions/` as Pages Functions with the KV binding.

3. Add the Stripe secrets to the Pages project (**Settings → Variables and Secrets**, type Secret), or from a terminal:

   ```bash
   npx wrangler@4.162.0 pages secret put STRIPE_SECRET_KEY --project-name caddock-33audio
   npx wrangler@4.162.0 pages secret put STRIPE_WEBHOOK_SECRET --project-name caddock-33audio
   ```

4. Seed the stock key once: run the **Refresh catalog** workflow by hand (it needs the GitHub secrets below), or run `python -m catalog stock --seed` with the same variables exported.

5. If the Pages URL is not `https://caddock-33audio.pages.dev`, set `canonical_origin` in `data/site.json` to it. When a custom domain is chosen, add it under the Pages project’s **Custom domains**, set `custom_domain` in `data/site.json`, and rebuild.

The generator still writes an empty `docs/.nojekyll`. It does nothing on Cloudflare and is harmless.

### Bindings, variables, and secrets

| Name | Where | Purpose |
| --- | --- | --- |
| `STOCK` | KV binding in `wrangler.toml` | Holds one key, `stock`, with the stock JSON document |
| `CHECKOUT_ENABLED` | `[vars]` in `wrangler.toml` | `"false"` by default. `"true"` turns on Stripe checkout |
| `STRIPE_SECRET_KEY` | Pages secret | Creates Checkout Sessions and reads paid line items |
| `STRIPE_WEBHOOK_SECRET` | Pages secret | Verifies `Stripe-Signature` on `/api/stripe-webhook` |
| `CLOUDFLARE_API_TOKEN` | GitHub repo secret | Lets the workflow write the KV key (token needs Workers KV Storage: Edit) |
| `CLOUDFLARE_ACCOUNT_ID` | GitHub repo secret | Account for the KV namespace |
| `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET` | GitHub repo secrets | eBay Browse API sync |

## Stock in Workers KV

The `STOCK` namespace has a single key, `stock`:

```json
{
  "version": 1,
  "currency": "USD",
  "shipping": "6.35",
  "parts": [
    {"id": "MM177-4.32K", "series": "MM177", "part_number": "MM177-4.32K", "value": "4.32 kΩ",
     "resistance": "4.32K", "tolerance": "0.1%", "qty": 63, "price": "10.00"}
  ],
  "applied_sessions": ["cs_test_..."],
  "updated_at": "2026-11-16T03:00:00+00:00"
}
```

- `GET /api/stock` returns that document without `applied_sessions`. It is public and cached for 30 seconds.
- `python -m catalog stock` writes `data/stock.json` from the catalog. With `--seed`, it reads the live key and merges. Catalog fields (price, value, which parts exist) win, but live quantities win, so a daily refresh does not undo sales. `--overwrite` (or the workflow’s `overwrite_stock` input) resets quantities to the catalog. Without `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, or a real namespace id in `wrangler.toml`, seeding is skipped.
- The seed uses `npx wrangler@4.162.0 kv key get|put --remote`.

## Stripe checkout

`CHECKOUT_ENABLED` stays `"false"` until Mark is ready. While it is off, `POST /api/checkout` returns `503` with “Checkout is a demo, not yet active,” and the cart page shows that message.

When it is on:

1. `POST /api/checkout` takes `{"items":[{"id":"MM177-4.32K","qty":2}]}`. It reads the KV stock document, merges duplicate lines, rejects unknown, sold-out, or over-quantity lines, and prices everything from KV. Client prices are ignored.
2. It creates a Stripe Checkout Session with those line items, a $6.35 fixed shipping rate, and US-only shipping address collection, then returns the session URL.
3. Stripe sends `checkout.session.completed` to `POST /api/stripe-webhook`. The function verifies the signature, ignores sessions that are not `paid`, reads the session line items from Stripe, and decrements the `stock` key.
4. Buyers land on `/checkout/success/` (the cart is cleared) or `/checkout/cancel/`.

Order email is a TODO hook (`notifyOrder` in `worker/env.js`). For now it logs the order. Stripe’s own receipt emails still go to the buyer.

### Test mode

Use Stripe test keys (`sk_test_…`) until launch.

1. Set `STRIPE_SECRET_KEY` to a test secret key, and `CHECKOUT_ENABLED = "true"` on a preview branch.
2. In Stripe (test mode), add a webhook endpoint `https://<your-pages-url>/api/stripe-webhook` for `checkout.session.completed` and copy its signing secret into `STRIPE_WEBHOOK_SECRET`.
3. Pay with card `4242 4242 4242 4242`, any future expiry, any CVC, and a US address.

Locally, put the same values in `.dev.vars` (git-ignored), run `npx wrangler@4.162.0 pages dev`, and forward events with `stripe listen --forward-to localhost:8788/api/stripe-webhook`.

### Overselling and consistency

- KV is eventually consistent. A write can take up to about 60 seconds to show everywhere, and `/api/stock` adds up to 30 seconds of cache.
- The webhook does a read-modify-write of one key. KV has no transactions, so two orders finishing at once can race and lose one decrement.
- Stock is checked when the session is created, not reserved. Two buyers can pay for the last unit. The webhook clamps at zero and logs an `oversold` entry, and Mark has to refund or backorder by hand.
- Re-delivered webhooks are skipped by session id (`applied_sessions`, last 500).
- If oversells become a problem, move stock into a Durable Object or D1 for atomic decrements.

## Local preview

Python 3.15 for the generator (standard library only) and Node 26 for wrangler and the JS tests.

```bash
python -m catalog refresh          # parse, eBay sync, stock doc, build
npx wrangler@4.162.0 kv key put stock --path data/stock.json --binding STOCK --local
npx wrangler@4.162.0 pages dev     # http://localhost:8788 with Functions and local KV
```

Tests:

```bash
python -m unittest discover -s tests -v
node --test tests/js/*.test.mjs
```

## Refresh workflow

`.github/workflows/refresh.yml` runs every day and on manual dispatch. It runs the tests, parses the listing, syncs eBay when those secrets exist, builds and seeds the stock document when the Cloudflare secrets exist, rebuilds `docs/`, and commits changes. Cloudflare Pages then deploys the new commit.
