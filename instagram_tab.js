/* ============================================================
   ERGO LLM-Cockpit — Reiter "Instagram"  (20.08.2026, Pauls Auftrag)
   ============================================================

   Auftrag (Paul, 20.08.2026): "können wir dann noch einen Reiter
   Instagram bauen und ähnlich LinkedIn alle posts tracken und den
   impact auf geo herausarbeiten" — präzisiert: "wir müssen das ohne
   den offiziellen account machen. aber ich will ja auch die
   wettbewerber mit drin haben".

   Genau daraus folgt der Weg: die offizielle Graph API zeigt nur das
   EIGENE Konto, für Wettbewerber ist sie blind. Also derselbe Weg wie
   bei LinkedIn — Google-Suche nach site:instagram.com/p je Marke über
   SerpAPI, wöchentlich (scripts/update_instagram.py).

   DREI UNTERSCHIEDE ZU LINKEDIN, alle am 20.08.2026 nachgeprüft und
   alle sichtbar im Reiter, nicht im Kleingedruckten:

   1. KEINE ENGAGEMENT-ZAHLEN. Instagram liefert öffentlich nur die
      Login-Hülle — kein og:title, kein like_count, nichts. Mit echten
      Post-URLs geprüft, mit Browser- und mit Crawler-Kennung. Bei
      LinkedIn stehen Reaktionen offen auf der Seite, hier nicht. Ein
      "0 Likes" wäre erfunden, deshalb gibt es die Spalte gar nicht.
      Was bleibt, ist Aktivität: wer postet wann worüber.

   2. DAS KONTO STEHT NICHT IMMER IM TITEL. Google liefert mal
      "ERGO Versicherung | Der langersehnte #Frühling ..." (Konto |
      Text) und mal nur den Beitragstext. Ohne erkennbares Konto
      bleibt die Spalte "—" statt geraten.

   3. MARKENNAMEN SIND MEHRDEUTIG. Die Allianz-Suche liefert das
      Stadion Allianz Parque (São Paulo) und Allianz Life (USA). Das
      mitzuzählen hieße: Allianz hat per Namensrecht mehr "Aktivität"
      als ERGO — ein systematischer Fehler im Markenvergleich, nicht
      bloß Rauschen. Der Sammler fällt deshalb je Post ein Sprach-
      Urteil; nur deutschsprachige (oder sprachlich neutrale) Posts
      lösen ein Ereignis aus. Verworfene verschwinden nicht, sie
      werden hier gezählt und sind aufklappbar.

   Wirkungs-Anbindung: je relevantem Post ein Event "instagram_post"
   in shared/events.jsonl — damit läuft Instagram durch DIESELBEN
   Rechnungen wie Presse, LinkedIn & Co. (SoV-Impact und Zitatanteil).
   Der Auszug unten ist live aus diesen Modellen, keine eigene Rechnung.

   Einbindung: wird von health_banner.js nachgeladen (wie linkedin_tab.js).
   ============================================================ */
