---
title: Workers AI extracts filters; code ranks; keywords fall back
status: Accepted
date: 2026-11-16
summary: Workers AI extracts filters; code ranks; keywords fall back.
---

## Context

Buyers describe needs in words ("10M for a tube amp"). The catalog is small, numeric, and must never be misrepresented.

## Decision

Use Workers AI only to convert the question into a JSON filter object (JSON mode with a schema). Rank in-stock parts with deterministic code. Always run a keyword parser, merge it with the AI result, and use it alone when AI is unavailable, slow (over 6 s), or returns unusable output. Report the mode and the fallback reason in every response.

## Consequences

- Results are always real catalog entries with real prices and stock.
- A small, cheap model is enough.
- The feature works in local dev, preview deployments, and accounts without Workers AI.

## Alternatives

- **Vectorize embeddings.** Weak on numeric values such as 4.32 kΩ.
- **LLM-written answers with the catalog in the prompt.** Risk of invented parts; long prompts on every call.
