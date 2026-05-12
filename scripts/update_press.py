"""Sammelt Pressemitteilungen + Medienberichte fuer 10 Versicherer.

Zwei Quellen pro Versicherer:
1. Eigene Pressemitteilungen (Google News RSS mit site:-Filter)
2. Medienberichte ueber den Versicherer (Google News RSS allgemein)

Nach Themen getaggt, mit Timeline und Frequenz-Vergleich.

Workflow: laeuft in github-deployment/ als CWD
Output:
- data/press_data.json (alle Artikel + Statistiken)
- dashboard_template.html: PRESS_DATA-Block gepatcht
"""
import json
import re
import os
import sys
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter
import time

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
        "key": "ergo", "name": "ERGO",
        "media_query": "ERGO+Versicherung",
        "own_query": "site:ergo.com+OR+site:ergo-group.com",
        "domain": "ergo.com",
    },
    {
        "key": "allianz", "name": "Allianz",
        "media_query": "Allianz+Versicherung+Deutschland",
        "own_query": "site:allianz.de+OR+site:allianz.com+Presse+OR+Pressemitteilung",
        "domain": "allianz.de",
    },
    {
        "key": "axa", "name": "AXA",
        "media_query": "AXA+Versicherung+Deutschland",
        "own_query": "site:axa.de+Presse+OR+Pressemitteilung",
        "domain": "axa.de",
    },
    {
        "key": "huk", "name": "HUK-Coburg",
        "media_query": "HUK-Coburg+Versicherung",
        "own_query": "site:huk.de+OR+site:huk-coburg.de+Presse",
        "domain": "huk.de",
    },
    {
        "key": "generali", "name": "Generali",
        "media_query": "Generali+Deutschland+Versicherung",
        "own_query": "site:generali.de+Presse+OR+Pressemitteilung",
        "domain": "generali.de",
    },
    {
        "key": "signal-iduna", "name": "Signal Iduna",
        "media_query": "Signal+Iduna+Versicherung",
        "own_query": "site:signal-iduna.de+Presse",
        "domain": "signal-iduna.de",
    },
    {
        "key": "ruv", "name": "R+V",
        "media_query": "R%2BV+Versicherung",
        "own_query": "site:ruv.de+Presse+OR+Pressemitteilung",
        "domain": "ruv.de",
    },
    {
        "key": "devk", "name": "DEVK",
        "media_query": "DEVK+Versicherung",
        "own_query": "site:devk.de+Pressemitteilung",
        "domain": "devk.de",
    },
    {
        "key": "hannoversche", "name": "Hannoversche",
        "media_query": "Hannoversche+Lebensversicherung",
        "own_query": "site:hannoversche.de",
        "domain": "hannoversche.de",
    },
    {
        "key": "cosmos", "name": "Cosmos Direkt",
        "media_query": "CosmosDirekt+Versicherung",
        "own_query": "site:cosmosdirekt.de+Presse+OR+Pressemitteilung",
        "domain": "cosmosdirekt.de",
    },
]

# ── Themen-Tagging ────────────────────────────────────────────────────────────
TOPIC_RULES = [
    ("KFZ & Mobilität",       [r"\bkfz\b", r"\bauto\b", r"\bfahrzeug", r"\bmobilit", r"\be-auto", r"\belektroauto", r"\bverkehr", r"\bunfall"]),
    ("Gesundheit & Pflege",    [r"\bgesundheit", r"\bkranken", r"\bpflege", r"\bmedizin", r"\barzt", r"\bklinik", r"\bvorsorge", r"\bdkv\b"]),
    ("Digitalisierung & KI",   [r"\bdigital", r"\bki\b", r"\bartificial", r"\bonline", r"\bapp\b", r"\btech", r"\bcloud", r"\bautomatis", r"\bchatbot"]),
    ("Klima & Nachhaltigkeit", [r"\bklima", r"\bnachhaltig", r"\bumwelt", r"\bwetter", r"\bsturm", r"\bueberschwemmung", r"\bhochwasser", r"\bco2", r"\bgreen"]),
    ("Finanzen & Vorsorge",    [r"\brente", r"\baltersvorsorge", r"\bleben.?versicherung", r"\banlage", r"\bfonds", r"\bkapital", r"\bfinan", r"\bsparen"]),
    ("Recht & Regulierung",    [r"\brecht", r"\bregulier", r"\bbafin", r"\bgesetz", r"\bcompliance", r"\bdatenschutz", r"\bgdpr", r"\bdsgvo"]),
    ("Personal & Karriere",    [r"\bmitarbeiter", r"\bkarriere", r"\bpersonal", r"\bausbildung", r"\brecruiting", r"\btarif.?vertrag", r"\bstreik"]),
    ("Schaden & Leistung",     [r"\bschaden", r"\bleistung", r"\bregulierung", r"\bwiederbeschaffung", r"\bkulanz"]),
    ("Produkt & Innovation",   [r"\bprodukt", r"\bneu.?versicherung", r"\binnovation", r"\btarif(?!vertrag)", r"\bangebo"]),
    ("Unternehmen & Strategie",[r"\bfusion", r"\bumsatz", r"\bgewinn", r"\bbilanz", r"\bstrateg", r"\brestruktur", r"\bwachstum", r"\bmarkt"]),
]


