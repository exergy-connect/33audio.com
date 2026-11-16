"""Build the Academy into academy/dist.

python -m academy build            # write academy/dist
python -m academy build --check    # build into a temp dir and fail on broken links, embeds, or badges

Code shown on pages is read from the repository at build time and linked to GitHub at the
commit being built, so lessons cannot drift from the code they describe.
"""

from __future__ import annotations

import argparse
import json
import base64
import gzip
import os
import random
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from academy import ACADEMY, CONTENT, DATA, DIST, ROOT, STATIC
from academy.charts import DatasetError, load_dataset, render_chart, render_labnet
from academy.diagrams import DIAGRAMS, render_diagram
from academy.markdown import render as render_md

LANGS = {".js": "js", ".mjs": "js", ".py": "python", ".toml": "toml", ".yml": "yaml", ".yaml": "yaml", ".json": "json", ".sql": "sql", ".graphql": "graphql", ".yang": "text", ".txt": "text", ".md": "text"}
PROPOSALS = ROOT / "network" / "labnet" / "proposals"
LABNET_REPO = "exergy-connect/lab.net"
LABNET_SITE = "https://exergy-connect.com/lab.net/"
LABNET_FILES = ["tools/run-validation.mjs", "src/lab/validation/run.js", "src/lab/dataplane/routing.js", "src/ui/auto-layout.js"]
NAV = [("", "Home"), ("paths/", "Learning Paths"), ("courses/", "Course Catalog"), ("labs/", "Labs"), ("explore/", "Explore"), ("reference/", "Reference")]


class BuildError(RuntimeError):
    pass


def git_sha() -> str:
    env = os.environ.get("GITHUB_SHA")
    if env:
        return env
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "main"


def front_matter(text: str) -> tuple[dict, str]:
    meta: dict = {}
    if text.startswith("---\n"):
        end = text.index("\n---\n", 4)
        for line in text[4:end].splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
        text = text[end + 5:]
    return meta, text


