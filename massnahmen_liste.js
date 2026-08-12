/* ============================================================
   Gebündelte Maßnahmenliste (12.08.2026)

   Der Empfehlungs-Reiter führte fünf voneinander unabhängige Listen mit fünf
   verschiedenen Prioritäts-Skalen: dynamische Themen-Empfehlungen (PRIO
   HOCH/MITTEL), Peec-Empfehlungen (Priorität hoch/mittel/niedrig), Content-GAP
   (HOCH/MITTEL/NIEDRIG), Treiber-GAP (HOCH/MITTEL/OK) und zwölf statische
   Maßnahmen (I/E-Score 0,8 bis 3,0). Wer den Reiter öffnete, konnte nicht
   wissen, ob "PRIO HOCH" bei Kfz mehr wiegt als "I/E 3.0" bei den
   Aktualitäts-Signalen. Dazu stand dieselbe Maßnahme mehrfach unter
   verschiedenen Namen (Rechner, Presse, Glossar je zweimal).

   Diese Datei zieht alles in EINE Rangfolge. Sortiert wird nach erwartetem
   Sichtbarkeitsgewinn (Entscheidung Paul, 11.08.2026).

   Die unbequeme Konsequenz daraus, und sie ist der eigentliche Befund:
   Nur bei den Themen-Maßnahmen lässt sich ein Gewinn überhaupt beziffern —
   dort gibt es einen gemessenen Zusammenhang zwischen Zitatanteil und
   Sichtbarkeit. Bei allem anderen ist der Gewinn NICHT messbar. Das wird hier
   nicht durch eine erfundene Punktzahl überdeckt, sondern ausgeschrieben, mit
   dem Grund. Die Liste hat deshalb vier Ränge:

     1. messbar        — Gewinn aus dem Modell, in Prozentpunkten
     2. Rückstand      — ERGO liegt hinter dem Wettbewerb; das ist ein
                         Rückstands-, kein Wirkungsargument
     3. fremde Wertung — Peecs Opportunity-Score, Formel nicht offengelegt
     4. Schätzung      — die statischen Langfrist-Maßnahmen, Aufwand und
                         Wirkung frei gesetzt

   Innerhalb jedes Rangs wird nach der jeweils besten verfügbaren Größe
   sortiert. Ein Rang ist keine Wertung der Maßnahme, sondern eine Aussage
   darüber, wie gut wir ihren Nutzen kennen.
   ============================================================ */
