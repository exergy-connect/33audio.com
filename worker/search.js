// Natural-language part search over docs/catalog.json.
// Workers AI turns the question into structured filters when env.AI is bound.
// The keyword parser below always runs, fills gaps, and is the whole answer when AI is absent or fails.

export const DEFAULT_MODEL = "@cf/meta/llama-3.1-8b-instruct-fast";
export const MAX_QUERY = 200;
export const AI_TIMEOUT_MS = 6000;

const MULTIPLIERS = { r: 1, "": 1, k: 1e3, m: 1e6, g: 1e9 };

const FAMILY_HINTS = [
  { re: /\bnew design|\bnew build|\bnot nrnd|\bcurrent production/i, family: "MS", reason: "Caddock marks Type MM not recommended for new designs, so Type MS is preferred" },
];

const USE_HINTS = [
  {
    re: /\b(tube|valve|tubes|valves|plate|anode|b\+|high[- ]voltage|hv)\b/i,
    minVoltage: 500,
    use: "tube amplifier",
    reason: "tube circuits run high plate and B+ voltages, so a 500 V or higher rating is preferred",
  },
  {
    re: /\b(grid[- ]leak|grid resistor|grid stopper)\b/i,
    use: "grid resistor",
    reason: "grid-leak resistors are usually high values in the hundreds of kilohms to megohms",
    defaultOhms: 1e6,
  },
  {
    re: /\b(feedback|nfb|gain[- ]setting)\b/i,
    use: "feedback network",
    maxTolerance: 1,
    reason: "feedback and gain-setting networks benefit from tight tolerance",
  },
  {
    re: /\b(precision|tight tolerance|matched|instrumentation|metrolog)/i,
    maxTolerance: 0.1,
    use: "precision",
    reason: "precision work asks for 0.1% or better",
  },
  {
    re: /\b(power|watt|watts|dissipat|current sense)\b/i,
    minPower: 0.75,
    use: "power",
    reason: "power use prefers the higher wattage series",
  },
];

export function normalizeQuery(q) {
  return String(q ?? "").replace(/\s+/g, " ").trim().slice(0, MAX_QUERY);
}

// Accepts 10M, 10 MΩ, 4.32k, 4K32, 1M5, 470R, 470 ohm, 10 megohm, 2.2 kilohm.
export function parseResistance(text) {
  const s = String(text ?? "");
  const words = s.match(/(\d+(?:\.\d+)?)\s*(mega?\s*ohms?|megs?|kilo\s*ohms?|kohms?|ohms?|Ω)/i);
  if (words) {
    const n = Number(words[1]);
    const unit = words[2].toLowerCase();
    if (unit.startsWith("meg")) return n * 1e6;
    if (unit.startsWith("k")) return n * 1e3;
    return n;
  }
  const rkm = s.match(/(?<![\w.])(\d+)([RKMG])(\d+)(?![\w.])/i);
  if (rkm) {
    return Number(`${rkm[1]}.${rkm[3]}`) * MULTIPLIERS[rkm[2].toLowerCase()];
  }
  const suffix = s.match(/(?<![\w.])(\d+(?:\.\d+)?)\s?([RKMG])(?:Ω|\b)/i);
  if (suffix) return Number(suffix[1]) * MULTIPLIERS[suffix[2].toLowerCase()];
  return null;
}

export function parseTolerance(text) {
  const m = String(text ?? "").match(/(\d+(?:\.\d+)?)\s*%/);
  return m ? Number(m[1]) : null;
}

export function heuristicIntent(q) {
  const text = normalizeQuery(q);
  const intent = { ohms: parseResistance(text), maxTolerance: parseTolerance(text), series: null, family: null, minVoltage: null, minPower: null, use: null, reasons: [] };
  const explicitTolerance = intent.maxTolerance != null;
  const series = text.match(/\b(MM177|MM215|MS151|MS176)\b/i);
  if (series) intent.series = series[1].toUpperCase();
  const family = text.match(/\b(?:type\s*)?(MM|MS)\b/i);
  if (!intent.series && family) intent.family = family[1].toUpperCase();
  for (const hint of FAMILY_HINTS) {
    if (!intent.family && !intent.series && hint.re.test(text)) {
      intent.family = hint.family;
      intent.reasons.push(hint.reason);
    }
  }
  for (const hint of USE_HINTS) {
    if (!hint.re.test(text)) continue;
    intent.use ??= hint.use;
    if (hint.minVoltage) intent.minVoltage = Math.max(intent.minVoltage ?? 0, hint.minVoltage);
    if (hint.minPower) intent.minPower = Math.max(intent.minPower ?? 0, hint.minPower);
    if (hint.maxTolerance && !explicitTolerance) intent.maxTolerance = Math.min(intent.maxTolerance ?? Infinity, hint.maxTolerance);
    if (hint.defaultOhms && intent.ohms == null) intent.ohms = hint.defaultOhms;
    intent.reasons.push(hint.reason);
  }
  return intent;
}

