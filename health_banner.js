/* ============================================================
   ERGO LLM-Cockpit — Health-/Frische-Banner
   Zweck: sichtbar warnen, wenn ein LLM keine Daten mehr liefert
   (typisch: API-Guthaben aufgebraucht oder Key/Modell ungueltig)
   oder wenn der Snapshot ueberaltert ist.
   Eigenstaendig, keine Abhaengigkeit vom Dashboard-Code.
   Liest data/geo_snapshot.json (dieselbe Datei wie das Dashboard).
   Einbindung: <script src="health_banner.js"></script> vor </body>.
   ============================================================ */
(function () {
  "use strict";

  // 12.08.2026 von 2 auf 8 Tage: Der GEO-Crawl laeuft seit der Umstellung nur
  // noch WOECHENTLICH. Mit der alten 2-Tage-Grenze stand das Banner ab jedem
  // Mittwoch bis zum naechsten Lauf im Bild - fuenf von sieben Tagen Alarm ohne
  // Anlass. Genau so gewoehnt man sich ab hinzusehen, und dann faellt der echte
  // Ausfall nicht mehr auf. 8 = 7 Tage Takt + 1 Tag Luft, weil GitHub geplante
  // Laeufe im Free-Tier um Stunden verzoegert. Aeltere Daten heissen: ein Lauf
  // ist ausgefallen.
  //
  // 13.08.2026: Hier stand "sonntags 23:10 UTC" - und zwar richtig, als es
  // geschrieben wurde. Keine 24 Stunden spaeter wurde der Cron im GEO-Repo auf
  // Montag gezogen (analyze.yml, "Crawl von taeglich auf woechentlich (Mo)"),
  // und der Satz war falsch. Ich hatte eine Zeile darueber selbst notiert, dass
  // diese Angabe eine Kopie einer Annahme ist, die woanders steht - genau daran
  // ist sie dann gescheitert.
  // Konsequenz: Der Wochentag steht hier nicht mehr. Das Banner braucht ihn
  // nicht, es braucht nur die Grenze. Was es nicht behauptet, kann nicht
  // veralten. Der Takt selbst steht im GEO-Repo, und nur dort.
  var MAX_AGE_DAYS = 8;
  var CRAWL_TAKT = "nur einmal pro Woche";
  var SNAP_URL = "data/geo_snapshot.json";
  var LLM_NAMES = { chatgpt: "ChatGPT", gemini: "Gemini", perplexity: "Perplexity", claude: "Claude", grok: "Grok" };
  var LLM_HINT = {
    chatgpt: "OpenAI-Guthaben pruefen: platform.openai.com/settings/organization/billing",
    perplexity: "Perplexity-API-Guthaben pruefen: perplexity.ai/settings/api",
    gemini: "Google-/Gemini-API-Key & Kontingent pruefen",
    claude: "Anthropic-API-Key & Guthaben pruefen",
    grok: "xAI-API-Key & Guthaben pruefen"
  };

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  function parseDate(s) {
    if (!s) return null;
    s = String(s).trim();
    // run_id-Form "2026-05-30T00-17-37Z" -> ISO mit Doppelpunkten
    var m = s.match(/^(\d{4}-\d{2}-\d{2})T(\d{2})-(\d{2})-(\d{2})Z?$/);
    if (m) s = m[1] + "T" + m[2] + ":" + m[3] + ":" + m[4] + "Z";
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) s += "T00:00:00Z";
    var d = new Date(s);
    return isNaN(d.getTime()) ? null : d;
  }

  function fmtDate(d) {
    if (!d) return "unbekannt";
    try { return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" }); }
    catch (e) { return d.toISOString().slice(0, 10); }
  }

  function analyze(g) {
    var out = { broken: [], allZero: false, ageDays: null, snapDate: null, ok: true, carried: [] };
    if (!g || !g.products) return out;

    // 15.08.2026: Fortgeschriebene LLMs anzeigen. Der Perplexity-Ausfall ab dem
    // 06.08. blieb acht Tage unsichtbar, weil die Fortschreibung im Cockpit wie
    // eine frische Messung aussah. Der GEO-Lauf liefert carried_forward und
    // seit heute auch das Ursprungsdatum je Engine (carried_forward_from) -
    // update_snapshot.py reicht beide durch. Ein LLM, das nur Konserve zeigt,
    // ist kein Fehler, aber es gehoert gesagt.
    (g.carried_forward || []).forEach(function (l) {
      var von = (g.carried_forward_from || {})[l] || null;
      out.carried.push({ llm: l, von: von });
    });

    // Fix 2026-07-15: Nur LLMs pruefen, die im Snapshot wirklich Produktdaten haben.
    // g.llms kann pausierte LLMs enthalten (z.B. Perplexity nach Abschaltung) —
    // die loesten frueher einen FALSCHEN "liefert keine Daten"-Alarm aus.
    var llms = [];
    for (var pid0 in g.products) {
      var sbl0 = g.products[pid0].summary_by_llm || {};
      for (var k in sbl0) if (llms.indexOf(k) < 0) llms.push(k);
    }
    if (!llms.length && Array.isArray(g.llms)) llms = g.llms.slice();

    var totals = {};
    llms.forEach(function (l) { totals[l] = 0; });
    for (var pid in g.products) {
      var sbl = g.products[pid].summary_by_llm || {};
      llms.forEach(function (l) {
        var brands = (sbl[l] && sbl[l].brands) || [];
        brands.forEach(function (b) { totals[l] += (b.mentions || 0); });
      });
    }

    var anyData = llms.some(function (l) { return totals[l] > 0; });
    out.allZero = !anyData;
    out.broken = anyData ? llms.filter(function (l) { return totals[l] === 0; }) : [];

    out.snapDate = parseDate(g.finished_at || g.started_at || g.run_id);
    if (out.snapDate) out.ageDays = Math.round((Date.now() - out.snapDate.getTime()) / 86400000 * 10) / 10;

    var stale = (out.ageDays === null) || (out.ageDays > MAX_AGE_DAYS);
    out.stale = stale;
    out.ok = (out.broken.length === 0) && !out.allZero && !stale && out.carried.length === 0;
    return out;
  }

  function render(a) {
    if (a.ok) return;

    // Dismiss nur fuer diesen Snapshot-Stand (kommt bei neuen Daten wieder)
    var key = "ergo_health_dismiss_" + (a.snapDate ? a.snapDate.toISOString().slice(0, 16) : "na")
      + "_" + a.broken.join("-") + (a.stale ? "_stale" : "") + (a.allZero ? "_zero" : "")
      + ((a.carried || []).length ? ("_cf" + a.carried.map(function (c) { return c.llm; }).join("-")) : "");
    try { if (sessionStorage.getItem(key) === "1") return; } catch (e) {}

    var critical = a.allZero || a.broken.length > 0;
    var bg = critical ? "#DC0028" : "#B45309";      // ERGO-Rot bzw. Bernstein
    var msgs = [];

    if (a.allZero) {
      msgs.push("Der letzte LLM-Lauf (Snapshot vom " + fmtDate(a.snapDate) +
        ") enthaelt fuer ALLE Anbieter 0 Nennungen — der Lauf ist vermutlich fehlgeschlagen. Bitte GitHub-Actions-Lauf pruefen.");
    } else if (a.broken.length) {
      a.broken.forEach(function (l) {
        var name = LLM_NAMES[l] || l;
        var hint = LLM_HINT[l] || "API-Key & Guthaben pruefen";
        msgs.push(name + " liefert keine Daten (0 Nennungen im Lauf vom " + fmtDate(a.snapDate) +
          "). Wahrscheinlich API-Guthaben aufgebraucht oder Key/Modell ungueltig. → " + hint + ".");
      });
    }
    if (a.stale && !a.allZero) {
      msgs.push("Die LLM-Daten sind " + (a.ageDays !== null ? a.ageDays + " Tage" : "sehr") +
        " alt (Snapshot vom " + fmtDate(a.snapDate) + "). Der GEO-Crawl laeuft " + CRAWL_TAKT +
        " — bei diesem Alter ist mindestens ein Lauf ausgefallen. Bitte den GitHub-Actions-Lauf im GEO-Repo pruefen.");
    }
    (a.carried || []).forEach(function (c) {
      var name = LLM_NAMES[c.llm] || c.llm;
      msgs.push(name + " hat in diesem Lauf keine eigenen Daten geliefert — angezeigt wird der " +
        "fortgeschriebene Stand" + (c.von ? (" vom " + fmtDate(parseDate(c.von))) : " des letzten Laufs") +
        ". Typische Ursache: API-Guthaben aufgebraucht. → " + (LLM_HINT[c.llm] || "API-Key & Guthaben pruefen") + ".");
    });

    var bar = document.createElement("div");
    bar.setAttribute("role", "alert");
    bar.style.cssText = "position:sticky;top:0;left:0;right:0;z-index:99999;background:" + bg +
      ";color:#fff;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;" +
      "box-shadow:0 2px 8px rgba(0,0,0,.25);padding:10px 44px 10px 16px;font-size:13.5px;line-height:1.45;";

    var inner = "<strong style=\"font-weight:700\">" + (critical ? "⚠️ Datenpipeline-Warnung" : (a.stale ? "⏳ Daten veraltet" : "⚠️ Hinweis zur Datenqualität")) +
      "</strong> &nbsp;" + msgs.map(function (m) {
        return "<span style=\"display:inline-block;margin:2px 10px 2px 0\">" + m + "</span>";
      }).join("");
    bar.innerHTML = inner;

    var x = document.createElement("button");
    x.textContent = "✕";
    x.title = "Ausblenden";
    x.style.cssText = "position:absolute;top:6px;right:10px;background:transparent;border:0;color:#fff;" +
      "font-size:16px;cursor:pointer;line-height:1;padding:4px;width:auto;margin:0;box-shadow:none;text-transform:none;letter-spacing:normal;";
    x.onclick = function () {
      try { sessionStorage.setItem(key, "1"); } catch (e) {}
      bar.parentNode && bar.parentNode.removeChild(bar);
    };
    bar.appendChild(x);

    document.body.insertBefore(bar, document.body.firstChild);
  }

  ready(function () {
    fetch(SNAP_URL + "?t=" + Date.now(), { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (g) {
        if (!g) return;
        // Fix 18.07.2026: dashboard_v3 deklariert GEO_SNAPSHOT als top-level
        // `let` — das landet NICHT auf window. Die Runtime-Module (Uebersicht,
        // Empfehlungen, Peec-Vergleich, Korrelation Block 3, Themen-Hotspots)
        // lesen aber window.GEO_SNAPSHOT und blieben im echten Browser leer
        // (jsdom-Tests setzten window direkt — daher dort gruen). Da dieses
        // Modul dieselbe Datei ohnehin laedt, wird sie hier gespiegelt.
        if (!window.GEO_SNAPSHOT) window.GEO_SNAPSHOT = g;
        render(analyze(g));
      })
      .catch(function () { /* still: kein falscher Alarm bei Netzfehler */ });
  });
})();

/* Loader (15.07.2026): Navigations-Redesign nachladen — health_banner.js ist
   auf allen Dashboard-Varianten eingebunden, so braucht es keinen Template-Edit. */
(function(){ try{ var s=document.createElement("script"); s.src="nav_redesign.js?t="+Date.now(); document.body.appendChild(s); }catch(e){} })();

/* Loader (13.08.2026): SOHO-Reiter (kleine Gewerbe) nachladen. Gleicher Weg und
   aus demselben Grund — dashboard_template.html hat 13,3 MB und laesst sich
   ueber den Konnektor nicht schreiben; ein Runtime-Modul haengt sich den Reiter
   selbst an und kommt ohne Template-Edit aus. */
(function(){ try{ var s=document.createElement("script"); s.src="soho_tab.js?t="+Date.now(); document.body.appendChild(s); }catch(e){} })();
