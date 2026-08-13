/* ============================================================
   ERGO LLM-Cockpit — Reiter "SOHO (Gewerbe)"  (13.08.2026)
   ============================================================

   Was hier steht und warum
   ------------------------
   Bis heute hat dieses Cockpit ausschliesslich Privatkunden-Themen
   gemessen. Nicht, weil das Gewerbegeschaeft unwichtig waere, sondern
   weil nie jemand danach gefragt hat: Peec hatte fuer Gewerbe null
   Prompts, der eigene Crawl elf private Themen. Im Dashboard sah das
   genauso aus wie "gemessen und nichts gefunden" — der teuerste Irrtum,
   den eine Messstrecke anbieten kann.

   Am 13.08.2026 wurden dafuer 60 eigene Prompts geschrieben
   (30 Betriebshaftpflicht, 30 Firmen-Rechtsschutz) und die beiden
   Produkte in die GEO-Konfiguration aufgenommen. Der erste Lauf lief
   am selben Abend, 20:14 bis 21:06 UTC. Dieser Reiter zeigt dessen
   Ergebnis.

   Zwei Entwurfsentscheidungen, die man kennen sollte
   --------------------------------------------------
   1. NICHTS ist hier fest eingetragen. Jede Zahl wird zur Laufzeit aus
      window.GEO_SNAPSHOT gerechnet. Der Reiter kann damit nicht still
      veralten — er zeigt immer den Stand, den auch der Rest des
      Cockpits zeigt. Waeren die Zahlen vom 13.08. hier eincodiert,
      saehe der Reiter in vier Wochen taeglich frisch aus und waere es
      nicht. Genau daran ist die alte Auto-Deploy-Seite gescheitert.

   2. Fehlen die beiden Themen im Snapshot, wird das GESAGT statt
      kaschiert. Der Cockpit-Snapshot wird vom Nightly geholt; zwischen
      GEO-Lauf und Nightly liegen Stunden, in denen die Themen im
      GEO-Repo stehen, aber noch nicht hier. Ein leerer Reiter waere in
      dieser Zeit von einem kaputten nicht zu unterscheiden.

   Zur Perplexity-Behandlung
   -------------------------
   Liefert ein LLM an einem Tag keine eigenen Daten, schreibt der Lauf
   fuer die etablierten Themen den Vortageswert fort. Fuer ein neues
   Thema gibt es keinen Vortag — dort steht dann ehrlich nichts. Dieser
   Reiter rechnet deshalb ausschliesslich mit LLMs, die fuer das
   jeweilige Thema tatsaechlich Prompts abgesetzt haben (prompts_total
   > 0), und schreibt darunter, welche das waren. Ein Anteil, der
   stillschweigend auf zwei statt drei Systemen beruht, ist kein
   Anteil, sondern eine Falle.

   Einbindung: wird von health_banner.js nachgeladen, damit die
   13-MB-Vorlage dashboard_template.html nicht angefasst werden muss.
   ============================================================ */
