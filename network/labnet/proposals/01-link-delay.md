# Link propagation delay and RTT in ping results

Context: the Exergy ∞ Engineering Academy (exergy-connect/33audio.com, `academy/`) teaches Cloudflare using the 33audio shop and models its request path with lab.net topologies in `network/labnet/*.xp`, run through lab.net's own engine (`tools/run-validation.mjs` flow). lab.net already models routing (BGP/OSPF/IS-IS), forwarding hops, ECMP, and ICMP. The gap below blocks part of the Academy.

## Motivation

Needed by the Academy's delivery Explore page and Lab ("what latency to expect" on the anycast path); observability Explore (comparing nearest-edge vs. failover RTT).

`SIMULATION-FIDELITY.md` states ping and aggregate flows do not model propagation latency, and `PLAN.md` Phase 3 lists "delay/bandwidth" for the virtual link model. Today the Academy can show *which* edge a request reaches (anycast, failover) but not *how much longer* the failover path takes.

## Minimal proposed design

- Topology: optional `delay_ms` (number ≥ 0, default 0) on a link, next to the existing `bandwidth_bps`. Applies per direction; optional `delay_ms: {a: 3, b: 5}` keyed by endpoint order for asymmetry. YANG: `leaf delay_ms { type decimal64 { fraction-digits 3; } }` under `/topology/links`.
- Behavior: frame delivery on that link is scheduled `delay_ms` later in simulation time (deterministic, no jitter). Protocol timers see the delay naturally.
- `dataplane.ping()` returns `rtt_ms` (simulated) per sequence, and each `forward` hop gains `at_ms` (sim time the frame arrived).
- Validation: `packet` steps accept `expect.max_rtt_ms`.
- Metrics: `rtt_ms` in ping results and in the validation report `detail`; inspector shows per-link delay.

The fields follow existing conventions: node-level containers like `bgp`/`ospf`, link-level settings like `bandwidth_bps`, `validation.actions` entries like `ping`/`mrc`, and `validate:` steps. Each would be added to `yang/lab-net.yang` and exposed in the inspector and PCAPNG capture like existing features.

## Example

```yaml
links:
  - interfaces: [{node: isp_hou}, {node: cf_iah}]
    delay_ms: 2
  - interfaces: [{node: isp_hou}, {node: transit}]
    delay_ms: 6
validate:
  - label: nearest edge answers within 10 ms
    packet: {from: visitor, type: icmp-echo, target: 192.0.2.10, expect: {type: icmp-echo-reply, from: web_iah, max_rtt_ms: 10}}
```

## Out of scope

Jitter, loss, queueing delay, serialization delay for ICMP, and per-flow latency in the fluid flow model.

## How the Academy will use it

Add `delay_ms` to `network/labnet/anycast-edge*.xp` and chart simulated RTT for nearest edge vs. failover, badged SIMULATED with the lab.net commit. Until this exists, the Academy marks the dependent section as pending and links this issue.
