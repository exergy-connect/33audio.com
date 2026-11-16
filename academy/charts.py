"""Datasets, provenance badges, and build-time SVG charts.

Every dataset declares kind "real" or "simulated". Real data must name its source and
collection time. Simulated data must say how to replace it with real data. The build
refuses anything else, so a chart can never appear without a provenance badge.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

PALETTE = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--c4)"]


class DatasetError(ValueError):
    pass


def load_dataset(name: str, real_dir: Path, sim_dir: Path) -> dict:
    for folder in (real_dir, sim_dir):
        path = folder / f"{name}.json"
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            data["_path"] = str(path)
            validate_dataset(name, data)
            return data
    raise DatasetError(f"dataset {name!r} not found in {real_dir} or {sim_dir}")


def validate_dataset(name: str, data: dict) -> None:
    kind = data.get("kind")
    if kind == "real":
        for key in ("source", "collected_at"):
            if not data.get(key):
                raise DatasetError(f"real dataset {name!r} is missing {key!r}")
    elif kind == "simulated":
        if not data.get("make_real"):
            raise DatasetError(f"simulated dataset {name!r} must list make_real steps")
    else:
        raise DatasetError(f"dataset {name!r} has kind {kind!r}; use 'real' or 'simulated'")


def badge(data: dict) -> str:
    if data["kind"] == "real":
        meta = f'{escape(data["source"])} · {escape(data["collected_at"])}'
        env = f' · {escape(data["environment"])}' if data.get("environment") else ""
        return f'<div class="provenance"><span class="badge badge-real">REAL TELEMETRY</span><span class="badge-meta">{meta}{env}</span></div>'
    return '<div class="provenance"><span class="badge badge-sim">SIMULATED / EXAMPLE DATA</span><span class="badge-meta">Illustrative numbers, not measurements</span></div>'


def make_real(data: dict) -> str:
    if data["kind"] == "real":
        return ""
    steps = "".join(f"<li>{escape(step)}</li>" for step in data["make_real"])
    return f'<details class="make-real"><summary>How to switch this to real telemetry</summary><ol>{steps}</ol></details>'


def data_table(data: dict) -> str:
    series = (data.get("series") or []) + (data.get("extra_columns") or [])
    x = data.get("x", "label")
    head = f"<th scope=\"col\">{escape(data.get('x_label', x))}</th>" + "".join(f"<th scope=\"col\">{escape(s['label'])}</th>" for s in series)
    rows = []
    for row in data.get("rows", []):
        cells = "".join(f"<td>{escape(fmt(row.get(s['key'])))}</td>" for s in series)
        rows.append(f"<tr><th scope=\"row\">{escape(str(row.get(x, '')))}</th>{cells}</tr>")
    return f'<details class="data-table"><summary>Data table</summary><div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div></details>'


def fmt(value) -> str:
    if value is None:
        return "–"
    if isinstance(value, float):
        return f"{value:,.1f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def bar_chart(data: dict) -> str:
    series = data["series"]
    rows = data["rows"]
    x = data.get("x", "label")
    unit = data.get("unit", "")
    peak = max((row.get(s["key"]) or 0) for row in rows for s in series) or 1
    label_w, bar_h, gap, group_gap, chart_w = 150, 14, 3, 14, 460
    group_h = len(series) * (bar_h + gap) + group_gap
    height = len(rows) * group_h + 30
    width = label_w + chart_w + 70
    out = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(data["title"])}" xmlns="http://www.w3.org/2000/svg">']
    for i, row in enumerate(rows):
        y0 = 10 + i * group_h
        out.append(f'<text class="axis-label" x="{label_w - 8}" y="{y0 + (len(series) * (bar_h + gap)) / 2 + 4}" text-anchor="end">{escape(str(row.get(x, "")))}</text>')
        for j, s in enumerate(series):
            value = row.get(s["key"]) or 0
            w = max(1.0, chart_w * value / peak)
            y = y0 + j * (bar_h + gap)
            out.append(f'<rect x="{label_w}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="3" fill="{PALETTE[j % len(PALETTE)]}"><title>{escape(s["label"])}: {escape(fmt(value))} {escape(unit)}</title></rect>')
            out.append(f'<text class="value-label" x="{label_w + w + 6:.1f}" y="{y + bar_h - 3}">{escape(fmt(value))}{escape(unit and " " + unit)}</text>')
    out.append("</svg>")
    return "".join(out) + legend(series)


def line_chart(data: dict) -> str:
    series = data["series"]
    rows = data["rows"]
    x = data.get("x", "label")
    unit = data.get("unit", "")
    width, height, left, bottom, top = 640, 240, 48, 30, 12
    plot_w, plot_h = width - left - 12, height - bottom - top
    peak = max((row.get(s["key"]) or 0) for row in rows for s in series) or 1
    n = max(1, len(rows) - 1)
    out = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(data["title"])}" xmlns="http://www.w3.org/2000/svg">']
    for frac in (0, 0.5, 1):
        y = top + plot_h * (1 - frac)
        out.append(f'<line class="grid" x1="{left}" x2="{width - 12}" y1="{y:.1f}" y2="{y:.1f}"/>')
        out.append(f'<text class="axis-label" x="{left - 6}" y="{y + 4:.1f}" text-anchor="end">{escape(fmt(round(peak * frac, 1)))}</text>')
    step = max(1, len(rows) // 6)
    for i, row in enumerate(rows):
        if i % step == 0 or i == len(rows) - 1:
            px = left + plot_w * i / n
            out.append(f'<text class="axis-label" x="{px:.1f}" y="{height - 10}" text-anchor="middle">{escape(str(row.get(x, "")))}</text>')
    for j, s in enumerate(series):
        points = " ".join(f"{left + plot_w * i / n:.1f},{top + plot_h * (1 - (row.get(s['key']) or 0) / peak):.1f}" for i, row in enumerate(rows))
        out.append(f'<polyline fill="none" stroke="{PALETTE[j % len(PALETTE)]}" stroke-width="2.5" points="{points}"><title>{escape(s["label"])} ({escape(unit)})</title></polyline>')
    out.append("</svg>")
    return "".join(out) + legend(series)


def legend(series: list[dict]) -> str:
    items = "".join(f'<li><span class="swatch" style="background:{PALETTE[i % len(PALETTE)]}"></span>{escape(s["label"])}</li>' for i, s in enumerate(series))
    return f'<ul class="legend">{items}</ul>'


def render_chart(name: str, data: dict) -> str:
    kind = data.get("chart", "bar")
    body = {"bar": bar_chart, "line": line_chart}.get(kind, lambda d: "")(data)
    notes = f'<p class="chart-note">{escape(data["description"])}</p>' if data.get("description") else ""
    return (
        f'<figure class="chart-figure" data-dataset="{escape(name)}" data-kind="{escape(data["kind"])}">'
        f'<figcaption><span class="chart-title">{escape(data["title"])}</span>{badge(data)}</figcaption>'
        f"{body}{notes}{data_table(data)}{make_real(data)}</figure>"
    )


def labnet_badge(run: dict) -> str:
    sim = run["simulator"]
    meta = f'Computed by lab.net @ {escape(str(sim["commit"])[:7])}, seed {escape(str(sim["seed"]))}, {escape(str(run["timeMs"]))} ms simulated · routing simulation, not a measurement'
    return f'<div class="provenance"><span class="badge badge-sim">SIMULATED / EXAMPLE DATA</span><span class="badge-meta">{meta}</span></div>'


def path_pairs(run: dict) -> list[tuple[str, str]]:
    """Directed node pairs the validation ICMP packets crossed, from lab.net's ethernet hops."""
    pairs = []
    for result in run.get("results", []):
        for hop in result.get("hops", []):
            if hop.get("kind") == "ethernet" and hop.get("from") and hop.get("to"):
                pair = (hop["from"], hop["to"])
                if pair not in pairs:
                    pairs.append(pair)
    return pairs