(function () {
  "use strict";

  function ready(fn){ if(document.readyState!=="loading") fn(); else document.addEventListener("DOMContentLoaded",fn); }
  function esc(s){ return String(s==null?"":s).replace(/[&<>"]/g,function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]; }); }
  function n1(v){ return (v==null||isNaN(v))?null:(Math.round(v*10)/10).toFixed(1).replace(".",","); }
  function pp(v){ var t=n1(v); return t==null?"—":((v>0?"+":"")+t+" pp"); }
  function mdLinks(s){
    return esc(s).replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, function(m,txt,url){
      return '<a href="'+url+'" target="_blank" rel="noopener" class="text-blue-600 hover:underline">'+txt+'</a>'; });
  }

  var RANG = {
    messbar:   {n:1, kurz:"messbar",        cls:"bg-green-100 text-green-800"},
    rueckstand:{n:2, kurz:"Rückstand",      cls:"bg-amber-100 text-amber-800"},
    fremd:     {n:3, kurz:"fremde Wertung", cls:"bg-blue-100 text-blue-800"},
    schaetzung:{n:4, kurz:"Schätzung",      cls:"bg-gray-100 text-gray-700"}
  };

  /* ---------- Quelle 1: Themen-Hotspots (die einzigen mit beziffertem Gewinn) ---------- */
  function ausThemen(){
    var hs = window.__RECO_HOTSPOTS || [];
    var f  = (typeof window.geoCiteSlope==="function") ? window.geoCiteSlope() : null;
    return hs.filter(function(h){ return h.potential!=null; }).map(function(h){
      return {
        titel: h.n + ": zitierfähige Inhalte aufbauen",
        was: "Themen-Hub, FAQ und Vergleichstabellen auf ergo.de, dazu Präsenz in den Portalen, "
           + "die in diesem Thema tatsächlich zitiert werden.",
        gewinn: h.potential,
        gewinnText: pp(h.potential) + " Sichtbarkeit",
        gewinnDetail: "wenn ERGO dort den Zitatanteil des Marktführers erreicht ("
           + n1(h.cite) + " % → " + n1(h.citeLead) + " %)"
           + (f ? ", gerechnet mit " + (Math.round(f.slope*100)/100).toFixed(2).replace(".",",")
                + " pp je pp Quellpräsenz" : ""),
        rang: "messbar",
        beleg: "Zusammenhang aus dem Querschnitt über Marken und Themen, kein Kausalnachweis — "
             + "kein Versprechen für den Fall, dass ERGO seinen Anteil erhöht.",
        aufwand: null,
        quelle: "GEO-Snapshot, cited_sources je Thema"
      };
    });
  }

  /* ---------- Quelle 2: Content-Bestand gegen den Wettbewerb ---------- */
  // Zusammengeführt mit den statischen Maßnahmen, die dasselbe meinen: das
  // Rechner-Portfolio, der Pressebereich und das Glossar standen bisher je
  // zweimal im Reiter, einmal als Zahl und einmal als Vorhaben.
  var GAP_ZU_STATISCH = { rechner:4, presse:6, glossar:2 };
  var GAP_FELDER = [
    {key:"faq",     label:"FAQ-Seiten ausbauen"},
    {key:"rechner", label:"Rechner und Tools ausbauen"},
    {key:"presse",  label:"Pressebereich aufbauen"},
    {key:"glossar", label:"Glossar/Lexikon aufbauen"},
    {key:"produkt", label:"Produktseiten ausbauen"},
    {key:"ratgeber",label:"Ratgeber-Bestand"},
    {key:"service", label:"Service-Hub"}
  ];

  function ausContentGap(){
    var P = window.PROVIDERS; if(!P || !P.ergo) return [];
    var marken = Object.keys(P).filter(function(k){ return k!=="ergo" && P[k] && P[k].total; });
    var raus=[];
    GAP_FELDER.forEach(function(f){
      var eigen = P.ergo[f.key]||0;
      // Gleiche Regel wie in der GAP-Tabelle: nur Anbieter zaehlen, die in
      // diesem Feld ueberhaupt etwas haben. Wer kein Glossar fuehrt, hat kein
      // kleines - er hat gar keins und darf den Schnitt nicht druecken.
      var werte = marken.map(function(k){ return P[k][f.key]||0; }).filter(function(v){ return v>0; });
      if(!werte.length) return;
      var schnitt = werte.reduce(function(a,b){return a+b;},0)/werte.length;
      var spitze  = Math.max.apply(null, werte);
      var spitzeMarke = marken.filter(function(k){ return (P[k][f.key]||0)===spitze; })[0];
      if(eigen >= schnitt) return;                 // kein Rückstand, keine Maßnahme
      var luecke = schnitt - eigen;
      var stat = GAP_ZU_STATISCH[f.key] ? (window.ACTIONS||[]).filter(function(a){return a.id===GAP_ZU_STATISCH[f.key];})[0] : null;
      raus.push({
        titel: f.label,
        was: "ERGO hat " + eigen + ", der Wettbewerbsschnitt liegt bei " + n1(schnitt)
           + " (Spitze " + spitze + (spitzeMarke?(", "+(P[spitzeMarke].name||spitzeMarke)):"") + ")."
           + (stat ? " " + esc(stat.how) : ""),
        gewinn: null,
        gewinnText: "nicht messbar",
        gewinnDetail: "Der Bestand an eigenen Seiten ist in der Messung kein Treiber der Sichtbarkeit — "
                    + "das Vorkommen in zitierten Quellen ist es. Was zählt, ist nicht die Zahl der Seiten, "
                    + "sondern ob sie zitiert werden.",
        rang: "rueckstand",
        sortWert: eigen>0 ? (luecke/Math.max(eigen,1)) : 99,   // relativer Rückstand
        beleg: "Bestandsvergleich aus dem Crawl. Rückstandsargument, kein Wirkungsargument.",
        aufwand: stat ? stat.effort : null,
        quelle: "Content-Inventar" + (stat ? " · deckt sich mit der Langfrist-Maßnahme „" + esc(stat.title) + "“" : "")
      });
    });
    return raus;
  }

  /* ---------- Quelle 3: Aktivitätsrückstand aus der Ereignis-Pipeline ---------- */
  function ausTreiberGap(){
    var rows = window.__DRIVER_GAP || [];
    return rows.filter(function(r){ return r.gap < 0; }).map(function(r){
      var im = r.imp || null;
      var gesichert = im && im.significant === true;
      return {
        titel: r.hint || r.label,
        was: "ERGO kommt im 30-Tage-Fenster auf " + r.ergo + ", der Wettbewerbsschnitt auf "
           + n1(r.avg) + ".",
        gewinn: null,
        gewinnText: gesichert ? pp(im.avg_sov_effect_pp) : "nicht nachweisbar",
        gewinnDetail: gesichert
            ? "cluster-robust gesichert"
            : "Der gemessene Effekt dieses Treibers liegt unter seiner Nachweisgrenze — die Messung "
            + "könnte ihn bei der heutigen Datenlage gar nicht finden. Das heißt nicht, dass er nicht wirkt.",
        rang: "rueckstand",
        sortWert: Math.abs(r.gap) / Math.max(r.avg, 1),
        beleg: "Aktivitätsvergleich aus der Ereignis-Pipeline. Rückstandsargument, kein Wirkungsargument.",
        aufwand: null,
        quelle: "Ereignis-Log, letzte 30 Tage"
      };
    });
  }

  /* ---------- Quelle 4: Peec ---------- */
  function ausPeec(){
    var d = window.__PACT; if(!d || !(d.items||[]).length) return [];
    return d.items.map(function(x){
      var txt = x.text_de || x.text || "";
      var kurz = txt.split(/(?<=[.!?])\s/).slice(0,1).join(" ");
      return {
        titel: (x.key_de||x.key||"Empfehlung") + ": " + (kurz.length>110 ? kurz.slice(0,107)+"…" : kurz),
        was: txt,
        istMarkdown: true,
        unuebersetzt: !x.text_de,
        gewinn: null,
        gewinnText: "nicht messbar",
        gewinnDetail: "Peec vergibt einen Opportunity-Score aus Abdeckungslücke und Zitat-Volumen. "
                    + "Die Formel legt Peec nicht offen — der Wert taugt zur Reihenfolge, nicht als Wirkungsnachweis.",
        rang: "fremd",
        sortWert: (x.score!=null ? x.score : 0) + (x.tier||0),
        beleg: "Von einem Sprachmodell erzeugt und vor der Umsetzung fachlich zu prüfen.",
        aufwand: null,
        quelle: "Peec AI · " + (x.group_de||x.group||"")
      };
    });
  }

  /* ---------- Quelle 5: die statischen Langfrist-Maßnahmen ---------- */
  function ausStatisch(){
    var A = window.ACTIONS || [];
    var schonDrin = Object.keys(GAP_ZU_STATISCH).map(function(k){ return GAP_ZU_STATISCH[k]; });
    return A.filter(function(a){ return schonDrin.indexOf(a.id) < 0; }).map(function(a){
      return {
        titel: a.title,
        was: a.how || "",
        gewinn: null,
        gewinnText: "nicht messbar",
        gewinnDetail: "Wirkung und Aufwand sind hier geschätzt, nicht gemessen. Diese Maßnahmen stammen "
                    + "aus der fachlichen Einschätzung, nicht aus den Daten dieses Cockpits.",
        rang: "schaetzung",
        sortWert: a.effort ? (a.impact/a.effort) : 0,
        beleg: "Fachliche Einschätzung" + (a.horizon ? ", geplant für " + esc(a.horizon) : "") + ".",
        aufwand: a.effort,
        quelle: "Langfrist-Planung"
      };
    });
  }

  /* ---------- Zusammenführen und rendern ---------- */
  function zeile(m, i){
    var r = RANG[m.rang] || RANG.schaetzung;
    return '<tr class="border-b align-top hover:bg-gray-50">'
      + '<td class="px-2 py-3 text-right text-xs text-gray-400 font-mono">' + (i+1) + '</td>'
      + '<td class="px-3 py-3">'
        + '<div class="font-semibold text-sm text-ergo-dark">' + esc(m.titel) + '</div>'
        + '<div class="text-xs text-gray-600 mt-1 leading-relaxed">'
          + (m.istMarkdown ? mdLinks(m.was) : esc(m.was)) + '</div>'
        + (m.unuebersetzt ? '<div class="text-xs text-amber-700 mt-1">Noch nicht übersetzt — Peecs englisches Original.</div>' : '')
        + '<div class="text-xs text-gray-400 mt-1">' + esc(m.quelle) + '</div>'
      + '</td>'
      + '<td class="px-3 py-3 whitespace-nowrap">'
        + '<div class="font-bold text-sm ' + (m.gewinn!=null ? 'text-green-700' : 'text-gray-400') + '">'
          + esc(m.gewinnText) + '</div>'
        + '<div class="text-xs text-gray-500 mt-1 leading-relaxed" style="max-width:22rem;white-space:normal">'
          + esc(m.gewinnDetail) + '</div>'
      + '</td>'
      + '<td class="px-3 py-3">'
        + '<span class="px-2 py-0.5 rounded-full text-xs font-semibold ' + r.cls + '">' + r.kurz + '</span>'
        + '<div class="text-xs text-gray-500 mt-1 leading-relaxed" style="max-width:18rem">' + esc(m.beleg) + '</div>'
      + '</td>'
      + '<td class="px-3 py-3 text-center text-xs text-gray-500">'
        + (m.aufwand!=null ? (esc(String(m.aufwand)) + '<div class="text-gray-400">geschätzt</div>') : '–')
      + '</td>'
      + '</tr>';
  }

  function build(){
    var host = document.querySelector('section[data-content="actions"]');
    if(!host) return false;
    // Erst bauen, wenn die Quellen geladen sind - sonst entstuende eine Liste,
    // die zufaellig ist, je nachdem was gerade da war.
    if(!window.__RECO_HOTSPOTS || !window.PROVIDERS) return false;

    var alle = [].concat(ausThemen(), ausContentGap(), ausTreiberGap(), ausPeec(), ausStatisch());
    if(!alle.length) return false;

    alle.sort(function(a,b){
      var ra=(RANG[a.rang]||RANG.schaetzung).n, rb=(RANG[b.rang]||RANG.schaetzung).n;
      if(ra!==rb) return ra-rb;
      if(a.gewinn!=null && b.gewinn!=null) return b.gewinn-a.gewinn;
      return (b.sortWert||0)-(a.sortWert||0);
    });

    var nMess = alle.filter(function(m){ return m.rang==="messbar"; }).length;
    var box = document.getElementById("massnahmenListe");
    if(!box){
      box = document.createElement("div");
      box.id = "massnahmenListe";
      box.className = "bg-white rounded-xl p-6 shadow mb-6";
      // Ganz nach oben: die eine Rangfolge ist die Hauptansicht, alles andere
      // darunter und eingeklappt. Auch die dynamischen Karten - sie sind
      // Zeile 1 bis 7 dieser Liste, nur anders gesetzt.
      host.insertBefore(box, host.firstChild);
    }

    box.innerHTML =
        '<h2 class="text-2xl font-bold text-ergo-dark mb-1">Alle Maßnahmen in einer Rangfolge</h2>'
      + '<p class="text-sm text-gray-600 mb-1">' + alle.length + ' Maßnahmen aus fünf Quellen, zusammengeführt und '
      + 'entdoppelt. Sortiert nach erwartetem Sichtbarkeitsgewinn.</p>'
      + '<div class="text-xs text-gray-600 bg-amber-50 border-l-4 border-amber-400 rounded p-3 mb-4 leading-relaxed">'
      + '<b>Warum nur ' + nMess + ' Zeilen eine Zahl tragen.</b> Ein Gewinn lässt sich nur dort beziffern, wo ein '
      + 'gemessener Zusammenhang existiert — und das ist bislang allein der zwischen Zitatanteil und Sichtbarkeit '
      + 'in einem Thema. Für alles andere steht hier bewusst „nicht messbar" statt einer erfundenen Punktzahl. '
      + 'Das ist keine Absage an diese Maßnahmen: die Spalte daneben sagt jeweils, worauf sie sich stattdessen stützen.'
      + '</div>'
      + '<div class="overflow-x-auto"><table class="w-full text-sm"><thead><tr class="bg-ergo-dark text-white">'
      + '<th class="px-2 py-2 text-right">#</th>'
      + '<th class="px-3 py-2 text-left">Maßnahme</th>'
      + '<th class="px-3 py-2 text-left">Erwarteter Gewinn</th>'
      + '<th class="px-3 py-2 text-left">Worauf es sich stützt</th>'
      + '<th class="px-3 py-2 text-center">Aufwand</th>'
      + '</tr></thead><tbody>'
      + alle.map(zeile).join("")
      + '</tbody></table></div>'
      + '<div class="text-xs text-gray-400 mt-3 leading-relaxed">'
      + 'Aufwand in Personentagen-Klassen aus der Langfrist-Planung, wo vorhanden — geschätzt, nicht gemessen, '
      + 'und deshalb nicht in die Sortierung eingegangen. Die Einzelansichten der fünf Quellen stehen unverändert '
      + 'eingeklappt darunter.</div>';

    einzelansichtenFalten(host, box);
    return true;
  }

  /* Die fünf Quell-Blöcke stehen weiterhin vollständig da — aber eingeklappt.
     Sie stehen zu lassen, wie sie waren, hätte den Sinn der Bündelung
     aufgehoben: Wer den Reiter öffnet, hätte wieder sechs Listen vor sich
     statt einer. Gelöscht werden sie nicht, weil jede von ihnen etwas kann,
     was die Rangfolge nicht kann — Filter je Bereich, die Peec-Slices, die
     vollständigen Bestandszahlen je Wettbewerber.
     Bewusst über das DOM statt über das Markup: die Blöcke werden von fünf
     verschiedenen Stellen gerendert, teils asynchron. Ein <details> im HTML
     hätte bedeutet, jede dieser Stellen anzufassen. */
  function einzelansichtenFalten(host, box){
    var d = document.getElementById("massnahmenQuellen");
    if(!d){
      d = document.createElement("details");
      d.id = "massnahmenQuellen";
      d.className = "mb-6";
      var s = document.createElement("summary");
      s.className = "cursor-pointer select-none text-sm font-semibold text-ergo-dark hover:text-ergo-red py-2";
      s.textContent = "Einzelansichten der Quellen anzeigen — dynamische Themen-Karten, "
                    + "Peec-Empfehlungen mit Bereichsfilter, Content-Bestand je Wettbewerber, "
                    + "Treiber-Aktivität, Langfrist-Planung";
      d.appendChild(s);
      var innen = document.createElement("div");
      innen.className = "mt-2";
      innen.id = "massnahmenQuellenInnen";
      d.appendChild(innen);
      host.appendChild(d);
    }
    var innen2 = document.getElementById("massnahmenQuellenInnen");
    // Bewusst NICHT nur einmal: empfehlungen_dynamic.js haengt seinen Block
    // asynchron ein und kann nach diesem Lauf noch auftauchen. Beim naechsten
    // Durchgang wird er dann ebenfalls eingefaltet, statt allein oben stehen
    // zu bleiben.
    Array.prototype.slice.call(host.children).forEach(function(el){
      if(el === box || el === d) return;
      innen2.appendChild(el);
    });
  }

  ready(function(){
    var v=0; (function w(){ v++; if(build()) return; if(v<60) setTimeout(w,500); })();
    var tb=document.querySelector('[data-tab="actions"]');
    if(tb) tb.addEventListener("click", function(){ [400,1200,2500].forEach(function(d){ setTimeout(build,d); }); });
  });
})();
