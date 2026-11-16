(function () {
  "use strict";

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (key) {
      if (key === "text") node.textContent = attrs[key];
      else if (key === "cls") node.className = attrs[key];
      else node.setAttribute(key, attrs[key]);
    });
    (children || []).forEach(function (child) { if (child) node.appendChild(child); });
    return node;
  }

  function badge(kind, meta) {
    var wrap = el("div", { cls: "provenance" });
    wrap.appendChild(el("span", { cls: "badge " + (kind === "real" ? "badge-real" : "badge-sim"), text: kind === "real" ? "REAL TELEMETRY" : "SIMULATED / EXAMPLE DATA" }));
    if (meta) wrap.appendChild(el("span", { cls: "badge-meta", text: meta }));
    return wrap;
  }

  function kvList(obj) {
    var dl = el("dl", { cls: "kv-grid" });
    Object.keys(obj).forEach(function (key) {
      dl.appendChild(el("dt", { text: key }));
      dl.appendChild(el("dd", { text: obj[key] == null ? "–" : String(obj[key]) }));
    });
    return dl;
  }

  function unavailable(out, path, error) {
    out.textContent = "";
    out.appendChild(el("p", { cls: "muted", text: path + " did not answer (" + error + "). Live widgets need the Academy Worker: run `npm run dev --prefix academy` or open the deployed site." }));
  }

  function timedFetch(url) {
    var t0 = performance.now();
    return fetch(url, { cache: "no-store" }).then(function (response) {
      return response.text().then(function (text) {
        var data = null;
        try { data = JSON.parse(text); } catch (e) { /* not JSON */ }
        return { response: response, data: data, ms: Math.round((performance.now() - t0) * 10) / 10 };
      });
    });
  }

  var widgets = {
    echo: function (out) {
      return timedFetch("/api/lab/echo").then(function (r) {
        if (!r.data || !r.response.ok) throw new Error("HTTP " + r.response.status);
        out.textContent = "";
        out.appendChild(badge("real", "Round trip measured by your browser · " + new Date().toISOString()));
        out.appendChild(kvList({ "round trip (ms)": r.ms, status: r.response.status, "server-timing": r.response.headers.get("server-timing") }));
        out.appendChild(badge(r.data.kind, r.data.source + " · " + r.data.collected_at));
        out.appendChild(kvList(Object.assign({}, r.data.edge, { ray: r.data.request.ray })));
      });
    },
    cache: function (out) {
      var key = "w" + Date.now();
      return timedFetch("/api/lab/cache?key=" + key + "&ttl=30").then(function (first) {
        return timedFetch("/api/lab/cache?key=" + key + "&ttl=30").then(function (second) {
          if (!first.response.ok) throw new Error("HTTP " + first.response.status);
          out.textContent = "";
          out.appendChild(badge("real", "Measured by your browser against this Worker · " + new Date().toISOString()));
          out.appendChild(kvList({
            "first call": first.response.headers.get("x-academy-cache") + " in " + first.ms + " ms",
            "second call": second.response.headers.get("x-academy-cache") + " in " + second.ms + " ms",
            "generated_at (both)": first.data.generated_at + " / " + second.data.generated_at,
          }));
        });
      });
    },
    burst: function (out) {
      var counts = { ok: 0, limited: 0, other: 0 };
      var i = 0;
      out.textContent = "Sending…";
      return new Promise(function (resolve, reject) {
        function next() {
          if (i >= 30) {
            out.textContent = "";
            out.appendChild(badge("real", "30 requests from your browser to /api/lab/echo · " + new Date().toISOString()));
            out.appendChild(kvList({ "2xx": counts.ok, "429 limited": counts.limited, other: counts.other }));
            if (!counts.ok && counts.other) reject(new Error("no successful answers"));
            else resolve();
            return;
          }
          i += 1;
          fetch("/api/lab/echo", { cache: "no-store" }).then(function (res) {
            if (res.status === 429) counts.limited += 1;
            else if (res.ok) counts.ok += 1;
            else counts.other += 1;
          }).catch(function () { counts.other += 1; }).then(function () { setTimeout(next, 50); });
        }
        next();
      });
    },
    telemetry: function (out) {
      return timedFetch("/api/telemetry").then(function (r) {
        if (!r.data) throw new Error("HTTP " + r.response.status);
        out.textContent = "";
        if (r.data.kind === "real") {
          out.appendChild(badge("real", r.data.source + " · " + r.data.collected_at));
          out.appendChild(el("pre", { text: JSON.stringify({ search_modes: r.data.search_modes, lab_requests: r.data.lab_requests }, null, 2) }));
        } else {
          out.appendChild(badge("simulated", "No live data: " + (r.data.missing || []).join(", ") + " not configured"));
          var ol = el("ol");
          (r.data.steps || [r.data.message]).forEach(function (s) { ol.appendChild(el("li", { text: s })); });
          out.appendChild(ol);
        }
      });
    }
  };

  function initLive(root) {
    var name = root.getAttribute("data-live");
    var run = root.querySelector("[data-live-run]");
    var out = root.querySelector("[data-live-out]");
    run.addEventListener("click", function () {
      run.disabled = true;
      var path = name === "telemetry" ? "/api/telemetry" : name === "cache" ? "/api/lab/cache" : "/api/lab/echo";
      var result;
      try { result = Promise.resolve(widgets[name](out, root)); } catch (e) { result = Promise.reject(e); }
      result.catch(function (error) { unavailable(out, path, error.message); }).then(function () { run.disabled = false; });
    });
  }

  function initCrawlers(figure) {
    var button = el("button", { type: "button", text: "Refresh live analytics" });
    var status = el("p", { role: "status", "aria-live": "polite" });
    var live = el("div");
    figure.insertAdjacentElement("afterend", live);
    live.appendChild(button);
    live.appendChild(status);
    function refresh() {
      button.disabled = true;
      status.textContent = "Loading live crawler analytics…";
      timedFetch("/api/crawler-analytics").then(function (r) {
        if (!r.response.ok || !r.data || r.data.kind !== "real") {
          throw new Error(r.data && r.data.message || "Live analytics unavailable. Showing the last available chart.");
        }
        var data = r.data;
        var content = el("div", { "data-crawler-result": "" });
        content.appendChild(badge("real", data.source + " · Updated " + data.collected_at));
        content.appendChild(el("p", { text: "Crawler requests · " + data.since + " to " + data.until }));
        content.appendChild(el("p", { text: data.description }));
        var table = el("table");
        var head = el("tr");
        ["Crawler", "llms.txt / catalog.*", "Part pages"].forEach(function (label) {
          head.appendChild(el("th", { scope: "col", text: label }));
        });
        table.appendChild(el("thead", {}, [head]));
        var body = el("tbody");
        var peak = Math.max.apply(null, data.rows.map(function (row) { return Math.max(row.llms, row.pages); }).concat([1]));
        data.rows.forEach(function (row) {
          var tr = el("tr", {}, [el("th", { scope: "row", text: row.label })]);
          ["llms", "pages"].forEach(function (key) {
            var cell = el("td", { text: row[key].toLocaleString() + " " });
            cell.appendChild(el("meter", { min: "0", max: String(peak), value: String(row[key]), "aria-label": row.label + " " + key, text: String(row[key]) }));
            tr.appendChild(cell);
          });
          body.appendChild(tr);
        });
        table.appendChild(body);
        content.appendChild(el("div", { cls: "table-wrap" }, [table]));
        var previous = live.querySelector("[data-crawler-result]");
        if (previous) previous.remove();
        live.appendChild(content);
        figure.hidden = true;
        status.textContent = "Live analytics loaded. Refreshes may use results cached for 60 seconds.";
      }).catch(function (error) {
        status.textContent = error.message + (figure.hidden ? " Last successful live results remain visible." : "");
      }).then(function () { button.disabled = false; });
    }
    button.addEventListener("click", refresh);
    refresh();
  }

  function init() {
    var toggle = document.querySelector("[data-nav-toggle]");
    var nav = document.getElementById("site-nav");
    if (toggle && nav) {
      toggle.addEventListener("click", function () {
        var open = nav.classList.toggle("open");
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
      });
    }
    document.querySelectorAll("[data-copy]").forEach(function (button) {
      button.addEventListener("click", function () {
        var code = button.closest("figure").querySelector("code");
        if (!navigator.clipboard) return;
        navigator.clipboard.writeText(code.textContent).then(function () {
          button.textContent = "Copied";
          setTimeout(function () { button.textContent = "Copy"; }, 1500);
        });
      });
    });
    document.querySelectorAll("[data-live]").forEach(initLive);
    document.querySelectorAll('[data-dataset="crawler-hits"]').forEach(initCrawlers);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
