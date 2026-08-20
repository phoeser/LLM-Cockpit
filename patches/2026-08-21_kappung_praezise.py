#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kappungs-Erkennung praezise machen (21.08.2026).

Der Fehler, den der erste echte Lauf sichtbar gemacht hat
---------------------------------------------------------
Lauf #507 holte fuer Allianz auf LinkedIn 37 Treffer aus vier von vier
erlaubten Seiten. Meine bisherige Regel fragte "ist die Ausbeute so gross wie
die erlaubte Tiefe mal zehn?" - also 37 >= 40. Antwort: nein. Damit galt
Allianz als vollstaendig erfasst, obwohl das Seitenbudget aufgebraucht war.

Die Luecke entsteht durch das Dedup ueber Seitengrenzen hinweg: Google liefert
auf spaeteren Seiten gern einzelne Wiederholungen, die herausfallen. Vier volle
Seiten ergeben deshalb oft 36-39 statt 40 eindeutige Treffer.

Die Frage war schlicht falsch gestellt. Es kommt nicht auf die Trefferzahl an,
sondern darauf, WARUM das Blaettern endete:

  Google hatte nichts mehr     -> vollstaendig
  unser Seitenbudget war leer  -> Untergrenze

Also gibt serpapi() das jetzt selbst zurueck ("erschoepft"), statt dass die
Schleife es aus der Trefferzahl erraet.

Wirkung: Allianz, Generali, Signal Iduna und DEVK werden im Reiter kuenftig
korrekt mit vorangestelltem Groesser-Gleich gefuehrt; ERGO, AXA, HUK-Coburg,
R+V, Hannoversche und CosmosDirekt stehen als vollstaendig da, weil bei ihnen
tatsaechlich Google am Ende war.

Idempotent; bricht laut ab, wenn eine Textstelle nicht genau einmal passt.
"""
import ast
import sys
from pathlib import Path

DOC_ALT = '''    """Blaettert bis zu max_seiten durch.
    -> (treffer, fehlertext_oder_None, anzahl_suchen)'''

DOC_NEU = '''    """Blaettert bis zu max_seiten durch.
    -> (treffer, fehlertext_oder_None, anzahl_suchen, erschoepft)

    "erschoepft" beantwortet die Frage, auf die es fuer die Anzeige ankommt:
    Haben wir aufgehoert, weil GOOGLE nichts mehr hatte (True), oder weil
    unser Seitenbudget zu Ende war (False)? Nur im zweiten Fall ist die Zahl
    eine Untergrenze. Vorher wurde das aus der Trefferzahl geschaetzt
    ("volle Ausbeute = gekappt") - das ging schief, sobald das Dedup ueber
    die Seiten hinweg ein paar Wiederholungen entfernte: Allianz kam am
    20.08. mit 37 statt 40 Treffern zurueck und galt damit faelschlich als
    vollstaendig, obwohl vier von vier erlaubten Seiten voll waren.'''

INIT_ALT = "    alle, gesehen, anzahl_suchen = [], set(), 0"
INIT_NEU = "    alle, gesehen, anzahl_suchen = [], set(), 0\n    erschoepft = False"

FEHLER_ALT = '''            if "any results" in str(fehlertext):
                break
            return alle, str(fehlertext), anzahl_suchen'''
FEHLER_NEU = '''            if "any results" in str(fehlertext):
                erschoepft = True
                break
            return alle, str(fehlertext), anzahl_suchen, erschoepft'''

ENDE_ALT = '''        if len(seite) < TREFFER_JE_SEITE or not frisch:
            break
    return alle, None, anzahl_suchen'''
ENDE_NEU = '''        if len(seite) < TREFFER_JE_SEITE or not frisch:
            erschoepft = True
            break
    return alle, None, anzahl_suchen, erschoepft'''


def aufruf(site):
    alt = '''            treffer, fehlertext, seiten = serpapi("%s %%s" %% query, key, fenster,
                                                  max_seiten=tiefe)
            n_suchen += seiten
            # Volle Ausbeute bei ausgeschoepfter Tiefe heisst: da war noch mehr.
            if seiten >= tiefe and len(treffer) >= tiefe * TREFFER_JE_SEITE:
                gekappt.append(brand)''' % site
    neu = '''            treffer, fehlertext, seiten, erschoepft = serpapi(
                "%s %%s" %% query, key, fenster, max_seiten=tiefe)
            n_suchen += seiten
            # Gekappt heisst: nicht Google war am Ende, sondern unser Budget.
            if not erschoepft:
                gekappt.append(brand)''' % site
    return ("Aufruf und Kappungs-Regel", alt, neu)


JE_DATEI = {
    "scripts/update_linkedin.py": aufruf("site:linkedin.com/posts"),
    "scripts/update_instagram.py": aufruf("site:instagram.com/p"),
}

GEMEINSAM = [
    ("Rueckgabe dokumentieren", DOC_ALT, DOC_NEU),
    ("Merker anlegen", INIT_ALT, INIT_NEU),
    ("Fehlerpfad", FEHLER_ALT, FEHLER_NEU),
    ("Regulaeres Ende", ENDE_ALT, ENDE_NEU),
]


def main():
    fertig = 0
    for pfad, eigen in JE_DATEI.items():
        p = Path(pfad)
        if not p.exists():
            print("FEHLER: %s nicht gefunden." % pfad)
            return 1
        s = p.read_text(encoding="utf-8")
        # Marker muss eindeutig sein: das Wort "erschoepft" steht schon in
        # bestehenden Kommentaren ("Vorrat erschoepft").
        if "if not erschoepft:" in s:
            print("[Patch] %s: bereits angewandt." % pfad)
            fertig += 1
            continue
        for beschreibung, alt, neu in GEMEINSAM + [eigen]:
            n = s.count(alt)
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
