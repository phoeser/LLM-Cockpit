"""Sammelt ECHTE Sentiment-Daten fuer 10 Versicherer aus 4 Quellen und patcht dashboard_template.html.

Quellen:
1. Trustpilot    (urllib + Playwright-Fallback)  — Score + Count
2. eKomi         (HTML-Scrape)                   — Score + Count
3. Google Places (API, braucht GOOGLE_PLACES_API_KEY) — Score + Count
4. Finanztip     (HTML-Scrape)                   — Verdict + Topics

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
from pathlib import Path
from datetime import datetime, timezone

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# ── Brand-Konfiguration ──────────────────────────────────────────────────────
BRANDS = [
    {
        "key": "ergo", "name": "ERGO", "domain": "ergo.de",
        "ekomi_slugs": ["ergo-direkt-versicherungen-regulierung", "ergo-versicherungsgruppe"],
        "ekomi_multi": None,
        "google_query": "ERGO Group AG Düsseldorf Versicherung",
        "finanztip_urls": [
            "https://www.finanztip.de/erfahrungen/ergo/",
            "https://www.finanztip.de/kfz-versicherung/ergo-kfz-versicherung/",
        ],
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
        "finanztip_urls": [
            "https://www.finanztip.de/erfahrungen/allianz/",
            "https://www.finanztip.de/kfz-versicherung/allianz-kfz-versicherung/",
        ],
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
        "finanztip_urls": [
            "https://www.finanztip.de/kfz-versicherung/axa-kfz-versicherung/",
        ],
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
        "finanztip_urls": [
            "https://www.finanztip.de/kfz-versicherung/kfz-versicherung-der-huk-coburg/",
        ],
        "products": [],
    },
    {
        "key": "generali", "name": "Generali", "domain": "generali.de",
        "ekomi_slugs": [],
        "ekomi_multi": None,
        "google_query": "Generali Deutschland Versicherung München",
        "finanztip_urls": [
            "https://www.finanztip.de/kfz-versicherung/generali-kfz-versicherung/",
        ],
        "products": [],
    },
    {
        "key": "signal-iduna", "name": "Signal Iduna", "domain": "signal-iduna.de",
        "ekomi_slugs": [],
        "ekomi_multi": None,
        "google_query": "Signal Iduna Versicherung Dortmund",
        "finanztip_urls": [
            "https://www.finanztip.de/erfahrungen/signal-iduna/",
        ],
        "products": [],
    },
    {
        "key": "ruv", "name": "R+V", "domain": "ruv.de",
        "ekomi_slugs": ["ruv"],
        "ekomi_multi": None,
        "google_query": "R+V Versicherung Wiesbaden",
        "finanztip_urls": [],
        "products": [
            {"name": "Gesamt", "ekomi": "ruv"},
        ],
    },
    {
        "key": "devk", "name": "DEVK", "domain": "devk.de",
        "ekomi_slugs": ["devk"],
        "ekomi_multi": None,
        "google_query": "DEVK Versicherungen Köln",
        "finanztip_urls": [
            "https://www.finanztip.de/kfz-versicherung/devk-kfz-versicherung/",
        ],
        "products": [
            {"name": "Gesamt", "ekomi": "devk"},
        ],
    },
    {
        "key": "hannoversche", "name": "Hannoversche", "domain": "hannoversche.de",
        "ekomi_slugs": ["hannoversche-leben"],
        "ekomi_multi": None,
        "google_query": "Hannoversche Lebensversicherung Hannover",
        "finanztip_urls": [
            "https://www.finanztip.de/risikolebensversicherung/hannoversche-rlv/",
        ],
        "products": [
            {"name": "Lebensversicherung", "ekomi": "hannoversche-leben"},
        ],
    },
    {
        "key": "cosmosdirekt", "name": "Cosmos Direkt", "domain": "cosmosdirekt.de",
        "ekomi_slugs": [],
        "ekomi_multi": None,
        "google_query": "CosmosDirekt Versicherung Saarbrücken",
        "finanztip_urls": [
            "https://www.finanztip.de/erfahrungen/cosmosdirekt/",
        ],
        "products": [],
    },
]


# ── HTTP-Helper


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


# ── 1. TRUSTPILOT ────────────────────────────────────────────────────────────
def crawl_trustpilot(domain):
    """Trustpilot-Score via urllib (JSON-LD aus HTML)."""
    url = "https://de.trustpilot.com/review/" + domain
    html = fetch_html(url)
    if not html:
        return {"score": None, "count": None, "url": url, "error": "fetch failed"}
    m_score = re.search(r'"ratingValue":\s*"?([\d.]+)"?', html)
    m_count = re.search(r'"reviewCount":\s*"?(\d+)"?', html)
    if m_score:
        return {
            "score": round(float(m_score.group(1)), 1),
            "count": int(m_count.group(1)) if m_count else None,
            "url": url,
        }
    return {"score": None, "count": None, "url": url, "error": "no ratingValue found"}


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
        # eKomi-Format: "Bewertung: 4.5 Sterne von 32835 Bewertungen"
        m_title = re.search(r'Bewertung:\s*([\d.,]+)\s*Sterne\s*von\s*([\d.]+)\s*Bewertungen', html)
        if m_title:
            m_score = m_title
            m_count = m_title
            score_val = float(m_title.group(1).replace(",", "."))
            count_val = int(m_title.group(2).replace(".", ""))
            if count_val >= best["count"]:
                best = {"score": round(score_val, 1), "count": count_val, "url": url}
            continue
        # Fallback: JSON-LD aggregateRating
        m_score = re.search(r'"ratingValue"[:\s]*"?([\d.]+)"?', html)
        m_count = re.search(r'"ratingCount"[:\s]*"?(\d+)"?', html)
        if not m_count:
            m_count = re.search(r'"reviewCount"[:\s]*"?(\d+)"?', html)
        # Fallback: Score/5 Pattern
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
        # eKomi-Format: "Bewertung: X.X Sterne von NNNNN Bewertungen"
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
def crawl_google_places(query, api_key):
    """Google Places API: Legacy Text Search zuerst, dann New API als Fallback."""
    if not api_key:
        return {"score": None, "count": None, "error": "no API key"}

    # 1) Legacy Places API (in den meisten Projekten standardmaessig aktiv)
    encoded = urllib.parse.quote(query)
    legacy_url = ("https://maps.googleapis.com/maps/api/place/textsearch/json"
                  "?query=%s&language=de&key=%s" % (encoded, api_key))
    try:
        legacy_data = fetch_json(legacy_url)
        if legacy_data:
            status = legacy_data.get("status", "")
            if status == "OK":
                results = legacy_data.get("results", [])
                if results:
                    best = max(results, key=lambda r: r.get("user_ratings_total", 0))
                    if best.get("rating"):
                        return {
                            "score": round(best.get("rating", 0), 1),
                            "count": best.get("user_ratings_total"),
                            "place_id": best.get("place_id"),
                            "matched_name": best.get("name"),
                            "api": "legacy",
                        }
            elif status == "REQUEST_DENIED":
                print("    [Google Legacy] REQUEST_DENIED: %s" % legacy_data.get("error_message", "")[:80])
            else:
                print("    [Google Legacy] Status: %s" % status)
    except Exception as e:
        print("    [Google Legacy] Exception: %s" % str(e)[:80])

    # 2) Neue Places API (v1) als Fallback
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
            "X-Goog-FieldMask": "places.displayName,places.rating,places.userRatingCount,places.id",
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        places = data.get("places", [])
        if places:
            best = max(places, key=lambda p: p.get("userRatingCount", 0))
            name = best.get("displayName", {})
            return {
                "score": round(best.get("rating", 0), 1) or None,
                "count": best.get("userRatingCount"),
                "place_id": best.get("id"),
                "matched_name": name.get("text", "") if isinstance(name, dict) else str(name),
                "api": "new",
            }
        return {"score": None, "count": None, "error": "no results (new API)"}
    except Exception as e2:
        return {"score": None, "count": None, "error": "both APIs failed: %s" % str(e2)[:60]}


# ── 4. FINANZTIP ─────────────────────────────────────────────────────────────
FINANZTIP_VERDICTS = {
    "empfehlung": ["finanztip empfehlung", "finanztip-empfehlung", "empfohlen von finanztip",
                    "unser tipp", "unsere empfehlung", "finanztip empfiehlt"],
    "alternativ": ["alternative", "günstige alternative", "kann eine option sein",
                    "unter bestimmten voraussetzungen"],
    "nicht-empfohlen": ["nicht empfohlen", "nicht empfehlung", "raten wir ab",
                         "können wir nicht empfehlen", "nicht zu empfehlen"],
}

def crawl_finanztip(urls):
    """Finanztip-Verdict aus HTML extrahieren."""
    if not urls:
        return {"verdict": None, "url": None, "topics": []}

    for url in urls:
        html = fetch_html(url)
        if not html:
            continue
        text_lower = html.lower()

        # Verdict erkennen (Prioritaet: empfehlung > nicht-empfohlen > alternativ)
        verdict = None
        for v_key in ["empfehlung", "nicht-empfohlen", "alternativ"]:
            for phrase in FINANZTIP_VERDICTS[v_key]:
                if phrase in text_lower:
                    # "nicht empfohlen" darf nicht "empfehlung" ueberschreiben wenn beides vorkommt
                    if v_key == "empfehlung" and any(neg in text_lower for neg in FINANZTIP_VERDICTS["nicht-empfohlen"]):
                        verdict = "nicht-empfohlen"
                    else:
                        verdict = v_key
                    break
            if verdict:
                break

        # Topics: <h2> und <h3> als Themen-Hinweise
        topics = []
        for m in re.finditer(r'<h[23][^>]*>(.*?)</h[23]>', html, re.IGNORECASE):
            t = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if 5 < len(t) < 80 and not any(skip in t.lower() for skip in ["cookie", "newsletter", "inhalt", "navigation"]):
                topics.append(t)

        if verdict:
            return {"verdict": verdict, "url": url, "topics": topics[:5]}

    return {"verdict": "keine-klare-empfehlung", "url": urls[0], "topics": []}


# ── AGGREGATION ──────────────────────────────────────────────────────────────
def aggregate(tp_score, ekomi_score, google_score, ft_verdict):
    """Sentiment-Verteilung aus 4 Quellen gewichtet berechnen.

    Gewichte (normiert auf verfuegbare Quellen):
    - Trustpilot:  0.35
    - eKomi:       0.20
    - Google:      0.15
    - Finanztip:   0.30
    """
    scores = []  # (positiv-%, gewicht)

    # Sterne -> Positiv-% Mapping: 1.0=10%, 2.0=25%, 3.0=45%, 4.0=65%, 5.0=85%
    def stars_to_pos(s):
        return max(10, min(90, 10 + (s - 1) * 18.75))

    if tp_score is not None:
        scores.append((stars_to_pos(tp_score), 0.35))
    if ekomi_score is not None:
        scores.append((stars_to_pos(ekomi_score), 0.20))
    if google_score is not None:
        scores.append((stars_to_pos(google_score), 0.15))

    ft_map = {"empfehlung": 78, "alternativ": 55, "nicht-empfohlen": 30, "keine-klare-empfehlung": 45}
    if ft_verdict in ft_map:
        scores.append((ft_map[ft_verdict], 0.30))

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


# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    google_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
    if not google_key:
        print("WARN: GOOGLE_PLACES_API_KEY nicht gesetzt — Google-Quelle wird uebersprungen")

    print("=" * 60)
    print("Sentiment-Crawl %s  |  4 Quellen  |  10 Brands" % today)
    print("=" * 60)

    results = []
    tp_missing_keys = []  # Fuer Playwright-Fallback

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
        gp = crawl_google_places(brand["google_query"], google_key) if google_key else {"score": None, "count": None}
        if gp.get("score"):
            print("  [Google]      %.1f / 5  (%s Reviews)  [%s]" % (gp["score"], gp.get("count", "?"), gp.get("matched_name", "")))
        else:
            print("  [Google]      MISS — %s" % gp.get("error", "kein Key"))

        # 4) Finanztip
        ft = crawl_finanztip(brand.get("finanztip_urls", []))
        if ft.get("verdict"):
            print("  [Finanztip]   %s" % ft["verdict"])
        else:
            print("  [Finanztip]   MISS — keine Seite gefunden")

        # Aggregate
        agg = aggregate(tp.get("score"), ek.get("score"), gp.get("score"), ft.get("verdict"))
        print("  => Aggregate: positiv=%d%% neutral=%d%% kritisch=%d%%" % (agg["positiv"], agg["neutral"], agg["kritisch"]))

        # Quellen-Zaehler
        sources_count = sum(1 for s in [tp.get("score"), ek.get("score"), gp.get("score"), ft.get("verdict")] if s)
        print("  => %d/4 Quellen erfolgreich" % sources_count)

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
            },
            "finanztip": {
                "verdict": ft.get("verdict"),
                "url": ft.get("url"),
                "topics": ft.get("topics", []),
            },
            "aggregate": agg,
            "sources_count": sources_count,
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
                # Re-aggregate mit neuem TP-Score
                entry["aggregate"] = aggregate(
                    br["score"],
                    entry["ekomi"]["score"],
                    entry["google"]["score"],
                    entry["finanztip"]["verdict"],
                )
                entry["sources_count"] = sum(1 for s in [
                    br["score"], entry["ekomi"]["score"],
                    entry["google"]["score"], entry["finanztip"]["verdict"]
                ] if s)
                print("  [TP-Browser] %s -> %.1f (re-aggregated)" % (entry["name"], br["score"]))

    # ── JSON speichern ────────────────────────────────────────────────────
    out_data = {
        "as_of": today,
        "sources": ["Trustpilot", "eKomi", "Google Places", "Finanztip"],
        "methodology": {
            "trustpilot": "Direct HTML crawl (urllib + Playwright fallback); JSON-LD ratingValue extraction",
            "ekomi": "Direct HTML crawl; JSON-LD/Meta aggregateRating extraction",
            "google": "Google Places API (findplacefromtext); requires GOOGLE_PLACES_API_KEY",
            "finanztip": "HTML crawl; keyword-based verdict extraction (empfehlung/alternativ/nicht-empfohlen)",
            "aggregate_weights": {"trustpilot": 0.35, "ekomi": 0.20, "google": 0.15, "finanztip": 0.30},
        },
        "by_brand": results,
    }

    json_path = Path("data/sentiment_data.json")
    if not json_path.parent.exists():
        json_path.parent.mkdir(parents=True)
    json_path.write_text(json.dumps(out_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nSaved: %s (%d bytes)" % (json_path, json_path.stat().st_size))

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
        "sources": ["Trustpilot", "eKomi", "Google Places", "Finanztip"],
        "by_brand": [],
        "by_source": {},
    }
    for e in results:
        agg = e["aggregate"]
        sd["by_brand"].append({
            "name": e["name"],
            "positiv": agg["positiv"],
            "neutral": agg["neutral"],
            "kritisch": agg["kritisch"],
        })
        sd["by_source"][e["key"]] = {
            "name": e["name"],
            "trustpilot": {"score": e["trustpilot"]["score"], "count": e["trustpilot"]["count"], "url": e["trustpilot"]["url"]},
            "ekomi": {"score": e["ekomi"]["score"], "count": e["ekomi"]["count"], "url": e["ekomi"]["url"]},
            "google": {"score": e["google"]["score"], "count": e["google"]["count"]},
            "finanztip": {"verdict": e["finanztip"]["verdict"], "url": e["finanztip"]["url"]},
            "sources_count": e["sources_count"],
            "products": e.get("products", []),
        }

    new_block = "const SENTIMENT_DATA = " + json.dumps(sd, ensure_ascii=False, separators=(",", ": ")) + ";"

    # Alten Kommentar + Block ersetzen
    content = re.sub(
        r'// Sentiment-Demo-Daten[^\n]*\n',
        '// Sentiment-Daten (Live-Crawl aus 4 Quellen: Trustpilot, eKomi, Google, Finanztip)\n',
        content, count=1
    )
    pattern = re.compile(r"const SENTIMENT_DATA\s*=\s*\{.*?\};", re.DOTALL)
    if pattern.search(content):
        content = pattern.sub(new_block, content, count=1)
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
    # Live-Badge einfuegen (falls nicht schon vorhanden)
    if 'badge-sentiment-live' not in content:
        content = content.replace(
            '<h3 class="text-lg font-bold text-ergo-dark">Sentiment-Analyse je Anbieter</h3>',
            '<h3 class="text-lg font-bold text-ergo-dark">Sentiment-Analyse je Anbieter</h3>\n'
            '        <span class="badge badge-sentiment-live" style="background:#e8f5e9;color:#2e7d32;font-size:11px;padding:2px 8px;border-radius:4px;margin-left:8px;">'
            'Live-Daten · Stand <span id="sentimentDate"></span></span>',
        )

    # NULL-byte-safe schreiben
    template.write_bytes(content.encode("utf-8").replace(b"\x00", b"").rstrip() + b"\n")

    success_count = sum(1 for e in results if e["sources_count"] >= 2)
    print("\nPatched dashboard_template.html")
    print("  %d/10 Brands mit >= 2 Quellen" % success_count)
    print("  SENTIMENT_DATA: %d bytes" % len(new_block))


if __name__ == "__main__":
    main()
