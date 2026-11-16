"""Render the static catalog into docs/."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from email.utils import parsedate_to_datetime
from html import escape
from pathlib import Path
from xml.etree import ElementTree as ET

from catalog import ASSETS, DATA, DOCS
from catalog.fees import estimate, from_cents, to_cents
from catalog.llm_pages import faq_json_ld, faq_pairs, ontology_json_ld, part_summary, render_catalog_json, render_catalog_md, render_llms_full, render_llms_txt, render_robots
from catalog.purchase import configured_flow_url, flatten, match_listings, resistance_label, resolve_purchase

TEMPLATES = Path(__file__).resolve().parent / "templates"


def rel(depth: int, target: str = "") -> str:
    prefix = "./" if depth == 0 else "../" * depth
    return prefix if not target else prefix + target


def depth_of(rel_path: str) -> int:
    parent = Path(rel_path).parent.as_posix()
    if parent in ("", "."):
        return 0
    return len(Path(parent).parts)


def public_origin(site: dict) -> str:
    custom = site.get("custom_domain")
    if custom:
        return "https://" + str(custom).strip().strip("/")
    return str(site["canonical_origin"]).rstrip("/")


def abs_url(origin: str, path: str) -> str:
    return origin + "/" + path.lstrip("/")


def json_ld(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def search_blob(part: dict) -> str:
    resistance = part["resistance"]
    bare = resistance[:-1] if resistance[-1:] in {"K", "M"} else resistance
    bits = [
        part["id"],
        part["series"],
        resistance,
        bare,
        str(part["ohms"]),
        part["tolerance"],
        part["tolerance"].replace("%", ""),
        part["tolerance_code"],
        "caddock",
        "micronox",
        "film",
        "nos",
        part["family"].lower(),
    ]
    return " ".join(bits).lower()


def lastmod(catalog: dict) -> str | None:
    raw = catalog.get("source_last_modified")
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).date().isoformat()
    except (TypeError, ValueError, IndexError):
        return None


SCHEMA_DIR = "schema"


def reset_output(docs: Path) -> None:
    """Empty docs/ except docs/schema, which `python -m catalog schema` generates with xYang."""
    docs.mkdir(parents=True, exist_ok=True)
    for child in list(docs.iterdir()):
        if child.name == SCHEMA_DIR:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def copy_assets(docs: Path, asset_dir: Path) -> None:
    source = asset_dir / "datasheets"
    if not source.is_dir():
        return
    dest = docs / "datasheets"
    dest.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if item.is_file():
            shutil.copy2(item, dest / item.name)
    for name in ("styles.css", "search.js", "favicon.svg", "checkout.js", "fees.js"):
        shutil.copy2(TEMPLATES / name, docs / name)


def feedback_text(site: dict, ebay: dict) -> str:
    percentage = ebay.get("feedback_percentage")
    if percentage is not None and str(percentage) != "":
        number = float(percentage)
        shown = str(int(number)) if number == int(number) else str(number)
        score = ebay.get("feedback_score")
        label = f"{shown}% positive eBay feedback"
        if score not in (None, ""):
            label += f" ({score})"
        return label
    return site.get("ebay_feedback_label") or "eBay store"


def head(title: str, description: str, canonical: str, depth: int, og_type: str, extra: str = "", describedby: str = "") -> str:
    root = rel(depth)
    described = (
        f'<link rel="describedby" href="{escape(describedby)}" type="text/markdown">'
        if describedby
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en" data-root="{escape(root)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#1b4332">
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}">
<link rel="canonical" href="{escape(canonical)}">
{described}
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:url" content="{escape(canonical)}">
<meta property="og:type" content="{escape(og_type)}">
<meta property="og:site_name" content="33audio">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{escape(title)}">
<meta name="twitter:description" content="{escape(description)}">
<link rel="icon" href="{escape(rel(depth, 'favicon.svg'))}" type="image/svg+xml">
<link rel="stylesheet" href="{escape(rel(depth, 'styles.css'))}">
<script>
try {{
  var flow = localStorage.getItem("33audio-payment-flow");
  if (flow === "ebay" || flow === "stripe" || flow === "paypal") document.documentElement.setAttribute("data-payment-flow", flow);
}} catch (e) {{}}
</script>
{extra}
</head>
"""


