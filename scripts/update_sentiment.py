"""Sammelt Sentiment-Daten fuer 10 Versicherer und patcht dashboard_template.html.

Quellen-Hierarchie (in Reihenfolge):
1. 06_sentiment/sentiment_data.json   -> manuell gepflegte Vollversion (Finanztip + Google + Topics)
2. Trustpilot live (best-effort)       -> ueberschreibt tp.score wenn erreichbar
3. Aggregate wird neu berechnet aus tp + finanztip + google

Workflow im Repo: lebt in github-deployment/, sucht ../06_sentiment/sentiment_data.json
Workflow lokal:   gleicher Pfad relativ zu cwd

Output:
- 06_sentiment/sentiment_data.json (mit aktualisiertem as_of + tp-Werten)
- dashboard_template.html: by_brand Block + as_of patched
"""
import json
import re
import urllib.request
import gzip
import os
from pathlib import Path
from datetime import datetime

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def fetch_trustpilot(domain):
    url = "https://de.trustpilot.com/review/" + domain
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
            if data[:2] == b"\x1f\x8b":
                data = gzip.decompress(data)
            html = data.decode("utf-8", errors="ignore")
        m_score = re.search(r'"ratingValue":\s*"?([\d.]+)"?', html)
        m_count = re.search(r'"reviewCount":\s*"?(\d+)"?', html)
        return {
            "score": float(m_score.group(1)) if m_score else None,
            "count": int(m_count.group(1)) if m_count else None,
            "url": url,
        }
    except Exception as e:
        return {"score": None, "count": None, "url": url, "error": str(e)[:80]}


def aggregate(tp_score, ft_verdict, google_score=None):
    """Sentiment-Verteilung positiv/neutral/kritisch aus drei Signalen."""
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
    # pos in [20, 80], neg ~= 55% des Rests (Rest = 100-pos), neu = Rest - neg
    pos = max(20, min(80, pos))
    rest = 100 - pos
    neg = max(5, min(45, rest * 0.55))
    neu = max(5, rest - neg)
    # Normieren falls pos+neu+neg != 100
    total = pos + neu + neg
    if total != 100:
        pos = round(pos * 100 / total, 1)
        neu = round(neu * 100 / total, 1)
        neg = round(neg * 100 / total, 1)
    return {"positiv": round(pos), "neutral": round(neu), "kritisch": round(neg)}


