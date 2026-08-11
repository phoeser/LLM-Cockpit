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

  /* ============================================================
     Hebel Quellpraesenz -> Sichtbarkeit (11.08.2026)
     Erster Anlauf nahm die Steigung aus dem Peec-Scatter (0,63 pp je pp). Beim
     Gegenlesen fiel auf: die ist auf Peecs footprint_pct gerechnet (Skala rund
     0-32 %), waehrend die Karten mit dem Zitatanteil aus cited_sources arbeiten
     (Skala rund 0-18 %). Zwei Messungen derselben Sache, aber nicht dieselbe
     Einheit - die Steigung der einen auf die Werte der anderen anzuwenden ergibt
     eine Zahl, die nach Praezision aussieht und keine ist.
     Deshalb hier auf GENAU den Daten gerechnet, die auch in den Karten stehen:
     je Thema und Marke der Zitatanteil aus cited_sources gegen den Gemini-SoV
     aus demselben Snapshot. Eine Quelle, eine Skala, deskriptive OLS.
     ============================================================ */
  window.geoCiteSlope=function(){
    var g=window.GEO_SNAPSHOT; if(!g||!g.products) return null;
    var pts=[];
    Object.keys(g.products).forEach(function(pid){
      var pd=g.products[pid];
      var br=(((pd.summary_by_llm)||{}).gemini||{}).brands||[];
      var tot=0, cnt={};
      (((pd.cited_sources)||{}).overall||[]).forEach(function(r){
        var n=r.count||0; tot+=n;
        var bn=DOM2BRAND[(r.domain||"").replace(/^www\./,"")];
        if(bn) cnt[bn]=(cnt[bn]||0)+n; });
      if(!tot) return;
      br.forEach(function(b){
        if(b.share_of_voice==null) return;
        pts.push({x:100*(cnt[b.name]||0)/tot, y:100*b.share_of_voice, brand:b.name}); });
    });
    if(pts.length<20) return null;
    var n=pts.length, sx=0,sy=0,sxx=0,sxy=0,syy=0;
    pts.forEach(function(p){ sx+=p.x; sy+=p.y; sxx+=p.x*p.x; sxy+=p.x*p.y; syy+=p.y*p.y; });
    var den=n*sxx-sx*sx; if(Math.abs(den)<1e-9) return null;
    var b=(n*sxy-sx*sy)/den;
    var rden=Math.sqrt(Math.max(den,0)*Math.max(n*syy-sy*sy,0));
    var r=rden>0?((n*sxy-sx*sy)/rden):null;
    function mittel(mk,f){ var s=pts.filter(function(p){return p.brand===mk;});
      return s.length?s.reduce(function(a,p){return a+p[f];},0)/s.length:null; }
    return {slope:b, intercept:(sy-b*sx)/n, n:n, r:r,
            ergoCite:mittel("ERGO","x"), ergoSov:mittel("ERGO","y")};
  };

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
      var tot=0,cE=0,cL=0;
      (((pd.cited_sources)||{}).overall||[]).forEach(function(r){ var n=r.count||0; tot+=n;
        var bn=DOM2BRAND[(r.domain||"").replace(/^www\./,"")];
        if(bn==="ERGO") cE+=n;
        if(bn===leader) cL+=n; });
      if(e!=null&&a!=null) hs.push({pid:pid,n:pd.name||pid,gap:a-e,
        cite:tot?100*cE/tot:0, citeLead:tot?100*cL/tot:null});
    });
    /* 11.08.2026 — zwei Aenderungen an diesem Block:
       (1) Die Kappung. Hier stand .slice(0,3), waehrend die ausgewiesene Regel
           darunter nur "Rueckstand > 3 pp UND Zitatanteil < 8 %" nannte. Danach
           qualifizieren sich sieben Themen, angezeigt wurden drei. Unsichtbar blieben
           u. a. Rechtsschutz (11,5 pp Rueckstand bei 0,0 % Zitatanteil) - das
           drittgroesste Loch im Portfolio tauchte in den Empfehlungen nicht auf.
           Eine stille Kappung liest sich wie Vollstaendigkeit. Jetzt alle.
       (2) Der erwartete Gewinn. Bisher nannte die Karte nur den Rueckstand. Die
           Steigung aus dem Scatter (+x pp SoV je pp Quellpraesenz) lag ungenutzt im
           Korrelations-Reiter. Damit wird aus "Quellpraesenz ausbauen" eine Zahl,
           an der man in sechs Monaten messen kann, ob etwas passiert ist.
           Bewusst gekappt am tatsaechlichen Rueckstand: mehr als den Abstand zum
           Marktfuehrer kann das Schliessen der Quellenluecke nicht einbringen. */
    var fsl=window.geoCiteSlope();
    var slope=(fsl&&fsl.slope>0)?fsl.slope:null;
    hs.forEach(function(h){
      h.potential=(slope!=null&&h.citeLead!=null&&h.citeLead>h.cite)
        ? Math.min(h.gap, (h.citeLead-h.cite)*slope) : null;
      h.rank=(h.potential!=null)?h.potential:h.gap;   // ohne Steigung: Rueckstand als Ersatzmass
    });
    var treffer=hs.filter(function(h){return h.gap>3&&h.cite<8;});
    treffer.sort(function(x,y){return y.rank-x.rank;});
    treffer.forEach(function(h,i){
      var pot=(h.potential!=null)
        ? " Erwarteter Gewinn, wenn ERGO dort den Zitatanteil von "+leader+" erreicht: <b>"+pp(h.potential)+"</b> Sichtbarkeit ("
          +(Math.round(h.cite*10)/10).toFixed(1).replace(".",",")+" % → "+(Math.round(h.citeLead*10)/10).toFixed(1).replace(".",",")+" %, gerechnet mit "
          +(Math.round(slope*100)/100).toFixed(2).replace(".",",")+" pp je pp Quellpräsenz)."
        : " Erwarteter Gewinn: keine Angabe — die Steigung Quellpräsenz→Sichtbarkeit ist aus dem aktuellen Peec-Export nicht ableitbar.";
      cards.push(card(i<3?"hoch":"mittel",
        h.n+": zitierfähige Inhalte aufbauen",
        "Rückstand zu "+leader+": <b>"+pp(h.gap).replace("+","")+"</b> bei nur <b>"+(Math.round(h.cite*10)/10).toFixed(1).replace(".",",")+" %</b> eigenem Zitatanteil."+pot+
        " Themen-Hub/FAQ/Tabellen auf ergo.de + Präsenz in den dort zitierten Portalen ausbauen.",
        "Gemini-grounded, Snapshot "+String(g.finished_at||"").slice(0,10)+", cited_sources je Thema"
          +(h.potential!=null?(" · Steigung aus denselben Snapshot-Daten über "+fsl.n+" Marken-Thema-Zellen"+(fsl.r!=null?(", r = "+(Math.round(fsl.r*100)/100).toFixed(2).replace(".",",")):"")+" (deskriptiv, kein Kausalnachweis)"):""),
        chip("🟢 direkt beeinflussbar")));
    });
    window.__RECO_HOTSPOTS=treffer;

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
      '<span style="font-size:11px;color:#9ca3af">aktualisiert sich mit jedem Nightly · GEO-Snapshot vom '+String(g.finished_at||"").slice(0,10)+' (Seiten-Crawl läuft wöchentlich)</span></div>'+
      (cards.length?cards.join(""):'<div style="font-size:12px;color:#9ca3af;margin-top:8px">Keine dynamischen Empfehlungen ableitbar (Datenlage prüfen).</div>')+
      '<div style="font-size:11px;color:#9ca3af;margin-top:8px">Regeln: Content-Prio = Rückstand &gt; 3 pp UND eigener Zitatanteil &lt; 8 %; <b>alle</b> Themen, die das erfüllen, stehen hier — sortiert nach erwartetem Sichtbarkeitsgewinn, nicht nach Rückstand (Prio hoch = die drei größten Gewinne). Deshalb steht das Thema mit dem größten Rückstand nicht zwingend oben: der Gewinn ist am tatsächlichen Rückstand gekappt und begrenzt durch die Quellpräsenz, die der Marktführer dort selbst hat — wo auch er wenig zitiert wird, ist über diesen Hebel weniger zu holen, der Rest des Rückstands kommt anderswoher. Der erwartete Gewinn ist eine Zerlegung aus dem Querschnitt über Marken, kein Versprechen: er sagt, wie viel Sichtbarkeit Marken mit dieser Quellpräsenz im Schnitt haben, nicht was ein Eingriff bewirkt. Preis-Hinweis nur, wenn der Preis-Effekt statistisch gesichert ist (P ≥ 0,95) und ERGO ≥ 30 % über der günstigsten Zielmarke liegt. Statische Langfrist-Empfehlungen weiter unten.</div>';
    host.insertBefore(box, host.firstChild);
    return true;
  }
  ready(function(){
    var tries=0; (function w(){ tries++; if(build()) return; if(tries<50) setTimeout(w,400); })();
    var tb=document.querySelector('[data-tab="actions"]');
    if(tb) tb.addEventListener("click",function(){ [300,900].forEach(function(d){ setTimeout(build,d); }); });
  });
})();
