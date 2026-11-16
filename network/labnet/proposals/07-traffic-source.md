# Deterministic traffic source for bots and floods

Context: the Exergy ∞ Engineering Academy (exergy-connect/33audio.com, `academy/`) teaches Cloudflare using the 33audio shop and models its request path with lab.net topologies in `network/labnet/*.xp`, run through lab.net's own engine (`tools/run-validation.mjs` flow). lab.net already models routing (BGP/OSPF/IS-IS), forwarding hops, ECMP, and ICMP. The gap below blocks part of the Academy.

## Motivation

Needed by the Academy's security Explore (DDoS layers, bots) and security Lab (controlled traffic without hitting any real deployment).

The only safe way to show DDoS mitigation or bot rate limits is against a model. lab.net validation actions send single pings or one MRC transfer; there is no sustained, multi-source request generator.

## Minimal proposed design

- Node action: `validation.actions` entry `type: traffic` with `target`, `kind: icmp | http-get` (http after the HTTP service proposal (02)), `path`, `rate_per_s`, `duration_ms`, `sources: {count, prefix}` (synthetic source addresses from a prefix behind the node), `seed`.
- Behavior: schedules requests in simulation time; responses are tallied, not individually captured unless capture is on.
- Validation step: `traffic: {from, ...expect: {min_ok, max_ok, min_limited}}`.
- Metrics: per-second sent/ok/dropped/limited series and per-hop drop counters in the result, suitable for charting.

The fields follow existing conventions: node-level containers like `bgp`/`ospf`, link-level settings like `bandwidth_bps`, `validation.actions` entries like `ping`/`mrc`, and `validate:` steps. Each would be added to `yang/lab-net.yang` and exposed in the inspector and PCAPNG capture like existing features.

## Example

```yaml
nodes:
  botnet:
    device: linux
    validation:
      actions:
        - {type: traffic, target: 192.0.2.10, kind: http-get, path: /api/search, rate_per_s: 200, duration_ms: 5000, sources: {count: 50, prefix: 203.0.113.0/24}, seed: 7}
```

## Out of scope

Volumetric L3/L4 attack modeling, spoofing outside the declared prefix, realistic bot behavior, TCP SYN floods.

## How the Academy will use it

Run a seeded flood against the simulated edge with the filter proposal (03) and the rate-limit proposal (06), and chart lab.net's per-second results badged SIMULATED, instead of sending any real attack traffic. Until this exists, the Academy marks the dependent section as pending and links this issue.
