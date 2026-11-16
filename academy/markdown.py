"""A small Markdown renderer: headings, paragraphs, lists, tables, fenced code, quotes, and inline marks.

Lines starting with `:::` are directives handed to a callback, so pages can embed repo files,
charts, diagrams, and live widgets. Container directives (note, tip, warn, details) wrap Markdown.
"""

from __future__ import annotations

import re
from html import escape
from typing import Callable

CONTAINERS = {"note", "tip", "warn", "details", "steps"}

Directive = Callable[[str, str], str]
LinkFixer = Callable[[str], str]


def slugify(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_]+", "-", text).strip("-")


def inline(text: str, fix_link: LinkFixer) -> str:
    codes: list[str] = []

    def stash(match: re.Match) -> str:
        codes.append(f"<code>{escape(match.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", stash, text)
    text = escape(text, quote=False)

    def link(match: re.Match) -> str:
        label, href = match.group(1), match.group(2)
        url = fix_link(href.replace("&amp;", "&"))
        external = url.startswith("http") and "github.com" not in url
        rel = ' rel="noopener"' if external else ""
        return f'<a href="{escape(url)}"{rel}>{label}</a>'

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*([^*\s][^*]*)\*(?!\w)", r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


def render(source: str, directive: Directive, fix_link: LinkFixer, toc: list | None = None) -> str:
    lines = source.splitlines()
    out: list[str] = []
    i = 0
    para: list[str] = []

    def flush() -> None:
        if para:
            out.append(f"<p>{inline(' '.join(para), fix_link)}</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush()
            lang = stripped[3:].strip()
            body = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1
            out.append(code_block("\n".join(body), lang))
            continue

        if stripped.startswith(":::"):
            flush()
            spec = stripped[3:].strip()
            name, _, arg = spec.partition(" ")
            if name in CONTAINERS:
                depth = 1
                body = []
                i += 1
                while i < len(lines):
                    s = lines[i].strip()
                    if s.startswith(":::"):
                        inner = s[3:].strip().split(" ", 1)[0]
                        if inner in CONTAINERS:
                            depth += 1
                        elif inner == "":
                            depth -= 1
                            if depth == 0:
                                break
                    body.append(lines[i])
                    i += 1
                i += 1
                out.append(container(name, arg.strip(), render("\n".join(body), directive, fix_link, toc)))
                continue
            if name == "":
                i += 1
                continue
            out.append(directive(name, arg.strip()))
            i += 1
            continue

        heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading:
            flush()
            level = len(heading.group(1))
            text = heading.group(2).strip()
            anchor = slugify(text)
            if toc is not None and level in (2, 3):
                toc.append((level, anchor, re.sub(r"`", "", text)))
            out.append(f'<h{level} id="{anchor}">{inline(text, fix_link)}<a class="anchor" href="#{anchor}" aria-label="Link to this section">#</a></h{level}>')
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"^\|?\s*:?-{3,}", lines[i + 1].strip()):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            out.append(table(rows, fix_link))
            continue

        if re.match(r"^([-*]|\d+\.)\s+", stripped):
            flush()
            ordered = bool(re.match(r"^\d+\.", stripped))
            items: list[str] = []
            while i < len(lines):
                s = lines[i]
                m = re.match(r"^([-*]|\d+\.)\s+(.*)$", s.strip())
                if m and not s.startswith("   ") and (bool(re.match(r"^\d+\.", s.strip())) == ordered):
                    items.append(m.group(2))
                elif s.startswith("  ") and s.strip() and items:
                    items[-1] += " " + s.strip()
                else:
                    break
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(item, fix_link)}</li>" for item in items) + f"</{tag}>")
            continue

        if stripped.startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            out.append(f"<blockquote>{render(chr(10).join(quote), directive, fix_link)}</blockquote>")
            continue

        if not stripped:
            flush()
            i += 1
            continue

        para.append(stripped)
        i += 1

    flush()
    return "\n".join(out)


def code_block(body: str, lang: str) -> str:
    if lang == "output":
        return (
            '<figure class="code output"><figcaption><span class="tag tag-output">Expected output</span></figcaption>'
            f"<pre><code>{escape(body)}</code></pre></figure>"
        )
    label = {"bash": "Shell", "sh": "Shell", "js": "JavaScript", "json": "JSON", "toml": "TOML", "yaml": "YAML", "py": "Python", "python": "Python", "sql": "SQL", "graphql": "GraphQL", "http": "HTTP", "text": "Text"}.get(lang, lang or "Code")
    return (
        f'<figure class="code"><figcaption><span class="tag">{escape(label)}</span>'
        '<button type="button" class="copy" data-copy>Copy</button></figcaption>'
        f'<pre><code class="language-{escape(lang or "text")}">{escape(body)}</code></pre></figure>'
    )


def table(rows: list[str], fix_link: LinkFixer) -> str:
    def cells(row: str) -> list[str]:
        row = row.strip().strip("|")
        return [c.strip() for c in row.split("|")]

    head = cells(rows[0])
    body = rows[2:]
    html = ['<div class="table-wrap"><table><thead><tr>']
    html += [f"<th scope=\"col\">{inline(c, fix_link)}</th>" for c in head]
    html.append("</tr></thead><tbody>")
    for row in body:
        html.append("<tr>" + "".join(f"<td>{inline(c, fix_link)}</td>" for c in cells(row)) + "</tr>")
    html.append("</tbody></table></div>")
    return "".join(html)


def container(name: str, title: str, inner: str) -> str:
    if name == "details":
        return f'<details class="details"><summary>{escape(title or "Details")}</summary>{inner}</details>'
    if name == "steps":
        return f'<div class="steps">{inner}</div>'
    label = {"note": "Note", "tip": "Tip", "warn": "Careful"}[name]
    heading = escape(title) if title else label
    return f'<aside class="callout callout-{name}"><p class="callout-title">{heading}</p>{inner}</aside>'
