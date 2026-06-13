#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Treiber-Tracker (Roadmap Punkt 3): emittiert Events fuer zitier-relevante,
steuerbare Sichtbarkeits-Treiber, sobald sie sich aendern:

  wikipedia_change    - Aenderung des deutschen Wikipedia-Artikels je Marke
                        (LLMs gewichten Wikipedia stark).
  portal_rank_change  - Aenderung des Preis-Rangs auf Check24 je Marke/Produkt
                        (Check24 ist die meistzitierte Portal-Quelle der LLMs).
  rating_status_change- Aenderung von Testsieger/Empfehlungs-Status je Marke/Produkt
                        (Finanztip/Warentest/M&M/DFSI aus ratings_external.json).

Vergleich gegen data/driver_state.json (letzter Stand). Erster Lauf legt nur den
Baseline an (keine Events). Aufruf im Nightly NACH update_prices.py + update_ratings.py,
VOR sov_history.py / correlation_impact.py.
"""
import json
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from shared.event_emitter import emit_event
    HAS_EVENTS = True
except Exception:
    HAS_EVENTS = False

STATE = Path("data/driver_state.json")
PRICE = Path("data/price_comparison.json")
RATINGS = Path("data/ratings_external.json")

# Unsere 10 Marken: key -> (Anzeigename, deutscher Wikipedia-Artikel)
BRANDS = {
    "ergo": ("ERGO", "ERGO Group"),
    "allianz": ("Allianz", "Allianz SE"),
    "axa": ("AXA", "AXA"),
    "huk": ("HUK-Coburg", "HUK-Coburg"),
    "generali": ("Generali", "Generali Deutschland"),
    "signal-iduna": ("Signal Iduna", "Signal Iduna"),
    "ruv": ("R+V", "R+V Versicherung"),
    "devk": ("DEVK", "DEVK"),
    "hannoversche": ("Hannoversche", "Hannoversche Leben"),
    "cosmosdirekt": ("Cosmos Direkt", "CosmosDirekt"),
}
PRICE_KEY_ALIAS = {"signal-iduna": "signal-iduna", "cosmosdirekt": "cosmosdirekt", "ruv": "ruv"}


def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def fetch_wikipedia():
    """Liefert {brand_name: {'length':int,'rev':str}} aus de.wikipedia.org."""
    out = {}
    for key, (name, title) in BRANDS.items():
        try:
            url = ("https://de.wikipedia.org/w/api.php?action=query&prop=revisions|info"
                   "&titles=" + urllib.parse.quote(title) +
                   "&rvprop=timestamp|size&redirects=1&format=json&formatversion=2")
            req = urllib.request.Request(url, headers={"User-Agent": "ERGO-GEO-Tracker/1.0"})
            d = json.loads(urllib.request.urlopen(req, timeout=20).read())
            pg = (d.get("query", {}).get("pages") or [{}])[0]
            if pg.get("missing"):
                continue
            revs = pg.get("revisions") or [{}]
            out[name] = {"length": pg.get("length"), "rev": revs[0].get("timestamp"),
                         "title": pg.get("title")}
        except Exception as e:
            print("  [wiki] %s: %s" % (name, str(e)[:60]))
        time.sleep(1.0)
    return out


def price_ranks():
    """Preis-Rang je (Produkt, Marke) auf Basis 50-Jahre-Profil, nur unsere Marken."""
    if not PRICE.exists():
        return {}
    try:
        d = json.loads(PRICE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    ranks = {}
    for prod, pdata in (d.get("products") or {}).items():
        prof = (pdata.get("profiles") or {}).get("age_50") or {}
        brands = prof.get("brands") or {}
        ours = []
        for key in BRANDS:
            b = brands.get(key)
            if b and isinstance(b.get("price"), (int, float)):
                ours.append((key, b["price"]))
        ours.sort(key=lambda kv: kv[1])
        for i, (key, _p) in enumerate(ours, start=1):
            ranks["%s|%s" % (prod, key)] = i
    return ranks


def rating_status():
    """Testsieger/Empfehlungs-Status je (Produkt, Marke) als Vergleichssignatur."""
    if not RATINGS.exists():
        return {}
    try:
        d = json.loads(RATINGS.read_text(encoding="utf-8"))
    except Exception:
        return {}
    name2key = {v[0]: k for k, v in BRANDS.items()}
    out = {}
    for prod in ("zahnzusatz", "sterbegeld", "risikoleben"):
        for v in (d.get(prod, {}) or {}).get("versicherer", []):
            key = name2key.get(v.get("name"))
            if not key:
                continue
            sig = "ft=%s|wt=%s|mm=%s|dfsi=%s" % (v.get("finanztip"), v.get("warentest"),
                                                 v.get("mm"), v.get("dfsi"))
            out["%s|%s" % (prod, key)] = sig
    return out


def _rating_score(sig):
    """Numerischer Qualitaets-Score aus der Rating-Signatur ft=..|wt=..|mm=..|dfsi=.."""
    if not sig:
        return 0.0
    parts = dict(p.split("=", 1) for p in sig.split("|") if "=" in p)
    sc = 0.0
    ft = (parts.get("ft") or "").lower()
    if "empfohlen" in ft and "nicht" not in ft:
        sc += 2
    elif "nicht empfohlen" in ft:
        sc -= 1
    wt = (parts.get("wt") or "").lower()
    for kw, v in (("sehr gut", 3), ("gut", 2), ("befriedigend", 1), ("nicht empfohlen", -1)):
        if kw in wt:
            sc += v; break
    mm = parts.get("mm") or ""
    try:
        sc += float(mm)
    except (TypeError, ValueError):
        pass
    dfsi = (parts.get("dfsi") or "").lower()
    for kw, v in (("hervorragend", 4), ("sehr gut", 3), ("gut", 2), ("befriedigend", 1)):
        if kw in dfsi:
            sc += v; break
    return sc


def main():
    state = load_state()
    new_state = {}
    n = 0

    # 1) Wikipedia
    print("[drivers] Wikipedia ...")
    wiki = fetch_wikipedia()
    new_state["wikipedia"] = wiki
    prev_wiki = state.get("wikipedia", {})
    for name, cur in wiki.items():
        pv = prev_wiki.get(name)
        if not pv:
            continue
        dlen = (cur.get("length") or 0) - (pv.get("length") or 0)
        changed_rev = cur.get("rev") and pv.get("rev") and cur["rev"] != pv["rev"]
        if changed_rev or abs(dlen) >= 200:
            if HAS_EVENTS:
                emit_event(event_type="wikipedia_change", brand=name, source="wikipedia",
                           crawler="track_drivers",
                           magnitude=min(abs(dlen) / 1000.0, 2.0) or 0.5,
                           sentiment=("positive" if dlen > 0 else "negative" if dlen < 0 else "neutral"),
                           detail={"metric": "article_length", "old": pv.get("length"),
                                   "new": cur.get("length"), "delta": dlen})
            n += 1

    # 2) Check24 Portal-Rang
    print("[drivers] Check24 Portal-Rang ...")
    ranks = price_ranks()
    new_state["portal_rank"] = ranks
    prev_ranks = state.get("portal_rank", {})
    for k, cur in ranks.items():
        pv = prev_ranks.get(k)
        if pv is None or pv == cur:
            continue
        prod, bkey = k.split("|", 1)
        name = BRANDS[bkey][0]
        if HAS_EVENTS:
            emit_event(event_type="portal_rank_change", brand=name, source="check24",
                       crawler="track_drivers", product=prod,
                       magnitude=min(abs(pv - cur) * 0.4, 2.0),
                       sentiment=("positive" if cur < pv else "negative"),
                       detail={"metric": "check24_price_rank", "old_rank": pv,
                               "new_rank": cur, "direction": "up" if cur < pv else "down"})
        n += 1

    # 3) Testsieger / Rating-Status
    print("[drivers] Rating-/Testsieger-Status ...")
    rat = rating_status()
    new_state["rating_status"] = rat
    prev_rat = state.get("rating_status", {})
    for k, cur in rat.items():
        pv = prev_rat.get(k)
        if pv is None or pv == cur:
            continue
        prod, bkey = k.split("|", 1)
        name = BRANDS[bkey][0]
        if HAS_EVENTS:
            _ds = _rating_score(cur) - _rating_score(pv)
            emit_event(event_type="rating_status_change", brand=name, source="ratings_external",
                       crawler="track_drivers", product=prod, magnitude=0.8,
                       sentiment=("positive" if _ds > 0 else "negative" if _ds < 0 else "neutral"),
                       detail={"metric": "test_status", "old": pv, "new": cur, "score_delta": round(_ds, 2)})
        n += 1

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(new_state, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OK: %d Treiber-Events emittiert, Baseline aktualisiert -> %s" % (n, STATE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
