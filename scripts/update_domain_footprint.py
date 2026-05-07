"""Crawlt fuer jeden der 10 Anbieter alle Subdomains via hackertarget.com.
Schreibt domain_footprint_data.json + patcht das Template inline.

Hackertarget free tier: max 50 Resultate pro Query - akzeptabel als Stichprobe.
Fuer ERGO sehen wir vermutlich primaer ergo.de und einige Vermittler-Subdomains.
Wichtiger Datenpunkt: Welche Domains pro Marke gehoeren dazu, was liegt wo.
"""
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from shared.event_emitter import emit_event, load_previous_data, save_for_comparison
except ImportError:
    emit_event = None

# Marke -> primaere Domain
BRANDS = [
    ("ergo", "ERGO", "ergo.de", ["ergo.de", "ergo.com", "ergodirekt.de"]),
    ("allianz", "Allianz", "allianz.de", ["allianz.de", "allianz.com", "allianzdirect.de", "markt-und-kunde.de"]),
    ("axa", "AXA", "axa.de", ["axa.de", "axa.com"]),
    ("huk", "HUK-Coburg", "huk.de", ["huk.de", "huk24.de"]),
    ("generali", "Generali", "generali.de", ["generali.de", "generali.com"]),
    ("signal-iduna", "Signal Iduna", "signal-iduna.de", ["signal-iduna.de"]),
    ("ruv", "R+V", "ruv.de", ["ruv.de"]),
    ("devk", "DEVK", "devk.de", ["devk.de"]),
    ("hannoversche", "Hannoversche", "hannoversche.de", ["hannoversche.de"]),
    ("cosmosdirekt", "Cosmos Direkt", "cosmosdirekt.de", ["cosmosdirekt.de"]),
]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def fetch_subdomains(domain):
    """Hole Subdomains via hackertarget.com hostsearch API (free tier).
    Returns list of subdomain strings."""
    url = "https://api.hackertarget.com/hostsearch/?q=" + domain
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            txt = r.read().decode("utf-8", errors="ignore")
        subs = set()
        for line in txt.splitlines():
            host = line.split(",", 1)[0].strip().lower()
            if host and host.endswith("." + domain) or host == domain:
                subs.add(host)
        return sorted(subs)
    except Exception as e:
        sys.stderr.write("  WARN " + domain + ": " + str(e)[:80] + "\n")
        return []


def categorize(subs, base_domain):
    """Klassifiziere Subdomains in Kategorien."""
    cats = {"www_root": 0, "vermittler": 0, "service": 0, "newsroom": 0, "tech": 0, "other": 0}
    examples = {"vermittler": [], "service": [], "newsroom": [], "tech": [], "other": []}
    for s in subs:
        if s == base_domain or s == "www." + base_domain:
            cats["www_root"] += 1
            continue
        # Vermittler-Pattern: vorname-nachname.domain or rd-stadt.domain
        prefix = s.replace("." + base_domain, "")
        if "-" in prefix and not prefix.startswith(("api", "app", "cdn", "stat", "test", "dev", "stage", "prod")):
            cats["vermittler"] += 1
            if len(examples["vermittler"]) < 5: examples["vermittler"].append(s)
        elif any(k in prefix for k in ["news", "press", "media", "blog", "magazin"]):
            cats["newsroom"] += 1
            if len(examples["newsroom"]) < 5: examples["newsroom"].append(s)
        elif any(k in prefix for k in ["service", "kunde", "portal", "support", "hilfe", "login", "my"]):
            cats["service"] += 1
            if len(examples["service"]) < 5: examples["service"].append(s)
        elif any(k in prefix for k in ["api", "app", "cdn", "stat", "test", "dev", "stage", "tech"]):
            cats["tech"] += 1
            if len(examples["tech"]) < 5: examples["tech"].append(s)
        else:
            cats["other"] += 1
            if len(examples["other"]) < 5: examples["other"].append(s)
    return cats, examples


