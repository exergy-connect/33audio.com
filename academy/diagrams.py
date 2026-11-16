"""Architecture diagrams as small specs, rendered to inline SVG at build time.

Each node is (id, label, sublabel, column, row, kind). Columns and rows are grid cells,
so diagrams stay aligned and scale with the viewBox on small screens.
"""

from __future__ import annotations

from html import escape

CELL_W, CELL_H = 200, 92
BOX_W, BOX_H = 168, 60
PAD = 16

KIND_CLASS = {
    "client": "n-client",
    "edge": "n-edge",
    "fn": "n-fn",
    "store": "n-store",
    "ext": "n-ext",
    "ai": "n-ai",
    "ci": "n-ci",
    "sec": "n-sec",
    "obs": "n-obs",
}

DIAGRAMS: dict[str, dict] = {
    "shop-architecture": {
        "title": "33audio shop on Cloudflare Pages",
        "desc": "Browsers reach Cloudflare's edge. Static pages come from Pages assets. /api routes run as Pages Functions that read the STOCK KV document, cache it with the Cache API, call Stripe and Workers AI, and write Analytics Engine events. GitHub Actions seeds KV.",
        "nodes": [
            ("browser", "Browser", "cart.js · ask.js", 0, 1, "client"),
            ("edge", "Cloudflare edge", "anycast · TLS · cache", 1, 1, "edge"),
            ("assets", "Pages assets", "docs/ (generated)", 2, 0, "edge"),
            ("fn", "Pages Functions", "functions/api/*.js", 2, 2, "fn"),
            ("kv", "Workers KV", "STOCK → key \"stock\"", 3, 1, "store"),
            ("cache", "Cache API", "/api/stock 30 s", 3, 2, "store"),
            ("stripe", "Stripe", "Checkout + webhook", 3, 3, "ext"),
            ("ai", "Workers AI", "env.AI (production)", 2, 3, "ai"),
            ("ae", "Analytics Engine", "caddock_search", 1, 3, "obs"),
            ("gha", "GitHub Actions", "refresh.yml seeds KV", 3, 0, "ci"),
        ],
        "edges": [
            ("browser", "edge", "HTTPS"),
            ("edge", "assets", "GET /parts/…"),
            ("edge", "fn", "/api/*"),
            ("fn", "kv", "get / put"),
            ("fn", "cache", "match / put"),
            ("fn", "stripe", "REST"),
            ("fn", "ai", "run()"),
            ("fn", "ae", "writeDataPoint"),
            ("gha", "kv", "wrangler kv put"),
        ],
    },
    "checkout-flow": {
        "title": "Checkout and webhook flow",
        "desc": "1: the cart posts to /api/checkout. 2: the Function validates against the KV stock document. 3: it creates a Stripe Checkout Session. 4: Stripe calls /api/stripe-webhook after payment. 5: the webhook verifies the signature, decrements stock in KV, and purges the cached /api/stock.",
        "nodes": [
            ("cart", "1 · Cart", "POST /api/checkout", 0, 0, "client"),
            ("checkout", "2 · checkout.js", "validateCart()", 1, 0, "fn"),
            ("kv", "Workers KV", "stock document", 2, 1, "store"),
            ("session", "3 · Stripe Checkout", "hosted payment", 2, 0, "ext"),
            ("hook", "4 · stripe-webhook.js", "verify signature", 1, 2, "fn"),
            ("apply", "5 · applySale()", "idempotent by session", 2, 2, "fn"),
            ("purge", "Cache API", "delete /api/stock", 3, 2, "store"),
        ],
        "edges": [
            ("cart", "checkout", ""),
            ("checkout", "kv", "read"),
            ("checkout", "session", "create"),
            ("session", "hook", "checkout.session.completed"),
            ("hook", "apply", ""),
            ("apply", "kv", "put"),
            ("apply", "purge", ""),
        ],
    },
    "discovery-surfaces": {
        "title": "Discovery surfaces generated from one catalog",
        "desc": "The parsed catalog feeds the static build, which writes HTML with schema.org JSON-LD, llms.txt, catalog.json and catalog.md, the sitemap, and robots.txt. The YANG model feeds xYang, which writes the JSON Schema, JSON-LD context, and vocabulary. Search engines and AI crawlers read those files.",
        "nodes": [
            ("data", "data/catalog.json", "parsed listing", 0, 1, "store"),
            ("build", "catalog/build.py", "static generator", 1, 1, "ci"),
            ("html", "Part pages", "Product + FAQ JSON-LD", 2, 0, "edge"),
            ("llms", "llms.txt", "llms-full.txt", 2, 1, "edge"),
            ("cat", "catalog.json / .md", "$schema + @context", 2, 2, "edge"),
            ("yang", "model/*.yang", "YANG 1.1", 0, 3, "store"),
            ("xyang", "xYang", "catalog/schema.py", 1, 3, "ci"),
            ("schema", "docs/schema/", "JSON Schema · JSON-LD", 2, 3, "edge"),
            ("bots", "Crawlers", "Googlebot · GPTBot · ClaudeBot", 3, 1, "client"),
        ],
        "edges": [
            ("data", "build", ""),
            ("build", "html", ""),
            ("build", "llms", ""),
            ("build", "cat", ""),
            ("yang", "xyang", ""),
            ("xyang", "schema", ""),
            ("html", "bots", ""),
            ("llms", "bots", ""),
            ("cat", "bots", ""),
            ("schema", "cat", "validates"),
        ],
    },
    "ai-search-flow": {
        "title": "Natural-language part search",
        "desc": "The question goes to /api/search. A cached answer returns at once. Otherwise Workers AI extracts JSON filters when bound, and the keyword parser always runs and fills gaps. The ranker scores in-stock parts from catalog.json, and the Function logs and writes an Analytics Engine data point.",
        "nodes": [
            ("q", "Question", "\"10M for a tube amp\"", 0, 1, "client"),
            ("fn", "/api/search", "functions/api/search.js", 1, 1, "fn"),
            ("cache", "Cache API", "AI answers 300 s", 1, 0, "store"),
            ("ai", "Workers AI", "JSON-schema output", 2, 0, "ai"),
            ("kw", "Keyword parser", "always runs", 2, 2, "fn"),
            ("rank", "rankParts()", "value · V · W · tol", 3, 1, "fn"),
            ("catalog", "catalog.json", "via env.ASSETS", 3, 0, "store"),
            ("ae", "Analytics Engine", "mode · latency", 3, 2, "obs"),
        ],
        "edges": [
            ("q", "fn", ""),
            ("fn", "cache", "match"),
            ("fn", "ai", "if env.AI"),
            ("fn", "kw", ""),
            ("ai", "rank", "intent"),
            ("kw", "rank", "fills gaps"),
            ("catalog", "rank", ""),
            ("fn", "ae", ""),
        ],
    },
    "security-layers": {
        "title": "Security layers in front of the shop",
        "desc": "Traffic meets network and HTTP DDoS protection first, then WAF custom rules, then rate-limiting rules, then bot scoring, before reaching Pages Functions. The Academy Worker adds an in-code Rate Limiting binding.",
        "nodes": [
            ("net", "Internet", "clients · bots", 0, 1, "client"),
            ("ddos", "DDoS protection", "L3/4 + HTTP, always on", 1, 1, "sec"),
            ("waf", "WAF custom rules", "security/waf/rules.json", 2, 0, "sec"),
            ("rl", "Rate-limiting rules", "/api/search, /api/checkout", 2, 1, "sec"),
            ("bot", "Bot scoring", "verified bots allowed", 2, 2, "sec"),
            ("app", "Pages Functions", "33audio shop", 3, 1, "fn"),
            ("academy", "Academy Worker", "LAB_LIMITER binding", 3, 2, "fn"),
        ],
        "edges": [
            ("net", "ddos", ""),
            ("ddos", "waf", ""),
            ("waf", "rl", ""),
            ("rl", "bot", ""),
            ("rl", "app", ""),
            ("bot", "academy", ""),
        ],
    },
    "observability-pipeline": {
        "title": "Observability pipeline",
        "desc": "Functions and the Academy Worker write structured logs (Workers Logs, wrangler tail) and Analytics Engine data points. The SQL API and GraphQL Analytics API read them back. The Academy's /api/telemetry turns them into REAL TELEMETRY charts once a token is configured.",
        "nodes": [
            ("fn", "Shop Functions", "console.log JSON", 0, 0, "fn"),
            ("worker", "Academy Worker", "observability.enabled", 0, 2, "fn"),
            ("logs", "Workers Logs", "dashboard · query", 1, 0, "obs"),
            ("tail", "wrangler tail", "live stream", 1, 1, "obs"),
            ("ae", "Analytics Engine", "writeDataPoint", 1, 2, "obs"),
            ("sql", "SQL API", "academy_lab · caddock_search", 2, 2, "obs"),
            ("gql", "GraphQL Analytics", "zone + Workers datasets", 2, 0, "obs"),
            ("tele", "/api/telemetry", "REAL vs SIMULATED", 3, 1, "fn"),
        ],
        "edges": [
            ("fn", "logs", ""),
            ("fn", "tail", ""),
            ("worker", "tail", ""),
            ("worker", "ae", ""),
            ("fn", "ae", ""),
            ("ae", "sql", ""),
            ("sql", "tele", ""),
            ("gql", "tele", ""),
        ],
    },
    "academy-architecture": {
        "title": "How the Academy itself is deployed",
        "desc": "GitHub Actions tests and builds the Academy from this repository, then deploys it as the exergy-academy Worker with static assets. The Worker serves pages, runs live lab endpoints behind a Rate Limiting binding, writes Analytics Engine events, and reads telemetry through the SQL API.",
        "nodes": [
            ("repo", "GitHub repo", "academy/ + shop code", 0, 1, "ci"),
            ("gha", "academy.yml", "test · e2e · deploy", 1, 1, "ci"),
            ("assets", "Static assets", "academy/dist", 2, 0, "edge"),
            ("worker", "exergy-academy", "academy/worker/index.js", 2, 1, "fn"),
            ("rl", "Rate Limiting", "LAB_LIMITER", 3, 0, "sec"),
            ("ae", "Analytics Engine", "academy_lab", 3, 1, "obs"),
            ("api", "Cloudflare API", "SQL · GraphQL", 3, 2, "ext"),
        ],
        "edges": [
            ("repo", "gha", "push"),
            ("gha", "assets", "build"),
            ("gha", "worker", "wrangler deploy"),
            ("worker", "rl", "limit()"),
            ("worker", "ae", "write"),
            ("worker", "api", "/api/telemetry"),
        ],
    },
}


