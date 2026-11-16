// Server-side cart rules. Prices and quantities always come from the stock document.

export const MAX_LINES = 100;
export const MAX_APPLIED_SESSIONS = 500;

export function toCents(amount) {
  const text = String(amount ?? "").trim();
  if (!/^\d+(\.\d{1,2})?$/.test(text)) throw new Error(`bad money value ${JSON.stringify(amount)}`);
  const [whole, frac = ""] = text.split(".");
  return Number(whole) * 100 + Number((frac + "00").slice(0, 2));
}

export function partsById(doc) {
  const map = new Map();
  for (const part of doc?.parts ?? []) map.set(part.id, part);
  return map;
}

// Returns { ok, errors, lines, subtotalCents, shippingCents, totalCents }.
export function validateCart(items, doc) {
  const errors = [];
  if (!Array.isArray(items) || items.length === 0) {
    return { ok: false, errors: [{ code: "empty_cart", message: "The cart is empty." }], lines: [] };
  }
  const wanted = new Map();
  for (const item of items) {
    const id = typeof item?.id === "string" ? item.id : "";
    const qty = item?.qty;
    if (!id || !Number.isInteger(qty) || qty < 1) {
      errors.push({ code: "bad_item", id, message: "Each line needs a part id and a whole-number quantity of at least 1." });
      continue;
    }
    wanted.set(id, (wanted.get(id) ?? 0) + qty);
  }
  if (wanted.size > MAX_LINES) {
    errors.push({ code: "too_many_lines", message: `A cart can hold at most ${MAX_LINES} different parts.` });
  }
  const stock = partsById(doc);
  const lines = [];
  for (const [id, qty] of wanted) {
    const part = stock.get(id);
    if (!part) {
      errors.push({ code: "unknown_part", id, message: `${id} is not in the current stock list.` });
      continue;
    }
    const available = Number.isInteger(part.qty) ? part.qty : 0;
    if (available < 1) {
      errors.push({ code: "out_of_stock", id, available: 0, message: `${id} is out of stock.` });
      continue;
    }
    if (qty > available) {
      errors.push({ code: "insufficient_stock", id, available, message: `Only ${available} of ${id} available.` });
      continue;
    }
    lines.push({
      id,
      partNumber: part.part_number ?? id,
      name: `Caddock ${part.part_number ?? id} resistor`,
      unitCents: toCents(part.price),
      qty,
    });
  }
  if (errors.length) return { ok: false, errors, lines: [] };
  const subtotalCents = lines.reduce((sum, line) => sum + line.unitCents * line.qty, 0);
  const shippingCents = toCents(doc.shipping);
  return { ok: true, errors: [], lines, subtotalCents, shippingCents, totalCents: subtotalCents + shippingCents };
}

// Applies a paid order to the stock document. Re-delivered webhooks are ignored by session id.
export function applySale(doc, sold, sessionId) {
  const applied = Array.isArray(doc.applied_sessions) ? doc.applied_sessions : [];
  if (sessionId && applied.includes(sessionId)) {
    return { changed: false, doc, oversold: [] };
  }
  const next = structuredClone(doc);
  const stock = partsById(next);
  const oversold = [];
  for (const { id, qty } of sold) {
    const part = stock.get(id);
    if (!part) {
      oversold.push({ id, qty, available: 0 });
      continue;
    }
    const available = Number.isInteger(part.qty) ? part.qty : 0;
    if (qty > available) oversold.push({ id, qty, available });
    part.qty = Math.max(0, available - qty);
  }
  next.applied_sessions = [...applied, sessionId].filter(Boolean).slice(-MAX_APPLIED_SESSIONS);
  next.updated_at = new Date().toISOString();
  return { changed: true, doc: next, oversold };
}

export function publicStock(doc) {
  const { applied_sessions, ...rest } = doc;
  return rest;
}