export const INTENT_SCHEMA = {
  type: "object",
  properties: {
    ohms: { type: ["number", "null"], description: "Requested resistance in ohms, for example 10000000 for 10M" },
    max_tolerance_percent: { type: ["number", "null"] },
    series: { type: ["string", "null"], enum: ["MM177", "MM215", "MS151", "MS176", null] },
    family: { type: ["string", "null"], enum: ["MM", "MS", null] },
    min_voltage: { type: ["number", "null"] },
    min_power_watts: { type: ["number", "null"] },
    use: { type: ["string", "null"], description: "Short application phrase, for example tube amplifier" },
  },
  required: ["ohms"],
};

const SYSTEM_PROMPT = `You turn a shopper's question about Caddock film resistors into JSON filters.
The shop sells four series: MM177 (0.6 W, 500 V), MM215 (1 W, 800 V), MS151 (0.5 W, 300 V), MS176 (0.75 W, 500 V).
Type MM is not recommended for new designs; Type MS is. Values run from about 19 ohms to 2.5 megohms.
Convert values to ohms: 10M = 10000000, 4.32K = 4320, 470R = 470. Tube or valve amplifiers imply min_voltage 500.
Return only JSON matching the schema. Use null for anything the question does not say.`;

function finite(n) {
  const x = Number(n);
  return Number.isFinite(x) && x > 0 ? x : null;
}

export function sanitizeAiIntent(raw) {
  let data = raw;
  if (typeof data === "string") {
    const match = data.match(/\{[\s\S]*\}/);
    if (!match) return null;
    try {
      data = JSON.parse(match[0]);
    } catch {
      return null;
    }
  }
  if (!data || typeof data !== "object") return null;
  const series = typeof data.series === "string" && /^(MM177|MM215|MS151|MS176)$/i.test(data.series) ? data.series.toUpperCase() : null;
  const family = typeof data.family === "string" && /^(MM|MS)$/i.test(data.family) ? data.family.toUpperCase() : null;
  return {
    ohms: finite(data.ohms),
    maxTolerance: finite(data.max_tolerance_percent),
    series,
    family,
    minVoltage: finite(data.min_voltage),
    minPower: finite(data.min_power_watts),
    use: typeof data.use === "string" && data.use.trim() ? data.use.trim().slice(0, 60) : null,
  };
}

export async function aiIntent(env, q, { model, timeoutMs = AI_TIMEOUT_MS } = {}) {
  const run = env.AI.run(model || env.SEARCH_MODEL || DEFAULT_MODEL, {
    messages: [
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: q },
    ],
    response_format: { type: "json_schema", json_schema: INTENT_SCHEMA },
    max_tokens: 200,
    temperature: 0,
  });
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`Workers AI timed out after ${timeoutMs} ms`)), timeoutMs);
  });
  try {
    const result = await Promise.race([run, timeout]);
    const parsed = sanitizeAiIntent(result?.response ?? result);
    if (!parsed) throw new Error("Workers AI returned no usable JSON");
    return parsed;
  } finally {
    clearTimeout(timer);
  }
}

// AI fields win where present; the keyword parser fills anything AI left empty.
export function mergeIntent(ai, heuristic) {
  if (!ai) return heuristic;
  const merged = { reasons: [...heuristic.reasons] };
  for (const key of ["ohms", "maxTolerance", "series", "family", "minVoltage", "minPower", "use"]) {
    merged[key] = ai[key] ?? heuristic[key] ?? null;
  }
  return merged;
}

function seriesSpecs(catalog) {
  const map = new Map();
  for (const s of catalog.series ?? []) {
    map.set(s.name, { family: s.family, power: Number(s.power_rating), voltage: Number(s.voltage_rating), nrnd: Boolean(s.not_recommended_for_new_designs) });
  }
  return map;
}

export function partOhms(part) {
  const r = part.resistance ?? {};
  const value = Number(r.value);
  const unit = String(r.unit ?? "ohm").toLowerCase();
  if (unit === "kohm" || unit === "kiloohm") return value * 1e3;
  if (unit === "mohm" || unit === "megaohm") return value * 1e6;
  return value;
}

