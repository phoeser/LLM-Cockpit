#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monatlicher URL-Crawler: holt je Anbieter die Sitemap(s), zaehlt URLs und
kategorisiert sie nach Content-Typ + Sparte -> data/providers.json.

- Sitemap-Discovery ueber robots.txt (Fallback: bekannte Pfade)
- Sitemap-Index wird rekursiv aufgeloest
- gzip wird erkannt/dekomprimiert
- Browser-User-Agent gegen WAF
- Blockierte/leere Anbieter werden mit status markiert (Dashboard behaelt dann manuellen Wert)

Aufruf (monatlich): python scripts/crawl_provider_sitemaps.py
"""
import json
import re
import gzip
import sys
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Anbieter + Domain + Fallback-Sitemap-Pfade (robots.txt hat Vorrang)
PROVIDERS = {
    "ergo":         {"name": "ERGO", "domains": ["www.ergo.de", "www.ergo.com"], "fallback": ["/de/sitemap.xml", "/sitemap.xml"]},
    "allianz":      {"name": "Allianz", "domains": ["www.allianz.de", "www.allianz.com"], "fallback": ["/sitemap.xml"]},
    "huk":          {"name": "HUK-Coburg", "domains": ["www.huk.de"], "fallback": ["/sitemap.xml"]},
    "axa":          {"name": "AXA", "domains": ["www.axa.de", "www.axa.com"], "fallback": ["/sitemap.xml"]},
    "generali":     {"name": "Generali", "domains": ["www.generali.de", "www.generali.com"], "fallback": ["/sitemap.xml", "/de/sitemap.xml"]},
    "signal":       {"name": "Signal Iduna", "domains": ["www.signal-iduna.de"], "fallback": ["/sitemap.xml"]},
    "ruv":          {"name": "R+V", "domains": ["www.ruv.de"], "fallback": ["/sitemap.xml"]},
    "devk":         {"name": "DEVK", "domains": ["www.devk.de"], "fallback": ["/sitemap.xml"]},
    "hannoversche": {"name": "Hannoversche", "domains": ["www.hannoversche.de"], "fallback": ["/sitemap.xml"]},
    "cosmosdirekt": {"name": "Cosmos Direkt", "domains": ["www.cosmosdirekt.de"], "fallback": ["/sitemap.xml"]},
}

# Content-Typ-Regeln (Reihenfolge = Prioritaet); jede URL bekommt genau 1 Typ
CONTENT_RULES = [
    ("presse",  [r"/presse", r"/newsroom", r"pressemitteilung", r"/news/"]),
    ("faq",     [r"/faq", r"haeufige-fragen", r"haeufige_fragen", r"/fragen-und-antworten"]),
    ("glossar", [r"/glossar", r"/lexikon", r"/versicherungslexikon", r"/abc/"]),
    ("rechner", [r"rechner", r"tarifrechner", r"beitrag-berechnen", r"kalkulator", r"/rechnen"]),
    ("ratgeber",[r"/ratgeber", r"/magazin", r"/journal", r"/rechtsportal", r"/wissen", r"/tipps", r"/blog", r"/aktuelles", r"wissenswert", r"/themen/"]),
    # NEU (datenbasiert aus Sonstige-Analyse) — vor 'produkt', damit Firmen-/Rechts-/Standort-Seiten gewinnen:
    ("rechtliches",[r"/impressum", r"/datenschutz", r"/agb", r"nutzungsbedingung", r"rechtliche-hinweise", r"/cookie", r"erstinformation", r"/widerruf", r"barrierefreiheit", r"transparenz"]),
    ("unternehmen",[r"ueber-uns", r"ueber_uns", r"wir-ueber-uns", r"/unternehmen", r"/konzern", r"karriere", r"/jobs", r"nachhaltigkeit", r"/engagement", r"investor", r"autoren-experten", r"/ueber-die", r"unsere-werte", r"public-affairs"]),
    ("standorte", [r"/gs/", r"geschaeftsstelle", r"/vermittler", r"/agentur", r"/standort", r"/filiale", r"vor-ort", r"vertretersuche", r"berater-finden", r"vertretung"]),
    ("medien",    [r"/mediathek", r"/download", r"/formular", r"/dokument", r"broschuere", r"/podcast", r"merkblatt", r"/bilder/"]),
    ("service", [r"/service", r"/kontakt", r"/schadenmeldung", r"/schaden-melden", r"/hilfe", r"/kundenservice", r"meine-?", r"/login", r"kundenportal", r"/mein-"]),
    ("b2b",     [r"/firmen", r"/gewerbe", r"/business", r"/makler", r"/unternehmenskunden", r"/geschaeftskunden"]),
    ("video",   [r"/video", r"youtube"]),
    # 'produkt' breiter: 'versicherung' (ohne fuehrenden Slash), Privatkunden-Bereiche, Vorsorge-/Schutz-Begriffe:
    ("produkt", [r"/produkt", r"versicherung", r"/vorsorge", r"/tarife", r"/de/produkte", r"/pk/", r"/privatkunden", r"absicherung", r"/rente", r"/police", r"/rundum-schutz", r"gesundheit-freizeit"]),
]

# Sparten-Regeln (Mehrfachzuordnung moeglich -> Tiefe je Sparte)
SPARTEN_RULES = {
    "KFZ":          [r"kfz", r"auto", r"motorrad", r"\bpkw\b", r"e-auto", r"fahrzeug"],
    "Kranken":      [r"kranken", r"gesundheit", r"zahn", r"pflege", r"\bdkv\b"],
    "Leben":        [r"leben", r"rente", r"altersvorsorge", r"vorsorge", r"sterbegeld", r"risikoleben", r"berufsunf"],
    "Haftpflicht":  [r"haftpflicht"],
    "Hausrat":      [r"hausrat", r"wohngebaeude", r"wohnen", r"gebaeude", r"haus-"],
    "Rechtsschutz": [r"rechtsschutz"],
    "Reise":        [r"reise"],
    "Tier":         [r"tier", r"hund", r"pferd", r"katze"],
    "Unfall":       [r"unfall"],
}


def http_get(url, timeout=25):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/xml,text/xml,text/html,*/*;q=0.9",
        "Accept-Language": "de-DE,de;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        final_url = r.geturl()
    if raw[:2] == b"\x1f\x8b":  # gzip magic
        try:
            raw = gzip.decompress(raw)
        except Exception:
            pass
    return raw, final_url


_BROWSER = {"pw": None, "ctx": None}


def _browser_get(url, timeout=30):
    """Playwright-Fallback: holt eine URL mit echtem Chromium.
    Noetig fuer Anbieter mit Bot-Erkennung auf TLS-Ebene (z.B. Allianz/Akamai),
    bei denen urllib trotz Browser-User-Agent geblockt wird."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("    [browser] Playwright nicht installiert — kein Fallback")
        return None
    try:
        if _BROWSER["pw"] is None:
            _BROWSER["pw"] = sync_playwright().start()
            b = _BROWSER["pw"].chromium.launch(
                headless=True, args=["--disable-blink-features=AutomationControlled"])
            _BROWSER["ctx"] = b.new_context(
                user_agent=UA, locale="de-DE",
                extra_http_headers={"Accept-Language": "de-DE,de;q=0.9"})
        page = _BROWSER["ctx"].new_page()
        try:
            resp = page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
            if resp is None or resp.status >= 400:
                print("    [browser] %s -> HTTP %s" % (url, resp.status if resp else "?"))
                return None
            raw = resp.body()
            if raw[:2] == b"\x1f\x8b":
                try:
                    raw = gzip.decompress(raw)
                except Exception:
                    pass
            print("    [browser] OK %s (%d Bytes)" % (url, len(raw)))
            return raw
        finally:
            page.close()
    except Exception as e:
        print("    [browser] fail %s: %s" % (url, str(e)[:80]))
        return None


