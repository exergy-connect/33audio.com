(function () {
  var form = document.querySelector("[data-ask-form]");
  if (!form) return;
  var input = form.querySelector("input[name=q]");
  var modeEl = document.querySelector("[data-ask-mode]");
  var summaryEl = document.querySelector("[data-ask-summary]");
  var list = document.querySelector("[data-ask-results]");

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  function localPath(url) {
    try {
      return ".." + new URL(url).pathname;
    } catch (e) {
      return url;
    }
  }

  function render(data) {
    modeEl.hidden = false;
    modeEl.textContent = data.mode === "ai"
      ? "Answered with Workers AI (" + data.model + ") in " + data.took_ms + " ms."
      : "Answered by the keyword parser in " + data.took_ms + " ms. " + (data.fallback_reason || "");
    summaryEl.textContent = data.summary;
    list.textContent = "";
    data.results.forEach(function (r) {
      var li = el("li", "ask-result");
      var a = el("a", "ask-part", r.part_number);
      a.href = localPath(r.url);
      li.appendChild(a);
      li.appendChild(el("span", "ask-spec", r.resistance + " · " + r.tolerance + " · " + r.voltage_rating + " V · " + r.power_rating + " W · " + r.quantity + " in source catalog · source price $" + r.price));
      if (r.why && r.why.length) li.appendChild(el("span", "ask-why", r.why.join(", ")));
      list.appendChild(li);
    });
  }

  function ask(q) {
    summaryEl.textContent = "Searching…";
    list.textContent = "";
    var url = new URL("../api/search", location.href);
    url.searchParams.set("q", q);
    history.replaceState(null, "", "?q=" + encodeURIComponent(q));
    fetch(url.toString(), { headers: { Accept: "application/json" } })
      .then(function (response) {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.json();
      })
      .then(render)
      .catch(function () {
        modeEl.hidden = true;
        summaryEl.textContent = "The part finder needs the site's /api/search function, which did not answer. Use the catalog search instead.";
      });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var q = input.value.trim();
    if (q) ask(q);
  });
  document.querySelectorAll("[data-ask-example]").forEach(function (button) {
    button.addEventListener("click", function () {
      input.value = button.textContent;
      ask(button.textContent);
    });
  });
  var initial = new URLSearchParams(location.search).get("q");
  if (initial) {
    input.value = initial;
    ask(initial);
  }
})();
