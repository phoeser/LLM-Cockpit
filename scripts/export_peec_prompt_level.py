#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Peec Prompt-Level-Export fuer ALLE getrackten Marken.

Zweck: Grundlage fuer die NEUTRALE Share of Voice (scripts/build_peec_neutral_sov.py).
Der bisherige Prompt-Level-Export (data/peec_prompt_level.csv) enthielt nur ERGO +
Allianz — damit laesst sich keine faire, markenneutrale SoV rechnen. Dieses Skript
zieht get_brand_report auf Prompt-Ebene OHNE Marken-Filter, also fuer alle Marken des
Projekts, und schreibt dieselbe CSV-Struktur wie bisher.

Warum es zaehlt (Pruefung 31.07.2026): 21 % der Peec-Prompts nennen ERGO ausdruecklich,
kein einziger einen Wettbewerber. Das blaeht ERGOs Peec-SoV ~3x auf. Erst mit allen
Marken auf Prompt-Ebene laesst sich die SoV OHNE die ERGO-markierten Prompts rechnen.

Aufruf (auf Pauls Rechner, Peec-Key):
    PEEC_TOKEN=<pat> python3 scripts/export_peec_prompt_level.py [--days 30]

Danach:
    python3 scripts/build_peec_neutral_sov.py

HINWEIS zur Robustheit: Das exakte Dimensions-/Feldschema von get_brand_report auf
Prompt-Ebene ist hier best-effort gespiegelt (analog zur bewaehrten tag_id-Variante in
export_peec_segments.py). Das Skript LOGGT beim ersten Lauf die tatsaechlich gelieferten
Spalten. Weicht ein Feldname ab, hier im FIELD-Mapping anpassen (eine Zeile).
"""
import argparse
import csv
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

MCP_URL = "https://api.peec.ai/mcp"
PROJECT_ID = os.environ.get("PEEC_PROJECT_ID", "or_9e1c1c57-28de-4714-bfc0-363bfa6a0757")
OUT_FILE = Path("data/peec_prompt_level.csv")

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
    return [dict(zip(cols, row)) for row in d.get("rows", [])], cols


def _first(d, *names, default=""):
    for n in names:
        if n in d and d[n] not in (None, ""):
            return d[n]
    return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()
    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    S = (end - timedelta(days=args.days)).isoformat()
    E = end.isoformat()
    period = f"{S}_{E}"
    print(f"[prompt_level] Fenster {S}..{E}, Projekt {PROJECT_ID}")

    _connect()

    # Prompt-Ebene je Marke: KEIN Marken-Filter -> alle Marken des Projekts.
    # dimensions best-effort: prompt + engine (analog tag_id in export_peec_segments).
    rows, cols = _tab(_call("get_brand_report", {
        "project_id": PROJECT_ID, "start_date": S, "end_date": E, "limit": 20000,
        "dimensions": ["prompt_id", "engine"]}))
    print(f"[prompt_level] {len(rows)} Zeilen. Gelieferte Spalten: {cols}")
    if not rows:
        sys.exit("FEHLER: get_brand_report lieferte keine Zeilen — Dimensions/Parameter pruefen.")

    # Feld-Mapping (bei abweichenden Spaltennamen HIER anpassen):
    def _row_out(r):
        return {
            "zeitraum": period,
            "marke": _first(r, "brand_name", "marke", "brand"),
            "prompt_id": _first(r, "prompt_id", "prompt", "query_id"),
            "prompt_text": _first(r, "prompt_text", "prompt", "query_text", "text"),
            "topic": _first(r, "topic", "topic_name", "tag"),
            "engine": _first(r, "engine", "model", "model_channel"),
            "engine_typ": _first(r, "engine_typ", "engine_type"),
            "visibility": _first(r, "visibility", default=0),
            "mention_count": _first(r, "mention_count", "mentions", default=0),
            "sentiment": _first(r, "sentiment", default=""),
            "position": _first(r, "position", default=""),
        }
    out_rows = [_row_out(r) for r in rows]
    # Diagnose: Marken- und Prompt-Abdeckung
    brands = sorted({r["marke"] for r in out_rows if r["marke"]})
    prompts = {r["prompt_id"] for r in out_rows if r["prompt_id"]}
    have_text = sum(1 for r in out_rows if r["prompt_text"])
    print(f"[prompt_level] Marken: {len(brands)} | Prompts: {len(prompts)} | "
          f"Zeilen mit prompt_text: {have_text}/{len(out_rows)}")
    print(f"[prompt_level] Marken-Liste: {brands}")
    if len(brands) < 3:
        print("[prompt_level] WARNUNG: <3 Marken — vermutlich doch ein Marken-Filter aktiv "
              "oder falsche Dimension. Neutrale SoV waere nicht aussagekraeftig.")
    if have_text == 0:
        print("[prompt_level] WARNUNG: kein prompt_text geliefert — dann kann die neutrale "
              "SoV markierte Prompts nicht erkennen. Feld-Mapping/Report-Optionen pruefen.")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    fields = ["zeitraum", "marke", "prompt_id", "prompt_text", "topic", "engine",
              "engine_typ", "visibility", "mention_count", "sentiment", "position"]
    with OUT_FILE.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        w.writeheader()
        for r in out_rows:
            w.writerow(r)
    print(f"[prompt_level] OK: {OUT_FILE} ({len(out_rows)} Zeilen, {len(brands)} Marken)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
