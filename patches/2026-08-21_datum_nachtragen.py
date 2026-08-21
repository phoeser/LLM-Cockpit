#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Erscheinungsdatum in Bestandsdaten nachtragen (21.08.2026).

Ab sofort leiten die Sammler das Erscheinungsdatum aus der Beitrags-URL ab
(shared/social_dating.py). Dieses Skript holt das fuer die bereits gesammelten
Daten nach - einmalig, ohne einen einzigen Netzabruf, weil alles Noetige in
den URLs steckt, die wir laengst haben.

Warum das mehr ist als Kosmetik
-------------------------------
Bisher hingen 183 von 184 LinkedIn-Posts und 269 von 274 Instagram-Beitraegen
am FUND-Tag. Zwei Folgen:

1. Die Wirkungsrechnung ordnete sie dem falschen Messintervall zu - bei
   Wochentakt ist der Versatz so gross wie das Intervall selbst.
2. Der Erstimport-Filter warf sie vollstaendig aus der Analyse (75 LinkedIn-
   und 92 Instagram-Events), weil ein Monat Beitraege auf einen Fund-Tag
   komprimiert ein Artefakt gewesen waere.

Mit echten Daten faellt beides weg: Die Beitraege verteilen sich auf ihre
tatsaechlichen Tage, und der Filter greift nicht mehr, weil sie datiert sind.
Aus totem Bestand wird damit nutzbare Historie.

Was angefasst wird
------------------
  scripts/correlation_impact.py  erkennt datierung "url" als echtes Datum an
  data/linkedin_posts.jsonl      Feld "date", nur wenn es leer ist
  data/instagram_posts.jsonl     dito
  shared/events.jsonl            detail.date + detail.datierung="url" bei
                                 linkedin_post/instagram_post ohne Datum

Die Engine-Aenderung steckt hier mit drin, weil correlation_impact.py 300 KB
gross ist und nicht ueber die Deploy-Seite geht - dieselbe Begruendung wie beim
Instagram-Patch vom 20.08.

Sicherungen: Ein abgeleitetes Datum nach dem Fund-Tag wird verworfen (dann
stimmt das ID-Schema nicht mehr). Vorhandene Daten aus der Google-Trefferliste
werden NIE ueberschrieben. Das Skript ist idempotent.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from shared.social_dating import datum_aus_url
except ImportError:
    # Reihenfolge zaehlt: shared/social_dating.py kommt ueber die Deploy-Seite
    # ins Repo, dieser Patch ueber den Konnektor. Fehlt das Modul, ist die Seite
    # noch nicht gepusht - dann klar sagen, was fehlt, statt mit einem
    # Stacktrace abzubrechen.
    print("FEHLER: shared/social_dating.py fehlt im Repo. Zuerst die Deploy-Seite "
          "pushen (sie enthaelt das Modul), dann diesen Patch erneut anstossen.")
    sys.exit(1)

POSTS = [("data/linkedin_posts.jsonl", "first_seen"),
         ("data/instagram_posts.jsonl", "first_seen")]
EVENTS = Path("shared/events.jsonl")
SOCIAL = ("linkedin_post", "instagram_post")

ENGINE = Path("scripts/correlation_impact.py")
ENGINE_ERSETZUNGEN = [
    ("Erstimport-Filter: url zaehlt als Datum",
     '''        if d_.get("fenster") or d_.get("datierung") == "post":
            continue''',
     '''        # 21.08.2026: "url" zaehlt wie "post" als echtes Erscheinungsdatum - es
        # stammt aus der Beitrags-ID der Plattform und ist damit exakter als
        # Googles Angabe, nicht ungenauer (shared/social_dating.py).
        if d_.get("fenster") or d_.get("datierung") in ("post", "url"):
            continue'''),
    ("Undatiert-Pruefung",
     '''            undatiert = d_.get("datierung") != "post"''',
     '''            undatiert = d_.get("datierung") not in ("post", "url")'''),
]


def engine_anpassen():
    if not ENGINE.exists():
        print("[Datum] %s fehlt - uebersprungen." % ENGINE)
        return 0
    s = ENGINE.read_text(encoding="utf-8")
    if '("post", "url")' in s:
        print("[Datum] %-32s bereits angepasst" % str(ENGINE))
        return 0
    for beschreibung, alt, neu in ENGINE_ERSETZUNGEN:
        n = s.count(alt)
        if n != 1:
            print("FEHLER in %s bei '%s': %d Treffer (erwartet 1) - nichts geaendert."
                  % (ENGINE, beschreibung, n))
            raise SystemExit(1)
        s = s.replace(alt, neu, 1)
    import ast
    ast.parse(s)                      # nur gueltiges Python schreiben
    ENGINE.write_text(s, encoding="utf-8")
    print("[Datum] %-32s Erstimport-Filter erkennt jetzt \"url\"" % str(ENGINE))
    return 1


def posts_nachtragen():
    gesamt = 0
    for pfad, fundfeld in POSTS:
        p = Path(pfad)
        if not p.exists():
            print("[Datum] %s fehlt - uebersprungen." % pfad)
            continue
        raus, geaendert = [], 0
        for zeile in p.read_text(encoding="utf-8").splitlines():
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                d = json.loads(zeile)
            except Exception:
                raus.append(zeile)          # unlesbare Zeile bleibt unangetastet
                continue
            if not d.get("date"):
                neu = datum_aus_url(d.get("url"), d.get(fundfeld))
                if neu:
                    d["date"] = neu
                    d["datierung"] = "url"
                    geaendert += 1
            raus.append(json.dumps(d, ensure_ascii=False))
        p.write_text("\n".join(raus) + "\n", encoding="utf-8")
        print("[Datum] %-32s %d Beitraege datiert" % (pfad, geaendert))
        gesamt += geaendert
    return gesamt


def events_nachtragen():
    if not EVENTS.exists():
        print("[Datum] shared/events.jsonl fehlt - uebersprungen.")
        return 0
    raus, geaendert = [], 0
    for zeile in EVENTS.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile:
            continue
        try:
            e = json.loads(zeile)
        except Exception:
            raus.append(zeile)
            continue
        if e.get("event_type") in SOCIAL:
            det = e.get("detail") or {}
            if not det.get("date"):
                # Fund-Tag ist der Zeitstempel des Events selbst.
                neu = datum_aus_url(e.get("url"), str(e.get("timestamp") or "")[:10])
                if neu:
                    det["date"] = neu
                    det["datierung"] = "url"
                    e["detail"] = det
                    geaendert += 1
        raus.append(json.dumps(e, ensure_ascii=False))
    EVENTS.write_text("\n".join(raus) + "\n", encoding="utf-8")
    print("[Datum] %-32s %d Ereignisse datiert" % ("shared/events.jsonl", geaendert))
    return geaendert


def main():
    c = engine_anpassen()
    a = posts_nachtragen()
    b = events_nachtragen()
    if not (a or b or c):
        print("[Datum] Nichts nachzutragen - bereits erledigt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
