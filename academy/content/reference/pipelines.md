---
title: Deployment pipelines
summary: The GitHub Actions workflows that test, build, and deploy both projects.
---

All workflows use `actions/checkout@v7`, `actions/setup-python@v7` with Python 3.15, and `actions/setup-node@v7` with Node 26. Artifacts use `upload-artifact@v7` and `download-artifact@v8`, the latest majors.

## academy.yml

Runs on every push and pull request.

1. **test**: Python and Node unit tests; rebuilds `docs/` and fails if the committed output differs; validates the xYang schema; builds the Academy in check mode (every embed, link, and badge); validates the WAF and cache rules.
2. **labs**: starts the shop with `wrangler pages dev` and a seeded local KV, starts the Academy Worker with `wrangler dev`, runs `lab-check.mjs` for the deploy, discovery, AI, observability, and Academy checks, then measures time to first byte and runs a capped burst against the Academy's own rate limiter. Those two files become REAL TELEMETRY datasets in the uploaded `academy-dist` artifact.
3. **deploy**: on `main` or a manual run. If `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` are missing, it posts a notice and skips the remaining steps, so the run stays green. Otherwise it deploys the exact artifact that the labs job built.

::: embed .github/workflows/academy.yml "  deploy:" "npx wrangler deploy"

## shop-deploy.yml

A manual alternative to the Pages Git integration: creates the `caddock-33audio` project if needed and runs `wrangler pages deploy docs`. It skips cleanly without credentials. Use either this or Git integration, because a Pages project is one or the other.

::: embed .github/workflows/shop-deploy.yml "      - name: Deploy docs/ and functions/"

## refresh.yml and schema.yml

From earlier pull requests: the daily refresh re-parses the listing, syncs eBay, seeds KV (skipping without credentials), rebuilds `docs/`, and checks the schema. `schema.yml` regenerates `docs/schema/` when the YANG models change.

## Why the labs job matters

A tutorial that is not executed rots. Because CI runs the same commands the lab pages show, a change that breaks a lab breaks the build. The lab pages' expected output blocks were captured from those commands.
