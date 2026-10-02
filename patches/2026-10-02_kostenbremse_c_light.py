#!/usr/bin/env python3
"""Patch 02.10.2026: Kostenbremse "C-light" (Entscheidung Paul 01.10.2026).

1. Anzeige: geo_wirkung.js, korrelation_upgrade.js, geo_doku_tab.js, geo_faktenblatt.py -
   der eigene Crawl fragt ab dem Lauf 05./06.10. nur noch ChatGPT ohne Websuche ab.
   Fehlt Gemini im Snapshot, sagen die Bloecke das, statt "nicht ladbar".
2. update_sentiment.py: Wochenlauf im Montags-Nightly (Korrektur der Bremse vom 26.09.).
3. correlation_impact.py: Strukturbruch 2026-10-05 registriert.
4. sov_history.jsonl / level_cells_history.jsonl: Lauf 29.09. mit behobener
   Fortschreibung neu gerechnet (ERGO gesamt 8,83 -> 13,1 Prozent).
Idempotent je Teil (Signatur des neuen Texts bzw. Pruefsumme der alten Zeilen).
Bricht ein Teil ab, bleibt die betroffene Datei unveraendert.
"""
import hashlib, json, sys

SIG = {"geo_wirkung.js": "function ownGroundedAus()", "korrelation_upgrade.js": "function ownGroundedAus()", "geo_doku_tab.js": "8 (ERGO + 7 Wettbewerber", "scripts/geo_faktenblatt.py": "Seit dem 05.10.2026 fragt der eigene Crawl", "scripts/update_sentiment.py": "jetzt.weekday() == 0", "scripts/correlation_impact.py": "\"date\": \"2026-10-05\""}

