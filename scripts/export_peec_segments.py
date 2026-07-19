#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exportiert zwei bislang ungenutzte Peec-Dimensionen nach data/peec_segments.json:

1. FANOUT-QUERIES — die Suchanfragen, die die Engines SELBST formulieren,
   bevor sie antworten. Die direkteste Content-Vorgabe, die es gibt: worauf
   optimiert werden muss, damit die Engine die eigene Seite ueberhaupt findet.

2. SICHTBARKEIT JE TAG — die Prompts sind in Peec nach Funnel-Stufe
   (Awareness/Consideration/Decision/Retention), Persona (young professional,
   retiree, ...) und Themenfeldern getaggt. Unser Zellen-Export ignoriert diese
   Dimension bisher komplett.

WICHTIG — laeuft NICHT im Nightly (persoenlicher Peec-Token, siehe
export_peec_sources.py). Aufruf als Cowork-Task.

Aufruf:  PEEC_TOKEN=<pat> python3 scripts/export_peec_segments.py [--days 30] [--query-days 7]

Hinweis zum Fenster: Fanout-Queries fallen pro Antwort an und sind entsprechend
zahlreich (~3.000 in 7 Tagen). Deshalb ein kuerzeres Fenster als bei den
Tag-Kennzahlen, plus Deduplizierung auf den Query-Text.
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

MCP_URL = "https://api.peec.ai/mcp"
PROJECT_ID = os.environ.get("PEEC_PROJECT_ID", "or_9e1c1c57-28de-4714-bfc0-363bfa6a0757")
OUT_FILE = Path("data/peec_segments.json")
HIST_FILE = Path("data/peec_segments_history.csv")
MAX_QUERY_PAGES = 5      # a 1000 Zeilen (API-Hardcap pro Seite)
TOP_QUERIES = 300        # so viele distinkte Queries ins Dashboard

# Funnel-Stufen in sinnvoller Reihenfolge (Peec-Systemtags, Gruppe intentType)
FUNNEL_ORDER = ["Awareness", "Consideration", "Decision", "Retention"]

_session = {}
_seq = [0]


def _rpc(method, params=None, want_id=True):
    token = os.environ.get("PEEC_TOKEN", "")
    if not token:
        sys.exit("FEHLER: PEEC_TOKEN nicht gesetzt (Peec Personal Access Token).")
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json",
               "Accept": "application/json, text/event-stream"}
    if _session.get("id"):
        headers["Mcp-Session-Id"] = _session["id"]
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    if want_id:
        _seq[0] += 1
        msg["id"] = _seq[0]
    req = urllib.request.Request(MCP_URL, json.dumps(msg).encode("utf-8"), headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        sid = r.headers.get("Mcp-Session-Id")
        if sid:
            _session["id"] = sid
        body = r.read().decode("utf-8")
    if not body.strip():
        return None
    if body.lstrip().startswith("{"):
        return json.loads(body)
    out = None
    for line in body.splitlines():
        if line.startswith("data:"):
            try:
                out = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                pass
    return out


def _connect():
    _rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                        "clientInfo": {"name": "llm-cockpit-export", "version": "1.0"}})
    _rpc("notifications/initialized", {}, want_id=False)


def _call(tool, args):
    r = _rpc("tools/call", {"name": tool, "arguments": args})
    content = ((r or {}).get("result") or {}).get("content") or []
    text = content[0].get("text", "") if content else ""
    if not text:
        raise RuntimeError(f"{tool}: leere Antwort ({str(r)[:200]})")
    return json.loads(text)