def header(site: dict, depth: int, current: str) -> str:
    ebay = site["purchase"]["ebay"]["store_url"]
    items = [
        ("catalog/", "Catalog"),
        ("series/mm177/", "MM177"),
        ("series/mm215/", "MM215"),
        ("series/ms151/", "MS151"),
        ("series/ms176/", "MS176"),
    ]
    links = []
    for href, label in items:
        current_attr = ' aria-current="page"' if current == href else ""
        links.append(f'<a href="{escape(rel(depth, href))}"{current_attr}>{escape(label)}</a>')
    links.append(f'<a href="{escape(ebay)}">eBay</a>')
    return f"""<a class="skip" href="#content">Skip to content</a>
<header class="site-header">
  <div class="copper-rule"></div>
  <div class="wrap header-row">
    <a class="brand" href="{escape(rel(depth))}">33audio</a>
    <nav class="nav" aria-label="Primary">{''.join(links)}</nav>
  </div>
  <div class="wrap">
    <form class="search-form" action="{escape(rel(depth, 'catalog/'))}" method="get" role="search">
      <label class="search-label" for="site-q">Search by series, value, or part number</label>
      <div class="search-row">
        <input id="site-q" data-search-input name="q" type="search" placeholder="MM177 4.32K" enterkeyhint="search">
        <button type="submit">Search</button>
      </div>
    </form>
    <div class="payment-switch">
      <label class="payment-label" for="payment-flow">Checkout demo</label>
      <select id="payment-flow" data-payment-select>
        <option value="ebay">eBay</option>
        <option value="stripe">Stripe</option>
        <option value="paypal">PayPal</option>
      </select>
      <a href="{escape(rel(depth, 'fees/'))}">Selling costs</a>
    </div>
  </div>
</header>
"""


def footer(site: dict, catalog: dict, depth: int) -> str:
    listing = catalog["listing"]
    region = listing.get("region_note") or "USA orders only."
    source = catalog["source_url"]
    return f"""<footer class="site-footer">
  <div class="wrap">
    <p>33audio · {escape(site['location']['label'])} · {escape(site['email'])}</p>
    <p>{escape(region)} Catalog price ${escape(catalog['unit_price'])} each. {escape(site['shipping']['summary'])}. Mail order is a PayPal invoice from Mark. eBay prices and shipping are on the listing.</p>
    <p>Inventory is taken from the <a href="{escape(source)}">33audio Caddock listing</a>. {escape(catalog.get('legend') or '')}</p>
    <p><a href="{escape(rel(depth, 'fees/'))}">Selling costs</a> · <a href="{escape(rel(depth, 'catalog.md'))}">Catalog (Markdown)</a> · <a href="{escape(rel(depth, 'catalog.json'))}">Catalog (JSON)</a> · <a href="{escape(rel(depth, 'llms.txt'))}">llms.txt</a></p>
  </div>
</footer>
"""


def origin_of(canonical: str, rel_path: str) -> str:
    suffix = rel_path.strip("/")
    base = canonical.rstrip("/")
    if suffix and base.endswith(suffix):
        base = base[: -len(suffix)].rstrip("/")
    return base


def layout(title: str, description: str, canonical: str, rel_path: str, body: str, site: dict, catalog: dict, current: str, og_type: str = "website", extra_head: str = "", search: bool = False, extra_scripts: str = "") -> str:
    depth = depth_of(rel_path)
    script = f'<script src="{escape(rel(depth, "search.js"))}" defer></script>' if search else ""
    describedby = origin_of(canonical, rel_path) + "/llms.txt"
    return (
        head(title, description, canonical, depth, og_type, extra_head, describedby)
        + "<body>\n"
        + header(site, depth, current)
        + f'<main id="content" class="wrap">\n{body}\n</main>\n'
        + footer(site, catalog, depth)
        + f'<script src="{escape(rel(depth, "checkout.js"))}" defer></script>'
        + script
        + extra_scripts
        + "\n</body>\n</html>\n"
    )


def chips() -> str:
    buttons = ['<button type="button" data-series-chip="" aria-pressed="true">All</button>']
    for series in ("MM177", "MM215", "MS151", "MS176"):
        buttons.append(
            f'<button type="button" data-series-chip="{series}" aria-pressed="false">{series}</button>'
        )
    return '<div class="chips" role="group" aria-label="Filter by series">' + "".join(buttons) + "</div>"


def part_row(part: dict, href: str) -> str:
    label = resistance_label(part["resistance"])
    return (
        f'<a class="part-row" data-part-id="{escape(part["id"])}" href="{escape(href)}">'
        f'<span class="pid">{escape(part["id"])}</span>'
        f'<span class="meta">{escape(label)}</span>'
        f'<span class="meta">{escape(part["tolerance"])}</span>'
        f'<span class="meta">{part["quantity"]} listed</span>'
        f'<span class="meta">${escape(part["price"])}</span>'
        "</a>"
    )


def nrnd_html(site: dict, family: str) -> str:
    nrnd = site.get("nrnd") or {}
    if family not in nrnd.get("families", []):
        return ""
    return (
        '<aside class="note"><p>'
        + escape(nrnd["summary"])
        + f' <a href="{escape(nrnd["source_url"])}">{escape(nrnd["source_label"])}</a>.</p></aside>'
    )


def datasheet_link(site: dict, family: str, depth: int) -> str:
    sheet = site["datasheets"][family]
    return f'<p><a href="{escape(rel(depth, sheet["file"]))}">{escape(sheet["label"])}</a></p>'


