import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { formatOhms, heuristicIntent, mergeIntent, parseResistance, rankParts, sanitizeAiIntent, searchCatalog } from "../../worker/search.js";

const catalog = JSON.parse(await readFile(new URL("../../docs/catalog.json", import.meta.url), "utf8"));

test("parses resistance notations", () => {
  assert.equal(parseResistance("I need a 10M resistor"), 10e6);
  assert.equal(parseResistance("MM177 4.32K"), 4320);
  assert.equal(parseResistance("4K32 please"), 4320);
  assert.equal(parseResistance("1M5 grid leak"), 1.5e6);
  assert.equal(parseResistance("470R"), 470);
  assert.equal(parseResistance("10 megohm"), 10e6);
  assert.equal(parseResistance("220 ohms"), 220);
  assert.equal(parseResistance("MS176 something"), null);
});

test("keyword intent for the tube amp question", () => {
  const intent = heuristicIntent("I need a 10M resistor for a tube amp");
  assert.equal(intent.ohms, 10e6);
  assert.equal(intent.minVoltage, 500);
  assert.equal(intent.use, "tube amplifier");
});

test("ranking prefers exact values and in-stock parts", () => {
  const results = rankParts(catalog, heuristicIntent("MM177 4.32K"));
  assert.equal(results[0].part_number, "MM177-4.32K");
  assert.ok(results.every((r) => r.quantity > 0));
});

test("tube amp search without AI falls back and explains why", async () => {
  const result = await searchCatalog({ q: "I need a 10M resistor for a tube amp", catalog, env: {} });
  assert.equal(result.mode, "keyword");
  assert.match(result.fallback_reason, /not bound/);
  assert.match(result.summary, /No 10 MΩ part is in stock/);
  assert.ok(result.results.length > 0);
  assert.ok(result.results[0].ohms >= 1e6, "closest values are megohm parts");
  assert.ok(result.results[0].voltage_rating >= 500, "tube amp prefers 500 V or more");
});

test("AI intent is used when the binding answers", async () => {
  const env = {
    AI: {
      async run(model, input) {
        assert.ok(input.response_format.json_schema);
        return { response: { ohms: 2150000, series: null, family: "MM", min_voltage: 800, use: "tube amplifier" } };
      },
    },
  };
  const result = await searchCatalog({ q: "two point one five meg for my preamp plate", catalog, env });
  assert.equal(result.mode, "ai");
  assert.equal(result.results[0].part_number, "MM215-2.15M");
});

test("AI failure falls back to the keyword parser", async () => {
  const env = { AI: { run: async () => { throw new Error("boom"); } } };
  const result = await searchCatalog({ q: "4.32K", catalog, env });
  assert.equal(result.mode, "keyword");
  assert.match(result.fallback_reason, /boom/);
  assert.equal(result.results[0].ohms, 4320);
});

test("AI output is sanitized", () => {
  assert.equal(sanitizeAiIntent("not json"), null);
  const parsed = sanitizeAiIntent('Here: {"ohms": "4320", "series": "xx", "family": "ms"}');
  assert.deepEqual([parsed.ohms, parsed.series, parsed.family], [4320, null, "MS"]);
  const merged = mergeIntent({ ohms: null, family: "MS" }, heuristicIntent("4.32K tube"));
  assert.equal(merged.ohms, 4320);
  assert.equal(merged.family, "MS");
});

test("formats ohms", () => {
  assert.equal(formatOhms(10e6), "10 MΩ");
  assert.equal(formatOhms(4320), "4.32 kΩ");
  assert.equal(formatOhms(19.7), "19.7 Ω");
});
