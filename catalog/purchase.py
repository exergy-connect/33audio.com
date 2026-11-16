"""Buy-link rules. Change data/site.json purchase.mode to swap eBay for checkout."""

from __future__ import annotations

import re
from urllib.parse import quote, urlparse

PERCENT_PATTERNS = {
    "B": re.compile(r"(?<![0-9.])0\.10?\s*%"),
    "C": re.compile(r"(?<![0-9.])0\.25\s*%"),
    "D": re.compile(r"(?<![0-9.])0?\.5\s*%"),
    "F": re.compile(r"(?<![0-9.])1\s*%"),
    "G": re.compile(r"(?<![0-9.])2\s*%"),
    "J": re.compile(r"(?<![0-9.])5\s*%"),
}


class PurchaseError(ValueError):
    pass


class _Map(dict):
    def __missing__(self, key: str) -> str:
        raise PurchaseError(f"Unknown placeholder {{{key}}}")


def resistance_label(resistance: str) -> str:
    if resistance[-1:] in {"K", "k"}:
        return f"{resistance[:-1]} kΩ"
    if resistance[-1:] in {"M", "m"}:
        return f"{resistance[:-1]} MΩ"
    return f"{resistance} Ω"


def flatten(catalog: dict) -> list[dict]:
    parts = []
    for series in catalog["series"]:
        for part in series["parts"]:
            parts.append({**part, "series": series["id"], "family": series["family"]})
    return parts


def _norm_title(title: str) -> str:
    return title.lower().replace("ω", " ohm ").replace("Ω", " ohm ").replace("ohms", "ohm")


def _series_in(title: str, series: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(series.lower())}(?![a-z0-9])", _norm_title(title)) is not None


def _resistance_in(title: str, part: dict) -> bool:
    norm = _norm_title(title)
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([km])?", part["resistance"].lower())
    if not match:
        return False
    number, mult = match.group(1), match.group(2)
    if mult:
        if re.search(rf"(?<![0-9.]){re.escape(number)}\s*{mult}(?![a-z0-9])", norm):
            return True
    elif re.search(rf"(?<![0-9.]){re.escape(number)}(?!\s*[km])(?![0-9])", norm):
        return True
    ohms = part["ohms"]
    if isinstance(ohms, (int, float)) and float(ohms).is_integer():
        if re.search(rf"(?<![0-9.]){int(ohms)}(?![0-9])\s*ohm", norm):
            return True
    return False


def _tolerance_codes(title: str, resistance: str) -> set[str]:
    norm = _norm_title(title)
    found = {code for code, pattern in PERCENT_PATTERNS.items() if pattern.search(norm)}
    match = re.search(
        rf"(?<![a-z0-9.]){re.escape(resistance.lower())}\s*-?\s*([bfdcgj])(?![a-z0-9])",
        norm,
    )
    if match:
        found.add(match.group(1).upper())
    return found


def match_listings(catalog: dict, listings: list[dict]) -> dict[str, dict]:
    parts = flatten(catalog)
    groups: dict[tuple[str, str], list[dict]] = {}
    for part in parts:
        groups.setdefault((part["series"], part["resistance"]), []).append(part)
    chosen: dict[str, list[dict]] = {}
    for listing in listings:
        title = listing.get("title") or ""
        if not title:
            continue
        hits = []
        for part in parts:
            if not _series_in(title, part["series"]) or not _resistance_in(title, part):
                continue
            codes = _tolerance_codes(title, part["resistance"])
            if codes and part["tolerance_code"] not in codes:
                continue
            if not codes and len(groups[(part["series"], part["resistance"])]) != 1:
                continue
            hits.append(part)
        ids = {part["id"] for part in hits}
        if len(ids) != 1:
            continue
        chosen.setdefault(hits[0]["id"], []).append(listing)

    def rank(item: dict, part_id: str) -> tuple:
        title = (item.get("title") or "").lower().replace(" ", "")
        exact = 0 if part_id.lower() in title else 1
        return (exact, len(item.get("title") or ""), item.get("item_id") or "")

    return {part_id: sorted(items, key=lambda item: rank(item, part_id))[0] for part_id, items in chosen.items()}