def flow_button(flow: str, label: str, href: str | None, note: str) -> str:
    if href:
        control = (
            f'<a class="button primary" data-flow="{escape(flow)}" href="{escape(href)}">{escape(label)}</a>'
        )
    else:
        control = (
            f'<button type="button" class="button primary is-demo" data-flow="{escape(flow)}" disabled>'
            f'{escape(label)} <span class="demo-tag">demo, not yet active</span></button>'
        )
    return control + f'<p class="fine buy-note" data-flow="{escape(flow)}">{escape(note)}</p>'


def buy_html(decision: dict, part: dict, site: dict) -> str:
    stripe = configured_flow_url(site, part, "stripe")
    paypal = configured_flow_url(site, part, "paypal")
    stripe_label = (site.get("payment_flows") or {}).get("stripe", {}).get("label") or "Pay with Stripe"
    paypal_label = (site.get("payment_flows") or {}).get("paypal", {}).get("label") or "Pay with PayPal"
    controls = [
        flow_button("ebay", decision["primary_label"], decision["ebay_href"], decision["primary_note"]),
        flow_button(
            "stripe",
            stripe_label,
            stripe,
            "Opens the Stripe Payment Link for this part." if stripe else "No Stripe Payment Link is configured yet. This control is a demo, not a checkout.",
        ),
        flow_button(
            "paypal",
            paypal_label,
            paypal,
            "Opens the PayPal checkout link for this part." if paypal else "No PayPal checkout URL is configured yet. This control is a demo, not a checkout.",
        ),
        f'<a class="button secondary" href="{escape(decision["ask_href"])}">{escape(decision["ask_label"])}</a>',
    ]
    listing = decision.get("listing") or {}
    extra = ""
    if listing.get("title"):
        price = f' Listing price ${escape(str(listing["price"]))}.' if listing.get("price") else ""
        extra = f'<p class="fine">Matched eBay listing: {escape(listing["title"])}.{price}</p>'
    return f'<div class="buy">{"".join(controls)}</div>{extra}'


def fact_items(catalog: dict) -> str:
    listing = catalog["listing"]
    lines = [
        listing.get("temperature_line"),
        listing.get("origin_line"),
        listing.get("environment_line"),
        listing.get("provenance"),
    ]
    items = "".join(f"<li>{escape(line)}</li>" for line in lines if line)
    return f'<ul class="facts">{items}</ul>' if items else ""


def page_title(part: dict) -> str:
    stock = ", in stock" if part["quantity"] > 0 else ""
    return f"Caddock {part['id']} Micronox resistor, NOS{stock} | 33audio"


def page_description(part: dict, site: dict) -> str:
    label = resistance_label(part["resistance"])
    if part["quantity"] > 0:
        stock = f"{part['quantity']} in stock"
    else:
        stock = "ask about availability"
    return (
        f"NOS Caddock {part['id']}, {label}, {part['tolerance']} ({part['tolerance_code']}). "
        f"${part['price']}, {stock}. {site['location']['label']}. USA shipping. 33audio."
    )


def product_ld(part: dict, description: str, page_url: str, buy_url: str, site: dict, made_in_usa: bool) -> dict:
    availability = "https://schema.org/InStock" if part["quantity"] > 0 else "https://schema.org/OutOfStock"
    data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "@id": f"{page_url}#product",
        "name": f"Caddock {part['id']} Micronox resistor",
        "sku": part["id"],
        "mpn": part["id"],
        "brand": {"@type": "Brand", "name": "Caddock"},
        "description": description,
        "category": "Micronox film resistor",
        "url": page_url,
        "additionalProperty": [
            {"@type": "PropertyValue", "name": "Resistance", "value": resistance_label(part["resistance"])},
            {"@type": "PropertyValue", "name": "Tolerance", "value": part["tolerance"]},
            {"@type": "PropertyValue", "name": "Quantity listed", "value": part["quantity"]},
        ],
        "offers": {
            "@type": "Offer",
            "url": page_url,
            "priceCurrency": "USD",
            "price": part["price"],
            "availability": availability,
            "itemCondition": "https://schema.org/NewCondition",
            "areaServed": "US",
            "seller": {
                "@type": "Organization",
                "name": site["name"],
                "email": site["email"],
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": site["location"]["locality"],
                    "addressRegion": site["location"]["region"],
                    "addressCountry": site["location"]["country"],
                },
            },
            "shippingDetails": {
                "@type": "OfferShippingDetails",
                "shippingRate": {
                    "@type": "MonetaryAmount",
                    "value": site["shipping"]["amount"],
                    "currency": site["shipping"]["currency"],
                },
                "shippingDestination": {"@type": "DefinedRegion", "addressCountry": "US"},
            },
        },
        "potentialAction": {"@type": "BuyAction", "target": buy_url},
    }
    if made_in_usa:
        data["countryOfOrigin"] = "US"
    return data