def labnet_graph(name: str, run: dict) -> str:
    nodes = {n["id"]: n for n in run["graph"]["nodes"]}
    xs = [n["x"] for n in nodes.values()]
    ys = [n["y"] for n in nodes.values()]
    w, h = 150, 58
    pad = 20
    min_x, min_y = min(xs) - w / 2 - pad, min(ys) - h / 2 - pad
    width, height = max(xs) - min(xs) + w + 2 * pad, max(ys) - min(ys) + h + 2 * pad
    used = {frozenset(p) for p in path_pairs(run)}
    out = [f'<svg class="labnet-graph" viewBox="{min_x:.0f} {min_y:.0f} {width:.0f} {height:.0f}" role="img" aria-label="lab.net topology {escape(run["topology"])} with the validation packet path highlighted" xmlns="http://www.w3.org/2000/svg">']
    for edge in run["graph"]["edges"]:
        a, b = nodes[edge["a"]], nodes[edge["b"]]
        cls = "lk on-path" if frozenset((edge["a"], edge["b"])) in used else "lk"
        out.append(f'<line class="{cls}" x1="{a["x"]:.0f}" y1="{a["y"]:.0f}" x2="{b["x"]:.0f}" y2="{b["y"]:.0f}"><title>{escape(edge["a"])} {escape(edge.get("aIf") or "")} ↔ {escape(edge["b"])} {escape(edge.get("bIf") or "")}</title></line>')
    on_path = {n for p in used for n in p}
    for node in nodes.values():
        kind = "host" if node.get("role") == "host" else "router"
        cls = f"nd nd-{kind}" + (" on-path" if node["id"] in on_path else "")
        sub = f'AS {node["as"]}' if node.get("as") else (node.get("device") or "")
        out.append(
            f'<g class="{cls}"><rect x="{node["x"] - w / 2:.0f}" y="{node["y"] - h / 2:.0f}" width="{w}" height="{h}" rx="10"/>'
            f'<text x="{node["x"]:.0f}" y="{node["y"] - 4:.0f}" text-anchor="middle" class="nd-label">{escape(node["id"])}</text>'
            f'<text x="{node["x"]:.0f}" y="{node["y"] + 15:.0f}" text-anchor="middle" class="nd-sub">{escape(sub)}</text></g>'
        )
    out.append("</svg>")
    return "".join(out)


