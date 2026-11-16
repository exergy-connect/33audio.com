"""LLM-oriented catalog files: llms.txt, catalog.md, and catalog.json."""

from __future__ import annotations

import json
from decimal import Decimal

from catalog.purchase import flatten, resistance_label

AI_CRAWLERS = (
    "GPTBot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "ClaudeBot",
    "Claude-SearchBot",
    "PerplexityBot",
    "Google-Extended",
    "Applebot-Extended",
    "Bingbot",
)


def provenance_text(listing: dict) -> str:
    kept = []
    for line in listing.get("statements") or []:
        low = line.lower()
        if "liquidation stock" in low or "distributor that closed" in low:
            kept.append(line.strip().rstrip("."))
    if kept:
        return " ".join(kept) + "."
    text = (listing.get("provenance") or "").strip()
    return text if text.endswith(".") or not text else text + "."


def part_summary(part: dict, site: dict, listing: dict) -> str:
    """Same facts, without the awkward 'NOS these resistors...' splice."""
    label = resistance_label(part["resistance"])
    origin = provenance_text(listing).rstrip(".")
    nos = f"It is NOS: {origin[0].lower() + origin[1:]}." if origin else "33audio lists it as NOS stock."
    return (
        f"Caddock {part['id']} is a {label} Type {part['series']} Micronox film resistor. "
        f"{nos} "
        f"The source catalog price is ${part['price']}; ask about availability and current pricing in {site['location']['label']}."
    )


def faq_pairs(series: dict, part: dict, catalog: dict, site: dict) -> list[tuple[str, str]]:
    listing = catalog["listing"]
    summary = part_summary(part, site, listing)
    mm_note = site.get("nrnd", {}).get("summary", "")
    temp = listing.get("temperature_line") or "Temperature range to 275°C max"
    uses = (
        "The 1985 Caddock datasheet scans linked from this site describe these Micronox film "
        "resistors for high-temperature work in geophysical, industrial, aerospace, and military "
        "equipment, and the 33audio listing calls them ideal for harsh environments. "
        f"{temp}. Buyers also use exact NOS values to repair equipment that already has a "
        "Caddock MM or MS resistor in it. This catalog does not name a particular amplifier or speaker."
    )
    mm_vs_ms = (
        "Type MM, including MM177 and MM215, is Caddock's precision film series in a molded body. "
        "Type MS, including MS151 and MS176, is the power film series with a silicone conformal coating. "
        "Both use Micronox film. "
        + (mm_note + " " if mm_note else "")
        + "Those distinctions are on the 1985 datasheet scans and on Caddock's current Type MM datasheet."
    )
    nos = (
        "On this site, NOS means the liquidation stock described by 33audio: "
        + provenance_text(listing)
        + " It is not a claim that Caddock still recommends the part for a new design."
    )
    return [
        (f"What is {part['id']}?", summary),
        ("What is the difference between Caddock Type MM and Type MS?", mm_vs_ms),
        ("What does NOS mean for these resistors?", nos),
        ("What are these Caddock resistors used for?", uses),
    ]


def faq_json_ld(pairs: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {"@type": "Answer", "text": answer},
            }
            for question, answer in pairs
        ],
    }


def _series_blurb(series: dict) -> str:
    note = series.get("default_note") or series.get("default_tolerance") or ""
    return f"{len(series['parts'])} values, {note}".strip().rstrip(",")


