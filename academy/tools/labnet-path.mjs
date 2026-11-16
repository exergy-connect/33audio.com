#!/usr/bin/env node
// Runs a lab.net topology with lab.net's own engine and keeps what its CLI report drops:
// the hop list of each ICMP validation packet and the routing tables of chosen nodes.
// Mirrors lab.net's tools/run-validation.mjs (loadLab → startSimCluster → step → runValidation).
//
//   node academy/tools/labnet-path.mjs network/labnet/anycast-edge.xp \
//     --labnet ../lab.net --nodes isp_hou,cf_iah --out academy/data/labnet/anycast-edge.json
//
// --labnet is a lab.net checkout with build/wasm/exergy-lab.net.{js,wasm} and build/yang
// (make wasm or the browser-wasm CI artifact, then npm ci && npm run build:yang). Node 24+.

import { execFileSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

import { parseArgs } from "./lib/http.mjs";

function labnetCommit(dir) {
  if (process.env.LABNET_COMMIT) return process.env.LABNET_COMMIT;
  try {
    return execFileSync("git", ["-C", dir, "rev-parse", "HEAD"], { encoding: "utf8" }).trim();
  } catch {
    return null;
  }
}

export function routeView(entry) {
  return {
    prefix: `${entry.prefix}/${entry.length}`,
    protocol: entry.type ?? null,
    nexthop: entry.nexthop ?? null,
    aspath: entry.aspath ?? null,
    ifname: entry.ifname ?? entry.iface ?? null,
  };
}

export function hopView(hop) {
  const keep = ["kind", "at", "from", "to", "ttl", "via", "action", "ifname", "seq"];
  return Object.fromEntries(keep.filter((key) => hop[key] != null).map((key) => [key, hop[key]]));
}

export async function runLab({ labnet, topologyPath, nodes = [], settleMs = 1000, seed = 42, pcap = null }) {
  const root = path.resolve(labnet);
  const mod = (rel) => import(pathToFileURL(path.join(root, rel)).href);
  const { loadLab } = await mod("src/lab/topology/netlab.js");
  const { startSimCluster } = await mod("src/lab/simulation/cluster.js");
  const { runValidation } = await mod("src/lab/validation/run.js");
  const { encodePcapng } = await mod("src/lab/capture/pcapng.js");
  const { graphEdges } = await mod("src/lab/presentation/graph.js");
  const { automaticLayout } = await mod("src/ui/auto-layout.js");
  const { default: createModule } = await mod("build/wasm/exergy-lab.net.js");

  const source = await readFile(topologyPath, "utf8");
  const topology = loadLab(source, { filename: path.resolve(topologyPath) });
  const module = await createModule();
  const cluster = await startSimCluster(topology, { module, seed, maxShards: 1, useWorkers: false, capture: pcap ? { omitBackground: false } : false });
  const dataplane = cluster.dataplane;
  try {
    await cluster.step(dataplane.nowMs + settleMs);
    const sessions = cluster.sessions.map((s) => ({ ...s, left: s.left?.name ?? s.left, right: s.right?.name ?? s.right }));
    const results = runValidation(dataplane, topology.validate ?? [], sessions, topology);
    const tables = {};
    for (const name of nodes) {
      const snap = dataplane.snapshot(name);
      if (!snap) throw new Error(`unknown node ${name}`);
      tables[name] = { fib: (snap.fib ?? []).map(routeView), locRib: (snap.locRib ?? []).map(routeView) };
    }
    let capture = null;
    if (pcap) {
      const packets = dataplane.stopCapture();
      await mkdir(path.dirname(pcap), { recursive: true });
      await writeFile(pcap, encodePcapng(packets, { names: dataplane.hostnames(topology.name || "lab") }));
      capture = { path: pcap, records: packets.length };
    }
    const layout = automaticLayout({ nodes: Object.keys(topology.nodes).map((id) => ({ id })), links: topology.links ?? [] });
    const graph = {
      nodes: Object.entries(topology.nodes).map(([id, node]) => ({
        id,
        device: node.device ?? null,
        role: node.role ?? null,
        as: node.bgp?.as ?? null,
        x: layout.positions.get(id)?.x ?? 0,
        y: layout.positions.get(id)?.y ?? 0,
      })),
      edges: graphEdges(topology).map(({ a, b, aIf, bIf }) => ({ a, b, aIf, bIf })),
    };
    return {
      topology: topology.name,
      graph,
      timeMs: dataplane.nowMs,
      sessions: sessions.map(({ left, right, leftAs, rightAs, state }) => ({ left, right, leftAs, rightAs, state })),
      results: results.map(({ label, ok, detail, hops }) => ({ label, ok, detail, ...(hops ? { hops: hops.map(hopView) } : {}) })),
      tables,
      capture,
    };
  } finally {
    await cluster.dispose();
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2), { labnet: process.env.LABNET_DIR ?? "../lab.net", "settle-ms": "1000", seed: "42" });
  const topologyPath = args._[0];
  if (!topologyPath) {
    console.error("usage: node academy/tools/labnet-path.mjs <topology.xp> --labnet <lab.net checkout> [--nodes a,b] [--out file] [--pcap file]");
    process.exit(2);
  }
  console.debug = () => {};
  const run = await runLab({
    labnet: args.labnet,
    topologyPath,
    nodes: typeof args.nodes === "string" ? args.nodes.split(",") : [],
    settleMs: Number(args["settle-ms"]),
    seed: Number(args.seed),
    pcap: typeof args.pcap === "string" ? args.pcap : null,
  });
  const output = {
    kind: "simulated",
    title: `lab.net run of ${path.basename(topologyPath)}`,
    simulator: { name: "lab.net", repo: "exergy-connect/lab.net", commit: labnetCommit(args.labnet), seed: Number(args.seed), settle_ms: Number(args["settle-ms"]) },
    topology_file: topologyPath,
    make_real: [
      "This is lab.net's deterministic routing simulation of the topology file, not a measurement of the Internet.",
      "lab.net computes BGP sessions, routes, and the forwarding path; it does not model propagation delay for ping.",
      "Measured latency for the shop comes from the observability lab (measure.mjs against your deployment).",
    ],
    ...run,
  };
  for (const r of run.results) console.error(`${r.ok ? "PASS" : "FAIL"} ${r.label}: ${r.detail}`);
  const text = JSON.stringify(output, null, 2) + "\n";
  if (typeof args.out === "string") {
    await mkdir(path.dirname(args.out), { recursive: true });
    await writeFile(args.out, text);
    console.error(`wrote ${args.out}`);
  } else process.stdout.write(text);
  process.exitCode = run.results.length && run.results.every((r) => r.ok) ? 0 : 1;
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) await main();
