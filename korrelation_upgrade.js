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

  /* 12.08.2026 korrigiert: Der alte Text setzte Peecs footprint_pct mit dem
     cite_share des eigenen Crawls gleich ("misst ihn als ... bzw. als ..."). Sie
     messen NICHT dasselbe: cite_share ist der Anteil der markeneigenen Domain an
     den zitierten Quellen, footprint_pct der zitatgewichtete Anteil der Quellen
     MIT MARKENERWAEHNUNG (deshalb summierte sich footprint_pct ueber die Marken
     auf 302 %). Diese Grafik nutzt nur noch den eigenen Crawl. */
  var FOOTDEF="Quellpräsenz = Anteil der markeneigenen Domain an den von den Sprachmodellen zitierten Quellen (eigener Crawl, Feld cite_share). Nicht zu verwechseln mit Peecs footprint_pct — das zählt Quellen mit Markenerwähnung und ist eine andere Größe.";

  /* 12.08.2026 ENTFERNT: meansOf/rankOf/topOf - die Peec-Markenmittel. Sie waren
     die Grundlage des alten Peec-Scatters und des Bias-Hinweises; beide sind weg,
     damit auch diese drei. Der Peec-Reiter rechnet seine Mittel selbst. */

  /* 12.08.2026 ENTFERNT: peecBiasWarn() - der Warnhinweis, dass Peecs Prompt-Satz
     ERGO-zentriert ist. Er hing am alten Peec-Scatter; seit dieser Block auf den
     eigenen Crawl umgestellt ist, wurde die Funktion nirgends mehr aufgerufen.
     Der Hinweis selbst geht NICHT verloren - er steht unveraendert im Peec-Reiter
     (dashboard_v3.html, ueber der Kennzahlentafel und noch einmal ueber der
     ERGO-fokussierten Ansicht), also dort, wo die Peec-Zahlen auch stehen.
     Bewusst geloescht statt "fuer spaeter" behalten: eine Funktion, die niemand
     aufruft, deren Kommentar aber behauptet, sie werde gebraucht, kostet beim
     naechsten Lesen genau die Zeit, die dieser Umbau gerade gespart hat. */

  /* ---------- Ueber-/Unterperformer-Scatter ----------
     12.08.2026 GRUNDLEGEND UMGEBAUT (Befund Paul: "das sieht falsch aus" - er hatte
     recht). Vorher lag hier Peecs footprint_pct auf der x-Achse, beschriftet als
     "Anteil der markeneigenen Domain an allen zitierten URLs". Peec rechnet unter
     diesem Feld aber etwas anderes, und zwar laut der eigenen Quellenangabe in
     peec_footprint.json: "zitatgewichteter Anteil der Quellen-URLs MIT
     MARKENERWAEHNUNG". Beweis ohne Interpretation: die 28 Markenwerte summierten
     sich auf 301,7 % - ein Anteil an einem gemeinsamen Topf kann das nicht.

     Damit stand auf der x-Achse "wie oft wird die Marke in zitierten Quellen
     erwaehnt" und auf der y-Achse "wie oft wird die Marke in Antworten erwaehnt".
     Zweimal im Kern dieselbe Groesse. Das r von 0,90 war zu einem grossen Teil
     Selbstkorrelation, und die versprochene Aussage - "sorge dafuer, dass deine
     Seiten zitiert werden" - stand nirgends in den Daten.

     Jetzt: cite_share aus dem EIGENEN Crawl (Anteil der markeneigenen Domain an
     den zitierten Quellen, grounded, ueber alle sauberen Messtage gemittelt) -
     dieselbe Groesse, aus der auch die Abstands-Zerlegung rechnet.

     Zweiter Befund, unabhaengig davon: Die Gerade hing an drei Punkten. Ueber alle
     28 Peec-Marken war die Steigung 0,618 (r=0,90); ohne Allianz, HUK und ERGO nur
     noch 0,188 (r=0,41). ERGO war einer dieser drei - die Aussage "ERGO liegt X pp
     unter der Erwartung" mass ERGO also gegen eine Linie, die ERGO mitdefiniert.
     Deshalb hier: Hebelpunkte werden ausgewiesen, eine zweite Gerade OHNE sie
     gezeichnet, und ERGOs Abweichung gegen eine Gerade gerechnet, in die ERGO
     selbst NICHT eingeht (Leave-one-out). ---------- */
  var scatterChart=null;

  /* Markenmittel aus dem eigenen Crawl. Quelle: gap_explorer.brand_means im
     Nightly - dort liegen sov und cite_share je Marke bereits gemittelt und
     engine-konsistent nebeneinander. Keine zweite Rechnung, damit diese Grafik
     und die Zerlegung nicht auseinanderlaufen koennen. */
  function crawlBrandMeans(){
    var ci=window.CORRELATION_IMPACT; if(!ci) return null;
    var sb=(((ci.price_level_pooled||{}).streubild||{}).grounded)||{};
    var bm=sb.available?sb.brand_means:null; if(!bm) return null;
    var out=[];
    Object.keys(bm).forEach(function(b){
      var v=bm[b]||{};
      if(typeof v.cite_share==="number" && typeof v.sov==="number") out.push({brand:b, foot:v.cite_share, sov:v.sov});
    });
    return out.length>=5?{pts:out, tage:sb.n_tage||null, von:sb.tage_von||null, bis:sb.tage_bis||null,
                          nCells:sb.n_cells||null, nTopics:sb.n_topics||null}:null;
  }

  function ols(pts){
    var n=pts.length; if(n<3) return null;
    var sx=0,sy=0,sxx=0,sxy=0,syy=0;
    pts.forEach(function(p){ sx+=p.foot; sy+=p.sov; sxx+=p.foot*p.foot; sxy+=p.foot*p.sov; syy+=p.sov*p.sov; });
    var den=n*sxx-sx*sx; if(Math.abs(den)<1e-9) return null;
    var b=(n*sxy-sx*sy)/den, a=(sy-b*sx)/n;
    var rden=Math.sqrt(den*(n*syy-sy*sy));
    return {slope:b, intercept:a, n:n, r:(rden>1e-9?((n*sxy-sx*sy)/rden):null),
            xbar:sx/n, sxx:sxx-sx*sx/n};
  }

  /* Hebelpunkte nach der ueblichen Faustregel h_i > 3p/n (p = 2 Parameter). */
  function hebelpunkte(pts, f){
    if(!f||f.sxx<=1e-9) return [];
    var n=pts.length, grenze=3*2/n;
    return pts.filter(function(p){
      var h=1/n+Math.pow(p.foot-f.xbar,2)/f.sxx;
      return h>grenze;
    }).map(function(p){ return p.brand; });
  }

  function scatterBlock(){
    var D=crawlBrandMeans();
    var nBr=D?D.pts.length:null;
    return '<div id="korrScatterBlock" style="border:1px solid #eee;border-radius:11px;padding:14px 16px;margin-bottom:14px">'+
      '<div style="font-size:13px;font-weight:700;margin-bottom:2px">Über-/Unterperformer — Quellpräsenz gegen Sichtbarkeit (eigener Crawl)</div>'+
      '<div style="font-size:11px;color:#9ca3af;margin-bottom:8px">Jeder Punkt = eine Marke'+(nBr?(" ("+nBr+" Marken)"):"")+', Mittel über die Themen und über alle sauberen Messtage. '+
        'Durchgezogen = Ausgleichsgerade über alle Marken. Gestrichelt = dieselbe Gerade ohne die Marken, die sie am stärksten bestimmen. Liegen beide weit auseinander, trägt der Zusammenhang nur wenige Punkte.</div>'+
      '<div style="position:relative;height:270px"><canvas id="korrScatterCv"></canvas></div>'+
      '<div style="font-size:11px;color:#6b7280;margin-top:6px" id="korrScatterNote"></div>'+
      '<div style="font-size:10.5px;color:#9ca3af;margin-top:4px">'+FOOTDEF+' Deskriptiver Zusammenhang, kein Kausalnachweis.</div>'+
    '</div>';
  }

  function renderScatter(){
    var cv=document.getElementById("korrScatterCv"), noteEl=document.getElementById("korrScatterNote");
    if(!cv) return;
    var D=crawlBrandMeans();
    if(!D){ if(noteEl) noteEl.textContent="Markenmittel aus dem eigenen Crawl (correlation_impact.json → price_level_pooled.streubild) noch nicht geladen — der Scatter erscheint nach dem nächsten Nightly bzw. Reload. Keine Ersatz-Nullen."; return; }
    var pts=D.pts;
    if(!window.Chart){ if(noteEl) noteEl.textContent="Diagrammbibliothek nicht geladen — die Zahlen stehen unverändert in den Karten oben."; return; }
    var fAll=ols(pts); if(!fAll){ if(noteEl) noteEl.textContent="Zu wenig Streuung in der Quellpräsenz für eine Ausgleichsgerade."; return; }
    var heb=hebelpunkte(pts,fAll);
    var rest=pts.filter(function(p){ return heb.indexOf(p.brand)<0; });
    var fRest=(rest.length>=3)?ols(rest):null;

    var xs=pts.map(function(p){return p.foot;});
    var xmin=Math.min.apply(null,xs), xmax=Math.max.apply(null,xs);
    var pad=(xmax-xmin)*0.08||1; xmin-=pad; xmax+=pad;
    function colOf(br){ return br==="ERGO"?"#dc0028":(br==="Allianz"?"#003781":(heb.indexOf(br)>=0?"#b45309":"#9ca3af")); }
    var ds=[
      {type:"scatter",label:"Marken",data:pts.map(function(p){return {x:p.foot,y:p.sov,brand:p.brand};}),
       pointRadius:pts.map(function(p){return (p.brand==="ERGO"||p.brand==="Allianz")?7:(heb.indexOf(p.brand)>=0?6:4);}),
       pointBackgroundColor:pts.map(function(p){return colOf(p.brand);}), pointBorderColor:"#fff", pointBorderWidth:1},
      {type:"line",label:"alle",data:[{x:xmin,y:fAll.intercept+fAll.slope*xmin},{x:xmax,y:fAll.intercept+fAll.slope*xmax}],
       borderColor:"#6b7280",borderWidth:2,pointRadius:0,fill:false}
    ];
    if(fRest) ds.push({type:"line",label:"ohne Hebelpunkte",
       data:[{x:xmin,y:fRest.intercept+fRest.slope*xmin},{x:xmax,y:fRest.intercept+fRest.slope*xmax}],
       borderColor:"#c8ccd2",borderWidth:2,borderDash:[6,4],pointRadius:0,fill:false});

    if(scatterChart){ try{scatterChart.destroy();}catch(e){} scatterChart=null; }
    try{
      scatterChart=new Chart(cv,{data:{datasets:ds},options:{responsive:true,maintainAspectRatio:false,animation:false,
        plugins:{legend:{display:false},tooltip:{callbacks:{label:function(ctx){ var r=ctx.raw||{}; if(r.brand==null) return null;
          var res=r.y-(fAll.intercept+fAll.slope*r.x);
          return r.brand+": "+num(r.y,1)+"% SoV bei "+num(r.x,1)+"% Quellpräsenz ("+(res>=0?"+":"")+num(res,1)+" pp vs. Gerade)"+(heb.indexOf(r.brand)>=0?" — Hebelpunkt":""); }}}},
        scales:{x:{title:{display:true,text:"Quellpräsenz % (eigener Crawl) — Anteil der markeneigenen Domain an den zitierten Quellen"}},
                y:{title:{display:true,text:"Share of Voice %  (grounded)"},beginAtZero:true}}}});
    }catch(e){}

    if(!noteEl) return;
    var s="";
    /* ERGOs Abweichung gegen eine Gerade OHNE ERGO - sonst misst sich ERGO an
       einer Linie, die es selbst mitzieht. */
    var ohneErgo=pts.filter(function(p){ return p.brand!=="ERGO"; });
    var fOE=(ohneErgo.length>=3)?ols(ohneErgo):null;
    var er=pts.filter(function(p){ return p.brand==="ERGO"; })[0];
    if(er&&fOE){
      var resE=er.sov-(fOE.intercept+fOE.slope*er.foot);
      s+="<b>ERGO:</b> "+(resE>=0?("+"+num(resE,1)+" pp über"):(num(resE,1)+" pp unter"))+" der Erwartung. "+
         "<span style='color:#9ca3af'>Gegen eine Gerade gerechnet, in die ERGO selbst nicht eingeht — sonst misst sich ERGO an einer Linie, die es mitzieht.</span> ";
    } else if(er){ s+="<b>ERGO:</b> keine Angabe — zu wenige andere Marken für eine Vergleichsgerade. "; }
    else { s+="ERGO ist in dieser Auswertung nicht enthalten. "; }

    s+="<div style='margin-top:5px;color:#9ca3af'>Steigung "+signed(fAll.slope,2)+" pp SoV je pp Quellpräsenz über "+fAll.n+" Marken"+
       (fAll.r!=null?(", r = "+num(fAll.r,2)):"")+". ";
    if(fRest&&heb.length){
      s+="Ohne "+heb.join(", ")+" (Hebelpunkte): "+signed(fRest.slope,2)+
         (fRest.r!=null?(", r = "+num(fRest.r,2)):"")+". ";
      var faktor=(Math.abs(fRest.slope)>1e-9)?Math.abs(fAll.slope/fRest.slope):null;
      if(faktor!=null&&faktor>1.5) s+="<b style='color:#b45309'>Die beiden Geraden unterscheiden sich um Faktor "+num(faktor,1)+" — der Zusammenhang wird von wenigen Marken getragen und ist entsprechend unsicher.</b> ";
    } else if(!heb.length){
      s+="Keine Marke überschreitet die übliche Hebelgrenze (h &gt; 3p/n) — die Gerade hängt an keinem Einzelpunkt. ";
    }
    if(D.tage) s+="Grundlage: "+D.tage+" Messtage"+((D.von&&D.bis)?(" ("+D.von+" bis "+D.bis+")"):"")+", "+(D.nTopics||"?")+" Themen. ";
    s+="ERGO rot, Allianz blau, Hebelpunkte bernstein.</div>";
    /* Der wichtigste Vorbehalt gehoert an die Grafik, nicht in eine Fussnote weiter
       unten: Zitate und Nennungen stammen zu einem Teil aus DENSELBEN Antworten.
       Ein Teil des Zusammenhangs ist deshalb Messkonstruktion, nicht Wirkung. Die
       Zahl dazu rechnet der Nightly bereits (level_model.full_joint.circularity). */
    var circ=(((((window.CORRELATION_IMPACT||{}).level_model||{}).full_joint||{}).grounded||{}).circularity)||null;
    if(circ&&circ.share_same_engine!=null){
      s+="<div style='margin-top:6px;padding:7px 10px;background:#fff8ed;border:1px solid #f0dcc0;border-left:3px solid #b45309;border-radius:7px;color:#7a4a12'>"+
         "<b>Warum dieser Zusammenhang so eng aussieht.</b> "+num(100*circ.share_same_engine,0)+" % der Zitate stammen aus derselben Engine, die hier auch die Sichtbarkeit misst. "+
         "Beide Achsen lesen damit teilweise dieselben Antworten — ein Teil der Enge ist Messkonstruktion und keine Wirkung. "+
         "Die Grafik zeigt, wo eine Marke im Vergleich zu den anderen steht, nicht wie viel Sichtbarkeit eine zusätzlich zitierte Seite bringt.</div>";
    }
    noteEl.innerHTML=s;
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
    module.exports={ scatterBlock:scatterBlock, block3Skeleton:block3Skeleton, mount:mount };
  }
})();
