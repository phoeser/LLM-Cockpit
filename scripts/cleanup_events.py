#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Einmalige Bereinigung von shared/events.jsonl (Review-Fix 2026-06-12).

Entfernt die Folgen zweier am 12.06.2026 behobener Bugs:

  1. PHANTOM-PRESSE-EVENTS: press_mention/news_mention, die denselben Artikel
     (brand + normalisierter Titel) mehrfach melden. Ursache: update_press.py
     verglich gegen die auf 80 Artikel gekappte .previous.json — Artikel ab
     Position 81 wurden jede Nacht erneut als "neu" emittiert.
     -> Es bleibt jeweils das ERSTE Event pro (brand, titel).

  2. DOPPELTE BERATER-EVENTS: berater_shift mit identischer Metrik UND
     identischen old/new-Werten innerhalb von 14 Tagen. Ursache: falsche
     save/load-Reihenfolge in update_berater.py (2-Laufe-Vergleichsfenster).
     -> Es bleibt jeweils das ERSTE Event.

Sicherheit:
  - Standard ist DRY-RUN: zeigt nur, was entfernt wuerde, schreibt nichts.
  - Mit --apply wird geschrieben; vorher Backup events.jsonl.bak_<datum>.
  - Nicht parsebare Zeilen werden NIE entfernt.

Aufruf im Repo-Root:
  python scripts/cleanup_events.py            # Dry-Run (erst pruefen!)
  python scripts/cleanup_events.py --apply    # anwenden + Backup

Danach: shared/events.jsonl (+ Backup) committen und correlation_impact.py
einmal neu laufen lassen (passiert sonst automatisch im naechsten Nightly).
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

EVENTS = Path("shared/events.jsonl")
BERATER_WINDOW_DAYS = 14


def _norm_title(detail):
    t = (detail or {}).get("title", "") or ""
    return re.sub(r"[^a-z0-9äöü]", "", t.lower())[:60]


def main():
    apply_changes = "--apply" in sys.argv
    if not EVENTS.exists():
        print("FEHLER: %s nicht gefunden — bitte im Repo-Root ausfuehren." % EVENTS)
        return 1

    lines = EVENTS.read_text(encoding="utf-8", errors="ignore").splitlines()
    keep, removed = [], []
    seen_press = set()          # (brand, norm_title)
    seen_berater = {}           # (metric, old, new) -> erstes Datum

    for line in lines:
        s = line.strip()
        if not s:
            continue
        try:
            e = json.loads(s)
        except Exception:
            keep.append(line)   # nicht parsebar -> niemals loeschen
            continue

        et = e.get("event_type")
        day = (e.get("timestamp") or "")[:10]

        if et in ("press_mention", "news_mention"):
            k = (e.get("brand"), _norm_title(e.get("detail")))
            if k[1] and k in seen_press:
                removed.append(e)
                continue
            seen_press.add(k)

        elif et == "berater_shift":
            d = e.get("detail") or {}
            k = (d.get("metric", ""),
                 str(d.get("old_value", d.get("old_pct"))),
                 str(d.get("new_value", d.get("new_pct"))))
            first = seen_berater.get(k)
            if first and day:
                try:
                    gap = (date.fromisoformat(day) - date.fromisoformat(first)).days
                except Exception:
                    gap = 999
                if 0 <= gap <= BERATER_WINDOW_DAYS:
                    removed.append(e)
                    continue
            if day:
                seen_berater[k] = day

        keep.append(line)

    print("Events gesamt: %d | zu entfernen: %d | bleiben: %d"
          % (len([l for l in lines if l.strip()]), len(removed), len(keep)))
    by = {}
    for e in removed:
        k = "%s / %s" % (e.get("event_type"), e.get("brand"))
        by[k] = by.get(k, 0) + 1
    for k, c in sorted(by.items(), key=lambda kv: -kv[1]):
        print("  %-45s %4d" % (k, c))

    if not apply_changes:
        print("\nDRY-RUN — nichts geschrieben. Anwenden mit:  "
              "python scripts/cleanup_events.py --apply")
        return 0

    bak = EVENTS.with_name("events.jsonl.bak_%s" % date.today().strftime("%Y%m%d"))
    bak.write_text("\n".join(lines) + "\n", encoding="utf-8")
    EVENTS.write_text("\n".join(keep) + "\n", encoding="utf-8")
    print("\nOK: %s bereinigt (Backup: %s)" % (EVENTS, bak.name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
