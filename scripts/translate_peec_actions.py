#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Peec-Empfehlungen ins Deutsche (12.08.2026)
============================================

Peec liefert seine Handlungsempfehlungen auf Englisch. In einem sonst
durchgaengig deutschen Cockpit stehen damit 37 Eintraege in einer Sprache, in
der man sie einem Fachbereich nicht weiterreichen kann. Dieses Skript
uebersetzt sie und schreibt das Ergebnis als `text_de` in die Items.

Zwei Entscheidungen, die den Aufbau erklaeren
---------------------------------------------
1. Cache statt Neuuebersetzung. `data/peec_actions_de.json` haelt die
   Uebersetzungen unter dem Hash des Originaltextes. Peecs Export wird
   regelmaessig komplett neu geschrieben (und laeuft als Cowork-Task, nicht im
   Nightly); ohne Cache wuerde jede Nacht alles neu uebersetzt - Kosten ohne
   Gegenwert und jedes Mal leicht andere Formulierungen. Mit Cache kostet ein
   Lauf ohne neue Empfehlungen exakt nichts.

2. Uebersetzen, nicht umschreiben. Die Texte sind Arbeitsanweisungen mit
   Links und Zitaten aus konkreten Wettbewerberseiten. Das Modell bekommt
   deshalb eine enge Anweisung: Inhalt und Markdown-Links unveraendert lassen,
   Eigennamen und deutsche Fachbegriffe nicht "zurueckuebersetzen", nichts
   hinzuerfinden. Eine Uebersetzung, die die Empfehlung verbessert, waere hier
   ein Fehler - der Fachbereich muss pruefen koennen, was Peec wirklich gesagt
   hat.

Faellt die Uebersetzung aus (kein Schluessel, API-Fehler), bleibt der englische
Text stehen und die Anzeige faellt darauf zurueck. Nie ein leeres Feld.

Aufruf:  GEMINI_API_KEY=<key> python3 scripts/translate_peec_actions.py
"""

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUELLE = os.path.join(BASIS, "data", "peec_actions.json")
CACHE = os.path.join(BASIS, "data", "peec_actions_de.json")

MODELL = "gemini-flash-latest"
ANWEISUNG = """Übersetze die folgende Handlungsempfehlung aus dem Englischen ins Deutsche.

Strenge Regeln:
- Übersetze, formuliere NICHT um. Keine Verbesserungen, keine Ergänzungen, keine Kürzungen.
- Markdown-Links vollständig unverändert lassen, inklusive Linktext und URL.
- Deutsche Begriffe und Eigennamen, die schon im Original stehen (Produktnamen,
  Markennamen, Seitentitel, Suchbegriffe in Anführungszeichen), bleiben exakt so stehen.
- Sprich den Leser mit "Sie" an, sachlich, wie eine Arbeitsanweisung.
- Antworte NUR mit der Übersetzung, ohne Vorrede und ohne Anführungszeichen drumherum.

