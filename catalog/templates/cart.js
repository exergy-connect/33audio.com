(function (factory) {
  var api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", api.init);
    else api.init();
  }
})(function () {
  var KEY = "33audio-cart";

  function toCents(value) {
    var text = String(value == null ? "" : value).trim();
    if (!/^\d+(\.\d{1,2})?$/.test(text)) return null;
    var pieces = text.split(".");
    return Number(pieces[0]) * 100 + Number(((pieces[1] || "") + "00").slice(0, 2));
  }

  function money(cents) {
    return "$" + Math.floor(cents / 100) + "." + String(cents % 100).padStart(2, "0");
  }

  function clampQty(qty, available) {
    var n = Math.floor(Number(qty));
    var max = Math.max(0, Math.floor(Number(available) || 0));
    if (!isFinite(n) || n < 1) n = 1;
    return Math.min(n, max);
  }

  // items: { id: qty }. parts: { id: { price, qty } }. Unknown or sold-out parts drop out.
  function cartTotals(items, parts, shipping) {
    var lines = [];
    var subtotal = 0;
    var count = 0;
    Object.keys(items || {}).forEach(function (id) {
      var part = parts[id];
      if (!part) return;
      var unit = toCents(part.price);
      var qty = clampQty(items[id], part.qty);
      if (unit === null || qty < 1) return;
      lines.push({ id: id, qty: qty, unitCents: unit, lineCents: unit * qty, available: part.qty });
      subtotal += unit * qty;
      count += qty;
    });
    var shippingCents = lines.length ? toCents(shipping) || 0 : 0;
    return { lines: lines, count: count, subtotalCents: subtotal, shippingCents: shippingCents, totalCents: subtotal + shippingCents };
  }

  function load() {
    try {
      var data = JSON.parse(localStorage.getItem(KEY) || "{}");
      return data && typeof data === "object" && !Array.isArray(data) ? data : {};
    } catch (error) {
      return {};
    }
  }

  function save(items) {
    try {
      localStorage.setItem(KEY, JSON.stringify(items));
    } catch (error) {
      /* storage can be blocked; the cart then lasts for this page only */
    }
  }

  function flow() {
    return document.documentElement.getAttribute("data-payment-flow") || "ebay";
  }

  function init() {
    var root = document.documentElement.getAttribute("data-root") || "./";
    var state = { items: load(), parts: {}, shipping: "0.00", live: false };

    if (document.querySelector("[data-clear-cart]")) {
      state.items = {};
      save(state.items);
    }

    function setText(selector, text) {
      Array.prototype.forEach.call(document.querySelectorAll(selector), function (node) { node.textContent = text; });
    }

    function available(id) {
      var part = state.parts[id];
      return part ? part.qty : 0;
    }

    function updateStockLabels() {
      Array.prototype.forEach.call(document.querySelectorAll("[data-stock-qty]"), function (node) {
        var id = node.getAttribute("data-stock-qty");
        if (state.parts[id]) node.textContent = String(state.parts[id].qty);
      });
      Array.prototype.forEach.call(document.querySelectorAll("[data-add-to-cart]"), function (button) {
        var id = button.getAttribute("data-add-to-cart");
        var left = available(id) - (state.items[id] || 0);
        button.disabled = left < 1;
        if (button.hasAttribute("data-label")) {
          button.textContent = available(id) < 1 ? "Sold out" : left < 1 ? "All in cart" : button.getAttribute("data-label");
        }
      });
      Array.prototype.forEach.call(document.querySelectorAll("[data-qty-input]"), function (input) {
        var id = input.getAttribute("data-qty-input");
        var max = Math.max(1, available(id) - (state.items[id] || 0));
        input.max = String(max);
        input.value = String(clampQty(input.value, max) || 1);
      });
      var source = document.querySelector("[data-stock-source]");
      if (source) source.textContent = state.live ? "Live stock" : "Stock as of the last site build";
    }

    function renderCount() {
      var totals = cartTotals(state.items, state.parts, state.shipping);
      setText("[data-cart-count]", String(totals.count));
      return totals;
    }

    function setItem(id, qty) {
      if (qty < 1) delete state.items[id];
      else state.items[id] = clampQty(qty, available(id));
      save(state.items);
      refresh();
    }

    function renderCartPage(totals) {
      var list = document.querySelector("[data-cart-lines]");
      if (!list) return;
      list.replaceChildren();
      totals.lines.forEach(function (line) {
        var part = state.parts[line.id];
        var li = document.createElement("li");
        li.className = "cart-line";
        var name = document.createElement("a");
        name.className = "pid";
        name.href = root + "parts/" + line.id.toLowerCase() + "/";
        name.textContent = line.id;
        var meta = document.createElement("span");
        meta.className = "meta";
        meta.textContent = (part.label || "") + " · " + money(line.unitCents) + " each · " + line.available + " available";
        var stepper = document.createElement("div");
        stepper.className = "stepper";
        var minus = document.createElement("button");
        minus.type = "button";
        minus.textContent = "−";
        minus.setAttribute("aria-label", "One fewer " + line.id);
        minus.addEventListener("click", function () { setItem(line.id, line.qty - 1); });
        var qty = document.createElement("output");
        qty.textContent = String(line.qty);
        qty.setAttribute("aria-label", "Quantity of " + line.id);
        var plus = document.createElement("button");
        plus.type = "button";
        plus.textContent = "+";
        plus.disabled = line.qty >= line.available;
        plus.setAttribute("aria-label", "One more " + line.id);
        plus.addEventListener("click", function () { setItem(line.id, line.qty + 1); });
        stepper.appendChild(minus);
        stepper.appendChild(qty);
        stepper.appendChild(plus);
        var price = document.createElement("strong");
        price.className = "line-total";
        price.textContent = money(line.lineCents);
        var remove = document.createElement("button");
        remove.type = "button";
        remove.className = "link-button";
        remove.textContent = "Remove";
        remove.addEventListener("click", function () { setItem(line.id, 0); });
        li.appendChild(name);
        li.appendChild(meta);
        li.appendChild(stepper);
        li.appendChild(price);
        li.appendChild(remove);
        list.appendChild(li);
      });
      var empty = document.querySelector("[data-cart-empty]");
      var summary = document.querySelector("[data-cart-summary]");
      if (empty) empty.hidden = totals.lines.length > 0;
      if (summary) summary.hidden = totals.lines.length === 0;
      setText("[data-cart-subtotal]", money(totals.subtotalCents));
      setText("[data-cart-shipping]", money(totals.shippingCents));
      setText("[data-cart-total]", money(totals.totalCents));
      var checkout = document.querySelector("[data-checkout]");
      if (checkout) checkout.disabled = totals.lines.length === 0 || flow() !== "stripe";
    }

    function refresh() {
      updateStockLabels();
      renderCartPage(renderCount());
    }

    function status(message, kind) {
      var node = document.querySelector("[data-checkout-status]");
      if (!node) return;
      node.hidden = !message;
      node.textContent = message || "";
      node.className = "note" + (kind ? " " + kind : "");
    }

    document.addEventListener("click", function (event) {
      var add = event.target.closest("[data-add-to-cart]");
      if (add) {
        var id = add.getAttribute("data-add-to-cart");
        var input = document.querySelector('[data-qty-input="' + CSS.escape(id) + '"]');
        var qty = input ? Number(input.value) : 1;
        setItem(id, (state.items[id] || 0) + qty);
        var done = document.querySelector('[data-added="' + CSS.escape(id) + '"]');
        if (done) done.hidden = false;
        return;
      }
      var step = event.target.closest("[data-step]");
      if (step) {
        var field = document.querySelector('[data-qty-input="' + CSS.escape(step.getAttribute("data-step-for")) + '"]');
        if (field) {
          field.value = String(clampQty(Number(field.value) + Number(step.getAttribute("data-step")), field.max));
        }
      }
    });

    var checkoutButton = document.querySelector("[data-checkout]");
    if (checkoutButton) {
      fetch(root + "api/checkout", { headers: { Accept: "application/json" } })
        .then(function (response) { return response.json(); })
        .then(function (data) {
          if (!data.enabled) status(data.message || "Checkout is a demo, not yet active.", "demo");
        })
        .catch(function () {
          status("The checkout service is not reachable from this preview. Checkout is a demo, not yet active.", "demo");
        });
      checkoutButton.addEventListener("click", function () {
        var items = Object.keys(state.items).map(function (id) { return { id: id, qty: state.items[id] }; });
        checkoutButton.disabled = true;
        status("Starting checkout…");
        fetch(root + "api/checkout", {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ items: items }),
        })
          .then(function (response) { return response.json().then(function (data) { return { ok: response.ok, data: data }; }); })
          .then(function (result) {
            if (result.ok && result.data.url) {
              window.location.assign(result.data.url);
              return;
            }
            var problems = (result.data.problems || []).map(function (p) { return p.message; }).join(" ");
            status([result.data.message, problems].filter(Boolean).join(" "), result.data.enabled === false ? "demo" : "error");
            checkoutButton.disabled = false;
          })
          .catch(function () {
            status("Checkout could not be reached. Please try again later.", "error");
            checkoutButton.disabled = false;
          });
      });
    }

    var select = document.querySelector("[data-payment-select]");
    if (select) select.addEventListener("change", function () { setTimeout(refresh, 0); });

    fetch(root + "search.json")
      .then(function (response) { return response.json(); })
      .then(function (index) {
        (index.parts || []).forEach(function (part) {
          state.parts[part.id] = { price: part.price, qty: part.quantity, label: part.label };
        });
        state.shipping = index.shipping || state.shipping;
        refresh();
        return fetch(root + "api/stock", { headers: { Accept: "application/json" } });
      })
      .then(function (response) {
        if (!response || !response.ok) throw new Error("no live stock");
        return response.json();
      })
      .then(function (doc) {
        (doc.parts || []).forEach(function (part) {
          var known = state.parts[part.id] || {};
          state.parts[part.id] = { price: part.price, qty: part.qty, label: known.label || part.value };
        });
        if (doc.shipping) state.shipping = doc.shipping;
        state.live = true;
        refresh();
      })
      .catch(function () {
        refresh();
      });
  }

  return { toCents: toCents, money: money, clampQty: clampQty, cartTotals: cartTotals, init: init };
});