class Builder:
    def __init__(self, out: Path, real_dir: Path | None = None):
        self.out = out
        self.site = json.loads((CONTENT / "site.json").read_text(encoding="utf-8"))
        self.sha = git_sha()
        self.built_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        self.real_dir = real_dir or Path(os.environ.get("ACADEMY_REAL_DIR") or DATA / "real")
        self.sim_dir = DATA / "simulated"
        self.datasets: dict[str, dict] = {}
        self.embeds: list[str] = []
        self.pages: list[str] = []
        self.links: set[tuple[str, str]] = set()
        self.topics = {t["slug"]: t for t in self.site["topics"]}
        self.labnet_runs: dict[str, dict] = {}
        self.pending_used: set[str] = set()

    # ---- links and directives -------------------------------------------------

    def blob(self, path: str, start: int | None = None, end: int | None = None) -> str:
        url = f"https://github.com/{self.site['repo']}/blob/{self.sha}/{path}"
        if start:
            url += f"#L{start}" + (f"-L{end}" if end and end != start else "")
        return url

    def fix_link(self, href: str) -> str:
        if href.startswith("repo:"):
            path = href[5:]
            target = path.split("#")[0]
            if not (ROOT / target).exists():
                raise BuildError(f"repo link to missing path {target}")
            return self.blob(target) if not target.endswith("/") else f"https://github.com/{self.site['repo']}/tree/{self.sha}/{target}"
        return href

    def directive(self, name: str, arg: str) -> str:
        if name == "embed":
            return self.embed(arg)
        if name == "chart":
            data = self.dataset(arg)
            return render_chart(arg, data)
        if name == "labnet":
            return self.labnet(arg)
        if name == "pending":
            return self.pending(arg)
        if name == "diagram":
            if arg not in DIAGRAMS:
                raise BuildError(f"unknown diagram {arg}")
            return render_diagram(arg)
        if name == "live":
            return live_widget(arg)
        raise BuildError(f"unknown directive ::: {name}")

    def dataset(self, name: str) -> dict:
        if name not in self.datasets:
            try:
                self.datasets[name] = load_dataset(name, self.real_dir, self.sim_dir)
            except DatasetError as error:
                raise BuildError(str(error)) from error
        return self.datasets[name]

    def labnet_run(self, name: str) -> dict:
        if name not in self.labnet_runs:
            path = DATA / "labnet" / f"{name}.json"
            if not path.is_file():
                raise BuildError(f"lab.net run {name} not found at {path}")
            run = json.loads(path.read_text(encoding="utf-8"))
            for key in ("simulator", "topology_file", "graph", "results", "make_real"):
                if not run.get(key):
                    raise BuildError(f"lab.net run {name} is missing {key}")
            if run.get("kind") != "simulated" or not run["simulator"].get("commit"):
                raise BuildError(f"lab.net run {name} must be kind simulated with a lab.net commit")
            if not (ROOT / run["topology_file"]).is_file():
                raise BuildError(f"lab.net run {name} names a missing topology {run['topology_file']}")
            self.labnet_runs[name] = run
        return self.labnet_runs[name]

    def pending(self, arg: str) -> str:
        slug, _, what = arg.partition(" ")
        index = json.loads((PROPOSALS / "index.json").read_text(encoding="utf-8"))
        proposal = next((p for p in index["proposals"] if p["slug"] == slug), None)
        if not proposal or not (PROPOSALS / f"{slug}.md").is_file():
            raise BuildError(f"unknown lab.net proposal {slug}")
        self.pending_used.add(slug)
        draft = self.blob(f"network/labnet/proposals/{slug}.md")
        if proposal.get("issue_url"):
            link = f'<a href="{escape(proposal["issue_url"])}">lab.net issue: {escape(proposal["title"])}</a>'
        else:
            link = f'<a href="{escape(draft)}">{escape(proposal["title"])}</a> (issue draft, not yet filed in lab.net)'
        detail = f" {escape(what)}" if what else ""
        return f'<aside class="callout callout-pending"><p class="callout-title"><span class="pill pill-pending">Pending lab.net extension</span></p><p>This part needs a lab.net feature that does not exist yet:{detail} {link}.</p></aside>'

    def labnet_open_url(self, topology_file: str) -> str:
        source = (ROOT / topology_file).read_bytes()
        artefact = base64.urlsafe_b64encode(gzip.compress(source, mtime=0)).decode().rstrip("=")
        return f"{LABNET_SITE}#lab={artefact}"

    def labnet_source(self, commit: str, path: str) -> str:
        return f"https://github.com/{LABNET_REPO}/blob/{commit}/{path}"

    def labnet(self, arg: str) -> str:
        parts = arg.split()
        name = parts[0]
        prefix = parts[1] if len(parts) > 1 else None
        run = self.labnet_run(name)
        commit = run["simulator"]["commit"]
        links = " · ".join([
            f'<a class="button small" href="{escape(self.labnet_open_url(run["topology_file"]))}">Open this lab in lab.net</a>',
            f'<a href="{escape(self.blob(run["topology_file"]))}">Topology <code>{escape(run["topology_file"])}</code></a>',
            f'<a href="/labnet/{escape(name)}.json">Run JSON</a>',
            f'<a href="/labnet/{escape(name)}.pcapng">PCAPNG capture</a>' if run.get("capture") else "",
            f'lab.net source at <code>{escape(commit[:7])}</code>: '
            + ", ".join(f'<a href="{escape(self.labnet_source(commit, p))}"><code>{escape(p)}</code></a>' for p in LABNET_FILES),
        ])
        return render_labnet(name, run, links, prefix)

    def embed(self, arg: str) -> str:
        parts = shlex.split(arg)
        path = parts[0]
        start_pat = parts[1] if len(parts) > 1 else None
        end_pat = parts[2] if len(parts) > 2 else None
        file = (ROOT / path).resolve()
        if ROOT not in file.parents or not file.is_file():
            raise BuildError(f"embed: {path} is not a file in the repository")
        lines = file.read_text(encoding="utf-8").splitlines()
        a, b = 0, len(lines) - 1
        if start_pat:
            hits = [i for i, line in enumerate(lines) if start_pat in line]
            if not hits:
                raise BuildError(f"embed: {start_pat!r} not found in {path}")
            a = hits[0]
            if end_pat:
                exact = end_pat[1:] if end_pat.startswith("=") else None
                ends = [i for i in range(a, len(lines)) if (lines[i].strip() == exact if exact is not None else end_pat in lines[i])]
                if not ends:
                    raise BuildError(f"embed: end {end_pat!r} not found in {path} after line {a + 1}")
                b = ends[0]
            elif file.suffix in (".js", ".mjs", ".yang", ".json", ".graphql"):
                b = brace_end(lines, a)
            elif file.suffix == ".py":
                b = indent_end(lines, a)
            else:
                b = a
                while b + 1 < len(lines) and lines[b + 1].strip():
                    b += 1
        snippet = "\n".join(lines[a:b + 1])
        self.embeds.append(f"{path}#L{a + 1}-L{b + 1}")
        lang = LANGS.get(file.suffix, "text")
        span = f"lines {a + 1}–{b + 1}" if (a, b) != (0, len(lines) - 1) else f"{len(lines)} lines"
        return (
            f'<figure class="code embed"><figcaption><span class="tag tag-repo">Repo file</span>'
            f'<a class="embed-path" href="{escape(self.blob(path, a + 1, b + 1))}">{escape(path)}</a>'
            f'<span class="embed-meta">{span} · commit {escape(self.sha[:7])}</span>'
            f'<button type="button" class="copy" data-copy>Copy</button></figcaption>'
            f'<pre><code class="language-{lang}">{escape(snippet)}</code></pre></figure>'
        )

    # ---- layout ------------------------------------------------------------------

    def layout(self, path: str, title: str, description: str, body: str, section: str, toc: list | None = None, wide: bool = False) -> str:
        nav = []
        for href, label in NAV:
            current = ' aria-current="page"' if section == href else ""
            nav.append(f'<a href="/{href}"{current}>{escape(label)}</a>')
        toc_html = ""
        if toc:
            items = "".join(f'<li class="toc-l{lvl}"><a href="#{anchor}">{escape(text)}</a></li>' for lvl, anchor, text in toc)
            toc_html = f'<nav class="toc" aria-label="On this page"><p class="toc-title">On this page</p><ul>{items}</ul></nav>'
        page_title = f"{title} · Exergy ∞ Academy" if path else f"{self.site['name']}"
        author = self.site["author"]
        main_cls = "page wide" if wide or not toc else "page with-toc"
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(page_title)}</title>
<meta name="description" content="{escape(description)}">
<meta name="theme-color" content="#0b1020">
<meta name="color-scheme" content="dark">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/styles.css">
<script src="/app.js" defer></script>
</head>
<body>
<a class="skip" href="#content">Skip to content</a>
<header class="topbar">
  <div class="bar">
    <a class="brand" href="/" aria-label="Exergy Engineering Academy home">{logo_svg(28)}<span class="brand-text">Exergy <span class="inf">∞</span> Academy</span></a>
    <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav" data-nav-toggle><span class="sr-only">Menu</span><span aria-hidden="true">☰</span></button>
    <nav id="site-nav" class="nav" aria-label="Primary">{''.join(nav)}</nav>
  </div>
