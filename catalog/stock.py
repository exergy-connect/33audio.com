"""Build the KV stock document from the catalog and optionally push it with wrangler."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from catalog import DATA, ROOT
from catalog.purchase import flatten, resistance_label

WRANGLER = "wrangler@4.162.0"
STOCK_KEY = "stock"
PLACEHOLDER_ID = "REPLACE_WITH_STOCK_KV_NAMESPACE_ID"


def stock_doc(catalog: dict, site: dict) -> dict:
    parts = []
    for part in flatten(catalog):
        parts.append(
            {
                "id": part["id"],
                "series": part["series"],
                "part_number": part["id"],
                "value": resistance_label(part["resistance"]),
                "resistance": part["resistance"],
                "tolerance": part["tolerance"],
                "qty": part["quantity"],
                "price": part["price"],
            }
        )
    return {
        "version": 1,
        "currency": "USD",
        "shipping": site["shipping"]["amount"],
        "source": catalog.get("source_url"),
        "source_last_modified": catalog.get("source_last_modified"),
        "parts": parts,
    }


def merge(base: dict, live: dict | None, overwrite: bool) -> dict:
    """Catalog fields win. Live KV quantities win unless overwrite is set, so paid orders are not undone."""
    merged = json.loads(json.dumps(base))
    if not live or overwrite:
        merged["applied_sessions"] = list((live or {}).get("applied_sessions") or [])
        return merged
    live_qty = {part.get("id"): part.get("qty") for part in live.get("parts") or []}
    for part in merged["parts"]:
        qty = live_qty.get(part["id"])
        if isinstance(qty, int):
            part["qty"] = qty
    merged["applied_sessions"] = list(live.get("applied_sessions") or [])
    return merged


def namespace_id(config_path: Path) -> str | None:
    if not config_path.exists():
        return None
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    for item in config.get("kv_namespaces") or []:
        if item.get("binding") == "STOCK":
            value = str(item.get("id") or "").strip()
            if value and value != PLACEHOLDER_ID:
                return value
    return None


def wrangler(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["npx", "--yes", WRANGLER, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def read_live(ns_id: str) -> dict | None:
    result = wrangler("kv", "key", "get", STOCK_KEY, "--namespace-id", ns_id, "--remote", "--text")
    if result.returncode != 0:
        raise RuntimeError(f"wrangler kv key get failed: {result.stderr.strip()[-500:]}")
    text = result.stdout.strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) and isinstance(value.get("parts"), list) else None


def write_live(ns_id: str, doc: dict) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(doc, handle, ensure_ascii=False)
        path = handle.name
    try:
        result = wrangler("kv", "key", "put", STOCK_KEY, "--path", path, "--namespace-id", ns_id, "--remote")
    finally:
        os.unlink(path)
    if result.returncode != 0:
        raise RuntimeError(f"wrangler kv key put failed: {result.stderr.strip()[-500:]}")


def seed(base: dict, overwrite: bool, config_path: Path) -> int:
    missing = [name for name in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID") if not os.environ.get(name)]
    if missing:
        print(f"Stock KV seed skipped: {', '.join(missing)} not set.")
        return 0
    ns_id = namespace_id(config_path)
    if not ns_id:
        print("Stock KV seed skipped: set the STOCK kv_namespaces id in wrangler.toml.")
        return 0
    try:
        live = read_live(ns_id)
        doc = merge(base, live, overwrite)
        doc["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        if live is not None and not overwrite:
            comparable = {k: v for k, v in live.items() if k != "updated_at"}
            if comparable == {k: v for k, v in doc.items() if k != "updated_at"}:
                print("Stock KV already up to date.")
                return 0
        write_live(ns_id, doc)
    except RuntimeError as error:
        print(f"Stock KV seed failed: {error}", file=sys.stderr)
        return 1
    action = "Overwrote" if overwrite or live is None else "Merged"
    print(f"{action} KV key '{STOCK_KEY}' with {len(doc['parts'])} parts.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build data/stock.json and optionally seed Workers KV")
    parser.add_argument("--catalog", default=str(DATA / "catalog.json"))
    parser.add_argument("--site", default=str(DATA / "site.json"))
    parser.add_argument("--out", default=str(DATA / "stock.json"))
    parser.add_argument("--config", default=str(ROOT / "wrangler.toml"))
    parser.add_argument("--seed", action="store_true", help="Push to the STOCK KV namespace with wrangler")
    parser.add_argument("--overwrite", action="store_true", help="Replace KV quantities with catalog quantities")
    args = parser.parse_args(argv)
    catalog = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    site = json.loads(Path(args.site).read_text(encoding="utf-8"))
    base = stock_doc(catalog, site)
    Path(args.out).write_text(json.dumps(base, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(base['parts'])} parts to {args.out}")
    if args.seed:
        return seed(base, args.overwrite, Path(args.config))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
