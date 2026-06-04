#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Review-Themen-Clustering: Klassifiziert echte Bewertungstexte (Google-Berater,
Google, eKomi, Check24) per Gemini in Themen + Sentiment und aggregiert je Marke.

Quellen:
  - data/berater_reviews.json   (Google Places, ERGO-Berater-Stichprobe, Volltexte)
  - data/review_history.json    (Google/eKomi/Check24-Einzelbewertungen)

Output: data/review_themes.json   (vom Dashboard gelesen, Bewertungen-Tab)
Cache:  data/review_themes_cache.json  (md5(text) -> Klassifikation; spart API-Kosten)

Aufruf: GEMINI_API_KEY=... python scripts/review_themes.py
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BERATER_FILE = Path("data/berater_reviews.json")
HISTORY_FILE = Path("data/review_history.json")
OUT_FILE = Path("data/review_themes.json")
CACHE_FILE = Path("data/review_themes_cache.json")

THEMES = [
    "Beratungsqualität",
    "Freundlichkeit & Service",
    "Erreichbarkeit & Reaktionszeit",
    "Schadenregulierung & Leistungsfall",
    "Preis-Leistung",
    "Vertrag & Abwicklung",
    "Digitale Services",
    "Sonstiges",
]
BATCH_SIZE = 25
MAX_QUOTE_LEN = 180


def _md5(t):
    return hashlib.md5(t.strip().lower().encode("utf-8")).hexdigest()


def collect_reviews():
    """Alle Texte einsammeln -> Liste {id, brand, source, text, rating, date}."""
    out = []
    seen = set()

    def add(brand, source, text, rating, date):
        text = (text or "").strip()
        if len(text) < 25 or "Aggregiertes Rating" in text:
            return
        h = _md5(text)
        if h in seen:
            return
        seen.add(h)
        d = str(date or "")[:10] if date else None
        if d and not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
            d = None
        out.append({"id": h, "brand": brand or "ergo", "source": source,
                    "text": text[:600], "rating": rating, "date": d})

    if BERATER_FILE.exists():
        try:
            br = json.loads(BERATER_FILE.read_text(encoding="utf-8"))
            for agency in br.get("reviews", []):
                for r in (agency.get("reviews") or []):
                    add("ergo", "Google (Berater)", r.get("text"), r.get("rating"), r.get("time"))
        except Exception as e:
            print("WARN berater_reviews:", str(e)[:80])

    if HISTORY_FILE.exists():
        try:
            for r in json.loads(HISTORY_FILE.read_text(encoding="utf-8")):
                add(r.get("brand"), r.get("source"), r.get("text"), r.get("score"), r.get("date"))
        except Exception as e:
            print("WARN review_history:", str(e)[:80])

    return out


def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def classify_batch(reviews, api_key):
    """Ein Gemini-Call fuer bis zu BATCH_SIZE Reviews. Gibt {id: {themes, sentiment}} zurueck."""
    items = "\n".join(
        '%d. "%s"' % (i + 1, r["text"][:300].replace('"', "'").replace("\n", " "))
        for i, r in enumerate(reviews)
    )
    prompt = (
        "Du bist ein Analyst fuer Versicherungs-Kundenbewertungen. Klassifiziere jede "
        "der folgenden Bewertungen.\n"
        "Erlaubte Themen (1-2 pro Bewertung, exakt diese Schreibweise): "
        + "; ".join(THEMES) + ".\n"
        "Sentiment: positiv, neutral oder negativ.\n"
        "Antworte NUR mit einem JSON-Array, ein Objekt je Bewertung in der gegebenen "
        'Reihenfolge: [{"nr": 1, "themes": ["..."], "sentiment": "positiv"}, ...]\n\n'
        "Bewertungen:\n" + items
    )
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 16384,
                             "responseMimeType": "application/json"},
    }).encode("utf-8")
    # Gleiches Aufruf-Muster wie update_sentiment.py (nachweislich funktionierend)
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "gemini-flash-latest:generateContent?key=%s" % api_key)
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as he:
        try:
            detail = he.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            detail = ""
        raise RuntimeError("HTTP %s: %s" % (he.code, detail))
    txt = data["candidates"][0]["content"]["parts"][0]["text"]
    m = re.search(r"\[.*\]", txt, re.S)
    if not m:
        raise ValueError("kein JSON-Array in Gemini-Antwort")
    arr = json.loads(m.group(0))
    out = {}
    for obj in arr:
        try:
            idx = int(obj.get("nr", 0)) - 1
            if 0 <= idx < len(reviews):
                themes = [t for t in (obj.get("themes") or []) if t in THEMES] or ["Sonstiges"]
                senti = obj.get("sentiment", "neutral")
                if senti not in ("positiv", "neutral", "negativ"):
                    senti = "neutral"
                out[reviews[idx]["id"]] = {"themes": themes, "sentiment": senti}
        except Exception:
            continue
    return out


