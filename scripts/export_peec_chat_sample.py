#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Peec-Chat-Stichprobe + Matcher-Vergleich  ->  data/matcher_validation.json

ZWECK
Peec und unser eigener Crawl erkennen Markennennungen unabhaengig voneinander.
Laesst man BEIDE Matcher auf DENSELBEN Antworttext los, faellt eine echte
Uebereinstimmungsquote ab — also eine Schaetzung des Messfehlers statt der
bisherigen Aussage "die Aggregate stimmen ungefaehr ueberein". Genau danach
fragen Analysten und Aktuare zuerst.

WAS INS REPO GEHT — und was nicht
Peecs AGB beschraenken die Nutzung auf "internal business operations ... by its
own personnel" (§ 1.1, § 5.1). Deshalb landen im oeffentlichen Repo NUR die
aggregierten Vergleichszahlen sowie kurze Belegausschnitte (<= SNIPPET_CHARS
Zeichen) zu Abweichungen. Die Volltexte bleiben lokal in --raw-dir und werden
NICHT gepusht. Fuer den Audit-Trail Richtung Aktuare nutzen wir die Antworten
unseres EIGENEN Crawls (data/runs im GEO-Repo) — die unterliegen keiner
Fremdnutzungsschranke.

METHODE
1. Geschichtete Zufallsstichprobe: je (Thema x Engine) gleich viele Chats,
   Ziehung mit festem Seed -> reproduzierbar.
2. Je Chat: Peecs erkannte Marken (brands_mentioned) gegen unseren Matcher
   (analyzer/metrics.count_mentions aus dem GEO-Repo, im Original geladen,
   NICHT nachgebaut — ein Nachbau wuerde nichts beweisen).
3. Auszaehlung je Marke: beide erkannt / nur Peec / nur wir / beide nicht.
   Daraus Uebereinstimmung, Cohens Kappa und die Richtung der Abweichung.

Aufruf:
    PEEC_TOKEN=<pat> python3 scripts/export_peec_chat_sample.py \
        [--n 50] [--days 7] [--seed 20260719] [--raw-dir /pfad/lokal]
