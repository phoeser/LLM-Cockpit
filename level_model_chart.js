/* ============================================================
   ERGO LLM-Cockpit — Level-Modell-Grafik (GEO-Tab)
   Zeigt, WAS den Sichtbarkeits-Vorsprung erklaert:
   - Within-Effekt: bewegt mehr eigener Zitations-Footprint im
     Thema die Sichtbarkeit? (Marke gegen sich selbst, Themen-FE)
   - Between-Effekt: erklaert den Autoritaets-/Marken-Vorsprung.
   - Balken: Ø Sichtbarkeit je Marke (inkl. Marktfuehrer),
     aufgeteilt in den durch Footprint erklaerten Anteil und die
     uebrige Prominenz. Darunter je ein dynamisches Lesebeispiel.
   Quelle: data/correlation_impact.json (Feld level_model).
   Eigenstaendig, grounded/ungrounded-Umschalter, passt sich an.
   Einbindung: <script src="level_model_chart.js"></script>.
   ============================================================ */
(function () {
  "use strict";

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  function getModel() {
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

  function seg() { return mode === "g" ? lm.grounded : (mode === "u" ? lm.ungrounded : lm.combined); }

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

  function buildRows(m) {
    var ar = (m.authority_ranking || []).slice();
    if (!ar.length) return [];
    var bb = (m.between_effect && m.between_effect.coef_pp_sov_per_pp_citeshare) || 0;
    var baseX = Math.min.apply(null, ar.map(function (a) { return a.mean_cite_share_pct; }));
    var rows = ar.map(function (a) {
      var sov = a.mean_sov_pct || 0;
      var fp = bb * ((a.mean_cite_share_pct || 0) - baseX);
      if (fp < 0) fp = 0; if (fp > sov) fp = sov;
      return { brand: a.brand, sov: sov, cite: a.mean_cite_share_pct || 0, fp: fp, rest: sov - fp };
    });
    rows.sort(function (x, y) { return x.sov - y.sov; });
    return rows;
  }

  function renderChart(canvas) {
    var m = seg();
    if (!window.Chart) return;
    if (chart) { chart.destroy(); chart = null; }
    if (!m || !m.available) return;
    var lead = m.leader || "Marktführer";
    var rows = buildRows(m);
    if (!rows.length) return;
    var labels = rows.map(function (r) { return r.brand === lead ? r.brand + " (Marktführer)" : r.brand; });
    var fpData = rows.map(function (r) { return +r.fp.toFixed(2); });
    var restData = rows.map(function (r) { return +r.rest.toFixed(2); });
    var borders = rows.map(function (r) { return (r.brand === "ERGO" || r.brand === lead) ? "#1a1a2e" : "rgba(0,0,0,0)"; });

    chart = new window.Chart(canvas.getContext("2d"), {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          { label: "durch Footprint erklärt (modellbasiert)", data: fpData, backgroundColor: "#dc0028",
            borderColor: borders, borderWidth: 2, stack: "s" },
          { label: "übrige Prominenz", data: restData, backgroundColor: "#d9d7d2",
            borderColor: borders, borderWidth: 2, stack: "s" }
        ]
      },
      options: {
        indexAxis: "y", responsive: true, maintainAspectRatio: false, layout: { padding: 8 },
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 12 } } },
          tooltip: { callbacks: { afterBody: function (items) {
            var r = rows[items[0].dataIndex];
            var pct = r.sov > 0 ? Math.round(100 * r.fp / r.sov) : 0;
            return "Ø SoV " + r.sov.toFixed(1) + " % · Footprint Ø " + r.cite.toFixed(1) + " % · footprint-erklärt " + pct + " %";
          } } }
        },
        scales: {
          x: { stacked: true, beginAtZero: true, grid: { color: "#eee" },
               title: { display: true, text: "Ø Sichtbarkeit (Share of Voice, %)" },
               ticks: { callback: function (v) { return v + " %"; } } },
          y: { stacked: true, grid: { display: false } }
        }
      }
    });
  }

  function renderExample() {
    var box = document.getElementById("lmExample");
    if (!box) return;
    var m = seg();
    if (!m || !m.available || !m.authority_ranking) { box.innerHTML = ""; return; }
    var lead = m.leader;
    var ar = m.authority_ranking;
    var al = ar.filter(function (a) { return a.brand === lead; })[0];
    var er = ar.filter(function (a) { return a.brand === "ERGO"; })[0];
    if (!al || !er) { box.innerHTML = ""; return; }
    var gEr = (m.gap_decomposition || {})["ERGO"];
    var share = gEr && gEr.share_explained != null ? Math.round(gEr.share_explained * 100) : null;
    var modeLbl = mode === "g" ? "grounded (Web-Suche)" : (mode === "u" ? "ungrounded (Trainingswissen)" : "kombiniert (alle LLMs)");
    box.innerHTML =
      '<b>Lesebeispiel · ' + modeLbl + ':</b> ' + lead + ' ist mit Ø ' + al.mean_sov_pct.toFixed(0) +
      ' % Sichtbarkeit Marktführer — der rote Balkenanteil zeigt, dass der Großteil davon auf den hohen ' +
      'Zitations-Footprint (Ø ' + al.mean_cite_share_pct.toFixed(1) + ' % aller Quellen-Zitate im Thema) zurückgeht. ' +
      'ERGO erreicht Ø ' + er.mean_sov_pct.toFixed(0) + ' % bei nur Ø ' + er.mean_cite_share_pct.toFixed(1) + ' % Footprint' +
      (share != null ? ('; rund ' + share + ' % des Rückstands zu ' + lead + ' erklärt allein der geringere Footprint') : '') +
      '. Hebel für ERGO: eigene Quellpräsenz Richtung ' + al.mean_cite_share_pct.toFixed(0) + ' % ausbauen.';
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
        '<p style="font-size:13px;color:#6b7280;margin:2px 0 0">Zitations-Footprint als Treiber des SoV-<b>Niveaus</b>, zerlegt in Within (eigener Content bewegt Sichtbarkeit) und Between (Autoritäts-Vorsprung). Balken: Ø Sichtbarkeit je Marke (inkl. Marktführer), aufgeteilt in den durch Footprint erklärten Anteil und die übrige Prominenz.</p>' +
      '</div>' +
      '<div id="lmToggle" style="display:flex;gap:6px;margin-bottom:12px">' +
        '<button data-m="g" class="lm-btn" style="font-size:12px;padding:5px 12px;border-radius:8px;border:1px solid #dc0028;background:#dc0028;color:#fff;cursor:pointer">grounded (Web-Suche)</button>' +
        '<button data-m="u" class="lm-btn" style="font-size:12px;padding:5px 12px;border-radius:8px;border:1px solid #ccc;background:#fff;color:#282d37;cursor:pointer">ungrounded (Trainingswissen)</button>' +
        '<button data-m="c" class="lm-btn" style="font-size:12px;padding:5px 12px;border-radius:8px;border:1px solid #ccc;background:#fff;color:#282d37;cursor:pointer">beides (alle LLMs)</button>' +
      '</div>' +
      '<div id="lmStats" style="display:flex;flex-wrap:wrap;gap:16px;margin-bottom:14px"></div>' +
      '<div style="position:relative;width:100%;height:320px"><canvas id="lmCanvas"></canvas></div>' +
      '<p id="lmExample" style="font-size:12px;color:#374151;background:#f8f7f4;border-left:3px solid #dc0028;border-radius:4px;padding:9px 12px;margin:12px 0 0;line-height:1.5"></p>' +
      '<p id="lmNote" style="font-size:11px;color:#9ca3af;margin:10px 0 0"></p>';
    if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(card, anchor);
    else host.appendChild(card);

    var canvas = document.getElementById("lmCanvas");
    var note = document.getElementById("lmNote");
    if (note) note.textContent = (lm.note || "") + ((seg() && seg().exploratory) ? " Derzeit explorativ (wenige Themen)." : "");

    renderStats();
    renderChart(canvas);
    renderExample();

    card.querySelectorAll(".lm-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        mode = btn.getAttribute("data-m");
        card.querySelectorAll(".lm-btn").forEach(function (b) {
          var on = b.getAttribute("data-m") === mode;
          b.style.background = on ? "#dc0028" : "#fff"; b.style.color = on ? "#fff" : "#282d37"; b.style.borderColor = on ? "#dc0028" : "#ccc";
        });
        renderStats(); renderChart(canvas); renderExample();
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
