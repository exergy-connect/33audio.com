---
title: WAF, rate-limit, and cache rules live in the repository
status: Accepted
date: 2026-11-16
summary: WAF, rate-limit, and cache rules live in the repository.
---

## Context

Dashboard changes are fast but unreviewed and unrecoverable. The shop needs a handful of custom rules, one or two rate limits, and three cache rules on one zone.

## Decision

Keep the rules as JSON (`security/waf/rules.json`, `delivery/cache-rules.json`) and apply them with `security/waf/apply.mjs`, which validates, prints a dry run by default, and replaces each phase entrypoint through the Rulesets API with `--apply`.

## Consequences

- Rules are reviewed in pull requests and reproducible on a new zone.
- Replacing an entrypoint overwrites rules added in the dashboard. The repository is the source of truth.
- No state file: the script cannot detect drift, but `--show` prints the live rules for comparison.

## Alternatives

- **Terraform** with the Cloudflare provider: drift detection and plans, at the cost of state management. A good next step if more zones appear.
