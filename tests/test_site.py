import json
import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path
from urllib.parse import unquote

from catalog.build import build
from catalog.fees import estimate, to_cents
from catalog.parse import parse_html
from catalog.purchase import PurchaseError, configured_flow_url, match_listings, resolve_purchase
from catalog.stock import merge, namespace_id, seed, stock_doc

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "caddockmsmm.html"
SITE = json.loads((ROOT / "data" / "site.json").read_text(encoding="utf-8"))


def catalog():
    html = FIXTURE.read_text(encoding="utf-8")
    return parse_html(html, "https://www.33audio.com/enter/caddockmsmm.html", None)


class ParseTests(unittest.TestCase):
    def test_counts_and_known_values(self):
        data = catalog()
        by_series = {series["id"]: series for series in data["series"]}
        self.assertEqual([series["id"] for series in data["series"]], ["MM177", "MM215", "MS151", "MS176"])
        self.assertEqual([len(by_series[name]["parts"]) for name in ("MM177", "MM215", "MS151", "MS176")], [31, 25, 20, 9])
        self.assertEqual(data["unit_price"], "10.00")
        parts = {part["id"]: part for series in data["series"] for part in series["parts"]}
        self.assertEqual(parts["MM177-4.32K"]["quantity"], 63)
        self.assertEqual(parts["MM177-4.32K"]["tolerance"], "0.1%")
        self.assertFalse(parts["MM177-4.32K"]["tolerance_explicit"])
        self.assertEqual(parts["MM177-665K"]["quantity"], 32)
        self.assertEqual(parts["MM177-665K-F"]["tolerance"], "1%")
        self.assertEqual(parts["MM177-665K-F"]["quantity"], 35)
        self.assertEqual(parts["MM215-4.32K"]["quantity"], 42)
        self.assertEqual(parts["MS176-5K-C"]["tolerance"], "0.25%")
        self.assertEqual(parts["MS176-500K-G"]["tolerance"], "2%")
        self.assertEqual(parts["MS151-33.2K"]["quantity"], 14)
        self.assertEqual(parts["MM177-1.09K-D"]["quantity"], 46)
        self.assertIn("liquidation stock", data["listing"]["provenance"])


class MatchTests(unittest.TestCase):
    def test_match_and_ambiguity(self):
        data = catalog()
        listings = [
            {"item_id": "1", "title": "Caddock MM177 4.32K 0.1% Micronox", "url": "https://www.ebay.com/itm/1"},
            {"item_id": "2", "title": "Caddock MM177 665K 1%", "url": "https://www.ebay.com/itm/2"},
            {"item_id": "3", "title": "Caddock MM177 665K resistor", "url": "https://www.ebay.com/itm/3"},
            {"item_id": "4", "title": "Caddock MM177 14.32K", "url": "https://www.ebay.com/itm/4"},
        ]
        matched = match_listings(data, listings)
        self.assertEqual(matched["MM177-4.32K"]["url"], "https://www.ebay.com/itm/1")
        self.assertEqual(matched["MM177-665K-F"]["url"], "https://www.ebay.com/itm/2")
        self.assertNotIn("MM177-665K", matched)
        self.assertTrue(all(item["url"] != "https://www.ebay.com/itm/4" for item in matched.values()))


class PurchaseTests(unittest.TestCase):
    def test_ebay_fallback_and_mailto(self):
        data = catalog()
        part = next(part for series in data["series"] for part in series["parts"] if part["id"] == "MM177-4.32K")
        part = {**part, "series": "MM177", "family": "MM"}
        decision = resolve_purchase(part, None, SITE)
        self.assertIn("https://www.ebay.com/sch/i.html", decision["primary_href"])
        self.assertIn("_ssn=33audiomarko", decision["primary_href"])
        self.assertIn("MM177", unquote(decision["primary_href"]))
        self.assertTrue(decision["ask_href"].startswith("mailto:mark@33audio.com"))
        self.assertIn("MM177-4.32K", unquote(decision["ask_href"]))
        direct = resolve_purchase(part, {"url": "https://www.ebay.com/itm/99", "title": "x"}, SITE)
        self.assertEqual(direct["primary_href"], "https://www.ebay.com/itm/99")

    def test_checkout_mode_requires_https(self):
        data = catalog()
        part = next(part for series in data["series"] for part in series["parts"] if part["id"] == "MM177-4.32K")
        part = {**part, "series": "MM177", "family": "MM"}
        site = json.loads(json.dumps(SITE))
        site["purchase"]["mode"] = "checkout"
        site["purchase"]["checkout"]["url"] = ""
        with self.assertRaises(PurchaseError):
            resolve_purchase(part, None, site)
        site["purchase"]["checkout"]["url"] = "https://pay.example.test/checkout?sku={part_id}"
        decision = resolve_purchase(part, None, site)
        self.assertEqual(decision["primary_href"], "https://pay.example.test/checkout?sku=MM177-4.32K")
        self.assertIn("ebay.com", decision["ebay_href"])


