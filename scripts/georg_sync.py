#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GEOrg-Wissensbasis aktualisieren (11.08.2026)
==============================================

Laedt data/geo_faktenblatt.md als Wissensbasis-Dokument zu ElevenLabs hoch und
haengt es an den Agenten. Laeuft am Ende des Nightly, damit GEOrg immer auf dem
Stand der letzten Nacht antwortet.

Wichtig zum Verhalten
---------------------
Ohne gesetzte Zugangsdaten passiert NICHTS und der Schritt endet mit Erfolg.
Das ist Absicht: Solange der Agent nicht existiert, soll der Nightly nicht
rot werden. Erst wenn beide Umgebungsvariablen gesetzt sind, wird gearbeitet.

  ELEVENLABS_API_KEY   Schluessel aus dem ElevenLabs-Konto
  GEORG_AGENT_ID       ID des angelegten Agenten

Ablauf
------
1. Faktenblatt lesen und auf Plausibilitaet pruefen.
2. Neues Dokument anlegen (POST /v1/convai/knowledge-base/text).
3. Agenten lesen, die Wissensbasis-Liste um das neue Dokument ergaenzen und die
   frueheren GEOrg-Faktenblaetter daraus entfernen (PATCH /v1/convai/agents/<id>).
4. Die abgeloesten Dokumente loeschen, damit sich im Konto keine Altlasten
   sammeln. Schlaegt das Loeschen fehl, ist das kein Fehler des Laufs - der
   Agent zeigt dann schon auf das neue Dokument.

Bewusst NICHT gemacht: das bestehende Dokument ueberschreiben. Ein
fehlgeschlagener Upload wuerde sonst die funktionierende Wissensbasis
beschaedigen. Neu anlegen, umhaengen, altes wegraeumen ist die sichere
Reihenfolge - dieselbe Logik wie bei den Datei-Pushes im Cockpit.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAKTEN = os.path.join(BASIS, "data", "geo_faktenblatt.md")
API = "https://api.elevenlabs.io"

# Am Namen erkennt der Lauf seine eigenen Altdokumente wieder.
PRAEFIX = "GEOrg Faktenblatt "
MIN_ZEICHEN = 4000


def ruf(pfad, key, methode="GET", koerper=None):
    daten = json.dumps(koerper).encode("utf-8") if koerper is not None else None
    req = urllib.request.Request(API + pfad, data=daten, method=methode)
    req.add_header("xi-api-key", key)
    if daten:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as r:
        roh = r.read().decode("utf-8")
    return json.loads(roh) if roh.strip() else {}


def main():
    key = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()
    agent = (os.environ.get("GEORG_AGENT_ID") or "").strip()
    if not key or not agent:
        print("GEOrg: keine Zugangsdaten gesetzt — Schritt uebersprungen. "
              "Das ist kein Fehler; der Agent ist noch nicht eingerichtet.")
        return 0

    if not os.path.exists(FAKTEN):
        print("FEHLER: data/geo_faktenblatt.md fehlt — erst geo_faktenblatt.py laufen lassen.",
              file=sys.stderr)
        return 1
    with open(FAKTEN, encoding="utf-8") as f:
        text = f.read()

    # Nie eine funktionierende Wissensbasis durch eine leere ersetzen.
    if len(text) < MIN_ZEICHEN:
        print(f"FEHLER: Faktenblatt nur {len(text)} Zeichen (Mindestmass {MIN_ZEICHEN}). "
              "Die bestehende Wissensbasis bleibt unveraendert.", file=sys.stderr)
        return 1

    stempel = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    name = PRAEFIX + stempel

    try:
        neu = ruf("/v1/convai/knowledge-base/text", key, "POST", {"text": text, "name": name})
    except urllib.error.HTTPError as e:
        print(f"FEHLER beim Anlegen des Dokuments: HTTP {e.code} — {e.read().decode('utf-8')[:400]}",
              file=sys.stderr)
        return 1
    neu_id = neu.get("id")
    if not neu_id:
        print(f"FEHLER: Antwort ohne Dokument-ID: {json.dumps(neu)[:300]}", file=sys.stderr)
        return 1
    print(f"GEOrg: Dokument angelegt — {name} ({len(text):,} Zeichen, ID {neu_id})".replace(",", "."))

    try:
        cfg = ruf(f"/v1/convai/agents/{agent}", key)
    except urllib.error.HTTPError as e:
        print(f"FEHLER beim Lesen des Agenten: HTTP {e.code} — {e.read().decode('utf-8')[:400]}",
              file=sys.stderr)
        return 1

    prompt = ((cfg.get("conversation_config") or {}).get("agent") or {}).get("prompt") or {}
    bisher = prompt.get("knowledge_base") or []
    # Fremde Dokumente bleiben unangetastet - nur die eigenen Altstaende weichen.
    alt_eigene = [d for d in bisher if str(d.get("name", "")).startswith(PRAEFIX)]
    behalten = [d for d in bisher if not str(d.get("name", "")).startswith(PRAEFIX)]
    neue_liste = behalten + [{"type": "text", "name": name, "id": neu_id, "usage_mode": "auto"}]

    try:
        ruf(f"/v1/convai/agents/{agent}", key, "PATCH", {
            "conversation_config": {"agent": {"prompt": {"knowledge_base": neue_liste}}}
        })
    except urllib.error.HTTPError as e:
        print(f"FEHLER beim Umhaengen: HTTP {e.code} — {e.read().decode('utf-8')[:400]}",
              file=sys.stderr)
        print("Das neue Dokument liegt im Konto, ist aber nicht angehaengt.", file=sys.stderr)
        return 1
    print(f"GEOrg: Agent zeigt jetzt auf das neue Faktenblatt "
          f"({len(behalten)} fremde Dokumente unveraendert).")

    for d in alt_eigene:
        try:
            ruf(f"/v1/convai/knowledge-base/{d.get('id')}?force=true", key, "DELETE")
            print(f"GEOrg: Altdokument entfernt — {d.get('name')}")
        except Exception as e:
            # Kein Abbruch: der Agent zeigt bereits auf das neue Dokument.
            print(f"GEOrg: Altdokument {d.get('name')} konnte nicht entfernt werden ({e}). "
                  "Nicht kritisch, bitte gelegentlich im Konto aufraeumen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