PAARE = [
    ("geo_wirkung.js",
r'''      '<span style="font-size:10.5px;color:'+MUTE+'">Peec: Gemini, Perplexity, AI&nbsp;Overview, AI&nbsp;Mode = grounded · ChatGPT = UI. Eigener Crawl: Gemini = grounded · ChatGPT = UI.</span></div>';
''',
r'''      '<span style="font-size:10.5px;color:'+MUTE+'">Peec: Gemini, AI&nbsp;Overview, AI&nbsp;Mode = grounded (Perplexity bis 15.06.2026) · ChatGPT = UI. Eigener Crawl: ChatGPT = UI; Gemini (grounded) nur bis 29.09.2026.</span></div>';
'''),
    ("geo_wirkung.js",
r'''  }
  function chanLbl(){ return gwMode==="g"?"Grounded (Web-Suche)":(gwMode==="u"?"UI / ChatGPT":"Alle Engines"); }
''',
r'''  }
  /* 02.10.2026: Kostenbremse (Entscheidung Paul). Der eigene Crawl fragt ab dem Lauf
     vom 05./06.10.2026 nur noch ChatGPT ohne Websuche ab; Gemini und Perplexity sind aus.
     Grounded misst danach nur noch Peec. Liegt ein Snapshot vor, in dem Gemini fehlt,
     ist "keine Daten" kein Ladefehler, sondern Absicht - das wird so gesagt. */
  function ownGroundedAus(){
    try{ var g=snapData(); var L=(g&&g.llms)||null; if(!L||!L.length) return false;
         return L.indexOf("gemini")<0 && L.indexOf("perplexity")<0; }catch(e){ return false; }
  }
  var OWN_AUS_TXT="<b>Eigener Crawl ohne Websuche-Kanal</b> — seit 05.10.2026 fragt der eigene Crawl nur noch ChatGPT ohne Websuche ab (Kostenbremse). Den grounded-Kanal misst nur noch Peec. Keine Ersatz-Nullen.";
  function chanLbl(){ return gwMode==="g"?"Grounded (Web-Suche)":(gwMode==="u"?"UI / ChatGPT":"Alle Engines"); }
'''),
    ("geo_wirkung.js",
r'''             : "<b>Eigener Crawl (geo_snapshot.json) fuer diesen Kanal nicht ladbar</b> — erscheint nach Reload. Keine Ersatz-Null.",
''',
r'''             : ((gwMode!=="u" && ownGroundedAus() && gwMode==="g") ? OWN_AUS_TXT : "<b>Eigener Crawl (geo_snapshot.json) fuer diesen Kanal nicht ladbar</b> — erscheint nach Reload. Keine Ersatz-Null."),
'''),
    ("geo_wirkung.js",
r'''    if(!od){ return '<div id="gwBBox" style="border:1px solid '+LINE+';border-radius:11px;padding:14px 16px;font-size:12px;color:'+MUTE+'"><b>Eigener Crawl nicht ladbar</b> — Themen-Detail erscheint nach Reload. Keine Ersatz-Nullen.</div>'; }
''',
r'''    if(!od){ return '<div id="gwBBox" style="border:1px solid '+LINE+';border-radius:11px;padding:14px 16px;font-size:12px;color:'+MUTE+'">'+((gwMode==="g"&&ownGroundedAus())?OWN_AUS_TXT:'<b>Eigener Crawl nicht ladbar</b> — Themen-Detail erscheint nach Reload. Keine Ersatz-Nullen.')+'</div>'; }
'''),
    ("geo_wirkung.js",
r'''    if(!C||!od){ return '<div id="gwCBox" style="border:1px solid '+LINE+';border-radius:11px;padding:14px 16px;font-size:12px;color:'+MUTE+'"><b>Kreuz-Matrix benoetigt eigenen Crawl und Peec-Themenliste</b> — erscheint nach Reload. Keine Ersatz-Nullen.</div>'; }
''',
r'''    if(!C||!od){ return '<div id="gwCBox" style="border:1px solid '+LINE+';border-radius:11px;padding:14px 16px;font-size:12px;color:'+MUTE+'">'+((!od&&gwMode==="g"&&ownGroundedAus())?OWN_AUS_TXT:'<b>Kreuz-Matrix benoetigt eigenen Crawl und Peec-Themenliste</b> — erscheint nach Reload. Keine Ersatz-Nullen.')+'</div>'; }
'''),
    ("korrelation_upgrade.js",
r'''  }
  function b3ModeLbl(){ return b3Mode==="g"?"grounded (Web-Suche)":(b3Mode==="u"?"UI / ungrounded (ChatGPT)":"alle Engines"); }
''',
r'''  }
  /* 02.10.2026: Kostenbremse (Entscheidung Paul). Der eigene Crawl fragt ab dem Lauf
     vom 05./06.10.2026 nur noch ChatGPT ohne Websuche ab; Gemini und Perplexity sind aus.
     Grounded misst danach nur noch Peec. Liegt ein Snapshot vor, in dem Gemini fehlt,
     ist "keine Daten" kein Ladefehler, sondern Absicht - das wird so gesagt. */
  function ownGroundedAus(){
    try{ var g=snapData(); var L=(g&&g.llms)||null; if(!L||!L.length) return false;
         return L.indexOf("gemini")<0 && L.indexOf("perplexity")<0; }catch(e){ return false; }
  }
  var OWN_AUS_TXT="<b>Eigener Crawl ohne Websuche-Kanal</b> — seit 05.10.2026 fragt der eigene Crawl nur noch ChatGPT ohne Websuche ab (Kostenbremse). Den grounded-Kanal misst nur noch Peec. Keine Ersatz-Nullen.";
  function b3ModeLbl(){ return b3Mode==="g"?"grounded (Web-Suche)":(b3Mode==="u"?"UI / ungrounded (ChatGPT)":"alle Engines"); }
'''),
    ("korrelation_upgrade.js",
r'''      '<span style="font-size:10.5px;color:#9ca3af">Peec: Gemini, Perplexity, AI Overview, AI Mode = grounded · ChatGPT = UI. Eigener Crawl: Gemini = grounded · ChatGPT = ungrounded.</span></div>';
''',
r'''      '<span style="font-size:10.5px;color:#9ca3af">Peec: Gemini, AI Overview, AI Mode = grounded (Perplexity bis 15.06.2026) · ChatGPT = UI. Eigener Crawl: ChatGPT = ungrounded; Gemini (grounded) nur bis 29.09.2026.</span></div>';
'''),
    ("korrelation_upgrade.js",
r'''    var own=ownSov(b3Mode);
    if(!own){
''',
r'''    var own=ownSov(b3Mode);
    if(!own && b3Mode==="g" && ownGroundedAus()){
      box.innerHTML=b3Btns()+'<div style="font-size:12px;color:#9ca3af">'+OWN_AUS_TXT+'</div>'; b3Wire(box); return;
    }
    if(!own){
'''),
    ("korrelation_upgrade.js",
r'''      var srcTxt = b3Mode==="g" ? "<b>Peec</b> (grounded: Gemini, Perplexity, AI Overview, AI Mode) gegen <b>eigenen Crawl</b> (Gemini-API, grounded)"
''',
r'''      var srcTxt = b3Mode==="g" ? "<b>Peec</b> (grounded: Gemini, AI Overview, AI Mode) gegen <b>eigenen Crawl</b> (Gemini-API, grounded)"
'''),
    ("korrelation_upgrade.js",
r'''                                 : "<b>Peec</b> (alle Engines) gegen <b>eigenen Crawl</b> (Mittel aus Gemini und ChatGPT)");
''',
r'''                                 : "<b>Peec</b> (alle Engines) gegen <b>eigenen Crawl</b> ("+(ownGroundedAus()?"seit 05.10.2026 nur ChatGPT":"Mittel aus Gemini und ChatGPT")+")");
'''),
    ("geo_doku_tab.js",
r'''        ['<b>Peec AI</b> (fuehrend)','Primaerquelle LLM-Sichtbarkeit',num(R.P.n_brands,0),'5 (inkl. Google AI Overview / AI Mode)','UI-Scraping, woechentlich'],
        ['Eigener API-Crawl','Backup & Konsistenzpruefung','25','3 (Gemini und Perplexity mit Websuche, ChatGPT ohne)','eigene API, woechentlich (seit 10.08.2026)']
''',
r'''        ['<b>Peec AI</b> (fuehrend)','Primaerquelle LLM-Sichtbarkeit',num(R.P.n_brands,0),'4: ChatGPT, Gemini, AI Overview, AI Mode (Perplexity bis 15.06.2026)','UI-Scraping, woechentlich'],
        ['Eigener API-Crawl','Backup & Konsistenzpruefung','8 (ERGO + 7 Wettbewerber, seit 13.08.2026)','1: ChatGPT ohne Websuche (bis 29.09.2026 zusaetzlich Gemini und Perplexity mit Websuche)','eigene API, woechentlich (seit 10.08.2026); Websuche-Engines seit 05.10.2026 aus (Kostenbremse)']
'''),
    ("scripts/geo_faktenblatt.py",
r'''        "Gegenprobe und Auditgrundlage.\n"
    )
    t.append(
        "Die beiden Quellen kommen bei den absoluten Niveaus zu deutlich verschiedenen Werten. "
''',
r'''        "Gegenprobe und Auditgrundlage.\n"
    )
    # 02.10.2026: Kostenbremse (Entscheidung Paul) - der eigene Crawl fragt ab dem Lauf
    # vom 05./06.10.2026 nur noch ChatGPT ohne Websuche ab.
    t.append(
        "Seit dem 05.10.2026 fragt der eigene Crawl aus Kostengruenden nur noch ChatGPT ohne "
        "Websuche ab. Den Kanal mit Websuche (Gemini, Google AI Overview, AI Mode) misst seither "
        "nur noch der kommerzielle Dienst; Perplexity misst keine der beiden Quellen mehr. Die "
        "Gegenprobe gibt es damit nur noch im Kanal ohne Websuche, fuer den Kanal mit Websuche "
        "reicht sie bis zum Lauf vom 29.09.2026.\n"
    )
    t.append(
        "Die beiden Quellen kommen bei den absoluten Niveaus zu deutlich verschiedenen Werten. "
'''),
    ("scripts/update_sentiment.py",
r'''def _nur_woechentlich_ueberspringen():
    """Kostenbremse (26.09.2026, Entscheidung Paul): woechentlich statt taeglich.

    Google Places und Gemini liefen hier fuer 27 Marken JEDEN Tag. Die
    Sichtbarkeit wird aber nur woechentlich gemessen - taegliche Bewertungs-
    Ereignisse bringen der Auswertung kaum etwas und kosten 30x im Monat.

    Der woechentliche Lauf ist der Montags-Lauf von "Weekly Check24 Prices &
    Reviews" (der ruft dieses Skript ohnehin im Wochenlauf auf). Der taegliche
    Nightly ueberspringt deshalb, AUSSER:
      - er wurde von Hand gestartet (workflow_dispatch), oder
      - die letzte Auswertung (as_of) ist aelter als 7 Tage - Sicherheitsnetz,
        falls der Montagslauf ausfiel. Der Pipeline-Waechter meldet erst ab 9.
    Erzwingen: SENTIMENT_ERZWINGEN=1

    ACHTUNG fuer die Auswertung: Ab diesem Tag entstehen review_change /
    review_volume-Ereignisse woechentlich (kumuliert) statt taeglich. Das ist
    ein Regimewechsel in der Ereigniszahl, kein Messbruch der Sichtbarkeit.
    """
    if os.environ.get("SENTIMENT_ERZWINGEN") == "1":
        return False
    if os.environ.get("GITHUB_EVENT_NAME") != "schedule":
        return False
    if "Nightly" not in os.environ.get("GITHUB_WORKFLOW", ""):
        return False
    try:
        pfad = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "sentiment_dashboard.json")
        with open(pfad, "r", encoding="utf-8") as f:
            stand = json.load(f).get("as_of", "")
        alter = (datetime.now(timezone.utc).date() - datetime.strptime(stand, "%Y-%m-%d").date()).days
    except Exception:
        return False  # kein lesbarer Stand -> lieber laufen
    if alter > 7:
        print("Sicherheitsnetz: Stimmungsdaten sind %d Tage alt - Lauf wird ausgefuehrt." % alter)
        return False
    print("Kostenbremse: Stimmungs-Auswertung laeuft woechentlich (Montag, Preis-Workflow). "
          "Letzte Auswertung vor %d Tagen - Nightly ueberspringt." % alter)
    return True


''',
r'''def _nur_woechentlich_ueberspringen():
    """Kostenbremse (26.09.2026, Entscheidung Paul): woechentlich statt taeglich.

    Google Places und Gemini liefen hier fuer 27 Marken JEDEN Tag. Die
    Sichtbarkeit wird aber nur woechentlich gemessen - taegliche Bewertungs-
    Ereignisse bringen der Auswertung kaum etwas und kosten 30x im Monat.

    02.10.2026, Korrektur: Der woechentliche Lauf ist jetzt der MONTAGS-NIGHTLY,
    nicht mehr der Preis-Workflow. Grund (Pruefung 29.09.): Dieses Skript
    schreibt die Dashboard-Werte in dashboard_template.html; der Preis-Workflow
    committet aber nur data/ und shared/ - die Template-Aenderung ging verloren,
    das Dashboard blieb auf dem alten Stand, und das Sicherheitsnetz liess den
    Nightly zusaetzlich laufen (rund 8 statt 4 Laeufe im Monat).

    Regeln fuer geplante Laeufe:
      - Nightly: laeuft montags (UTC). An anderen Tagen nur, wenn die letzte
        Auswertung (as_of) aelter als 7 Tage ist - Sicherheitsnetz, falls der
        Montagslauf ausfiel. Der Pipeline-Waechter meldet erst ab 9.
      - Jeder andere geplante Workflow (z. B. "Weekly Check24 Prices &
        Reviews"): ueberspringt immer - sonst doppelte Kosten am Montag.
    Handstart (workflow_dispatch) laeuft immer. Erzwingen: SENTIMENT_ERZWINGEN=1

    ACHTUNG fuer die Auswertung: Ab 27.09. entstehen review_change /
    review_volume-Ereignisse woechentlich (kumuliert) statt taeglich. Das ist
    ein Regimewechsel in der Ereigniszahl, kein Messbruch der Sichtbarkeit.
    """
    if os.environ.get("SENTIMENT_ERZWINGEN") == "1":
        return False
    if os.environ.get("GITHUB_EVENT_NAME") != "schedule":
        return False
    if "Nightly" not in os.environ.get("GITHUB_WORKFLOW", ""):
        print("Kostenbremse: Stimmungs-Auswertung laeuft im Montags-Nightly - "
              "dieser Workflow ueberspringt.")
        return True
    jetzt = datetime.now(timezone.utc)
    if jetzt.weekday() == 0:
        print("Kostenbremse: Montag - woechentliche Stimmungs-Auswertung laeuft.")
        return False
    try:
        pfad = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "sentiment_dashboard.json")
        with open(pfad, "r", encoding="utf-8") as f:
            stand = json.load(f).get("as_of", "")
        alter = (jetzt.date() - datetime.strptime(stand, "%Y-%m-%d").date()).days
    except Exception:
        return False  # kein lesbarer Stand -> lieber laufen
    if alter > 7:
        print("Sicherheitsnetz: Stimmungsdaten sind %d Tage alt - Lauf wird ausgefuehrt." % alter)
        return False
    print("Kostenbremse: Stimmungs-Auswertung laeuft montags im Nightly. "
          "Letzte Auswertung vor %d Tagen - heute uebersprungen." % alter)
    return True


'''),
    ("scripts/correlation_impact.py",
r''']


def _spans_break(brand, start_day, end_day):''',
r'''    # ---- 02.10.2026: Kostenbremse (Entscheidung Paul). Gemini und Perplexity im
    # eigenen Crawl abgeschaltet; grounded misst danach nur noch Peec.
    {
        "brand": "*",
        "date": "2026-10-05",
        "grund": ("Eigener Crawl ab dem Lauf vom 05./06.10.2026 nur noch mit ChatGPT ohne "
                  "Websuche (Gemini und Perplexity abgeschaltet, Kostenbremse, Entscheidung "
                  "Paul 01.10.). Der Gesamt-SoV des eigenen Crawls ist ab hier der "
                  "ChatGPT-Wert allein, vorher das Mittel aus drei Engines: ERGO am 29.09. "
                  "gesamt 13,1 %, ChatGPT allein 9,6 %. Der grounded-Kanal des eigenen "
                  "Crawls endet mit dem Lauf vom 29.09. (Perplexity dort bereits "
                  "fortgeschrieben vom 22.09.)."),
        "nachrechenbar": True,
        "warum_nicht": ("Rueckwaerts vergleichbar ist die ChatGPT-Reihe (sov_history "
                        "source=snapshot_llm, llm=chatgpt; level_cells sov_u): sie laeuft "
                        "ueber das Datum hinweg unveraendert weiter. Gesamt- und grounded-"
                        "Werte sind ueber das Datum nicht vergleichbar."),
    },
]


def _spans_break(brand, start_day, end_day):'''),
]