"""
import argparse
import json
import os
import random
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

MCP_URL = "https://api.peec.ai/mcp"
PROJECT_ID = os.environ.get("PEEC_PROJECT_ID", "or_9e1c1c57-28de-4714-bfc0-363bfa6a0757")
GEO_RAW = "https://raw.githubusercontent.com/phoeser/geo-visibility-tool/main"
OUT_FILE = Path("data/matcher_validation.json")
SNIPPET_CHARS = 200      # max. Belegausschnitt im oeffentlichen Repo
MAX_DISCREPANCIES = 25   # so viele Abweichungsbelege werden gespeichert
RETENTION_DAYS = 180     # rollierendes Fenster fuer die lokale Rohablage

_session = {}
_seq = [0]


# --------------------------------------------------------------------------
# Peec MCP
# --------------------------------------------------------------------------
def _rpc(method, params=None, want_id=True):
    token = os.environ.get("PEEC_TOKEN", "")
    if not token:
        sys.exit("FEHLER: PEEC_TOKEN nicht gesetzt.")
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
                        "clientInfo": {"name": "llm-cockpit-sample", "version": "1.0"}})
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


# --------------------------------------------------------------------------
# Unser Matcher — im Original aus dem GEO-Repo laden
# --------------------------------------------------------------------------
def load_own_matcher(tmp_dir: Path):
    """Laedt analyzer/metrics.py + data/config.json aus dem GEO-Repo.

    Bewusst der Originalcode: ein Nachbau wuerde die Frage, ob unser Matcher
    richtig zaehlt, gerade nicht beantworten.
    """
    tmp_dir.mkdir(parents=True, exist_ok=True)
    mpath = tmp_dir / "geo_metrics.py"
    for url, dest in ((f"{GEO_RAW}/analyzer/metrics.py", mpath),
                      (f"{GEO_RAW}/data/config.json", tmp_dir / "geo_config.json")):
        with urllib.request.urlopen(url, timeout=60) as r:
            dest.write_bytes(r.read())
    sys.path.insert(0, str(tmp_dir))
    import importlib
    metrics = importlib.import_module("geo_metrics")
    cfg = json.loads((tmp_dir / "geo_config.json").read_text(encoding="utf-8"))
    specs = [metrics.BrandSpec(name=cfg["brand"]["name"], aliases=cfg["brand"]["aliases"],
                               domain=cfg["brand"]["domain"],
                               extra_domains=list(cfg["brand"].get("extra_domains") or []))]
    for c in cfg["competitors"]:
        specs.append(metrics.BrandSpec(name=c["name"], aliases=c["aliases"],
                                       domain=c["domain"],
                                       extra_domains=list(c.get("extra_domains") or [])))
    return metrics, specs


def cohens_kappa(both, only_a, only_b, neither):
    """Cohens Kappa fuer zwei binaere Bewerter."""
    n = both + only_a + only_b + neither
    if n == 0:
        return None
    po = (both + neither) / n
    pa1, pb1 = (both + only_a) / n, (both + only_b) / n
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    if abs(1 - pe) < 1e-12:
        return None
    return round((po - pe) / (1 - pe), 4)


def prune_raw(raw_dir: Path, days: int):
    """Rollierendes Fenster fuer die lokale Rohablage (Volltexte)."""
    if not raw_dir.is_dir():
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    gone = 0
    for p in raw_dir.glob("*.json"):
        m = re.match(r"^(\d{4}-\d{2}-\d{2})", p.name)
        if m and m.group(1) < cutoff:
            p.unlink()
            gone += 1
    return gone


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50, help="Stichprobengroesse")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--seed", type=int, default=20260719)
    ap.add_argument("--raw-dir", default="", help="Lokale Ablage der Volltexte (NICHT ins Repo)")
    args = ap.parse_args()

    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    S, E = (end - timedelta(days=args.days)).isoformat(), end.isoformat()
    print(f"[sample] Fenster {S}..{E}, n={args.n}, seed={args.seed}")

    metrics, specs = load_own_matcher(Path("/tmp/geo_matcher"))
    print(f"[sample] Matcher geladen: {len(specs)} Marken aus dem GEO-Repo")

    _connect()

    chats = _tab(_call("list_chats", {"project_id": PROJECT_ID, "start_date": S,
                                      "end_date": E, "limit": 1000}))
    if not chats:
        sys.exit("[sample] Keine Chats im Fenster.")
    print(f"[sample] {len(chats)} Chats in der Grundgesamtheit (erste Seite)")

    # Geschichtet nach Engine (model_channel_id), Ziehung mit festem Seed
    rnd = random.Random(args.seed)
    strata = defaultdict(list)
    for c in chats:
        strata[c.get("model_channel_id") or "?"].append(c)
    per = max(1, args.n // max(len(strata), 1))
    picked = []
    for k in sorted(strata):
        pool = sorted(strata[k], key=lambda x: x["id"])
        rnd.shuffle(pool)
        picked += pool[:per]
    picked = picked[:args.n]
    print(f"[sample] {len(picked)} Chats gezogen aus {len(strata)} Engine-Schichten")

    peec_names = {}
    counts = defaultdict(lambda: {"both": 0, "only_peec": 0, "only_own": 0, "neither": 0})
    discrepancies = []
    raw_dir = Path(args.raw_dir) if args.raw_dir else None
    raw_payload = []
    n_ok = 0

    for i, c in enumerate(picked, 1):
        try:
            full = _call("get_chat", {"project_id": PROJECT_ID, "chat_id": c["id"]})
        except Exception as ex:  # noqa: BLE001
            print(f"[sample] {c['id']}: {ex}")
            continue
        msgs = full.get("messages") or []
        answer = ""
        for m in msgs:
            role = (m.get("role") or "").lower()
            if role in ("assistant", "model") or (not role and m is msgs[-1]):
                answer = str(m.get("content") or "")
        if not answer and len(msgs) > 1:
            answer = str(msgs[-1].get("content") or "")
        if not answer:
            continue
        n_ok += 1

        peec_set = set()
        for b in full.get("brands_mentioned") or []:
            nm = b.get("name") if isinstance(b, dict) else str(b)
            if nm:
                peec_set.add(nm.strip())
                peec_names[nm.strip()] = True

        for sp in specs:
            own_hit = metrics.count_mentions(answer, sp) > 0
            peec_hit = sp.name in peec_set
            key = sp.name
            if own_hit and peec_hit:
                counts[key]["both"] += 1
            elif peec_hit:
                counts[key]["only_peec"] += 1
                if len(discrepancies) < MAX_DISCREPANCIES:
                    discrepancies.append({"brand": key, "art": "nur Peec", "chat": c["id"],
                                          "engine": c.get("model_channel_id"),
                                          "auszug": answer[:SNIPPET_CHARS]})
            elif own_hit:
                counts[key]["only_own"] += 1
                if len(discrepancies) < MAX_DISCREPANCIES:
                    hit = next(metrics._iter_valid_mentions(answer, sp), None)
                    start = max(0, (hit.start() - 60)) if hit else 0
                    discrepancies.append({"brand": key, "art": "nur eigener Crawl", "chat": c["id"],
                                          "engine": c.get("model_channel_id"),
                                          "auszug": answer[start:start + SNIPPET_CHARS]})
            else:
                counts[key]["neither"] += 1

        if raw_dir:
            raw_payload.append({"chat_id": c["id"], "date": c.get("date"),
                                "engine": c.get("model_channel_id"),
                                "prompt": str((msgs[0] or {}).get("content") or "")[:2000],
                                "answer": answer,
                                "peec_brands": sorted(peec_set),
                                "sources": [s.get("url") for s in (full.get("sources") or [])]})
        if i % 10 == 0:
            print(f"[sample]   {i}/{len(picked)} …")

    # ---- Kennzahlen --------------------------------------------------------
    per_brand, tb, tp, to, tn = [], 0, 0, 0, 0
    for name, c in sorted(counts.items(), key=lambda kv: -(kv[1]["both"] + kv[1]["only_peec"] + kv[1]["only_own"])):
        n = c["both"] + c["only_peec"] + c["only_own"] + c["neither"]
        agree = (c["both"] + c["neither"]) / n if n else None
        per_brand.append({
            "brand": name, "beide": c["both"], "nur_peec": c["only_peec"],
            "nur_eigen": c["only_own"], "keiner": c["neither"],
            "uebereinstimmung_pct": round(agree * 100, 2) if agree is not None else None,
            "kappa": cohens_kappa(c["both"], c["only_peec"], c["only_own"], c["neither"]),
        })
        tb += c["both"]; tp += c["only_peec"]; to += c["only_own"]; tn += c["neither"]

    total = tb + tp + to + tn
    out = {
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "window": {"start": S, "end": E, "days": args.days},
        "stichprobe": {"angefragt": args.n, "ausgewertet": n_ok, "seed": args.seed,
                       "schichtung": "je Engine (model_channel_id) gleich viele Chats",
                       "grundgesamtheit_seite1": len(chats)},
        "gesamt": {
            "vergleiche": total, "beide": tb, "nur_peec": tp, "nur_eigen": to, "keiner": tn,
            "uebereinstimmung_pct": round((tb + tn) / total * 100, 2) if total else None,
            "kappa": cohens_kappa(tb, tp, to, tn),
        },
        "je_marke": per_brand,
        "abweichungen": discrepancies,
        "methode": (
            "Geschichtete Zufallsstichprobe (Seed fest, daher reproduzierbar). Je Chat laufen "
            "BEIDE Matcher auf demselben Antworttext: Peecs brands_mentioned und "
            "analyzer/metrics.count_mentions aus dem GEO-Repo im Original. Verglichen wird "
            "je Marke binaer (genannt / nicht genannt). Kappa korrigiert die Uebereinstimmung "
            "um den Zufallsanteil — bei seltenen Marken ist die reine Quote irrefuehrend hoch."
        ),
        "grenzen": (
            "Kein Goldstandard: Weicht ein Matcher ab, ist damit NICHT gesagt, welcher recht "
            "hat — das zeigen erst die Belegausschnitte. Die Stichprobe deckt ein "
            + str(args.days) + "-Tage-Fenster und die erste Seite der Grundgesamtheit ab. "
            "Peecs AGB beschraenken die Nutzung auf den eigenen Geschaeftsbetrieb, deshalb "
            "stehen hier nur Kennzahlen und Ausschnitte bis "
            + str(SNIPPET_CHARS) + " Zeichen, keine Volltexte."
        ),
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[sample] {OUT_FILE} geschrieben")
    print(f"[sample] {n_ok} Antworten, {total} Marken-Vergleiche, "
          f"Uebereinstimmung {out['gesamt']['uebereinstimmung_pct']} %, Kappa {out['gesamt']['kappa']}")
    print(f"[sample]   beide={tb} nur_peec={tp} nur_eigen={to} keiner={tn}")

    if raw_dir and raw_payload:
        raw_dir.mkdir(parents=True, exist_ok=True)
        f = raw_dir / f"{E}_chat_sample.json"
        f.write_text(json.dumps(raw_payload, ensure_ascii=False, indent=1), encoding="utf-8")
        gone = prune_raw(raw_dir, RETENTION_DAYS)
        print(f"[sample] Volltexte lokal: {f} ({f.stat().st_size // 1024} KB)"
              + (f", {gone} Datei(en) aelter als {RETENTION_DAYS} Tage entfernt" if gone else ""))
        print("[sample] HINWEIS: diese Datei NICHT ins oeffentliche Repo pushen.")


if __name__ == "__main__":
    main()