def breadcrumb_ld(origin: str, series: dict, part: dict) -> dict:
    series_path = f"series/{series['id'].lower()}/"
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "33audio", "item": abs_url(origin, "")},
            {"@type": "ListItem", "position": 2, "name": series["id"], "item": abs_url(origin, series_path)},
            {"@type": "ListItem", "position": 3, "name": part["id"], "item": abs_url(origin, f"parts/{part['id'].lower()}/")},
        ],
    }


def render_home(catalog: dict, site: dict, ebay: dict, origin: str) -> str:
    listing = catalog["listing"]
    count = sum(len(series["parts"]) for series in catalog["series"])
    cards = []
    for series in catalog["series"]:
        ordered = sorted(series["parts"], key=lambda part: float(part["ohms"]))
        span = f"{resistance_label(ordered[0]['resistance'])} to {resistance_label(ordered[-1]['resistance'])}"
        note = series["default_note"] or f"{series['default_tolerance']} unless noted"
        cards.append(
            f'<a class="series-card" href="{escape(rel(0, "series/" + series["id"].lower() + "/"))}">'
            f'<strong>{escape(series["id"])}</strong>'
            f'<span>{len(series["parts"])} values · {escape(span)}</span><br>'
            f'<span class="muted">{escape(note)}</span></a>'
        )
    lede = listing.get("provenance") or listing.get("product_line") or "NOS Caddock Micronox film resistors."
    payment = listing.get("payment_note") or "Email Mark for a PayPal invoice."
    title = "Caddock Micronox resistors, NOS | 33audio"
    description = (
        f"NOS Caddock MM177, MM215, MS151, and MS176 Micronox film resistors. "
        f"${catalog['unit_price']} each, in stock in {site['location']['label']}. USA shipping from 33audio."
    )
    store = site["purchase"]["ebay"]["store_url"]
    org = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Organization",
                "name": site["name"],
                "email": site["email"],
                "url": abs_url(origin, ""),
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": site["location"]["locality"],
                    "addressRegion": site["location"]["region"],
                    "addressCountry": site["location"]["country"],
                },
                "sameAs": [store],
            },
            {"@type": "WebSite", "name": "33audio", "url": abs_url(origin, "")},
        ],
    }
    body = f"""
<p class="eyebrow">{escape(site['location']['label'])} · USA stock · NOS</p>
<h1>Caddock Micronox film resistors</h1>
<p class="lede">{escape(lede)}</p>
<ul class="terms">
  <li><strong>${escape(catalog['unit_price'])}</strong>&nbsp;each</li>
  <li><strong>${escape(site['shipping']['amount'])}</strong>&nbsp;flat shipping, any quantity</li>
  <li>USA only</li>
  <li>{count} values</li>
</ul>
<p class="search-status" data-search-status aria-live="polite"></p>
{chips()}
<div data-search-live hidden></div>
<div class="series-grid">{''.join(cards)}</div>
<h2>Ordering</h2>
<p>Buy on eBay from the <a href="{escape(store)}">33audio store</a> ({escape(feedback_text(site, ebay))}). Each part page opens a matched listing when the eBay sync has one, or a search of that store. The checkout demo menu switches that Buy button to Stripe or PayPal when you want to compare. {escape(payment)} The catalog price is ${escape(catalog['unit_price'])} each. {escape(site['shipping']['summary'])}. <a href="{escape(rel(0, 'fees/'))}">Selling costs</a> compares the published fees.</p>
{nrnd_html(site, 'MM')}
{fact_items(catalog)}
"""
    extra = f'<script type="application/ld+json">{json_ld(org)}</script>'
    return layout(title, description, abs_url(origin, ""), "index.html", body, site, catalog, "", extra_head=extra, search=True)


def render_catalog(catalog: dict, site: dict, origin: str) -> str:
    rows = []
    for series in catalog["series"]:
        for part in series["parts"]:
            href = rel(1, f"parts/{part['id'].lower()}/")
            rows.append(part_row(part, href))
    count = len(rows)
    title = "Caddock resistor catalog | 33audio"
    description = f"Search {count} NOS Caddock Micronox resistor values stocked by 33audio in {site['location']['label']}."
    body = f"""
<p class="eyebrow">All values</p>
<h1>Catalog</h1>
<p class="search-status" data-search-status aria-live="polite">{count} parts</p>
{chips()}
<p data-search-empty hidden>No parts match. Try a series and a value, such as MM177 4.32K.</p>
<div class="part-list" data-search-list>{''.join(rows)}</div>
"""
    return layout(title, description, abs_url(origin, "catalog/"), "catalog/index.html", body, site, catalog, "catalog/", search=True)


