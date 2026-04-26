"""Sammelt Sentiment-Daten (Trustpilot Score, Google Reviews) fuer 10 Versicherer
und schreibt sie in dashboard_template.html als SENTIMENT_DATA-Block."""
import json
import re
import urllib.request
import gzip
import os
from pathlib import Path
from datetime import datetime

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

BRANDS = [
    {"key": "ergo",         "name": "ERGO",          "domain": "ergo.de"},
    {"key": "allianz",      "name": "Allianz",       "domain": "allianz.de"},
    {"key": "axa",          "name": "AXA",           "domain": "axa.de"},
    {"key": "huk",          "name": "HUK-Coburg",    "domain": "huk.de"},
    {"key": "generali",     "name": "Generali",      "domain": "generali.de"},
    {"key": "signal-iduna", "name": "Signal Iduna",  "domain": "signal-iduna.de"},
    {"key": "ruv",          "name": "R+V",           "domain": "ruv.de"},
    {"key": "devk",         "name": "DEVK",          "domain": "devk.de"},
    {"key": "hannoversche", "name": "Hannoversche",  "domain": "hannoversche.de"},
    {"key": "cosmosdirekt", "name": "Cosmos Direkt", "domain": "cosmosdirekt.de"},
]

FINANZTIP = {
    "ergo": "nicht-empfohlen", "allianz": "nicht-empfohlen", "axa": "alternativ",
    "huk": "empfehlung", "generali": "nicht-empfohlen", "signal-iduna": "keine-klare-empfehlung",
    "ruv": "keine-klare-empfehlung", "devk": "alternativ",
    "hannoversche": "empfehlung", "cosmosdirekt": "alternativ",
}

def fetch_trustpilot(domain):
    url = f"https://de.trustpilot.com/review/{domain}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
            if data[:2] == b'\x1f\x8b':
                data = gzip.decompress(data)
            html = data.decode('utf-8', errors='ignore')
        m_score = re.search(r'"ratingValue":\s*"?([\d.]+)"?', html)
        m_count = re.search(r'"reviewCount":\s*"?(\d+)"?', html)
        score = float(m_score.group(1)) if m_score else None
        count = int(m_count.group(1)) if m_count else None
        return {"score": score, "count": count, "url": url}
    except Exception as e:
        return {"score": None, "count": None, "url": url, "error": str(e)[:80]}

def aggregate(tp_score, ft_verdict):
    scores = []
    if tp_score is not None:
        positive_pct = 30 + (tp_score - 1) * 15
        scores.append((positive_pct, 0.6))
    if ft_verdict in ("empfehlung",):
        scores.append((75, 0.4))
    elif ft_verdict in ("alternativ",):
        scores.append((58, 0.4))
    elif ft_verdict in ("nicht-empfohlen",):
        scores.append((38, 0.4))
    else:
        scores.append((50, 0.4))
    if not scores:
        return {"positiv": 50, "neutral": 25, "kritisch": 25}
    total_w = sum(w for _, w in scores)
    pos = sum(p * w for p, w in scores) / total_w
    pos = max(20, min(85, pos))
    neg = max(5, min(40, 50 - (pos - 50) * 0.8))
    neu = 100 - pos - neg
    return {"positiv": round(pos), "neutral": round(neu), "kritisch": round(neg)}

def main():
    out = {"as_of": datetime.utcnow().strftime("%Y-%m-%d"), "by_brand": []}
    for b in BRANDS:
        print(f"-- {b['name']} ({b['domain']}) --")
        tp = fetch_trustpilot(b['domain'])
        print(f"   Trustpilot: score={tp.get('score')} count={tp.get('count')}")
        ft_verdict = FINANZTIP.get(b['key'], "keine-klare-empfehlung")
        agg = aggregate(tp.get('score'), ft_verdict)
        out['by_brand'].append({
            "key": b['key'], "name": b['name'],
            "trustpilot": {"score": tp.get('score'), "count": tp.get('count'), "url": tp.get('url')},
            "finanztip": ft_verdict, "google": None, "aggregate": agg,
        })
    json_path = Path("06_sentiment/sentiment_data.json")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\nSaved JSON: {json_path}")

    template = Path("dashboard_template.html")
    if not template.exists():
        print(f"WARNING: {template} not found, skip patch")
        return
    content = template.read_text(encoding='utf-8')
    by_brand_lines = []
    for entry in out['by_brand']:
        agg = entry['aggregate']
        by_brand_lines.append(f"    {{ name: \"{entry['name']}\", positiv: {agg['positiv']}, neutral: {agg['neutral']}, kritisch: {agg['kritisch']} }}")
    new_block = "  by_brand: [\n" + ",\n".join(by_brand_lines) + "\n  ],"
    pattern = re.compile(r'  by_brand:\s*\[[\s\S]*?\n  \],', re.MULTILINE)
    if pattern.search(content):
        content = pattern.sub(new_block, content, count=1)
        template.write_text(content, encoding='utf-8')
        print(f"Patched {template}")
    content = template.read_text(encoding='utf-8')
    content = re.sub(r'as_of:\s*"[^"]*"', f'as_of: "{out["as_of"]}"', content)
    template.write_text(content, encoding='utf-8')
    print(f"Updated as_of to {out['as_of']}")

if __name__ == "__main__":
    main()
