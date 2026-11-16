---
title: AI-assisted search · Explore
summary: How the shop's part finder uses Workers AI to turn a plain-language request into structured filters, ranks real stock deterministically, and falls back to a keyword parser.
---

## The feature

A buyer types "I need a 10M resistor for a tube amp". The shop has no 10 MΩ part, and the buyer did not say which series or voltage rating they need. The part finder at `/ask/` answers anyway: it explains that 10 MΩ is not in stock, then lists the closest megohm values with a voltage rating of 500 V or more, because tube circuits run high plate voltages.

::: diagram ai-search-flow

## Design: the model extracts, the code decides

The language model never writes the answer. It only turns the question into a small JSON object of filters. Plain code then scores the parts that are actually in `catalog.json`. That split keeps every result real: the model cannot invent a part number, a price, or a quantity.

::: embed worker/search.js "export async function aiIntent"

Workers AI's JSON mode constrains the output to `INTENT_SCHEMA`. The Function still sanitizes every field, because a schema-constrained model can return a value of the right type that makes no sense:

::: embed worker/search.js "export function sanitizeAiIntent"

## Graceful degradation

The keyword parser always runs. It understands values like `10M`, `4K32`, `1M5`, and `470R`, and words like tube, precision, power, and grid leak. When `env.AI` is missing (local dev, preview deployments, or an account without Workers AI) or the model fails or takes more than 6 seconds, the keyword result is the whole answer. Every response says which path ran and why:

::: embed worker/search.js "export async function searchCatalog"

## Ranking

Value closeness dominates, measured in decades so 2.5 MΩ is "closer" to 10 MΩ than 100 kΩ is. Voltage, power, tolerance, and family preferences add or subtract points and also explain the result:

::: embed worker/search.js "export function rankParts"

## The endpoint

`functions/api/search.js` loads `catalog.json` through the Pages `ASSETS` binding (one fetch per isolate), caches AI answers for 300 seconds with the Cache API, writes an Analytics Engine data point, and adds `Server-Timing`:

::: embed functions/api/search.js "export async function onRequestGet"

## Cost and abuse

Every AI call costs neurons. Three controls keep that bounded:

1. Repeated questions hit the Cache API, not the model. Keyword answers are not cached because they are nearly free.
2. A WAF rate-limiting rule allows 10 searches per 10 seconds per client and data center ([security/waf/rules.json](repo:security/waf/rules.json)). Pages Functions cannot use the Workers Rate Limiting binding, so the rule lives at the zone ([ADR 0005](/reference/adr/0005-rate-limiting-split/)).
3. Queries are capped at 200 characters, and `max_tokens` is 200.

## Trade-offs

| Approach | Strength | Weakness | Used here |
| --- | --- | --- | --- |
| LLM extracts filters, code ranks | Results are always real stock; cheap small model; explainable | Needs a parser for the filters | Yes |
| Embeddings in Vectorize | Good fuzzy matching on descriptions | Numeric values like 4.32 kΩ embed poorly; another index to keep in sync | No |
| LLM writes the answer from the catalog in its prompt | Fluent answers | Can invent parts; long prompts on every call | No |
| Keyword search only | Free, fast, predictable | Misses intent such as "tube amp" implying voltage | Fallback |

## Measured

::: chart search-modes

The real version of this chart comes from the `caddock_search` Analytics Engine dataset once the shop runs in production with the AI binding.
