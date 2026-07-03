/* ============================================================
   ERGO LLM-Cockpit — Footprint-Grafik (GEO-Tab)
   Zeigt: Zitations-Footprint (wie oft die eigene Domain einer
   Marke in den von den LLMs zitierten Quellen auftaucht) gegen
   die Sichtbarkeit (SoV). Belegt den Kern-Treiber „Quellpraesenz".
   Eigenstaendig: nutzt die im Dashboard vorhandene globale
   GEO_SNAPSHOT (Fallback: data/geo_snapshot.json). Passt sich
   dynamisch an neue Themen/Daten an.
   Einbindung: <script src="footprint_chart.js"></script> vor </body>.
   ============================================================ */
(function () {
  "use strict";

  var BRAND_DOMAINS = {
    "ergo.de": "ERGO", "ergo.com": "ERGO", "ergodirekt.de": "ERGO",
    "allianz.de": "Allianz", "allianzdirect.de": "Allianz",
    "huk.de": "HUK-Coburg", "huk24.de": "HUK-Coburg", "huk-coburg.de": "HUK-Coburg",
    "axa.de": "AXA", "generali.de": "Generali",
    "signal-iduna.de": "Signal Iduna", "cosmosdirekt.de": "CosmosDirekt", "cosmos-direkt.de": "CosmosDirekt",
    "hannoversche.de": "Hannoversche", "ruv.de": "R+V", "devk.de": "DEVK"
  };
  var GROUNDED = { gemini: 1, perplexity: 1 };

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  function dom2brand(d) {
    d = String(d || "").replace(/^www\./, "");
    return BRAND_DOMAINS[d] || null;
  }

  function getSnapshot() {
    try { if (typeof GEO_SNAPSHOT !== "undefined" && GEO_SNAPSHOT && GEO_SNAPSHOT.products) return Promise.resolve(GEO_SNAPSHOT); } catch (e) {}
    if (window.GEO_SNAPSHOT && window.GEO_SNAPSHOT.products) return Promise.resolve(window.GEO_SNAPSHOT);
    return fetch("data/geo_snapshot.json?t=" + Date.now(), { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
  }

  function pearson(xs, ys) {
    var n = xs.length; if (n < 3) return null;
    var mx = 0, my = 0, i;
    for (i = 0; i < n; i++) { mx += xs[i]; my += ys[i]; }
    mx /= n; my /= n;
    var sxy = 0, sxx = 0, syy = 0;
    for (i = 0; i < n; i++) { sxy += (xs[i] - mx) * (ys[i] - my); sxx += (xs[i] - mx) * (xs[i] - mx); syy += (ys[i] - my) * (ys[i] - my); }
    if (sxx <= 0 || syy <= 0) return null;
    return sxy / Math.sqrt(sxx * syy);
  }

  // Aggregiert je Marke: Footprint (Zitate eigene Domain) + SoV (grounded/ungrounded)
  function aggregate(g) {
    var products = g.products || {};
    var llms = Array.isArray(g.llms) && g.llms.length ? g.llms : null;
    if (!llms) { llms = []; for (var p0 in products) { var s0 = products[p0].summary_by_llm || {}; for (var k in s0) if (llms.indexOf(k) < 0) llms.push(k); } }
    var grounded = llms.filter(function (l) { return GROUNDED[l]; });
    var ungrounded = llms.filter(function (l) { return !GROUNDED[l]; });

    var agg = {};
    function ensure(b) { if (!agg[b]) agg[b] = { cite: 0, gSum: 0, uSum: 0, n: 0 }; return agg[b]; }

    for (var pid in products) {
      var pd = products[pid];
      var cs = pd.cited_sources || {};
      var overall = cs.overall || [];
      // Footprint je Marke (eigene Domain) in diesem Produkt
      var cc = {};
      overall.forEach(function (row) { var b = dom2brand(row.domain); if (b) cc[b] = (cc[b] || 0) + (row.count || 0); });
      // SoV je Marke/Engine
      var sbl = pd.summary_by_llm || {};
      var sov = {};
      llms.forEach(function (eng) {
        (((sbl[eng] || {}).brands) || []).forEach(function (br) {
          sov[br.name] = sov[br.name] || {}; sov[br.name][eng] = br.share_of_voice || 0;
        });
      });
      var brands = {};
      Object.keys(sov).forEach(function (b) { brands[b] = 1; });
      Object.keys(cc).forEach(function (b) { brands[b] = 1; });
      Object.keys(brands).forEach(function (b) {
        var s = sov[b] || {};
        var gVals = grounded.map(function (e) { return s[e] || 0; });
        var uVals = ungrounded.map(function (e) { return s[e] || 0; });
        var gAvg = gVals.length ? gVals.reduce(function (a, c) { return a + c; }, 0) / gVals.length : 0;
        var uAvg = uVals.length ? uVals.reduce(function (a, c) { return a + c; }, 0) / uVals.length : 0;
        var a = ensure(b);
        a.cite += (cc[b] || 0); a.gSum += gAvg; a.uSum += uAvg; a.n += 1;
      });
    }
    var rows = Object.keys(agg).map(function (b) {
      var a = agg[b];
      return { brand: b, cite: a.cite, g: a.n ? 100 * a.gSum / a.n : 0, u: a.n ? 100 * a.uSum / a.n : 0 };
    }).sort(function (x, y) { return y.cite - x.cite; });
    return { rows: rows, hasGrounded: grounded.length > 0, hasUngrounded: ungrounded.length > 0, grounded: grounded, ungrounded: ungrounded };
  }

  var chart = null, mode = "g", agg = null;

  function render(canvas) {
    if (!window.Chart || !agg) return;
    var rows = agg.rows;
    var pts = rows.map(function (r) { return { x: r.cite, y: +(mode === "g" ? r.g : r.u).toFixed(1), label: r.brand }; });
    var colors = pts.map(function (p) { return p.label === "ERGO" ? "#2a78d6" : "#888781"; });
    var xs = pts.map(function (p) { return p.x; }), ys = pts.map(function (p) { return p.y; });
    var r = pearson(xs, ys);
    var rEl = document.getElementById("fpR"); if (rEl) rEl.textContent = (r === null ? "—" : (Math.round(r * 100) / 100).toFixed(2));
    // Trendlinie
    var line = [];
    if (xs.length >= 2) {
      var n = xs.length, mx = xs.reduce(function (a, c) { return a + c; }, 0) / n, my = ys.reduce(function (a, c) { return a + c; }, 0) / n;
      var sxy = 0, sxx = 0; for (var i = 0; i < n; i++) { sxy += (xs[i] - mx) * (ys[i] - my); sxx += (xs[i] - mx) * (xs[i] - mx); }
      var b = sxx ? sxy / sxx : 0, a0 = my - b * mx, xmax = Math.max.apply(null, xs) * 1.05 + 1;
      line = [{ x: 0, y: a0 }, { x: xmax, y: a0 + b * xmax }];
    }
    var labelPlugin = {
      id: "fpLab", afterDatasetsDraw: function (c) {
        var ctx = c.ctx; ctx.save(); ctx.font = "12px -apple-system,sans-serif"; ctx.fillStyle = "#52514e";
        var m = c.getDatasetMeta(0);
        pts.forEach(function (p, i) { var el = m.data[i]; if (!el) return; var dx = (p.label === "Allianz" || p.label === "HUK-Coburg") ? -8 : 9; ctx.textAlign = dx < 0 ? "right" : "left"; ctx.fillText(p.label, el.x + dx, el.y + 4); });
        ctx.restore();
      }
    };
    if (chart) chart.destroy();
    chart = new window.Chart(canvas.getContext("2d"), {
      data: {
        datasets: [
          { type: "scatter", data: pts, pointBackgroundColor: colors, pointBorderColor: colors, pointRadius: 7, pointHoverRadius: 9, order: 2 },
          { type: "line", data: line, borderColor: "#b4b2a9", borderWidth: 1.5, borderDash: [5, 4], pointRadius: 0, fill: false, order: 1 }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false, layout: { padding: 14 },
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: function (c) { return c.raw.label ? c.raw.label + ": Footprint " + c.raw.x + ", SoV " + c.raw.y + "%" : ""; } } } },
        scales: {
          x: { title: { display: true, text: "Zitations-Footprint (Nennungen der eigenen Domain in LLM-Quellen)" }, grid: { color: "#eee" }, beginAtZero: true },
          y: { title: { display: true, text: "Sichtbarkeit " + (mode === "g" ? "grounded (Web-Suche)" : "ungrounded (Trainingswissen)") + " – SoV %" }, grid: { color: "#eee" }, beginAtZero: true, ticks: { callback: function (v) { return v + "%"; } } }
        }
      },
      plugins: [labelPlugin]
    });
  }

  function build(g) {
    agg = aggregate(g);
    if (!agg.rows.length) return;
    var host = document.querySelector('section[data-content="geo"]') || document.body;
    if (document.getElementById("fpCard")) return;
    var anchor = document.getElementById("geoProductCards") || document.getElementById("geoRankingTable");
    var card = document.createElement("div");
    card.id = "fpCard";
    card.className = "bg-white rounded-xl shadow p-6 mb-6";
    card.innerHTML =
      '<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;margin-bottom:8px">' +
        '<div><h3 style="font-size:16px;font-weight:600;margin:0">Quellpräsenz treibt Sichtbarkeit</h3>' +
        '<p style="font-size:13px;color:#6b7280;margin:2px 0 0">Zitations-Footprint (eigene Domain in den von LLMs zitierten Quellen) vs. Share of Voice, je Marke.</p></div>' +
        '<div style="text-align:right;font-size:13px;color:#6b7280">Korrelation r<br><span id="fpR" style="font-size:22px;font-weight:700;color:#1a1a2e">—</span></div>' +
      '</div>' +
      '<div id="fpToggle" style="display:flex;gap:6px;margin-bottom:10px">' +
        '<button data-m="g" class="fp-btn" style="font-size:12px;padding:5px 12px;border-radius:8px;border:1px solid #dc0028;background:#dc0028;color:#fff;cursor:pointer">grounded (Web-Suche)</button>' +
        '<button data-m="u" class="fp-btn" style="font-size:12px;padding:5px 12px;border-radius:8px;border:1px solid #ccc;background:#fff;color:#282d37;cursor:pointer">ungrounded (Trainingswissen)</button>' +
      '</div>' +
      '<div style="position:relative;width:100%;height:360px"><canvas id="fpCanvas"></canvas></div>';
    if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(card, anchor);
    else host.appendChild(card);

    var canvas = document.getElementById("fpCanvas");
    render(canvas);

    // Toggle grounded/ungrounded
    card.querySelectorAll(".fp-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        mode = btn.getAttribute("data-m");
        card.querySelectorAll(".fp-btn").forEach(function (b) {
          var on = b.getAttribute("data-m") === mode;
          b.style.background = on ? "#dc0028" : "#fff"; b.style.color = on ? "#fff" : "#282d37"; b.style.borderColor = on ? "#dc0028" : "#ccc";
        });
        render(canvas);
      });
    });

    // Neu zeichnen, wenn der GEO-Tab sichtbar wird (Groessen-Fix bei versteckten Tabs)
    var tabBtn = document.querySelector('[data-tab="geo"]');
    if (tabBtn) tabBtn.addEventListener("click", function () { setTimeout(function () { if (chart) chart.resize(); else render(canvas); }, 60); });
  }

  ready(function () {
    // kleine Verzoegerung, damit GEO_SNAPSHOT/Chart.js sicher da sind
    var tries = 0;
    (function wait() {
      tries++;
      getSnapshot().then(function (g) {
        if (g && g.products && window.Chart) { build(g); }
        else if (tries < 20) setTimeout(wait, 300);
      });
    })();
  });
})();
