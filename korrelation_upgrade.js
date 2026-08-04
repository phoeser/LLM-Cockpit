/* ============================================================
   ERGO LLM-Cockpit — Reiter "Wirkt unsere Arbeit auf die LLM-Sichtbarkeit?"
   Zusatzmodul v6 (04.08.2026) — Umbau auf EIN Ergebnis-Panel.
   -----------------------------------------------------------------
   Das Ergebnis-Panel selbst wird in dashboard_v3.html gebaut
   (window.__korrRender, Container #korrErgebnis). Dieses Modul liefert
   nur noch die beiden interaktiven Bausteine, die externe Daten
   brauchen und deshalb nicht im Panel-Renderer stehen:

     1. Ueber-/Unterperformer-Scatter (Chart.js + data/peec_footprint.json)
        -> Mount-Punkt  #korrMountScatter
     2. Quellen-Vergleich Peec vs. eigener Crawl (data/peec_cells.csv +
        GEO_SNAPSHOT)                -> Mount-Punkt  #korrMountSourceCompare

   Regeln (Projektstandard):
   - Jede Zahl kommt zur Laufzeit aus einer JSON/CSV. Keine eingefrorenen
     Werte, keine statischen Fallbacks. Fehlt ein Feld -> "keine Angabe"
     plus Grund, nie eine Zahl aus dem Code.
   - "Keine Daten" erscheint nie als 0.
   - Markenzahlen werden gezaehlt, nicht behauptet.
   ============================================================ */
