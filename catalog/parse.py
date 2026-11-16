"""Parse the 33audio Caddock listing into data/catalog.json."""

from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import Decimal
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen

from catalog import DATA

SOURCE_URL = "https://www.33audio.com/enter/caddockmsmm.html"
TOLERANCE_CODES = {
    "J": "5%",
    "G": "2%",
    "F": "1%",
    "D": "0.5%",
    "C": "0.25%",
    "B": "0.1%",
}
ITEM_RE = re.compile(
    r"^(?P<number>\d+(?:\.\d+)?)(?P<mult>[KkMm])?(?:-(?P<tol>[JGFCDB]))?(?:\s*-+)+\s*(?P<qty>\d+)\s*$"
)
NOTE_RE = re.compile(r"^([JGFCDB])[\s-]*tolerance unless noted otherwise$", re.I)
ANCHOR_RE = re.compile(r"""<a\s+name=["']((?:MM|MS)\d+)["']\s*>""", re.I)


class ParseError(ValueError):
    pass


def html_lines(fragment: str) -> list[str]:
    fragment = unescape(fragment).replace("\xa0", " ")
    fragment = re.sub(r"(?i)<br\s*/?>", "\x00", fragment)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    lines = []
    for raw in fragment.split("\x00"):
        line = re.sub(r"\s+", " ", raw).strip(" >")
        if line:
            lines.append(line)
    return lines


def ohms_value(number: str, mult: str | None) -> int | float:
    value = Decimal(number)
    if mult:
        value *= {"K": Decimal(1000), "M": Decimal(1_000_000)}[mult.upper()]
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def keep_statement(line: str) -> bool:
    low = line.lower()
    if low.startswith(("goto ", "back to", "value, tolerance")):
        return False
    if "click here" in low:
        return False
    if "datasheet" in low and len(line) < 40:
        return False
    if set(line) <= set("- "):
        return False
    return True


def first_line(lines: list[str], needle: str) -> str | None:
    needle = needle.lower()
    for line in lines:
        if needle in line.lower():
            return line
    return None


def first_sentence(lines: list[str], needle: str) -> str | None:
    for index, line in enumerate(lines):
        if needle.lower() not in line.lower():
            continue
        sentence = []
        for continuation in lines[index:]:
            sentence.append(continuation)
            if continuation.rstrip().endswith((".", "!", "?")):
                break
        return " ".join(sentence)
    return None


def listing_fields(lines: list[str], html: str) -> dict:
    title = ""
    title_match = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    if title_match:
        title = re.sub(r"\s+", " ", unescape(title_match.group(1))).strip()
    blob = "\n".join(lines + [title])
    return {
        "film": "Micronox" if re.search(r"micronox", blob, re.I) else None,
        "product_line": first_line(lines, "high performance film"),
        "temperature_line": first_line(lines, "275"),
        "origin_line": first_line(lines, "made in usa"),
        "environment_line": first_line(lines, "harsh"),
        "provenance": first_sentence(lines, "liquidation"),
        "payment_note": first_line(lines, "paypal"),
        "region_note": first_line(lines, "usa orders only") or first_line(lines, "no international"),
        "statements": [line for line in lines if keep_statement(line)],
    }


def parse_section(series: str, fragment: str, price: str) -> dict:
    lines = html_lines(fragment)
    default = None
    note = None
    parts = []
    seen: set[str] = set()
    for line in lines:
        if line.upper() == series:
            continue
        if line.lower() == "back to top of page":
            continue
        note_match = NOTE_RE.match(line)
        if note_match:
            default = note_match.group(1).upper()
            note = line
            continue
        item = ITEM_RE.match(line)
        if not item:
            raise ParseError(f"Unexpected line in {series}: {line!r}")
        if not default:
            raise ParseError(f"{series} lists a value before its tolerance note")
        explicit = item.group("tol")
        code = (explicit or default).upper()
        number = item.group("number")
        mult = item.group("mult")
        resistance = f"{number}{mult.upper()}" if mult else number
        part_id = f"{series}-{resistance}" + (f"-{code}" if explicit else "")
        if part_id in seen:
            raise ParseError(f"Duplicate part id {part_id}")
        seen.add(part_id)
        parts.append(
            {
                "id": part_id,
                "resistance": resistance,
                "ohms": ohms_value(number, mult),
                "tolerance_code": code,
                "tolerance": TOLERANCE_CODES[code],
                "tolerance_explicit": bool(explicit),
                "quantity": int(item.group("qty")),
                "price": price,
            }
        )
    if not parts:
        raise ParseError(f"{series} has no parts")
    if not default:
        raise ParseError(f"{series} has no default tolerance")
    family = "MM" if series.startswith("MM") else "MS"
    return {
        "id": series,
        "family": family,
        "default_tolerance_code": default,
        "default_tolerance": TOLERANCE_CODES[default],
        "default_note": note,
        "parts": parts,
    }


def parse_html(html: str, source_url: str, source_last_modified: str | None = None) -> dict:
    anchors = list(ANCHOR_RE.finditer(html))
    if not anchors:
        raise ParseError("No series anchors found")
    intro_lines = html_lines(html[: anchors[0].start()])
    price_match = re.search(r"\$(\d+\.\d{2})\s+each", "\n".join(intro_lines), re.I)
    if not price_match:
        raise ParseError("Catalog price ($x.xx each) was not found")
    price = price_match.group(1)
    legend = first_line(intro_lines, "tolerances:")
    if not legend or "J=5%" not in legend or "B=.1%" not in legend:
        raise ParseError(f"Tolerance legend missing or changed: {legend!r}")
    series = []
    for index, anchor in enumerate(anchors):
        name = anchor.group(1).upper()
        end = anchors[index + 1].start() if index + 1 < len(anchors) else len(html)
        series.append(parse_section(name, html[anchor.end() : end], price))
    ids = [part["id"] for group in series for part in group["parts"]]
    if len(ids) != len(set(ids)):
        raise ParseError("Part ids are not unique")
    document = {
        "source_url": source_url,
        "source_last_modified": source_last_modified,
        "currency": "USD",
        "unit_price": price,
        "legend": legend,
        "tolerance_codes": TOLERANCE_CODES,
        "listing": {k: v for k, v in listing_fields(intro_lines, html).items() if v is not None},
        "series": series,
    }
    if source_last_modified is None:
        del document["source_last_modified"]
    return document


def fetch_html(url: str) -> tuple[str, str | None]:
    request = Request(
        url,
        headers={
            "User-Agent": "33audio-catalog/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, "replace"), response.headers.get("Last-Modified")


def write_catalog(catalog: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parse the 33audio Caddock catalog page")
    parser.add_argument("--html", help="Parse a local HTML file instead of fetching")
    parser.add_argument("--url", default=SOURCE_URL)
    parser.add_argument("--out", default=str(DATA / "catalog.json"))
    args = parser.parse_args(argv)
    if args.html:
        html = Path(args.html).read_text(encoding="utf-8")
        catalog = parse_html(html, args.url, None)
    else:
        html, modified = fetch_html(args.url)
        catalog = parse_html(html, args.url, modified)
    write_catalog(catalog, Path(args.out))
    count = sum(len(series["parts"]) for series in catalog["series"])
    print(f"Wrote {count} parts to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
