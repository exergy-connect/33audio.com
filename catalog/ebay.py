"""Sync active eBay listings for seller 33audiomarko via the Browse API.

Skips with exit code 0 when EBAY_CLIENT_ID or EBAY_CLIENT_SECRET is unset.
Does not scrape eBay HTML.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

from catalog import DATA

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
SCOPE = "https://api.ebay.com/oauth/api_scope"
FALLBACK_QUERIES = ("caddock", "micronox", "resistor", "MM177", "MM215", "MS151", "MS176")


class EbayError(RuntimeError):
    pass


def _encode(value: str, safe: str = "", encoding: str | None = None, errors: str | None = None) -> str:
    return quote(str(value), safe="{}[]|:,")


def _request_json(url: str, headers: dict, data: bytes | None = None) -> tuple[dict, int]:
    request = Request(url, data=data, headers=headers)
    try:
        with urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode()), response.status
    except HTTPError as error:
        raw = error.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"message": raw[:400]}
        return payload, error.code


def access_token(client_id: str, client_secret: str) -> str:
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    body = urlencode({"grant_type": "client_credentials", "scope": SCOPE}).encode()
    payload, status = _request_json(
        TOKEN_URL,
        {
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body,
    )
    if status >= 400 or not payload.get("access_token"):
        raise EbayError(f"eBay token request failed (HTTP {status})")
    return payload["access_token"]


def search_page(token: str, params: dict) -> tuple[dict, int]:
    url = SEARCH_URL + "?" + urlencode(params, quote_via=_encode)
    return _request_json(
        url,
        {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            "Accept": "application/json",
        },
    )


def error_message(payload: dict, status: int) -> str:
    errors = payload.get("errors") if isinstance(payload, dict) else None
    if errors:
        text = "; ".join(str(item.get("message") or item.get("errorId")) for item in errors)
    else:
        text = str(payload)[:300]
    return f"HTTP {status}: {text}"


def paginate(token: str, params: dict) -> tuple[list[dict], str | None]:
    offset = 0
    found: list[dict] = []
    while True:
        query = dict(params)
        query["limit"] = "200"
        query["offset"] = str(offset)
        payload, status = search_page(token, query)
        if status >= 400:
            return [], error_message(payload, status)
        batch = payload.get("itemSummaries") or []
        found.extend(batch)
        total = int(payload.get("total") or len(found))
        offset += len(batch)
        if not batch or offset >= total or offset >= 5000:
            return found, None


def seller_filter(seller: str) -> str:
    return f"sellers:{{{seller}}},buyingOptions:{{FIXED_PRICE|AUCTION|BEST_OFFER}}"


def collect_summaries(token: str, seller: str) -> list[dict]:
    primary, error = paginate(token, {"filter": seller_filter(seller)})
    if not error:
        return primary
    print(f"Seller-only Browse search was rejected ({error}). Trying keyword searches.", file=sys.stderr)
    found: dict[str, dict] = {}
    for term in FALLBACK_QUERIES:
        batch, term_error = paginate(token, {"q": term, "filter": seller_filter(seller)})
        if term_error:
            raise EbayError(f"eBay search failed for {term!r}: {term_error}")
        for item in batch:
            item_id = item.get("itemId")
            if item_id:
                found[item_id] = item
    return list(found.values())


def listing_from_summary(item: dict, seller: str) -> dict | None:
    url = item.get("itemWebUrl") or ""
    host = urlparse(url).netloc
    if not url.startswith("https://") or not host.endswith("ebay.com"):
        legacy = str(item.get("legacyItemId") or "")
        url = f"https://www.ebay.com/itm/{legacy}" if legacy.isdigit() else ""
    if not url.startswith("https://www.ebay.com/"):
        return None
    info = item.get("seller") or {}
    username = info.get("username") or ""
    if username and username.lower() != seller.lower():
        return None
    price = item.get("price") or {}
    return {
        "item_id": item.get("itemId") or "",
        "title": item.get("title") or "",
        "url": url,
        "price": price.get("value"),
        "currency": price.get("currency"),
        "condition": item.get("condition"),
        "seller": username or seller,
        "feedback_percentage": info.get("feedbackPercentage"),
        "feedback_score": info.get("feedbackScore"),
    }


def comparable(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if key != "synced_at"}


def write_listings(path: Path, payload: dict) -> None:
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = None
        if isinstance(previous, dict) and comparable(previous) == comparable(payload):
            print("eBay listings unchanged")
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload['listings'])} eBay listings to {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync 33audiomarko listings from the eBay Browse API")
    parser.add_argument("--out", default=str(DATA / "ebay.json"))
    parser.add_argument("--site", default=str(DATA / "site.json"))
    args = parser.parse_args(argv)
    client_id = os.environ.get("EBAY_CLIENT_ID", "").strip()
    client_secret = os.environ.get("EBAY_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print("eBay sync skipped: EBAY_CLIENT_ID or EBAY_CLIENT_SECRET is not set.")
        return 0
    site = json.loads(Path(args.site).read_text(encoding="utf-8"))
    seller = site["purchase"]["ebay"]["seller"]
    store_url = site["purchase"]["ebay"]["store_url"]
    try:
        token = access_token(client_id, client_secret)
        summaries = collect_summaries(token, seller)
    except (EbayError, URLError, TimeoutError) as error:
        print(f"eBay sync failed: {error}", file=sys.stderr)
        return 1
    listings = []
    for summary in summaries:
        listing = listing_from_summary(summary, seller)
        if listing and listing["item_id"]:
            listings.append(listing)
    listings.sort(key=lambda item: item["item_id"])
    feedback_percentage = None
    feedback_score = None
    for listing in listings:
        if listing.get("feedback_percentage") is not None:
            feedback_percentage = listing["feedback_percentage"]
            feedback_score = listing.get("feedback_score")
            break
    payload = {
        "seller": seller,
        "store_url": store_url,
        "synced_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "feedback_percentage": feedback_percentage,
        "feedback_score": feedback_score,
        "listings": listings,
    }
    write_listings(Path(args.out), payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