def render_diagram(name: str) -> str:
    spec = DIAGRAMS[name]
    nodes = {n[0]: n for n in spec["nodes"]}
    cols = max(n[3] for n in spec["nodes"]) + 1
    rows = max(n[4] for n in spec["nodes"]) + 1
    width = cols * CELL_W + PAD * 2 - (CELL_W - BOX_W)
    height = rows * CELL_H + PAD * 2 - (CELL_H - BOX_H)

    def box(node):
        x = PAD + node[3] * CELL_W
        y = PAD + node[4] * CELL_H
        return x, y

    parts = [
        f'<svg class="diagram" viewBox="0 0 {width} {height}" role="img" aria-labelledby="d-{name}-t d-{name}-d" xmlns="http://www.w3.org/2000/svg">',
        f'<title id="d-{name}-t">{escape(spec["title"])}</title><desc id="d-{name}-d">{escape(spec["desc"])}</desc>',
        f'<defs><marker id="arrow-{name}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="arrowhead"/></marker></defs>',
    ]
    for a, b, label in spec["edges"]:
        ax, ay = box(nodes[a])
        bx, by = box(nodes[b])
        acx, acy = ax + BOX_W / 2, ay + BOX_H / 2
        bcx, bcy = bx + BOX_W / 2, by + BOX_H / 2
        x1, y1 = clip(acx, acy, bcx, bcy)
        x2, y2 = clip(bcx, bcy, acx, acy)
        parts.append(f'<line class="edge" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" marker-end="url(#arrow-{name})"/>')
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            parts.append(f'<text class="edge-label" x="{mx:.1f}" y="{my - 5:.1f}" text-anchor="middle">{escape(label)}</text>')
    for node in spec["nodes"]:
        x, y = box(node)
        cls = KIND_CLASS.get(node[5], "")
        parts.append(
            f'<g class="node {cls}"><rect x="{x}" y="{y}" width="{BOX_W}" height="{BOX_H}" rx="10"/>'
            f'<text x="{x + BOX_W / 2}" y="{y + 26}" text-anchor="middle" class="node-label">{escape(node[1])}</text>'
            f'<text x="{x + BOX_W / 2}" y="{y + 45}" text-anchor="middle" class="node-sub">{escape(node[2])}</text></g>'
        )
    parts.append("</svg>")
    return (
        f'<figure class="diagram-figure">{"".join(parts)}'
        f'<figcaption><strong>{escape(spec["title"])}.</strong> {escape(spec["desc"])}</figcaption></figure>'
    )


def clip(cx: float, cy: float, tx: float, ty: float) -> tuple[float, float]:
    """Point where the line from a box center toward a target leaves the box."""
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    hw, hh = BOX_W / 2 + 2, BOX_H / 2 + 2
    scale = min(hw / abs(dx) if dx else float("inf"), hh / abs(dy) if dy else float("inf"))
    return cx + dx * scale, cy + dy * scale