Text:
"""


def hashe(t):
    return hashlib.sha1((t or "").encode("utf-8")).hexdigest()[:16]


def lade_cache():
    try:
        with open(CACHE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def uebersetze(text, key):
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           f"{MODELL}:generateContent?key={key}")
    payload = json.dumps({
        "contents": [{"parts": [{"text": ANWEISUNG + text}]}],
        "generationConfig": {
            # Niedrige Temperatur: es soll uebersetzt, nicht formuliert werden.
            "temperature": 0.1,
            # 12.08.2026: Hier standen 1200 Token, und die Haelfte der
            # Uebersetzungen kam abgeschnitten zurueck - 162 Zeichen fuer ein
            # Original von 327, mit finishReason MAX_TOKENS. Ursache:
            # gemini-flash-latest denkt vor der Antwort, und die Denk-Token
            # zaehlen gegen maxOutputTokens; fuer die Ausgabe blieb kaum etwas
            # uebrig. Ein Versuch, das Denken per thinkingConfig abzuschalten,
            # wird von dieser API-Version mit INVALID_ARGUMENT abgelehnt -
            # also stattdessen genug Budget fuer beides. Nebeneffekt: die
            # Uebersetzungen wurden auch fachlich besser (aus der
            # "Bestattungsversicherung" wurde die Sterbegeldversicherung).
            "maxOutputTokens": 4000,
        },
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.loads(r.read().decode("utf-8"))
    kand = (d.get("candidates") or [{}])[0]
    # Abgeschnittene Antworten sind schlimmer als gar keine: sie sehen
    # vollstaendig aus. Deshalb hier hart ausschliessen, nicht erst in der
    # Laengenpruefung darauf hoffen.
    if kand.get("finishReason") not in (None, "STOP"):
        raise RuntimeError(f"Antwort unvollstaendig (finishReason={kand.get('finishReason')})")
    out = kand.get("content", {}).get("parts", [{}])[0].get("text", "")
    return (out or "").strip()


def plausibel(orig, de):
    """Grobe Gegenpruefung. Eine Uebersetzung, die viel kuerzer ist als das
    Original oder noch identisch damit, ist keine - dann lieber das Englische
    stehen lassen als etwas Kaputtes anzeigen."""
    if not de or len(de) < 20:
        return False, "zu kurz"
    if de.strip() == orig.strip():
        return False, "unveraendert"
    if len(de) < 0.4 * len(orig):
        return False, f"auffaellig kurz ({len(de)} gegen {len(orig)} Zeichen)"
    # Alle Markdown-Links muessen mitgekommen sein.
    import re
    n_orig = len(re.findall(r"\]\(https?://", orig))
    n_de = len(re.findall(r"\]\(https?://", de))
    if n_orig != n_de:
        return False, f"Links verloren ({n_de} von {n_orig})"
    return True, ""


def main():
    key = (os.environ.get("GEMINI_API_KEY") or "").strip()

    try:
        with open(QUELLE, encoding="utf-8") as f:
            daten = json.load(f)
    except Exception as e:
        print(f"FEHLER: data/peec_actions.json nicht lesbar ({e}).", file=sys.stderr)
        return 1

    items = daten.get("items") or []
    if not items:
        print("Keine Peec-Empfehlungen vorhanden — nichts zu tun.")
        return 0

    cache = lade_cache()
    aus_cache = neu = fehler = 0

    for it in items:
        orig = it.get("text") or ""
        if not orig:
            continue
        h = hashe(orig)
        if h in cache:
            it["text_de"] = cache[h]
            aus_cache += 1
            continue
        if not key:
            fehler += 1
            continue
        try:
            de = uebersetze(orig, key)
            ok, grund = plausibel(orig, de)
            if not ok:
                print(f"  uebersprungen ({grund}): {orig[:60]}…")
                fehler += 1
                continue
            cache[h] = de
            it["text_de"] = de
            neu += 1
            time.sleep(0.15)  # dem Dienst Luft lassen
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code}: {e.read().decode('utf-8')[:200]}", file=sys.stderr)
            fehler += 1
        except Exception as e:
            print(f"  Fehler: {e}", file=sys.stderr)
            fehler += 1

    if not key and fehler:
        print(f"GEMINI_API_KEY nicht gesetzt — {fehler} Empfehlung(en) bleiben englisch. "
              "Das ist kein Abbruchgrund; die Anzeige faellt auf den Originaltext zurueck.")

    # Cache immer schreiben, auch bei Teilerfolg - jede einzelne Uebersetzung
    # soll erhalten bleiben.
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")

    with open(QUELLE, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Peec-Empfehlungen: {aus_cache} aus dem Cache, {neu} neu uebersetzt, "
          f"{fehler} ohne Uebersetzung. Cache umfasst jetzt {len(cache)} Eintraege.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
