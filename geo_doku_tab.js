/* ============================================================
   ERGO LLM-Cockpit — Reiter "Dokumentation" (Runtime-Modul, 18.07.2026)
   -----------------------------------------------------------------
   Statische Methodik-Dokumentation fuer Statistiker / Aktuare:
   praezise, ehrlich, mit allen Einschraenkungen. Kein fetch noetig.
   Muster uebernommen aus korrelation_upgrade.js (IIFE, "use strict",
   ready()/Retry, Inline-Styles, Karten-Look, ERGO-Rot #dc0028).

   Additiv & rebuild-sicher:
     (a) Tab-Button "📖 Dokumentation" (data-tab="doku") ans Ende der
         Tab-Leiste (parentNode des [data-tab="overview"]-Buttons).
     (b) <section data-content="doku"> (initial display:none) als
         Geschwister der uebrigen Sections.
     (c) Tab-Wechsel-Logik: Klick auf unseren Button zeigt unsere
         Section + versteckt alle anderen; Klick auf jeden anderen
         .tab-btn versteckt unsere Section wieder. Idempotent.

   Alle Zahlen stammen aus den Uebergaben 17./18.07.2026, dem
   Reiter-Doku 16_KORRELATIONSANALYSE_V5_DOKU.md und den Workflow-YMLs
   (scripts/correlation_impact.py als Statistik-Ground-Truth). Wo eine
   Zahl je Nightly dynamisch ist, ist sie als "Stand 18.07.2026"
   gekennzeichnet. Keine Zahl erfunden.
   ============================================================ */
