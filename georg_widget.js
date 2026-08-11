/* ============================================================
   GEOrg — Sprach-Agent auf dem Dashboard (11.08.2026)

   Blendet den ElevenLabs-Gespraechsagenten als Schaltflaeche unten rechts ein,
   auf allen Reitern. Die Wissensbasis ist data/geo_faktenblatt.md, das der
   Nightly erzeugt und scripts/georg_sync.py hochlaedt.

   Warum das ueber eine Konfigurationsdatei laeuft und nicht fest verdrahtet ist:
   Solange in data/georg.json keine Agenten-ID steht, passiert hier gar nichts -
   kein Skript wird nachgeladen, keine Schaltflaeche erscheint, keine Verbindung
   nach aussen. Damit kann dieser Code ausgeliefert werden, bevor entschieden
   ist, ob der Agent ueberhaupt kommt. Ein Schalter statt eines spaeteren
   Eingriffs in den Code.

   Zur Absicherung: Die Agenten-ID steht zwangslaeufig im ausgelieferten HTML,
   das laesst sich nicht vermeiden. Der Schutz liegt deshalb auf der Gegenseite -
   in der ElevenLabs-Konfiguration wird eine Hostname-Allowlist mit genau
   phoeser.github.io hinterlegt. Der Agent antwortet dann nur, wenn die Anfrage
   von dieser Seite kommt.
   ============================================================ */
(function () {
  "use strict";

  var GELADEN = false;

  function mounten(cfg) {
    if (GELADEN || !cfg || !cfg.agent_id || cfg.aktiv === false) return;
    GELADEN = true;

    // Hinweiszeile ueber dem Widget: GEOrg antwortet aus dem Faktenblatt vom
    // letzten Nightly, nicht aus den Live-Daten dieser Seite. Wer das nicht
    // weiss, haelt eine Abweichung fuer einen Fehler.
    var hinweis = document.createElement("div");
    hinweis.id = "georgHinweis";
    hinweis.style.cssText =
      "position:fixed;right:16px;bottom:96px;max-width:250px;z-index:2147483000;" +
      "background:#fff;border:1px solid #e5e7eb;border-left:3px solid #dc0028;" +
      "border-radius:8px;padding:8px 11px;font-size:11px;line-height:1.45;color:#4b5563;" +
      "box-shadow:0 2px 10px rgba(0,0,0,.08)";
    hinweis.innerHTML =
      '<b style="color:#1a1a2e">GEOrg</b> beantwortet Fragen zu diesen Daten. ' +
      "Er kennt den Stand des letzten Nightly" +
      (cfg.stand ? " (" + String(cfg.stand).slice(0, 10) + ")" : "") +
      " — nicht mehr und nicht weniger. " +
      '<span style="color:#9ca3af">Antworten sind maschinell erzeugt; bei Zahlen gilt das Dashboard.</span>' +
      '<button onclick="document.getElementById(\'georgHinweis\').remove()" ' +
      'style="display:block;margin-top:5px;font-size:10px;color:#9ca3af;background:none;' +
      'border:none;padding:0;cursor:pointer">ausblenden</button>';

    var widget = document.createElement("elevenlabs-convai");
    widget.setAttribute("agent-id", cfg.agent_id);

    var s = document.createElement("script");
    s.src = "https://unpkg.com/@elevenlabs/convai-widget-embed";
    s.async = true;
    s.type = "text/javascript";
    // Laedt der Anbieter nicht, bleibt die Seite unveraendert - der Hinweis
    // waere dann eine Schaltflaeche ohne Funktion und verschwindet mit.
    s.onerror = function () {
      var h = document.getElementById("georgHinweis");
      if (h) h.remove();
      try { widget.remove(); } catch (e) {}
      console.warn("GEOrg: Widget-Skript nicht erreichbar — Dashboard laeuft unveraendert weiter.");
    };

    document.body.appendChild(widget);
    document.body.appendChild(hinweis);
    document.body.appendChild(s);
  }

  function start() {
    fetch("data/georg.json", { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; })
      .then(function (cfg) {
        if (!cfg || !cfg.agent_id) return;   // stillschweigend nichts tun
        mounten(cfg);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
