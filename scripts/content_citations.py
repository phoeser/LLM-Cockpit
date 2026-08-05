"""
Content -> Zitate: welche konkreten URLs es in die Antworten der LLMs schaffen.

Erzeugt data/content_citations.json — eine Zeile je normalisierter URL plus einen
Aggregat-Block `kennzahlen` und einen `presse`-Block.

Frage, die der Datensatz beantwortet:
    Nicht "wirken Seitenaenderungen?", sondern "WELCHE Inhalte werden zitiert?"
    — URL-genau, mit Seitentyp, Zitatverlauf und Aenderungshistorie.

Datenquellen (alle lokal, KEIN Zugriff auf Peec-/LLM-APIs):
  1. data/peec_sources.json          Top-40 Domains + Top-150 URLs nach Zitaten,
                                     rollierendes 30-Tage-Fenster (Peec AI MCP-Export).
  2. data/peec_snapshots/*_sources.json  4 archivierte Staende -> Zitatverlauf je URL.
  3. shared/events.jsonl             page_new / page_change des GEO-Page-Trackers
                                     (URL, similarity, added_lines, classification).
  4. GEO data/page_dates.json        brand, first_seen, last_seen, published, modified,
                                     published_obergrenze (Sitemap-lastmod, ab 05.08.2026)
                                     je getrackter URL (Grundgesamtheit = Nenner).
  5. GEO data/runs/latest.json       eigener Crawl: `sources` je Antwort und Engine.
  6. data/press_data.json            Presseartikel je Marke (Medium-Name, kein Artikel-URL).

GEO-Dateien werden genauso bezogen wie in scripts/merge_geo_page_events.py:
zuerst der lokale Stand im Cockpit (data/page_dates.json, den merge_geo dorthin
schreibt), dann ein lokaler GEO-Checkout ($GEO_LOCAL_DIR / ../geo-visibility-tool /
/tmp/geo-visibility-tool), zuletzt die GitHub-Contents-API des GEO-Repos. Faellt alles
aus, laeuft das Skript trotzdem durch und meldet die betroffenen Kennzahlen als
available=false MIT Grund — nie als 0.

Projektregeln, die hier gelten:
  * Fehlende Daten sind {"available": false, "grund": ...}, niemals 0.
  * Jede Kennzahl traegt ein Feld `vorbehalt` mit ihrer Einschraenkung.
  * Der Erstsichtungs-Zeitstempel des Crawlers ist KEIN Publikationsdatum. Er wird
    nur als Proxy ausgewiesen (published_quelle="proxy_first_seen").
  * Der Sitemap-<lastmod> ist ebenfalls KEIN Publikationsdatum, sondern eine reine
    OBERGRENZE ("veroeffentlicht <= X"). Er steht nur in published_obergrenze,
    ersetzt `published` nie, und macht `tage_bis_erstes_zitat` zu einer unteren
    Schranke (tage_bis_erstes_zitat_art="untere_schranke"). Sein Nutzen ist der
    AUSSCHLUSS von Neuheit, nicht ihr Nachweis — kennzahlen.neuheit_ausschluss_je_marke.
  * Ko-Vorkommen (Seite wird zitiert, Marke wird genannt) ist kein Kausalnachweis.

Aufruf:  python3 scripts/content_citations.py   (aus dem Repo-Wurzelverzeichnis)
"""
import base64
import json
import os
import re
import sys
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

# ---------------------------------------------------------------------------
# Pfade / Konfiguration
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
PEEC_SOURCES = ROOT / "data" / "peec_sources.json"
PEEC_SNAP_DIR = ROOT / "data" / "peec_snapshots"
EVENTS_FILE = Path(os.environ.get("EVENTS_FILE", ROOT / "shared" / "events.jsonl"))
PRESS_FILE = ROOT / "data" / "press_data.json"
PRESS_HISTORY = ROOT / "data" / "press_history.json"
PAGE_DATES_FILE = ROOT / "data" / "page_dates.json"   # von merge_geo_page_events gepflegt
OUT_FILE = ROOT / "data" / "content_citations.json"

GEO_REPO = os.environ.get("GEO_REPO", "phoeser/geo-visibility-tool")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GEO_LOCAL_CANDIDATES = [
    os.environ.get("GEO_LOCAL_DIR"),
    str(ROOT.parent / "geo-visibility-tool"),
    "/tmp/geo-visibility-tool",
]

# Eigene Domains (ERGO-Konzern). Bewusst explizit, nicht geraten.
OWN_DOMAINS = {
    "ergo.de", "ergo.com", "ergodirekt.de", "ergo-reiseversicherung.de",
    "dkv.de", "dkv.com", "ergo-run.de",
}
OWN_BRANDS = {"ERGO", "DKV", "ERGO Direkt"}

# Engine-Belastbarkeit des eigenen Crawls (verifiziert 08/2026):
#   perplexity  -> echte Quell-URLs, URL-genau auswertbar
#   gemini      -> fast nur vertexaisearch-Redirects, Ziel-URL nicht aufloesbar
#   chatgpt     -> laeuft ohne Websuche; "sources" sind im Fliesstext genannte URLs
ENGINE_BELASTBAR = {"perplexity": True, "gemini": False, "chatgpt": False}
ENGINE_GRUND = {
    "perplexity": "Liefert echte Quell-URLs je Antwort — URL-genau auswertbar.",
    "gemini": ("Liefert fast ausschliesslich vertexaisearch.cloud.google.com-Redirects; "
               "die Ziel-URL ist ohne Aufloesen der Weiterleitung nicht bekannt."),
    "chatgpt": ("Laeuft im Crawl ohne Websuche — die 'sources' sind lediglich im "
                "Antworttext genannte URLs, keine abgerufenen Quellen."),
}

# Peec-Seitentyp (englisch) -> einheitliches deutsches Label
PEEC_CLS_MAP = {
    "Product Page": "Produktseite",
    "Category Page": "Kategorieseite",
    "Comparison": "Vergleich/Test",
    "Article": "Artikel",
    "Listicle": "Liste",
    "Homepage": "Homepage",
    "Profile": "Profil",
    "Guide": "Ratgeber",
    "Review": "Bewertung",
    "Forum": "Forum",
    "Video": "Video",
}

# Pfad-Regelwerk fuer den Seitentyp, wenn Peec keine Klassifikation liefert.
# Reihenfolge = Prioritaet. Erster Treffer gewinnt. Kein Treffer -> null (nie raten).
PFADREGELN = [
    (r"/(presse|newsroom|press|media-?center)(/|$)", "Presse"),
    (r"/(ueber-uns|ueber_uns|about|unternehmen|karriere|jobs|investor)(/|$)", "Unternehmensseite"),
    (r"/(ratgeber|guide|wissen|lexikon|tipps)(/|$)", "Ratgeber"),
    (r"/(magazin|blog|news|aktuelles)(/|$)", "Redaktion/Blog"),
    (r"/(service|kontakt|hilfe|faq|schaden|kundenportal|login)(/|$)", "Service"),
    (r"/(vergleich|test|testsieger|rechner|tarifrechner)(/|$)", "Vergleich/Test"),
    (r"/(produkte|produkt|versicherungen|versicherung)(/|$)", "Produktseite"),
    (r"-versicherung(/|$)", "Produktseite"),
    (r"versicherung$", "Produktseite"),
]

