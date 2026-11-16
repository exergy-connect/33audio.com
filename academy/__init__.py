"""Exergy ∞ Engineering Academy static site generator."""

from pathlib import Path

ACADEMY = Path(__file__).resolve().parent
ROOT = ACADEMY.parent
CONTENT = ACADEMY / "content"
STATIC = ACADEMY / "static"
DATA = ACADEMY / "data"
DIST = ACADEMY / "dist"
