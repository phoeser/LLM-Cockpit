/* ============================================================
   ERGO LLM-Cockpit — Reiter "LinkedIn"  (18.08.2026, Pauls Auftrag)
   ============================================================

   Was dieser Reiter zeigt
   -----------------------
   Oeffentliche LinkedIn-Posts mit Bezug zu ERGO oder einem der
   Wettbewerber — gesammelt NICHT durch Crawlen von LinkedIn (das
   verbieten deren Nutzungsbedingungen, und die Bot-Abwehr macht es
   ohnehin unzuverlaessig), sondern ueber die Google-Suche nach
   site:linkedin.com/posts je Marke (SerpAPI, woechentlich montags,
   scripts/update_linkedin.py). Abgestimmt mit Paul am 18.08.2026.

   Ehrlichkeits-Regeln (Projektstandard):
   - Erfasst ist, was OEFFENTLICH und von Google INDEXIERT ist — die
     reichweitenstarken Posts, nicht jeder Beitrag. Keine Like-Zahlen.
     Diese Untererfassung steht sichtbar im Reiter.
   - Jede Zahl kommt zur Laufzeit aus data/linkedin_posts.jsonl bzw.
     data/correlation_impact.json. Nichts ist fest eingetragen.
   - Solange der Sammler noch nie lief, SAGT der Reiter das, statt
     leer auszusehen wie ein kaputter.

   Wirkungs-Anbindung: der Sammler emittiert je Post ein Event
   "linkedin_post" in shared/events.jsonl. Damit laeuft LinkedIn
   automatisch durch DIESELBEN Rechnungen wie Presse & Co. — Wirkung
   auf die Sichtbarkeit (SoV-Impact) und auf den Zitatanteil
   (zitatanteil_impact). Die beiden Zeilen unten sind Live-Auszuege
   aus diesen Modellen, keine eigene Rechnung.

   Einbindung: wird von health_banner.js nachgeladen (wie soho_tab.js),
   damit die grosse Vorlage nicht angefasst werden muss.
   ============================================================ */
