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

# Erhebungsregime der eigenen Pressemitteilungen - wird in die Ausgabe-JSON
# geschrieben, damit nachgelagerte Auswertungen den Bruch kennen, ohne diesen
# Code zu lesen.
PRESS_QUERY_REGIME = {
    "ergo_query_angeglichen_am": "2026-08-23",
    "hinweis": ("Bis 22.08.2026 lief die ERGO-own_query ohne '+Presse OR "
                "Pressemitteilung'; press_mention-Zahlen vor/nach diesem Tag "
                "entstammen verschiedenen Erhebungsregimen."),
}

# ── Brand-Konfiguration ──────────────────────────────────────────────────────
BRANDS = [
    {
        "key": "ergo", "name": "ERGO",
        "media_query": "ERGO+Versicherung",
        # 23.08.2026 REGIMEWECHSEL (Modell-Audit, Pauls Go): Bis heute lief die
        # ERGO-Anfrage OHNE den Zusatz "+Presse OR Pressemitteilung", den
        # Allianz, AXA und Generali seit jeher tragen. Folge: ERGO zaehlte
        # ALLES, was Google auf ergo.com/ergo-group.com indexiert (auch
        # Magazin- und Ratgeberartikel), die Wettbewerber nur Presse-Seiten -
        # die press_mention-Zaehlbasis war systematisch asymmetrisch und der
        # ERGO-Vergleich damit unfair NACH OBEN verzerrt.
        # Ereignisse vor dem 23.08.2026 bleiben unveraendert im Bestand; wer
        # press_mention ueber diesen Tag hinweg vergleicht, vergleicht zwei
        # Erhebungsregime. Das JSON weist das unter press_query_regime aus.
        "own_query": "site:ergo.com+OR+site:ergo-group.com+Presse+OR+Pressemitteilung",
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


# ---------------------------------------------------------------------------
# Beitragsanpassungen als eigenes Ereignis (10.08.2026)
#
# Warum das hier steht und nicht im Preis-Crawler: Der Preis-Crawler MISST
# Niveaus. Fuer die Event-Study braucht das Modell aber DATIERTE AENDERUNGEN -
# und die sind ueber Stichproben praktisch nicht zu bekommen. Nachgerechnet
# ueber die Git-Historie von price_comparison.json aendern sich an den meisten
# Tagen null von rund 230 Zellen; Versicherungstarife bewegen sich ein- bis
# zweimal im Jahr. Der Impact-Block meldet entsprechend "nach Artefaktfilter zu
# wenige Preisereignisse (n=1 von 22, noetig sind 5)".
#
# Beitragsanpassungen werden dagegen ANGEKUENDIGT - mit Marke und Datum, also
# genau in dem Format, das die Event-Study braucht. Der Presse-Crawl laeuft
# ohnehin; hier wird nur zusaetzlich klassifiziert.
#
# Bewusst eng gefasst: "Beitrag" allein triggert nicht (zu viele Treffer wie
# "Beitrag zur Nachhaltigkeit"), es braucht die Kombination mit einer
# Aenderungsrichtung oder einen der eindeutigen Fachbegriffe.
_BAP_EINDEUTIG = [
    r"beitragsanpassung", r"pr(ä|ae)mienanpassung", r"beitragserh(ö|oe)hung",
    r"pr(ä|ae)mienerh(ö|oe)hung", r"beitragssenkung", r"tarifanpassung",
    r"beitragsentlastung",
]
_BAP_KOMBI_A = [r"\bbeitr(a|ä)g", r"\bpr(ä|ae)mie", r"\btarif"]
_BAP_KOMBI_B = [r"erh(ö|oe)h", r"steig", r"senk", r"g(ü|ue)nstiger", r"teurer",
                r"anpass", r"\bplus\b", r"\bminus\b", r"prozent"]

# Ausschluesse. Gegen die 1.111 Titel im Presse-Archiv getestet: ohne diese Liste
# schlugen "Axa steigert Beitragseinnahmen" und "Signal Iduna steigert
# Praemieneinnahmen auf 7,2 Milliarden Euro" als Beitragsanpassung an. Das ist
# UMSATZ, nicht Preis - zwei von fuenf Treffern waren falsch. Beitragseinnahmen
# steigen, wenn ein Versicherer mehr Vertraege verkauft, voellig unabhaengig
# davon, was der einzelne Kunde zahlt.
_BAP_NICHT = [
    r"beitragseinnahm", r"pr(ä|ae)mieneinnahm", r"beitragsaufkommen",
    r"beitragsvolumen", r"pr(ä|ae)mienvolumen", r"bruttobeitr",
    r"gebuchte (beitr|pr(ä|ae)mie)", r"\bumsatz",
]


def erkenne_beitragsanpassung(titel):
    """Ist das eine Meldung ueber eine Beitrags-/Praemienaenderung?

    Rueckgabe: (True/False, richtung) mit richtung in {"hoch","runter",None}.
    Die Richtung bleibt None, wenn der Titel sie nicht hergibt - dann steht im
    Event ausdruecklich "unbekannt" statt einer geratenen Vorzeichenangabe.
    """
    t = (titel or "").lower()
    if any(re.search(p, t) for p in _BAP_NICHT):
        return False, None
    treffer = any(re.search(p, t) for p in _BAP_EINDEUTIG)
    if not treffer:
        treffer = (any(re.search(p, t) for p in _BAP_KOMBI_A)
                   and any(re.search(p, t) for p in _BAP_KOMBI_B))
    if not treffer:
        return False, None
    hoch = re.search(r"erh(ö|oe)h|steig|teurer|\bplus\b|anheb", t)
    runter = re.search(r"senk|g(ü|ue)nstiger|billiger|\bminus\b|entlast", t)
    if hoch and not runter:
        return True, "hoch"
    if runter and not hoch:
        return True, "runter"
    return True, None


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
    """Parse RSS pubDate (RFC 822) zu ISO-Format.
    Review-Fix 2026-06-04: email.utils statt Eigenbau — numerische
    TZ-Offsets (+0100) gingen vorher verloren (Datum wurde None)."""
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str.strip()).strftime("%Y-%m-%d")
    except Exception:
        try:
            clean = re.sub(r'\s+\S{1,6}$', '', date_str.strip())
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



# ══════════════════════════════════════════════════════════════════════════════
# URL-Aufloesung: Google-News-Redirects -> echte Artikel-URLs
# ------------------------------------------------------------------------------
# Google News RSS liefert ausschliesslich Redirect-Links der Form
#   https://news.google.com/rss/articles/CBMi...?oc=5
# Ohne die echte Ziel-URL laesst sich nicht pruefen, ob ein Presseartikel
# spaeter von den LLMs zitiert wurde (Join gegen data/peec_sources.json).
#
# Zusaetzliche Felder je Artikel (bestehende Felder bleiben unveraendert):
#   url_real            echte Artikel-URL (leer, wenn nicht aufloesbar)
#   domain              Domain ohne "www." (aus url_real oder Publisher-Tabelle)
#   url_real_quelle     "redirect" | "rss_source" | "unaufgeloest"
#   url_real_geprueft_am  ISO-Datum des Aufloesungsversuchs
#
# Wege in dieser Reihenfolge:
#   (a) Google-News-Artikel-ID dekodieren (base64/Protobuf). Bei den seit ca.
#       2024 ausgelieferten "AU_yqL..."-IDs steht die Ziel-URL NICHT mehr im
#       Klartext drin — der Weg greift nur noch bei aelteren Eintraegen.
#   (b) HTTP: GET mit allow_redirects. Landet der Redirect nicht bei Google,
#       ist das die Ziel-URL. Sonst wird aus der Interstitial-Seite das
#       Signatur-Paar (data-n-a-ts / data-n-a-sg) gezogen und ueber den
#       DotsSplashUi-batchexecute-Endpoint die Ziel-URL angefragt.
#   (c) Fallback: keine URL, Domain aus dem RSS-Feld "source" ueber die
#       gepflegte Publisher-Tabelle -> url_real_quelle = "rss_source".
#
# Grundsatz: Der Presse-Lauf darf NIE am Aufloesen scheitern. Jeder Fehler
# fuehrt zu "unaufgeloest", nicht zum Abbruch.
# ══════════════════════════════════════════════════════════════════════════════

URL_CACHE_PATH = Path("data/press_url_cache.json")
BATCHEXECUTE_URL = "https://news.google.com/_/DotsSplashUi/data/batchexecute"

# Publisher-Klarname (RSS-Feld "source") -> Domain. Nur Fallback, wenn die
# echte URL nicht aufgeloest werden konnte. Keys werden case-insensitiv
# verglichen (siehe domain_from_source).
PUBLISHER_DOMAINS = {
    # Versicherer / eigene Newsrooms
    "ergo group ag": "ergo.com", "ergo group": "ergo.com", "ergo": "ergo.com",
    "allianz": "allianz.de", "allianz.com": "allianz.com",
    "allianz commercial": "commercial.allianz.com",
    "axa deutschland": "axa.de", "axa versicherung": "axa.de", "axa": "axa.de",
    "huk-coburg": "huk.de", "huk coburg": "huk.de",
    "generali": "generali.de", "generali deutschland": "generali.de",
    "signal iduna": "signal-iduna.de",
    "r+v versicherung": "ruv.de", "r+v": "ruv.de",
    "devk": "devk.de", "devk versicherungen": "devk.de",
    "hannoversche versicherung": "hannoversche.de", "hannoversche": "hannoversche.de",
    "cosmos direkt": "cosmosdirekt.de", "cosmosdirekt": "cosmosdirekt.de",
    # PR-Verteiler
    "presseportal": "presseportal.de", "mynewsdesk": "mynewsdesk.com",
    "lifepr": "lifepr.de", "pressebox": "pressebox.de",
    # Fach- / Finanzpresse
    "ad hoc news": "ad-hoc-news.de",
    "versicherungsbote": "versicherungsbote.de",
    "versicherungsjournal": "versicherungsjournal.de",
    "versicherungsjournal deutschland": "versicherungsjournal.de",
    "versicherungsmonitor": "versicherungsmonitor.de",
    "versicherungsmagazin": "versicherungsmagazin.de",
    "versicherungswirtschaft-heute": "versicherungswirtschaft-heute.de",
    "procontra": "procontra-online.de",
    "asscompact": "asscompact.de", "asscompact österreich": "asscompact.at",
    "pfefferminzia": "pfefferminzia.de",
    "das investment": "dasinvestment.com",
    "fonds professionell": "fondsprofessionell.de",
    "finanzwelt": "finanzwelt.de",
    "cash-online": "cash-online.de",
    "börsen-zeitung": "boersen-zeitung.de",
    "der platow brief": "platow.de", "platow": "platow.de",
    "private banking magazin": "private-banking-magazin.de",
    "portfolio institutionell": "portfolio-institutionell.de",
    "dpn magazin": "dpn-online.com",
    "it finanzmagazin": "it-finanzmagazin.de",
    "it boltwise": "it-boltwise.de",
    "citywire": "citywire.com",
    "marketscreener deutschland": "marketscreener.com",
    "finanzen.net": "finanzen.net", "boerse.de": "boerse.de",
    "der aktionär": "deraktionaer.de",
    "capital.com": "capital.com",
    "stiftung warentest": "test.de",
    # Tages- / Wirtschaftspresse
    "faz": "faz.net", "frankfurter allgemeine zeitung": "faz.net",
    "handelsblatt": "handelsblatt.com",
    "wirtschaftswoche": "wiwo.de", "wiwo": "wiwo.de",
    "sz.de": "sueddeutsche.de", "süddeutsche zeitung": "sueddeutsche.de",
    "die zeit": "zeit.de", "zeit online": "zeit.de",
    "t-online": "t-online.de", "focus online": "focus.de",
    "ntv": "n-tv.de", "n-tv": "n-tv.de",
    "msn": "msn.com", "chip": "chip.de",
    "zdfheute": "zdf.de", "ndr.de": "ndr.de", "ndr": "ndr.de",
    "neue zürcher zeitung": "nzz.ch",
    "rp online": "rp-online.de",
    "merkur": "merkur.de", "hna": "hna.de",
    "saarbrücker zeitung": "saarbruecker-zeitung.de",
    "braunschweiger zeitung": "braunschweiger-zeitung.de",
    "sächsische zeitung": "saechsische.de",
    "ruhr nachrichten": "ruhrnachrichten.de",
    "derwesten": "derwesten.de", "neue gladbecker zeitung": "waz.de",
    "allgemeine zeitung": "allgemeine-zeitung.de",
    "goslarsche.de": "goslarsche.de",
    "fränkischer tag": "infranken.de", "infranken.de": "infranken.de",
    "nn.de": "nn.de", "neue presse coburg": "np-coburg.de",
    "kurierverlag": "kurierverlag.de",
    "blick.de": "blick.de",
    "schwarzwälder bote": "schwarzwaelder-bote.de",
    "tageblatt": "tageblatt.lu", "luxemburger wort": "wort.lu",
    "budapester zeitung": "budapester.hu", "heute": "heute.at",
    # Branchen- / Sonstige
    "autohaus.de": "autohaus.de", "automobilwoche": "automobilwoche.de",
    "autoservicepraxis.de": "autoservicepraxis.de",
    "vision mobility": "vision-mobility.de",
    "deutsches handwerksblatt": "handwerksblatt.de",
    "horizont.net": "horizont.net", "meedia": "meedia.de",
    "anwalt.de": "anwalt.de", "aponet.de": "aponet.de",
    "onefootball": "onefootball.com", "joyn": "joyn.de",
    "reisetopia": "reisetopia.de",
    "sap news center": "news.sap.com",
    "tsv 1860 e.v.": "tsv1860.org",
    "marketingscout.com": "marketingscout.com",
    "verbraucherschutzforum.berlin": "verbraucherschutzforum.berlin",
}

_DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$")


def normalize_domain(value):
    """Host aus URL oder Rohstring -> Domain in Kleinschreibung ohne 'www.'."""
    if not value:
        return ""
    v = value.strip().lower()
    if "://" in v:
        try:
            v = urllib.parse.urlsplit(v).netloc
        except ValueError:
            return ""
    v = v.split("/")[0].split("@")[-1].split(":")[0]
    if v.startswith("www."):
        v = v[4:]
    return v if _DOMAIN_RE.match(v) else ""


def domain_from_source(source):
    """Publisher-Klarname aus dem RSS-Feld 'source' -> Domain (Fallback-Weg c)."""
    if not source:
        return ""
    key = source.strip().lower()
    if key in PUBLISHER_DOMAINS:
        return PUBLISHER_DOMAINS[key]
    # Viele Quellen liefern die Domain bereits direkt ("versicherungsbote.de")
    direct = normalize_domain(key)
    if direct:
        return direct
    # Toleranter Zweitversuch: Zusaetze wie "Deutschland"/"Online" abschneiden
    stripped = re.sub(r"\s+(deutschland|online|magazin|de)$", "", key).strip()
    return PUBLISHER_DOMAINS.get(stripped, "")


def extract_gnews_id(url):
    """Google-News-Artikel-ID aus der Redirect-URL ziehen."""
    m = re.search(r"news\.google\.com/(?:rss/)?(?:articles|read)/([^?/#]+)", url or "")
    return m.group(1) if m else ""


def decode_gnews_id(article_id):
    """Weg (a): base64-kodiertes Protobuf dekodieren.

    Aeltere IDs enthielten die Ziel-URL im Klartext. Die seit ca. 2024
    ausgelieferten IDs (Praefix 'AU_yqL...') sind opake Handles — dort
    liefert diese Funktion nichts und Weg (b) uebernimmt.
    """
    if not article_id:
        return ""
    try:
        import base64
        pad = article_id + "=" * (-len(article_id) % 4)
        raw = base64.urlsafe_b64decode(pad.encode("ascii", errors="ignore"))
    except Exception:
        return ""
    text = raw.decode("latin-1", errors="replace")
    m = re.search(r"https?://[^\x00-\x20\"'<>\\]{6,}", text)
    if not m:
        return ""
    candidate = m.group(0)
    # Protobuf-Laengenpraefixe koennen Muell anhaengen -> am ersten
    # Steuerzeichen/Trennzeichen abschneiden
    candidate = re.split(r"[\x00-\x1f]", candidate)[0].strip()
    if normalize_domain(candidate) and "news.google.com" not in candidate:
        return candidate
    return ""


def _http_get(session, url, timeout, tries=3, **kwargs):
    """GET mit Retry bei 429/5xx und exponentiellem Backoff. Nie werfend."""
    delay = 1.5
    for attempt in range(tries):
        try:
            resp = session.get(url, timeout=timeout, **kwargs)
        except Exception:
            if attempt == tries - 1:
                return None
            time.sleep(delay)
            delay *= 2
            continue
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt == tries - 1:
                return None
            time.sleep(delay)
            delay *= 2
            continue
        return resp
    return None


def _http_post(session, url, timeout, tries=3, **kwargs):
    delay = 1.5
    for attempt in range(tries):
        try:
            resp = session.post(url, timeout=timeout, **kwargs)
        except Exception:
            if attempt == tries - 1:
                return None
            time.sleep(delay)
            delay *= 2
            continue
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt == tries - 1:
                return None
            time.sleep(delay)
            delay *= 2
            continue
        return resp
    return None


def _resolve_via_batchexecute(session, article_id, ts, sig, timeout=25):
    """Ziel-URL ueber den DotsSplashUi-Endpoint anfragen (Teil von Weg b)."""
    payload = [
        "garturlreq",
        [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1,
          None, None, None, None, None, 0, 1],
         "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
        article_id, int(ts), str(sig),
    ]
    freq = [[["Fbv4je", json.dumps(payload), None, "generic"]]]
    resp = _http_post(
        session, BATCHEXECUTE_URL, timeout,
        data={"f.req": json.dumps(freq)},
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
    )
    if resp is None or resp.status_code != 200:
        return ""
    m = re.search(r'garturlres\\\\"\s*,\s*\\\\"(https?://[^\\\\"]+)', resp.text)
    if not m:
        m = re.search(r'garturlres[^h]{0,20}(https?://[^\\"\s]+)', resp.text)
    if not m:
        return ""
    return m.group(1).replace("\\/", "/")


def resolve_google_news_url(url, session=None, timeout=20, sleep=0.4):
    """Eine Google-News-Redirect-URL aufloesen.

    Rueckgabe: (url_real, quelle) mit quelle in {"redirect", ""}.
    Wirft nie — im Fehlerfall ("", "").
    """
    try:
        import requests
    except ImportError:
        return "", ""

    if session is None:
        session = requests.Session()
        session.headers["User-Agent"] = UA

    article_id = extract_gnews_id(url)

    # Weg (a): ID dekodieren
    decoded = decode_gnews_id(article_id)
    if decoded:
        return decoded, "redirect"

    # Weg (b): HTTP-Redirect / Interstitial + batchexecute
    resp = _http_get(session, url, timeout, allow_redirects=True)
    if resp is None:
        return "", ""
    final = resp.url or ""
    if normalize_domain(final) and "news.google.com" not in final and "google.com/url" not in final:
        return final, "redirect"

    html = resp.text or ""
    ts_m = re.search(r'data-n-a-ts="(\d+)"', html)
    sg_m = re.search(r'data-n-a-sg="([^"]+)"', html)
    if not (ts_m and sg_m and article_id):
        return "", ""
    if sleep:
        time.sleep(sleep)
    real = _resolve_via_batchexecute(session, article_id, ts_m.group(1), sg_m.group(1), timeout)
    if real and normalize_domain(real) and "news.google.com" not in real:
        return real, "redirect"
    return "", ""


def load_url_cache(path=URL_CACHE_PATH):
    """Cache article_id -> {url_real, quelle, geprueft_am}. Nie werfend."""
    try:
        if Path(path).exists():
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_url_cache(cache, path=URL_CACHE_PATH):
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as exc:
        print("    WARN: URL-Cache nicht schreibbar: %s" % str(exc)[:80])


def enrich_article_urls(articles, cache=None, session=None, budget_seconds=None,
                        max_lookups=None, sleep=0.4, verbose=True):
    """Artikel-Dicts in-place um url_real/domain/url_real_quelle/... ergaenzen.

    Idempotent: Eintraege, die bereits ein url_real_quelle in {"redirect",
    "rss_source"} tragen, werden uebersprungen. "unaufgeloest" wird erneut
    versucht (Google liefert manchmal beim zweiten Anlauf).
    Bestehende Felder (url, source, ...) werden nie ueberschrieben.
    Rueckgabe: Counter mit den Quellen.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    stats = Counter()
    if cache is None:
        cache = load_url_cache()

    try:
        import requests
        if session is None:
            session = requests.Session()
            session.headers["User-Agent"] = UA
    except ImportError:
        session = None  # nur Cache + Fallback moeglich

    started = time.time()
    lookups = 0
    for art in articles:
        try:
            if art.get("url_real_quelle") in ("redirect", "rss_source"):
                stats["uebersprungen"] += 1
                continue

            url = art.get("url", "") or ""
            article_id = extract_gnews_id(url)
            real, quelle = "", ""

            cached = cache.get(article_id) if article_id else None
            if cached and cached.get("url_real"):
                real, quelle = cached["url_real"], "redirect"
                stats["cache"] += 1
            elif not article_id:
                # Kein Google-News-Link -> URL ist bereits echt
                if normalize_domain(url):
                    real, quelle = url, "redirect"
            elif session is not None:
                budget_over = budget_seconds is not None and (time.time() - started) > budget_seconds
                lookup_over = max_lookups is not None and lookups >= max_lookups
                if not (budget_over or lookup_over):
                    lookups += 1
                    real, quelle = resolve_google_news_url(url, session=session, sleep=sleep)
                    if real:
                        cache[article_id] = {"url_real": real, "quelle": "redirect",
                                             "geprueft_am": today}
                    if sleep:
                        time.sleep(sleep)

            if real:
                art["url_real"] = real
                art["domain"] = normalize_domain(real)
                art["url_real_quelle"] = "redirect"
            else:
                dom = domain_from_source(art.get("source", ""))
                art["url_real"] = ""
                art["domain"] = dom
                art["url_real_quelle"] = "rss_source" if dom else "unaufgeloest"
            art["url_real_geprueft_am"] = today
            stats[art["url_real_quelle"]] += 1
        except Exception as exc:  # Presse-Lauf darf nie am Aufloesen scheitern
            art.setdefault("url_real", "")
            art.setdefault("domain", domain_from_source(art.get("source", "")))
            art["url_real_quelle"] = art.get("url_real_quelle") or "unaufgeloest"
            art["url_real_geprueft_am"] = today
            stats["fehler"] += 1
            if verbose:
                print("    WARN: URL-Aufloesung fehlgeschlagen: %s" % str(exc)[:80])
    return stats


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
        "press_query_regime": PRESS_QUERY_REGIME,
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
    # Review-Fix 2026-06-12: wirklich NEUE Artikel je Brand sammeln (Basis fuer
    # Event-Emission; vorher wurde gegen die auf 80 Artikel gekappte .previous.json
    # verglichen -> Artikel ab Position 81 jede Nacht erneut als Event emittiert).
    new_by_brand = {}
    new_history_entries = []
    for brand in BRANDS:
        key = brand["key"]
        name = brand["name"]
        for a in all_brands.get(key, []):
            norm = re.sub(r'[^a-z0-9]', '', a.get("title", "").lower())[:60]
            dedup_key = (key, norm)
            if dedup_key not in existing_keys:
                entry = {
                    "brand": key,
                    "brand_name": name,
                    "title": a.get("title", ""),
                    "url": a.get("url", ""),
                    "date": a.get("date", ""),
                    "source": a.get("source", ""),
                    "type": a.get("type", "media"),
                    "topics": a.get("topics", []),
                    "crawl_date": today,
                }
                existing_articles.append(entry)
                new_history_entries.append(entry)
                existing_keys.add(dedup_key)
                new_by_brand.setdefault(key, []).append(a)
                new_count += 1

    # ── Echte Artikel-URLs aufloesen (Google-News-Redirects) ─────────────
    # Nur fuer die neuen Eintraege; Altbestand macht scripts/backfill_press_urls.py.
    # Fehler hier duerfen den Presse-Lauf nie abbrechen.
    if new_history_entries:
        try:
            budget = float(os.environ.get("PRESS_URL_BUDGET_SECONDS", "600"))
            url_cache = load_url_cache()
            res_stats = enrich_article_urls(
                new_history_entries, cache=url_cache, budget_seconds=budget,
            )
            save_url_cache(url_cache)
            print("URL-Aufloesung: %s" % ", ".join(
                "%s=%d" % (k, v) for k, v in sorted(res_stats.items())) or "-")
        except Exception as exc:
            print("WARN: URL-Aufloesung uebersprungen: %s" % str(exc)[:120])

    # Nach Datum sortieren (neueste zuerst)
    existing_articles.sort(key=lambda x: (x.get("date") or ""), reverse=True)  # None-sicher (Review-Fix)

    # Max 6 Monate Retention
    cutoff_6m = (datetime.now(timezone.utc) - timedelta(days=180)).strftime("%Y-%m-%d")
    existing_articles = [a for a in existing_articles if (a.get("date") or "9999") >= cutoff_6m]  # None-sicher (Review-Fix)

    # Max 2000 Artikel insgesamt
    if len(existing_articles) > 2000:
        existing_articles = existing_articles[:2000]

    history_path.write_text(json.dumps(existing_articles, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Presse-History: %d neue Artikel, %d total (max 6 Monate)" % (new_count, len(existing_articles)))


    # ── Event-Emission für Korrelations-Engine ───────────────────────────
    if HAS_EVENTS:
        print("\n--- Event-Emission ---")
        event_count = 0

        for brand in BRANDS:
            key = brand["key"]
            name = brand["name"]
            # Review-Fix 2026-06-12: "neu" = neu gegenueber der ungekappten
            # press_history.json (Dedup-Set), nicht gegenueber der auf 80
            # Artikel gekappten .previous.json (verursachte Phantom-Events).
            new_articles = [a for a in new_by_brand.get(key, []) if a.get("date")]
            
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

                    # Beitragsanpassung? Dann ZUSAETZLICH ein eigenes, datiertes
                    # Preisereignis schreiben. Das Presse-Event bleibt bestehen -
                    # die Meldung ist beides, und die beiden Modelle lesen
                    # getrennte Ereignistypen.
                    ist_bap, richtung = erkenne_beitragsanpassung(article.get("title", ""))
                    if ist_bap:
                        emit_event(
                            event_type="price_announcement",
                            brand=name,
                            source="google_news_rss",
                            crawler="update_press",
                            magnitude=1.0,
                            url=article.get("url", ""),
                            sentiment=("negative" if richtung == "hoch"
                                       else "positive" if richtung == "runter" else "neutral"),
                            detail={
                                "title": article.get("title", "")[:120],
                                "date": article.get("date", ""),
                                "media_source": article.get("source", ""),
                                "richtung": richtung or "unbekannt",
                                "hinweis": ("Angekuendigte Beitrags-/Praemienanpassung aus der "
                                            "Presseauswertung. KEIN gemessener Preis - das Datum "
                                            "ist das Meldedatum, nicht zwingend der Wirksamkeitstag. "
                                            "Richtung 'unbekannt' heisst: der Titel gibt sie nicht her."),
                            },
                        )
                        event_count += 1

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
                        "url_real": art.get("url_real", ""),
                        "domain": art.get("domain", ""),
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