def _tab(d):
    cols = d.get("columns", [])
    return [dict(zip(cols, row)) for row in d.get("rows", [])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30, help="Fenster fuer Tag-Kennzahlen")
    ap.add_argument("--query-days", type=int, default=7, help="Fenster fuer Fanout-Queries")
    args = ap.parse_args()

    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    S = (end - timedelta(days=args.days)).isoformat()
    QS = (end - timedelta(days=args.query_days)).isoformat()
    E = end.isoformat()
    print(f"[peec_segments] Tags {S}..{E} | Queries {QS}..{E}")

    _connect()

    # ---- Tag-Stammdaten -----------------------------------------------------
    tags = _tab(_call("list_tags", {"project_id": PROJECT_ID, "limit": 200}))
    tag_meta = {t["id"]: {"name": t.get("name"), "group": t.get("group"),
                          "system": bool(t.get("is_system"))} for t in tags}
    print(f"[peec_segments] {len(tags)} Tags")

    # ---- Sichtbarkeit je Marke x Tag ---------------------------------------
    rows = _tab(_call("get_brand_report", {
        "project_id": PROJECT_ID, "start_date": S, "end_date": E, "limit": 500,
        "dimensions": ["tag_id"],
        "order_by": [{"field": "share_of_voice", "direction": "desc"}]}))
    seg = []
    for r in rows:
        tid = r.get("tag_id")
        if not tid:
            continue
        m = tag_meta.get(tid, {})
        seg.append({
            "tag": m.get("name") or tid,
            "group": m.get("group"),
            "brand": r.get("brand_name"),
            "sov": round(r.get("share_of_voice") or 0, 5),
            "vis": round(r.get("visibility") or 0, 5),
            "mentions": r.get("mention_count") or 0,
            "sentiment": r.get("sentiment"),
            "position": r.get("position"),
        })
    print(f"[peec_segments] {len(seg)} Marke-x-Tag-Zellen")

    # ---- Fanout-Queries -----------------------------------------------------
    raw = []
    for page in range(MAX_QUERY_PAGES):
        d = _tab(_call("list_search_queries", {
            "project_id": PROJECT_ID, "start_date": QS, "end_date": E,
            "limit": 1000, "offset": page * 1000}))
        raw += d
        if len(d) < 1000:
            break
    texts = [q.get("query_text", "").strip() for q in raw if q.get("query_text")]
    cnt = Counter(texts)
    print(f"[peec_segments] {len(texts)} Fanout-Queries, {len(cnt)} distinkt")

    # Wie viele Queries nennen ueberhaupt eine Marke? (Wortgrenzen wie im Matcher)
    BRAND_PAT = re.compile(
        r"\b(ergo|dkv|allianz|huk|huk24|axa|generali|cosmos\s?direkt|devk|"
        r"hannoversche|r\+v|signal\s?iduna|adac|check24|verivox|finanztip|"
        r"stiftung\s?warentest)\b", re.IGNORECASE)
    with_brand = sum(1 for t in texts if BRAND_PAT.search(t))
    with_ergo = sum(1 for t in texts if re.search(r"\b(ergo|dkv)\b", t, re.IGNORECASE))

    queries = [{"q": q, "n": n} for q, n in cnt.most_common(TOP_QUERIES)]

    out = {
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "window": {"start": S, "end": E, "days": args.days},
        "query_window": {"start": QS, "end": E, "days": args.query_days},
        "source": "Peec AI MCP (get_brand_report dimensions=tag_id, list_search_queries)",
        "funnel_order": FUNNEL_ORDER,
        "segments": seg,
        "queries": queries,
        "query_stats": {
            "total": len(texts), "distinct": len(cnt),
            "with_brand": with_brand, "with_ergo": with_ergo,
        },
        "methode": (
            "Fanout-Queries sind die Suchanfragen, die eine Engine selbst absetzt, bevor "
            "sie antwortet — sie zeigen, wonach die Engine sucht, nicht was Nutzer eintippen. "
            "Die Tag-Kennzahlen brechen Sichtbarkeit und Share of Voice nach Funnel-Stufe, "
            "Persona und Themenfeld auf; ein Prompt kann mehrere Tags tragen, die Zellen "
            "sind daher NICHT ueberschneidungsfrei und summieren sich nicht auf 100 %."
        ),
        "grenzen": (
            "Queries: rollierendes " + str(args.query_days) + "-Tage-Fenster, maximal "
            + str(MAX_QUERY_PAGES * 1000) + " Zeilen, im Dashboard die Top-" + str(TOP_QUERIES)
            + " nach Haeufigkeit — der Long Tail fehlt. Die Zuordnung der Prompts zu Tags "
            "stammt aus dem Peec-Projekt-Setup, nicht aus einer eigenen Erhebung."
        ),
    }
    # ---- Tag-ZEITREIHE (date x tag_id) --------------------------------------
    # Der Block oben ist ein 30-Tage-Aggregat zu EINEM Stichtag — daraus laesst
    # sich keine Veraenderung ueber die Zeit rechnen. Fuer die Funnel-Schichtung
    # im Treibermodell (correlation_impact.funnel_stratified_analysis) braucht es
    # eine Reihe je Tag. Die CSV waechst nicht von selbst: sie wird bei jedem Lauf
    # neu geschrieben, deckt aber das volle --days-Fenster ab.
    hist_rows = []
    try:
        hrows = _tab(_call("get_brand_report", {
            "project_id": PROJECT_ID, "start_date": S, "end_date": E, "limit": 10000,
            "dimensions": ["date", "tag_id"],
            "order_by": [{"field": "share_of_voice", "direction": "desc"}]}))
        for r in hrows:
            tid = r.get("tag_id")
            if not tid:
                continue
            m = tag_meta.get(tid, {})
            hist_rows.append({
                "datum": (r.get("date") or "")[:10],
                "marke": r.get("brand_name"),
                "tag": m.get("name") or tid,
                "gruppe": m.get("group") or "",
                "share_of_voice": r.get("share_of_voice"),
                "visibility": r.get("visibility"),
                "mention_count": r.get("mention_count"),
                "sentiment": r.get("sentiment"),
                "position": r.get("position"),
                "brand_id": r.get("brand_id"),
                "tag_id": tid,
            })
        print(f"[peec_segments] {len(hist_rows)} Tag-Zeitreihen-Zeilen "
              f"({len({r['datum'] for r in hist_rows})} Messtage)")
    except Exception as ex:  # noqa: BLE001
        print(f"[peec_segments] WARNUNG: Tag-Zeitreihe nicht abrufbar ({str(ex)[:120]}) — "
              "peec_segments_history.csv wird NICHT geschrieben (alte Datei bleibt stehen).")

    if hist_rows:
        import csv as _csv
        HIST_FILE.parent.mkdir(parents=True, exist_ok=True)
        cols = ["datum", "marke", "tag", "gruppe", "share_of_voice", "visibility",
                "mention_count", "sentiment", "position", "brand_id", "tag_id"]
        with open(HIST_FILE, "w", encoding="utf-8-sig", newline="") as fh:
            w = _csv.DictWriter(fh, fieldnames=cols, delimiter=";")
            w.writeheader()
            for r in sorted(hist_rows, key=lambda x: (x["datum"], x["tag"], x["marke"] or "")):
                w.writerow(r)
        print(f"[peec_segments] {HIST_FILE} geschrieben ({HIST_FILE.stat().st_size // 1024} KB)")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[peec_segments] {OUT_FILE} geschrieben ({OUT_FILE.stat().st_size // 1024} KB)")
    print(f"[peec_segments] Queries mit Markenname: {with_brand}/{len(texts)}"
          f" ({with_brand/max(len(texts),1)*100:.0f} %), davon ERGO/DKV: {with_ergo}")


if __name__ == "__main__":
    main()