def template_values(part: dict, site: dict) -> dict:
    ebay = site["purchase"]["ebay"]
    return {
        "part_id": part["id"],
        "series": part["series"],
        "resistance": part["resistance"],
        "resistance_label": resistance_label(part["resistance"]),
        "tolerance": part["tolerance"],
        "tolerance_code": part["tolerance_code"],
        "quantity": part["quantity"],
        "price": part["price"],
        "ohms": part["ohms"],
        "seller": ebay["seller"],
        "query": site["purchase"]["ebay"]["query"].format_map(
            _Map(
                {
                    "part_id": part["id"],
                    "series": part["series"],
                    "resistance": part["resistance"],
                    "tolerance": part["tolerance"],
                    "tolerance_code": part["tolerance_code"],
                }
            )
        ),
    }


def fill_text(template: str, values: dict) -> str:
    return template.format_map(_Map(values))


def fill_url(template: str, values: dict) -> str:
    encoded = {key: quote(str(value), safe="") for key, value in values.items()}
    return template.format_map(_Map(encoded))


def safe_https(url: str, host_suffix: str | None = None) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    if host_suffix and not parsed.netloc.endswith(host_suffix):
        return None
    return url


def configured_flow_url(site: dict, part: dict, flow: str) -> str | None:
    """HTTPS checkout URL for Stripe or PayPal. Part entry wins, then the global template."""
    flows = site.get("payment_flows") or {}
    config = flows.get(flow) or {}
    parts = config.get("parts") or {}
    template = str(parts.get(part["id"]) or config.get("url") or "").strip()
    if not template:
        return None
    values = template_values(part, site)
    href = fill_url(template, values) if "{" in template else template
    return safe_https(href)


def mailto_link(email: str, subject: str, body: str) -> str:
    return f"mailto:{email}?subject={quote(subject)}&body={quote(body)}"


def ebay_target(part: dict, listing: dict | None, site: dict, values: dict) -> tuple[str, str]:
    ebay = site["purchase"]["ebay"]
    if listing and listing.get("url"):
        url = safe_https(listing["url"], "ebay.com")
        if url:
            return url, fill_text(ebay["matched_note"], values)
    return fill_url(ebay["search_url"], values), fill_text(ebay["search_note"], values)


def resolve_purchase(part: dict, listing: dict | None, site: dict) -> dict:
    purchase = site["purchase"]
    mode = purchase["mode"]
    values = template_values(part, site)
    ask = purchase["ask"]
    ask_href = mailto_link(
        ask["email"],
        fill_text(ask["subject"], values),
        fill_text(ask["body"], values),
    )
    ebay_href, ebay_note = ebay_target(part, listing, site, values)
    if mode == "ebay":
        return {
            "mode": mode,
            "primary_href": ebay_href,
            "primary_label": purchase["ebay"]["buy_label"],
            "primary_note": ebay_note,
            "ask_href": ask_href,
            "ask_label": ask["label"],
            "ebay_href": ebay_href,
            "listing": listing,
        }
    if mode == "checkout":
        checkout = purchase["checkout"]
        href = fill_url(checkout["url"], values) if checkout.get("url") else ""
        if safe_https(href) is None:
            raise PurchaseError("purchase.mode is checkout, but purchase.checkout.url is not an https URL")
        return {
            "mode": mode,
            "primary_href": href,
            "primary_label": checkout.get("buy_label") or "Buy",
            "primary_note": fill_text(checkout.get("note") or "Checkout for {part_id}.", values),
            "ask_href": ask_href,
            "ask_label": ask["label"],
            "ebay_href": ebay_href,
            "listing": listing,
        }
    raise PurchaseError(f"Unknown purchase.mode {mode!r}")
