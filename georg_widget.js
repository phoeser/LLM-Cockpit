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

    /* 12.08.2026 ENTFERNT (Wunsch Paul): Hier stand eine kleine Hinweiskarte
       ueber dem Widget - "GEOrg kennt den Stand des letzten Nightly ...".
       Sie stand dauerhaft im Bild und wiederholte, was GEOrg im Gespraech
       ohnehin sagt: sein Systemprompt weist ihn an, den Stand zu nennen, wenn
       jemand nach Aktualitaet fragt oder eine Zahl abweicht. Der Vorbehalt
       geht also nicht verloren, er steht nur nicht mehr staendig da.
       Derselbe Text liegt zusaetzlich im Zustimmungshinweis des Widgets
       (platform_settings.widget.terms_text). */
    var widget = document.createElement("elevenlabs-convai");
    widget.setAttribute("agent-id", cfg.agent_id);

    var s = document.createElement("script");
    s.src = "https://unpkg.com/@elevenlabs/convai-widget-embed";
    s.async = true;
    s.type = "text/javascript";
    // Laedt der Anbieter nicht, bleibt die Seite unveraendert - der Hinweis
    // waere dann eine Schaltflaeche ohne Funktion und verschwindet mit.
    s.onerror = function () {
      try { widget.remove(); } catch (e) {}
      console.warn("GEOrg: Widget-Skript nicht erreichbar — Dashboard laeuft unveraendert weiter.");
    };

    document.body.appendChild(widget);
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
