---
title: Declare the Workers AI binding only for production
status: Accepted
date: 2026-11-16
summary: Declare the Workers AI binding only for production.
---

## Context

Workers AI has no local emulation. With `[ai]` at the top level of `wrangler.toml`, `wrangler pages dev` tries to open a remote proxy session and, without `CLOUDFLARE_API_TOKEN`, fails to start: "In a non-interactive environment, it's necessary to set a CLOUDFLARE_API_TOKEN environment variable". That would break every local lab.

## Decision

Declare `[env.production.ai]` only, and repeat the KV, Analytics Engine, and variable bindings under `[env.production]`, because Pages does not inherit bindings into named environments. A unit test checks that the two sets match.

## Consequences

- `wrangler pages dev` starts with no account. `/api/search` uses the keyword parser and says so.
- Production deployments get `env.AI`. Preview deployments do not, which also demonstrates the fallback.
- Developers who want real AI locally pass `--ai AI` to `wrangler pages dev` with a token.
