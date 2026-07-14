/* ============================================================
   ERGO LLM-Cockpit — Korrelations-Reiter: Zwei-Ebenen-Synthese v3
   Statistik-Upgrade 2026-07-14:
   - Treiber-Ranking als Forest-Plot mit 95%-Konfidenzintervallen
     (Punktschätzer + CI-Band + Nulllinie statt nackter Balken)
   - Within-/Between-Effekte sauber getrennt (Estimand-Regel aus
     10_TREIBERMODELL_DESIGN.md): Within = Hebel im Thema,
     Between = Markenniveau (erklärt den Autoritätsvorsprung)
   - Ehrliche Fallzahl: Between-Effekte haben effektiv n = Marken
   - Über-/Unterperformer-Scatter (cite_share vs. SoV, OLS-Gerade)
   Quelle: window.CORRELATION_IMPACT (level_model, multivariate,
   validation). Additiv, verändert bestehende Sektionen nicht.
   ============================================================ */
(function () {
  "use strict";
  function ready(fn){ if(document.readyState!=="loading") fn(); else document.addEventListener("DOMContentLoaded",fn); }
  function num(v,d){ return (v==null||isNaN(v))?"—":(Math.round(v*Math.pow(10,d))/Math.pow(10,d)).toFixed(d).replace(".",","); }
  function signed(v,d){ return (v==null||isNaN(v))?"—":((v>0?"+":"")+num(v,d)); }
  function clamp(v,a,b){ return Math.max(a,Math.min(b,v)); }

  var mode="g";
  function seg(lm){ return mode==="g"?lm.grounded:(mode==="u"?lm.ungrounded:lm.combined); }
  function segOf(o){ return o?(mode==="g"?o.grounded:(mode==="u"?o.ungrounded:o.combined)):null; }
  function modeLbl(){ return mode==="g"?"grounded (Web-Suche)":(mode==="u"?"ungrounded (ChatGPT)":"kombiniert (alle LLMs)"); }
  function evChip(kind){
    if(kind===3) return '<span style="font-size:10px;font-weight:700;color:#067d3a;background:#e6f5ec;border-radius:4px;padding:2px 7px">kausal belegt</span>';
    if(kind===2) return '<span style="font-size:10px;font-weight:700;color:#6b7280;background:#eef0f2;border-radius:4px;padding:2px 7px">kein belastbarer Effekt</span>';
    if(kind===1) return '<span style="font-size:10px;font-weight:700;color:#8a6d00;background:#fdf3d7;border-radius:4px;padding:2px 7px">konsistente Assoziation · explorativ</span>';
    return '<span style="font-size:10px;font-weight:700;color:#6b7280;background:#eef0f2;border-radius:4px;padding:2px 7px">nicht nachweisbar</span>';
  }
  function hbar(wPct,col,h){ return '<div style="flex:1;background:#eef0f2;border-radius:6px;height:'+(h||14)+'px;overflow:hidden"><div style="width:'+clamp(wPct,2,100)+'%;height:100%;background:'+col+';border-radius:6px"></div></div>'; }

  // Sicherheits-Ampel aus prob_direction (Richtungssicherheit). Vorzeichen-Instabilität stuft herab.
  function conf(p,stable){
    var r;
    if(p==null) r={t:"nicht bewertbar",c:"#6b7280",bg:"#eef0f2"};
    else if(p>=0.99) r={t:"sehr sicher",c:"#067d3a",bg:"#e6f5ec"};
    else if(p>=0.90) r={t:"wahrscheinlich",c:"#8a6d00",bg:"#fdf3d7"};
    else r={t:"noch unklar",c:"#6b7280",bg:"#eef0f2"};
    if(stable===false && r.t!=="noch unklar" && r.t!=="nicht bewertbar") r={t:"noch unklar",c:"#6b7280",bg:"#eef0f2"};
    r.p=p; return r;
  }
  function confChip(cf){ return '<span style="font-size:10px;font-weight:700;color:'+cf.c+';background:'+cf.bg+';border-radius:4px;padding:2px 7px">'+cf.t+(cf.p!=null?' · P='+num(cf.p,2):'')+'</span>'; }
  function ampelChip(k){
    var map={direkt:["🟢","direkt beeinflussbar"],mittelbar:["🟡","mittelbar (über Dritte)"],strukturell:["⚪","strukturell (kein Hebel)"]};
    var v=map[k]||map.strukturell;
    return '<span style="font-size:10px;color:#374151;background:#f3f4f6;border-radius:4px;padding:2px 7px">'+v[0]+' '+v[1]+'</span>';
  }
  function barColFor(cf){ return cf.c==="#067d3a"?"#dc0028":(cf.c==="#8a6d00"?"#e0a800":"#9ca3af"); }

  /* ---------- Forest-Plot-Datenaufbereitung ----------
     Effekte werden in pp SoV je +1 SD des Treibers standardisiert,
     inkl. 95%-CI (CI der Roh-Koeffizienten × SD des Treibers).   */
  function stdRow(eff, base){
    // eff = {coef..., ci95_low, ci95_high, prob_direction, effect_std_pp}
    if(!eff || eff.effect_std_pp==null) return null;
    var coefKey = eff.coef_pp_sov_per_pp_citeshare!=null ? eff.coef_pp_sov_per_pp_citeshare : eff.coef;
    var sd = (coefKey && Math.abs(coefKey)>1e-9) ? Math.abs(eff.effect_std_pp / coefKey) : null;
    var lo = (sd!=null && eff.ci95_low!=null) ? eff.ci95_low*sd : null;
    var hi = (sd!=null && eff.ci95_high!=null) ? eff.ci95_high*sd : null;
    if(lo!=null && hi!=null && lo>hi){ var t=lo; lo=hi; hi=t; }
    return Object.assign({est:eff.effect_std_pp, lo:lo, hi:hi, p:eff.prob_direction}, base||{});
  }

  function driverRows(C){
    var lm=C.level_model||{}; var m=seg(lm)||{};
    var pm=segOf(lm.price_model)||{};
    var rows=[];
    if(m.between_effect){
      var r1=stdRow(m.between_effect,{
        label:"Zitations-Footprint — Markenniveau",
        sub:"Warum Marke A sichtbarer ist als B (Between/Mundlak)",
        stable:(m.between_loo||{}).sign_stable, ctrl:"mittelbar",
        nTxt:"n eff. = "+(m.n_brands||"?")+" Marken",
        plain:"Marken mit dauerhaft höherer Quellpräsenz sind sichtbarer. Erklärt den Autoritätsvorsprung (z. B. Allianz). Stärkster Befund."});
      if(r1) rows.push(r1);
    }
    if(m.within_effect){
      var r2=stdRow(m.within_effect,{
        label:"Zitations-Footprint — Hebel im Thema",
        sub:"Bewegt MEHR eigener Footprint im Thema die Sichtbarkeit? (Within, themenbereinigt)",
        stable:null, ctrl:"direkt",
        nTxt:"n = "+(m.n_cells||"?")+" Zellen · "+(m.n_topics||"?")+" Themen",
        plain:"Das ist der eigentliche ERGO-Hebel: eigenen Zitatanteil in einzelnen Themen ausbauen."});
      if(r2) rows.push(r2);
    }
    if(pm.between_effect){
      var r3=stdRow(pm.between_effect,{
        label:"Relativpreis — Markenniveau",
        sub:"Teurer vs. günstiger (Between, Preis-Level-Modell)",
        stable:(pm.between_loo||{}).sign_stable, ctrl:"direkt",
        nTxt:"n eff. = "+(pm.n_brands||"?")+" Marken · "+(pm.n_topics||"?")+" Themen",
        plain:"Preisniveau hängt bisher kaum mit Sichtbarkeit zusammen — schwaches, unsicheres Signal (sehr kleine Fallzahl). Der Nullbefund ist selbst eine Aussage."});
      if(r3) rows.push(r3);
    }
    rows.push({label:"Einzel-Aktivitäten / Events (kurzfristig)",
      sub:"Seitenänderungen, Presse, Bewertungen (Event-Study, multivariat)",
      est:0, lo:null, hi:null, p:null, stable:null, ctrl:"direkt", events:true,
      nTxt:"n = "+((C.multivariate||{}).n_points||"?")+" Intervalle",
      plain:"Bisher kein verlässlicher Kurzfrist-Effekt: das Event-Modell schlägt die Marken-Basislinie out-of-sample nicht."});
    // Sortierung: Events ans Ende, sonst nach |Effekt|
    rows.sort(function(a,b){ if(a.events) return 1; if(b.events) return -1; return Math.abs(b.est||0)-Math.abs(a.est||0); });
    return rows;
  }

  /* ---------- Forest-Plot (HTML/CSS) ---------- */
  function forestPlot(C){
    var rows=driverRows(C);
    // Skala über alle CI-Grenzen und Schätzer, symmetrisch um 0
    var mx=1;
    rows.forEach(function(r){
      mx=Math.max(mx, Math.abs(r.est||0), Math.abs(r.lo||0), Math.abs(r.hi||0));
    });
    mx=mx*1.08;
    function x(v){ return 50 + 50*(v/mx); } // Prozentposition (0 = Mitte)

    var body=rows.map(function(r){
      var cf=r.events?{t:"kein belastbarer Effekt",c:"#6b7280",bg:"#eef0f2"}:conf(r.p,r.stable);
      var col=r.events?"#9ca3af":barColFor(cf);
      var unstable=(r.stable===false&&!r.events)?'<span style="font-size:10px;color:#b45309">↔ Vorzeichen nicht stabil (LOO)</span>':"";
      var nchip=r.nTxt?'<span style="font-size:10px;color:#9ca3af">'+r.nTxt+'</span>':"";
      var ciTxt=(r.lo!=null&&r.hi!=null)?('<span style="font-size:10px;color:#9ca3af">95%-CI '+signed(r.lo,1)+' … '+signed(r.hi,1)+' pp</span>'):"";
      // Plot-Zeile: Nulllinie, CI-Band, Punktschätzer
      var plot='<div style="position:relative;height:20px;background:#f7f8fa;border-radius:4px;overflow:hidden">'+
        '<div style="position:absolute;left:50%;top:0;bottom:0;width:1px;background:#c8ccd2"></div>';
      if(r.lo!=null&&r.hi!=null){
        var l=clamp(Math.min(x(r.lo),x(r.hi)),0,100), rgt=clamp(Math.max(x(r.lo),x(r.hi)),0,100);
        plot+='<div style="position:absolute;left:'+l+'%;width:'+Math.max(rgt-l,0.5)+'%;top:7px;height:6px;background:'+col+'55;border-radius:3px"></div>';
      }
      if(!r.events){
        plot+='<div style="position:absolute;left:calc('+clamp(x(r.est),0,100)+'% - 4px);top:5px;width:8px;height:10px;background:'+col+';border-radius:2px"></div>';
      } else {
        plot+='<div style="position:absolute;left:calc(50% - 4px);top:5px;width:8px;height:10px;border:2px solid '+col+';border-radius:2px;background:#fff"></div>';
      }
      plot+='</div>';
      var eff=r.events?"~0":signed(r.est,1)+" pp";
      return '<div style="margin:11px 0">'+
        '<div style="display:grid;grid-template-columns:230px 1fr 74px;align-items:center;gap:10px">'+
          '<div><div style="font-size:12.5px;font-weight:600;line-height:1.25">'+r.label+'</div>'+
          '<div style="font-size:10.5px;color:#9ca3af">'+(r.sub||'')+'</div></div>'+
          plot+
          '<div style="font-size:12px;font-weight:700;text-align:right;color:#1a1a2e">'+eff+'</div></div>'+
        '<div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-top:4px">'+confChip(cf)+ampelChip(r.ctrl)+ciTxt+unstable+nchip+'</div>'+
        '<div style="font-size:11px;color:#6b7280;margin-top:2px">'+r.plain+'</div>'+
      '</div>';
    }).join('');
    return '<div style="border:1px solid #eee;border-radius:10px;padding:14px 16px;margin-bottom:14px">'+
      '<div style="font-size:13px;font-weight:700;margin-bottom:2px">Treiber-Ranking (Forest-Plot) — was bewegt die Sichtbarkeit? <span style="font-weight:500;color:#9ca3af">('+modeLbl()+')</span></div>'+
      '<div style="font-size:11px;color:#9ca3af;margin-bottom:4px">Quadrat = bester Schätzwert · Band = 95%-Konfidenzintervall · Mittellinie = kein Effekt. Schneidet das Band die Mittellinie, ist der Effekt statistisch nicht gesichert.</div>'+
      '<div style="display:grid;grid-template-columns:230px 1fr 74px;gap:10px;font-size:10px;color:#c0c4cb"><div></div><div style="display:flex;justify-content:space-between"><span>−'+num(mx,0)+' pp</span><span>0</span><span>+'+num(mx,0)+' pp</span></div><div></div></div>'+
      body+
      '<div style="font-size:10.5px;color:#9ca3af;margin-top:8px">Effekt in <b>pp Sichtbarkeit je +1 Standardabweichung</b> des Treibers (Mundlak/CRE-Level-Modell). <b>Wichtig:</b> Markenniveau-Effekte (Between) stützen sich effektiv nur auf die Zahl der <b>Marken</b>, nicht der Zellen — deshalb steht dort „n eff.". Alles Zusammenhänge, kein Kausalnachweis (Ausnahme: Maßnahmen-Wirkung/DiD).</div>'+
    '</div>';
  }

  /* ---------- Über-/Unterperformer-Scatter ---------- */
  var scatterChart=null;
  function scatterBlock(){
    return '<div style="border:1px solid #eee;border-radius:10px;padding:14px 16px;margin-bottom:14px">'+
      '<div style="font-size:13px;font-weight:700;margin-bottom:2px">Über-/Unterperformer — Quellpräsenz vs. Sichtbarkeit <span style="font-weight:500;color:#9ca3af" id="korrScatterMode"></span></div>'+
      '<div style="font-size:11px;color:#9ca3af;margin-bottom:8px">Jeder Punkt = eine Marke. Linie = erwartete Sichtbarkeit bei gegebener Quellpräsenz (OLS). Über der Linie = Marke macht aus ihrer Quellpräsenz überdurchschnittlich viel Sichtbarkeit.</div>'+
      '<div style="position:relative;height:260px"><canvas id="korrScatterCv"></canvas></div>'+
      '<div style="font-size:11px;color:#6b7280;margin-top:6px" id="korrScatterNote"></div>'+
    '</div>';
  }
  function renderScatter(C){
    var lm=C.level_model||{}; var m=seg(lm)||{}; var ar=m.authority_ranking||[];
    var cv=document.getElementById("korrScatterCv");
    var md=document.getElementById("korrScatterMode");
    var noteEl=document.getElementById("korrScatterNote");
    if(!cv || !window.Chart) return;
    if(md) md.textContent="("+modeLbl()+")";
    var pts=ar.filter(function(a){return a.mean_cite_share_pct!=null && a.mean_sov_pct!=null;});
    if(pts.length<3){ if(noteEl) noteEl.textContent="Zu wenige Marken mit Daten."; return; }
    // OLS y = a + b x
    var n=pts.length, sx=0, sy=0, sxx=0, sxy=0;
    pts.forEach(function(p){ sx+=p.mean_cite_share_pct; sy+=p.mean_sov_pct; sxx+=p.mean_cite_share_pct*p.mean_cite_share_pct; sxy+=p.mean_cite_share_pct*p.mean_sov_pct; });
    var b=(n*sxy-sx*sy)/Math.max(n*sxx-sx*sx,1e-9), a=(sy-b*sx)/n;
    var xmin=Math.min.apply(null,pts.map(function(p){return p.mean_cite_share_pct;})), xmax=Math.max.apply(null,pts.map(function(p){return p.mean_cite_share_pct;}));
    var pad=(xmax-xmin)*0.08||1; xmin-=pad; xmax+=pad;
    var leader=m.leader;
    function colOf(brand){ return brand==="ERGO"?"#dc0028":(brand===leader?"#003781":"#9ca3af"); }
    var data={
      datasets:[
        {type:"scatter", label:"Marken",
         data:pts.map(function(p){return {x:p.mean_cite_share_pct,y:p.mean_sov_pct,brand:p.brand};}),
         pointRadius:pts.map(function(p){return (p.brand==="ERGO"||p.brand===leader)?7:5;}),
         pointBackgroundColor:pts.map(function(p){return colOf(p.brand);}),
         pointBorderColor:"#fff", pointBorderWidth:1},
        {type:"line", label:"OLS", data:[{x:xmin,y:a+b*xmin},{x:xmax,y:a+b*xmax}],
         borderColor:"#c8ccd2", borderWidth:2, borderDash:[6,4], pointRadius:0, fill:false}
      ]};
    if(scatterChart){ try{scatterChart.destroy();}catch(e){} scatterChart=null; }
    try{
      scatterChart=new Chart(cv,{data:data,options:{
        responsive:true, maintainAspectRatio:false, animation:false,
        plugins:{legend:{display:false}, tooltip:{callbacks:{label:function(ctx){
          var raw=ctx.raw||{}; if(raw.brand==null) return null;
          var exp=a+b*raw.x, res=raw.y-exp;
          return raw.brand+": "+num(raw.y,1)+"% SoV bei "+num(raw.x,1)+"% Zitatanteil ("+(res>=0?"+":"")+num(res,1)+" pp vs. erwartet)";
        }}}},
        scales:{x:{title:{display:true,text:"Zitatanteil (Quellpräsenz) %"},min:Math.floor(xmin),max:Math.ceil(xmax)},
                y:{title:{display:true,text:"Share of Voice %"},beginAtZero:true}}
      }});
    }catch(e){}
    if(noteEl){
      var er=pts.filter(function(p){return p.brand==="ERGO";})[0];
      if(er){
        var res=er.mean_sov_pct-(a+b*er.mean_cite_share_pct);
        noteEl.innerHTML="<b>ERGO:</b> "+(res>=0?("+"+num(res,1)+" pp über"):(num(res,1)+" pp unter"))+" der erwarteten Sichtbarkeit — "+
          (res>=0?"die „Verwertung“ der Quellpräsenz ist gut, die Baustelle ist die Quellpräsenz selbst.":"auch die Verwertung der vorhandenen Quellpräsenz ist unterdurchschnittlich.")+
          " <span style='color:#9ca3af'>Steigung "+signed(b,2)+" pp SoV je pp Zitatanteil (deskriptive OLS über "+n+" Marken, entspricht dem Between-Zusammenhang).</span>";
      }
    }
  }

  /* ---------- Kachel Ebene A ---------- */
  function tileA(C){
    var lm=C.level_model||{}; var m=seg(lm);
    if(!m||!m.available) return '<div style="font-size:13px;color:#6b7280">Für diese Auswahl noch zu wenige Daten.</div>';
    var ar=m.authority_ranking||[]; var lead=m.leader;
    var al=ar.filter(function(a){return a.brand===lead;})[0]||{}; var er=ar.filter(function(a){return a.brand==="ERGO";})[0]||{};
    var we=m.within_effect||{}; var be=m.between_effect||{}; var bstable=(m.between_loo||{}).sign_stable;
    var w=we.coef_pp_sov_per_pp_citeshare;
    var wcf=conf(we.prob_direction,null); var bcf=conf(be.prob_direction,bstable);
    var mx=Math.max(al.mean_cite_share_pct||1, er.mean_cite_share_pct||1, 1);
    return '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:4px"><b style="font-size:14px">Ebene A · Niveau (Stock)</b> '+evChip(1)+'</div>'+
      '<div style="font-size:12px;color:#4b5563;margin:0 0 8px">Treiber: <b>Zitations-Footprint</b> (Präsenz in den zitierten Quellen).</div>'+
      '<div style="font-size:24px;font-weight:700;color:#1a1a2e;line-height:1.1">'+signed(w,1)+' <span style="font-size:12px;font-weight:500;color:#9ca3af">pp SoV je +1 pp Zitatanteil (Within/Hebel)</span></div>'+
      '<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:4px 0 3px">'+confChip(wcf)+'<span style="font-size:10.5px;color:#9ca3af">themenbereinigt · 95%-CI '+signed(we.ci95_low,2)+'…'+signed(we.ci95_high,2)+'</span></div>'+
      (be.effect_std_pp!=null?('<div style="font-size:11.5px;color:#4b5563;margin:2px 0 10px">Marken-Ebene (erklärt den Autoritätsvorsprung): <b>'+signed(be.effect_std_pp,1)+' pp</b> je +1&nbsp;SD Footprint&nbsp; '+confChip(bcf)+' <span style="font-size:10px;color:#9ca3af">n eff. = '+(m.n_brands||"?")+' Marken</span></div>'):'<div style="margin-bottom:8px"></div>')+
      '<div style="font-size:11px;color:#6b7280;margin-bottom:3px">Zitatanteil je Marke (Ø):</div>'+
      '<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px"><span style="width:56px;font-size:11px">ERGO</span>'+hbar(100*(er.mean_cite_share_pct||0)/mx,'#dc0028',12)+'<span style="width:38px;font-size:11px;text-align:right">'+num(er.mean_cite_share_pct,1)+'%</span></div>'+
      '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px"><span style="width:56px;font-size:11px">'+lead+'</span>'+hbar(100*(al.mean_cite_share_pct||0)/mx,'#9ca3af',12)+'<span style="width:38px;font-size:11px;text-align:right">'+num(al.mean_cite_share_pct,1)+'%</span></div>'+
      '<button id="korrGeoLink" style="font-size:12px;padding:6px 12px;border-radius:8px;border:1px solid #dc0028;background:#fff;color:#dc0028;cursor:pointer">→ Grafik &amp; Details (Reiter „LLM-Sichtbarkeit")</button>';
  }

  /* ---------- Kachel Ebene B ---------- */
  function tileB(C){
    var mv=C.multivariate||{}; var coefs=mv.coefficients||{};
    var nTot=Object.keys(coefs).length;
    var nSig=Object.keys(coefs).filter(function(k){return coefs[k].significant;}).length;
    var val=C.validation||{}; var oos=(val.out_of_sample||{}).r2_oos_vs_baseline; var days=C.sov_measure_days;
    var fp=val.placebo_false_positive_rate;
    // Ganzes Modell schlägt die Basislinie out-of-sample nicht (R²<=0) => kein Einzeleffekt ist verlässlich.
    var nRel=(oos!=null && oos<=0)?0:nSig;
    var spuriousNote=(nSig>nRel)?('<div style="font-size:10.5px;color:#b45309;margin:2px 0 8px">'+nSig+' Effekt statistisch auffällig, aber Modell ohne Vorhersagekraft → als Rauschen gewertet.</div>'):'';
    return '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:4px"><b style="font-size:14px">Ebene B · Bewegung (Flow)</b> '+evChip(2)+'</div>'+
      '<div style="font-size:12px;color:#4b5563;margin:0 0 8px">Kurzfristige Events: Seitenänderungen, neue Seiten, Presse, Bewertungen.</div>'+
      '<div style="font-size:24px;font-weight:700;color:#1a1a2e;line-height:1.1">'+nRel+' / '+nTot+' <span style="font-size:12px;font-weight:500;color:#9ca3af">Event-Typen mit verlässlicher Wirkung</span></div>'+
      '<div style="font-size:11px;color:#9ca3af;margin:2px 0 6px">= kein belastbarer Kurzfrist-Effekt</div>'+
      spuriousNote+
      '<div style="font-size:12px;color:#4b5563">Große verlässliche Tageseffekte sind <b>ausgeschlossen</b> (Out-of-Sample R² '+num(oos,2)+' ggü. Basislinie). Kleine Effekte &lt;~1 pp sind bei '+days+' Messtagen nicht ausschließbar.</div>'+
      '<div style="font-size:11px;color:#9ca3af;margin-top:8px">Placebo-Falsch-Positiv-Rate '+(fp!=null?num(fp*100,1)+'&nbsp;%':'—')+' (Ziel ≈5 % → Modell ist konservativ/ehrlich). Nur bei web-gestützten LLMs plausibel; bei ChatGPT Rauschen.</div>';
  }

  function fazit(C){
    var lm=C.level_model||{}; var m=seg(lm)||{}; var ar=m.authority_ranking||[];
    var al=ar.filter(function(a){return a.brand===m.leader;})[0]||{}; var er=ar.filter(function(a){return a.brand==="ERGO";})[0]||{};
    var over=(er.mean_sov_pct!=null && er.mean_cite_share_pct!=null && er.mean_sov_pct>er.mean_cite_share_pct)?
      (' <b>Lichtblick:</b> ERGO macht aus seiner Quellpräsenz überdurchschnittlich viel Sichtbarkeit ('+num(er.mean_sov_pct,0)+' % SoV bei nur '+num(er.mean_cite_share_pct,0)+' % Zitatanteil, siehe Scatter) — die eigentliche Baustelle ist also die Quellpräsenz selbst, nicht die „Verwertung".'):'';
    return '<b>Kurz gesagt:</b> Sichtbarkeit kommt aus <b>Quellpräsenz</b>, nicht aus einzelnen Aktionen. ERGO ist in den zitierten Quellen schwächer vertreten ('+num(er.mean_cite_share_pct,0)+' % vs. '+(m.leader||"Allianz")+' '+num(al.mean_cite_share_pct,0)+' %) — genau das erklärt den Großteil des Rückstands.'+over+' <b>Preis</b> ist bisher nur ein schwacher, unsicherer Treiber. <b>Hebel:</b> eigene Inhalte zitierfähig ausbauen, priorisiert dort, wo heute Portale dominieren. Ob das kausal wirkt, prüfen wir über Experimente (Maßnahmen-Wirkung / DiD).';
  }

  function details(C){
    var lm=C.level_model||{}; var m=seg(lm)||{};
    var g=(m.gap_decomposition||{})["ERGO"]; var share=g&&g.share_explained!=null?Math.round(Math.min(g.share_explained,1)*100):null;
    var loo=m.between_loo;
    var looTxt = loo? ('Robustheit (Leave-one-brand-out): Vorzeichen bleibt beim Weglassen jeder einzelnen Marke stabil ('+(loo.sign_stable?'ja':'NEIN')+'; Between-Spanne '+signed(loo.min,2)+'…'+signed(loo.max,2)+').') : '';
    return '<div style="font-size:12px;color:#4b5563;line-height:1.6">'+
      (share!=null?('<b>Gap-Zerlegung:</b> Rund <b>'+share+' %</b> des SoV-Abstands zu '+(m.leader||"Allianz")+' gehen statistisch mit dem geringeren Zitations-Footprint einher — eine <b>Zerlegung, kein Kausalnachweis</b> (ein Teil dürfte allgemeine Markenstärke sein). Der Within-Befund ('+signed((m.within_effect||{}).coef_pp_sov_per_pp_citeshare,1)+' pp/pp, themenbereinigt) stützt, dass Footprint eigenständig wirkt.<br>'):'')+
      (looTxt?(looTxt+'<br>'):'')+
      'Modellgüte: Zusammenhang r '+num(m.raw_pearson_r,2)+', R² '+(m.r2_within_topics==null?'—':Math.round(m.r2_within_topics*100)+' %')+' ('+modeLbl()+').'+
      (mode==="u"?' <b>Achtung:</b> Das sehr hohe R² bei ungrounded ist kein Kausal-Triumph — Zitatanteil und ChatGPT-SoV bilden teils dieselbe latente Markenautorität ab.':'')+'<br>'+
      '<b>Ehrliche Fallzahlen:</b> Within-Effekte nutzen alle '+(m.n_cells||'?')+' Zellen; Between-Effekte („Markenniveau") stützen sich effektiv nur auf '+(m.n_brands||'?')+' Marken — die CIs sind entsprechend breit zu lesen. Der <b>Preis-Treiber</b> stammt aus dem Preis-Level-Modell (n eff. = '+(((segOf((C.level_model||{}).price_model))||{}).n_brands||'?')+' Marken, wenige Themen) und ist bewusst als schwach/unsicher markiert.<br>'+
      '<span style="color:#9ca3af"><b>Sicherheit</b> (Richtungssicherheit P): '+confChip({t:"sehr sicher",c:"#067d3a",bg:"#e6f5ec",p:null})+' P≥0,99 · '+confChip({t:"wahrscheinlich",c:"#8a6d00",bg:"#fdf3d7",p:null})+' 0,90–0,99 · '+confChip({t:"noch unklar",c:"#6b7280",bg:"#eef0f2",p:null})+' &lt;0,90 oder Vorzeichen instabil. <b>Beeinflussbarkeit:</b> '+ampelChip("direkt")+' '+ampelChip("mittelbar")+' '+ampelChip("strukturell")+'.<br>Methodik: Mundlak/CRE-Level-Modell (Zelle = Marke × Thema, Themen-FE); Zusammenhänge, kein Kausalnachweis (Ausnahme DiD). Zitatanteil und Sichtbarkeit stammen teils aus denselben LLM-Antworten (mögliche Überlappung). Evidenz-Skala: '+evChip(3)+' (nur DiD) · '+evChip(1)+' · '+evChip(2)+'</span></div>';
  }

  function wieBeeinflussen(){
    return '<div style="border:1px dashed #dc0028;border-radius:10px;padding:12px 14px;margin-top:12px;background:#fffafb">'+
      '<div style="font-size:13px;font-weight:700;color:#dc0028;margin-bottom:6px">So beeinflussen Sie es — Hebel nach Stärke</div>'+
      '<div style="font-size:12.5px;color:#282d37;line-height:1.6">'+
      '<b>1. Eigene Inhalte zitierfähig ausbauen</b> (größter Hebel): Themen-Hubs, FAQ, klare Definitionen, Tabellen, strukturierte Daten — damit LLMs ergo.de als Quelle zitieren.<br>'+
      '<b>2. Präsenz auf den zitierten Portalen</b> (Check24, Verivox) &amp; Testquellen (test.de): Listung, Rang, Bewertungen.<br>'+
      '<b>3. Bewertungen &amp; Presse</b> als flankierende Signale.'+
      '</div>'+
      '<div style="font-size:11.5px;color:#6b7280;margin-top:6px">→ <b>Welche Quellen je Thema zählen</b>, zeigt die <b>Kanal-Analyse</b> im Reiter „LLM-Sichtbarkeit". Den <b>echten Wirkungs-Effekt</b> messen wir über Experimente (Maßnahmen-Wirkung / DiD).</div>'+
      '</div>';
  }

  function renderPanel(host, C){
    var card=document.getElementById("korrSynth");
    if(!card){ card=document.createElement("div"); card.id="korrSynth"; card.className="bg-white rounded-xl shadow p-6 mb-6"; host.insertBefore(card, host.firstChild); }
    card.innerHTML=
      '<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;margin-bottom:12px">'+
        '<div><h3 style="font-size:17px;font-weight:700;margin:0">Was treibt die LLM-Sichtbarkeit?</h3>'+
        '<p style="font-size:12px;color:#6b7280;margin:2px 0 0">Zwei Ebenen: dauerhaftes <b>Niveau</b> (Quellpräsenz) vs. kurzfristige <b>Bewegung</b> (Events). Forest-Plot: je Treiber <b>Stärke</b>, <b>Unsicherheit (95%-CI)</b> und <b>Beeinflussbarkeit</b>.</p></div>'+
        '<div id="korrToggle" style="display:flex;gap:6px">'+
          '<button data-m="g" class="ksw" style="font-size:11px;padding:4px 10px;border-radius:8px;border:1px solid #dc0028;background:#dc0028;color:#fff;cursor:pointer">grounded</button>'+
          '<button data-m="u" class="ksw" style="font-size:11px;padding:4px 10px;border-radius:8px;border:1px solid #ccc;background:#fff;color:#282d37;cursor:pointer">ungrounded</button>'+
          '<button data-m="c" class="ksw" style="font-size:11px;padding:4px 10px;border-radius:8px;border:1px solid #ccc;background:#fff;color:#282d37;cursor:pointer">beides</button>'+
        '</div>'+
      '</div>'+
      '<div id="korrLever">'+forestPlot(C)+'</div>'+
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">'+
        '<div style="border:1px solid #eee;border-radius:10px;padding:14px" id="korrA">'+tileA(C)+'</div>'+
        '<div style="border:1px solid #eee;border-radius:10px;padding:14px;background:#fafafa" id="korrB">'+tileB(C)+'</div>'+
      '</div>'+
      '<div id="korrScatterWrap" style="margin-top:16px">'+scatterBlock()+'</div>'+
      '<div style="font-size:12.5px;color:#282d37;background:#f8f7f4;border-left:3px solid #dc0028;border-radius:4px;padding:11px 14px;margin-top:2px;line-height:1.55" id="korrFazit">'+fazit(C)+'</div>'+
      wieBeeinflussen()+
      '<details style="margin-top:12px"><summary style="cursor:pointer;font-size:12px;font-weight:600;color:#6b7280">Methodik &amp; Details anzeigen</summary>'+
        '<div style="margin-top:8px" id="korrDet">'+details(C)+'</div></details>';

    card.querySelectorAll(".ksw").forEach(function(btn){
      btn.addEventListener("click",function(){
        mode=btn.getAttribute("data-m");
        card.querySelectorAll(".ksw").forEach(function(b){var on=b.getAttribute("data-m")===mode;b.style.background=on?"#dc0028":"#fff";b.style.color=on?"#fff":"#282d37";b.style.borderColor=on?"#dc0028":"#ccc";});
        document.getElementById("korrLever").innerHTML=forestPlot(C);
        document.getElementById("korrA").innerHTML=tileA(C);
        document.getElementById("korrFazit").innerHTML=fazit(C);
        document.getElementById("korrDet").innerHTML=details(C);
        renderScatter(C);
        wireGeoLink();
        // Gap-Wasserfall auf denselben Modus schalten (falls geladen)
        if(window.__gwSetMode) try{ window.__gwSetMode(mode); }catch(e){}
      });
    });
    renderScatter(C);
    wireGeoLink();
  }
  function wireGeoLink(){ var b=document.getElementById("korrGeoLink"); if(b) b.addEventListener("click",function(){ var t=document.querySelector('[data-tab="geo"]'); if(t){ t.click(); window.scrollTo({top:0,behavior:"smooth"}); } }); }

  // Detail-/Monitoring-Sektionen einklappen; Alt-Titel ausblenden
  function tidy(host){
    [].slice.call(host.children).forEach(function(el){
      if(el.id!=="korrSynth" && el.id!=="korrDetails" && el.id!=="gapWaterfallBox" && /^🔗\s*Korrelation/.test((el.innerText||"").trim())) el.style.display="none";
    });
    if(document.getElementById("korrDetails")) return;
    var rxs=[/Validierte Impact-Analyse/,/Maßnahmen-Wirkung/,/Share of Voice/,/Tagesübersicht/,/Mention-Tracking/,/Event-Stream/];
    var kids=[].slice.call(host.children); var toCollapse=[];
    rxs.forEach(function(rx){ var b=kids.filter(function(el){ return el.id!=="korrSynth"&&el.id!=="korrDetails"&&el.id!=="gapWaterfallBox"&&rx.test((el.innerText||"").slice(0,90)); })[0]; if(b&&toCollapse.indexOf(b)<0) toCollapse.push(b); });
    if(toCollapse.length){
      var det=document.createElement("details"); det.id="korrDetails"; det.className="bg-white rounded-xl shadow mb-6"; det.style.cssText="padding:6px 18px";
      det.innerHTML='<summary style="cursor:pointer;font-size:13px;font-weight:600;color:#6b7280;padding:12px 0">Alle Detail-Auswertungen anzeigen (Event-Study, Maßnahmen-Wirkung/DiD, SoV-Verlauf, Mentions, Event-Stream)</summary>';
      toCollapse[0].parentNode.insertBefore(det, toCollapse[0]);
      toCollapse.forEach(function(b){ b.style.display=""; det.appendChild(b); });
    }
  }

  function build(){
    var host=document.querySelector('section[data-content="korrelation"]');
    if(!host) return false;
    var C=window.CORRELATION_IMPACT;
    if(!C || !C.level_model) return false;
    renderPanel(host,C);
    [0,400,1000,2000,3500].forEach(function(d){ setTimeout(function(){ tidy(host); }, d); });
    return true;
  }
  ready(function(){
    var tries=0;
    (function wait(){ tries++; if(build()) return; if(tries<40) setTimeout(wait,300); })();
    var tb=document.querySelector('[data-tab="korrelation"]'); if(tb) tb.addEventListener("click",function(){ [150,600,1400].forEach(function(d){ setTimeout(build,d); }); });
  });
})();