def render_series(series: dict, catalog: dict, site: dict, origin: str) -> str:
    path = f"series/{series['id'].lower()}/"
    depth = depth_of(path + "index.html")
    rows = [part_row(part, rel(depth, f"parts/{part['id'].lower()}/")) for part in series["parts"]]
    ordered = sorted(series["parts"], key=lambda part: float(part["ohms"]))
    span = f"{resistance_label(ordered[0]['resistance'])} to {resistance_label(ordered[-1]['resistance'])}"
    title = f"Caddock {series['id']} Micronox resistors, NOS | 33audio"
    description = (
        f"{len(series['parts'])} NOS Caddock {series['id']} Micronox resistors, "
        f"{series['default_note']}. ${catalog['unit_price']} each from 33audio in {site['location']['label']}."
    )
    elements = []
    for index, part in enumerate(series["parts"], start=1):
        elements.append(
            {
                "@type": "ListItem",
                "position": index,
                "name": part["id"],
                "url": abs_url(origin, f"parts/{part['id'].lower()}/"),
            }
        )
    item_list = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": f"Caddock {series['id']} Micronox resistors",
        "numberOfItems": len(series["parts"]),
        "itemListElement": elements,
    }
    body = f"""
<p class="eyebrow">Caddock {escape(series['family'])} · Micronox film</p>
<h1>{escape(series['id'])}</h1>
<p>{len(series['parts'])} values · {escape(span)} · {escape(series['default_note'] or series['default_tolerance'])}</p>
{nrnd_html(site, series['family'])}
{datasheet_link(site, series['family'], depth)}
<div class="part-list">{''.join(rows)}</div>
"""
    extra = f'<script type="application/ld+json">{json_ld(item_list)}</script>'
    return layout(title, description, abs_url(origin, path), path + "index.html", body, site, catalog, path, extra_head=extra)


def tolerance_sentence(series: dict, part: dict) -> str:
    if part["tolerance_explicit"]:
        return f"{part['tolerance']} ({part['tolerance_code']}), as marked on the list"
    return f"{part['tolerance']} ({part['tolerance_code']}), the {series['id']} default"


def render_part(series: dict, part: dict, decision: dict, catalog: dict, site: dict, origin: str) -> str:
    path = f"parts/{part['id'].lower()}/"
    depth = depth_of(path + "index.html")
    title = page_title(part)
    description = page_description(part, site)
    label = resistance_label(part["resistance"])
    page_url = abs_url(origin, path)
    made = bool(catalog["listing"].get("origin_line"))
    pairs = faq_pairs(series, part, catalog, site)
    faq_html = "".join(
        f"<details><summary>{escape(question)}</summary><p>{escape(answer)}</p></details>"
        for question, answer in pairs
    )
    scripts = (
        f'<script type="application/ld+json">{json_ld(product_ld(part, description, page_url, decision["primary_href"], site, made))}</script>'
        f'<script type="application/ld+json">{json_ld(ontology_json_ld(part, catalog.get("currency", "USD"), origin, decision.get("listing")))}</script>'
        f'<script type="application/ld+json">{json_ld(faq_json_ld(pairs))}</script>'
        f'<script type="application/ld+json">{json_ld(breadcrumb_ld(origin, series, part))}</script>'
    )
    others = []
    for sibling in series["parts"]:
        if sibling["id"] == part["id"]:
            continue
        others.append(
            f'<a href="{escape(rel(depth, "parts/" + sibling["id"].lower() + "/"))}">{escape(sibling["id"])}</a>'
        )
    stock = "In stock" if part["quantity"] > 0 else "Ask about availability"
    provenance = catalog["listing"].get("provenance") or ""
    body = f"""
<nav class="crumbs" aria-label="Breadcrumb">
  <a href="{escape(rel(depth))}">Home</a> /
  <a href="{escape(rel(depth, 'series/' + series['id'].lower() + '/'))}">{escape(series['id'])}</a> /
  <span>{escape(part['id'])}</span>
</nav>
<p class="eyebrow">Caddock {escape(series['id'])} · Micronox film · NOS</p>
<h1 class="part">{escape(part['id'])}</h1>
<p class="lede">{escape(label)} · {escape(part['tolerance'])} ({escape(part['tolerance_code'])})</p>
<p class="summary">{escape(part_summary(part, site, catalog['listing']))}</p>
{buy_html(decision, part, site)}
<dl class="spec">
  <div><dt>Resistance</dt><dd>{escape(label)} <span class="muted">({escape(part['resistance'])})</span></dd></div>
  <div><dt>Tolerance</dt><dd>{escape(tolerance_sentence(series, part))}</dd></div>
  <div><dt>Quantity listed</dt><dd>{part['quantity']} · {stock}</dd></div>
  <div><dt>Catalog price</dt><dd>${escape(part['price'])} each</dd></div>
  <div><dt>Shipping</dt><dd>{escape(site['shipping']['summary'])}</dd></div>
  <div><dt>Seller</dt><dd>33audio, {escape(site['location']['label'])}</dd></div>
</dl>
{nrnd_html(site, series['family'])}
<p>{escape(provenance)}</p>
{datasheet_link(site, series['family'], depth)}
<h2>Questions</h2>
<div class="faq">{faq_html}</div>
<h2>Other {escape(series['id'])} values</h2>
<p class="related">{''.join(others)}</p>
"""
    return layout(title, description, page_url, path + "index.html", body, site, catalog, "", og_type="product", extra_head=scripts)


