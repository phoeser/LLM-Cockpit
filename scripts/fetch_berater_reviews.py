#!/usr/bin/env python3
"""
Einmaliges Skript: Google Places Reviews für ERGO Berater-Agenturen.
Liest berater_data.json, sucht jeden Berater auf Google Places,
speichert Rating, Review-Count und bis zu 5 Reviews pro Berater.

Nutzung:
  GOOGLE_PLACES_API_KEY=xxx python scripts/fetch_berater_reviews.py

Kosten: ~$0.032 pro Text Search + ~$0.017 pro Place Details = ~$0.05 pro Berater
Bei 300 Beratern: ca. 15 EUR
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────────
API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")
BERATER_FILE = Path(__file__).resolve().parent.parent / "berater_data.json"
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "berater_reviews.json"
MAX_REVIEWS = 5       # Google Places API gibt max 5 Reviews zurück
DELAY_BETWEEN = 0.3   # Sekunden zwischen API-Calls (Rate Limiting)
BATCH_SIZE = 50       # Status-Update alle N Berater

# ─── API Helpers ──────────────────────────────────────────────────

def places_text_search(query):
    """Google Places API (New) — Text Search, gibt place_id zurück."""
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "places.id,places.displayName,places.rating,places.userRatingCount,places.formattedAddress"
    }
    body = json.dumps({
        "textQuery": query,
        "languageCode": "de",
        "maxResultCount": 1
    }).encode("utf-8")
    
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            places = data.get("places", [])
            if places:
                return places[0]
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"  HTTP {e.code}: {err_body[:200]}")
    except Exception as e:
        print(f"  Error: {e}")
    return None


def places_get_reviews(place_id):
    """Google Places API (New) — Place Details für Reviews."""
    url = f"https://places.googleapis.com/v1/{place_id}"
    headers = {
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "reviews,rating,userRatingCount"
    }
    
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"  Reviews HTTP {e.code}: {err_body[:200]}")
    except Exception as e:
        print(f"  Reviews Error: {e}")
    return None


def format_review(review):
    """Extrahiert relevante Felder aus einem Google Review."""
    text_obj = review.get("text", {})
    return {
        "author": review.get("authorAttribution", {}).get("displayName", "Unbekannt"),
        "rating": review.get("rating", 0),
        "text": text_obj.get("text", "") if isinstance(text_obj, dict) else str(text_obj),
        "time": review.get("publishTime", ""),
        "language": text_obj.get("languageCode", "de") if isinstance(text_obj, dict) else "de"
    }


# ─── Main ─────────────────────────────────────────────────────────

def main():
    if not API_KEY:
        print("ERROR: GOOGLE_PLACES_API_KEY nicht gesetzt!")
        sys.exit(1)
    
    # Berater-Daten laden
    if not BERATER_FILE.exists():
        print(f"ERROR: {BERATER_FILE} nicht gefunden!")
        sys.exit(1)
    
    with open(BERATER_FILE, "r", encoding="utf-8") as f:
        berater_data = json.load(f)
    
    vermittler = berater_data.get("vermittler", [])
    print(f"Starte Google Places Review-Abfrage für {len(vermittler)} Berater...")
    
    # Bereits vorhandene Reviews laden (für Resume)
    reviews_data = {}
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)
            reviews_data = {r["key"]: r for r in existing.get("reviews", [])}
        print(f"  {len(reviews_data)} bestehende Einträge geladen (Resume-Modus)")
    
    stats = {"found": 0, "not_found": 0, "skipped": 0, "errors": 0, "with_reviews": 0}
    
    for i, v in enumerate(vermittler):
        key = f"{v.get('firstname','').strip()}_{v.get('lastname','').strip()}_{v.get('city','').strip()}"
        key = key.replace(" ", "_").lower()
        
        # Skip wenn bereits vorhanden
        if key in reviews_data:
            stats["skipped"] += 1
            continue
        
        name = f"{v.get('firstname','')} {v.get('lastname','')}".strip()
        city = v.get("city", "")
        
        # Suchquery: "ERGO Berater [Name] [Stadt]"
        query = f"ERGO Versicherung {name} {city}"
        
        if (i + 1) % BATCH_SIZE == 0 or i == 0:
            print(f"\n--- Berater {i+1}/{len(vermittler)} ---")
        
        print(f"  [{i+1}] {name}, {city} ... ", end="", flush=True)
        
        # 1. Text Search — Place finden
        place = places_text_search(query)
        time.sleep(DELAY_BETWEEN)
        
        if not place:
            print("nicht gefunden")
            reviews_data[key] = {
                "key": key,
                "name": name,
                "city": city,
                "found": False,
                "rating": None,
                "review_count": 0,
                "reviews": []
            }
            stats["not_found"] += 1
            continue
        
        place_id = place.get("id", "")
        rating = place.get("rating", 0)
        review_count = place.get("userRatingCount", 0)
        address = place.get("formattedAddress", "")
        display_name = place.get("displayName", {}).get("text", "")
        
        print(f"gefunden: {display_name} | {rating}★ ({review_count} Reviews)")
        stats["found"] += 1
        
        # 2. Place Details — Reviews holen (nur wenn Reviews vorhanden)
        reviews = []
        if review_count > 0 and place_id:
            details = places_get_reviews(place_id)
            time.sleep(DELAY_BETWEEN)
            
            if details and details.get("reviews"):
                reviews = [format_review(r) for r in details["reviews"][:MAX_REVIEWS]]
                stats["with_reviews"] += 1
        
        reviews_data[key] = {
            "key": key,
            "name": name,
            "city": city,
            "found": True,
            "place_id": place_id,
            "place_name": display_name,
            "address": address,
            "rating": rating,
            "review_count": review_count,
            "reviews": reviews
        }
        
        # Zwischenspeichern alle 20 Berater
        if (i + 1) % 20 == 0:
            _save(reviews_data)
            print(f"  >>> Zwischengespeichert ({len(reviews_data)} Einträge)")
    
    # Final speichern
    _save(reviews_data)
    
    # Stats
    print(f"\n{'='*50}")
    print(f"ERGEBNIS:")
    print(f"  Gefunden:      {stats['found']}")
    print(f"  Nicht gefunden: {stats['not_found']}")
    print(f"  Übersprungen:  {stats['skipped']}")
    print(f"  Mit Reviews:   {stats['with_reviews']}")
    print(f"  Gesamt:        {len(reviews_data)} Einträge")
    
    # Durchschnitts-Rating berechnen
    rated = [r for r in reviews_data.values() if r.get("rating") and r["rating"] > 0]
    if rated:
        avg = sum(r["rating"] for r in rated) / len(rated)
        print(f"  Durchschnitts-Rating: {avg:.2f}★ (über {len(rated)} Agenturen)")
    
    print(f"\nGespeichert: {OUTPUT_FILE}")


def _save(reviews_data):
    """Speichert Reviews als JSON."""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    all_reviews = list(reviews_data.values())
    rated = [r for r in all_reviews if r.get("rating") and r["rating"] > 0]
    avg_rating = sum(r["rating"] for r in rated) / len(rated) if rated else 0
    
    output = {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "total_agencies": len(all_reviews),
        "found_on_google": sum(1 for r in all_reviews if r.get("found")),
        "with_reviews": sum(1 for r in all_reviews if r.get("reviews")),
        "average_rating": round(avg_rating, 2),
        "reviews": all_reviews
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
