/* ============================================================
   ERGO LLM-Cockpit — Reiter "Dokumentation" (Runtime-Modul, 18.07.2026)
   -----------------------------------------------------------------
   Methodik-Doku fuer Statistiker / Aktuare: praezise, ehrlich, mit
   allen Einschraenkungen. Muster uebernommen aus korrelation_upgrade.js
   (IIFE, "use strict", ready()/Retry, Inline-Styles, Karten-Look,
   ERGO-Rot #dc0028).

   DYNAMISCH (18.07.2026): Die Kennzahlen im Text werden bei JEDEM
   Seitenaufruf aus den Live-Daten gezogen —
     window.CORRELATION_IMPACT (level_model.peec26_model /
       cross_source_validation / citation_engine_mix / validation /
       multivariate; Muster p26Get/xsrcGet aus korrelation_upgrade.js),
     GEO_SNAPSHOT via snapData() (lexikalisch, sonst window),
     window.PEEC_DATA (as_of/window).
   Jede dynamische Zahl traegt ein Herkunfts-Label: dynamisch ->
   "Stand: <Datum>", fehlend -> "Auditwert 18.07.2026". Statische
   Methodik-Texte (Formeln, p-Boden 1/2^G=0,0078 bei G=7 usw.) bleiben
   statisch — das sind Eigenschaften des Verfahrens, keine Daten.
   Re-Render: beim showDoku()-Klick und im ready()-Retry wird dokuInner
   neu gerendert (idempotent, billig; NIE Null/NaN — num()-Guards).

   Additiv & rebuild-sicher (Tab-Button + Section wie zuvor).
   ============================================================ */