</header>
<div class="{main_cls}">
{toc_html}
<main id="content">
{body}
</main>
</div>
<footer class="footer">
  <div class="bar footer-grid">
    <p><span class="inf">∞</span> {escape(self.site['name'])}. Worked example: the {escape(self.site['shop']['name'])}.</p>
    <p>Built by {escape(author['name'])} (<a href="https://github.com/{escape(author['github'])}">@{escape(author['github'])}</a>) from <a href="https://github.com/{escape(self.site['repo'])}/tree/{escape(self.sha)}">{escape(self.site['repo'])}@{escape(self.sha[:7])}</a> at {escape(self.built_at)}. Code under the MIT license.</p>
    <p>Charts carry a <span class="badge badge-real">REAL TELEMETRY</span> or <span class="badge badge-sim">SIMULATED / EXAMPLE DATA</span> badge. <a href="/reference/real-vs-simulated/">Policy</a>.</p>
  </div>
</footer>
</body>
</html>
"""

    def write(self, path: str, html: str) -> None:
        target = self.out / path / "index.html" if not path.endswith(".html") else self.out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        self.pages.append(path)

    def markdown_page(self, source: Path) -> tuple[dict, str, list]:
        meta, text = front_matter(source.read_text(encoding="utf-8"))
        toc: list = []
        html = render_md(text, self.directive, self.fix_link, toc)
        return meta, html, toc

    # ---- pages -------------------------------------------------------------------

    def topic_header(self, topic: dict, kind: str) -> str:
        other = "lab" if kind == "explore" else "explore"
        other_href = f"/{'labs' if other == 'lab' else 'explore'}/{topic['slug']}/"
        services = "".join(f'<li>{escape(s)}</li>' for s in topic["services"])
        tabs = (
            f'<div class="tabs" role="list">'
            f'<a role="listitem" href="/explore/{topic["slug"]}/"{" aria-current=page" if kind == "explore" else ""}>Explore</a>'
            f'<a role="listitem" href="/labs/{topic["slug"]}/"{" aria-current=page" if kind == "lab" else ""}>Lab</a></div>'
        )
        local = '<span class="pill pill-local">Runs locally with wrangler dev</span>' if topic.get("local") else ""
        return (
            f'<p class="eyebrow">Topic {topic["number"]} · {escape(topic["level"])} · {"Explore" if kind == "explore" else "Lab"}</p>'
            f'<h1>{escape(topic["title"])}</h1><p class="lede">{escape(topic["short"])}</p>'
            f'{tabs}<ul class="services">{services}</ul>{local}'
            f'<p class="switch">Also see the <a href="{other_href}">{other.capitalize()}</a> for this topic.</p>'
        )

    def build_topics(self) -> None:
        for topic in self.site["topics"]:
            for kind, folder in (("explore", "explore"), ("lab", "labs")):
                source = CONTENT / "topics" / topic["slug"] / f"{kind}.md"
                if not source.is_file():
                    raise BuildError(f"topic {topic['slug']} is missing {kind}.md")
                meta, html, toc = self.markdown_page(source)
                files = "".join(f'<li><a href="{escape(self.fix_link("repo:" + f))}"><code>{escape(f)}</code></a></li>' for f in topic["files"])
                body = self.topic_header(topic, kind) + html + f'<section class="files"><h2 id="files">Files in this topic</h2><ul>{files}</ul></section>'
                toc.append((2, "files", "Files in this topic"))
                self.links.add((f"{folder}/{topic['slug']}/", meta.get("title", topic["title"])))
                self.write(f"{folder}/{topic['slug']}/", self.layout(f"{folder}/{topic['slug']}/", f"{topic['title']} · {kind.capitalize()}", meta.get("summary", topic["short"]), body, f"{folder}/", toc))

    def topic_card(self, topic: dict) -> str:
        services = ", ".join(topic["services"][:3])
        return (
            f'<article class="card topic-card"><p class="card-num">{topic["number"]:02d}</p>'
            f'<h3><a href="/explore/{topic["slug"]}/">{escape(topic["title"])}</a></h3>'
            f'<p>{escape(topic["short"])}</p><p class="card-meta">{escape(topic["level"])} · {escape(services)}</p>'
            f'<p class="card-links"><a href="/explore/{topic["slug"]}/">Explore</a><a href="/labs/{topic["slug"]}/">Lab</a></p></article>'
        )

    def build_indexes(self) -> None:
        topics = self.site["topics"]
        cards = "".join(self.topic_card(t) for t in topics)
        self.write("courses/", self.layout("courses/", "Course Catalog", "Six courses, each with an Explore section and a hands-on Lab, all built on the 33audio shop.", f"""
