#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pipeline-Freshness-/Health-Check (2026-07-02).

Zweck: das Fehlen jeglicher Ueberwachung war die Kern-Ursache dafuer, dass
eingefrorene Crawls tagelang unbemerkt blieben. Dieses Skript prueft je
Daten-Element das echte Alter und schlaegt Alarm.

Aufrufe:
  python scripts/pipeline_health.py            # menschlicher Report (stdout)
  python scripts/pipeline_health.py --write     # schreibt data/pipeline_health.json
  python scripts/pipeline_health.py --check      # exit 1, wenn etwas ueberaltert (fuer CI-Alarm)

Additiv, read-only ausser --write. Aendert KEINE bestehende Pipeline-Logik.
"""
import json
import sys
import re
from pathlib import Path
from datetime import datetime, timezone

NOW = datetime.now(timezone.utc)
DATA = Path("data")
SHARED = Path("shared")

def _parse_dt(s):
    if not s:
        return None
    s = str(s).strip().replace("Z", "+00:00")
    # nur Datum -> Mitternacht UTC
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        s += "T00:00:00+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def _age_days(dt):
    return None if dt is None else round((NOW - dt).total_seconds() / 86400, 1)

def _load_json(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return None

def _max_date_in_jsonl(p, field="date"):
    best = None
    try:
        for line in Path(p).read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            v = r.get(field) or (r.get("timestamp") or "")[:10]
            dt = _parse_dt(v)
            if dt and (best is None or dt > best):
                best = dt
    except Exception:
        return None
    return best

def _geo_snapshot_health():
    g = _load_json(DATA / "geo_snapshot.json")
    if not g:
        return {"name": "GEO-Snapshot (SoV)", "file": "data/geo_snapshot.json",
                "last": None, "age_days": None, "max_age": 2, "note": "Datei fehlt/unlesbar"}
    dt = _parse_dt(g.get("finished_at") or g.get("started_at") or g.get("run_id"))
    # LLMs mit lauter 0-Nennungen (= defekter Abruf) erkennen
    broken = set()
    for pid, pd in (g.get("products") or {}).items():
        for llm, s in (pd.get("summary_by_llm") or {}).items():
            brands = s.get("brands") or []
            if brands and not any((b.get("mentions") or 0) > 0 for b in brands):
                broken.add(llm)
    return {"name": "GEO-Snapshot (SoV)", "file": "data/geo_snapshot.json",
            "last": dt.date().isoformat() if dt else None, "age_days": _age_days(dt),
            "max_age": 2, "broken_llms": sorted(broken)}  # taeglicher Crawl (seit 19.07. wieder)

ELEMENTS = []

def build():
    ELEMENTS.clear()
    ELEMENTS.append(_geo_snapshot_health())

    dt = _max_date_in_jsonl(DATA / "sov_history.jsonl")
    ELEMENTS.append({"name": "SoV-Historie", "file": "data/sov_history.jsonl",
                     "last": dt.date().isoformat() if dt else None, "age_days": _age_days(dt), "max_age": 2})

    ci = _load_json(DATA / "correlation_impact.json") or {}
    dt = _parse_dt(ci.get("generated_at"))
    ELEMENTS.append({"name": "Korrelation/Impact", "file": "data/correlation_impact.json",
                     "last": dt.date().isoformat() if dt else None, "age_days": _age_days(dt), "max_age": 2})

    # Sentiment-Export: neuestes Datum irgendwo im JSON
    sd = _load_json(DATA / "sentiment_dashboard.json")
    dtb = None
    if sd:
        for m in re.findall(r"\d{4}-\d{2}-\d{2}", json.dumps(sd)):
            d = _parse_dt(m)
            if d and (dtb is None or d > dtb):
                dtb = d
    ELEMENTS.append({"name": "Sentiment-Export", "file": "data/sentiment_dashboard.json",
                     "last": dtb.date().isoformat() if dtb else None, "age_days": _age_days(dtb), "max_age": 9})

    ev = _max_date_in_jsonl(SHARED / "events.jsonl", field="timestamp")
    ELEMENTS.append({"name": "Event-Log", "file": "shared/events.jsonl",
                     "last": ev.date().isoformat() if ev else None, "age_days": _age_days(ev), "max_age": 3})

    pc = _load_json(DATA / "price_comparison.json")
    dtp = None
    if pc:
        for m in re.findall(r"\d{4}-\d{2}-\d{2}", json.dumps(pc)):
            d = _parse_dt(m)
            if d and (dtp is None or d > dtp):
                dtp = d
    ELEMENTS.append({"name": "Preise (Check24)", "file": "data/price_comparison.json",
                     "last": dtp.date().isoformat() if dtp else None, "age_days": _age_days(dtp), "max_age": 9})

    for e in ELEMENTS:
        a = e.get("age_days")
        e["stale"] = (a is None) or (a > e["max_age"])
    return ELEMENTS

def report():
    build()
    print("PIPELINE-FRESHNESS-CHECK  (Stand %s UTC)" % NOW.strftime("%Y-%m-%d %H:%M"))
    print("-" * 66)
    for e in ELEMENTS:
        flag = "STALE!" if e["stale"] else "ok"
        print("  [%-6s] %-22s letzter: %-10s  Alter: %s Tage (max %s)"
              % (flag, e["name"], e.get("last") or "-", e.get("age_days"), e["max_age"]))
        if e.get("broken_llms"):
            print("           -> LLM ohne Daten (Abruf defekt): %s" % ", ".join(e["broken_llms"]))
    n_stale = sum(1 for e in ELEMENTS if e["stale"])
    print("-" * 66)
    print("  %d von %d Elementen veraltet." % (n_stale, len(ELEMENTS)))
    return n_stale

def write():
    build()
    broken = sorted({l for e in ELEMENTS for l in e.get("broken_llms", [])})
    out = {"generated_at": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "overall_stale": any(e["stale"] for e in ELEMENTS),
           "broken_llms": broken, "elements": ELEMENTS}
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "pipeline_health.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OK: data/pipeline_health.json geschrieben (stale=%s, broken_llms=%s)" % (out["overall_stale"], broken))

def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--write":
        write(); return 0
    if arg == "--check":
        n = 0
        build()
        for e in ELEMENTS:
            if e["stale"]:
                n += 1
                print("STALE: %s (letzter %s, %s Tage alt)" % (e["name"], e.get("last"), e.get("age_days")))
        if n:
            print("ALARM: %d Daten-Element(e) veraltet." % n); return 1
        print("Alle Daten frisch."); return 0
    report(); return 0

if __name__ == "__main__":
    sys.exit(main())