(function () {
  "use strict";

  var SOHO = [
    { id: "betriebshaftpflicht", kurz: "Betriebshaftpflicht" },
    { id: "firmenrechtsschutz",  kurz: "Firmen-Rechtsschutz" }
  ];
  // Privates Pendant als Massstab. Firmen-Rechtsschutz gegen privaten
  // Rechtsschutz zu halten ist der ehrlichste verfuegbare Vergleich:
  // gleiche Sparte, gleicher Lauf, gleiche LLMs — nur anderes Segment.
  var MASSSTAB = { id: "rechtsschutz", label: "Rechtsschutz (privat)" };

  var EIGEN = "ERGO";
  var ROT = "#DC0028", DUNKEL = "#282D37", GRAU = "#6b7280";

  // Die Snapshot-Schluessel sind kleingeschrieben; in einer Fussnote, die ein
  // Mensch liest, gehoeren die Produktnamen so hin, wie die Anbieter sie
  // schreiben.
  var LLM_NAME = { chatgpt: "ChatGPT", gemini: "Gemini", perplexity: "Perplexity",
                   claude: "Claude", grok: "Grok" };
  function llmName(id) { return LLM_NAME[id] || id; }

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function n1(x) { return (Math.round(x * 10) / 10).toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 }); }
  function iv(x) { return Math.round(x).toLocaleString("de-DE"); }

  function snap() { return window.GEO_SNAPSHOT || null; }

  function produkt(id) {
    var g = snap();
    return (g && g.products && g.products[id]) ? g.products[id] : null;
  }

  /* LLMs, die fuer DIESES Thema wirklich gearbeitet haben. Ein LLM mit
     prompts_total = 0 hat nichts beigetragen; seine Nullen duerfen den
     Durchschnitt nicht verduennen. */
  function llmsMitDaten(p) {
    var out = [];
    var sbl = (p && p.summary_by_llm) || {};
    for (var k in sbl) {
      if (Object.prototype.hasOwnProperty.call(sbl, k) && (sbl[k].prompts_total || 0) > 0) out.push(k);
    }
    return out.sort();
  }
  function alleLlms(p) {
    var out = [], sbl = (p && p.summary_by_llm) || {};
    for (var k in sbl) if (Object.prototype.hasOwnProperty.call(sbl, k)) out.push(k);
    return out.sort();
  }

  /* Marken ueber die arbeitenden LLMs zusammenfassen.
     mentions summiert, Quoten gemittelt — die Quoten sind je LLM auf
     dieselbe Promptzahl bezogen, ein einfaches Mittel ist damit
     sachlich richtig und nicht nur bequem. */
  function aggregat(p) {
    var llms = llmsMitDaten(p), acc = {}, prompts = 0;
    llms.forEach(function (l) {
      var v = p.summary_by_llm[l] || {};
      prompts += (v.prompts_total || 0);
      (v.brands || []).forEach(function (b) {
        var a = acc[b.name] || (acc[b.name] = { name: b.name, mentions: 0, sov: [], app: [], rank: [], cite: [] });
        a.mentions += (b.mentions || 0);
        a.sov.push(b.share_of_voice || 0);
        a.app.push(b.appearance_rate || 0);
        a.cite.push(b.citation_rate || 0);
        if (b.avg_rank) a.rank.push(b.avg_rank);
      });
    });
    var liste = [];
    for (var k in acc) {
      if (!Object.prototype.hasOwnProperty.call(acc, k)) continue;
      var a = acc[k], mit = function (arr) { return arr.length ? arr.reduce(function (x, y) { return x + y; }, 0) / arr.length : 0; };
      liste.push({
        name: a.name,
        mentions: a.mentions,
        sov: mit(a.sov) * 100,
        app: mit(a.app) * 100,
        cite: mit(a.cite) * 100,
        rank: a.rank.length ? mit(a.rank) : null
      });
    }
    liste.sort(function (x, y) { return y.mentions - x.mentions; });
    return { marken: liste, llms: llms, promptLaeufe: prompts };
  }

  /* ---------------- Bausteine ---------------- */

  function markenTabelle(agg) {
    var max = agg.marken.length ? Math.max.apply(null, agg.marken.map(function (m) { return m.mentions; })) : 1;
    var zeilen = agg.marken.map(function (m) {
      var ist = (m.name === EIGEN);
      var breite = max > 0 ? Math.round(m.mentions / max * 100) : 0;
      return '<tr style="border-bottom:1px solid #f1f5f9' + (ist ? ';background:#fff5f7' : '') + '">'
        + '<td style="padding:7px 10px;font-weight:' + (ist ? "700" : "500") + ';color:' + (ist ? ROT : DUNKEL) + '">' + esc(m.name) + '</td>'
        + '<td style="padding:7px 10px;width:34%">'
        + '<div style="background:#eef2f7;border-radius:3px;height:9px;overflow:hidden">'
        + '<div style="width:' + breite + '%;height:9px;background:' + (ist ? ROT : "#94a3b8") + '"></div></div></td>'
        + '<td style="padding:7px 10px;text-align:right;font-variant-numeric:tabular-nums">' + iv(m.mentions) + '</td>'
        + '<td style="padding:7px 10px;text-align:right;font-variant-numeric:tabular-nums">' + n1(m.sov) + ' %</td>'
        + '<td style="padding:7px 10px;text-align:right;font-variant-numeric:tabular-nums">' + n1(m.app) + ' %</td>'
        + '<td style="padding:7px 10px;text-align:right;font-variant-numeric:tabular-nums;color:' + (m.cite > 0 ? DUNKEL : "#b45309") + '">' + n1(m.cite) + ' %</td>'
        + '<td style="padding:7px 10px;text-align:right;color:' + GRAU + ';font-variant-numeric:tabular-nums">' + (m.rank ? n1(m.rank) : "—") + '</td>'
        + '</tr>';
    }).join("");

    return '<table style="width:100%;border-collapse:collapse;font-size:13px">'
      + '<thead><tr style="border-bottom:2px solid #e2e8f0;color:' + GRAU + ';font-size:11.5px;text-transform:uppercase;letter-spacing:.03em">'
      + '<th style="padding:6px 10px;text-align:left">Anbieter</th><th></th>'
      + '<th style="padding:6px 10px;text-align:right">Nennungen</th>'
      + '<th style="padding:6px 10px;text-align:right">Anteil</th>'
      + '<th style="padding:6px 10px;text-align:right">in % der Antworten</th>'
      + '<th style="padding:6px 10px;text-align:right">als Quelle zitiert</th>'
      + '<th style="padding:6px 10px;text-align:right">Ø-Rang</th></tr></thead>'
      + '<tbody>' + zeilen + '</tbody></table>';
  }

  /* Der eigentliche Befund des ersten Laufs steckt nicht in den
     Nennungen, sondern hier: wessen Seiten die Modelle als Beleg
     heranziehen. Genannt zu werden heisst, im Text vorzukommen.
     Zitiert zu werden heisst, die Antwort zu stuetzen. */
  function quellenBlock(p) {
    var cs = p.cited_sources;
    if (!cs || !cs.overall || !cs.overall.length) {
      return '<p style="font-size:12.5px;color:' + GRAU + ';margin:8px 0 0">Für dieses Thema hat der Lauf keine Quellenliste geliefert.</p>';
    }
    var zeilen = cs.overall.slice(0, 12).map(function (q) {
      var eigen = /(^|\.)ergo\.de$|(^|\.)dkv\.de$|ergodirekt\.de$/.test(q.domain || "");
      return '<tr style="border-bottom:1px solid #f1f5f9' + (eigen ? ';background:#fff5f7' : '') + '">'
        + '<td style="padding:5px 10px;font-family:ui-monospace,Menlo,monospace;font-size:12px;color:' + (eigen ? ROT : DUNKEL) + ';font-weight:' + (eigen ? "700" : "400") + '">' + esc(q.domain) + '</td>'
        + '<td style="padding:5px 10px;font-size:11.5px;color:' + GRAU + '">' + esc(q.category || "") + '</td>'
        + '<td style="padding:5px 10px;text-align:right;font-variant-numeric:tabular-nums">' + iv(q.count) + '</td>'
        + '<td style="padding:5px 10px;text-align:right;color:' + GRAU + ';font-variant-numeric:tabular-nums">' + n1(q.share || 0) + ' %</td></tr>';
    }).join("");

    var eigeneDrin = cs.overall.some(function (q) { return /ergo\.de$|dkv\.de$/.test(q.domain || ""); });
    var hinweis = eigeneDrin
      ? ''
      : '<p style="margin:8px 0 0;font-size:12.5px;color:#7a4a12;background:#fff8ed;border-left:3px solid #b45309;padding:8px 12px;border-radius:4px">'
        + '<b>Keine ERGO-Domain unter den meistzitierten Quellen.</b> Die Modelle nennen ERGO in diesem Thema durchaus — '
        + 'als Beleg heranziehen tun sie andere. Das ist der Hebel: Nennung folgt der Quelle, nicht umgekehrt.</p>';

    return '<table style="width:100%;border-collapse:collapse;font-size:13px">'
      + '<thead><tr style="border-bottom:2px solid #e2e8f0;color:' + GRAU + ';font-size:11.5px;text-transform:uppercase;letter-spacing:.03em">'
      + '<th style="padding:6px 10px;text-align:left">Domain</th>'
      + '<th style="padding:6px 10px;text-align:left">Art</th>'
      + '<th style="padding:6px 10px;text-align:right">Zitate</th>'
      + '<th style="padding:6px 10px;text-align:right">Anteil</th></tr></thead>'
      + '<tbody>' + zeilen + '</tbody></table>'
      + '<p style="margin:6px 0 0;font-size:11.5px;color:' + GRAU + '">' + iv(cs.total || 0) + ' Quellenangaben insgesamt in diesem Thema.</p>'
      + hinweis;
  }

  function themenBlock(def) {
    var p = produkt(def.id);
    if (!p) return "";
    var agg = aggregat(p);
    var eigen = agg.marken.filter(function (m) { return m.name === EIGEN; })[0];
    var erster = agg.marken[0];
    var alle = alleLlms(p), ohne = alle.filter(function (l) { return agg.llms.indexOf(l) < 0; });

    var kopfzahl = eigen
      ? '<div style="display:flex;gap:26px;flex-wrap:wrap;margin:2px 0 14px">'
        + kachel("ERGO-Anteil", n1(eigen.sov) + " %", eigen.name === (erster && erster.name) ? "Platz 1" : ("Platz " + (agg.marken.indexOf(eigen) + 1) + " von " + agg.marken.length))
        + kachel("ERGO in Antworten", n1(eigen.app) + " %", "von " + iv(agg.promptLaeufe) + " Prompt-Läufen")
        + kachel("ERGO als Quelle", n1(eigen.cite) + " %", erster ? ("Erstplatzierter: " + n1(erster.cite) + " %") : "")
        + kachel("Stärkster Anbieter", erster ? esc(erster.name) : "—", erster ? (n1(erster.sov) + " % Anteil") : "")
        + '</div>'
      : '<p style="color:' + ROT + ';font-weight:600">ERGO kommt in diesem Thema in keiner einzigen Antwort vor.</p>';

    var fussnote = ohne.length
      ? '<p style="margin:10px 0 0;font-size:11.5px;color:' + GRAU + '">Gerechnet über ' + agg.llms.map(llmName).map(esc).join(" und ")
        + '. Ohne eigene Daten für dieses Thema: ' + ohne.map(llmName).map(esc).join(", ")
        + ' — bei einem neu aufgesetzten Thema gibt es keinen Vortageswert, der fortgeschrieben werden könnte. '
        + 'Die Anteile oben beruhen deshalb auf ' + agg.llms.length + ' von ' + alle.length + ' Systemen.</p>'
      : '<p style="margin:10px 0 0;font-size:11.5px;color:' + GRAU + '">Gerechnet über ' + agg.llms.map(llmName).map(esc).join(", ") + '.</p>';

    return '<div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:18px 20px;margin-bottom:16px">'
      + '<h3 style="margin:0 0 2px;font-size:17px;color:' + DUNKEL + '">' + esc(p.name || def.kurz) + '</h3>'
      + '<p style="margin:0 0 12px;font-size:12px;color:' + GRAU + '">' + iv(agg.promptLaeufe) + ' Prompt-Läufe · '
      + (p.url ? '<a href="' + esc(p.url) + '" target="_blank" style="color:' + ROT + '">Produktseite</a>' : '') + '</p>'
      + kopfzahl
      + markenTabelle(agg)
      + fussnote
      + '<h4 style="margin:20px 0 6px;font-size:14px;color:' + DUNKEL + '">Worauf sich die Antworten stützen</h4>'
      + quellenBlock(p)
      + '</div>';
  }

  function kachel(titel, wert, unten) {
    return '<div><div style="font-size:11px;color:' + GRAU + ';text-transform:uppercase;letter-spacing:.04em">' + esc(titel) + '</div>'
      + '<div style="font-size:24px;font-weight:700;color:' + DUNKEL + ';line-height:1.2">' + wert + '</div>'
      + (unten ? '<div style="font-size:11.5px;color:' + GRAU + '">' + unten + '</div>' : '') + '</div>';
  }

  /* Der Vergleich mit dem privaten Pendant. Ohne ihn steht eine Zahl wie
     "10,6 % Anteil" ohne Massstab im Raum — schlecht oder normal, das
     entscheidet erst der Bezug. */
  function einordnung() {
    var pv = produkt(MASSSTAB.id);
    var pf = produkt("firmenrechtsschutz");
    if (!pv || !pf) return "";
    var av = aggregat(pv), af = aggregat(pf);
    function anteil(agg, name) {
      var m = agg.marken.filter(function (x) { return x.name === name; })[0];
      return m ? m.sov : 0;
    }
    var ergoP = anteil(av, EIGEN), ergoG = anteil(af, EIGEN);
    var allP = anteil(av, "Allianz"), allG = anteil(af, "Allianz");

    return '<div style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:12px;padding:16px 20px;margin-bottom:16px">'
      + '<h3 style="margin:0 0 8px;font-size:15px;color:' + DUNKEL + '">Einordnung: gewerblich gegen privat</h3>'
      + '<table style="border-collapse:collapse;font-size:13px">'
      + '<tr><td style="padding:4px 16px 4px 0;color:' + GRAU + '"></td>'
      + '<td style="padding:4px 16px 4px 0;text-align:right;color:' + GRAU + '">ERGO</td>'
      + '<td style="padding:4px 0;text-align:right;color:' + GRAU + '">Allianz</td></tr>'
      + '<tr><td style="padding:4px 16px 4px 0">' + esc(MASSSTAB.label) + '</td>'
      + '<td style="padding:4px 16px 4px 0;text-align:right;font-weight:600">' + n1(ergoP) + ' %</td>'
      + '<td style="padding:4px 0;text-align:right">' + n1(allP) + ' %</td></tr>'
      + '<tr><td style="padding:4px 16px 4px 0">Firmen-Rechtsschutz (gewerblich)</td>'
      + '<td style="padding:4px 16px 4px 0;text-align:right;font-weight:600;color:' + ROT + '">' + n1(ergoG) + ' %</td>'
      + '<td style="padding:4px 0;text-align:right">' + n1(allG) + ' %</td></tr>'
      + '</table>'
      + '<p style="margin:10px 0 0;font-size:12.5px;color:#475569">Gleiche Sparte, gleicher Lauf, gleiche Modelle — '
      + 'nur anderes Segment. Der Abstand im Anteil ist in beiden Segmenten ähnlich; der Unterschied liegt darin, '
      + 'dass ERGO privat wenigstens als Quelle vorkommt.</p>'
      + '</div>';
  }

  function leerZustand() {
    var g = snap();
    var stand = g && (g.finished_at || g.run_id) ? String(g.finished_at || g.run_id).slice(0, 10) : "unbekannt";
    return '<div style="background:#fff8ed;border-left:4px solid #b45309;border-radius:8px;padding:16px 20px;color:#7a4a12">'
      + '<b>Die beiden Gewerbe-Themen stehen noch nicht im Cockpit-Snapshot.</b><br><br>'
      + 'Sie wurden am 13.08.2026 im GEO-Repo aufgesetzt und dort auch schon gemessen. In dieses Cockpit '
      + 'kommen sie mit dem nächsten Nightly, der den GEO-Snapshot abholt. Der Snapshot, der hier gerade '
      + 'geladen ist, stammt vom ' + esc(stand) + ' und kennt sie noch nicht.<br><br>'
      + 'Das ist kein Fehler, sondern der normale Abstand zwischen Messung und Auslieferung — '
      + 'er steht hier, damit ein leerer Reiter nicht wie ein kaputter aussieht.'
      + '</div>';
  }

  function sectionHTML() {
    var g = snap();
    if (!g) {
      return '<div style="padding:20px;color:' + GRAU + '">Snapshot noch nicht geladen.</div>';
    }
    var vorhanden = SOHO.filter(function (d) { return !!produkt(d.id); });
    var kopf = '<h2 style="margin:0 0 4px;font-size:22px;color:' + ROT + '">SOHO — kleine Gewerbe</h2>'
      + '<p style="margin:0 0 16px;font-size:13px;color:' + GRAU + ';max-width:70ch">'
      + 'Betriebshaftpflicht und Firmen-Rechtsschutz, gemessen mit 60 eigens dafür geschriebenen Prompts '
      + 'aus der Sicht von Solo-Selbstständigen, Handwerk, Gastronomie, Heilberufen und Onlinehandel. '
      + 'Vor dem 13.08.2026 gab es zu diesem Segment keine einzige Messung — weder im eigenen Crawl noch bei Peec.'
      + '</p>';

    if (!vorhanden.length) return kopf + leerZustand();

    var warnung = (vorhanden.length < SOHO.length)
      ? '<div style="background:#fff8ed;border-left:3px solid #b45309;padding:8px 12px;border-radius:4px;font-size:12.5px;color:#7a4a12;margin-bottom:14px">'
        + 'Nur ' + vorhanden.length + ' von ' + SOHO.length + ' Gewerbe-Themen im Snapshot enthalten.</div>'
      : '';

    var hinweisEinzelmessung = '<div style="background:#eff6ff;border-left:3px solid #3b82f6;padding:10px 14px;border-radius:4px;font-size:12.5px;color:#1e3a5f;margin-bottom:16px">'
      + '<b>Bestandsaufnahme, kein Verlauf.</b> Diese Zahlen stammen aus dem ersten Lauf überhaupt. '
      + 'Ob sie typisch sind oder ein Ausreißer, lässt sich erst nach einigen wöchentlichen Läufen sagen. '
      + 'Bis dahin taugen sie zur Größenordnung und zum Vergleich der Anbieter untereinander — nicht als Trend.'
      + '</div>';

    return kopf + warnung + hinweisEinzelmessung
      + vorhanden.map(themenBlock).join("")
      + einordnung();
  }

  /* ---------------- Reiter anlegen ---------------- */

  function zeigen() {
    [].slice.call(document.querySelectorAll("[data-tab]")).forEach(function (b) {
      b.classList.remove("tab-active"); b.classList.add("tab-inactive");
    });
    var btn = document.getElementById("sohoTabBtn");
    if (btn) { btn.classList.remove("tab-inactive"); btn.classList.add("tab-active"); }
    [].slice.call(document.querySelectorAll("[data-content]")).forEach(function (s) { s.classList.add("hidden"); });
    var sec = document.getElementById("sohoSection");
    if (sec) {
      sec.classList.remove("hidden");
      // Bei jedem Aufruf frisch rechnen: der Snapshot kann zwischen
      // Seitenaufbau und Klick nachgeladen worden sein.
      try { sec.innerHTML = sectionHTML(); } catch (e) {}
    }
    try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) {}
  }
  function verstecken() {
    var sec = document.getElementById("sohoSection");
    if (sec) sec.classList.add("hidden");
    var btn = document.getElementById("sohoTabBtn");
    if (btn) { btn.classList.remove("tab-active"); btn.classList.add("tab-inactive"); }
  }

  function knopf() {
    if (document.getElementById("sohoTabBtn")) return true;
    var ref = document.querySelector('[data-tab="overview"]');
    if (!ref || !ref.parentNode) return false;
    var btn = document.createElement("button");
    btn.id = "sohoTabBtn";
    btn.className = (ref.className || "tab-btn").replace(/tab-active/g, "tab-inactive");
    if (btn.className.indexOf("tab-btn") < 0) btn.className += " tab-btn";
    if (btn.className.indexOf("tab-inactive") < 0) btn.className += " tab-inactive";
    btn.setAttribute("data-tab", "soho");
    btn.innerHTML = "🏢 SOHO";
    btn.addEventListener("click", function (e) { e.preventDefault(); zeigen(); });
    // Vor die Dokumentation, falls die schon da ist — sonst ans Ende.
    var doku = document.getElementById("dokuTabBtn");
    if (doku && doku.parentNode === ref.parentNode) ref.parentNode.insertBefore(btn, doku);
    else ref.parentNode.appendChild(btn);
    return true;
  }
  function section() {
    if (document.getElementById("sohoSection")) return true;
    var ref = document.querySelector('section[data-content="overview"]');
    if (!ref || !ref.parentNode) return false;
    var sec = document.createElement("section");
    sec.id = "sohoSection";
    sec.setAttribute("data-content", "soho");
    sec.className = "tab-content hidden";
    sec.innerHTML = sectionHTML();
    ref.parentNode.appendChild(sec);
    return true;
  }
  function andereKnoepfe() {
    [].slice.call(document.querySelectorAll(".tab-btn")).forEach(function (b) {
      if (b.id === "sohoTabBtn") return;
      if (b.getAttribute("data-soho-wired") === "1") return;
      b.setAttribute("data-soho-wired", "1");
      b.addEventListener("click", function () { verstecken(); });
    });
  }

  function bauen() {
    var a = knopf(), b = section();
    if (a) andereKnoepfe();
    return a && b;
  }

  ready(function () {
    var versuche = 0;
    (function warten() {
      versuche++;
      bauen();
      // Weiter versuchen, bis Reiter UND Section stehen und der Snapshot
      // da ist. nav_redesign.js sortiert die Leiste um, geo_doku_tab.js
      // haengt sich ebenfalls an — wer zuerst fertig ist, ist nicht
      // vorhersagbar, deshalb wird mehrfach nachgefasst statt einmal
      // geraten.
      var fertig = document.getElementById("sohoSection") && document.getElementById("sohoTabBtn") && snap();
      if (!fertig && versuche < 40) setTimeout(warten, 250);
      else if (fertig) {
        andereKnoepfe();
        var sec = document.getElementById("sohoSection");
        if (sec && sec.classList.contains("hidden")) {
          try { sec.innerHTML = sectionHTML(); } catch (e) {}
        }
      }
    })();
  });
})();
