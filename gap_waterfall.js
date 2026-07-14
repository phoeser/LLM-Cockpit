/* ===========================================================================
   ERGO LLM-Cockpit — Gap-Wasserfall "Warum liegt der Marktfuehrer vorn?" v2
   Fix 2026-07-14: nutzt die real vorhandenen Daten
   level_model.{grounded|ungrounded|combined}.gap_decomposition
   (das frueher erwartete level_model.joint_model liefert die Pipeline nicht
   — die Box zeigte deshalb dauerhaft nur einen Platzhalter).
   Zerlegt den SoV-Abstand einer Marke zum Marktfuehrer in:
   Footprint-Beitrag (gekappt bei 100 %) + Rest/unerklaert.
   Modus (grounded/ungrounded/beides) folgt dem Umschalter der Synthese
   (window.__gwSetMode wird von korrelation_upgrade.js aufgerufen).
   Einbindung: <script src="gap_waterfall.js"></script>
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
  function sovLbl(v){ return (v==null||isNaN(v))?"—":(Math.round(v*10)/10).toFixed(1).replace(".",",")+" %"; }

  var COL = { base:"#9aa0a8", foot:"#b8860b", rest:"#d9dce1", leader:"#dc0028" };
  var mode = "g", curBrand = "ERGO";
  function seg(lm){ return mode==="g"?lm.grounded:(mode==="u"?lm.ungrounded:lm.combined); }
  function modeLbl(){ return mode==="g"?"grounded (Web-Suche)":(mode==="u"?"ungrounded (ChatGPT)":"kombiniert"); }

  function sovOf(m, brand){
    var ar = m.authority_ranking || [];
    for (var i=0;i<ar.length;i++){ if(ar[i].brand===brand) return ar[i].mean_sov_pct; }
    return null;
  }

  function render(host, lm, brand){
    var box = document.getElementById("gapWaterfallBox");
    if(!box){
      box=document.createElement("div"); box.id="gapWaterfallBox";
      box.className="bg-white rounded-xl shadow p-6 mb-6";
      var anchor=document.getElementById("korrSynth");
      if(anchor && anchor.nextSibling) host.insertBefore(box, anchor.nextSibling);
      else if(anchor) host.appendChild(box);
      else host.insertBefore(box, host.firstChild);
    }
    var m = seg(lm) || {};
    if(!m.available || !m.gap_decomposition){
      box.innerHTML='<h3 style="font-size:16px;font-weight:700;margin:0">Warum liegt der Marktführer vorn?</h3>'+
        '<p style="font-size:12px;color:#9ca3af;margin-top:8px">Für diese Auswahl noch keine Zerlegungs-Daten.</p>';
      return;
    }
    var leader = m.leader;
    var others = Object.keys(m.gap_decomposition);
    if(others.indexOf(brand)<0) brand = (others.indexOf("ERGO")>=0?"ERGO":others[0]);
    curBrand = brand;
    var g = m.gap_decomposition[brand] || {};
    var baseSov = sovOf(m, brand);
    var leadSov = sovOf(m, leader);
    if(baseSov==null || leadSov==null){ baseSov = 0; leadSov = (g.actual_gap_pp||0); }

    var gap = g.actual_gap_pp || 0;
    // Footprint-Beitrag bei 100 % des Abstands kappen (Design-Doc: >100 % kappen)
    var foot = Math.max(0, Math.min(g.explained_by_footprint_pp||0, gap));
    var capped = (g.explained_by_footprint_pp||0) > gap + 0.05;
    var rest = Math.max(0, gap - foot);
    var shareTxt = (g.share_explained!=null) ? Math.round(Math.min(g.share_explained,1)*100) : null;

    // Marken-Umschalter
    var sel = '<div style="display:flex;gap:6px;flex-wrap:wrap">'+others.map(function(o){
      var on=o===brand; return '<button data-b="'+o+'" class="gwb" style="font-size:11px;padding:3px 9px;border-radius:8px;border:1px solid '+(on?"#dc0028":"#ccc")+';background:'+(on?"#dc0028":"#fff")+';color:'+(on?"#fff":"#282d37")+';cursor:pointer">'+o+'</button>';
    }).join("")+'</div>';

    // Gestapelter Balken von Basis bis Marktfuehrer
    var segs = [
      {label:brand+" Basis", val:baseSov, col:COL.base, isBase:true},
      {label:"Footprint (Quellpräsenz)", val:foot, col:COL.foot},
      {label:"Rest / unerklärt (Markenstärke u. a.)", val:rest, col:COL.rest}
    ];
    var total = leadSov>0?leadSov:segs.reduce(function(a,s){return a+s.val;},0);
    var bar='<div style="display:flex;height:34px;border-radius:6px;overflow:hidden;margin:14px 0 6px;border:1px solid #eee">';
    segs.forEach(function(s){ var w=total>0?(s.val/total*100):0; if(w<=0)return;
      bar+='<div title="'+s.label+': '+(s.isBase?sovLbl(s.val):pp(s.val))+'" style="width:'+w+'%;background:'+s.col+'"></div>'; });
    bar+='</div>';

    var legend='<div style="display:grid;grid-template-columns:1fr auto;gap:2px 12px;font-size:12.5px;margin-top:6px">';
    legend+='<div><span style="display:inline-block;width:10px;height:10px;background:'+COL.base+';border-radius:2px;margin-right:6px"></span>'+brand+' Basis (Ø SoV)</div><div style="text-align:right;font-weight:600">'+sovLbl(baseSov)+'</div>';
    legend+='<div><span style="display:inline-block;width:10px;height:10px;background:'+COL.foot+';border-radius:2px;margin-right:6px"></span>Footprint (Quellpräsenz)'+(capped?' <span style="font-size:10px;color:#b45309">(auf 100 % gekappt)</span>':'')+'</div><div style="text-align:right;font-weight:600;color:'+COL.foot+'">'+pp(foot)+'</div>';
    legend+='<div><span style="display:inline-block;width:10px;height:10px;background:'+COL.rest+';border-radius:2px;margin-right:6px"></span>Rest / unerklärt</div><div style="text-align:right;font-weight:600">'+pp(rest)+'</div>';
    legend+='<div style="border-top:1px solid #eee;padding-top:4px"><span style="display:inline-block;width:10px;height:10px;background:'+COL.leader+';border-radius:2px;margin-right:6px"></span><b>'+leader+' (Marktführer)</b></div><div style="text-align:right;font-weight:700;border-top:1px solid #eee;padding-top:4px;color:'+COL.leader+'">'+sovLbl(leadSov)+'</div>';
    legend+='</div>';

    var sentence = 'Von '+pp(gap).replace("+","")+' Rückstand gehen '+(shareTxt!=null?('rund <b>'+shareTxt+' %</b>'):pp(foot))+' statistisch mit dem geringeren Zitations-Footprint einher — eine <b>Zerlegung, kein Kausalnachweis</b>.';

    box.innerHTML =
      '<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px">'+
        '<div><h3 style="font-size:16px;font-weight:700;margin:0">Warum liegt '+leader+' vor '+brand+'?</h3>'+
        '<p style="font-size:12px;color:#6b7280;margin:2px 0 0">SoV-Abstand zum Marktführer, zerlegt nach dem Mundlak-Level-Modell <span style="color:#9ca3af">('+modeLbl()+' · Modus folgt dem Umschalter oben)</span></p></div>'+
        sel+'</div>'+ bar + legend +
      '<div style="font-size:12px;color:#6b7280;margin-top:10px">'+sentence+'</div>';

    box.querySelectorAll(".gwb").forEach(function(btn){
      btn.addEventListener("click", function(){ render(host, lm, btn.getAttribute("data-b")); });
    });
  }

  function build(){
    var host=document.querySelector('section[data-content="korrelation"]');
    if(!host || !window.__GW_LM) return false;
    render(host, window.__GW_LM, curBrand);
    return true;
  }
  ready(function(){
    getData().then(function(d){
      window.__GW_LM=(d && d.level_model)?d.level_model:{};
      // Modus-Hook fuer korrelation_upgrade.js (Synthese-Umschalter)
      window.__gwSetMode=function(m){ mode=m; build(); };
      var tries=0; (function wait(){ tries++; if(build())return; if(tries<40) setTimeout(wait,300); })();
      var tab=document.querySelector('[data-tab="korrelation"]');
      if(tab) tab.addEventListener("click", function(){ [150,600,1400].forEach(function(x){ setTimeout(build,x); }); });
    });
  });
})();