def main():
    out = []
    print("=== Domain-Footprint Crawl fuer", len(BRANDS), "Marken ===")
    for key, name, primary, all_domains in BRANDS:
        print("  " + name + " (" + primary + ")")
        all_subs = []
        per_domain = {}
        for d in all_domains:
            subs = fetch_subdomains(d)
            per_domain[d] = {"count": len(subs), "examples": subs[:10]}
            all_subs.extend(subs)
            time.sleep(2)  # rate limit
        # Dedupe
        unique = sorted(set(all_subs))
        # Categorize against primary
        cats, examples = categorize(unique, primary)
        out.append({
            "key": key,
            "name": name,
            "primary_domain": primary,
            "total_unique_subdomains": len(unique),
            "domain_count": len(all_domains),
            "domains": all_domains,
            "per_domain": per_domain,
            "categories": cats,
            "examples": examples,
            "fragmentation_score": (len(all_domains) - 1) * 10 + (cats["newsroom"] > 0 and primary not in [d for d in all_domains if "news" in d or "press" in d]) * 20,
        })

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "hackertarget.com hostsearch (free tier, max 50 results)",
        "brands": out,
    }

    out_dir = Path(__file__).parent.parent
    json_path = out_dir / "domain_footprint_data.json"

    # Vorherige Daten sichern fuer Vergleich
    if emit_event and json_path.exists():
        save_for_comparison(json_path)

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OK", json_path, "(" + str(json_path.stat().st_size) + " bytes)")

    # --- Event-Emitter: domain_change Events ---
    if emit_event:
        _emit_domain_events(json_path, payload)

    # Patch dashboard_template.html
    template = out_dir / "dashboard_template.html"
    if template.exists():
        import re as _re
        html = template.read_text(encoding="utf-8")
        block = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        new_marker = "/* DOMAIN_FOOTPRINT_START */" + block + "/* DOMAIN_FOOTPRINT_END */"
        pat = _re.compile(r"/\*\s*DOMAIN_FOOTPRINT_START\s*\*/[\s\S]*?/\*\s*DOMAIN_FOOTPRINT_END\s*\*/")
        if pat.search(html):
            html = pat.sub(lambda m: new_marker, html, count=1)
            template.write_bytes(html.encode("utf-8").replace(b"\x00", b"").rstrip() + b"\n")
            print("OK Template gepatcht: " + str(template))
        else:
            print("WARN: DOMAIN_FOOTPRINT marker nicht im Template gefunden")
    return 0


def _emit_domain_events(json_path: Path, payload: dict) -> None:
    """Vergleicht Domain-Footprint mit vorherigem und emittiert domain_change Events."""
    prev = load_previous_data(json_path)
    if not prev:
        print("   Kein vorheriger Domain-Footprint -- ueberspringe Event-Emission")
        return

    prev_brands = {b["key"]: b for b in prev.get("brands", [])}
    curr_brands = {b["key"]: b for b in payload.get("brands", [])}
    event_count = 0

    for key, curr in curr_brands.items():
        prev_b = prev_brands.get(key)
        if not prev_b:
            continue

        brand_name = curr["name"]
        curr_total = curr.get("total_unique_subdomains", 0)
        prev_total = prev_b.get("total_unique_subdomains", 0)

        # Gesamtzahl Subdomains veraendert
        if curr_total and prev_total and abs(curr_total - prev_total) >= 2:
            delta = curr_total - prev_total
            emit_event(
                event_type="domain_change",
                brand=brand_name,
                source="hackertarget_hostsearch",
                crawler="update_domain_footprint",
                magnitude=min(abs(delta) / 5, 2.0),
                detail={
                    "metric": "total_subdomains",
                    "old_count": prev_total,
                    "new_count": curr_total,
                    "direction": "growth" if delta > 0 else "shrink",
                },
            )
            event_count += 1

        # Kategorie-Shifts (vermittler, service, newsroom, tech, other)
        curr_cats = curr.get("categories", {})
        prev_cats = prev_b.get("categories", {})
        for cat in ["vermittler", "service", "newsroom", "tech", "other"]:
            c_val = curr_cats.get(cat, 0)
            p_val = prev_cats.get(cat, 0)
            if abs(c_val - p_val) >= 2:
                emit_event(
                    event_type="domain_change",
                    brand=brand_name,
                    source="hackertarget_hostsearch",
                    crawler="update_domain_footprint",
                    magnitude=min(abs(c_val - p_val) / 3, 2.0),
                    detail={
                        "metric": "category_" + cat,
                        "old_count": p_val,
                        "new_count": c_val,
                    },
                )
                event_count += 1

        # Neue Domains pro Marke erkannt
        curr_domains = set(curr.get("domains", []))
        prev_domains = set(prev_b.get("domains", []))
        new_domains = curr_domains - prev_domains
        if new_domains:
            emit_event(
                event_type="page_new",
                brand=brand_name,
                source="hackertarget_hostsearch",
                crawler="update_domain_footprint",
                magnitude=min(len(new_domains) * 0.5, 2.0),
                detail={
                    "metric": "new_domains",
                    "domains": sorted(new_domains),
                },
            )
            event_count += 1

    print("   " + str(event_count) + " domain_change/page_new Events emittiert")


if __name__ == "__main__":
    sys.exit(main())
