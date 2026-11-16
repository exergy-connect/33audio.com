# Minimal HTTP request/response between hosts (origin and Worker nodes)

Context: the Exergy ∞ Engineering Academy (exergy-connect/33audio.com, `academy/`) teaches Cloudflare using the 33audio shop and models its request path with lab.net topologies in `network/labnet/*.xp`, run through lab.net's own engine (`tools/run-validation.mjs` flow). lab.net already models routing (BGP/OSPF/IS-IS), forwarding hops, ECMP, and ICMP. The gap below blocks part of the Academy.

## Motivation

Needed by the Academy's deploy Explore (origin vs. edge function), delivery Lab, and every L7 feature below (WAF, load balancer, cache, rate limit).

lab.net hosts answer ICMP, and BGP rides a simulated TCP byte stream, but no host serves an application request. The shop's path ends at an HTTP handler (Pages Function or Worker) and an origin; ICMP to an anycast address is the closest stand-in today.

## Minimal proposed design

- Node: `http` container on `device: linux` hosts: `http.routes: [{path, status, body_bytes, headers}]` (static responses), optional `http.proxy: <node or address>` to forward unmatched paths (a Worker forwarding to an origin).
- Transport: request and response carried over lab.net's existing simulated TCP stream (port 80), so routing, ECMP, link state, and captures apply.
- Validation: new packet type `http-get` with `path`, `host`; `expect: {status, from, header}`.
- Result: hops as for ICMP plus `http-request`/`http-response` hop kinds (`at`, `path`, `status`, `served_by`).
- Metrics: per-host request count by path/status in the snapshot; PCAPNG contains the HTTP bytes.

The fields follow existing conventions: node-level containers like `bgp`/`ospf`, link-level settings like `bandwidth_bps`, `validation.actions` entries like `ping`/`mrc`, and `validate:` steps. Each would be added to `yang/lab-net.yang` and exposed in the inspector and PCAPNG capture like existing features.

## Example

```yaml
nodes:
  web_iah:
    device: linux
    role: host
    http:
      routes:
        - {path: /api/stock, status: 200, body_bytes: 12628, headers: {cache-control: "public, max-age=30"}}
validate:
  - label: stock endpoint answers at the nearest edge
    packet: {from: visitor, type: http-get, target: 192.0.2.10, path: /api/stock, expect: {status: 200, from: web_iah}}
```

## Out of scope

TLS, HTTP/2 and HTTP/3, request bodies, chunked encoding, cookies, scripting of handlers, and real application code in hosts.

## How the Academy will use it

Replace the ICMP stand-in in the anycast labs with `GET /api/stock`, and model the shop's Worker-to-origin hop with `http.proxy`. Until this exists, the Academy marks the dependent section as pending and links this issue.
