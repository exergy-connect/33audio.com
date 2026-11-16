---
title: Pages for the shop, a Worker with static assets for the Academy
status: Accepted
date: 2026-11-16
summary: Pages for the shop, a Worker with static assets for the Academy.
---

## Context

The shop is about a hundred generated HTML files plus four API routes. It already deploys from Git on Cloudflare Pages (PR #3), with `docs/` committed by the daily refresh workflow. The Academy needs live lab endpoints, the Workers Rate Limiting binding, and Workers Logs.

## Decision

Keep the shop on **Pages with Pages Functions** (project `caddock-33audio`). Deploy the Academy as a **Worker with static assets** (`exergy-academy`), built from `academy/` and deployed by `.github/workflows/academy.yml`.

## Consequences

- The shop keeps Git integration, preview deployments per branch, and no build step on Cloudflare.
- The Academy can use `[[ratelimits]]` and `[observability]`, which Wrangler 4.162.0 rejects for Pages projects (its `supportedPagesConfigFields` list has neither).
- Two deployables, two `wrangler.toml` files. Each can be deployed without the other.

## Alternatives

- **Both on Pages.** No rate-limit binding or Workers Logs for the Academy.
- **Move the shop to Workers with static assets.** Possible and Cloudflare's recommended direction for new projects, but it would rewrite PR #3's routing and deployment for no user-visible gain today.
