#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google-Reviews der zentralen MARKEN-Profile aller 10 Versicherer.

Zweck: Vergleichbare Datenbasis fuer das Review-Themen-Clustering — fuer jede
Marke dieselbe Mechanik (neueste deutsche Google-Reviews der Hauptprofile),
analog zum Berater-Crawl, aber je Marke 1-3 zentrale Standorte.

Output: data/brand_reviews.json
Aufruf: GOOGLE_PLACES_API_KEY=... python scripts/fetch_brand_reviews.py
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "brand_reviews.json"
DELAY = 0.5

# Je Marke 1-3 Suchanfragen fuer zentrale Profile (Hauptsitz/Direktversicherer)
BRAND_QUERIES = {
    "ergo": ["ERGO Group AG Düsseldorf", "ERGO Versicherung Hauptverwaltung Düsseldorf"],
    "allianz": ["Allianz Deutschland AG München", "Allianz SE München"],
    "axa": ["AXA Versicherung AG Köln"],
    "huk": ["HUK-COBURG Versicherung Coburg Zentrale", "HUK24 AG Coburg"],
    "generali": ["Generali Deutschland AG München"],
    "signal-iduna": ["SIGNAL IDUNA Gruppe Dortmund", "SIGNAL IDUNA Hamburg"],
    "ruv": ["R+V Versicherung AG Wiesbaden"],
    "devk": ["DEVK Versicherungen Zentrale Köln"],
    "hannoversche": ["Hannoversche Lebensversicherung AG Hannover"],
    "cosmosdirekt": ["CosmosDirekt Saarbrücken"],
}


def search_place(query):
    body = json.dumps({"textQuery": query, "languageCode": "de", "maxResultCount": 1}).encode()
    req = urllib.request.Request(
        "https://places.googleapis.com/v1/places:searchText", data=body,
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": API_KEY,
                 "X-Goog-FieldMask": "places.id,places.displayName,places.rating,places.userRatingCount,places.formattedAddress"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            places = json.loads(r.read().decode()).get("places") or []
            return places[0] if places else None
    except Exception as e:
        print("  Suche-Fehler:", str(e)[:100])
        return None


def get_reviews(place_id):
    """Legacy Details API: neueste deutsche Reviews."""
    url = ("https://maps.googleapis.com/maps/api/place/details/json?place_id=%s"
           "&fields=reviews,rating,user_ratings_total&reviews_sort=newest"
           "&language=de&key=%s" % (place_id, API_KEY))
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            d = json.loads(r.read().decode())
        if d.get("status") != "OK":
            print("  Details-Status:", d.get("status"))
            return None
        return d.get("result") or {}
    except Exception as e:
        print("  Details-Fehler:", str(e)[:100])
        return None


def main():
    if not API_KEY:
        print("FEHLER: GOOGLE_PLACES_API_KEY fehlt")
        return 1
    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "brands": {}}
    for brand, queries in BRAND_QUERIES.items():
        entries = []
        for q in queries:
            place = search_place(q)
            time.sleep(DELAY)
            if not place:
                print("[%s] nicht gefunden: %s" % (brand, q))
                continue
            pid = place.get("id")
            res = get_reviews(pid) if pid else None
            time.sleep(DELAY)
            revs = []
            for r in (res or {}).get("reviews") or []:
                txt = (r.get("text") or "").strip()
                if not txt:
                    continue
                revs.append({
                    "author": r.get("author_name", "?"),
                    "rating": r.get("rating"),
                    "text": txt[:600],
                    "time": datetime.utcfromtimestamp(r.get("time", 0)).strftime("%Y-%m-%dT%H:%M:%SZ") if r.get("time") else "",
                    "language": r.get("language", "de"),
                })
            entries.append({
                "query": q,
                "place_name": (place.get("displayName") or {}).get("text", ""),
                "place_id": pid,
                "rating": (res or {}).get("rating") or place.get("rating"),
                "review_count": (res or {}).get("user_ratings_total") or place.get("userRatingCount"),
                "reviews": revs,
            })
            print("[%s] %s: %d Texte" % (brand, q, len(revs)))
        out["brands"][brand] = entries
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(len(r["reviews"]) for b in out["brands"].values() for r in b)
    print("OK: %s (%d Texte)" % (OUTPUT_FILE, total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
