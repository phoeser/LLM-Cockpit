"""Crawlt die offene ERGO Vermittler-API und schreibt berater_data.json.

API: GET https://www.ergo.de/ergode/handlers/agentsearchhandler.ashx
     ?zip={plz}&radius={km}&page={n}

Zusaetzlich: Stichproben-Crawl der Berater-Homepages fuer Seiten-Typologisierung.
"""
import json
import os
import re
import random
import sys
import time
from pathlib import Path

# Event-Emitter für Korrelations-Engine
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from shared.event_emitter import emit_event, load_previous_data, save_for_comparison
    HAS_EVENTS = True
except ImportError:
    HAS_EVENTS = False
import urllib.request
import urllib.error
from html.parser import HTMLParser

# DE-flaechendeckend: ~200 PLZ-Seeds fuer maximale Abdeckung
SEED_PLZ = [
    ("01067", "Dresden"), ("01587", "Riesa"), ("02625", "Bautzen"),
    ("02763", "Zittau"), ("03046", "Cottbus"), ("03238", "Finsterwalde"),
    ("04109", "Leipzig"), ("04600", "Altenburg"), ("04838", "Eilenburg"),
    ("06108", "Halle"), ("06484", "Quedlinburg"), ("06844", "Dessau"),
    ("07743", "Jena"), ("07545", "Gera"), ("08056", "Zwickau"),
    ("08523", "Plauen"), ("09111", "Chemnitz"), ("09599", "Freiberg"),
    ("10115", "Berlin-Mitte"), ("10783", "Berlin-Schoeneberg"),
    ("12099", "Berlin-Tempelhof"), ("12555", "Berlin-Koepenick"),
    ("13347", "Berlin-Wedding"), ("13585", "Berlin-Spandau"),
    ("14467", "Potsdam"), ("14712", "Rathenow"),
    ("15230", "Frankfurt-Oder"), ("15517", "Fuerstenwalde"),
    ("16225", "Eberswalde"), ("16816", "Neuruppin"),
    ("17033", "Neubrandenburg"), ("17489", "Greifswald"),
    ("18055", "Rostock"), ("18435", "Stralsund"),
    ("19053", "Schwerin"), ("19348", "Perleberg"),
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
    ("50667", "Koeln"), ("51063", "Koeln-Muelheim"),
    ("51373", "Leverkusen"), ("52062", "Aachen"),
    ("52349", "Dueren"), ("53111", "Bonn"),
    ("53474", "Bad-Neuenahr"), ("54290", "Trier"),
    ("55116", "Mainz"), ("55543", "Bad-Kreuznach"),
    ("56068", "Koblenz"), ("56410", "Montabaur"),
    ("57072", "Siegen"), ("57462", "Olpe"),
    ("58095", "Hagen"), ("58636", "Iserlohn"),
    ("59065", "Hamm"), ("59494", "Soest"),
    ("60311", "Frankfurt-Main"), ("60488", "Frankfurt-West"),
    ("61169", "Friedberg"), ("63065", "Offenbach"),
    ("63450", "Hanau"), ("64283", "Darmstadt"),
    ("65183", "Wiesbaden"), ("65428", "Ruesselsheim"),
    ("66111", "Saarbruecken"), ("66538", "Neunkirchen"),
    ("67059", "Ludwigshafen"), ("67433", "Neustadt-Weinstr"),
    ("67655", "Kaiserslautern"), ("68159", "Mannheim"),
    ("69115", "Heidelberg"), ("69412", "Eberbach"),
    ("70173", "Stuttgart"), ("70806", "Kornwestheim"),
    ("71032", "Boeblingen"), ("71638", "Ludwigsburg"),
    ("72072", "Tuebingen"), ("72764", "Reutlingen"),
    ("73033", "Goeppingen"), ("73430", "Aalen"),
    ("74072", "Heilbronn"), ("74523", "Schwaebisch-Hall"),
    ("75175", "Pforzheim"), ("76133", "Karlsruhe"),
    ("76646", "Bruchsal"), ("77652", "Offenburg"),
    ("78050", "Villingen"), ("78462", "Konstanz"),
    ("79098", "Freiburg"), ("79539", "Loerrach"),
    ("80331", "Muenchen-Mitte"), ("81369", "Muenchen-Sued"),
    ("81925", "Muenchen-Bogenhausen"), ("82041", "Furth"),
    ("82362", "Weilheim"), ("83022", "Rosenheim"),
    ("83512", "Wasserburg"), ("84028", "Landshut"),
    ("84489", "Burghausen"), ("85049", "Ingolstadt"),
    ("85368", "Moosburg"), ("86150", "Augsburg"),
    ("86720", "Noerdlingen"), ("87435", "Kempten"),
    ("88045", "Friedrichshafen"), ("89073", "Ulm"),
    ("89312", "Guenzburg"),
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
RADIUS_KM = 200
PAGE_LIMIT = 100
SLEEP_BETWEEN = 0.2
MAX_RETRIES = 2


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
                time.sleep(1.0)
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


# ---------------------------------------------------------------------------
# Seiten-Typologisierung: Stichproben-Crawl der Berater-Homepages
# ---------------------------------------------------------------------------

class SimpleHTMLAnalyzer(HTMLParser):
    """Leichtgewichtiger HTML-Parser ohne externe Abhaengigkeiten."""
    def __init__(self):
        super().__init__()
        self.title = ""
        self.meta_desc = ""
        self.meta_robots = ""
        self.canonical = ""
        self.h1_texts = []
        self.link_count = 0
        self.internal_links = 0
        self.external_links = 0
        self.has_schema_org = False
        self.has_contact_form = False
        self.has_calculator = False
        self.has_blog = False
        self.has_termin = False
        self.has_bewertungen = False
        self.has_team = False
        self.has_video = False
        self.has_faq = False
        self.has_google_maps = False
        self.img_count = 0
        self.product_keywords = []
        self._in_title = False
        self._in_h1 = False
        self._current_text = ""
        self._raw_html = ""

    def feed_full(self, html):
        self._raw_html = html.lower()
        self.has_schema_org = "schema.org" in self._raw_html
        self.has_contact_form = any(k in self._raw_html for k in
            ['type="submit"', "kontaktformular", "nachricht senden", "anfrage senden"])
        self.has_calculator = any(k in self._raw_html for k in
            ["jetzt berechnen", "beitrag berechnen", "tarifrechner", "onlinerechner"])
        self.has_blog = any(k in self._raw_html for k in
            ["/blog", "aktuelles", "neuigkeiten", "ratgeber"])
        self.has_termin = any(k in self._raw_html for k in
            ["termin vereinbaren", "terminvereinbarung", "beratungstermin",
             "jetzt termin", "callback", "rueckruf"])
        self.has_bewertungen = any(k in self._raw_html for k in
            ["bewertung", "kundenmeinung", "erfahrung", "rezension", "trustpilot",
             "provenexpert", "google-bewertung"])
        self.has_team = any(k in self._raw_html for k in
            ["unser team", "team vorstellen", "mitarbeiter", "ihre ansprechpartner"])
        self.has_video = any(k in self._raw_html for k in
            ["youtube.com/embed", "vimeo.com", "<video", "video-container"])
        self.has_faq = any(k in self._raw_html for k in
            ["faq", "haeufige fragen", "h\xc3\xa4ufige fragen", "fragen und antworten"])
        self.has_google_maps = any(k in self._raw_html for k in
            ["maps.google", "google.com/maps", "maps.googleapis"])
        prod_kw = {
            "zahnzusatz": ["zahnzusatz", "zahnversicherung"],
            "rechtsschutz": ["rechtsschutz"],
            "haftpflicht": ["haftpflicht", "privathaftpflicht"],
            "kfz": ["kfz-versicherung", "autoversicherung", "kfz versicherung"],
            "hausrat": ["hausrat"],
            "berufsunfaehigkeit": ["berufsunf", "bu-versicherung"],
            "sterbegeld": ["sterbegeld"],
            "risikoleben": ["risikoleben", "risiko-leben"],
            "pflege": ["pflegeversicherung", "pflege-"],
            "reise": ["reiseversicherung", "reisekranken"],
        }
        for prod, kws in prod_kw.items():
            if any(kw in self._raw_html for kw in kws):
                self.product_keywords.append(prod)
        try:
            self.feed(html)
        except Exception:
            pass

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "title":
            self._in_title = True
            self._current_text = ""
        elif tag == "h1":
            self._in_h1 = True
            self._current_text = ""
        elif tag == "meta":
            name = (d.get("name") or "").lower()
            if name == "description":
                self.meta_desc = d.get("content", "")
            elif name == "robots":
                self.meta_robots = d.get("content", "")
        elif tag == "link":
            if (d.get("rel") or "").lower() == "canonical":
                self.canonical = d.get("href", "")
        elif tag == "a":
            self.link_count += 1
            href = d.get("href", "")
            if href.startswith("http") and "ergo.de" not in href:
                self.external_links += 1
            else:
                self.internal_links += 1
        elif tag == "img":
            self.img_count += 1

    def handle_endtag(self, tag):
        if tag == "title" and self._in_title:
            self._in_title = False
            self.title = self._current_text.strip()
        elif tag == "h1" and self._in_h1:
            self._in_h1 = False
            self.h1_texts.append(self._current_text.strip())

    def handle_data(self, data):
        if self._in_title or self._in_h1:
            self._current_text += data


def classify_page_type(analysis):
    """Klassifiziert eine Berater-Seite in einen Typ."""
    features = []
    if analysis["has_team"]:
        features.append("agentur")
    if analysis["has_blog"]:
        features.append("blog")
    if analysis["has_bewertungen"]:
        features.append("bewertungen")
    if analysis["has_video"]:
        features.append("video")
    if analysis["has_faq"]:
        features.append("faq")
    if analysis["has_google_maps"]:
        features.append("maps")
    if analysis["has_termin"]:
        features.append("termin")
    if analysis["has_contact_form"]:
        features.append("kontakt")
    individual_score = len(features)
    prod_count = len(analysis.get("product_keywords", []))
    if individual_score >= 4:
        page_type = "individuell"
        desc = "Stark individualisiert"
    elif individual_score >= 2:
        page_type = "angepasst"
        desc = "Teilweise angepasst"
    elif prod_count >= 5:
        page_type = "produktkatalog"
        desc = "Reiner Produktkatalog"
    else:
        page_type = "minimal"
        desc = "Minimal/Standard-Template"
    return {
        "type": page_type,
        "type_label": desc,
        "individual_score": individual_score,
        "features": features,
    }


def crawl_homepage(homepage):
    """Crawlt eine Berater-Homepage und analysiert den Inhalt."""
    url = "https://%s" % homepage
    req = urllib.request.Request(url, headers={
        "User-Agent": HEADERS["User-Agent"],
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read(500000)
            ct = r.headers.get("Content-Type", "")
            enc = "utf-8"
            if "charset=" in ct:
                enc = ct.split("charset=")[-1].split(";")[0].strip()
            try:
                html = raw.decode(enc, errors="replace")
            except (LookupError, UnicodeDecodeError):
                html = raw.decode("utf-8", errors="replace")
        analyzer = SimpleHTMLAnalyzer()
        analyzer.feed_full(html)
        result = {
            "homepage": homepage,
            "status": "ok",
            "title": analyzer.title[:200],
            "meta_desc": analyzer.meta_desc[:300],
            "meta_robots": analyzer.meta_robots,
            "canonical": analyzer.canonical,
            "h1": analyzer.h1_texts[:3],
            "link_count": analyzer.link_count,
            "internal_links": analyzer.internal_links,
            "external_links": analyzer.external_links,
            "img_count": analyzer.img_count,
            "has_schema_org": analyzer.has_schema_org,
            "has_contact_form": analyzer.has_contact_form,
            "has_calculator": analyzer.has_calculator,
            "has_blog": analyzer.has_blog,
            "has_termin": analyzer.has_termin,
            "has_bewertungen": analyzer.has_bewertungen,
            "has_team": analyzer.has_team,
            "has_video": analyzer.has_video,
            "has_faq": analyzer.has_faq,
            "has_google_maps": analyzer.has_google_maps,
            "product_keywords": analyzer.product_keywords,
            "page_size_kb": round(len(raw) / 1024, 1),
        }
        classification = classify_page_type(result)
        result.update(classification)
        return result
    except urllib.error.HTTPError as e:
        return {"homepage": homepage, "status": "http_%d" % e.code, "type": "error"}
    except Exception as e:
        return {"homepage": homepage, "status": "error", "error": str(e)[:200], "type": "error"}


def run_typology(rows, sample_size=80):
    """Stichproben-Crawl und Typologisierung der Berater-Seiten."""
    with_hp = [r for r in rows if r["homepage"] and ".ergo.de" in r["homepage"]]
    if not with_hp:
        print("  Keine Berater mit ergo.de-Homepage gefunden")
        return None
    rd = [r for r in with_hp if r["homepage"].startswith("rd-")]
    dkv = [r for r in with_hp if "-dkv." in r["homepage"] or "dkv-" in r["homepage"]]
    std = [r for r in with_hp if r not in rd and r not in dkv]
    random.seed(42)
    sample = []
    for group, name, quota in [(rd, "rd", 15), (dkv, "dkv", 15), (std, "standard", 50)]:
        n = min(quota, len(group))
        sample.extend(random.sample(group, n))
    print("\n=== Seiten-Typologisierung: %d Seiten crawlen ===" % len(sample))
    print("  RD: %d, DKV: %d, Standard: %d" % (
        sum(1 for s in sample if s["homepage"].startswith("rd-")),
        sum(1 for s in sample if "-dkv." in s["homepage"] or "dkv-" in s["homepage"]),
        sum(1 for s in sample if not s["homepage"].startswith("rd-") and "-dkv." not in s["homepage"] and "dkv-" not in s["homepage"]),
    ))
    results = []
    for i, r in enumerate(sample):
        hp = r["homepage"]
        if not hp.startswith("http"):
            hp_full = hp if "." in hp else hp + ".ergo.de"
        else:
            hp_full = hp
        sys.stdout.write("  [%d/%d] %s ... " % (i + 1, len(sample), hp_full))
        sys.stdout.flush()
        res = crawl_homepage(hp_full)
        results.append(res)
        print(res.get("type", "?") + " (%s)" % res.get("status", "?"))
        time.sleep(0.5)
    ok = [r for r in results if r["status"] == "ok"]
    errors = [r for r in results if r["status"] != "ok"]
    type_counts = {}
    feature_counts = {}
    product_counts = {}
    seo_stats = {
        "with_meta_desc": 0, "with_schema_org": 0, "with_canonical": 0,
        "robots_index": 0, "robots_noindex": 0, "robots_unset": 0,
    }
    avg_links = 0
    avg_images = 0
    avg_page_size = 0
    for r in ok:
        t = r.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
        for f in r.get("features", []):
            feature_counts[f] = feature_counts.get(f, 0) + 1
        for p in r.get("product_keywords", []):
            product_counts[p] = product_counts.get(p, 0) + 1
        if r.get("meta_desc"):
            seo_stats["with_meta_desc"] += 1
        if r.get("has_schema_org"):
            seo_stats["with_schema_org"] += 1
        if r.get("canonical"):
            seo_stats["with_canonical"] += 1
        robots = (r.get("meta_robots") or "").lower()
        if "noindex" in robots:
            seo_stats["robots_noindex"] += 1
        elif robots:
            seo_stats["robots_index"] += 1
        else:
            seo_stats["robots_unset"] += 1
        avg_links += r.get("link_count", 0)
        avg_images += r.get("img_count", 0)
        avg_page_size += r.get("page_size_kb", 0)
    n_ok = max(len(ok), 1)
    typology = {
        "sample_size": len(sample),
        "crawled_ok": len(ok),
        "crawled_errors": len(errors),
        "type_distribution": dict(sorted(type_counts.items(), key=lambda kv: -kv[1])),
        "feature_frequency": dict(sorted(feature_counts.items(), key=lambda kv: -kv[1])),
        "product_keyword_frequency": dict(sorted(product_counts.items(), key=lambda kv: -kv[1])),
        "seo_stats": seo_stats,
        "avg_links": round(avg_links / n_ok, 1),
        "avg_images": round(avg_images / n_ok, 1),
        "avg_page_size_kb": round(avg_page_size / n_ok, 1),
        "individual_score_avg": round(sum(r.get("individual_score", 0) for r in ok) / n_ok, 2),
        "pages": [{
            "homepage": r["homepage"],
            "type": r.get("type", "?"),
            "type_label": r.get("type_label", "?"),
            "features": r.get("features", []),
            "product_keywords": r.get("product_keywords", []),
            "has_calculator": r.get("has_calculator", False),
            "meta_robots": r.get("meta_robots", ""),
            "individual_score": r.get("individual_score", 0),
            "page_size_kb": r.get("page_size_kb", 0),
        } for r in ok],
    }
    print("\n=== Typologisierung Ergebnis ===")
    print("  Gecrawlt: %d ok, %d Fehler" % (len(ok), len(errors)))
    print("  Typen: %s" % type_counts)
    print("  Features: %s" % feature_counts)
    print("  SEO: %s" % seo_stats)
    return typology


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
    out_path = out_dir / "berater_data.json"
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
    # Seiten-Typologisierung (kann mit SKIP_TYPOLOGY=1 uebersprungen werden)
    if os.environ.get("SKIP_TYPOLOGY") != "1":
        typology = run_typology(rows)
        if typology:
            agg["typology"] = typology

    # ── Event-Emission für Korrelations-Engine ───────────────────────────
    if HAS_EVENTS:
        print("\n--- Event-Emission ---")
        prev_data = load_previous_data(out_path)
        event_count = 0
        
        # Berater-Anzahl-Veränderung
        prev_total = prev_data.get("totals", {}).get("vermittler", 0)
        curr_total = t["vermittler"]
        if prev_total and abs(curr_total - prev_total) >= 5:
            emit_event(
                event_type="berater_shift",
                brand="ERGO",
                source="ergo_berater_api",
                crawler="update_berater",
                magnitude=min(abs(curr_total - prev_total) / 20, 2.0),
                detail={
                    "metric": "vermittler_count",
                    "old_value": prev_total,
                    "new_value": curr_total,
                    "delta": curr_total - prev_total,
                },
            )
            event_count += 1
        
        # Typologie-Shifts (wenn vorhanden)
        if "typology" in agg and "typology" in prev_data:
            curr_types = agg["typology"].get("type_distribution", {})
            prev_types = prev_data["typology"].get("type_distribution", {})
            for type_name in ["individuell", "angepasst", "produktkatalog", "minimal"]:
                curr_pct = curr_types.get(type_name, {}).get("percent", 0)
                prev_pct = prev_types.get(type_name, {}).get("percent", 0)
                if abs(curr_pct - prev_pct) > 2:  # >2% Shift
                    emit_event(
                        event_type="berater_shift",
                        brand="ERGO",
                        source="ergo_berater_api",
                        crawler="update_berater",
                        magnitude=min(abs(curr_pct - prev_pct) / 5, 2.0),
                        detail={
                            "metric": "type_distribution_" + type_name,
                            "old_pct": prev_pct,
                            "new_pct": curr_pct,
                            "delta_pct": round(curr_pct - prev_pct, 1),
                        },
                    )
                    event_count += 1
        
        # Daten für nächsten Vergleich sichern
        save_for_comparison(out_path)
        print("  %d Events emittiert" % event_count)

    payload = dict(agg)
    payload["vermittler"] = rows
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OK Geschrieben: %s (%d bytes)" % (out_path, out_path.stat().st_size))
    t = agg["totals"]
    print("   Total: %d Vermittler" % t["vermittler"])
    print("   Mit Subdomain: %d" % t["with_subdomain"])
    print("   Mit Foto: %d" % t["with_image"])
    print("   Mit Social: %d" % t["with_social"])
    # Patch dashboard_template.html
    template = out_dir / "dashboard_template.html"
    if template.exists():
        import re as _re
        html = template.read_text(encoding="utf-8")
        compact = dict(agg)
        sample_keys = ("firstname", "lastname", "zipcode", "city", "homepage", "image")
        compact["vermittler"] = [{k: v.get(k, "") for k in sample_keys} for v in rows[:50]]
        if "typology" in compact:
            typo_compact = dict(compact["typology"])
            typo_compact.pop("pages", None)
            compact["typology"] = typo_compact
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