"""Backfill: echte Artikel-URLs fuer den Presse-Altbestand aufloesen.

Alle Eintraege in data/press_history.json tragen als `url` einen
Google-News-Redirect (https://news.google.com/rss/articles/CBMi...). Damit
laesst sich nicht pruefen, ob ein Presseartikel spaeter von den LLMs zitiert
wurde. Dieses Skript ergaenzt je Eintrag — ohne bestehende Felder zu
ueberschreiben:

    url_real              echte Artikel-URL ("" wenn nicht aufloesbar)
    domain                Domain ohne "www."
    url_real_quelle       "redirect" | "rss_source" | "unaufgeloest"
    url_real_geprueft_am  ISO-Datum des Aufloesungsversuchs

Die eigentliche Aufloesungslogik liegt in scripts/update_press.py und wird
hier importiert (eine Implementierung, zwei Aufrufer).

Eigenschaften:
  * checkpoint-faehig  — nach jedem Block wird press_history.json + Cache
    geschrieben; ein Abbruch kostet hoechstens den letzten Block.
  * idempotent         — Eintraege mit url_real_quelle in {redirect,
    rss_source} werden uebersprungen; "unaufgeloest" wird auf Wunsch
    (--retry-unresolved) erneut versucht.
  * in Etappen lauffaehig — --max-seconds begrenzt die Laufzeit, danach
    einfach erneut starten.

Aufruf (aus dem Repo-Root):
    python3 scripts/backfill_press_urls.py                 # alles, 6 Threads
    python3 scripts/backfill_press_urls.py --max-seconds 500
    python3 scripts/backfill_press_urls.py --limit 100 --workers 4
    python3 scripts/backfill_press_urls.py --report        # nur Auswertung
"""
import argparse
import json
import os
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import update_press as up  # noqa: E402  (Aufloesungslogik + Publisher-Tabelle)

HISTORY_PATH = Path("data/press_history.json")
CACHE_PATH = up.URL_CACHE_PATH

_local = threading.local()


def _session():
    """Pro Thread eine eigene requests.Session (Sessions sind nicht thread-safe)."""
    s = getattr(_local, "session", None)
    if s is None:
        import requests
        s = requests.Session()
        s.headers["User-Agent"] = up.UA
        _local.session = s
    return s