def render_llms_txt(catalog: dict, site: dict, origin: str) -> str:
    listing = catalog["listing"]
    store = site["purchase"]["ebay"]["store_url"]
    lines = [
        f"# {site['name']}",
        "",
        (
            f"> {site['name']} in {site['location']['label']} sells NOS Caddock Micronox film resistors "
            f"in the MM177, MM215, MS151, and MS176 series. "
            f"{provenance_text(listing)} "
            f"Price is ${catalog['unit_price']} each. "
            f"{site['shipping']['summary']}. "
            f"{listing.get('region_note') or 'USA orders only.'}"
        ),
        "",
        (
            f"Seller: {site['seller_name']} ({site['email']}). "
            f"eBay store: {store}. "
            f"{listing.get('product_line') or 'Caddock high performance film resistors'}. "
            f"{listing.get('temperature_line') or ''} "
            f"{listing.get('origin_line') or ''} "
            f"{listing.get('environment_line') or ''}"
        ).strip(),
        "",
        site.get("nrnd", {}).get("summary", ""),
        "",
        "Caddock catalog quantities and prices are reference data, not confirmed offers or eBay availability. Ask Mark to confirm availability. eBay listings are a separate selection.",
        f"- [eBay listings]({origin}/ebay/): Synced listings with their own prices and direct purchase links",
        "## Catalog files",
        "",
        f"- [All parts (Markdown)]({origin}/catalog.md): Table of every value, tolerance, quantity, and price",
        f"- [All parts (JSON)]({origin}/catalog.json): The same catalog as JSON",
        f"- [Full text for agents]({origin}/llms-full.txt): One summary sentence per part, plus the shared FAQ",
        f"- [Catalog vocabulary]({origin}/schema/README.md): Every field of catalog.json with its schema.org and Wikidata mapping",
        f"- [Catalog JSON Schema]({origin}/schema/catalog.schema.json): JSON Schema 2020-12 generated by xYang from the YANG model",
        f"- [Catalog JSON-LD context]({origin}/schema/context.jsonld): Maps catalog.json keys to schema.org and the c33 vocabulary",
        "",
        "## Series",
        "",
    ]
    for series in catalog["series"]:
        url = f"{origin}/series/{series['id'].lower()}/"
        lines.append(f"- [{series['id']}]({url}): {_series_blurb(series)}")
    lines += ["", "## Parts", ""]
    for part in flatten(catalog):
        url = f"{origin}/parts/{part['id'].lower()}/"
        qty = f"{part['quantity']} listed" if part["quantity"] else "ask about availability"
        lines.append(
            f"- [{part['id']}]({url}): {resistance_label(part['resistance'])}, "
            f"{part['tolerance']} ({part['tolerance_code']}), {qty}, ${part['price']}"
        )
    lines += [
        "",
        "## Optional",
        "",
        f"- [Selling costs]({origin}/fees/): Published US fee comparison for eBay, Stripe, and PayPal",
        f"- [eBay store]({store}): 33audio listings on eBay",
        f"- [Type MM datasheet scan]({origin}/datasheets/mmdata85.jpg): EEM 1985 scan hosted by 33audio",
        f"- [Type MS datasheet scan]({origin}/datasheets/msdata85.jpg): EEM 1985 scan hosted by 33audio",
        f"- [Caddock Type MM datasheet]({site.get('nrnd', {}).get('source_url', '')}): Current Caddock PDF, Type MM not recommended for new designs",
        "",
    ]
    return "\n".join(line for line in lines if line is not None).rstrip() + "\n"


def render_llms_full(catalog: dict, site: dict, origin: str) -> str:
    listing = catalog["listing"]
    chunks = [
        render_llms_txt(catalog, site, origin).rstrip(),
        "",
        "## Part summaries",
        "",
    ]
    for series in catalog["series"]:
        for part in series["parts"]:
            enriched = {**part, "series": series["id"]}
            chunks.append(part_summary(enriched, site, listing))
            chunks.append("")
    sample = catalog["series"][0]
    sample_part = {**sample["parts"][0], "series": sample["id"]}
    chunks.append("## FAQ")
    chunks.append("")
    for question, answer in faq_pairs(sample, sample_part, catalog, site):
        chunks.append(f"### {question}")
        chunks.append("")
        chunks.append(answer)
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n"


