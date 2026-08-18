/* ===========================================================================
   ERGO LLM-Cockpit — Ursachenanalyse "Warum liegt der Marktfuehrer vorn?" v3
   (Neuaufbau v5, 18.07.2026) Nur validierte Zerlegung:
   1. Wasserfall ZWEISTUFIG aus level_model.structure_summary
      (Autoritaet = Groesse+Footprint | Preis | Rest, gekappt) falls vorhanden,
      sonst Footprint-only aus gap_decomposition. KEIN full_joint mehr
      (3-Wege-Zerlegung ist laut Audit 17.07. nicht kommunizierbar).
      Beitraege werden proportional gekappt, wenn Summe > Gap. Fix grounded.
   2. NEU: Themen-Hotspots — wo genau verliert die Marke gegen den
      Marktfuehrer? Je Thema: SoV-Gap + eigener Zitatanteil -> Prio-Label
      (Content-Luecke / Verwertung / fast gleichauf). Quelle: GEO_SNAPSHOT
      client-seitig (kein Pipeline-Feld noetig).
   3. NEU (31.07.2026): Branchen-Benchmark — externer 16-Branchen-Vergleich
      (Cowork-Analyse 26.07.2026): Wie gross "duerfte" der Allianz-Vorsprung
      rein aus der Groesse sein? Quelle: data/benchmark_branchen.json
      (Runtime-Fetch). Alle Zahlen kommen aus der Datei, nichts hartkodiert;
      fehlt sie, erscheint ein Hinweis — NIE Ersatz-Nullen. Nur sichtbar in
      der Standard-Ansicht ERGO vs. Allianz (fuer andere Paare gibt es keine
      Benchmark-Daten).
   Fix grounded (der grounded/ungrounded-Umschalter ist im Neuaufbau v5 entfallen).
   =========================================================================== */