(function () {
  "use strict";
  function ready(fn){ if(document.readyState!=="loading") fn(); else document.addEventListener("DOMContentLoaded",fn); }
  function esc(s){ return String(s==null?"":s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];}); }
  function num(v,d){ if(v==null||isNaN(v)) return "—"; d=(d==null?1:d); return Number(v).toFixed(d).replace(".",","); }
  function pp(v,d){ if(v==null||isNaN(v)) return "—"; return (v>0?"+":"")+num(v,d)+" pp"; }

  var POSTS=null, GELADEN=false, LADEFEHLER=false;
  /* Muss zu REGELSTAND in scripts/update_instagram.py passen. Traegt ein
     gespeicherter Beitrag einen anderen (oder gar keinen) Stand, wird seine
     Einordnung hier neu gerechnet - sonst behielten die 100 Beitraege des
     Erstlaufs fuer immer die Einordnung von vor der Nachkalibrierung. */
  var REGELSTAND="2026-08-20b";
  var BM={"ERGO":"#c2002f","Allianz":"#003781","AXA":"#00008f","HUK-Coburg":"#006633","Generali":"#c8102e","R+V":"#004f9f","Signal Iduna":"#003e7e","CosmosDirekt":"#f59e0b","DEVK":"#10b981","Hannoversche":"#6366f1"};

  function laden(cb){
    if(GELADEN){ cb(); return; }
    fetch("data/instagram_posts.jsonl?t="+Date.now(),{cache:"no-store"})
      .then(function(r){ return r.ok?r.text():null; })
      .catch(function(){ return null; })
      .then(function(t){
        GELADEN=true;
        if(t==null){ LADEFEHLER=true; POSTS=null; cb(); return; }
        POSTS=[];
        t.split("\n").forEach(function(l){
          l=l.trim(); if(!l) return;
          try{ var p=JSON.parse(l); if(p&&p.url) POSTS.push(p); }catch(e){}
        });
        cb();
      });
  }

  /* ---------------- Einordnung je Post (Laufzeit) ----------------
     Dieselben Regeln wie in scripts/update_instagram.py, hier noch einmal
     zur Laufzeit — damit auch Posts aus früheren Läufen eingeordnet werden,
     die die Felder noch nicht mitbringen. Steht ein Feld schon in der Datei,
     gewinnt es; gerechnet wird nur, was fehlt. */
  var SATZ_START=/^(der|die|das|den|dem|ein|eine|einen|einem|wir|ihr|ihre|du|dein|deine|mit|bei|für|jetzt|heute|hier|so|wenn|weil|am|im|unser|unsere|neu|neue|mehr|was|wie|warum|wer|wann|ob|und|oder|auch|noch|schon|nur|endlich|egal|kein|keine)\b/i;
  var MARKEN_TOKEN=["ergo","dkv","allianz","axa","huk","hukcoburg","coburg","generali","signal","iduna","signaliduna","ruv","rv","devk","hannoversche","cosmosdirekt","cosmos"];
  var GENERISCH=["versicherung","versicherungen","versicherungsag","versicherungs","group","gruppe","ag","se","deutschland","de","official","offiziell","karriere","insurance","direkt","vertrieb","leben","kranken"];
  var PARTNER=/bezirksdirektion|generalvertretung|agentur|geschäftsstelle|vertretung|versicherungsbüro|makler|hauptvertretung|beratungsstelle|finanzberatung/i;
  var DE=/\b(der|die|das|den|dem|des|und|oder|nicht|ist|sind|war|wir|ihr|ihre|ihren|du|dein|deine|dich|uns|unser|unsere|mit|bei|für|auf|aus|vom|zum|zur|im|ein|eine|einen|einem|kein|keine|schon|mehr|wie|was|wenn|weil|damit|jetzt|heute|hier|sich|auch|noch|sehr|beim|durch|gegen|ohne|über|versicherung|versicherungen|beratung|kunden|jahre|wird|wirst|haben|hat)\b/i;
  var FX=/\b(the|and|our|we|you|your|are|for|with|at|from|this|that|about|con|nuestro|nuestra|para|por|los|las|el|una|nuestros|do|dos|no|na|com|em|mais|que|sua|seu|le|les|pour|avec|della|nel|gli|il|by|of|to|all|how|what|why|get|more|best|world|now)\b/i;
  var FX_Z=/[ãõñçáíóúêôàèìò]/i;
  /* 20.08.2026 an den ersten 100 echten Beitraegen nachkalibriert - identisch
     mit scripts/update_instagram.py. Der erste Wurf sortierte 57 % als
     "Sonstiges" ein; jetzt sind es 18 %. Neu dazugekommen, weil der echte
     Bestand sie zeigte: Aktion & Rabatt, Service & App, Sponsoring. */
  var TYPEN=[
    ["Recruiting & Karriere", /\bm\/w\/d\b|karriere|\bjobs?\b|stelle\b|bewerb|ausbildung|duales studium|wir stellen ein|wir suchen|hiring|arbeitgeber|azubi|willkommen im team|neue kolleg|arbeiten bei|mein job|unser team|praktik/i],
    ["Aktion & Rabatt", /\bgratis\b|kostenlos|nachlass|rabatt|\baktion\b|gewinnspiel|sparen|bonus\w*|prämien?\s*(frei|gratis)|bis zu \d+\s*%|sonderkondition/i],
    ["Auszeichnung & Test", /testsieger|auszeichnung|\baward\b|prämiert|zertifi|siegel|ausgezeichnet|note sehr gut|\bstiftung warentest\b/i],
    ["Unternehmensnews & Zahlen", /quartal|halbjahr|geschäftsjahr|bilanz|umsatz|gewinn\b|vorstand|aufsichtsrat|ernennung|übernahme|fusion|rekord/i],
    ["Studie & Daten", /studie|umfrage|\breport\b|analyse|tacho|barometer|\bindex\b|zahlen zeigen/i],
    ["Jubiläum & Team", /\d+\s*jahre\b.{0,25}(bei|im team|dabei)|jubiläum|j-u-b-e-l|herzlichen glückwunsch|betriebsjubil/i],
    ["Event, Sport & Sponsoring", /messe|kongress|tagung|maklertreff|netzwerk|konferenz|roadshow|\bevent\b|\barena\b|sponsor|\btickets?\b|turnier|championat|meisterschaft|festival|konzert|reitsport|springreit|dressur|reiterin|wallach|stute|cruise|\bstadion\b|\bliga\b/i],
    ["Kooperation & Partner", /kooperation|partnerschaft|gemeinsam mit|zusammenarbeit|volksbank|sparkasse|partner von/i],
    ["Standort & Vertrieb", /bezirksdirektion|generalvertretung|subdirektion|geschäftsstelle|neuer standort|\bstandort\b|eröffnung|neues kapitel|umzug|neue räume/i],
    ["Nachhaltigkeit & Engagement", /nachhaltig|\bklima\b|\besg\b|spende|ehrenamt|soziales engagement|diversity|inklusion|charity/i],
    ["Service & App", /\bapp\b|kundenportal|meine versicherung|meine allianz|online[- ]service|vertragsunterlagen|versicherungsunterlagen|selfservice|\blogin\b|schaden melden/i],
    ["Saison & Gruß", /frohe (ostern|weihnachten)|frohes neues|frühling|sommerzeit|adventszeit|guten rutsch|feiertag|wünscht (ihnen|euch)|\bsommerpause\b/i],
    ["Ratgeber & Wissen", /tipps?\b|ratgeber|wusstest du|erklär|\bwarum\b|so geht|checkliste|finanzbildung|worauf (du|sie)|\bwissen\b|achten sie|darauf kommt es an|grundlagen|ist eigentlich|was tun (bei|wenn)|was ist\b|denk dran|nicht vergessen|swipe|urlaubsbereit|koffer sind gepackt/i],
    ["Produkt & Beratung", /tarif|absicherung|vorsorge|schadenfall|leistung(en)?\b|police|versichert\b|schützt|schutz\b|deckung|prämie|neue[rs]? produkt|baustein|beratung|beraten|\bbu\b|berufsunf|kasko|haftpflicht|zahnversicherung|kfz-versicherung|versicherung für|abschließen|\bschaden\b/i]
  ];
  var THEMEN=[
    ["Kfz", /\bkfz\b|\bauto\b|mobilit|e-auto|verbrenner|motorrad|führerschein/i],
    ["Gesundheit & Kranken", /krank|gesundheit|zahn|pflege|klinik|\bdkv\b/i],
    ["Leben & Vorsorge", /lebensvers|rente|vorsorge|altersvorsorge|berufsunf|hinterblieben/i],
    ["Wohnen & Sach", /hausrat|gebäude|wohn|haftpflicht|elementar|unwetter|bankschließfach/i],
    ["Recht", /rechtsschutz|\brecht\b|urteil/i],
    ["Reise", /reise|urlaub/i],
    ["Gewerbe & Firmen", /gewerbe|firmenkunden|betriebs|cyber/i]
  ];

  /* Schriftschnitt-Spielereien einebnen: Instagram-Bios stecken voller
     mathematischer Fettschrift ("𝙀𝙍𝙂𝙊 𝙑𝙚𝙧𝙨𝙞𝙘𝙝𝙚𝙧𝙪𝙣𝙜"). Ohne diese Normalisierung
     trifft keine einzige Regel, und der Beitrag faellt still in "Sonstiges". */
  function nrm(s){ try{ return String(s==null?"":s).normalize("NFKC"); }catch(e){ return String(s==null?"":s); } }

  function istKontoname(s){
    s=(s||"").trim();
    if(!(s.length>=2&&s.length<=50)) return false;
    if(s.split(/\s+/).length>5) return false;
    if(/[.!?…„“”"]/.test(s)) return false;
    if(SATZ_START.test(s)) return false;
    return true;
  }
  function teileVon(p){
    if(p.post_text!=null) return {konto:p.absender||"", text:p.post_text};
    var t=nrm(p.title).trim();
    if(!t) return {konto:"", text:""};
    var m=/^(.{2,50}?)\s+(?:on|auf)\s+Instagram\s*[:\-]/i.exec(t);
    if(m) return {konto:m[1].trim(), text:t.slice(m[0].length).replace(/^["“”]+|["“”]+$/g,"").trim()};
    var i=t.indexOf("|");
    if(i>0 && istKontoname(t.slice(0,i))) return {konto:t.slice(0,i).trim(), text:t.slice(i+1).trim()};
    return {konto:"", text:t};
  }
  function tokens(k){
    return (k||"").toLowerCase().replace(/ä/g,"ae").replace(/ö/g,"oe").replace(/ü/g,"ue").replace(/ß/g,"ss")
      .replace(/[^a-z0-9+ ]/g," ").split(/\s+/).filter(Boolean);
  }
  function absenderVon(p){
    var konto=teileVon(p).konto;
    if(p.absender_typ && p.absender!=null) return {name:p.absender||"—", typ:p.absender_typ};
    if(!konto) return {name:"—", typ:"Unbekannt"};
    if(PARTNER.test(konto)) return {name:konto, typ:"Vertriebspartner"};
    var tk=tokens(konto);
    var marke=tk.filter(function(w){ return MARKEN_TOKEN.indexOf(w)>=0; });
    if(marke.length){
      var rest=tk.filter(function(w){ return MARKEN_TOKEN.indexOf(w)<0 && GENERISCH.indexOf(w)<0; });
      return {name:konto, typ:(rest.length?"Vertriebspartner":"Unternehmensaccount")};
    }
    return {name:konto, typ:"Mitarbeitende/Sonstige"};
  }
  function textVon(p){ return [nrm(teileVon(p).text), nrm(p.snippet)].join(" "); }
  function typVon(p){
    if(p.post_typ && p.regeln===REGELSTAND) return p.post_typ;
    var t=textVon(p);
    for(var i=0;i<TYPEN.length;i++) if(TYPEN[i][1].test(t)) return TYPEN[i][0];
    return (t.trim().length<25)?"Ohne Textsignal":"Sonstiges";
  }
  function themaVon(p){
    if(p.thema && p.regeln===REGELSTAND) return p.thema;
    var t=textVon(p);
    for(var i=0;i<THEMEN.length;i++) if(THEMEN[i][1].test(t)) return THEMEN[i][0];
    return "—";
  }
  function relevantVon(p){
    if(p.relevant!=null) return !!p.relevant;
    var t=textVon(p)+" "+teileVon(p).konto;
    if(DE.test(t)) return true;
    if(FX_Z.test(t)||FX.test(t)) return false;
    return true;
  }
  function tagVon(p){ return p.date || p.first_seen || null; }
  function stichtag(d){ return new Date(Date.now()-d*86400000).toISOString().slice(0,10); }
  function relPosts(){ return (POSTS||[]).filter(relevantVon); }

  /* ---------------- Wirkungs-Auszug aus den Modellen ---------------- */
  function wirkungHTML(){
    var ci=window.CORRELATION_IMPACT||null;
    var h='<div class="bg-white rounded-xl p-5 shadow mb-6">'
      +'<h3 class="text-lg font-bold text-ergo-dark mb-1">Wirkt Instagram auf Sichtbarkeit oder Zitate?</h3>'
      +'<p class="text-xs text-gray-500 mb-3">Live-Auszug aus dem Korrelationsreiter — dieselbe cluster-robuste Rechnung wie für Presse, LinkedIn &amp; Co., kein eigenes Modell. Methodik dort (Abschnitt 2).</p>';
    if(!ci){
      h+='<div class="text-sm text-gray-400">Korrelationsdaten noch nicht geladen — der Auszug erscheint nach Reload.</div></div>';
      return h;
    }
    var sov=(ci.impact||{}).instagram_post||null;
    var zit=(((ci.zitatanteil_impact||{}).impact)||{}).instagram_post||null;
    if(!sov && !zit){
      h+='<div class="text-sm text-gray-500 bg-gray-50 border rounded-lg p-3">Noch keine Messbasis: In den bisherigen Messintervallen liegen keine erfassten Instagram-Posts — der Sammler ist neu. '
        +'Sobald einige Wochen Posts neben den Sichtbarkeits-Messungen liegen, erscheint Instagram hier automatisch mit denselben Kennzahlen wie die anderen Treiber. <b>Kein Wert ist hier keine Null</b> — es wurde schlicht noch nichts gemessen.</div></div>';
      return h;
    }
    function zeile(r, ziel){
      if(!r) return '<tr><td class="py-1.5 pr-2 text-gray-700">'+esc(ziel)+'</td><td colspan="4" class="py-1.5 text-gray-400">noch nicht schätzbar</td></tr>';
      if(r.available===false) return '<tr><td class="py-1.5 pr-2 text-gray-700">'+esc(ziel)+'</td><td colspan="4" class="py-1.5 text-gray-400">'+esc(r.grund||'nicht schätzbar')+' ('+(r.n_with_event||0)+' Ereignis-Intervalle)</td></tr>';
      var sig=r.significant===true;
      return '<tr class="border-b"><td class="py-1.5 pr-2 text-gray-700">'+esc(ziel)+'</td>'
        +'<td class="py-1.5 pr-2 text-right font-semibold">'+pp(r.effect_within_fe_pp,2)+'</td>'
        +'<td class="py-1.5 pr-2 text-right text-gray-500">'+num(r.ci95_low_cluster_pp,2)+' … '+num(r.ci95_high_cluster_pp,2)+'</td>'
        +'<td class="py-1.5 pr-2 text-right text-gray-500">'+(r.p_cluster!=null?num(r.p_cluster,4):'—')+'</td>'
        +'<td class="py-1.5 text-center"><span class="px-2 py-0.5 rounded-full text-xs font-semibold '+(sig?'bg-green-100 text-green-800':'bg-gray-100 text-gray-600')+'">'+(sig?'gesichert':'nicht gesichert')+'</span></td></tr>';
    }
    h+='<div class="overflow-x-auto"><table class="w-full text-xs"><thead><tr class="text-left text-gray-500 border-b">'
      +'<th class="py-1 pr-2">Zielgröße</th><th class="py-1 pr-2 text-right">Effekt</th><th class="py-1 pr-2 text-right">95-%-KI (cluster)</th><th class="py-1 pr-2 text-right">p</th><th class="py-1 text-center">Status</th></tr></thead><tbody>'
      +zeile(sov,'Sichtbarkeit (Share of Voice)')
      +zeile(zit,'Zitatanteil (frühere Kettenstufe)')
      +'</tbody></table></div>'
      +'<div class="text-xs text-gray-400 mt-2">Beobachtete Zusammenhänge, kein Kausalnachweis. Ohne Engagement-Zahlen misst Instagram hier reine <b>Aktivität</b> (ein Post = ein Ereignis) — nicht Reichweite.</div>'
      +'</div>';
    return h;
  }

  /* ---------------- Abschnitts-HTML ---------------- */
  function sectionHTML(){
    var h='<div class="mb-5"><h2 class="text-2xl font-bold text-ergo-dark mb-1">Instagram-Aktivität: Wer postet was — und zahlt es auf GEO ein?</h2>'
      +'<p class="text-sm text-gray-600">Öffentliche, von Google indexierte Instagram-Beiträge zu den beobachteten Marken. '
      +'Quelle: Google-Suche (site:instagram.com/p), wöchentlich aktualisiert. Ohne offiziellen Account-Zugang — nur so sind die Wettbewerber überhaupt messbar. '
      +'<b>Keine Like-/Kommentarzahlen:</b> Instagram gibt sie öffentlich nicht heraus (am 20.08.2026 an echten Post-URLs geprüft). Als Aktivitäts-Indikator lesen, nicht als Reichweite.</p></div>';

    if(LADEFEHLER || POSTS===null){
      h+='<div class="bg-blue-50 border-l-4 border-blue-500 rounded-xl p-4 text-sm text-blue-900">'
        +'<b>Der Sammler ist eingerichtet, aber noch nicht gelaufen.</b> Der erste Lauf holt rückwirkend etwa einen Monat öffentlicher Beiträge; '
        +'danach füllt sich dieser Reiter wöchentlich. Voraussetzung: das Secret <code>SERPAPI_KEY</code> im LLM-Cockpit-Repo (dasselbe wie für LinkedIn).</div>';
      h+=wirkungHTML();
      return h;
    }
    if(!POSTS.length){
      h+='<div class="bg-blue-50 border-l-4 border-blue-500 rounded-xl p-4 text-sm text-blue-900">Der Sammler lief, hat aber noch keine öffentlichen Beiträge gefunden.</div>';
      h+=wirkungHTML();
      return h;
    }

    var REL=relPosts(), weg=POSTS.length-REL.length;
    var t30=stichtag(30), t90=stichtag(90);
    var je={}, je30={}, je90={};
    REL.forEach(function(p){
      var b=p.brand||"?", d=tagVon(p)||"";
      je[b]=(je[b]||0)+1;
      if(d>=t30) je30[b]=(je30[b]||0)+1;
      if(d>=t90) je90[b]=(je90[b]||0)+1;
    });
    var marken=Object.keys(je).sort(function(a,b){ return (je30[b]||0)-(je30[a]||0) || (je[b]||0)-(je[a]||0); });
    var sum30=Object.keys(je30).reduce(function(a,b){return a+je30[b];},0);
    var top30=marken[0]||"—";
    var ergo30=je30["ERGO"]||0;

    function karte(t,v,s){ return '<div class="bg-white rounded-xl p-4 shadow"><div class="text-xs text-gray-500 font-semibold">'+t+'</div><div class="text-2xl font-bold text-ergo-dark mt-0.5">'+v+'</div>'+(s?'<div class="text-xs text-gray-400 mt-1">'+s+'</div>':'')+'</div>'; }
    h+='<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">'
      +karte('Beiträge erfasst', REL.length, weg?('+ '+weg+' verworfen (Sprache)'):'seit Beginn der Sammlung')
      +karte('Beiträge letzte 30 Tage', sum30, 'alle Marken')
      +karte('Aktivste Marke (30 T.)', esc(top30), (je30[top30]||0)+' Beiträge')
      +karte('ERGO (30 T.)', ergo30, sum30?('= '+num(100*ergo30/sum30,0)+' % der erfassten Beiträge'):'')
      +'</div>';

    if(weg){
      h+='<details class="bg-amber-50 border-l-4 border-amber-500 rounded-xl p-4 text-sm text-amber-900 mb-6">'
        +'<summary class="cursor-pointer font-semibold">'+weg+' Beiträge nicht mitgezählt — fremdsprachige Namensvettern</summary>'
        +'<p class="text-xs mt-2 mb-2">Markennamen sind mehrdeutig: Die Allianz-Suche liefert das Stadion <i>Allianz Parque</i> (São Paulo) und <i>Allianz Life</i> (USA). Würde man das mitzählen, hätte Allianz per Namensrecht mehr „Aktivität“ als ERGO — ein systematischer Fehler im Markenvergleich. Verworfen wird nur, wo ein fremdsprachiges Signal steht und <b>kein</b> deutsches; ein deutscher Beitrag mit englischem Hashtag bleibt drin.</p>'
        +'<div class="overflow-x-auto max-h-64 overflow-y-auto"><table class="w-full text-xs"><thead><tr class="text-left border-b"><th class="py-1 pr-2">Marke</th><th class="py-1 pr-2">Grund</th><th class="py-1">Beitrag</th></tr></thead><tbody>';
      POSTS.filter(function(p){ return !relevantVon(p); }).slice(0,80).forEach(function(p){
        h+='<tr class="border-b"><td class="py-1 pr-2">'+esc(p.brand||"—")+'</td><td class="py-1 pr-2">'+esc(p.relevanz_grund||"fremdsprachiges Signal")+'</td>'
          +'<td class="py-1"><a href="'+esc(p.url)+'" target="_blank" rel="noopener" class="hover:underline">'+esc((p.title||p.url).slice(0,90))+'</a></td></tr>';
      });
      h+='</tbody></table></div></details>';
    }

    // Aktivitaets-Tabelle
    h+='<div class="bg-white rounded-xl p-5 shadow mb-6"><h3 class="text-lg font-bold text-ergo-dark mb-2">Aktivität im Vergleich</h3>'
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
      +'<div class="text-xs text-gray-400 mt-2">Datierung: Erscheinungstag, wenn Google ihn liefert, sonst Fund-Tag. Große Marken sind in der Google-Indexierung tendenziell überrepräsentiert; ein Beitrag, der mehrere Marken nennt, zählt bei jeder dieser Marken.</div></div>';

    h+=wirkungHTML();

    // ---- Was wird gepostet? (ohne Engagement: Verteilung statt Ranking) ----
    var jeTyp={}, jeAbs={};
    REL.forEach(function(p){
      var t=typVon(p); (jeTyp[t]=jeTyp[t]||{n:0, ergo:0}).n++;
      if(p.brand==="ERGO") jeTyp[t].ergo++;
      var a=absenderVon(p).typ; jeAbs[a]=(jeAbs[a]||0)+1;
    });
    var typen=Object.keys(jeTyp).sort(function(a,b){ return jeTyp[b].n-jeTyp[a].n; });
    h+='<div class="bg-white rounded-xl p-5 shadow mb-6"><h3 class="text-lg font-bold text-ergo-dark mb-1">Was wird gepostet?</h3>'
      +'<p class="text-xs text-gray-500 mb-3">Einordnung aus Beitragstext und Snippet (Heuristik, kein Volltext-Verständnis — Instagram gibt den vollen Text öffentlich nicht heraus). '
      +'<b>Anders als im LinkedIn-Reiter gibt es hier keine Reaktions-Spalte</b> — welche Typen „laufen“, lässt sich auf Instagram von außen nicht messen. Was sich messen lässt: welcher Typ wie häufig gepostet wird, und ob die Wirkung auf GEO mit dem Mix zusammenhängt (Tabelle oben).</p>'
      +'<div class="overflow-x-auto"><table class="w-full text-xs"><thead><tr class="text-left text-gray-500 border-b">'
      +'<th class="py-1.5 pr-2">Post-Typ</th><th class="py-1.5 pr-2 text-right">Beiträge</th><th class="py-1.5 pr-2 text-right">Anteil</th><th class="py-1.5 pr-2 text-right">davon ERGO</th><th class="py-1.5"></th></tr></thead><tbody>';
    var maxN=Math.max.apply(null, typen.map(function(t){return jeTyp[t].n;}).concat([1]));
    typen.forEach(function(t){
      var e=jeTyp[t];
      h+='<tr class="border-b"><td class="py-1.5 pr-2 text-gray-800">'+esc(t)+'</td>'
        +'<td class="py-1.5 pr-2 text-right font-semibold">'+e.n+'</td>'
        +'<td class="py-1.5 pr-2 text-right text-gray-500">'+num(100*e.n/(REL.length||1),0)+' %</td>'
        +'<td class="py-1.5 pr-2 text-right text-gray-500">'+e.ergo+'</td>'
        +'<td class="py-1.5"><div style="height:8px;border-radius:4px;min-width:2px;width:'+Math.round(100*e.n/maxN)+'%;background:#c2002f"></div></td></tr>';
    });
    h+='</tbody></table></div>'
      +'<div class="text-xs text-gray-400 mt-2">„Ohne Textsignal“ und „Sonstiges“ heißen: Der abrufbare Text trägt kein Merkmal, an dem sich der Typ festmachen lässt — geraten wird nicht. '
      +'Absender-Mix: '+Object.keys(jeAbs).sort(function(a,b){return jeAbs[b]-jeAbs[a];}).map(function(a){ return esc(a)+' '+jeAbs[a]; }).join(' · ')+'.</div></div>';

    // ---- Event-Log ----
    h+='<div class="bg-white rounded-xl p-5 shadow mb-6"><h3 class="text-lg font-bold text-ergo-dark mb-1">📋 Event-Log — jeder erfasste Beitrag</h3>'
      +'<p class="text-xs text-gray-500 mb-3">Wann, welcher Typ, welches Thema — und verlinkt. Spaltenköpfe sind klickbar zum Sortieren. '+'<b>Zur Spalte „Von wem":</b> Google gibt den Kontonamen bei rund neun von zehn Instagram-Beiträgen nicht heraus (am 20.08.2026 an 100 echten Treffern nachgezählt: 2 von 100 tragen ihn im Snippet, 6 im Titel). '+'Dann bleibt die Spalte leer — aus dem Beitragstext auf den Absender zu schließen hat sich bei LinkedIn bereits als Fehlerquelle erwiesen und wird hier bewusst nicht gemacht.</p>'
      +'<div class="flex flex-wrap gap-2 mb-3">'
      +'<select id="igFilterMarke" class="border border-gray-300 rounded px-2 py-1 text-xs" onchange="window.__igLog&&window.__igLog()"><option value="">Alle Marken</option></select>'
      +'<select id="igFilterTyp" class="border border-gray-300 rounded px-2 py-1 text-xs" onchange="window.__igLog&&window.__igLog()"><option value="">Alle Post-Typen</option></select>'
      +'<select id="igFilterAbs" class="border border-gray-300 rounded px-2 py-1 text-xs" onchange="window.__igLog&&window.__igLog()"><option value="">Alle Absender-Typen</option></select>'
      +'<label class="text-xs text-gray-500 flex items-center gap-1"><input type="checkbox" id="igZeigeVerworfen" onchange="window.__igLog&&window.__igLog()"> verworfene mitzeigen</label>'
      +'<input type="search" id="igSuche" placeholder="Volltext durchsuchen …" class="flex-1 min-w-[180px] border border-gray-300 rounded px-3 py-1 text-xs" oninput="window.__igLog&&window.__igLog()" />'
      +'</div>'
      +'<div id="igLogInfo" class="text-xs text-gray-400 mb-1"></div>'
      +'<div id="igLogTabelle" class="overflow-x-auto max-h-[32rem] overflow-y-auto border border-gray-200 rounded-lg"></div></div>';

    return h;
  }

  /* ---------------- Event-Log ---------------- */
  var LOG_SORT={feld:"datum", ab:true};
  function logZeilen(){
    var fm=(document.getElementById("igFilterMarke")||{}).value||"";
    var ft=(document.getElementById("igFilterTyp")||{}).value||"";
    var fa=(document.getElementById("igFilterAbs")||{}).value||"";
    var mitWeg=!!(document.getElementById("igZeigeVerworfen")||{}).checked;
    var q=((document.getElementById("igSuche")||{}).value||"").toLowerCase();
    var out=[];
    (POSTS||[]).forEach(function(p){
      var rel=relevantVon(p);
      if(!rel && !mitWeg) return;
      var a=absenderVon(p), t=typVon(p), th=themaVon(p);
      if(fm&&p.brand!==fm) return;
      if(ft&&t!==ft) return;
      if(fa&&a.typ!==fa) return;
      if(q && (textVon(p)+" "+a.name+" "+(p.brand||"")).toLowerCase().indexOf(q)<0) return;
      out.push({p:p, datum:tagVon(p)||"", exakt:!!p.date, marke:p.brand||"", autor:a.name,
                absTyp:a.typ, typ:t, thema:th, rel:rel,
                text:(teileVon(p).text||p.snippet||p.title||"")});
    });
    var f=LOG_SORT.feld, ab=LOG_SORT.ab?1:-1;
    out.sort(function(x,y){
      var A=x[f], B=y[f];
      if(A==null&&B==null) return 0;
      if(A==null) return 1; if(B==null) return -1;
      return String(B).localeCompare(String(A))*ab;
    });
    return out;
  }
  function logFuellen(){
    var el=document.getElementById("igLogTabelle"); if(!el||!POSTS) return;
    [["igFilterMarke", function(p){return p.brand;}],
     ["igFilterTyp", typVon],
     ["igFilterAbs", function(p){return absenderVon(p).typ;}]].forEach(function(cfg){
      var sel=document.getElementById(cfg[0]);
      if(!sel||sel.options.length>1) return;
      var s={}; relPosts().forEach(function(p){ var v=cfg[1](p); if(v) s[v]=1; });
      Object.keys(s).sort().forEach(function(v){
        var o=document.createElement("option"); o.value=v; o.textContent=v; sel.appendChild(o);
      });
    });
    var rows=logZeilen();
    var info=document.getElementById("igLogInfo");
    if(info){ var nWeg=rows.filter(function(r){return !r.rel;}).length;
      info.textContent=(rows.length-nWeg)+" von "+relPosts().length+" gezählten Beiträgen"+(nWeg?(" + "+nWeg+" verworfene eingeblendet"):""); }
    function th(feld,label){
      var pfeil=(LOG_SORT.feld===feld)?(LOG_SORT.ab?" ▼":" ▲"):"";
      return '<th class="py-1.5 px-2 text-left cursor-pointer select-none hover:text-ergo-red" onclick="window.__igSort(\''+feld+'\')">'+label+pfeil+'</th>';
    }
    var h='<table class="w-full text-xs"><thead class="sticky top-0 bg-white"><tr class="text-gray-500 border-b">'
      +th("datum","Datum")+th("marke","Marke")+th("autor","Von wem")+th("absTyp","Absender")
      +th("typ","Post-Typ")+th("thema","Thema")
      +'<th class="py-1.5 px-2 text-left">Beitrag</th></tr></thead><tbody>';
    if(!rows.length) h+='<tr><td colspan="7" class="py-3 px-2 text-gray-400">Keine Treffer.</td></tr>';
    rows.forEach(function(r){
      h+='<tr class="border-b align-top'+(r.rel?'':' bg-amber-50 text-gray-500')+'">'
        +'<td class="py-1.5 px-2 whitespace-nowrap text-gray-500">'+esc(r.datum||"—")+(r.exakt?'':'<span title="Fund-Tag, kein Erscheinungsdatum von Google geliefert"> *</span>')+'</td>'
        +'<td class="py-1.5 px-2 whitespace-nowrap"><span style="color:'+(BM[r.marke]||"#334155")+';font-weight:600">'+esc(r.marke)+'</span></td>'
        +'<td class="py-1.5 px-2 whitespace-nowrap">'+esc(r.autor)+'</td>'
        +'<td class="py-1.5 px-2 whitespace-nowrap text-gray-500">'+esc(r.absTyp)+'</td>'
        +'<td class="py-1.5 px-2 whitespace-nowrap">'+esc(r.typ)+'</td>'
        +'<td class="py-1.5 px-2 whitespace-nowrap text-gray-500">'+esc(r.thema)+'</td>'
        +'<td class="py-1.5 px-2"><a href="'+esc(r.p.url)+'" target="_blank" rel="noopener" class="text-gray-700 hover:text-ergo-red">'+esc(r.text.slice(0,150))+(r.text.length>150?"…":"")+'</a>'
        +(r.rel?'':' <span class="text-amber-700">(verworfen: '+esc(r.p.relevanz_grund||"fremdsprachig")+')</span>')+'</td>'
        +'</tr>';
    });
    h+='</tbody></table>';
    el.innerHTML=h;
  }
  window.__igLog=logFuellen;
  window.__igSort=function(feld){
    if(LOG_SORT.feld===feld) LOG_SORT.ab=!LOG_SORT.ab; else { LOG_SORT.feld=feld; LOG_SORT.ab=true; }
    logFuellen();
  };

  /* ---------------- Reiter anlegen (Muster linkedin_tab.js) ---------------- */
  function zeigen(){
    [].slice.call(document.querySelectorAll("[data-tab]")).forEach(function(b){ b.classList.remove("tab-active"); b.classList.add("tab-inactive"); });
    var btn=document.getElementById("instagramTabBtn");
    if(btn){ btn.classList.remove("tab-inactive"); btn.classList.add("tab-active"); }
    [].slice.call(document.querySelectorAll("[data-content]")).forEach(function(s){ s.classList.add("hidden"); });
    var sec=document.getElementById("instagramSection");
    if(sec){
      sec.classList.remove("hidden");
      laden(function(){ try{ sec.innerHTML=sectionHTML(); logFuellen(); }catch(e){} });
    }
    try{ window.scrollTo({top:0,behavior:"smooth"}); }catch(e){}
  }
  function verstecken(){
    var sec=document.getElementById("instagramSection");
    if(sec) sec.classList.add("hidden");
    var btn=document.getElementById("instagramTabBtn");
    if(btn){ btn.classList.remove("tab-active"); btn.classList.add("tab-inactive"); }
  }
  function knopf(){
    if(document.getElementById("instagramTabBtn")) return true;
    var ref=document.querySelector('[data-tab="overview"]');
    if(!ref||!ref.parentNode) return false;
    var btn=document.createElement("button");
    btn.id="instagramTabBtn";
    btn.className=(ref.className||"tab-btn").replace(/tab-active/g,"tab-inactive");
    if(btn.className.indexOf("tab-btn")<0) btn.className+=" tab-btn";
    if(btn.className.indexOf("tab-inactive")<0) btn.className+=" tab-inactive";
    btn.setAttribute("data-tab","instagram");
    btn.innerHTML="📷 Instagram";
    btn.addEventListener("click",function(e){ e.preventDefault(); zeigen(); });
    // Direkt hinter den LinkedIn-Reiter — die beiden gehoeren zusammen.
    var li=document.getElementById("linkedinTabBtn");
    if(li&&li.parentNode===ref.parentNode&&li.nextSibling) ref.parentNode.insertBefore(btn,li.nextSibling);
    else if(li&&li.parentNode===ref.parentNode) ref.parentNode.appendChild(btn);
    else{
      var doku=document.getElementById("dokuTabBtn");
      if(doku&&doku.parentNode===ref.parentNode) ref.parentNode.insertBefore(btn,doku);
      else ref.parentNode.appendChild(btn);
    }
    return true;
  }
  function section(){
    if(document.getElementById("instagramSection")) return true;
    var ref=document.querySelector('section[data-content="overview"]');
    if(!ref||!ref.parentNode) return false;
    var sec=document.createElement("section");
    sec.id="instagramSection";
    sec.setAttribute("data-content","instagram");
    sec.className="tab-content hidden";
    ref.parentNode.appendChild(sec);
    return true;
  }
  function andereKnoepfe(){
    [].slice.call(document.querySelectorAll(".tab-btn")).forEach(function(b){
      if(b.id==="instagramTabBtn") return;
      if(b.getAttribute("data-ig-wired")==="1") return;
      b.setAttribute("data-ig-wired","1");
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
