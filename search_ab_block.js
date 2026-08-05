/* ============================================================
   ERGO LLM-Cockpit — Websuche-A/B (Korrelations-Tab, Frage 2)
   Der erste kausal belegte Befund des Projekts: dieselben Fragen
   einmal MIT erzwungener Websuche und einmal OHNE Werkzeuge,
   gepaart ueber die Prompts. Das ist ein kontrolliertes
   Experiment — im Unterschied zum Rest dieses Reiters, der
   Beobachtungsdaten auswertet.

   Bloecke:
     1. Kopf: was hier anders ist (Experiment statt Beobachtung)
     2. Kernzahl gross: mit Suche vs. ohne, Differenz + KI + p
     3. Weitere Kennzahlen (kompakte Tabelle)
     4. Forest je Produkt (Punktschaetzer + 95-%-KI, Nulllinie)
     5. Gegenproben + Vorbehalte offen sichtbar, nicht versteckt

   Quelle: data/search_ab.json (Runtime-fetch, erzeugt von
   scripts/fetch_search_ab.py aus dem GEO-Repo). Fehlt die Datei
   oder steht available:false darin, erscheint ein Hinweis MIT
   Grund — NIE Ersatzzahlen.
   Keine externen Abhaengigkeiten, Grafik als Inline-SVG.
   Einbindung: <script src="search_ab_block.js"></script>
   Haengt sich in #korrErgebnis unter Block 2 ("Bewegen einzelne
   Ereignisse sie kurzfristig?") ein; faellt zurueck auf das Ende
   des Panels bzw. auf die Sektion [data-content="korrelation"].
   Der Forest nutzt die Forest-Funktion des Reiters, wenn sie
   global erreichbar ist (window.__korrForest / window.forestPlot),
   sonst die eigene, formgleiche Variante weiter unten.
   ============================================================ */
