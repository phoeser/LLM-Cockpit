"""Sammelt ECHTE Sentiment-Daten fuer 10 Versicherer aus 5 Quellen und patcht dashboard_template.html.

Quellen:
1. Trustpilot    (urllib + Playwright-Fallback)  — Score + Count
2. eKomi         (HTML-Scrape)                   — Score + Count
3. Google Places (API, braucht GOOGLE_PLACES_API_KEY) — Score + Count
4. Check24       (JSON-LD-Scrape, produktspezifisch)  — Score + Count
5. Franke & Bornberg (AJAX-API, produktspezifisch)    — Ratingklasse + Schulnote

Workflow: laeuft in github-deployment/ als CWD
Output:
- data/sentiment_data.json (alle Rohdaten + Aggregate)
- dashboard_template.html: SENTIMENT_DATA-Block gepatcht
"""
import json
import re
import os
import sys
import gzip
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from datetime import datetime, timezone


# Event-Emitter für Korrelations-Engine
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from shared.event_emitter import emit_event, load_previous_data, save_for_comparison
    HAS_EVENTS = True
except ImportError:
    HAS_EVENTS = False

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# ── Brand-Konfiguration ──────────────────────────────────────────────────────
BRANDS = [
    {
        "key": "ergo", "name": "ERGO", "domain": "ergo.de",
        "ekomi_slugs": ["ergo-direkt-versicherungen-regulierung", "ergo-versicherungsgruppe"],
        "ekomi_multi": None,
        "google_query": "ERGO Group AG Düsseldorf Versicherung",
        "check24_slug": "ergo",
        "fb_keywords": ["ERGO"],
        "products": [
            {"name": "KFZ-Versicherung", "ekomi": "ergo-versicherung-service"},
            {"name": "Krankenversicherung", "ekomi": "ergo-versicherungsgruppe"},
            {"name": "Reiseversicherung", "ekomi": "reiseversicherungde"},
            {"name": "Rechtsschutz (DAS)", "ekomi": "das-rechtsschutzversicherung"},
            {"name": "Schadenregulierung", "ekomi": "ergo-direkt-versicherungen-regulierung"},
            {"name": "Vermittler-Service", "ekomi": "ergo-versicherung"},
            {"name": "Online-Abschluss", "ekomi": "ergo-direkt-versicherungen-abschluss"},
        ],
    },
    {
        "key": "allianz", "name": "Allianz", "domain": "allianz.de",
        "ekomi_slugs": ["allianz-kfz-versicherung"],
        "ekomi_multi": "allianz-kundenbewertungen",
        "google_query": "Allianz Versicherung München Deutschland",
        "check24_slug": "allianz",
        "fb_keywords": ["Allianz"],
        "products": [
            {"name": "KFZ-Versicherung", "ekomi": "allianz-kfz-versicherung"},
            {"name": "Reiserücktritt", "ekomi": "allianz-reiseruecktrittsversicherung"},
            {"name": "Reisekranken", "ekomi": "allianz-reisekrankenversicherung"},
            {"name": "Unfallversicherung", "ekomi": "allianz-unfallversicherung"},
            {"name": "Risikolebensversicherung", "ekomi": "allianz-risikolebensversicherung"},
            {"name": "Haftpflicht", "ekomi": "allianz-privat-haftpflichtversicherung"},
        ],
    },
    {
        "key": "axa", "name": "AXA", "domain": "axa.de",
        "ekomi_slugs": ["axa-nps", "axa-konzern-ag-service"],
        "ekomi_multi": None,
        "google_query": "AXA Versicherung Deutschland Köln",
        "check24_slug": "axa",
        "fb_keywords": ["AXA"],
        "products": [
            {"name": "Schadenservice", "ekomi": "axa-nps"},
            {"name": "Kundenservice (DBV)", "ekomi": "axa-konzern-ag-service"},
            {"name": "Leistung (DBV)", "ekomi": "axa-de-dbv-leistung"},
        ],
    },
    {
        "key": "huk", "name": "HUK-Coburg", "domain": "huk.de",
        "ekomi_slugs": [],
        "ekomi_multi": None,
        "google_query": "HUK-Coburg Versicherung Coburg",
        "check24_slug": "huk-coburg",
        "fb_keywords": ["HUK-COBURG", "HUK"],
        "products": [],
    },
    {
        "key": "generali", "name": "Generali", "domain": "generali.de",
        "ekomi_slugs": [],
        "ekomi_multi": None,
        "google_query": "Generali Deutschland Versicherung München",
        "check24_slug": "generali",
        "fb_keywords": ["Generali"],
        "products": [],
    },
    {
        "key": "signal-iduna", "name": "Signal Iduna", "domain": "signal-iduna.de",
        "ekomi_slugs": [],
        "ekomi_multi": None,
        "google_query": "Signal Iduna Versicherung Dortmund",
        "check24_slug": "signal-iduna",
        "fb_keywords": ["SIGNAL IDUNA", "Signal Iduna"],
        "products": [],
    },
    {
        "key": "ruv", "name": "R+V", "domain": "ruv.de",
        "ekomi_slugs": ["ruv"],
        "ekomi_multi": None,
        "google_query": "R+V Versicherung Wiesbaden",
        "check24_slug": "r-und-v",
        "fb_keywords": ["R+V", "R + V", "Condor"],
        "products": [
            {"name": "Gesamt", "ekomi": "ruv"},
        ],
    },
    {
        "key": "devk", "name": "DEVK", "domain": "devk.de",
        "ekomi_slugs": ["devk"],
        "ekomi_multi": None,
        "google_query": "DEVK Versicherungen Köln",
        "check24_slug": "devk",
        "fb_keywords": ["DEVK"],
        "products": [
            {"name": "Gesamt", "ekomi": "devk"},
        ],
    },
    {
        "key": "hannoversche", "name": "Hannoversche", "domain": "hannoversche.de",
        "ekomi_slugs": ["hannoversche-leben"],
        "ekomi_multi": None,
        "google_query": "Hannoversche Lebensversicherung Hannover",
        "check24_slug": "hannoversche",
        "fb_keywords": ["Hannoversche"],
        "products": [
            {"name": "Lebensversicherung", "ekomi": "hannoversche-leben"},
        ],
    },
    {
        "key": "cosmosdirekt", "name": "Cosmos Direkt", "domain": "cosmosdirekt.de",
        "ekomi_slugs": [],
        "ekomi_multi": None,
        "google_query": "CosmosDirekt Versicherung Saarbrücken",
        "check24_slug": "cosmosdirekt",
        "fb_keywords": ["CosmosDirekt", "Cosmos"],
        "products": [],
    },
]

# ── Produktkategorien fuer produktspezifische Tabellen ────────────────────────
PRODUCT_CATEGORIES = [
    {
        "key": "zahnzusatz",
        "name": "Zahnzusatzversicherung",
        "check24_path": "zahnzusatzversicherung",
        "fb_rating_id": "gkvzahn_neu",
    },
    {
        "key": "sterbegeld",
        "name": "Sterbegeldversicherung",
        "check24_path": None,
        "fb_rating_id": None,
    },
    {
        "key": "risikoleben",
        "name": "Risikolebensversicherung",
        "check24_path": "risikolebensversicherung",
        "fb_rating_id": "hbs_rlv",
    },
]


# ── HTTP-Helper ──────────────────────────────────────────────────────────────
def fetch_html(url, timeout=15):
    """Holt HTML von einer URL, decompressed gzip falls noetig."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            if data[:2] == b"\x1f\x8b":
                data = gzip.decompress(data)
            return data.decode("utf-8", errors="ignore")
    except Exception as e:
        return None


def fetch_json(url, timeout=15):
    """Holt JSON von einer URL."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return None


def post_json(url, data_dict, timeout=15):
    """POST-Request mit Form-Daten, gibt JSON zurueck."""
    try:
        body = urllib.parse.urlencode(data_dict).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST", headers={
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return None


