# Caching reverse proxy node (CDN edge cache)

Context: the Exergy ∞ Engineering Academy (exergy-connect/33audio.com, `academy/`) teaches Cloudflare using the 33audio shop and models its request path with lab.net topologies in `network/labnet/*.xp`, run through lab.net's own engine (`tools/run-validation.mjs` flow). lab.net already models routing (BGP/OSPF/IS-IS), forwarding hops, ECMP, and ICMP. The gap below blocks part of the Academy.

## Motivation

Needed by the Academy's delivery Explore and Lab (Cache API vs. CDN cache, Tiered Cache).

The delivery topic explains HIT/MISS, TTLs, and tiered caching, but lab.net has no node that answers repeated requests from a cache or forwards misses upstream.

## Minimal proposed design

- Builds on the HTTP service proposal (02). Node: `cache` container on an HTTP proxy host: `upstream: <node or address>`, `rules: [{path_prefix, ttl_ms}]`, optional `parent: <node>` for one tier.
- Behavior: key = host + path; MISS forwards to `parent` or `upstream` and stores the response for `ttl_ms` of simulation time; HIT answers locally. Adds `x-cache: HIT|MISS` and `age` headers.
- Hops: `cache` hop `{at, key, result}`.
- Metrics: hits, misses, and hit ratio per node in the snapshot; validation `state` check `cache: {hits, misses}`.

The fields follow existing conventions: node-level containers like `bgp`/`ospf`, link-level settings like `bandwidth_bps`, `validation.actions` entries like `ping`/`mrc`, and `validate:` steps. Each would be added to `yang/lab-net.yang` and exposed in the inspector and PCAPNG capture like existing features.

## Example

```yaml
nodes:
  cf_iah:
    cache:
      upstream: origin
      parent: cf_upper
      rules: [{path_prefix: /api/stock, ttl_ms: 30000}]
validate:
  - label: second request is a HIT
    packet: {from: visitor, type: http-get, target: 192.0.2.10, path: /api/stock, repeat: 2, expect: {status: 200, header: {x-cache: HIT}}}
```

## Out of scope

Vary, revalidation (ETag/304), purge APIs, stale-while-revalidate, cache storage limits.

## How the Academy will use it

Simulate the 30 s `/api/stock` cache and a lower/upper tier, and chart HIT/MISS counts from lab.net next to the shop's real Server-Timing data. Until this exists, the Academy marks the dependent section as pending and links this issue.