(function () {
  "use strict";
  function ready(fn){ if(document.readyState!=="loading") fn(); else document.addEventListener("DOMContentLoaded",fn); }

  var RED="#dc0028";
  var STAND="Stand 18.07.2026";

  /* ---------- Bausteine (Inline-Styles, Karten-Look) ---------- */
  function chapter(id, title, open, inner){
    return '<details id="'+id+'"'+(open?' open':'')+
      ' style="border:1px solid #ececf0;border-radius:12px;background:#fff;margin:0 0 12px;padding:2px 18px;box-shadow:0 1px 2px rgba(0,0,0,.03)">'+
      '<summary style="cursor:pointer;font-size:15px;font-weight:700;color:#1a1a2e;padding:13px 0;list-style:none">'+title+'</summary>'+
      '<div style="font-size:12.5px;color:#374151;line-height:1.62;padding:2px 0 16px">'+inner+'</div>'+
    '</details>';
  }
  function h(t){ return '<div style="font-size:13px;font-weight:700;color:#1a1a2e;margin:14px 0 5px">'+t+'</div>'; }
  function note(t){ return '<div style="font-size:11.5px;color:#6b7280;margin:6px 0 0">'+t+'</div>'; }
  function warn(t){
    return '<div style="border-left:3px solid '+RED+';background:#fff5f6;border-radius:0 8px 8px 0;padding:8px 12px;margin:9px 0;font-size:12px;color:#374151;line-height:1.55">'+t+'</div>';
  }
  function info(t){
    return '<div style="border-left:3px solid #1d4ed8;background:#f4f7fe;border-radius:0 8px 8px 0;padding:8px 12px;margin:9px 0;font-size:12px;color:#374151;line-height:1.55">'+t+'</div>';
  }
  function badge(txt,kind){
    var c={ok:["#067d3a","#e6f5ec"],warn:["#8a6d00","#fdf3d7"],muted:["#6b7280","#eef0f2"],info:["#1d4ed8","#e7eefe"],bad:["#b91c1c","#fdecec"]}[kind]||["#6b7280","#eef0f2"];
    return '<span style="font-size:10px;font-weight:700;color:'+c[0]+';background:'+c[1]+';border-radius:4px;padding:2px 7px;white-space:nowrap">'+txt+'</span>';
  }
  // Verfahrens-Karte fuer Kapitel 4 (Was / Warum / Wo / Interpretation / Grenzen)
  function method(o){
    function row(lbl,val){ return val?('<tr><td style="vertical-align:top;padding:3px 10px 3px 0;font-weight:700;color:#1a1a2e;white-space:nowrap">'+lbl+'</td><td style="padding:3px 0;color:#374151">'+val+'</td></tr>'):''; }
    return '<div style="border:1px solid #ececf0;border-radius:11px;background:#fbfbfc;padding:11px 14px;margin:10px 0">'+
      '<div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start;margin-bottom:5px">'+
        '<div style="font-size:12.5px;font-weight:800;color:'+RED+'">'+o.name+'</div>'+(o.badge||'')+'</div>'+
      '<table style="width:100%;border-collapse:collapse;font-size:12px;line-height:1.5">'+
        row("Was", o.was)+ row("Warum", o.warum)+ row("Wo", o.wo)+ row("Interpretation", o.interp)+ row("Grenzen", o.grenzen)+
      '</table></div>';
  }
  function tbl(headers, rows){
    var th=headers.map(function(x,i){ return '<th style="text-align:'+(i?'right':'left')+';padding:6px 9px;color:#64748b;border-bottom:1px solid #e2e8f0;font-weight:600">'+x+'</th>'; }).join("");
    var tr=rows.map(function(r){
      return '<tr style="border-bottom:1px solid #f1f5f9">'+r.map(function(c,i){
        return '<td style="text-align:'+(i?'right':'left')+';padding:6px 9px;color:#374151'+(i?'':';font-weight:600')+'">'+c+'</td>'; }).join("")+'</tr>';
    }).join("");
    return '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12px;margin:8px 0">'+
      '<thead><tr>'+th+'</tr></thead><tbody>'+tr+'</tbody></table></div>';
  }

  /* ============================================================
     Kapitel 1 — Ueberblick & Datenfluesse
     ============================================================ */
  function kap1(){
    return h("Was gemessen wird")+
      'Das Cockpit misst die <b>LLM-Sichtbarkeit</b> der ERGO und ihrer Wettbewerber: In welchem Umfang und wie tauchen die Marken in den Antworten grosser Sprachmodelle auf Versicherungs-Fragen auf. Ziel ist ein <b>Treibermodell</b>, das statistisch benennt, was bessere Sichtbarkeit erklaert.'+
      h("Zwei-Quellen-Prinzip")+
      'Zwei unabhaengige Messsysteme messen dieselbe Sache — das ist die zentrale Absicherung gegen Zirkularitaet:'+
      tbl(["Quelle","Rolle","Marken","Engines","Erhebung"],[
        ['<b>Peec AI</b> (fuehrend)','Primaerquelle LLM-Sichtbarkeit','26','5 (inkl. Google AI Overview / AI Mode)','UI-Scraping, woechentlich'],
        ['Eigener API-Crawl','Backup & Konsistenzpruefung','7','2 (Gemini grounded, ChatGPT ungrounded; Perplexity pausiert)','eigene API, taeglich']
      ])+
      note("Peec fuehrt, weil es mehr Marken und mehr Engines abdeckt; der eigene Crawl liefert den zirkularitaetsarmen externen Gegentest (Kapitel 4, Verfahren 5).")+
      h("Wirkungs- vs. Hebelmetrik")+
      'Zwei Metrik-Familien werden bewusst getrennt gehalten:'+
      info('<b>Brand Mention / Share of Voice = Wirkungsmetrik.</b> Kommt die Marke in der Antwort selbst vor? Das liest der Nutzer — die eigentliche Empfehlung. Fein aufgeschluesselt nach Position in der Antwort und Sentiment.')+
      info('<b>Zitations-Footprint = Frueh-/Hebelindikator.</b> <b>Definition:</b> Anteil der markeneigenen Domain (z.&nbsp;B. ergo.de) an allen zitierten URLs je Thema. Nachgelagert, aber steuerbar: die Antwortformulierung laesst sich nicht beeinflussen, die Zitierfaehigkeit der eigenen Inhalte schon.')+
      warn('<b>Kausalkette:</b> Grounded LLMs generieren aus den abgerufenen Quellen. Ohne Quellpraesenz kaum Empfehlung — deshalb ist der Footprint Fruehindikator <i>und</i> Stellhebel, aber nie ein Ersatz fuer die Wirkungsmessung.');
  }

  /* ============================================================
     Kapitel 2 — Aktualisierungs-Rhythmen
     ============================================================ */
  function kap2(){
    return 'Alle Rhythmen aus den Workflow-YMLs des Repos (bzw. der geo-visibility-tool-/Cowork-Pipeline). Zeiten in <b>UTC</b>.'+
      tbl(["Was","Workflow / Task","Rhythmus (UTC)","Zieldatei(en)"],[
        ['Eigener LLM-Crawl','analyze.yml <span style="color:#9ca3af">(geo-visibility-tool)</span>','taeglich 23:10','geo_snapshot.json (in den Nightly geladen)'],
        ['Cockpit-Nightly<br><span style="color:#9ca3af;font-weight:400">Snapshot laden, SoV-Historie, Korrelations-/Impact-Analyse, Interventionen, Check24-Preise, Ratings, Sentiment, Presse, Pipeline-Health</span>','nightly-update.yml','taeglich 04:30','correlation_impact.json, geo_snapshot.json, sov_history.jsonl, intervention_results.json u.&nbsp;a.'],
        ['Peec-Export<br><span style="color:#9ca3af;font-weight:400">versionierte Snapshots + Wochen-Panel (seit 18.07.)</span>','Cowork-Task peec-weekly-export','woechentlich Mo 07:07','peec_snapshots/YYYY-MM-DD_*.csv, peec_history_weekly.csv, peec_cells.csv, peec_footprint.json'],
        ['Check24-Preise & Reviews','weekly-prices.yml','woechentlich Mo 05:45','price_comparison.json, review_history.json'],
        ['Berater Google Reviews','berater-reviews.yml','woechentlich So 05:00','berater_reviews.json, brand_reviews.json'],
        ['Ratings-Research (Gemini)','monthly-ratings-research.yml','monatlich 1. um 02:00','ratings_external.json'],
        ['Anbieter-Sitemaps (URLs)','monthly-urls.yml','monatlich 1. um 06:45','providers.json'],
        ['Berater-Daten','berater-update.yml','manuell (workflow_dispatch)','berater_data.json']
      ])+
      note("Der Nightly startet um 04:30 UTC bewusst NACH dem GEO-Crawl (23:10 UTC), damit Snapshot, SoV und Korrelation mit den GEO-Daten desselben Tages rechnen. Alle schreibenden Workflows teilen die Concurrency-Gruppe <code>repo-writes</code> und sind gestaffelt, weil diese Gruppe nur einen Pending-Slot hat.")+
      warn("Nicht ins Repo pushen, waehrend ein Workflow laeuft — dessen Commit scheitert sonst am Fast-Forward.");
  }

  /* ============================================================
     Kapitel 3 — Metriken & Definitionen
     ============================================================ */
  function kap3(){
    return tbl(["Metrik","Definition"],[
      ['Share of Voice (SoV)','Anteil der Marken-Nennungen an allen Marken-Nennungen, <b>je Produkt&times;Engine auf die Summe der Markennennungen normiert</b> (Summe = 100&nbsp;%). Ueber Produkte gemittelt.'],
      ['Visibility / Appearance-Rate','Anteil der Prompts/Antworten je Thema, in denen die Marke ueberhaupt erscheint.'],
      ['Position / avg_rank','Durchschnittliche Rang-Position der Marke innerhalb der Antwort (frueher genannt = besser).'],
      ['citation_rate','Anteil der Antworten, in denen mindestens eine Quelle der Marke zitiert wird.'],
      ['Footprint','<b>footprint_pct</b> (Peec, 26 Marken) bzw. <b>cite_share</b> (eigener Crawl, 7 Marken): Anteil der markeneigenen Domain an allen zitierten URLs je Thema.'],
      ['Peec-Sentiment','Skala 0&ndash;100, hoeher = positiver. ERGO ~51 (neutral). <b>&ne; Kundenbewertungs-Sentiment</b> des eigenen Crawls (Check24/Google-Reviews) — nie mischen.'],
      ['Empfehlungsrate (Nordstern)','Anteil der Prompts je Thema, in denen die Marke <b>positiv</b> genannt wird. Noch nicht messbar — braucht Prompt-Level-Sentiment.']
    ])+
    h("Kreuz-Matrix je Thema (erwaehnt &times; zitiert)")+
    'Zwei Achsen kombiniert. Schwellen: <b>erwaehnt</b> ab &ge;&nbsp;10&nbsp;% Appearance, <b>zitiert</b> ab &ge;&nbsp;5&nbsp;% Zitatanteil.'+
    tbl(["","zitiert","nicht zitiert"],[
      ['<b>erwaehnt/empfohlen</b>','Idealzustand','Wirkung da, aber fragil'],
      ['<b>nicht erwaehnt</b>','Potenzial ungenutzt','Handlungsbedarf']
    ])+
    note("Nuancen: Mention ohne eigenes Zitat moeglich (Trainingswissen / Portal-Zitat); Zitat ohne Mention ebenso (ergo.de zitiert, aber Allianz empfohlen).");
  }

  /* ============================================================
     Kapitel 4 — Statistische Verfahren (Herzstueck)
     ============================================================ */
  function kap4(){
    return 'Statistik-Ground-Truth: <code>scripts/correlation_impact.py</code> (im Nightly ausgefuehrt). Jedes Verfahren mit Was / Warum / Wo im Dashboard / Interpretation / Grenzen.'+
    method({ name:"1 · Mundlak / CRE-Level-Modell (Between / Within)", badge:badge("Kernmodell","info"),
      was:"Correlated-Random-Effects-Modell mit Zerlegung in Between-Effekt (Unterschiede <i>zwischen</i> Marken) und Within-Effekt (Bewegung <i>innerhalb</i> einer Marke ueber die Themen). Beobachtungseinheit = Zelle Marke&times;Thema.",
      warum:"CRE statt reiner Fixed Effects, weil hier gerade die <b>Between-Effekte interessieren</b> (welche Marke ist strukturell sichtbarer) — FE wuerde sie wegprojizieren. Mundlak-Terme (Zell-Mittel je Marke) trennen Between von Within sauber.",
      wo:"Reiter Korrelationsanalyse, Block 2 (Treiber-Forest) und Block 1 (Kernbefunde).",
      interp:"Effekt in <b>pp Sichtbarkeit je +1&nbsp;SD des Treibers</b>. Peec-26-Footprint-Between: coef 0,607 (+2,96&nbsp;pp/SD). <span style='color:#9ca3af'>("+STAND+", Peec-intern).</span>",
      grenzen:"Zusammenhang, kein Kausalnachweis. Between-Effekte sind querschnittlich — Confounder auf Markenebene bleiben moeglich." })+
    method({ name:"2 · Wild-Cluster-Bootstrap", badge:badge("Signifikanz-Mass","info"),
      was:"Wild-Cluster-Bootstrap auf Markenebene (Cluster = Marke, Rademacher-Gewichte &plusmn;1). Bei G&le;12 Clustern <b>vollstaendige Enumeration aller 2^G Vorzeichen-Vektoren</b> (exakt, reproduzierbar, kein Seed); bei G&gt;12 Sampling mit Seed 42 und 4095 Draws.",
      warum:"Bei kleiner Cluster-Zahl G sind Cluster-robuste Standardfehler unzuverlaessig — beobachtete SE-Faktoren 0,37&ndash;2,24 ueber die Bloecke (with_peec 2,04 / 2,24). Der Bootstrap ist dann das belastbare Mass, nicht die SE.",
      wo:"Block 2 (Forest, Chip 'Wild-p') und Block 5 (Methodik).",
      interp:"Kleiner p = robust gegen das Weglassen einzelner Marken. Peec-26-Footprint: <b>Wild-p 0,0063</b> ("+STAND+").",
      grenzen:"Exakter <b>p-Boden = 1/2^G</b>. Bei G=7 (eigener Crawl) also <b>1/128 = 0,0078</b> — sechs Effekte sitzen auf diesem Boden, 'signifikanter geht rechnerisch nicht'." })+
    method({ name:"3 · Benjamini-Hochberg-FDR", badge:badge("Mehrfachtest-Korrektur","info"),
      was:"False-Discovery-Rate-Korrektur (Benjamini-Hochberg) ueber die Wild-p, angewandt <b>je Modellblock</b>.",
      warum:"Nicht ueber prob_direction (Posterior-Mass) korrigiert, weil dieses bei kleiner Fallzahl fast immer 1,0 ist — im JSON standen <b>61 von 130</b> Effekten auf exakt P=1,0. Die Wild-p tragen echte Information, das Posterior nicht.",
      wo:"Block 1/2 (Badge 'FDR-q') und Block 5.",
      interp:"q = erwarteter Falsch-Entdeckungs-Anteil. Peec-26-Footprint: <b>FDR-q 0,013</b> ("+STAND+").",
      grenzen:"Die Kanaele sind <b>nicht unabhaengig</b> (combined mischt grounded und ungrounded) — q-Werte um 0,05 nicht ueberinterpretieren." })+
    method({ name:"4 · Leave-one-out-Vorzeichenstabilitaet", badge:badge("Robustheit","info"),
      was:"Jede Marke einmal weglassen, das Modell refitten, pruefen ob das Vorzeichen des Between-Effekts stabil bleibt (between_loo).",
      warum:"Bei kleinem G koennen einzelne Marken einen Befund allein tragen. Beispiel: Der frühere Preis-Befund kippte ohne Signal Iduna (coef &minus;5,87, p 0,52; ohne cite_share sogar Vorzeichenwechsel auf +0,81).",
      wo:"Block 1/2 (Chip 'LOO stabil / instabil'), Block 5.",
      interp:"Peec-26-Footprint: in <b>allen 26 Refits</b> vorzeichenstabil ("+STAND+").",
      grenzen:"Prueft nur das Vorzeichen, nicht die Effektgroesse; bei sehr kleinem G bleibt jeder LOO-Test wenig trennscharf." })+
    method({ name:"5 · Cross-Source-Validierung", badge:badge("externer Gegentest","ok"),
      was:"Peec-Footprint (UI-Scraping) gegen den eigenen Gemini-SoV (eigene API) — zwei getrennte Messsysteme, keine gemeinsamen Antworten.",
      warum:"Der zirkularitaetsaermste Test des Projekts: nicht aus denselben Antworten gerechnet.",
      wo:"Block 1 (Karte 'Unabhaengiger Gegentest'), Block 5.",
      interp:"r = 0,82 ueber 7 Marken (p 0,023); r = 0,73 ueber 70 Zellen.",
      grenzen:"<b>LOO-fragil:</b> ohne Allianz faellt r auf 0,60 (p 0,21, n=6). Spearman p 0,052, Fisher-KI bei n=7 sehr breit ([0,18; 0,97]). Der plausibelste Befund des Projekts — aber kein Fels." })+
    method({ name:"6 · Zirkularitaets-Messung", badge:badge("Diagnostik","info"),
      was:"citation_engine_mix (welche Engine die Zitate liefert) und share_same_engine je Kanal — misst, wie stark Zielgroesse und Footprint aus derselben Engine stammen.",
      warum:"Macht die Selbstbezueglichkeit explizit statt sie zu behaupten. citation_engine_mix (Stand Lauf 17.07.): ChatGPT 1467 / Gemini 60.",
      wo:"Block 5 (Zirkularitaets-Zeilen je Kanal).",
      interp:"Eigener Crawl grounded: level 'none' (share_same_engine 0,039); ungrounded: 'high' (0,961); combined: 'high' (1,0). Peec-26 intern: 'high' (Footprint und SoV aus denselben Peec-Antworten). Der externe Gegentest (Verfahren 5) ist der zirkularitaetsarme Kontrapunkt.",
      grenzen:"<b>Rest-Zirkularitaet bleibt:</b> der Peec-Footprint ist ueber alle 5 Engines aggregiert, inkl. Gemini — und Gemini liefert auch die Zielgroesse des eigenen Crawls. Deutlich unabhaengiger als alles andere, aber nicht voellig frei." })+
    method({ name:"7 · Gap-Zerlegung", badge:badge("deskriptiv","muted"),
      was:"Zerlegt den ERGO&rarr;Allianz-Sichtbarkeitsabstand in einen Footprint-erklaerten Teil und einen Rest (allgemeine Markenstaerke).",
      warum:"Zeigt, wie viel des Rueckstands mit steuerbarem Footprint einhergeht.",
      wo:"Block 1 (Karte 'ERGO-Rueckstand'), Block 4 (Ursachen-Wasserfall).",
      interp:"Rueckstand ~12,6&nbsp;pp (Peec grounded), davon ~6,6&nbsp;pp footprint-erklaert ("+STAND+").",
      grenzen:"<b>Deskriptive Zerlegung, kein Kausalnachweis.</b> 'Autoritaet' = Groesse + Footprint als EINE Stufe, weil beide bei 7 Marken nicht trennbar sind." })+
    method({ name:"8 · Event-Study (multivariat) mit Out-of-Sample-Validierung", badge:badge("Nullbefund","muted"),
      was:"Multivariate Event-Study auf Interventionen/Marktereignisse, mit Out-of-Sample-Pruefung (r2_oos_vs_baseline) und Placebo-Falsch-Positiv-Rate.",
      warum:"Testet, ob kurzfristige Ereignisse die Sichtbarkeit vorhersagen — und ob das Modell die reine Marken-Basislinie schlaegt.",
      wo:"Block 1 (Karte 'Kurzfrist-Events'), Detail-Auswertungen.",
      interp:"<b>R&sup2;_oos &lt; 0</b> gegen Baseline &rarr; keine Vorhersagekraft &rarr; sauberer <b>Nullbefund</b>; Placebo-FP-Rate als Gegenprobe.",
      grenzen:"Nullbefund heisst 'nicht nachweisbar', nicht 'nachweislich null'. Kurze Historie limitiert die Power." })+
    method({ name:"9 · DiD / Interventionsanalyse", badge:badge("geplant / limitiert","warn"),
      was:"Difference-in-Differences auf einzelne Interventionen (intervention_analysis.py).",
      warum:"Der einzige Weg zu echter Kausalitaet — wenn genug Panel-Historie vorliegt.",
      wo:"Detail-Auswertungen (Massnahmen-Wirkung).",
      interp:"Derzeit durch die kurze Peec-Historie limitiert.",
      grenzen:"Das Wochen-Panel waechst erst seit 18.07. (versionierte Snapshots); belastbare Staggered-DiD-Aussagen brauchen mehr Wochen." })+
    method({ name:"10 · Spearman-Rang-Konvergenz (Quellen-Vergleich)", badge:badge("Konsistenz","info"),
      was:"Vergleich Peec vs. eigener Crawl je Thema ueber die Spearman-Rangkorrelation der Markenreihenfolge (statt der Niveaus).",
      warum:"<b>Raenge statt Niveaus</b>, weil 26 vs. 7 Marken im Nenner die absoluten SoV-Niveaus mechanisch verschieben — die Reihenfolge ist die faire Vergleichsgroesse.",
      wo:"Block 3 (Quellen-Vergleich, Spalte 'Rang-&rho;', Gesamt-r-Badge).",
      interp:"&rho; &ge; 0,8 = beide Quellen sehen dieselbe Markenreihenfolge &rarr; Messung validiert.",
      grenzen:"Rangkorrelation ignoriert Abstaende; grosse ERGO-Niveau-Differenzen bleiben Pruef-Kandidaten." });
  }

  /* ============================================================
     Kapitel 5 — Interpretationsleitfaden
     ============================================================ */
  function kap5(){
    return h("Was gilt")+
      '<ul style="margin:4px 0;padding-left:18px">'+
        '<li><b>Footprint &rarr; Sichtbarkeit</b> ist belastbar bei n=26: Wild-p 0,0063, FDR-q 0,013, LOO-stabil ('+STAND+', Peec-intern; externer Gegentest r 0,82, aber LOO-fragil).</li>'+
      '</ul>'+
      h("Was nicht gilt")+
      '<ul style="margin:4px 0;padding-left:18px">'+
        '<li><b>Preis nicht identifizierbar</b> bei 7 Marken: Preis, Groesse und Footprint sind statistisch nicht trennbar. Der scheinbare Effekt entstand nur durch <b>cite_share als bad control</b> (steckt mechanisch in der Zielgroesse); zudem sind Engine und Grounding perfekt kollinear (grounded = nur Gemini, ungrounded = nur ChatGPT). relprice allein: coef &minus;10,49, p 0,27.</li>'+
        '<li><b>Groesse</b> ist kein eigenstaendiger Effekt (Wild-p 0,61 bei n=26) — der Footprint absorbiert sie.</li>'+
        '<li><b>Events</b>: Nullbefund (R&sup2;_oos &lt; 0).</li>'+
      '</ul>'+
      h("Kernprinzipien")+
      '<ul style="margin:4px 0;padding-left:18px">'+
        '<li><b>Grundsatz "fehlende Daten sind nie Null".</b> Ein ausgefallener Kanal darf nie als '+'"0,0 &mdash; gesichert kein Effekt" erscheinen. Roter Faden fast aller Bugs im Projekt.</li>'+
        '<li><b>Zusammenhang &ne; Kausalitaet.</b> Alle Level-Modell-Befunde sind Korrelationen; Kausalitaet braucht DiD.</li>'+
        '<li><b>Befunde, die zur Geschichte passen, am haertesten testen.</b> Der Preis-Befund fuehlte sich richtig an (p 0,023) und war trotzdem ein Artefakt.</li>'+
      '</ul>'+
      h("Bekannte Verzerrungsquellen")+
      '<ul style="margin:4px 0;padding-left:18px">'+
        '<li><b>Eine Engine je Kanal &rarr; Kanal &equiv; Engine</b> (grounded = Gemini, ungrounded = ChatGPT): jeder Confounder, der die Engines unterschiedlich trifft, laedt auf dem Kanal-Koeffizienten.</li>'+
        '<li><b>Peec-Fenster ~30 Tage rollierend</b> (vier Wochen): Trend-/Lag-Aussagen brauchen mehr Wochen.</li>'+
        '<li><b>ChatGPT-UI vs. API:</b> Peec misst ChatGPT ueber die UI, der eigene Crawl ueber die API — nicht dieselbe Umgebung.</li>'+
      '</ul>';
  }

  /* ============================================================
     Kapitel 6 — Aenderungs-Log der Methodik
     ============================================================ */
  function kap6(){
    return tbl(["Datum","Aenderung"],[
      ['17.07.2026','<b>Statistik-Haertung:</b> Wild-Cluster-Bootstrap, Benjamini-Hochberg-FDR und Leave-one-out ersetzen die Posterior-P (61&times; exakt 1,0). Von 15 '+'"sehr sicheren" Between-Effekten (P&ge;0,99) ueberleben nur <b>8 von 15</b>; Groesse und Preis fallen. Zirkularitaet erstmals gemessen; erfundenes CI-Band entfernt.'],
      ['18.07.2026','<b>Peec-26-Modell</b> (peec26_model): Footprint&rarr;SoV ueber 286 Zellen / 26 Marken / 11 Themen — Wild-p 0,0063, FDR-q 0,013, LOO-stabil. Wild-Bootstrap kann jetzt G&gt;12 (Rademacher-Sampling). Reiter-Umbauten (Korrelationsanalyse v5, LLM-Sichtbarkeit) + Snapshot-Versionierung (Wochen-Panel).']
    ]);
  }

  /* ============================================================
     Section-Inhalt
     ============================================================ */
  function sectionHTML(){
    return '<div id="dokuInner" class="bg-white rounded-xl shadow p-6 mb-6" style="max-width:980px">'+
      '<div style="margin-bottom:14px">'+
        '<h3 style="font-size:18px;font-weight:800;margin:0;color:#1a1a2e">📖 Dokumentation &mdash; Methodik des LLM-Cockpits</h3>'+
        '<p style="font-size:12px;color:#6b7280;margin:4px 0 0">Fuer Statistiker, Mathematiker und Aktuare: praezise, ehrlich, mit allen Einschraenkungen. Zahlen aus den Uebergaben 17./18.07.2026 und <code>correlation_impact.py</code>; dynamische Groessen sind als '+'"'+STAND+'" gekennzeichnet.</p>'+
      '</div>'+
      chapter("dokuKap1","1 · Ueberblick &amp; Datenfluesse", true, kap1())+
      chapter("dokuKap2","2 · Aktualisierungs-Rhythmen", false, kap2())+
      chapter("dokuKap3","3 · Metriken &amp; Definitionen", false, kap3())+
      chapter("dokuKap4","4 · Statistische Verfahren", false, kap4())+
      chapter("dokuKap5","5 · Interpretationsleitfaden", false, kap5())+
      chapter("dokuKap6","6 · Aenderungs-Log der Methodik", false, kap6())+
    '</div>';
  }

  /* ============================================================
     Tab-Integration (additiv, idempotent, rebuild-sicher)
     ============================================================ */
  function showDoku(){
    // alle Content-Sections verstecken
    [].slice.call(document.querySelectorAll('section[data-content]')).forEach(function(s){ s.style.display="none"; });
    var sec=document.getElementById("dokuSection"); if(sec) sec.style.display="";
    // alle Tab-Buttons inaktiv, unseren aktiv
    [].slice.call(document.querySelectorAll('.tab-btn')).forEach(function(b){
      if(b.classList.contains("tab-active")){ b.classList.remove("tab-active"); b.classList.add("tab-inactive"); }
    });
    var btn=document.getElementById("dokuTabBtn");
    if(btn){ btn.classList.remove("tab-inactive"); btn.classList.add("tab-active"); }
  }
  function hideDoku(){
    var sec=document.getElementById("dokuSection"); if(sec) sec.style.display="none";
    var btn=document.getElementById("dokuTabBtn");
    if(btn){ btn.classList.remove("tab-active"); btn.classList.add("tab-inactive"); }
  }

  function ensureButton(){
    if(document.getElementById("dokuTabBtn")) return true;
    var ref=document.querySelector('[data-tab="overview"]');
    if(!ref || !ref.parentNode) return false;
    var btn=document.createElement("button");
    btn.id="dokuTabBtn";
    btn.className=(ref.className||"tab-btn").replace(/tab-active/g,"tab-inactive");
    if(btn.className.indexOf("tab-btn")<0) btn.className+=" tab-btn";
    if(btn.className.indexOf("tab-inactive")<0) btn.className+=" tab-inactive";
    btn.setAttribute("data-tab","doku");
    btn.innerHTML="📖 Dokumentation";
    btn.addEventListener("click", function(e){ e.preventDefault(); showDoku(); });
    ref.parentNode.appendChild(btn);
    return true;
  }
  function ensureSection(){
    if(document.getElementById("dokuSection")) return true;
    var ref=document.querySelector('section[data-content="overview"]');
    if(!ref || !ref.parentNode) return false;
    var sec=document.createElement("section");
    sec.id="dokuSection";
    sec.setAttribute("data-content","doku");
    sec.style.display="none";
    sec.innerHTML=sectionHTML();
    ref.parentNode.appendChild(sec);
    return true;
  }
  function wireOtherButtons(){
    // Klick auf JEDEN anderen .tab-btn versteckt unsere Section wieder.
    [].slice.call(document.querySelectorAll('.tab-btn')).forEach(function(b){
      if(b.id==="dokuTabBtn") return;
      if(b.getAttribute("data-doku-wired")==="1") return;
      b.setAttribute("data-doku-wired","1");
      b.addEventListener("click", function(){ hideDoku(); });
    });
  }

  function build(){
    var okB=ensureButton();
    var okS=ensureSection();
    if(okB) wireOtherButtons();
    return okB && okS;
  }

  ready(function(){
    var tries=0;
    (function wait(){
      tries++;
      var done=build();
      // Auch nach Erfolg weiterlaufen lassen, damit spaet gebaute Buttons
      // (nav_redesign.js) verkabelt werden — bis max. ~12 s.
      if(tries<40) setTimeout(wait,300);
    })();
    // Falls die Tab-Leiste komplett neu aufgebaut wird: bei jedem Klick
    // auf irgendeinen Tab-Button unsere Verkabelung nachziehen.
    document.addEventListener("click", function(e){
      var t=e.target;
      if(t && t.closest && t.closest('.tab-btn')){ setTimeout(function(){ ensureButton(); wireOtherButtons(); },50); }
    }, true);
  });

  // Test-Hook (nur fuer jsdom)
  if(typeof module!=="undefined" && module.exports){ module.exports={ build:build, showDoku:showDoku, hideDoku:hideDoku }; }
})();