VORBEHALT_PEEC = ("Peec liefert nur die Top-150-URLs nach Zitaten im rollierenden "
                  "30-Tage-Fenster — der Long Tail fehlt, seltener zitierte Seiten "
                  "erscheinen als 'nicht zitiert'.")
VORBEHALT_KOVOR = ("Zitat einer URL und Nennung einer Marke in derselben Antwort sind "
                   "ein Ko-Vorkommen, kein Kausalnachweis.")
VORBEHALT_NENNER = ("Nenner ist die vom GEO-Crawl getrackte Seitenmenge (Sitemap-Auswahl "
                    "je Marke), nicht die vollstaendige Website.")


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------
def norm_url(raw):
    """Host klein, www. weg, Trailing Slash weg, Fragment weg.
    Query bleibt erhalten (unterscheidet echte Seiten). Peec-URLs sind bereits so
    normalisiert; page_dates/Events/Crawl-Quellen nicht."""
    if not raw:
        return None
    try:
        s = urlsplit(str(raw).strip())
    except Exception:
        return None
    host = (s.netloc or "").lower().split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return None
    path = (s.path or "").rstrip("/")
    return host + path + (("?" + s.query) if s.query else "")


def join_key(url_norm):
    """Join-Schluessel: zusaetzlich Pfad kleingeschrieben. Peec schreibt
    ergo.de/de/Produkte/..., der Crawl ergo.de/de/produkte/... — ohne diese Stufe
    faellt jeder ERGO-Treffer aus dem Join."""
    return url_norm.lower() if url_norm else None


def host_of(url_norm):
    return url_norm.split("/", 1)[0] if url_norm else None


def ts_date(ts):
    """ISO-Zeitstempel (auch 2026-08-04T00-16-03Z) -> 'YYYY-MM-DD'."""
    if not ts:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(ts))
    return "%s-%s-%s" % m.groups() if m else None


def days_between(d1, d2):
    """d2 - d1 in Tagen (beide 'YYYY-MM-DD'); None wenn nicht parsebar."""
    try:
        a = datetime.strptime(d1, "%Y-%m-%d")
        b = datetime.strptime(d2, "%Y-%m-%d")
    except Exception:
        return None
    return (b - a).days


