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
    "ergo":         {"name": "ERGO", "domains": ["www.ergo.de"], "fallback": ["/de/sitemap.xml", "/sitemap.xml"]},
    "allianz":      {"name": "Allianz", "domains": ["www.allianz.de"], "fallback": ["/sitemap.xml"]},
    "huk":          {"name": "HUK-Coburg", "domains": ["www.huk.de"], "fallback": ["/sitemap.xml"]},
    "axa":          {"name": "AXA", "domains": ["www.axa.de"], "fallback": ["/sitemap.xml"]},
    "generali":     {"name": "Generali", "domains": ["www.generali.de"], "fallback": ["/sitemap.xml", "/de/sitemap.xml"]},
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
    ("ratgeber",[r"/ratgeber", r"/magazin", r"/wissen", r"/tipps", r"/blog", r"/aktuelles", r"wissenswert", r"/themen/"]),
    ("service", [r"/service", r"/kontakt", r"/schadenmeldung", r"/schaden-melden", r"/hilfe", r"/kundenservice", r"meine-?", r"/login"]),
    ("b2b",     [r"/firmen", r"/gewerbe", r"/business", r"/makler", r"/unternehmenskunden", r"/geschaeftskunden"]),
    ("video",   [r"/video", r"youtube"]),
    ("produkt", [r"/produkt", r"/versicherung", r"/vorsorge", r"/tarife", r"/de/produkte"]),
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


def discover_sitemaps(domain):
    """robots.txt -> Sitemap-URLs; sonst leer."""
    urls = []
    try:
        raw, _ = http_get("https://%s/robots.txt" % domain, timeout=15)
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
        raw, _ = http_get(sitemap_url)
    except Exception as e:
        print("    sitemap fail %s: %s" % (sitemap_url, str(e)[:80]))
        return []
    # WAF/HTML statt XML?
    head = raw[:200].lstrip().lower()
    if head.startswith(b"<!doctype html") or b"<html" in head:
        print("    %s -> HTML (geblockt?)" % sitemap_url)
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
    for domain in cfg["domains"]:
        sitemaps = discover_sitemaps(domain)
        if not sitemaps:
            sitemaps = ["https://%s%s" % (domain, p) for p in cfg.get("fallback", ["/sitemap.xml"])]
        seen = set()
        all_urls = []
        for sm in sitemaps:
            all_urls.extend(collect_urls(sm, seen))
        all_urls = list(dict.fromkeys(all_urls))  # dedupe, Reihenfolge erhalten
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
            # Analyse-Hilfe: Pfad-Segment-Haeufigkeiten + Stichprobe der Sonstige-URLs
            seg_freq = {}
            for u in sonstige_urls:
                try:
                    path = re.sub(r"^https?://[^/]+", "", u).strip("/")
                    seg = path.split("/")[0].split("?")[0][:40] if path else "(root)"
                    seg_freq[seg] = seg_freq.get(seg, 0) + 1
                except Exception:
                    pass
            top_segs = dict(sorted(seg_freq.items(), key=lambda kv: -kv[1])[:25])
            print("  OK: %d URLs (Sitemaps: %d)" % (len(all_urls), len(seen)))
            return {
                "name": name,
                "total": len(all_urls),
                "ratgeber": counts["ratgeber"], "faq": counts["faq"], "rechner": counts["rechner"],
                "presse": counts["presse"], "glossar": counts["glossar"], "service": counts["service"],
                "produkt": counts["produkt"], "b2b": counts["b2b"], "video": counts["video"],
                "sonstige": counts["sonstige"],
                "sonstige_top_segments": top_segs,
                "sonstige_sample": sonstige_urls[:50],
                "sparten": dict(sorted(sparten.items(), key=lambda kv: -kv[1])),
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


if __name__ == "__main__":
    sys.exit(main())