(function () {
  "use strict";
  function ready(fn){ if(document.readyState!=="loading") fn(); else document.addEventListener("DOMContentLoaded",fn); }

  var RED="#dc0028";
  var AUDIT="Auditwert 18.07.2026";

  /* ---------- Zahlen-/Datum-Helfer (Muster aus korrelation_upgrade.js) ---------- */
  function num(v,d){ if(v==null||isNaN(v)) return "—"; d=(d==null?1:d); return (Math.round(v*Math.pow(10,d))/Math.pow(10,d)).toFixed(d).replace(".",","); }
  function fmtDate(s){ var m=/^(\d{4})-(\d{2})-(\d{2})/.exec(String(s==null?"":s)); return m?(m[3]+"."+m[2]+"."+m[1]):""; }
  // Herkunfts-Label: dynamisch -> "Stand: <Datum>", sonst Auditwert.
  function srcOf(dyn,date){ return '<span style="color:#9ca3af">('+(dyn?("Stand: "+(date||"aktueller Nightly")):AUDIT)+')</span>'; }

  /* ---- Statische Auditwerte (18.07.2026) als Fallback, solange die neuen
         Felder noch nicht im Nightly-JSON stehen. NIE als Nullen ausgeben.
         (Werte identisch zu korrelation_upgrade.js.) ---- */
  var FB = {
    peec26: { eff:2.96, coef:0.607, wild_p:0.0063, fdr_q:0.013,
              loo:{min:0.42,max:0.65,sign_stable:true}, size_wild_p:0.61,
              brand_r:0.90, brand_rho:0.35, gap:12.64, foot:6.63,
              n_cells:286, n_brands:26, n_topics:11, leader:"Allianz" },
    xsrc:   { r_brands:0.823, p_brands:0.023, n_brands:7, r_cells:0.728, n_cells:70,
              loo_r:0.597, loo_p:0.21 }
  };

  /* ---------- Daten-Resolver mit Fallback (kopiert aus korrelation_upgrade.js) ---------- */
  function p26Get(C){
    var p=((C||{}).level_model||{}).peec26_model;
    if(p && p.available){
      var be=(((p.drivers_eff||{}).peec_foot||{}).between)||{};
      /* gap_decomposition ist im aktuellen Nightly null - die Zerlegung steht in
         gap_neutral (branding-neutral gerechnet). Der Korrelations-Reiter wurde
         darauf umgestellt, die Doku nicht: Kapitel 7 zeigte deshalb 'Rueckstand
         ~— pp'. Der Fallback griff nicht, weil available=true ist. (Fix 10.08.2026) */
      var gd=p.gap_neutral||p.gap_decomposition||{};
      return { dyn:true, eff:be.effect_std_pp, coef:be.coef,
        wild_p:(p.wild_p||{}).peec_foot, fdr_q:(p.fdr_q||{}).peec_foot,
        loo:p.between_loo||be.between_loo||FB.peec26.loo, size_wild_p:(p.wild_p||{}).size,
        brand_r:(p.brand_level||{}).pearson_r, brand_rho:(p.brand_level||{}).spearman_r,
        gap:gd.actual_gap_pp, foot:((gd.contrib_pp||{}).peec_foot),
        n_cells:p.n_cells, n_brands:p.n_brands, n_topics:p.n_topics,
        leader:p.leader_neutral||p.leader||"Allianz" };
    }
    return Object.assign({dyn:false},FB.peec26);
  }
  function xsrcGet(C){
    var x=((C||{}).level_model||{}).cross_source_validation;
    if(x && x.available){
      return { dyn:true, r_brands:x.pearson_r_brands, r_cells:x.pearson_r_cells,
               n_brands:x.n_brands, n_cells:x.n_cells };
    }
    return Object.assign({dyn:false},FB.xsrc);
  }
  // Nordstern "Empfehlungsrate light" (Naeherung): geo_wirkung.js cacht
  // data/peec_nordstern.json auf window.__GW_NS. Dynamisch lesen, sonst Fallback
  // (Stand 18.07.2026) — nie Nullen. Muster wie p26Get/xsrcGet.
  function nsGet(){
    var j=window.__GW_NS;
    function grd(node){ var v=node&&node.grounded; return (v&&!v.keine_daten&&v.empfehlungsrate_light_pct!=null)?v.empfehlungsrate_light_pct:null; }
    if(j && j.ergo){
      var e=grd(j.ergo);
      if(e!=null) return { dyn:true, date:fmtDate(j.as_of), ergo:e, allianz:grd(j.allianz_benchmark) };
    }
    return { dyn:false, date:"18.07.2026", ergo:7.6, allianz:10.2 };
  }
  // dashboard_v3 haelt GEO_SNAPSHOT als top-level `let` -> nicht auf window.
  // Erst lexikalische Bindung versuchen, dann window (health_banner.js spiegelt).
  function snapData(){ try{ if(typeof GEO_SNAPSHOT!=="undefined" && GEO_SNAPSHOT) return GEO_SNAPSHOT; }catch(e){} return window.GEO_SNAPSHOT||null; }

  /* ---------- Live-Werte fuer den Doku-Text buendeln (Render-Zeitpunkt) ---------- */
  function resolve(){
    var C=window.CORRELATION_IMPACT||{};
    var lm=C.level_model||{};
    var P=p26Get(C), X=xsrcGet(C);
    var val=C.validation||{}, mv=C.multivariate||{}, mix=lm.citation_engine_mix||{};
    var g=snapData(), PD=window.PEEC_DATA||{};
    function sh(node){ return (node&&node.circularity)?node.circularity.share_same_engine:null; }
    var shG=sh(lm.grounded), shU=sh(lm.ungrounded), shC=sh(lm.combined);
    var circDyn=(shG!=null||shU!=null||shC!=null);
    var oos=(val.out_of_sample||{}).r2_oos_vs_baseline;
    var plac=val.placebo_false_positive_rate, npts=mv.n_points;
    return {
      C:C, P:P, X:X,
      cDate:fmtDate(C.generated_at),
      gDate:fmtDate(g&&(g.finished_at||g.started_at)),
      pDate:fmtDate(PD.as_of||PD.generated_at||PD.date),
      peecWin:(PD.window!=null?PD.window:PD.window_days),
      shG:(shG!=null?shG:0.039), shU:(shU!=null?shU:0.961), shC:(shC!=null?shC:1.0), circDyn:circDyn,
      mixCg:(mix.chatgpt!=null?mix.chatgpt:1467), mixGe:(mix.gemini!=null?mix.gemini:60),
      mixDyn:(mix.chatgpt!=null||mix.gemini!=null),
      oos:oos, plac:plac, npts:npts, evDyn:(oos!=null||plac!=null||npts!=null),
      NS:nsGet()
    };
  }
  function standLine(R){
    function part(name,date){ return name+" "+(date?("Stand "+date):AUDIT); }
    return note("Datenstand — "+part("eigener Crawl:",R.gDate)+" · "+part("Korrelations-Analyse:",R.cDate)+
      " · "+part("Peec:",R.pDate)+(R.peecWin?(" (Fenster "+R.peecWin+(/^[0-9]+$/.test(String(R.peecWin))?" Tage":"")+")"):"")+".");
  }

  /* Frische je Daten-Element (10.08.2026).
     scripts/pipeline_health.py schreibt data/pipeline_health.json bei JEDEM Nightly -
     und bis heute hat es niemand gelesen. Der Frische-Status faerbte nur den
     Workflow rot; im Cockpit selbst war er unsichtbar. Genau derselbe Fehlertyp wie
     bei chatgpt_web: erhoben, aber nicht angeschlossen. Jetzt steht er dort, wo man
     ihn sucht - im Doku-Reiter unter dem Datenstand. */
  function frischeBlock(){
    /* Eigene esc-Kopie: dieses Modul hat keine. Der erste Entwurf rief ein globales
       esc() auf, das es hier nicht gibt - der ReferenceError liess den GESAMTEN
       Doku-Reiter leer, weil renderInner() bei einem Fehler abbricht. Genau die
       Sorte stiller Ausfall, die heute schon zweimal aufgetaucht ist; hier hat der
       headless-Test sie gefangen. */
    function esc(x){ return String(x==null?'':x).replace(/[&<>"]/g,function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
    var H=window.__PIPELINE_HEALTH;
    if(!H || !H.elements || !H.elements.length){
      return note("Frische je Daten-Element: data/pipeline_health.json nicht geladen — die Datei entsteht im Nightly.");
    }
    var alt_=H.elements.filter(function(e){return e.stale;});
    var kopf = alt_.length
      ? '<div style="font-size:12.5px;font-weight:700;color:#b91c1c;margin-bottom:6px">'
        + alt_.length + ' von ' + H.elements.length + ' Daten-Elementen sind veraltet</div>'
      : '<div style="font-size:12.5px;font-weight:700;color:#067d3a;margin-bottom:6px">Alle '
        + H.elements.length + ' Daten-Elemente sind frisch</div>';
    var zeilen = H.elements.map(function(e){
      var alter=(e.age_days==null)?null:Number(e.age_days);
      var farbe = e.stale ? '#b91c1c' : (alter!=null && e.max_age && alter > e.max_age*0.7 ? '#b45309' : '#6b7280');
      return '<tr style="border-bottom:1px solid #f4f4f6">'
        + '<td style="padding:4px 8px">'+esc(e.name)+'</td>'
        + '<td style="padding:4px 8px;color:#9ca3af;font-size:11px">'+esc(e.file||'')+'</td>'
        + '<td style="padding:4px 8px;text-align:right;color:'+farbe+'">'
          + (alter==null?'keine Angabe':(alter.toFixed(1)+' T.'))+'</td>'
        + '<td style="padding:4px 8px;text-align:right;color:#9ca3af">Grenze '+(e.max_age!=null?e.max_age:'—')+'</td>'
        + '<td style="padding:4px 8px;color:'+farbe+'">'+(e.stale?'veraltet':'frisch')+'</td></tr>';
    }).join('');
    return kopf
      + '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12px">'
      + '<thead><tr style="text-align:left;color:#9ca3af;font-size:11px">'
      + '<th style="padding:4px 8px">Element</th><th style="padding:4px 8px">Datei</th>'
      + '<th style="padding:4px 8px;text-align:right">Alter</th><th style="padding:4px 8px;text-align:right">Grenze</th>'
      + '<th style="padding:4px 8px">Status</th></tr></thead><tbody>'+zeilen+'</tbody></table></div>'
      + note('Aus data/pipeline_health.json, geschrieben im Nightly (Stand '
             + esc(String(H.generated_at||'').slice(0,16).replace('T',' ')) + ' UTC). Die Grenzen für GEO-Snapshot '
             + 'und SoV-Historie stehen seit dem 10.08.2026 auf 9 Tage statt 2 — der eigene Crawl läuft seitdem '
             + 'wöchentlich, und ein Alarm, der jede Woche sechs Tage lang leuchtet, wird ignoriert.');
  }

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
  function kap1(R){
    return h("Was gemessen wird")+
      'Das Cockpit misst die <b>LLM-Sichtbarkeit</b> der ERGO und ihrer Wettbewerber: In welchem Umfang und wie tauchen die Marken in den Antworten grosser Sprachmodelle auf Versicherungs-Fragen auf. Ziel ist ein <b>Treibermodell</b>, das statistisch benennt, was bessere Sichtbarkeit erklaert.'+
      h("Zwei-Quellen-Prinzip")+
      'Zwei unabhaengige Messsysteme messen dieselbe Sache — das ist die zentrale Absicherung gegen Zirkularitaet:'+
      tbl(["Quelle","Rolle","Marken","Engines","Erhebung"],[
        ['<b>Peec AI</b> (fuehrend)','Primaerquelle LLM-Sichtbarkeit',num(R.P.n_brands,0),'5 (inkl. Google AI Overview / AI Mode)','UI-Scraping, woechentlich'],
        ['Eigener API-Crawl','Backup & Konsistenzpruefung','25','3 (Gemini und Perplexity mit Websuche, ChatGPT ohne)','eigene API, woechentlich (seit 10.08.2026)']
      ])+
      note("Peec fuehrt, weil es mehr Marken und mehr Engines abdeckt; der eigene Crawl liefert den zirkularitaetsarmen externen Gegentest (Kapitel 4, Verfahren 5).")+
      h("Wirkungs- vs. Hebelmetrik")+
      'Zwei Metrik-Familien werden bewusst getrennt gehalten:'+
      info('<b>Brand Mention / Share of Voice = Wirkungsmetrik.</b> Kommt die Marke in der Antwort selbst vor? Das liest der Nutzer — die eigentliche Empfehlung. Fein aufgeschluesselt nach Position in der Antwort und Sentiment.')+
      info('<b>Zitations-Footprint = Frueh-/Hebelindikator.</b> <b>Definition:</b> Anteil der markeneigenen Domain (z.&nbsp;B. ergo.de) an allen zitierten URLs je Thema. Nachgelagert, aber steuerbar: die Antwortformulierung laesst sich nicht beeinflussen, die Zitierfaehigkeit der eigenen Inhalte schon.')+
      warn('<b>Kausalkette:</b> Grounded LLMs generieren aus den abgerufenen Quellen. Ohne Quellpraesenz kaum Empfehlung — deshalb ist der Footprint Fruehindikator <i>und</i> Stellhebel, aber nie ein Ersatz fuer die Wirkungsmessung.')+
      standLine(R);
  }

  /* ============================================================
     Kapitel 2 — Aktualisierungs-Rhythmen
     ============================================================ */
  function kap2(R){
    return 'Alle Rhythmen aus den Workflow-YMLs des Repos (bzw. der geo-visibility-tool-/Cowork-Pipeline). Zeiten in <b>UTC</b>.'+
      h("Kommt auch wirklich Frisches an?")+
      'Rhythmen sagen, was laufen SOLL. Der Block hier sagt, was tatsächlich ankommt:'+
      frischeBlock()+
      tbl(["Was","Workflow / Task","Rhythmus (UTC)","Zieldatei(en)"],[
        ['Eigener LLM-Crawl','analyze.yml <span style="color:#9ca3af">(geo-visibility-tool)</span>','woechentlich So 23:10','geo_snapshot.json (in den Nightly geladen)'],
        ['Cockpit-Nightly<br><span style="color:#9ca3af;font-weight:400">Snapshot laden, SoV-Historie, Korrelations-/Impact-Analyse, Interventionen, Check24-Preise, Ratings, Sentiment, Presse, Pipeline-Health</span>','nightly-update.yml','taeglich 05:30','correlation_impact.json, geo_snapshot.json, sov_history.jsonl, intervention_results.json u.&nbsp;a.'],
        ['Peec-Export<br><span style="color:#9ca3af;font-weight:400">versionierte Snapshots + Wochen-Panel (seit 18.07.)</span>','Cowork-Task peec-weekly-export','woechentlich Mo 07:07','peec_snapshots/YYYY-MM-DD_*.csv, peec_history_weekly.csv, peec_cells.csv, peec_footprint.json'],
        ['Check24-Preise & Reviews','weekly-prices.yml','woechentlich Mo 05:45','price_comparison.json, review_history.json'],
        ['Berater Google Reviews','berater-reviews.yml','woechentlich So 05:00','berater_reviews.json, brand_reviews.json'],
        ['Ratings-Research (Gemini)','monthly-ratings-research.yml','monatlich 1. um 02:00','ratings_external.json'],
        ['Anbieter-Sitemaps (URLs)','monthly-urls.yml','monatlich 1. um 06:45','providers.json'],
        ['Berater-Daten','berater-update.yml','manuell (workflow_dispatch)','berater_data.json']
      ])+
      note("Der Nightly startet um 05:30 UTC bewusst NACH dem GEO-Crawl (23:10 UTC), damit Snapshot, SoV und Korrelation mit den GEO-Daten desselben Tages rechnen. Alle schreibenden Workflows teilen die Concurrency-Gruppe <code>repo-writes</code> und sind gestaffelt, weil diese Gruppe nur einen Pending-Slot hat.")+
      warn("Nicht ins Repo pushen, waehrend ein Workflow laeuft — dessen Commit scheitert sonst am Fast-Forward.")+
      standLine(R);
  }

  /* ============================================================
     Kapitel 3 — Metriken & Definitionen  (statisch: Definitionen)
     ============================================================ */
  function kap3(R){
    return tbl(["Metrik","Definition"],[
      ['Share of Voice (SoV)','Anteil der Marken-Nennungen an allen Marken-Nennungen, <b>je Produkt&times;Engine auf die Summe der Markennennungen normiert</b> (Summe = 100&nbsp;%). Ueber Produkte gemittelt.'],
      ['Visibility / Appearance-Rate','Anteil der Prompts/Antworten je Thema, in denen die Marke ueberhaupt erscheint.'],
      ['Position / avg_rank','Durchschnittliche Rang-Position der Marke innerhalb der Antwort (frueher genannt = besser).'],
      ['citation_rate','Anteil der Antworten, in denen mindestens eine Quelle der Marke zitiert wird.'],
      ['Footprint','<b>footprint_pct</b> (Peec) bzw. <b>cite_share</b> (eigener Crawl): Anteil der markeneigenen Domain an allen zitierten URLs je Thema.'],
      ['Peec-Sentiment','Skala 0&ndash;100, hoeher = positiver. ERGO ~51 (neutral). <b>&ne; Kundenbewertungs-Sentiment</b> des eigenen Crawls (Check24/Google-Reviews) — nie mischen.'],
      ['Empfehlungsrate (Nordstern)','Anteil der Prompts, in denen die Marke <b>positiv</b> genannt wird — die eigentliche Zielgroesse. <b>Empfehlungsrate light</b> als <b>Naeherung</b> seit 18.07.2026: Nennung <b>und</b> Peec-Sentiment&nbsp;&ge;&nbsp;60. Grounded aktuell ERGO&nbsp;<b>'+num(R.NS.ergo,1)+'&nbsp;%</b> vs. Allianz&nbsp;<b>'+num(R.NS.allianz,1)+'&nbsp;%</b> '+srcOf(R.NS.dyn,R.NS.date)+'. Quelle: <code>data/peec_nordstern.json</code>, woechentlich. <b>Keine echte Empfehlungs-Klassifikation</b> — die braucht NLP auf den Antwort-Volltexten; die Datengrundlage dafuer (mention_contexts &plusmn;1&nbsp;Satz im eigenen Crawl, A.2b) wird seit 19.07.2026 erhoben.']
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
  function kap4(R){
    var P=R.P, X=R.X;
    return 'Statistik-Ground-Truth: <code>scripts/correlation_impact.py</code> (im Nightly ausgefuehrt). Jedes Verfahren mit Was / Warum / Wo im Dashboard / Interpretation / Grenzen. Kennzahlen werden bei jedem Aufruf frisch gezogen; fehlt ein Feld, steht der Auditwert.'+
    method({ name:"1 · Mundlak / CRE-Level-Modell (Between / Within)", badge:badge("Kernmodell","info"),
      was:"Correlated-Random-Effects-Modell mit Zerlegung in Between-Effekt (Unterschiede <i>zwischen</i> Marken) und Within-Effekt (Bewegung <i>innerhalb</i> einer Marke ueber die Themen). Beobachtungseinheit = Zelle Marke&times;Thema.",
      warum:"CRE statt reiner Fixed Effects, weil hier gerade die <b>Between-Effekte interessieren</b> (welche Marke ist strukturell sichtbarer) — FE wuerde sie wegprojizieren. Mundlak-Terme (Zell-Mittel je Marke) trennen Between von Within sauber.",
      wo:"Reiter Korrelationsanalyse, Block 2 (Treiber-Forest) und Block 1 (Kernbefunde).",
      interp:"Effekt in <b>pp Sichtbarkeit je +1&nbsp;SD des Treibers</b>. Peec-26-Footprint-Between: coef "+num(P.coef,3)+" (+"+num(P.eff,1)+"&nbsp;pp/SD). "+srcOf(P.dyn,R.cDate)+" Peec-intern.",
      grenzen:"Zusammenhang, kein Kausalnachweis. Between-Effekte sind querschnittlich — Confounder auf Markenebene bleiben moeglich." })+
    method({ name:"2 · Wild-Cluster-Bootstrap", badge:badge("Signifikanz-Mass","info"),
      was:"Wild-Cluster-Bootstrap auf Markenebene (Cluster = Marke, Rademacher-Gewichte &plusmn;1). Bei G&le;12 Clustern <b>vollstaendige Enumeration aller 2^G Vorzeichen-Vektoren</b> (exakt, reproduzierbar, kein Seed); bei G&gt;12 Sampling mit Seed 42 und 4095 Draws.",
      warum:"Bei kleiner Cluster-Zahl G sind Cluster-robuste Standardfehler unzuverlaessig — beobachtete SE-Faktoren 0,37&ndash;2,24 ueber die Bloecke (with_peec 2,04 / 2,24). Der Bootstrap ist dann das belastbare Mass, nicht die SE.",
      wo:"Block 2 (Forest, Chip 'Wild-p') und Block 5 (Methodik).",
      interp:"Kleiner p = robust gegen das Weglassen einzelner Marken. Peec-26-Footprint: <b>Wild-p "+num(P.wild_p,4)+"</b> "+srcOf(P.dyn,R.cDate)+".",
      grenzen:"Exakter <b>p-Boden = 1/2^G</b>. Bei G=7 (eigener Crawl) also <b>1/128 = 0,0078</b> — sechs Effekte sitzen auf diesem Boden, 'signifikanter geht rechnerisch nicht'." })+
    method({ name:"3 · Benjamini-Hochberg-FDR", badge:badge("Mehrfachtest-Korrektur","info"),
      was:"False-Discovery-Rate-Korrektur (Benjamini-Hochberg) ueber die Wild-p, angewandt <b>je Modellblock</b>.",
      warum:"Nicht ueber prob_direction (Posterior-Mass) korrigiert, weil dieses bei kleiner Fallzahl fast immer 1,0 ist — im JSON standen <b>61 von 130</b> Effekten auf exakt P=1,0. Die Wild-p tragen echte Information, das Posterior nicht.",
      wo:"Block 1/2 (Badge 'FDR-q') und Block 5.",
      interp:"q = erwarteter Falsch-Entdeckungs-Anteil. Peec-26-Footprint: <b>FDR-q "+num(P.fdr_q,3)+"</b> "+srcOf(P.dyn,R.cDate)+".",
      grenzen:"Die Kanaele sind <b>nicht unabhaengig</b> (combined mischt grounded und ungrounded) — q-Werte um 0,05 nicht ueberinterpretieren." })+
    method({ name:"4 · Leave-one-out-Vorzeichenstabilitaet", badge:badge("Robustheit","info"),
      was:"Jede Marke einmal weglassen, das Modell refitten, pruefen ob das Vorzeichen des Between-Effekts stabil bleibt (between_loo).",
      warum:"Bei kleinem G koennen einzelne Marken einen Befund allein tragen. Beispiel: Der frühere Preis-Befund kippte ohne Signal Iduna (coef &minus;5,87, p 0,52; ohne cite_share sogar Vorzeichenwechsel auf +0,81).",
      wo:"Block 1/2 (Chip 'LOO stabil / instabil'), Block 5.",
      interp:"Peec-26-Footprint: in <b>allen "+num(P.n_brands,0)+" Refits</b> vorzeichenstabil "+srcOf(P.dyn,R.cDate)+".",
      grenzen:"Prueft nur das Vorzeichen, nicht die Effektgroesse; bei sehr kleinem G bleibt jeder LOO-Test wenig trennscharf." })+
    method({ name:"5 · Cross-Source-Validierung", badge:badge("externer Gegentest","ok"),
      was:"Peec-Footprint (UI-Scraping) gegen den eigenen Gemini-SoV (eigene API) — zwei getrennte Messsysteme, keine gemeinsamen Antworten.",
      warum:"Der zirkularitaetsaermste Test des Projekts: nicht aus denselben Antworten gerechnet.",
      wo:"Block 1 (Karte 'Unabhaengiger Gegentest'), Block 5.",
      interp:"r = "+num(X.r_brands,2)+" ueber "+num(X.n_brands,0)+" Marken (p "+num(FB.xsrc.p_brands,3)+"); r = "+num(X.r_cells,2)+" ueber "+num(X.n_cells,0)+" Zellen. "+srcOf(X.dyn,R.cDate),
      grenzen:"<b>LOO-fragil:</b> ohne Allianz faellt r auf 0,60 (p 0,21, n=6). Spearman p 0,052, Fisher-KI bei n=7 sehr breit ([0,18; 0,97]). Der plausibelste Befund des Projekts — aber kein Fels." })+
    method({ name:"6 · Zirkularitaets-Messung", badge:badge("Diagnostik","info"),
      was:"citation_engine_mix (welche Engine die Zitate liefert) und share_same_engine je Kanal — misst, wie stark Zielgroesse und Footprint aus derselben Engine stammen.",
      warum:"Macht die Selbstbezueglichkeit explizit statt sie zu behaupten. citation_engine_mix: ChatGPT "+num(R.mixCg,0)+" / Gemini "+num(R.mixGe,0)+". "+srcOf(R.mixDyn,R.cDate),
      wo:"Block 5 (Zirkularitaets-Zeilen je Kanal).",
      interp:"Eigener Crawl grounded: level 'none' (share_same_engine "+num(R.shG,3)+"); ungrounded: 'high' ("+num(R.shU,3)+"); combined: 'high' ("+num(R.shC,3)+"). Peec-26 intern: 'high' (Footprint und SoV aus denselben Peec-Antworten). "+srcOf(R.circDyn,R.cDate)+" Der externe Gegentest (Verfahren 5) ist der zirkularitaetsarme Kontrapunkt.",
      grenzen:"<b>Rest-Zirkularitaet bleibt:</b> der Peec-Footprint ist ueber alle 5 Engines aggregiert, inkl. Gemini — und Gemini liefert auch die Zielgroesse des eigenen Crawls. Deutlich unabhaengiger als alles andere, aber nicht voellig frei." })+
    method({ name:"7 · Gap-Zerlegung", badge:badge("deskriptiv","muted"),
      was:"Zerlegt den ERGO&rarr;Allianz-Sichtbarkeitsabstand in einen Footprint-erklaerten Teil und einen Rest (allgemeine Markenstaerke).",
      warum:"Zeigt, wie viel des Rueckstands mit steuerbarem Footprint einhergeht.",
      wo:"Block 1 (Karte 'ERGO-Rueckstand'), Block 4 (Ursachen-Wasserfall).",
      interp:"Rueckstand ~"+num(P.gap,1)+"&nbsp;pp (Peec grounded), davon ~"+num(P.foot,1)+"&nbsp;pp footprint-erklaert "+srcOf(P.dyn,R.cDate)+".",
      grenzen:"<b>Deskriptive Zerlegung, kein Kausalnachweis.</b> 'Autoritaet' = Groesse + Footprint als EINE Stufe, weil beide bei dieser Fallzahl nicht trennbar sind." })+
    method({ name:"8 · Event-Study (multivariat) mit Out-of-Sample-Validierung", badge:badge("Nullbefund","muted"),
      was:"Multivariate Event-Study auf Interventionen/Marktereignisse, mit Out-of-Sample-Pruefung (r2_oos_vs_baseline) und Placebo-Falsch-Positiv-Rate.",
      warum:"Testet, ob kurzfristige Ereignisse die Sichtbarkeit vorhersagen — und ob das Modell die reine Marken-Basislinie schlaegt.",
      wo:"Block 1 (Karte 'Kurzfrist-Events'), Detail-Auswertungen.",
      interp:"<b>R&sup2;_oos "+(R.oos!=null?num(R.oos,2):"&lt; 0")+"</b> gegen Baseline &rarr; keine Vorhersagekraft &rarr; sauberer <b>Nullbefund</b>; Placebo-Falsch-Positiv-Rate "+(R.plac!=null?(num(R.plac*100,1)+"&nbsp;%"):"n.&nbsp;a.")+", n = "+(R.npts!=null?num(R.npts,0):"?")+" Intervalle. "+srcOf(R.evDyn,R.gDate),
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
  function kap5(R){
    var P=R.P, X=R.X;
    return h("Was gilt")+
      '<ul style="margin:4px 0;padding-left:18px">'+
        '<li><b>Footprint &rarr; Sichtbarkeit</b> ist belastbar bei n='+num(P.n_brands,0)+': Wild-p '+num(P.wild_p,4)+', FDR-q '+num(P.fdr_q,3)+', LOO-stabil '+srcOf(P.dyn,R.cDate)+' (Peec-intern; externer Gegentest r '+num(X.r_brands,2)+', aber LOO-fragil).</li>'+
      '</ul>'+
      h("Was nicht gilt")+
      '<ul style="margin:4px 0;padding-left:18px">'+
        '<li><b>Preis nicht identifizierbar</b> bei 7 Marken: Preis, Groesse und Footprint sind statistisch nicht trennbar. Der scheinbare Effekt entstand nur durch <b>cite_share als bad control</b> (steckt mechanisch in der Zielgroesse); zudem sind Engine und Grounding perfekt kollinear (grounded = nur Gemini, ungrounded = nur ChatGPT). relprice allein: coef &minus;10,49, p 0,27.</li>'+
        '<li><b>Groesse</b> ist kein eigenstaendiger Effekt (Wild-p '+num(P.size_wild_p,2)+' bei n='+num(P.n_brands,0)+') — der Footprint absorbiert sie.</li>'+
        '<li><b>Events</b>: Nullbefund (R&sup2;_oos '+(R.oos!=null?num(R.oos,2):"&lt; 0")+').</li>'+
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
  function kap6(R){
    var P=R.P;
    return tbl(["Datum","Aenderung"],[
      ['17.07.2026','<b>Statistik-Haertung:</b> Wild-Cluster-Bootstrap, Benjamini-Hochberg-FDR und Leave-one-out ersetzen die Posterior-P (61&times; exakt 1,0). Von 15 '+'"sehr sicheren" Between-Effekten (P&ge;0,99) ueberleben nur <b>8 von 15</b>; Groesse und Preis fallen. Zirkularitaet erstmals gemessen; erfundenes CI-Band entfernt.'],
      ['18.07.2026','<b>Peec-26-Modell</b> (peec26_model): Footprint&rarr;SoV ueber '+num(P.n_cells,0)+' Zellen / '+num(P.n_brands,0)+' Marken / '+num(P.n_topics,0)+' Themen — Wild-p '+num(P.wild_p,4)+', FDR-q '+num(P.fdr_q,3)+', LOO-stabil. Wild-Bootstrap kann jetzt G&gt;12 (Rademacher-Sampling). Reiter-Umbauten (Korrelationsanalyse v5, LLM-Sichtbarkeit) + Snapshot-Versionierung (Wochen-Panel).']
    ]);
  }

  /* ============================================================
     Section-Inhalt (dynamisch bei jedem Render)
     ============================================================ */
  function innerHTML(){
    var R=resolve();
    return '<div style="margin-bottom:14px">'+
        '<h3 style="font-size:18px;font-weight:800;margin:0;color:#1a1a2e">📖 Dokumentation &mdash; Methodik des LLM-Cockpits</h3>'+
        '<p style="font-size:12px;color:#6b7280;margin:4px 0 0">Fuer Statistiker, Mathematiker und Aktuare: praezise, ehrlich, mit allen Einschraenkungen. <b>Kennzahlen werden bei jedem Aufruf aus den aktuellen Nightly-Daten gezogen; wo ein Feld (noch) fehlt, steht der gekennzeichnete Auditwert.</b> Quellen: <code>correlation_impact.py</code>, GEO-Snapshot, Peec-Export.</p>'+
      '</div>'+
      chapter("dokuKap1","1 · Ueberblick &amp; Datenfluesse", true, kap1(R))+
      chapter("dokuKap2","2 · Aktualisierungs-Rhythmen", false, kap2(R))+
      chapter("dokuKap3","3 · Metriken &amp; Definitionen", false, kap3(R))+
      chapter("dokuKap4","4 · Statistische Verfahren", false, kap4(R))+
      chapter("dokuKap5","5 · Interpretationsleitfaden", false, kap5(R))+
      chapter("dokuKap6","6 · Aenderungs-Log der Methodik", false, kap6(R));
  }
  function sectionHTML(){
    return '<div id="dokuInner" class="bg-white rounded-xl shadow p-6 mb-6" style="max-width:980px">'+innerHTML()+'</div>';
  }
  // Re-Render bei jedem Aufruf: dokuInner neu bauen (idempotent, billig).
  // Offen/zu-Zustand der Kapitel bleibt erhalten. NIE Null/NaN (num-Guards).
  function renderInner(){
    var di=document.getElementById("dokuInner"); if(!di) return;
    var ids=["dokuKap1","dokuKap2","dokuKap3","dokuKap4","dokuKap5","dokuKap6"], open={};
    ids.forEach(function(id){ var e=document.getElementById(id); if(e) open[id]=e.hasAttribute("open"); });
    try{ di.innerHTML=innerHTML(); }catch(e){ return; }
    ids.forEach(function(id){ var e=document.getElementById(id); if(e){ if(open[id]) e.setAttribute("open",""); else e.removeAttribute("open"); } });
  }

  /* ============================================================
     Tab-Integration (additiv, idempotent, rebuild-sicher)
     ============================================================ */
  /* HOTFIX 18.07.2026: Das Dashboard schaltet Tabs KLASSENBASIERT
     (classList 'hidden', dashboard_v3 ~Z. 3495) — die erste Fassung dieses
     Moduls versteckte Sections per Inline-style.display. Inline gewinnt gegen
     Klassen: Nach einem Klick auf 'Dokumentation' blieben ALLE Reiter leer.
     Jetzt exakt der Mechanismus des Dashboards; dazu ein Repair-Sweep, der
     verirrte Inline-Styles entfernt (ausser data-content="domain", das im
     Markup bewusst inline versteckt ist). */
  function clearStrayInline(){
    [].slice.call(document.querySelectorAll('section[data-content]')).forEach(function(s){
      if(s.getAttribute("data-content")==="domain") return;
      if(s.style && s.style.display==="none") s.style.display="";
    });
  }
  function showDoku(){
    clearStrayInline();
    [].slice.call(document.querySelectorAll('[data-tab]')).forEach(function(b){
      b.classList.remove("tab-active"); b.classList.add("tab-inactive");
    });
    var btn=document.getElementById("dokuTabBtn");
    if(btn){ btn.classList.remove("tab-inactive"); btn.classList.add("tab-active"); }
    [].slice.call(document.querySelectorAll('[data-content]')).forEach(function(s){ s.classList.add("hidden"); });
    var sec=document.getElementById("dokuSection"); if(sec) sec.classList.remove("hidden");
    try{ renderInner(); }catch(e){} // Doku bei jedem Aufruf frisch aus den Live-Daten
    try{ window.scrollTo({top:0,behavior:"smooth"}); }catch(e){}
  }
  function hideDoku(){
    var sec=document.getElementById("dokuSection"); if(sec) sec.classList.add("hidden");
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
    sec.className="tab-content hidden"; // HOTFIX: Klassen-Mechanismus statt Inline-Style
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
      build();
      // Doku bei jedem Retry frisch rendern: die Section wird evtl. gebaut,
      // bevor CORRELATION_IMPACT/GEO_SNAPSHOT/PEEC_DATA geladen sind — so
      // ziehen die Zahlen nach, sobald die Daten da sind (bis max. ~12 s).
      try{ renderInner(); }catch(e){}
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
  if(typeof module!=="undefined" && module.exports){ module.exports={ build:build, showDoku:showDoku, hideDoku:hideDoku, resolve:resolve, renderInner:renderInner, innerHTML:innerHTML, p26Get:p26Get, xsrcGet:xsrcGet }; }
})();
