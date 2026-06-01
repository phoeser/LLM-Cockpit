#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SoV-Historie aufzeichnen (dichte Zeitreihe fuer die Korrelations-/Impact-Analyse).

Problem: update_snapshot.py zieht nur das jeweils aktuelle latest.json (ueberschrieben)
und persistiert nur 'sov_change'-Events BEI VERAENDERUNG. Eine dichte tägliche
SoV-Messreihe existiert dadurch nicht.

Loesung: Dieses Skript schreibt bei JEDEM Lauf den aktuellen SoV-Stand je Marke aus
data/geo_snapshot.json als Messpunkt in data/sov_history.jsonl (append-only) — egal ob
sich der Wert geaendert hat. Pro (Messtag, Marke) genau ein Eintrag (idempotent).

Beim allerersten Lauf wird zusaetzlich aus shared/events.jsonl (sov_change) backgefillt,
damit die bereits bekannten Mess-/Aenderungstage nicht verloren gehen.

Aufruf im Nightly NACH update_snapshot.py, VOR correlation_impact.py.
Format je Zeile: {"date":"YYYY-MM-DD","brand":"ERGO","sov_pct":17.0,"avg_rank":4.7,"source":"snapshot"}
"""
import json
import sys
from pathlib import Path

SNAPSHOT = Path("data/geo_snapshot.json")
HISTORY = Path("data/sov_history.jsonl")
EVENTS = Path("shared/events.jsonl")


def load_history():
    rows = []
    if HISTORY.exists():
        for line in HISTORY.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def existing_keys(rows):
    return {(r.get("date"), r.get("brand")) for r in rows}


def backfill_from_events(seen, out_lines):
    """Einmalig: bekannte SoV-Stände aus sov_change-Events uebernehmen."""
    if not EVENTS.exists():
        return 0
    added = 0
    for line in EVENTS.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("event_type") != "sov_change":
            continue
        d = e.get("detail") or {}
        if d.get("metric") != "share_of_voice_pct" or d.get("new_pct") is None:
            continue
        day = (e.get("timestamp") or "")[:10]
        brand = e.get("brand")
        if not day or not brand or (day, brand) in seen:
            continue
        seen.add((day, brand))
        out_lines.append(json.dumps({
            "date": day, "brand": brand,
            "sov_pct": round(float(d["new_pct"]), 2),
            "avg_rank": None, "source": "backfill_event",
        }, ensure_ascii=False))
        added += 1
    return added


def main():
    rows = load_history()
    seen = existing_keys(rows)
    out_lines = []

    # Einmaliger Backfill, wenn Historie noch leer/klein
    if len(rows) < 5:
        n = backfill_from_events(seen, out_lines)
        print("Backfill aus events.jsonl: %d Messpunkte" % n)

    # Aktuellen Snapshot als heutigen Messpunkt aufnehmen
    if SNAPSHOT.exists():
        try:
            snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        except Exception as e:
            snap = None
            print("WARN: geo_snapshot.json nicht lesbar: %s" % str(e)[:80])
        if snap:
            day = (snap.get("finished_at") or snap.get("started_at") or "")[:10]
            ranking = snap.get("totals_ranking", []) or []
            added = 0
            for r in ranking:
                brand = r.get("name")
                sov = r.get("share_of_voice")
                if not brand or sov is None or not day:
                    continue
                if (day, brand) in seen:
                    continue
                seen.add((day, brand))
                out_lines.append(json.dumps({
                    "date": day, "brand": brand,
                    "sov_pct": round(float(sov) * 100, 2),
                    "avg_rank": r.get("avg_rank"),
                    "source": "snapshot",
                }, ensure_ascii=False))
                added += 1
            print("Snapshot %s: %d neue Messpunkte" % (day, added))
    else:
        print("WARN: data/geo_snapshot.json fehlt — nur Backfill")

    if out_lines:
        HISTORY.parent.mkdir(parents=True, exist_ok=True)
        with HISTORY.open("a", encoding="utf-8") as f:
            f.write("\n".join(out_lines) + "\n")

    total = len(load_history())
    days = len({r.get("date") for r in load_history()})
    print("OK: %s — %d Eintraege, %d Messtage" % (HISTORY, total, days))
    return 0


if __name__ == "__main__":
    sys.exit(main())