fehler = 0
dateien = {}
for pfad, a, n in PAARE:
    dateien.setdefault(pfad, []).append((a, n))
for pfad, paare in dateien.items():
    s = open(pfad, encoding="utf-8").read()
    if SIG[pfad] in s:
        print("SKIP: " + pfad + " bereits angewendet"); continue
    ok = True
    for a, n in paare:
        if s.count(a) != 1:
            print("ABBRUCH: " + pfad + " - Ankertext " + str(s.count(a)) + "x statt 1x, Datei unveraendert."); fehler = 1; ok = False; break
        s = s.replace(a, n)
    if ok:
        open(pfad, "w", encoding="utf-8").write(s); print("OK: " + pfad)

# --- 4. Lauf 29.09. in der Historie richtigstellen ---
K = json.loads(r'''{"sov_sha":"9d54fa31ce976b302d7e62410d591ff11dade3a60193ea365c6718f8f46bc168","sov":[["snapshot","Allianz","",{"sov_pct":33.78}],["snapshot","HUK-Coburg","",{"sov_pct":23.53}],["snapshot","AXA","",{"sov_pct":11.56}],["snapshot","ERGO","",{"sov_pct":13.1,"avg_rank":6.85}],["snapshot","Signal Iduna","",{"sov_pct":6.75}],["snapshot","CosmosDirekt","",{"sov_pct":5.69}],["snapshot","DKV","",{"sov_pct":3.49}],["snapshot","Generali","",{"sov_pct":2.09}],["snapshot_llm","Allianz","perplexity",{"sov_pct":33.86}],["snapshot_llm","HUK-Coburg","perplexity",{"sov_pct":20.4}],["snapshot_llm","DKV","perplexity",{"sov_pct":6.02}],["snapshot_llm","Signal Iduna","perplexity",{"sov_pct":6.76}],["snapshot_llm","AXA","perplexity",{"sov_pct":9.43}],["snapshot_llm","CosmosDirekt","perplexity",{"sov_pct":6.93}],["snapshot_llm","Generali","perplexity",{"sov_pct":2.05}],["snapshot_product","ERGO","zahnzusatz",{"sov_pct":20.37}],["snapshot_product","Allianz","zahnzusatz",{"sov_pct":38.46}],["snapshot_product","HUK-Coburg","zahnzusatz",{"sov_pct":19.13}],["snapshot_product","AXA","zahnzusatz",{"sov_pct":4.37}],["snapshot_product","Signal Iduna","zahnzusatz",{"sov_pct":12.06}],["snapshot_product","DKV","zahnzusatz",{"sov_pct":4.99}],["snapshot_product","Generali","zahnzusatz",{"sov_pct":0.21}],["snapshot_product","CosmosDirekt","zahnzusatz",{"sov_pct":0.42}],["snapshot_product","Allianz","sterbegeld",{"sov_pct":39.52}],["snapshot_product","ERGO","sterbegeld",{"sov_pct":19.52}],["snapshot_product","CosmosDirekt","sterbegeld",{"sov_pct":9.29}],["snapshot_product","HUK-Coburg","sterbegeld",{"sov_pct":15.71}],["snapshot_product","Signal Iduna","sterbegeld",{"sov_pct":11.9}],["snapshot_product","AXA","sterbegeld",{"sov_pct":2.14}],["snapshot_product","Generali","sterbegeld",{"sov_pct":1.19}],["snapshot_product","DKV","sterbegeld",{"sov_pct":0.71}],["snapshot_product","Allianz","risikoleben",{"sov_pct":29.04}],["snapshot_product","HUK-Coburg","risikoleben",{"sov_pct":25.36}],["snapshot_product","CosmosDirekt","risikoleben",{"sov_pct":14.52}],["snapshot_product","ERGO","risikoleben",{"sov_pct":15.13}],["snapshot_product","AXA","risikoleben",{"sov_pct":5.73}],["snapshot_product","Signal Iduna","risikoleben",{"sov_pct":4.7}],["snapshot_product","Generali","risikoleben",{"sov_pct":5.11}],["snapshot_product","DKV","risikoleben",{"sov_pct":0.41}],["snapshot_product","Allianz","berufsunfaehigkeit",{"sov_pct":37.01}],["snapshot_product","HUK-Coburg","berufsunfaehigkeit",{"sov_pct":20.47}],["snapshot_product","CosmosDirekt","berufsunfaehigkeit",{"sov_pct":7.61}],["snapshot_product","AXA","berufsunfaehigkeit",{"sov_pct":6.3}],["snapshot_product","ERGO","berufsunfaehigkeit",{"sov_pct":13.91}],["snapshot_product","Signal Iduna","berufsunfaehigkeit",{"sov_pct":9.45}],["snapshot_product","Generali","berufsunfaehigkeit",{"sov_pct":5.25}],["snapshot_product","ERGO","reise",{"sov_pct":29.72}],["snapshot_product","Allianz","reise",{"sov_pct":31.3}],["snapshot_product","HUK-Coburg","reise",{"sov_pct":13.78}],["snapshot_product","AXA","reise",{"sov_pct":8.86}],["snapshot_product","Signal Iduna","reise",{"sov_pct":4.92}],["snapshot_product","DKV","reise",{"sov_pct":9.84}],["snapshot_product","Generali","reise",{"sov_pct":0.98}],["snapshot_product","CosmosDirekt","reise",{"sov_pct":0.59}],["snapshot_product","Allianz","rechtsschutz",{"sov_pct":45.81}],["snapshot_product","HUK-Coburg","rechtsschutz",{"sov_pct":37.43}],["snapshot_product","AXA","rechtsschutz",{"sov_pct":6.59}],["snapshot_product","ERGO","rechtsschutz",{"sov_pct":7.19}],["snapshot_product","Signal Iduna","rechtsschutz",{"sov_pct":2.4}],["snapshot_product","CosmosDirekt","rechtsschutz",{"sov_pct":0.6}],["snapshot_product","HUK-Coburg","haftpflicht",{"sov_pct":28.02}],["snapshot_product","Allianz","haftpflicht",{"sov_pct":29.75}],["snapshot_product","AXA","haftpflicht",{"sov_pct":23.03}],["snapshot_product","CosmosDirekt","haftpflicht",{"sov_pct":7.1}],["snapshot_product","ERGO","haftpflicht",{"sov_pct":6.14}],["snapshot_product","Signal Iduna","haftpflicht",{"sov_pct":3.84}],["snapshot_product","Generali","haftpflicht",{"sov_pct":2.11}],["snapshot_product","HUK-Coburg","hausrat",{"sov_pct":31.88}],["snapshot_product","Allianz","hausrat",{"sov_pct":30.05}],["snapshot_product","AXA","hausrat",{"sov_pct":20.64}],["snapshot_product","CosmosDirekt","hausrat",{"sov_pct":8.94}],["snapshot_product","ERGO","hausrat",{"sov_pct":4.36}],["snapshot_product","Signal Iduna","hausrat",{"sov_pct":2.98}],["snapshot_product","Generali","hausrat",{"sov_pct":1.15}],["snapshot_product","HUK-Coburg","kfz",{"sov_pct":32.74}],["snapshot_product","Allianz","kfz",{"sov_pct":34.35}],["snapshot_product","CosmosDirekt","kfz",{"sov_pct":9.47}],["snapshot_product","AXA","kfz",{"sov_pct":12.84}],["snapshot_product","ERGO","kfz",{"sov_pct":5.94}],["snapshot_product","Generali","kfz",{"sov_pct":2.57}],["snapshot_product","Signal Iduna","kfz",{"sov_pct":2.09}],["snapshot_product","Allianz","unfall",{"sov_pct":30.13}],["snapshot_product","HUK-Coburg","unfall",{"sov_pct":25.89}],["snapshot_product","CosmosDirekt","unfall",{"sov_pct":6.7}],["snapshot_product","ERGO","unfall",{"sov_pct":14.29}],["snapshot_product","AXA","unfall",{"sov_pct":13.39}],["snapshot_product","Signal Iduna","unfall",{"sov_pct":6.25}],["snapshot_product","Generali","unfall",{"sov_pct":3.12}],["snapshot_product","DKV","unfall",{"sov_pct":0.22}],["snapshot_product","DKV","krankenhauszusatz",{"sov_pct":21.22}],["snapshot_product","AXA","krankenhauszusatz",{"sov_pct":13.19}],["snapshot_product","HUK-Coburg","krankenhauszusatz",{"sov_pct":18.16}],["snapshot_product","Allianz","krankenhauszusatz",{"sov_pct":21.8}],["snapshot_product","ERGO","krankenhauszusatz",{"sov_pct":10.52}],["snapshot_product","Signal Iduna","krankenhauszusatz",{"sov_pct":13.58}],["snapshot_product","Generali","krankenhauszusatz",{"sov_pct":1.53}],["snapshot_product","Allianz","betriebshaftpflicht",{"sov_pct":51.72}],["snapshot_product","Signal Iduna","betriebshaftpflicht",{"sov_pct":11.03}],["snapshot_product","AXA","betriebshaftpflicht",{"sov_pct":24.83}],["snapshot_product","ERGO","betriebshaftpflicht",{"sov_pct":6.21}],["snapshot_product","Generali","betriebshaftpflicht",{"sov_pct":2.07}],["snapshot_product","HUK-Coburg","betriebshaftpflicht",{"sov_pct":4.14}],["snapshot_product","Allianz","firmenrechtsschutz",{"sov_pct":48.72}],["snapshot_product","ERGO","firmenrechtsschutz",{"sov_pct":11.54}],["snapshot_product","AXA","firmenrechtsschutz",{"sov_pct":17.95}],["snapshot_product","HUK-Coburg","firmenrechtsschutz",{"sov_pct":16.03}],["snapshot_product","Signal Iduna","firmenrechtsschutz",{"sov_pct":5.13}],["snapshot_product","Generali","firmenrechtsschutz",{"sov_pct":0.64}]],"sov_neu":["{\"date\": \"2026-09-29\", \"brand\": \"ERGO\", \"llm\": \"perplexity\", \"sov_pct\": 14.55, \"avg_rank\": null, \"source\": \"snapshot_llm\"}"],"cells_sha":"fd1ec0e377ed0787fcdbd6033a032b5ffa74f865f1c539b070420d4f10e5c41d","cells":[["AXA","zahnzusatz",{"sov_g":5.62,"sov_c":4.01}],["DKV","zahnzusatz",{"sov_g":6.85,"sov_c":4.5667}],["CosmosDirekt","zahnzusatz",{"sov_g":0.58,"sov_c":0.3867}],["Allianz","zahnzusatz",{"sov_g":37.105,"sov_c":39.0233}],["Signal Iduna","zahnzusatz",{"sov_g":7.115,"sov_c":13.4733}],["ERGO","zahnzusatz",{"sov_g":27.005,"sov_c":18.2667}],["HUK-Coburg","zahnzusatz",{"sov_g":15.45,"sov_c":20.09}],["CosmosDirekt","sterbegeld",{"sov_g":14.015,"sov_c":9.77}],["Signal Iduna","sterbegeld",{"sov_g":4.165,"sov_c":11.11}],["ERGO","sterbegeld",{"sov_g":26.895,"sov_c":20.28}],["HUK-Coburg","sterbegeld",{"sov_g":9.47,"sov_c":15.0733}],["AXA","sterbegeld",{"sov_g":1.52,"sov_c":2.0833}],["Allianz","sterbegeld",{"sov_g":43.94,"sov_c":39.9767}],["CosmosDirekt","risikoleben",{"sov_g":18.575,"sov_c":14.41}],["Signal Iduna","risikoleben",{"sov_g":5.715,"sov_c":5.4667}],["Generali","risikoleben",{"sov_g":1.86,"sov_c":4.9233}],["ERGO","risikoleben",{"sov_g":14.79,"sov_c":15.7533}],["HUK-Coburg","risikoleben",{"sov_g":25.815,"sov_c":25.3133}],["AXA","risikoleben",{"sov_g":4.2,"sov_c":5.1933}],["Allianz","risikoleben",{"sov_g":28.545,"sov_c":28.6067}],["CosmosDirekt","berufsunfaehigkeit",{"sov_g":11.085,"sov_c":8.0933}],["AXA","berufsunfaehigkeit",{"sov_g":9.515,"sov_c":6.5767}],["Allianz","berufsunfaehigkeit",{"sov_g":40.88,"sov_c":37.5833}],["Signal Iduna","berufsunfaehigkeit",{"sov_g":7.375,"sov_c":9.1433}],["Generali","berufsunfaehigkeit",{"sov_g":4.99,"sov_c":5.2033}],["ERGO","berufsunfaehigkeit",{"sov_g":8.54,"sov_c":13.2067}],["HUK-Coburg","berufsunfaehigkeit",{"sov_g":17.615,"sov_c":20.1933}],["AXA","reise",{"sov_g":10.665,"sov_c":7.72}],["DKV","reise",{"sov_g":11.905,"sov_c":7.9367}],["CosmosDirekt","reise",{"sov_g":0.74,"sov_c":0.4933}],["Allianz","reise",{"sov_g":25.66,"sov_c":34.5367}],["Signal Iduna","reise",{"sov_g":6.2,"sov_c":4.1333}],["Generali","reise",{"sov_g":1.24,"sov_c":0.8267}],["ERGO","reise",{"sov_g":26.135,"sov_c":32.1033}],["HUK-Coburg","reise",{"sov_g":17.45,"sov_c":12.2433}],["Signal Iduna","rechtsschutz",{"sov_g":2.85,"sov_c":2.4167}],["ERGO","rechtsschutz",{"sov_g":11.865,"sov_c":8.4267}],["HUK-Coburg","rechtsschutz",{"sov_g":34.675,"sov_c":37.5867}],["AXA","rechtsschutz",{"sov_g":5.67,"sov_c":6.1067}],["Allianz","rechtsschutz",{"sov_g":44.135,"sov_c":44.9267}],["CosmosDirekt","haftpflicht",{"sov_g":9.865,"sov_c":6.7867}],["Signal Iduna","haftpflicht",{"sov_g":4.39,"sov_c":3.76}],["Generali","haftpflicht",{"sov_g":2.455,"sov_c":2.0533}],["ERGO","haftpflicht",{"sov_g":6.93,"sov_c":6.0767}],["HUK-Coburg","haftpflicht",{"sov_g":28.315,"sov_c":28.0433}],["AXA","haftpflicht",{"sov_g":20.095,"sov_c":23.3967}],["Allianz","haftpflicht",{"sov_g":27.95,"sov_c":29.8833}],["CosmosDirekt","hausrat",{"sov_g":13.62,"sov_c":9.08}],["Signal Iduna","hausrat",{"sov_g":4.255,"sov_c":3.06}],["Generali","hausrat",{"sov_g":1.77,"sov_c":1.18}],["ERGO","hausrat",{"sov_g":4.855,"sov_c":4.3467}],["HUK-Coburg","hausrat",{"sov_g":32.08,"sov_c":31.83}],["AXA","hausrat",{"sov_g":14.69,"sov_c":20.46}],["Allianz","hausrat",{"sov_g":28.73,"sov_c":30.0433}],["CosmosDirekt","kfz",{"sov_g":12.435,"sov_c":8.29}],["Signal Iduna","kfz",{"sov_g":1.84,"sov_c":2.0933}],["Generali","kfz",{"sov_g":1.72,"sov_c":2.8767}],["ERGO","kfz",{"sov_g":7.625,"sov_c":5.3}],["HUK-Coburg","kfz",{"sov_g":33.755,"sov_c":32.6767}],["AXA","kfz",{"sov_g":8.435,"sov_c":14.4967}],["Allianz","kfz",{"sov_g":34.2,"sov_c":34.2733}],["CosmosDirekt","unfall",{"sov_g":11.705,"sov_c":7.8033}],["Signal Iduna","unfall",{"sov_g":6.325,"sov_c":6.2667}],["Generali","unfall",{"sov_g":2.81,"sov_c":3.07}],["ERGO","unfall",{"sov_g":15.07,"sov_c":14.49}],["HUK-Coburg","unfall",{"sov_g":25.695,"sov_c":25.8467}],["AXA","unfall",{"sov_g":6.73,"sov_c":11.8367}],["Allianz","unfall",{"sov_g":31.275,"sov_c":30.4233}],["DKV","krankenhauszusatz",{"sov_g":28.77,"sov_c":19.4133}],["AXA","krankenhauszusatz",{"sov_g":17.065,"sov_c":12.08}],["Allianz","krankenhauszusatz",{"sov_g":16.97,"sov_c":23.2867}],["Signal Iduna","krankenhauszusatz",{"sov_g":8.87,"sov_c":14.8333}],["Generali","krankenhauszusatz",{"sov_g":1.92,"sov_c":1.28}],["ERGO","krankenhauszusatz",{"sov_g":14.6,"sov_c":9.9667}],["HUK-Coburg","krankenhauszusatz",{"sov_g":11.8,"sov_c":19.1333}],["AXA","betriebshaftpflicht",{"sov_g":11.38,"sov_c":21.9533}],["Allianz","betriebshaftpflicht",{"sov_g":56.995,"sov_c":53.5133}],["Signal Iduna","betriebshaftpflicht",{"sov_g":17.29,"sov_c":12.1}],["Generali","betriebshaftpflicht",{"sov_g":5.13,"sov_c":3.42}],["ERGO","betriebshaftpflicht",{"sov_g":8.425,"sov_c":5.6167}],["AXA","firmenrechtsschutz",{"sov_g":15.955,"sov_c":17.68}],["Allianz","firmenrechtsschutz",{"sov_g":51.085,"sov_c":49.55}],["Signal Iduna","firmenrechtsschutz",{"sov_g":9.19,"sov_c":6.1267}],["ERGO","firmenrechtsschutz",{"sov_g":18.13,"sov_c":13.9633}]]}''')

