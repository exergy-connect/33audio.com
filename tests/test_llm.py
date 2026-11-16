import json
import unittest
from pathlib import Path

from catalog.build import build
from catalog.llm_pages import (
    AI_CRAWLERS,
    catalog_document,
    part_summary,
    provenance_text,
    render_catalog_md,
    render_llms_txt,
    render_robots,
)
from catalog.parse import parse_html

ROOT = Path(__file__).resolve().parents[1]
SITE = json.loads((ROOT / "data" / "site.json").read_text(encoding="utf-8"))
ORIGIN = "https://example.test/33audio"


def parsed():
    html = (ROOT / "tests" / "fixtures" / "caddockmsmm.html").read_text(encoding="utf-8")
    return parse_html(html, "https://www.33audio.com/enter/caddockmsmm.html", None)


class LlmFileTests(unittest.TestCase):
    def test_llms_txt_lists_every_part_and_the_seller_facts(self):
        data = parsed()
        text = render_llms_txt(data, SITE, ORIGIN)
        self.assertTrue(text.startswith("# 33audio\n"))
        self.assertIn("> 33audio in Houston, TX sells NOS Caddock Micronox film resistors", text)
        self.assertIn("$10.00 each", text)
        self.assertIn("$6.35 flat shipping", text)
        self.assertIn("USA orders only", text)
        self.assertIn("https://www.ebay.com/str/33audiomarko", text)
        self.assertIn(f"{ORIGIN}/catalog.md", text)
        self.assertIn(f"{ORIGIN}/catalog.json", text)
        self.assertIn("## Series", text)
        for series in data["series"]:
            self.assertIn(f"{ORIGIN}/series/{series['id'].lower()}/", text)
            for part in series["parts"]:
                self.assertIn(f"- [{part['id']}]({ORIGIN}/parts/{part['id'].lower()}/)", text)
        self.assertIn("liquidation stock from a Caddock stocking distributor that closed in the 1980s", provenance_text(data["listing"]))

    def test_catalog_markdown_and_json_match_the_parts(self):
        data = parsed()
        document = catalog_document(data, SITE, ORIGIN)
        self.assertEqual(len(document["parts"]), 85)
        self.assertEqual(document["shipping"]["amount"], "6.35")
        row = next(part for part in document["parts"] if part["part_number"] == "MM177-4.32K")
        self.assertEqual(row["resistance"]["label"], "4.32 kΩ")
        self.assertEqual(row["quantity"], 63)
        markdown = render_catalog_md(data, SITE, ORIGIN)
        self.assertEqual(markdown.count("\n| MM177-"), 31)
        self.assertEqual(markdown.count("\n| MM215-"), 25)
        self.assertEqual(markdown.count("\n| MS151-"), 20)
        self.assertEqual(markdown.count("\n| MS176-"), 9)
        self.assertIn(f"| MM177-4.32K | MM177 | 4.32 kΩ | 0.1% (B) | 63 | $10.00 | {ORIGIN}/parts/mm177-4.32k/ |", markdown)

    def test_robots_allows_named_ai_crawlers_and_keeps_the_sitemap(self):
        text = render_robots(ORIGIN)
        self.assertIn("User-agent: *\nAllow: /", text)
        for bot in AI_CRAWLERS:
            self.assertIn(f"User-agent: {bot}\nAllow: /", text)
        self.assertTrue(text.strip().endswith(f"Sitemap: {ORIGIN}/sitemap.xml"))

    def test_part_summary_uses_catalog_facts_only(self):
        data = parsed()
        series = data["series"][0]
        part = {**series["parts"][0], "series": series["id"]}
        text = part_summary(part, SITE, data["listing"])
        self.assertIn(part["id"], text)
        self.assertIn("Houston, TX", text)
        self.assertIn("$10.00", text)
        self.assertNotIn("Acoustat", text)

    def test_build_writes_the_files(self):
        import tempfile

        data = parsed()
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp) / "docs"
            build(data, {"listings": []}, SITE, docs, ROOT / "assets")
            page = (docs / "parts" / "mm177-4.32k" / "index.html").read_text(encoding="utf-8")
            self.assertIn("FAQPage", page)
            self.assertIn("What does NOS mean", page)
            self.assertIn('rel="describedby"', page)
            self.assertIn("llms.txt", (docs / "index.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