def labnet_hops(run: dict) -> str:
    rows = []
    for result in run.get("results", []):
        for hop in result.get("hops", []):
            if hop.get("kind") not in ("forward", "icmp-request", "icmp-reply", "icmp-unreachable", "drop", "ecmp"):
                continue
            ttl = escape(str(hop.get("ttl", "–")))
            rows.append(f'<tr><td><code>{escape(hop["kind"])}</code></td><td>{escape(hop.get("at", ""))}</td><td>{escape(hop.get("from", ""))} → {escape(hop.get("to", ""))}</td><td>{ttl}</td></tr>')
    if not rows:
        return ""
    return ('<div class="table-wrap"><table><thead><tr><th scope="col">lab.net hop</th><th scope="col">At node</th><th scope="col">Packet</th><th scope="col">TTL after</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def labnet_routes(run: dict, prefix: str | None) -> str:
    rows = []
    for node, tables in run.get("tables", {}).items():
        for entry in tables.get("locRib", []):
            if prefix and entry["prefix"] != prefix:
                continue
            rows.append(f'<tr><td>{escape(node)}</td><td><code>{escape(entry["prefix"])}</code></td><td>{escape(str(entry.get("nexthop") or ""))}</td><td>{escape(str(entry.get("aspath") or "(local)"))}</td></tr>')
    if not rows:
        return ""
    return ('<div class="table-wrap"><table><thead><tr><th scope="col">Node</th><th scope="col">Loc-RIB prefix</th><th scope="col">Next hop</th><th scope="col">AS path</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def labnet_results(run: dict) -> str:
    items = "".join(
        f'<li class="{"pass" if r["ok"] else "fail"}"><span class="res">{"PASS" if r["ok"] else "FAIL"}</span> <strong>{escape(r["label"])}</strong>: {escape(r["detail"])}</li>'
        for r in run.get("results", [])
    )
    return f'<ul class="labnet-results">{items}</ul>'


def render_labnet(name: str, run: dict, links: str, prefix: str | None = None) -> str:
    return (
        f'<figure class="labnet-figure" data-labnet="{escape(name)}" data-kind="simulated">'
        f'<figcaption><span class="chart-title">{escape(run["title"])}</span>{labnet_badge(run)}</figcaption>'
        f'{labnet_graph(name, run)}<p class="chart-note">Layout from lab.net\'s <code>automaticLayout()</code>. Highlighted links carried the validation ICMP packets, taken from the hops lab.net returned.</p>'
        f'{labnet_results(run)}'
        f'<details class="data-table"><summary>Forwarding hops (from lab.net)</summary>{labnet_hops(run)}</details>'
        f'<details class="data-table"><summary>BGP Loc-RIB entries</summary>{labnet_routes(run, prefix)}</details>'
        f'<p class="labnet-links">{links}</p>'
        f"{make_real(run)}</figure>"
    )
