#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exportiert den Peec-Quellen-Report (Domains + URLs) nach data/peec_sources.json
fuer den Dashboard-Reiter "Quellen & Zitate".

Wo das laeuft (Stand 12.08.2026):
In GitHub Actions, taeglich um 04:00 UTC — .github/workflows/peec-daily-sources.yml,
mit dem Repository-Secret PEEC_TOKEN. Der Lauf liegt bewusst VOR dem Nightly
(05:30 UTC), damit dieser die frischen Quellen schon sieht, und teilt sich mit
ihm die concurrency-group "repo-writes".

Hier stand bis 12.08.2026 das Gegenteil ("laeuft NICHT im Nightly ... als
Cowork-Task auf Pauls Rechner"). Das galt, solange es kein Secret gab, und war
seit Einrichtung des Tages-Workflows falsch. Wer sich darauf verlassen hat,
suchte den Export an der falschen Stelle.

Peec bietet fuer persoenliche Keys nur den MCP-Server; die REST-API ist auf
Enterprise-Keys beschraenkt ("Personal API keys are not supported on this API
yet"). Deshalb spricht dieses Skript JSON-RPC gegen api.peec.ai/mcp und braucht
keinen laufenden lokalen MCP-Server — nur den Token.

Aufruf:  PEEC_TOKEN=<pat> python3 scripts/export_peec_sources.py [--days 30]

Datenquelle: MCP-Tools get_domain_report / get_url_report (Projekt "ERGO Germany").

Kennzahlen (Peec-Definitionen, siehe docs.peec.ai):
  citation_count       — Zitate gesamt (Modell verlinkt die Quelle sichtbar)
  retrieval_count      — Abrufe gesamt (Modell hat die URL gelesen)
  retrieved_chat_count — Anzahl Antworten, in denen die Domain abgerufen wurde
  classification       — Peec-HEURISTIK (You/Competitor/Editorial/Aggregator/
                         UGC/Broker/Institutional/Reference/Other). Keine
                         gepruefte Taxonomie — im Dashboard als solche kennzeichnen.
  mentioned_brand_ids  — Marken, die in Antworten mit dieser Quelle genannt wurden.
                         ACHTUNG: Ko-Vorkommen, KEINE Kausalitaet.
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

MCP_URL = "https://api.peec.ai/mcp"
PROJECT_ID = os.environ.get("PEEC_PROJECT_ID", "or_9e1c1c57-28de-4714-bfc0-363bfa6a0757")  # ERGO Germany
OUT_FILE = Path("data/peec_sources.json")
TOP_DOMAINS = int(os.environ.get("PEEC_TOP_DOMAINS", "100"))
# 12.08.2026 von 500 auf 1500 angehoben. Grund aus den Daten: Im Export vom
# 11.08. traegt die 500. URL immer noch 140 Zitate - der Rand war nicht
# annaehernd erreicht. Die Plaetze 151 bis 500 machen 40 % aller Zitate aus,
# und zwei Drittel der ERGO-URLs liegen dort. Die Paginierung bricht ab,
# sobald Peec weniger liefert als angefordert; wo der echte Deckel liegt,
# steht danach im Feld "abruf" der Ausgabedatei.
TOP_URLS = int(os.environ.get("PEEC_TOP_URLS", "1500"))
# Serverseitige Obergrenze je EINZELNER Anfrage (Peec: "expected number to be
# <=1000 at limit"). Mehr als das geht nur ueber Paginierung, nicht ueber ein
# groesseres limit.
MAX_LIMIT_PRO_ANFRAGE = 1000

_session = {}
_seq = [0]


def _rpc(method, params=None, want_id=True):
    token = os.environ.get("PEEC_TOKEN", "")
    if not token:
        sys.exit("FEHLER: PEEC_TOKEN nicht gesetzt (Peec Personal Access Token).")
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
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
    out = None  # SSE-Antwort
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
    """Columnar JSON -> Liste von Dicts."""
    cols = d.get("columns", [])
    return [dict(zip(cols, row)) for row in d.get("rows", [])]


def _fetch_ranked(tool, base_args, want, label):
    """Holt bis zu `want` Zeilen, sortiert nach citation_count.

    Peec deckelt `limit` serverseitig moeglicherweise. Kommen weniger Zeilen
    zurueck als angefordert, wird einmal mit `offset` nachgefasst; versteht der
    Server das Argument nicht, bleibt es beim ersten Ergebnis. Der Rueckgabewert
    enthaelt immer auch, was tatsaechlich ankam — die Kappung wird dadurch in
    peec_sources.json sichtbar statt stillschweigend.
    """
    order = [{"field": "citation_count", "direction": "desc"}]
    rows, seen, offset, paginiert = [], set(), 0, False
    schluessel = "domain" if tool == "get_domain_report" else "url"
    while len(rows) < want:
        args = dict(base_args)
        # 12.08.2026: Hier stand nur "want - len(rows)". Bei want=1500 ging damit
        # schon die ERSTE Anfrage mit limit=1500 raus, und Peec lehnt sie ab:
        # "Too big: expected number to be <=1000 at limit". Das Skript ist dann
        # abgestuerzt, statt in zwei Seiten zu holen - obwohl die Paginierung
        # darunter genau dafuer gebaut ist. Jetzt wird je Anfrage gedeckelt.
        args["limit"] = min(want - len(rows), MAX_LIMIT_PRO_ANFRAGE)
        args["order_by"] = order
        if offset:
            args["offset"] = offset
        try:
            batch = _tab(_call(tool, args))
        except Exception as ex:
            if offset:
                print(f"[peec_sources] {label}: Paginierung ab offset={offset} nicht "
                      f"unterstuetzt ({str(ex)[:80]}) — bleibe bei {len(rows)} Zeilen.")
                break
            raise
        neu = [r for r in batch if r.get(schluessel) not in seen]
        for r in neu:
            seen.add(r.get(schluessel))
        rows.extend(neu)
        if not neu or len(batch) < args["limit"]:
            break
        offset = len(rows)
        paginiert = True
    if len(rows) < want:
        print(f"[peec_sources] {label}: {len(rows)} von {want} angeforderten Zeilen "
              f"geliefert — serverseitige Obergrenze erreicht.")
    return rows, {"angefordert": want, "erhalten": len(rows), "paginiert": paginiert}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30, help="Fensterlaenge in Tagen (Default 30)")
    ap.add_argument("--top-urls", type=int, default=TOP_URLS,
                    help="Zahl der URLs nach Zitaten (Default %(default)s, env PEEC_TOP_URLS)")
    ap.add_argument("--top-domains", type=int, default=TOP_DOMAINS,
                    help="Zahl der Domains nach Zitaten (Default %(default)s, env PEEC_TOP_DOMAINS)")
    args = ap.parse_args()

    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    start = end - timedelta(days=args.days)
    S, E = start.isoformat(), end.isoformat()
    print(f"[peec_sources] Fenster {S} .. {E} (Projekt {PROJECT_ID})")

    _connect()

    brands = _tab(_call("list_brands", {"project_id": PROJECT_ID, "limit": 100}))
    brand_name = {b["id"]: b["name"] for b in brands}
    own = [b["name"] for b in brands if b.get("is_own")]
    print(f"[peec_sources] {len(brands)} Marken, eigene: {own}")

    basis = {"project_id": PROJECT_ID, "start_date": S, "end_date": E}
    domains, dom_abruf = _fetch_ranked("get_domain_report", basis, args.top_domains, "Domains")
    print(f"[peec_sources] {len(domains)} Domains")

    urls, url_abruf = _fetch_ranked("get_url_report", basis, args.top_urls, "URLs")
    print(f"[peec_sources] {len(urls)} URLs")

    def slim_domain(d):
        return {
            "domain": d.get("domain"),
            "cls": d.get("classification"),
            "cit": d.get("citation_count") or 0,
            "ret": d.get("retrieval_count") or 0,
            "chats": d.get("retrieved_chat_count") or 0,
            "brands": sorted({brand_name.get(b) for b in (d.get("mentioned_brand_ids") or [])
                              if brand_name.get(b)}),
        }

    def slim_url(u):
        return {
            "url": u.get("url"),
            "cls": u.get("classification"),
            "title": u.get("title"),
            "cit": u.get("citation_count") or 0,
            "ret": u.get("retrieval_count") or 0,
            "brands": sorted({brand_name.get(b) for b in (u.get("mentioned_brand_ids") or [])
                              if brand_name.get(b)}),
        }

    dom_rows = [slim_domain(d) for d in domains]
    url_rows = [slim_url(u) for u in urls]

    # Seitentyp-Mix je Marke: Zitate auf URLs, in deren Antworten die Marke genannt wurde.
    # Das ist ein KO-VORKOMMEN, kein Nachweis, dass die Quelle die Nennung verursacht hat.
    by_brand_class = {}
    for u in url_rows:
        for b in u["brands"]:
            by_brand_class.setdefault(b, {}).setdefault(u["cls"] or "Unbekannt", 0)
            by_brand_class[b][u["cls"] or "Unbekannt"] += u["cit"]

    out = {
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "window": {"start": S, "end": E, "days": args.days},
        "source": "Peec AI MCP (get_domain_report / get_url_report), Projekt ERGO Germany",
        "own_brands": own,
        "methode": (
            "citation_count = Zitate (Quelle sichtbar verlinkt), retrieval_count = Abrufe. "
            "Der Seitentyp-Mix je Marke zaehlt Zitate auf URLs, in deren Antworten die Marke "
            "genannt wurde — ein Ko-Vorkommen, KEIN Kausalnachweis."
        ),
        "abruf": {"domains": dom_abruf, "urls": url_abruf},
        "grenzen": (
            "Die Klassifikation der Domains und Seitentypen stammt aus einer Peec-Heuristik, "
            "nicht aus einer geprueften Taxonomie; Einzelfaelle koennen falsch einsortiert sein. "
            "Ausgewertet werden die Top-" + str(len(url_rows)) + "-URLs und Top-"
            + str(len(dom_rows)) + "-Domains nach Zitaten (angefordert: "
            + str(url_abruf["angefordert"]) + " bzw. " + str(dom_abruf["angefordert"]) + "), "
            "nicht die Grundgesamtheit — der Long Tail fehlt"
            + (", die serverseitige Obergrenze war niedriger als angefordert"
               if url_abruf["erhalten"] < url_abruf["angefordert"] else "")
            + ". Fenster: rollierende " + str(args.days) + " Tage."
        ),
        "domains": dom_rows,
        "urls": url_rows,
        "brand_class_mix": by_brand_class,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[peec_sources] {OUT_FILE} geschrieben ({OUT_FILE.stat().st_size // 1024} KB)")
    tot = sum(d["cit"] for d in dom_rows)
    for d in dom_rows[:5]:
        print(f"  {d['domain']:<28} {str(d['cls']):<14} {d['cit']:>6} Zitate "
              f"({d['cit']/tot*100:.1f} % der Top-{len(dom_rows)})")


if __name__ == "__main__":
    main()