def fetch_raw(url, timeout=25):
    """urllib zuerst; bei Fehler oder HTML-statt-Inhalt (WAF) Browser-Fallback."""
    try:
        raw, _ = http_get(url, timeout=timeout)
        head = raw[:200].lstrip().lower()
        if head.startswith(b"<!doctype html") or b"<html" in head:
            raise RuntimeError("HTML statt erwartetem Inhalt (WAF-Block?)")
        return raw
    except Exception as e:
        print("    http fail %s: %s -> Browser-Fallback" % (url, str(e)[:70]))
        raw = _browser_get(url, timeout=max(timeout, 30))
        if raw is None:
            raise
        return raw


def discover_sitemaps(domain):
    """robots.txt -> Sitemap-URLs; sonst leer."""
    urls = []
    try:
        raw = fetch_raw("https://%s/robots.txt" % domain, timeout=15)
        for line in raw.decode("utf-8", "replace").splitlines():
            m = re.match(r"\s*Sitemap:\s*(\S+)", line, re.I)
            if m:
                urls.append(m.group(1).strip())
    except Exception as e:
        print("    robots.txt fail %s: %s" % (domain, str(e)[:80]))
    return urls


def collect_urls(sitemap_url, seen_sitemaps, depth=0):
    """Laedt eine Sitemap (oder Index, rekursiv) und gibt alle <loc>-URLs zurueck."""
    if depth > 3 or sitemap_url in seen_sitemaps:
        return []
    seen_sitemaps.add(sitemap_url)
    try:
        raw = fetch_raw(sitemap_url)
    except Exception as e:
        print("    sitemap fail %s: %s" % (sitemap_url, str(e)[:80]))
        return []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        print("    XML-Parse-Fehler %s: %s" % (sitemap_url, str(e)[:80]))
        return []
    tag = root.tag.lower()
    urls = []
    locs = [e.text.strip() for e in root.iter() if e.tag.lower().endswith("loc") and e.text]
    if tag.endswith("sitemapindex"):
        for child in locs:
            time.sleep(0.3)
            urls.extend(collect_urls(child, seen_sitemaps, depth + 1))
    else:
        urls.extend(locs)
    return urls


