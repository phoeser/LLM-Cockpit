#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Einmalige Messung: Wie viele Posts hat Google je Marke und Woche wirklich?

Warum es diese Messung gibt (20.08.2026, Pauls Befund)
------------------------------------------------------
Beide Social-Sammler liefern je Marke exakt 10 Posts. Das ist keine Zaehlung,
sondern eine Obergrenze: Google hat den Parameter num=100 im September 2025
abgeschaltet, seither sind 10 Treffer je Suche das Maximum. Der Sammler fragt
weiterhin num=100 ab - es wird ignoriert.

Mehr geht nur ueber Blaettern (start=10, 20, ...), und JEDE Seite ist bei
SerpAPI eine eigene, kostenpflichtige Suche. Ob sich das lohnt, haengt an
einer Zahl, die wir nicht kennen: Verpassen wir je Marke und Woche zwei Posts
oder zweihundert?

Genau diese Zahl misst dieses Skript - einmalig, mit hartem Budget, ohne die
Sammlung zu veraendern. Es schreibt NICHT in linkedin_posts.jsonl,
instagram_posts.jsonl oder events.jsonl. Es entsteht nur ein Bericht.

Budget
------
MAX_SUCHEN begrenzt den Lauf hart. Ueberschrittene Kombinationen werden im
Bericht als "nicht gemessen" ausgewiesen - nicht stillschweigend weggelassen.

Abbruch nach oben: Liefert eine Seite weniger als 10 Treffer, ist Googles
Vorrat erschoepft; weitere Seiten waeren verschenktes Geld und werden
uebersprungen. Genau dieser Fall ist die gute Nachricht - dann kennen wir die
echte Gesamtzahl.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BERICHT = Path("data/serp_depth_report.md")

MARKEN = [
    ("ERGO",       '"ERGO" Versicherung'),
    ("Allianz",    '"Allianz" Versicherung'),
]
PLATTFORMEN = [
    ("LinkedIn",  "site:linkedin.com/posts", r"^/posts/"),
    ("Instagram", "site:instagram.com/p",    r"^/(p|reel)/"),
]
SEITEN = 4          # start=0,10,20,30
MAX_SUCHEN = 16     # hartes Budget: 2 Marken x 2 Plattformen x 4 Seiten
FENSTER = "qdr:w"   # dasselbe Fenster, in dem die Sammler im Regelbetrieb laufen


def kanon(u):
    return (u or "").split("?")[0].split("#")[0].rstrip("/")


def passt(url, host_teil, pfad_muster):
    try:
        p = urllib.parse.urlparse(url)
        if p.scheme != "https":
            return False
        wirt = host_teil.split(":")[1].split("/")[0]          # linkedin.com bzw. instagram.com
        if not (p.netloc == wirt or p.netloc.endswith("." + wirt)):
            return False
        return bool(re.match(pfad_muster, p.path))
    except Exception:
        return False


def suche(query, key, start):
    q = urllib.parse.urlencode({
        "engine": "google", "q": query, "hl": "de", "gl": "de",
        "lr": "lang_de",            # deutschsprachig - macht die 10 Plaetze wertvoller
        "filter": "0", "start": str(start), "tbs": FENSTER,
        "api_key": key,
    })
    req = urllib.request.Request("https://serpapi.com/search.json?" + q,
                                 headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    key = os.environ.get("SERPAPI_KEY", "").strip()
    if not key:
        print("[Tiefentest] Kein SERPAPI_KEY gesetzt - abgebrochen.")
        return 1

    heute = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    verbraucht = 0
    zeilen, roh = [], []

    for pname, site, pfad in PLATTFORMEN:
        for marke, teil in MARKEN:
            urls, seiten_info, erschoepft, fehler = set(), [], False, None
            for i in range(SEITEN):
                if verbraucht >= MAX_SUCHEN:
                    seiten_info.append("Budget")
                    break
                try:
                    res = suche("%s %s" % (site, teil), key, i * 10)
                    verbraucht += 1
                except Exception as e:
                    fehler = str(e)[:80]
                    break
                err = res.get("error")
                if err and "any results" not in str(err):
                    fehler = str(err)[:80]
                    break
                treffer = [t for t in (res.get("organic_results") or [])
                           if passt(kanon(t.get("link")), site, pfad)]
                alle = len(res.get("organic_results") or [])
                for t in treffer:
                    urls.add(kanon(t.get("link")))
                seiten_info.append("%d" % alle)
                if alle < 10:
                    erschoepft = True
                    break
            zeilen.append({
                "plattform": pname, "marke": marke,
                "seiten": seiten_info, "eindeutig": len(urls),
                "erschoepft": erschoepft, "fehler": fehler,
            })
            print("[Tiefentest] %-10s %-10s Seiten=%s -> %d eindeutige Posts%s%s"
                  % (pname, marke, "/".join(seiten_info), len(urls),
                     "  (Vorrat erschoepft)" if erschoepft else "",
                     "  FEHLER: %s" % fehler if fehler else ""))
            roh.append(sorted(urls))

    b = ["# Tiefentest der Social-Sammler", "",
         "Gemessen: %s | Fenster: letzte Woche (%s) | Suchen verbraucht: **%d**"
         % (heute, FENSTER, verbraucht), "",
         "Frage: Wie viele oeffentliche Posts hat Google je Marke und Woche wirklich -",
         "und wie viele davon sehen wir mit der heutigen Einstellung (1 Seite = 10)?", "",
         "| Plattform | Marke | Treffer je Seite | eindeutige Posts | heute erfasst | Vorrat |",
         "|---|---|---|---|---|---|"]
    for z in zeilen:
        vorrat = ("vollstaendig" if z["erschoepft"]
                  else ("FEHLER" if z["fehler"] else "weitere Seiten vorhanden"))
        # "heute erfasst" ist nicht pauschal 10: hat eine Marke weniger, sehen wir
        # auch heute schon alles. Pauschal 10 zu schreiben wuerde eine Luecke
        # behaupten, die es dort nicht gibt.
        heute_erfasst = min(10, z["eindeutig"])
        b.append("| %s | %s | %s | **%d** | %d | %s |"
                 % (z["plattform"], z["marke"], "/".join(z["seiten"]) or "-",
                    z["eindeutig"], heute_erfasst, vorrat))
    b += ["",
          "**Lesehilfe:** \"Vorrat erschoepft\" heisst, Google hat nicht mehr - die Zahl",
          "in *eindeutige Posts* ist dann die echte Gesamtzahl der Woche. Steht dort",
          "*weitere Seiten vorhanden*, ist auch diese Zahl noch eine Untergrenze.", "",
          "Eindeutige Posts zaehlt nur echte Beitrags-URLs der jeweiligen Plattform;",
          "Profil- und Fremdtreffer sind herausgerechnet.", ""]
    BERICHT.parent.mkdir(parents=True, exist_ok=True)
    BERICHT.write_text("\n".join(b), encoding="utf-8")
    print("[Tiefentest] Bericht geschrieben: %s (%d Suchen verbraucht)" % (BERICHT, verbraucht))
    return 0


if __name__ == "__main__":
    sys.exit(main())