def schluessel(r):
    return (r["source"], r["brand"], r.get("llm") or r.get("product") or "")

def korrigiere(pfad, sha, aendern, neu_zeilen, k, erledigt):
    zeilen = open(pfad, encoding="utf-8").read().split("\n")
    tag = [i for i, l in enumerate(zeilen) if l.startswith('{"date": "2026-09-29"')]
    alt = [zeilen[i] for i in tag]
    if any(erledigt in l for l in alt):
        print("SKIP: " + pfad + " bereits korrigiert"); return 0
    if hashlib.sha256("\n".join(alt).encode("utf-8")).hexdigest() != sha:
        print("ABBRUCH: " + pfad + " - Zeilen vom 29.09. weichen ab, nichts geaendert."); return 1
    if tag != list(range(tag[0], tag[-1] + 1)):
        print("ABBRUCH: " + pfad + " - Zeilen vom 29.09. nicht zusammenhaengend."); return 1
    neu = []
    for l in alt:
        r = json.loads(l)
        if k(r) in aendern:
            r.update(aendern[k(r)])
        neu.append(json.dumps(r, ensure_ascii=False))
    neu += neu_zeilen
    zeilen[tag[0]:tag[-1] + 1] = neu
    open(pfad, "w", encoding="utf-8").write("\n".join(zeilen))
    print("OK: " + pfad + " - " + str(len(alt)) + " Zeilen ersetzt durch " + str(len(neu)))
    return 0

fehler |= korrigiere("data/sov_history.jsonl", K["sov_sha"],
                     {(a, b, c): d for a, b, c, d in K["sov"]}, K["sov_neu"], schluessel,
                     '"brand": "ERGO", "llm": "perplexity"')
fehler |= korrigiere("data/level_cells_history.jsonl", K["cells_sha"],
                     {(a, b): d for a, b, d in K["cells"]}, [], lambda r: (r["brand"], r["topic"]),
                     '"brand": "ERGO", "topic": "zahnzusatz", "sov_g": 27.005')
sys.exit(fehler)
