/* ============================================================
   ERGO LLM-Cockpit — Reiter "Korrelationsanalyse" — Neuaufbau v5 (18.07.2026)
   Plan B (15_KORRELATION_NEUAUFBAU_PLAN.md). Nur validierte Befunde.
   -----------------------------------------------------------------
   Peec ist die FUEHRENDE Quelle (26 Marken), der eigene Crawl wird
   SEPARAT ausgewiesen, dazwischen eine Differenzanalyse.
   Struktur:
     BLOCK 1  Kernbefunde (K1-K6, Karten mit Evidenz-Badge + Stand)
     BLOCK 2  Treiber im Detail (Forest: Peec-26 + eigener Crawl + Events)
              + Ueber-/Unterperformer-Scatter (Peec-26-Markenmittel, 26 Punkte)
     BLOCK 3  Quellen-Vergleich Peec (fuehrend) vs. eigener Crawl (Differenz)
     BLOCK 4  Ursachenanalyse ERGO vs. Allianz  -> gap_waterfall.js (separates Modul)
     BLOCK 5  Methodik & Validierung (aufklappbar)
   Dynamik: level_model.peec26_model / cross_source_validation / structure_summary
   erscheinen erst nach dem naechsten Nightly -> saubere Fallbacks (weniger zeigen,
   NIE Platzhalter-Nullen). Kein grounded/ungrounded-Umschalter mehr (Peec-26 ist
   engine-uebergreifend grounded; der eigene Crawl-Teil zeigt grounded fix).
   Additiv: Host section[data-content="korrelation"], build()-Retry + Tab-Rebuild.
   ============================================================ */