(function () {
  "use strict";
  function ready(fn){ if(document.readyState!=="loading") fn(); else document.addEventListener("DOMContentLoaded",fn); }
  function getData(){
    if (window.CORRELATION_IMPACT) return Promise.resolve(window.CORRELATION_IMPACT);
    return fetch("data/correlation_impact.json?t="+Date.now(),{cache:"no-store"})
      .then(function(r){return r.ok?r.json():null;}).catch(function(){return null;});
  }
  function pp(v){ return (v==null||isNaN(v))?"—":((v>0?"+":"")+(Math.round(v*10)/10).toFixed(1).replace(".",",")+" pp"); }
  function pct(v){ return (v==null||isNaN(v))?"—":(Math.round(v*10)/10).toFixed(1).replace(".",",")+" %"; }

  var COL = { base:"#9aa0a8", size:"#6b7280", foot:"#b8860b", price:"#0e7490", rest:"#d9dce1", leader:"#dc0028" };
  var LBL = { authority:"Bekanntheit & Quellpräsenz", size:"Bekanntheit & Größe", cite_share:"Quellpräsenz (in wie vielen zitierten Quellen)", relprice:"Preisniveau" };
  var AMP = { authority:"🟡", size:"⚪", cite_share:"🟡", relprice:"🟢" };
  var mode = "g", curBrand = "ERGO", curRef = null;
  function seg(o){ return o?(mode==="g"?o.grounded:(mode==="u"?o.ungrounded:o.combined)):null; }
  function modeLbl(){ return mode==="g"?"grounded (Web-Suche)":(mode==="u"?"ungrounded (ChatGPT)":"kombiniert"); }

  // Guard: Faellt ein Kanal aus, sind alle SoV-Werte 0; leader faellt dann per max()
  // ueber lauter Nullen auf die erstbeste Marke, und die Box fragt "Warum liegt X vor Y?"
  // ueber einem leeren Balken. Vorsorglicher Guard gegen LLM-Ausfaelle.
  function isDead(fit){
    if(!fit) return false;
    if(fit.available===false) return true;
    var vals=[];
    var de=fit.drivers_eff;
    if(de){ Object.keys(de).forEach(function(k){
      ["within","between"].forEach(function(lv){ if(de[k]&&de[k][lv]) vals.push(de[k][lv].effect_std_pp); }); }); }
    ["within_effect","between_effect"].forEach(function(k){ if(fit[k]) vals.push(fit[k].effect_std_pp); });
    if(!vals.length) return false;
    return vals.every(function(v){ return v===0 || v==null; });
  }
  function deadBox(){
    return '<h3 style="font-size:16px;font-weight:700;margin:0">Ursachenanalyse</h3>'+
      '<div style="border:1px solid #f3d7a5;background:#fdf6e6;border-radius:10px;padding:12px 14px;margin-top:10px">'+
      '<b style="font-size:12.5px;color:#8a6d00">⚠ Keine Daten in diesem Kanal</b>'+
      '<div style="font-size:11.5px;color:#6b5b28;margin-top:3px">Für den Kanal <b>'+modeLbl()+'</b> liegen keine Messdaten vor '+
      '(vermutlich ein LLM-Ausfall). Ohne Messwerte gibt es keinen Rückstand zu zerlegen — '+
      'es wird bewusst weder Marktführer noch Ursache benannt.</div></div>';
  }

  function sovOf(m, brand){
    var ar = (m&&m.authority_ranking) || [];
    for (var i=0;i<ar.length;i++){ if(ar[i].brand===brand) return ar[i].mean_sov_pct; }
    return null;
  }

  /* ---- Zerlegungs-Quelle: structure_summary (Autorität|Preis|Rest) > Footprint-only ----
     18.07.2026: full_joint (3-Wege cite/size/relprice) ist raus (Audit 17.07., E1:
     Referenzmarke instabil, Attribution bei 7 Marken nicht identifiziert). Die
     robuste Zusammenfassung kommt aus level_model.structure_summary; fehlt sie
     (aelterer Nightly), faellt die Box auf die reine Footprint-Zerlegung zurueck. */
  function decompFor(lm, brand){
    // 1) structure_summary (nur ERGO, zweistufig Autorität|Preis|Rest)
    var ss = seg(lm.structure_summary);
    if(brand==="ERGO" && ss && ss.available && ss.gap_pp!=null){
      var contrib={}; if(ss.authority_pp!=null) contrib.authority=ss.authority_pp; if(ss.price_pp) contrib.relprice=ss.price_pp;
      return { g:{actual_gap_pp:ss.gap_pp, contrib_pp:contrib, rest_pp:ss.rest_pp},
               leader:ss.leader,
               label:(ss.price_source==="pooled_joint"
                        ? ("Autorität + Preis · gemeinsames Modell, über "+(ss.n_days||"?")+" saubere Tage stabilisiert")
                        : "Autorität (Größe+Footprint) + Preis + Rest (Audit-Struktur)"),
               cols:{authority:COL.foot, relprice:COL.price}, brands:["ERGO"], joint:true,
               n:(ss.n_days||null), nb:null, nt:null, structure:true };
    }
    // 2) Footprint-only aus dem Basiskanal (Between/Mundlak)
    var m=seg(lm)||{};
    if(m.available && !isDead(m) && m.gap_decomposition && m.gap_decomposition[brand]){
      var g0=m.gap_decomposition[brand];
      return { g:{actual_gap_pp:g0.actual_gap_pp, contrib_pp:{cite_share:g0.explained_by_footprint_pp}},
               leader:m.leader, label:"nur Footprint (Mundlak-Between)", cols:{cite_share:COL.foot},
               brands:Object.keys(m.gap_decomposition), joint:false, n:m.n_cells, nb:m.n_brands, nt:m.n_topics };
    }
    return null;
  }

  /* ---- Gap-Explorer: BELIEBIGES Marken-Paar in Bekanntheit/Quellpräsenz/Preis ----
     Quelle: price_level_pooled.gap_explorer (gepooltes 3-Treiber-Modell). Beitrag je
     Treiber = Between-Koeffizient x Differenz der Markenmittel. Erlaubt ERGO vs HUK
     usw. — nicht nur gegen den Leader. */
  function decompExplorer(focus, ref){
    var plp = window.__GW_PLP;
    var ge = (plp && plp.gap_explorer) ? seg(plp.gap_explorer) : null;
    if(!ge || !ge.available || !ge.brand_means) return null;
    var brands = ge.brands || Object.keys(ge.brand_means);
    if(brands.indexOf(focus) < 0) return null;
    if(!ref || brands.indexOf(ref) < 0)
      ref = (ge.leader && brands.indexOf(ge.leader) >= 0) ? ge.leader
            : brands.filter(function(b){return b!==focus;})[0];
    var mf = ge.brand_means[focus], mr = ge.brand_means[ref];
    if(!mf || !mr) return null;
    var bc = ge.between_coef || {};
    var gap = (mr.sov||0) - (mf.sov||0);
    var contrib = {}, favors = {};
    ["size","cite_share","relprice"].forEach(function(k){
      if(bc[k]==null) return;
      var v = bc[k] * ((mr[k]||0) - (mf[k]||0));
      contrib[k] = v;
      if(v < -0.05) favors[k] = v;   // Treiber, der fuer die Fokus-Marke spricht
    });
    var ahead = brands.filter(function(b){ return b!==focus && ge.brand_means[b] && (ge.brand_means[b].sov||0) > (mf.sov||0); })
                       .sort(function(a,b){ return (ge.brand_means[b].sov||0)-(ge.brand_means[a].sov||0); }).slice(0,8);
    if(ahead.indexOf(ref)<0) ahead.unshift(ref);
    return { g:{actual_gap_pp:gap, contrib_pp:contrib}, leader:ref, focus:focus,
             baseSov:(mf.sov||0), leadSov:(mr.sov||0), refCandidates:ahead,
             brands:brands, cols:{size:COL.size, cite_share:COL.foot, relprice:COL.price},
             label:"Bekanntheit + Quellpräsenz + Preis · gemeinsames Modell, über "+(plp.n_days||"?")+" saubere Tage",
             // 10.08.2026: nt stand fest auf null, gerendert wurde daraus '? Themen' -
             // obwohl der Reiterkopf verspricht, dass statt einer Luecke 'keine Angabe
             // mit Grund' steht. n_topics liegt im selben Modellblock vor.
             n:ge.n_cells, nb:brands.length, nt:(ge.n_topics!=null?ge.n_topics:null), reliability:ge.driver_reliability,
             favors:favors, explorer:true, n_days:plp.n_days };
  }

  /* ---- Themen-Hotspots aus GEO_SNAPSHOT (client-seitig) ---- */
  var DOM2BRAND = { "ergo.de":"ERGO","ergo-reiseversicherung.de":"ERGO","dkv.com":"ERGO","allianz.de":"Allianz",
    "allianzdirect.de":"Allianz","axa.de":"AXA","generali.de":"Generali","cosmosdirekt.de":"CosmosDirekt",
    "huk.de":"HUK-Coburg","huk24.de":"HUK-Coburg","signal-iduna.de":"Signal Iduna",
    // 18.07.2026: Markenerweiterung Crawl 7->25 (additiv, Namen wie Crawl/BRAND_SIZE)
    "adac.de":"ADAC","arag.de":"ARAG","alte-leipziger.de":"Alte Leipziger","barmenia.de":"Barmenia",
    "da-direkt.de":"DA Direkt","devk.de":"DEVK","debeka.de":"Debeka","diebayerische.de":"Die Bayerische",
    "die-bayerische.de":"Die Bayerische","gothaer.de":"Gothaer","hdi.de":"HDI","hannoversche.de":"Hannoversche",
    "hansemerkur.de":"HanseMerkur","lv1871.de":"LV 1871","ruv.de":"R+V","vhv.de":"VHV",
    "wgv.de":"WGV","wuerttembergische.de":"Württembergische","zurich.de":"Zurich" };
  // 18.07.2026 Fix: dashboard_v3 haelt GEO_SNAPSHOT als top-level `let` — das
  // landet NICHT auf window. Erst lexikalische Bindung versuchen, dann window
  // (health_banner.js spiegelt zusaetzlich). Vorher fehlten die Hotspots im
  // echten Browser dauerhaft.
  function snapData(){ try{ if(typeof GEO_SNAPSHOT!=="undefined" && GEO_SNAPSHOT) return GEO_SNAPSHOT; }catch(e){} return window.GEO_SNAPSHOT||null; }
  function topicHotspots(brand, leader){
    var g=snapData();
    if(!g || !g.products) return null;
    var engines = mode==="g"?["gemini"]:(mode==="u"?["chatgpt"]:["gemini","chatgpt"]);
    var rows=[];
    Object.keys(g.products).forEach(function(pid){
      var pd=g.products[pid]; var sbl=pd.summary_by_llm||{};
      var sB=[], sL=[];
      engines.forEach(function(e){
        ((sbl[e]||{}).brands||[]).forEach(function(b){
          if(b.name===brand) sB.push(100*(b.share_of_voice||0));
          if(b.name===leader) sL.push(100*(b.share_of_voice||0));
        });
      });
      if(!sB.length && !sL.length) return;
      function avg(v){ return v.length? v.reduce(function(a,x){return a+x;},0)/v.length : 0; }
      // Zitatanteile aus cited_sources.overall
      var tot=0, cB=0, cL=0;
      (((pd.cited_sources)||{}).overall||[]).forEach(function(r){
        var n=r.count||0; tot+=n;
        var bb=DOM2BRAND[(r.domain||"").replace(/^www\./,"")];
        if(bb===brand) cB+=n;
        if(bb===leader) cL+=n;
      });
      rows.push({ pid:pid, name:(pd.name||pid), sovB:avg(sB), sovL:avg(sL), gap:avg(sL)-avg(sB),
                  citB:tot?100*cB/tot:0, citL:tot?100*cL/tot:0 });
    });
    rows.sort(function(a,b){ return b.gap-a.gap; });
    return rows;
  }
  function prioChip(r){
    if(r.gap<=1) return '<span style="font-size:10px;font-weight:700;color:#067d3a;background:#e6f5ec;border-radius:4px;padding:1px 6px">fast gleichauf</span>';
    if(r.citB<r.citL && r.citB<5) return '<span style="font-size:10px;font-weight:700;color:#b91c1c;background:#fee2e2;border-radius:4px;padding:1px 6px">Content-Lücke → Prio</span>';
    if(r.citB>=r.citL) return '<span style="font-size:10px;font-weight:700;color:#8a6d00;background:#fdf3d7;border-radius:4px;padding:1px 6px">Verwertungs-/Markenthema</span>';
    return '<span style="font-size:10px;font-weight:700;color:#8a6d00;background:#fdf3d7;border-radius:4px;padding:1px 6px">Quellpräsenz ausbauen</span>';
  }

  /* ---- Branchen-Benchmark (Ursachenanalyse, Zusatz 31.07.2026) ----
     Externer Vergleich ueber 16 Branchen: LLM-Sichtbarkeit folgt der realen
     Marktgroesse nur unterproportional (SoV ~ a * Realanteil^b, b ~ 0,5).
     Daraus ergibt sich ein "erwartbarer" Allianz-Vorsprung — dem der
     gemessene gegenuebergestellt wird. Andere Messmethode als Peec/eigener
     Crawl -> Niveaus NICHT direkt vergleichbar, nur die Verhaeltnisse. */
  function fx(v,d){ if(v==null||isNaN(v)) return "—"; d=(d==null?1:d); return (Math.round(v*Math.pow(10,d))/Math.pow(10,d)).toFixed(d).replace(".",","); }
  function benchSection(brand, leader){
    if(brand!=="ERGO" || leader!=="Allianz") return "";
    var head='<div style="margin-top:16px;border-top:1px solid #f0f0f0;padding-top:12px">'+
      '<div style="font-size:13px;font-weight:700;margin-bottom:2px">Branchen-Benchmark: Wie groß „dürfte" der Allianz-Vorsprung sein?</div>';
    var B=window.__GW_BENCH;
    if(B===undefined) return head+'<div style="font-size:11.5px;color:#9ca3af">Benchmark (data/benchmark_branchen.json) wird geladen …</div></div>';
    if(!B || !B.spotlight || !B.regression) return head+'<div style="font-size:11.5px;color:#9ca3af">Benchmark-Datei (data/benchmark_branchen.json) nicht erreichbar — die Sektion erscheint nach Reload. <b>Keine Ersatz-Nullen.</b></div></div>';
    var s=B.spotlight, r=B.regression;
    function tile(v,l,accent){ return '<div style="flex:1;min-width:150px;background:#f6f7f9;border-radius:8px;padding:9px 12px">'+
      '<div style="font-size:19px;font-weight:800;color:'+(accent||"#282d37")+';line-height:1.1">'+v+'</div>'+
      '<div style="font-size:10.5px;color:#6b7280;margin-top:2px;line-height:1.4">'+l+'</div></div>'; }
    /* 12.08.2026 GEKUERZT (Entscheidung Paul): Hier standen zwei lange Absaetze
       plus Kacheln mit Spotlight-Werten. Der Benchmark misst mit einem anderen
       Verfahren, ueber andere Marken, und wird nicht aktualisiert - er ist laut
       eigenem Hinweis nur qualitativ lesbar. Was davon wirklich traegt, sind
       zwei Saetze. Der Methodenapparat und die nicht vergleichbaren Niveaus
       sind raus; die Datei data/benchmark_branchen.json bleibt fuer den, der
       nachschauen will. */
    var txt='<div style="font-size:11.5px;color:#4b5563;line-height:1.55">'
      +'LLM-Sichtbarkeit folgt der Marktgr\u00f6\u00dfe nur <b>unterproportional</b> \u2014 gro\u00dfe Anbieter werden gestaucht, '
      +'Testsieger- und Ratgeber-Marken verst\u00e4rkt (r '+fx(r.pearson,2)+' \u00fcber '+(B.n_marken||"?")+' Marken in '
      +(B.n_branchen||"?")+' Branchen). Das hei\u00dft f\u00fcr ERGO beides: der R\u00fcckstand zu Allianz ist kein reiner '
      +'Gr\u00f6\u00dfeneffekt \u2014 und Sichtbarkeit ist f\u00fcr Herausforderer billiger zu holen als Marktanteil.</div>'
      +'<div style="font-size:10.5px;color:#9ca3af;margin-top:5px">Externer Quercheck (Stand '+(B.stand||"?")+'), '
      +'anderes Messverfahren \u2014 nur qualitativ lesbar, nicht mit den Zahlen dieses Reiters vergleichbar. '
      +'Details: data/benchmark_branchen.json.</div>';
    return head+txt+'</div>';
  }

  function render(host, lm, brand){
    var box = document.getElementById("gapWaterfallBox");
    if(!box){
      box=document.createElement("div"); box.id="gapWaterfallBox";
      box.className="bg-white rounded-xl shadow p-6 mb-6";
      // 04.08.2026: Ankerpunkt ist jetzt das eine Ergebnis-Panel (#korrErgebnis);
      // die frueheren Karten #korrSynth/#korrMethodik gibt es nicht mehr.
      var anchor=document.getElementById("korrErgebnis")||document.getElementById("korrSynth");
      if(anchor && anchor.nextSibling) host.insertBefore(box, anchor.nextSibling);
      else if(anchor) host.appendChild(box);
      else host.insertBefore(box, host.firstChild);
    }
    // Guard zuerst: bei totem Kanal gar nicht erst zerlegen.
    if(isDead(seg(lm))){
      box.innerHTML = deadBox();
      return;
    }
    var d = decompExplorer(brand, curRef) || decompFor(lm, brand);
    if(!d){
      box.innerHTML='<h3 style="font-size:16px;font-weight:700;margin:0">Ursachenanalyse: Warum liegt der Marktführer vorn?</h3>'+
        '<p style="font-size:12px;color:#9ca3af;margin-top:8px">Für diese Auswahl noch keine Zerlegungs-Daten.</p>';
      return;
    }
    if(d.brands.indexOf(brand)<0) brand=(d.brands.indexOf("ERGO")>=0?"ERGO":d.brands[0]);
    curBrand=brand;
    var leader=d.leader, g=d.g;
    var m=seg(lm)||{};
    var baseSov=(d.explorer&&d.baseSov!=null)?d.baseSov:sovOf(m,brand), leadSov=(d.explorer&&d.leadSov!=null)?d.leadSov:sovOf(m,leader);
    var gap=g.actual_gap_pp||0;
    // Beitraege: negative auf 0, Summe proportional auf max. Gap kappen
    var contrib={}; var sum=0;
    Object.keys(g.contrib_pp||{}).forEach(function(k){ var v=Math.max(0,g.contrib_pp[k]||0); contrib[k]=v; sum+=v; });
    var capped=false;
    if(sum>gap && sum>0){ var f=gap/sum; Object.keys(contrib).forEach(function(k){ contrib[k]*=f; }); capped=true; sum=gap; }
    var rest=Math.max(0,gap-sum);
    if(baseSov==null||leadSov==null){ baseSov=0; leadSov=gap; }

    // Marken-Umschalter + Kanal-Umschalter (Punkt 5, 18.07.2026: grounded/ungrounded zurueck)
    var brandSel='<div style="display:flex;gap:6px;flex-wrap:wrap">'+d.brands.map(function(o){
      var on=o===brand; return '<button data-b="'+o+'" class="gwb" style="font-size:11px;padding:3px 9px;border-radius:8px;border:1px solid '+(on?"#dc0028":"#ccc")+';background:'+(on?"#dc0028":"#fff")+';color:'+(on?"#fff":"#282d37")+';cursor:pointer">'+o+'</button>';
    }).join("")+'</div>';
    var modeSel='<div style="display:flex;gap:5px;align-items:center;flex-wrap:wrap"><span style="font-size:10.5px;color:#9ca3af">Kanal:</span>'+["g","u","c"].map(function(k){
      var lbl=k==="g"?"grounded":(k==="u"?"ungrounded":"kombiniert"); var on=mode===k;
      return '<button data-m="'+k+'" class="gwm" style="font-size:10.5px;padding:2px 8px;border-radius:7px;border:1px solid '+(on?"#1a1a2e":"#ccc")+';background:'+(on?"#1a1a2e":"#fff")+';color:'+(on?"#fff":"#282d37")+';cursor:pointer">'+lbl+'</button>';
    }).join("")+'</div>';
    var refSel = (d.explorer && d.refCandidates && d.refCandidates.length)
      ? ('<div style="display:flex;gap:5px;align-items:center;flex-wrap:wrap;justify-content:flex-end"><span style="font-size:10.5px;color:#9ca3af">vs</span>'+
         d.refCandidates.map(function(o){ var on=o===leader;
           return '<button data-r="'+o+'" class="gwr" style="font-size:10.5px;padding:2px 8px;border-radius:7px;border:1px solid '+(on?"#dc0028":"#ccc")+';background:'+(on?"#dc0028":"#fff")+';color:'+(on?"#fff":"#282d37")+';cursor:pointer">'+o+'</button>'; }).join("")+'</div>')
      : '';
    var sel='<div style="display:flex;flex-direction:column;gap:6px;align-items:flex-end">'+modeSel+refSel+brandSel+'</div>';

    // Balken
    var order=["authority","size","cite_share","relprice"];
    var segs=[{label:brand+": eigene Sichtbarkeit heute",val:baseSov,col:COL.base,isBase:true}];
    order.forEach(function(k){ if(contrib[k]!=null) segs.push({label:(AMP[k]||"")+" "+(LBL[k]||k),val:contrib[k],col:d.cols[k]||COL.rest,k:k}); });
    if(rest>0.05) segs.push({label:"Rest / unerklärt",val:rest,col:COL.rest});
    var total=leadSov>0?leadSov:segs.reduce(function(a,s){return a+s.val;},0);
    var _fpB=null,_fpL=null; (function(){ var _ar=(m&&m.authority_ranking)||[];
      _ar.forEach(function(x){ if(x.brand===brand)_fpB=x.mean_cite_share_pct; if(x.brand===leader)_fpL=x.mean_cite_share_pct; }); })();
    var compareHead='<div style="display:flex;align-items:stretch;gap:10px;margin:6px 0 4px">'+
      '<div style="flex:1;background:#f6f7f9;border-radius:8px;padding:10px 12px">'+
        '<div style="font-size:11px;color:#6b7280">'+brand+' · Ø Sichtbarkeit</div>'+
        '<div style="font-size:26px;font-weight:800;color:#282d37;line-height:1.1">'+pct(baseSov)+'</div>'+
        (_fpB!=null?'<div style="font-size:10.5px;color:#9ca3af">in '+pct(_fpB)+' der zitierten Quellen</div>':'')+'</div>'+
      '<div style="display:flex;flex-direction:column;justify-content:center;align-items:center;min-width:78px">'+
        '<div style="font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:.4px">Abstand</div>'+
        '<div style="font-size:20px;font-weight:800;color:#dc0028;line-height:1.1">'+pp(gap)+'</div></div>'+
      '<div style="flex:1;background:#fbeef0;border-radius:8px;padding:10px 12px;text-align:right">'+
        '<div style="font-size:11px;color:#b91c1c">'+leader+' · Marktführer</div>'+
        '<div style="font-size:26px;font-weight:800;color:#dc0028;line-height:1.1">'+pct(leadSov)+'</div>'+
        (_fpL!=null?'<div style="font-size:10.5px;color:#d19aa2">in '+pct(_fpL)+' der zitierten Quellen</div>':'')+'</div>'+
      '</div>'+
      '<div style="font-size:11.5px;color:#6b7280;margin:8px 0 2px">So füllt sich der Abstand von '+pp(gap)+' auf — von <b>'+brand+'s eigener Sichtbarkeit</b> (grau) bis zum <b style="color:#dc0028">'+leader+'-Niveau</b> (rot). Je länger ein Abschnitt, desto mehr trägt er zum Rückstand bei:</div>';
    var bar='<div style="display:flex;height:34px;border-radius:6px;overflow:hidden;margin:14px 0 6px;border:1px solid #eee">';
    segs.forEach(function(s){ var w=total>0?(s.val/total*100):0; if(w<=0)return;
      bar+='<div title="'+s.label+': '+(s.isBase?pct(s.val):pp(s.val))+'" style="width:'+w+'%;background:'+s.col+'"></div>'; });
    bar+='</div>';

    // Legende mit Anteilen am Gap
    var legend='<div style="display:grid;grid-template-columns:1fr auto auto;gap:2px 14px;font-size:12.5px;margin-top:6px">';
    legend+='<div><span style="display:inline-block;width:10px;height:10px;background:'+COL.base+';border-radius:2px;margin-right:6px"></span>'+brand+': eigene Sichtbarkeit heute</div><div style="text-align:right;font-weight:600">'+pct(baseSov)+'</div><div></div>';
    order.forEach(function(k){
      if(contrib[k]==null) return;
      var sh=gap>0?Math.round(100*contrib[k]/gap):null;
      legend+='<div><span style="display:inline-block;width:10px;height:10px;background:'+(d.cols[k]||COL.rest)+';border-radius:2px;margin-right:6px"></span>'+(AMP[k]||"")+' '+(LBL[k]||k)+'</div>'+
        '<div style="text-align:right;font-weight:600;color:'+(d.cols[k]||"#282d37")+'">'+pp(contrib[k])+'</div>'+
        '<div style="text-align:right;color:#9ca3af;font-size:11px">'+(sh!=null?("≈ "+sh+" % des Gaps"):"")+'</div>';
    });
    if(rest>0.05) legend+='<div><span style="display:inline-block;width:10px;height:10px;background:'+COL.rest+';border-radius:2px;margin-right:6px"></span>Rest / unerklärt</div><div style="text-align:right;font-weight:600">'+pp(rest)+'</div><div style="text-align:right;color:#9ca3af;font-size:11px">'+(gap>0?("≈ "+Math.round(100*rest/gap)+" %"):"")+'</div>';
    legend+='<div style="border-top:1px solid #eee;padding-top:4px"><span style="display:inline-block;width:10px;height:10px;background:'+COL.leader+';border-radius:2px;margin-right:6px"></span><b>'+leader+' (Marktführer)</b></div><div style="text-align:right;font-weight:700;border-top:1px solid #eee;padding-top:4px;color:'+COL.leader+'">'+pct(leadSov)+'</div><div style="border-top:1px solid #eee"></div>';
    legend+='</div>';

    var notes='<div style="font-size:11px;color:#6b7280;margin-top:10px;line-height:1.5">'+
      'Zerlegung: <b>'+d.label+'</b> · '+(d.n||"keine Angabe")+' Zellen, '+(d.nb||"keine Angabe")+' Marken, '+(d.nt!=null?(d.nt+' Themen'):'<span title="n_topics fehlt in diesem Modellblock — wird mit dem naechsten Nightly geliefert">Themenzahl: keine Angabe</span>')+' ('+modeLbl()+')'+(capped?' · Beiträge proportional auf 100 % des Gaps gekappt':'')+'. '+
      (d.explorer?'<b>Hinweis zur Aufteilung:</b> „Bekanntheit & Größe" ist ein fester Näherungswert (Marktanteil + Markenbekanntheit), keine geschätzte Größe — dadurch weniger mit der Quellpräsenz vermengt als zwei geschätzte Treiber. Die Trennung ist im gepoolten Modell richtungsstabil, bleibt aber eine <b>Tendenz</b>, kein Kausalnachweis. '+
        (function(){ var f=d.favors||{}; var ks=Object.keys(f); if(!ks.length) return '';
          var L={size:"Bekanntheit & Größe",cite_share:"Quellpräsenz",relprice:"Preisniveau"};
          return '<b>Spricht für '+brand+':</b> '+ks.map(function(k){return L[k]+" ("+pp(f[k])+")";}).join(", ")+' — dieser Faktor wirkt zugunsten von '+brand+' und ist im Wasserfall nicht als Rückstand dargestellt. '; })()
        :((contrib.size!=null||contrib.authority!=null)?'<b>Achtung:</b> Größe und Footprint sind bei so wenigen Marken statistisch nicht trennbar — sie werden bewusst als <b>eine</b> Autoritäts-Stufe geführt. ':''))+
      '⚪ nicht beeinflussbar · 🟡 mittelbar (Portale/Quellen) · 🟢 direkt beeinflussbar. Zerlegung, kein Kausalnachweis.</div>';

    // Themen-Hotspots
    var hs=topicHotspots(brand, leader);
    var hsHtml='';
    if(hs && hs.length){
      var top=hs.filter(function(r){return r.gap>1;}).slice(0,3).map(function(r){return r.name;});
      hsHtml='<div style="margin-top:16px;border-top:1px solid #f0f0f0;padding-top:12px">'+
        '<div style="font-size:13px;font-weight:700;margin-bottom:2px">Wo genau verliert '+brand+'? — Themen-Hotspots</div>'+
        '<div style="font-size:11px;color:#9ca3af;margin-bottom:8px">Je Thema: Sichtbarkeits-Rückstand zu '+leader+' und eigener Zitatanteil ('+modeLbl()+'). Rot = großer Gap bei schwacher Quellpräsenz → dort zuerst Content aufbauen.</div>'+
        '<table style="width:100%;border-collapse:collapse;font-size:12.5px"><thead><tr style="text-align:left;color:#64748b;border-bottom:1px solid #e2e8f0">'+
        '<th style="padding:5px 8px">Thema</th><th style="padding:5px 8px;text-align:right">'+brand+' SoV</th><th style="padding:5px 8px;text-align:right">'+leader+' SoV</th><th style="padding:5px 8px;text-align:right">Gap</th><th style="padding:5px 8px;text-align:right">Zitatanteil '+brand+' / '+leader+'</th><th style="padding:5px 8px;text-align:center">Einordnung</th></tr></thead><tbody>';
      hs.forEach(function(r){
        var neg=r.gap<0;
        hsHtml+='<tr style="border-bottom:1px solid #f1f5f9'+(r.gap>1&&r.citB<5&&r.citB<r.citL?';background:#fff8f8':'')+'">'+
          '<td style="padding:5px 8px;font-weight:600;color:#1e293b">'+r.name+'</td>'+
          '<td style="padding:5px 8px;text-align:right">'+pct(r.sovB)+'</td>'+
          '<td style="padding:5px 8px;text-align:right">'+pct(r.sovL)+'</td>'+
          '<td style="padding:5px 8px;text-align:right;font-weight:700;color:'+(neg?"#067d3a":(r.gap>5?"#b91c1c":"#282d37"))+'">'+(neg?"−":"")+pp(Math.abs(r.gap)).replace("+","")+(neg?" vorn":"")+'</td>'+
          '<td style="padding:5px 8px;text-align:right;color:#475569">'+pct(r.citB)+' / '+pct(r.citL)+'</td>'+
          '<td style="padding:5px 8px;text-align:center">'+prioChip(r)+'</td></tr>';
      });
      hsHtml+='</tbody></table>';
      if(top.length) hsHtml+='<div style="font-size:12px;color:#282d37;background:#f8f7f4;border-left:3px solid #dc0028;border-radius:4px;padding:9px 12px;margin-top:10px"><b>Prio-Empfehlung:</b> Größte Rückstände bei <b>'+top.join(", ")+'</b> — dort zitierfähige Inhalte und Portal-Präsenz zuerst ausbauen.</div>';
      hsHtml+='</div>';
    }

    box.innerHTML =
      '<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px">'+
        '<div><h3 style="font-size:16px;font-weight:700;margin:0">6 · Ursachenanalyse: Warum liegt '+leader+' vor '+brand+'?</h3>'+
        '<p style="font-size:12px;color:#6b7280;margin:2px 0 0">Woraus sich ERGOs Rückstand zum Marktführer zusammensetzt <span style="color:#9ca3af">('+modeLbl()+')</span></p></div>'+
        sel+'</div>'+ compareHead + bar + legend + notes + hsHtml + benchSection(brand, leader);

    box.querySelectorAll(".gwb").forEach(function(btn){
      btn.addEventListener("click", function(){ render(host, lm, btn.getAttribute("data-b")); });
    });
    box.querySelectorAll(".gwm").forEach(function(btn){
      btn.addEventListener("click", function(){ mode=btn.getAttribute("data-m"); render(host, lm, curBrand); });
    });
    box.querySelectorAll(".gwr").forEach(function(btn){
      btn.addEventListener("click", function(){ curRef=btn.getAttribute("data-r"); render(host, lm, curBrand); });
    });

    // 18.07.2026 Fix: GEO_SNAPSHOT laedt asynchron — fehlen die Hotspots noch,
    // spaeter erneut rendern (vorher fehlten sie dauerhaft, wenn der Snapshot
    // beim ersten Render noch nicht da war).
    /* 17.08.2026 (Revisions-Rest): Der Zaehler lag als EINE Eigenschaft auf der
       render-Funktion, aber jeder Tab-Klick startet ueber build() eine eigene
       Retry-Kette - mehrere Ketten zogen sich gegenseitig das 30er-Budget ab
       und renderten parallel doppelt. Jetzt haengt zusaetzlich ein Timer-Handle
       daneben: solange ein Nachversuch geplant ist, wird kein zweiter geplant
       und kein Budget verbraucht. */
    if(!hs){
      if(!render.__hsTimer && (render.__hsTries=(render.__hsTries||0)+1)<=30){
        render.__hsTimer=setTimeout(function(){ render.__hsTimer=null; render(host, lm, curBrand); },600);
      }
    } else { render.__hsTries=0; }
  }

  function build(){
    var host=document.querySelector('section[data-content="korrelation"]');
    if(!host || !window.__GW_LM) return false;
    render(host, window.__GW_LM, curBrand);
    return true;
  }
  ready(function(){
    // Branchen-Benchmark (31.07.2026): parallel laden; __GW_BENCH bleibt bis
    // dahin undefined ("wird geladen"), danach Objekt oder null ("nicht
    // erreichbar") — danach einmal neu rendern.
    fetch("data/benchmark_branchen.json?t="+Date.now(),{cache:"no-store"})
      .then(function(r){ return r.ok?r.json():null; }).catch(function(){ return null; })
      .then(function(b){ window.__GW_BENCH=b; try{ build(); }catch(e){} });
    getData().then(function(d){
      window.__GW_LM=(d && d.level_model)?d.level_model:{}; window.__GW_PLP=(d && d.price_level_pooled)?d.price_level_pooled:null;
      window.__gwSetMode=function(m){ mode=m; build(); };
      var tries=0; (function wait(){ tries++; if(build())return; if(tries<40) setTimeout(wait,300); })();
      var tab=document.querySelector('[data-tab="korrelation"]');
      if(tab) tab.addEventListener("click", function(){ [150,600,1400].forEach(function(x){ setTimeout(build,x); }); });
    });
  });
})();