def render_fees(catalog: dict, site: dict, origin: str) -> str:
    costs = site["selling_costs"]
    example = costs["example"]
    totals = estimate(
        to_cents(example["item_price"]),
        to_cents(example["shipping"]),
        int(example["quantity"]),
        costs,
    )
    buyer = from_cents(totals["total_cents"])
    cards = [
        ("eBay", totals["ebay_cents"], costs["ebay"]["category_note"], costs["ebay"]["source_url"], costs["ebay"]["source_label"]),
        ("Stripe", totals["stripe_cents"], costs["stripe"]["note"], costs["stripe"]["source_url"], costs["stripe"]["source_label"]),
        ("PayPal Checkout", totals["paypal_cents"], costs["paypal"]["note"], costs["paypal"]["source_url"], costs["paypal"]["source_label"]),
    ]
    card_html = []
    for name, fee, note, url, label in cards:
        kept = from_cents(totals["total_cents"] - fee)
        card_html.append(
            f'<article class="fee-card"><h2>{escape(name)}</h2>'
            f'<p class="fee-amount">${escape(from_cents(fee))}</p>'
            f'<p>Fee on ${escape(buyer)}. About ${escape(kept)} remains after this fee, before postage the seller pays the carrier.</p>'
            f'<p class="fine">{escape(note)} <a href="{escape(url)}">{escape(label)}</a>. Checked {escape(costs["checked_on"])}.</p></article>'
        )
    payload = {
        "ebay": {key: costs["ebay"][key] for key in (
            "final_value_percent", "cap", "above_cap_percent", "order_threshold",
            "per_order_fee_at_or_under_threshold", "per_order_fee_over_threshold",
        )},
        "stripe": {"percent": costs["stripe"]["percent"], "fixed": costs["stripe"]["fixed"]},
        "paypal": {"percent": costs["paypal"]["percent"], "fixed": costs["paypal"]["fixed"]},
    }
    paypal_updated = costs["paypal"].get("page_updated")
    updated = f" PayPal's page says it was last updated {paypal_updated}." if paypal_updated else ""
    title = "Selling costs for a $10 Caddock resistor | 33audio"
    description = (
        f"Compare published US fees for a ${example['item_price']} part plus "
        f"${example['shipping']} shipping: eBay, Stripe, and PayPal Checkout."
    )
    body = f"""
<p class="eyebrow">Demo comparison · checked {escape(costs['checked_on'])}</p>
<h1>Selling costs</h1>
<p class="lede">What a published US fee schedule would take from a ${escape(example['item_price'])} resistor plus ${escape(example['shipping'])} shipping. This is not a quote for 33audio's account.</p>
<p>Buyer pays <strong>${escape(buyer)}</strong> in this example. Quantity is {int(example['quantity'])}. Sales tax is left out. eBay's fee base includes sales tax when eBay collects it.</p>
<div class="fee-grid">{''.join(card_html)}</div>
<h2>Calculator</h2>
<p>Shipping here is entered once per order, matching 33audio's flat rate. The eBay $7,500 step is published as calculated per item; this calculator applies it to the order total, which is exact for a one-item order.</p>
<form class="calc" data-fee-form>
  <label>Item price, USD <input name="price" type="number" min="0" step="0.01" value="{escape(example['item_price'])}" inputmode="decimal"></label>
  <label>Shipping, USD <input name="shipping" type="number" min="0" step="0.01" value="{escape(example['shipping'])}" inputmode="decimal"></label>
  <label>Quantity <input name="quantity" type="number" min="1" step="1" value="{int(example['quantity'])}"></label>
</form>
<dl class="spec" data-fee-result></dl>
<h2>Sources</h2>
<ul class="facts">
  <li><a href="{escape(costs['ebay']['source_url'])}">{escape(costs['ebay']['source_label'])}</a>. Most categories without a Store: {escape(costs['ebay']['final_value_percent'])}% up to ${escape(costs['ebay']['cap'])}, then {escape(costs['ebay']['above_cap_percent'])}%. Per order ${escape(costs['ebay']['per_order_fee_at_or_under_threshold'])} at or under ${escape(costs['ebay']['order_threshold'])}, ${escape(costs['ebay']['per_order_fee_over_threshold'])} over that. Checked {escape(costs['ebay']['checked_on'])}.</li>
  <li><a href="{escape(costs['stripe']['source_url'])}">{escape(costs['stripe']['source_label'])}</a>. {escape(costs['stripe']['percent'])}% + ${escape(costs['stripe']['fixed'])} per successful domestic card charge. Checked {escape(costs['stripe']['checked_on'])}.</li>
  <li><a href="{escape(costs['paypal']['source_url'])}">{escape(costs['paypal']['source_label'])}</a>. PayPal Checkout {escape(costs['paypal']['percent'])}% + ${escape(costs['paypal']['fixed'])} for a domestic USD payment.{escape(updated)} Checked {escape(costs['paypal']['checked_on'])}.</li>
</ul>
""" + '<script type="application/json" id="fee-rates">' + json_ld(payload) + "</script>\n"
    script = '<script src="../fees.js" defer></script>'
    return layout(
        title, description, abs_url(origin, "fees/"), "fees/index.html", body,
        site, catalog, "fees/", extra_scripts=script,
    )


