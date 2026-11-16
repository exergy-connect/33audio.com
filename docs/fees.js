(function () {
  var ratesNode = document.getElementById("fee-rates");
  var form = document.querySelector("[data-fee-form]");
  var out = document.querySelector("[data-fee-result]");
  if (!ratesNode || !form || !out) return;
  var rates = JSON.parse(ratesNode.textContent);

  function cents(value) {
    var number = Number(value);
    if (!isFinite(number) || number < 0) return null;
    return Math.round(number * 100);
  }

  function money(centsValue) {
    var sign = centsValue < 0 ? "-" : "";
    var abs = Math.abs(centsValue);
    return sign + "$" + Math.floor(abs / 100) + "." + String(abs % 100).padStart(2, "0");
  }

  function percentFee(total, percent) {
    return Math.round(total * Number(percent) / 100);
  }

  function ebayFee(total) {
    var ebay = rates.ebay;
    var cap = cents(ebay.cap);
    var threshold = cents(ebay.order_threshold);
    var base = Math.min(total, cap);
    var above = Math.max(0, total - cap);
    var per = total <= threshold ? cents(ebay.per_order_fee_at_or_under_threshold) : cents(ebay.per_order_fee_over_threshold);
    return percentFee(base, ebay.final_value_percent) + percentFee(above, ebay.above_cap_percent) + per;
  }

  function render() {
    var data = new FormData(form);
    var price = cents(data.get("price"));
    var shipping = cents(data.get("shipping"));
    var quantity = Number(data.get("quantity"));
    if (price === null || shipping === null || !isFinite(quantity) || quantity < 1) {
      out.textContent = "Enter a price, a shipping amount, and a quantity of at least 1.";
      return;
    }
    var total = price * Math.round(quantity) + shipping;
    var rows = [
      ["Buyer pays", money(total)],
      ["eBay fee", money(ebayFee(total))],
      ["Stripe fee", money(percentFee(total, rates.stripe.percent) + cents(rates.stripe.fixed))],
      ["PayPal Checkout fee", money(percentFee(total, rates.paypal.percent) + cents(rates.paypal.fixed))]
    ];
    out.replaceChildren();
    rows.forEach(function (row) {
      var line = document.createElement("div");
      var label = document.createElement("dt");
      var value = document.createElement("dd");
      label.textContent = row[0];
      value.textContent = row[1];
      line.appendChild(label);
      line.appendChild(value);
      out.appendChild(line);
    });
  }

  form.addEventListener("input", render);
  render();
})();
