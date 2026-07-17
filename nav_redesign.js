/* ============================================================
   ERGO LLM-Cockpit — Navigations-Redesign (15.07.2026)
   Runtime-Modul (kein Template-Edit noetig):
   1. Reiter-Umbenennung: LLM-Sichtbarkeit, Empfehlungen, Presse,
      Content Aenderungen, Korrelationsanalyse
   2. Die 10 Anbieter-Tabs wandern in ein Dropdown
      "Anbieter-Webseiten" (Wunsch 15.07.).
   Geladen via health_banner.js (Loader am Dateiende).
   Fix 15.07. abends: Menue haengt am document.body (position:fixed),
   weil die Tab-Leiste per overflow das absolute Menue abgeschnitten hat.
   ============================================================ */
(function () {
  "use strict";
  function ready(fn){ if(document.readyState!=="loading") fn(); else document.addEventListener("DOMContentLoaded",fn); }

  var RENAME = { geo:"LLM-Sichtbarkeit", actions:"Empfehlungen", presse:"Presse",
                 contentgeo:"Content Änderungen", korrelation:"🔗 Korrelationsanalyse" };
  var BRANDS = ["ergo","allianz","huk","axa","generali","signal","ruv","devk","hannoversche","cosmosdirekt"];

  function build(){
    var bar = document.querySelector('.tab-btn[data-tab="overview"]');
    if(!bar) return false;
    var container = bar.parentNode;
    if(document.getElementById("brandDDBtn")) return true; // idempotent

    // 1) Labels umbenennen
    Object.keys(RENAME).forEach(function(k){
      var b=document.querySelector('.tab-btn[data-tab="'+k+'"]');
      if(b) b.textContent=RENAME[k];
    });

    // 2) Anbieter-Dropdown
    var firstBrand=document.querySelector('.tab-btn[data-tab="'+BRANDS[0]+'"]');
    if(!firstBrand) return true;
    var wrap=document.createElement("div");
    wrap.id="brandDD"; wrap.style.cssText="position:relative;display:inline-block";
    var btn=document.createElement("button");
    btn.id="brandDDBtn"; btn.type="button";
    btn.className="tab-btn tab-inactive px-4 py-2 text-sm font-semibold rounded border-2 transition";
    btn.textContent="Anbieter-Webseiten ▾";
    btn.removeAttribute("data-tab");
    var menu=document.createElement("div");
    menu.id="brandDDMenu";
    menu.style.cssText="display:none;position:fixed;z-index:9000;background:#fff;border:1px solid #e5e7eb;border-radius:10px;box-shadow:0 10px 28px rgba(0,0,0,.15);padding:6px;min-width:190px;max-height:70vh;overflow-y:auto";
    wrap.appendChild(btn);
    document.body.appendChild(menu); // an body: Tab-Leiste hat overflow und wuerde das Menue abschneiden
    container.insertBefore(wrap, firstBrand);
    BRANDS.forEach(function(k){
      var b=document.querySelector('.tab-btn[data-tab="'+k+'"]');
      if(!b) return;
      b.style.cssText="display:block;width:100%;text-align:left;padding:7px 12px;font-size:13px;font-weight:600;border:0;border-radius:8px";
      menu.appendChild(b);
    });

    function openMenu(){
      var r=btn.getBoundingClientRect();
      menu.style.top=(r.bottom+4)+"px";
      menu.style.left=Math.max(8, Math.min(r.left, window.innerWidth-210))+"px";
      menu.style.display="block";
    }
    btn.addEventListener("click",function(e){ e.stopPropagation(); if(menu.style.display==="block"){ menu.style.display="none"; } else { openMenu(); } });
    window.addEventListener("scroll",function(){ menu.style.display="none"; }, true);
    window.addEventListener("resize",function(){ menu.style.display="none"; });
    document.addEventListener("click",function(){ menu.style.display="none"; });
    menu.addEventListener("click",function(e){ e.stopPropagation(); });
    menu.querySelectorAll("[data-tab]").forEach(function(b){
      b.addEventListener("click",function(){
        menu.style.display="none";
        btn.textContent="Anbieter: "+b.textContent+" ▾";
        btn.classList.remove("tab-inactive"); btn.classList.add("tab-active");
      });
    });
    document.querySelectorAll(".tab-btn[data-tab]").forEach(function(b){
      if(b.closest("#brandDDMenu")) return;
      b.addEventListener("click",function(){
        btn.textContent="Anbieter-Webseiten ▾";
        btn.classList.remove("tab-active"); btn.classList.add("tab-inactive");
      });
    });
    return true;
  }
  ready(function(){ var tries=0; (function w(){ tries++; if(build()) return; if(tries<40) setTimeout(w,300); })(); });
})();

/* Loader (15.07.2026): Zusatzmodule nachladen. */
(function(){ try{
  ["peec_compare.js","overview_upgrade.js"].forEach(function(f){
    var s=document.createElement("script"); s.src=f+"?t="+Date.now(); document.body.appendChild(s);
  });
}catch(e){} })();