def write_search_index(docs: Path, parts: list[dict]) -> None:
    payload = {
        "parts": [
            {
                "id": part["id"],
                "series": part["series"],
                "resistance": part["resistance"],
                "label": resistance_label(part["resistance"]),
                "tolerance": part["tolerance"],
                "quantity": part["quantity"],
                "price": part["price"],
                "url": f"parts/{part['id'].lower()}/",
                "search": search_blob(part),
            }
            for part in parts
        ]
    }
    (docs / "search.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_sitemap(docs: Path, origin: str, paths: list[str], modified: str | None) -> None:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path in paths:
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(abs_url(origin, path))}</loc>")
        if modified:
            lines.append(f"    <lastmod>{modified}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    (docs / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_robots(docs: Path, origin: str) -> None:
    (docs / "robots.txt").write_text(render_robots(origin), encoding="utf-8")


def validate(docs: Path, catalog: dict, site: dict, origin: str) -> None:
    errors = []
    if site.get("custom_domain"):
        if (docs / "CNAME").read_text(encoding="utf-8").strip() != str(site["custom_domain"]).strip():
            errors.append("CNAME missing for custom_domain")
    elif (docs / "CNAME").exists():
        errors.append("CNAME should not be published while custom_domain is unset")
    parts = flatten(catalog)
    html_files = list(docs.rglob("*.html"))
    titles = []
    descriptions = []
    for html_path in html_files:
        text = html_path.read_text(encoding="utf-8")
        if 'name="viewport" content="width=device-width, initial-scale=1"' not in text:
            errors.append(f"missing viewport: {html_path.name}")
        title_match = re.search(r"<title>(.*?)</title>", text)
        desc_match = re.search(r'<meta name="description" content="(.*?)">', text)
        if not title_match or not desc_match:
            errors.append(f"missing title or description: {html_path}")
            continue
        titles.append(title_match.group(1))
        descriptions.append(desc_match.group(1))
        if "http://" in text and "http://www.sitemaps.org" not in text and "http://www.w3.org" not in text:
            if re.search(r"<script[^>]+src=[\"']https?://", text):
                errors.append(f"external script: {html_path}")
    if len(titles) != len(set(titles)):
        errors.append("duplicate titles")
    if len(descriptions) != len(set(descriptions)):
        errors.append("duplicate meta descriptions")
    for part in parts:
        page = docs / "parts" / part["id"].lower() / "index.html"
        if not page.exists():
            errors.append(f"missing page {part['id']}")
            continue
        text = page.read_text(encoding="utf-8")
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', text)
        parsed = [json.loads(block) for block in blocks]
        product = next((item for item in parsed if item.get("@type") == "Product"), None)
        if not product:
            errors.append(f"no Product JSON-LD for {part['id']}")
            continue
        offer = product.get("offers") or {}
        if offer.get("@type") != "Offer" or offer.get("price") != part["price"] or offer.get("priceCurrency") != "USD":
            errors.append(f"bad Offer for {part['id']}")
        if "schema.org" not in str(offer.get("availability")):
            errors.append(f"bad availability for {part['id']}")
        if site["purchase"]["mode"] == "ebay":
            primary = re.search(r'data-flow="ebay" href="([^"]+)"', text)
            if not primary or "ebay.com" not in primary.group(1):
                errors.append(f"primary buy is not eBay for {part['id']}")
        if not configured_flow_url(site, part, "stripe") and "demo, not yet active" not in text:
            errors.append(f"missing Stripe demo state for {part['id']}")
        if f"mailto:{site['email']}" not in text:
            errors.append(f"missing ask link for {part['id']}")
        if part["id"] not in text:
            errors.append(f"part id missing in page {part['id']}")
    sitemap = ET.fromstring((docs / "sitemap.xml").read_text(encoding="utf-8"))
    locs = [node.text for node in sitemap.iter() if node.tag.endswith("loc")]
    if len(locs) != len(set(locs)):
        errors.append("duplicate sitemap URLs")
    expected = 7 + len(catalog["series"]) + len(parts)
    robots_text = (docs / "robots.txt").read_text(encoding="utf-8")
    for bot in (
        "GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot",
        "PerplexityBot", "Google-Extended", "Applebot-Extended", "Bingbot",
    ):
        if f"User-agent: {bot}\nAllow: /" not in robots_text:
            errors.append(f"robots.txt does not allow {bot}")
    if not (docs / "llms.txt").is_file() or not (docs / "llms-full.txt").is_file():
        errors.append("llms.txt files missing")
    if not (docs / "catalog.md").is_file() or not (docs / "catalog.json").is_file():
        errors.append("machine-readable catalog missing")
    if len(locs) != expected:
        errors.append(f"sitemap has {len(locs)} URLs, expected {expected}")
    if not all(loc and loc.startswith(origin) for loc in locs):
        errors.append("sitemap loc is not canonical")
    robots = (docs / "robots.txt").read_text(encoding="utf-8")
    if abs_url(origin, "sitemap.xml") not in robots:
        errors.append("robots.txt missing sitemap")
    index = json.loads((docs / "search.json").read_text(encoding="utf-8"))
    if len(index.get("parts") or []) != len(parts):
        errors.append("search index size does not match the catalog")
    if errors:
        raise SystemExit("Site validation failed:\n- " + "\n- ".join(errors))


def build(catalog: dict, ebay: dict, site: dict, docs: Path, asset_dir: Path) -> None:
    reset_output(docs)
    copy_assets(docs, asset_dir)
    origin = public_origin(site)
    if site.get("custom_domain"):
        (docs / "CNAME").write_text(str(site["custom_domain"]).strip() + "\n", encoding="utf-8")
    matches = match_listings(catalog, ebay.get("listings") or [])
    parts = flatten(catalog)
    paths = ["", "catalog/", "fees/", "llms.txt", "llms-full.txt", "catalog.md", "catalog.json"]
    (docs / "llms.txt").write_text(render_llms_txt(catalog, site, origin), encoding="utf-8")
    (docs / "llms-full.txt").write_text(render_llms_full(catalog, site, origin), encoding="utf-8")
    (docs / "catalog.md").write_text(render_catalog_md(catalog, site, origin), encoding="utf-8")
    (docs / "catalog.json").write_text(render_catalog_json(catalog, site, origin, matches), encoding="utf-8")
    fees_page = docs / "fees" / "index.html"
    fees_page.parent.mkdir(parents=True, exist_ok=True)
    fees_page.write_text(render_fees(catalog, site, origin), encoding="utf-8")
    (docs / "index.html").write_text(render_home(catalog, site, ebay, origin), encoding="utf-8")
    (docs / "catalog").mkdir(parents=True, exist_ok=True)
    (docs / "catalog" / "index.html").write_text(render_catalog(catalog, site, origin), encoding="utf-8")
    for series in catalog["series"]:
        path = f"series/{series['id'].lower()}/"
        paths.append(path)
        page = docs / "series" / series["id"].lower() / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(render_series(series, catalog, site, origin), encoding="utf-8")
        for part in series["parts"]:
            enriched = {**part, "series": series["id"], "family": series["family"]}
            decision = resolve_purchase(enriched, matches.get(part["id"]), site)
            part_path = f"parts/{part['id'].lower()}/"
            paths.append(part_path)
            part_page = docs / "parts" / part["id"].lower() / "index.html"
            part_page.parent.mkdir(parents=True, exist_ok=True)
            part_page.write_text(render_part(series, enriched, decision, catalog, site, origin), encoding="utf-8")
    write_search_index(docs, parts)
    write_sitemap(docs, origin, paths, lastmod(catalog))
    write_robots(docs, origin)
    (docs / ".nojekyll").write_bytes(b"")
    validate(docs, catalog, site, origin)


def load_json(path: Path, default: dict | None = None) -> dict:
    if not path.exists():
        if default is None:
            raise SystemExit(f"Missing {path}")
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the 33audio static catalog into docs/")
    parser.add_argument("--catalog", default=str(DATA / "catalog.json"))
    parser.add_argument("--site", default=str(DATA / "site.json"))
    parser.add_argument("--ebay", default=str(DATA / "ebay.json"))
    parser.add_argument("--docs", default=str(DOCS))
    parser.add_argument("--assets", default=str(ASSETS))
    args = parser.parse_args(argv)
    catalog = load_json(Path(args.catalog))
    site = load_json(Path(args.site))
    ebay = load_json(
        Path(args.ebay),
        {
            "seller": site["purchase"]["ebay"]["seller"],
            "store_url": site["purchase"]["ebay"]["store_url"],
            "listings": [],
        },
    )
    build(catalog, ebay, site, Path(args.docs), Path(args.assets))
    count = sum(len(series["parts"]) for series in catalog["series"])
    print(f"Built {count} part pages in {args.docs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
