"""Generate and check the catalog ontology artifacts with xYang.

python -m catalog schema            write docs/schema/* from model/*.yang
python -m catalog schema --check    fail if docs/schema is stale or the catalogs do not validate
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

from catalog import DATA, DOCS, ROOT

MODEL_DIR = ROOT / "model"
SCHEMA_DIR = DOCS / "schema"
CATALOG_MODULE = MODEL_DIR / "audio33-catalog.yang"
SOURCE_MODULE = MODEL_DIR / "audio33-source-listing.yang"
EXT_PREFIX = "c33:"


def _xyang():
    try:
        import xyang
    except ImportError as error:
        raise SystemExit("xYang is required: pip install xyang") from error
    return xyang


def site_origin() -> str:
    site = json.loads((DATA / "site.json").read_text(encoding="utf-8"))
    custom = site.get("custom_domain")
    if custom:
        return "https://" + str(custom).strip().strip("/")
    return str(site["canonical_origin"]).rstrip("/")


def generate_schema(module_path: Path, schema_url: str, *, native: bool = False) -> dict:
    xyang = _xyang()
    module = xyang.parse_yang_file(module_path, include_path=(str(MODEL_DIR),))
    return xyang.generate_json_schema(module, schema_id=schema_url, native_json=native)


def extensions(node: dict) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for entry in (node.get("x-yang") or {}).get("extensions") or []:
        name = str(entry.get("name", ""))
        if name.startswith(EXT_PREFIX):
            found.setdefault(name[len(EXT_PREFIX):], []).append(str(entry.get("argument", "")))
    return found


def _object_schema(node: dict) -> dict | None:
    if node.get("type") == "array" and isinstance(node.get("items"), dict):
        node = node["items"]
    return node if isinstance(node.get("properties"), dict) else None


def walk(schema: dict, path: str = ""):
    for name, node in (schema.get("properties") or {}).items():
        here = f"{path}/{name}"
        yield here, name, node
        child = _object_schema(node)
        if child is not None:
            yield from walk(child, here)


def render_readme(schema: dict, origin: str) -> str:
    lines = [
        "# 33audio catalog vocabulary",
        "",
        "Generated from [`model/audio33-catalog.yang`](audio33-catalog.yang) with [xYang](https://github.com/exergy-connect/xYang). Do not edit by hand; run `python -m catalog schema`.",
        "",
        f"- JSON Schema (2020-12, with `x-yang`): [{origin}/schema/catalog.schema.json]({origin}/schema/catalog.schema.json)",
        f"- JSON-LD context: [{origin}/schema/context.jsonld]({origin}/schema/context.jsonld)",
        f"- Term descriptions with schema.org and Wikidata links: [{origin}/schema/vocab.jsonld]({origin}/schema/vocab.jsonld)",
        f"- Catalog that follows this model: [{origin}/catalog.json]({origin}/catalog.json)",
        f"- Source listing model (for `data/catalog.json` in the repository): [source-listing.schema.json]({origin}/schema/source-listing.schema.json)",
        "",
        "`catalog.json` carries `$schema` and `@context` pointing here. JSON-LD readers map its keys to schema.org where a property clearly matches, and to the `c33:` namespace otherwise. Terms are scoped by position, so `name` under `seller` is `schema:name` while `name` under `series` is `schema:model`.",
        "",
        "| Path | Meaning | schema.org | Wikidata | Unit |",
        "| --- | --- | --- | --- | --- |",
    ]
    for path, _name, node in walk(schema):
        ext = extensions(node)
        org = ", ".join(
            [f"[{p}](https://schema.org/{p})" for p in ext.get("schema-org-property", [])]
            + [f"class [{c}](https://schema.org/{c})" for c in ext.get("schema-org-class", [])]
        )
        wd = ", ".join(f"[{q}](https://www.wikidata.org/wiki/{q})" for q in ext.get("wikidata", []))
        unit = ", ".join(ext.get("unit-code", []))
        meaning = " ".join(str(node.get("description", "")).split()).replace("|", "\\|")
        lines.append(f"| `{path}` | {meaning} | {org} | {wd} | {unit} |")
    lines += [
        "",
        "Power and voltage ratings come from Caddock's Type MM and Type MS datasheets. Prices, quantities, and condition come from the 33audio listing.",
        "",
    ]
    return "\n".join(lines)


def dumps(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def artifacts(origin: str) -> dict[str, str]:
    catalog_schema = generate_schema(CATALOG_MODULE, f"{origin}/schema/catalog.schema.json")
    source_schema = generate_schema(SOURCE_MODULE, f"{origin}/schema/source-listing.schema.json", native=True)
    xyang = _xyang()
    module = xyang.parse_yang_file(CATALOG_MODULE, include_path=(str(MODEL_DIR),))
    return {
        "xyang-jsonld.yang": (MODEL_DIR / "xyang-jsonld.yang").read_text(encoding="utf-8"),
        "catalog.schema.json": dumps(catalog_schema),
        "source-listing.schema.json": dumps(source_schema),
        "context.jsonld": dumps(xyang.generate_jsonld_context(module)),
        "vocab.jsonld": dumps(xyang.generate_jsonld_vocab(module)),
        "README.md": render_readme(catalog_schema, origin),
        "audio33-catalog.yang": CATALOG_MODULE.read_text(encoding="utf-8"),
        "audio33-source-listing.yang": SOURCE_MODULE.read_text(encoding="utf-8"),
    }


def validate_with_xyang(module_path: Path, document: dict, native: bool) -> list[str]:
    xyang = _xyang()
    result = xyang.validate(module_path, document, include_path=(MODEL_DIR,), native_json=native)
    return [f"{issue.get('path')}: {issue.get('code')}: {issue.get('message')}" for issue in result["errors"]]


def validate_with_json_schema(schema: dict, document: dict) -> list[str]:
    try:
        import jsonschema
    except ImportError as error:
        raise SystemExit("jsonschema is required for --check: pip install jsonschema") from error
    # JSON decimal constraints need exact arithmetic (24.9 is a multiple of 0.001).
    schema = json.loads(json.dumps(schema), parse_float=Decimal)
    document = json.loads(json.dumps(document), parse_float=Decimal)
    validator = jsonschema.Draft202012Validator(schema)
    return [f"/{'/'.join(str(p) for p in err.absolute_path)}: {err.message}" for err in validator.iter_errors(document)]


def check(origin: str) -> list[str]:
    problems = []
    expected = artifacts(origin)
    for name, text in expected.items():
        path = SCHEMA_DIR / name
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            problems.append(f"docs/schema/{name} is out of date; run python -m catalog schema")
    public = json.loads((DOCS / "catalog.json").read_text(encoding="utf-8"))
    if public.get("$schema") != f"{origin}/schema/catalog.schema.json":
        problems.append("docs/catalog.json $schema does not point at the published schema")
    if public.get("@context") != f"{origin}/schema/context.jsonld":
        problems.append("docs/catalog.json @context does not point at the published context")
    body = public
    problems += [f"docs/catalog.json (xYang) {e}" for e in validate_with_xyang(CATALOG_MODULE, body, native=False)]
    schema = json.loads(expected["catalog.schema.json"])
    problems += [f"docs/catalog.json (JSON Schema) {e}" for e in validate_with_json_schema(schema, body)]
    source = json.loads((DATA / "catalog.json").read_text(encoding="utf-8"))
    problems += [f"data/catalog.json (xYang native) {e}" for e in validate_with_xyang(SOURCE_MODULE, source, native=True)]
    source_schema = json.loads(expected["source-listing.schema.json"])
    problems += [f"data/catalog.json (JSON Schema native) {e}" for e in validate_with_json_schema(source_schema, source)]
    return problems


def write(origin: str) -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    for name, text in artifacts(origin).items():
        (SCHEMA_DIR / name).write_text(text, encoding="utf-8")
    print(f"Wrote {SCHEMA_DIR}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate or check docs/schema with xYang")
    parser.add_argument("--check", action="store_true", help="Only check; exit 1 on any mismatch")
    args = parser.parse_args(argv)
    origin = site_origin()
    if not args.check:
        write(origin)
    problems = check(origin)
    if problems:
        print("Schema check failed:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    print("Model, schema, and catalogs agree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
