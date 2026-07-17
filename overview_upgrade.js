/* ============================================================
   ERGO LLM-Cockpit — Übersicht kompakt (15.07.2026)
   Grafische Kurz-Übersicht als erste Sektion im Übersicht-Tab:
   KPI-Kacheln (SoV+Trend, Rang/Gap, Treiber-Fazit, Peec-Check),
   SoV-Balken Top-Marken, Themen-Hotspots, Preisposition.
   Datenquellen: GEO_SNAPSHOT, SOV_HISTORY, CORRELATION_IMPACT,
   PRICE_COMPARISON (alle bereits vom v3-Loader geladen).
   ============================================================ */
(function () {
  "use strict";
  function ready(fn){ if(document.readyState!=="loading") fn(); else document.addEventListener("DOMContentLoaded",fn); }
  function pct(v,d){ return (v==null||isNaN(v))?"—":(Math.round(v*Math.pow(10,d==null?1:d))/Math.pow(10,d==null?1:d)).toFixed(d==null?1:d).replace(".",",")+" %"; }
  function pp(v){ return (v==null||isNaN(v))?"—":((v>0?"+":"")+(Math.round(v*10)/10).toFixed(1).replace(".",",")+" pp"); }
  var BC={ERGO:"#dc0028",Allianz:"#003781","HUK-Coburg":"#006633",AXA:"#00008f",Generali:"#c8102e","Signal Iduna":"#005ca9","R+V":"#004f9f",DEVK:"#005ea8",Hannoversche:"#007a33",CosmosDirekt:"#f59e0b"};

  function kpi(icon,label,value,sub,color){
    return '<div style="flex:1;min-width:170px;background:linear-gradient(180deg,#fff,#fafafa);border:1px solid #eee;border-radius:12px;padding:14px 16px">'+
      '<div style="font-size:20px">'+icon+'</div>'+
      '<div style="font-size:22px;font-weight:800;color:'+(color||"#1a1a2e")+';line-height:1.15;margin-top:2px">'+value+'</div>'+
      '<div style="font-size:12px;font-weight:600;color:#374151">'+label+'</div>'+
      (sub?'<div style="font-size:11px;color:#9ca3af;margin-top:2px">'+sub+'</div>':'')+'</div>';
  }

  function ergoTrend(){
    var h=window.SOV_HISTORY;
    if(!Array.isArray(h)||!h.length) return null;
    var byDate={};
    h.forEach(function(r){ if(r.brand!=="ERGO"||r.sov_pct==null) return;
      (byDate[r.date]=byDate[r.date]||[]).push(r.sov_pct); });
    var days=Object.keys(byDate).sort();
    if(days.length<2) return null;
    function avg(a){ return a.reduce(function(x,y){return x+y;},0)/a.length; }
    var last=avg(byDate[days[days.length-1]]);
    var prevDay=days[Math.max(0,days.length-8)];
    return { last:last, delta:last-avg(byDate[prevDay]), since:prevDay };
  }

  function build(){
    var host=document.querySelector('section[data-content="overview"]');
    var g=window.GEO_SNAPSHOT;
    if(!host||!g||!g.totals_ranking) return false;
    if(document.getElementById("ovCompact")) return true;

    var rank=g.totals_ranking;
    var ergoIdx=-1, ergo=null, leader=rank[0];
    rank.forEach(function(r,i){ if(r.name==="ERGO"){ ergoIdx=i; ergo=r; } });
    var tr=ergoTrend();
    var ci=window.CORRELATION_IMPACT||{}, lm=ci.level_model||{};
    var fj=(lm.full_joint||{}).grounded, pfj=(lm.price_footprint_joint||{}).grounded;
    var gd=((fj&&fj.available&&fj.gap_decomposition)||{}).ERGO || ((pfj&&pfj.available&&pfj.gap_decomposition)||{}).ERGO;
    var wp=lm.with_peec, val=(wp&&wp.validation)||{};

    // Kachel-Zeile
    var k='';
    k+=kpi("📈","ERGO Sichtbarkeit (SoV gesamt)", pct(100*(ergo?ergo.share_of_voice:null)),
      tr?("Trend seit "+tr.since+": "+pp(tr.delta)):"", tr&&tr.delta<0?"#b91c1c":"#067d3a");
    k+=kpi("🏁","Rang unter "+rank.length+" Marken", ergoIdx>=0?("#"+(ergoIdx+1)):"—",
      leader?("Führer: "+leader.name+" "+pct(100*leader.share_of_voice)):"" );
    if(gd&&gd.contrib_pp){
      var c=gd.contrib_pp;
      k+=kpi("🧭","Warum Allianz vorn liegt", pp(gd.actual_gap_pp).replace("+","")+" Gap",
        "Footprint "+pp(c.cite_share)+" · Größe "+pp(c.size)+" · Preis "+pp(c.relprice),"#1a1a2e");
    } else {
      k+=kpi("🧭","Haupttreiber","Quellpräsenz","Details im Reiter Korrelationsanalyse");
    }
    k+=kpi("✔","Messung validiert (Peec AI)", val.spearman_r!=null?("ρ = "+String(val.spearman_r).replace(".",",")):"—",
      val.n_common_cells?(val.n_common_cells+" gemeinsame Zellen, 2. Quelle"):"","#067d3a");

    // SoV-Balken Top 6
    var mx=Math.max.apply(null,rank.slice(0,6).map(function(r){return r.share_of_voice;}));
    var bars=rank.slice(0,6).map(function(r){
      var w=Math.max(3,100*r.share_of_voice/mx);
      var col=BC[r.name]||"#9ca3af";
      return '<div style="display:flex;align-items:center;gap:8px;margin:4px 0">'+
        '<span style="width:110px;font-size:12px;font-weight:'+(r.name==="ERGO"?"800":"500")+';color:'+(r.name==="ERGO"?"#dc0028":"#374151")+'">'+r.name+'</span>'+
        '<div style="flex:1;background:#f1f5f9;border-radius:5px;height:14px;overflow:hidden"><div style="width:'+w+'%;height:100%;background:'+col+';border-radius:5px"></div></div>'+
        '<span style="width:52px;text-align:right;font-size:12px;font-weight:600">'+pct(100*r.share_of_voice)+'</span></div>';
    }).join('');

    // Themen-Hotspots (Top 3 Gap zum Führer, gemini)
    var hs=[];
    Object.keys(g.products||{}).forEach(function(pid){
      var br=(((g.products[pid].summary_by_llm)||{}).gemini||{}).brands||[];
      var e=null,a=null;
      br.forEach(function(b){ if(b.name==="ERGO")e=100*b.share_of_voice; if(b.name===(leader?leader.name:"Allianz"))a=100*b.share_of_voice; });
      if(e!=null&&a!=null) hs.push({n:g.products[pid].name||pid, gap:a-e});
    });
    hs.sort(function(x,y){return y.gap-x.gap;});
    var hsHtml=hs.slice(0,3).map(function(h){
      return '<div style="display:flex;justify-content:space-between;font-size:12.5px;padding:5px 0;border-bottom:1px solid #f5f5f5"><span style="font-weight:600;color:#1e293b">'+h.n+'</span><span style="font-weight:700;color:#b91c1c">'+pp(h.gap).replace("+","")+' Rückstand</span></div>';
    }).join('');

    // Preisposition (Anzahl Produkte guenstigste / teuerste Zielmarke)
    var pcd=window.PRICE_COMPARISON, cheap=0, exp=0, tot=0;
    if(pcd&&pcd.products){
      Object.keys(pcd.products).forEach(function(pid){
        var b=((pcd.products[pid].profiles||{}).age_50||{}).brands||{};
        var prices=[]; var ep=null;
        Object.keys(b).forEach(function(k){ if(k.indexOf("_other_")===0)return; var p=b[k]&&b[k].price; if(p>0){ prices.push(p); if(k==="ergo") ep=p; } });
        if(ep!=null&&prices.length>=2){ tot++; if(ep<=Math.min.apply(null,prices)) cheap++; if(ep>=Math.max.apply(null,prices)) exp++; }
      });
    }

    var box=document.createElement("div");
    box.id="ovCompact"; box.className="bg-white rounded-xl p-6 shadow mb-6";
    box.innerHTML='<div style="display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:6px">'+
      '<h2 class="text-2xl font-bold text-ergo-dark" style="margin:0">Auf einen Blick</h2>'+
      '<span style="font-size:11px;color:#9ca3af">Stand: '+String(g.finished_at||g.started_at||"").slice(0,10)+' · alle Details in den Reitern</span></div>'+
      '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:12px">'+k+'</div>'+
      '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-top:16px">'+
        '<div style="border:1px solid #eee;border-radius:12px;padding:14px"><div style="font-size:13px;font-weight:700;margin-bottom:6px">Sichtbarkeit Top-Marken</div>'+bars+'</div>'+
        '<div style="border:1px solid #eee;border-radius:12px;padding:14px"><div style="font-size:13px;font-weight:700;margin-bottom:6px">Größte Themen-Rückstände</div>'+(hsHtml||'<span style="font-size:12px;color:#9ca3af">—</span>')+
          '<div style="font-size:11px;color:#9ca3af;margin-top:6px">→ Prio-Details: Reiter Korrelationsanalyse</div></div>'+
        '<div style="border:1px solid #eee;border-radius:12px;padding:14px"><div style="font-size:13px;font-weight:700;margin-bottom:6px">Preisposition ERGO</div>'+
          '<div style="font-size:26px;font-weight:800;color:#1a1a2e">'+(tot? (cheap+"× günstigste · "+exp+"× teuerste"):"—")+'</div>'+
          '<div style="font-size:11px;color:#9ca3af;margin-top:4px">von '+tot+' vergleichbaren Produkten (50-J.-Referenzprofil) · Details: Reiter Preisvergleich</div></div>'+
      '</div>';
    host.insertBefore(box, host.firstChild);
    return true;
  }
  ready(function(){
    var tries=0; (function w(){ tries++; if(build()) return; if(tries<50) setTimeout(w,400); })();
    var tb=document.querySelector('[data-tab="overview"]');
    if(tb) tb.addEventListener("click",function(){ [300,900].forEach(function(d){ setTimeout(build,d); }); });
  });
})();
