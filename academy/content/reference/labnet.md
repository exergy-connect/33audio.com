---
title: lab.net integration
summary: How the request-path labs run on lab.net.
---

## What lab.net is

[lab.net](https://github.com/exergy-connect/lab.net) is Exergy's network lab: routers, switches, and Linux hosts simulated in the browser or in Node, with protocol engines compiled to WebAssembly (BGP, OSPF, IS-IS, BFD, EVPN, SRv6, MPLS). Simulation time and event order are deterministic, so the same topology and seed replay the same way. Topologies are xForm `.xp` files with `nodes`, `links`, and a `validate:` list of state and packet checks. The repository is private; its browser build is public at [exergy-connect.com/lab.net](https://exergy-connect.com/lab.net/).

## How the Academy uses it

| Piece | Where | Uses lab.net's |
| --- | --- | --- |
| Topologies | [network/labnet/](repo:network/labnet/) | `.xp` format, `bgp.advertise`, `validate:` state and packet steps |
| Official validation | `validation-runner` image, `tools/run-validation.mjs` | CLI, JSON report, PCAPNG capture |
| Academy runner | [academy/tools/labnet-path.mjs](repo:academy/tools/labnet-path.mjs) | `loadLab`, `startSimCluster`, `runValidation`, `encodePcapng`, `graphEdges`, `automaticLayout` |
| Recorded runs | [academy/data/labnet/](repo:academy/data/labnet/) | Output of the runner at lab.net commit `06c71623`, seed 42 |
| Figures | `::: labnet` in lesson Markdown | lab.net's layout, hops, routes, and check results |
| Open in lab.net | Link under each figure | `#lab=` gzip artefact loading |

The runner is lab.net's own validation flow plus two additions: it keeps the `hops` that `runValidation()` returns for packet steps, and it reads `fib` and `locRib` from node snapshots. It does not simulate anything itself.

::: embed academy/tools/labnet-path.mjs "export async function runLab"

## Pinned version

The Academy pins lab.net commit `06c71623b044e5ee2d4a9bcfe052bc1b9fe7c6d2`, which is the source of the WebAssembly build its runs were recorded with. To move to a newer lab.net, change the commit in `.github/workflows/academy.yml` and in the lab instructions, regenerate the runs, and review the diff.

## CI

The `labnet` job in `academy.yml` needs a `LABNET_TOKEN` secret: a fine-grained token with read access to `exergy-connect/lab.net` contents. With it, the job checks out lab.net at the pinned commit, runs lab.net's own GitHub Action on both topologies (uploading its PCAPNG and JSON evidence), builds the `validation-runner` image, regenerates the Academy's runs inside it, and fails if they differ from the committed files. Without the secret, the job posts a notice and skips.

## What lab.net cannot model yet

Each gap below has a minimal extension drafted in lab.net's conventions: node containers like `bgp`, link settings like `bandwidth_bps`, `validation.actions`, and `validate:` steps. The Academy marks dependent sections as pending and links them.

::: pending 01-link-delay Request latency per path.

::: pending 02-http-service Origin and Worker nodes that answer HTTP.

::: pending 03-filter-waf A firewall or WAF role.

::: pending 04-load-balancer A load balancer with backends and health checks.

::: pending 05-edge-cache A CDN or edge cache node.

::: pending 06-rate-limit Rate limiting on a node.

::: pending 07-traffic-source A bot or DDoS traffic source.