(function () {
  "use strict";
  function ready(fn){ if(document.readyState!=="loading") fn(); else document.addEventListener("DOMContentLoaded",fn); }
  function num(v,d){ if(v==null||isNaN(v)) return "—"; d=(d==null?1:d); return (Math.round(v*Math.pow(10,d))/Math.pow(10,d)).toFixed(d).replace(".",","); }
  function signed(v,d){ return (v==null||isNaN(v))?"—":((v>0?"+":"")+num(v,d)); }
  function clamp(v,a,b){ return Math.max(a,Math.min(b,v)); }
  function dateOf(C){ var s=(C&&C.generated_at)||""; var m=/^(\d{4})-(\d{2})-(\d{2})/.exec(s); return m?(m[3]+"."+m[2]+"."+m[1]):""; }

  /* ---- Statische Auditwerte (18.07.2026) als Fallback, solange die neuen
         Felder noch nicht im Nightly-JSON stehen. NIE als Nullen ausgeben. ---- */
  var FB = {
    peec26: { eff:2.96, coef:0.607, wild_p:0.0063, fdr_q:0.013,
              loo:{min:0.42,max:0.65,sign_stable:true}, size_wild_p:0.61,
              brand_r:0.90, brand_rho:0.35, gap:12.64, foot:6.63,
              n_cells:286, n_brands:26, n_topics:11, leader:"Allianz" },
    xsrc:   { r_brands:0.823, p_brands:0.023, n_brands:7, r_cells:0.728, n_cells:70,
              loo_r:0.597, loo_p:0.21 }
  };
  var STAND="Auditwert 18.07. — dynamisch ab dem naechsten Nightly";

  /* ---- Footprint-Definition (Punkt 2, 18.07.2026): einmal als Info-Box,
         zusaetzlich als Tooltip ueberall dort, wo Footprint-Zahlen stehen. ---- */
  var FOOTDEF="Zitations-Footprint = Anteil der markeneigenen Domain an allen zitierten URLs je Thema. Peec: footprint_pct, 26 Marken, 5 Engines. Eigener Crawl: cite_share, 7 Marken, Gemini grounded.";
  function footInfoBox(){
    return '<div style="border:1px solid #dbe4fb;background:#f4f7fe;border-radius:11px;padding:12px 15px;margin:0 0 14px">'+
      '<div style="font-size:12.5px;font-weight:700;color:#1d4ed8;margin-bottom:3px">ℹ Was ist der Zitations-Footprint?</div>'+
      '<div style="font-size:12px;color:#374151;line-height:1.55">Der <b>Zitations-Footprint</b> ist der <b>Anteil der markeneigenen Domain an allen zitierten URLs</b> je Thema — also: wie oft verweisen die LLM-Antworten auf Quellen der Marke selbst (z.&nbsp;B. ergo.de), gemessen an allen Quellenangaben. '+
      '<b>Peec</b> misst ihn als <code>footprint_pct</code> ueber <b>26 Marken</b> und 5 Engines; der <b>eigene Crawl</b> als <code>cite_share</code> ueber <b>7 Marken</b> (Gemini, grounded). '+
      'Wichtig fuers Handeln: Die Antwortformulierung der LLMs laesst sich nicht steuern — die <b>Zitierfaehigkeit der eigenen Inhalte</b> schon. Alle Footprint-Zahlen in diesem Reiter (Forest, Scatter, Zerlegung) sind in dieser Definition gemessen.</div></div>';
  }

  function badge(txt,kind){
    var c={ok:["#067d3a","#e6f5ec"],warn:["#8a6d00","#fdf3d7"],muted:["#6b7280","#eef0f2"],info:["#1d4ed8","#e7eefe"]}[kind]||["#6b7280","#eef0f2"];
    return '<span style="font-size:10px;font-weight:700;color:'+c[0]+';background:'+c[1]+';border-radius:4px;padding:2px 7px;white-space:nowrap">'+txt+'</span>';
  }
  function card(o){
    return '<div style="border:1px solid #ececf0;border-radius:11px;padding:13px 15px;background:#fff;display:flex;flex-direction:column;gap:5px">'+
      '<div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start">'+
        '<div style="font-size:12.5px;font-weight:700;color:#1a1a2e;line-height:1.25">'+o.title+'</div>'+(o.badge||'')+'</div>'+
      (o.value!=null?('<div style="font-size:21px;font-weight:800;color:'+(o.accent||"#1a1a2e")+';line-height:1.08">'+o.value+
        (o.sub?(' <span style="font-size:11px;font-weight:500;color:#9ca3af">'+o.sub+'</span>'):'')+'</div>'):'')+
      (o.plain?('<div style="font-size:11.5px;color:#4b5563;line-height:1.45">'+o.plain+'</div>'):'')+
      (o.source?('<div style="font-size:10px;color:#b3b8bf;margin-top:auto;padding-top:2px">'+o.source+'</div>'):'')+
    '</div>';
  }

  /* ---------- Daten-Resolver mit Fallback ---------- */
  function p26Get(C){
    var p=(C.level_model||{}).peec26_model;
    if(p && p.available){
      var be=(((p.drivers_eff||{}).peec_foot||{}).between)||{};
      var gd=p.gap_decomposition||{};
      return { dyn:true, eff:be.effect_std_pp, coef:be.coef,
        wild_p:(p.wild_p||{}).peec_foot, fdr_q:(p.fdr_q||{}).peec_foot,
        loo:p.between_loo||be.between_loo||FB.peec26.loo, size_wild_p:(p.wild_p||{}).size,
        brand_r:(p.brand_level||{}).pearson_r, brand_rho:(p.brand_level||{}).spearman_r,
        gap:gd.actual_gap_pp, foot:((gd.contrib_pp||{}).peec_foot),
        n_cells:p.n_cells, n_brands:p.n_brands, n_topics:p.n_topics, leader:p.leader||"Allianz" };
    }
    var f=FB.peec26; f=Object.assign({dyn:false},f); return f;
  }
  function xsrcGet(C){
    var x=(C.level_model||{}).cross_source_validation;
    if(x && x.available){
      return { dyn:true, r_brands:x.pearson_r_brands, r_cells:x.pearson_r_cells,
               n_brands:x.n_brands, n_cells:x.n_cells };
    }
    return Object.assign({dyn:false},FB.xsrc);
  }
  // Eigener Crawl (grounded) Footprint-Between aus dem 2-Treiber-Modell (price_footprint_joint)
  function ownFootGet(C){
    var pfj=((C.level_model||{}).price_footprint_joint||{}).grounded;
    if(pfj && pfj.available && !isDead(pfj)){
      var be=(((pfj.drivers_eff||{}).cite_share||{}).between)||{};
      if(be.effect_std_pp!=null) return { dyn:true, eff:be.effect_std_pp, coef:be.coef,
        wild_p:be.wild_cluster_p!=null?be.wild_cluster_p:null, pdir:be.prob_direction,
        loo:be.between_loo, n_brands:pfj.n_brands, n_cells:pfj.n_cells, n_topics:pfj.n_topics };
    }
    // Fallback: reines grounded-Between (Solo-Fit)
    var g=(C.level_model||{}).grounded||{};
    if(g.available && !isDead(g) && g.between_effect){
      var b=g.between_effect;
      return { dyn:true, eff:b.effect_std_pp, coef:b.coef_pp_sov_per_pp_citeshare, wild_p:null,
        pdir:b.prob_direction, loo:g.between_loo, n_brands:g.n_brands, n_cells:g.n_cells, n_topics:g.n_topics };
    }
    return null;
  }

  // Entarteter Fit (LLM-Ausfall): alle Effekte 0/null. Nie als Befund werten.
  function isDead(fit){
    if(!fit) return false;
    if(fit.available===false) return true;
    var vals=[]; var de=fit.drivers_eff;
    if(de){ Object.keys(de).forEach(function(k){ ["within","between"].forEach(function(lv){ if(de[k]&&de[k][lv]) vals.push(de[k][lv].effect_std_pp); }); }); }
    ["within_effect","between_effect"].forEach(function(k){ if(fit[k]) vals.push(fit[k].effect_std_pp); });
    if(!vals.length) return false;
    return vals.every(function(v){ return v===0 || v==null; });
  }

  /* ============================================================
     BLOCK 1 — Kernbefunde
     ============================================================ */
  // Gepooltes Preis-Levelmodell + 3-Treiber-Gap-Explorer (dynamisch, Stand Nightly)
  function poolGet(C){
    var plp=(C||{}).price_level_pooled||{};
    var ge=((plp.gap_explorer||{}).grounded)||{};
    var rp=((((plp.price_to_sov||{}).grounded||{}).drivers_eff||{}).relprice)||{};
    var ok=plp.available && ge.available;
    var nb=ge.n_brands||(ge.brand_means?Object.keys(ge.brand_means).length:null);
    return { dyn:!!ok, n_days:plp.n_days, n_brands:nb,
             size:((ge.driver_reliability||{}).size)||null,
             price_between_coef:(rp.between||{}).coef, price_between_p:(rp.between||{}).wild_cluster_p,
             price_between_dir:(rp.between||{}).prob_direction, price_within_coef:(rp.within||{}).coef };
  }

  function block1(C){
    var P=p26Get(C), X=xsrcGet(C);
    var cards=[];
    // K1 Footprint -> Sichtbarkeit (FUEHREND, Peec-26)
    var belastbar=(P.wild_p!=null && P.wild_p<0.05 && P.loo && P.loo.sign_stable);
    cards.push(card({
      title:'<span title="'+FOOTDEF+'">Footprint → Sichtbarkeit</span> <span style="font-weight:600;color:#1d4ed8">(fuehrend)</span>',
      value:signed(P.eff,1)+" pp", sub:"SoV je +1&nbsp;SD Quellpraesenz", accent:"#067d3a",
      badge: (P.dyn&&belastbar)?badge("belastbar (n="+(P.n_brands||26)+")","ok"):badge("ab naechstem Nightly","warn"),
      plain:"Marken mit mehr Quellen-Footprint sind sichtbarer. Wild-Cluster-p "+num(P.wild_p,4)+
            (P.fdr_q!=null?(", FDR-q "+num(P.fdr_q,3)):"")+", LOO "+((P.loo&&P.loo.sign_stable)?"vorzeichenstabil":"instabil")+
            (P.loo?(" ("+num(P.loo.min,2)+"…"+num(P.loo.max,2)+")"):"")+".",
      source: P.dyn?("Quelle: Peec-26 · "+(P.n_cells||"?")+" Zellen / "+(P.n_brands||"?")+" Marken · Stand "+(dateOf(C)||"aktueller Nightly"))
                   :("Quelle: Peec-26 · <b>berechnet ab dem naechsten Nightly</b> — statischer Auditwert Wild-p 0,0063 (18.07.)")
    }));
    // K2 Unabhaengiger Gegentest (cross_source_validation)
    cards.push(card({
      title:"Unabhaengiger Gegentest",
      value:"r = "+num(X.r_brands,2), sub:X.n_brands+" Marken", accent:"#1a1a2e",
      badge:badge("zwei Messsysteme","info"),
      plain:"Peec-Footprint (UI-Scraping) gegen den eigenen Gemini-SoV — getrennte Quellen, keine gemeinsamen Antworten. Zellebene r "+num(X.r_cells,2)+" (n "+X.n_cells+"). "+
            "<b>⚠ fragil:</b> ohne Allianz faellt r auf 0,60 (p 0,21, n=6).",
      source: X.dyn?("Quelle: level_model.cross_source_validation · Stand "+(dateOf(C)||"aktueller Nightly"))
                   :("Quelle: Uebergabe 17.07. · "+STAND)
    }));
    // K3 ERGO-Rueckstand
    cards.push(card({
      title:"ERGO-Rueckstand zu Allianz",
      value:num(P.gap,1)+" pp", sub:"SoV-Abstand", accent:"#dc0028",
      badge: P.dyn?badge("Peec-26","ok"):badge("ab naechstem Nightly","warn"),
      plain:"Rund <b>"+num(P.foot,1)+" pp</b> davon gehen mit dem geringeren Footprint einher (Peec-26-Zerlegung); der Rest ist allgemeine Markenstaerke. Zerlegung, kein Kausalnachweis.",
      source: P.dyn?("Quelle: peec26_model.gap_decomposition · Stand "+(dateOf(C)||"aktueller Nightly")):("Quelle: Peec-26 · "+STAND)
    }));
    // K4 Groesse — dynamisch: breites Peec-26 (null) vs. gepooltes 14-Preis-Marken-Modell
    var PL=poolGet(C);
    var _sizeRobust=(PL.dyn && PL.size && PL.size.wild_cluster_p!=null && PL.size.wild_cluster_p<0.05 && PL.size.loo_sign_stable);
    cards.push(card({
      title:"Unternehmensgroesse",
      value:_sizeRobust?"schwaches, uneinheitliches Signal":"kein robuster Effekt", accent:"#6b7280",
      badge:badge(_sizeRobust?"uneinheitlich":"Nullbefund","muted"),
      plain:"Im breiten Peec-26-Modell <b>kein</b> eigenstaendiger Effekt (Wild-p "+num(P.size_wild_p,2)+")."+
            (PL.dyn&&PL.size?(" Im ueber "+(PL.n_days||"?")+" Tage gepoolten Modell der "+(PL.n_brands||"?")+" Preis-Marken ein "+(_sizeRobust?"schwaches, richtungsstabiles":"nicht signifikantes")+" Signal (Wild-p "+num(PL.size.wild_cluster_p,3)+", LOO "+(PL.size.loo_sign_stable?"stabil":"instabil")+")."):"")+
            " Ueber die Modelle hinweg <b>nicht konsistent</b> \u2192 kein gesicherter Groessen-Effekt.",
      source: "Quelle: peec26_model.wild_p.size + price_level_pooled.gap_explorer \u00b7 Stand "+(dateOf(C)||"aktueller Nightly")
    }));
    // K5 Preis — dynamisch aus dem gepoolten Preis-Levelmodell (Between identifizierbar, nicht kausal)
    var _priceOk=(PL.dyn && PL.price_between_coef!=null);
    cards.push(card({
      title:"Preisniveau",
      value:_priceOk?"identifizierbar (Between)":"nicht identifizierbar",
      accent:_priceOk?"#0e7490":"#6b7280",
      badge:badge(_priceOk?"nicht kausal":"nicht trennbar","muted"),
      plain:_priceOk
        ?("Aktualisiert: mit jetzt <b>"+(PL.n_brands||"?")+" Preis-Marken</b> und ueber "+(PL.n_days||"?")+" Tage gemittelt IST der Preis identifizierbar \u2014 guenstiger Relativpreis geht mit mehr Sichtbarkeit einher (Between "+num(PL.price_between_coef,2)+", Richtung "+Math.round((PL.price_between_dir||0)*100)+"\u202f%, Wild-p "+num(PL.price_between_p,3)+"). <b>Aber nur als Marken-Vergleich</b>; die kausal saubere Within-Schaetzung liegt bei ~0 ("+num(PL.price_within_coef,2)+"). Der fruehere '7 Marken / verworfen'-Stand ist ueberholt.")
        :"Preis-Levelmodell baut sich noch ueber die Nightly-Tage auf (mind. 3 saubere Tage noetig).",
      source:"Quelle: price_level_pooled \u00b7 Stand "+(dateOf(C)||"aktueller Nightly")
    }));
    // K6 Kurzfrist-Events
    var val=C.validation||{}; var oos=(val.out_of_sample||{}).r2_oos_vs_baseline; var fp=val.placebo_false_positive_rate;
    var mv=C.multivariate||{}; var coefs=mv.coefficients||{}; var nTot=Object.keys(coefs).length;
    var nRel=(oos!=null&&oos<=0)?0:Object.keys(coefs).filter(function(k){ return coefs[k].significant && coefs[k].reliable!==false; }).length;
    cards.push(card({
      title:"Kurzfrist-Events",
      value:nRel+" / "+(nTot||"?"), sub:"Event-Typen mit verlaesslicher Wirkung", accent:"#6b7280",
      badge:badge("Nullbefund","muted"),
      plain:"Kein einzelnes Marktereignis bewegt die Sichtbarkeit gesichert. Out-of-Sample-R² "+num(oos,2)+" (&lt;0 → keine Vorhersagekraft), Placebo-Falsch-Positiv-Rate "+(fp!=null?num(fp*100,1)+"&nbsp;%":"—")+"."+((function(){var ed=C.event_impact_denoised; if(ed&&ed.available){return " <b>Auch nach Entrauschung</b> (nur grounded-Engines + Wochen-Mittel, "+(ed.n_intervalle_woechentlich||"?")+" Wochen-Intervalle) bleibt es bei "+(ed.n_gesichert_woechentlich||0)+" gesicherten Effekten — ein <b>belastbarer</b> Nullbefund, nicht bloß Rauschen.";} return "";})()),
      source:"Quelle: eigener Crawl · Event-Study, "+(mv.n_points||"?")+" Intervalle"
    }));
    return '<div style="margin-bottom:6px"><div style="font-size:14px;font-weight:700;color:#1a1a2e">1 · Kernbefunde</div>'+
      '<div style="font-size:11.5px;color:#9ca3af;margin:1px 0 10px">Jede Karte nennt Quelle und Stand. Fehlt ein Nightly-Feld, zeigt die Karte den Auditwert und weist ihn aus — <b>fehlende Daten sind nie Null</b>.</div>'+
      '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:11px">'+cards.join("")+'</div></div>';
  }

  /* ============================================================
     BLOCK 2 — Treiber im Detail (Forest) + Scatter
     ============================================================ */
  function forestRows(C){
    var rows=[]; var P=p26Get(C); var O=ownFootGet(C);
    // Zeile 1: Peec-26 Footprint-Between (fuehrend), Wild-p statt Posterior-P
    rows.push({
      label:'<span title="'+FOOTDEF+'">Zitations-Footprint — Peec-26 (fuehrend)</span>',
      sub:"Between (26 Marken, groessenbereinigt) · Peec, engine-uebergreifend · Anteil eigener Domain an zitierten URLs",
      est:P.eff, wild_p:P.wild_p, stable:(P.loo&&P.loo.sign_stable),
      chip: (P.wild_p!=null?("Wild-p "+num(P.wild_p,4)):("Wild-p "+num(FB.peec26.wild_p,4))),
      kind: (P.wild_p!=null&&P.wild_p<0.05&&P.loo&&P.loo.sign_stable)?"ok":"warn",
      nTxt:"n eff. = "+(P.n_brands||26)+" Marken"+(P.dyn?"":" · Auditwert"),
      plain:"Der belastbarste Treiber: mehr Quellpraesenz → mehr Sichtbarkeit, auch nach Groessen-Kontrolle."
    });
    // Zeile 2: eigener Crawl Footprint-Between (grounded)
    if(O){
      rows.push({
        label:'<span title="'+FOOTDEF+'">Zitations-Footprint — eigener Crawl</span>',
        sub:"Between (7 Marken, grounded/Gemini) · zur Konsistenzpruefung · Anteil eigener Domain an zitierten URLs (cite_share)",
        est:O.eff, wild_p:O.wild_p, pdir:O.pdir, stable:(O.loo&&O.loo.sign_stable),
        chip: (O.wild_p!=null?("Wild-p "+num(O.wild_p,4)):((O.pdir!=null&&O.pdir>=1)?"P=1,0":("P="+num(O.pdir,2)))),
        kind: (O.stable? "ok":"warn"),
        nTxt:"n eff. = "+(O.n_brands||"?")+" Marken",
        plain:"Der eigene Gemini-Crawl zeigt denselben Zusammenhang (kleinere Fallzahl) — stuetzt Peec.",
        noCI:(O.pdir!=null&&O.pdir>=1)
      });
    }
    // Zeile 3: Events ~0
    rows.push({ label:"Einzel-Aktivitaeten / Events", sub:"kurzfristige Wirkung (Event-Study, multivariat)",
      est:0, events:true, chip:"kein belastbarer Effekt", kind:"muted",
      nTxt:"n = "+((C.multivariate||{}).n_points||"?")+" Intervalle",
      plain:"Bisher kein verlaesslicher Kurzfrist-Effekt: das Event-Modell schlaegt die Marken-Basislinie out-of-sample nicht." });
    return rows;
  }
  function forestPlot(C){
    var rows=forestRows(C);
    var mx=1; rows.forEach(function(r){ mx=Math.max(mx,Math.abs(r.est||0)); }); mx=mx*1.15;
    function x(v){ return 50 + 50*(v/mx); }
    var grid=''; [-0.5,0.5].forEach(function(f){ grid+='<div style="position:absolute;left:'+(50+50*f)+'%;top:0;bottom:0;width:1px;background:#f0f1f3"></div>'; });
    var body=rows.map(function(r,i){
      var col=r.kind==="ok"?"#dc0028":(r.kind==="warn"?"#e0a800":"#9ca3af");
      var plot='<div style="position:relative;height:26px;background:'+(i%2?"#fbfbfc":"#f7f8fa")+';border-radius:4px;overflow:hidden">'+grid+
        '<div style="position:absolute;left:50%;top:0;bottom:0;width:2px;background:#c8ccd2"></div>';
      if(!r.events){
        plot+='<div style="position:absolute;left:calc('+clamp(x(r.est),1,99)+'% - 5px);top:7px;width:10px;height:12px;background:'+col+';border-radius:2px;box-shadow:0 0 0 1px #fff"></div>';
      } else {
        plot+='<div style="position:absolute;left:calc(50% - 5px);top:7px;width:10px;height:12px;border:2px solid '+col+';border-radius:2px;background:#fff"></div>';
      }
      plot+='</div>';
      var eff=r.events?"~0":signed(r.est,1)+" pp";
      var unstable=(r.stable===false&&!r.events)?' <span style="font-size:10px;color:#b45309" title="Vorzeichen wechselt beim Weglassen einzelner Marken">↔ instabil</span>':"";
      var noCIchip=(r.noCI&&!r.events)?' <span style="font-size:10px;color:#9ca3af" title="Kein Konfidenzband: bei P=1,0 laesst sich keine Streuung zurueckrechnen. Ein erfundenes ±-Band waere irrefuehrend.">ohne CI</span>':"";
      return '<div style="display:grid;grid-template-columns:230px 1fr 84px;align-items:center;gap:10px;padding:8px 0;border-top:1px solid #f4f5f6">'+
        '<div><div style="font-size:12.5px;font-weight:600;line-height:1.25">'+r.label+'</div>'+
          '<div style="font-size:10.5px;color:#9ca3af;margin:1px 0 3px">'+(r.sub||'')+'</div>'+
          '<div style="display:flex;gap:5px;flex-wrap:wrap;align-items:center">'+badge(r.chip,r.kind)+unstable+noCIchip+'</div>'+
          '<div style="font-size:10px;color:#b3b8bf;margin-top:2px">'+(r.nTxt||'')+'</div></div>'+
        '<div>'+plot+'<div style="font-size:10.5px;color:#8b919a;margin-top:3px;line-height:1.35">'+r.plain+'</div></div>'+
        '<div style="font-size:13px;font-weight:700;text-align:right;color:'+(r.events?"#9ca3af":"#1a1a2e")+'">'+eff+'</div>'+
      '</div>';
    }).join("");
    return '<div style="border:1px solid #eee;border-radius:11px;padding:14px 16px;margin-bottom:14px">'+
      '<div style="font-size:13px;font-weight:700;margin-bottom:2px">Treiber im Detail — was bewegt die Sichtbarkeit?</div>'+
      '<div style="font-size:11px;color:#9ca3af;margin-bottom:6px">Quadrat = Schaetzwert (pp Sichtbarkeit je +1&nbsp;SD des Treibers) · dicke Mittellinie = kein Effekt. Belastbarkeit ueber <b>Wild-Cluster-p</b> (nicht Posterior-P). Kein erfundenes Konfidenzband.</div>'+
      '<div style="display:grid;grid-template-columns:230px 1fr 84px;gap:10px;font-size:10px;color:#c0c4cb"><div></div><div style="display:flex;justify-content:space-between;padding:0 2px"><span>−'+num(mx,0)+' pp</span><span>0</span><span>+'+num(mx,0)+' pp</span></div><div style="text-align:right">Effekt</div></div>'+
      body+
      '<div style="font-size:10.5px;color:#9ca3af;margin-top:8px">Peec-26 = Mundlak/CRE-Between ueber 26 Marken (fuehrend). Der eigene Crawl (7 Marken, grounded) dient der Konsistenzpruefung. Zusammenhaenge, kein Kausalnachweis (dafuer DiD).</div>'+
    '</div>';
  }

  /* Warnhinweis: Peec-SoV ist durch den ERGO-zentrierten Prompt-Satz verzerrt (Pruefung 31.07.2026). */
  function peecBiasWarn(){
    return '<div style="background:#fff4f4;border:1px solid #f3c6c6;border-left:4px solid #dc0028;border-radius:8px;padding:10px 12px;margin-bottom:10px;font-size:11.5px;color:#7a1420;line-height:1.5">'+
      '<b>\u26a0 Peec-SoV ist hier kein neutrales Marktranking.</b> Das Peec-Projekt \u201eERGO Germany\u201c ist ERGOs eigenes Monitoring: <b>132 von 614 Prompts (21\u202f%) nennen ERGO ausdr\u00fccklich</b> (\u201eIst ERGO vertrauensw\u00fcrdig f\u00fcr \u2026?\u201c), <b>kein einziger nennt einen Wettbewerber</b>. Dadurch liegt ERGOs Peec-SoV (~23\u202f%, Platz\u202f1) rund <b>3,2\u00d7</b> \u00fcber dem neutralen eigenen Crawl (~7\u202f%), w\u00e4hrend alle anderen Marken bei ~0,9\u00d7 liegen. Als echtes Marktranking gilt der <b>eigene Crawl</b> (Allianz und HUK vor ERGO). Peec hier = \u201eSichtbarkeit, wenn gezielt \u00fcber ERGO gefragt wird\u201c.'+
    '</div>';
  }
  /* ---------- Ueber-/Unterperformer-Scatter (Peec-26-Markenmittel, 26 Punkte) ---------- */
  var scatterChart=null;
  var scatterNeutral = true;  // Default: branding-neutrale Ansicht (nur Prompts ohne Marke)
  function peecNeutralAvail(){ var P=window.PEEC_DATA; return !!(P && P.footprint_pct_neutral && P.peec_sov_pct_neutral); }
  window.__scatterToggle = function(n){ scatterNeutral = !!n; var el=document.getElementById("korrScatterBlock"); if(el){ el.outerHTML = scatterBlock(); renderScatter(); } };
  function scatterBlock(){
    var avail=peecNeutralAvail(); var neu=scatterNeutral && avail;
    function tb(n,label){ var on=(scatterNeutral===!!n); return '<button onclick="window.__scatterToggle('+n+')" style="font-size:10.5px;padding:2px 9px;border-radius:7px;border:1px solid '+(on?"#067d3a":"#ccc")+';background:'+(on?"#067d3a":"#fff")+';color:'+(on?"#fff":"#282d37")+';cursor:pointer">'+label+'</button>'; }
    var toggle='<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:8px">'+
      '<span style="font-size:10.5px;color:#9ca3af">Prompts:</span>'+tb(1,"Neutral (ohne Branding)")+tb(0,"inkl. Branding (ERGO-fokussiert)")+
      (avail?'':'<span style="font-size:10px;color:#b45309">— neutrale Ansicht ab dem naechsten Peec-Export verfuegbar</span>')+'</div>';
    var note = neu
      ? '<div style="background:#e6f5ec;border:1px solid #bfe3cd;border-left:4px solid #067d3a;border-radius:8px;padding:9px 12px;margin-bottom:10px;font-size:11.5px;color:#14532d;line-height:1.5"><b>Branding-neutrale Ansicht.</b> Nur Prompts <b>ohne</b> Markennamen (Peec-System-Tag <code>non-branded</code>) — das faire Marktbild. ERGO ist hier nicht kuenstlich vorne; neutral liegen Allianz und HUK vor ERGO.</div>'
      : peecBiasWarn();
    return '<div id="korrScatterBlock" style="border:1px solid #eee;border-radius:11px;padding:14px 16px;margin-bottom:14px">'+
      '<div style="font-size:13px;font-weight:700;margin-bottom:2px">Ueber-/Unterperformer — Quellpraesenz vs. Sichtbarkeit (Peec-26)</div>'+
      '<div style="font-size:11px;color:#9ca3af;margin-bottom:8px">Jeder Punkt = eine der 26 Peec-Marken (Markenmittel ueber die Themen). Linie = erwartete Sichtbarkeit bei gegebenem Footprint (OLS). Ueber der Linie = macht aus dem Footprint ueberdurchschnittlich viel Sichtbarkeit.</div>'+
      toggle + note +
      '<div style="position:relative;height:270px"><canvas id="korrScatterCv"></canvas></div>'+
      '<div style="font-size:11px;color:#6b7280;margin-top:6px" id="korrScatterNote"></div>'+
    '</div>';
  }
  function peecBrandMeans(){
    var P=window.PEEC_DATA;
    if(!P) return null;
    var useNeu = scatterNeutral && peecNeutralAvail();
    var fp = useNeu ? P.footprint_pct_neutral : P.footprint_pct;
    var sv = useNeu ? P.peec_sov_pct_neutral : P.peec_sov_pct;
    if(!fp || !sv) return null;
    var out=[];
    Object.keys(fp).forEach(function(b){
      if(!sv[b]) return;
      var ft=fp[b], st=sv[b]; var fv=[], svv=[];
      Object.keys(ft).forEach(function(t){ if(t==="Corporate") return; if(typeof ft[t]==="number") fv.push(ft[t]); });
      Object.keys(st).forEach(function(t){ if(t==="Corporate") return; if(typeof st[t]==="number") svv.push(st[t]); });
      if(!fv.length || !svv.length) return;
      out.push({ brand:b, foot: fv.reduce(function(a,x){return a+x;},0)/fv.length, sov: svv.reduce(function(a,x){return a+x;},0)/svv.length });
    });
    return out.length>=3?out:null;
  }
  function renderScatter(){
    var cv=document.getElementById("korrScatterCv"); var noteEl=document.getElementById("korrScatterNote");
    if(!cv || !window.Chart) return;
    var pts=peecBrandMeans();
    if(!pts){ if(noteEl) noteEl.textContent="Peec-Markenmittel (data/peec_footprint.json) noch nicht geladen — erscheinen nach dem naechsten Peec-Export bzw. Reload."; return; }
    var n=pts.length, sx=0,sy=0,sxx=0,sxy=0;
    pts.forEach(function(p){ sx+=p.foot; sy+=p.sov; sxx+=p.foot*p.foot; sxy+=p.foot*p.sov; });
    var b=(n*sxy-sx*sy)/Math.max(n*sxx-sx*sx,1e-9), a=(sy-b*sx)/n;
    var xmin=Math.min.apply(null,pts.map(function(p){return p.foot;})), xmax=Math.max.apply(null,pts.map(function(p){return p.foot;}));
    var pad=(xmax-xmin)*0.08||1; xmin-=pad; xmax+=pad;
    function colOf(br){ return br==="ERGO"?"#dc0028":(br==="Allianz"?"#003781":"#9ca3af"); }
    var data={ datasets:[
      {type:"scatter",label:"Marken",data:pts.map(function(p){return {x:p.foot,y:p.sov,brand:p.brand};}),
       pointRadius:pts.map(function(p){return (p.brand==="ERGO"||p.brand==="Allianz")?7:4;}),
       pointBackgroundColor:pts.map(function(p){return colOf(p.brand);}), pointBorderColor:"#fff", pointBorderWidth:1},
      {type:"line",label:"OLS",data:[{x:xmin,y:a+b*xmin},{x:xmax,y:a+b*xmax}],borderColor:"#c8ccd2",borderWidth:2,borderDash:[6,4],pointRadius:0,fill:false}
    ]};
    if(scatterChart){ try{scatterChart.destroy();}catch(e){} scatterChart=null; }
    try{
      scatterChart=new Chart(cv,{data:data,options:{responsive:true,maintainAspectRatio:false,animation:false,
        plugins:{legend:{display:false},tooltip:{callbacks:{label:function(ctx){ var r=ctx.raw||{}; if(r.brand==null) return null; var res=r.y-(a+b*r.x); return r.brand+": "+num(r.y,1)+"% SoV bei "+num(r.x,1)+"% Footprint ("+(res>=0?"+":"")+num(res,1)+" pp vs. erwartet)"; }}}},
        scales:{x:{title:{display:true,text:"Zitations-Footprint % (Peec) — Anteil eigener Domain an zitierten URLs"}},y:{title:{display:true,text:"Peec Share of Voice %"},beginAtZero:true}}}});
    }catch(e){}
    if(noteEl){
      var er=pts.filter(function(p){return p.brand==="ERGO";})[0];
      if(er){ var res=er.sov-(a+b*er.foot);
        noteEl.innerHTML="<b>ERGO:</b> "+(res>=0?("+"+num(res,1)+" pp ueber"):(num(res,1)+" pp unter"))+" der erwarteten Sichtbarkeit. "+
          "<span style='color:#9ca3af'>Steigung "+signed(b,2)+" pp SoV je pp Footprint (deskriptive OLS ueber "+n+" Peec-Marken). ERGO rot, Allianz blau.</span>";
      } else noteEl.textContent="";
    }
  }

  function block2(C){
    return '<div style="margin:16px 0 6px"><div style="font-size:14px;font-weight:700;color:#1a1a2e">2 · Treiber im Detail</div>'+
      '<div style="font-size:11.5px;color:#9ca3af;margin:1px 0 10px">Peec-26 und der eigene Crawl stehen nebeneinander. Preis-Zeile und 3-Wege-Zerlegung (Groesse / Quellpraesenz / Preis) stehen in der Ursachenanalyse (Block 4) aus dem gepoolten Modell.</div>'+
      '<div id="korrForest">'+forestPlot(C)+'</div>'+ scatterBlock() +'</div>';
  }

  /* ============================================================
     BLOCK 3 — Quellen-Vergleich: Peec (fuehrend) vs. eigener Crawl
     (Differenzanalyse; Logik aus peec_compare.js, kompakt, Fokus Differenz)
     ============================================================ */
  var TMAP={ "Zahnzusatz":"zahnzusatz","Sterbegeld":"sterbegeld","Risikoleben":"risikoleben",
    "Berufsunfähigkeit":"berufsunfaehigkeit","Rechtsschutz":"rechtsschutz","Haftpflicht":"haftpflicht",
    "Hausrat":"hausrat","Kfz":"kfz","Unfall":"unfall","Krankenhauszusatz":"krankenhauszusatz","Reise":"reise" };
  // Punkt 5 (18.07.2026): grounded/ungrounded-Umschalter. Peec-Engines:
  // Gemini/Perplexity/AI Overview/AI Mode = grounded, ChatGPT = UI (ui_mixed).
  // Die CSV traegt das auch als Spalte engine_typ — die ist fuehrend.
  var GROUNDED_ENGINES={ "Gemini":1,"Perplexity":1,"AI Overview":1,"AI Mode":1 };
  var b3Mode="g"; // "g" grounded | "u" ChatGPT/UI | "all" alle Engines
  var BMAP={ "HUK24":"HUK-Coburg" };
  function pearson(x,y){ var n=x.length; if(n<3) return null; var mx=0,my=0; x.forEach(function(v){mx+=v;}); y.forEach(function(v){my+=v;}); mx/=n; my/=n; var c=0,vx=0,vy=0; for(var i=0;i<n;i++){ c+=(x[i]-mx)*(y[i]-my); vx+=(x[i]-mx)*(x[i]-mx); vy+=(y[i]-my)*(y[i]-my); } return (vx>0&&vy>0)?c/Math.sqrt(vx*vy):null; }
  function ranks(v){ var s=v.map(function(x,i){return [x,i];}).sort(function(a,b){return a[0]-b[0];}); var r=new Array(v.length); s.forEach(function(p,i){ r[p[1]]=i; }); return r; }
  // 18.07.2026 Fix: dashboard_v3 haelt GEO_SNAPSHOT als top-level `let` — das
  // landet NICHT auf window. Erst lexikalische Bindung versuchen, dann window
  // (health_banner.js spiegelt zusaetzlich). Ursache des leeren Quellen-Vergleichs.
  function snapData(){ try{ if(typeof GEO_SNAPSHOT!=="undefined" && GEO_SNAPSHOT) return GEO_SNAPSHOT; }catch(e){} return window.GEO_SNAPSHOT||null; }
  // Eigene Crawl-Werte je Kanal. Ausfall-Guard: Ein Produkt, in dem der gewaehlte
  // Kanal in Summe 0 Nennungen hat, gilt als "keine Daten" und wird uebersprungen
  // (roter Faden des Projekts: fehlende Daten sind nie Null).
  function ownSov(mode){
    var g=snapData(); if(!g||!g.products) return null; var out={};
    var engs= mode==="u"?["chatgpt"]:(mode==="all"?["gemini","chatgpt"]:["gemini"]);
    Object.keys(g.products).forEach(function(pid){
      var sbl=g.products[pid].summary_by_llm||{}; var acc={}, cnt={}, sum=0;
      engs.forEach(function(e){ ((sbl[e]||{}).brands||[]).forEach(function(b){
        var v=100*(b.share_of_voice||0); acc[b.name]=(acc[b.name]||0)+v; cnt[b.name]=(cnt[b.name]||0)+1; sum+=v; }); });
      if(sum<=0) return; // Kanal in diesem Produkt ausgefallen/leer -> keine Zeile statt Nullen
      var row={_name:g.products[pid].name||pid};
      Object.keys(acc).forEach(function(bn){ row[bn]=acc[bn]/cnt[bn]; });
      out[pid]=row;
    });
    return Object.keys(out).length?out:null;
  }
  function loadPeecCells(){
    if(window.__KORR_PEEC_CELLS3) return Promise.resolve(window.__KORR_PEEC_CELLS3);
    return fetch("data/peec_cells.csv?t="+Date.now(),{cache:"no-store"}).then(function(r){ return r.ok?r.text():null; }).then(function(t){
      if(!t) return null;
      var lines=t.replace(/^﻿/,"").split("\n"); var head=lines[0].split(";"); var idx={}; head.forEach(function(h,i){ idx[h.trim()]=i; });
      var mc={g:{},u:{},all:{}}, tot={g:{},u:{},all:{}};
      for(var i=1;i<lines.length;i++){ var c=lines[i].split(";"); if(c.length<5) continue;
        var pid=TMAP[(c[idx.thema]||"").trim()]; if(!pid) continue; var b=BMAP[c[idx.marke]]||c[idx.marke];
        var cls=(idx.engine_typ!=null && c[idx.engine_typ]!=null && c[idx.engine_typ]!=="")
              ? ((c[idx.engine_typ]||"").trim()==="grounded"?"g":"u")
              : (GROUNDED_ENGINES[c[idx.engine]]?"g":"u");
        var m=parseFloat(c[idx.mention_count]||0)||0;
        [cls,"all"].forEach(function(k){ mc[k][pid]=mc[k][pid]||{}; mc[k][pid][b]=(mc[k][pid][b]||0)+m; tot[k][pid]=(tot[k][pid]||0)+m; }); }
      var out={}; ["g","u","all"].forEach(function(k){ out[k]={}; Object.keys(mc[k]).forEach(function(pid){ out[k][pid]={}; Object.keys(mc[k][pid]).forEach(function(b){ out[k][pid][b]=tot[k][pid]?100*mc[k][pid][b]/tot[k][pid]:0; }); }); });
      if(!Object.keys(out.all).length) return null; // leeres Parse-Ergebnis NIE cachen — spaeter erneut versuchen
      window.__KORR_PEEC_CELLS3=out; return out;
    }).catch(function(){ return null; });
  }
  function b3ModeLbl(){ return b3Mode==="g"?"grounded (Web-Suche)":(b3Mode==="u"?"UI / ungrounded (ChatGPT)":"alle Engines"); }
  function b3Btns(){
    function btn(id,lbl){ var on=b3Mode===id; return '<button data-m="'+id+'" class="b3m" style="font-size:11px;padding:3px 10px;border-radius:8px;border:1px solid '+(on?"#dc0028":"#ccc")+';background:'+(on?"#dc0028":"#fff")+';color:'+(on?"#fff":"#282d37")+';cursor:pointer">'+lbl+'</button>'; }
    return '<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:9px"><span style="font-size:11px;font-weight:600;color:#6b7280">Kanal:</span>'+
      btn("g","Grounded (Web-Suche)")+btn("u","UI / ChatGPT")+btn("all","Alle Engines")+
      '<span style="font-size:10.5px;color:#9ca3af">Peec: Gemini, Perplexity, AI Overview, AI Mode = grounded · ChatGPT = UI. Eigener Crawl: Gemini = grounded · ChatGPT = ungrounded.</span></div>';
  }
  function block3Skeleton(){
    return '<div style="margin:16px 0 6px"><div style="font-size:14px;font-weight:700;color:#1a1a2e">3 · Quellen-Vergleich: Peec (fuehrend) vs. eigener Crawl</div>'+
      '<div style="font-size:11.5px;color:#9ca3af;margin:1px 0 10px">Zwei unabhaengige Messungen derselben Sache. Niveau-Unterschiede sind methodisch normal (Peec verteilt ueber 26 Marken, der eigene Crawl ueber 7) — entscheidend ist die <b>Rang-Konvergenz</b> je Thema.</div>'+
      peecBiasWarn()+
      '<div id="korrDiffBox" style="border:1px solid #eee;border-radius:11px;padding:14px 16px"><div style="font-size:12px;color:#9ca3af">Quellen-Vergleich wird geladen (data/peec_cells.csv) …</div></div></div>';
  }
  var fb3Wait=0;
  function fillBlock3(){
    var box=document.getElementById("korrDiffBox"); if(!box) return;
    var own=ownSov(b3Mode);
    if(!own){
      // 18.07.2026 Fix: GEO_SNAPSHOT laedt asynchron — warten statt aufgeben
      // (vorher blieb hier dauerhaft der "nach Reload"-Text stehen).
      if(fb3Wait++<40){ setTimeout(fillBlock3,500); return; }
      box.innerHTML=b3Btns()+'<div style="font-size:12px;color:#9ca3af">Eigener Crawl (data/geo_snapshot.json): fuer den Kanal <b>'+b3ModeLbl()+'</b> keine Daten ladbar — Vergleich erscheint nach Reload oder in einem anderen Kanal. <b>Keine Ersatz-Nullen.</b></div>'; b3Wire(box); return;
    }
    loadPeecCells().then(function(cells){
      // 18.07.2026 Fix: Box IMMER frisch greifen — renderPanel kann das DOM
      // inzwischen neu aufgebaut haben (die alte Referenz waere detached).
      box=document.getElementById("korrDiffBox"); if(!box) return;
      if(!cells){ box.innerHTML='<div style="font-size:12px;color:#9ca3af">Peec-Zellen (data/peec_cells.csv) nicht erreichbar — der Quellen-Vergleich wird beim naechsten Reload gezeigt. <b>Keine Ersatz-Nullen.</b></div>'; return; }
      var peec=cells[b3Mode]||{};
      if(!Object.keys(peec).length){ box.innerHTML=b3Btns()+'<div style="font-size:12px;color:#9ca3af">Peec: fuer den Kanal <b>'+b3ModeLbl()+'</b> keine Zellen im aktuellen Export. <b>Keine Ersatz-Nullen.</b></div>'; b3Wire(box); return; }
      // 31.07.2026 (Entscheidung Paul): Der Vergleich zeigt nur noch die vier
      // Kernmarken ERGO, Allianz, HUK-Coburg, AXA — je Marke "Peec / eigener
      // Crawl" nebeneinander. Rang-ρ laeuft ueber genau diese vier Marken
      // (n=4, grob — dafuer direkt lesbar). Fehlt eine Marke in einer Quelle,
      // steht dort "—", nie 0.
      var B3FOCUS=["ERGO","Allianz","HUK-Coburg","AXA"];
      var rowsHtml="", allOwn=[], allPeec=[];
      var pids=Object.keys(own).filter(function(p){ return peec[p]; });
      pids.forEach(function(pid){
        var o=own[pid], p=peec[pid];
        var avail=B3FOCUS.filter(function(b){ return o[b]!=null && p[b]!=null; });
        if(avail.length<3) return; // zu wenig Kernmarken in beiden Quellen -> keine Zeile statt Nullen
        var xo=avail.map(function(b){return o[b];}), xp=avail.map(function(b){return p[b];});
        xo.forEach(function(v){allOwn.push(v);}); xp.forEach(function(v){allPeec.push(v);});
        var rho=pearson(ranks(xo),ranks(xp));
        var rc=(rho==null)?"#9ca3af":(rho>=0.8?"#067d3a":(rho>=0.5?"#b45309":"#b91c1c"));
        var cells4=B3FOCUS.map(function(b){
          var vP=p[b], vO=o[b];
          var txt=(vP==null&&vO==null)?"—":((vP==null?"—":num(vP,1))+" / "+(vO==null?"—":num(vO,1)));
          return '<td style="padding:5px 8px;text-align:right;white-space:nowrap'+(b==="ERGO"?';font-weight:700;color:#dc0028':';color:#334155')+'">'+txt+'</td>';
        }).join("");
        rowsHtml+='<tr style="border-bottom:1px solid #f1f5f9">'+
          '<td style="padding:5px 8px;font-weight:600;color:#1e293b">'+(o._name||pid)+'</td>'+cells4+
          '<td style="padding:5px 8px;text-align:right;font-weight:700;color:'+rc+'">'+(rho==null?"—":num(rho,2))+'</td></tr>';
      });
      var rAll=pearson(allOwn,allPeec);
      var srcTxt = b3Mode==="g" ? "<b>Peec</b> (grounded: Gemini, Perplexity, AI Overview, AI Mode) vs. <b>eigener Crawl</b> (Gemini-API, grounded)"
                 : (b3Mode==="u" ? "<b>Peec</b> (ChatGPT-UI) vs. <b>eigener Crawl</b> (ChatGPT-API, ungrounded)"
                                 : "<b>Peec</b> (alle 5 Engines) vs. <b>eigener Crawl</b> (Mittel aus Gemini + ChatGPT)");
      box.innerHTML=b3Btns()+'<div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;align-items:flex-start;margin-bottom:8px">'+
        '<div style="font-size:12px;color:#4b5563;max-width:640px">SoV je Thema fuer die vier Kernmarken, Zellenformat <b>Peec / eigener Crawl</b> (jeweils %): '+srcTxt+'. Rechte Spalte: Rang-Konvergenz ueber genau diese vier Marken (Spearman-ρ).</div>'+
        '<span style="font-size:11px;font-weight:700;color:#067d3a;background:#e6f5ec;border-radius:6px;padding:4px 10px;white-space:nowrap">Gesamt-Korrelation r = '+(rAll==null?"—":num(rAll,2))+'</span></div>'+
        '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12.5px">'+
        '<thead><tr style="text-align:left;color:#64748b;border-bottom:1px solid #e2e8f0">'+
        '<th style="padding:5px 8px">Thema</th><th style="padding:5px 8px;text-align:right;color:#dc0028">ERGO</th>'+
        '<th style="padding:5px 8px;text-align:right">Allianz</th><th style="padding:5px 8px;text-align:right">HUK-Coburg</th>'+
        '<th style="padding:5px 8px;text-align:right">AXA</th>'+
        '<th style="padding:5px 8px;text-align:right" title="Spearman-Rangkorrelation der Reihenfolge von ERGO, Allianz, HUK-Coburg, AXA (1,0 = identisch)">Rang-ρ</th></tr></thead>'+
        '<tbody>'+rowsHtml+'</tbody></table></div>'+
        '<div style="font-size:11px;color:#9ca3af;margin-top:8px">Beschraenkt auf die vier Kernmarken ERGO, Allianz, HUK-Coburg, AXA (Entscheidung Paul, 31.07.2026). Zellenformat: Peec / eigener Crawl in %. Rang-ρ ≥ 0,8 (gruen) = beide Quellen sehen dieselbe Reihenfolge der vier Marken — bei n=4 grob, aber direkt lesbar. Niveau-Unterschiede folgen aus 26 vs. 7 Marken im Nenner. Kanal: '+b3ModeLbl()+' · Peec-Export siehe data/peec_cells.csv (zeitraum-Spalte).</div>';
      b3Wire(box);
    });
  }
  // Umschalter-Verkabelung: setzt den Kanal und rendert Block 3 neu (Daten sind gecacht).
  function b3Wire(box){
    box.querySelectorAll(".b3m").forEach(function(btn){
      btn.addEventListener("click", function(){
        var m=btn.getAttribute("data-m");
        if(m===b3Mode) return;
        b3Mode=m; fb3Wait=0; fillBlock3();
      });
    });
  }

  /* ============================================================
     BLOCK 5 — Methodik & Validierung (aufklappbar)
     ============================================================ */
  function circLine(name, circ, mixTxt){
    if(!circ) return '<li><b>'+name+':</b> keine Zirkularitaets-Kennzahl im JSON.</li>';
    var lvl=circ.level; var sh=circ.share_same_engine;
    var t=(lvl==="none")?"unabhaengig gemessen":(lvl==="high"?"stark selbstbezueglich":"teils selbstbezueglich");
    return '<li><b>'+name+':</b> '+t+(sh!=null?(" ("+num(100*sh,0)+" % gleiche Engine)"):"")+(mixTxt?(" · "+mixTxt):"")+'.</li>';
  }
  function block5(C){
    var lm=C.level_model||{}; var mix=lm.citation_engine_mix||{};
    var mixTxt=(mix.chatgpt!=null||mix.gemini!=null)?("Zitate ChatGPT "+(mix.chatgpt||0)+" / Gemini "+(mix.gemini||0)):"";
    var X=xsrcGet(C); var P=p26Get(C);
    var circItems=""
      + circLine("eigener Crawl grounded (Gemini)", (lm.grounded||{}).circularity, mixTxt)
      + circLine("eigener Crawl ungrounded (ChatGPT)", (lm.ungrounded||{}).circularity, "")
      + circLine("Peec-26 (intern)", (P.dyn?((lm.peec26_model||{}).circularity):{level:"high"}), "Footprint und SoV aus denselben Peec-Antworten")
      + '<li><b>Cross-Source (extern):</b> '+(X.dyn?"unabhaengig gemessen":"unabhaengig gemessen (Auditwert)")+' — Peec-Footprint vs. eigener SoV, r '+num(X.r_brands,2)+' ('+X.n_brands+' Marken). Der zirkularitaetsarme Gegentest.</li>';
    return '<details style="margin-top:16px;border:1px solid #eee;border-radius:11px;padding:4px 16px" open>'+
      '<summary style="cursor:pointer;font-size:14px;font-weight:700;color:#1a1a2e;padding:10px 0">5 · Methodik &amp; Validierung</summary>'+
      '<div style="font-size:12px;color:#4b5563;line-height:1.6;padding-bottom:12px">'+
        '<b>Wild-Cluster-Bootstrap &amp; FDR.</b> Statt Posterior-Wahrscheinlichkeiten (die bei kleiner Fallzahl fast immer 1,0 sind) wird die Signifikanz ueber einen Wild-Cluster-Bootstrap auf Markenebene bestimmt und per Benjamini-Hochberg (FDR) fuer Mehrfachtests korrigiert. So bleibt nur belastbar, was auch dem Weglassen einzelner Marken standhaelt.<br>'+
        '<b>Zwei Zirkularitaets-Ebenen:</b> Peec-26 misst intern konsistent (Footprint und SoV aus denselben Peec-Antworten, engine-uebergreifend); der externe Gegentest (Cross-Source) kreuzt zwei getrennte Messsysteme.'+
        '<ul style="margin:8px 0 6px;padding-left:18px">'+circItems+'</ul>'+
        '<b>Limitationen (ehrlich):</b><ul style="margin:6px 0 0;padding-left:18px">'+
          '<li><b>Preis-Identifikation:</b> Ueber 14 Preis-Marken und mehrere Tage gepoolt ist der Preis als Between-Effekt richtungsstabil identifizierbar (guenstiger → sichtbarer), aber nicht kausal (Within ≈ 0). Siehe Ursachenanalyse.</li>'+
          '<li><b>Boden des Wild-p:</b> bei nur 7 Clustern (eigener Crawl) ist der kleinstmoegliche p-Wert 0,0078 (2⁷ Vorzeichen-Vektoren) — "sicherer" geht rechnerisch nicht.</li>'+
          '<li><b>Peec-Historie kurz:</b> derzeit ein Vier-Wochen-Fenster; Trend-/Lag-Aussagen brauchen mehr Wochen.</li>'+
          '<li><b>Cross-Source fragil:</b> ohne Allianz faellt r von 0,82 auf 0,60 (p 0,21). Der plausibelste Befund des Projekts — aber kein Fels.</li>'+
        '</ul>'+
      '</div></details>';
  }

  /* ============================================================
     Panel-Aufbau
     ============================================================ */
  function peecBadgeTop(C){
    var X=xsrcGet(C);
    return '<span title="Peec AI = fuehrende Messquelle (26 Marken, 5 Engines). Cross-Source-Gegentest r='+num(X.r_brands,2)+'" style="font-size:10px;font-weight:700;color:#067d3a;background:#e6f5ec;border-radius:4px;padding:2px 7px;vertical-align:middle">Peec fuehrend · Gegentest r='+num(X.r_brands,2)+'</span>';
  }
  function renderPanel(host, C){
    var card0=document.getElementById("korrSynth");
    if(!card0){ card0=document.createElement("div"); card0.id="korrSynth"; card0.className="bg-white rounded-xl shadow p-6 mb-6"; host.insertBefore(card0, host.firstChild); }
    card0.innerHTML=
      '<div style="margin-bottom:14px">'+
        '<h3 style="font-size:17px;font-weight:700;margin:0">Korrelationsanalyse — was treibt die LLM-Sichtbarkeit? '+peecBadgeTop(C)+'</h3>'+
        '<p style="font-size:12px;color:#6b7280;margin:3px 0 0">Nur validierte Befunde. <b>Peec AI</b> ist die fuehrende Quelle (26 Marken), der <b>eigene Crawl</b> steht getrennt daneben, dazwischen eine Differenzanalyse. Die Kernbefunde (Block 1/2) sind engine-uebergreifend; im Quellen-Vergleich (Block 3) und in der Ursachenanalyse (Block 4) laesst sich der Kanal <b>grounded / UI</b> umschalten.</p>'+
      '</div>'+
      footInfoBox()+ block1(C)+ block2(C)+ block3Skeleton();
    // Block 5 als eigene Karte direkt nach korrSynth -> gap_waterfall (Block 4) schiebt sich dazwischen
    var meth=document.getElementById("korrMethodik");
    if(!meth){ meth=document.createElement("div"); meth.id="korrMethodik"; meth.className="bg-white rounded-xl shadow p-6 mb-6"; }
    meth.innerHTML=block5(C);
    if(card0.nextSibling!==meth){ if(card0.parentNode) card0.parentNode.insertBefore(meth, card0.nextSibling); }
    renderScatter();
    fillBlock3();
  }

  /* ---------- Detail-Sektionen als eingeklappter Anhang (tidy) ---------- */
  function rerenderDetails(){ ["renderCorrelationTab"].forEach(function(fn){ try{ if(typeof window[fn]==="function") window[fn](); }catch(e){} }); }
  var KEEP={ korrSynth:1, korrMethodik:1, korrDetails:1, gapWaterfallBox:1 };
  function tidy(host){
    [].slice.call(host.children).forEach(function(el){
      if(!KEEP[el.id] && /^🔗\s*Korrelation/.test((el.innerText||el.textContent||"").trim())) el.style.display="none";
    });
    if(document.getElementById("korrDetails")) return;
    var rxs=[/Validierte Impact-Analyse/,/Maßnahmen-Wirkung/,/Share of Voice/,/Tagesübersicht/,/Mention-Tracking/,/Event-Stream/];
    var kids=[].slice.call(host.children); var toCollapse=[];
    rxs.forEach(function(rx){ var b=kids.filter(function(el){ return !KEEP[el.id]&&rx.test(((el.innerText||el.textContent)||"").slice(0,90)); })[0]; if(b&&toCollapse.indexOf(b)<0) toCollapse.push(b); });
    if(toCollapse.length){
      var det=document.createElement("details"); det.id="korrDetails"; det.open=true; det.className="bg-white rounded-xl shadow mb-6"; det.style.cssText="padding:6px 18px";
      det.innerHTML='<summary style="cursor:pointer;font-size:13px;font-weight:600;color:#6b7280;padding:12px 0">Detail-Auswertungen (Event-Study, Maßnahmen-Wirkung/DiD, SoV-Verlauf, Mentions, Event-Stream) — zum Ein-/Ausklappen klicken</summary>';
      toCollapse[0].parentNode.insertBefore(det, toCollapse[0]);
      toCollapse.forEach(function(b){ b.style.display=""; det.appendChild(b); });
      det.addEventListener("toggle", function(){ if(det.open) setTimeout(rerenderDetails,60); });
      setTimeout(rerenderDetails,120);
    }
  }

  function build(){
    var host=document.querySelector('section[data-content="korrelation"]');
    if(!host) return false;
    var C=window.CORRELATION_IMPACT;
    if(!C || !C.level_model) return false;
    renderPanel(host,C);
    [0,400,1000,2000,3500].forEach(function(d){ setTimeout(function(){ tidy(host); },d); });
    return true;
  }
  ready(function(){
    var tries=0;
    (function wait(){ tries++; if(build()) return; if(tries<40) setTimeout(wait,300); })();
    var tb=document.querySelector('[data-tab="korrelation"]'); if(tb) tb.addEventListener("click",function(){ [150,600,1400].forEach(function(d){ setTimeout(build,d); }); });
  });

  // Test-Hook (nur fuer jsdom): erlaubt gezieltes Ansteuern ohne Chart.js
  if(typeof module!=="undefined" && module.exports){ module.exports={ p26Get:p26Get, xsrcGet:xsrcGet, ownFootGet:ownFootGet, forestRows:forestRows }; }
})();