# ── 1. TRUSTPILOT ────────────────────────────────────────────────────────────
def crawl_trustpilot(domain):
    """Trustpilot-Score via urllib (JSON-LD aus HTML) + neueste Reviews."""
    url = "https://de.trustpilot.com/review/" + domain
    html = fetch_html(url)
    if not html:
        return {"score": None, "count": None, "url": url, "recent_reviews": [], "error": "fetch failed"}
    m_score = re.search(r'"ratingValue":\s*"?([\d.]+)"?', html)
    m_count = re.search(r'"reviewCount":\s*"?(\d+)"?', html)

    # Neueste Reviews aus JSON-LD extrahieren
    recent = []
    try:
        ld_blocks = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
        for block in ld_blocks:
            try:
                data = json.loads(block)
                reviews_list = None
                if isinstance(data, dict) and "review" in data:
                    reviews_list = data["review"]
                elif isinstance(data, dict) and "@graph" in data:
                    for item in data["@graph"]:
                        if isinstance(item, dict) and "review" in item:
                            reviews_list = item["review"]
                            break
                if reviews_list and isinstance(reviews_list, list):
                    for rv in reviews_list[:8]:
                        r_title = rv.get("name", rv.get("headline", ""))
                        r_body = rv.get("reviewBody", "")
                        r_rating = None
                        if "reviewRating" in rv and isinstance(rv["reviewRating"], dict):
                            try:
                                r_rating = float(rv["reviewRating"].get("ratingValue", 0))
                            except (ValueError, TypeError):
                                pass
                        r_date = rv.get("datePublished", "")[:10]
                        r_author = ""
                        if "author" in rv and isinstance(rv["author"], dict):
                            r_author = rv["author"].get("name", "")
                        if r_title or r_body:
                            recent.append({
                                "title": r_title[:120],
                                "text": r_body[:200],
                                "score": r_rating,
                                "date": r_date,
                                "author": r_author,
                            })
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
    except Exception:
        pass

    if m_score:
        return {
            "score": round(float(m_score.group(1)), 1),
            "count": int(m_count.group(1)) if m_count else None,
            "url": url,
            "recent_reviews": recent,
        }
    return {"score": None, "count": None, "url": url, "recent_reviews": [], "error": "no ratingValue found"}


