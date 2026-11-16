(function () {
  var KEY = "33audio-payment-flow";
  var select = document.querySelector("[data-payment-select]");

  function apply(flow) {
    if (flow !== "ebay" && flow !== "stripe" && flow !== "paypal") flow = "ebay";
    document.documentElement.setAttribute("data-payment-flow", flow);
    if (select) select.value = flow;
    try {
      localStorage.setItem(KEY, flow);
    } catch (error) {
      /* private browsing can block storage; the choice still applies this page */
    }
  }

  if (!select) return;
  var current = document.documentElement.getAttribute("data-payment-flow") || "ebay";
  select.value = current;
  select.addEventListener("change", function () {
    apply(select.value);
  });
})();
