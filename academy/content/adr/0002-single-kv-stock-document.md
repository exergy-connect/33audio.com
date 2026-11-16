---
title: One KV document holds all stock
status: Accepted
date: 2026-11-16
summary: One KV document holds all stock.
---

## Context

85 parts, roughly 12 KB of JSON. Pages read stock on every catalog view; writes happen on a paid order or the daily refresh.

## Decision

Store everything in one Workers KV key, `stock`, in the `STOCK` namespace. Cache `/api/stock` for 30 seconds per data center with the Cache API. Make the webhook idempotent by recording applied Checkout Session ids in the document.

## Consequences

- One read per page view, served from the edge.
- Read-modify-write is not atomic. Two simultaneous paid orders can race; the second write wins. The oversold check logs any mismatch, and checkout re-validates stock before payment.
- Writes take up to about 60 seconds to reach every data center.

## Alternatives

- **Durable Object** for serialized decrements. Revisit if orders become concurrent.
- **D1** with a conditional `UPDATE`. Revisit if order history or reporting is needed.
- **One key per part.** More reads, no real benefit at this size.