def median(vals):
    v = sorted(x for x in vals if x is not None)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else round((v[n // 2 - 1] + v[n // 2]) / 2, 1)


def seitentyp_aus_pfad(url_norm):
    """Dokumentiertes Pfad-Regelwerk. Kein Treffer -> None (nie raten)."""
    if not url_norm:
        return None
    path = url_norm.split("/", 1)[1] if "/" in url_norm else ""
    if not path:
        return "Homepage"
    p = "/" + path.lower()
    for pat, label in PFADREGELN:
        if re.search(pat, p):
            return label
    return None


# ---------------------------------------------------------------------------
# GEO-Dateizugriff — gleiche Reihenfolge wie merge_geo_page_events.py
# ---------------------------------------------------------------------------
def _gh_contents(path):
    """GEO-Datei ueber die GitHub-Contents-API (wie merge_geo_page_events.fetch_page_dates).
    Wirft bei jedem Fehler — der Aufrufer faengt ab und meldet available=false."""
    url = "https://api.github.com/repos/%s/contents/%s?ref=main" % (GEO_REPO, path)
    headers = {"Accept": "application/vnd.github.v3+json",
               "User-Agent": "llm-cockpit-content-citations"}
    if GITHUB_TOKEN:
        headers["Authorization"] = "Bearer " + GITHUB_TOKEN
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        meta = json.loads(r.read().decode("utf-8"))
    if meta.get("content"):
        return json.loads(base64.b64decode(meta["content"]).decode("utf-8"))
    dl = meta.get("download_url")
    if not dl:
        raise RuntimeError("Contents-API ohne content/download_url")
    with urllib.request.urlopen(urllib.request.Request(dl, headers=headers), timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def load_geo(rel_path, local_cache=None):
    """(daten, quellenbeschreibung, fehlergrund) — nie eine Exception nach aussen."""
    if local_cache and Path(local_cache).exists():
        try:
            return (json.loads(Path(local_cache).read_text(encoding="utf-8")),
                    "lokaler Cockpit-Stand %s" % Path(local_cache).relative_to(ROOT), None)
        except Exception as ex:
            pass
    for cand in GEO_LOCAL_CANDIDATES:
        if not cand:
            continue
        p = Path(cand) / rel_path
        if p.exists():
            try:
                return (json.loads(p.read_text(encoding="utf-8")),
                        "lokaler GEO-Checkout %s" % p, None)
            except Exception as ex:
                return (None, None, "GEO-Datei %s nicht lesbar: %s" % (p, str(ex)[:120]))
    try:
        return (_gh_contents(rel_path), "GitHub-Contents-API %s/%s" % (GEO_REPO, rel_path), None)
    except Exception as ex:
        return (None, None, ("GEO-Datei %s weder lokal (data/, $GEO_LOCAL_DIR, "
                             "../geo-visibility-tool) noch ueber die GitHub-API "
                             "erreichbar: %s" % (rel_path, str(ex)[:120])))


# ---------------------------------------------------------------------------
# Einlesen
# ---------------------------------------------------------------------------
def load_peec():
    if not PEEC_SOURCES.exists():
        return None, "data/peec_sources.json fehlt — Export scripts/export_peec_sources.py nie gelaufen."
    try:
        return json.loads(PEEC_SOURCES.read_text(encoding="utf-8")), None
    except Exception as ex:
        return None, "data/peec_sources.json nicht lesbar: %s" % str(ex)[:120]


def load_peec_snapshots():
    """[(datum, {join_key: {cit, ret, cls, title, brands}})] chronologisch."""
    out = []
    if not PEEC_SNAP_DIR.exists():
        return out
    for p in sorted(PEEC_SNAP_DIR.glob("*_sources.json")):
        datum = p.name.split("_")[0]
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        idx = {}
        for u in d.get("urls", []):
            k = join_key(norm_url(u.get("url")))
            if k:
                idx[k] = u
        out.append((datum, idx))
    return out


def load_events():
    """join_key -> Aggregat der page_new/page_change-Events."""
    agg = {}
    if not EVENTS_FILE.exists():
        return agg, "shared/events.jsonl fehlt."
    with open(EVENTS_FILE, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or '"page_' not in line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            et = e.get("event_type")
            if et not in ("page_new", "page_change"):
                continue
            det = e.get("detail") or {}
            url = e.get("url") or det.get("url")
            k = join_key(norm_url(url))
            if not k:
                continue
            a = agg.setdefault(k, {"url_raw": url, "brand": e.get("brand"),
                                   "first_ts": None, "first_new_ts": None,
                                   "n_changes": 0, "added": 0, "removed": 0,
                                   "last_sim": None, "last_change_ts": None,
                                   "types": Counter()})
            ts = e.get("timestamp")
            if ts and (a["first_ts"] is None or ts < a["first_ts"]):
                a["first_ts"] = ts
            if et == "page_new":
                if ts and (a["first_new_ts"] is None or ts < a["first_new_ts"]):
                    a["first_new_ts"] = ts
            else:
                a["n_changes"] += 1
                a["added"] += int(det.get("added_lines") or 0)
                a["removed"] += int(det.get("removed_lines") or 0)
                if ts and (a["last_change_ts"] is None or ts > a["last_change_ts"]):
                    a["last_change_ts"] = ts
                    if det.get("similarity") is not None:
                        a["last_sim"] = det.get("similarity")
                cls = det.get("classification")
                if isinstance(cls, dict) and cls.get("type"):
                    a["types"][cls["type"]] += 1
                elif isinstance(cls, str) and cls:
                    a["types"][cls] += 1
    return agg, None


def load_own_crawl():
    """(engine -> {join_key: n}, meta) aus GEO data/runs/latest.json."""
    data, quelle, grund = load_geo("data/runs/latest.json")
    if data is None:
        return None, {"available": False, "grund": grund}
    per = defaultdict(Counter)
    raw_counts = Counter()
    for _pid, prod in (data.get("products") or {}).items():
        for pl in prod.get("per_llm", []) or []:
            eng = (pl.get("llm") or "unbekannt").lower()
            for res in pl.get("results", []) or []:
                for src in (res.get("sources") or []):
                    n = norm_url(src.get("url"))
                    if not n:
                        continue
                    raw_counts[eng] += 1
                    per[eng][join_key(n)] += 1
    meta = {"available": True, "quelle": quelle, "run_id": data.get("run_id"),
            "finished_at": data.get("finished_at"),
            "roh_quellen_je_engine": dict(raw_counts),
            "distinkte_urls_je_engine": {e: len(c) for e, c in per.items()}}
    return per, meta


# ---------------------------------------------------------------------------
# Aufbau der Zeilen
# ---------------------------------------------------------------------------
def build():
    erzeugt = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    peec, peec_err = load_peec()
    snaps = load_peec_snapshots()
    events, ev_err = load_events()
    page_dates, pd_quelle, pd_err = load_geo("data/page_dates.json", local_cache=PAGE_DATES_FILE)
    own_per_engine, own_meta = load_own_crawl()

    # -- Peec-Index -------------------------------------------------------
    peec_urls = {}
    peec_domains = {}
    if peec:
        for u in peec.get("urls", []):
            k = join_key(norm_url(u.get("url")))
            if k:
                peec_urls[k] = u
        for d in peec.get("domains", []):
            dom = (d.get("domain") or "").lower().replace("www.", "")
            if dom:
                peec_domains[dom] = d
    peec_as_of = (peec or {}).get("as_of")
    peec_window = (peec or {}).get("window") or {}

    # -- page_dates-Index -------------------------------------------------
    pd_idx = {}
    brand_getrackt = Counter()
    domain_brand = {}
    if isinstance(page_dates, dict):
        for raw, v in page_dates.items():
            n = norm_url(raw)
            k = join_key(n)
            if not k:
                continue
            pd_idx[k] = {"raw": raw, "norm": n, **(v if isinstance(v, dict) else {})}
            b = (v or {}).get("brand")
            if b:
                brand_getrackt[b] += 1
                domain_brand.setdefault(host_of(n), Counter())[b] += 1
    domain_brand = {d: c.most_common(1)[0][0] for d, c in domain_brand.items()}

    snap_dates = [d for d, _ in snaps]
    erster_snapshot = snap_dates[0] if snap_dates else None

    # -- Zeilen-Universum -------------------------------------------------
    # Bewusst NICHT alle 6.487 getrackten Seiten: Zeilen bekommen URLs, die
    # (a) im Peec-Top-150 stehen, (b) im eigenen Crawl als Quelle auftauchen UND
    # zu einer getrackten Seite gehoeren, oder (c) eigene (ERGO/DKV-)Seiten sind.
    # Reine Wettbewerber-Seiten ohne Zitat zaehlen nur in den Kennzahlen mit.
    keys = set(peec_urls)
    for k, v in pd_idx.items():
        if host_of(v["norm"]) in OWN_DOMAINS or v.get("brand") in OWN_BRANDS:
            keys.add(k)
    if own_per_engine:
        for eng, cnt in own_per_engine.items():
            if not ENGINE_BELASTBAR.get(eng):
                continue
            for k in cnt:
                if k in pd_idx or host_of(k) in OWN_DOMAINS:
                    keys.add(k)

    rows = []
    for k in sorted(keys):
        pu = peec_urls.get(k)
        pdv = pd_idx.get(k)
        ev = events.get(k)

        url_norm = (norm_url(pu["url"]) if pu else None) or (pdv or {}).get("norm") or k
        url_raw = (pu or {}).get("url") or (pdv or {}).get("raw") or (ev or {}).get("url_raw") or url_norm
        host = host_of(url_norm)

        brand = (pdv or {}).get("brand") or (ev or {}).get("brand") or domain_brand.get(host)
        ist_eigen = host in OWN_DOMAINS or (brand in OWN_BRANDS if brand else False)

        # Seitentyp
        if pu and pu.get("cls"):
            styp = PEEC_CLS_MAP.get(pu["cls"], pu["cls"])
            styp_q = "peec"
            styp_roh = pu["cls"]
        else:
            styp = seitentyp_aus_pfad(url_norm)
            styp_q = "pfadregel" if styp else None
            styp_roh = None

        # Publikationsdatum
        published, published_q = None, None
        if pdv and pdv.get("published"):
            published, published_q = ts_date(pdv["published"]), "schema"
        else:
            proxy = (ev or {}).get("first_new_ts") or (ev or {}).get("first_ts") \
                or (pdv or {}).get("first_seen")
            if proxy:
                published, published_q = ts_date(proxy), "proxy_first_seen"

        # Obergrenze aus dem Sitemap-<lastmod> (GEO ab 05.08.2026). STRIKT eine
        # Obergrenze: "veroeffentlicht <= X". Sie ersetzt `published` NIE und wird
        # nie als Publikationstag ausgegeben — die Seite kann beliebig aelter sein.
        # Der GEO-Crawl setzt sie nur, wo `published` fehlt und der lastmod kein
        # Massenstempel (CMS-/Deploy-Zeitstempel) ist.
        obergrenze, obergrenze_q = None, None
        if pdv and pdv.get("published_obergrenze") and not (pdv or {}).get("published"):
            obergrenze = ts_date(pdv["published_obergrenze"])
            obergrenze_q = pdv.get("published_obergrenze_quelle") or "sitemap_lastmod"

        # Zitatverlauf aus den Snapshots. Fehlt die URL in einem Stand, ist ihre
        # Zitatzahl UNBEKANNT (sie lag unter der Top-150-Kappung) — der Stand wird
        # dann weggelassen, nicht als 0 gefuehrt.
        verlauf = {}
        erstes_zitat_datum = None
        for datum, idx in snaps:
            e = idx.get(k)
            if not e:
                continue
            cit = int(e.get("cit") or 0)
            verlauf[datum] = cit
            if cit > 0 and erstes_zitat_datum is None:
                erstes_zitat_datum = datum

        own_eng = {}
        if own_per_engine:
            for eng, cnt in own_per_engine.items():
                if cnt.get(k):
                    own_eng[eng] = cnt[k]
        own_pplx = own_eng.get("perplexity")

        zitiert = bool(pu) or bool(erstes_zitat_datum) or bool(own_pplx)

        # Tage bis erstes Zitat.
        #   * echtes schema.org-Datum  -> Punktschaetzung
        #   * Sitemap-Obergrenze       -> UNTERE SCHRANKE (published <= Obergrenze,
        #                                 also ist die echte Spanne >= dem Wert)
        #   * Erstsichtungs-Proxy      -> ebenfalls UNTERE SCHRANKE (published <=
        #                                 Erstsichtung), und nur belegbar, wenn der
        #                                 Proxy vor dem ersten Snapshot liegt.
        tage, tage_grund, tage_art, tage_basis = None, None, None, None
        if not erstes_zitat_datum:
            tage_grund = "kein_zitat_in_snapshots"
        elif published_q == "schema":
            tage = days_between(published, erstes_zitat_datum)
            tage_art, tage_basis = "punktschaetzung", "schema"
        else:
            # Beide Ersatzquellen sind Obergrenzen des Publikationstags: die Seite
            # existierte am lastmod-Tag und ebenso bei unserer Erstsichtung. Die
            # FRUEHERE der beiden ist die schaerfere Schranke und liefert die
            # groessere (also aussagekraeftigere) Untergrenze fuer die Spanne.
            schranken = []
            if obergrenze:
                schranken.append((obergrenze, obergrenze_q))
            if (published and published_q == "proxy_first_seen"
                    and erster_snapshot and published < erster_snapshot):
                schranken.append((published, "proxy_first_seen"))
            if not schranken:
                tage_grund = ("kein_datum" if not (published or obergrenze)
                              else "proxy_nicht_vor_erstem_snapshot")
            else:
                schranken.sort(key=lambda x: (x[0], x[1] != "sitemap_lastmod"))
                basis, basis_q = schranken[0]
                _t = days_between(basis, erstes_zitat_datum)
                if _t is not None and _t >= 0:
                    tage, tage_art, tage_basis = _t, "untere_schranke", basis_q
                else:
                    # Schranke liegt NACH dem ersten Zitat -> die Untergrenze waere
                    # negativ und damit inhaltsleer. Kein Wert statt Scheinpraezision.
                    tage_grund = "schranke_nach_erstem_zitat"
        zensiert = bool(erstes_zitat_datum and erster_snapshot
                        and erstes_zitat_datum == erster_snapshot)

        row = {
            "url_norm": url_norm,
            "url_raw": url_raw,
            "brand": brand,
            "seitentyp": styp,
            "quelle_seitentyp": styp_q,
            "seitentyp_roh": styp_roh,
            "first_event_ts": (ev or {}).get("first_ts"),
            "n_changes": (ev or {}).get("n_changes", 0) if ev else 0,
            "sum_added_lines": (ev or {}).get("added", 0) if ev else 0,
            "last_similarity": (ev or {}).get("last_sim"),
            "last_change_ts": (ev or {}).get("last_change_ts"),
            "change_types": sorted((ev or {}).get("types", {}).keys()) if ev else [],
            "published": published,
            "published_quelle": published_q,
            "published_obergrenze": obergrenze,
            "published_obergrenze_quelle": obergrenze_q,
            "peec_cit": (pu or {}).get("cit"),
            "peec_ret": (pu or {}).get("ret"),
            "peec_cls": (pu or {}).get("cls"),
            "peec_title": (pu or {}).get("title"),
            "peec_brands": (pu or {}).get("brands") or [],
            "peec_cit_verlauf": verlauf,
            "own_cit_perplexity": own_pplx,
            "own_cit_engines": own_eng,
            "ist_eigene_seite": ist_eigen,
            "ist_getrackt": bool(pdv),
            "zitiert": zitiert,
            "tage_bis_erstes_zitat": tage,
            "tage_bis_erstes_zitat_art": tage_art,
            "tage_bis_erstes_zitat_basis": tage_basis,
            "erstes_zitat_snapshot": erstes_zitat_datum,
            "zitat_linkszensiert": zensiert,
        }
        if tage is None:
            row["tage_bis_erstes_zitat_grund"] = tage_grund
        # Platz sparen: rein optionale Zusatzfelder ohne Inhalt weglassen.
        # Die Pflichtfelder der Auswertung bleiben IMMER stehen (auch als null),
        # damit fehlende Werte sichtbar sind und nicht mit 0 verwechselt werden.
        for opt in ("seitentyp_roh", "last_change_ts", "peec_title", "erstes_zitat_snapshot",
                    "published_obergrenze", "published_obergrenze_quelle",
                    "tage_bis_erstes_zitat_art", "tage_bis_erstes_zitat_basis"):
            if row.get(opt) is None:
                row.pop(opt, None)
        if not row["zitat_linkszensiert"]:
            row.pop("zitat_linkszensiert")
        rows.append(row)

    rows.sort(key=lambda r: (-(r["peec_cit"] or 0), -(r["own_cit_perplexity"] or 0),
                             r["url_norm"]))

    kennzahlen = build_kennzahlen(rows, peec, peec_urls, pd_idx, brand_getrackt,
                                  snaps, own_per_engine, own_meta, domain_brand)
    presse = build_presse(peec, peec_domains, peec_urls, snaps)

    meta = {
        "erzeugt_am": erzeugt,
        "script": "scripts/content_citations.py",
        "frage": ("Welche konkreten Inhalte (URLs) schaffen es in die Zitate der LLMs — "
                  "mit Seitentyp, Zitatverlauf und Aenderungshistorie."),
        "quellen": {
            "peec_sources": {"available": peec is not None,
                             "as_of": peec_as_of, "fenster": peec_window,
                             "grund": peec_err},
            "peec_snapshots": {"available": bool(snaps), "staende": snap_dates,
                               "grund": None if snaps else "Keine data/peec_snapshots/*_sources.json gefunden."},
            "events": {"available": not ev_err, "urls": len(events), "grund": ev_err},
            "page_dates": {"available": bool(pd_idx), "quelle": pd_quelle,
                           "urls": len(pd_idx), "grund": pd_err},
            "eigener_crawl": own_meta,
        },
        "normalisierung": ("Host klein + 'www.' entfernt + Trailing Slash entfernt + Fragment "
                           "entfernt; Join zusaetzlich case-insensitiv im Pfad (Peec schreibt "
                           "/de/Produkte/, der Crawl /de/produkte/). Query bleibt erhalten."),
        "zeilen_auswahl": ("Zeilen bekommen URLs, die im Peec-Top-150 stehen, im eigenen "
                           "Crawl als belastbare Quelle auftauchen oder zu einer eigenen "
                           "(ERGO/DKV-)Domain gehoeren. Getrackte Wettbewerber-Seiten ohne "
                           "Zitat gehen nur in die Kennzahlen ein, nicht in die Zeilen."),
        "seitentyp_regeln": {
            "peec": "Peec-Klassifikation (Heuristik des Anbieters), auf deutsche Labels gemappt.",
            "pfadregel": [{"muster": p, "typ": t} for p, t in PFADREGELN],
            "kein_treffer": "seitentyp = null, quelle_seitentyp = null — es wird nicht geraten.",
        },
        "published_quellen": {
            "schema": "schema.org/OpenGraph-Datum aus dem Roh-HTML (GEO data/page_dates.json).",
            "proxy_first_seen": ("PROXY: erster page_new-/Crawl-Zeitstempel. Das ist der Tag "
                                 "unserer Erstsichtung, NICHT der Publikationstag."),
            "sitemap_lastmod": ("OBERGRENZE, kein Publikationsdatum: aus dem Sitemap-<lastmod> "
                                "folgt nur 'veroeffentlicht <= X'; die Seite kann beliebig "
                                "aelter sein. Steht ausschliesslich im Feld "
                                "published_obergrenze, nie in `published`. Der GEO-Crawl setzt "
                                "sie nur, wo kein schema.org-Datum vorliegt und der lastmod "
                                "kein Massenstempel (CMS-/Deploy-Zeitstempel) ist."),
        },
        "published_obergrenze_lesart": ("published_obergrenze ist eine SCHRANKE, kein Datum: "
                                        "die Seite wurde spaetestens an diesem Tag "
                                        "veroeffentlicht. Damit laesst sich Neuheit "
                                        "AUSSCHLIESSEN (Obergrenze alt => Seite sicher nicht "
                                        "neu), aber nie belegen (Obergrenze jung => nur "
                                        "Kandidat). Siehe kennzahlen.neuheit_ausschluss_je_marke."),
        "engines": {e: {"belastbar": b, "grund": ENGINE_GRUND[e]} for e, b in ENGINE_BELASTBAR.items()},
        "peec_cit_verlauf_lesart": ("Nur Staende, in denen die URL im Top-150 stand. Ein "
                                    "fehlender Stand heisst 'unter der Kappung, Zitatzahl "
                                    "unbekannt' — NICHT 0."),
        "grund_codes": {
            "kein_zitat_in_snapshots": "URL stand in keinem archivierten Peec-Stand im Top-150.",
            "kein_datum": "Weder schema.org-Publikationsdatum noch Erstsichtungs-Proxy vorhanden.",
            "proxy_nicht_vor_erstem_snapshot": ("Nur Erstsichtungs-Proxy, der nicht vor dem "
                                                "ersten Snapshot liegt — die Reihenfolge "
                                                "Publikation -> Zitat ist nicht belegbar."),
            "schranke_nach_erstem_zitat": ("Nur eine Obergrenze (Sitemap-lastmod/Erstsichtung), "
                                           "die NACH dem ersten beobachteten Zitat liegt — die "
                                           "untere Schranke waere negativ und inhaltsleer."),
        },
        "tage_bis_erstes_zitat_arten": {
            "punktschaetzung": ("Start ist das echte schema.org-Publikationsdatum — der Wert "
                                "schaetzt die Spanne direkt."),
            "untere_schranke": ("Start ist eine Obergrenze des Publikationstags (Sitemap-"
                                "lastmod oder unsere Erstsichtung). Weil die Seite hoechstens "
                                "an diesem Tag veroeffentlicht wurde, ist die ECHTE Spanne "
                                ">= dem ausgewiesenen Wert. Nicht mit Punktschaetzungen "
                                "mitteln."),
        },
        "optionale_felder": ("seitentyp_roh, last_change_ts, peec_title, erstes_zitat_snapshot, "
                             "zitat_linkszensiert, published_obergrenze, "
                             "published_obergrenze_quelle, tage_bis_erstes_zitat_art und "
                             "tage_bis_erstes_zitat_basis fehlen in einer Zeile, wenn sie "
                             "leer sind."),
        "n_zeilen": len(rows),
    }

    return {"meta": meta, "kennzahlen": kennzahlen, "presse": presse, "seiten": rows}


# ---------------------------------------------------------------------------
# Kennzahlen
# ---------------------------------------------------------------------------
NEU_ALT_TAGE = 90     # Obergrenze aelter als das => Seite ist SICHER nicht neu
NEU_JUNG_TAGE = 30    # Obergrenze juenger als das => Neuheits-KANDIDAT


def build_neuheit_ausschluss(pd_idx, stichtag=None):
    """Neuheit ausschliessen — der eigentliche Nutzen der Sitemap-Obergrenze.

    Die Obergrenze sagt 'veroeffentlicht <= X'. Damit laesst sich Neuheit nicht
    BELEGEN, aber sauber AUSSCHLIESSEN: liegt X mehr als 90 Tage zurueck, ist die
    Seite sicher nicht neu — unabhaengig davon, wie viel aelter sie tatsaechlich
    ist. Umgekehrt macht ein junges X eine Seite nur zum Kandidaten.

    Deshalb sind die beiden Spalten bewusst NICHT symmetrisch:
      sicher_nicht_neu  = harte Aussage (Ausschluss)
      kandidat_neu_30d  = weiche Aussage (Verdacht, nicht belegt)
    """
    if not pd_idx:
        return {"available": False,
                "grund": "Keine page_dates.json — ohne getrackte Seiten kein Nenner.",
                "vorbehalt": VORBEHALT_NENNER}
    stichtag = stichtag or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    je_marke = {}
    for v in pd_idx.values():
        b = v.get("brand") or "Unbekannt"
        s = je_marke.setdefault(b, {
            "brand": b, "seiten": 0,
            "sicher_nicht_neu": 0, "davon_aus_publikationsdatum": 0,
            "davon_aus_obergrenze": 0,
            "kandidat_neu_30d": 0, "davon_sicher_neu": 0, "davon_nur_kandidat": 0,
            "ohne_datumsschranke": 0})
        s["seiten"] += 1
        pub = ts_date(v.get("published"))
        obg = ts_date(v.get("published_obergrenze")) if not v.get("published") else None
        schranke = pub or obg          # in beiden Faellen gilt: published <= schranke
        if not schranke:
            s["ohne_datumsschranke"] += 1
            continue
        alter = days_between(schranke, stichtag)
        if alter is None:
            s["ohne_datumsschranke"] += 1
            continue
        if alter > NEU_ALT_TAGE:
            s["sicher_nicht_neu"] += 1
            if pub:
                s["davon_aus_publikationsdatum"] += 1
            else:
                s["davon_aus_obergrenze"] += 1
        elif alter <= NEU_JUNG_TAGE:
            s["kandidat_neu_30d"] += 1
            if pub:
                s["davon_sicher_neu"] += 1
            else:
                s["davon_nur_kandidat"] += 1
    for s in je_marke.values():
        s["sicher_nicht_neu_pct"] = (round(100.0 * s["sicher_nicht_neu"] / s["seiten"], 1)
                                     if s["seiten"] else None)
        s["entscheidbar_pct"] = (round(100.0 * (s["seiten"] - s["ohne_datumsschranke"])
                                       / s["seiten"], 1) if s["seiten"] else None)
    marken = sorted(je_marke.values(), key=lambda s: -s["seiten"])
    ges = sum(s["seiten"] for s in marken)
    ohne = sum(s["ohne_datumsschranke"] for s in marken)
    return {
        "available": True,
        "stichtag": stichtag,
        "marken": marken,
        "gesamt": {"seiten": ges, "mit_datumsschranke": ges - ohne,
                   "ohne_datumsschranke": ohne,
                   "mit_datumsschranke_pct": round(100.0 * (ges - ohne) / ges, 1) if ges else None,
                   "sicher_nicht_neu": sum(s["sicher_nicht_neu"] for s in marken),
                   "kandidat_neu_30d": sum(s["kandidat_neu_30d"] for s in marken)},
        "definition": ("Datumsschranke = echtes Publikationsdatum ODER Sitemap-Obergrenze "
                       "('veroeffentlicht <= X'). sicher_nicht_neu = Schranke aelter als %d "
                       "Tage; das ist eine HARTE Aussage, denn aelter als die Schranke kann die "
                       "Seite nur werden, nicht juenger. kandidat_neu_30d = Schranke juenger als "
                       "%d Tage; nur wo sie aus einem echten Publikationsdatum stammt "
                       "(davon_sicher_neu), ist die Seite belegbar neu — bei einer Obergrenze "
                       "(davon_nur_kandidat) kann sie beliebig aelter sein. Seiten mit Schranke "
                       "zwischen %d und %d Tagen sind in keiner der beiden Spalten."
                       % (NEU_ALT_TAGE, NEU_JUNG_TAGE, NEU_JUNG_TAGE, NEU_ALT_TAGE)),
        "vorbehalt": ("Die Obergrenze stammt aus dem Sitemap-<lastmod> und wird vom GEO-Crawl "
                      "nur gesetzt, wo kein Publikationsdatum vorliegt und der lastmod kein "
                      "Massenstempel ist — bei Marken ohne Sitemap-lastmod (oder mit "
                      "Massenstempel) bleibt die Zeile unentscheidbar. " + VORBEHALT_NENNER),
    }


def build_kennzahlen(rows, peec, peec_urls, pd_idx, brand_getrackt, snaps,
                     own_per_engine, own_meta, domain_brand):
    k = {}
    snap_dates = [d for d, _ in snaps]

    # 1. Zitat-Trefferquote je Marke ---------------------------------------
    if not brand_getrackt:
        k["trefferquote_je_marke"] = {
            "available": False,
            "grund": "Keine page_dates.json — ohne getrackte Grundgesamtheit gibt es keinen Nenner.",
            "vorbehalt": VORBEHALT_NENNER}
    else:
        zitiert_je_marke = Counter()
        for r in rows:
            if r["zitiert"] and r["ist_getrackt"] and r["brand"]:
                zitiert_je_marke[r["brand"]] += 1
        marken = []
        for b, getrackt in brand_getrackt.most_common():
            z = zitiert_je_marke.get(b, 0)
            marken.append({"brand": b, "getrackt": getrackt, "zitiert": z,
                           "quote_pct": round(100.0 * z / getrackt, 2) if getrackt else None,
                           "eigen": b in OWN_BRANDS})
        k["trefferquote_je_marke"] = {
            "available": True, "marken": marken,
            "definition": ("zitiert = URL steht im Peec-Top-150 und/oder wurde im eigenen "
                           "Perplexity-Crawl als Quelle gefuehrt; getrackt = Seiten der Marke "
                           "in data/page_dates.json."),
            "vorbehalt": VORBEHALT_PEEC + " " + VORBEHALT_NENNER +
                         " Die Quote ist deshalb eine Untergrenze, kein Anteil an allen Zitaten."}

    # 2. Zitatanteil je Seitentyp -----------------------------------------
    if not peec_urls:
        k["zitatanteil_je_seitentyp"] = {"available": False,
                                         "grund": "Keine Peec-URL-Daten.",
                                         "vorbehalt": VORBEHALT_PEEC}
    else:
        typ_cit = Counter()
        typ_n = Counter()
        for u in peec_urls.values():
            t = PEEC_CLS_MAP.get(u.get("cls"), u.get("cls")) or "unklassifiziert"
            typ_cit[t] += int(u.get("cit") or 0)
            typ_n[t] += 1
        tot = sum(typ_cit.values())
        k["zitatanteil_je_seitentyp"] = {
            "available": True, "gesamt_zitate": tot,
            "typen": [{"seitentyp": t, "zitate": c, "urls": typ_n[t],
                       "anteil_pct": round(100.0 * c / tot, 2) if tot else None}
                      for t, c in typ_cit.most_common()],
            "vorbehalt": VORBEHALT_PEEC + " Seitentyp-Klassifikation stammt aus einer "
                         "Peec-Heuristik, nicht aus einer geprueften Taxonomie."}

    # 3. ERGO vs. Allianz je Seitentyp ------------------------------------
    if not peec_urls:
        k["ergo_vs_allianz_je_seitentyp"] = {"available": False,
                                             "grund": "Keine Peec-URL-Daten.",
                                             "vorbehalt": VORBEHALT_PEEC}
    else:
        vgl = {}
        gruppen = {"ERGO": lambda h: h in OWN_DOMAINS,
                   "Allianz": lambda h: h in ("allianz.de", "allianzdirect.de", "allianz.com")}
        for label, test in gruppen.items():
            for u in peec_urls.values():
                h = host_of(norm_url(u.get("url")))
                if not test(h):
                    continue
                t = PEEC_CLS_MAP.get(u.get("cls"), u.get("cls")) or "unklassifiziert"
                row = vgl.setdefault(t, {"seitentyp": t, "ERGO": 0, "Allianz": 0,
                                         "ERGO_urls": 0, "Allianz_urls": 0})
                row[label] += int(u.get("cit") or 0)
                row[label + "_urls"] += 1
        k["ergo_vs_allianz_je_seitentyp"] = {
            "available": bool(vgl),
            "grund": None if vgl else "Keine ERGO-/Allianz-URLs im Top-150.",
            "typen": sorted(vgl.values(), key=lambda r: -(r["ERGO"] + r["Allianz"])),
            "vorbehalt": VORBEHALT_PEEC + " Verglichen werden nur URLs, die es in die "
                         "Top-150 geschafft haben; beide Marken sind damit gleich hart "
                         "gekappt, aber der jeweilige Long Tail fehlt."}

    # 4. Verlauf der ERGO-URLs im Peec-Top-150 -----------------------------
    if not snaps:
        k["ergo_top150_verlauf"] = {"available": False,
                                    "grund": "Keine archivierten Peec-Snapshots.",
                                    "vorbehalt": VORBEHALT_PEEC}
    else:
        verlauf = []
        for datum, idx in snaps:
            urls = [u for kk, u in idx.items() if host_of(kk) in OWN_DOMAINS]
            verlauf.append({"datum": datum, "urls_im_top150": len(urls),
                            "zitate": sum(int(u.get("cit") or 0) for u in urls)})
        k["ergo_top150_verlauf"] = {
            "available": True, "staende": verlauf,
            "vorbehalt": VORBEHALT_PEEC + " Jeder Stand ist ein eigenes rollierendes "
                         "30-Tage-Fenster; die Faenster ueberlappen sich stark, die Punkte "
                         "sind daher nicht unabhaengig."}

    # 5. Median-Tage bis erstes Zitat --------------------------------------
    # Punktschaetzungen (echtes Publikationsdatum) und untere Schranken
    # (Sitemap-Obergrenze / Erstsichtungs-Proxy) werden GETRENNT ausgewiesen —
    # ein gemeinsamer Median waere eine Zahl ohne definierte Bedeutung.
    punkt = [r for r in rows if r["tage_bis_erstes_zitat"] is not None
             and r.get("tage_bis_erstes_zitat_art") == "punktschaetzung"]
    schranke = [r for r in rows if r["tage_bis_erstes_zitat"] is not None
                and r.get("tage_bis_erstes_zitat_art") == "untere_schranke"]
    s_obg = [r for r in schranke if r.get("tage_bis_erstes_zitat_basis") == "sitemap_lastmod"]
    s_proxy = [r for r in schranke
               if r.get("tage_bis_erstes_zitat_basis") == "proxy_first_seen"]
    if schranke:
        schranke_block = {
            "available": True,
            "median_tage_mindestens": median([r["tage_bis_erstes_zitat"] for r in schranke]),
            "n": len(schranke),
            "davon_sitemap_obergrenze": len(s_obg),
            "davon_erstsichtungs_proxy": len(s_proxy),
            "lesart": ("Untergrenze: die echte Spanne Publikation -> erstes Zitat ist "
                       "MINDESTENS so gross. Nicht mit der Punktschaetzung mitteln und nicht "
                       "als 'so schnell wurde zitiert' lesen."),
        }
    else:
        schranke_block = {"available": False,
                          "grund": ("Keine zitierte URL mit Sitemap-Obergrenze oder "
                                    "verwertbarem Erstsichtungs-Proxy.")}
    vorbehalt = ("Der Zitatzeitpunkt ist auf die %d archivierten Snapshots gerastert; URLs, "
                 "die schon im ersten Stand zitiert wurden, sind linkszensiert (das echte "
                 "erste Zitat liegt frueher). Ausgewiesen ist NUR die Punktschaetzung aus "
                 "echten schema.org-Publikationsdaten; Seiten, fuer die es nur eine "
                 "Sitemap-Obergrenze oder unsere Erstsichtung gibt, stehen getrennt unter "
                 "`untere_schranke` und sind dort Mindestwerte." % len(snaps))
    if not punkt:
        grund = ("Fuer keine zitierte URL liegt ein echtes schema.org-Publikationsdatum vor "
                 "(ERGO: %d von %d getrackten Seiten mit schema.org-Datum)."
                 % (sum(1 for r in rows if r["brand"] == "ERGO"
                        and r.get("published_quelle") == "schema"),
                    brand_getrackt.get("ERGO", 0)))
        if schranke:
            grund += (" Es gibt nur untere Schranken: fuer %d URLs sind es mindestens %s Tage "
                      "(davon %d aus der Sitemap-Obergrenze) — siehe `untere_schranke`."
                      % (len(schranke), schranke_block["median_tage_mindestens"], len(s_obg)))
        k["median_tage_bis_erstes_zitat"] = {
            "available": False, "grund": grund,
            "median_tage": None, "n": 0,
            "davon_echtes_publikationsdatum": 0, "davon_proxy": 0,
            "art": "punktschaetzung",
            "untere_schranke": schranke_block,
            "vorbehalt": vorbehalt}
    else:
        k["median_tage_bis_erstes_zitat"] = {
            "available": True,
            "median_tage": median([r["tage_bis_erstes_zitat"] for r in punkt]),
            "n": len(punkt),
            "davon_echtes_publikationsdatum": len(punkt),
            "davon_proxy": 0,
            "art": "punktschaetzung",
            "linkszensiert": sum(1 for r in rows if r.get("zitat_linkszensiert")),
            "untere_schranke": schranke_block,
            "vorbehalt": vorbehalt}

    # 5b. Neuheit ausschliessen (Nutzen der Sitemap-Obergrenze) -------------
    k["neuheit_ausschluss_je_marke"] = build_neuheit_ausschluss(pd_idx)

    # 6. Engine-Abdeckung eigener Seiten -----------------------------------
    if own_per_engine is None:
        k["engine_abdeckung"] = {"available": False,
                                 "grund": (own_meta or {}).get("grund", "Eigener Crawl nicht verfuegbar."),
                                 "vorbehalt": "Ohne data/runs/latest.json keine Engine-Aussage."}
    else:
        engines = []
        for eng, cnt in sorted(own_per_engine.items()):
            eigen = [kk for kk in cnt if host_of(kk) in OWN_DOMAINS]
            getrackt = [kk for kk in cnt if kk in pd_idx]
            engines.append({
                "engine": eng, "belastbar": ENGINE_BELASTBAR.get(eng, False),
                "grund": ENGINE_GRUND.get(eng, "Engine unbekannt — nicht bewertet."),
                "distinkte_quell_urls": len(cnt),
                "roh_quellenangaben": (own_meta.get("roh_quellen_je_engine") or {}).get(eng),
                "eigene_urls": len(eigen) if ENGINE_BELASTBAR.get(eng) else None,
                "eigene_urls_hinweis": None if ENGINE_BELASTBAR.get(eng)
                    else "nicht ausgewiesen — Engine liefert keine belastbaren Quell-URLs",
                "getrackte_urls": len(getrackt) if ENGINE_BELASTBAR.get(eng) else None,
            })
        k["engine_abdeckung"] = {
            "available": True, "engines": engines,
            "run_id": own_meta.get("run_id"), "stand": own_meta.get("finished_at"),
            "vorbehalt": ("Nur Perplexity liefert echte Quell-URLs. Gemini gibt fast nur "
                          "vertexaisearch-Redirects zurueck, ChatGPT laeuft ohne Websuche — "
                          "beide werden hier bewusst NICHT mitgezaehlt. Ein einzelner Lauf, "
                          "kein Mittel ueber mehrere Tage.")}

    k["_hinweis"] = VORBEHALT_KOVOR
    return k


# ---------------------------------------------------------------------------
# Presse-Block (Domain-Ebene)
# ---------------------------------------------------------------------------
# Medienname (Google-News 'source') -> Domain. Nur belegte Zuordnungen; alles
# andere bleibt unzugeordnet und wird als solches ausgewiesen.
MEDIUM_DOMAIN = {
    "versicherungsbote": "versicherungsbote.de",
    "handelsblatt": "handelsblatt.com",
    "faz.net": "faz.net", "faz": "faz.net",
    "wiwo.de": "wiwo.de", "wirtschaftswoche": "wiwo.de",
    "versicherungsjournal.de": "versicherungsjournal.de",
    "versicherungsjournal": "versicherungsjournal.de",
    "test.de": "test.de", "stiftung warentest": "test.de",
    "finanztip": "finanztip.de",
    "verbraucherzentrale": "verbraucherzentrale.de",
    "versicherungsmagazin.de": "versicherungsmagazin.de",
    "versicherungswirtschaft-heute": "versicherungswirtschaft-heute.de",
    "procontra": "procontra-online.de",
    "cash-online.de": "cash-online.de",
    "boersen-zeitung.de": "boersen-zeitung.de",
    "horizont.net": "horizont.net",
    "asscompact": "asscompact.de",
    "das investment": "dasinvestment.com",
}


_MULTI_TLD = {"co.uk", "com.au", "co.nz", "com.br", "co.jp", "org.uk", "gov.uk", "ac.uk"}


def etld1(host):
    """Registrierbare Domain. wissenswert.hannoversche.de -> hannoversche.de."""
    if not host:
        return None
    parts = str(host).lower().strip(".").split(".")
    if len(parts) <= 2:
        return ".".join(parts)
    if ".".join(parts[-2:]) in _MULTI_TLD:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def load_press_history():
    """Presseartikel mit aufgeloesten echten URLs (scripts/backfill_press_urls.py).
    Liefert (artikel, meta). Ohne aufgeloeste URLs -> meta['aufgeloest'] = 0."""
    if not PRESS_HISTORY.exists():
        return None, {"available": False, "grund": "data/press_history.json fehlt."}
    try:
        arts = json.loads(PRESS_HISTORY.read_text(encoding="utf-8"))
    except Exception as ex:
        return None, {"available": False,
                      "grund": "press_history.json nicht lesbar: %s" % str(ex)[:120]}
    if not isinstance(arts, list):
        return None, {"available": False, "grund": "press_history.json hat unerwartete Struktur."}
    aufgeloest = sum(1 for a in arts if a.get("url_real"))
    daten = sorted(a.get("date") for a in arts if a.get("date"))
    meta = {
        "available": True,
        "artikel_gesamt": len(arts),
        "artikel_mit_echter_url": aufgeloest,
        "aufloesungsquote_pct": round(100.0 * aufgeloest / len(arts), 1) if arts else None,
        "zeitraum": {"von": daten[0] if daten else None, "bis": daten[-1] if daten else None},
        "marken": sorted({(a.get("brand_name") or a.get("brand")) for a in arts if a.get("brand")}),
        "quelle": ("Google-News-RSS; die Redirect-URLs sind zu echten Artikel-URLs "
                   "aufgeloest (Feld url_real), dadurch ist der Abgleich artikelgenau "
                   "moeglich."),
    }
    return arts, meta


def build_presse(peec, peec_domains, peec_urls=None, snaps=None):
    """Zitierte Quellen gegen die eigene Presseaktivitaet — auf Domain-Ebene UND,
    seit der Aufloesung der Google-News-Redirects, artikelgenau."""
    if not peec_domains:
        return {"available": False, "grund": "Keine Peec-Domaindaten.",
                "vorbehalt": VORBEHALT_PEEC}

    fenster = (peec or {}).get("window") or {}
    f_start, f_end = fenster.get("start"), fenster.get("end")

    arts, presse_meta = load_press_history()

    # Zaehler je registrierbarer Domain
    ergo_gesamt, ergo_fenster = Counter(), Counter()
    alle_gesamt = Counter()
    marken_je_domain = {}
    ohne_domain = Counter()
    treffer = []

    # Peec-URL-Menge (Top-150 + alle Snapshot-Staende)
    peec_url_idx = dict(peec_urls or {})
    for eintrag in (snaps or []):
        idx = eintrag[1] if isinstance(eintrag, (tuple, list)) and len(eintrag) > 1 else None
        if not isinstance(idx, dict):
            continue
        for k, u in idx.items():
            if k and k not in peec_url_idx:
                peec_url_idx[k] = u

    if arts:
        for a in arts:
            dom = a.get("domain") or ""
            if not dom and a.get("url_real"):
                k = norm_url(a.get("url_real"))
                dom = (k or "").split("/")[0]
            dom = etld1(dom)
            if not dom:
                medium = (a.get("source") or "").strip().lower()
                dom = MEDIUM_DOMAIN.get(medium)
                if not dom:
                    if medium:
                        ohne_domain[medium] += 1
                    continue
            ist_ergo = (a.get("brand") or "").lower() in ("ergo", "dkv")
            alle_gesamt[dom] += 1
            marken_je_domain.setdefault(dom, set()).add(a.get("brand_name") or a.get("brand"))
            if ist_ergo:
                ergo_gesamt[dom] += 1
                dt = a.get("date")
                if dt and f_start and f_end and f_start <= dt <= f_end:
                    ergo_fenster[dom] += 1
            # artikelgenauer Abgleich
            k = join_key(norm_url(a.get("url_real")))
            if k and k in peec_url_idx:
                pu = peec_url_idx[k] or {}
                treffer.append({
                    "url": k, "titel": a.get("title"), "datum": a.get("date"),
                    "marke": a.get("brand_name") or a.get("brand"),
                    "typ": a.get("type"), "domain": dom,
                    "peec_cit": pu.get("cit"), "peec_cls": pu.get("cls"),
                    "peec_titel": pu.get("title"),
                })
        treffer.sort(key=lambda t: -(t.get("peec_cit") or 0))

    # Domainliste: alle zitierten Domains, bei denen es Presseaktivitaet gibt,
    # plus die redaktionellen Top-Domains (auch ohne eigene Artikel).
    kandidaten = {}
    for d in peec_domains.values():
        dom = etld1(d.get("domain"))
        if not dom:
            continue
        if d.get("cls") == "Editorial" or alle_gesamt.get(dom):
            vor = kandidaten.get(dom)
            if not vor or (d.get("cit") or 0) > (vor.get("cit") or 0):
                kandidaten[dom] = d

    domains = []
    for dom, d in kandidaten.items():
        eintrag = {
            "domain": dom, "cls": d.get("cls"),
            "zitate": d.get("cit"), "abrufe": d.get("ret"),
            "marken_in_antworten": d.get("brands") or [],
            "ergo_genannt": "ERGO" in (d.get("brands") or []),
            "ergo_presseartikel_im_peec_fenster": ergo_fenster.get(dom),
            "ergo_presseartikel_gesamt": ergo_gesamt.get(dom),
            "presseartikel_alle_marken": alle_gesamt.get(dom),
            "marken_mit_presse": sorted(marken_je_domain.get(dom, ())) or None,
        }
        if not presse_meta.get("available"):
            eintrag["presse_hinweis"] = "Presseliste nicht verfuegbar — kein Abgleich moeglich."
        elif not ergo_gesamt.get(dom):
            eintrag["presse_hinweis"] = ("Kein ERGO-Artikel dieses Mediums in der "
                                         "Presse-Historie — nicht als 'keine "
                                         "Presseaktivitaet' lesen, der Feed erfasst "
                                         "nicht alles.")
        elif not ergo_fenster.get(dom):
            eintrag["presse_hinweis"] = ("ERGO-Artikel vorhanden, aber keiner im "
                                         "Peec-Fenster %s..%s." % (f_start, f_end))
        domains.append(eintrag)
    domains.sort(key=lambda e: -(e.get("zitate") or 0))

    return {
        "available": True,
        "ebene": "Domain und Artikel-URL",
        "peec_fenster": fenster,
        "domains": domains,
        "artikel_treffer": treffer,
        "n_artikel_treffer": len(treffer),
        "artikel_treffer_hinweis": (
            "Presseartikel, deren echte URL in Peecs zitierten Quellen auftaucht. "
            "Eine leere oder sehr kurze Liste heisst: die einzelne Meldung schafft es "
            "nicht in die Zitate — Wirkung entsteht ueber die Domain, nicht ueber den "
            "einzelnen Artikel." if not treffer else
            "Presseartikel, deren echte URL in Peecs zitierten Quellen auftaucht. "
            "Evergreen-Vergleichsseiten, die Google News als Artikel ausspielt, sind "
            "hier mit enthalten — sie werden unabhaengig von der Pressearbeit zitiert."),
        "presse_quelle": presse_meta,
        "unzugeordnete_medien": ohne_domain.most_common(15),
        "vorbehalt": ("Domainzuordnung auf der registrierbaren Domain (Content-"
                      "Subdomains wie wissenswert.hannoversche.de zaehlen auf "
                      "hannoversche.de). Der artikelgenaue Abgleich ist durch die "
                      "Peec-Top-150-Kappung nach unten begrenzt: ein Artikel ohne "
                      "Treffer kann trotzdem zitiert worden sein, nur nicht haeufig "
                      "genug fuer die Top-150. 'ERGO genannt' heisst nur, dass ERGO in "
                      "Antworten vorkam, in denen diese Domain zitiert wurde "
                      "(Ko-Vorkommen, kein Kausalnachweis). " + VORBEHALT_PEEC),
    }


# ---------------------------------------------------------------------------
def main():
    out = build()
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")),
                        encoding="utf-8")
    kb = OUT_FILE.stat().st_size / 1024.0
    m = out["meta"]
    print("[content_citations] %d Zeilen -> %s (%.0f KB)" % (m["n_zeilen"], OUT_FILE, kb))
    for name, q in m["quellen"].items():
        state = "ok" if q.get("available") else "FEHLT"
        print("   %-16s %-6s %s" % (name, state, q.get("grund") or q.get("quelle") or ""))
    for name, kz in out["kennzahlen"].items():
        if name.startswith("_"):
            continue
        if not kz.get("available"):
            print("   Kennzahl %-30s available=false: %s" % (name, kz.get("grund")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
