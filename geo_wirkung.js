/* ============================================================
   ERGO LLM-Cockpit — Reiter "LLM-Sichtbarkeit" — Block "Wirkung & Hebel"
   (18.07.2026, Pauls Arbeitsauftrag 2b + Punkt 4 — GEO-Metrik-Logik)
   -----------------------------------------------------------------
   Haengt sich ADDITIV OBEN in section[data-content="geo"] (erstes Kind),
   koexistiert mit dem peecMerged-/peecCmp-Block von nav_redesign.js.
   Struktur:
     1 · Wirkung: Kommt ERGO in der Antwort vor?  (KPI-Karten, WIRKUNGSMETRIK)
     2 · Themen im Detail: Peec -> eigener Crawl -> Differenz  (Tabelle)
     3 · Kreuz-Matrix: erwaehnt x zitiert  (2x2-Quadranten je Thema)
     4 · Hebel: Zitations-Footprint (Fruehindikator, nachgelagert)
   FUEHREND = Peec (Antworttext-Sichtbarkeit). Eigener Crawl SEPARAT.
   Kanal-Umschalter (Grounded / UI-ChatGPT / Alle) wirkt auf 1-3.
   Roter Faden des Projekts: FEHLENDE DATEN SIND NIE NULL. Ueberall dort,
   wo ein Kanal/eine Quelle ausfaellt, steht ein Hinweistext — nie "0,0 %".
   Quellen: GEO_SNAPSHOT (top-level let, nicht auf window) + data/peec_cells.csv.
   Idempotent: id="geoWirkung", bei Rebuild ersetzt.
   ============================================================ */