(function () {
  "use strict";
  function ready(fn){ if(document.readyState!=="loading") fn(); else document.addEventListener("DOMContentLoaded",fn); }
  function num(v,d){ if(v==null||isNaN(v)) return "—"; d=(d==null?1:d); return (Math.round(v*Math.pow(10,d))/Math.pow(10,d)).toFixed(d).replace(".",","); }
  function signed(v,d){ return (v==null||isNaN(v))?"—":((v>0?"+":"")+num(v,d)); }

  var FOOTDEF="Zitations-Footprint = Anteil der markeneigenen Domain an allen zitierten URLs je Thema. Peec misst ihn als footprint_pct, der eigene Crawl als cite_share.";

  /* ---------- Peec-Markenmittel (Basis fuer Scatter und Bias-Hinweis) ---------- */
  function meansOf(tbl){
    if(!tbl) return null;
    var out={};
    Object.keys(tbl).forEach(function(b){
      var t=tbl[b]||{}, vs=[];
      Object.keys(t).forEach(function(k){ if(k==="Corporate") return; if(typeof t[k]==="number") vs.push(t[k]); });
      if(vs.length) out[b]=vs.reduce(function(a,x){return a+x;},0)/vs.length;
    });
    return Object.keys(out).length?out:null;
  }
  function rankOf(m,b){ return Object.keys(m).sort(function(x,y){return m[y]-m[x];}).indexOf(b)+1; }
  function topOf(m,n){ return Object.keys(m).sort(function(x,y){return m[y]-m[x];}).slice(0,Math.max(n,0)); }

  /* ---------- Warnhinweis: Peec-Prompt-Satz ist ERGO-zentriert ----------
     Alle Zahlen live aus data/peec_footprint.json (neutral_meta + die beiden
     SoV-Tabellen). Fehlt neutral_meta, bleibt der Hinweis qualitativ. */
  function peecBiasWarn(){
    var P=window.PEEC_DATA;
    var nm=(P&&P.neutral_meta)||null;
    var mb=meansOf(P&&P.peec_sov_pct), mn=meansOf(P&&P.peec_sov_pct_neutral);
    var s='<div style="background:#fff4f4;border:1px solid #f3c6c6;border-left:4px solid #dc0028;border-radius:8px;padding:10px 12px;margin-bottom:10px;font-size:11.5px;color:#7a1420;line-height:1.5">'+
      '<b>⚠ Der Peec-SoV mit Branding-Prompts ist kein neutrales Marktranking.</b> Das Peec-Projekt „ERGO Germany“ ist ERGOs eigenes Monitoring: ein Teil der Prompts nennt ERGO ausdrücklich, kein einziger einen Wettbewerber. ';
    if(nm && nm.n_prompts_branded!=null && nm.n_prompts_neutral!=null){
      var tot=nm.n_prompts_branded+nm.n_prompts_neutral;
      s+='<b>'+nm.n_prompts_branded+' von '+tot+' Prompts ('+num(100*nm.n_prompts_branded/tot,0)+' %)</b> nennen ERGO im Prompt. ';
    } else {
      s+='<span style="color:#9ca3af">Zahl der Branding-Prompts: keine Angabe — Feld <code>neutral_meta</code> fehlt im Peec-Export.</span> ';
    }
    if(mb && mn && mb.ERGO!=null && mn.ERGO!=null){
      var rb=rankOf(mb,"ERGO"), rn=rankOf(mn,"ERGO");
      var vor=topOf(mn,rn-1).filter(function(b){ return b!=="ERGO"; });
      s+='Dadurch liegt ERGOs Peec-SoV mit Branding-Prompts bei <b>'+num(mb.ERGO,1)+' %</b> (Platz '+rb+'); <b>neutral</b> (nur markenfreie Prompts) bei <b>'+num(mn.ERGO,1)+' %</b> — Platz '+rn+
        (vor.length?(' hinter '+vor.map(function(b){ return b+' ('+num(mn[b],1)+' %)'; }).join(' und ')):'')+
        ', Faktor <b>'+num(mb.ERGO/Math.max(mn.ERGO,1e-9),1)+'×</b>. ';
    } else {
      s+='<span style="color:#9ca3af">Branded gegen neutral: keine Angabe — die neutrale SoV-Tabelle fehlt im Peec-Export.</span> ';
    }
    s+='Als Marktranking gilt die neutrale Ansicht bzw. der eigene Crawl. Peec-branded heißt hier „Sichtbarkeit, wenn gezielt über ERGO gefragt wird“.</div>';
    return s;
  }

  /* ---------- Ueber-/Unterperformer-Scatter ---------- */
  var scatterChart=null;
  var scatterNeutral=true;   // Default: branding-neutrale Ansicht
  function peecNeutralAvail(){ var P=window.PEEC_DATA; return !!(P && P.footprint_pct_neutral && P.peec_sov_pct_neutral); }
  window.__scatterToggle=function(n){
    scatterNeutral=!!n;
    var el=document.getElementById("korrScatterBlock");
    if(el){ el.outerHTML=scatterBlock(); renderScatter(); }
  };
  function peecBrandMeans(){
    var P=window.PEEC_DATA; if(!P) return null;
    var useNeu=scatterNeutral && peecNeutralAvail();
    var fp=meansOf(useNeu?P.footprint_pct_neutral:P.footprint_pct);
    var sv=meansOf(useNeu?P.peec_sov_pct_neutral:P.peec_sov_pct);
    if(!fp||!sv) return null;
    var out=[];
    Object.keys(fp).forEach(function(b){ if(sv[b]==null) return; out.push({brand:b, foot:fp[b], sov:sv[b]}); });
    return out.length>=3?out:null;
  }
  function scatterBlock(){
    var avail=peecNeutralAvail(), neu=scatterNeutral&&avail;
    var pts=peecBrandMeans();
    var nBr=pts?pts.length:null;
    function tb(n,label){ var on=(scatterNeutral===!!n); return '<button onclick="window.__scatterToggle('+n+')" style="font-size:10.5px;padding:2px 9px;border-radius:7px;border:1px solid '+(on?"#067d3a":"#ccc")+';background:'+(on?"#067d3a":"#fff")+';color:'+(on?"#fff":"#282d37")+';cursor:pointer">'+label+'</button>'; }
    var toggle='<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:8px">'+
      '<span style="font-size:10.5px;color:#9ca3af">Prompts:</span>'+tb(1,"Neutral (ohne Branding)")+tb(0,"inkl. Branding (ERGO-fokussiert)")+
      (avail?'':'<span style="font-size:10px;color:#b45309">— neutrale Ansicht erst mit dem naechsten Peec-Export</span>')+'</div>';
    var note=neu
      ? '<div style="background:#e6f5ec;border:1px solid #bfe3cd;border-left:4px solid #067d3a;border-radius:8px;padding:9px 12px;margin-bottom:10px;font-size:11.5px;color:#14532d;line-height:1.5"><b>Branding-neutrale Ansicht.</b> Nur Prompts <b>ohne</b> Markennamen (Peec-System-Tag <code>non-branded</code>) — das faire Marktbild.</div>'
      : peecBiasWarn();
    return '<div id="korrScatterBlock" style="border:1px solid #eee;border-radius:11px;padding:14px 16px;margin-bottom:14px">'+
      '<div style="font-size:13px;font-weight:700;margin-bottom:2px">Über-/Unterperformer — Quellpräsenz gegen Sichtbarkeit (Peec)</div>'+
      '<div style="font-size:11px;color:#9ca3af;margin-bottom:8px">Jeder Punkt = eine Peec-Marke'+(nBr?(" ("+nBr+" Marken im aktuellen Export)"):"")+', Markenmittel über die Themen. Linie = erwartete Sichtbarkeit bei gegebenem Footprint (deskriptive OLS). Über der Linie = macht aus dem Footprint überdurchschnittlich viel Sichtbarkeit.</div>'+
      toggle + note +
      '<div style="position:relative;height:270px"><canvas id="korrScatterCv"></canvas></div>'+
      '<div style="font-size:11px;color:#6b7280;margin-top:6px" id="korrScatterNote"></div>'+
      '<div style="font-size:10.5px;color:#9ca3af;margin-top:4px">'+FOOTDEF+' Deskriptiver Zusammenhang, kein Kausalnachweis.</div>'+
    '</div>';
  }
  function renderScatter(){
    var cv=document.getElementById("korrScatterCv"), noteEl=document.getElementById("korrScatterNote");
    if(!cv) return;
    var pts=peecBrandMeans();
    if(!pts){ if(noteEl) noteEl.textContent="Peec-Markenmittel (data/peec_footprint.json) noch nicht geladen — der Scatter erscheint nach dem nächsten Peec-Export bzw. Reload. Keine Ersatz-Nullen."; return; }
    if(!window.Chart){ if(noteEl) noteEl.textContent="Diagrammbibliothek nicht geladen — die Zahlen stehen unverändert in den Karten oben."; return; }
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
        noteEl.innerHTML="<b>ERGO:</b> "+(res>=0?("+"+num(res,1)+" pp über"):(num(res,1)+" pp unter"))+" der erwarteten Sichtbarkeit. "+
          "<span style='color:#9ca3af'>Steigung "+signed(b,2)+" pp SoV je pp Footprint (deskriptive OLS über "+n+" Peec-Marken). ERGO rot, Allianz blau.</span>";
      } else noteEl.textContent="ERGO ist im aktuellen Peec-Export nicht enthalten.";
    }
  }

  /* ============================================================
     Quellen-Vergleich: Peec vs. eigener Crawl (Differenz)
     ============================================================ */
  var TMAP={ "Zahnzusatz":"zahnzusatz","Sterbegeld":"sterbegeld","Risikoleben":"risikoleben",
    "Berufsunfähigkeit":"berufsunfaehigkeit","Rechtsschutz":"rechtsschutz","Haftpflicht":"haftpflicht",
    "Hausrat":"hausrat","Kfz":"kfz","Unfall":"unfall","Krankenhauszusatz":"krankenhauszusatz","Reise":"reise" };
  var GROUNDED_ENGINES={ "Gemini":1,"Perplexity":1,"AI Overview":1,"AI Mode":1 };
  var BMAP={ "HUK24":"HUK-Coburg" };
  var b3Mode="g"; // "g" grounded | "u" ChatGPT/UI | "all"
  function pearson(x,y){ var n=x.length; if(n<3) return null; var mx=0,my=0; x.forEach(function(v){mx+=v;}); y.forEach(function(v){my+=v;}); mx/=n; my/=n; var c=0,vx=0,vy=0; for(var i=0;i<n;i++){ c+=(x[i]-mx)*(y[i]-my); vx+=(x[i]-mx)*(x[i]-mx); vy+=(y[i]-my)*(y[i]-my); } return (vx>0&&vy>0)?c/Math.sqrt(vx*vy):null; }
  function ranks(v){ var s=v.map(function(x,i){return [x,i];}).sort(function(a,b){return a[0]-b[0];}); var r=new Array(v.length); s.forEach(function(p,i){ r[p[1]]=i; }); return r; }
  function snapData(){ try{ if(typeof GEO_SNAPSHOT!=="undefined" && GEO_SNAPSHOT) return GEO_SNAPSHOT; }catch(e){} return window.GEO_SNAPSHOT||null; }
  function ownSov(mode){
    var g=snapData(); if(!g||!g.products) return null; var out={};
    var engs= mode==="u"?["chatgpt"]:(mode==="all"?["gemini","chatgpt"]:["gemini"]);
    Object.keys(g.products).forEach(function(pid){
      var sbl=g.products[pid].summary_by_llm||{}; var acc={}, cnt={}, sum=0;
      engs.forEach(function(e){ ((sbl[e]||{}).brands||[]).forEach(function(b){
        var v=100*(b.share_of_voice||0); acc[b.name]=(acc[b.name]||0)+v; cnt[b.name]=(cnt[b.name]||0)+1; sum+=v; }); });
      if(sum<=0) return; // Kanal in diesem Produkt ausgefallen -> keine Zeile statt Nullen
      var row={_name:g.products[pid].name||pid};
      Object.keys(acc).forEach(function(bn){ row[bn]=acc[bn]/cnt[bn]; });
      out[pid]=row;
    });
    return Object.keys(out).length?out:null;
  }
  function ownBrandCount(){
    var g=snapData(); if(!g||!g.products) return null; var set={};
    Object.keys(g.products).forEach(function(pid){
      var sbl=g.products[pid].summary_by_llm||{};
      Object.keys(sbl).forEach(function(e){ ((sbl[e]||{}).brands||[]).forEach(function(b){ if(b&&b.name) set[b.name]=1; }); });
    });
    var n=Object.keys(set).length; return n||null;
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
      if(!Object.keys(out.all).length) return null;
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
    var P=window.PEEC_DATA;
    var nPeec=(P&&P.brands&&P.brands.length)||null, nOwn=ownBrandCount();
    var mk=(nPeec&&nOwn)?("Markenzahl "+nPeec+" bei Peec gegen "+nOwn+" im eigenen Crawl")
                        :"Markenzahl je Quelle: keine Angabe, solange eine der beiden Quellen nicht geladen ist";
    return '<div style="font-size:13px;font-weight:700;color:#1a1a2e">Gegenprobe: Peec gegen den eigenen Crawl</div>'+
      '<div style="font-size:11.5px;color:#9ca3af;margin:1px 0 10px">Zwei unabhängige Messungen derselben Sache. Niveau-Unterschiede kommen von unterschiedlichen Engines und Methoden, nicht aus der Markenzahl ('+mk+') — entscheidend ist die <b>Rang-Konvergenz</b> je Thema.</div>'+
      '<div id="korrDiffBox" style="border:1px solid #eee;border-radius:11px;padding:14px 16px"><div style="font-size:12px;color:#9ca3af">Quellen-Vergleich wird geladen (data/peec_cells.csv) …</div></div>';
  }
  var fb3Wait=0;
  function fillBlock3(){
    var box=document.getElementById("korrDiffBox"); if(!box) return;
    var own=ownSov(b3Mode);
    if(!own){
      if(fb3Wait++<40){ setTimeout(fillBlock3,500); return; }
      box.innerHTML=b3Btns()+'<div style="font-size:12px;color:#9ca3af">Eigener Crawl (data/geo_snapshot.json): für den Kanal <b>'+b3ModeLbl()+'</b> keine Daten ladbar — der Vergleich erscheint nach Reload oder in einem anderen Kanal. <b>Keine Ersatz-Nullen.</b></div>'; b3Wire(box); return;
    }
    loadPeecCells().then(function(cells){
      box=document.getElementById("korrDiffBox"); if(!box) return;
      if(!cells){ box.innerHTML='<div style="font-size:12px;color:#9ca3af">Peec-Zellen (data/peec_cells.csv) nicht erreichbar — der Quellen-Vergleich wird beim nächsten Reload gezeigt. <b>Keine Ersatz-Nullen.</b></div>'; return; }
      var peec=cells[b3Mode]||{};
      if(!Object.keys(peec).length){ box.innerHTML=b3Btns()+'<div style="font-size:12px;color:#9ca3af">Peec: für den Kanal <b>'+b3ModeLbl()+'</b> keine Zellen im aktuellen Export. <b>Keine Ersatz-Nullen.</b></div>'; b3Wire(box); return; }
      var B3FOCUS=["ERGO","Allianz","HUK-Coburg","AXA"];
      var rowsHtml="", allOwn=[], allPeec=[], nRows=0;
      var pids=Object.keys(own).filter(function(p){ return peec[p]; });
      pids.forEach(function(pid){
        var o=own[pid], p=peec[pid];
        var avail=B3FOCUS.filter(function(b){ return o[b]!=null && p[b]!=null; });
        if(avail.length<3) return;
        nRows++;
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
      if(!nRows){ box.innerHTML=b3Btns()+'<div style="font-size:12px;color:#9ca3af">Kein Thema hat in beiden Quellen genug Kernmarken — <b>keine Ersatz-Nullen</b>.</div>'; b3Wire(box); return; }
      var rAll=pearson(allOwn,allPeec);
      var srcTxt = b3Mode==="g" ? "<b>Peec</b> (grounded: Gemini, Perplexity, AI Overview, AI Mode) gegen <b>eigenen Crawl</b> (Gemini-API, grounded)"
                 : (b3Mode==="u" ? "<b>Peec</b> (ChatGPT-UI) gegen <b>eigenen Crawl</b> (ChatGPT-API, ungrounded)"
                                 : "<b>Peec</b> (alle Engines) gegen <b>eigenen Crawl</b> (Mittel aus Gemini und ChatGPT)");
      box.innerHTML=b3Btns()+'<div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;align-items:flex-start;margin-bottom:8px">'+
        '<div style="font-size:12px;color:#4b5563;max-width:640px">SoV je Thema für die vier Kernmarken, Zellenformat <b>Peec / eigener Crawl</b> (jeweils %): '+srcTxt+'. Rechte Spalte: Rang-Konvergenz über genau diese vier Marken (Spearman-ρ).</div>'+
        '<span style="font-size:11px;font-weight:700;color:#067d3a;background:#e6f5ec;border-radius:6px;padding:4px 10px;white-space:nowrap">Gesamt-Korrelation r = '+(rAll==null?"—":num(rAll,2))+'</span></div>'+
        '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12.5px">'+
        '<thead><tr style="text-align:left;color:#64748b;border-bottom:1px solid #e2e8f0">'+
        '<th style="padding:5px 8px">Thema</th><th style="padding:5px 8px;text-align:right;color:#dc0028">ERGO</th>'+
        '<th style="padding:5px 8px;text-align:right">Allianz</th><th style="padding:5px 8px;text-align:right">HUK-Coburg</th>'+
        '<th style="padding:5px 8px;text-align:right">AXA</th>'+
        '<th style="padding:5px 8px;text-align:right" title="Spearman-Rangkorrelation der Reihenfolge von ERGO, Allianz, HUK-Coburg, AXA (1,0 = identisch)">Rang-ρ</th></tr></thead>'+
        '<tbody>'+rowsHtml+'</tbody></table></div>'+
        '<div style="font-size:11px;color:#9ca3af;margin-top:8px">Beschränkt auf die vier Kernmarken ERGO, Allianz, HUK-Coburg, AXA (Entscheidung Paul, 31.07.2026). Zellenformat: Peec / eigener Crawl in %. Rang-ρ ≥ 0,8 (grün) = beide Quellen sehen dieselbe Reihenfolge — bei vier Marken grob, aber direkt lesbar. Kanal: '+b3ModeLbl()+' · Peec-Export siehe data/peec_cells.csv.</div>';
      b3Wire(box);
    });
  }
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
     Mount in das eine Ergebnis-Panel (#korrErgebnis, gebaut in
     dashboard_v3.html). __korrRender ruft window.__korrKuMount()
     direkt auf; zusaetzlich Retry und Tab-Klick als Netz.
     ============================================================ */
  function mount(){
    var sc=document.getElementById("korrMountScatter");
    var cmp=document.getElementById("korrMountSourceCompare");
    if(!sc && !cmp) return false;
    if(sc && !sc.querySelector("#korrScatterBlock")) sc.innerHTML=scatterBlock();
    if(cmp && !cmp.querySelector("#korrDiffBox")) cmp.innerHTML=block3Skeleton();
    renderScatter();
    fb3Wait=0; fillBlock3();
    return true;
  }
  window.__korrKuMount=mount;

  ready(function(){
    var tries=0;
    (function wait(){ tries++; if(mount()) return; if(tries<40) setTimeout(wait,300); })();
    var tb=document.querySelector('[data-tab="korrelation"]');
    if(tb) tb.addEventListener("click",function(){ [150,600,1400].forEach(function(d){ setTimeout(mount,d); }); });
  });

  // Test-Hook (headless): erlaubt gezieltes Ansteuern ohne Chart.js
  if(typeof module!=="undefined" && module.exports){
    module.exports={ peecBiasWarn:peecBiasWarn, scatterBlock:scatterBlock, block3Skeleton:block3Skeleton, meansOf:meansOf, mount:mount };
  }
})();