<p class="eyebrow">Course Catalog</p><h1>Six courses, one real app</h1>
<p class="lede">Every course teaches from the same repository: the 33audio Caddock resistor shop on Cloudflare Pages. Each has an <strong>Explore</strong> section (concepts, architecture, trade-offs) and a <strong>Lab</strong> (commands, code, expected output).</p>
<div class="grid cards">{cards}</div>
<h2>Services covered</h2>{self.services_table()}
""", "courses/"))

        explore = "".join(f'<li><a href="/explore/{t["slug"]}/"><span class="num">{t["number"]:02d}</span> {escape(t["title"])}</a><span>{escape(t["short"])}</span></li>' for t in topics)
        self.write("explore/", self.layout("explore/", "Explore", "Concepts, architecture diagrams, and trade-offs for each topic.", f"""
<p class="eyebrow">Explore</p><h1>Concepts, architecture, and trade-offs</h1>
<p class="lede">Explore pages explain how each part of the shop works on Cloudflare and why it was built that way. Diagrams show the real request flow. Code is embedded from the repository at the commit this site was built from.</p>
<ul class="index-list">{explore}</ul>
{render_diagram("shop-architecture")}
""", "explore/"))

        labs = "".join(
            f'<li><a href="/labs/{t["slug"]}/"><span class="num">{t["number"]:02d}</span> {escape(t["title"])}</a><span>{escape(t["short"])}'
            f'{" <em class=pill-inline>local</em>" if t.get("local") else ""}</span></li>'
            for t in topics
        )
        self.write("labs/", self.layout("labs/", "Labs", "Hands-on labs with real commands and expected output.", f"""
<p class="eyebrow">Labs</p><h1>Hands-on labs</h1>
<p class="lede">Each lab runs against the code in this repository. Every lab starts locally with <code>wrangler pages dev</code> or <code>wrangler dev</code>, so no Cloudflare account is needed until the deploy step. Security labs send controlled traffic only to your own local or deployed instance.</p>
<aside class="callout callout-tip"><p class="callout-title">Set up once</p>
<p>Clone the repo, then install Python 3.15 and Node 26 or newer. Wrangler is pinned to 4.162.0 in <code>academy/package.json</code>.</p></aside>
<figure class="code"><figcaption><span class="tag">Shell</span><button type="button" class="copy" data-copy>Copy</button></figcaption><pre><code class="language-bash">git clone https://github.com/{escape(self.site['repo'])}.git
cd 33audio.com
npm ci --prefix academy
python -m pip install -r requirements-schema.txt</code></pre></figure>
<ul class="index-list">{labs}</ul>
<h2>Automated lab check</h2>
<p><code>academy/tools/lab-check.mjs</code> runs the deploy, discovery, AI, and observability lab checks against a running shop. CI runs it on every push against <code>wrangler pages dev</code>.</p>
""", "labs/"))

        path_cards = "".join(self.path_card(p) for p in self.site["paths"])
        self.write("paths/", self.layout("paths/", "Learning Paths", "Guided sequences through the Explore and Lab pages.", f"""
<p class="eyebrow">Learning Paths</p><h1>Pick a path</h1>
<p class="lede">A path strings Explore and Lab pages into an order that builds on itself. Each one ends with something you can measure.</p>
<div class="grid cards">{path_cards}</div>
""", "paths/"))
        for p in self.site["paths"]:
            steps = []
            for i, (kind, slug) in enumerate(p["steps"], 1):
                t = self.topics[slug]
                folder = "labs" if kind == "lab" else "explore"
                steps.append(
                    f'<li class="path-step"><span class="step-num">{i}</span><div><p class="step-kind">{"Lab" if kind == "lab" else "Explore"} · Topic {t["number"]}</p>'
                    f'<h3><a href="/{folder}/{slug}/">{escape(t["title"])}</a></h3><p>{escape(t["short"])}</p></div></li>'
                )
            self.write(f"paths/{p['slug']}/", self.layout(f"paths/{p['slug']}/", p["title"], p["summary"], f"""