def main():
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    reviews = collect_reviews()
    print("[themes] %d Bewertungstexte gesammelt" % len(reviews))
    if not reviews:
        print("[themes] nichts zu tun")
        return 0

    cache = load_cache()
    todo = [r for r in reviews if r["id"] not in cache]
    print("[themes] %d bereits klassifiziert (Cache), %d neu" % (len(reviews) - len(todo), len(todo)))

    if todo and not api_key:
        print("[themes] WARN: GEMINI_API_KEY fehlt — nutze nur Cache")
        todo = []

    failed = 0
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i + BATCH_SIZE]
        try:
            res = classify_batch(batch, api_key)
            cache.update(res)
            failed = 0
            print("[themes] Batch %d: %d/%d klassifiziert" % (i // BATCH_SIZE + 1, len(res), len(batch)))
        except Exception as e:
            failed += 1
            print("[themes] Batch-Fehler: %s" % str(e)[:120])
            time.sleep(10)
            if failed >= 5:
                print("[themes] zu viele Fehler — breche Klassifikation ab (Cache bleibt)")
                break
        time.sleep(4)  # Gemini-Rate-Limit (free tier: 15 Anfragen/Minute)

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    # ===== Aggregation je Marke =====
    agg = {}
    classified = 0
    for r in reviews:
        c = cache.get(r["id"])
        if not c:
            continue
        classified += 1
        b = agg.setdefault(r["brand"], {"total": 0, "themes": {}, "reviews": []})
        b["total"] += 1
        b["reviews"].append({
            "date": r.get("date"), "rating": r.get("rating"),
            "sentiment": c["sentiment"], "source": r["source"],
            "themes": c["themes"], "text": r["text"][:400],
        })
        for t in c["themes"]:
            th = b["themes"].setdefault(t, {"count": 0, "positiv": 0, "neutral": 0, "negativ": 0, "quotes": []})
            th["count"] += 1
            th[c["sentiment"]] += 1
            if len(th["quotes"]) < 3 and len(r["text"]) > 40:
                th["quotes"].append({
                    "text": r["text"][:MAX_QUOTE_LEN] + ("…" if len(r["text"]) > MAX_QUOTE_LEN else ""),
                    "rating": r.get("rating"), "source": r["source"],
                    "sentiment": c["sentiment"],
                })

    for b in agg.values():
        b["themes"] = dict(sorted(b["themes"].items(), key=lambda kv: -kv[1]["count"]))
        # chronologisch absteigend (None-Daten ans Ende) — fuer Ampel/Trend/Lesen
        b["reviews"].sort(key=lambda r: (r.get("date") or "0000-00-00"), reverse=True)
        b["reviews"] = b["reviews"][:300]

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": "gemini-flash-latest",
        "themes_taxonomy": THEMES,
        "reviews_total": len(reviews),
        "reviews_classified": classified,
        "by_brand": agg,
    }
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[themes] OK: %s (%d Marken, %d/%d klassifiziert)" % (OUT_FILE, len(agg), classified, len(reviews)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
