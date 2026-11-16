"""Selling-cost estimates from the rates stored in data/site.json."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def to_cents(amount: str | int | float) -> int:
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def _percent(total_cents: int, percent: str) -> int:
    value = Decimal(total_cents) * Decimal(percent) / Decimal(100)
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def estimate(item_cents: int, shipping_cents: int, quantity: int, costs: dict) -> dict:
    if quantity < 1:
        raise ValueError("quantity must be at least 1")
    total = item_cents * quantity + shipping_cents
    ebay = costs["ebay"]
    cap = to_cents(ebay["cap"])
    threshold = to_cents(ebay["order_threshold"])
    base = min(total, cap)
    above = max(0, total - cap)
    ebay_fee = (
        _percent(base, ebay["final_value_percent"])
        + _percent(above, ebay["above_cap_percent"])
        + to_cents(ebay["per_order_fee_at_or_under_threshold"] if total <= threshold else ebay["per_order_fee_over_threshold"])
    )
    stripe = costs["stripe"]
    paypal = costs["paypal"]
    stripe_fee = _percent(total, stripe["percent"]) + to_cents(stripe["fixed"])
    paypal_fee = _percent(total, paypal["percent"]) + to_cents(paypal["fixed"])
    return {
        "total_cents": total,
        "ebay_cents": ebay_fee,
        "stripe_cents": stripe_fee,
        "paypal_cents": paypal_fee,
    }
