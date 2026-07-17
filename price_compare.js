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
  // nur Wettbewerber aus DIESEM Projekt (geo-visibility config.competitors) + ERGO
  var ALLOWED = ["ergo","allianz","axa","generali","signal-iduna","cosmosdirekt","huk","huk-coburg"];

  var data = null, profile = "age_50";

  function getData(){
    // Basis: Crawler-Daten; dazu die manuelle Preis-Vollerhebung (14.07.2026) mergen.
    // Merge-Regel je Produkt: die Quelle mit MEHR Marken gewinnt.
    var base = window.PRICE_COMPARISON ? Promise.resolve(window.PRICE_COMPARISON)
      : fetch("data/price_comparison.json?t="+Date.now(),{cache:"no-store"})
          .then(function(r){return r.ok?r.json():null;}).catch(function(){return null;});
    var man = fetch("data/price_manual.json?t="+Date.now(),{cache:"no-store"})
          .then(function(r){return r.ok?r.json():null;}).catch(function(){return null;});
    function nBrands(prod){
      var b=((prod.profiles||{}).age_50||{}).brands||{};
      return Object.keys(b).filter(function(k){return k.indexOf("_other_")!==0;}).length;
    }
    return Promise.all([base,man]).then(function(res){
      var a=res[0], b=res[1];
      if(!b) return a;
      if(!a) return b;
      a.products=a.products||{};
      Object.keys(b.products||{}).forEach(function(pid){
        var mp=b.products[pid], cp=a.products[pid];
        if(!cp || nBrands(mp)>nBrands(cp)){
          mp.params=(mp.params||"")+" · Quelle: manuelle Erhebung "+(b.as_of||"");
          a.products[pid]=mp;
        }
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
    if(!prod || !prod.profiles || !prod.profiles[profile]){
      wrap.innerHTML='<h3 style="font-size:16px;font-weight:600;margin:0">'+pname+'</h3>'+
        '<p style="font-size:12px;color:#9ca3af;margin:8px 0 0">Noch keine Check24-Preisdaten. '+coveredProductsNote()+'</p>';
      return wrap;
    }
    var brands = prod.profiles[profile].brands || {};
    // nur getrackte Heatmap-Marken (kein "_other_")
    var rows=[];
    Object.keys(brands).forEach(function(k){
      if(k.indexOf("_other_")===0) return;
      if(ALLOWED.indexOf(k)<0) return;
      var nm = BRAND_NAME[k]; if(!nm) return;
      var b=brands[k];
      rows.push({key:k, name:nm, b:b, price: (b.price==null?Infinity:b.price)});
    });
    rows.sort(function(x,y){ return x.price - y.price; });

    var params = prod.params ? ('<div style="font-size:11px;color:#9ca3af;margin:2px 0 10px">'+prod.params+'</div>') : '';
    var allianz = rows.filter(function(r){return r.key==="allianz";})[0];
    var rest = rows.filter(function(r){return r.key!=="allianz";});

    function rowHtml(r, isBench){
      var isErgo = r.key==="ergo";
      var bg = isErgo?"#fff1f3":(isBench?"#f3f6fb":"#fff");
      var badge = isErgo?'<span style="font-size:9px;font-weight:700;color:#dc0028;background:#fde7ec;border-radius:4px;padding:1px 5px;margin-left:6px">ERGO</span>'
                 : (isBench?'<span style="font-size:9px;font-weight:700;color:#2a78d6;background:#e7f0fb;border-radius:4px;padding:1px 5px;margin-left:6px">Marktführer</span>':'');
      return '<tr style="border-top:1px solid #f0f0f0;background:'+bg+'">'+
        '<td style="padding:7px 8px;font-weight:'+(isErgo||isBench?"700":"500")+'">'+r.name+badge+'</td>'+
        '<td style="padding:7px 8px;font-weight:700;white-space:nowrap">'+eur(r.b.price)+'</td>'+
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
        '<tbody>'+body+'</tbody></table></div>';
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
