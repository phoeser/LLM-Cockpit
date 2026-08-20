#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Seitentiefe der Social-Sammler auf Pauls Entscheidung bringen (20.08.2026).

Ausgangslage: Beide Sammler blaettern derzeit bis zu FUENF Seiten fuer ALLE
zehn Marken. Im Vollausbau waeren das rund 433 SerpAPI-Suchen im Monat - das
freie Kontingent liegt bei 250.

Pauls Entscheidung nach dem gemessenen Tiefentest: "im freien Kontingent
bleiben". Also gestaffelt statt pauschal:

  ERGO, Allianz, AXA, HUK-Coburg   4 Seiten   (bis 40 Posts je Marke)
  die uebrigen sechs Marken        1 Seite
  harte Notbremse                  25 Suchen je Lauf und Plattform

Rechnung: 4x4 + 6x1 = 22 je Lauf und Plattform, beide Plattformen woechentlich
= rund 190 Suchen im Monat. Bleibt im freien Kontingent.

Warum gerade diese vier Marken Tiefe bekommen: Der Tiefentest hat gezeigt, wo
die Kappung wehtut. ERGO hatte auf LinkedIn neun Posts in der Woche - Vorrat
erschoepft, wir hatten alle. Allianz mindestens 37 bei zehn erfassten. Die
Untererfassung trifft die grossen Wettbewerber, also ausgerechnet die Zellen,
aus denen der Markenvergleich seine Aussage zieht.