class BuildTests(unittest.TestCase):
    def test_build_writes_pages(self):
        data = catalog()
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp) / "docs"
            docs.mkdir()
            (docs / "old.html").write_text("bye")
            build(data, {"listings": []}, SITE, docs, ROOT / "assets")
            self.assertFalse((docs / "old.html").exists())
            self.assertFalse((docs / "CNAME").exists())
            page = (docs / "parts" / "mm177-4.32k" / "index.html").read_text(encoding="utf-8")
            self.assertIn('name="viewport" content="width=device-width, initial-scale=1"', page)
            self.assertIn("Caddock MM177-4.32K Micronox resistor, NOS, in stock | 33audio", page)
            self.assertIn("Buy on eBay", page)
            self.assertIn("Ask about this part", page)
            self.assertIn("min-height: 44px", (docs / "styles.css").read_text(encoding="utf-8"))
            self.assertIn("demo, not yet active", page)
            fees = (docs / "fees" / "index.html").read_text(encoding="utf-8")
            self.assertIn("13.6%", fees)
            self.assertIn("2.9%", fees)
            self.assertIn("3.49%", fees)
            self.assertIn("https://stripe.com/pricing", fees)
            self.assertIn("https://www.paypal.com/us/business/paypal-business-fees", fees)
            self.assertIn("https://www.ebay.com/sellercenter/selling/seller-fees", fees)
            self.assertIn('name="viewport"', fees)
            self.assertIsNone(configured_flow_url(SITE, {"id": "MM177-4.32K", "series": "MM177", "resistance": "4.32K", "tolerance": "0.1%", "tolerance_code": "B", "quantity": 63, "price": "10.00", "ohms": 4320}, "stripe"))


class StockTests(unittest.TestCase):
    def test_stock_doc_and_merge(self):
        doc = stock_doc(catalog(), SITE)
        self.assertEqual(len(doc["parts"]), 85)
        self.assertEqual(doc["shipping"], "6.35")
        first = next(p for p in doc["parts"] if p["id"] == "MM177-4.32K")
        self.assertEqual(first, {
            "id": "MM177-4.32K", "series": "MM177", "part_number": "MM177-4.32K",
            "value": "4.32 kΩ", "resistance": "4.32K", "tolerance": "0.1%", "qty": 63, "price": "10.00",
        })
        live = {"parts": [{"id": "MM177-4.32K", "qty": 60}, {"id": "GONE-1", "qty": 4}], "applied_sessions": ["cs_1"]}
        merged = merge(doc, live, overwrite=False)
        self.assertEqual(next(p for p in merged["parts"] if p["id"] == "MM177-4.32K")["qty"], 60)
        self.assertNotIn("GONE-1", [p["id"] for p in merged["parts"]])
        self.assertEqual(merged["applied_sessions"], ["cs_1"])
        reset = merge(doc, live, overwrite=True)
        self.assertEqual(next(p for p in reset["parts"] if p["id"] == "MM177-4.32K")["qty"], 63)

    def test_seed_skips_without_credentials(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(seed(stock_doc(catalog(), SITE), False, ROOT / "wrangler.toml"), 0)
        self.assertIsNone(namespace_id(ROOT / "wrangler.toml"))


class FeeTests(unittest.TestCase):
    def test_example_order(self):
        costs = SITE["selling_costs"]
        result = estimate(to_cents("10.00"), to_cents("6.35"), 1, costs)
        self.assertEqual(result["total_cents"], 1635)
        self.assertEqual(result["ebay_cents"], 262)
        self.assertEqual(result["stripe_cents"], 77)
        self.assertEqual(result["paypal_cents"], 106)


if __name__ == "__main__":
    unittest.main()
