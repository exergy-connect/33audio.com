// HTTP request with per-phase timings (DNS, TCP connect, TLS, first byte, download), using only node:http(s).

import http from "node:http";
import https from "node:https";
import { performance } from "node:perf_hooks";

export function timedRequest(url, { method = "GET", headers = {}, body, timeoutMs = 15000 } = {}) {
  const target = new URL(url);
  const lib = target.protocol === "https:" ? https : http;
  return new Promise((resolve, reject) => {
    const t = { start: performance.now() };
    const req = lib.request(target, { method, headers: { "User-Agent": "exergy-academy-lab/1.0", ...headers }, agent: false }, (res) => {
      t.firstByte = performance.now();
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => {
        t.end = performance.now();
        const buffer = Buffer.concat(chunks);
        resolve({
          status: res.statusCode,
          httpVersion: res.httpVersion,
          headers: res.headers,
          body: buffer.toString("utf8"),
          bytes: buffer.length,
          remoteAddress: res.socket?.remoteAddress ?? null,
          timings: phases(t),
        });
      });
    });
    req.setTimeout(timeoutMs, () => req.destroy(new Error(`timeout after ${timeoutMs} ms`)));
    req.on("socket", (socket) => {
      socket.on("lookup", () => (t.lookup = performance.now()));
      socket.on("connect", () => (t.connect = performance.now()));
      socket.on("secureConnect", () => (t.secure = performance.now()));
    });
    req.on("error", reject);
    if (body) req.write(body);
    req.end();
  });
}

function round(n) {
  return Math.round(n * 10) / 10;
}

export function phases(t) {
  const lookup = t.lookup ?? t.start;
  const connect = t.connect ?? lookup;
  const secure = t.secure ?? connect;
  return {
    dns_ms: round(lookup - t.start),
    connect_ms: round(connect - lookup),
    tls_ms: round(secure - connect),
    ttfb_ms: round(t.firstByte - t.start),
    server_wait_ms: round(t.firstByte - secure),
    download_ms: round(t.end - t.firstByte),
    total_ms: round(t.end - t.start),
  };
}

// Server-Timing: cache;desc="MISS";dur=1, kv;desc="STOCK get";dur=3
export function parseServerTiming(header) {
  if (!header) return [];
  return String(header)
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map((entry) => {
      const [name, ...params] = entry.split(";").map((p) => p.trim());
      const out = { name, dur: null, desc: null };
      for (const param of params) {
        const [key, raw = ""] = param.split("=");
        const value = raw.replace(/^"|"$/g, "");
        if (key === "dur") out.dur = Number(value);
        if (key === "desc") out.desc = value;
      }
      return out;
    });
}

export function percentile(values, p) {
  const sorted = values.filter((v) => Number.isFinite(v)).sort((a, b) => a - b);
  if (!sorted.length) return null;
  const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1));
  return sorted[index];
}

export function parseArgs(argv, defaults = {}) {
  const args = { ...defaults, _: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg.startsWith("--")) {
      const [key, inline] = arg.slice(2).split("=", 2);
      if (inline !== undefined) args[key] = inline;
      else if (i + 1 < argv.length && !argv[i + 1].startsWith("--")) args[key] = argv[++i];
      else args[key] = true;
    } else args._.push(arg);
  }
  return args;
}