def find_sentiment_json():
    """Sucht 06_sentiment/sentiment_data.json relativ zu CWD oder Repo-Root."""
    candidates = [
        Path("06_sentiment/sentiment_data.json"),
        Path("../06_sentiment/sentiment_data.json"),
        Path(__file__).parent.parent.parent / "06_sentiment" / "sentiment_data.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def main():
    src_path = find_sentiment_json()
    if not src_path:
        print("ERROR: 06_sentiment/sentiment_data.json nicht gefunden")
        # Fallback: minimale Liste
        manual_data = {"by_brand": []}
    else:
        manual_data = json.loads(src_path.read_text(encoding="utf-8"))
        print("Lade manuelle Sentiment-Daten aus: " + str(src_path))

    today = datetime.utcnow().strftime("%Y-%m-%d")
    manual_data["as_of"] = today

    # Trustpilot live refresh + neu aggregieren
    for entry in manual_data.get("by_brand", []):
        name = entry.get("name", "?")
        domain = entry.get("domain", "")
        if domain:
            tp_live = fetch_trustpilot(domain)
            if tp_live.get("score") is not None:
                entry.setdefault("trustpilot", {})
                entry["trustpilot"]["score"] = tp_live["score"]
                entry["trustpilot"]["count"] = tp_live.get("count") or entry["trustpilot"].get("count")
                entry["trustpilot"]["url"] = tp_live["url"]
                entry["trustpilot"]["note"] = "Live-Crawl " + today
                print("  TP live: " + name + " -> " + str(tp_live["score"]))
            else:
                print("  TP fail: " + name + " (manueller Wert bleibt)")
        # Re-aggregate (auch falls TP nicht live ging)
        tp_score = entry.get("trustpilot", {}).get("score")
        ft = entry.get("finanztip") or {}
        ft_verdict = ft.get("verdict") if isinstance(ft, dict) else ft
        g = entry.get("google") or {}
        g_score = g.get("score") if isinstance(g, dict) else None
        entry["aggregate"] = aggregate(tp_score, ft_verdict, g_score)

    # JSON zurueckschreiben
    if src_path:
        src_path.write_text(json.dumps(manual_data, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Saved: " + str(src_path))

    # dashboard_template.html patchen: kompletten SENTIMENT_DATA-Block ersetzen
    template = Path("dashboard_template.html")
    if not template.exists():
        print("WARN: dashboard_template.html nicht gefunden, skip patch")
        return
    content = template.read_text(encoding="utf-8")

    # Build full SENTIMENT_DATA structure
    sd = {
        "is_demo": False,
        "as_of": today,
        "sources": ["Trustpilot", "Finanztip", "Google Reviews"],
        "by_brand": [],
        "by_source": {},
    }
    for e in manual_data.get("by_brand", []):
        agg = e.get("aggregate", {})
        sd["by_brand"].append({
            "name": e["name"],
            "positiv": agg.get("positiv", 50),
            "neutral": agg.get("neutral", 25),
            "kritisch": agg.get("kritisch", 25),
        })
        # by_source mit detailed fields
        tp = e.get("trustpilot") or {}
        ft = e.get("finanztip") or {}
        g = e.get("google") or {}
        sd["by_source"][e["key"]] = {
            "name": e["name"],
            "trustpilot": {"score": tp.get("score"), "count": tp.get("count")},
            "finanztip": ft.get("verdict") if isinstance(ft, dict) else ft,
            "google": g.get("score") if isinstance(g, dict) else g,
            "positive": e.get("topics_positive", []),
            "negative": e.get("topics_negative", []),
        }

    # Compact JSON-Style fuer JS-Var
    new_block = "const SENTIMENT_DATA = " + json.dumps(sd, ensure_ascii=False, separators=(",", ": ")) + ";"
    # Replace whole `const SENTIMENT_DATA = {...};` statement
    pattern = re.compile(r"const SENTIMENT_DATA\s*=\s*\{[\s\S]*?\n\};", re.MULTILINE)
    if pattern.search(content):
        content = pattern.sub(new_block, content, count=1)
        # NULL-byte safe schreiben
        template.write_bytes(content.encode("utf-8").replace(b"\x00", b"").rstrip() + b"\n")
        print("Patched dashboard_template.html, SENTIMENT_DATA komplett ersetzt mit " + str(len(sd["by_brand"])) + " Brands + by_source-Details")
    else:
        # Fallback: try old by_brand-only pattern
        by_brand_lines = []
        for e in manual_data.get("by_brand", []):
            agg = e.get("aggregate", {})
            by_brand_lines.append(
                "    { name: \"" + e["name"] + "\", positiv: " + str(agg.get("positiv", 50))
                + ", neutral: " + str(agg.get("neutral", 25))
                + ", kritisch: " + str(agg.get("kritisch", 25)) + " }"
            )
        new_b = "  by_brand: [\n" + ",\n".join(by_brand_lines) + "\n  ],"
        p2 = re.compile(r"  by_brand:\s*\[[\s\S]*?\n  \],", re.MULTILINE)
        if p2.search(content):
            content = p2.sub(new_b, content, count=1)
            content = re.sub(r'as_of:\s*"[^"]*"', 'as_of: "' + today + '"', content)
            template.write_bytes(content.encode("utf-8").replace(b"\x00", b"").rstrip() + b"\n")
            print("Patched (fallback): nur by_brand")
        else:
            print("WARN: Kein Pattern gefunden")


if __name__ == "__main__":
    main()
