# Ordered packet/request filter on a node (firewall and WAF role)

Context: the Exergy ∞ Engineering Academy (exergy-connect/33audio.com, `academy/`) teaches Cloudflare using the 33audio shop and models its request path with lab.net topologies in `network/labnet/*.xp`, run through lab.net's own engine (`tools/run-validation.mjs` flow). lab.net already models routing (BGP/OSPF/IS-IS), forwarding hops, ECMP, and ICMP. The gap below blocks part of the Academy.

## Motivation

Needed by the Academy's security Explore (WAF custom rules) and security Lab (verify blocks without touching a real zone).

The Academy keeps real WAF rules in `security/waf/rules.json` but can only verify them on a live Cloudflare zone. lab.net has no node that drops or answers traffic by rule.

## Minimal proposed design

- Node: `filter` container on any node: ordered `rules: [{ref, match, action}]`, first match wins, default `allow`.
- `match` (all optional, ANDed): `proto` (icmp|tcp|udp), `src`/`dst` prefix, `dport`, `ifname`; once the HTTP service proposal (02) exists, `http.method`, `http.path` (exact or prefix), `http.header`.
- `action`: `allow`, `drop`, `reject` (ICMP unreachable or TCP RST), and for HTTP `respond: {status}` (e.g. 403).
- Evaluated on ingress before forwarding/delivery; emits a `filter` hop `{at, ref, action}` and a `drop` hop on block.
- Validation: `state` check `filter: [{ref, hits}]`; packet steps can `expect: {type: dropped, at: <node>}`.
- Metrics: per-rule hit counters in the node snapshot and inspector.

The fields follow existing conventions: node-level containers like `bgp`/`ospf`, link-level settings like `bandwidth_bps`, `validation.actions` entries like `ping`/`mrc`, and `validate:` steps. Each would be added to `yang/lab-net.yang` and exposed in the inspector and PCAPNG capture like existing features.

## Example

```yaml
nodes:
  cf_iah:
    filter:
      rules:
        - {ref: block_exploit_probes, match: {http: {path_prefix: /wp-}}, action: {respond: {status: 403}}}
        - {ref: webhook_post_only, match: {http: {path: /api/stripe-webhook, method_not: POST}}, action: {respond: {status: 403}}}
validate:
  - label: probe is blocked at the edge
    packet: {from: visitor, type: http-get, target: 192.0.2.10, path: /wp-login.php, expect: {status: 403, from: cf_iah}}
```

## Out of scope

Stateful connection tracking, NAT, regex matching, managed rulesets, rule expression language parity with Cloudflare.

## How the Academy will use it

Translate the enabled rules in `security/waf/rules.json` into a lab.net `filter` and run the security lab's probe checks in simulation before applying them to a zone. Until this exists, the Academy marks the dependent section as pending and links this issue.