(function () {
  "use strict";

  var BOX_ID = "searchAbBox";
  var COL = {
    a: "#DC0028", b: "#9ca3af", sig: "#DC0028", pos: "#0f766e",
    neg: "#7c3aed", text: "#282d37", grau: "#6b7280", null_: "#475569"
  };

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function de(v, n) {
    if (v == null || isNaN(v)) return null;
    return Number(v).toFixed(n == null ? 1 : n).replace(".", ",");
  }
  /* Anteil (0..1) als Prozent */
  function pct(v, n) {
    var s = de(v == null ? null : v * 100, n);
    return s == null ? "keine Angabe" : s + " %";
  }
  /* Anteil (0..1) als Prozentpunkte mit Vorzeichen */
  function pp(v, n) {
    var s = de(v == null ? null : v * 100, n);
    if (s == null) return "keine Angabe";
    return (v > 0 ? "+" : "") + s + " pp";
  }
  function zahl(v, n) {
    var s = de(v, n == null ? 2 : n);
    return s == null ? "keine Angabe" : s;
  }
  function sgnZahl(v, n) {
    var s = de(v, n == null ? 2 : n);
    if (s == null) return "keine Angabe";
    return (v > 0 ? "+" : "") + s;
  }
  function pWert(p) {
    if (p == null || isNaN(p)) return "keine Angabe";
    // Exakter Wert, solange die Aufloesung des Permutationstests ihn hergibt
    if (p > 0 && p < 0.0001) return "p < 0,0001";
    return "p = " + de(p, p < 0.01 ? 4 : 3);
  }
  function datum(s) {
    var m = String(s || "").match(/(\d{4})-(\d{2})-(\d{2})/);
    return m ? (m[3] + "." + m[2] + "." + m[1]) : null;
  }
  /* Wert einer Kennzahl je nach Einheit formatieren */
  function val(m, key) {
    var v = m[key];
    if (v == null || isNaN(v)) return "keine Angabe";
    if (m.einheit === "anteil") return (key === "diff" || key === "ci_low" || key === "ci_high") ? pp(v) : pct(v);
    if (m.einheit === "rang") return (key === "diff" || key === "ci_low" || key === "ci_high") ? sgnZahl(v) : zahl(v);
    return (key === "diff" || key === "ci_low" || key === "ci_high") ? sgnZahl(v) : zahl(v);
  }

  /* ---------- Forest: fremde Funktion bevorzugen ---------------------------
     Der Korrelations-Reiter hat in dashboard_v3.html bereits einen Forest
     (Punkt + 95-%-Band + gestrichelte Nulllinie). Er liegt in einer IIFE und
     ist derzeit nicht global; sobald er als window.__korrForest exportiert
     ist, wird er hier automatisch benutzt. Bis dahin zeichnet forestLocal()
     dieselbe Form mit denselben Farben. ---------------------------------- */
  function forestFn() {
    if (typeof window.__korrForest === "function") return window.__korrForest;
    if (typeof window.forestPlot === "function") return window.forestPlot;
    return null;
  }
  function niceTicks(lo, hi, n) {
    var span = (hi - lo) || 1, raw = span / (n || 5);
    var mag = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10));
    var step = [1, 2, 2.5, 5, 10].map(function (f) { return f * mag; })
      .filter(function (s) { return s >= raw; })[0] || mag * 10;
    var out = [], t = Math.ceil(lo / step) * step;
    for (; t <= hi + 1e-9 && out.length < 12; t += step) out.push(Math.round(t * 1000) / 1000);
    return out;
  }
  function forestLocal(rows, opts) {
    opts = opts || {};
    rows = rows || [];
    var plot = rows.filter(function (r) { return r.eff != null; });
    var dead = rows.filter(function (r) { return r.eff == null; });
    var deadHtml = dead.length ? ('<div style="border-top:1px solid #eee;margin-top:8px;padding-top:8px">'
      + '<div style="font-size:11.5px;font-weight:600;color:#4b5563;margin-bottom:3px">Nicht schätzbar — bleibt sichtbar, statt zu verschwinden</div>'
      + dead.map(function (r) {
        return '<div style="font-size:11px;color:#6b7280;line-height:1.5">' + esc(r.label)
          + ' — <span style="color:#b45309">kein Effekt schätzbar</span>'
          + (r.note ? (": " + esc(r.note)) : "") + "</div>";
      }).join("") + "</div>") : "";
    if (!plot.length) return deadHtml || '<div style="font-size:12px;color:#9ca3af;padding:10px 0">Keine schätzbaren Effekte.</div>';

    var W = 760, LBL = 236, PADL = 12, PADR = 96, RH = 32, TOP = 34;
    var lo = Math.min.apply(null, plot.map(function (r) { return r.lo != null ? r.lo : r.eff; }));
    var hi = Math.max.apply(null, plot.map(function (r) { return r.hi != null ? r.hi : r.eff; }));
    var span = Math.max(hi - lo, 0.001), m = span * 0.10;
    lo -= m; hi += m;
    if (lo > 0) lo = -span * 0.06;
    if (hi < 0) hi = span * 0.06;
    var PW = W - LBL - PADL - PADR;
    var x = function (v) { return LBL + PADL + ((v - lo) / (hi - lo)) * PW; };
    var H = TOP + plot.length * RH + 34;
    var s = '<svg viewBox="0 0 ' + W + " " + H + '" style="width:100%;height:auto;font-family:inherit" role="img">';
    niceTicks(lo, hi, 5).forEach(function (t) {
      s += '<line x1="' + x(t).toFixed(1) + '" y1="' + (TOP - 14) + '" x2="' + x(t).toFixed(1)
        + '" y2="' + (TOP + plot.length * RH - 12) + '" stroke="#f1f5f9" stroke-width="1"/>';
      s += '<text x="' + x(t).toFixed(1) + '" y="' + (TOP - 20) + '" text-anchor="middle" font-size="10" fill="#94a3b8">'
        + (t > 0 ? "+" : "") + String(t).replace(".", ",") + "</text>";
    });
    plot.forEach(function (r, i) {
      if (i % 2) s += '<rect x="0" y="' + (TOP + i * RH - RH / 2 + 3) + '" width="' + W + '" height="' + (RH - 2) + '" fill="#fafafa"/>';
    });
    s += '<line x1="' + x(0).toFixed(1) + '" y1="' + (TOP - 14) + '" x2="' + x(0).toFixed(1)
      + '" y2="' + (TOP + plot.length * RH - 12) + '" stroke="' + COL.null_ + '" stroke-width="1.5" stroke-dasharray="5 3"/>';
    plot.forEach(function (r, i) {
      var y = TOP + i * RH;
      var col = r.sig ? COL.sig : (r.eff > 0 ? COL.pos : COL.neg);
      s += '<text x="' + (LBL - 8) + '" y="' + (y + 1) + '" text-anchor="end" font-size="12.5" fill="' + COL.text + '">' + esc(r.label) + "</text>";
      if (r.sub) s += '<text x="' + (LBL - 8) + '" y="' + (y + 12) + '" text-anchor="end" font-size="9.5" fill="#94a3b8">' + esc(r.sub) + "</text>";
      if (r.lo != null && r.hi != null) {
        s += '<line x1="' + x(r.lo).toFixed(1) + '" y1="' + y + '" x2="' + x(r.hi).toFixed(1) + '" y2="' + y
          + '" stroke="' + col + '" stroke-width="2.5" opacity="0.4" stroke-linecap="round"/>';
        [r.lo, r.hi].forEach(function (v) {
          s += '<line x1="' + x(v).toFixed(1) + '" y1="' + (y - 5) + '" x2="' + x(v).toFixed(1) + '" y2="' + (y + 5)
            + '" stroke="' + col + '" stroke-width="2" opacity="0.65"/>';
        });
      } else {
        s += '<text x="' + (x(r.eff) + 9).toFixed(1) + '" y="' + (y + 4) + '" font-size="9.5" fill="#b45309">kein Konfidenzintervall verfügbar</text>';
      }
      s += '<circle cx="' + x(r.eff).toFixed(1) + '" cy="' + y + '" r="5" fill="' + col + '" stroke="#fff" stroke-width="1.5"/>';
      s += '<text x="' + (W - 6) + '" y="' + (y + 4) + '" text-anchor="end" font-size="11" fill="#475569">' + esc(r.valLabel || "") + "</text>";
      s += "<title>" + esc(r.label) + ": " + esc(r.valLabel || "")
        + (r.lo != null && r.hi != null ? (", 95-%-Intervall [" + esc(r.ciLabel || "") + "]") : ", kein Konfidenzintervall verfügbar")
        + (r.n != null ? (", " + r.n + " Prompt-Paare") : "") + "</title>";
    });
    s += '<text x="' + (LBL + PADL + PW / 2) + '" y="' + (H - 6) + '" text-anchor="middle" font-size="10.5" fill="#94a3b8">'
      + esc(opts.xlabel || "") + "</text>";
    return s + "</svg>" + deadHtml;
  }

  /* ---------- Bausteine ---------- */
  function armTile(label, wert, sub, farbe) {
    return '<div style="flex:1;min-width:132px;background:#f6f7f9;border-radius:9px;padding:10px 13px">'
      + '<div style="font-size:10.5px;color:#6b7280;line-height:1.3">' + esc(label) + "</div>"
      + '<div style="font-size:27px;font-weight:800;color:' + (farbe || COL.text) + ';line-height:1.15;margin-top:2px">' + esc(wert) + "</div>"
      + (sub ? '<div style="font-size:10.5px;color:#8a8f98;margin-top:2px;line-height:1.4">' + esc(sub) + "</div>" : "")
      + "</div>";
  }

  function kernBlock(d) {
    var lead = null, i;
    for (i = 0; i < (d.kennzahlen || []).length; i++) {
      if (d.kennzahlen[i].leitkennzahl) { lead = d.kennzahlen[i]; break; }
    }
    if (!lead) lead = (d.kennzahlen || [])[0];
    if (!lead) return '<div style="font-size:12px;color:#9ca3af">Keine Kennzahlen in data/search_ab.json.</div>';
    var ci = "[" + val(lead, "ci_low") + "; " + val(lead, "ci_high") + "]";
    var arme = d.arme || {}, a = arme.a || {}, b = arme.b || {};
    return '<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:stretch">'
      + armTile("ERGO-SoV " + (a.label || "mit Suche"), val(lead, "arm_a"), a.definition || null, COL.a)
      + armTile("ERGO-SoV " + (b.label || "ohne Suche"), val(lead, "arm_b"), b.definition || null, COL.b)
      + '<div style="flex:1.5;min-width:230px;background:#fff5f6;border:1px solid #f6cdd4;border-radius:9px;padding:10px 13px">'
      + '<div style="font-size:10.5px;color:#6b7280;line-height:1.3">Differenz (gepaart über dieselben Prompts)</div>'
      + '<div style="font-size:27px;font-weight:800;color:' + COL.a + ';line-height:1.15;margin-top:2px">' + val(lead, "diff") + "</div>"
      + '<div style="font-size:11px;color:#6b5b28;margin-top:3px;line-height:1.45">95-%-Intervall ' + esc(ci)
      + " · " + esc(pWert(d.permutation_p)) + "</div></div></div>"
      + '<div style="font-size:11px;color:#8a8f98;margin-top:6px;line-height:1.55">'
      + esc(lead.label) + " · " + (lead.n != null ? (lead.n + " Prompt-Paare") : "Paarzahl: keine Angabe")
      + (d.permutation_p_hinweis ? (" · " + esc(d.permutation_p_hinweis)) : "")
      + "</div>";
  }

  function kennzahlenTabelle(d) {
    var rows = (d.kennzahlen || []).filter(function (m) { return !m.leitkennzahl; });
    if (!rows.length) return "";
    var h = '<div style="margin-top:12px;overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:11.5px">'
      + '<thead><tr style="color:#6b7280;text-align:left">'
      + '<th style="padding:4px 8px 4px 0;font-weight:600">Weitere Kennzahlen</th>'
      + '<th style="padding:4px 8px;text-align:right;font-weight:600">mit Suche</th>'
      + '<th style="padding:4px 8px;text-align:right;font-weight:600">ohne Suche</th>'
      + '<th style="padding:4px 8px;text-align:right;font-weight:600">Differenz [95-%-Intervall]</th>'
      + '<th style="padding:4px 0 4px 8px;font-weight:600">Intervall ohne Null</th></tr></thead><tbody>';
    rows.forEach(function (m) {
      var ok = m.ci_excludes_zero === true;
      h += '<tr style="border-top:1px solid #f1f2f4">'
        + '<td style="padding:5px 8px 5px 0;color:' + COL.text + '">' + esc(m.label)
        + (m.key === "cited" ? ' <span title="siehe Vorbehalte" style="color:#b45309">⚠</span>' : "")
        + (m.n != null ? (' <span style="color:#b9bec6">n ' + m.n + "</span>") : "") + "</td>"
        + '<td style="padding:5px 8px;text-align:right">' + esc(val(m, "arm_a")) + "</td>"
        + '<td style="padding:5px 8px;text-align:right">' + esc(val(m, "arm_b")) + "</td>"
        + '<td style="padding:5px 8px;text-align:right;font-weight:600">' + esc(val(m, "diff"))
        + ' <span style="font-weight:400;color:#8a8f98">[' + esc(val(m, "ci_low")) + "; " + esc(val(m, "ci_high")) + "]</span></td>"
        + '<td style="padding:5px 0 5px 8px;color:' + (ok ? "#067d3a" : "#8a8f98") + '">'
        + (m.ci_excludes_zero == null ? "keine Angabe" : (ok ? "ja" : "nein")) + "</td></tr>";
    });
    return h + "</tbody></table></div>";
  }

  function forestBlock(d) {
    var rows = (d.je_produkt || []).map(function (p) {
      var hatDiff = p.diff != null && !isNaN(p.diff);
      return {
        label: p.name || p.product_id,
        sub: (p.n_pairs != null ? (p.n_pairs + " Paare") : "Paarzahl: keine Angabe")
          + (hatDiff ? (" · " + pct(p.arm_a) + " vs. " + pct(p.arm_b)) : ""),
        // Der geteilte Forest des Reiters rechnet in Prozentpunkten
        eff: hatDiff ? p.diff * 100 : null,
        lo: p.ci_low != null ? p.ci_low * 100 : null,
        hi: p.ci_high != null ? p.ci_high * 100 : null,
        sig: p.ci_excludes_zero === true,
        n: p.n_pairs,
        valLabel: pp(p.diff),
        ciLabel: pp(p.ci_low) + "; " + pp(p.ci_high),
        note: hatDiff ? null : (p.hinweis || "im Datensatz kein Schätzwert für dieses Produkt")
      };
    });
    if (!rows.length) {
      return '<div style="font-size:11.5px;color:#9ca3af;margin-top:12px">Keine Je-Produkt-Zeilen in data/search_ab.json — es werden bewusst keine Ersatzwerte gezeigt.</div>';
    }
    var xlabel = "Wirkung der Websuche auf den ERGO-Anteil (Prozentpunkte) — Punkt = Schätzer, Balken = 95-%-Intervall, gestrichelt = kein Unterschied";
    var fn = forestFn();
    var svg;
    try {
      svg = fn ? fn(rows, { xlabel: xlabel }) : forestLocal(rows, { xlabel: xlabel });
    } catch (e) {
      svg = forestLocal(rows, { xlabel: xlabel });
    }
    return '<div style="margin-top:16px">'
      + '<div style="font-size:13px;font-weight:700;color:' + COL.text + ';margin-bottom:2px">Je Produkt: wo die Suche etwas ändert</div>'
      + '<div style="font-size:11px;color:#6b7280;margin-bottom:6px;line-height:1.55">'
      + 'Rot = Intervall ohne die Null. ' + esc(d.je_produkt_hinweis || "") + "</div>"
      + svg + "</div>";
  }

  function gegenprobenBlock(d) {
    var g = d.gegenproben || {};
    var teile = [];
    if (g.arm_a_ohne_quellen != null) {
      teile.push("<b>Arm A ohne jede ausgewiesene Quelle:</b> " + g.arm_a_ohne_quellen
        + (g.arm_a_ok != null ? (" von " + g.arm_a_ok) : "")
        + (g.arm_a_ohne_quellen_rate != null ? (" (" + pct(g.arm_a_ohne_quellen_rate, 2) + ")") : ""));
    }
    if (g.arm_b_mit_fliesstext_urls != null) {
      teile.push("<b>Arm B mit selbst genannten URLs im Fließtext:</b> " + g.arm_b_mit_fliesstext_urls
        + (g.arm_b_ok != null ? (" von " + g.arm_b_ok) : "")
        + (g.arm_b_mit_fliesstext_urls_rate != null ? (" (" + pct(g.arm_b_mit_fliesstext_urls_rate, 2) + ")") : ""));
    }
    if (!teile.length) return "";
    return '<div style="margin-top:14px;font-size:11.5px;color:#4b5563;line-height:1.6">'
      + '<span style="font-weight:700;color:' + COL.text + '">Gegenproben:</span> ' + teile.join(" · ") + "</div>";
  }

  function vorbehalteBlock(d) {
    var v = d.vorbehalte || [];
    if (!v.length) return "";
    return '<div style="margin-top:14px;border:1px solid #f3d7a5;background:#fdf6e6;border-radius:10px;padding:11px 14px">'
      + '<div style="font-size:12.5px;font-weight:700;color:#8a6d00;margin-bottom:5px">Was dieser Befund nicht sagt</div>'
      + v.map(function (x) {
        return '<div style="font-size:11.5px;color:#6b5b28;line-height:1.6;margin-bottom:5px">'
          + '<b>' + esc(x.titel) + ":</b> " + esc(x.text)
          + (x.quelle ? (' <span style="color:#a89469">(' + esc(x.quelle) + ")</span>") : "") + "</div>";
      }).join("")
      + "</div>";
  }

  function kopf(d) {
    var q = d.quelle || {}, u = d.umfang || {}, f = d.fehler || {};
    var dat = datum(q.created_at) || datum(q.datum);
    var meta = [];
    if (u.n_prompts != null) meta.push(u.n_prompts + " Prompts");
    if (u.n_produkte != null) meta.push(u.n_produkte + " Produkte");
    if (u.repeats != null) meta.push(u.repeats + " Wiederholungen");
    if (u.n_calls != null) meta.push(u.n_calls + " Aufrufe");
    if (f.n_failed != null) meta.push(f.n_failed + " Fehler");
    if (d.modell) meta.push("Modell " + d.modell);
    if (dat) meta.push("Lauf " + dat);
    return '<div style="display:inline-block;font-size:10px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;'
      + 'color:#8a6d00;background:#fdf6e6;border:1px solid #f3d7a5;border-radius:999px;padding:2px 9px">Kontrolliertes Experiment</div>'
      + '<h3 style="font-size:16px;font-weight:700;color:' + COL.text + ';margin:7px 0 2px">Wirkt die Websuche? Dieselben Fragen unter zwei Bedingungen</h3>'
      + '<p style="font-size:11.5px;color:#6b7280;line-height:1.6;margin:0 0 10px">'
      + 'Der Rest dieses Reiters <b>beobachtet</b>: er vergleicht, was ohnehin passiert. Hier wurde <b>eingegriffen</b> — '
      + 'jeder Prompt lief einmal mit erzwungener Websuche und einmal ohne jedes Werkzeug, sonst identisch, '
      + 'und die beiden Antworten werden paarweise verglichen. Deshalb ist der Unterschied hier '
      + '<b>die Wirkung der Suche</b> und nicht bloß ein Zusammenhang.'
      + (meta.length ? ('<br><span style="color:#9ca3af">' + esc(meta.join(" · ")) + "</span>") : "")
      + "</p>";
  }

  function fehltBlock(d) {
    var grund = (d && d.grund)
      ? ("Der Nightly konnte den Datensatz nicht übernehmen. Grund: " + d.grund)
      : ("data/search_ab.json ist nicht erreichbar — die Datei erzeugt "
         + "scripts/fetch_search_ab.py aus dem GEO-Repo.");
    return '<div style="border:1px solid #f3d7a5;background:#fdf6e6;border-radius:10px;padding:12px 14px">'
      + '<b style="font-size:12.5px;color:#8a6d00">⚠ Websuche-Experiment: keine Daten</b>'
      + '<div style="font-size:11.5px;color:#6b5b28;margin-top:3px;line-height:1.55">' + esc(grund)
      + " Es werden bewusst <b>keine Ersatzzahlen</b> gezeigt; der Block erscheint wieder, sobald der Datensatz vorliegt.</div></div>";
  }

  function html(d) {
    if (!d || d.available === false) return kopf({ umfang: {}, fehler: {}, quelle: {} }) + fehltBlock(d);
    var q = d.quelle || {};
    return kopf(d) + kernBlock(d) + kennzahlenTabelle(d) + forestBlock(d)
      + gegenprobenBlock(d) + vorbehalteBlock(d)
      + '<div style="font-size:10.5px;color:#b9bec6;margin-top:10px;line-height:1.5">Quelle: data/search_ab.json'
      + (q.pfad ? (" aus " + esc(q.repo || "") + "/" + esc(q.pfad)) : "")
      + (d.erzeugt_am ? (" · übernommen am " + esc(datum(d.erzeugt_am) || d.erzeugt_am)) : "")
      + " · dieses Experiment gehört nicht in die Zeitreihe.</div>";
  }

  /* ---------- Einhaengen ----------------------------------------------------
     #korrErgebnis wird von window.__korrRender komplett neu geschrieben; der
     Block muss danach erneut eingehaengt werden. Anker ist die Karte mit der
     Ueberschrift "2 · …" (Frage 2). Faellt der Anker weg, landet der Block am
     Ende des Panels, notfalls in der Sektion selbst. -------------------- */
  function anker() {
    var panel = document.getElementById("korrErgebnis");
    if (!panel) return null;
    var kinder = panel.children, i, h3;
    for (i = 0; i < kinder.length; i++) {
      h3 = kinder[i].querySelector ? kinder[i].querySelector("h3") : null;
      if (h3 && /^\s*2\s*[·.]/.test(h3.textContent || "")) {
        return { host: panel, nach: kinder[i] };
      }
    }
    return { host: panel, nach: null };
  }

  function build() {
    var data = window.__SEARCH_AB;
    if (data === undefined) return false;           // laedt noch
    var a = anker();
    if (!a) {
      // Panel noch nicht da: Rueckfall auf die Sektion selbst
      var sec = document.querySelector('section[data-content="korrelation"]');
      if (!sec) return false;
      a = { host: sec, nach: document.getElementById("korrErgebnis") };
    }
    var box = document.getElementById(BOX_ID);
    var neu = false;
    if (!box) {
      box = document.createElement("div");
      box.id = BOX_ID;
      box.className = "bg-white rounded-xl p-5 shadow mb-5";
      neu = true;
    }
    var amPlatz = box.parentNode === a.host
      && (a.nach ? box.previousElementSibling === a.nach : true);
    if (neu || !amPlatz) {
      if (a.nach && a.nach.nextSibling) a.host.insertBefore(box, a.nach.nextSibling);
      else a.host.appendChild(box);
    }
    if (neu || box.getAttribute("data-stand") !== String(window.__SEARCH_AB_STAND || "")) {
      box.innerHTML = html(data);
      box.setAttribute("data-stand", String(window.__SEARCH_AB_STAND || ""));
    }
    return true;
  }

  ready(function () {
    fetch("data/search_ab.json?t=" + Date.now(), { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; })
      .then(function (d) {
        window.__SEARCH_AB = d;
        window.__SEARCH_AB_STAND = (d && d.erzeugt_am) || "leer";
        var tries = 0;
        (function warte() {
          tries++;
          if (build() && document.getElementById("korrErgebnis")) return;
          if (tries < 60) setTimeout(warte, 300);
        })();
        // Panel wird bei jedem Rendern neu geschrieben -> danach neu einhaengen
        var panelWatch = setInterval(function () {
          var p = document.getElementById("korrErgebnis");
          if (!p) return;
          clearInterval(panelWatch);
          try {
            new MutationObserver(function () {
              if (!document.getElementById(BOX_ID)) setTimeout(build, 0);
            }).observe(p, { childList: true });
          } catch (e) { /* ohne Observer greift der Tab-Klick unten */ }
        }, 300);
        var tab = document.querySelector('[data-tab="korrelation"]');
        if (tab) tab.addEventListener("click", function () {
          [150, 600, 1400].forEach(function (ms) { setTimeout(build, ms); });
        });
      });
  });
})();