def render_catalog_md(catalog: dict, site: dict, origin: str) -> str:
    lines = [
        "# 33audio Caddock resistor catalog",
        "",
        (
            f"{provenance_text(catalog['listing'])} "
            f"${catalog['unit_price']} each. {site['shipping']['summary']}. "
            f"Ships from {site['location']['label']}. "
            f"{catalog['listing'].get('region_note') or 'USA orders only.'}"
        ),
        "",
        "Reference quantities and prices from the Caddock source catalog; ask Mark to confirm availability. These are not eBay offers. Shop eBay listings separately at " + origin + "/ebay/.",
        "",
        "| Part | Series | Value | Tolerance | Source quantity | Source price | Page |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for part in flatten(catalog):
        page = f"{origin}/parts/{part['id'].lower()}/"
        lines.append(
            f"| {part['id']} | {part['series']} | {resistance_label(part['resistance'])} "
            f"| {part['tolerance']} ({part['tolerance_code']}) | {part['quantity']} "
            f"| ${part['price']} | {page} |"
        )
    lines.append("")
    return "\n".join(lines)


def _decimal(value: float | int | str) -> str:
    return format(Decimal(str(value)).normalize(), "f")


def part_record(part: dict, currency: str, origin: str, ebay_listing: dict | None = None) -> dict:
    """One entry of /parts in model/audio33-catalog.yang."""
    row = {
        "part_number": part["id"],
        "manufacturer": "Caddock",
        "series": part["series"],
        "resistance": {
            "value": _decimal(part["ohms"]),
            "unit": "ohm",
            "label": resistance_label(part["resistance"]),
        },
        "tolerance": {
            "percent": _decimal(part["tolerance"].rstrip("%")),
            "code": part["tolerance_code"],
        },
        "condition": "new-old-stock",
        "quantity": part["quantity"],
        "price": part["price"],
        "currency": currency,
        "url": f"{origin}/parts/{part['id'].lower()}/",
    }
    if (ebay_listing or {}).get("url"):
        row["ebay_listing"] = ebay_listing["url"]
    return row


def ontology_json_ld(part: dict, currency: str, origin: str, ebay_listing: dict | None = None) -> dict:
    """Part page JSON-LD in the catalog vocabulary, describing the same node as the schema.org Product."""
    record = part_record(part, currency, origin, ebay_listing)
    return {
        "@context": f"{origin}/schema/context.jsonld",
        "@id": f"{origin}/catalog.json",
        "parts": [{"@id": f"{record['url']}#product", **record}],
    }


def catalog_document(catalog: dict, site: dict, origin: str, ebay_matches: dict | None = None) -> dict:
    """The public catalog in the shape of model/audio33-catalog.yang (RFC 7951 JSON)."""
    ebay_matches = ebay_matches or {}
    currency = catalog.get("currency", "USD")
    nrnd_families = set(site.get("nrnd", {}).get("families") or [])
    specs = site.get("series_specs") or {}
    series_rows = []
    for series in catalog["series"]:
        spec = specs.get(series["id"], {})
        row = {
            "name": series["id"],
            "family": series["family"],
            "product_line": spec.get("product_line", f"Caddock Type {series['family']}"),
            "film": "Micronox",
            "default_tolerance": series["default_tolerance_code"],
            "not_recommended_for_new_designs": series["family"] in nrnd_families,
        }
        if spec.get("power_rating") is not None:
            row["power_rating"] = _decimal(spec["power_rating"])
        if spec.get("voltage_rating") is not None:
            row["voltage_rating"] = int(spec["voltage_rating"])
        if spec.get("datasheet"):
            row["datasheet"] = spec["datasheet"]
        series_rows.append(row)
    parts = [part_record(part, currency, origin, ebay_matches.get(part["id"])) for part in flatten(catalog)]
    document = {
        "$schema": f"{origin}/schema/catalog.schema.json",
        "@context": f"{origin}/schema/context.jsonld",
        "currency": currency,
        "unit_price": catalog["unit_price"],
        "region_note": catalog["listing"].get("region_note"),
        "provenance": provenance_text(catalog["listing"]),
        "source_url": catalog.get("source_url"),
        "seller": {
            "name": site["name"],
            "email": site["email"],
            "locality": site["location"]["locality"],
            "region": site["location"]["region"],
            "country": site["location"]["country"],
            "ebay_store": site["purchase"]["ebay"]["store_url"],
            "ebay_seller": site["purchase"]["ebay"]["seller"],
        },
        "shipping": {
            "amount": site["shipping"]["amount"],
            "currency": site["shipping"]["currency"],
            "per": "order",
            "country": site["location"]["country"],
            "summary": site["shipping"]["summary"],
        },
        "series": series_rows,
        "parts": parts,
    }
    return {key: value for key, value in document.items() if value is not None}


def render_catalog_json(catalog: dict, site: dict, origin: str, ebay_matches: dict | None = None) -> str:
    return json.dumps(catalog_document(catalog, site, origin, ebay_matches), indent=2, ensure_ascii=False) + "\n"


def render_robots(origin: str) -> str:
    blocks = ["User-agent: *", "Allow: /", ""]
    for name in AI_CRAWLERS:
        blocks.extend([f"User-agent: {name}", "Allow: /", ""])
    blocks.append(f"Sitemap: {origin}/sitemap.xml")
    return "\n".join(blocks) + "\n"
