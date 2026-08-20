#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Instagram-Unterstuetzung in scripts/correlation_impact.py nachtragen.

Warum dieser Umweg (20.08.2026)
-------------------------------
correlation_impact.py ist 300 KB gross, die noetige Aenderung umfasst 42
Zeilen. Der Auto-Deploy-Weg ueber den Browser scheiterte an genau dieser
Datei ("Failed to fetch"), waehrend acht kleinere Dateien desselben Laufs
durchgingen - der Engpass ist die Uebertragungsgroesse, nicht der Inhalt.

Also wird nicht die Datei transportiert, sondern die Aenderung: dieses
Skript (4 KB) geht ueber den Konnektor ins Repo, der Workflow
"apply-patch.yml" fuehrt es DORT aus, wo die grosse Datei ohnehin liegt,
und committet das Ergebnis. Uebertragen werden nie mehr als ein paar KB.

Eigenschaften, auf die es hier ankommt
-------------------------------------
- IDEMPOTENT: schon angewandt -> Exit 0, "nichts zu tun". Ein zweiter Lauf
  kann nichts kaputtmachen.
- LAUT bei Abweichung: passt eine Textstelle nicht mehr exakt (weil jemand
  anderes die Datei geaendert hat), bricht das Skript mit Exit 1 ab und
  nennt die Stelle. Nichts wird "so ungefaehr" ersetzt.
- Jede Ersetzung muss GENAU EINMAL passen - sonst Abbruch.
"""
import sys
from pathlib import Path

ZIEL = Path("scripts/correlation_impact.py")

# (Beschreibung, alt, neu) - Reihenfolge egal, jede Stelle muss genau einmal passen.
ERSETZUNGEN = [
    ("Erstimport-Filter verallgemeinern",
     'def _drop_linkedin_erstimport(events):\n    """LinkedIn-Erstimport je Marke aus den WIRKUNGS-Rechnungen nehmen.',
     'def _drop_social_erstimport(events, typ="linkedin_post", label="LinkedIn"):\n'
     '    """Social-Erstimport je Marke aus den WIRKUNGS-Rechnungen nehmen.\n\n'
     '    20.08.2026 verallgemeinert: dieselbe Mechanik gilt fuer Instagram, weil\n'
     '    der Instagram-Sammler nach demselben Muster arbeitet (Monatsfenster im\n'
     '    Erstlauf, Wochenfenster danach, Datum nur wenn Google eins liefert).\n'
     '    Der Aufrufer sagt, welcher Ereignistyp gemeint ist - die Regel selbst\n'
     '    ist unveraendert.'),
    ("Typ-Vergleich 1 parametrisieren",
     '        if e.get("event_type") != "linkedin_post":\n            continue\n        d_ = e.get("detail") or {}',
     '        if e.get("event_type") != typ:\n            continue\n        d_ = e.get("detail") or {}'),
    ("Typ-Vergleich 2 parametrisieren",
     '        if e.get("event_type") == "linkedin_post":\n            d_ = e.get("detail") or {}',
     '        if e.get("event_type") == typ:\n            d_ = e.get("detail") or {}'),
    ("Audit-Schluessel parametrisieren",
     '    EVENT_LOAD_AUDIT["linkedin_erstimport"] = {',
     '    EVENT_LOAD_AUDIT["%s_erstimport" % typ.split("_")[0]] = {'),
    ("Audit-Hinweis parametrisieren",
     '                    "Posts auf einen Fund-Tag komprimiert). Anzeige im LinkedIn-"\n'
     '                    "Reiter unberuehrt."),',
     '                    "Posts auf einen Fund-Tag komprimiert). Anzeige im %s-"\n'
     '                    "Reiter unberuehrt." % label),'),
    ("Log-Ausgabe parametrisieren",
     '        print("[LinkedIn-Erstimport] %d Events vom jeweils ersten Sammel-Tag aus den "\n'
     '              "Wirkungs-Rechnungen ausgeschlossen (Import-Artefakt)." % dropped)',
     '        print("[%s-Erstimport] %d Events vom jeweils ersten Sammel-Tag aus den "\n'
     '              "Wirkungs-Rechnungen ausgeschlossen (Import-Artefakt)." % (label, dropped))'),
    ("Aufruf: beide Plattformen",
     '    out = _drop_linkedin_erstimport(out)\n',
     '    out = _drop_social_erstimport(out, "linkedin_post", "LinkedIn")\n'
     '    out = _drop_social_erstimport(out, "instagram_post", "Instagram")\n'),
    ("instagram_post als Treibertyp",
     '    "page_change", "page_new", "page_removed", "press_mention", "news_mention",\n    "linkedin_post",',
     '    # 20.08.2026: "instagram_post" — oeffentliche Instagram-Beitraege je Marke\n'
     '    # (update_instagram.py, woechentlich via SerpAPI/Google). Anders als bei\n'
     '    # LinkedIn gibt es hier KEINE Engagement-Zahlen (Instagram liefert\n'
     '    # oeffentlich nur die Login-Huelle) — die Magnitude ist deshalb immer 1,0,\n'
     '    # ein Post ist ein Post.\n'
     '    "page_change", "page_new", "page_removed", "press_mention", "news_mention",\n'
     '    "linkedin_post", "instagram_post",'),
    ("Anzeigename",
     '    "linkedin_post": "LinkedIn-Posts",',
     '    "linkedin_post": "LinkedIn-Posts",\n    "instagram_post": "Instagram-Posts",'),
    ("Umdatierung auf Erscheinungstag",
     'MEDIA_DATED_TYPES = ("press_mention", "news_mention", "linkedin_post")',
     'MEDIA_DATED_TYPES = ("press_mention", "news_mention", "linkedin_post",\n'
     '                     "instagram_post")'),
    ("Inhalts-Dedup",
     '    if t in ("press_mention", "news_mention", "linkedin_post"):',
     '    if t in ("press_mention", "news_mention", "linkedin_post", "instagram_post"):'),
]


def main():
    if not ZIEL.exists():
        print("FEHLER: %s nicht gefunden - laeuft dieses Skript im Repo-Wurzelverzeichnis?" % ZIEL)
        return 1
    s = ZIEL.read_text(encoding="utf-8")
    if "instagram_post" in s and "_drop_social_erstimport" in s:
        print("[Patch] Bereits angewandt - nichts zu tun.")
        return 0
    for beschreibung, alt, neu in ERSETZUNGEN:
        n = s.count(alt)
        if n != 1:
            print("FEHLER bei '%s': Textstelle %d-mal gefunden (erwartet: genau 1). "
                  "Die Datei weicht vom erwarteten Stand ab - es wird NICHTS geaendert."
                  % (beschreibung, n))
            return 1
        s = s.replace(alt, neu, 1)
    # Sicherheitsnetz: nur schreiben, wenn das Ergebnis gueltiges Python ist.
    import ast
    try:
        ast.parse(s)
    except SyntaxError as e:
        print("FEHLER: Ergebnis waere kein gueltiges Python (%s) - nichts geschrieben." % e)
        return 1
    ZIEL.write_text(s, encoding="utf-8")
    print("[Patch] %d Stellen geaendert, %s ist wieder gueltiges Python." % (len(ERSETZUNGEN), ZIEL))
    return 0


if __name__ == "__main__":
    sys.exit(main())
