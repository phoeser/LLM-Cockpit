/* ============================================================
   ERGO LLM-Cockpit — Content → Zitate (Content-Tab)
   Zeigt URL-genau, WELCHE Inhalte es in die Zitate der LLMs
   schaffen — nicht nur, ob Seitenaenderungen wirken.

   Bloecke:
     1. Kernaussage (zitierte eigene Seiten / getrackte Seiten)
     2. Tabelle der zitierten eigenen Seiten (Seitentyp, Zitat-
        verlauf als Sparkline ueber die Peec-Staende, letzte Aenderung)
     3. Seitentyp-Vergleich ERGO vs. Allianz (Zitate je Typ)
     4. Zitatanteil je Seitentyp (Gesamtmarkt) + Trefferquote je Marke
     5. Presse: zitierte redaktionelle Domains + ERGO-Presseaktivitaet
        (Domain-Ebene — artikelgenau nicht moeglich)
     6. Engine-Abdeckung (nur Perplexity belastbar)

   Quelle: data/content_citations.json (Runtime-fetch, erzeugt von
   scripts/content_citations.py). Fehlt die Datei, erscheint ein
   Hinweis — NIE Ersatz-Nullen.
   Keine externen Abhaengigkeiten, Diagramme als Inline-SVG.
   Einbindung: <script src="content_citations.js"></script>
   Haengt sich in <section data-content="contentgeo"> ein (Karte
   #ccCard, hinter #contentGeoBody).
   ============================================================ */
