# Rate limiting on a node

Context: the Exergy ∞ Engineering Academy (exergy-connect/33audio.com, `academy/`) teaches Cloudflare using the 33audio shop and models its request path with lab.net topologies in `network/labnet/*.xp`, run through lab.net's own engine (`tools/run-validation.mjs` flow). lab.net already models routing (BGP/OSPF/IS-IS), forwarding hops, ECMP, and ICMP. The gap below blocks part of the Academy.

## Motivation

Needed by the Academy's security Explore and Lab (zone rate-limiting rule for /api/search, Workers Rate Limiting binding).

The Academy can demonstrate 429s only against a local Worker. It cannot show where in the path a limit applies or how a limiter keyed by source behaves under many sources.

## Minimal proposed design

- Node: `ratelimit` container: `rules: [{ref, match, key: src | src_prefix_24, requests, period_ms, action: drop | respond: {status: 429}}]`. `match` reuses the the filter proposal (03) matcher.
- Behavior: fixed-window counter per key in simulation time, deterministic; evaluated after `filter`.
- Hops: `ratelimit` hop `{at, ref, key, count, action}` when it acts.
- Metrics: per-rule allowed/limited counters, top keys, in the snapshot; validation `state` check `ratelimit: [{ref, limited_min}]`.

The fields follow existing conventions: node-level containers like `bgp`/`ospf`, link-level settings like `bandwidth_bps`, `validation.actions` entries like `ping`/`mrc`, and `validate:` steps. Each would be added to `yang/lab-net.yang` and exposed in the inspector and PCAPNG capture like existing features.

## Example

```yaml
nodes:
  cf_iah:
    ratelimit:
      rules:
        - {ref: search_rate_limit, match: {http: {path: /api/search}}, key: src, requests: 10, period_ms: 10000, action: {respond: {status: 429}}}
```

## Out of scope

Sliding windows, distributed counters across nodes, token buckets with burst, per-header keys beyond a fixed list.

## How the Academy will use it

Mirror `search_rate_limit` from `security/waf/rules.json` and show limited counts per source when combined with the traffic-source proposal (07). Until this exists, the Academy marks the dependent section as pending and links this issue.
