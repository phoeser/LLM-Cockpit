/* ============================================================
   ERGO LLM-Cockpit — Preisvergleich (neuer Aufbau)
   - Referenzkunde 50 Jahre (Profil-Umschalter 30/50/65)
   - nur die Marken aus dem Content-/Heatmap-Vergleich (getrackte
     Versicherer; Check24-"_other_" werden ausgeblendet)
   - Allianz als Benchmark separiert/hervorgehoben, ERGO rot
   - Check24-Tarifnote + 1-2 Kernmerkmale je Tarif, nach Preis sortiert
   - die 6 Sichtbarkeits-Produkte (fehlende: Hinweis)
   Quelle: data/price_comparison.json. Einbindung:
   <script src="price_compare.js"></script>.
   ============================================================ */
(function () {
  "use strict";
  function ready(fn){ if(document.readyState!=="loading") fn(); else document.addEventListener("DOMContentLoaded",fn); }

  // Reihenfolge/Namen der Heatmap-Marken (getrackter Wettbewerber-Set)
  var BRAND_NAME = {
    "allianz":"Allianz","ergo":"ERGO","axa":"AXA","huk":"HUK-Coburg","huk-coburg":"HUK-Coburg",
    "generali":"Generali","signal-iduna":"Signal Iduna","cosmosdirekt":"CosmosDirekt",
    "ruv":"R+V","devk":"DEVK","hannoversche":"Hannoversche"
  };
  // alle Produkte aus den LLM-Sichtbarkeits-Prompts (geo-visibility config, Reihenfolge + Anzeigename)
  var SICHT = [
    ["zahnzusatz","Zahnzusatzversicherung"],
    ["sterbegeld","Sterbegeldversicherung"],
    ["risikoleben","Risikolebensversicherung"],
    ["berufsunfaehigkeit","Berufsunfähigkeitsversicherung"],
    ["reise","Reiseversicherung"],
    ["rechtsschutz","Rechtsschutzversicherung"],
    ["haftpflicht","Privathaftpflichtversicherung"],
    ["hausrat","Hausratversicherung"],
    ["kfz","Kfz-Versicherung"],
    ["unfall","Unfallversicherung"],
    ["krankenhauszusatz","Krankenhauszusatzversicherung"]
  ];
  /* Getrackte Marken. 10.08.2026 ergaenzt: R+V, DEVK und Hannoversche standen zwar
     in BRAND_NAME, fehlten aber in ALLOWED - ihre Preise wurden also erhoben und
     dann beim Rendern stillschweigend verworfen. Nachgezaehlt waren das 16 Zellen
     (R+V 8, DEVK 4, Hannoversche 4). R+V steckte dabei unter ZWEI Schreibweisen in
     den Daten ("ruv" im Crawl, "r-v" in der manuellen Erhebung) - ohne die
     Alias-Normalisierung unten waere die Haelfte weiterhin unsichtbar geblieben. */
  var ALIAS = { "r-v":"ruv", "r+v":"ruv", "rv":"ruv", "huk-coburg":"huk",
                "hannoversche-leben":"hannoversche", "signal":"signal-iduna" };
  function normMarke(k){ return ALIAS[String(k).toLowerCase()] || String(k).toLowerCase(); }
  var ALLOWED = ["ergo","allianz","axa","generali","signal-iduna","cosmosdirekt","huk",
                 "ruv","devk","hannoversche"];

  /* Warum eine Marke in einer Zelle fehlen kann. Fehlt hier ein Eintrag, steht
     "nicht erhoben" - das ist die ehrliche Vorgabe: eine Luecke ohne Grund sieht
     aus wie ein Datenfehler, und genau so wurde sie bisher gelesen. */
  var OHNE_PREIS_GRUND = {
    "huk": "nicht auf Vergleichsportalen gelistet — die HUK-Coburg ist 2021 bei Verivox ausgestiegen und vertreibt direkt; über Portal-Crawling nicht erreichbar",
    "generali": "in den meisten Vergleichsrechnern nicht gelistet",
    "devk": "in den meisten Vergleichsrechnern nicht gelistet",
    "hannoversche": "nur in einzelnen Sparten gelistet",
    "ruv": "nur in einzelnen Sparten gelistet"
  };

  /* Altersunabhaengige Produkte (10.08.2026).
     Bei Haftpflicht, Hausrat und Rechtsschutz haengt die Praemie nicht vom Alter
     ab - die monatliche Erhebung erfasst sie deshalb bewusst nur bei age_50 (so
     steht es in scheduled_tasks/monatliche-preiserhebung-check24). Das ist
     richtig: dreimal dasselbe zu erheben braucht dreimal so lange und bringt
     nichts.
     Falsch war nur, was das Dashboard daraus machte - in den Profilen 30 und 65
     stand "noch keine Preisdaten", als haette man vergessen zu messen. Jetzt wird
     der age_50-Wert dort gezeigt und ausdruecklich als altersunabhaengig
     gekennzeichnet. */
  var ALTERSUNABHAENGIG = { haftpflicht:1, hausrat:1, rechtsschutz:1 };

  var data = null, profile = "age_50";

  function getData(){
    // Basis: Crawler-Daten; dazu die manuelle Preis-Vollerhebung (14.07.2026) mergen.
    // Merge-Regel je Produkt: die Quelle mit MEHR Marken gewinnt.
    var base = window.PRICE_COMPARISON ? Promise.resolve(window.PRICE_COMPARISON)
      : fetch("data/price_comparison.json?t="+Date.now(),{cache:"no-store"})
          .then(function(r){return r.ok?r.json():null;}).catch(function(){return null;});
    var man = fetch("data/price_manual.json?t="+Date.now(),{cache:"no-store"})
          .then(function(r){return r.ok?r.json():null;}).catch(function(){return null;});
    /* MERGE JE PROFIL — umgebaut 10.08.2026.
       Vorher: "die Quelle mit mehr Marken gewinnt", gezaehlt wurden aber NUR die
       Marken im Profil age_50, und ersetzt wurde das GANZE Produkt mit allen
       Profilen. Die manuelle Erhebung hat bei sechs von zehn Produkten ueberhaupt
       nur age_50 - dadurch verschwanden bei Haftpflicht, Hausrat und Rechtsschutz
       die vom Crawler erhobenen 30er- und 65er-Werte vollstaendig aus dem
       Dashboard. Rund zehn bereits erhobene Preispunkte, die niemand sah.
       Jetzt: je Profil entscheiden, und innerhalb des Profils die Marken beider
       Quellen VEREINIGEN statt eine zu verwerfen. Bei derselben Marke in beiden
       Quellen gewinnt der frischere Stand; steht der nicht fest, die Quelle mit
       mehr Detail (Note, Tarif, Leistung). Je Profil wird mitgefuehrt, woher die
       Werte stammen - das steht als Fussnote unter der Tabelle. */
    function echteMarken(obj){
      return Object.keys(obj||{}).filter(function(k){return k.indexOf("_other_")!==0;});
    }
    function detailTiefe(v){
      var n=0; ["grade","grade_label","tariff","leistung","waiting_period","customer_score"].forEach(function(f){ if(v&&v[f]!=null&&v[f]!=="") n++; });
      return n;
    }
    return Promise.all([base,man]).then(function(res){
      var a=res[0], b=res[1];
      if(!b) return a;
      if(!a) return b;
      a.products=a.products||{};
      var aStand=a.as_of||"", bStand=b.as_of||"";
      var manFrischer = (bStand && aStand) ? (bStand>aStand) : false;
      Object.keys(b.products||{}).forEach(function(pid){
        var mp=b.products[pid];
        var cp=a.products[pid];
        if(!cp){ // Produkt kennt der Crawler gar nicht
          mp._quellen={};
          Object.keys(mp.profiles||{}).forEach(function(prof){ mp._quellen[prof]="manuell"; });
          a.products[pid]=mp;
          return;
        }
        cp.profiles=cp.profiles||{};
        cp._quellen=cp._quellen||{};
        Object.keys(mp.profiles||{}).forEach(function(prof){
          var mpr=mp.profiles[prof]||{}, cpr=cp.profiles[prof];
          if(!cpr){                                   // Profil nur manuell vorhanden
            cp.profiles[prof]=mpr; cp._quellen[prof]="manuell"; return;
          }
          var cb=cpr.brands||{}, mb=mpr.brands||{};
          var ausManuell=0, ausCrawl=echteMarken(cb).length;
          Object.keys(mb).forEach(function(marke){
            if(!(marke in cb)){ cb[marke]=mb[marke]; if(marke.indexOf("_other_")!==0) ausManuell++; return; }
            // Marke in beiden: frischerer Stand gewinnt, sonst der detailreichere
            var nimmManuell = manFrischer ? true : (detailTiefe(mb[marke])>detailTiefe(cb[marke]));
            if(nimmManuell) cb[marke]=mb[marke];
          });
          cpr.brands=cb;
          cp._quellen[prof] = ausManuell
            ? ("gemischt: "+ausCrawl+" aus dem Crawl, "+ausManuell+" ergänzt aus der manuellen Erhebung "+(bStand||"o. D."))
            : "Crawl";
        });
        // Produktbeschreibung nur ergaenzen, nicht ersetzen
        if(mp.params && (cp.params||"").indexOf(mp.params)<0 && !cp.params){ cp.params=mp.params; }
      });
      return a;
    });
  }
  function eur(v){ return (v==null||isNaN(v))?"—":(Math.round(v*100)/100).toFixed(2).replace(".",",")+" €"; }

  function grade(b){
    if(b.grade==null && !b.grade_label) return '<span style="color:#9ca3af">–</span>';
    var g = b.grade==null ? "" : (typeof b.grade==="number" ? String(b.grade).replace(".",",") : b.grade);
    var lab = b.grade_label ? (' · '+b.grade_label) : "";
    return '<b>'+g+'</b>'+lab;
  }

  // 1-2 Kernmerkmale je Produkt
  function merkmale(pid, b){
    var out=[];
    if(b.waiting_period) out.push("Wartezeit "+b.waiting_period);
    if(b.tariff) out.push(b.tariff);
    if(pid==="zahnzusatz" && b.leistung){
      // "Zahnersatz / gut / 75 % / Zahnbehandlung / exzellent / 100 % / ..."
      var parts=String(b.leistung).split(" / ");
      var picks=[];
      for(var i=0;i+2<parts.length && picks.length<2;i+=3){
        picks.push(parts[i]+" "+parts[i+2]);
      }
      out = picks.length?picks:out;
    }
    if(!out.length) return '<span style="color:#9ca3af">–</span>';
    return out.slice(0,2).join(" · ");
  }

  // 17.07.2026: Frueher stand hier der hartkodierte Satz "Der Preis-Crawl deckt aktuell
  // Zahnzusatz, Sterbegeld und Risikoleben ab." Er war falsch (der Crawl deckt sieben
  // Produkte) und erschien als Erklaerung unter JEDEM leeren Produkt. Jetzt aus den
  // Daten abgeleitet - damit kann er nicht wieder veralten.
  // Muss auf das AKTUELL gewaehlte Profil filtern. Sonst listet der Satz Produkte, die
  // auf der eigenen Card darueber gerade "noch keine Preisdaten" melden - er stand dann
  // z.B. auf der Sterbegeld-Card und nannte Sterbegeld als abgedeckt.
  // "Preisdaten" statt "Preis-Crawl": ein Teil stammt aus der manuellen Vollerhebung
  // (price_manual.json), nicht aus dem Check24-Crawl.
  function coveredProductsNote(){
    var ps = (data.products||{});
    var names = [];
    Object.keys(ps).forEach(function(k){
      var prof = ((ps[k]||{}).profiles || {})[profile];
      if(!prof) return;
      var bs = prof.brands || {};
      var any = Object.keys(bs).some(function(b){
        return b.indexOf("_other_")!==0 && ALLOWED.indexOf(b)>=0;
      });
      if(any){
        var hit = null;
        for(var i=0;i<SICHT.length;i++){ if(SICHT[i][0]===k){ hit=SICHT[i][1]; break; } }
        names.push(hit || k);
      }
    });
    if(!names.length) return "Für dieses Altersprofil liegen derzeit keine Preisdaten vor.";
    if(names.length===1) return "Preisdaten liegen in diesem Profil nur für "+names[0]+" vor.";
    return "Preisdaten liegen in diesem Profil für "+names.slice(0,-1).join(", ")+" und "+names[names.length-1]+" vor.";
  }

  function productCard(pid, pname){
    var prod = (data.products||{})[pid];
    var wrap = document.createElement("div");
    wrap.className="bg-white rounded-xl shadow p-6 mb-6";
    // Altersunabhaengiges Produkt: age_50 stellvertretend fuer alle Stufen
    var altersUnab = false;
    /* Bedingung bewusst NICHT "nur wenn das Profil fehlt": der Crawler legt fuer
       diese Produkte auch bei 30 und 65 duenne Profile an (Haftpflicht age_30 = 0
       Marken, age_65 = 1, waehrend age_50 auf 42 kommt). Eine fast leere Tabelle
       ist irrefuehrender als gar keine. Ist der Preis altersunabhaengig, gilt der
       age_50-Stand fuer jede Stufe - also wird er auch ueberall gezeigt. */
    if(prod && prod.profiles && ALTERSUNABHAENGIG[pid] && profile !== "age_50" && prod.profiles.age_50){
      prod = Object.assign({}, prod);
      var pp = {}; Object.keys(prod.profiles).forEach(function(k){ pp[k]=prod.profiles[k]; });
      pp[profile] = prod.profiles.age_50;
      prod.profiles = pp;
      altersUnab = true;
    }
    if(!prod || !prod.profiles || !prod.profiles[profile]){
      wrap.innerHTML='<h3 style="font-size:16px;font-weight:600;margin:0">'+pname+'</h3>'+
        '<p style="font-size:12px;color:#9ca3af;margin:8px 0 0">Noch keine Check24-Preisdaten. '+coveredProductsNote()+'</p>';
      return wrap;
    }
    var brands = prod.profiles[profile].brands || {};
    // nur getrackte Heatmap-Marken (kein "_other_")
    var rows=[];
    var gesehen = {};
    Object.keys(brands).forEach(function(k){
      if(k.indexOf("_other_")===0) return;
      var nk = normMarke(k);
      if(ALLOWED.indexOf(nk)<0) return;
      var nm = BRAND_NAME[nk] || BRAND_NAME[k]; if(!nm) return;
      var b=brands[k];
      if(gesehen[nk]){                       // dieselbe Marke unter zwei Schreibweisen
        if(b.price!=null && (gesehen[nk].b.price==null || b.price<gesehen[nk].b.price)) gesehen[nk].b=b;
        return;
      }
      var zeile={key:nk, name:nm, b:b, price: (b.price==null?Infinity:b.price)};
      gesehen[nk]=zeile; rows.push(zeile);
    });
    rows.forEach(function(r){ r.price = (r.b.price==null?Infinity:r.b.price); });
    rows.sort(function(x,y){ return x.price - y.price; });

    var params = prod.params ? ('<div style="font-size:11px;color:#9ca3af;margin:2px 0 10px">'+prod.params+'</div>') : '';
    if(altersUnab){
      params += '<div style="font-size:11px;color:#2563eb;background:#eff6ff;border:1px solid #bfdbfe;border-radius:6px;padding:6px 9px;margin:0 0 10px">'
        + '<b>Altersunabhängiges Produkt.</b> Die Prämie hängt hier nicht vom Alter ab — gezeigt wird der bei 50 Jahren erhobene Wert. '
        + 'Er wird bewusst nur einmal erhoben; dreimal dasselbe zu messen bräuchte dreimal so lange und ergäbe dieselbe Zahl.</div>';
    }
    var allianz = rows.filter(function(r){return r.key==="allianz";})[0];
    var rest = rows.filter(function(r){return r.key!=="allianz";});

    function rowHtml(r, isBench){
      var isErgo = r.key==="ergo";
      var bg = isErgo?"#fff1f3":(isBench?"#f3f6fb":"#fff");
      var badge = isErgo?'<span style="font-size:9px;font-weight:700;color:#dc0028;background:#fde7ec;border-radius:4px;padding:1px 5px;margin-left:6px">ERGO</span>'
                 : (isBench?'<span style="font-size:9px;font-weight:700;color:#2a78d6;background:#e7f0fb;border-radius:4px;padding:1px 5px;margin-left:6px">Marktführer</span>':'');
      /* 10.08.2026: Fortgeschriebene Werte kennzeichnen. update_prices.py behaelt
         seit heute den Vorstand, wenn ein Lauf eine Zelle nicht liefert - das
         verhindert die Fluktuation, die das Preissignal ueberdeckt hat. Damit ein
         acht Wochen alter Wert aber nicht wie der heutige Preis aussieht, steht
         sein Stand daneben. */
      var alt = '';
      if(r.b._fortgeschrieben && r.b._stand){
        var tage = Math.floor((Date.now() - Date.parse(r.b._stand)) / 86400000);
        if(!isNaN(tage) && tage > 0){
          alt = '<span title="Dieser Wert stammt aus einem früheren Lauf — der aktuelle Crawl hat die Zelle nicht geliefert. Er wird fortgeschrieben, statt die Zeile leer zu lassen."'
              + ' style="font-size:9px;color:'+(tage>28?'#b45309':'#9ca3af')+';margin-left:6px;white-space:nowrap">Stand '
              + r.b._stand + ' (' + tage + ' T.)</span>';
        }
      }
      return '<tr style="border-top:1px solid #f0f0f0;background:'+bg+'">'+
        '<td style="padding:7px 8px;font-weight:'+(isErgo||isBench?"700":"500")+'">'+r.name+badge+'</td>'+
        '<td style="padding:7px 8px;font-weight:700;white-space:nowrap">'+eur(r.b.price)+alt+'</td>'+
        '<td style="padding:7px 8px;white-space:nowrap">'+grade(r.b)+'</td>'+
        '<td style="padding:7px 8px;color:#4b5563">'+merkmale(pid, r.b)+'</td></tr>';
    }

    var body='';
    if(allianz){ body += rowHtml(allianz, true); }
    rest.forEach(function(r){ body += rowHtml(r, false); });

    wrap.innerHTML =
      '<h3 style="font-size:16px;font-weight:600;margin:0">'+pname+' <span style="font-size:12px;font-weight:500;color:#6b7280">— Referenzkunde '+
        (data.profiles.filter(function(p){return p.key===profile;})[0]||{label:"50 Jahre"}).label+'</span></h3>'+
      params+
      '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12.5px">'+
        '<thead><tr style="text-align:left;color:#6b7280;font-size:11px">'+
          '<th style="padding:6px 8px">Anbieter</th><th style="padding:6px 8px">Preis / Monat</th>'+
          '<th style="padding:6px 8px">Check24-Tarifnote</th><th style="padding:6px 8px">Kernmerkmale</th></tr></thead>'+
        '<tbody>'+body+'</tbody></table></div>'+
      (function(){
        /* 10.08.2026: Fehlende Marken bekommen einen Grund statt einer Leerstelle.
           Vorher endete die Tabelle einfach - wer ERGO, Allianz und AXA sah, hielt
           das fuer den Markt, obwohl sieben getrackte Marken fehlten. */
        var da={}; rows.forEach(function(r){ da[r.key]=1; });
        var offen = ALLOWED.filter(function(k){ return !da[k] && BRAND_NAME[k]; });
        if(!offen.length) return '';
        var mitGrund=[], ohneGrund=[];
        offen.forEach(function(k){
          if(OHNE_PREIS_GRUND[k]) mitGrund.push(BRAND_NAME[k]+' ('+OHNE_PREIS_GRUND[k]+')');
          else ohneGrund.push(BRAND_NAME[k]);
        });
        var t='<div style="font-size:11px;color:#9ca3af;margin-top:8px;line-height:1.55"><b>Ohne Preis in dieser Zelle:</b> ';
        var teile=[];
        if(ohneGrund.length) teile.push(ohneGrund.join(', ')+' — in diesem Profil nicht erhoben');
        mitGrund.forEach(function(x){ teile.push(x); });
        return t+teile.join(' · ')+'. Eine fehlende Zeile heißt <b>nicht</b> „kein Angebot" und schon gar nicht „Preis null".</div>';
      })()+
      (function(){
        var q=(prod._quellen||{})[profile];
        return q ? ('<div style="font-size:11px;color:#cbd5e1;margin-top:4px">Quelle dieser Zelle: '+q+'</div>') : '';
      })();
    return wrap;
  }

  function render(host){
    // Container (idempotent)
    var box = document.getElementById("priceCompareBox");
    if(!box){
      box=document.createElement("div"); box.id="priceCompareBox";
      host.insertBefore(box, host.firstChild);
    }
    box.innerHTML="";
    // Kopf + Profil-Umschalter
    var head=document.createElement("div");
    head.className="bg-white rounded-xl shadow p-6 mb-6";
    var profs=(data.profiles||[{key:"age_50",label:"50 Jahre"}]);
    head.innerHTML=
      '<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px">'+
        '<div><h3 style="font-size:17px;font-weight:700;margin:0">Preisvergleich (Check24)</h3>'+
        '<p style="font-size:12px;color:#6b7280;margin:2px 0 0">Günstigster vergleichbarer Tarif je Anbieter, nur die Wettbewerber aus dem Sichtbarkeits-Vergleich. Allianz als Benchmark hervorgehoben, ERGO rot. Stand: '+(data.as_of||"—")+'.</p></div>'+
        '<div id="priceProf" style="display:flex;gap:6px">'+
          profs.map(function(p){var on=p.key===profile;return '<button data-p="'+p.key+'" class="pcp" style="font-size:11px;padding:4px 10px;border-radius:8px;border:1px solid '+(on?"#dc0028":"#ccc")+';background:'+(on?"#dc0028":"#fff")+';color:'+(on?"#fff":"#282d37")+';cursor:pointer">'+p.label+'</button>';}).join('')+
        '</div>'+
      '</div>';
    box.appendChild(head);
    SICHT.forEach(function(pp){ box.appendChild(productCard(pp[0], pp[1])); });

    box.querySelectorAll(".pcp").forEach(function(btn){
      btn.addEventListener("click",function(){ profile=btn.getAttribute("data-p"); render(host); });
    });

    // alte Inhalte der Sektion ausblenden (nur unser Box bleibt)
    [].slice.call(host.children).forEach(function(el){ if(el.id!=="priceCompareBox") el.style.display="none"; });
  }

  function build(){
    var host=document.querySelector('section[data-content="preisvergleich"]');
    if(!host) return false;
    if(!data) return false;
    render(host);
    return true;
  }

  ready(function(){
    getData().then(function(d){
      data=d;
      var tries=0;
      (function wait(){ tries++; if(build()) return; if(tries<40) setTimeout(wait,300); })();
      var tb=document.querySelector('[data-tab="preisvergleich"]');
      if(tb) tb.addEventListener("click",function(){ [150,600,1400].forEach(function(x){ setTimeout(build,x); }); });
    });
  });
})();
