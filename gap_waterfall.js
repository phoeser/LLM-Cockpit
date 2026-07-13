/* ===========================================================================
   ERGO LLM-Cockpit — Gap-Wasserfall "Warum liegt der Marktfuehrer vorn?"
   Zerlegt den SoV-Abstand einer Marke zum Marktfuehrer in Treiber-Beitraege
   (Footprint, Groesse, Rest) aus level_model.joint_model.gap_decomposition.
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

  var COL = { base:"#9aa0a8", cite_share:"#b8860b", size:"#6b7280", rest:"#d9dce1", leader:"#dc0028" };
  var LBL = { cite_share:"Footprint (Autoritaet)", size:"Groesse/Bekanntheit" };

  function sovOf(lm, brand){
    var ar = (lm.combined && lm.combined.authority_ranking) || [];
    for (var i=0;i<ar.length;i++){ if(ar[i].brand===brand) return ar[i].mean_sov_pct; }
    return null;
  }

  function render(host, lm, brand){
    var jm = lm.joint_model;
    var box = document.getElementById("gapWaterfallBox");
    if(!box){ box=document.createElement("div"); box.id="gapWaterfallBox";
      box.className="bg-white rounded-xl shadow p-6 mb-6";
      var anchor=document.getElementById("driverRankingBox");
      if(anchor && anchor.nextSibling) host.insertBefore(box, anchor.nextSibling); else host.insertBefore(box, host.firstChild);
    }
    box.innerHTML="";
    if(!jm || !jm.available || !jm.gap_decomposition){
      box.innerHTML='<h3 style="font-size:16px;font-weight:700;margin:0">Warum liegt der Marktführer vorn?</h3>'+
        '<p style="font-size:12px;color:#9ca3af;margin-top:8px">Noch keine Zerlegungs-Daten (kommt mit dem nächsten Nightly).</p>';
      return;
    }
    var leader = jm.leader;
    var others = Object.keys(jm.gap_decomposition);
    if(others.indexOf(brand)<0) brand = (others.indexOf("ERGO")>=0?"ERGO":others[0]);
    var g = jm.gap_decomposition[brand];
    var baseSov = sovOf(lm, brand);
    var leadSov = sovOf(lm, leader);
    if(baseSov==null || leadSov==null){ baseSov = 0; leadSov = (g.actual_gap_pp||0); }

    var contrib = g.contrib_pp || {};
    var keys = Object.keys(contrib);
    var explained = g.explained_pp!=null ? g.explained_pp : keys.reduce(function(a,k){return a+(contrib[k]||0);},0);
    var rest = (g.actual_gap_pp||0) - explained;

    // Segmente des Balkens (von baseSov bis leadSov)
    var segs = [{k:"base", label:brand, val:baseSov, col:COL.base}];
    keys.forEach(function(k){ segs.push({k:k, label:(LBL[k]||k), val:Math.max(0,contrib[k]||0), col:COL[k]||COL.rest}); });
    if(rest>0.05) segs.push({k:"rest", label:"Rest / unerklärt", val:rest, col:COL.rest});
    var total = leadSov>0?leadSov:segs.reduce(function(a,s){return a+s.val;},0);

    // Marken-Umschalter
    var sel = '<div style="display:flex;gap:6px;flex-wrap:wrap">'+others.map(function(o){
      var on=o===brand; return '<button data-b="'+o+'" class="gwb" style="font-size:11px;padding:3px 9px;border-radius:8px;border:1px solid '+(on?"#dc0028":"#ccc")+';background:'+(on?"#dc0028":"#fff")+';color:'+(on?"#fff":"#282d37")+';cursor:pointer">'+o+'</button>';
    }).join("")+'</div>';

    var bar='<div style="display:flex;height:34px;border-radius:6px;overflow:hidden;margin:14px 0 6px;border:1px solid #eee">';
    segs.forEach(function(s){ var w=total>0?(s.val/total*100):0; if(w<=0)return;
      bar+='<div title="'+s.label+': '+ (s.k==="base"?sovLbl(s.val):pp(s.val)) +'" style="width:'+w+'%;background:'+s.col+'"></div>'; });
    bar+='</div>';

    // Legende / Stufen
    var legend='<div style="display:grid;grid-template-columns:1fr auto;gap:2px 12px;font-size:12.5px;margin-top:6px">';
    legend+='<div><span style="display:inline-block;width:10px;height:10px;background:'+COL.base+';border-radius:2px;margin-right:6px"></span>'+brand+' Basis</div><div style="text-align:right;font-weight:600">'+sovLbl(baseSov)+'</div>';
    keys.forEach(function(k){ legend+='<div><span style="display:inline-block;width:10px;height:10px;background:'+(COL[k]||COL.rest)+';border-radius:2px;margin-right:6px"></span>'+(LBL[k]||k)+'</div><div style="text-align:right;font-weight:600;color:'+(COL[k]||"#282d37")+'">'+pp(contrib[k])+'</div>'; });
    if(rest>0.05) legend+='<div><span style="display:inline-block;width:10px;height:10px;background:'+COL.rest+';border-radius:2px;margin-right:6px"></span>Rest / unerklärt</div><div style="text-align:right;font-weight:600">'+pp(rest)+'</div>';
    legend+='<div style="border-top:1px solid #eee;padding-top:4px"><span style="display:inline-block;width:10px;height:10px;background:'+COL.leader+';border-radius:2px;margin-right:6px"></span><b>'+leader+' (Marktführer)</b></div><div style="text-align:right;font-weight:700;border-top:1px solid #eee;padding-top:4px;color:'+COL.leader+'">'+sovLbl(leadSov)+'</div>';
    legend+='</div>';

    // Auto-Satz
    var top = keys.slice().sort(function(a,b){return (contrib[b]||0)-(contrib[a]||0);})[0];
    var sentence = top ? ('Von '+pp(g.actual_gap_pp).replace("+","")+' Rückstand entfallen '+pp(contrib[top]).replace("+","")+' auf '+(LBL[top]||top).replace(" (Autoritaet)","")+' — der größte Hebel.') : '';

    box.innerHTML =
      '<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px">'+
        '<div><h3 style="font-size:16px;font-weight:700;margin:0">Warum liegt '+leader+' vor '+brand+'?</h3>'+
        '<p style="font-size:12px;color:#6b7280;margin:2px 0 0">SoV-Abstand zum Marktführer, zerlegt in Treiber-Beiträge (gemeinsames Modell).</p></div>'+
        sel+'</div>'+ bar + legend +
      '<div style="font-size:12px;color:#6b7280;margin-top:10px">'+sentence+'</div>';

    box.querySelectorAll(".gwb").forEach(function(btn){
      btn.addEventListener("click", function(){ render(host, lm, btn.getAttribute("data-b")); });
    });
  }

  function build(){
    var host=document.querySelector('section[data-content="korrelation"]');
    if(!host || !window.__GW_LM) return false;
    render(host, window.__GW_LM, "ERGO");
    return true;
  }
  ready(function(){
    getData().then(function(d){
      window.__GW_LM=(d && d.level_model)?d.level_model:{};
      var tries=0; (function wait(){ tries++; if(build())return; if(tries<40) setTimeout(wait,300); })();
      var tab=document.querySelector('[data-tab="korrelation"]');
      if(tab) tab.addEventListener("click", function(){ [150,600,1400].forEach(function(x){ setTimeout(build,x); }); });
    });
  });
})();