def tag_topics(title):
    """Ordne einem Titel 1-3 Themen zu."""
    title_lower = title.lower()
    matched = []
    for topic_name, patterns in TOPIC_RULES:
        for pat in patterns:
            if re.search(pat, title_lower):
                matched.append(topic_name)
                break
    return matched[:3] if matched else ["Allgemein"]


def parse_rss_date(date_str):
    """Parse RSS pubDate (RFC 822) zu ISO-Format."""
    try:
        clean = re.sub(r'\s+\w{2,4}$', '', date_str.strip())
        dt = datetime.strptime(clean, "%a, %d %b %Y %H:%M:%S")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def crawl_google_news(query, source_type="media", max_items=100):
    """Google News RSS-Feed crawlen.
    source_type: 'media' = Medienberichte, 'own' = eigene Pressemitteilungen
    """
    url = "https://news.google.com/rss/search?q=%s&hl=de&gl=DE&ceid=DE:de" % query
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            xml_data = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print("    RSS-Fehler (%s): %s" % (source_type, str(e)[:60]))
        return []

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as e:
        print("    XML-Parse-Fehler: %s" % str(e)[:60])
        return []

    items = []
    for item_el in root.findall(".//item")[:max_items]:
        title_el = item_el.find("title")
        link_el = item_el.find("link")
        pub_el = item_el.find("pubDate")
        source_el = item_el.find("source")

        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        link = link_el.text.strip() if link_el is not None and link_el.text else ""
        pub_date = parse_rss_date(pub_el.text) if pub_el is not None and pub_el.text else None
        source = source_el.text.strip() if source_el is not None and source_el.text else ""

        if not title:
            continue

        topics = tag_topics(title)
        items.append({
            "title": title,
            "url": link,
            "date": pub_date,
            "source": source,
            "type": source_type,
            "topics": topics,
        })

    return items


def deduplicate(articles):
    """Entferne Duplikate basierend auf aehnlichen Titeln."""
    seen_titles = set()
    unique = []
    for a in articles:
        # Normalisiere Titel fuer Vergleich
        norm = re.sub(r'[^a-zäöü0-9]', '', a["title"].lower())[:60]
        if norm not in seen_titles:
            seen_titles.add(norm)
            unique.append(a)
    return unique