Eigenschaften: idempotent, bricht laut ab, wenn eine Textstelle nicht genau
einmal passt, und schreibt nur bei gueltigem Python-Ergebnis.
"""
import ast
import sys
from pathlib import Path

ALT_KONSTANTEN = '''#   SEITEN_MAX        hoechstens fuenf Seiten je Marke (= 50 Treffer)
#   frueher Abbruch   eine nicht volle Seite heisst: mehr gibt es nicht.
#                     Das kostet nichts und spart in ruhigen Wochen fast alles.
SEITEN_MAX = 5
TREFFER_JE_SEITE = 10   # Googles feste Seitengroesse, seit num=100 weg ist'''

NEU_KONSTANTEN = '''#   Seiten je Marke   gestaffelt (siehe unten)
#   frueher Abbruch   eine nicht volle Seite heisst: mehr gibt es nicht.
#                     Das kostet nichts und spart in ruhigen Wochen fast alles.
#   BUDGET_JE_LAUF    harte Obergrenze, damit kein Fehler das Kontingent leert.
#
# 20.08.2026, Pauls Entscheidung nach dem gemessenen Tiefentest ("im freien
# Kontingent bleiben"): Fuenf Seiten fuer alle zehn Marken waeren bis zu 433
# Suchen im Monat - das freie Kontingent liegt bei 250. Also gestaffelt.
#
# Der Tiefentest vom 20.08. hat auch gezeigt, WO die Kappung wehtut: ERGO hatte
# auf LinkedIn neun Posts in der Woche (Vorrat erschoepft, wir hatten alle),
# Allianz mindestens 37 bei nur zehn erfassten. Die Untererfassung trifft also
# die grossen Wettbewerber - genau die Zellen, aus denen der Markenvergleich
# seine Aussage zieht. Deshalb bekommen die Kern-Marken Tiefe, der Rest bleibt
# bei einer Seite und wird im Reiter als moeglicherweise gekappt ausgewiesen.
KERN_MARKEN = ("ERGO", "Allianz", "AXA", "HUK-Coburg")
SEITEN_KERN = 4          # 4 Marken x 4 Seiten = 16
SEITEN_UEBRIGE = 1       # 6 Marken x 1 Seite  =  6   -> 22 je Lauf und Plattform
BUDGET_JE_LAUF = 25      # Notbremse: nie mehr als das, egal was passiert
TREFFER_JE_SEITE = 10   # Googles feste Seitengroesse, seit num=100 weg ist


def seiten_fuer(brand):
    """Wie tief wird fuer diese Marke geblaettert?"""
    return SEITEN_KERN if brand in KERN_MARKEN else SEITEN_UEBRIGE'''

ALT_LR = '''        "filter": "0",   # Googles Aehnlichkeits-Ausduennung aus; wirkt weiterhin
        "start": str(start),'''

NEU_LR = '''        "filter": "0",   # Googles Aehnlichkeits-Ausduennung aus; wirkt weiterhin
        # 20.08.2026: deutschsprachig einschraenken. Im Tiefentest gemessen -
        # ohne diese Grenze gingen Plaetze an gleichnamige Treffer aus anderen
        # Maerkten (Allianz Parque, Sao Paulo; Allianz Life, USA). Bei zehn
        # Plaetzen je Seite ist jeder davon zu teuer fuer ein Fussballstadion.
        # Preis der Regel: ein deutscher Absender, der englisch postet, faellt
        # heraus. Das ist bei einem Deutschland-Vergleich der bessere Fehler.
        "lr": "lang_de",
        "start": str(start),'''

GEKAPPT_ZEILE = '\n    gekappt = []   # Marken, bei denen Google noch mehr gehabt haette'

GEMEINSAM = [
    ("Gestaffelte Seitentiefe + Budget", ALT_KONSTANTEN, NEU_KONSTANTEN),
    ("Deutschsprachig einschraenken", ALT_LR, NEU_LR),
    ("Standardtiefe der Blaetter-Funktion",
     "def serpapi(query, key, fenster, max_seiten=SEITEN_MAX):",
     "def serpapi(query, key, fenster, max_seiten=SEITEN_KERN):"),
    ("Liste der gekappten Marken (Instagram)",
     "    neu, fehler, fehler_texte, n_weg = [], 0, [], 0",
     "    neu, fehler, fehler_texte, n_weg = [], 0, [], 0" + GEKAPPT_ZEILE),
    ("Liste der gekappten Marken (LinkedIn)",
     "    neu, fehler, fehler_texte = [], 0, []",
     "    neu, fehler, fehler_texte = [], 0, []" + GEKAPPT_ZEILE),
    ("Gekappte Marken in den State",
     '"suchen": n_suchen, "fehler": fehler,',
     '''"suchen": n_suchen, "fehler": fehler,
                                     # Marken, bei denen die Ausbeute die
                                     # erlaubte Tiefe voll ausschoepfte - dort
                                     # haette Google mehr gehabt. Der Reiter
                                     # weist diese Zahlen als Untergrenze aus.
                                     "gekappt": sorted(set(gekappt)),'''),
]


def schleife(site, tag):
    """Budget-Notbremse und Kappungs-Erkennung - je Datei eigener Suchstring."""
    alt = ('            treffer, fehlertext, seiten = serpapi("%s %%s" %% query, key, fenster)\n'
           '            n_suchen += seiten' % site)
    neu = ('''            # Budget-Notbremse: schon Verbrauchtes plus die tiefste moegliche
            # Abfrage dieser Marke darf BUDGET_JE_LAUF nicht sprengen. Lieber
            # eine Marke ohne Tiefe als ein leergeraeumtes Kontingent.
            tiefe = seiten_fuer(brand)
            if n_suchen + tiefe > BUDGET_JE_LAUF:
                tiefe = max(0, BUDGET_JE_LAUF - n_suchen)
            if tiefe < 1:
                print("[%s] %%s: Budget von %%d Suchen erreicht - uebersprungen."
                      %% (brand, BUDGET_JE_LAUF))
                gekappt.append(brand)
                continue
            treffer, fehlertext, seiten = serpapi("%s %%s" %% query, key, fenster,
                                                  max_seiten=tiefe)
            n_suchen += seiten
            # Volle Ausbeute bei ausgeschoepfter Tiefe heisst: da war noch mehr.
            if seiten >= tiefe and len(treffer) >= tiefe * TREFFER_JE_SEITE:
                gekappt.append(brand)''' % (tag, site))
    return ("Budget-Notbremse und Kappungs-Erkennung (%s)" % tag, alt, neu)


JE_DATEI = {
    "scripts/update_linkedin.py": [schleife("site:linkedin.com/posts", "LinkedIn")],
    "scripts/update_instagram.py": [schleife("site:instagram.com/p", "Instagram")],
}


def main():
    fertig = 0
    for pfad, eigene in JE_DATEI.items():
        p = Path(pfad)
        if not p.exists():
            print("FEHLER: %s nicht gefunden." % pfad)
            return 1
        s = p.read_text(encoding="utf-8")
        if "BUDGET_JE_LAUF" in s:
            print("[Patch] %s: bereits angewandt." % pfad)
            fertig += 1
            continue
        for beschreibung, alt, neu in GEMEINSAM + eigene:
            n = s.count(alt)
            if n == 0 and beschreibung.startswith("Liste der gekappten"):
                continue          # die beiden Varianten schliessen einander aus
            if n != 1:
                print("FEHLER in %s bei '%s': %d Treffer (erwartet 1) - nichts geaendert."
                      % (pfad, beschreibung, n))
                return 1
            s = s.replace(alt, neu, 1)
        try:
            ast.parse(s)
        except SyntaxError as e:
            print("FEHLER: %s waere kein gueltiges Python (%s) - nichts geschrieben." % (pfad, e))
            return 1
        p.write_text(s, encoding="utf-8")
        print("[Patch] %s angepasst." % pfad)
    if fertig == len(JE_DATEI):
        print("[Patch] Nichts zu tun.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
