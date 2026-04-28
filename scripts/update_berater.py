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

# DE-flaechendeckend: ~200 PLZ-Seeds fuer maximale Abdeckung
# Mehrere Seeds pro 2-stelligem Bereich + Zwischenpunkte fuer lueckenlose Abdeckung
SEED_PLZ = [
    # 0xxxx - Sachsen, Brandenburg, Thueringen
    ("01067", "Dresden"), ("01587", "Riesa"), ("02625", "Bautzen"),
    ("02763", "Zittau"), ("03046", "Cottbus"), ("03238", "Finsterwalde"),
    ("04109", "Leipzig"), ("04600", "Altenburg"), ("04838", "Eilenburg"),
    ("06108", "Halle"), ("06484", "Quedlinburg"), ("06844", "Dessau"),
    ("07743", "Jena"), ("07545", "Gera"), ("08056", "Zwickau"),
    ("08523", "Plauen"), ("09111", "Chemnitz"), ("09599", "Freiberg"),
    # 1xxxx - Berlin, Brandenburg, Mecklenburg-Vorpommern
    ("10115", "Berlin-Mitte"), ("10783", "Berlin-Schoeneberg"),
    ("12099", "Berlin-Tempelhof"), ("12555", "Berlin-Koepenick"),
    ("13347", "Berlin-Wedding"), ("13585", "Berlin-Spandau"),
    ("14467", "Potsdam"), ("14712", "Rathenow"),
    ("15230", "Frankfurt-Oder"), ("15517", "Fuerstenwalde"),
    ("16225", "Eberswalde"), ("16816", "Neuruppin"),
    ("17033", "Neubrandenburg"), ("17489", "Greifswald"),
    ("18055", "Rostock"), ("18435", "Stralsund"),
    ("19053", "Schwerin"), ("19348", "Perleberg"),
    # 2xxxx - Hamburg, Schleswig-Holstein, Niedersachsen-Nord
    ("20095", "Hamburg-Mitte"), ("21073", "Hamburg-Harburg"),
    ("21335", "Lueneburg"), ("22043", "Hamburg-Wandsbek"),
    ("22846", "Norderstedt"), ("23552", "Luebeck"),
    ("23966", "Wismar"), ("24103", "Kiel"),
    ("24837", "Schleswig"), ("25524", "Itzehoe"),
    ("25746", "Heide"), ("26122", "Oldenburg"),
    ("26382", "Wilhelmshaven"), ("26789", "Leer"),
    ("27568", "Bremerhaven"), ("27749", "Delmenhorst"),
    ("28195", "Bremen"), ("29221", "Celle"),
    ("29439", "Luechow"),
    # 3xxxx - Niedersachsen, NRW-Nord, Hessen-Nord
    ("30159", "Hannover"), ("30880", "Laatzen"),
    ("31134", "Hildesheim"), ("31582", "Nienburg"),
    ("32257", "Buende"), ("32756", "Detmold"),
    ("33602", "Bielefeld"), ("33824", "Werther"),
    ("34117", "Kassel"), ("34576", "Homberg"),
    ("35037", "Marburg"), ("35390", "Giessen"),
    ("36037", "Fulda"), ("37073", "Goettingen"),
    ("37154", "Northeim"), ("38100", "Braunschweig"),
    ("38440", "Wolfsburg"), ("38820", "Halberstadt"),
    ("39104", "Magdeburg"), ("39576", "Stendal"),
    # 4xxxx - NRW (Rheinland, Ruhrgebiet)
    ("40213", "Duesseldorf"), ("40699", "Erkrath"),
    ("41061", "Moenchengladbach"), ("41462", "Neuss"),
    ("42103", "Wuppertal"), ("42651", "Solingen"),
    ("42853", "Remscheid"), ("44135", "Dortmund"),
    ("44623", "Herne"), ("45127", "Essen"),
    ("45468", "Muelheim-Ruhr"), ("46045", "Oberhausen"),
    ("46395", "Bocholt"), ("47051", "Duisburg"),
    ("47441", "Moers"), ("47798", "Krefeld"),
    ("48143", "Muenster"), ("48431", "Rheine"),
    ("49074", "Osnabrueck"), ("49477", "Ibbenbueren"),
    # 5xxxx - NRW-Sued, Rheinland-Pfalz-Nord
    ("50667", "Koeln"), ("51063", "Koeln-Muelheim"),
    ("51373", "Leverkusen"), ("52062", "Aachen"),
    ("52349", "Dueren"), ("53111", "Bonn"),
    ("53474", "Bad-Neuenahr"), ("54290", "Trier"),
    ("55116", "Mainz"), ("55543", "Bad-Kreuznach"),
    ("56068", "Koblenz"), ("56410", "Montabaur"),
    ("57072", "Siegen"), ("57462", "Olpe"),
    ("58095", "Hagen"), ("58636", "Iserlohn"),
    ("59065", "Hamm"), ("59494", "Soest"),
    # 6xxxx - Hessen, Rheinland-Pfalz-Sued, Saarland
    ("60311", "Frankfurt-Main"), ("60488", "Frankfurt-West"),
    ("61169", "Friedberg"), ("63065", "Offenbach"),
    ("63450", "Hanau"), ("64283", "Darmstadt"),
    ("65183", "Wiesbaden"), ("65428", "Ruesselsheim"),
    ("66111", "Saarbruecken"), ("66538", "Neunkirchen"),
    ("67059", "Ludwigshafen"), ("67433", "Neustadt-Weinstr"),
    ("67655", "Kaiserslautern"), ("68159", "Mannheim"),
    ("69115", "Heidelberg"), ("69412", "Eberbach"),
    # 7xxxx - Baden-Wuerttemberg
    ("70173", "Stuttgart"), ("70806", "Kornwestheim"),
    ("71032", "Boeblingen"), ("71638", "Ludwigsburg"),
    ("72072", "Tuebingen"), ("72764", "Reutlingen"),
    ("73033", "Goeppingen"), ("73430", "Aalen"),
    ("74072", "Heilbronn"), ("74523", "Schwaebisch-Hall"),
    ("75175", "Pforzheim"), ("76133", "Karlsruhe"),
    ("76646", "Bruchsal"), ("77652", "Offenburg"),
    ("78050", "Villingen"), ("78462", "Konstanz"),
    ("79098", "Freiburg"), ("79539", "Loerrach"),
    # 8xxxx - Bayern-Sued
    ("80331", "Muenchen-Mitte"), ("81369", "Muenchen-Sued"),
    ("81925", "Muenchen-Bogenhausen"), ("82041", "Furth"),
    ("82362", "Weilheim"), ("83022", "Rosenheim"),
    ("83512", "Wasserburg"), ("84028", "Landshut"),
    ("84489", "Burghausen"), ("85049", "Ingolstadt"),
    ("85368", "Moosburg"), ("86150", "Augsburg"),
    ("86720", "Noerdlingen"), ("87435", "Kempten"),
    ("88045", "Friedrichshafen"), ("89073", "Ulm"),
    ("89312", "Guenzburg"),
    # 9xxxx - Bayern-Nord, Thueringen-Sued
    ("90402", "Nuernberg"), ("90762", "Fuerth"),
    ("91054", "Erlangen"), ("91522", "Ansbach"),
    ("92224", "Amberg"), ("92637", "Weiden"),
    ("93047", "Regensburg"), ("93309", "Kelheim"),
    ("94032", "Passau"), ("94315", "Straubing"),
    ("95028", "Hof"), ("95444", "Bayreuth"),
    ("96047", "Bamberg"), ("96450", "Coburg"),
    ("97070", "Wuerzburg"), ("97421", "Schweinfurt"),
    ("97616", "Bad-Neustadt"), ("98527", "Suhl"),
    ("98693", "Ilmenau"), ("99084", "Erfurt"),
    ("99423", "Weimar"),
]

API_URL = "https://www.ergo.de/ergode/handlers/agentsearchhandler.ashx"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0 Safari/537.36"),
    "Referer": "https://www.ergo.de/de/Vermittlersuche",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}
RADIUS_KM = 80       # 80km Radius fuer lueckenlose Abdeckung
PAGE_LIMIT = 100     # max 100 Seiten pro PLZ (= 1000 Agenten)
SLEEP_BETWEEN = 0.2  # etwas langsamer fuer Stabilitaet
MAX_RETRIES = 2      # Retry bei Fehlern


def fetch_page(plz, page):
    url = "%s?zip=%s&radius=%d&page=%d" % (API_URL, plz, RADIUS_KM, page)
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            sys.stderr.write("  WARN %s p%d attempt %d: %s: %s\n" % (plz, page, attempt, type(e).__name__, e))
            if attempt < MAX_RETRIES:
                time.sleep(1.0)  # 1s Pause vor Retry
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