def crawl_trustpilot_browser(brands_data):
    """Playwright-Fallback fuer Trustpilot (nur fuer Brands ohne urllib-Score)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [TP-Browser] playwright nicht installiert, skip")
        return {}
    import time
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"],
        )
        ctx = browser.new_context(
            user_agent=UA, locale="de-DE", timezone_id="Europe/Berlin",
            viewport={"width": 1280, "height": 800},
        )
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        page = ctx.new_page()
        for entry in brands_data:
            key = entry["key"]
            domain = entry["domain"]
            url = "https://de.trustpilot.com/review/" + domain
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                time.sleep(2)
                html = page.content()
                m_s = re.search(r'"ratingValue":\s*"?([\d.]+)"?', html)
                m_c = re.search(r'"reviewCount":\s*"?(\d+)"?', html)
                if m_s:
                    results[key] = {
                        "score": round(float(m_s.group(1)), 1),
                        "count": int(m_c.group(1)) if m_c else None,
                        "url": url,
                    }
                    print("  [TP-Browser] %s -> %.1f (%s)" % (entry["name"], results[key]["score"], results[key]["count"]))
            except Exception as e:
                print("  [TP-Browser] %s error: %s" % (entry["name"], str(e)[:60]))
            time.sleep(2)
        browser.close()
    return results


# ── 2. eKOMI ─────────────────────────────────────────────────────────────────
def crawl_ekomi(slugs, multi_id=None):
    """eKomi-Score aus HTML-Seite extrahieren. Nimmt den Slug mit den meisten Reviews."""
    best = {"score": None, "count": 0, "url": None}

    urls_to_try = []
    for s in slugs:
        urls_to_try.append("https://www.ekomi.de/bewertungen-%s.html" % s)
    if multi_id:
        urls_to_try.append("https://www.ekomi.de/certificate_multi.php?id=%s" % multi_id)

    for url in urls_to_try:
        html = fetch_html(url)
        if not html:
            continue
        m_title = re.search(r'Bewertung:\s*([\d.,]+)\s*Sterne\s*von\s*([\d.]+)\s*Bewertungen', html)
        if m_title:
            score_val = float(m_title.group(1).replace(",", "."))
            count_val = int(m_title.group(2).replace(".", ""))
            if count_val >= best["count"]:
                best = {"score": round(score_val, 1), "count": count_val, "url": url}
            continue
        m_score = re.search(r'"ratingValue"[:\s]*"?([\d.]+)"?', html)
        m_count = re.search(r'"ratingCount"[:\s]*"?(\d+)"?', html)
        if not m_count:
            m_count = re.search(r'"reviewCount"[:\s]*"?(\d+)"?', html)
        if not m_score:
            m_score = re.search(r'(\d[.,]\d)\s*/\s*5', html)
        if not m_count:
            m_count = re.search(r'von\s+(\d[\d.]*)\s+Bewertungen', html)
        if m_score:
            score = float(m_score.group(1).replace(",", "."))
            count_val = m_count.group(1).replace(".", "") if m_count else "0"
            count = int(count_val)
            if count >= best["count"]:
                best = {"score": round(score, 1), "count": count, "url": url}

    if best["score"] is not None:
        return best
    return {"score": None, "count": None, "url": urls_to_try[0] if urls_to_try else None}


def crawl_ekomi_products(products):
    """Crawlt eKomi-Produktseiten und gibt Liste mit Score/Count/URL pro Produkt zurueck."""
    results = []
    for prod in products:
        slug = prod.get("ekomi", "")
        if not slug:
            continue
        url = "https://www.ekomi.de/bewertungen-%s.html" % slug
        html = fetch_html(url)
        if not html:
            results.append({"name": prod["name"], "score": None, "count": None, "url": url})
            continue
        m_title = re.search(r'Bewertung:\s*([\d.,]+)\s*Sterne\s*von\s*([\d.]+)\s*Bewertungen', html)
        if m_title:
            score = round(float(m_title.group(1).replace(",", ".")), 1)
            count = int(m_title.group(2).replace(".", ""))
        else:
            m_score = re.search(r'"ratingValue"[:\s]*"?([\d.]+)"?', html)
            m_count = re.search(r'von\s+([\d.]+)\s+Bewertungen', html)
            score = round(float(m_score.group(1).replace(",", ".")), 1) if m_score else None
            count_str = m_count.group(1).replace(".", "") if m_count else None
            count = int(count_str) if count_str else None
        results.append({"name": prod["name"], "score": score, "count": count, "url": url})
    return results


# ── 3. GOOGLE PLACES ─────────────────────────────────────────────────────────
def _fetch_google_reviews(place_id, api_key):
    """Holt einzelne Reviews fuer einen Place via Place Details (New API)."""
    if not place_id or not api_key:
        return []
    details_url = "https://places.googleapis.com/v1/%s" % place_id
    try:
        req = urllib.request.Request(details_url, headers={
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "reviews",
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        reviews = data.get("reviews", [])
        result = []
        for rv in reviews[:10]:
            text_obj = rv.get("text", {})
            text = text_obj.get("text", "") if isinstance(text_obj, dict) else str(text_obj)
            author_obj = rv.get("authorAttribution", {})
            author = author_obj.get("displayName", "") if isinstance(author_obj, dict) else ""
            result.append({
                "text": text[:500],
                "score": rv.get("rating"),
                "date": rv.get("publishTime", "")[:10],
                "author": author,
            })
        print("    [Google Reviews] %d Reviews geholt" % len(result))
        return result
    except Exception as e:
        print("    [Google Reviews] Fehler: %s" % str(e)[:120])
        return []


def crawl_google_places(query, api_key):
    """Google Places API: New API (Text Search) zuerst, dann Legacy als Fallback.
    Bei Erfolg werden zusaetzlich einzelne Reviews per Place Details geholt."""
    if not api_key:
        return {"score": None, "count": None, "recent_reviews": [], "error": "no API key"}

    print("    [Google] API-Key vorhanden (%s...%s), Query: %s" % (api_key[:4], api_key[-4:], query[:40]))

    # ── Versuch 1: New Places API (Text Search) ──
    new_url = "https://places.googleapis.com/v1/places:searchText"
    payload = json.dumps({
        "textQuery": query,
        "languageCode": "de",
        "maxResultCount": 3,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(new_url, data=payload, method="POST", headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName,places.rating,places.userRatingCount,places.id,places.reviews",
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            resp_body = r.read().decode("utf-8")
            data = json.loads(resp_body)
        places = data.get("places", [])
        if places:
            best = max(places, key=lambda p: p.get("userRatingCount", 0))
            name_obj = best.get("displayName", {})
            matched = name_obj.get("text", "") if isinstance(name_obj, dict) else str(name_obj)
            score = best.get("rating")
            if score:
                # Reviews direkt aus searchText oder per Details-Call
                reviews_raw = best.get("reviews", [])
                reviews = []
                if reviews_raw:
                    for rv in reviews_raw[:10]:
                        text_obj = rv.get("text", {})
                        text = text_obj.get("text", "") if isinstance(text_obj, dict) else str(text_obj)
                        author_obj = rv.get("authorAttribution", {})
                        author = author_obj.get("displayName", "") if isinstance(author_obj, dict) else ""
                        reviews.append({
                            "text": text[:500],
                            "score": rv.get("rating"),
                            "date": rv.get("publishTime", "")[:10],
                            "author": author,
                        })
                    print("    [Google New] %d Reviews inline erhalten" % len(reviews))
                else:
                    # Fallback: Reviews per Place Details holen
                    place_id = best.get("id")
                    if place_id:
                        reviews = _fetch_google_reviews(place_id, api_key)

                return {
                    "score": round(score, 1),
                    "count": best.get("userRatingCount"),
                    "place_id": best.get("id"),
                    "matched_name": matched,
                    "api": "new",
                    "recent_reviews": reviews,
                }
            print("    [Google New] Treffer '%s' aber kein Rating" % matched)
        else:
            print("    [Google New] Keine Ergebnisse fuer: %s" % query[:50])
    except urllib.error.HTTPError as he:
        err_body = ""
        try:
            err_body = he.read().decode("utf-8", errors="ignore")[:200]
        except Exception:
            pass
        print("    [Google New] HTTP %d: %s" % (he.code, err_body))
    except Exception as e:
        print("    [Google New] Exception: %s" % str(e)[:120])

    # ── Versuch 2: Legacy Text Search API ──
    encoded = urllib.parse.quote(query)
    legacy_url = ("https://maps.googleapis.com/maps/api/place/textsearch/json"
                  "?query=%s&language=de&key=%s" % (encoded, api_key))
    try:
        req = urllib.request.Request(legacy_url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            legacy_data = json.loads(r.read().decode("utf-8"))
        status = legacy_data.get("status", "")
        if status == "OK":
            results_list = legacy_data.get("results", [])
            if results_list:
                best = max(results_list, key=lambda r: r.get("user_ratings_total", 0))
                if best.get("rating"):
                    # Legacy liefert keine Reviews inline — per Details nachladen
                    reviews = []
                    place_id = best.get("place_id")
                    if place_id:
                        # Legacy Place Details fuer Reviews
                        det_url = ("https://maps.googleapis.com/maps/api/place/details/json"
                                   "?place_id=%s&fields=reviews&language=de&key=%s" % (place_id, api_key))
                        try:
                            det_req = urllib.request.Request(det_url, headers={"User-Agent": UA})
                            with urllib.request.urlopen(det_req, timeout=15) as dr:
                                det_data = json.loads(dr.read().decode("utf-8"))
                            for rv in det_data.get("result", {}).get("reviews", [])[:10]:
                                reviews.append({
                                    "text": rv.get("text", "")[:500],
                                    "score": rv.get("rating"),
                                    "date": rv.get("time", ""),
                                    "author": rv.get("author_name", ""),
                                })
                            # Legacy date ist Unix-Timestamp, umwandeln
                            for rv in reviews:
                                if rv["date"] and isinstance(rv["date"], (int, float)):
                                    try:
                                        from datetime import datetime as dt
                                        rv["date"] = dt.utcfromtimestamp(rv["date"]).strftime("%Y-%m-%d")
                                    except Exception:
                                        rv["date"] = ""
                            print("    [Google Legacy Details] %d Reviews geholt" % len(reviews))
                        except Exception as de:
                            print("    [Google Legacy Details] Fehler: %s" % str(de)[:120])

                    return {
                        "score": round(best.get("rating", 0), 1),
                        "count": best.get("user_ratings_total"),
                        "place_id": place_id,
                        "matched_name": best.get("name"),
                        "api": "legacy",
                        "recent_reviews": reviews,
                    }
                print("    [Google Legacy] Treffer '%s' aber kein Rating" % best.get("name", "?"))
        elif status == "REQUEST_DENIED":
            print("    [Google Legacy] REQUEST_DENIED: %s" % legacy_data.get("error_message", "")[:120])
        else:
            print("    [Google Legacy] Status: %s — %s" % (status, legacy_data.get("error_message", "")[:80]))
    except urllib.error.HTTPError as he:
        err_body = ""
        try:
            err_body = he.read().decode("utf-8", errors="ignore")[:200]
        except Exception:
            pass
        print("    [Google Legacy] HTTP %d: %s" % (he.code, err_body))
    except Exception as e:
        print("    [Google Legacy] Exception: %s" % str(e)[:120])

    return {"score": None, "count": None, "recent_reviews": [], "error": "both APIs failed"}


# ── 4. CHECK24 ───────────────────────────────────────────────────────────────
def crawl_check24(slug, product_path):
    """Check24-Bewertung aus JSON-LD der Produkt-Versicherer-Seite extrahieren.

    URL-Muster: https://www.check24.de/{product_path}/{slug}/
    Liefert score (1-5) und count. Filtert Portal-Ratings raus.
    """
    if not product_path or not slug:
        return {"score": None, "count": None, "url": None}

    url = "https://www.check24.de/%s/%s/" % (product_path, slug)
    html = fetch_html(url, timeout=12)
    if not html:
        return {"score": None, "count": None, "url": url, "error": "fetch failed"}

    # JSON-LD aggregateRating suchen
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL):
        try:
            d = json.loads(m.group(1))
            if isinstance(d, dict) and d.get("aggregateRating"):
                ar = d["aggregateRating"]
                raw_score = ar.get("ratingValue")
                raw_count = ar.get("ratingCount") or ar.get("reviewCount")
                if raw_score is not None:
                    score = float(str(raw_score).replace(",", "."))
                    count = int(str(raw_count).replace(".", "")) if raw_count else None
                    return {
                        "score": round(score, 1),
                        "count": count,
                        "url": url,
                        "item": ar.get("itemReviewed", ""),
                    }
        except (json.JSONDecodeError, ValueError, TypeError):
            continue

    # Fallback: ratingValue direkt im HTML
    m_score = re.search(r'"ratingValue"[:\s]*"?([\d.,]+)"?', html)
    if m_score:
        score = float(m_score.group(1).replace(",", "."))
        m_count = re.search(r'"ratingCount"[:\s]*"?(\d+)"?', html)
        count = int(m_count.group(1)) if m_count else None
        return {"score": round(score, 1), "count": count, "url": url}

    return {"score": None, "count": None, "url": url, "error": "no rating found"}


def crawl_check24_all_brands(brands, product_path):
    """Check24-Ratings fuer alle Brands eines Produkts holen + Portal-Ratings rausfiltern."""
    raw = {}
    for brand in brands:
        slug = brand.get("check24_slug", "")
        result = crawl_check24(slug, product_path)
        raw[brand["key"]] = result

    # Portal-Rating-Filter: wenn >= 4 Brands exakt gleichen Count haben, ist es das Portal-Rating
    count_freq = {}
    for key, r in raw.items():
        c = r.get("count")
        if c and c > 1000:
            count_freq[c] = count_freq.get(c, 0) + 1

    portal_counts = {c for c, freq in count_freq.items() if freq >= 4}

    filtered = {}
    for key, r in raw.items():
        if r.get("count") in portal_counts:
            filtered[key] = {"score": None, "count": None, "url": r.get("url"), "error": "portal-level rating filtered"}
        else:
            filtered[key] = r
    return filtered


# ── 5. FRANKE & BORNBERG ─────────────────────────────────────────────────────
FB_RATING_CLASSES = {
    "FFF+": 0.5, "FFF": 1.0, "FF+": 2.0, "FF": 3.0,
    "F+": 4.0, "F": 5.0, "F-": 6.0,
}


def fb_grade_to_stars(grade):
    """Konvertiert F&B Schulnote (0.5-6.0) in 5-Sterne-Skala."""
    if grade is None:
        return None
    return round(1.0 + (6.0 - grade) / 5.5 * 4.0, 1)


def crawl_franke_bornberg(rating_id, brands):
    """Franke-und-Bornberg-Ratings per AJAX-API abrufen und best-per-Brand zuordnen.

    Fuer jeden Brand wird der Tarif mit der besten (niedrigsten) Schulnote genommen.
    """
    if not rating_id:
        return {b["key"]: None for b in brands}

    url = "https://www.franke-bornberg.de/page/rating/getrating.php"
    data = post_json(url + "?" + urllib.parse.urlencode({"ratingid": rating_id}), {"ratingid": rating_id})
    if not data or not isinstance(data, list):
        # Retry with body-only POST
        try:
            body = urllib.parse.urlencode({"ratingid": rating_id}).encode("utf-8")
            req = urllib.request.Request(url, data=body, method="POST", headers={
                "User-Agent": UA,
                "Content-Type": "application/x-www-form-urlencoded",
            })
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception:
            data = None

    if not data or not isinstance(data, list):
        print("    [F&B] API-Fehler fuer rating_id=%s" % rating_id)
        return {b["key"]: None for b in brands}

    print("    [F&B] %d Tarife geladen fuer %s" % (len(data), rating_id))

    # Pro Brand: besten Tarif (niedrigste Schulnote) finden
    result = {}
    for brand in brands:
        keywords = brand.get("fb_keywords", [brand["name"]])
        best_grade = None
        best_class = None
        best_tariff = None

        for entry in data:
            name_html = entry.get("name", "")
            # Gesellschaft aus <div class="gsl">...</div> extrahieren
            gsl_match = re.search(r'<div class="gsl">(.*?)</div>', name_html)
            gsl = gsl_match.group(1) if gsl_match else name_html
            tarif_match = re.search(r'<div class="tarif">(.*?)</div>', name_html)
            tarif = tarif_match.group(1) if tarif_match else ""

            # Keyword-Matching
            gsl_upper = gsl.upper()
            matched = any(kw.upper() in gsl_upper for kw in keywords)
            if not matched:
                continue

            # Schulnote extrahieren
            grade_sort = entry.get("Rat02_sort")
            if grade_sort is not None:
                try:
                    grade = float(str(grade_sort).replace(",", "."))
                except (ValueError, TypeError):
                    grade = None
            else:
                # Aus Display-Feld
                grade_display = entry.get("Rat02_display", "")
                m = re.search(r'(\d[.,]\d)', grade_display)
                grade = float(m.group(1).replace(",", ".")) if m else None

            # Ratingklasse extrahieren
            class_display = entry.get("Rat01_display", "")
            cm = re.search(r'class="ratingNote">(.*?)</span>', class_display)
            rating_class = cm.group(1).strip() if cm else None

            if grade is not None and (best_grade is None or grade < best_grade):
                best_grade = grade
                best_class = rating_class
                best_tariff = tarif

        if best_grade is not None:
            result[brand["key"]] = {
                "grade": best_grade,
                "class": best_class,
                "stars": fb_grade_to_stars(best_grade),
                "tariff": best_tariff,
            }
        else:
            result[brand["key"]] = None

    return result


# ── AGGREGATION ──────────────────────────────────────────────────────────────
def aggregate(tp_score, ekomi_score, google_score, check24_score=None, fb_stars=None):
    """Sentiment-Verteilung aus bis zu 5 Quellen gewichtet berechnen.

    Gewichte (gleichmaessig auf verfuegbare Quellen):
    - Trustpilot:       0.20
    - eKomi:            0.20
    - Google:           0.20
    - Check24:          0.20
    - Franke&Bornberg:  0.20
    """
    scores = []  # (positiv-%, gewicht)

    def stars_to_pos(s):
        return max(10, min(90, 10 + (s - 1) * 18.75))

    if tp_score is not None:
        scores.append((stars_to_pos(tp_score), 0.20))
    if ekomi_score is not None:
        scores.append((stars_to_pos(ekomi_score), 0.20))
    if google_score is not None:
        scores.append((stars_to_pos(google_score), 0.20))
    if check24_score is not None:
        scores.append((stars_to_pos(check24_score), 0.20))
    if fb_stars is not None:
        scores.append((stars_to_pos(fb_stars), 0.20))

    if not scores:
        return {"positiv": 50, "neutral": 25, "kritisch": 25}

    total_w = sum(w for _, w in scores)
    pos = sum(p * w for p, w in scores) / total_w
    pos = max(15, min(85, pos))
    rest = 100 - pos
    neg = max(5, min(40, rest * 0.55))
    neu = max(5, rest - neg)

    total = pos + neu + neg
    return {
        "positiv": round(pos * 100 / total),
        "neutral": round(neu * 100 / total),
        "kritisch": round(neg * 100 / total),
    }


# ── THEMEN-EXTRAKTION AUS REVIEW-TEXTEN ─────────────────────────────────────

# Keyword-Woerterbuch: Thema -> (Keywords, Sentiment)
TOPIC_KEYWORDS = {
    # Positive Themen
    "Schnelle Schadenbearbeitung": (["schnell bearbeit", "schnelle bearbeitung", "schnelle abwicklung", "schnell reguliert", "zuegig bearbeit", "zuegig reguliert", "schnelle regulierung", "unkomplizierte abwicklung", "schnell ausgezahlt", "schnelle auszahlung"], "positive"),
    "Freundlicher Kundenservice": (["freundlich", "nett", "hilfsbereit", "zuvorkommend", "hoeflich", "kompetente beratung", "guter service", "toller service", "super service", "klasse service", "erstklassiger service"], "positive"),
    "Gutes Preis-Leistungs-Verhaeltnis": (["preis-leistung", "preis leistung", "guenstig", "fairer preis", "guter preis", "preislich", "gute konditionen", "preiswert"], "positive"),
    "Kompetente Beratung": (["kompetent", "fachkundig", "professionell", "gut beraten", "ausfuehrlich erklaert", "ausfuehrliche beratung", "individuelle beratung"], "positive"),
    "Einfacher Online-Abschluss": (["online abschluss", "einfach abgeschlossen", "unkompliziert", "schnell abgeschlossen", "problemlos", "einfache abwicklung", "digital", "app"], "positive"),
    "Gute Erreichbarkeit": (["gut erreichbar", "schnell erreichbar", "sofort jemand", "kurze wartezeit", "schnell durchgekommen", "schnell geantwortet"], "positive"),
    "Zuverlaessige Leistung": (["zuverlaessig", "verlaesslich", "kann ich empfehlen", "sehr empfehlenswert", "empfehle ich", "bin zufrieden", "sehr zufrieden", "absolut zufrieden", "rundum zufrieden", "top versicherung"], "positive"),

    # Negative Themen
    "Schlechter Kundenservice": (["schlechter service", "schlechter kundenservice", "unfreundlich", "nicht ernst genommen", "ignoriert", "kein rueckruf", "keine antwort", "nie erreichbar", "katastrophaler service"], "negative"),
    "Lange Wartezeiten": (["lange wartezeit", "wochen gewartet", "monate gewartet", "ewig gewartet", "seit wochen", "seit monaten", "keine reaktion", "nicht reagiert", "ueber 4 wochen"], "negative"),
    "Beitragserhöhungen": (["beitragserhoehung", "beitraege erhoeh", "beitraege hoch", "teurer geworden", "preis gestiegen", "erhoehung", "beitrag gestiegen", "beitraege steigen"], "negative"),
    "Leistungsablehnung": (["abgelehnt", "ablehnung", "nicht gezahlt", "nicht uebernommen", "verweigert", "nicht reguliert", "nicht erstattet", "nicht bezahlt", "keine leistung", "leistung verweigert"], "negative"),
    "Probleme bei Kuendigung": (["kuendigung", "gekuendigt", "nicht kuendigen", "kuendigungsfrist", "ruecktritt", "widerruf"], "negative"),
    "Intransparente Kommunikation": (["intransparent", "nicht nachvollziehbar", "keine information", "keine transparenz", "unklar", "nicht erklaert", "nicht informiert", "versteckte kosten", "kleingedruckt"], "negative"),
    "Schlechte Schadenregulierung": (["schaden nicht reguliert", "schadenregulierung mangelhaft", "spart am kundenservice", "nicht kulant", "kein entgegenkommen", "hingehalten", "abgewimmelt", "verzoegert"], "negative"),
}


# ── Gemini-basierte Review-Analyse ──────────────────────────────────────────
def analyze_reviews_with_gemini(review_texts, brand_name):
    """Analysiert Review-Texte mit Gemini Flash und extrahiert Top-Themen.

    Returns: (positive_topics: list[str], negative_topics: list[str]) oder (None, None) bei Fehler.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None, None

    # Maximal 50 Reviews, je max 300 Zeichen (Gemini Flash Free-Tier-freundlich)
    trimmed = []
    for t in review_texts[:50]:
        text = t.get("text", "").strip()
        score = t.get("score", "?")
        if text:
            trimmed.append("%s Sterne: %s" % (score, text[:300]))

    if len(trimmed) < 3:
        return None, None

    reviews_block = "\n---\n".join(trimmed)

    prompt = (
        "Du bist ein Versicherungs-Marktanalyst. Analysiere die folgenden echten Kundenbewertungen "
        "fuer %s und extrahiere die wichtigsten Themen.\n\n"
        "BEWERTUNGEN:\n%s\n\n"
        "Antworte NUR mit exakt diesem JSON-Format, keine weiteren Erklaerungen:\n"
        '{"positive": ["Thema 1 (X Nennungen)", "Thema 2 (X Nennungen)", ...], '
        '"negative": ["Thema 1 (X Nennungen)", "Thema 2 (X Nennungen)", ...]}\n\n'
        "Regeln:\n"
        "- Maximal 5 positive und 5 negative Themen\n"
        "- Zaehle wie oft ein Thema vorkommt und gib es in Klammern an\n"
        "- Themen muessen konkret und versicherungsspezifisch sein (z.B. 'Schnelle Schadenregulierung', nicht 'Gut')\n"
        "- Nur Themen die mindestens 2x vorkommen\n"
        "- Deutsche Themennamen\n"
    ) % (brand_name, reviews_block)

    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=%s" % api_key
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 500,
                "responseMimeType": "application/json",
            }
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers={
            "Content-Type": "application/json",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        # Gemini-Antwort parsen
        text_resp = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        # JSON aus der Antwort extrahieren
        text_resp = text_resp.strip()
        if text_resp.startswith("```"):
            # Code-Block entfernen
            text_resp = re.sub(r"^```(?:json)?\s*", "", text_resp)
            text_resp = re.sub(r"\s*```$", "", text_resp)

        parsed = json.loads(text_resp)
        pos = parsed.get("positive", [])[:5]
        neg = parsed.get("negative", [])[:5]

        # Validierung: nur Strings erlaubt
        pos = [str(t) for t in pos if isinstance(t, str) and len(t) > 3]
        neg = [str(t) for t in neg if isinstance(t, str) and len(t) > 3]

        return pos, neg

    except Exception as exc:
        print("  [Gemini] Fehler fuer %s: %s" % (brand_name, str(exc)[:120]))
        return None, None


def extract_review_topics(reviews, brand_key, brand_name="", days=14):
    """Extrahiert haeufige positive und negative Themen aus Review-Texten.

    Strategie: Zuerst Gemini Flash (wenn GEMINI_API_KEY vorhanden), dann Keyword-Fallback.
    """
    from datetime import timedelta as td
    cutoff = (datetime.now(timezone.utc) - td(days=days)).strftime("%Y-%m-%d")

    # Reviews fuer diese Brand filtern
    brand_reviews = [r for r in reviews if r.get("brand") == brand_key or r.get("key") == brand_key]
    recent = [r for r in brand_reviews if r.get("date", "") >= cutoff and r.get("text", "").strip()]

    # Fallback: wenn keine Reviews der letzten 14 Tage, alle mit Text nehmen
    if len(recent) < 3:
        recent = [r for r in brand_reviews if r.get("text", "").strip()]

    if not recent:
        return [], []

    # === Versuch 1: Gemini Flash API ===
    gemini_pos, gemini_neg = analyze_reviews_with_gemini(recent, brand_name or brand_key)
    if gemini_pos is not None or gemini_neg is not None:
        print("  [Topics] %s: Gemini-Analyse — %d positive, %d negative" % (
            brand_name or brand_key, len(gemini_pos or []), len(gemini_neg or [])))
        return gemini_pos or [], gemini_neg or []

    # === Versuch 2: Keyword-Matching Fallback ===
    print("  [Topics] %s: Keyword-Fallback (kein Gemini API Key)" % (brand_name or brand_key))
    positive_counts = {}
    negative_counts = {}

    for rv in recent:
        text = rv.get("text", "").lower()
        # Umlaute normalisieren fuer Keyword-Matching
        text_norm = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
        score = rv.get("score")

        for topic, (keywords, sentiment) in TOPIC_KEYWORDS.items():
            for kw in keywords:
                kw_norm = kw.lower()
                if kw_norm in text or kw_norm in text_norm:
                    if sentiment == "positive" and (score is None or score >= 3):
                        positive_counts[topic] = positive_counts.get(topic, 0) + 1
                    elif sentiment == "negative" and (score is None or score <= 3):
                        negative_counts[topic] = negative_counts.get(topic, 0) + 1
                    break

    pos_sorted = sorted(positive_counts.items(), key=lambda x: -x[1])
    neg_sorted = sorted(negative_counts.items(), key=lambda x: -x[1])

    pos_topics = ["%s (%d Nennungen)" % (t, c) for t, c in pos_sorted[:5]]
    neg_topics = ["%s (%d Nennungen)" % (t, c) for t, c in neg_sorted[:5]]

    return pos_topics, neg_topics


# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    google_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
    if not google_key:
        print("WARN: GOOGLE_PLACES_API_KEY nicht gesetzt — Google-Quelle wird uebersprungen")

    print("=" * 60)
    print("Sentiment-Crawl %s  |  5 Quellen  |  10 Brands" % today)
    print("=" * 60)

    results = []
    tp_missing_keys = []

    # ── Phase 1: Brand-Level Crawling (Trustpilot, eKomi, Google) ──
    for brand in BRANDS:
        key = brand["key"]
        name = brand["name"]
        print("\n--- %s ---" % name)

        # 1) Trustpilot
        tp = crawl_trustpilot(brand["domain"])
        if tp.get("score"):
            print("  [Trustpilot]  %.1f / 5  (%s Reviews)" % (tp["score"], tp.get("count", "?")))
        else:
            print("  [Trustpilot]  MISS — %s" % tp.get("error", "unbekannt"))
            tp_missing_keys.append(brand)

        # 2) eKomi
        ek = crawl_ekomi(brand.get("ekomi_slugs", []), brand.get("ekomi_multi"))
        if ek.get("score"):
            print("  [eKomi]       %.1f / 5  (%s Reviews)" % (ek["score"], ek.get("count", "?")))
        else:
            print("  [eKomi]       MISS — kein Profil oder keine Bewertungen")

        # 2b) eKomi Produkt-Level
        products_data = []
        if brand.get("products"):
            products_data = crawl_ekomi_products(brand["products"])
            ok_count = sum(1 for p in products_data if p.get("score"))
            print("  [eKomi Prod]  %d/%d Produkte mit Score" % (ok_count, len(products_data)))

        # 3) Google Places
        try:
            gp = crawl_google_places(brand["google_query"], google_key) if google_key else {"score": None, "count": None, "recent_reviews": []}
        except Exception as gex:
            print("  [Google]      CRASH — %s: %s" % (type(gex).__name__, str(gex)[:200]))
            gp = {"score": None, "count": None, "recent_reviews": [], "error": str(gex)[:200]}
        if not isinstance(gp, dict):
            gp = {"score": None, "count": None, "recent_reviews": [], "error": "unexpected return type"}
        if "recent_reviews" not in gp:
            gp["recent_reviews"] = []
        if gp.get("score"):
            print("  [Google]      %.1f / 5  (%s Reviews)  [%s]" % (gp["score"], gp.get("count", "?"), gp.get("matched_name", "")))
        else:
            print("  [Google]      MISS — %s" % gp.get("error", "kein Key"))

        results.append({
            "key": key,
            "name": name,
            "domain": brand["domain"],
            "trustpilot": {
                "score": tp.get("score"),
                "count": tp.get("count"),
                "url": tp.get("url", "https://de.trustpilot.com/review/" + brand["domain"]),
                "note": "Live-Crawl " + today if tp.get("score") else tp.get("error", "nicht verfuegbar"),
            },
            "ekomi": {
                "score": ek.get("score"),
                "count": ek.get("count"),
                "url": ek.get("url"),
                "note": "Live-Crawl " + today if ek.get("score") else "kein Profil",
            },
            "google": {
                "score": gp.get("score"),
                "count": gp.get("count"),
                "place_id": gp.get("place_id"),
                "matched_name": gp.get("matched_name"),
                "note": "Google Places API " + today if gp.get("score") else gp.get("error", "nicht verfuegbar"),
                "recent_reviews": gp.get("recent_reviews", []),
            },
            "products": products_data,
        })

    # Playwright-Fallback fuer fehlende Trustpilot-Scores
    if tp_missing_keys:
        print("\n--- Playwright-Fallback fuer %d Brands ---" % len(tp_missing_keys))
        browser_results = crawl_trustpilot_browser(tp_missing_keys)
        for entry in results:
            br = browser_results.get(entry["key"])
            if br and br.get("score"):
                entry["trustpilot"]["score"] = br["score"]
                entry["trustpilot"]["count"] = br.get("count") or entry["trustpilot"].get("count")
                entry["trustpilot"]["url"] = br["url"]
                entry["trustpilot"]["note"] = "Browser-Crawl " + today

    # ── Phase 2: Produktspezifisches Crawling (Check24 + Franke & Bornberg) ──
    print("\n" + "=" * 60)
    print("Phase 2: Produktspezifische Daten")
    print("=" * 60)

    product_results = {}

    for cat in PRODUCT_CATEGORIES:
        cat_key = cat["key"]
        cat_name = cat["name"]
        print("\n=== %s ===" % cat_name)
        product_results[cat_key] = {"name": cat_name, "brands": {}}

        # Check24 fuer dieses Produkt
        if cat.get("check24_path"):
            print("  Crawle Check24 %s..." % cat["check24_path"])
            c24_data = crawl_check24_all_brands(BRANDS, cat["check24_path"])
            for brand in BRANDS:
                c24 = c24_data.get(brand["key"], {})
                if c24 and c24.get("score"):
                    print("    [C24] %s: %.1f (%s)" % (brand["name"], c24["score"], c24.get("count", "?")))
                product_results[cat_key]["brands"].setdefault(brand["key"], {})["check24"] = c24 or {"score": None, "count": None}
        else:
            print("  Check24: nicht verfuegbar fuer %s" % cat_name)
            for brand in BRANDS:
                product_results[cat_key]["brands"].setdefault(brand["key"], {})["check24"] = {"score": None, "count": None}

        # Franke & Bornberg fuer dieses Produkt
        if cat.get("fb_rating_id"):
            print("  Crawle Franke & Bornberg (%s)..." % cat["fb_rating_id"])
            fb_data = crawl_franke_bornberg(cat["fb_rating_id"], BRANDS)
            for brand in BRANDS:
                fb = fb_data.get(brand["key"])
                if fb:
                    print("    [F&B] %s: %s (Note %.1f -> %.1f*)" % (brand["name"], fb["class"], fb["grade"], fb["stars"]))
                product_results[cat_key]["brands"].setdefault(brand["key"], {})["fb"] = fb
        else:
            print("  Franke & Bornberg: nicht verfuegbar fuer %s" % cat_name)
            for brand in BRANDS:
                product_results[cat_key]["brands"].setdefault(brand["key"], {})["fb"] = None

    # ── Phase 3: Aggregation ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Phase 3: Aggregation")
    print("=" * 60)

    for entry in results:
        key = entry["key"]
        name = entry["name"]

        # Fuer den Gesamt-Score: Durchschnitt der produktspezifischen Check24/FB-Scores
        c24_scores = []
        fb_scores = []
        for cat in PRODUCT_CATEGORIES:
            brand_prod = product_results.get(cat["key"], {}).get("brands", {}).get(key, {})
            c24 = brand_prod.get("check24", {})
            if c24 and c24.get("score"):
                c24_scores.append(c24["score"])
            fb = brand_prod.get("fb")
            if fb and fb.get("stars"):
                fb_scores.append(fb["stars"])

        avg_c24 = round(sum(c24_scores) / len(c24_scores), 1) if c24_scores else None
        avg_fb = round(sum(fb_scores) / len(fb_scores), 1) if fb_scores else None

        entry["check24"] = {
            "score": avg_c24,
            "count": None,
            "note": "Durchschnitt aus %d Produkten" % len(c24_scores) if c24_scores else "keine Daten",
        }
        entry["fb"] = {
            "score": avg_fb,
            "note": "Durchschnitt aus %d Produkten (Sterne-Aequivalent)" % len(fb_scores) if fb_scores else "keine Daten",
        }

        # Aggregate
        agg = aggregate(
            entry["trustpilot"]["score"],
            entry["ekomi"]["score"],
            entry["google"]["score"],
            avg_c24,
            avg_fb,
        )
        entry["aggregate"] = agg

        sources_count = sum(1 for s in [
            entry["trustpilot"]["score"], entry["ekomi"]["score"],
            entry["google"]["score"], avg_c24, avg_fb,
        ] if s)
        entry["sources_count"] = sources_count

        print("  %s: positiv=%d%% neutral=%d%% kritisch=%d%% (%d/5 Quellen)" % (
            name, agg["positiv"], agg["neutral"], agg["kritisch"], sources_count))

    # ── Phase 4: Produkt-Tabellen aggregieren ─────────────────────────────
    print("\n" + "=" * 60)
    print("Phase 4: Produkt-Tabellen")
    print("=" * 60)

    for cat in PRODUCT_CATEGORIES:
        cat_key = cat["key"]
        cat_data = product_results[cat_key]
        print("\n--- %s ---" % cat_data["name"])

        for brand in BRANDS:
            key = brand["key"]
            brand_result = next(r for r in results if r["key"] == key)
            prod_brand = cat_data["brands"].get(key, {})

            c24 = prod_brand.get("check24", {})
            fb = prod_brand.get("fb")

            # Produkt-Level Aggregate
            prod_agg = aggregate(
                brand_result["trustpilot"]["score"],
                brand_result["ekomi"]["score"],
                brand_result["google"]["score"],
                c24.get("score") if c24 else None,
                fb["stars"] if fb else None,
            )

            prod_brand["aggregate"] = prod_agg
            prod_brand["trustpilot_score"] = brand_result["trustpilot"]["score"]
            prod_brand["ekomi_score"] = brand_result["ekomi"]["score"]
            prod_brand["google_score"] = brand_result["google"]["score"]

            c24_str = "%.1f" % c24["score"] if c24 and c24.get("score") else "-"
            fb_str = "%s(%.1f)" % (fb["class"], fb["grade"]) if fb else "-"
            print("  %s: TP=%.1f eK=%.1f G=%.1f C24=%s F&B=%s -> pos=%d%%" % (
                brand["name"],
                brand_result["trustpilot"]["score"] or 0,
                brand_result["ekomi"]["score"] or 0,
                brand_result["google"]["score"] or 0,
                c24_str, fb_str,
                prod_agg["positiv"],
            ))

    # ── JSON speichern ────────────────────────────────────────────────────
    out_data = {
        "as_of": today,
        "sources": ["Trustpilot", "eKomi", "Google Places", "Check24", "Franke & Bornberg"],
        "methodology": {
            "trustpilot": "Direct HTML crawl (urllib + Playwright fallback); JSON-LD ratingValue extraction",
            "ekomi": "Direct HTML crawl; JSON-LD/Meta aggregateRating extraction",
            "google": "Google Places API (findplacefromtext); requires GOOGLE_PLACES_API_KEY",
            "check24": "JSON-LD aggregateRating from product/insurer pages; portal-level ratings filtered",
            "franke_bornberg": "AJAX POST API; best tariff per brand (lowest school grade = best rating)",
            "aggregate_weights": {"trustpilot": 0.20, "ekomi": 0.20, "google": 0.20, "check24": 0.20, "franke_bornberg": 0.20},
        },
        "by_brand": results,
        "by_product": {},
    }

    for cat in PRODUCT_CATEGORIES:
        cat_key = cat["key"]
        cat_data = product_results[cat_key]
        out_data["by_product"][cat_key] = {
            "name": cat_data["name"],
            "check24_available": cat.get("check24_path") is not None,
            "fb_available": cat.get("fb_rating_id") is not None,
            "fb_rating_id": cat.get("fb_rating_id"),
            "brands": {},
        }
        for brand in BRANDS:
            key = brand["key"]
            pb = cat_data["brands"].get(key, {})
            brand_result = next(r for r in results if r["key"] == key)
            out_data["by_product"][cat_key]["brands"][key] = {
                "name": brand["name"],
                "trustpilot": brand_result["trustpilot"]["score"],
                "ekomi": brand_result["ekomi"]["score"],
                "google": brand_result["google"]["score"],
                "check24": pb.get("check24", {}).get("score") if pb.get("check24") else None,
                "check24_count": pb.get("check24", {}).get("count") if pb.get("check24") else None,
                "fb_class": pb["fb"]["class"] if pb.get("fb") else None,
                "fb_grade": pb["fb"]["grade"] if pb.get("fb") else None,
                "fb_stars": pb["fb"]["stars"] if pb.get("fb") else None,
                "fb_tariff": pb["fb"]["tariff"] if pb.get("fb") else None,
                "aggregate": pb.get("aggregate", {"positiv": 50, "neutral": 25, "kritisch": 25}),
            }

    json_path = Path("data/sentiment_data.json")
    if not json_path.parent.exists():
        json_path.parent.mkdir(parents=True)
    json_path.write_text(json.dumps(out_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nSaved: %s (%d bytes)" % (json_path, json_path.stat().st_size))

    # ── Review-History: persistente JSON-Datei mit allen Reviews ──────────
    history_path = Path("data/review_history.json")
    existing_reviews = []
    if history_path.exists():
        try:
            existing_reviews = json.loads(history_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            existing_reviews = []

    # ── Doubletten-Bereinigung: robuster Dedup-Key ──────────────────────
    def _dedup_key(rv):
        """Erzeugt einen robusten Deduplizierungs-Schluessel fuer eine Review."""
        brand = rv.get("brand", "")
        source = rv.get("source", "")
        date = rv.get("date", "")
        # Primaer: Text-Anfang (zuverlaessiger als Titel)
        text_prefix = rv.get("text", "").strip()[:80].lower()
        title_prefix = rv.get("title", "").strip()[:50].lower()
        author = rv.get("author", "").strip().lower()
        # Kombination aus allen verfuegbaren Feldern
        return (brand, source, date, text_prefix or title_prefix, author)

    # Bestehende Reviews deduplizieren (einmalige Bereinigung)
    deduped = []
    existing_keys = set()
    dupes_removed = 0
    for rv in existing_reviews:
        k = _dedup_key(rv)
        if k not in existing_keys:
            deduped.append(rv)
            existing_keys.add(k)
        else:
            dupes_removed += 1
    if dupes_removed > 0:
        print("  [Dedup] %d Doubletten aus Review-History entfernt" % dupes_removed)
    existing_reviews = deduped

    new_count = 0
    for entry in results:
        brand_key = entry["key"]
        brand_name = entry["name"]
        # Trustpilot Reviews
        for rv in entry["trustpilot"].get("recent_reviews", []):
            new_rv = {
                "brand": brand_key,
                "brand_name": brand_name,
                "source": "Trustpilot",
                "title": rv.get("title", ""),
                "text": rv.get("text", ""),
                "score": rv.get("score"),
                "date": rv.get("date", ""),
                "author": rv.get("author", ""),
                "crawl_date": today,
            }
            dedup_key = _dedup_key(new_rv)
            if dedup_key not in existing_keys:
                existing_reviews.append(new_rv)
                existing_keys.add(dedup_key)
                new_count += 1

        # Google Places Reviews
        for rv in entry["google"].get("recent_reviews", []):
            new_rv = {
                "brand": brand_key,
                "brand_name": brand_name,
                "source": "Google",
                "title": "",
                "text": rv.get("text", ""),
                "score": rv.get("score"),
                "date": rv.get("date", ""),
                "author": rv.get("author", ""),
                "crawl_date": today,
            }
            dedup_key = _dedup_key(new_rv)
            if dedup_key not in existing_keys:
                existing_reviews.append(new_rv)
                existing_keys.add(dedup_key)
                new_count += 1

    # Nach Datum sortieren (neueste zuerst)
    existing_reviews.sort(key=lambda x: x.get("date", ""), reverse=True)

    # Max 6 Monate Retention
    from datetime import timedelta
    cutoff_6m = (datetime.now(timezone.utc) - timedelta(days=180)).strftime("%Y-%m-%d")
    existing_reviews = [r for r in existing_reviews if r.get("date", "9999") >= cutoff_6m or r.get("crawl_date", "9999") >= cutoff_6m]

    # Max 1000 Reviews behalten
    if len(existing_reviews) > 1000:
        existing_reviews = existing_reviews[:1000]

    history_path.write_text(json.dumps(existing_reviews, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Review-History: %d neue Reviews, %d total" % (new_count, len(existing_reviews)))

    # ── Dashboard-Template patchen ────────────────────────────────────────
    template = Path("dashboard_template.html")
    if not template.exists():
        print("WARN: dashboard_template.html nicht gefunden, skip patch")
        return

    content = template.read_text(encoding="utf-8")

    # SENTIMENT_DATA-Block fuer JS aufbauen
    sd = {
        "is_demo": False,
        "as_of": today,
        "sources": ["Trustpilot", "eKomi", "Google Places", "Check24", "Franke & Bornberg"],
        "by_brand": [],
        "by_source": {},
        "by_product": {},
    }
    for e in results:
        agg = e["aggregate"]
        sd["by_brand"].append({
            "name": e["name"],
            "positiv": agg["positiv"],
            "neutral": agg["neutral"],
            "kritisch": agg["kritisch"],
        })
        # Top-Themen: zuerst aus Review-Texten (14 Tage), dann Score-Fallback
        text_pos, text_neg = extract_review_topics(existing_reviews, e["key"], brand_name=e["name"], days=14)

        if text_pos or text_neg:
            # Textbasierte Themen gefunden
            positive_topics = text_pos
            negative_topics = text_neg
            print("  [Topics] %s: %d positive, %d negative aus Reviews" % (e["name"], len(text_pos), len(text_neg)))
        else:
            # Fallback: Score-basierte Zusammenfassung
            positive_topics = []
            negative_topics = []
            if e["trustpilot"]["score"] and e["trustpilot"]["score"] >= 4.0:
                positive_topics.append("Starke Trustpilot-Bewertung (%.1f★)" % e["trustpilot"]["score"])
            elif not e["trustpilot"]["score"]:
                negative_topics.append("Kein Trustpilot-Profil gefunden")
            if e["ekomi"]["score"] and e["ekomi"]["score"] >= 4.5:
                positive_topics.append("Sehr gute eKomi-Bewertung (%.1f★)" % e["ekomi"]["score"])
            if e["google"]["score"] and e["google"]["score"] >= 4.0:
                positive_topics.append("Gute Google-Bewertung (%.1f★)" % e["google"]["score"])
            elif e["google"]["score"] and e["google"]["score"] < 3.5:
                negative_topics.append("Schwache Google-Bewertung (%.1f★)" % e["google"]["score"])
            if e["sources_count"] >= 4:
                positive_topics.append("Breite Praesenz: %d von 5 Quellen" % e["sources_count"])
            elif e["sources_count"] <= 2:
                negative_topics.append("Schwache Praesenz: nur %d von 5 Quellen" % e["sources_count"])
            print("  [Topics] %s: Fallback (Score-basiert)" % e["name"])

        sd["by_source"][e["key"]] = {
            "name": e["name"],
            "trustpilot": {"score": e["trustpilot"]["score"], "count": e["trustpilot"]["count"], "url": e["trustpilot"]["url"]},
            "ekomi": {"score": e["ekomi"]["score"], "count": e["ekomi"]["count"], "url": e["ekomi"]["url"]},
            "google": {"score": e["google"]["score"], "count": e["google"]["count"], "place_id": e["google"].get("place_id"), "matched_name": e["google"].get("matched_name")},
            "check24": {"score": e["check24"]["score"], "note": e["check24"]["note"]},
            "fb": {"score": e["fb"]["score"], "note": e["fb"]["note"]},
            "sources_count": e["sources_count"],
            "products": e.get("products", []),
            "positive": positive_topics[:6],
            "negative": negative_topics[:6],
        }

    # Produktspezifische Daten fuer Dashboard
    for cat in PRODUCT_CATEGORIES:
        cat_key = cat["key"]
        cat_data = product_results[cat_key]
        sd["by_product"][cat_key] = {
            "name": cat_data["name"],
            "brands": [],
        }
        for brand in BRANDS:
            key = brand["key"]
            pb = cat_data["brands"].get(key, {})
            brand_result = next(r for r in results if r["key"] == key)
            c24 = pb.get("check24", {})
            fb = pb.get("fb")
            prod_agg = pb.get("aggregate", {"positiv": 50, "neutral": 25, "kritisch": 25})

            sd["by_product"][cat_key]["brands"].append({
                "key": key,
                "name": brand["name"],
                "trustpilot": brand_result["trustpilot"]["score"],
                "ekomi": brand_result["ekomi"]["score"],
                "google": brand_result["google"]["score"],
                "check24": c24.get("score") if c24 else None,
                "check24_count": c24.get("count") if c24 else None,
                "fb_class": fb["class"] if fb else None,
                "fb_grade": fb["grade"] if fb else None,
                "fb_stars": fb["stars"] if fb else None,
                "positiv": prod_agg["positiv"],
                "neutral": prod_agg["neutral"],
                "kritisch": prod_agg["kritisch"],
            })

    # Review-History aus persistenter Datei laden (max 100 fuer Dashboard, dedupliziert)
    history_for_dash = []
    dash_keys = set()
    if history_path.exists():
        try:
            all_hist = json.loads(history_path.read_text(encoding="utf-8"))
            for rv in all_hist:
                entry = {
                    "brand": rv.get("brand", ""),
                    "brand_name": rv.get("brand_name", ""),
                    "source": rv.get("source", "Trustpilot"),
                    "title": rv.get("title", ""),
                    "text": rv.get("text", ""),
                    "score": rv.get("score"),
                    "date": rv.get("date", ""),
                    "author": rv.get("author", ""),
                    "crawl_date": rv.get("crawl_date", ""),
                }
                dk = _dedup_key(entry)
                if dk not in dash_keys:
                    history_for_dash.append(entry)
                    dash_keys.add(dk)
                if len(history_for_dash) >= 100:
                    break
        except (json.JSONDecodeError, IOError):
            pass
    sd["recent_reviews"] = history_for_dash


    # ── Event-Emission für Korrelations-Engine ───────────────────────────
    if HAS_EVENTS:
        print("\n--- Event-Emission ---")
        prev_path = Path("data/sentiment_data.json")
        prev_data = load_previous_data(prev_path)
        # Handle both formats: flat dict {brand_key: data} or nested {by_brand: [...]}
        if "by_brand" in prev_data:
            by_brand = prev_data["by_brand"]
            if isinstance(by_brand, dict):
                prev_brands = by_brand
            else:
                prev_brands = {}  # by_brand list has no per-source data
        else:
            prev_brands = prev_data  # flat format: prev_data IS the brand dict
        event_count = 0

        for entry in results:
            brand_key = entry["key"]
            brand_name = entry["name"]
            # Quellen liegen direkt im Entry (nicht unter "sources")
            prev_entry = prev_brands.get(brand_key, {}) if isinstance(prev_brands, dict) else {}

            # Google Places: Rating-Veränderung
            curr_google = entry.get("google", {})
            prev_google = prev_entry.get("google", {}) if isinstance(prev_entry, dict) else {}
            if curr_google.get("score") and prev_google.get("score"):
                delta = curr_google["score"] - prev_google["score"]
                if abs(delta) >= 0.05:
                    emit_event(
                        event_type="review_change",
                        brand=brand_name,
                        source="google_places",
                        crawler="update_sentiment",
                        magnitude=min(abs(delta) * 5, 2.0),
                        detail={
                            "metric": "average_rating",
                            "old_value": prev_google["score"],
                            "new_value": curr_google["score"],
                            "change": round(delta, 2),
                        },
                    )
                    event_count += 1

            # Google: Review-Volumen
            curr_count = curr_google.get("count", 0)
            prev_count = prev_google.get("count", 0)
            if curr_count and prev_count and (curr_count - prev_count) >= 3:
                emit_event(
                    event_type="review_volume",
                    brand=brand_name,
                    source="google_places",
                    crawler="update_sentiment",
                    magnitude=min((curr_count - prev_count) / 10, 2.0),
                    detail={
                        "old_count": prev_count,
                        "new_count": curr_count,
                        "delta": curr_count - prev_count,
                    },
                )
                event_count += 1

            # Trustpilot: Rating-Veränderung
            curr_tp = entry.get("trustpilot", {})
            prev_tp = prev_entry.get("trustpilot", {}) if isinstance(prev_entry, dict) else {}
            if curr_tp.get("score") and prev_tp.get("score"):
                delta = curr_tp["score"] - prev_tp["score"]
                if abs(delta) >= 0.05:
                    emit_event(
                        event_type="review_change",
                        brand=brand_name,
                        source="trustpilot",
                        crawler="update_sentiment",
                        magnitude=min(abs(delta) * 5, 2.0),
                        detail={
                            "metric": "average_rating",
                            "old_value": prev_tp["score"],
                            "new_value": curr_tp["score"],
                            "change": round(delta, 2),
                        },
                    )
                    event_count += 1
            
            # Franke & Bornberg: Rating-Änderung (produktspezifisch)
            curr_fb = entry.get("fb", {})
            prev_fb = prev_entry.get("fb", {}) if isinstance(prev_entry, dict) else {}
            if isinstance(curr_fb, dict) and isinstance(prev_fb, dict):
                for product_key in ["zahnzusatz", "sterbegeld", "risikoleben"]:
                    curr_rating = None
                    prev_rating = None
                    # F&B Daten sind verschachtelt - prüfe verschiedene Strukturen
                    for fb_data in [curr_fb]:
                        if isinstance(fb_data.get(product_key), dict):
                            curr_rating = fb_data[product_key].get("note")
                    for fb_data in [prev_fb]:
                        if isinstance(fb_data.get(product_key), dict):
                            prev_rating = fb_data[product_key].get("note")
                    
                    if curr_rating and prev_rating and curr_rating != prev_rating:
                        emit_event(
                            event_type="rating_update",
                            brand=brand_name,
                            source="franke_bornberg",
                            crawler="update_sentiment",
                            product=product_key,
                            magnitude=min(abs(curr_rating - prev_rating) * 2, 2.0),
                            detail={
                                "metric": "schulnote",
                                "old_value": prev_rating,
                                "new_value": curr_rating,
                            },
                        )
                        event_count += 1
        
        # Aktuelle Daten für nächsten Vergleich sichern
        save_for_comparison(prev_path)
        print("  %d Events emittiert" % event_count)

    new_block = "const SENTIMENT_DATA = " + json.dumps(sd, ensure_ascii=False, separators=(",", ": ")) + ";"

    # Alten Kommentar + Block ersetzen
    content = re.sub(
        r'// Sentiment-(?:Demo-)?[Dd]aten[^\n]*\n',
        '// Sentiment-Daten (Live-Crawl aus 5 Quellen: Trustpilot, eKomi, Google, Check24, Franke & Bornberg)\n',
        content, count=1
    )
    # Balanced-Bracket-Suche statt Regex (Regex bricht bei }; in Review-Texten)
    marker = re.search(r"const SENTIMENT_DATA\s*=\s*\{", content)
    if marker:
        brace_start = marker.end() - 1  # Position der oeffnenden {
        depth = 0
        in_string = False
        escape_next = False
        end_pos = brace_start
        for i in range(brace_start, len(content)):
            ch = content[i]
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end_pos = i + 1
                    break
        # Semikolon nach } ueberspringen
        if end_pos < len(content) and content[end_pos] == ';':
            end_pos += 1
        content = content[:marker.start()] + new_block + content[end_pos:]
    else:
        print("WARN: SENTIMENT_DATA-Pattern nicht gefunden")
        return

    # Demo-Badge entfernen
    content = re.sub(
        r'\s*<span class="badge badge-yellow">Demo-Daten[^<]*</span>',
        '',
        content, count=1
    )

    # Live-Badge einfuegen (falls nicht schon vorhanden)
    if 'badge-sentiment-live' not in content:
        live_badge = ('<h3 class="text-lg font-bold text-ergo-dark">'
                      'Sentiment-Analyse je Anbieter</h3>\n'
                      '        <span class="badge badge-sentiment-live" '
                      'style="background:#e8f5e9;color:#2e7d32;font-size:11px;'
                      'padding:2px 8px;border-radius:4px;margin-left:8px;">'
                      'Live-Daten \u00b7 Stand '
                      '<span id="sentimentDate"></span></span>')
        content = content.replace(
            '<h3 class="text-lg font-bold text-ergo-dark">Sentiment-Analyse je Anbieter</h3>',
            live_badge,
        )

    # ── CORRELATION_EVENTS aus events.jsonl ins Dashboard injizieren ──────
    events_file = Path("shared/events.jsonl")
    if events_file.exists():
        try:
            from shared.event_emitter import load_events
            all_events = load_events(events_file, max_age_days=90)
            if all_events:
                events_json = json.dumps(all_events, ensure_ascii=False, separators=(",", ":"))
                events_block = "window.CORRELATION_EVENTS = %s;" % events_json
                # Vor der Zeile "const CORRELATION_EVENTS = window.CORRELATION_EVENTS || [];" einfuegen
                corr_marker = "const CORRELATION_EVENTS = window.CORRELATION_EVENTS || [];"
                if corr_marker in content:
                    content = content.replace(
                        corr_marker,
                        events_block + "\n  " + corr_marker
                    )
                    print("  CORRELATION_EVENTS: %d Events injiziert" % len(all_events))
                else:
                    print("  WARN: CORRELATION_EVENTS-Marker nicht gefunden")
        except Exception as exc:
            print("  WARN: Events-Injection fehlgeschlagen: %s" % str(exc)[:100])

    # NULL-byte-safe schreiben
    template.write_bytes(content.encode("utf-8").replace(b"\x00", b"").rstrip() + b"\n")

    success_count = sum(1 for e in results if e["sources_count"] >= 2)
    print("\nPatched dashboard_template.html")
    print("  %d/10 Brands mit >= 2 Quellen" % success_count)
    print("  SENTIMENT_DATA: %d bytes" % len(new_block))


if __name__ == "__main__":
    main()
