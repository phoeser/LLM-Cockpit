"""Crawlt die offene ERGO Vermittler-API und schreibt berater_data.json.

API: GET https://www.ergo.de/ergode/handlers/agentsearchhandler.ashx
     ?zip={plz}&radius={km}&page={n}
Response: {"TotalAgentCount": int,
           "Agents": [{firstname, lastname, zipcode, city, address,
                       phone, mobile, homepage, function: [Codes],
                       social: {...}}]}

ENV BERATER_PLZ_LIMIT=N -> nur erste N Seed-PLZ crawlen (lokales Test-Helper).

Stand 2026-04-26 - API ist oeffentlich abrufbar, kein Auth noetig.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

SEED_PLZ = [
    ("20095", "Hamburg"), ("28195", "Bremen"), ("24103", "Kiel"),
    ("23552", "Luebeck"), ("19053", "Schwerin"), ("18055", "Rostock"),
    ("30159", "Hannover"), ("33602", "Bielefeld"), ("44135", "Dortmund"),
    ("48143", "Muenster"), ("50667", "Koeln"), ("40213", "Duesseldorf"),
    ("47051", "Duisburg"), ("52062", "Aachen"), ("55116", "Mainz"),
    ("60311", "Frankfurt"), ("65183", "Wiesbaden"), ("66111", "Saarbruecken"),
    ("34117", "Kassel"), ("99084", "Erfurt"), ("06108", "Halle"),
    ("10115", "Berlin"), ("14467", "Potsdam"), ("01067", "Dresden"),
    ("04109", "Leipzig"), ("39104", "Magdeburg"), ("03046", "Cottbus"),
    ("80331", "Muenchen"), ("90402", "Nuernberg"), ("70173", "Stuttgart"),
    ("76133", "Karlsruhe"), ("79098", "Freiburg"), ("89073", "Ulm"),
    ("93047", "Regensburg"), ("86150", "Augsburg"), ("87435", "Kempten"),
]

API_URL = "https://www.ergo.de/ergode/handlers/agentsearchhandler.ashx"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0 Safari/537.36"),
    "Referer": "https://www.ergo.de/de/Vermittlersuche",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}
RADIUS_KM = 50
PAGE_LIMIT = 60
SLEEP_BETWEEN = 0.15


def fetch_page(plz, page):
    url = "%s?zip=%s&radius=%d&page=%d" % (API_URL, plz, RADIUS_KM, page)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        sys.stderr.write("  WARN %s p%d: %s: %s\n" % (plz, page, type(e).__name__, e))
        return None


def crawl_plz(plz, name):
    first = fetch_page(plz, 1)
    if not first:
        return []
    total = first.get("TotalAgentCount", 0)
    agents = list(first.get("Agents", []))
    if total <= 10:
        return agents
    pages = min((total + 9) // 10, PAGE_LIMIT)
    print("  %s %s: total=%d, lade %d Seiten" % (plz, name, total, pages))
    for p in range(2, pages + 1):
        time.sleep(SLEEP_BETWEEN)
        d = fetch_page(plz, p)
        if d and d.get("Agents"):
            agents.extend(d["Agents"])
        else:
            break
    return agents


def normalize(a):
    return {
        "firstname": (a.get("firstname") or "").strip(),
        "lastname": (a.get("lastname") or "").strip(),
        "zipcode": (a.get("zipcode") or "").strip(),
        "city": (a.get("city") or "").strip(),
        "address": (a.get("address") or "").strip(),
        "phone": (a.get("phone") or "").strip(),
        "mobile": (a.get("mobile") or "").strip(),
        "homepage": (a.get("homepage") or "").strip().lower(),
        "image": a.get("image") or "",
        "functions": list(a.get("function") or []),
        "social": a.get("social") or {},
    }


def aggregate(rows):
    total = len(rows)
    with_home = sum(1 for r in rows if r["homepage"])
    with_image = sum(1 for r in rows if r["image"])
    with_social = sum(1 for r in rows if r["social"] and any(r["social"].values()))
    fn_count = {}
    for r in rows:
        for f in r["functions"]:
            fn_count[f] = fn_count.get(f, 0) + 1
    city_count = {}
    for r in rows:
        c = r["city"] or "?"
        city_count[c] = city_count.get(c, 0) + 1
    top_cities = sorted(city_count.items(), key=lambda kv: -kv[1])[:20]
    rd_count = sum(1 for r in rows if r["homepage"].startswith("rd-"))
    dkv_count = sum(1 for r in rows if "-dkv." in r["homepage"])
    standard_count = sum(1 for r in rows
                         if r["homepage"]
                         and not r["homepage"].startswith("rd-")
                         and "-dkv." not in r["homepage"])
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "totals": {
            "vermittler": total,
            "with_subdomain": with_home,
            "with_image": with_image,
            "with_social": with_social,
            "estimated_subpages_low": with_home * 10,
            "estimated_subpages_high": with_home * 15,
        },
        "subdomain_pattern": {
            "rd_regional": rd_count,
            "dkv_partner": dkv_count,
            "standard_einzelagent": standard_count,
        },
        "functions": dict(sorted(fn_count.items(), key=lambda kv: -kv[1])),
        "top_cities": top_cities,
    }


def main():
    out_dir = Path(__file__).parent.parent
    seen = {}
    raw_count = 0
    plz_limit = os.environ.get("BERATER_PLZ_LIMIT")
    seed = SEED_PLZ[: int(plz_limit)] if plz_limit and plz_limit.isdigit() else SEED_PLZ
    print("=== ERGO Vermittler-Crawl ueber %d Seed-PLZ ===" % len(seed))
    t0 = time.time()
    for plz, name in seed:
        try:
            agents = crawl_plz(plz, name)
        except Exception as e:
            sys.stderr.write("  ERROR %s: %s\n" % (plz, e))
            continue
        raw_count += len(agents)
        for a in agents:
            n = normalize(a)
            key = n["homepage"] or "%s|%s|%s" % (n["firstname"], n["lastname"], n["address"])
            if key not in seen:
                seen[key] = n
    rows = list(seen.values())
    elapsed = time.time() - t0
    print("\n=== Crawl fertig: %d raw, %d unique (%.1fs) ===" % (raw_count, len(rows), elapsed))
    agg = aggregate(rows)
    payload = dict(agg)
    payload["vermittler"] = rows
    out = out_dir / "berater_data.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OK Geschrieben: %s (%d bytes)" % (out, out.stat().st_size))
    t = agg["totals"]
    print("   Total: %d Vermittler" % t["vermittler"])
    print("   Mit Subdomain: %d" % t["with_subdomain"])
    print("   Geschaetzt %d-%d Subseiten" % (t["estimated_subpages_low"], t["estimated_subpages_high"]))
    # Patch dashboard_template.html: BERATER_DATA Block austauschen
    template = out_dir / "dashboard_template.html"
    if template.exists():
        import re as _re
        html = template.read_text(encoding="utf-8")
        # Compact payload fuer Inline-Embed: Aggregationen voll, Vermittler-Liste auf 50 limitiert
        compact = dict(agg)
        sample_keys = ("firstname", "lastname", "zipcode", "city", "homepage")
        compact["vermittler"] = [{k: v.get(k, "") for k in sample_keys} for v in rows[:50]]
        block = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
        new_marker = "/* BERATER_DATA_START */" + block + "/* BERATER_DATA_END */"
        pat = _re.compile(r"/\*\s*BERATER_DATA_START\s*\*/[\s\S]*?/\*\s*BERATER_DATA_END\s*\*/")
        if pat.search(html):
            html = pat.sub(lambda m: new_marker, html, count=1)
            data = html.encode("utf-8").replace(b"\x00", b"").rstrip() + b"\n"
            template.write_bytes(data)
            print("   Template gepatcht: %s (%d bytes)" % (template, template.stat().st_size))
        else:
            print("   WARN: BERATER_DATA marker nicht gefunden im Template")
    else:
        print("   INFO: %s nicht vorhanden, skip Template-Patch" % template)
    return 0


if __name__ == "__main__":
    sys.exit(main())