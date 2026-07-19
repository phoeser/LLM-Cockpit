#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exportiert Peecs Opportunity-gescorte Handlungsempfehlungen ("Actions")
nach data/peec_actions.json fuer den Reiter "Empfehlungen".

Zweistufig, wie von Peec vorgesehen:
  1. scope=overview  -> welche Slices haben die groesste Opportunity
  2. je Slice der passende Detail-Scope (owned/editorial/reference/ugc)
     -> die eigentlichen Empfehlungstexte

WICHTIG — laeuft NICHT im Nightly: persoenliche Peec-Keys sind auf der REST-API
gesperrt ("Personal API keys are not supported on this API yet"), nur der
MCP-Server akzeptiert sie. Der Token gehoert Paul und darf nicht als
GitHub-Secret liegen. Aufruf als Cowork-Task, analog peec-weekly-export.

Aufruf:  PEEC_TOKEN=<pat> python3 scripts/export_peec_actions.py [--days 30] [--top 8]

Einordnung der Kennzahlen (docs.peec.ai):
  opportunity_score          — kontinuierlicher Score, danach sortieren
  relative_opportunity_score — Stufe 1=niedrig, 2=mittel, 3=hoch
  gap_percentage             — Anteil, den ERGO in diesem Slice NICHT abdeckt
  coverage_percentage        — Anteil, den ERGO abdeckt
Peec legt die Score-Formel nicht offen — die Werte taugen zur PRIORISIERUNG,
nicht als gemessener Wirkungsnachweis. Im Dashboard entsprechend kennzeichnen.
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

MCP_URL = "https://api.peec.ai/mcp"
PROJECT_ID = os.environ.get("PEEC_PROJECT_ID", "or_9e1c1c57-28de-4714-bfc0-363bfa6a0757")
OUT_FILE = Path("data/peec_actions.json")

_session = {}
_seq = [0]

GROUP_DE = {
    "OWNED": "Eigene Seiten",
    "EDITORIAL": "Redaktionelle Medien",
    "REFERENCE": "Nachschlagewerke",
    "UGC": "Nutzerinhalte / Social",
}
TYPE_DE = {
    "PRODUCT_PAGE": "Produktseite", "COMPARISON": "Vergleichsseite",
    "CATEGORY_PAGE": "Kategorieseite", "LISTICLE": "Listenartikel",
    "ARTICLE": "Artikel", "HOW_TO_GUIDE": "Ratgeber", "HOMEPAGE": "Startseite",
    "ALTERNATIVE": "Alternativen", "PROFILE": "Profil", "DISCUSSION": "Diskussion",
}


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
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--top", type=int, default=8, help="Wie viele Slices im Detail abfragen")
    args = ap.parse_args()

    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    start = end - timedelta(days=args.days)
    S, E = start.isoformat(), end.isoformat()
    print(f"[peec_actions] Fenster {S} .. {E}")

    _connect()

    overview = _tab(_call("get_actions", {"project_id": PROJECT_ID, "start_date": S,
                                          "end_date": E, "scope": "overview"}))
    overview.sort(key=lambda r: -(r.get("opportunity_score") or 0))
    print(f"[peec_actions] {len(overview)} Slices im Overview")

    slices_out, items_out = [], []
    for row in overview:
        group = (row.get("action_group_type") or "").upper()
        key = row.get("url_classification") or row.get("domain") or ""
        slices_out.append({
            "group": group, "group_de": GROUP_DE.get(group, group),
            "key": key, "key_de": TYPE_DE.get(key, key),
            "score": round(row.get("opportunity_score") or 0, 4),
            "tier": row.get("relative_opportunity_score"),
            "gap": row.get("gap_percentage"), "cov": row.get("coverage_percentage"),
        })

    for row in overview[:args.top]:
        group = (row.get("action_group_type") or "").upper()
        scope = group.lower()
        a = {"project_id": PROJECT_ID, "start_date": S, "end_date": E, "scope": scope}
        if row.get("url_classification"):
            a["url_classification"] = row["url_classification"]
        if row.get("domain"):
            a["domain"] = row["domain"]
        try:
            detail = _tab(_call("get_actions", a))
        except Exception as ex:  # noqa: BLE001
            print(f"[peec_actions] {scope}/{a.get('url_classification') or a.get('domain')}: {ex}")
            continue
        key = row.get("url_classification") or row.get("domain") or ""
        for d in detail:
            items_out.append({
                "text": d.get("text"),
                "group": group, "group_de": GROUP_DE.get(group, group),
                "key": key, "key_de": TYPE_DE.get(key, key),
                "score": round(d.get("opportunity_score") or 0, 4),
                "tier": d.get("relative_opportunity_score"),
            })
        print(f"[peec_actions] {scope}/{key}: {len(detail)} Empfehlungen")

    items_out.sort(key=lambda x: -(x.get("score") or 0))

    out = {
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "window": {"start": S, "end": E, "days": args.days},
        "source": "Peec AI MCP (get_actions), Projekt ERGO Germany",
        "methode": (
            "Peec bewertet je Slice (Seitentyp bzw. Domain) eine Opportunity aus Abdeckungs-"
            "luecke und Zitat-Volumen und leitet daraus konkrete Empfehlungen ab. "
            "Stufe: 3 = hoch, 2 = mittel, 1 = niedrig."
        ),
        "grenzen": (
            "Die Score-Formel legt Peec nicht offen — die Werte dienen der PRIORISIERUNG "
            "und sind kein gemessener Wirkungsnachweis. Die Empfehlungstexte sind "
            "LLM-generiert und vor Umsetzung fachlich zu pruefen. Im Detail abgefragt "
            "werden die Top-" + str(args.top) + " Slices, nicht alle."
        ),
        "slices": slices_out,
        "items": items_out,
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[peec_actions] {OUT_FILE} geschrieben: {len(slices_out)} Slices, {len(items_out)} Empfehlungen")


if __name__ == "__main__":
    main()
