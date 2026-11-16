import copy
import importlib.util
import json
import unittest
from pathlib import Path

from catalog.llm_pages import catalog_document, ontology_json_ld
from catalog.parse import parse_html

ROOT = Path(__file__).resolve().parents[1]
SITE = json.loads((ROOT / "data" / "site.json").read_text(encoding="utf-8"))
HAVE_TOOLS = bool(importlib.util.find_spec("xyang")) and bool(importlib.util.find_spec("jsonschema"))


def parsed():
    html = (ROOT / "tests" / "fixtures" / "caddockmsmm.html").read_text(encoding="utf-8")
    return parse_html(html, "https://www.33audio.com/enter/caddockmsmm.html", None)


class CatalogDocumentTests(unittest.TestCase):
    def test_document_points_at_schema_and_context(self):
        doc = catalog_document(parsed(), SITE, "https://example.test")
        self.assertEqual(doc["$schema"], "https://example.test/schema/catalog.schema.json")
        self.assertEqual(doc["@context"], "https://example.test/schema/context.jsonld")
        part = next(p for p in doc["parts"] if p["part_number"] == "MM177-4.32K")
        self.assertEqual(part["resistance"], {"value": "4320", "unit": "ohm", "label": "4.32 kΩ"})
        self.assertEqual(part["tolerance"], {"percent": "0.1", "code": "B"})
        self.assertEqual(part["condition"], "new-old-stock")
        mm177 = next(s for s in doc["series"] if s["name"] == "MM177")
        self.assertEqual((mm177["power_rating"], mm177["voltage_rating"]), ("0.6", 500))
        self.assertTrue(mm177["not_recommended_for_new_designs"])
        ms151 = next(s for s in doc["series"] if s["name"] == "MS151")
        self.assertEqual((ms151["power_rating"], ms151["voltage_rating"]), ("0.5", 300))
        self.assertFalse(ms151["not_recommended_for_new_designs"])

    def test_parser_omits_missing_last_modified(self):
        self.assertNotIn("source_last_modified", parsed())

    def test_part_page_node_shares_the_product_id(self):
        data = parsed()
        series = data["series"][0]
        part = {**series["parts"][0], "series": series["id"]}
        block = ontology_json_ld(part, "USD", "https://example.test")
        self.assertEqual(block["@context"], "https://example.test/schema/context.jsonld")
        self.assertEqual(block["parts"][0]["@id"], f"https://example.test/parts/{part['id'].lower()}/#product")


@unittest.skipUnless(HAVE_TOOLS, "pip install -r requirements-schema.txt")
class XyangSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from catalog import schema

        cls.schema = schema
        cls.origin = schema.site_origin()
        cls.artifacts = schema.artifacts(cls.origin)
        cls.catalog_schema = json.loads(cls.artifacts["catalog.schema.json"])

    def test_committed_artifacts_and_catalogs_pass_the_check(self):
        self.assertEqual(self.schema.check(self.origin), [])

    def test_every_node_has_a_description(self):
        missing = [path for path, _name, node in self.schema.walk(self.catalog_schema) if not node.get("description")]
        self.assertEqual(missing, [])

    def test_context_maps_terms_by_position(self):
        context = json.loads(self.artifacts["context.jsonld"])["@context"]
        self.assertEqual(context["currency"]["@id"], "https://schema.org/priceCurrency")
        parts = context["parts"]["@context"]
        self.assertEqual(parts["part_number"]["@id"], "https://schema.org/mpn")
        self.assertEqual(parts["condition"]["@id"], "https://exergy-connect.github.io/33audio.com/schema/vocab#condition")
        self.assertEqual(parts["url"], {"@id": "https://schema.org/url", "@type": "@id"})
        self.assertEqual(context["series"]["@context"]["name"]["@id"], "https://schema.org/model")
        self.assertEqual(context["seller"]["@context"]["name"]["@id"], "https://schema.org/name")
        self.assertEqual(context["shipping"]["@context"]["currency"]["@id"], "https://schema.org/currency")
        for path in (("source_url",), ("seller", "ebay_store"), ("series", "datasheet"), ("parts", "ebay_listing")):
            term = context[path[0]]
            if len(path) == 2:
                term = term["@context"][path[1]]
            self.assertEqual(term["@type"], "@id")

    def test_vocab_links_wikidata_and_schema_org_classes(self):
        graph = {node["@id"]: node for node in json.loads(self.artifacts["vocab.jsonld"])["@graph"]}
        namespace = self.catalog_schema["x-yang"]["namespace"]
        self.assertEqual(graph["https://schema.org/itemListElement"]["skos:closeMatch"], [{"@id": "http://www.wikidata.org/entity/Q5321"}])
        self.assertEqual(graph["https://schema.org/itemListElement"]["rdfs:range"], {"@id": "https://schema.org/Product"})
        self.assertEqual(graph["https://schema.org/unitText"]["schema:unitCode"], "OHM")
        self.assertEqual(graph[namespace + "condition"]["skos:closeMatch"], [{"@id": "http://www.wikidata.org/entity/Q907054"}])
        self.assertEqual(graph["https://schema.org/seller"]["rdfs:range"], {"@id": "https://schema.org/Organization"})

    def test_invalid_catalogs_are_rejected(self):
        doc = json.loads((ROOT / "docs" / "catalog.json").read_text(encoding="utf-8"))
        bad_price = copy.deepcopy(doc)
        bad_price["parts"][0]["price"] = 10
        self.assertTrue(self.schema.validate_with_xyang(self.schema.CATALOG_MODULE, bad_price, native=False))
        self.assertTrue(self.schema.validate_with_json_schema(self.catalog_schema, bad_price))
        orphan = copy.deepcopy(doc)
        orphan["series"] = [s for s in orphan["series"] if s["name"] != "MS176"]
        errors = self.schema.validate_with_xyang(self.schema.CATALOG_MODULE, orphan, native=False)
        self.assertTrue(any("leafref" in e for e in errors))
        keyless = copy.deepcopy(doc)
        del keyless["parts"][0]["part_number"]
        self.assertTrue(self.schema.validate_with_xyang(self.schema.CATALOG_MODULE, keyless, native=False))
        self.assertTrue(self.schema.validate_with_json_schema(self.catalog_schema, keyless))

    def test_source_listing_needs_native_json(self):
        source = json.loads((ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(self.schema.validate_with_xyang(self.schema.SOURCE_MODULE, source, native=True), [])
        schema = json.loads(self.artifacts["source-listing.schema.json"])
        self.assertEqual(self.schema.validate_with_json_schema(schema, source), [])
        imprecise = copy.deepcopy(source)
        imprecise["series"][0]["parts"][0]["ohms"] = 24.9001
        self.assertTrue(self.schema.validate_with_json_schema(schema, imprecise))
        for path in (("series", 0, "id"), ("series", 0, "parts", 0, "id")):
            keyless = copy.deepcopy(source)
            entry = keyless
            for key in path[:-1]:
                entry = entry[key]
            del entry[path[-1]]
            self.assertTrue(self.schema.validate_with_xyang(self.schema.SOURCE_MODULE, keyless, native=True))
            self.assertTrue(self.schema.validate_with_json_schema(schema, keyless))
        rfc = self.schema.validate_with_xyang(self.schema.SOURCE_MODULE, source, native=False)
        self.assertTrue(any("decimal64" in e for e in rfc))


if __name__ == "__main__":
    unittest.main()