(function () {
  "use strict";
  function ready(fn){ if(document.readyState!=="loading") fn(); else document.addEventListener("DOMContentLoaded",fn); }
  function num(v,d){ if(v==null||isNaN(v)) return "—"; d=(d==null?1:d); return (Math.round(v*Math.pow(10,d))/Math.pow(10,d)).toFixed(d).replace(".",","); }
  function pctS(v,d){ return (v==null||isNaN(v))?"—":(num(v,d==null?1:d)+" %"); }
  function signed(v,d){ return (v==null||isNaN(v))?"—":((v>0?"+":"")+num(v,d)); }

  /* ---------- Konstanten / Mappings (identisch zu peec_compare.js) ---------- */
  var TMAP={ "Zahnzusatz":"zahnzusatz","Sterbegeld":"sterbegeld","Risikoleben":"risikoleben",
    "Berufsunfähigkeit":"berufsunfaehigkeit","Rechtsschutz":"rechtsschutz","Haftpflicht":"haftpflicht",
    "Hausrat":"hausrat","Kfz":"kfz","Unfall":"unfall","Krankenhauszusatz":"krankenhauszusatz","Reise":"reise" };
  var BMAP={ "HUK24":"HUK-Coburg" };
  // Fallback-Klassifizierung, falls engine_typ-Spalte fehlt (engine_typ ist fuehrend).
  var GROUNDED_ENGINES={ "Gemini":1,"Perplexity":1,"AI Overview":1,"AI Mode":1 };
  // Domains, die als ERGO-Zitat zaehlen (Konzern-Marken, die der Matcher mitzaehlt).
  var ERGO_DOMAINS=["ergo.de","ergo-reiseversicherung.de","dkv.com"];

  // Schwellen (transparent ausgewiesen)
  var TH_MENTION=10; // appearance_rate >= 10 % = "erwaehnt"
  var TH_CITE=5;     // ERGO-Zitatanteil >= 5 %   = "zitiert"

  var ERGO_RED="#dc0028", INK="#1a1a2e", GREY="#6b7280", MUTE="#9ca3af", LINE="#ececf0";

  var gwMode="g"; // "g" grounded | "u" UI/ChatGPT | "all" alle

  /* ---------- GEO_SNAPSHOT-Zugriff (Muster aus korrelation_upgrade.js) ---------- */
  function snapData(){ try{ if(typeof GEO_SNAPSHOT!=="undefined" && GEO_SNAPSHOT) return GEO_SNAPSHOT; }catch(e){} return window.GEO_SNAPSHOT||null; }

  /* ---------- Statistik-Helfer (identisch zu peec_compare.js) ---------- */
  function pearson(x,y){ var n=x.length; if(n<3) return null; var mx=0,my=0; x.forEach(function(v){mx+=v;}); y.forEach(function(v){my+=v;}); mx/=n; my/=n; var c=0,vx=0,vy=0; for(var i=0;i<n;i++){ c+=(x[i]-mx)*(y[i]-my); vx+=(x[i]-mx)*(x[i]-mx); vy+=(y[i]-my)*(y[i]-my); } return (vx>0&&vy>0)?c/Math.sqrt(vx*vy):null; }
  function ranks(v){ var s=v.map(function(x,i){return [x,i];}).sort(function(a,b){return a[0]-b[0];}); var r=new Array(v.length); s.forEach(function(p,i){ r[p[1]]=i; }); return r; }
  function mean(a){ if(!a||!a.length) return null; var s=0; for(var i=0;i<a.length;i++) s+=a[i]; return s/a.length; }

  /* ============================================================
     Peec-Zellen: reiches Parsing (visibility/sov/sentiment/position je Marke)
     Struktur: { g:{pid:{marke:{vis,sov,sent,pos,n}}}, u:{...}, all:{...} }
     Werte pro Zelle = Mittel ueber die Engines des Kanals.
     visibility/sov: 0..1 -> in % umgerechnet (x100). sentiment: 0..100.
     ============================================================ */
  function parsePeec(text){
    if(!text) return null;
    var lines=text.replace(/^﻿/,"").split("\n");
    var head=lines[0].split(";"); var idx={}; head.forEach(function(h,i){ idx[h.trim().replace(/^﻿/,"")]=i; });
    if(idx.marke==null||idx.thema==null||idx.visibility==null) return null;
    var acc={g:{},u:{},all:{}};
    function bump(cls,pid,b,r){
      var C=acc[cls]; C[pid]=C[pid]||{};
      var o=C[pid][b]||(C[pid][b]={vis:0,sov:0,sent:0,pos:0,n:0,ns:0,np:0});
      var vis=parseFloat(r[idx.visibility]); var sov=parseFloat(r[idx.share_of_voice]);
      var sent=parseFloat(r[idx.sentiment]); var pos=parseFloat(r[idx.position]);
      if(!isNaN(vis)) o.vis+=vis; if(!isNaN(sov)) o.sov+=sov;
      o.n+=1;
      if(!isNaN(sent)){ o.sent+=sent; o.ns+=1; }
      if(!isNaN(pos)){ o.pos+=pos; o.np+=1; }
    }
    for(var i=1;i<lines.length;i++){
      var r=lines[i].split(";"); if(r.length<5) continue;
      var pid=TMAP[(r[idx.thema]||"").trim()]; if(!pid) continue;
      var b=BMAP[r[idx.marke]]||r[idx.marke];
      var et=(idx.engine_typ!=null?(r[idx.engine_typ]||"").trim():"");
      var cls=et? (et==="grounded"?"g":"u") : (GROUNDED_ENGINES[r[idx.engine]]?"g":"u");
      bump(cls,pid,b,r); bump("all",pid,b,r);
    }
    // Mittelwerte bilden
    var out={g:{},u:{},all:{}};
    ["g","u","all"].forEach(function(k){
      Object.keys(acc[k]).forEach(function(pid){
        out[k][pid]={};
        Object.keys(acc[k][pid]).forEach(function(b){
          var o=acc[k][pid][b];
          out[k][pid][b]={ vis: o.n?100*o.vis/o.n:null, sov: o.n?100*o.sov/o.n:null,
            sent: o.ns?o.sent/o.ns:null, pos: o.np?o.pos/o.np:null };
        });
      });
    });
    return (Object.keys(out.all).length)?out:null;
  }
  function loadCells(){
    if(window.__GW_CELLS) return Promise.resolve(window.__GW_CELLS);
    return fetch("data/peec_cells.csv?t="+Date.now(),{cache:"no-store"})
      .then(function(r){ return r.ok?r.text():null; })
      .then(function(t){ var p=parsePeec(t); if(p) window.__GW_CELLS=p; return p; })
      .catch(function(){ return null; });
  }

  /* ============================================================
     Eigener Crawl je Kanal. Ausfall-Guard: Produkt mit Kanal-SoV-Summe 0
     wird uebersprungen (keine Ersatz-Nullen).
     Rueckgabe: { pid:{ _name, app, rank, sov, brands:{marke:sov%} } }
     Kanal: g->gemini, u->chatgpt, all->Mittel der Engines.
     ============================================================ */
  function ownData(mode){
    var g=snapData(); if(!g||!g.products) return null;
    var engs= mode==="u"?["chatgpt"]:(mode==="all"?["gemini","chatgpt"]:["gemini"]);
    var out={};
    Object.keys(g.products).forEach(function(pid){
      var P=g.products[pid], sbl=P.summary_by_llm||{};
      var appA=[], rankA=[], sovErgo=[], brandSov={}, brandCnt={}, chSum=0;
      engs.forEach(function(e){
        var brs=(sbl[e]||{}).brands||[];
        var s=0; brs.forEach(function(b){ s+=(b.share_of_voice||0); });
        if(s<=0) return; // Kanal in diesem Produkt ausgefallen -> nicht mitzaehlen
        chSum+=s;
        brs.forEach(function(b){
          brandSov[b.name]=(brandSov[b.name]||0)+100*(b.share_of_voice||0);
          brandCnt[b.name]=(brandCnt[b.name]||0)+1;
          if(b.name==="ERGO"){
            if(b.appearance_rate!=null) appA.push(100*b.appearance_rate);
            if(b.avg_rank!=null) rankA.push(b.avg_rank);
            sovErgo.push(100*(b.share_of_voice||0));
          }
        });
      });
      if(chSum<=0) return; // gesamter Kanal fuer dieses Produkt leer -> keine Zeile
      var brands={}; Object.keys(brandSov).forEach(function(bn){ brands[bn]=brandSov[bn]/brandCnt[bn]; });
      out[pid]={ _name:P.name||pid, app: appA.length?mean(appA):null,
        rank: rankA.length?mean(rankA):null, sov: sovErgo.length?mean(sovErgo):null, brands:brands };
    });
    return Object.keys(out).length?out:null;
  }

  /* ---------- ERGO-Zitatanteil je Thema (engine-uebergreifend aggregiert) ---------- */
  function ergoCiteShare(pid){
    var g=snapData(); if(!g||!g.products||!g.products[pid]) return null;
    var ov=((g.products[pid].cited_sources||{}).overall)||[];
    if(!ov.length) return null;
    var tot=0, ergo=0;
    ov.forEach(function(s){
      var c=s.count||0; tot+=c;
      var dom=(s.domain||"").toLowerCase();
      for(var i=0;i<ERGO_DOMAINS.length;i++){ if(dom.indexOf(ERGO_DOMAINS[i])>=0){ ergo+=c; break; } }
    });
    return tot>0 ? 100*ergo/tot : null;
  }

  /* ---------- Peec-ERGO-Aggregat je Kanal (Mittel ueber Themen) ---------- */
  function peecErgoAgg(cells,mode){
    var C=cells&&cells[mode]; if(!C) return null;
    var vis=[],sov=[],sent=[],pos=[],nT=0;
    Object.keys(C).forEach(function(pid){
      var e=C[pid]["ERGO"]; if(!e) return; nT++;
      if(e.vis!=null) vis.push(e.vis); if(e.sov!=null) sov.push(e.sov);
      if(e.sent!=null) sent.push(e.sent); if(e.pos!=null) pos.push(e.pos);
    });
    if(!nT) return null;
    return { vis:mean(vis), sov:mean(sov), sent:mean(sent), pos:mean(pos), nThemes:nT };
  }
  function ownErgoAgg(od){
    if(!od) return null;
    var app=[],rank=[];
    Object.keys(od).forEach(function(pid){ var o=od[pid]; if(o.app!=null) app.push(o.app); if(o.rank!=null) rank.push(o.rank); });
    if(!app.length && !rank.length) return null;
    return { app:mean(app), rank:mean(rank), nProd:Object.keys(od).length };
  }

  /* ============================================================
     UI-Bausteine (Stil aus korrelation_upgrade.js)
     ============================================================ */
  function badge(txt,kind){
    var c={ok:["#067d3a","#e6f5ec"],warn:["#8a6d00","#fdf3d7"],muted:[GREY,"#eef0f2"],
      info:["#1d4ed8","#e7eefe"],lead:["#b30021","#fde7ec"]}[kind]||[GREY,"#eef0f2"];
    return '<span style="font-size:10px;font-weight:700;color:'+c[0]+';background:'+c[1]+';border-radius:4px;padding:2px 7px;white-space:nowrap">'+txt+'</span>';
  }
  function kpiCard(o){
    return '<div id="'+(o.id||"")+'" style="border:1px solid '+LINE+';border-radius:11px;padding:13px 15px;background:#fff;display:flex;flex-direction:column;gap:5px">'+
      '<div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start">'+
        '<div style="font-size:12.5px;font-weight:700;color:'+INK+';line-height:1.25">'+o.title+'</div>'+(o.badge||'')+'</div>'+
      (o.value!=null?('<div style="font-size:21px;font-weight:800;color:'+(o.accent||INK)+';line-height:1.08"><span class="gwVal">'+o.value+'</span>'+
        (o.sub?(' <span style="font-size:11px;font-weight:500;color:'+MUTE+'">'+o.sub+'</span>'):'')+'</div>'):'')+
      (o.plain?('<div style="font-size:11.5px;color:#4b5563;line-height:1.45">'+o.plain+'</div>'):'')+
      (o.foot?('<div style="font-size:10px;color:#b3b8bf;margin-top:auto;padding-top:2px">'+o.foot+'</div>'):'')+
    '</div>';
  }
  function chanBtns(){
    function b(id,lbl){ var on=gwMode===id; return '<button data-gm="'+id+'" class="gwm" style="font-size:11px;padding:3px 11px;border-radius:8px;border:1px solid '+(on?ERGO_RED:"#ccc")+';background:'+(on?ERGO_RED:"#fff")+';color:'+(on?"#fff":"#282d37")+';cursor:pointer">'+lbl+'</button>'; }
    return '<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:0 0 12px"><span style="font-size:11px;font-weight:600;color:'+GREY+'">Kanal:</span>'+
      b("g","Grounded (Web-Suche)")+b("u","UI / ChatGPT")+b("all","Alle Engines")+
      '<span style="font-size:10.5px;color:'+MUTE+'">Peec: Gemini, Perplexity, AI&nbsp;Overview, AI&nbsp;Mode = grounded · ChatGPT = UI. Eigener Crawl: Gemini = grounded · ChatGPT = UI.</span></div>';
  }
  function chanLbl(){ return gwMode==="g"?"Grounded (Web-Suche)":(gwMode==="u"?"UI / ChatGPT":"Alle Engines"); }
  function h(n,txt){ return '<div style="font-size:14px;font-weight:700;color:'+INK+';margin:18px 0 2px">'+n+' · '+txt+'</div>'; }
  function sub(txt){ return '<div style="font-size:11.5px;color:'+MUTE+';margin:1px 0 10px">'+txt+'</div>'; }

  /* ============================================================
     BLOCK A — Wirkungsmetriken (KPI-Karten)
     ============================================================ */
  function blockA(cells,od){
    var P=peecErgoAgg(cells,gwMode), O=ownErgoAgg(od);
    var cards=[];
    // 1) Sichtbarkeit im Antworttext (Peec, fuehrend)
    cards.push(kpiCard({ id:"gwKpiVis",
      title:"Sichtbarkeit im Antworttext <span style=\"font-weight:600;color:#b30021\">(Peec, fuehrend)</span>",
      badge:badge("Wirkungsmetrik","lead"),
      value: P&&P.vis!=null? pctS(P.vis,1) : null,
      accent:"#067d3a", sub: P&&P.vis!=null?("ø ueber "+P.nThemes+" Themen"):"",
      plain: (P&&P.vis!=null)? "Anteil der Antworten, in denen ERGO im Text vorkommt (Peec-Visibility, Kanal "+chanLbl()+")."
             : "<b>Noch keine Peec-Zellen ladbar</b> (data/peec_cells.csv) — Wert erscheint nach Reload. Keine Ersatz-Null.",
      foot:"Quelle: Peec · visibility-Spalte je Thema, ueber Themen gemittelt" }));
    // 2) Sichtbarkeit eigener Crawl (separat)
    cards.push(kpiCard({ id:"gwKpiApp",
      title:"Sichtbarkeit eigener Crawl <span style=\"font-weight:600;color:"+GREY+"\">(separat)</span>",
      badge:badge("Konsistenzpruefung","info"),
      value: O&&O.app!=null? pctS(O.app,1) : null,
      accent:INK, sub: O&&O.app!=null?("ø ueber "+O.nProd+" Themen"):"",
      plain: (O&&O.app!=null)? "ERGO-Appearance-Rate im eigenen API-Crawl (Kanal "+chanLbl()+"), Themen mit leerem Kanal ausgelassen."
             : "<b>Eigener Crawl (geo_snapshot.json) fuer diesen Kanal nicht ladbar</b> — erscheint nach Reload. Keine Ersatz-Null.",
      foot:"Quelle: eigener Crawl · appearance_rate, Produkte mit Kanal-Summe 0 uebersprungen" }));
    // 3) Position in der Antwort
    var posTxt = (P&&P.pos!=null)? num(P.pos,1) : "—";
    var rankTxt= (O&&O.rank!=null)? num(O.rank,1) : "—";
    cards.push(kpiCard({ id:"gwKpiPos",
      title:"Position in der Antwort", badge:badge("niedriger = besser","muted"),
      value: (P&&P.pos!=null)? posTxt : null, accent:INK, sub:"Peec-Position",
      plain: "Peec-Position ERGO: <b>"+posTxt+"</b>"+((P&&P.pos==null)?" (keine Peec-Daten)":"")+
             " · eigener Ø-Rang: <b>"+rankTxt+"</b>"+((O&&O.rank==null)?" (kein Kanal-Wert)":"")+". Beide Kanal "+chanLbl()+".",
      foot:"Quelle: Peec position · eigener avg_rank" }));
    // 4) Sentiment (Peec-Antworttext)
    cards.push(kpiCard({ id:"gwKpiSent",
      title:"Sentiment (Peec-Antworttext)", badge:badge("0–100","muted"),
      value: (P&&P.sent!=null)? num(P.sent,0) : null, accent:INK, sub:"ERGO-Mittel",
      plain: (P&&P.sent!=null)? "Ton des Peec-Antworttextes zu ERGO (ø ueber Themen, Kanal "+chanLbl()+")."
             : "<b>Kein Peec-Sentiment ladbar</b> — erscheint nach Reload. Keine Ersatz-Null.",
      foot:"⚠ Peec-Antwort-Sentiment ≠ Kundenbewertungs-Sentiment (eigener Sentiment-Reiter) — nicht mischen." }));
    // 5) Nordstern — EHRLICH, keine Zahl
    cards.push(kpiCard({ id:"gwNordstern",
      title:"Nordstern: Empfehlungsrate (positiv genannt)", badge:badge("noch nicht messbar","warn"),
      value:"noch nicht messbar", accent:GREY,
      plain:"Braucht Sentiment auf Prompt-Ebene (positiv genannt je einzelner Antwort). Kommt gegebenenfalls aus der Peec-API-Exploration. Bis dahin bewusst <b>keine Ersatz-Zahl</b>.",
      foot:"Zielgroesse — noch keine belastbare Messung vorhanden" }));
    return '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:11px">'+cards.join("")+'</div>';
  }

  /* ============================================================
     BLOCK B — Themen-Tripel: Peec -> eigener Crawl -> Differenz
     ============================================================ */
  function blockBData(cells,od){
    // gemeinsame Themen (in beiden Quellen fuer den Kanal)
    var C=cells&&cells[gwMode]; if(!C||!od) return null;
    var pids=Object.keys(od).filter(function(p){ return C[p] && C[p]["ERGO"]; });
    return pids;
  }
  function blockB(cells,od){
    var C=cells&&cells[gwMode];
    if(!C){ return '<div id="gwBBox" style="border:1px solid '+LINE+';border-radius:11px;padding:14px 16px;font-size:12px;color:'+MUTE+'"><b>Peec-Zellen nicht ladbar</b> — Themen-Detail erscheint nach Reload. Keine Ersatz-Nullen.</div>'; }
    if(!od){ return '<div id="gwBBox" style="border:1px solid '+LINE+';border-radius:11px;padding:14px 16px;font-size:12px;color:'+MUTE+'"><b>Eigener Crawl nicht ladbar</b> — Themen-Detail erscheint nach Reload. Keine Ersatz-Nullen.</div>'; }
    var pids=blockBData(cells,od)||[];
    if(!pids.length){ return '<div id="gwBBox" style="border:1px solid '+LINE+';border-radius:11px;padding:14px 16px;font-size:12px;color:'+MUTE+'">Fuer den Kanal <b>'+chanLbl()+'</b> keine gemeinsamen Themen. Keine Ersatz-Nullen.</div>'; }
    var rows="";
    pids.forEach(function(pid){
      var pe=C[pid]["ERGO"], o=od[pid];
      // Rang-rho: gemeinsame Marken (SoV-basiert)
      var common=Object.keys(o.brands).filter(function(b){ return C[pid][b] && C[pid][b].sov!=null; });
      var xo=common.map(function(b){ return o.brands[b]; });
      var xp=common.map(function(b){ return C[pid][b].sov; });
      var rho=(common.length>=3)? pearson(ranks(xo),ranks(xp)) : null;
      var diff=(pe.vis!=null && o.app!=null)? (pe.vis-o.app) : null; // Peec-Vis − eigene Appearance (pp)
      var rc=(rho==null)?MUTE:(rho>=0.8?"#067d3a":(rho>=0.5?"#b45309":"#b91c1c"));
      rows+='<tr style="border-bottom:1px solid #f1f5f9">'+
        '<td style="padding:5px 8px;font-weight:600;color:#1e293b">'+(o._name||pid)+'</td>'+
        '<td style="padding:5px 8px;text-align:right">'+pctS(pe.vis,1)+'</td>'+
        '<td style="padding:5px 8px;text-align:right">'+pctS(pe.sov,1)+'</td>'+
        '<td style="padding:5px 8px;text-align:right">'+(pe.pos!=null?num(pe.pos,1):"—")+'</td>'+
        '<td style="padding:5px 8px;text-align:right">'+(pe.sent!=null?num(pe.sent,0):"—")+'</td>'+
        '<td style="padding:5px 8px;text-align:right;border-left:1px solid #eef2f7">'+pctS(o.app,1)+'</td>'+
        '<td style="padding:5px 8px;text-align:right">'+pctS(o.sov,1)+'</td>'+
        '<td style="padding:5px 8px;text-align:right">'+(o.rank!=null?num(o.rank,1):"—")+'</td>'+
        '<td style="padding:5px 8px;text-align:right;border-left:1px solid #eef2f7;color:'+(diff!=null&&Math.abs(diff)>10?"#b45309":"#64748b")+'">'+(diff==null?"—":signed(diff,1)+" pp")+'</td>'+
        '<td style="padding:5px 8px;text-align:right;font-weight:700;color:'+rc+'">'+(rho==null?"—":num(rho,2))+'</td></tr>';
    });
    return '<div id="gwBBox" style="border:1px solid '+LINE+';border-radius:11px;padding:8px 12px 12px">'+
      '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12px">'+
      '<thead>'+
      '<tr style="color:#64748b"><th></th>'+
        '<th colspan="4" style="padding:4px 8px;text-align:center;color:#b30021;font-size:11px;border-bottom:1px solid #e2e8f0">Peec (fuehrend)</th>'+
        '<th colspan="3" style="padding:4px 8px;text-align:center;color:'+GREY+';font-size:11px;border-bottom:1px solid #e2e8f0;border-left:1px solid #eef2f7">Eigener Crawl</th>'+
        '<th colspan="2" style="border-left:1px solid #eef2f7"></th></tr>'+
      '<tr style="text-align:right;color:#64748b;border-bottom:1px solid #e2e8f0">'+
        '<th style="padding:5px 8px;text-align:left">Thema</th>'+
        '<th style="padding:5px 8px">Visibility</th><th style="padding:5px 8px">SoV</th><th style="padding:5px 8px">Position</th><th style="padding:5px 8px">Sentiment</th>'+
        '<th style="padding:5px 8px;border-left:1px solid #eef2f7">Appearance</th><th style="padding:5px 8px">SoV</th><th style="padding:5px 8px">Ø-Rang</th>'+
        '<th style="padding:5px 8px;border-left:1px solid #eef2f7" title="Peec-Visibility − eigene Appearance">Differenz</th>'+
        '<th style="padding:5px 8px" title="Spearman-Rangkorrelation der Markenreihenfolge (SoV), 1,0 = identisch">Rang-ρ</th></tr></thead>'+
      '<tbody>'+rows+'</tbody></table></div>'+
      '<div style="font-size:11px;color:'+MUTE+';margin-top:8px">Alles ERGO-zentriert. <b>Differenz</b> = Peec-Visibility − eigene Appearance (Niveau-Unterschiede sind methodisch normal: Peec verteilt ueber 26 Marken, der eigene Crawl ueber 7). <b>Rang-ρ</b> ≥ 0,8 (gruen) = beide Quellen sehen dieselbe Markenreihenfolge. Kanal: '+chanLbl()+'.</div>'+
    '</div>';
  }

  /* ============================================================
     BLOCK C — Kreuz-Matrix: erwaehnt x zitiert (2x2)
     ============================================================ */
  function blockC(cells,od){
    var C=cells&&cells[gwMode];
    if(!C||!od){ return '<div id="gwCBox" style="border:1px solid '+LINE+';border-radius:11px;padding:14px 16px;font-size:12px;color:'+MUTE+'"><b>Kreuz-Matrix benoetigt eigenen Crawl und Peec-Themenliste</b> — erscheint nach Reload. Keine Ersatz-Nullen.</div>'; }
    // Universum = B-Datenbasis des Kanals (gemeinsame Themen)
    var pids=blockBData(cells,od)||[];
    var q={mc:[],mn:[],nc:[],nn:[]}, noData=[];
    pids.forEach(function(pid){
      var o=od[pid];
      var app=o.app;                     // Kanal-abhaengig
      var cite=ergoCiteShare(pid);       // engine-uebergreifend
      if(app==null){ noData.push(o._name||pid); return; }
      var men=app>=TH_MENTION;
      var cit=(cite!=null)&&(cite>=TH_CITE);
      var label=(o._name||pid);
      if(men&&cit) q.mc.push(label);
      else if(men&&!cit) q.mn.push(label);
      else if(!men&&cit) q.nc.push(label);
      else q.nn.push(label);
    });
    function quad(id,icon,title,desc,list,col,bg){
      return '<div id="'+id+'" style="border:1px solid '+LINE+';border-radius:11px;padding:12px 14px;background:'+bg+'">'+
        '<div style="font-size:12.5px;font-weight:700;color:'+col+';margin-bottom:2px">'+icon+' '+title+' <span style="font-weight:600;color:'+GREY+'">('+list.length+')</span></div>'+
        '<div style="font-size:11px;color:'+GREY+';margin-bottom:6px">'+desc+'</div>'+
        '<div style="font-size:12px;color:'+INK+';line-height:1.5">'+(list.length?list.join(", "):'<span style="color:'+MUTE+'">—</span>')+'</div></div>';
    }
    var grid='<div id="gwCGrid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:11px">'+
      quad("gwQmc","✅","Idealzustand — erwaehnt & zitiert","ERGO kommt vor und wird aus eigenen Quellen belegt.",q.mc,"#067d3a","#f2fbf5")+
      quad("gwQmn","🟡","Wirkung da, aber fragil","Erwaehnt, aber nicht zitiert — stuetzt sich auf Trainingswissen/Portal-Zitate.",q.mn,"#8a6d00","#fffdf4")+
      quad("gwQnc","🟠","Potenzial ungenutzt","Zitiert, aber nicht empfohlen — Quelle wird gelesen, ERGO aber nicht genannt.",q.nc,"#b45309","#fff8f1")+
      quad("gwQnn","🔴","Handlungsbedarf — weder noch","Weder erwaehnt noch zitiert.",q.nn,"#b91c1c","#fff5f5")+
    '</div>';
    var noRow='<div id="gwCNoData" style="font-size:11px;color:'+MUTE+';margin-top:8px">ohne Daten: '+(noData.length?noData.join(", "):"—")+'</div>';
    var foot='<div style="font-size:11px;color:'+MUTE+';margin-top:8px;line-height:1.55">'+
      'Datenbasis: eigener Crawl (Kanal '+chanLbl()+'). Schwellen: <b>erwaehnt</b> = Appearance-Rate ≥ '+TH_MENTION+' %, <b>zitiert</b> = ERGO-Zitatanteil ≥ '+TH_CITE+' % der zitierten URLs. '+
      '<b>Zitatanteil engine-uebergreifend</b> (cited_sources aggregiert ueber alle Engines — nicht kanalgetrennt). '+
      'Nuancen: Mention ohne eigenes Zitat ist moeglich (LLM nennt ERGO aus Trainingswissen oder ueber Portal-Zitate); Zitat ohne Mention ebenso (ergo.de wird als Quelle gelesen, empfohlen wird aber z.&nbsp;B. Allianz). Themen ohne Kanal-Daten sind separat als „ohne Daten" ausgewiesen, nicht als Null.</div>';
    return '<div id="gwCBox">'+grid+noRow+foot+'</div>';
  }

  /* ============================================================
     BLOCK D — Hebel: Zitations-Footprint (Fruehindikator)
     ============================================================ */
  function footprintMean(brand){
    var P=window.PEEC_DATA;
    if(!P||!P.footprint_pct||!P.footprint_pct[brand]) return null;
    var ft=P.footprint_pct[brand], vals=[];
    Object.keys(ft).forEach(function(t){ if(t==="Corporate") return; if(typeof ft[t]==="number") vals.push(ft[t]); });
    return vals.length?mean(vals):null;
  }
  function blockD(){
    var eF=footprintMean("ERGO"), aF=footprintMean("Allianz");
    var have=(eF!=null||aF!=null);
    var body;
    if(have){
      body='<div style="display:flex;gap:22px;flex-wrap:wrap;margin:6px 0 10px">'+
        '<div><div style="font-size:11px;color:'+GREY+'">ERGO-Footprint</div><div style="font-size:20px;font-weight:800;color:'+ERGO_RED+'">'+pctS(eF,1)+'</div></div>'+
        '<div><div style="font-size:11px;color:'+GREY+'">Allianz-Footprint</div><div style="font-size:20px;font-weight:800;color:#003781">'+pctS(aF,1)+'</div></div>'+
        ((eF!=null&&aF!=null)?('<div><div style="font-size:11px;color:'+GREY+'">Abstand</div><div style="font-size:20px;font-weight:800;color:'+INK+'">'+signed(eF-aF,1)+' pp</div></div>'):'')+
        '</div>';
    } else {
      body='<div style="font-size:12px;color:'+MUTE+';margin:6px 0 10px"><b>window.PEEC_DATA.footprint_pct nicht geladen</b> — ERGO-/Allianz-Footprint erscheinen nach dem naechsten Peec-Export bzw. Reload. Keine Ersatz-Nullen.</div>';
    }
    return '<div id="gwDBox" style="border:1px solid #dbe4fb;background:#f6f8fe;border-radius:11px;padding:14px 16px">'+
      '<div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start;flex-wrap:wrap">'+
        '<div style="font-size:13px;font-weight:700;color:#1d4ed8">Zitations-Footprint = Fruehindikator / Hebel (nachgelagert)</div>'+
        badge("FRÜHINDIKATOR — nicht die Wirkung selbst","warn")+'</div>'+
      body+
      '<div style="font-size:12px;color:#374151;line-height:1.55">Warum als Hebel und nicht als Wirkung:'+
        '<ol style="margin:6px 0 0;padding-left:18px">'+
        '<li><b>Kausalkette (grounded):</b> mehr zitierfaehige eigene Quellen → mehr Nennungen in web-gestuetzten Antworten.</li>'+
        '<li><b>Steuerbarkeit:</b> die Antwortformulierung der LLMs laesst sich nicht steuern — die Zitierfaehigkeit der eigenen Inhalte schon.</li>'+
        '<li><b>Klick-Traffic:</b> zitierte eigene URLs bringen zusaetzlich direkten Verweis-Traffic.</li></ol></div>'+
      '<div style="font-size:11px;color:'+MUTE+';margin-top:8px">Footprint = Mittel ueber Themen ohne „Corporate" (PEEC_DATA.footprint_pct). Details: Reiter <b>Korrelationsanalyse</b>.</div>'+
    '</div>';
  }

  /* ============================================================
     Datenstand
     ============================================================ */
  function standLine(cells){
    var g=snapData(); var parts=[];
    if(g&&g.finished_at){ var m=/^(\d{4})-(\d{2})-(\d{2})/.exec(g.finished_at); if(m) parts.push("eigener Crawl "+m[3]+"."+m[2]+"."+m[1]); }
    // Peec-Zeitraum aus dem ersten CSV-Feld (window-cache haelt kein Rohtext -> aus PEEC_DATA/Fallback)
    if(window.__GW_ZR) parts.push("Peec "+window.__GW_ZR);
    return parts.length? ('<div style="font-size:10.5px;color:#b3b8bf;margin-top:4px">Datenstand: '+parts.join(" · ")+'</div>') : '';
  }

  /* ============================================================
     Gesamt-Render (idempotent)
     ============================================================ */
  function render(host){
    var cells=window.__GW_CELLS||null;
    var od=ownData(gwMode);
    var box=document.getElementById("geoWirkung");
    if(!box){ box=document.createElement("div"); box.id="geoWirkung"; box.className="bg-white rounded-xl shadow p-6 mb-6"; host.insertBefore(box, host.firstChild); }
    // Falls die Section neu aufgebaut wurde und die Box detached ist -> wieder als erstes Kind
    if(box.parentNode!==host){ host.insertBefore(box, host.firstChild); }
    box.innerHTML=
      '<div style="margin-bottom:12px">'+
        '<h3 style="font-size:17px;font-weight:700;margin:0;color:'+INK+'">Wirkung &amp; Hebel — kommt ERGO in der Antwort vor? '+badge("Peec fuehrend","lead")+'</h3>'+
        '<p style="font-size:12px;color:'+GREY+';margin:3px 0 0">Die <b>Wirkungsmetrik</b> steht vorne: ob und wie ERGO im Antworttext vorkommt (Peec, fuehrend). Der eigene Crawl steht separat zur Konsistenzpruefung. Der Zitations-Footprint ist der <b>Fruehindikator/Hebel</b> — nachgelagert.</p>'+
        standLine(cells)+
      '</div>'+
      chanBtns()+
      h("1","Wirkung: Kommt ERGO in der Antwort vor?")+ sub("KPI-Karten. Peec-Sichtbarkeit im Antworttext ist die fuehrende Wirkungsmetrik; der eigene Crawl steht daneben.")+
      blockA(cells,od)+
      h("2","Themen im Detail: Peec → eigener Crawl → Differenz")+ sub("Je Thema das Tripel Peec (fuehrend) → eigener Crawl → Differenz, plus Rang-Konvergenz der Markenreihenfolge.")+
      blockB(cells,od)+
      h("3","Kreuz-Matrix: erwaehnt × zitiert")+ sub("Wird ERGO genannt (eigener Crawl) und aus eigenen Quellen belegt (Zitate)? Vier Quadranten je Thema.")+
      blockC(cells,od)+
      h("4","Hebel: Zitations-Footprint (Fruehindikator)")+ sub("Nachgelagerter Steuerungs-Hebel — nicht die Wirkung selbst.")+
      blockD();
    wire(host);
  }
  function wire(host){
    var box=document.getElementById("geoWirkung"); if(!box) return;
    box.querySelectorAll(".gwm").forEach(function(btn){
      btn.addEventListener("click", function(){
        var m=btn.getAttribute("data-gm"); if(m===gwMode) return;
        gwMode=m; render(host);
      });
    });
  }

  /* ============================================================
     Build + Retry (Muster aus korrelation_upgrade.js)
     ============================================================ */
  var loadTries=0;
  function ensureData(host){
    // Peec-Zellen laden (einmal), Peec-Zeitraum merken; danach neu rendern.
    loadCells().then(function(cells){
      if(cells && !window.__GW_ZR){
        // Zeitraum aus Roh-CSV einmalig ziehen (nur fuers Datenstand-Label)
        fetch("data/peec_cells.csv?t="+Date.now(),{cache:"no-store"}).then(function(r){ return r.ok?r.text():null; }).then(function(t){
          if(t){ var l=t.replace(/^﻿/,"").split("\n")[1]; if(l){ window.__GW_ZR=(l.split(";")[0]||"").replace(/_/g," bis "); } render(host); }
        }).catch(function(){});
      }
      render(host);
      // Weiter pollen, solange eine Quelle fehlt (max ~20s) — aber immer schon rendern (mit Hinweistexten)
      if((!cells || !snapData()) && loadTries++<50){ setTimeout(function(){ window.__GW_CELLS=window.__GW_CELLS; ensureData(host); }, 400); }
    });
  }
  function build(){
    var host=document.querySelector('section[data-content="geo"]');
    if(!host) return false;
    render(host);       // sofort Skelett/Hinweise (id existiert immer)
    ensureData(host);   // asynchron nachladen + re-render
    return true;
  }
  ready(function(){
    var tries=0;
    (function wait(){ tries++; if(build()) return; if(tries<40) setTimeout(wait,300); })();
    var tb=document.querySelector('[data-tab="geo"]');
    if(tb) tb.addEventListener("click", function(){ [150,600,1400].forEach(function(d){ setTimeout(build,d); }); });
  });

  // Test-Hook (jsdom)
  if(typeof module!=="undefined" && module.exports){
    module.exports={ parsePeec:parsePeec, ownData:ownData, peecErgoAgg:peecErgoAgg, ergoCiteShare:ergoCiteShare, TH_MENTION:TH_MENTION, TH_CITE:TH_CITE };
  }
})();