def classify(url):
    u = url.lower()
    for typ, pats in CONTENT_RULES:
        for p in pats:
            if re.search(p, u):
                return typ
    return "sonstige"


def sparten_of(url):
    u = url.lower()
    out = []
    for sp, pats in SPARTEN_RULES.items():
        if any(re.search(p, u) for p in pats):
            out.append(sp)
    return out


def crawl_provider(key, cfg):
    name = cfg["name"]
    print("\n=== %s (%s) ===" % (name, key))
    # 2026-06-06: Ueber ALLE Domains des Anbieters crawlen und URLs summieren
    # (vorher: return nach der ersten Domain mit Treffern -> Konzern-.com wurde
    #  nie erfasst). seen ist global ueber alle Domains (dedupe exakter URLs).
    all_urls = []
    per_domain = {}
    seen = set()
    for domain in cfg["domains"]:
        sitemaps = discover_sitemaps(domain)
        if not sitemaps:
            sitemaps = ["https://%s%s" % (domain, p) for p in cfg.get("fallback", ["/sitemap.xml"])]
        before = len(all_urls)
        for sm in sitemaps:
            all_urls.extend(collect_urls(sm, seen))
        all_urls = list(dict.fromkeys(all_urls))  # dedupe, Reihenfolge erhalten
        per_domain[domain] = {"count": len(all_urls) - before}
        print("  %s: +%d URLs (kumuliert %d)" % (domain, len(all_urls) - before, len(all_urls)))

    if all_urls:
        counts = {t: 0 for t, _ in CONTENT_RULES}
        counts["sonstige"] = 0
        sparten = {sp: 0 for sp in SPARTEN_RULES}
        sonstige_urls = []
        for u in all_urls:
            c = classify(u)
            counts[c] += 1
            if c == "sonstige":
                sonstige_urls.append(u)
            for sp in sparten_of(u):
                sparten[sp] += 1
        sparten = {k: v for k, v in sparten.items() if v > 0}
        seg_freq = {}
        for u in sonstige_urls:
            try:
                path = re.sub(r"^https?://[^/]+", "", u).strip("/")
                seg = path.split("/")[0].split("?")[0][:40] if path else "(root)"
                seg_freq[seg] = seg_freq.get(seg, 0) + 1
            except Exception:
                pass
        top_segs = dict(sorted(seg_freq.items(), key=lambda kv: -kv[1])[:25])
        print("  OK: %d URLs gesamt ueber %d Domain(s)" % (len(all_urls), len(cfg["domains"])))
        return {
            "name": name,
            "total": len(all_urls),
            "ratgeber": counts["ratgeber"], "faq": counts["faq"], "rechner": counts["rechner"],
            "presse": counts["presse"], "glossar": counts["glossar"], "service": counts["service"],
            "produkt": counts["produkt"], "b2b": counts["b2b"], "video": counts["video"],
            "rechtliches": counts["rechtliches"], "unternehmen": counts["unternehmen"],
            "standorte": counts["standorte"], "medien": counts["medien"],
            "sonstige": counts["sonstige"],
            "sonstige_top_segments": top_segs,
            "sonstige_sample": sonstige_urls[:50],
            "sparten": dict(sorted(sparten.items(), key=lambda kv: -kv[1])),
            "per_domain": per_domain,
            "domains": cfg["domains"],
            "source": "crawl",
            "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "sitemaps_used": len(seen),
        }
    print("  BLOCKIERT/leer")
    return {"name": name, "total": None, "source": "blockiert",
            "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d")}


def main():
    out = {"_generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "providers": {}}
    only = sys.argv[1:] or list(PROVIDERS.keys())
    for key in only:
        if key not in PROVIDERS:
            continue
        try:
            out["providers"][key] = crawl_provider(key, PROVIDERS[key])
        except Exception as e:
            print("  ERROR %s: %s" % (key, str(e)[:120]))
            out["providers"][key] = {"name": PROVIDERS[key]["name"], "total": None, "source": "error", "error": str(e)[:200]}
        time.sleep(0.5)
    outp = Path("data/providers.json")
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for p in out["providers"].values() if p.get("total"))
    print("\n=== Fertig: %d/%d Anbieter gecrawlt -> %s ===" % (ok, len(out["providers"]), outp))
    return 0


def _close_browser():
    try:
        if _BROWSER["pw"] is not None:
            _BROWSER["pw"].stop()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        rc = main()
    finally:
        _close_browser()
    sys.exit(rc)
