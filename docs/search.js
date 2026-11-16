(function (factory) {
  var api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", api.init);
    } else {
      api.init();
    }
  }
})(function () {
  var IGNORE = { k: 1, m: 1, r: 1, ohm: 1, ohms: 1 };

  function tokens(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/ω|Ω/g, " ")
      .replace(/[^a-z0-9.]+/g, " ")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
  }

  function queryMatches(blob, query) {
    var need = tokens(query);
    var core = need.filter(function (token) { return !IGNORE[token]; });
    if (core.length) need = core;
    if (!need.length) return true;
    var have = tokens(blob);
    return need.every(function (queryToken) {
      return have.some(function (haveToken) {
        if (haveToken === queryToken) return true;
        if (haveToken.indexOf(queryToken) !== 0) return false;
        var rest = haveToken.slice(queryToken.length);
        return rest === "k" || rest === "m" || rest === "ohm" || rest === "ohms";
      });
    });
  }

  function renderHit(part, root) {
    var link = document.createElement("a");
    link.className = "part-row";
    link.href = part.source === "ebay" ? part.url : root + part.url;
    if (part.source === "ebay") {
      link.target = "_blank";
      link.rel = "noopener noreferrer";
    }
    var pid = document.createElement("span");
    pid.className = "pid";
    pid.textContent = part.source === "ebay" ? part.label : part.id;
    var meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent = part.source === "ebay"
      ? "eBay listing · " + part.currency + " " + part.price + " for the described lot"
      : "Caddock reference · " + part.label + " · " + part.tolerance + " · source price $" + part.price + " · ask about availability";
    link.appendChild(pid);
    link.appendChild(meta);
    return link;
  }

  function init() {
    var input = document.querySelector("[data-search-input]");
    if (!input) return;
    var root = document.documentElement.getAttribute("data-root") || "./";
    var list = document.querySelector("[data-search-list]");
    var live = document.querySelector("[data-search-live]");
    var status = document.querySelector("[data-search-status]");
    var empty = document.querySelector("[data-search-empty]");
    var chips = Array.prototype.slice.call(document.querySelectorAll("[data-series-chip]"));
    if (!list && !live) return;
    var series = "";

    fetch(root + "search.json")
      .then(function (response) {
        if (!response.ok) throw new Error(String(response.status));
        return response.json();
      })
      .then(function (index) {
        var parts = (index.parts || []).concat(index.listings || []);
        var byId = {};
        parts.forEach(function (part) { byId[part.id] = part; });

        function matchedParts() {
          var query = input.value || "";
          return parts.filter(function (part) {
            if (series && part.series !== series) return false;
            return queryMatches(part.search, query);
          });
        }

        function render() {
          var matched = matchedParts();
          var query = input.value.trim();
          var active = Boolean(query || series);
          if (list) {
            Array.prototype.forEach.call(list.querySelectorAll("[data-part-id]"), function (row) {
              var part = byId[row.getAttribute("data-part-id")];
              row.hidden = part ? matched.indexOf(part) === -1 : false;
            });
          }
          if (live) {
            live.innerHTML = "";
            if (!active && !live.hasAttribute("data-search-all")) {
              live.hidden = true;
            } else {
              live.hidden = false;
              var liveMatches = live.hasAttribute("data-search-ebay-only") ? matched.filter(function (part) { return part.source === "ebay"; }) : matched;
              var shown = live.hasAttribute("data-search-all") ? liveMatches : liveMatches.slice(0, 8);
              shown.forEach(function (part) { live.appendChild(renderHit(part, root)); });
              if (!matched.length) {
                var none = document.createElement("p");
                none.textContent = "No items match. Try a brand, part number, value, or keyword.";
                live.appendChild(none);
              } else if (liveMatches.length > shown.length) {
                var more = document.createElement("a");
                more.className = "more";
                more.href = root + "search/?q=" + encodeURIComponent(query);
                more.textContent = "All " + matched.length + " matches";
                live.appendChild(more);
              }
            }
          }
          if (empty) empty.hidden = !(list && active && matched.length === 0);
          if (status) {
            status.textContent = active
              ? matched.length + (matched.length === 1 ? " match" : " matches")
              : parts.length + " Caddock items and eBay listings";
          }
        }

        chips.forEach(function (chip) {
          chip.addEventListener("click", function () {
            series = chip.getAttribute("data-series-chip") || "";
            chips.forEach(function (item) {
              item.setAttribute("aria-pressed", (item.getAttribute("data-series-chip") || "") === series ? "true" : "false");
            });
            render();
          });
        });
        input.addEventListener("input", render);
        var params = new URLSearchParams(window.location.search);
        if (params.get("q")) input.value = params.get("q");
        var initialSeries = (params.get("series") || "").toUpperCase();
        if (initialSeries) {
          series = initialSeries;
          chips.forEach(function (item) {
            item.setAttribute("aria-pressed", (item.getAttribute("data-series-chip") || "").toUpperCase() === series ? "true" : "false");
          });
        }
        render();
      })
      .catch(function () {
        if (status) status.textContent = "Search is unavailable. Series pages still list every part.";
      });
  }

  return { queryMatches: queryMatches, init: init };
});
