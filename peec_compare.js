/* ============================================================
   ERGO LLM-Cockpit — Peec-Zweitmessung im LLM-Sichtbarkeits-Tab
   (15.07.2026) Zeigt beide Quellen GETRENNT + Abgleich:
   - Eigene Messung (API-Crawl, Gemini-grounded) je Thema
   - Peec AI (UI-Scraping, grounded-Engines inkl. AI Overview/Mode)
   - Abweichung + Rang-Konvergenz je Thema
   Quellen: window.GEO_SNAPSHOT + data/peec_cells.csv (fetch).
   Additiv: haengt sich als Sektion in den geo-Tab.
   ============================================================ */
(function () {
  "use strict";
  function ready(fn){ if(document.readyState!=="loading") fn(); else document.addEventListener("DOMContentLoaded",fn); }
  function pct(v){ return (v==null||isNaN(v))?"—":(Math.round(v*10)/10).toFixed(1).replace(".",",")+" %"; }

  var TMAP = { "Zahnzusatz":"zahnzusatz","Sterbegeld":"sterbegeld","Risikoleben":"risikoleben",
    "Berufsunfähigkeit":"berufsunfaehigkeit","Rechtsschutz":"rechtsschutz","Haftpflicht":"haftpflicht",
    "Hausrat":"hausrat","Kfz":"kfz","Unfall":"unfall","Krankenhauszusatz":"krankenhauszusatz","Reise":"reise" };
  var GROUND = { "Gemini":1,"Perplexity":1,"AI Overview":1,"AI Mode":1,"ChatGPT":1 };
  var BMAP = { "HUK24":"HUK-Coburg" };

  function loadPeec(){
    return fetch("data/peec_cells.csv?t="+Date.now(),{cache:"no-store"})
      .then(function(r){ return r.ok?r.text():null; })
      .then(function(t){
        if(!t) return null;
        var lines=t.replace(/^﻿/,"").split("\n");
        var head=lines[0].split(";");
        var idx={}; head.forEach(function(h,i){ idx[h.trim()]=i; });
        var mc={}, tot={};
        for(var i=1;i<lines.length;i++){
          var c=lines[i].split(";"); if(c.length<5) continue;
          if(!GROUND[c[idx.engine]]) continue;
          var pid=TMAP[(c[idx.thema]||"").trim()]; if(!pid) continue;
          var b=BMAP[c[idx.marke]]||c[idx.marke];
          var m=parseFloat(c[idx.mention_count]||0)||0;
          mc[pid]=mc[pid]||{}; mc[pid][b]=(mc[pid][b]||0)+m;
          tot[pid]=(tot[pid]||0)+m;
        }
        var out={};
        Object.keys(mc).forEach(function(pid){
          out[pid]={};
          Object.keys(mc[pid]).forEach(function(b){ out[pid][b]=tot[pid]?100*mc[pid][b]/tot[pid]:0; });
        });
        return out;
      }).catch(function(){ return null; });
  }

  // 18.07.2026 Fix: dashboard_v3 haelt GEO_SNAPSHOT als top-level `let` — das
  // landet NICHT auf window. Erst lexikalische Bindung versuchen, dann window
  // (health_banner.js spiegelt zusaetzlich).
  function snapData(){ try{ if(typeof GEO_SNAPSHOT!=="undefined" && GEO_SNAPSHOT) return GEO_SNAPSHOT; }catch(e){} return window.GEO_SNAPSHOT||null; }
  function ownSov(){
    var g=snapData();
    if(!g||!g.products) return null;
    var out={};
    Object.keys(g.products).forEach(function(pid){
      var brands=(((g.products[pid].summary_by_llm)||{}).gemini||{}).brands||[];
      out[pid]={_name:g.products[pid].name||pid};
      brands.forEach(function(b){ out[pid][b.name]=100*(b.share_of_voice||0); });
    });
    return out;
  }
  function pearson(x,y){
    var n=x.length; if(n<3) return null;
    var mx=0,my=0; x.forEach(function(v){mx+=v;}); y.forEach(function(v){my+=v;}); mx/=n; my/=n;
    var c=0,vx=0,vy=0;
    for(var i=0;i<n;i++){ c+=(x[i]-mx)*(y[i]-my); vx+=(x[i]-mx)*(x[i]-mx); vy+=(y[i]-my)*(y[i]-my); }
    return (vx>0&&vy>0)? c/Math.sqrt(vx*vy) : null;
  }
  function ranks(v){ var s=v.map(function(x,i){return [x,i];}).sort(function(a,b){return a[0]-b[0];}); var r=new Array(v.length); s.forEach(function(p,i){ r[p[1]]=i; }); return r; }

  function build(){
    var host=document.querySelector('section[data-content="geo"]');
    if(!host || document.getElementById("peecCmpBox")) return !!document.getElementById("peecCmpBox");
    var own=ownSov();
    if(!own) return false;
    loadPeec().then(function(peec){
      if(!peec || document.getElementById("peecCmpBox")) return;
      var box=document.createElement("div");
      box.id="peecCmpBox"; box.className="bg-white rounded-xl p-6 shadow mb-6";
      var rowsHtml=""; var allOwn=[], allPeec=[];
      var pids=Object.keys(own).filter(function(p){ return peec[p]; });
      pids.forEach(function(pid){
        var o=own[pid], p=peec[pid];
        var brands=Object.keys(o).filter(function(k){ return k!=="_name" && p[k]!=null; });
        if(brands.length<3) return;
        var xo=brands.map(function(b){return o[b];}), xp=brands.map(function(b){return p[b];});
        xo.forEach(function(v){allOwn.push(v);}); xp.forEach(function(v){allPeec.push(v);});
        var rho=pearson(ranks(xo),ranks(xp));
        var eO=o["ERGO"], eP=p["ERGO"];
        var diff=(eO!=null&&eP!=null)?(eO-eP):null;
        var rc=(rho==null)?"#9ca3af":(rho>=0.8?"#067d3a":(rho>=0.5?"#b45309":"#b91c1c"));
        rowsHtml+='<tr style="border-bottom:1px solid #f1f5f9">'+
          '<td style="padding:5px 8px;font-weight:600;color:#1e293b">'+(o._name||pid)+'</td>'+
          '<td style="padding:5px 8px;text-align:right">'+pct(eO)+'</td>'+
          '<td style="padding:5px 8px;text-align:right">'+pct(eP)+'</td>'+
          '<td style="padding:5px 8px;text-align:right;color:'+(diff!=null&&Math.abs(diff)>10?"#b45309":"#64748b")+'">'+(diff==null?"—":((diff>0?"+":"")+(Math.round(diff*10)/10).toFixed(1).replace(".",",")+" pp"))+'</td>'+
          '<td style="padding:5px 8px;text-align:right;font-weight:700;color:'+rc+'">'+(rho==null?"—":(Math.round(rho*100)/100).toFixed(2).replace(".",","))+'</td></tr>';
      });
      var rAll=pearson(allOwn,allPeec);
      box.innerHTML='<div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;align-items:flex-start">'+
        '<div><h3 class="text-lg font-bold text-ergo-dark" style="margin:0">Zweitmessung Peec AI — Abgleich der Quellen</h3>'+
        '<p style="font-size:12px;color:#6b7280;margin:2px 0 0">Zwei unabhängige Messungen derselben Sache: <b>Eigener Crawl</b> (Gemini-API, grounded) vs. <b>Peec AI</b> (UI-Scraping; Gemini, Perplexity, ChatGPT-UI, Google AI Overview &amp; AI Mode). Niveau-Unterschiede sind methodisch normal (Peec verteilt über 26 Marken) — entscheidend ist die <b>Rang-Konvergenz</b> je Thema.</p></div>'+
        '<span style="font-size:11px;font-weight:700;color:#067d3a;background:#e6f5ec;border-radius:6px;padding:4px 10px;white-space:nowrap">Gesamt-Korrelation r = '+(rAll==null?"—":(Math.round(rAll*100)/100).toFixed(2).replace(".",","))+'</span></div>'+
        '<div style="overflow-x:auto;margin-top:10px"><table style="width:100%;border-collapse:collapse;font-size:12.5px">'+
        '<thead><tr style="text-align:left;color:#64748b;border-bottom:1px solid #e2e8f0">'+
        '<th style="padding:5px 8px">Thema</th><th style="padding:5px 8px;text-align:right">ERGO SoV — eigener Crawl</th>'+
        '<th style="padding:5px 8px;text-align:right">ERGO SoV — Peec</th><th style="padding:5px 8px;text-align:right">Differenz</th>'+
        '<th style="padding:5px 8px;text-align:right" title="Spearman-Rangkorrelation der Markenreihenfolge in diesem Thema (1,0 = identische Reihenfolge)">Rang-ρ</th></tr></thead>'+
        '<tbody>'+rowsHtml+'</tbody></table></div>'+
        '<div style="font-size:11px;color:#9ca3af;margin-top:8px">Rang-ρ ≥ 0,8 grün = beide Quellen sehen dieselbe Markenreihenfolge (Messung validiert). Große ERGO-Differenzen (&gt;10 pp, bernstein) sind Prüf-Kandidaten (Prompt-Sets vergleichen). Peec-Daten: data/peec_cells.csv (Export 15.06.–14.07.).</div>';
      host.insertBefore(box, host.firstChild.nextSibling);
    });
    return true;
  }
  ready(function(){
    var tries=0; (function w(){ tries++; if(build()) return; if(tries<40) setTimeout(w,400); })();
    var tb=document.querySelector('[data-tab="geo"]');
    if(tb) tb.addEventListener("click",function(){ [300,900].forEach(function(d){ setTimeout(build,d); }); });
  });
})();
