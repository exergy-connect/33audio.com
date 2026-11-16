# Load balancer node with a VIP, backends, and health checks

Context: the Exergy ∞ Engineering Academy (exergy-connect/33audio.com, `academy/`) teaches Cloudflare using the 33audio shop and models its request path with lab.net topologies in `network/labnet/*.xp`, run through lab.net's own engine (`tools/run-validation.mjs` flow). lab.net already models routing (BGP/OSPF/IS-IS), forwarding hops, ECMP, and ICMP. The gap below blocks part of the Academy.

## Motivation

Needed by the Academy's deploy Explore (origin pools behind the edge) and delivery Explore (anycast vs. load balancing trade-off).

lab.net offers ECMP and anycast gateways, but nothing that distributes requests to a pool by policy and removes unhealthy backends, which is how a Cloudflare Load Balancer or an origin pool behaves.

## Minimal proposed design

- Node: `load_balancer` container on a `device: linux` node: `vip` (address), `backends: [node|address]`, `method: round_robin | hash_src` (deterministic), `health: {type: icmp, interval_ms, down_after}`.
- Behavior: traffic to the VIP is rewritten to the chosen healthy backend (destination NAT) and replies restored; backends failing health are skipped.
- Hops: `lb` hop `{at, vip, backend, reason}`.
- Validation: `state` check `load_balancer: {healthy: [..]}`; packet expectations already cover `from`.
- Metrics: per-backend selections and health transitions in the snapshot.

The fields follow existing conventions: node-level containers like `bgp`/`ospf`, link-level settings like `bandwidth_bps`, `validation.actions` entries like `ping`/`mrc`, and `validate:` steps. Each would be added to `yang/lab-net.yang` and exposed in the inspector and PCAPNG capture like existing features.

## Example

```yaml
nodes:
  lb1:
    device: linux
    load_balancer:
      vip: 198.51.100.10
      backends: [origin_a, origin_b]
      method: round_robin
      health: {type: icmp, interval_ms: 1000, down_after: 3}
```

## Out of scope

Weighted/geo steering, session affinity cookies, TLS termination, L7 routing (that belongs with the HTTP service proposal (02)).

## How the Academy will use it

Show an origin pool behind the edge and fail one origin in the deploy Explore page, with lab.net's selection counters as the evidence. Until this exists, the Academy marks the dependent section as pending and links this issue.