(function () {
  "use strict";

  var COL = {
    ergo: "#dc0028", allianz: "#0a3d8f", grau: "#9ca3af", hell: "#e5e7eb",
    gruen: "#067d3a", gold: "#b8860b", blau: "#2a78d6", text: "#282d37"
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
  function num(v) {
    if (v == null || isNaN(v)) return "—";
    return Number(v).toLocaleString("de-DE");
  }
  function pct(v) {
    if (v == null || isNaN(v)) return "—";
    return (Math.round(v * 10) / 10).toFixed(1).replace(".", ",") + " %";
  }
  function datum(s) {
    if (!s) return "—";
    var m = String(s).match(/(\d{4})-(\d{2})-(\d{2})/);
    return m ? m[3] + "." + m[2] + "." + m[1] : esc(s);
  }
  function shortUrl(u) {
    var s = String(u || "");
    return s.length > 62 ? s.slice(0, 60) + "…" : s;
  }
  function note(txt) {
    if (!txt) return "";
    return '<div style="font-size:10.5px;color:#8a8f98;line-height:1.5;margin-top:6px">' +
      "<b>Vorbehalt:</b> " + esc(txt) + "</div>";
  }
  function missing(grund) {
    return '<div style="border:1px solid #f3d7a5;background:#fdf6e6;border-radius:8px;' +
      'padding:10px 12px;font-size:11.5px;color:#6b5b28;margin-top:6px">' +
      "<b>Keine Daten:</b> " + esc(grund || "Grund nicht angegeben.") + "</div>";
  }
  function h3(t) {
    return '<div style="font-size:13.5px;font-weight:700;margin:18px 0 6px;color:' + COL.text + '">' + esc(t) + "</div>";
  }

  /* ---------- Inline-SVG-Bausteine ---------- */

  // Sparkline ueber die Peec-Staende. Fehlende Staende sind Luecken
  // (URL war nicht im Top-150) und werden NICHT als 0 gezeichnet.
  function sparkline(verlauf, alleStaende, w, h) {
    w = w || 88; h = h || 22;
    var pts = [];
    var max = 0;
    alleStaende.forEach(function (d, i) {
      var v = verlauf ? verlauf[d] : null;
      if (v == null) return;
      if (v > max) max = v;
      pts.push({ i: i, v: v, d: d });
    });
    if (!pts.length) return '<span style="font-size:10px;color:#b0b4bb">kein Stand</span>';
    var n = Math.max(alleStaende.length - 1, 1);
    var x = function (i) { return 1 + (i / n) * (w - 2); };
    var y = function (v) { return max > 0 ? (h - 2) - (v / max) * (h - 4) : h / 2; };
    var poly = pts.map(function (p) { return x(p.i).toFixed(1) + "," + y(p.v).toFixed(1); }).join(" ");
    var dots = pts.map(function (p) {
      return '<circle cx="' + x(p.i).toFixed(1) + '" cy="' + y(p.v).toFixed(1) + '" r="1.8" fill="' + COL.ergo + '">' +
        "<title>" + esc(p.d) + ": " + num(p.v) + " Zitate</title></circle>";
    }).join("");
    return '<svg width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + " " + h + '" role="img" ' +
      'aria-label="Zitatverlauf ueber die archivierten Peec-Staende">' +
      (pts.length > 1 ? '<polyline points="' + poly + '" fill="none" stroke="' + COL.ergo + '" stroke-width="1.4"/>' : "") +
      dots + "</svg>";
  }

  // Doppelbalken (zwei Marken je Kategorie)
  function bars2(rows, keyA, keyB, labA, labB, colA, colB) {
    var max = 0;
    rows.forEach(function (r) { max = Math.max(max, r[keyA] || 0, r[keyB] || 0); });
    if (!max) return missing("Keine Zitate in den verglichenen Seitentypen.");
    var W = 320, rowH = 34, padL = 118;
    var h = rows.length * rowH + 6;
    var svg = '<svg width="100%" viewBox="0 0 ' + (padL + W + 60) + " " + h + '" role="img" aria-label="' +
      esc(labA + " gegen " + labB + " je Seitentyp") + '">';
    rows.forEach(function (r, i) {
      var yTop = i * rowH + 4;
      var wA = (r[keyA] || 0) / max * W, wB = (r[keyB] || 0) / max * W;
      svg += '<text x="0" y="' + (yTop + 12) + '" font-size="11" fill="' + COL.text + '">' + esc(r.seitentyp) + "</text>";
      svg += '<rect x="' + padL + '" y="' + yTop + '" width="' + wA.toFixed(1) + '" height="11" fill="' + colA + '" rx="2"><title>' +
        esc(labA) + ": " + num(r[keyA]) + " Zitate</title></rect>";
      svg += '<rect x="' + padL + '" y="' + (yTop + 13) + '" width="' + wB.toFixed(1) + '" height="11" fill="' + colB + '" rx="2"><title>' +
        esc(labB) + ": " + num(r[keyB]) + " Zitate</title></rect>";
      svg += '<text x="' + (padL + Math.max(wA, wB) + 6) + '" y="' + (yTop + 16) + '" font-size="10" fill="#6b7280">' +
        num(r[keyA]) + " / " + num(r[keyB]) + "</text>";
    });
    svg += "</svg>";
    var leg = '<div style="font-size:10.5px;color:#6b7280;margin-top:4px">' +
      '<span style="display:inline-block;width:9px;height:9px;background:' + colA + ';border-radius:2px;margin-right:4px"></span>' + esc(labA) +
      '<span style="display:inline-block;width:9px;height:9px;background:' + colB + ';border-radius:2px;margin:0 4px 0 14px"></span>' + esc(labB) +
      "</div>";
    return svg + leg;
  }

  // Einfacher horizontaler Balken (eine Reihe)
  function bar1(label, wert, max, farbe, zusatz) {
    var w = max > 0 ? (wert / max) * 100 : 0;
    return '<div style="display:flex;align-items:center;gap:8px;margin:3px 0">' +
      '<div style="width:132px;font-size:11px;color:' + COL.text + '">' + esc(label) + "</div>" +
      '<div style="flex:1;background:' + COL.hell + ';border-radius:3px;height:11px;overflow:hidden">' +
      '<div style="width:' + w.toFixed(1) + '%;height:100%;background:' + farbe + '"></div></div>' +
      '<div style="width:120px;font-size:11px;color:#6b7280;text-align:right">' + esc(zusatz) + "</div></div>";
  }

  /* ---------- Bloecke ---------- */

  function blockKopf(d) {
    var kz = d.kennzahlen || {};
    var tq = kz.trefferquote_je_marke || {};
    var ergo = null;
    if (tq.available) {
      (tq.marken || []).forEach(function (m) { if (m.brand === "ERGO") ergo = m; });
    }
    var seiten = d.seiten || [];
    var eigenZit = seiten.filter(function (r) { return r.ist_eigene_seite && r.zitiert; });
    var peecZit = eigenZit.filter(function (r) { return r.peec_cit != null; });
    var nurPplx = eigenZit.filter(function (r) { return r.peec_cit == null && r.own_cit_perplexity; });

    /* KORREKTUR 10.08.2026: Der Satz lautete "Von 1.099 getrackten Seiten sind 45
       zitiert — davon 50 im Peec-Top-150". Das ist arithmetisch unmoeglich. Ursache:
       das "davon" bezog sich auf die 45 GETRACKTEN, gezaehlt wurden aber peecZit und
       nurPplx ueber ALLE eigenen zitierten Seiten (50 + 48 = 98) — zwei
       Grundgesamtheiten in einem Satz. Jetzt wird die Zerlegung der 45 aus den
       getrackten Seiten selbst gerechnet, und die weitere Menge steht als eigener
       Satz daneben. */
    var getracktZit = eigenZit.filter(function (r) { return r.ist_getrackt; });
    var gtPeec = getracktZit.filter(function (r) { return r.peec_cit != null; });
    var gtPplx = getracktZit.filter(function (r) { return r.peec_cit == null && r.own_cit_perplexity; });

    var kern;
    if (ergo) {
      kern = "Von " + num(ergo.getrackt) + " getrackten ERGO-Seiten sind " + num(ergo.zitiert) + " (" +
        pct(ergo.quote_pct) + ") überhaupt als zitierte Quelle nachweisbar";
      if (getracktZit.length) {
        kern += " — davon " + num(gtPeec.length) + " im Peec-Top-150 und " + num(gtPplx.length) +
          " nur im eigenen Perplexity-Lauf";
      }
      kern += ". Über die getrackte Menge hinaus sind insgesamt " + num(eigenZit.length) +
        " eigene URLs zitiert (" + num(peecZit.length) + " im Peec-Top-150, " + num(nurPplx.length) +
        " nur im eigenen Lauf) — diese Zahl ist größer, weil sie auch eigene Seiten enthält, die gar nicht getrackt werden.";
    } else {
      kern = num(peecZit.length) + " eigene Seiten stehen im Peec-Top-150. Eine Trefferquote ist nicht berechenbar: " +
        (tq.grund || "kein Nenner verfuegbar.");
    }
    var q = (d.meta && d.meta.quellen) || {};
    var stand = (q.peec_sources && q.peec_sources.as_of) || "—";
    var fenster = (q.peec_sources && q.peec_sources.fenster) || {};

    return '<h3 style="font-size:16px;font-weight:700;margin:0">Content → Zitate: welche Inhalte es in die LLM-Antworten schaffen</h3>' +
      '<p style="font-size:13px;color:#6b7280;margin:4px 0 10px">URL-genau statt „Seitenaenderungen wirken/wirken nicht". ' +
      "Quelle: Peec-Zitate (Stand " + esc(stand) + ", Fenster " + esc(fenster.start || "?") + " bis " + esc(fenster.end || "?") +
      ") und der eigene Crawl. Zitat und Markennennung in derselben Antwort sind ein Ko-Vorkommen, kein Kausalnachweis.</p>" +
      '<div style="border-left:3px solid ' + COL.ergo + ';background:#fdf2f4;padding:10px 12px;border-radius:0 8px 8px 0;' +
      'font-size:13px;font-weight:600;color:' + COL.text + '">' + esc(kern) + "</div>" +
      note(tq.vorbehalt);
  }

  function blockTabelle(d) {
    var staende = ((d.meta.quellen || {}).peec_snapshots || {}).staende || [];
    var rows = (d.seiten || []).filter(function (r) { return r.ist_eigene_seite && r.zitiert; });
    var html = h3("Zitierte eigene Seiten (" + rows.length + ") — sortiert nach Zitaten");
    if (!rows.length) {
      return html + missing("Keine eigene Seite in Peec-Top-150 oder im belastbaren Teil des eigenen Crawls.");
    }
    rows.sort(function (a, b) {
      return (b.peec_cit || 0) - (a.peec_cit || 0) || (b.own_cit_perplexity || 0) - (a.own_cit_perplexity || 0);
    });
    html += '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:11.5px">' +
      '<thead><tr style="text-align:left;color:#6b7280">' +
      '<th style="padding:5px 6px">Seite</th>' +
      '<th style="padding:5px 6px">Seitentyp</th>' +
      '<th style="padding:5px 6px;text-align:right">Peec-Zitate</th>' +
      '<th style="padding:5px 6px">Verlauf ' + esc((staende[0] || "").slice(5)) + "–" + esc((staende[staende.length - 1] || "").slice(5)) + "</th>" +
      '<th style="padding:5px 6px;text-align:right">eigener Lauf<br>(Perplexity)</th>' +
      '<th style="padding:5px 6px">letzte Aenderung</th></tr></thead><tbody>';

    rows.forEach(function (r) {
      var typ = r.seitentyp
        ? esc(r.seitentyp) + '<span style="color:#b0b4bb;font-size:9.5px"> · ' + esc(r.quelle_seitentyp) + "</span>"
        : '<span style="color:#b0b4bb">nicht zuordenbar</span>';
      var letzte = r.last_change_ts
        ? datum(r.last_change_ts) + '<span style="color:#9ca3af"> · ' + r.n_changes + " Aend.</span>"
        : (r.n_changes ? r.n_changes + " Aend." : '<span style="color:#b0b4bb">keine erfasst</span>');
      html += '<tr style="border-top:1px solid #f0f0f0">' +
        '<td style="padding:6px"><a href="' + esc(r.url_raw) + '" target="_blank" rel="noopener" style="color:' + COL.text + ';text-decoration:none">' +
        esc(shortUrl(r.url_norm)) + "</a>" +
        (r.peec_title ? '<div style="color:#9ca3af;font-size:10px">' + esc(r.peec_title) + "</div>" : "") + "</td>" +
        '<td style="padding:6px">' + typ + "</td>" +
        '<td style="padding:6px;text-align:right;font-weight:700">' + (r.peec_cit == null ? '<span style="color:#b0b4bb" title="nicht im Top-150 — Zitatzahl unbekannt, nicht 0">n. i. Top-150</span>' : num(r.peec_cit)) + "</td>" +
        '<td style="padding:6px">' + sparkline(r.peec_cit_verlauf, staende) + "</td>" +
        '<td style="padding:6px;text-align:right">' + (r.own_cit_perplexity == null ? '<span style="color:#b0b4bb">—</span>' : num(r.own_cit_perplexity)) + "</td>" +
        '<td style="padding:6px;color:#6b7280">' + letzte + "</td></tr>";
    });
    html += "</tbody></table></div>";
    html += note("Peec zeigt nur die Top-150-URLs des rollierenden 30-Tage-Fensters — eine Lücke in der Sparkline heisst " +
      "»in diesem Stand unter der Kappung, Zitatzahl unbekannt«, nicht »0 Zitate«. Die Spalte »eigener Lauf« zählt " +
      "Quellenangaben eines einzelnen Perplexity-Laufs (" + esc(((d.kennzahlen || {}).engine_abdeckung || {}).run_id || "Lauf unbekannt") + ").");
    return html;
  }

  function blockErgoAllianz(d) {
    var kz = (d.kennzahlen || {}).ergo_vs_allianz_je_seitentyp || {};
    var html = h3("Seitentyp-Vergleich: ERGO gegen Allianz (Zitate je Typ)");
    if (!kz.available) return html + missing(kz.grund) + note(kz.vorbehalt);
    html += bars2(kz.typen || [], "ERGO", "Allianz", "ERGO/DKV", "Allianz", COL.ergo, COL.allianz);
    html += note(kz.vorbehalt);
    return html;
  }

  function blockSeitentypMarkt(d) {
    var kz = (d.kennzahlen || {}).zitatanteil_je_seitentyp || {};
    var html = h3("Woraus die Engines insgesamt zitieren (Seitentyp-Mix aller Top-150-Quellen)");
    if (!kz.available) return html + missing(kz.grund) + note(kz.vorbehalt);
    var max = 0;
    (kz.typen || []).forEach(function (t) { max = Math.max(max, t.zitate || 0); });
    (kz.typen || []).forEach(function (t) {
      html += bar1(t.seitentyp, t.zitate || 0, max, COL.blau, num(t.zitate) + " · " + pct(t.anteil_pct) + " · " + t.urls + " URLs");
    });
    html += note(kz.vorbehalt);
    return html;
  }

  function blockTrefferquote(d) {
    var kz = (d.kennzahlen || {}).trefferquote_je_marke || {};
    var html = h3("Zitat-Trefferquote je Marke (zitierte ÷ getrackte Seiten)");
    if (!kz.available) return html + missing(kz.grund) + note(kz.vorbehalt);
    var marken = (kz.marken || []).filter(function (m) { return m.getrackt >= 50; }).slice(0, 12);
    var max = 0;
    marken.forEach(function (m) { max = Math.max(max, m.quote_pct || 0); });
    marken.forEach(function (m) {
      html += bar1(m.brand, m.quote_pct || 0, max, m.eigen ? COL.ergo : COL.grau,
        pct(m.quote_pct) + " · " + num(m.zitiert) + "/" + num(m.getrackt));
    });
    html += note(kz.vorbehalt);
    return html;
  }

  function blockVerlauf(d) {
    var kz = (d.kennzahlen || {}).ergo_top150_verlauf || {};
    var med = (d.kennzahlen || {}).median_tage_bis_erstes_zitat || {};
    var html = h3("ERGO-Seiten im Peec-Top-150 über die archivierten Stände");
    if (!kz.available) return html + missing(kz.grund) + note(kz.vorbehalt);
    var max = 0;
    (kz.staende || []).forEach(function (s) { max = Math.max(max, s.zitate || 0); });
    html += '<div style="display:flex;gap:14px;align-items:flex-end;padding:6px 0">';
    (kz.staende || []).forEach(function (s) {
      var hgt = max > 0 ? Math.round((s.zitate / max) * 66) + 4 : 4;
      html += '<div style="text-align:center;flex:1">' +
        '<div style="font-size:10.5px;color:#6b7280">' + num(s.zitate) + " Zitate</div>" +
        '<div style="height:' + hgt + 'px;background:' + COL.ergo + ';border-radius:3px 3px 0 0;margin:3px 0"></div>' +
        '<div style="font-size:11px;font-weight:700">' + s.urls_im_top150 + " URLs</div>" +
        '<div style="font-size:10px;color:#9ca3af">' + datum(s.datum) + "</div></div>";
    });
    html += "</div>";
    if (med && med.available) {
      html += '<div style="font-size:11.5px;color:#6b7280;margin-top:6px">Median bis zum ersten beobachteten Zitat: <b>' +
        num(med.median_tage) + " Tage</b> (n = " + num(med.n) + ", davon " + num(med.davon_echtes_publikationsdatum) +
        " mit echtem Publikationsdatum, " + num(med.davon_proxy) + " nur mit Erstsichtungs-Proxy; " +
        num(med.linkszensiert) + " URLs waren bereits im ersten Stand zitiert und damit linkszensiert).</div>" + note(med.vorbehalt);
    } else if (med) {
      html += missing(med.grund) + note(med.vorbehalt);
    }
    html += note(kz.vorbehalt);
    return html;
  }

  function blockPresse(d) {
    var p = d.presse || {};
    var html = h3("Presse: zitierte redaktionelle Domains und eigene Presseaktivität");
    if (!p.available) return html + missing(p.grund) + note(p.vorbehalt);
    var pqTop = p.presse_quelle || {};
    html += '<div style="font-size:11.5px;color:#374151;background:#f6f8fa;border:1px solid #e3e6ea;' +
      'border-radius:8px;padding:8px 10px;margin-bottom:8px"><b>Domain- und Artikel-Ebene.</b> ' +
      "Die Google-News-Redirects sind zu echten Artikel-URLs aufgelöst (" +
      num(pqTop.artikel_mit_echter_url) + " von " + num(pqTop.artikel_gesamt) + " Artikeln, " +
      (pqTop.aufloesungsquote_pct != null ? pqTop.aufloesungsquote_pct + "&nbsp;%" : "–") +
      "), der Abgleich läuft damit auch artikelgenau.</div>";
    html += '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:11.5px">' +
      '<thead><tr style="text-align:left;color:#6b7280">' +
      '<th style="padding:5px 6px">Redaktionelle Domain</th>' +
      '<th style="padding:5px 6px;text-align:right">Zitate</th>' +
      '<th style="padding:5px 6px">ERGO in denselben Antworten</th>' +
      '<th style="padding:5px 6px;text-align:right">ERGO-Artikel im Peec-Fenster</th>' +
      '<th style="padding:5px 6px;text-align:right">ERGO-Artikel gesamt</th>' +
      '<th style="padding:5px 6px;text-align:right">Artikel aller Marken</th></tr></thead><tbody>';
    (p.domains || []).forEach(function (r) {
      var wert = function (v, hint) {
        if (v != null) return num(v);
        return '<span style="color:#b0b4bb" title="' + esc(hint || "") + '">keine Angabe</span>';
      };
      html += '<tr style="border-top:1px solid #f0f0f0">' +
        '<td style="padding:6px">' + esc(r.domain) +
        (r.presse_hinweis ? '<div style="color:#9ca3af;font-size:10px">' + esc(r.presse_hinweis) + "</div>" : "") + "</td>" +
        '<td style="padding:6px;text-align:right;font-weight:700">' + num(r.zitate) + "</td>" +
        '<td style="padding:6px">' + (r.ergo_genannt ? '<span style="color:' + COL.gruen + '">ja (Ko-Vorkommen)</span>' : '<span style="color:#9ca3af">nein</span>') + "</td>" +
        '<td style="padding:6px;text-align:right">' + wert(r.ergo_presseartikel_im_peec_fenster, r.presse_hinweis) + "</td>" +
        '<td style="padding:6px;text-align:right">' + wert(r.ergo_presseartikel_gesamt, r.presse_hinweis) + "</td>" +
        '<td style="padding:6px;text-align:right;color:#6b7280">' + wert(r.presseartikel_alle_marken, "In der Presse-Historie kein Artikel dieses Mediums.") + "</td></tr>";
    });
    html += "</tbody></table></div>";
    html += h3("Schafft es die einzelne Meldung in die Zitate?");
    var tr = p.artikel_treffer || [];
    if (!tr.length) {
      html += '<div style="font-size:11.5px;color:#374151;background:#f6f8fa;border:1px solid #e3e6ea;' +
        'border-radius:8px;padding:8px 10px">Kein einziger Presseartikel taucht in den zitierten ' +
        "Quellen auf. Wirkung entsteht über die Domain, nicht über die einzelne Meldung.</div>";
    } else {
      html += '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:11.5px">' +
        '<thead><tr style="text-align:left;color:#6b7280">' +
        '<th style="padding:5px 6px">Artikel</th>' +
        '<th style="padding:5px 6px">Domain</th>' +
        '<th style="padding:5px 6px">Marke</th>' +
        '<th style="padding:5px 6px">Datum</th>' +
        '<th style="padding:5px 6px;text-align:right">Zitate</th></tr></thead><tbody>';
      tr.slice(0, 25).forEach(function (t) {
        html += '<tr style="border-top:1px solid #f0f0f0">' +
          '<td style="padding:6px">' + esc(t.titel || t.url) +
          (t.peec_cls ? '<div style="color:#9ca3af;font-size:10px">' + esc(t.peec_cls) + "</div>" : "") + "</td>" +
          '<td style="padding:6px">' + esc(t.domain) + "</td>" +
          '<td style="padding:6px">' + esc(t.marke || "–") + "</td>" +
          '<td style="padding:6px">' + datum(t.datum) + "</td>" +
          '<td style="padding:6px;text-align:right;font-weight:700">' + num(t.peec_cit) + "</td></tr>";
      });
      html += "</tbody></table></div>";
    }
    html += note(p.artikel_treffer_hinweis);
    var pq = p.presse_quelle || {};
    if (pq.available) {
      html += '<div style="font-size:10.5px;color:#8a8f98;margin-top:6px">Presse-Historie: ' + num(pq.artikel_gesamt) +
        " Artikel " + datum((pq.zeitraum || {}).von) + " bis " + datum((pq.zeitraum || {}).bis) +
        " über " + num((pq.marken || []).length) + " Marken; " +
        num((p.unzugeordnete_medien || []).length) + " Medien ohne belegte Domain-Zuordnung.</div>";
    } else {
      html += missing(pq.grund);
    }
    html += note(p.vorbehalt);
    return html;
  }

  function blockEngines(d) {
    var kz = (d.kennzahlen || {}).engine_abdeckung || {};
    var html = h3("Engine-Abdeckung des eigenen Crawls");
    if (!kz.available) return html + missing(kz.grund) + note(kz.vorbehalt);
    html += '<div style="display:flex;gap:10px;flex-wrap:wrap">';
    (kz.engines || []).forEach(function (e) {
      html += '<div style="flex:1;min-width:200px;border:1px solid ' + (e.belastbar ? "#cfe6d8" : "#eee") +
        ';background:' + (e.belastbar ? "#f4fbf7" : "#fafafa") + ';border-radius:8px;padding:9px 11px">' +
        '<div style="font-size:12px;font-weight:700">' + esc(e.engine) +
        '<span style="font-weight:400;font-size:10.5px;color:' + (e.belastbar ? COL.gruen : "#9ca3af") + '"> · ' +
        (e.belastbar ? "URL-genau belastbar" : "nicht belastbar") + "</span></div>" +
        '<div style="font-size:11px;color:#6b7280;margin-top:3px">' + num(e.distinkte_quell_urls) + " distinkte Quell-URLs</div>" +
        (e.belastbar
          ? '<div style="font-size:11px;color:#6b7280">' + num(e.eigene_urls) + " eigene · " + num(e.getrackte_urls) + " getrackte Seiten</div>"
          : '<div style="font-size:10.5px;color:#b0b4bb">' + esc(e.eigene_urls_hinweis || "") + "</div>") +
        '<div style="font-size:10px;color:#9ca3af;margin-top:3px">' + esc(e.grund) + "</div></div>";
    });
    html += "</div>";
    html += note(kz.vorbehalt);
    return html;
  }

  /* ---------- Aufbau ---------- */

  function build(d) {
    var host = document.querySelector('section[data-content="contentgeo"]');
    if (!host || document.getElementById("ccCard")) return true;
    var card = document.createElement("div");
    card.id = "ccCard";
    card.className = "bg-white rounded-xl shadow p-6 mb-6";

    if (!d) {
      card.innerHTML = '<h3 style="font-size:16px;font-weight:700;margin:0">Content → Zitate</h3>' +
        missing("data/content_citations.json wurde nicht gefunden oder ist nicht lesbar. " +
          "Die Datei erzeugt scripts/content_citations.py aus Peec-Quellen, GEO-Seitendaten und dem eigenen Crawl. " +
          "Es werden bewusst keine Ersatzwerte angezeigt.");
    } else {
      card.innerHTML = blockKopf(d) + blockTabelle(d) + blockErgoAllianz(d) + blockSeitentypMarkt(d) +
        blockTrefferquote(d) + blockVerlauf(d) + blockPresse(d) + blockEngines(d) +
        '<div style="font-size:10.5px;color:#8a8f98;margin-top:14px;border-top:1px solid #f0f0f0;padding-top:8px">' +
        "Quelle: data/content_citations.json (" + esc((d.meta || {}).erzeugt_am || "Stand unbekannt") + "), erzeugt von scripts/content_citations.py. " +
        esc(((d.kennzahlen || {})._hinweis) || "") + "</div>";
    }

    var anchor = document.getElementById("contentGeoBody");
    if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(card, anchor);
    else host.appendChild(card);
    return true;
  }

  function load() {
    if (window.CONTENT_CITATIONS) return Promise.resolve(window.CONTENT_CITATIONS);
    return fetch("data/content_citations.json?t=" + Date.now(), { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
  }

  ready(function () {
    var tries = 0;
    (function wait() {
      tries++;
      if (!document.querySelector('section[data-content="contentgeo"]')) {
        if (tries < 25) setTimeout(wait, 300);
        return;
      }
      load().then(function (d) { build(d); });
    })();
  });
})();