(function () {
  "use strict";
  function ready(fn){ if(document.readyState!=="loading") fn(); else document.addEventListener("DOMContentLoaded",fn); }
  function esc(s){ return String(s==null?"":s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];}); }
  function num(v,d){ if(v==null||isNaN(v)) return "—"; d=(d==null?1:d); return Number(v).toFixed(d).replace(".",","); }
  function pp(v,d){ if(v==null||isNaN(v)) return "—"; return (v>0?"+":"")+num(v,d)+" pp"; }

  var POSTS=null, GELADEN=false, LADEFEHLER=false;
  /* 18.08.2026: Performance-KPIs (Pauls Nachschaerfung "braeuchten noch
     Performance KPIs"). update_linkedin_kpis.py ruft woechentlich die
     OEFFENTLICHE Reaktions-/Kommentarzahl jeder Post-Seite ab (mehr gibt
     LinkedIn von aussen nicht her - Impressionen/Reichweite kennt nur der
     Seiten-Admin). Je Post zaehlt hier der JUENGSTE Messpunkt mit status=ok. */
  var KPI=null; // url -> {reactions, comments, checked}
  var BM={"ERGO":"#c2002f","Allianz":"#003781","AXA":"#00008f","HUK-Coburg":"#006633","Generali":"#c8102e","R+V":"#004f9f","Signal Iduna":"#003e7e","CosmosDirekt":"#f59e0b","DEVK":"#10b981","Hannoversche":"#6366f1"};

  function laden(cb){
    if(GELADEN){ cb(); return; }
    Promise.all([
      fetch("data/linkedin_posts.jsonl?t="+Date.now(),{cache:"no-store"}).then(function(r){ return r.ok?r.text():null; }).catch(function(){ return null; }),
      fetch("data/linkedin_kpis.jsonl?t="+Date.now(),{cache:"no-store"}).then(function(r){ return r.ok?r.text():null; }).catch(function(){ return null; })
    ]).then(function(res){
      GELADEN=true;
      var t=res[0];
      if(t==null){ LADEFEHLER=true; POSTS=null; cb(); return; }
      POSTS=[];
      t.split("\n").forEach(function(l){
        l=l.trim(); if(!l) return;
        try{ var p=JSON.parse(l); if(p&&p.url) POSTS.push(p); }catch(e){}
      });
      if(res[1]!=null){
        KPI={};
        res[1].split("\n").forEach(function(l){
          l=l.trim(); if(!l) return;
          try{
            var k=JSON.parse(l);
            if(!k||!k.url||k.status!=="ok") return;
            var alt=KPI[k.url];
            if(!alt || (k.checked||"")>=(alt.checked||"")) KPI[k.url]=k;
          }catch(e){}
        });
      }
      cb();
    });
  }
  function kpiVon(p){ return (KPI&&KPI[p.url])||null; }

  function tagVon(p){ return p.date || p.first_seen || null; }

  function stichtag(tageZurueck){
    var d=new Date(Date.now()-tageZurueck*86400000);
    return d.toISOString().slice(0,10);
  }

  /* ---------------- Wirkungs-Auszug aus den Modellen ---------------- */
  function wirkungHTML(){
    var ci=window.CORRELATION_IMPACT||null;
    var h='<div class="bg-white rounded-xl p-5 shadow mb-6">'
      +'<h3 class="text-lg font-bold text-ergo-dark mb-1">Wirkt LinkedIn auf Sichtbarkeit oder Zitate?</h3>'
      +'<p class="text-xs text-gray-500 mb-3">Live-Auszug aus dem Korrelationsreiter — dieselbe cluster-robuste Rechnung wie fuer Presse &amp; Co., kein eigenes Modell. Details und Methodik dort (Abschnitt 2).</p>';
    if(!ci){
      h+='<div class="text-sm text-gray-400">Korrelationsdaten noch nicht geladen — der Auszug erscheint nach Reload.</div></div>';
      return h;
    }
    var sov=(ci.impact||{}).linkedin_post||null;
    var zit=(((ci.zitatanteil_impact||{}).impact)||{}).linkedin_post||null;
    if(!sov && !zit){
      h+='<div class="text-sm text-gray-500 bg-gray-50 border rounded-lg p-3">Noch keine Messbasis: In den bisherigen Messintervallen liegen keine erfassten LinkedIn-Posts — der Sammler ist neu. '
        +'Sobald einige Wochen Posts neben den Sichtbarkeits-Messungen liegen, erscheint LinkedIn hier automatisch mit denselben Kennzahlen wie die anderen Treiber (Effekt, Konfidenzintervall, cluster-robustes p). <b>Kein Wert ist hier keine Null</b> — es wurde schlicht noch nichts gemessen.</div></div>';
      return h;
    }
    function zeile(r, ziel, effKey){
      if(!r) return '<tr><td class="py-1.5 pr-2 text-gray-700">'+esc(ziel)+'</td><td colspan="4" class="py-1.5 text-gray-400">noch nicht schaetzbar</td></tr>';
      if(r.available===false) return '<tr><td class="py-1.5 pr-2 text-gray-700">'+esc(ziel)+'</td><td colspan="4" class="py-1.5 text-gray-400">'+esc(r.grund||'nicht schaetzbar')+' ('+(r.n_with_event||0)+' Ereignis-Intervalle)</td></tr>';
      var eff=r[effKey], lo=r.ci95_low_cluster_pp, hi=r.ci95_high_cluster_pp;
      var sig=r.significant===true;
      return '<tr class="border-b"><td class="py-1.5 pr-2 text-gray-700">'+esc(ziel)+'</td>'
        +'<td class="py-1.5 pr-2 text-right font-semibold">'+pp(eff,2)+'</td>'
        +'<td class="py-1.5 pr-2 text-right text-gray-500">'+num(lo,2)+' … '+num(hi,2)+'</td>'
        +'<td class="py-1.5 pr-2 text-right text-gray-500">'+(r.p_cluster!=null?num(r.p_cluster,4):'—')+'</td>'
        +'<td class="py-1.5 text-center"><span class="px-2 py-0.5 rounded-full text-xs font-semibold '+(sig?'bg-green-100 text-green-800':'bg-gray-100 text-gray-600')+'">'+(sig?'gesichert':'nicht gesichert')+'</span></td></tr>';
    }
    h+='<div class="overflow-x-auto"><table class="w-full text-xs"><thead><tr class="text-left text-gray-500 border-b">'
      +'<th class="py-1 pr-2">Zielgroesse</th><th class="py-1 pr-2 text-right">Effekt</th><th class="py-1 pr-2 text-right">95-%-KI (cluster)</th><th class="py-1 pr-2 text-right">p</th><th class="py-1 text-center">Status</th></tr></thead><tbody>'
      /* 18.08.2026 (Opus-Review #14): Within-FE auch fuer die SoV-Zeile -
         das Cluster-KI daneben liegt um beta_fe, nicht um die Gruppendifferenz. */
      +zeile(sov,'Sichtbarkeit (Share of Voice)','effect_within_fe_pp')
      +zeile(zit,'Zitatanteil (fruehere Kettenstufe)','effect_within_fe_pp')
      +'</tbody></table></div>'
      +'<div class="text-xs text-gray-400 mt-2">Beobachtete Zusammenhaenge, kein Kausalnachweis. Bei wenigen Ereignis-Wochen sind breite Intervalle normal — die Zeilen werden mit jedem Wochenlauf schaerfer.</div>'
      +'</div>';
    return h;
  }

  /* ---------------- Abschnitts-HTML ---------------- */
  function sectionHTML(){
    var h='<div class="mb-5"><h2 class="text-2xl font-bold text-ergo-dark mb-1">LinkedIn-Aktivitaet: Wer ist mit welchen Inhalten praesent?</h2>'
      +'<p class="text-sm text-gray-600">Oeffentliche, von Google indexierte LinkedIn-Posts mit Bezug zu den beobachteten Marken. '
      +'Quelle: Google-Suche (site:linkedin.com/posts), woechentlich montags aktualisiert. '
      +'<b>Untererfassung bekannt:</b> nur oeffentliche, indexierte Posts, keine Like-/Kommentarzahlen — als Aktivitaets-Indikator lesen, nicht als Vollzaehlung.</p></div>';

    if(LADEFEHLER || POSTS===null){
      h+='<div class="bg-blue-50 border-l-4 border-blue-500 rounded-xl p-4 text-sm text-blue-900">'
        +'<b>Der Sammler ist eingerichtet, aber noch nicht gelaufen.</b> Der erste Lauf holt rueckwirkend etwa einen Monat oeffentlicher Posts; '
        +'danach fuellt sich dieser Reiter jeden Montag. Voraussetzung: das Secret <code>SERPAPI_KEY</code> ist im LLM-Cockpit-Repo hinterlegt.</div>';
      h+=wirkungHTML();
      return h;
    }
    if(!POSTS.length){
      h+='<div class="bg-blue-50 border-l-4 border-blue-500 rounded-xl p-4 text-sm text-blue-900">Der Sammler lief, hat aber noch keine oeffentlichen Posts gefunden. Naechster Lauf: Montag.</div>';
      h+=wirkungHTML();
      return h;
    }

    var t30=stichtag(30), t90=stichtag(90);
    var je={}, je30={}, je90={};
    POSTS.forEach(function(p){
      var b=p.brand||"?", d=tagVon(p)||"";
      je[b]=(je[b]||0)+1;
      if(d>=t30) je30[b]=(je30[b]||0)+1;
      if(d>=t90) je90[b]=(je90[b]||0)+1;
    });
    var marken=Object.keys(je).sort(function(a,b){ return (je30[b]||0)-(je30[a]||0) || (je[b]||0)-(je[a]||0); });
    var sum30=Object.values(je30).reduce(function(a,b){return a+b;},0);
    var top30=marken[0]||"—";
    var ergo30=je30["ERGO"]||0;

    function karte(t,v,s){ return '<div class="bg-white rounded-xl p-4 shadow"><div class="text-xs text-gray-500 font-semibold">'+t+'</div><div class="text-2xl font-bold text-ergo-dark mt-0.5">'+v+'</div>'+(s?'<div class="text-xs text-gray-400 mt-1">'+s+'</div>':'')+'</div>'; }
    h+='<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">'
      +karte('Posts erfasst (gesamt)', POSTS.length, 'seit Beginn der Sammlung')
      +karte('Posts letzte 30 Tage', sum30, 'alle Marken')
      +karte('Aktivste Marke (30 T.)', esc(top30), (je30[top30]||0)+' Posts')
      +karte('ERGO (30 T.)', ergo30, sum30?('= '+num(100*ergo30/sum30,0)+' % der erfassten Posts'):'')
      +'</div>';

    // Aktivitaets-Tabelle
    h+='<div class="bg-white rounded-xl p-5 shadow mb-6"><h3 class="text-lg font-bold text-ergo-dark mb-2">Aktivitaet im Vergleich</h3>'
      +'<div class="overflow-x-auto"><table class="w-full text-xs"><thead><tr class="text-left text-gray-500 border-b">'
      +'<th class="py-1.5 pr-2">Marke</th><th class="py-1.5 pr-2 text-right">30 Tage</th><th class="py-1.5 pr-2 text-right">90 Tage</th><th class="py-1.5 pr-2 text-right">gesamt</th><th class="py-1.5"></th></tr></thead><tbody>';
    var max30=Math.max.apply(null, marken.map(function(b){return je30[b]||0;}).concat([1]));
    marken.forEach(function(b){
      var w=Math.round(100*(je30[b]||0)/max30);
      h+='<tr class="border-b'+(b==="ERGO"?' font-semibold':'')+'"><td class="py-1.5 pr-2" style="color:'+(BM[b]||'#334155')+'">'+esc(b)+'</td>'
        +'<td class="py-1.5 pr-2 text-right">'+(je30[b]||0)+'</td>'
        +'<td class="py-1.5 pr-2 text-right">'+(je90[b]||0)+'</td>'
        +'<td class="py-1.5 pr-2 text-right text-gray-500">'+(je[b]||0)+'</td>'
        +'<td class="py-1.5"><div style="height:8px;border-radius:4px;width:'+w+'%;min-width:2px;background:'+(BM[b]||'#94a3b8')+'"></div></td></tr>';
    });
    h+='</tbody></table></div>'
      +'<div class="text-xs text-gray-400 mt-2">Datierung: Erscheinungstag, wenn Google ihn liefert, sonst Fund-Tag — grosse Marken mit vielen Followern sind in der Google-Indexierung tendenziell ueberrepraesentiert. Ein Post, der mehrere Marken nennt, zaehlt bei jeder dieser Marken (seit 18.08. — davor bekam die zuerst abgefragte Marke ihn exklusiv).</div></div>';

    // Engagement je Marke (aus den oeffentlichen Reaktions-/Kommentarzahlen)
    if(KPI && Object.keys(KPI).length){
      var eg={};
      POSTS.forEach(function(p){
        var k=kpiVon(p); if(!k||k.reactions==null) return;
        var e=(eg[p.brand]=eg[p.brand]||{n:0,rx:0,cm:0,nCm:0,top:null});
        e.n++; e.rx+=k.reactions;
        /* 18.08.2026 (Opus-Review #7): Kommentare nur zaehlen, wenn gemessen. */
        if(k.comments!=null){ e.cm+=k.comments; e.nCm++; }
        if(!e.top||k.reactions>e.top.rx) e.top={rx:k.reactions,titel:p.title||p.url,url:p.url};
      });
      var egMarken=Object.keys(eg).sort(function(a,b){ return (eg[b].rx/eg[b].n)-(eg[a].rx/eg[a].n); });
      var nGemessen=Object.keys(KPI).length;
      h+='<div class="bg-white rounded-xl p-5 shadow mb-6"><h3 class="text-lg font-bold text-ergo-dark mb-1">Engagement im Vergleich</h3>'
        +'<p class="text-xs text-gray-500 mb-2">Öffentliche Reaktions- und Kommentarzahlen der Post-Seiten, wöchentlich nachgemessen ('+nGemessen+' von '+POSTS.length+' Posts erfasst). '
        +'Das ist <b>Engagement, nicht Reichweite</b> — Impressionen kennt nur der Seiten-Admin.</p>'
        +'<div class="overflow-x-auto"><table class="w-full text-xs"><thead><tr class="text-left text-gray-500 border-b">'
        +'<th class="py-1.5 pr-2">Marke</th><th class="py-1.5 pr-2 text-right">Posts gemessen</th><th class="py-1.5 pr-2 text-right">Ø Reaktionen/Post</th><th class="py-1.5 pr-2 text-right">Reaktionen gesamt</th><th class="py-1.5 pr-2 text-right">Kommentare</th><th class="py-1.5">Top-Post</th></tr></thead><tbody>';
      egMarken.forEach(function(b){
        var e=eg[b];
        h+='<tr class="border-b'+(b==="ERGO"?' font-semibold':'')+'"><td class="py-1.5 pr-2" style="color:'+(BM[b]||'#334155')+'">'+esc(b)+'</td>'
          +'<td class="py-1.5 pr-2 text-right">'+e.n+'</td>'
          +'<td class="py-1.5 pr-2 text-right">'+num(e.rx/e.n,1)+'</td>'
          +'<td class="py-1.5 pr-2 text-right">'+e.rx+'</td>'
          +'<td class="py-1.5 pr-2 text-right">'+(e.nCm?(e.cm+(e.nCm<e.n?(' <span class="text-gray-400">('+e.nCm+' von '+e.n+' gemessen)</span>'):'')):'—')+'</td>'
          +'<td class="py-1.5 text-gray-500"><a href="'+esc(e.top.url)+'" target="_blank" rel="noopener" class="hover:text-ergo-red">'+esc((e.top.titel||'').slice(0,60))+'</a> <span class="text-gray-400">('+e.top.rx+')</span></td></tr>';
      });
      h+='</tbody></table></div>'
        +'<div class="text-xs text-gray-400 mt-2">Ø über die gemessenen Posts der Marke — Posts unter der Messgrenze (Authwall/Fehler) zählen nicht als 0, sie fehlen. Engagement wächst in den ersten Wochen; junge Posts sind darum systematisch niedriger.</div></div>';
    } else {
      h+='<div class="bg-white rounded-xl p-5 shadow mb-6"><h3 class="text-lg font-bold text-ergo-dark mb-1">Engagement im Vergleich</h3>'
        +'<div class="text-sm text-gray-400">Die erste KPI-Messung (Reaktionen/Kommentare je Post) läuft mit dem nächsten Wochenlauf — danach steht hier der Marken-Vergleich.</div></div>';
    }

    h+=wirkungHTML();

    // Neueste Posts + Archiv
    var sortiert=POSTS.slice().sort(function(a,b){ return (tagVon(b)||"").localeCompare(tagVon(a)||""); });
    h+='<div class="bg-white rounded-xl p-5 shadow mb-6"><h3 class="text-lg font-bold text-ergo-dark mb-2">Neueste Posts</h3>';
    sortiert.slice(0,15).forEach(function(p){
      h+='<div class="border-b py-2"><div class="flex items-center gap-2 flex-wrap">'
        +'<span class="px-2 py-0.5 rounded-full text-xs font-semibold text-white" style="background:'+(BM[p.brand]||'#94a3b8')+'">'+esc(p.brand)+'</span>'
        +'<span class="text-xs text-gray-400">'+esc(tagVon(p)||'ohne Datum')+(p.date?'':' (Fund-Tag)')+'</span></div>'
        +'<a href="'+esc(p.url)+'" target="_blank" rel="noopener" class="text-sm font-medium text-ergo-dark hover:text-ergo-red">'+esc(p.title||p.url)+'</a>'
        +(function(){ var k=kpiVon(p); return k&&k.reactions!=null?(' <span class="text-xs text-gray-500 whitespace-nowrap">👍 '+k.reactions+(k.comments!=null?(' · 💬 '+k.comments):'')+'</span>'):''; })()
        +(p.snippet?('<div class="text-xs text-gray-500 mt-0.5">'+esc(p.snippet)+'</div>'):'')
        +'</div>';
    });
    h+='</div>';

    h+='<div class="bg-white rounded-xl p-5 shadow mb-6"><h3 class="text-lg font-bold text-ergo-dark mb-2">Archiv ('+POSTS.length+' Posts)</h3>'
      +'<input type="search" id="liSuche" placeholder="Posts durchsuchen (Titel, Marke, Text) …" class="w-full border border-gray-300 rounded px-3 py-1.5 text-sm mb-3" oninput="window.__liArchiv&&window.__liArchiv()" />'
      +'<div id="liArchivListe" class="max-h-96 overflow-y-auto border border-gray-200 rounded-lg"></div></div>';

    return h;
  }

  function archivFuellen(){
    var el=document.getElementById("liArchivListe"); if(!el||!POSTS) return;
    var q=((document.getElementById("liSuche")||{}).value||"").toLowerCase();
    var rows=POSTS.slice().sort(function(a,b){ return (tagVon(b)||"").localeCompare(tagVon(a)||""); })
      .filter(function(p){ return !q || ((p.title||"")+" "+(p.brand||"")+" "+(p.snippet||"")).toLowerCase().indexOf(q)>=0; });
    el.innerHTML = rows.slice(0,300).map(function(p){
      return '<div class="border-b px-3 py-1.5 text-xs"><span class="text-gray-400">'+esc(tagVon(p)||'—')+'</span> · '
        +'<span style="color:'+(BM[p.brand]||'#334155')+';font-weight:600">'+esc(p.brand)+'</span> · '
        +'<a href="'+esc(p.url)+'" target="_blank" rel="noopener" class="text-gray-700 hover:text-ergo-red">'+esc(p.title||p.url)+'</a></div>';
    }).join("") || '<div class="px-3 py-3 text-xs text-gray-400">Keine Treffer.</div>';
  }
  window.__liArchiv=archivFuellen;

  /* ---------------- Reiter anlegen (Muster soho_tab.js) ---------------- */
  function zeigen(){
    [].slice.call(document.querySelectorAll("[data-tab]")).forEach(function(b){ b.classList.remove("tab-active"); b.classList.add("tab-inactive"); });
    var btn=document.getElementById("linkedinTabBtn");
    if(btn){ btn.classList.remove("tab-inactive"); btn.classList.add("tab-active"); }
    [].slice.call(document.querySelectorAll("[data-content]")).forEach(function(s){ s.classList.add("hidden"); });
    var sec=document.getElementById("linkedinSection");
    if(sec){
      sec.classList.remove("hidden");
      laden(function(){ try{ sec.innerHTML=sectionHTML(); archivFuellen(); }catch(e){} });
    }
    try{ window.scrollTo({top:0,behavior:"smooth"}); }catch(e){}
  }
  function verstecken(){
    var sec=document.getElementById("linkedinSection");
    if(sec) sec.classList.add("hidden");
    var btn=document.getElementById("linkedinTabBtn");
    if(btn){ btn.classList.remove("tab-active"); btn.classList.add("tab-inactive"); }
  }
  function knopf(){
    if(document.getElementById("linkedinTabBtn")) return true;
    var ref=document.querySelector('[data-tab="overview"]');
    if(!ref||!ref.parentNode) return false;
    var btn=document.createElement("button");
    btn.id="linkedinTabBtn";
    btn.className=(ref.className||"tab-btn").replace(/tab-active/g,"tab-inactive");
    if(btn.className.indexOf("tab-btn")<0) btn.className+=" tab-btn";
    if(btn.className.indexOf("tab-inactive")<0) btn.className+=" tab-inactive";
    btn.setAttribute("data-tab","linkedin");
    btn.innerHTML="💼 LinkedIn";
    btn.addEventListener("click",function(e){ e.preventDefault(); zeigen(); });
    // Hinter den Presse-Reiter, wenn es ihn gibt — thematisch verwandt.
    var presse=document.querySelector('[data-tab="press"]');
    if(presse&&presse.parentNode===ref.parentNode&&presse.nextSibling) ref.parentNode.insertBefore(btn,presse.nextSibling);
    else{
      var doku=document.getElementById("dokuTabBtn");
      if(doku&&doku.parentNode===ref.parentNode) ref.parentNode.insertBefore(btn,doku);
      else ref.parentNode.appendChild(btn);
    }
    return true;
  }
  function section(){
    if(document.getElementById("linkedinSection")) return true;
    var ref=document.querySelector('section[data-content="overview"]');
    if(!ref||!ref.parentNode) return false;
    var sec=document.createElement("section");
    sec.id="linkedinSection";
    sec.setAttribute("data-content","linkedin");
    sec.className="tab-content hidden";
    ref.parentNode.appendChild(sec);
    return true;
  }
  function andereKnoepfe(){
    [].slice.call(document.querySelectorAll(".tab-btn")).forEach(function(b){
      if(b.id==="linkedinTabBtn") return;
      if(b.getAttribute("data-li-wired")==="1") return;
      b.setAttribute("data-li-wired","1");
      b.addEventListener("click",function(){ verstecken(); });
    });
  }
  ready(function(){
    var versuche=0;
    (function warten(){
      versuche++;
      var a=knopf(), b=section();
      if(a) andereKnoepfe();
      if(!(a&&b)&&versuche<40) setTimeout(warten,250);
      else if(a&&b) andereKnoepfe();
    })();
  });
})();