export function formatOhms(ohms) {
  if (ohms == null) return null;
  const fmt = (n) => String(Number(n.toPrecision(4)));
  if (ohms >= 1e6) return `${fmt(ohms / 1e6)} MΩ`;
  if (ohms >= 1e3) return `${fmt(ohms / 1e3)} kΩ`;
  return `${fmt(ohms)} Ω`;
}

// Scores every in-stock part. Value closeness dominates; ratings and tolerance break ties and explain the pick.
export function rankParts(catalog, intent, limit = 6) {
  const specs = seriesSpecs(catalog);
  const scored = [];
  for (const part of catalog.parts ?? []) {
    if (!(part.quantity > 0)) continue;
    const spec = specs.get(part.series) ?? {};
    if (intent.series && part.series !== intent.series) continue;
    const ohms = partOhms(part);
    const tolerance = Number(part.tolerance?.percent);
    const why = [];
    let score = 0;
    if (intent.ohms) {
      const decades = Math.abs(Math.log10(ohms / intent.ohms));
      if (decades < 1e-6) {
        score += 100;
        why.push("exact value");
      } else {
        score += Math.max(0, 60 - decades * 60);
        why.push(`${Math.round(Math.abs(ohms / intent.ohms - 1) * 100)}% from the requested value`);
      }
    }
    if (intent.family) {
      if (spec.family === intent.family) {
        score += 15;
        why.push(`Type ${spec.family}`);
      } else score -= 15;
    }
    if (intent.minVoltage) {
      if (spec.voltage >= intent.minVoltage) {
        score += 12;
        why.push(`${spec.voltage} V rating`);
      } else score -= 25;
    }
    if (intent.minPower) {
      if (spec.power >= intent.minPower) {
        score += 10;
        why.push(`${spec.power} W rating`);
      } else score -= 10;
    }
    if (intent.maxTolerance) {
      if (tolerance <= intent.maxTolerance) {
        score += 10;
        why.push(`${tolerance}% tolerance`);
      } else score -= 10;
    }
    scored.push({
      part_number: part.part_number,
      series: part.series,
      resistance: part.resistance?.label ?? formatOhms(ohms),
      ohms,
      tolerance: `${tolerance}%`,
      voltage_rating: spec.voltage ?? null,
      power_rating: spec.power ?? null,
      quantity: part.quantity,
      price: part.price,
      url: part.url,
      score: Math.round(score * 10) / 10,
      why,
    });
  }
  scored.sort((a, b) => b.score - a.score || a.part_number.localeCompare(b.part_number));
  return scored.slice(0, limit);
}

export function summarize(intent, results) {
  if (!results.length) return "Nothing in stock matches. Try a value such as 4.32K, or email mark@33audio.com.";
  const asked = intent.ohms ? formatOhms(intent.ohms) : null;
  const exact = intent.ohms && results.some((r) => Math.abs(r.ohms - intent.ohms) < 1e-6);
  const parts = [];
  if (asked && !exact) parts.push(`No ${asked} part is in stock. These are the closest values.`);
  if (asked && exact) parts.push(`${asked} is in stock.`);
  if (intent.use) parts.push(`Ranked for ${intent.use}.`);
  return parts.join(" ") || "Closest matches in stock.";
}

export async function searchCatalog({ q, catalog, env = {}, now = () => Date.now() }) {
  const started = now();
  const query = normalizeQuery(q);
  const heuristic = heuristicIntent(query);
  let mode = "keyword";
  let fallbackReason = null;
  let ai = null;
  if (!query) fallbackReason = "empty query";
  else if (!env.AI) fallbackReason = "Workers AI is not bound (env.AI missing), so the keyword parser answered";
  else {
    try {
      ai = await aiIntent(env, query);
      mode = "ai";
    } catch (error) {
      fallbackReason = `Workers AI failed: ${String(error?.message ?? error).slice(0, 160)}`;
    }
  }
  const intent = mergeIntent(ai, heuristic);
  const results = query ? rankParts(catalog, intent) : [];
  return {
    query,
    mode,
    model: mode === "ai" ? env.SEARCH_MODEL || DEFAULT_MODEL : null,
    fallback_reason: fallbackReason,
    intent: { ...intent, ohms_label: formatOhms(intent.ohms) },
    summary: query ? summarize(intent, results) : "Ask for a part, for example: I need a 10M resistor for a tube amp.",
    results,
    took_ms: now() - started,
  };
}
