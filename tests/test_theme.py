import json
import re
import tempfile
import unittest
from pathlib import Path

from catalog.build import build
from catalog.parse import parse_html
from catalog.theme import vu_meter

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "caddockmsmm.html"
SITE = json.loads((ROOT / "data" / "site.json").read_text(encoding="utf-8"))
CSS = (ROOT / "catalog" / "templates" / "styles.css").read_text(encoding="utf-8")


def json_ld_types(html: str) -> list[str]:
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html)
    types = []
    for block in blocks:
        data = json.loads(block)
        for item in data.get("@graph", [data]):
            # The xYang catalog block uses its own context rather than schema.org @type.
            if "@type" in item:
                types.append(item["@type"])
    return types


class StylesheetTests(unittest.TestCase):
    def test_no_external_fonts_or_images(self):
        self.assertNotIn("@import", CSS)
        self.assertNotIn("@font-face", CSS)
        self.assertNotRegex(CSS, r"url\(\s*['\"]?(https?:)?//")

    def test_motion_only_without_reduced_motion_preference(self):
        allowed = CSS.index("@media (prefers-reduced-motion: no-preference)")
        reduce = CSS.index("@media (prefers-reduced-motion: reduce)")
        for match in re.finditer(r"animation:\s*spin33", CSS):
            self.assertGreater(match.start(), allowed)
            self.assertLess(match.start(), reduce)
        self.assertIn("animation: none !important", CSS[reduce:])

    def test_payment_flow_rules_kept(self):
        for flow in ("ebay", "stripe", "paypal"):
            self.assertRegex(CSS, rf'html\[data-payment-flow="{flow}"\] \.buy [^{{]*\[data-flow="{flow}"\]')
        self.assertRegex(CSS, r'html:not\(\[data-payment-flow\]\) \.buy [^{]*\[data-flow="ebay"\]')


class VuMeterTests(unittest.TestCase):
    def test_needle_is_clamped_and_ids_are_keyed(self):
        low = vu_meter(-5, "a")
        high = vu_meter(500, "b")
        self.assertIn('id="vu-glow-a"', low)
        self.assertIn('url(#vu-glow-b)', high)
        self.assertIn('aria-hidden="true"', low)
        self.assertEqual(vu_meter(-5, "x"), vu_meter(0, "x"))
        self.assertEqual(vu_meter(500, "x"), vu_meter(20, "x"))


class ThemedBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        html = FIXTURE.read_text(encoding="utf-8")
        data = parse_html(html, "https://www.33audio.com/enter/caddockmsmm.html", None)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.docs = Path(cls.tmp.name) / "docs"
        build(data, {"listings": []}, SITE, cls.docs, ROOT / "assets")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel: str) -> str:
        return (self.docs / rel).read_text(encoding="utf-8")

    def test_header_record_is_decorative(self):
        home = self.read("index.html")
        self.assertRegex(home, r'<svg class="brand-record"[^>]*aria-hidden="true"')
        self.assertRegex(home, r'<svg class="hero-art"[^>]*aria-hidden="true"')
        self.assertIn('<h1 id="home-title">', home)
        self.assertIn('<meta name="theme-color" content="#4a2b18">', home)

    def test_structured_data_survives(self):
        self.assertEqual(json_ld_types(self.read("index.html")), ["Organization", "WebSite"])
        self.assertEqual(json_ld_types(self.read("series/mm177/index.html")), ["ItemList"])
        part = self.read("parts/mm177-4.32k/index.html")
        self.assertEqual(json_ld_types(part), ["Product", "FAQPage", "BreadcrumbList"])
        self.assertIn('<h1 class="part">MM177-4.32K</h1>', part)
        self.assertIn('<span class="badge nos">NOS</span>', part)

    def test_buy_and_payment_controls(self):
        part = self.read("parts/mm177-4.32k/index.html")
        self.assertIn("Ask about availability", part)
        self.assertNotIn('data-buy="ebay"', part)
        self.assertNotIn("data-payment-select", part)
        self.assertNotIn("data-add-to-cart", part)

    def test_fee_meters(self):
        fees = self.read("fees/index.html")
        ids = re.findall(r'id="(vu-glow-[a-z]+)"', fees)
        self.assertEqual(sorted(ids), ["vu-glow-ebay", "vu-glow-paypal", "vu-glow-stripe"])
        self.assertIn("16.0% of the order", fees)

    def test_crawler_files_and_no_jekyll(self):
        for name in ("llms.txt", "llms-full.txt", "sitemap.xml", "robots.txt", "search.json", "catalog.md", "catalog.json"):
            self.assertTrue((self.docs / name).is_file(), name)
        self.assertEqual((self.docs / ".nojekyll").read_bytes(), b"")
        for name in ("_config.yml", "Gemfile", "_layouts", "_includes"):
            self.assertFalse((self.docs / name).exists(), name)


if __name__ == "__main__":
    unittest.main()
