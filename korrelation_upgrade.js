/* ============================================================
   ERGO LLM-Cockpit — Korrelations-Reiter: Zwei-Ebenen-Synthese
   (klarer/grafischer; Detail-Sektionen eingeklappt)
   Quelle: window.CORRELATION_IMPACT (level_model, multivariate, validation).
   Additiv, verändert bestehende Sektionen nicht (blendet nur ein).
   ============================================================ */
(function () {
  "use strict";
  function ready(fn){ if(document.readyState!=="loading") fn(); else document.addEventListener("DOMContentLoaded",fn); }
  function num(v,d){ return (v==null||isNaN(v))?"—":(Math.round(v*Math.pow(10,d))/Math.pow(10,d)).toFixed(d); }
  function signed(v,d){ return (v>0?"+":"")+num(v,d); }
  function clamp(v,a,b){ return Math.max(a,Math.min(b,v)); }

  var mode="g";
  function seg(lm){ return mode==="g"?lm.grounded:(mode==="u"?lm.ungrounded:lm.combined); }
  function modeLbl(){ return mode==="g"?"grounded (Web-Suche)":(mode==="u"?"ungrounded (ChatGPT)":"kombiniert (alle LLMs)"); }
  function evChip(kind){
    if(kind===3) return '<span style="font-size:10px;font-weight:700;color:#067d3a;background:#e6f5ec;border-radius:4px;padding:2px 7px">kausal belegt</span>';
    if(kind===1) return '<span style="font-size:10px;font-weight:700;color:#8a6d00;background:#fdf3d7;border-radius:4px;padding:2px 7px">konsistente Assoziation · explorativ</span>';
    return '<span style="font-size:10px;font-weight:700;color:#6b7280;background:#eef0f2;border-radius:4px;padding:2px 7px">nicht nachweisbar</span>';
  }
  function hbar(wPct,col,h){ return '<div style="flex:1;background:#eef0f2;border-radius:6px;height:'+(h||14)+'px;overflow:hidden"><div style="width:'+clamp(wPct,2,100)+'%;height:100%;background:'+col+';border-radius:6px"></div></div>'; }

  // ---- Wirkungs-Grafik: zwei Hebel auf einen Blick ----
  function leverGraphic(C){
    var lm=C.level_model||{}; var m=seg(lm)||{};
    var r=(m.raw_pearson_r!=null)?m.raw_pearson_r:0;         // Footprint-Stärke
    var mv=C.multivariate||{}; var coefs=mv.coefficients||{};
    var nSig=Object.keys(coefs).filter(function(k){return coefs[k].significant;}).length;
    var eventsW = nSig>0 ? 30 : 5;                            // Events: praktisch null
    function row(lbl,w,col,verdict){
      return '<div style="display:grid;grid-template-columns:200px 1fr 190px;align-items:center;gap:10px;margin:6px 0">'+
        '<div style="font-size:12.5px;font-weight:600">'+lbl+'</div>'+ hbar(w,col,16) +
        '<div style="font-size:11.5px;color:#4b5563">'+verdict+'</div></div>';
    }
    return '<div style="border:1px solid #eee;border-radius:10px;padding:14px 16px;margin-bottom:14px">'+
      '<div style="font-size:12px;color:#6b7280;margin-bottom:4px">Zwei Hebel — was bewegt die Sichtbarkeit?</div>'+
      row('Quellpräsenz (eigene Zitate)', r*100, '#dc0028', '<b>stärkster Zusammenhang</b> (r '+num(r,2)+')')+
      row('Einzel-Aktivitäten (Events)', eventsW, '#9ca3af', 'bisher <b>kein messbarer Effekt</b>')+
      '<div style="font-size:10.5px;color:#9ca3af;margin-top:4px">Balkenlänge = Stärke des gemessenen Zusammenhangs mit Sichtbarkeit (illustrativ).</div>'+
    '</div>';
  }

  // ---- Kachel Ebene A ----
  function tileA(C){
    var lm=C.level_model||{}; var m=seg(lm);
    if(!m||!m.available) return '<div style="font-size:13px;color:#6b7280">Für diese Auswahl noch zu wenige Daten.</div>';
    var ar=m.authority_ranking||[]; var lead=m.leader;
    var al=ar.filter(function(a){return a.brand===lead;})[0]||{}; var er=ar.filter(function(a){return a.brand==="ERGO";})[0]||{};
    var w=m.within_effect.coef_pp_sov_per_pp_citeshare;
    var mx=Math.max(al.mean_cite_share_pct||1, er.mean_cite_share_pct||1, 1);
    return '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:4px"><b style="font-size:14px">Ebene A · Niveau (Stock)</b> '+evChip(1)+'</div>'+
      '<div style="font-size:12px;color:#4b5563;margin:0 0 8px">Treiber: <b>Zitations-Footprint</b> (Präsenz in den zitierten Quellen).</div>'+
      '<div style="font-size:24px;font-weight:700;color:#1a1a2e;line-height:1.1">'+signed(w,1)+' <span style="font-size:12px;font-weight:500;color:#9ca3af">pp SoV je +1 pp Zitatanteil</span></div>'+
      '<div style="font-size:11px;color:#9ca3af;margin:2px 0 10px">themen­bereinigt (Marke gegen sich selbst) — der sauberste Befund</div>'+
      '<div style="font-size:11px;color:#6b7280;margin-bottom:3px">Zitatanteil je Marke (Ø):</div>'+
      '<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px"><span style="width:56px;font-size:11px">ERGO</span>'+hbar(100*(er.mean_cite_share_pct||0)/mx,'#dc0028',12)+'<span style="width:38px;font-size:11px;text-align:right">'+num(er.mean_cite_share_pct,1)+'%</span></div>'+
      '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px"><span style="width:56px;font-size:11px">'+lead+'</span>'+hbar(100*(al.mean_cite_share_pct||0)/mx,'#9ca3af',12)+'<span style="width:38px;font-size:11px;text-align:right">'+num(al.mean_cite_share_pct,1)+'%</span></div>'+
      '<button id="korrGeoLink" style="font-size:12px;padding:6px 12px;border-radius:8px;border:1px solid #dc0028;background:#fff;color:#dc0028;cursor:pointer">→ Grafik &amp; Details (Reiter „LLM-Sichtbarkeit")</button>';
  }

  // ---- Kachel Ebene B ----
  function tileB(C){
    var mv=C.multivariate||{}; var coefs=mv.coefficients||{};
    var nSig=Object.keys(coefs).filter(function(k){return coefs[k].significant;}).length;
    var val=C.validation||{}; var oos=(val.out_of_sample||{}).r2_oos_vs_baseline; var days=C.sov_measure_days;
    return '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:4px"><b style="font-size:14px">Ebene B · Bewegung (Flow)</b> '+evChip(2)+'</div>'+
      '<div style="font-size:12px;color:#4b5563;margin:0 0 8px">Kurzfristige Events: Seitenänderungen, neue Seiten, Presse, Bewertungen.</div>'+
      '<div style="font-size:24px;font-weight:700;color:#1a1a2e;line-height:1.1">'+nSig+' / '+Object.keys(coefs).length+' <span style="font-size:12px;font-weight:500;color:#9ca3af">Event-Typen gesichert</span></div>'+
      '<div style="font-size:11px;color:#9ca3af;margin:2px 0 10px">= kein belastbarer Kurzfrist-Effekt</div>'+
      '<div style="font-size:12px;color:#4b5563">Große verlässliche Tageseffekte sind <b>ausgeschlossen</b> (Vorhersage schlechter als Basislinie, Out-of-Sample R² '+num(oos,2)+'). Kleine Effekte &lt;~1 pp sind bei '+days+' Messtagen nicht ausschließbar.</div>'+
      '<div style="font-size:11px;color:#9ca3af;margin-top:8px">Nur bei web-gestützten LLMs plausibel; bei ChatGPT Rauschen.</div>';
  }

  function fazit(C){
    var lm=C.level_model||{}; var m=seg(lm)||{}; var ar=m.authority_ranking||[];
    var al=ar.filter(function(a){return a.brand===m.leader;})[0]||{}; var er=ar.filter(function(a){return a.brand==="ERGO";})[0]||{};
    return '<b>Kurz gesagt:</b> Sichtbarkeit kommt aus <b>Quellpräsenz</b>, nicht aus einzelnen Aktionen. ERGO ist in den zitierten Quellen schwächer vertreten ('+num(er.mean_cite_share_pct,0)+' % vs. '+(m.leader||"Allianz")+' '+num(al.mean_cite_share_pct,0)+' %) — genau das erklärt den Großteil des Rückstands. <b>Hebel:</b> eigene Inhalte zitierfähig ausbauen, priorisiert dort, wo heute Portale dominieren (z. B. Reise). Ob das kausal wirkt, prüfen wir über Experimente (Maßnahmen-Wirkung / DiD).';
  }

  function details(C){
    var lm=C.level_model||{}; var m=seg(lm)||{};
    var g=(m.gap_decomposition||{})["ERGO"]; var share=g&&g.share_explained!=null?Math.round(g.share_explained*100):null;
    var loo=m.between_loo;
    var looTxt = loo? ('Robustheit (Leave-one-brand-out): Vorzeichen bleibt beim Weglassen jeder einzelnen Marke stabil ('+(loo.sign_stable?'ja':'NEIN')+'; Between-Spanne '+signed(loo.min,2)+'…'+signed(loo.max,2)+').') : '';
    return '<div style="font-size:12px;color:#4b5563;line-height:1.6">'+
      (share!=null?('<b>Gap-Zerlegung:</b> Rund <b>'+share+' %</b> des SoV-Abstands zu '+(m.leader||"Allianz")+' gehen statistisch mit dem geringeren Zitations-Footprint einher — eine <b>Zerlegung, kein Kausalnachweis</b> (ein Teil dürfte allgemeine Markenstärke sein). Der Within-Befund ('+signed(m.within_effect.coef_pp_sov_per_pp_citeshare,1)+' pp/pp, themenbereinigt) stützt, dass Footprint eigenständig wirkt.<br>'):'')+
      (looTxt?(looTxt+'<br>'):'')+
      'Modellgüte: Zusammenhang r '+num(m.raw_pearson_r,2)+', R² '+(m.r2_within_topics==null?'—':Math.round(m.r2_within_topics*100)+' %')+' ('+modeLbl()+').<br>'+
      '<span style="color:#9ca3af">Methodik: Zusammenhänge, kein Kausalnachweis (Ausnahme DiD). Zitatanteil und Sichtbarkeit stammen teils aus denselben LLM-Antworten (mögliche Überlappung). „9 %" ist eine Zielmarke, keine SoV-Prognose. Datenbasis 6 Themen × 7 Marken — explorativ. Evidenz-Skala: '+evChip(3)+' (nur DiD) · '+evChip(1)+' · '+evChip(2)+'</span></div>';
  }

  function wieBeeinflussen(){
    return '<div style="border:1px dashed #dc0028;border-radius:10px;padding:12px 14px;margin-top:12px;background:#fffafb">'+
      '<div style="font-size:13px;font-weight:700;color:#dc0028;margin-bottom:6px">So beeinflussen Sie es — Hebel nach Stärke</div>'+
      '<div style="font-size:12.5px;color:#282d37;line-height:1.6">'+
      '<b>1. Eigene Inhalte zitierfähig ausbauen</b> (größter Hebel): Themen-Hubs, FAQ, klare Definitionen, Tabellen, strukturierte Daten — damit LLMs ergo.de als Quelle zitieren.<br>'+
      '<b>2. Präsenz auf den zitierten Portalen</b> (Check24, Verivox) &amp; Testquellen (test.de): Listung, Rang, Bewertungen.<br>'+
      '<b>3. Bewertungen &amp; Presse</b> als flankierende Signale.'+
      '</div>'+
      '<div style="font-size:11.5px;color:#6b7280;margin-top:6px">→ <b>Welche Quellen je Thema zählen</b>, zeigt die <b>Kanal-Analyse</b> im Reiter „LLM-Sichtbarkeit". Den <b>echten Wirkungs-Effekt</b> messen wir über Experimente (Maßnahmen-Wirkung / DiD).</div>'+
      '</div>';
  }

  function renderPanel(host, C){
    var card=document.getElementById("korrSynth");
    if(!card){ card=document.createElement("div"); card.id="korrSynth"; card.className="bg-white rounded-xl shadow p-6 mb-6"; host.insertBefore(card, host.firstChild); }
    card.innerHTML=
      '<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;margin-bottom:12px">'+
        '<div><h3 style="font-size:17px;font-weight:700;margin:0">Was treibt die LLM-Sichtbarkeit?</h3>'+
        '<p style="font-size:12px;color:#6b7280;margin:2px 0 0">Zwei Ebenen: dauerhaftes <b>Niveau</b> (Quellpräsenz) vs. kurzfristige <b>Bewegung</b> (Events).</p></div>'+
        '<div id="korrToggle" style="display:flex;gap:6px">'+
          '<button data-m="g" class="ksw" style="font-size:11px;padding:4px 10px;border-radius:8px;border:1px solid #dc0028;background:#dc0028;color:#fff;cursor:pointer">grounded</button>'+
          '<button data-m="u" class="ksw" style="font-size:11px;padding:4px 10px;border-radius:8px;border:1px solid #ccc;background:#fff;color:#282d37;cursor:pointer">ungrounded</button>'+
          '<button data-m="c" class="ksw" style="font-size:11px;padding:4px 10px;border-radius:8px;border:1px solid #ccc;background:#fff;color:#282d37;cursor:pointer">beides</button>'+
        '</div>'+
      '</div>'+
      '<div id="korrLever">'+leverGraphic(C)+'</div>'+
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">'+
        '<div style="border:1px solid #eee;border-radius:10px;padding:14px" id="korrA">'+tileA(C)+'</div>'+
        '<div style="border:1px solid #eee;border-radius:10px;padding:14px;background:#fafafa" id="korrB">'+tileB(C)+'</div>'+
      '</div>'+
      '<div style="font-size:12.5px;color:#282d37;background:#f8f7f4;border-left:3px solid #dc0028;border-radius:4px;padding:11px 14px;margin-top:14px;line-height:1.55" id="korrFazit">'+fazit(C)+'</div>'+
      wieBeeinflussen()+
      '<details style="margin-top:12px"><summary style="cursor:pointer;font-size:12px;font-weight:600;color:#6b7280">Methodik &amp; Details anzeigen</summary>'+
        '<div style="margin-top:8px" id="korrDet">'+details(C)+'</div></details>';

    card.querySelectorAll(".ksw").forEach(function(btn){
      btn.addEventListener("click",function(){
        mode=btn.getAttribute("data-m");
        card.querySelectorAll(".ksw").forEach(function(b){var on=b.getAttribute("data-m")===mode;b.style.background=on?"#dc0028":"#fff";b.style.color=on?"#fff":"#282d37";b.style.borderColor=on?"#dc0028":"#ccc";});
        document.getElementById("korrLever").innerHTML=leverGraphic(C);
        document.getElementById("korrA").innerHTML=tileA(C);
        document.getElementById("korrFazit").innerHTML=fazit(C);
        document.getElementById("korrDet").innerHTML=details(C);
        wireGeoLink();
      });
    });
    wireGeoLink();
  }
  function wireGeoLink(){ var b=document.getElementById("korrGeoLink"); if(b) b.addEventListener("click",function(){ var t=document.querySelector('[data-tab="geo"]'); if(t){ t.click(); window.scrollTo({top:0,behavior:"smooth"}); } }); }

  // Detail-/Monitoring-Sektionen einklappen; Alt-Titel ausblenden
  function tidy(host){
    [].slice.call(host.children).forEach(function(el){
      if(el.id!=="korrSynth" && el.id!=="korrDetails" && /^🔗\s*Korrelation/.test((el.innerText||"").trim())) el.style.display="none";
    });
    if(document.getElementById("korrDetails")) return;
    var rxs=[/Validierte Impact-Analyse/,/Maßnahmen-Wirkung/,/Share of Voice/,/Tagesübersicht/,/Mention-Tracking/,/Event-Stream/];
    var kids=[].slice.call(host.children); var toCollapse=[];
    rxs.forEach(function(rx){ var b=kids.filter(function(el){ return el.id!=="korrSynth"&&el.id!=="korrDetails"&&rx.test((el.innerText||"").slice(0,90)); })[0]; if(b&&toCollapse.indexOf(b)<0) toCollapse.push(b); });
    if(toCollapse.length){
      var det=document.createElement("details"); det.id="korrDetails"; det.className="bg-white rounded-xl shadow mb-6"; det.style.cssText="padding:6px 18px";
      det.innerHTML='<summary style="cursor:pointer;font-size:13px;font-weight:600;color:#6b7280;padding:12px 0">Alle Detail-Auswertungen anzeigen (Event-Study, Maßnahmen-Wirkung/DiD, SoV-Verlauf, Mentions, Event-Stream)</summary>';
      toCollapse[0].parentNode.insertBefore(det, toCollapse[0]);
      toCollapse.forEach(function(b){ b.style.display=""; det.appendChild(b); });
    }
  }

  function build(){
    var host=document.querySelector('section[data-content="korrelation"]');
    if(!host) return false;
    var C=window.CORRELATION_IMPACT;
    if(!C || !C.level_model) return false;
    renderPanel(host,C);
    [0,400,1000,2000,3500].forEach(function(d){ setTimeout(function(){ tidy(host); }, d); });
    return true;
  }
  ready(function(){
    var tries=0;
    (function wait(){ tries++; if(build()) return; if(tries<40) setTimeout(wait,300); })();
    var tb=document.querySelector('[data-tab="korrelation"]'); if(tb) tb.addEventListener("click",function(){ [150,600,1400].forEach(function(d){ setTimeout(build,d); }); });
  });
})();