def load_history(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("Unerwartetes Format in %s (erwartet: Liste)" % path)
    return data


def save_history(articles, path):
    """Atomar schreiben — ein Abbruch mitten im Write darf die Datei nicht killen."""
    p = Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(articles, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)


def needs_work(art, retry_unresolved):
    q = art.get("url_real_quelle")
    if q in ("redirect", "rss_source"):
        return False
    if q == "unaufgeloest" and not retry_unresolved:
        return False
    return True


def apply_result(art, real, today):
    """Ergebnis in den Artikel schreiben. Bestehende Felder bleiben unberuehrt."""
    if real:
        art["url_real"] = real
        art["domain"] = up.normalize_domain(real)
        art["url_real_quelle"] = "redirect"
    else:
        dom = up.domain_from_source(art.get("source", ""))
        art["url_real"] = ""
        art["domain"] = dom
        art["url_real_quelle"] = "rss_source" if dom else "unaufgeloest"
    art["url_real_geprueft_am"] = today
    return art["url_real_quelle"]


def resolve_one(art, cache, cache_lock, today, sleep):
    """Einen Artikel aufloesen. Wirft nie."""
    try:
        url = art.get("url", "") or ""
        article_id = up.extract_gnews_id(url)

        if not article_id:
            # Kein Google-News-Link -> URL ist bereits echt
            return apply_result(art, url if up.normalize_domain(url) else "", today)

        with cache_lock:
            hit = cache.get(article_id)
        if hit and hit.get("url_real"):
            return apply_result(art, hit["url_real"], today)

        real, _ = up.resolve_google_news_url(url, session=_session(), sleep=sleep)
        if real:
            with cache_lock:
                cache[article_id] = {"url_real": real, "quelle": "redirect",
                                     "geprueft_am": today}
        return apply_result(art, real, today)
    except Exception:
        return apply_result(art, "", today)


def report(articles):
    """Auswertung: Quoten je Weg + Top-Domains."""
    quelle = Counter(a.get("url_real_quelle") or "offen" for a in articles)
    total = len(articles)
    print("\n" + "=" * 62)
    print("AUFLOESUNGSQUOTE  (%d Artikel)" % total)
    print("=" * 62)
    for k in ("redirect", "rss_source", "unaufgeloest", "offen"):
        if quelle.get(k):
            print("  %-14s %5d  (%5.1f %%)" % (k, quelle[k], 100.0 * quelle[k] / total))
    with_domain = sum(1 for a in articles if a.get("domain"))
    with_url = sum(1 for a in articles if a.get("url_real"))
    print("  ---")
    print("  echte URL      %5d  (%5.1f %%)" % (with_url, 100.0 * with_url / total))
    print("  Domain bekannt %5d  (%5.1f %%)" % (with_domain, 100.0 * with_domain / total))

    dom = Counter(a["domain"] for a in articles if a.get("domain"))
    print("\nTOP-15 DOMAINS")
    for d, c in dom.most_common(15):
        print("  %-38s %4d" % (d, c))

    unres = Counter(a.get("source", "?") for a in articles
                    if a.get("url_real_quelle") == "unaufgeloest")
    if unres:
        print("\nUNAUFGELOEST — haeufigste RSS-Quellen (fehlen in PUBLISHER_DOMAINS)")
        for s, c in unres.most_common(10):
            print("  %-38s %4d" % (s[:38], c))
    return quelle


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--history", default=str(HISTORY_PATH))
    ap.add_argument("--cache", default=str(CACHE_PATH))
    ap.add_argument("--workers", type=int, default=6, help="parallele Threads (default 6)")
    ap.add_argument("--chunk", type=int, default=40, help="Artikel je Checkpoint (default 40)")
    ap.add_argument("--limit", type=int, default=0, help="max. Artikel in diesem Lauf (0 = alle)")
    ap.add_argument("--max-seconds", type=float, default=0,
                    help="Laufzeitbudget; danach sauber beenden (0 = unbegrenzt)")
    ap.add_argument("--sleep", type=float, default=0.2, help="Pause zwischen Google-Requests")
    ap.add_argument("--retry-unresolved", action="store_true",
                    help="Eintraege mit url_real_quelle=unaufgeloest erneut versuchen")
    ap.add_argument("--report", action="store_true", help="nur auswerten, nichts aufloesen")
    args = ap.parse_args()

    hist_path = Path(args.history)
    if not hist_path.exists():
        raise SystemExit("Nicht gefunden: %s (aus dem Repo-Root starten)" % hist_path)

    articles = load_history(hist_path)
    print("Presse-History: %d Artikel  (%s)" % (len(articles), hist_path))

    if args.report:
        report(articles)
        return

    cache = up.load_url_cache(args.cache)
    print("URL-Cache: %d Eintraege" % len(cache))

    todo = [a for a in articles if needs_work(a, args.retry_unresolved)]
    if args.limit:
        todo = todo[:args.limit]
    print("Zu bearbeiten: %d Artikel (Threads: %d, Chunk: %d)"
          % (len(todo), args.workers, args.chunk))
    if not todo:
        print("Nichts zu tun — alles aufgeloest.")
        report(articles)
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cache_lock = threading.Lock()
    started = time.time()
    done = 0
    run_stats = Counter()
    stopped_early = False

    for i in range(0, len(todo), args.chunk):
        if args.max_seconds and (time.time() - started) > args.max_seconds:
            stopped_early = True
            break
        chunk = todo[i:i + args.chunk]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            results = list(pool.map(
                lambda a: resolve_one(a, cache, cache_lock, today, args.sleep), chunk))
        run_stats.update(results)
        done += len(chunk)

        # Checkpoint
        save_history(articles, hist_path)
        up.save_url_cache(cache, args.cache)
        elapsed = time.time() - started
        rate = done / elapsed if elapsed else 0
        print("  [%4d/%4d] %5.1fs  %.2f Art./s  redirect=%d rss_source=%d unaufgeloest=%d"
              % (done, len(todo), elapsed, rate, run_stats["redirect"],
                 run_stats["rss_source"], run_stats["unaufgeloest"]))

    save_history(articles, hist_path)
    up.save_url_cache(cache, args.cache)

    print("\nLauf beendet: %d von %d bearbeitet in %.1fs%s"
          % (done, len(todo), time.time() - started,
             "  (Zeitbudget erreicht — einfach erneut starten)" if stopped_early else ""))
    report(articles)


if __name__ == "__main__":
    main()
