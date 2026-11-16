"""LLM-oriented catalog files: llms.txt, catalog.md, and catalog.json."""

from __future__ import annotations

import json

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
        f"The price is ${part['price']}, and 33audio ships it from {site['location']['label']}."
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
        "## Catalog files",
        "",
        f"- [All parts (Markdown)]({origin}/catalog.md): Table of every value, tolerance, quantity, and price",
        f"- [All parts (JSON)]({origin}/catalog.json): The same catalog as JSON",
        f"- [Full text for agents]({origin}/llms-full.txt): One summary sentence per part, plus the shared FAQ",
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
        "| Part | Series | Value | Tolerance | Quantity | Price | Page |",
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


def catalog_document(catalog: dict, site: dict, origin: str) -> dict:
    return {
        "seller": site["name"],
        "location": site["location"]["label"],
        "email": site["email"],
        "currency": catalog.get("currency", "USD"),
        "unit_price": catalog["unit_price"],
        "shipping": site["shipping"],
        "region_note": catalog["listing"].get("region_note"),
        "provenance": provenance_text(catalog["listing"]),
        "ebay_store": site["purchase"]["ebay"]["store_url"],
        "source_url": catalog.get("source_url"),
        "parts": [
            {
                "id": part["id"],
                "series": part["series"],
                "resistance": part["resistance"],
                "value": resistance_label(part["resistance"]),
                "tolerance": part["tolerance"],
                "tolerance_code": part["tolerance_code"],
                "quantity": part["quantity"],
                "price": part["price"],
                "url": f"{origin}/parts/{part['id'].lower()}/",
            }
            for part in flatten(catalog)
        ],
    }


def render_catalog_json(catalog: dict, site: dict, origin: str) -> str:
    return json.dumps(catalog_document(catalog, site, origin), indent=2, ensure_ascii=False) + "\n"


def render_robots(origin: str) -> str:
    blocks = ["User-agent: *", "Allow: /", ""]
    for name in AI_CRAWLERS:
        blocks.extend([f"User-agent: {name}", "Allow: /", ""])
    blocks.append(f"Sitemap: {origin}/sitemap.xml")
    return "\n".join(blocks) + "\n"
