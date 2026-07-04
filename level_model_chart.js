/* ============================================================
   ERGO LLM-Cockpit — Level-Modell-Grafik (GEO-Tab)
   Zeigt, WAS den Sichtbarkeits-Vorsprung erklaert:
   - Within-Effekt: bewegt mehr eigener Zitations-Footprint im
     Thema die Sichtbarkeit? (Marke gegen sich selbst, Themen-FE)
   - Between-Effekt: erklaert den Autoritaets-/Marken-Vorsprung
     (warum Allianz sichtbarer ist) statt ihn zu verstecken.
   - Balken: Anteil des SoV-Abstands zum Marktfuehrer, der durch
     Footprint erklaert ist, je Wettbewerber.
   Quelle: data/correlation_impact.json (Feld level_model).
   Eigenstaendig, passt sich dynamisch an. Grounded/Ungrounded-Umschalter.
   Einbindung: <script src="level_model_chart.js"></script>.
   ============================================================ */
(function () {
  "use strict";

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  function getModel() {
    // 1) evtl. schon global vorhanden
    try { if (typeof CORRELATION_IMPACT !== "undefined" && CORRELATION_IMPACT && CORRELATION_IMPACT.level_model) return Promise.resolve(CORRELATION_IMPACT.level_model); } catch (e) {}
    if (window.CORRELATION_IMPACT && window.CORRELATION_IMPACT.level_model) return Promise.resolve(window.CORRELATION_IMPACT.level_model);
    return fetch("data/correlation_impact.json?t=" + Date.now(), { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { return j ? j.level_model : null; })
      .catch(function () { return null; });
  }

  var lm = null, mode = "g", chart = null;

  function fmtSigned(v) { return (v > 0 ? "+" : "") + (Math.round(v * 100) / 100).toFixed(2); }

  function badge(sig) {
    return sig
      ? '<span style="font-size:10px;font-weight:700;color:#067d3a;background:#e6f5ec;border-radius:4px;padding:1px 6px">gesichert</span>'
      : '<span style="font-size:10px;font-weight:700;color:#8a6d00;background:#fdf3d7;border-radius:4px;padding:1px 6px">explorativ</span>';
  }

  function seg() { return mode === "g" ? lm.grounded : lm.ungrounded; }

  function renderStats() {
    var m = seg();
    var box = document.getElementById("lmStats");
    if (!box) return;
    if (!m || !m.available) { box.innerHTML = '<div style="font-size:13px;color:#6b7280">Für diese Auswahl noch zu wenige Daten.</div>'; return; }
    var w = m.within_effect, b = m.between_effect;
    function stat(label, coef, sig, tip) {
      return '<div style="flex:1;min-width:150px">' +
        '<div style="font-size:12px;color:#6b7280">' + label + ' ' + badge(sig) + '</div>' +
        '<div style="font-size:22px;font-weight:700;color:#1a1a2e">' + fmtSigned(coef) + ' <span style="font-size:12px;font-weight:500;color:#9ca3af">Pp/Pp</span></div>' +
        '<div style="font-size:11px;color:#9ca3af">' + tip + '</div></div>';
    }
    var r2 = (m.r2_within_topics == null ? "—" : Math.round(m.r2_within_topics * 100) + "%");
    var rr = (m.raw_pearson_r == null ? "—" : (Math.round(m.raw_pearson_r * 100) / 100).toFixed(2));
    box.innerHTML =
      stat("Within-Effekt", w.coef_pp_sov_per_pp_citeshare, w.significant, "eigener Content im Thema") +
      stat("Between-Effekt", b.coef_pp_sov_per_pp_citeshare, b.significant, "Autoritäts-Vorsprung (Marken-Mittel)") +
      '<div style="flex:1;min-width:150px">' +
        '<div style="font-size:12px;color:#6b7280">Modellgüte</div>' +
        '<div style="font-size:22px;font-weight:700;color:#1a1a2e">R² ' + r2 + '</div>' +
        '<div style="font-size:11px;color:#9ca3af">roher Zusammenhang r = ' + rr + '</div></div>';
  }

  function renderChart(canvas) {
    var m = seg();
    if (!window.Chart) return;
    if (chart) { chart.destroy(); chart = null; }
    if (!m || !m.available || !m.gap_decomposition) return;
    var lead = m.leader || "Marktführer";
    var rows = [];
    Object.keys(m.gap_decomposition).forEach(function (b) {
      var g = m.gap_decomposition[b];
      var actual = g.actual_gap_pp || 0;
      if (actual <= 0) return;
      var expl = g.explained_by_footprint_pp || 0;
      if (expl < 0) expl = 0; if (expl > actual) expl = actual;
      rows.push({ brand: b, expl: expl, rest: actual - expl, actual: actual, share: g.share_explained });
    });
    rows.sort(function (a, b) { return a.actual - b.actual; }); // kleinster Abstand oben
    var labels = rows.map(function (r) { return r.brand; });
    var explData = rows.map(function (r) { return +r.expl.toFixed(2); });
    var restData = rows.map(function (r) { return +r.rest.toFixed(2); });
    var borders = rows.map(function (r) { return r.brand === "ERGO" ? "#1a1a2e" : "rgba(0,0,0,0)"; });

    chart = new window.Chart(canvas.getContext("2d"), {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          { label: "durch Footprint erklärt", data: explData, backgroundColor: "#dc0028",
            borderColor: borders, borderWidth: 2, stack: "s" },
          { label: "übrige Autorität / Prominenz", data: restData, backgroundColor: "#d9d7d2",
            borderColor: borders, borderWidth: 2, stack: "s" }
        ]
      },
      options: {
        indexAxis: "y", responsive: true, maintainAspectRatio: false, layout: { padding: 8 },
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 12 } } },
          tooltip: { callbacks: { afterBody: function (items) {
            var r = rows[items[0].dataIndex];
            var pct = (r.share == null ? "—" : Math.round(r.share * 100) + "%");
            return "Abstand gesamt: " + r.actual.toFixed(1) + " Pp · Footprint erklärt " + pct;
          } } }
        },
        scales: {
          x: { stacked: true, beginAtZero: true, grid: { color: "#eee" },
               title: { display: true, text: "SoV-Abstand zu " + lead + " (Prozentpunkte)" },
               ticks: { callback: function (v) { return v + " Pp"; } } },
          y: { stacked: true, grid: { display: false } }
        }
      }
    });
  }

  function build() {
    var host = document.querySelector('section[data-content="geo"]');
    if (!host) return;
    if (document.getElementById("lmCard")) return;
    if (!lm || !lm.available) return;
    var anchor = document.getElementById("geoProductCards") || document.getElementById("geoRankingTable");
    var card = document.createElement("div");
    card.id = "lmCard";
    card.className = "bg-white rounded-xl shadow p-6 mb-6";
    card.innerHTML =
      '<div style="margin-bottom:8px">' +
        '<h3 style="font-size:16px;font-weight:600;margin:0">Was den Sichtbarkeits-Vorsprung erklärt (Level-Modell)</h3>' +
        '<p style="font-size:13px;color:#6b7280;margin:2px 0 0">Zitations-Footprint als Treiber des SoV-<b>Niveaus</b>, zerlegt in Within (eigener Content bewegt Sichtbarkeit) und Between (Autoritäts-Vorsprung). Balken: Anteil des Abstands zum Marktführer, der durch Footprint erklärt ist.</p>' +
      '</div>' +
      '<div id="lmToggle" style="display:flex;gap:6px;margin-bottom:12px">' +
        '<button data-m="g" class="lm-btn" style="font-size:12px;padding:5px 12px;border-radius:8px;border:1px solid #dc0028;background:#dc0028;color:#fff;cursor:pointer">grounded (Web-Suche)</button>' +
        '<button data-m="u" class="lm-btn" style="font-size:12px;padding:5px 12px;border-radius:8px;border:1px solid #ccc;background:#fff;color:#282d37;cursor:pointer">ungrounded (Trainingswissen)</button>' +
      '</div>' +
      '<div id="lmStats" style="display:flex;flex-wrap:wrap;gap:16px;margin-bottom:14px"></div>' +
      '<div style="position:relative;width:100%;height:300px"><canvas id="lmCanvas"></canvas></div>' +
      '<p id="lmNote" style="font-size:11px;color:#9ca3af;margin:10px 0 0"></p>';
    if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(card, anchor);
    else host.appendChild(card);

    var canvas = document.getElementById("lmCanvas");
    var note = document.getElementById("lmNote");
    if (note) note.textContent = (lm.note || "") + ((seg() && seg().exploratory) ? " Derzeit explorativ (wenige Themen)." : "");

    renderStats();
    renderChart(canvas);

    card.querySelectorAll(".lm-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        mode = btn.getAttribute("data-m");
        card.querySelectorAll(".lm-btn").forEach(function (b) {
          var on = b.getAttribute("data-m") === mode;
          b.style.background = on ? "#dc0028" : "#fff"; b.style.color = on ? "#fff" : "#282d37"; b.style.borderColor = on ? "#dc0028" : "#ccc";
        });
        renderStats(); renderChart(canvas);
      });
    });

    var tabBtn = document.querySelector('[data-tab="geo"]');
    if (tabBtn) tabBtn.addEventListener("click", function () { setTimeout(function () { if (chart) chart.resize(); else renderChart(canvas); }, 60); });
  }

  ready(function () {
    var tries = 0;
    (function wait() {
      tries++;
      getModel().then(function (model) {
        if (model && model.available && window.Chart && document.querySelector('section[data-content="geo"]')) { lm = model; build(); }
        else if (tries < 25) setTimeout(wait, 300);
      });
    })();
  });
})();
