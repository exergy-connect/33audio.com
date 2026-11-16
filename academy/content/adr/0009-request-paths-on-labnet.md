---
title: Request paths are simulated in lab.net, not in Academy code
status: Accepted
date: 2026-11-16
summary: Request paths are simulated in lab.net, not in Academy code.
---

## Context

The delivery topic needs to show how a request reaches Cloudflare: which edge answers, why, and what happens when a path fails. Exergy already has a network simulator, [lab.net](https://github.com/exergy-connect/lab.net) (private), with real BGP, OSPF, and IS-IS engines, deterministic simulation time, validation steps, and PCAPNG capture. A first draft of the Academy defined its own trace format and timing tool for this. That duplicated lab.net and was replaced.

## Decision

- Model the request path as lab.net topologies in `network/labnet/*.xp`, in lab.net's own format and validation language.
- Run them with lab.net's engine: its `validation-runner` image and `tools/run-validation.mjs` for the official report and capture, and `academy/tools/labnet-path.mjs`, which calls the same lab.net modules and also keeps the per-hop path and routing tables that the CLI report omits.
- Pin lab.net to a commit (`06c71623`) and record it in every run. Commit the runs, because lab.net is deterministic for a commit and seed. CI regenerates and diffs them when it has read access to lab.net.
- Draw figures from lab.net's output, including its `automaticLayout()` positions, and link "Open in lab.net" with the topology embedded as lab.net's `#lab=` artefact.
- Badge every run SIMULATED with the lab.net commit and seed. lab.net output is never shown as REAL TELEMETRY.
- Where lab.net cannot model something the showcase needs, draft a minimal lab.net extension and mark the Academy section as pending with a link to the draft ([network/labnet/proposals/](repo:network/labnet/proposals/)).

## Consequences

- Request-path lessons teach the real tool, and improve when lab.net does.
- lab.net does not model propagation delay for ping, so the Academy shows paths and hop counts but no simulated latency. Measured latency comes from the shop's own HTTP measurements.
- Regenerating runs needs lab.net access (private repository) and its WASM build. Readers without access can still open every lab in the public browser build at exergy-connect.com.