def compute_stats(articles_by_brand):
    """Statistiken fuer alle Brands berechnen."""
    now = datetime.now(timezone.utc)
    cutoff_30d = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    cutoff_90d = (now - timedelta(days=90)).strftime("%Y-%m-%d")

    stats = {}
    for key, articles in articles_by_brand.items():
        total = len(articles)
        own_count = sum(1 for a in articles if a.get("type") == "own")
        media_count = sum(1 for a in articles if a.get("type") == "media")
        last_30d = sum(1 for a in articles if a.get("date") and a["date"] >= cutoff_30d)
        last_90d = sum(1 for a in articles if a.get("date") and a["date"] >= cutoff_90d)

        # Topic-Verteilung
        topic_counts = Counter()
        for a in articles:
            for t in a.get("topics", []):
                topic_counts[t] += 1

        # Quellen-Verteilung
        source_counts = Counter(a.get("source", "Unbekannt") for a in articles)

        # Neueste und aelteste
        dates = [a["date"] for a in articles if a.get("date")]
        newest = max(dates) if dates else None
        oldest = min(dates) if dates else None

        stats[key] = {
            "total": total,
            "own": own_count,
            "media": media_count,
            "last_30d": last_30d,
            "last_90d": last_90d,
            "newest": newest,
            "oldest": oldest,
            "top_topics": topic_counts.most_common(5),
            "top_sources": source_counts.most_common(5),
        }
    return stats


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print("=" * 60)
    print("Presse-Crawl %s  |  2 Quellen  |  10 Brands" % today)
    print("=" * 60)

    all_brands = {}
    brand_meta = {}

    for brand in BRANDS:
        key = brand["key"]
        name = brand["name"]
        print("\n--- %s ---" % name)

        # 1) Eigene Pressemitteilungen (site:-Filter)
        own = crawl_google_news(brand["own_query"], source_type="own")
        print("  Eigene PMs: %d Artikel" % len(own))

        # Kurze Pause um Rate-Limiting zu vermeiden
        time.sleep(0.5)

        # 2) Medienberichte
        media = crawl_google_news(brand["media_query"], source_type="media")
        print("  Medien:     %d Artikel" % len(media))

        # Zusammenfuehren und deduplizieren
        combined = own + media
        combined = deduplicate(combined)
        # Sortieren nach Datum (neueste zuerst)
        combined.sort(key=lambda a: a.get("date") or "0000", reverse=True)
        all_brands[key] = combined

        dates = [a["date"] for a in combined if a.get("date")]
        newest = max(dates) if dates else "?"
        print("  Gesamt:     %d Artikel (dedupliziert), neuester: %s" % (len(combined), newest))

        # Topic-Zusammenfassung
        topic_counts = Counter()
        for a in combined:
            for t in a.get("topics", []):
                topic_counts[t] += 1
        top3 = ", ".join("%s(%d)" % (t, c) for t, c in topic_counts.most_common(3))
        print("  Top-Themen: %s" % top3)

        brand_meta[key] = {"name": name, "domain": brand["domain"]}

        time.sleep(0.5)

    # Statistiken berechnen
    stats = compute_stats(all_brands)

    # ── JSON speichern ────────────────────────────────────────────────────
    out_data = {
        "as_of": today,
        "sources": ["Google News RSS (Medien)", "Google News RSS (Eigene PMs via site:-Filter)"],
        "brands": brand_meta,
        "stats": {},
        "articles": {},
    }

    for key in all_brands:
        s = stats[key]
        out_data["stats"][key] = {
            "total": s["total"],
            "own": s["own"],
            "media": s["media"],
            "last_30d": s["last_30d"],
            "last_90d": s["last_90d"],
            "newest": s["newest"],
            "oldest": s["oldest"],
            "top_topics": [{"topic": t, "count": c} for t, c in s["top_topics"]],
            "top_sources": [{"source": src, "count": c} for src, c in s["top_sources"]],
        }
        # Alle Artikel speichern (max 80 pro Brand fuer JSON-Groesse)
        out_data["articles"][key] = all_brands[key][:80]

    json_path = Path("data/press_data.json")
    if not json_path.parent.exists():
        json_path.parent.mkdir(parents=True)
    json_path.write_text(json.dumps(out_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nSaved: %s (%d bytes)" % (json_path, json_path.stat().st_size))

    # ── Presse-History: persistente JSON-Datei mit allen Artikeln ─────────
    history_path = Path("data/press_history.json")
    existing_articles = []
    if history_path.exists():
        try:
            existing_articles = json.loads(history_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            existing_articles = []

    # Deduplizierungs-Set: (brand, normalized_title_prefix)
    existing_keys = set()
    for art in existing_articles:
        norm = re.sub(r'[^a-z0-9]', '', art.get("title", "").lower())[:60]
        k = (art.get("brand", ""), norm)
        existing_keys.add(k)

    new_count = 0
    for brand in BRANDS:
        key = brand["key"]
        name = brand["name"]
        for a in all_brands.get(key, []):
            norm = re.sub(r'[^a-z0-9]', '', a.get("title", "").lower())[:60]
            dedup_key = (key, norm)
            if dedup_key not in existing_keys:
                existing_articles.append({
                    "brand": key,
                    "brand_name": name,
                    "title": a.get("title", ""),
                    "url": a.get("url", ""),
                    "date": a.get("date", ""),
                    "source": a.get("source", ""),
                    "type": a.get("type", "media"),
                    "topics": a.get("topics", []),
                    "crawl_date": today,
                })
                existing_keys.add(dedup_key)
                new_count += 1

    # Nach Datum sortieren (neueste zuerst)
    existing_articles.sort(key=lambda x: x.get("date", ""), reverse=True)

    # Max 6 Monate Retention
    cutoff_6m = (datetime.now(timezone.utc) - timedelta(days=180)).strftime("%Y-%m-%d")
    existing_articles = [a for a in existing_articles if a.get("date", "9999") >= cutoff_6m]

    # Max 2000 Artikel insgesamt
    if len(existing_articles) > 2000:
        existing_articles = existing_articles[:2000]

    history_path.write_text(json.dumps(existing_articles, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Presse-History: %d neue Artikel, %d total (max 6 Monate)" % (new_count, len(existing_articles)))


    # ── Event-Emission für Korrelations-Engine ───────────────────────────
    if HAS_EVENTS:
        print("\n--- Event-Emission ---")
        prev_data = load_previous_data(json_path)
        prev_articles = prev_data.get("articles", {})
        event_count = 0
        
        for brand in BRANDS:
            key = brand["key"]
            name = brand["name"]
            current_articles = all_brands.get(key, [])
            previous_articles = prev_articles.get(key, [])
            
            # Vorherige Titel sammeln für Vergleich
            prev_titles = set()
            for a in previous_articles:
                norm = re.sub(r'[^a-zäöü0-9]', '', a.get("title", "").lower())[:60]
                prev_titles.add(norm)
            
            # Neue Artikel finden (nicht in vorherigem Crawl)
            new_articles = []
            for a in current_articles:
                norm = re.sub(r'[^a-zäöü0-9]', '', a.get("title", "").lower())[:60]
                if norm not in prev_titles and a.get("date"):
                    new_articles.append(a)
            
            if new_articles:
                for article in new_articles[:10]:  # Max 10 Events pro Brand
                    # Sentiment grob aus Themen ableiten
                    topics = article.get("topics", [])
                    sent = "neutral"
                    if any(t in topics for t in ["Schaden & Leistung"]):
                        sent = "negative"
                    elif any(t in topics for t in ["Produkt & Innovation", "Unternehmen & Strategie"]):
                        sent = "positive"
                    
                    evt_type = "press_mention" if article.get("type") == "own" else "news_mention"
                    emit_event(
                        event_type=evt_type,
                        brand=name,
                        source="google_news_rss",
                        crawler="update_press",
                        magnitude=1.0,
                        url=article.get("url", ""),
                        sentiment=sent,
                        detail={
                            "title": article.get("title", "")[:120],
                            "date": article.get("date", ""),
                            "media_source": article.get("source", ""),
                            "topics": topics,
                            "article_type": article.get("type", "media"),
                        },
                    )
                    event_count += 1
                    
                print("  %s: %d neue Artikel → %d Events" % (name, len(new_articles), min(len(new_articles), 10)))
        
        # Aktuelle Daten für nächsten Vergleich sichern
        save_for_comparison(json_path)
        print("  Gesamt: %d Events emittiert" % event_count)

    # ── Dashboard-Template patchen ────────────────────────────────────────
    template = Path("dashboard_template.html")
    if not template.exists():
        print("WARN: dashboard_template.html nicht gefunden, skip patch")
        return

    content = template.read_text(encoding="utf-8")

    # PRESS_DATA-Block fuer JS aufbauen
    pd = {
        "as_of": today,
        "stats": {},
        "timeline": {},
        "topic_matrix": {},
        "recent": {},
    }

    for key in all_brands:
        s = stats[key]
        pd["stats"][key] = {
            "name": brand_meta[key]["name"],
            "total": s["total"],
            "own": s["own"],
            "media": s["media"],
            "last_30d": s["last_30d"],
            "last_90d": s["last_90d"],
            "newest": s["newest"],
            "top_topics": [{"t": t, "c": c} for t, c in s["top_topics"]],
        }

        # Timeline: Artikel pro Monat
        month_counts = Counter()
        month_own = Counter()
        month_media = Counter()
        for a in all_brands[key]:
            if a.get("date"):
                m = a["date"][:7]
                month_counts[m] += 1
                if a.get("type") == "own":
                    month_own[m] += 1
                else:
                    month_media[m] += 1
        pd["timeline"][key] = [
            {"m": m, "total": month_counts[m], "own": month_own.get(m, 0), "media": month_media.get(m, 0)}
            for m in sorted(month_counts.keys())
        ]

        # Topic-Matrix
        topic_counts = Counter()
        for a in all_brands[key]:
            for t in a.get("topics", []):
                topic_counts[t] += 1
        pd["topic_matrix"][key] = [{"t": t, "c": c} for t, c in topic_counts.most_common(10)]

        # Letzte 20 Artikel fuer die Liste (mit URL fuer klickbare Links)
        pd["recent"][key] = [
            {
                "title": a["title"][:120],
                "url": a.get("url", ""),
                "date": a["date"],
                "source": a["source"],
                "type": a.get("type", "media"),
                "topics": a["topics"],
            }
            for a in all_brands[key][:20]
        ]

    # Presse-History ins Dashboard einbetten (kompakt: nur title, url, date, source, type)
    press_hist_path = Path("data/press_history.json")
    if press_hist_path.exists():
        try:
            all_hist = json.loads(press_hist_path.read_text(encoding="utf-8"))
            # Nach Brand gruppieren, max 50 pro Brand
            hist_by_brand = {}
            for art in all_hist:
                bk = art.get("brand", "")
                if bk not in hist_by_brand:
                    hist_by_brand[bk] = []
                if len(hist_by_brand[bk]) < 50:
                    hist_by_brand[bk].append({
                        "title": art.get("title", "")[:120],
                        "url": art.get("url", ""),
                        "date": art.get("date", ""),
                        "source": art.get("source", ""),
                        "type": art.get("type", "media"),
                    })
            pd["press_history"] = hist_by_brand
        except (json.JSONDecodeError, IOError):
            pd["press_history"] = {}
    else:
        pd["press_history"] = {}

    new_block = "const PRESS_DATA = " + json.dumps(pd, ensure_ascii=False, separators=(",", ": ")) + ";"

    def find_js_const_block(text, var_name):
        """Finde 'const VAR = {...};' mit Balanced-Bracket-Matching."""
        marker = re.search(r"const " + var_name + r"\s*=\s*\{", text)
        if not marker:
            return None
        brace_start = marker.end() - 1
        depth = 0
        in_string = False
        escape_next = False
        end_pos = brace_start
        for i in range(brace_start, len(text)):
            ch = text[i]
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
        if end_pos < len(text) and text[end_pos] == ';':
            end_pos += 1
        return (marker.start(), end_pos)

    # Pruefen ob PRESS_DATA schon existiert
    block_range = find_js_const_block(content, "PRESS_DATA")
    if block_range:
        start, end = block_range
        content = content[:start] + new_block + content[end:]
        print("PRESS_DATA-Block aktualisiert")
    else:
        # Neuen Block nach SENTIMENT_DATA einfuegen
        sentinel_range = find_js_const_block(content, "SENTIMENT_DATA")
        if sentinel_range:
            insert_pos = sentinel_range[1]
            content = content[:insert_pos] + "\n\n// Presse-Daten (Live-Crawl: eigene PMs + Medienberichte via Google News RSS)\n" + new_block + "\n" + content[insert_pos:]
            print("PRESS_DATA-Block neu eingefuegt (nach SENTIMENT_DATA)")
        else:
            print("WARN: Konnte PRESS_DATA nicht einfuegen -- kein SENTIMENT_DATA gefunden")
            return

    # NULL-byte-safe schreiben (kein rstrip -- kann lange Datenzeilen abschneiden!)
    clean = content.encode("utf-8").replace(b"\x00", b"")
    if not clean.endswith(b"\n"):
        clean += b"\n"
    template.write_bytes(clean)

    print("Patched dashboard_template.html")
    print("  PRESS_DATA: %d bytes" % len(new_block))

    # Zusammenfassung
    print("\n" + "=" * 60)
    print("ZUSAMMENFASSUNG")
    print("=" * 60)
    for key in all_brands:
        s = stats[key]
        print("  %-15s %3d total (%2d eigen, %3d medien) | 30d: %2d | 90d: %2d | newest: %s" % (
            brand_meta[key]["name"], s["total"], s["own"], s["media"],
            s["last_30d"], s["last_90d"], s["newest"] or "?"
        ))


if __name__ == "__main__":
    main()
