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
    return {(r.get("date"), r.get("brand"), r.get("llm")) for r in rows}


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
        if not day or not brand or (day, brand, None) in seen:
            continue
        seen.add((day, brand, None))
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
    seen_prod = {(r.get("date"), r.get("brand"), r.get("product")) for r in rows if r.get("product")}
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
                if (day, brand, None) in seen:
                    continue
                seen.add((day, brand, None))
                out_lines.append(json.dumps({
                    "date": day, "brand": brand,
                    "sov_pct": round(float(sov) * 100, 2),
                    "avg_rank": r.get("avg_rank"),
                    "source": "snapshot",
                }, ensure_ascii=False))
                added += 1
            # 2026-06-04: zusaetzlich SoV JE LLM (fuer die LLM-Auswahl im Dashboard).
            # Aggregation: Mentions je Marke ueber alle Produkte, je LLM -> Anteil.
            llm_mentions = {}
            for prod in (snap.get("products") or {}).values():
                for llm, summ in (prod.get("summary_by_llm") or {}).items():
                    for b in (summ.get("brands") or []):
                        bn, m = b.get("name"), b.get("mentions")
                        if not bn or m is None:
                            continue
                        llm_mentions.setdefault(llm, {})
                        llm_mentions[llm][bn] = llm_mentions[llm].get(bn, 0) + int(m)
            for llm, per_brand in llm_mentions.items():
                tot = sum(per_brand.values())
                if tot <= 0:
                    continue
                for brand, m in per_brand.items():
                    if (day, brand, llm) in seen:
                        continue
                    seen.add((day, brand, llm))
                    out_lines.append(json.dumps({
                        "date": day, "brand": brand, "llm": llm,
                        "sov_pct": round(m / tot * 100.0, 2),
                        "avg_rank": None, "source": "snapshot_llm",
                    }, ensure_ascii=False))
                    added += 1
            # 2026-06-09: zusaetzlich SoV JE PRODUKT (Aggregation der Mentions ueber
            # alle LLMs je Produkt) -> ermoeglicht spaetere Produktebenen-Korrelation.
            for prod_key, prod in (snap.get("products") or {}).items():
                pm = {}
                for summ in (prod.get("summary_by_llm") or {}).values():
                    for b in (summ.get("brands") or []):
                        bn, mm = b.get("name"), b.get("mentions")
                        if bn and mm is not None:
                            pm[bn] = pm.get(bn, 0) + int(mm)
                ptot = sum(pm.values())
                if ptot <= 0:
                    continue
                for brand, mm in pm.items():
                    if (day, brand, prod_key) in seen_prod:
                        continue
                    seen_prod.add((day, brand, prod_key))
                    out_lines.append(json.dumps({
                        "date": day, "brand": brand, "product": prod_key,
                        "sov_pct": round(mm / ptot * 100.0, 2),
                        "avg_rank": None, "source": "snapshot_product",
                    }, ensure_ascii=False))
                    added += 1
            print("Snapshot %s: %d neue Messpunkte (inkl. per-LLM + per-Produkt)" % (day, added))
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