<p class="eyebrow">Learning Path</p><h1>{escape(p['title'])}</h1><p class="lede">{escape(p['summary'])}</p>
<p><strong>For:</strong> {escape(p['audience'])}</p>
<ol class="path-steps">{''.join(steps)}</ol>
<p><a class="button" href="/{'labs' if p['steps'][0][0] == 'lab' else 'explore'}/{p['steps'][0][1]}/">Start with step 1</a> <a class="button ghost" href="/paths/">All paths</a></p>
""", "paths/"))

    def path_card(self, p: dict) -> str:
        n = len(p["steps"])
        labs = sum(1 for kind, _ in p["steps"] if kind == "lab")
        return (
            f'<article class="card path-card"><h3><a href="/paths/{p["slug"]}/">{escape(p["title"])}</a></h3>'
            f'<p>{escape(p["summary"])}</p><p class="card-meta">{n} steps · {labs} labs</p></article>'
        )

    def services_table(self) -> str:
        rows = "".join(f'<tr><th scope="row">{escape(t["title"])}</th><td>{escape(", ".join(t["services"]))}</td></tr>' for t in self.site["topics"])
        return f'<div class="table-wrap"><table><thead><tr><th scope="col">Course</th><th scope="col">Cloudflare services</th></tr></thead><tbody>{rows}</tbody></table></div>'

    def build_reference(self) -> None:
        items = []
        for ref in self.site["reference"]:
            items.append(f'<li><a href="/reference/{ref["slug"]}/">{escape(ref["title"])}</a><span>{escape(ref["summary"])}</span></li>')
            if ref["slug"] == "adr":
                self.build_adrs(ref)
                continue
            if ref["slug"] == "real-vs-simulated":
                continue
            source = CONTENT / "reference" / f"{ref['slug']}.md"
            meta, html, toc = self.markdown_page(source)
            body = f'<p class="eyebrow">Reference</p><h1>{escape(ref["title"])}</h1><p class="lede">{escape(ref["summary"])}</p>{html}'
            self.write(f"reference/{ref['slug']}/", self.layout(f"reference/{ref['slug']}/", ref["title"], ref["summary"], body, "reference/", toc))
        self.write("reference/", self.layout("reference/", "Reference", "ADRs, repository map, bindings, pipelines, and data formats.", f"""
<p class="eyebrow">Reference</p><h1>Reference</h1>
<p class="lede">The engineering record behind the Academy: decisions, configuration, pipelines, and formats.</p>
<ul class="index-list">{''.join(items)}</ul>
{render_diagram("academy-architecture")}
""", "reference/"))

    def build_adrs(self, ref: dict) -> None:
        rows = []
        for source in sorted((CONTENT / "adr").glob("*.md")):
            meta, html, toc = self.markdown_page(source)
            slug = source.stem
            status = meta.get("status", "Accepted")
            rows.append(f'<tr><td><a href="/reference/adr/{slug}/">{escape(meta["title"])}</a></td><td>{escape(status)}</td><td>{escape(meta.get("date", ""))}</td></tr>')
            body = (
                f'<p class="eyebrow">Architecture decision record · {escape(slug[:4])}</p><h1>{escape(meta["title"])}</h1>'
                f'<p class="adr-meta"><span class="pill">{escape(status)}</span> {escape(meta.get("date", ""))} · <a href="{escape(self.blob("academy/content/adr/" + source.name))}">source</a></p>{html}'
                f'<p><a href="/reference/adr/">All ADRs</a></p>'
            )
            self.write(f"reference/adr/{slug}/", self.layout(f"reference/adr/{slug}/", meta["title"], meta.get("summary", meta["title"]), body, "reference/", toc))
        table = f'<div class="table-wrap"><table><thead><tr><th scope="col">Decision</th><th scope="col">Status</th><th scope="col">Date</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        self.write("reference/adr/", self.layout("reference/adr/", ref["title"], ref["summary"], f'<p class="eyebrow">Reference</p><h1>{escape(ref["title"])}</h1><p class="lede">{escape(ref["summary"])} Each record follows context, decision, consequences, and alternatives.</p>{table}', "reference/"))

    def build_provenance(self) -> None:
        all_names = sorted({p.stem for p in self.sim_dir.glob("*.json")} | ({p.stem for p in self.real_dir.glob("*.json")} if self.real_dir.is_dir() else set()))
        rows = []
        counts = {"real": 0, "simulated": 0}
        for name in all_names:
            data = self.dataset(name)
            counts[data["kind"]] += 1
            used = "yes" if name in self.used_datasets else "no"
            src = escape(data.get("source", "")) if data["kind"] == "real" else "Example values written for teaching"
            when = escape(data.get("collected_at", "")) if data["kind"] == "real" else "–"
            badge_html = '<span class="badge badge-real">REAL TELEMETRY</span>' if data["kind"] == "real" else '<span class="badge badge-sim">SIMULATED</span>'
            rows.append(f"<tr><td><code>{escape(name)}</code></td><td>{escape(data.get('title', ''))}</td><td>{badge_html}</td><td>{src}</td><td>{when}</td><td>{used}</td></tr>")
        self.provenance_counts = counts
        meta, html, toc = self.markdown_page(CONTENT / "reference" / "real-vs-simulated.md")
        table = f'<div class="table-wrap"><table><thead><tr><th scope="col">Dataset</th><th scope="col">Title</th><th scope="col">Badge</th><th scope="col">Source</th><th scope="col">Collected</th><th scope="col">On a page</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        summary = f'<p class="stat-line">This build ({escape(self.sha[:7])}, {escape(self.built_at)}) has <strong>{counts["real"]}</strong> real and <strong>{counts["simulated"]}</strong> simulated datasets.</p>'
        toc.append((2, "datasets", "Datasets in this build"))
        lab_rows = []
        for path in sorted((DATA / "labnet").glob("*.json")):
            run = self.labnet_run(path.stem)
            passed = sum(1 for r in run["results"] if r["ok"])
            lab_rows.append(
                f'<tr><td><code>{escape(path.stem)}</code></td><td><a href="{escape(self.blob(run["topology_file"]))}"><code>{escape(run["topology_file"])}</code></a></td>'
                f'<td><span class="badge badge-sim">SIMULATED</span></td><td>lab.net @ <code>{escape(run["simulator"]["commit"][:7])}</code>, seed {escape(str(run["simulator"]["seed"]))}</td><td>{passed}/{len(run["results"])} checks pass</td></tr>'
            )
        lab_table = (
            '<h3 id="labnet-runs">lab.net runs</h3><p>Request paths come from lab.net, Exergy\'s network simulator, run on topology files in this repository. They are simulations and carry the SIMULATED badge with the lab.net commit and seed.</p>'
            f'<div class="table-wrap"><table><thead><tr><th scope="col">Run</th><th scope="col">Topology</th><th scope="col">Badge</th><th scope="col">Engine</th><th scope="col">Validation</th></tr></thead><tbody>{"".join(lab_rows)}</tbody></table></div>'
        )
        body = f'<p class="eyebrow">Reference</p><h1>Real vs. simulated data</h1><p class="lede">The badge policy, and every dataset in this build with its provenance.</p>{html}<h2 id="datasets">Datasets in this build</h2>{summary}{table}{lab_table}'
        self.write("reference/real-vs-simulated/", self.layout("reference/real-vs-simulated/", "Real vs. simulated data", "Badge policy and dataset provenance.", body, "reference/", toc))

    def build_home(self) -> None:
        topics = "".join(self.topic_card(t) for t in self.site["topics"])
        paths = "".join(self.path_card(p) for p in self.site["paths"])
        counts = getattr(self, "provenance_counts", {"real": 0, "simulated": 0})
        shop = self.site["shop"]
        status = "Deployed" if shop["deployed"] else "Not deployed yet. The shop and the Academy are one workflow run away; see the go-live checklist."
        body = f"""
