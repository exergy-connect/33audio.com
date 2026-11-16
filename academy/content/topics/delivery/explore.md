---
title: DNS, delivery, caching, and latency · Explore
summary: Follow a request from DNS to the edge with lab.net anycast simulations, choose what to cache at each layer (browser, edge, Cache API, Tiered Cache), and measure what the shop adds.
---

## The request path

A request for `/api/stock` crosses the visitor's resolver, the visitor's ISP, the path from that ISP to Cloudflare, and the Cloudflare data center that answers. Which data center answers is decided by BGP: Cloudflare announces the same anycast prefixes from every location, and each ISP forwards to the announcement it prefers, usually the one with the shortest AS path.

**DNS.** `caddock-33audio.pages.dev` resolves to Cloudflare anycast addresses. With a custom domain, a proxied CNAME to the Pages project (or a Cloudflare zone for the apex) keeps that property. Unproxied records would skip the edge and every protection on this site.

**Connection.** Cloudflare terminates TCP and TLS at the edge. HTTP/2 and HTTP/3 are on by default, and the `cf-ray` header names the data center that answered, for example `…-IAH` for Houston.

## Anycast routing, simulated in lab.net

The routing half of that path is modeled with [lab.net](/reference/labnet/), Exergy's deterministic network simulator, not with a hand-drawn diagram. [network/labnet/anycast-edge.xp](repo:network/labnet/anycast-edge.xp) is a lab.net topology: a Houston visitor, the visitor's ISP (AS 64510), a transit provider (AS 64520), and two Cloudflare edge routers (AS 13335, IAH and DFW) that both originate the documentation prefix `192.0.2.0/24` and both host `192.0.2.10`.

::: embed network/labnet/anycast-edge.xp "  validate:"

lab.net runs real BGP sessions between those routers, selects routes, builds forwarding tables, and forwards an ICMP echo hop by hop. The figure below is lab.net's own output for that file: its layout, its validation results, the forwarding hops it returned, and the ISP's BGP table.

::: labnet anycast-edge 192.0.2.0/24

Remove the direct IAH peering ([anycast-edge-failover.xp](repo:network/labnet/anycast-edge-failover.xp)) and the same address is reached at DFW through transit. Nothing changed on the visitor or the shop: anycast moved the traffic.

::: labnet anycast-edge-failover 192.0.2.0/24

What lab.net shows here is the forwarding path and the routing decision behind it. The TTL column counts router hops: the failover path has one more.

lab.net also lists an iBGP session between `cf_iah` and `cf_dfw`, because it pairs routers that share an AS. They have no link and no route to each other's loopback, so that session stays `idle` and plays no part in the path. Real Cloudflare locations are connected by Cloudflare's own backbone, which this two-location model leaves out.

::: pending 02-http-service The labs above use ICMP to the anycast address as a stand-in for an HTTP request, because lab.net hosts do not yet serve HTTP.

## How much latency the path adds

lab.net does not model propagation delay for ping today (see its `SIMULATION-FIDELITY.md`), so the Academy does not show simulated round-trip times for these paths and does not invent any.

::: pending 01-link-delay With per-link delay, the anycast labs would report the round-trip time of the nearest edge and of the failover path.

Measured latency for the shop comes from real requests instead: `Server-Timing` on every API response (below) and the time-to-first-byte measurements in the [observability topic](/explore/observability/).

## Cache layers in this repo

| Layer | Where it is set | What it caches | TTL |
| --- | --- | --- | --- |
| Browser | `Cache-Control` from Pages and the Functions | Static pages revalidate (`max-age=0, must-revalidate` with ETag); `/api/stock` | 0 s / 30 s |
| Pages asset cache | Automatic | Every file in `docs/` until the next deployment | Per deployment |
| Cache API | [functions/api/stock.js](repo:functions/api/stock.js), [functions/api/search.js](repo:functions/api/search.js) | Stock JSON; AI search answers | 30 s; 300 s |
| Cache Rules | [delivery/cache-rules.json](repo:delivery/cache-rules.json) | Discovery files, datasheets; bypass checkout and webhook | 300 s; 30 days |
| Tiered Cache | Same file, `settings` | Lower-tier data centers ask an upper tier before the origin | – |

The Cache API is per data center and is not shared across them. Tiered Cache applies to the zone's CDN cache, not to `caches.default`. That is why `/api/stock` keeps its TTL short: each data center refreshes on its own.

## Cache Rules as code

The shop's cache rules sit in the repository next to the WAF rules, and the same script applies them through the Rulesets API:

::: embed delivery/cache-rules.json "\"http_request_cache_settings\""

Tiered Cache with Smart Topology is enabled by two zone setting calls listed under `settings` in the same file. Smart Topology picks upper-tier data centers close to the origin. For a Pages origin, that mostly helps the dynamic routes, because static assets are already distributed.

## Building a cache key you can trust

The Cache API keys on a `Request`. `stockCacheKey()` normalizes every variant of `/api/stock` to one GET request on the same origin, so query strings cannot fragment the cache or be used to bypass it:

::: embed worker/env.js "export function stockCacheKey"

The search Function does the same with the lower-cased query, and only caches AI answers.

## Server-side timing

Both Functions report their own timing with the `Server-Timing` header. Workers clocks only advance across I/O, which is exactly what these entries measure:

::: embed worker/env.js "export function serverTiming" "=}"

## Cache behavior

::: chart cache-hit-ratio

::: pending 05-edge-cache With a caching node in lab.net, this curve could come from a simulated edge and upper tier instead of example numbers.

## Trade-offs

| Choice | Gain | Cost |
| --- | --- | --- |
| 30 s TTL on `/api/stock` | Most reads skip KV | Other data centers can show a sold-out part for up to 30 s; checkout re-checks |
| Cache only AI search answers | Saves Workers AI cost on repeats | Keyword answers run every time, at about 1 ms |
| Long edge TTL on datasheets | Near-zero origin traffic | Renaming is required to change a scan |
| Short edge TTL on llms.txt and catalog.json | Crawlers see the daily refresh within 5 minutes | Slightly more origin hits |
