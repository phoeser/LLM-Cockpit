"""Crawlt die offene ERGO Vermittler-API und schreibt berater_data.json.

API: GET https://www.ergo.de/ergode/handlers/agentsearchhandler.ashx
     ?zip={plz}&radius={km}&page={n}
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# DE-flaechendeckend: 95 PLZ-Seeds, eine pro 2-stelligem Bereich + Grossstaedte
SEED_PLZ = [
    ("01067", "Dresden"), ("02625", "Bautzen"), ("03046", "Cottbus"),
    ("04109", "Leipzig"), ("06108", "Halle"), ("07743", "Jena"),
    ("08056", "Zwickau"), ("09111", "Chemnitz"),
    ("10115", "Berlin"), ("12099", "Berlin-Tempelhof"), ("13347", "Berlin-Wedding"),
    ("14467", "Potsdam"), ("15230", "Frankfurt-Oder"), ("16225", "Eberswalde"),
    ("17033", "Neubrandenburg"), ("18055", "Rostock"), ("19053", "Schwerin"),
    ("20095", "Hamburg"), ("21073", "Hamburg-Sued"), ("22043", "Hamburg-Wandsbek"),
    ("23552", "Luebeck"), ("24103", "Kiel"), ("25524", "Itzehoe"),
    ("26122", "Oldenburg"), ("27568", "Bremerhaven"), ("28195", "Bremen"),
    ("29221", "Celle"),
    ("30159", "Hannover"), ("31134", "Hildesheim"), ("32257", "Buende"),
    ("33602", "Bielefeld"), ("34117", "Kassel"), ("35037", "Marburg"),
    ("36037", "Fulda"), ("37073", "Goettingen"), ("38100", "Braunschweig"),
    ("39104", "Magdeburg"),
    ("40213", "Duesseldorf"), ("41061", "Moenchengladbach"), ("42103", "Wuppertal"),
    ("44135", "Dortmund"), ("45127", "Essen"), ("46045", "Oberhausen"),
    ("47051", "Duisburg"), ("48143", "Muenster"), ("49074", "Osnabrueck"),
    ("50667", "Koeln"), ("51063", "Koeln-Muelheim"), ("52062", "Aachen"),
    ("53111", "Bonn"), ("54290", "Trier"), ("55116", "Mainz"),
    ("56068", "Koblenz"), ("57072", "Siegen"), ("58095", "Hagen"),
    ("59065", "Hamm"),
    ("60311", "Frankfurt-Main"), ("61169", "Friedberg"), ("63065", "Offenbach"),
    ("64283", "Darmstadt"), ("65183", "Wiesbaden"), ("66111", "Saarbruecken"),
    ("67059", "Ludwigshafen"), ("68159", "Mannheim"), ("69115", "Heidelberg"),
    ("70173", "Stuttgart"), ("71032", "Boeblingen"), ("72072", "Tuebingen"),
    ("73033", "Goeppingen"), ("74072", "Heilbronn"), ("75175", "Pforzheim"),
    ("76133", "Karlsruhe"), ("77652", "Offenburg"), ("78050", "Villingen"),
    ("79098", "Freiburg"),
    ("80331", "Muenchen"), ("81369", "Muenchen-Sued"), ("82041", "Furth"),
    ("83022", "Rosenheim"), ("84028", "Landshut"), ("85049", "Ingolstadt"),
    ("86150", "Augsburg"), ("87435", "Kempten"), ("88045", "Friedrichshafen"),
    ("89073", "Ulm"),
    ("90402", "Nuernberg"), ("91054", "Erlangen"), ("92224", "Amberg"),
    ("93047", "Regensburg"), ("94032", "Passau"), ("95028", "Hof"),
    ("96047", "Bamberg"), ("97070", "Wuerzburg"), ("98527", "Suhl"),
    ("99084", "Erfurt"),
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
PAGE_LIMIT = 80
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
    dkv_count = sum(1 for r in rows if "-dkv." in r["homepage"] or "dkv-" in r["homepage"])
    standard_count = sum(1 for r in rows
                         if r["homepage"]
                         and not r["homepage"].startswith("rd-")
                         and "-dkv." not in r["homepage"]
                         and "dkv-" not in r["homepage"])
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
    out_path = out_dir / "berater_data.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OK Geschrieben: %s (%d bytes)" % (out_path, out_path.stat().st_size))
    t = agg["totals"]
    print("   Total: %d Vermittler" % t["vermittler"])
    print("   Mit Subdomain: %d" % t["with_subdomain"])
    print("   Mit Foto: %d" % t["with_image"])
    print("   Mit Social: %d" % t["with_social"])
    # Patch dashboard_template.html: BERATER_DATA Block austauschen (nur Aggregate + 50er-Sample-Fallback)
    template = out_dir / "dashboard_template.html"
    if template.exists():
        import re as _re
        html = template.read_text(encoding="utf-8")
        compact = dict(agg)
        sample_keys = ("firstname", "lastname", "zipcode", "city", "homepage", "image")
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