<section class="hero">
  <div class="hero-copy">
    <p class="eyebrow">Cloudflare engineering, taught from one real app</p>
    <h1 class="hero-title"><span class="flare-text">Exergy</span> <span class="inf big">∞</span> Engineering Academy</h1>
    <p class="lede">{escape(self.site['tagline'])} Every lesson uses the same codebase: a Caddock resistor shop with Pages Functions, Workers KV, Stripe, Workers AI, and Analytics Engine.</p>
    <p class="hero-cta"><a class="button" href="/paths/">Start a learning path</a><a class="button ghost" href="/labs/">Browse labs</a></p>
    <p class="hero-status"><span class="dot" aria-hidden="true"></span>{escape(status)}</p>
  </div>
  <div class="hero-viz">{network_svg()}</div>
</section>

<section class="section">
  <h2>The worked example</h2>
  <div class="example">
    <div>
      <p>33audio sells new-old-stock Caddock Micronox film resistors from Houston. The repository builds a static catalog of 85 part pages, a cart, and Stripe checkout behind a feature flag, all on Cloudflare Pages. This Academy explains how each piece was designed, deployed, secured, and measured, and links straight to the code.</p>
      <ul class="facts">
        <li><strong>Pages Functions</strong> <code>/api/stock</code>, <code>/api/checkout</code>, <code>/api/stripe-webhook</code>, <code>/api/search</code></li>
        <li><strong>Workers KV</strong> one <code>stock</code> JSON document, seeded by GitHub Actions</li>
        <li><strong>Workers AI</strong> natural-language part search with a keyword fallback</li>
        <li><strong>Discovery</strong> schema.org JSON-LD, llms.txt, catalog.json, and an xYang ontology</li>
      </ul>
      <p><a href="/explore/deploy/">See the architecture</a> · <a href="https://github.com/{escape(self.site['repo'])}">Read the code</a></p>
    </div>
    {render_diagram("shop-architecture")}
  </div>
</section>

<section class="section">
  <h2>Courses</h2>
  <div class="grid cards">{topics}</div>
</section>

<section class="section">
  <h2>Learning paths</h2>
  <div class="grid cards cards-4">{paths}</div>
</section>

<section class="section evidence">
  <h2>Engineering evidence</h2>
  <div class="grid cards">
    <article class="card"><h3><a href="/reference/adr/">Architecture decisions</a></h3><p>Why Pages for the shop and Workers for the Academy, why one KV document, why AI with a fallback, and why WAF rules live in the repo.</p></article>
    <article class="card"><h3><a href="/reference/pipelines/">Deployment pipelines</a></h3><p>GitHub Actions that test, run the labs against <code>wrangler pages dev</code>, and deploy only when Cloudflare credentials exist.</p></article>
    <article class="card"><h3><a href="/labs/security/">Security experiments</a></h3><p>WAF and rate-limit rules as code, applied through the Rulesets API, and verified with capped traffic against your own instance.</p></article>
    <article class="card"><h3><a href="/labs/observability/">Traffic analysis</a></h3><p>Server-Timing, structured logs, Analytics Engine SQL, and the GraphQL Analytics API, with every chart labeled real or simulated.</p></article>
  </div>
