/* ============================================================
   ERGO LLM-Cockpit — Korrelations-Reiter: Zwei-Ebenen-Synthese
   Rahmt den Reiter als zwei Ebenen:
     A) Niveau/Stock  — Zitations-Footprint erklaert das SoV-Niveau
        (staerkster Zusammenhang; Details im Reiter LLM-Sichtbarkeit)
     B) Bewegung/Flow — Event-Study: was SoV kurzfristig verschiebt
        (aktuell kein belastbarer Effekt nachweisbar)
   Ehrliche Evidenz-Skala, Querverweis, ERGO-Fazit. Quelle:
   window.CORRELATION_IMPACT (level_model, multivariate, validation).
   Additive Ueberlagerung, veraendert die bestehenden Sektionen nicht.
   ============================================================ */
(function () {
  "use strict";
  function ready(fn){ if(document.readyState!=="loading") fn(); else document.addEventListener("DOMContentLoaded",fn); }
  function num(v,d){ return (v==null||isNaN(v))?"—":(Math.round(v*Math.pow(10,d))/Math.pow(10,d)).toFixed(d); }
  function signed(v,d){ return (v>0?"+":"")+num(v,d); }

  var mode="g";
  function seg(lm){ return mode==="g"?lm.grounded:(mode==="u"?lm.ungrounded:lm.combined); }
  function modeLbl(){ return mode==="g"?"grounded (Web-Suche)":(mode==="u"?"ungrounded (ChatGPT)":"kombiniert (alle LLMs)"); }

  function evChip(kind){
    if(kind===3) return '<span style="font-size:10px;font-weight:700;color:#067d3a;background:#e6f5ec;border-radius:4px;padding:2px 7px">kausal belegt</span>';
    if(kind===1) return '<span style="font-size:10px;font-weight:700;color:#8a6d00;background:#fdf3d7;border-radius:4px;padding:2px 7px">konsistente Assoziation · explorativ</span>';
    return '<span style="font-size:10px;font-weight:700;color:#6b7280;background:#eef0f2;border-radius:4px;padding:2px 7px">nicht nachweisbar (kurze Messreihe)</span>';
  }

  function ebeneA(C){
    var lm=C.level_model||{}; var m=seg(lm);
    if(!m||!m.available) return '<div style="font-size:13px;color:#6b7280">Für diese Auswahl noch zu wenige Daten.</div>';
    var ar=m.authority_ranking||[];
    var lead=m.leader; var al=ar.filter(function(a){return a.brand===lead;})[0]||{};
    var er=ar.filter(function(a){return a.brand==="ERGO";})[0]||{};
    var g=(m.gap_decomposition||{})["ERGO"];
    var share=g&&g.share_explained!=null?Math.round(g.share_explained*100):null;
    var w=m.within_effect.coef_pp_sov_per_pp_citeshare, b=m.between_effect.coef_pp_sov_per_pp_citeshare;
    var loo=m.between_loo;
    var looTxt = loo? ('Robustheit: Vorzeichen bleibt beim Weglassen jeder einzelnen Marke stabil ('+(loo.sign_stable?'ja':'NEIN')+'; Between-Spanne '+signed(loo.min,2)+'…'+signed(loo.max,2)+').') : '';
    return ''+
      '<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:6px">'+
        '<b style="font-size:14px">Ebene A · Niveau (Stock) — Quellpräsenz</b> '+evChip(1)+'</div>'+
      '<p style="font-size:12px;color:#4b5563;margin:0 0 8px">Stärkster statistischer Zusammenhang mit der Sichtbarkeit ist der <b>Zitations-Footprint</b> (wie oft die eigene Domain in den von LLMs zitierten Quellen vorkommt).</p>'+
      '<div style="display:flex;gap:18px;flex-wrap:wrap;margin-bottom:8px">'+
        '<div><div style="font-size:11px;color:#6b7280">Within-Effekt (themen­bereinigt, sauberster Befund)</div>'+
          '<div style="font-size:22px;font-weight:700;color:#1a1a2e">'+signed(w,2)+' <span style="font-size:11px;font-weight:500;color:#9ca3af">pp SoV / pp Zitatanteil</span></div></div>'+
        '<div><div style="font-size:11px;color:#6b7280">Between (Autoritäts-Kontext)</div>'+
          '<div style="font-size:22px;font-weight:700;color:#6b7280">'+signed(b,2)+'</div></div>'+
        '<div><div style="font-size:11px;color:#6b7280">Zusammenhang r</div>'+
          '<div style="font-size:22px;font-weight:700;color:#6b7280">'+num(m.raw_pearson_r,2)+'</div></div>'+
      '</div>'+
      '<p style="font-size:12px;color:#4b5563;margin:0 0 6px">ERGO Ø <b>'+num(er.mean_cite_share_pct,1)+' %</b> Footprint vs. '+lead+' Ø <b>'+num(al.mean_cite_share_pct,1)+' %</b>. '+
        (share!=null?('Dieser Rückstand geht statistisch mit rund <b>'+share+' %</b> des SoV-Abstands zu '+lead+' einher — eine <b>Zerlegung, kein Kausalnachweis</b> (ein Teil dürfte allgemeine Markenstärke spiegeln). Dass Footprint eigenständig wirkt, stützt der Within-Befund (Marke gegen sich selbst über Themen).'):'')+'</p>'+
      (looTxt?('<p style="font-size:11px;color:#9ca3af;margin:0 0 8px">'+looTxt+'</p>'):'')+
      '<button id="korrGeoLink" style="font-size:12px;padding:6px 12px;border-radius:8px;border:1px solid #dc0028;background:#fff;color:#dc0028;cursor:pointer">→ Grafik &amp; Details im Reiter „LLM-Sichtbarkeit"</button>';
  }

  function ebeneB(C){
    var mv=C.multivariate||{}; var coefs=mv.coefficients||{};
    var nSig=Object.keys(coefs).filter(function(k){return coefs[k].significant;}).length;
    var val=C.validation||{}; var oos=(val.out_of_sample||{}).r2_oos_vs_baseline;
    var plac=val.placebo_false_positive_rate;
    var days=C.sov_measure_days;
    return ''+
      '<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:6px">'+
        '<b style="font-size:14px">Ebene B · Bewegung (Flow) — kurzfristige Events</b> '+evChip(2)+'</div>'+
      '<p style="font-size:12px;color:#4b5563;margin:0 0 8px">Was verschiebt SoV <b>kurzfristig</b> (Seitenänderungen, neue Seiten, Presse/News, Bewertungen)?</p>'+
      '<p style="font-size:12px;color:#4b5563;margin:0 0 8px"><b>Kein Event-Typ zeigt einen belastbaren kurzfristigen Effekt</b> ('+nSig+' von '+Object.keys(coefs).length+' gesichert; alle P&lt;0,90). Große, verlässliche Tageseffekte sind <b>ausgeschlossen</b> — ein Modell mit Event-Treibern sagt SoV schlechter voraus als die reine Marken-Basislinie (Out-of-Sample R² = '+num(oos,2)+'). Kleine Effekte (&lt;~1 pp) sind bei '+days+' Messtagen <b>nicht ausschließbar</b>.</p>'+
      '<p style="font-size:12px;color:#4b5563;margin:0 0 6px">Nur bei <b>web-gestützten</b> LLMs überhaupt plausibel (Retrieval→Zitat→Nennung). Bei ChatGPT (ungrounded, parametrisch) sind Events per Konstruktion <b>Rauschen</b> — Wirkung erst beim nächsten Modell-Update.</p>'+
      '<p style="font-size:11px;color:#9ca3af;margin:0">Validierung: Placebo-Falsch-Positiv-Rate '+num(plac,3)+' (erwartet ~0,05 → das Modell erfindet keine Scheineffekte).</p>';
  }

  function fazit(C){
    var lm=C.level_model||{}; var m=seg(lm)||{};
    var ar=m.authority_ranking||[];
    var al=ar.filter(function(a){return a.brand===m.leader;})[0]||{};
    var er=ar.filter(function(a){return a.brand==="ERGO";})[0]||{};
    var w=m.within_effect?m.within_effect.coef_pp_sov_per_pp_citeshare:null;
    return ''+
      '<b>Fazit für ERGO.</b> ERGOs LLM-Sichtbarkeit hängt eng mit der Präsenz in den zitierten Quellen zusammen: Wo ERGOs Domain häufiger zitiert wird, ist ERGO sichtbarer — auch innerhalb derselben Marke über Themen hinweg ('+signed(w,1)+' pp SoV je pp Zitatanteil, '+modeLbl()+'). Der Zitat-Rückstand zu '+(m.leader||"Allianz")+' ('+num(er.mean_cite_share_pct,0)+' % vs. '+num(al.mean_cite_share_pct,0)+' %) geht mit dem Großteil des Sichtbarkeits-Abstands einher; ein Teil davon dürfte allgemeine Markenstärke sein, der Zusammenhang bleibt aber auch themen­bereinigt bestehen. Kurzfristige Einzel-Events zeigen dagegen keinen belastbaren Effekt. <b>Hebel:</b> Quellpräsenz systematisch ausbauen — priorisiert in Themen, in denen heute Portale die Zitate dominieren (z. B. Reise) — statt einzelnen Events hinterherzulaufen. Ob der Aufbau kausal wirkt, prüfen wir laufend über die Maßnahmen-Auswertung (DiD).';
  }

  function renderPanel(host, C){
    var card=document.getElementById("korrSynth");
    if(!card){
      card=document.createElement("div");
      card.id="korrSynth";
      card.className="bg-white rounded-xl shadow p-6 mb-6";
      host.insertBefore(card, host.firstChild);
    }
    card.innerHTML=
      '<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;margin-bottom:6px">'+
        '<div><h3 style="font-size:17px;font-weight:700;margin:0">Was treibt die LLM-Sichtbarkeit? — zwei Ebenen</h3>'+
        '<p style="font-size:12px;color:#6b7280;margin:3px 0 0">Sichtbarkeit ist v. a. ein <b>Niveau</b> (wer ist grundsätzlich präsent), nur zum kleinen Teil <b>Tagesbewegung</b>. Wir trennen beides sauber.</p></div>'+
        '<div id="korrToggle" style="display:flex;gap:6px">'+
          '<button data-m="g" class="ksw" style="font-size:11px;padding:4px 10px;border-radius:8px;border:1px solid #dc0028;background:#dc0028;color:#fff;cursor:pointer">grounded</button>'+
          '<button data-m="u" class="ksw" style="font-size:11px;padding:4px 10px;border-radius:8px;border:1px solid #ccc;background:#fff;color:#282d37;cursor:pointer">ungrounded</button>'+
          '<button data-m="c" class="ksw" style="font-size:11px;padding:4px 10px;border-radius:8px;border:1px solid #ccc;background:#fff;color:#282d37;cursor:pointer">beides</button>'+
        '</div>'+
      '</div>'+
      '<div style="font-size:10px;color:#9ca3af;margin-bottom:12px">Evidenz-Skala: '+evChip(3)+' (nur Maßnahmen-Auswertung/DiD) &nbsp; '+evChip(1)+' &nbsp; '+evChip(2)+'</div>'+
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px" id="korrCards">'+
        '<div style="border:1px solid #eee;border-radius:10px;padding:14px" id="korrA">'+ebeneA(C)+'</div>'+
        '<div style="border:1px solid #eee;border-radius:10px;padding:14px;background:#fafafa" id="korrB">'+ebeneB(C)+'</div>'+
      '</div>'+
      '<div style="font-size:12.5px;color:#282d37;background:#f8f7f4;border-left:3px solid #dc0028;border-radius:4px;padding:11px 14px;margin-top:14px;line-height:1.55" id="korrFazit">'+fazit(C)+'</div>'+
      '<p style="font-size:10.5px;color:#9ca3af;margin:10px 0 0;line-height:1.5">Methodik-Hinweise: Es handelt sich um <b>Zusammenhänge, keinen Kausalnachweis</b> (Ausnahme: Maßnahmen-Wirkung via DiD, unten). Zitatanteil und Sichtbarkeit stammen teils aus denselben LLM-Antworten (mögliche Überlappung). Die Ziel-Orientierung „Footprint Richtung 9 %" ist eine <b>Zielmarke</b>, keine vorhergesagte SoV-Prognose. Datenbasis Ebene A: 6 Themen × 7 Marken — <b>explorativ</b>.</p>';

    card.querySelectorAll(".ksw").forEach(function(btn){
      btn.addEventListener("click",function(){
        mode=btn.getAttribute("data-m");
        card.querySelectorAll(".ksw").forEach(function(b){var on=b.getAttribute("data-m")===mode;b.style.background=on?"#dc0028":"#fff";b.style.color=on?"#fff":"#282d37";b.style.borderColor=on?"#dc0028":"#ccc";});
        document.getElementById("korrA").innerHTML=ebeneA(C);
        document.getElementById("korrFazit").innerHTML=fazit(C);
        wireGeoLink();
      });
    });
    wireGeoLink();
  }

  function wireGeoLink(){
    var b=document.getElementById("korrGeoLink");
    if(b) b.addEventListener("click",function(){ var t=document.querySelector('[data-tab="geo"]'); if(t){ t.click(); window.scrollTo({top:0,behavior:"smooth"}); } });
  }

  function relabelEventStudy(host){
    if(host.getAttribute("data-b-labeled")) return;
    var nodes=[].slice.call(host.querySelectorAll("h1,h2,h3,h4,div,span"));
    var hit=nodes.filter(function(n){ return /Validierte Impact-Analyse/.test(n.textContent) && n.children.length<=2 && n.textContent.length<80; })[0];
    if(hit){
      var tag=document.createElement("span");
      tag.textContent=" — Ebene B (Detail)";
      tag.style.cssText="font-size:12px;color:#9ca3af;font-weight:500";
      hit.appendChild(tag);
      host.setAttribute("data-b-labeled","1");
    }
  }

  function build(){
    var host=document.querySelector('section[data-content="korrelation"]');
    if(!host) return false;
    var C=window.CORRELATION_IMPACT;
    if(!C || !C.level_model) return false;
    renderPanel(host,C);
    relabelEventStudy(host);
    return true;
  }

  ready(function(){
    var tries=0;
    (function wait(){
      tries++;
      if(build()) return;
      if(tries<40) setTimeout(wait,300);
    })();
    var tb=document.querySelector('[data-tab="korrelation"]');
    if(tb) tb.addEventListener("click",function(){ setTimeout(build,150); });
  });
})();
