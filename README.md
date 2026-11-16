# 33audio.com

Static catalog of NOS Caddock Micronox film resistors sold by Mark at 33audio, Houston, TX. Buyers can search part numbers such as `MM177 4.32K`, ask in plain words at `/ask/` ("I need a 10M resistor for a tube amp"), open one page per value, buy on eBay, email Mark, or (once switched on) pay through a Stripe cart.

The site is hosted on Cloudflare Pages. `docs/` is the generated static output. `functions/` holds the Pages Functions (`/api/stock`, `/api/checkout`, `/api/stripe-webhook`, `/api/search`), with shared Worker code in `worker/`.

`academy/` is the **Exergy ∞ Engineering Academy**, a separate Cloudflare project that teaches how this shop is built, discovered, secured, delivered, and observed. See [The Academy](#the-academy). Generator code and inventory data live outside `docs/`.

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

## Catalog ontology (xYang)

`model/audio33-catalog.yang` is a YANG 1.1 model of the public catalog: seller, offer terms, the four Caddock series with their datasheet power and voltage ratings, and every part (part number, manufacturer, series, resistance in ohms, tolerance, NOS condition, quantity, price, currency, page URL, eBay listing). Every node has a description. Custom extensions (`c33:schema-org-class`, `c33:schema-org-property`, `c33:wikidata`, `c33:unit-code`) map nodes to schema.org and to Wikidata items that clearly match, such as resistor (Q5321), ohm (Q47083), and new old stock (Q907054). `model/audio33-source-listing.yang` describes `data/catalog.json` as the parser writes it.

[xYang](https://github.com/exergy-connect/xYang) (`pip install -r requirements-schema.txt`) turns the models into the files under `docs/schema/`:

- `catalog.schema.json` and `source-listing.schema.json`: JSON Schema 2020-12 with `x-yang` metadata.
- `context.jsonld`: JSON-LD context exported by xYang from the extensions, with terms scoped by position. URI-valued leaves use the portable `jl:iri-value` extension in `model/xyang-jsonld.yang`.
- `vocab.jsonld` and `README.md`: every term with its description, schema.org mapping, Wikidata match, and unit.

`docs/catalog.json` points at the schema and context with `$schema` and `@context`. Part pages add a JSON-LD node in this vocabulary with the same `@id` as their schema.org Product, and `llms.txt` links the vocabulary.

```bash
python -m catalog schema          # regenerate docs/schema and validate
python -m catalog schema --check  # fail if docs/schema is stale or a catalog does not validate
```

The check validates `docs/catalog.json` with xYang and with the generated JSON Schema, and `data/catalog.json` with both validators in native JSON mode, because hand-edited `ohms` values are plain numbers. `.github/workflows/schema.yml` runs it on pushes that touch the model and commits the regenerated files. The daily refresh runs `--check` after rebuilding. `python -m catalog build` leaves `docs/schema/` in place.

## Selling costs

`/fees/` compares published US rates for a $10 part plus $6.35 shipping, with a calculator. The rates and source URLs live in `data/site.json` under `selling_costs`. Update them there when the fee pages change.

## eBay secrets

The sync uses the client-credentials grant against `https://api.ebay.com`. In the GitHub repo settings, add:

- `EBAY_CLIENT_ID`
- `EBAY_CLIENT_SECRET`

Locally, export the same variables before `python -m catalog ebay`. A missing secret skips the sync. It does not fail the build.

## Deploy on Cloudflare Pages

The site no longer uses GitHub Pages. If Pages is still switched on in the GitHub repo settings, turn it off.

1. Create the stock namespace and paste its id into **both** `[[kv_namespaces]]` blocks of `wrangler.toml` (top level and `[env.production]`; a test checks they match):

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
| `SEARCH_EVENTS` | Analytics Engine binding (`caddock_search`) | One data point per part search |
| `AI` | Workers AI, `[env.production.ai]` only | Turns `/api/search` questions into filters. Local dev and previews use the keyword fallback |
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

## Part search (Workers AI)

`/ask/` sends the question to `GET /api/search?q=…`. With `env.AI` bound, Workers AI (`@cf/meta/llama-3.1-8b-instruct-fast`, JSON mode) turns it into filters: ohms, tolerance, series, voltage, power, use. A keyword parser always runs and fills gaps, and answers alone when AI is missing, slow, or wrong. Code, not the model, ranks the parts in `catalog.json`, so every result is real stock. Each response says which path answered (`mode`, `fallback_reason`), AI answers are cached for 300 s with the Cache API, and each search writes an Analytics Engine data point.

The AI binding is declared only under `[env.production]`. Workers AI has no local mode, and a top-level `[ai]` block stops `wrangler pages dev` from starting without a Cloudflare token. To try real AI locally, run `npx wrangler@4.162.0 pages dev docs --ai AI` with `CLOUDFLARE_API_TOKEN` set.

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
npm ci --prefix academy
npm run dev:shop --prefix academy  # seeds local KV, then wrangler pages dev on http://127.0.0.1:8788
```

Tests:

```bash
python -m unittest discover -s tests -v
node --test tests/js/*.test.mjs
```

## Refresh workflow

`.github/workflows/refresh.yml` runs every day and on manual dispatch. It runs the tests, parses the listing, syncs eBay when those secrets exist, builds and seeds the stock document when the Cloudflare secrets exist, rebuilds `docs/`, and commits changes. Cloudflare Pages then deploys the new commit.

## The Academy

The Exergy ∞ Engineering Academy (`academy/`) is a Cloudflare-University-style site that uses this shop as its one worked example. It has Learning Paths, a Course Catalog, Labs, Explore pages, and Reference (ADRs, repository map, bindings, pipelines, API integrations, lab.net integration, go-live checklist). Six topics each have an Explore page and a Lab: deploy, discovery, AI search, delivery and request paths, security, and observability.

- **Real code, not copies.** Lessons embed repository files at build time (`::: embed path "start"`) and link to GitHub at the build commit. A missing file or function fails the build.
- **Real vs. simulated.** Every chart and lab.net figure shows REAL TELEMETRY (source and timestamp) or SIMULATED / EXAMPLE DATA (with steps to make it real). The build fails otherwise. Real datasets (`academy/data/real/`, not committed) come from `measure.mjs`, `loadtest.mjs`, and `telemetry.mjs`. CI generates them against `wrangler pages dev`.
- **Its own Worker.** `academy/wrangler.toml` deploys `exergy-academy` as a Worker with static assets, the `LAB_LIMITER` Rate Limiting binding, the `academy_lab` Analytics Engine dataset, and Workers Logs. Live lab endpoints: `/api/health`, `/api/lab/echo`, `/api/lab/cache`, `/api/telemetry`.
- **Edge config as code.** `security/waf/rules.json` (WAF custom rules and rate limits) and `delivery/cache-rules.json` (cache rules, Tiered Cache) are applied with `node security/waf/apply.mjs [--file …] [--apply]`, which dry-runs by default.

```bash
npm ci --prefix academy
python -m academy build                 # academy/dist
npm run dev --prefix academy            # build, then wrangler dev on http://127.0.0.1:8787
node academy/tools/lab-check.mjs --shop http://127.0.0.1:8788 --academy http://127.0.0.1:8787 --webhook-secret whsec_lab_local
```

### Request paths with lab.net

The delivery topic's request paths run on [lab.net](https://github.com/exergy-connect/lab.net) (private). `network/labnet/anycast-edge.xp` and `anycast-edge-failover.xp` are lab.net topologies of a visitor, an ISP, transit, and two Cloudflare edge locations announcing one anycast prefix. They are run with lab.net's own engine at commit `06c71623`. `academy/tools/labnet-path.mjs` calls lab.net's `loadLab`, `startSimCluster`, and `runValidation` and keeps the hops and routing tables. The recorded runs and PCAPNG captures are in `academy/data/labnet/`. lab.net is deterministic, so CI regenerates and diffs them when a `LABNET_TOKEN` secret (read access to lab.net) exists, and also runs lab.net's GitHub Action on both files. Each figure links "Open this lab in lab.net", which opens the topology in the public browser build at exergy-connect.com.

lab.net does not yet model link delay, HTTP, filters, load balancers, caches, rate limits, or traffic sources. `network/labnet/proposals/` has one minimal extension proposal per gap, and the Academy marks the dependent sections as pending. `network/labnet/proposals/index.json` maps each proposal to its lab.net issue, and the pending notes link those issues.

### Deploy the Academy

`.github/workflows/academy.yml` tests everything, runs the labs against `wrangler pages dev` and `wrangler dev`, and deploys `exergy-academy` on pushes to `main` when `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` exist. Without them it posts a notice and skips. By hand: `npm run deploy --prefix academy`.

## Remaining steps to go live

Nothing is deployed yet. These steps need the owner's Cloudflare account:

1. **Token and secrets.** Create a Cloudflare API token with Workers Scripts Edit, Cloudflare Pages Edit, Workers KV Storage Edit, and Account Analytics Read (plus Zone WAF Edit, Cache Rules Edit, Zone Settings Edit, and Zone Read for the edge rules). Add `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` as GitHub secrets. Optional: `ANALYTICS_API_TOKEN` (Account Analytics Read) for real telemetry in CI, and `LABNET_TOKEN` (read access to exergy-connect/lab.net) to regenerate lab.net runs in CI.
2. **KV.** `npx wrangler@4.162.0 kv namespace create STOCK`, then paste the id into both `[[kv_namespaces]]` blocks in `wrangler.toml`. Seed it with the Refresh catalog workflow.
3. **Shop.** Connect the repo in Cloudflare Pages (output `docs`, no build command), or run the **Deploy shop (Pages direct upload)** workflow. Pick one; a Pages project cannot be both.
4. **Workers AI.** Nothing to create. Production deployments get `env.AI` from `[env.production.ai]`. The account must have Workers AI available.
5. **Academy.** Push to `main` or run the **Academy** workflow. For live telemetry, set `CF_ACCOUNT_ID` in `academy/wrangler.toml` `[vars]` and `npx wrangler secret put ANALYTICS_API_TOKEN` from `academy/`.
6. **DNS.** Add the domain as a Cloudflare zone. Attach a custom domain to the Pages project (for example `shop.33audio.com`) and to the Worker (for example `academy.<domain>`). Set `custom_domain` and `canonical_origin` in `data/site.json` and rebuild. Then apply the edge rules with `CLOUDFLARE_ZONE_ID=… node security/waf/apply.mjs --apply` and `… --file delivery/cache-rules.json --apply`, and check that AI Crawl Control allows the crawlers listed in `robots.txt`.
7. **Stripe** (when ready): Pages secrets `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET`, a webhook for `checkout.session.completed`, then `CHECKOUT_ENABLED = "true"` in both `[vars]` blocks.
8. Set `"deployed": true` in `academy/content/site.json` once each project is live.

`.github/workflows/ci.yml` runs on every pull request and on pushes to `main`. It runs the tests, rebuilds `docs/`, and fails if the committed `docs/` differs from the build.

## Theme

The look is a 1960s–70s hi-fi receiver: a walnut cabinet with a brushed-aluminum faceplate in the header, LP sleeves for the series cards, a record label next to each part number, and a VU meter for each fee on `/fees/`. The meter needle shows that fee as a percent of what the buyer pays, on a 0 to 20% scale. The header record spins twice on load at 33⅓ RPM (1.8 s per turn) and again on hover. Nothing moves when the visitor has `prefers-reduced-motion: reduce` set.

It is CSS and inline SVG only. No web fonts or images are loaded; the font stacks fall back to system fonts. Styles live in `catalog/templates/styles.css`, and the SVG pieces live in `catalog/theme.py`.
