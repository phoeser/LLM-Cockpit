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
            var vor=KPI[k.url];
            if(!vor || (k.checked||"")>=(vor.checked||"")){
              /* Text und Autorname sind stabil - einmal geholt, nie wieder
                 verlieren, auch wenn eine spaetere Messung sie nicht mitliefert. */
              if(vor){ if(!k.text && vor.text) k.text=vor.text;
                       if(!k.autor_name && vor.autor_name) k.autor_name=vor.autor_name; }
              KPI[k.url]=k;
            }
          }catch(e){}
        });
      }
      cb();
    });
  }
  function kpiVon(p){ return (KPI&&KPI[p.url])||null; }

  /* ---------------- Einordnung je Post (Laufzeit) ----------------
     20.08.2026, Pauls Auftrag: "Event-Log, der jeden einzelnen Post zeigt
     (wann, von wem, Thema) und verlinkt — dann kann man den Effekt besser
     quantifizieren und auf bestimmte Arten von Posts eingrenzen."

     Dieselben Regeln wie in scripts/update_linkedin.py, hier aber zur
     LAUFZEIT — damit auch die Posts aus dem Erstlauf eingeordnet werden, die
     die Felder noch nicht mitbringen. Grundlage ist der oeffentliche
     Beitragstext (kommt mit der KPI-Messung), sonst Titel und Snippet. */
  var MEDIEN=["versicherungsbote","horizont","frankfurter-allgemeine-zeitung","handelsblatt",
              "wirtschaftswoche","procontra","asscompact","versicherungswirtschaft","cash-online","fondsprofessionell"];
  var MARKEN_ACCOUNTS=["ergo-group-ag","ergo-oesterreich","ergo-versicherung","ergo-direkt","dkv",
              "allianz","allianz-deutschland","allianz-se","axa","axa-deutschland","huk-coburg",
              "generali-deutschland","generali","signal-iduna","r-v-versicherung","devk","hannoversche","cosmosdirekt"];
  var TYPEN=[
    ["Recruiting & Karriere", /\bm\/w\/d\b|karriere|jobs?\b|stelle\b|bewerb|werde\s|ausbildung|wir suchen|hiring|arbeitgeber/i],
    ["Unternehmensnews & Zahlen", /quartal|halbjahr|gesch(ae|ä)ftsjahr|financialresults|bilanz|umsatz|gewinn|vorstand|aufsichtsrat|ernennung|übernahme|fusion|rekord/i],
    ["Studie & Daten", /studie|umfrage|report\b|analyse|tacho|barometer|trendwende|index\b/i],
    ["Auszeichnung & Test", /testsieger|auszeichnung|award|prämiert|siegel|zertifi/i],
    ["Event & Netzwerk", /messe|kongress|tagung|maklertreff|netzwerk|treffen|konferenz|roadshow|event/i],
    ["Kooperation & Partner", /kooperation|partnerschaft|gemeinsam mit|zusammenarbeit|volksbank|sparkasse|partner von/i],
    ["Standort & Vertrieb", /generalvertretung|neuer standort|eröffnung|neues kapitel|geschäftsstelle/i],
    ["Nachhaltigkeit & Engagement", /nachhaltig|klima|esg|spende|ehrenamt|soziales|diversity|inklusion/i],
    ["Ratgeber & Wissen", /tipps?\b|ratgeber|wissen|erklär|warum |so geht|checkliste|finanzbildung|worauf/i],
    ["Produkt & Beratung", /tarif|absicherung|vorsorge|schadenfall|leistung(en)?\b|police|versichert\b|schützt|deckung|prämie/i]
  ];
  var THEMEN=[
    ["Kfz", /\bkfz\b|auto|mobilit|e-auto|verbrenner|motorrad/i],
    ["Gesundheit & Kranken", /krank|gesundheit|zahn|pflege|klinik|dkv/i],
    ["Leben & Vorsorge", /lebensvers|rente|vorsorge|altersvorsorge|berufsunf|hinterblieben/i],
    ["Wohnen & Sach", /hausrat|gebäude|wohn|haftpflicht|elementar|unwetter/i],
    ["Recht", /rechtsschutz|urteil/i],
    ["Reise", /reise|urlaub/i],
    ["Gewerbe & Firmen", /gewerbe|firmenkunden|betriebs|cyber/i]
  ];
  function textVon(p){
    var k=kpiVon(p);
    return [(k&&k.text)||"", p.title||"", p.snippet||""].join(" ");
  }
  function absenderVon(p){
    var k=kpiVon(p);
    var m=/\/posts\/([^_\/]+)_/.exec(p.url||"");
    var slug=m?decodeURIComponent(m[1]):"";
    var s=slug.toLowerCase();
    var name=(k&&k.autor_name)||slug.replace(/-/g," ");
    var typ="Sonstige";
    if(!slug) return {name:"—", slug:"", typ:typ};
    if(MEDIEN.some(function(w){return s.indexOf(w)>=0;})) typ="Fachmedien";
    else if(MARKEN_ACCOUNTS.indexOf(s)>=0) typ="Unternehmensaccount";
    else if(/generalvertretung|agentur|geschäftsstelle|hauptvertretung|volksbank|sparkasse|makler|bezirksdirektion/.test(s)) typ="Vertriebspartner";
    else if(/-[0-9a-z]{6,}$/.test(s)||s.indexOf("-")>=0) typ="Mitarbeitende";
    return {name:name, slug:slug, typ:typ};
  }
  function typVon(p){
    var t=textVon(p);
    for(var i=0;i<TYPEN.length;i++) if(TYPEN[i][1].test(t)) return TYPEN[i][0];
    return "Ohne klares Signal";
  }
  function themaVon(p){
    var t=textVon(p);
    for(var i=0;i<THEMEN.length;i++) if(THEMEN[i][1].test(t)) return THEMEN[i][0];
    return "—";
  }

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

    // ---- Was wirkt? Engagement je Post-Typ ----
    var jeTyp={};
    POSTS.forEach(function(p){
      var t=typVon(p), k=kpiVon(p);
      var e=(jeTyp[t]=jeTyp[t]||{n:0,mitKpi:0,rx:0});
      e.n++;
      if(k&&k.reactions!=null){ e.mitKpi++; e.rx+=k.reactions; }
    });
    var typen=Object.keys(jeTyp).sort(function(a,b){
      var A=jeTyp[a],B=jeTyp[b];
      return (B.mitKpi?B.rx/B.mitKpi:-1)-(A.mitKpi?A.rx/A.mitKpi:-1);
    });
    h+='<div class="bg-white rounded-xl p-5 shadow mb-6"><h3 class="text-lg font-bold text-ergo-dark mb-1">Welche Art von Post läuft?</h3>'
      +'<p class="text-xs text-gray-500 mb-3">Einordnung aus dem öffentlichen Beitragstext (Heuristik, kein Volltext-Verständnis). '
      +'<b>Wichtig:</b> Das ist Engagement auf LinkedIn — <u>nicht</u> Wirkung auf die LLM-Sichtbarkeit. Die steht in der Tabelle darüber und braucht mehrere Wochen Messreihe.</p>'
      +'<div class="overflow-x-auto"><table class="w-full text-xs"><thead><tr class="text-left text-gray-500 border-b">'
      +'<th class="py-1.5 pr-2">Post-Typ</th><th class="py-1.5 pr-2 text-right">Posts</th><th class="py-1.5 pr-2 text-right">gemessen</th><th class="py-1.5 pr-2 text-right">Ø Reaktionen</th><th class="py-1.5"></th></tr></thead><tbody>';
    var maxAvg=Math.max.apply(null, typen.map(function(t){ var e=jeTyp[t]; return e.mitKpi?e.rx/e.mitKpi:0; }).concat([1]));
    typen.forEach(function(t){
      var e=jeTyp[t], avg=e.mitKpi?e.rx/e.mitKpi:null;
      h+='<tr class="border-b"><td class="py-1.5 pr-2 text-gray-800">'+esc(t)+'</td>'
        +'<td class="py-1.5 pr-2 text-right">'+e.n+'</td>'
        +'<td class="py-1.5 pr-2 text-right text-gray-500">'+e.mitKpi+'</td>'
        +'<td class="py-1.5 pr-2 text-right font-semibold">'+(avg==null?'—':num(avg,1))+'</td>'
        +'<td class="py-1.5"><div style="height:8px;border-radius:4px;min-width:2px;width:'+(avg==null?0:Math.round(100*avg/maxAvg))+'%;background:#c2002f"></div></td></tr>';
    });
    h+='</tbody></table></div><div class="text-xs text-gray-400 mt-2">„Ohne klares Signal“ heißt: Der abrufbare Text trägt kein Merkmal, an dem sich der Typ festmachen lässt — geraten wird nicht.</div></div>';

    // ---- Event-Log: jeder einzelne Post ----
    h+='<div class="bg-white rounded-xl p-5 shadow mb-6"><h3 class="text-lg font-bold text-ergo-dark mb-1">📋 Event-Log — jeder erfasste Post</h3>'
      +'<p class="text-xs text-gray-500 mb-3">Wann, von wem, welcher Typ, welches Thema, wie viel Engagement — und verlinkt. '
      +'Spaltenköpfe sind klickbar zum Sortieren. Grundlage für die Frage, welche Art von Post auf die LLM-Sichtbarkeit einzahlt.</p>'
      +'<div class="flex flex-wrap gap-2 mb-3">'
      +'<select id="liFilterMarke" class="border border-gray-300 rounded px-2 py-1 text-xs" onchange="window.__liLog&&window.__liLog()"><option value="">Alle Marken</option></select>'
      +'<select id="liFilterTyp" class="border border-gray-300 rounded px-2 py-1 text-xs" onchange="window.__liLog&&window.__liLog()"><option value="">Alle Post-Typen</option></select>'
      +'<select id="liFilterAbs" class="border border-gray-300 rounded px-2 py-1 text-xs" onchange="window.__liLog&&window.__liLog()"><option value="">Alle Absender-Typen</option></select>'
      +'<input type="search" id="liSuche" placeholder="Volltext durchsuchen …" class="flex-1 min-w-[180px] border border-gray-300 rounded px-3 py-1 text-xs" oninput="window.__liLog&&window.__liLog()" />'
      +'</div>'
      +'<div id="liLogInfo" class="text-xs text-gray-400 mb-1"></div>'
      +'<div id="liLogTabelle" class="overflow-x-auto max-h-[32rem] overflow-y-auto border border-gray-200 rounded-lg"></div></div>';

    return h;
  }

  /* ---------------- Event-Log ---------------- */
  var LOG_SORT={feld:"datum", ab:true};
  function logZeilen(){
    var fm=(document.getElementById("liFilterMarke")||{}).value||"";
    var ft=(document.getElementById("liFilterTyp")||{}).value||"";
    var fa=(document.getElementById("liFilterAbs")||{}).value||"";
    var q=((document.getElementById("liSuche")||{}).value||"").toLowerCase();
    var out=[];
    (POSTS||[]).forEach(function(p){
      var a=absenderVon(p), t=typVon(p), th=themaVon(p), k=kpiVon(p);
      if(fm&&p.brand!==fm) return;
      if(ft&&t!==ft) return;
      if(fa&&a.typ!==fa) return;
      if(q && (textVon(p)+" "+a.name+" "+p.brand).toLowerCase().indexOf(q)<0) return;
      out.push({p:p, datum:tagVon(p)||"", exakt:!!p.date, marke:p.brand||"", autor:a.name,
                absTyp:a.typ, typ:t, thema:th,
                rx:(k&&k.reactions!=null)?k.reactions:null,
                cm:(k&&k.comments!=null)?k.comments:null,
                text:((k&&k.text)||p.snippet||p.title||"")});
    });
    var f=LOG_SORT.feld, ab=LOG_SORT.ab?1:-1;
    out.sort(function(x,y){
      var A=x[f], B=y[f];
      if(A==null&&B==null) return 0;
      if(A==null) return 1; if(B==null) return -1;
      if(typeof A==="number"&&typeof B==="number") return (B-A)*ab;
      return String(B).localeCompare(String(A))*ab;
    });
    return out;
  }
  function logFuellen(){
    var el=document.getElementById("liLogTabelle"); if(!el||!POSTS) return;
    // Filter-Optionen einmalig fuellen
    [["liFilterMarke", function(p){return p.brand;}],
     ["liFilterTyp", typVon],
     ["liFilterAbs", function(p){return absenderVon(p).typ;}]].forEach(function(cfg){
      var sel=document.getElementById(cfg[0]);
      if(!sel||sel.options.length>1) return;
      var s={}; POSTS.forEach(function(p){ var v=cfg[1](p); if(v) s[v]=1; });
      Object.keys(s).sort().forEach(function(v){
        var o=document.createElement("option"); o.value=v; o.textContent=v; sel.appendChild(o);
      });
    });
    var rows=logZeilen();
    var info=document.getElementById("liLogInfo");
    if(info) info.textContent=rows.length+" von "+POSTS.length+" Posts";
    function th(feld,label,rechts){
      var pfeil=(LOG_SORT.feld===feld)?(LOG_SORT.ab?" ▼":" ▲"):"";
      return '<th class="py-1.5 px-2 '+(rechts?'text-right':'text-left')+' cursor-pointer select-none hover:text-ergo-red" onclick="window.__liSort(\''+feld+'\')">'+label+pfeil+'</th>';
    }
    var h='<table class="w-full text-xs"><thead class="sticky top-0 bg-white"><tr class="text-gray-500 border-b">'
      +th("datum","Datum")+th("marke","Marke")+th("autor","Von wem")+th("absTyp","Absender")
      +th("typ","Post-Typ")+th("thema","Thema")+th("rx","👍",true)+th("cm","💬",true)
      +'<th class="py-1.5 px-2 text-left">Beitrag</th></tr></thead><tbody>';
    if(!rows.length) h+='<tr><td colspan="9" class="py-3 px-2 text-gray-400">Keine Treffer.</td></tr>';
    rows.forEach(function(r){
      h+='<tr class="border-b align-top">'
        +'<td class="py-1.5 px-2 whitespace-nowrap text-gray-500">'+esc(r.datum||"—")+(r.exakt?'':'<span title="Fund-Tag, kein Erscheinungsdatum von Google geliefert"> *</span>')+'</td>'
        +'<td class="py-1.5 px-2 whitespace-nowrap"><span style="color:'+(BM[r.marke]||"#334155")+';font-weight:600">'+esc(r.marke)+'</span></td>'
        +'<td class="py-1.5 px-2 whitespace-nowrap">'+esc(r.autor)+'</td>'
        +'<td class="py-1.5 px-2 whitespace-nowrap text-gray-500">'+esc(r.absTyp)+'</td>'
        +'<td class="py-1.5 px-2 whitespace-nowrap">'+esc(r.typ)+'</td>'
        +'<td class="py-1.5 px-2 whitespace-nowrap text-gray-500">'+esc(r.thema)+'</td>'
        +'<td class="py-1.5 px-2 text-right'+(r.rx!=null?' font-semibold':' text-gray-400')+'">'+(r.rx!=null?r.rx:"—")+'</td>'
        +'<td class="py-1.5 px-2 text-right text-gray-500">'+(r.cm!=null?r.cm:"—")+'</td>'
        +'<td class="py-1.5 px-2"><a href="'+esc(r.p.url)+'" target="_blank" rel="noopener" class="text-gray-700 hover:text-ergo-red">'+esc(r.text.slice(0,150))+(r.text.length>150?"…":"")+'</a></td>'
        +'</tr>';
    });
    h+='</tbody></table>';
    el.innerHTML=h;
  }
  window.__liLog=logFuellen;
  window.__liSort=function(feld){
    if(LOG_SORT.feld===feld) LOG_SORT.ab=!LOG_SORT.ab; else { LOG_SORT.feld=feld; LOG_SORT.ab=true; }
    logFuellen();
  };
  window.__liArchiv=logFuellen;

  /* ---------------- Reiter anlegen (Muster soho_tab.js) ---------------- */
  function zeigen(){
    [].slice.call(document.querySelectorAll("[data-tab]")).forEach(function(b){ b.classList.remove("tab-active"); b.classList.add("tab-inactive"); });
    var btn=document.getElementById("linkedinTabBtn");
    if(btn){ btn.classList.remove("tab-inactive"); btn.classList.add("tab-active"); }
    [].slice.call(document.querySelectorAll("[data-content]")).forEach(function(s){ s.classList.add("hidden"); });
    var sec=document.getElementById("linkedinSection");
    if(sec){
      sec.classList.remove("hidden");
      laden(function(){ try{ sec.innerHTML=sectionHTML(); logFuellen(); }catch(e){} });
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
