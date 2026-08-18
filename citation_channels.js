/* ============================================================
   ERGO LLM-Cockpit — Zitations-Kanäle (GEO-Tab)
   Zeigt, WORAUS die LLMs je Thema schöpfen (eigene Seiten /
   Vergleichsportale / andere Versicherer / Fach- & Testquellen)
   und WO ERGO präsent ist — die konkreten Ziel-Quellen.
   Deskriptiv (was zitiert wird), kein Kausalanspruch.
   Mix wird aus Counts gerechnet (summiert immer 100%).
   Quelle: globales GEO_SNAPSHOT (Fallback fetch).
   Einbindung: <script src="citation_channels.js"></script>.
   ============================================================ */
(function () {
  "use strict";
  function ready(fn){ if(document.readyState!=="loading") fn(); else document.addEventListener("DOMContentLoaded",fn); }
  /* 15.08.2026: dkv.de/dkv.com ergaenzt, damit im Reiter nicht zwei Wahrheiten
     nebeneinander stehen (hier Fremdquelle, in allen anderen Modulen ERGO).
     18.08.2026 WIEDER ENTFERNT - diesmal in die andere Richtung aufgeloest:
     Paul hat entschieden, DKV als EIGENE Marke zu fuehren (konsistent zu
     CosmosDirekt, das ebenfalls eigenstaendig laeuft, obwohl es zur Generali
     gehoert). dkv.de/dkv.com sind damit ueberall Fremdquellen, und die
     Einheitlichkeit im Reiter bleibt gewahrt - nur eben andersherum. */
  var OWN = {"ergo.de":1,"ergo.com":1,"ergodirekt.de":1,"ergo-reiseversicherung.de":1};
  var CH = {
    eigen:       {lab:"ERGO (eigene Seiten)",        col:"#dc0028", how:"direkt: eigene Inhalte/Domains zitierfähig machen"},
    portal:      {lab:"Vergleichsportale / Ratgeber", col:"#2a78d6", how:"über Listung, Rang & Bewertungen dort (z. B. Check24, Verivox)"},
    wettbewerber:{lab:"Andere Versicherer",          col:"#9ca3af", how:"nicht direkt beeinflussbar"},
    sonstige:    {lab:"Fach-, Test- & Sonstige",     col:"#b9942e", how:"über Produktqualität, Tests (test.de), PR/Kooperationen"}
  };
  var ORDER = ["eigen","portal","wettbewerber","sonstige"];

  function getSnap(){
    try{ if(typeof GEO_SNAPSHOT!=="undefined" && GEO_SNAPSHOT && GEO_SNAPSHOT.products) return Promise.resolve(GEO_SNAPSHOT); }catch(e){}
    if(window.GEO_SNAPSHOT && window.GEO_SNAPSHOT.products) return Promise.resolve(window.GEO_SNAPSHOT);
    return fetch("data/geo_snapshot.json?t="+Date.now(),{cache:"no-store"}).then(function(r){return r.ok?r.json():null;}).catch(function(){return null;});
  }
  function dom(d){ return String(d||"").replace(/^www\./,""); }
  function r1(v){ return Math.round((v||0)*10)/10; }

  // Anteile robust aus Counts (summiert 100%)
  function mixOf(by){
    var tot=0, out={};
    ORDER.forEach(function(k){ var c=(by[k]||{}).count||0; out[k]=c; tot+=c; });
    var sh={}; ORDER.forEach(function(k){ sh[k]= tot>0 ? 100*out[k]/tot : 0; });
    return {share:sh, total:tot};
  }
  function mixBar(sh){
    var seg="";
    ORDER.forEach(function(k){ var s=sh[k]||0; if(s<=0) return;
      seg+='<div title="'+CH[k].lab+' '+r1(s)+'%" style="width:'+s+'%;background:'+CH[k].col+';height:100%"></div>'; });
    return '<div style="display:flex;height:12px;border-radius:6px;overflow:hidden;background:#eee">'+seg+'</div>';
  }
  function chip(domain, share, cat){
    var isOwn=OWN[dom(domain)]; var c=CH[cat]||CH.sonstige;
    return '<span style="display:inline-block;font-size:11px;padding:2px 7px;margin:2px 3px 2px 0;border-radius:10px;'+
      'background:'+(isOwn?"#dc0028":"#f1f0ee")+';color:'+(isOwn?"#fff":"#282d37")+';border:1px solid '+(isOwn?"#dc0028":"#e2e0dc")+'">'+
      '<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:'+c.col+';margin-right:4px;vertical-align:middle"></span>'+
      dom(domain)+' '+r1(share)+'%</span>';
  }

  function build(g){
    var host=document.querySelector('section[data-content="geo"]');
    if(!host || document.getElementById("chanCard")) return;
    var products=g.products||{};

    // Gesamt-Mix aus Themen aggregieren (robust)
    var agg={eigen:{count:0},portal:{count:0},wettbewerber:{count:0},sonstige:{count:0}};
    Object.keys(products).forEach(function(pid){
      var by=(products[pid].cited_sources||{}).by_category||{};
      ORDER.forEach(function(k){ agg[k].count += (by[k]||{}).count||0; });
    });
    var oMix=mixOf(agg);
    var co=g.cited_sources_overall||{};
    var coTop=(co.overall||[]).slice(0,14);

    var card=document.createElement("div");
    card.id="chanCard";
    card.className="bg-white rounded-xl shadow p-6 mb-6";

    var html=''+
      '<h3 style="font-size:16px;font-weight:600;margin:0">Zitations-Kanäle — woraus die LLMs schöpfen (und wo ERGO präsent ist)</h3>'+
      '<p style="font-size:13px;color:#6b7280;margin:3px 0 12px">Welche Quell-Typen die LLMs je Thema zitieren und wo ERGO vorkommt — die konkreten Ziel-Quellen. Deskriptiv (was zitiert wird), kein Kausalnachweis.</p>';

    html+='<div style="border:1px solid #eee;border-radius:10px;padding:14px;margin-bottom:14px">'+
      '<div style="font-size:13px;font-weight:600;margin-bottom:6px">Themenübergreifend: Quellen-Mix aller Zitate</div>'+
      mixBar(oMix.share)+
      '<div style="font-size:11px;color:#6b7280;margin:6px 0 10px">'+
        ORDER.map(function(k){return '<span style="margin-right:12px"><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:'+CH[k].col+';margin-right:4px"></span>'+CH[k].lab+' '+r1(oMix.share[k])+'%</span>';}).join('')+
      '</div>'+
      '<div style="font-size:12px;font-weight:600;margin-bottom:4px">Meist-zitierte Quellen der LLMs (Farbe = Kanal-Typ, ERGO rot):</div>'+
      '<div>'+coTop.map(function(r){return chip(r.domain,r.share,r.category);}).join('')+'</div>'+
    '</div>';

    html+='<div style="font-size:13px;font-weight:600;margin-bottom:6px">Je Thema: Kanal-Mix, ERGO-Präsenz und Ziel-Quellen</div>'+
      '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12px">'+
      '<thead><tr style="text-align:left;color:#6b7280">'+
        '<th style="padding:6px 8px">Thema</th><th style="padding:6px 8px;min-width:120px">Kanal-Mix</th>'+
        '<th style="padding:6px 8px">ERGO eigen</th><th style="padding:6px 8px">Meist-zitierte Quellen (außer ERGO)</th></tr></thead><tbody>';
    Object.keys(products).forEach(function(pid){
      var pd=products[pid]; var cs=pd.cited_sources||{}; var by=cs.by_category||{};
      var m=mixOf(by); var eigen=m.share.eigen; var portalDom=m.share.portal;
      var top=(cs.overall||[]).filter(function(r){return !OWN[dom(r.domain)];}).slice(0,4);
      html+='<tr style="border-top:1px solid #f0f0f0">'+
        '<td style="padding:7px 8px;font-weight:600">'+(pd.name||pid)+(portalDom>=30?' <span style="font-size:10px;color:#2a78d6">· portal-lastig</span>':'')+'</td>'+
        '<td style="padding:7px 8px">'+mixBar(m.share)+'</td>'+
        '<td style="padding:7px 8px;font-weight:700;color:'+(eigen>=5?"#067d3a":"#dc0028")+'">'+r1(eigen)+'%</td>'+
        '<td style="padding:7px 8px">'+top.map(function(r){return chip(r.domain,r.share,r.category);}).join('')+'</td>'+
      '</tr>';
    });
    html+='</tbody></table></div>';

    html+='<div style="margin-top:12px;font-size:11px;color:#6b7280;line-height:1.6">'+
      '<b>Wie beeinflussbar?</b> '+
      ORDER.map(function(k){return '<span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:'+CH[k].col+';margin:0 4px 0 10px"></span><b>'+CH[k].lab+':</b> '+CH[k].how;}).join('')+
      '<br>Lesart: Wo ERGO-eigen niedrig und Portale/Andere hoch sind, zählt zusätzlich die Präsenz/Bewertung auf den zitierten Portalen — nicht nur eigene Seiten. „portal-lastig" = ≥30 % der Zitate sind Vergleichsportale.</div>';

    card.innerHTML=html;
    var anchor=document.getElementById("lmCard")||document.getElementById("fpCard")||document.getElementById("geoProductCards");
    if(anchor && anchor.parentNode) anchor.parentNode.insertBefore(card, anchor.nextSibling||anchor);
    else host.appendChild(card);
  }

  ready(function(){
    var tries=0;
    (function wait(){
      tries++;
      getSnap().then(function(g){
        if(g && g.products && document.querySelector('section[data-content="geo"]')){ build(g); }
        else if(tries<25) setTimeout(wait,300);
      });
    })();
  });
})();
