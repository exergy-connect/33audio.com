"""Inline SVG pieces for the retro hi-fi theme. Decorative only, so every SVG is aria-hidden."""

from __future__ import annotations

import math

RECORD_SVG = (
    '<svg class="brand-record" viewBox="0 0 64 64" width="44" height="44" aria-hidden="true" focusable="false">'
    '<circle cx="32" cy="32" r="32" fill="#18120d"/>'
    '<g fill="none" stroke="#3a2e24" stroke-width=".6">'
    '<circle cx="32" cy="32" r="28"/><circle cx="32" cy="32" r="24.5"/><circle cx="32" cy="32" r="21"/><circle cx="32" cy="32" r="17.5"/>'
    "</g>"
    '<path d="M32 2a30 30 0 0 1 21 8.7l-4.2 4.2A24 24 0 0 0 32 8z" fill="#fff" opacity=".12"/>'
    '<circle cx="32" cy="32" r="12" fill="#d98b2b"/>'
    '<path d="M22.5 28h19" stroke="#8c4510" stroke-width="1.4"/>'
    '<text x="32" y="38.5" text-anchor="middle" font-family="Futura,Century Gothic,sans-serif" font-size="7" font-weight="700" fill="#2c190d">33⅓</text>'
    '<circle cx="32" cy="32" r="1.6" fill="#f3ead6"/>'
    "</svg>"
)

HERO_SVG = (
    '<svg class="hero-art" viewBox="0 0 240 200" width="256" height="213" aria-hidden="true" focusable="false">'
    '<rect x="4" y="18" width="164" height="164" rx="3" fill="#2f6f6a"/>'
    '<rect x="4" y="18" width="164" height="164" rx="3" fill="none" stroke="#1f5653" stroke-width="2"/>'
    '<path d="M18 160h64M18 150h48" stroke="#f3ead6" stroke-width="3" opacity=".75"/>'
    '<text x="18" y="52" font-family="Futura,Century Gothic,sans-serif" font-size="26" font-weight="700" fill="#f3ead6" letter-spacing="1">33⅓</text>'
    '<text x="18" y="68" font-family="Futura,Century Gothic,sans-serif" font-size="9" font-weight="700" fill="#f6c56f" letter-spacing="2">HI-FI · LP</text>'
    '<g transform="translate(166 100)">'
    '<circle r="72" fill="#18120d"/>'
    '<g fill="none" stroke="#3a2e24" stroke-width=".8">'
    '<circle r="66"/><circle r="60"/><circle r="54"/><circle r="48"/><circle r="42"/><circle r="36"/>'
    "</g>"
    '<path d="M0-70a70 70 0 0 1 49.5 20.5l-8.5 8.5A58 58 0 0 0 0-58z" fill="#fff" opacity=".1"/>'
    '<circle r="28" fill="#d98b2b"/>'
    '<circle r="28" fill="none" stroke="#8c4510" stroke-width="1"/>'
    '<text y="-8" text-anchor="middle" font-family="Futura,Century Gothic,sans-serif" font-size="7.5" font-weight="700" fill="#2c190d" letter-spacing=".8">33AUDIO</text>'
    '<text y="16" text-anchor="middle" font-family="Futura,Century Gothic,sans-serif" font-size="5" font-weight="700" fill="#2c190d" letter-spacing=".4">NOS · CADDOCK</text>'
    '<circle r="2.6" fill="#f3ead6"/>'
    "</g>"
    '<g stroke-linecap="round">'
    '<circle cx="224" cy="22" r="10" fill="#c9cac5" stroke="#8d8e88"/>'
    '<path d="M224 22l-8 92-30 30" fill="none" stroke="#c9cac5" stroke-width="4"/>'
    '<rect x="176" y="140" width="16" height="9" rx="2" transform="rotate(-45 184 144.5)" fill="#2c190d"/>'
    "</g>"
    "</svg>"
)

VU_SCALE_MAX = 20.0
VU_SWEEP = 50.0


def _point(cx: float, cy: float, radius: float, degrees: float) -> tuple[float, float]:
    angle = math.radians(degrees - 90)
    return round(cx + radius * math.cos(angle), 2), round(cy + radius * math.sin(angle), 2)


def _angle(percent: float) -> float:
    clamped = max(0.0, min(percent, VU_SCALE_MAX))
    return -VU_SWEEP + (clamped / VU_SCALE_MAX) * 2 * VU_SWEEP


def vu_meter(percent: float, key: str) -> str:
    """A VU-style meter whose needle shows a fee as a percent of what the buyer pays, on a 0 to 20% scale."""
    cx, cy, radius = 80.0, 92.0, 66.0
    ticks = []
    labels = []
    for value in range(0, int(VU_SCALE_MAX) + 1, 5):
        degrees = _angle(value)
        x1, y1 = _point(cx, cy, radius, degrees)
        x2, y2 = _point(cx, cy, radius - 8, degrees)
        ticks.append(f'<path d="M{x1} {y1}L{x2} {y2}"/>')
        lx, ly = _point(cx, cy, radius + 9, degrees)
        labels.append(f'<text x="{lx}" y="{ly}">{value}</text>')
    for value in range(1, int(VU_SCALE_MAX)):
        if value % 5:
            degrees = _angle(value)
            x1, y1 = _point(cx, cy, radius, degrees)
            x2, y2 = _point(cx, cy, radius - 4, degrees)
            ticks.append(f'<path d="M{x1} {y1}L{x2} {y2}"/>')
    sx, sy = _point(cx, cy, radius, _angle(0))
    rx, ry = _point(cx, cy, radius, _angle(15))
    ex, ey = _point(cx, cy, radius, _angle(VU_SCALE_MAX))
    nx, ny = _point(cx, cy, radius - 2, _angle(percent))
    return (
        '<svg class="vu" viewBox="0 0 160 96" width="288" height="173" aria-hidden="true" focusable="false">'
        f'<defs><radialGradient id="vu-glow-{key}" cx="50%" cy="85%" r="85%">'
        '<stop offset="0" stop-color="#fbe2a6"/><stop offset=".7" stop-color="#f2c06a"/><stop offset="1" stop-color="#d9973d"/>'
        "</radialGradient></defs>"
        f'<rect width="160" height="96" fill="url(#vu-glow-{key})"/>'
        f'<path d="M{sx} {sy}A{radius} {radius} 0 0 1 {rx} {ry}" fill="none" stroke="#2c190d" stroke-width="1.4"/>'
        f'<path d="M{rx} {ry}A{radius} {radius} 0 0 1 {ex} {ey}" fill="none" stroke="#a12d1d" stroke-width="4"/>'
        f'<g stroke="#2c190d" stroke-width="1.2">{"".join(ticks)}</g>'
        '<g font-family="Futura,Century Gothic,sans-serif" font-size="8" font-weight="700" fill="#2c190d" text-anchor="middle" dominant-baseline="middle">'
        f'{"".join(labels)}</g>'
        '<text x="10" y="88" font-family="Futura,Century Gothic,sans-serif" font-size="9" font-weight="700" fill="#2c190d" letter-spacing="1.5">FEE %</text>'
        f'<path d="M{cx} {cy}L{nx} {ny}" stroke="#18120d" stroke-width="1.6" stroke-linecap="round"/>'
        f'<circle cx="{cx}" cy="{cy}" r="6" fill="#2c190d"/>'
        "</svg>"
    )
