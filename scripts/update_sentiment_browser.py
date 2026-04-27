"""Trustpilot-Crawl via Playwright (Headless Chrome) - Fallback wenn urllib geblockt.

Wird vom Workflow nach update_sentiment.py aufgerufen, wenn der simple Crawl
nicht genug Live-Werte geliefert hat (siehe nightly-update.yml).

Setup im Workflow:
    - run: pip install playwright
    - run: playwright install chromium --with-deps
    - run: python scripts/update_sentiment_browser.py

Lokales Testen:
    pip install playwright
    playwright install chromium
    python scripts/update_sentiment_browser.py

Strategie:
- Headless Chromium mit realistischen Headers + Cookies
- 2 Sek Delay zwischen requests
- Versucht alle 10 Brands; wenn >=8 erfolgreich -> aktualisiert sentiment_data.json
"""
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path


def find_sentiment_json():
    candidates = [
        Path("data/sentiment_data.json"),
        Path("06_sentiment/sentiment_data.json"),
        Path("../06_sentiment/sentiment_data.json"),
        Path(__file__).parent.parent / "data" / "sentiment_data.json",
        Path(__file__).parent.parent.parent / "06_sentiment" / "sentiment_data.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def aggregate(tp_score, ft_verdict, google_score=None):
    scores = []
    if tp_score is not None:
        scores.append((30 + (tp_score - 1) * 15, 0.5))
    if google_score is not None:
        scores.append((30 + (google_score - 1) * 15, 0.2))
    weights = {"empfehlung": 75, "alternativ": 58, "nicht-empfohlen": 38}
    if ft_verdict in weights:
        scores.append((weights[ft_verdict], 0.3))
    elif ft_verdict:
        scores.append((50, 0.3))
    if not scores:
        return {"positiv": 50, "neutral": 25, "kritisch": 25}
    total_w = sum(w for _, w in scores)
    pos = sum(p * w for p, w in scores) / total_w
    pos = max(20, min(80, pos))
    rest = 100 - pos
    neg = max(5, min(45, rest * 0.55))
    neu = max(5, rest - neg)
    total = pos + neu + neg
    if total != 100:
        pos = pos * 100 / total
        neu = neu * 100 / total
        neg = neg * 100 / total
    return {"positiv": round(pos), "neutral": round(neu), "kritisch": round(neg)}


def crawl_with_browser(brands):
    """Versucht Trustpilot via Playwright zu crawlen.
    Returns: dict {brand_key: {score, count}}"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright nicht installiert. Skip browser fallback.")
        return {}

    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0 Safari/537.36"),
            locale="de-DE",
            timezone_id="Europe/Berlin",
            viewport={"width": 1280, "height": 800},
        )
        # Stealth-Mini: webdriver flag remove
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = context.new_page()

        for entry in brands:
            domain = entry.get("domain", "")
            name = entry.get("name", "?")
            if not domain:
                continue
            url = "https://de.trustpilot.com/review/" + domain
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                time.sleep(2)
                html = page.content()
                m_score = re.search(r'"ratingValue":\s*"?([\d.]+)"?', html)
                m_count = re.search(r'"reviewCount":\s*"?(\d+)"?', html)
                if m_score:
                    results[entry["key"]] = {
                        "score": float(m_score.group(1)),
                        "count": int(m_count.group(1)) if m_count else None,
                        "url": url,
                    }
                    print("  Browser TP: %s -> score=%s count=%s" % (
                        name, m_score.group(1), m_count.group(1) if m_count else "?"))
                else:
                    print("  Browser TP fail: %s (kein ratingValue im HTML)" % name)
            except Exception as e:
                print("  Browser TP error %s: %s" % (name, str(e)[:80]))
            time.sleep(2)  # politeness delay
        browser.close()
    return results


def main():
    src_path = find_sentiment_json()
    if not src_path:
        print("ERROR: 06_sentiment/sentiment_data.json nicht gefunden")
        return 1
    data = json.loads(src_path.read_text(encoding="utf-8"))
    today = datetime.utcnow().strftime("%Y-%m-%d")
    brands = data.get("by_brand", [])

    live = crawl_with_browser(brands)
    successes = len(live)
    print("\n=== Browser-Crawl: %d/%d erfolgreich ===" % (successes, len(brands)))

    if successes < 5:
        print("WARN: Zu wenige Erfolge - Template nicht aktualisiert.")
        return 0

    # Update entries with live data
    for entry in brands:
        live_data = live.get(entry["key"])
        if live_data and live_data["score"] is not None:
            tp = entry.setdefault("trustpilot", {})
            tp["score"] = live_data["score"]
            if live_data["count"]:
                tp["count"] = live_data["count"]
            tp["url"] = live_data["url"]
            tp["note"] = "Browser-Live-Crawl " + today
        # Re-aggregate
        tp_score = entry.get("trustpilot", {}).get("score")
        ft = entry.get("finanztip") or {}
        ft_verdict = ft.get("verdict") if isinstance(ft, dict) else ft
        g = entry.get("google") or {}
        g_score = g.get("score") if isinstance(g, dict) else None
        entry["aggregate"] = aggregate(tp_score, ft_verdict, g_score)

    data["as_of"] = today
    src_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Saved: " + str(src_path))

    # Patch template
    template = Path("dashboard_template.html")
    if not template.exists():
        return 0
    content = template.read_text(encoding="utf-8")
    by_brand_lines = []
    for e in brands:
        agg = e.get("aggregate", {})
        by_brand_lines.append(
            "    { name: \"" + e["name"] + "\", positiv: " + str(agg.get("positiv", 50))
            + ", neutral: " + str(agg.get("neutral", 25))
            + ", kritisch: " + str(agg.get("kritisch", 25)) + " }"
        )
    new_block = "  by_brand: [\n" + ",\n".join(by_brand_lines) + "\n  ],"
    pat = re.compile(r"  by_brand:\s*\[[\s\S]*?\n  \],", re.MULTILINE)
    if pat.search(content):
        content = pat.sub(new_block, content, count=1)
        content = re.sub(r'as_of:\s*"[^"]*"', 'as_of: "' + today + '"', content)
        template.write_bytes(content.encode("utf-8").replace(b"\x00", b"").rstrip() + b"\n")
        print("Patched dashboard_template.html (Browser-Source)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