</section>

<section class="section honesty">
  <h2>Real vs. simulated, always labeled</h2>
  <p>Every metric, chart, and trace carries a badge. <span class="badge badge-real">REAL TELEMETRY</span> names its source and timestamp. <span class="badge badge-sim">SIMULATED / EXAMPLE DATA</span> marks illustrative numbers and explains how to switch to real data. This build has <strong>{counts['real']}</strong> real and <strong>{counts['simulated']}</strong> simulated datasets. <a href="/reference/real-vs-simulated/">See every dataset</a>.</p>
</section>
"""
        self.write("", self.layout("", self.site["name"], self.site["tagline"], body, "", wide=True))

    def build_404(self) -> None:
        body = '<p class="eyebrow">404</p><h1>Page not found</h1><p class="lede">That page is not in this build.</p><p><a class="button" href="/">Home</a> <a class="button ghost" href="/courses/">Course Catalog</a></p>'
        html = self.layout("404", "Not found", "Page not found.", body, "", wide=True)
        (self.out / "404.html").write_text(html, encoding="utf-8")

    # ---- driver --------------------------------------------------------------------

    def run(self) -> dict:
        if self.out.exists():
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True)
        for item in STATIC.iterdir():
            if item.is_file():
                shutil.copy2(item, self.out / item.name)
        (self.out / "favicon.svg").write_text(logo_svg(64, standalone=True), encoding="utf-8")
        self.build_topics()
        self.build_indexes()
        self.build_reference()
        self.used_datasets = set(self.datasets)
        self.build_provenance()
        self.build_home()
        self.build_404()
        self.write_data_bundle()
        info = {
            "sha": self.sha,
            "built_at": self.built_at,
            "pages": sorted(self.pages),
            "embeds": self.embeds,
            "datasets": {name: {"kind": d["kind"], "source": d.get("source"), "collected_at": d.get("collected_at")} for name, d in sorted(self.datasets.items())},
            "labnet_runs": {name: {"topology": r["topology_file"], "labnet_commit": r["simulator"]["commit"], "passed": all(x["ok"] for x in r["results"])} for name, r in sorted(self.labnet_runs.items())},
        }
        (self.out / "build-info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
        validate_site(self.out)
        return info

    def write_data_bundle(self) -> None:
        folder = self.out / "data"
        folder.mkdir(exist_ok=True)
        for name, data in self.datasets.items():
            clean = {k: v for k, v in data.items() if not k.startswith("_")}
            (folder / f"{name}.json").write_text(json.dumps(clean, indent=2) + "\n", encoding="utf-8")
        labnet = self.out / "labnet"
        labnet.mkdir(exist_ok=True)
        for name, run in self.labnet_runs.items():
            shutil.copy2(DATA / "labnet" / f"{name}.json", labnet / f"{name}.json")
            pcap = DATA / "labnet" / f"{name}.pcapng"
            if run.get("capture") and pcap.is_file():
                shutil.copy2(pcap, labnet / f"{name}.pcapng")
            shutil.copy2(ROOT / run["topology_file"], labnet / Path(run["topology_file"]).name)


def brace_end(lines: list[str], start: int) -> int:
    depth = 0
    opened = False
    for i in range(start, len(lines)):
        code = re.sub(r"(\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'|`(?:\\.|[^`])*`)", "", lines[i])
        code = code.split("//")[0]
        depth += code.count("{") - code.count("}")
        if code.count("{"):
            opened = True
        if opened and depth <= 0:
            return i
    return len(lines) - 1


def indent_end(lines: list[str], start: int) -> int:
    base = len(lines[start]) - len(lines[start].lstrip())
    last = start
    for i in range(start + 1, len(lines)):
        if not lines[i].strip():
            continue
        if len(lines[i]) - len(lines[i].lstrip()) <= base and not lines[i].lstrip().startswith((")", "]", "}")):
            break
        last = i
    return last


def live_widget(name: str) -> str:
    titles = {
        "echo": ("Live request inspector", "Sends one request to this Academy's Worker at /api/lab/echo and shows what the edge saw."),
        "cache": ("Live Cache API demo", "Calls /api/lab/cache twice with the same key: the first is a MISS, the second a HIT from the Cache API."),
        "burst": ("Controlled rate-limit burst", "Sends 30 requests to this Academy's own /api/lab/echo, one every 50 ms, and counts 200 vs 429 answers from the Rate Limiting binding."),
        "telemetry": ("Live telemetry", "Asks /api/telemetry for Analytics Engine data. Without a configured token it says so, and the simulated chart above stays labeled."),
    }
    if name not in titles:
        raise BuildError(f"unknown live widget {name}")
    title, desc = titles[name]
    extra = ""
    button = "Run"
    return (
        f'<section class="live" data-live="{name}"><div class="live-head"><h4>{escape(title)}</h4><button type="button" class="button small" data-live-run>{button}</button></div>'
        f'<p class="live-desc">{escape(desc)}</p>{extra}<div class="live-out" data-live-out aria-live="polite">'
        f'<p class="muted">Live widgets need the Academy Worker (<code>npm run dev --prefix academy</code> or the deployed site). On a plain static preview they report that the endpoint is unavailable.</p></div></section>'
    )


def logo_svg(size: int, standalone: bool = False) -> str:
    ns = ' xmlns="http://www.w3.org/2000/svg"' if standalone else ""
    gid = "lg" + str(size)
    return (
        f'<svg{ns} class="logo" width="{size}" height="{size}" viewBox="0 0 64 64" aria-hidden="true" focusable="false">'
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff9a3c"/><stop offset=".45" stop-color="#ff4f8b"/><stop offset="1" stop-color="#7c5cff"/></linearGradient></defs>'
        f'<rect width="64" height="64" rx="14" fill="#0b1020"/>'
        f'<path d="M32 32c-5-6-9-9-13.5-9a9 9 0 0 0 0 18C23 41 27 38 32 32c5-6 9-9 13.5-9a9 9 0 0 1 0 18C41 41 37 38 32 32z" fill="none" stroke="url(#{gid})" stroke-width="4.5" stroke-linecap="round"/>'
        f'<circle cx="45.5" cy="23" r="2.6" fill="#ffd27a"/></svg>'
    )


def network_svg() -> str:
    rng = random.Random(33)
    width, height = 560, 380
    nodes = []
    for _ in range(26):
        nodes.append((rng.uniform(30, width - 30), rng.uniform(30, height - 30)))
    hub = (width * 0.55, height * 0.48)
    lines = []
    for i, (x, y) in enumerate(nodes):
        nearest = sorted(nodes, key=lambda n: (n[0] - x) ** 2 + (n[1] - y) ** 2)[1:3]
        for nx, ny in nearest:
            lines.append(f'<line x1="{x:.0f}" y1="{y:.0f}" x2="{nx:.0f}" y2="{ny:.0f}" class="mesh"/>')
        if i % 3 == 0:
            delay = (i % 7) * 0.6
            lines.append(f'<path d="M{x:.0f},{y:.0f} Q{(x + hub[0]) / 2:.0f},{min(y, hub[1]) - 40:.0f} {hub[0]:.0f},{hub[1]:.0f}" class="flow" style="animation-delay:{delay:.1f}s"/>')
    dots = "".join(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{2 + (i % 3)}" class="node-dot"/>' for i, (x, y) in enumerate(nodes))
    rings = "".join(f'<circle cx="{hub[0]:.0f}" cy="{hub[1]:.0f}" r="{r}" class="ring" style="animation-delay:{d}s"/>' for r, d in ((18, 0), (34, 0.8), (52, 1.6)))
    return (
        f'<svg class="netviz" viewBox="0 0 {width} {height}" role="img" aria-label="Stylized network: requests from many clients converge on a Cloudflare edge location" xmlns="http://www.w3.org/2000/svg">'
        '<defs><radialGradient id="flare" cx="55%" cy="48%" r="55%"><stop offset="0" stop-color="#ff7a45" stop-opacity=".55"/><stop offset=".35" stop-color="#ff4f8b" stop-opacity=".22"/><stop offset=".7" stop-color="#7c5cff" stop-opacity=".10"/><stop offset="1" stop-color="#0b1020" stop-opacity="0"/></radialGradient></defs>'
        f'<rect width="{width}" height="{height}" fill="url(#flare)"/>{"".join(lines)}{dots}{rings}'
        f'<circle cx="{hub[0]:.0f}" cy="{hub[1]:.0f}" r="9" class="hub"/></svg>'
    )


def validate_site(out: Path) -> None:
    errors = []
    for page in out.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        for href in re.findall(r'href="(/[^"#?]*)', text):
            target = out / href.lstrip("/")
            if href.endswith("/"):
                target = target / "index.html"
            if not target.exists():
                errors.append(f"{page.relative_to(out)} links to missing {href}")
        for fig in re.findall(r'<figure class="(?:chart|labnet)-figure"[^>]*>.*?</figcaption>', text, flags=re.S):
            if "badge-real" not in fig and "badge-sim" not in fig:
                errors.append(f"{page.relative_to(out)} has a chart without a provenance badge")
        if re.search(r"<script[^>]+src=[\"']https?://", text):
            errors.append(f"{page.relative_to(out)} loads a third-party script")
    if errors:
        raise BuildError("Academy validation failed:\n- " + "\n- ".join(sorted(set(errors))))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Exergy Academy")
    parser.add_argument("--out", default=str(DIST))
    parser.add_argument("--real-dir", default=None, help="folder of REAL TELEMETRY datasets (default academy/data/real)")
    parser.add_argument("--check", action="store_true", help="build into a temp dir and only validate")
    args = parser.parse_args(argv)
    real_dir = Path(args.real_dir) if args.real_dir else None
    try:
        if args.check:
            with tempfile.TemporaryDirectory() as tmp:
                info = Builder(Path(tmp) / "dist", real_dir).run()
        else:
            info = Builder(Path(args.out), real_dir).run()
    except BuildError as error:
        print(error, file=sys.stderr)
        return 1
    kinds = [d["kind"] for d in info["datasets"].values()]
    print(f"Academy: {len(info['pages'])} pages, {len(info['embeds'])} repo embeds, {kinds.count('real')} real and {kinds.count('simulated')} simulated datasets on pages.")
    return 0
