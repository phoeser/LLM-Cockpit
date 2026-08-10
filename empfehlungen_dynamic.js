/* ============================================================
   ERGO LLM-Cockpit — Dynamische Empfehlungen (15.07.2026)
   Erste Sektion im Empfehlungs-Tab: Empfehlungen werden bei jedem
   Seitenaufruf LIVE aus den aktuellen Modelldaten abgeleitet
   (aktualisieren sich also automatisch mit jedem Nightly):
   - Themen-Hotspots (Gap gross + eigener Zitatanteil klein -> Content-Prio)
   - Preis-Befunde (Produkte, in denen ERGO deutlich teurer ist)
   - Treiber-Lage (Footprint/Preis aus dem Joint-Modell)
   Quellen: GEO_SNAPSHOT, CORRELATION_IMPACT, PRICE_COMPARISON.
   ============================================================ */
(function () {
  "use strict";
  function ready(fn){ if(document.readyState!=="loading") fn(); else document.addEventListener("DOMContentLoaded",fn); }
  function pp(v){ return (v==null||isNaN(v))?"—":((v>0?"+":"")+(Math.round(v*10)/10).toFixed(1).replace(".",",")+" pp"); }
  var DOM2BRAND={"ergo.de":"ERGO","ergo-reiseversicherung.de":"ERGO","dkv.com":"ERGO","allianz.de":"Allianz","axa.de":"AXA","generali.de":"Generali","cosmosdirekt.de":"CosmosDirekt","huk.de":"HUK-Coburg","huk24.de":"HUK-Coburg","signal-iduna.de":"Signal Iduna","adac.de":"ADAC","arag.de":"ARAG","alte-leipziger.de":"Alte Leipziger","barmenia.de":"Barmenia","da-direkt.de":"DA Direkt","devk.de":"DEVK","debeka.de":"Debeka","diebayerische.de":"Die Bayerische","die-bayerische.de":"Die Bayerische","gothaer.de":"Gothaer","hdi.de":"HDI","hannoversche.de":"Hannoversche","hansemerkur.de":"HanseMerkur","lv1871.de":"LV 1871","ruv.de":"R+V","vhv.de":"VHV","wgv.de":"WGV","wuerttembergische.de":"Württembergische","zurich.de":"Zurich"};

  function card(prio, title, body, why, amp){
    var pc = prio==="hoch"?"#b91c1c":(prio==="mittel"?"#b45309":"#64748b");
    return '<div style="border:1px solid #eee;border-left:4px solid '+pc+';border-radius:10px;padding:12px 14px;margin:8px 0;background:#fff">'+
      '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">'+
      '<span style="font-size:10px;font-weight:800;color:#fff;background:'+pc+';border-radius:4px;padding:2px 7px;text-transform:uppercase">Prio '+prio+'</span>'+
      '<span style="font-size:13.5px;font-weight:700;color:#1a1a2e">'+title+'</span>'+(amp||'')+'</div>'+
      '<div style="font-size:12.5px;color:#374151;margin-top:4px">'+body+'</div>'+
      '<div style="font-size:11px;color:#9ca3af;margin-top:3px">Datengrundlage: '+why+'</div></div>';
  }
  function chip(t){ return '<span style="font-size:10px;color:#374151;background:#f3f4f6;border-radius:4px;padding:2px 7px">'+t+'</span>'; }

  function build(){
    var host=document.querySelector('section[data-content="actions"]');
    var g=window.GEO_SNAPSHOT;
    if(!host||!g||!g.products) return false;
    if(document.getElementById("recoDyn")) return true;
    var ci=window.CORRELATION_IMPACT||{}, lm=ci.level_model||{};
    var cards=[];

    // 1) Content-Prios aus Themen-Hotspots (Gap zum Fuehrer + eigener Zitatanteil)
    var leader=(g.totals_ranking&&g.totals_ranking[0])?g.totals_ranking[0].name:"Allianz";
    var hs=[];
    Object.keys(g.products).forEach(function(pid){
      var pd=g.products[pid];
      var br=(((pd.summary_by_llm)||{}).gemini||{}).brands||[];
      var e=null,a=null;
      br.forEach(function(b){ if(b.name==="ERGO")e=100*b.share_of_voice; if(b.name===leader)a=100*b.share_of_voice; });
      var tot=0,cE=0;
      (((pd.cited_sources)||{}).overall||[]).forEach(function(r){ var n=r.count||0; tot+=n;
        if(DOM2BRAND[(r.domain||"").replace(/^www\./,"")]==="ERGO") cE+=n; });
      if(e!=null&&a!=null) hs.push({pid:pid,n:pd.name||pid,gap:a-e,cite:tot?100*cE/tot:0});
    });
    hs.sort(function(x,y){return y.gap-x.gap;});
    hs.filter(function(h){return h.gap>3&&h.cite<8;}).slice(0,3).forEach(function(h,i){
      cards.push(card(i===0?"hoch":"mittel",
        h.n+": zitierfähige Inhalte aufbauen",
        "Rückstand zu "+leader+": <b>"+pp(h.gap).replace("+","")+"</b> bei nur <b>"+(Math.round(h.cite*10)/10).toFixed(1).replace(".",",")+" %</b> eigenem Zitatanteil. Themen-Hub/FAQ/Tabellen auf ergo.de + Präsenz in den dort zitierten Portalen ausbauen.",
        "Gemini-grounded, Snapshot "+String(g.finished_at||"").slice(0,10)+", cited_sources je Thema",
        chip("🟢 direkt beeinflussbar")));
    });

    // 2) Preis-Empfehlungen: Produkte mit ERGO deutlich ueber guenstigster Zielmarke
    var pcd=window.PRICE_COMPARISON;
    var pe=(((lm.price_footprint_joint||{}).grounded||{}).drivers_eff||{}).relprice;
    var priceSig = pe && pe.between && pe.between.prob_direction>=0.95;
    if(pcd&&pcd.products){
      var worst=[];
      Object.keys(pcd.products).forEach(function(pid){
        var b=((pcd.products[pid].profiles||{}).age_50||{}).brands||{};
        var mn=null, ep=null;
        Object.keys(b).forEach(function(k){ if(k.indexOf("_other_")===0)return; var p=b[k]&&b[k].price;
          if(p>0){ if(mn==null||p<mn)mn=p; if(k==="ergo")ep=p; } });
        if(ep!=null&&mn!=null&&mn>0&&ep/mn>=1.3) worst.push({n:(pcd.products[pid].name||pid),f:ep/mn});
      });
      worst.sort(function(x,y){return y.f-x.f;});
      if(worst.length&&priceSig){
        cards.push(card("mittel","Preisposition prüfen: "+worst.slice(0,3).map(function(w){return w.n;}).join(", "),
          "ERGO liegt hier "+worst.slice(0,3).map(function(w){return "×"+(Math.round(w.f*10)/10).toFixed(1).replace(".",",");}).join(" / ")+" über der günstigsten Zielmarke. Der Preis ist inzwischen ein gesicherter Neben-Treiber der Sichtbarkeit ("+pp(pe.between.effect_std_pp)+"/SD) — wirkt v. a. über Portal-Rankings.",
          "Preis-Vollerhebung + Joint-Modell (Preis bereinigt um Footprint, P="+String(pe.between.prob_direction).replace(".",",")+")",
          chip("🟢 direkt beeinflussbar")));
      }
    }

    // 3) Treiber-Lage / strukturelle Einordnung
    var fj=((lm.full_joint||{}).grounded||{});
    var gd=(fj.gap_decomposition||{}).ERGO;
    if(gd&&gd.contrib_pp){
      cards.push(card("info","Einordnung: Was ist NICHT beeinflussbar?",
        "Vom "+pp(gd.actual_gap_pp).replace("+","")+"-Rückstand zu "+leader+" entfallen "+pp(gd.contrib_pp.size)+" auf Größe/Marktmacht (kein Hebel). Beeinflussbar bleiben Footprint ("+pp(gd.contrib_pp.cite_share)+") und Preis ("+pp(gd.contrib_pp.relprice)+"). Achtung: Die Aufteilung zwischen Größe und Footprint ist bei dieser Fallzahl nur eine Tendenz.",
        "Voll-Zerlegung full_joint (Nightly "+String(ci.generated_at||"").slice(0,10)+")",
        chip("⚪ strukturell")));
    }

    var box=document.createElement("div");
    box.id="recoDyn"; box.className="bg-white rounded-xl p-6 shadow mb-6";
    box.innerHTML='<div style="display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:6px">'+
      '<h2 class="text-2xl font-bold text-ergo-dark" style="margin:0">Aktuelle Empfehlungen <span style="font-size:12px;font-weight:500;color:#9ca3af">(automatisch aus den Live-Daten abgeleitet)</span></h2>'+
      '<span style="font-size:11px;color:#9ca3af">aktualisiert sich mit jedem Nightly · Stand: '+String(g.finished_at||"").slice(0,10)+'</span></div>'+
      (cards.length?cards.join(""):'<div style="font-size:12px;color:#9ca3af;margin-top:8px">Keine dynamischen Empfehlungen ableitbar (Datenlage prüfen).</div>')+
      '<div style="font-size:11px;color:#9ca3af;margin-top:8px">Regeln: Content-Prio = Rückstand &gt; 3 pp UND eigener Zitatanteil &lt; 8 % · Preis-Hinweis nur, wenn der Preis-Effekt statistisch gesichert ist (P ≥ 0,95) und ERGO ≥ 30 % über der günstigsten Zielmarke liegt. Statische Langfrist-Empfehlungen weiter unten.</div>';
    host.insertBefore(box, host.firstChild);
    return true;
  }
  ready(function(){
    var tries=0; (function w(){ tries++; if(build()) return; if(tries<50) setTimeout(w,400); })();
    var tb=document.querySelector('[data-tab="actions"]');
    if(tb) tb.addEventListener("click",function(){ [300,900].forEach(function(d){ setTimeout(build,d); }); });
  });
})();
