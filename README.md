# 33audio.com

Static catalog of NOS Caddock Micronox film resistors sold by Mark at 33audio, Houston, TX. Buyers can search part numbers such as `MM177 4.32K`, open one page per value, and buy on eBay or email Mark.

The public site is the generated `docs/` folder. Generator code and inventory data live outside `docs/`.

## License

The code in this repository is under the MIT license (see `LICENSE`).

Listing data, product text, and images belong to 33audio and are not covered by that license. That includes `data/catalog.json`, `data/ebay.json`, the catalog HTML fixture, datasheet scans, and the generated product pages.

## What’s here

- `catalog/parse.py` reads the existing listing at `https://www.33audio.com/enter/caddockmsmm.html` and writes `data/catalog.json`.
- `catalog/ebay.py` pulls active listings for seller `33audiomarko` from the official eBay Browse API. It does not scrape eBay HTML. If `EBAY_CLIENT_ID` or `EBAY_CLIENT_SECRET` is missing, it exits successfully and leaves any existing `data/ebay.json` alone.
- `catalog/build.py` renders `docs/`: the homepage, a catalog, one page per series, one page per part, `search.json`, `sitemap.xml`, `robots.txt`, and an empty `.nojekyll` file.
- `data/site.json` holds seller details, the flat shipping rate, the public site URL, and the buy-button mode.

Prices and quantities come from the listing page. The page states `$10.00` each and USA-only orders. Houston and the `$6.35` flat shipping rate are seller terms in `data/site.json`, not fields on that page. The generator does not invent stock.

## Edit inventory

1. Change a quantity, price, or value in `data/catalog.json`, or edit shipping, email, and buy mode in `data/site.json`.
2. Rebuild:

```bash
python -m catalog build
```

Part ids look like `MM177-4.32K`. A tolerance letter is added only when the source line marks one, so `MM177-665K` (series default) and `MM177-665K-F` stay distinct.

The scheduled workflow fetches the live listing again and overwrites `data/catalog.json`. A hand edit lasts until that run. Change the source page, or reapply the edit after a refresh, if it needs to stick.

## Buy buttons

The site defaults to eBay. A checkout demo menu on every page switches the Buy button among eBay, Stripe, and PayPal and stores the choice in the browser.

- eBay opens the matched Browse API listing, or a search of `33audiomarko` when none is matched.
- Stripe and PayPal use `payment_flows` in `data/site.json`. Set `url` to an `https` template (`{part_id}`, `{series}`, `{resistance}`, `{query}`). A `parts` object can override that template for one part id. An empty URL shows a disabled “demo, not yet active” control instead of a link.

**Ask about this part** always emails `mark@33audio.com` with the part id in the subject.

## AI and search crawlers

Every build writes these files at the site root:

- `llms.txt` follows the [llms.txt](https://llmstxt.org/) convention: who 33audio is, the $10.00 price, $6.35 flat USA shipping, the eBay store, and a link to every series and part page.
- `llms-full.txt` adds one plain-language sentence per part and the shared FAQ.
- `catalog.md` and `catalog.json` are the same inventory as a Markdown table and as JSON. The footer links to them.

Part pages start with that sentence and a short FAQ (Type MM versus Type MS, what NOS means on this site, and the uses named on the 1985 Caddock datasheets). The FAQ is also FAQPage JSON-LD. The answers stay inside the 33audio listing and those datasheets.

`robots.txt` allows `GPTBot`, `OAI-SearchBot`, `ChatGPT-User`, `ClaudeBot`, `Claude-SearchBot`, `PerplexityBot`, `Google-Extended`, `Applebot-Extended`, and `Bingbot`, and it still points at the sitemap. If the site is later hosted on Cloudflare, leave **Block AI bots** / **AI Crawl Control** off (allowed). That dashboard setting blocks these crawlers even when `robots.txt` allows them.

### Search Console and Bing

After the site is public:

1. In [Google Search Console](https://search.google.com/search-console), add the site (the GitHub Pages URL, or the custom domain once it is chosen) and verify it.
2. Open **Sitemaps** and submit `sitemap.xml` (the full URL is the one in `robots.txt`).
3. In [Bing Webmaster Tools](https://www.bing.com/webmasters), add the same site. You can import it from Search Console, or verify it directly and submit the same sitemap URL.

## Selling costs

`/fees/` compares published US rates for a $10 part plus $6.35 shipping, with a calculator. The rates and source URLs live in `data/site.json` under `selling_costs`. Update them there when the fee pages change.

## eBay secrets

The sync uses the client-credentials grant against `https://api.ebay.com`. In the GitHub repo settings, add:

- `EBAY_CLIENT_ID`
- `EBAY_CLIENT_SECRET`

Locally, export the same variables before `python -m catalog ebay`. A missing secret skips the sync. It does not fail the build.

## GitHub Pages

1. Push this repository’s `main` branch.
2. In the repo settings, open **Pages**.
3. Deploy from branch `main`, folder `/docs`.

`docs/.nojekyll` is an empty file so GitHub Pages serves the files as-is and does not run Jekyll. The site generator writes it on every build.

The canonical origin in `data/site.json` is `https://exergy-connect.github.io/33audio.com` until a domain is chosen. Leave `custom_domain` as `null`. When the hostname is decided, set `custom_domain` to it (and point `canonical_origin` at `https://` that host), then rebuild. The generator writes `docs/CNAME` only in that case. No `CNAME` file is published while the decision is open.

## Local preview

Python 3.15. The tools use the standard library only. The refresh workflow installs it with `actions/setup-python@v7` (`python-version: '3.15'`).

```bash
python -m catalog parse
python -m catalog ebay
python -m catalog build
python -m http.server -d docs 8080
```

`python -m catalog refresh` runs all three. Tests:

```bash
python -m unittest discover -s tests -v
```

## Refresh workflow

`.github/workflows/refresh.yml` runs every day and on manual dispatch. It parses the listing, syncs eBay when the two secrets exist, rebuilds `docs/`, and commits any changes.
