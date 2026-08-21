#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LinkedIn-Aktivitaet je Marke sammeln (18.08.2026, Pauls Auftrag).

Was das ist — und was es ehrlich NICHT ist
------------------------------------------
LinkedIn laesst sich nicht direkt crawlen: kein oeffentlicher Such-API-Zugang,
aggressive Bot-Abwehr, und die Nutzungsbedingungen verbieten Scraping. Der
gangbare Weg (mit Paul am 18.08.2026 abgestimmt): die GOOGLE-SUCHE nach
oeffentlichen LinkedIn-Posts befragen, via SerpAPI — derselbe Schluessel, den
das GEO-Tool nutzt. Abfrage je Marke: site:linkedin.com/posts "<Marke>" ...

Das findet, was oeffentlich UND von Google indexiert ist — die reichweiten-
starken Posts, nicht jeder Beitrag. Keine Like-/Kommentarzahlen. Diese
Untererfassung steht im Reiter, nicht nur hier im Docstring.

Takt: WOECHENTLICH (montags), obwohl der Nightly taeglich laeuft — das Skript
prueft selbst, ob seit dem letzten Lauf 6+ Tage vergangen sind, und beendet
sich sonst wortlos mit Exit 0. Grund: SerpAPI-Kontingent — seit dem
20.08.2026 blaettert der Sammler bis zu fuenf Seiten je Marke, ein Lauf kostet
also bis zu 50 Suchen statt 10 (in ruhigen Wochen deutlich weniger, weil bei
der ersten nicht vollen Seite abgebrochen wird). Das Budget teilt er sich mit
dem GEO-Tool und dem Instagram-Sammler. FORCE_LINKEDIN=1 erzwingt einen Lauf.

Ausgabe:
- data/linkedin_posts.jsonl   ein Post pro Zeile, dedupliziert ueber die URL
- shared/events.jsonl         event_type "linkedin_post" je NEUEM Post —
                              damit laeuft LinkedIn automatisch in ALLE
                              Rechnungen des Korrelationsreiters ein
                              (SoV-Impact, Zitatanteil-Impact, Schichtungen)

Datierung: SerpAPI liefert zu manchen Treffern ein Datum ("vor 3 Tagen",
"12.08.2026", "Aug 12, 2026"). Parsebar -> detail.date, und die Korrelations-
Engine datiert das Event auf den Erscheinungstag um (MEDIA_DATED_TYPES).
Nicht parsebar -> Event traegt den Fund-Tag; die Engine zaehlt diese
Fallback-Faelle sichtbar mit. Ein Post kann Tage vor seiner Indexierung
erschienen sein — auch das ist eine bekannte Traegheit dieser Quelle.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from shared.event_emitter import emit_event
    HAS_EVENTS = True
except ImportError:
    HAS_EVENTS = False

OUT = Path("data/linkedin_posts.jsonl")
STATE = Path("data/linkedin_state.json")

# Dieselben zehn Marken wie der Presse-Crawl (update_press.py), mit
# Suchzusatz gegen Mehrdeutigkeit ("ergo" ist auch ein Adverb).
BRANDS = [
    ("ERGO",          '"ERGO" Versicherung'),
    ("Allianz",       '"Allianz" Versicherung'),
    ("AXA",           '"AXA" Versicherung'),
    ("HUK-Coburg",    '"HUK-Coburg"'),
    ("Generali",      '"Generali" Versicherung'),
    ("Signal Iduna",  '"Signal Iduna"'),
    ("R+V",           '"R+V" Versicherung'),
    ("DEVK",          '"DEVK"'),
    ("Hannoversche",  '"Hannoversche" Versicherung'),
    ("CosmosDirekt",  '"CosmosDirekt"'),
]

MONATE_EN = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def parse_datum(s):
    """SerpAPI-Datumsstring -> YYYY-MM-DD oder None. Keine Raterei: was nicht
    sicher parsebar ist, bleibt None (die Engine zaehlt Fallbacks sichtbar)."""
    if not s:
        return None
    s = str(s).strip()
    heute = datetime.now(timezone.utc)
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0)[:10]
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", s)
    if m:
        return "%s-%02d-%02d" % (m.group(3), int(m.group(2)), int(m.group(1)))
    m = re.match(r"^([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})$", s)
    if m and m.group(1).lower() in MONATE_EN:
        return "%s-%02d-%02d" % (m.group(3), MONATE_EN[m.group(1).lower()], int(m.group(2)))
    m = re.match(r"^(?:vor\s+)?(\d+)\s+(Tag|Tagen|day|days)", s, re.I)
    if m:
        return (heute - timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")
    if re.match(r"^(?:vor\s+)?\d+\s+(Stunde|Stunden|hour|hours|Minute|Minuten|minute|minutes)", s, re.I):
        return heute.strftime("%Y-%m-%d")
    m = re.match(r"^(?:vor\s+)?(\d+)\s+(Woche|Wochen|week|weeks)", s, re.I)
    if m:
        return (heute - timedelta(days=7 * int(m.group(1)))).strftime("%Y-%m-%d")
    return None


def kanon_url(u):
    """URL-Normalisierung fuers Dedup: Query/Fragment ab, Slash am Ende ab."""
    if not u:
        return None
    u = u.split("?")[0].split("#")[0].rstrip("/")
    return u


def ist_linkedin(u):
    """Echte Host-Pruefung statt Substring (Opus-Review #16 - 
    'linkedin.com.boese.example' passierte den alten in-Test)."""
    try:
        p = urllib.parse.urlparse(u)
        return (p.scheme == "https" and
                (p.netloc == "linkedin.com" or p.netloc.endswith(".linkedin.com")))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 20.08.2026 (Pauls Auftrag): Jeder Post bekommt drei ableitbare Merkmale mit -
# Absender, Absender-Typ und Post-Typ. Ziel dahinter: nicht nur "LinkedIn wirkt
# / wirkt nicht", sondern "WELCHE Art von Post wirkt". Dafuer muessen die
# Merkmale IM EVENT stehen, sonst kann die Korrelations-Engine spaeter nicht
# danach schichten.
#
# Alles wird aus Titel, Snippet und URL abgeleitet - der Post-Volltext liegt
# uns nicht vor. Das ist eine Heuristik, keine Inhaltsanalyse; sie steht im
# Reiter auch so dran. Dieselben Regeln laufen im Dashboard (linkedin_tab.js)
# noch einmal zur Laufzeit, damit auch die 76 Posts aus dem Erstlauf - die
# diese Felder noch nicht tragen - eingeordnet werden.
MEDIEN_SLUGS = ("versicherungsbote", "horizont", "frankfurter-allgemeine-zeitung",
                "handelsblatt", "wirtschaftswoche", "procontra", "asscompact",
                "versicherungswirtschaft", "cash-online", "fondsprofessionell")

# Offizielle Markenauftritte - exakte Slugs, damit "peterjungallianz" (ein
# Vertreter) nicht als Konzernaccount durchgeht.
MARKEN_ACCOUNTS = (
    "ergo-group-ag", "ergo-oesterreich", "ergo-versicherung", "ergo-direkt", "dkv",
    "allianz", "allianz-deutschland", "allianz-se", "axa", "axa-deutschland",
    "huk-coburg", "generali-deutschland", "generali", "signal-iduna",
    "r-v-versicherung", "devk", "hannoversche", "cosmosdirekt",
)

def absender(url, titel):
    """(Handle, Typ). Typ: Unternehmensaccount | Mitarbeitende | Vertriebspartner
    | Fachmedien | Sonstige.

    20.08.2026 nachgeschaerft, nachdem der erste Wurf ergo-oesterreich als
    "Vertriebspartner" einsortierte, nur weil im Titel "volksbank" stand: Ueber
    den Absender entscheidet der SLUG, nicht der Text des Posts. Wer postet,
    steht in der URL; wovon er schreibt, ist eine andere Frage."""
    m = re.search(r"/posts/([^_/]+)_", url or "")
    slug = urllib.parse.unquote(m.group(1)) if m else ""
    s = slug.lower()
    if not slug:
        return "", "Sonstige"
    if any(w in s for w in MEDIEN_SLUGS):
        return slug, "Fachmedien"
    if s in MARKEN_ACCOUNTS:
        return slug, "Unternehmensaccount"
    if re.search(r"generalvertretung|agentur|gesch(ae)?ftsstelle|hauptvertretung|volksbank|sparkasse|makler|bezirksdirektion", s):
        return slug, "Vertriebspartner"
    # Personen-Slugs: "vorname-nachname" oder mit LinkedIn-Hash am Ende.
    if re.search(r"-[0-9a-z]{6,}$", s) or s.count("-") >= 1:
        return slug, "Mitarbeitende"
    return slug, "Sonstige"


# Reihenfolge zaehlt: die erste passende Regel gewinnt.
POST_TYPEN = [
    ("Recruiting & Karriere", r"\bm/w/d\b|karriere|jobs?\b|stelle\b|bewerb|werde\s|ausbildung|dualesstudium|wir suchen|join|hiring|arbeitgeber"),
    ("Unternehmensnews & Zahlen", r"quartal|halbjahr|gesch(ae|ä)ftsjahr|financialresults|bilanz|umsatz|gewinn|vorstand|aufsichtsrat|ernennung|uebernahme|übernahme|fusion|rekord"),
    ("Studie & Daten", r"studie|umfrage|report\b|analyse|tacho|barometer|trendwende|zeigt.{0,15}dass|index\b"),
    ("Auszeichnung & Test", r"testsieger|auszeichnung|award|pr(ae|ä)miert|note\s+sehr\s+gut|zertifi|siegel"),
    ("Event & Netzwerk", r"messe|kongress|tagung|maklertreff|netzwerk|treffen|konferenz|roadshow|stand\b|event"),
    ("Kooperation & Partner", r"kooperation|partnerschaft|gemeinsam mit|zusammenarbeit|volksbank|sparkasse"),
    ("Standort & Vertrieb", r"generalvertretung|neuer standort|er(oe|ö)ffnung|neues kapitel|gesch(ae|ä)ftsstelle"),
    ("Nachhaltigkeit & Engagement", r"nachhaltig|klima|esg|spende|ehrenamt|soziales|diversity|inklusion"),
    ("Ratgeber & Wissen", r"tipps?\b|ratgeber|wissen|erkl(ae|ä)r|warum |so geht|checkliste|finanzbildung|worauf"),
    # 20.08.2026 nachgeschaerft: "versicherung" allein reicht NICHT - das Wort
    # steht in fast jedem Firmennamen ("ERGO Versicherung AG ..."), und der
    # erste Wurf sortierte dadurch die Haelfte aller Posts als "Produkt" ein.
    # Jetzt braucht es ein echtes Produktsignal.
    ("Produkt & Beratung", r"tarif|absicherung|vorsorge|schadenfall|leistung(en)?\b|police|versichert\b|sch(ue|ü)tzt|deckung|pr(ae|ä)mie|neue[rs]? produkt"),
]

def post_typ(titel, snippet):
    """Heuristik aus Titel + Snippet. Kein Volltext - deshalb gibt es bewusst
    einen ehrlichen Rest: Titel wie "Beitrag von Max Mustermann" tragen kein
    inhaltliches Signal, und die als "Produkt" zu raten waere schlechter als
    zuzugeben, dass man es nicht weiss."""
    t = ((titel or "") + " " + (snippet or "")).lower()
    for name, pat in POST_TYPEN:
        if re.search(pat, t):
            return name
    if re.match(r"^\s*beitrag von\b", (titel or "").lower()) and len((snippet or "").strip()) < 40:
        return "Ohne Textsignal"
    return "Sonstiges"


THEMEN = [
    ("Kfz", r"\bkfz\b|auto|mobilit|e-auto|verbrenner|motorrad"),
    ("Gesundheit & Kranken", r"krank|gesundheit|zahn|pflege|klinik|dkv"),
    ("Leben & Vorsorge", r"lebensvers|rente|vorsorge|altersvorsorge|berufsunf|hinterblieben"),
    ("Wohnen & Sach", r"hausrat|geb(ae|ä)ude|wohn|haftpflicht|elementar|unwetter"),
    ("Recht", r"rechtsschutz|recht\b|urteil"),
    ("Reise", r"reise|urlaub"),
    ("Gewerbe & Firmen", r"gewerbe|firmenkunden|unternehmen.{0,10}versicher|betriebs|cyber"),
]

def thema(titel, snippet):
    t = ((titel or "") + " " + (snippet or "")).lower()
    for name, pat in THEMEN:
        if re.search(pat, t):
            return name
    return ""


# 20.08.2026, Pauls Entscheidung nach einem Befund, der einen frueheren Fix
# widerlegt hat: BIS ZU FUENF SEITEN je Marke.
#
# Vorgeschichte: Am 18.08. fielen Paul "genau 10 Posts je Marke" auf. Meine
# Antwort damals war num=100 - und die war falsch. Google hat den Parameter
# num im September 2025 abgeschafft (SerpAPI fuehrt dazu ein offenes Ticket
# "Only 10 results when num=100 is set"). Ich hatte an einer Stellschraube
# gedreht, die es nicht mehr gibt, und das Ergebnis nicht nachgemessen. Der
# Deckel blieb: im Lauf vom 20.08. landeten die aktivsten Marken erneut auf
# exakt 10 - also systematisch untererfasst, und zwar ausgerechnet die
# Spitzenreiter, auf die es im Markenvergleich ankommt.
#
# Der einzige Weg an mehr Treffer ist Blaettern (start=10, 20, ...), und jede
# Seite ist eine eigene SerpAPI-Suche. Deshalb zwei Grenzen:
#   Seiten je Marke   gestaffelt (siehe unten)
#   frueher Abbruch   eine nicht volle Seite heisst: mehr gibt es nicht.
#                     Das kostet nichts und spart in ruhigen Wochen fast alles.
#   BUDGET_JE_LAUF    harte Obergrenze, damit kein Fehler das Kontingent leert.
#
# 20.08.2026, Pauls Entscheidung nach dem gemessenen Tiefentest ("im freien
# Kontingent bleiben"): Fuenf Seiten fuer alle zehn Marken waeren bis zu 433
# Suchen im Monat - das freie Kontingent liegt bei 250. Also gestaffelt.
#
# Der Tiefentest vom 20.08. hat auch gezeigt, WO die Kappung wehtut: ERGO hatte
# auf LinkedIn neun Posts in der Woche (Vorrat erschoepft, wir hatten alle),
# Allianz mindestens 37 bei nur zehn erfassten. Die Untererfassung trifft also
# die grossen Wettbewerber - genau die Zellen, aus denen der Markenvergleich
# seine Aussage zieht. Deshalb bekommen die Kern-Marken Tiefe, der Rest bleibt
# bei einer Seite und wird im Reiter als moeglicherweise gekappt ausgewiesen.
KERN_MARKEN = ("ERGO", "Allianz", "AXA", "HUK-Coburg")
SEITEN_KERN = 4          # 4 Marken x 4 Seiten = 16
SEITEN_UEBRIGE = 1       # 6 Marken x 1 Seite  =  6   -> 22 je Lauf und Plattform
BUDGET_JE_LAUF = 25      # Notbremse: nie mehr als das, egal was passiert
TREFFER_JE_SEITE = 10   # Googles feste Seitengroesse, seit num=100 weg ist


def seiten_fuer(brand):
    """Wie tief wird fuer diese Marke geblaettert?"""
    return SEITEN_KERN if brand in KERN_MARKEN else SEITEN_UEBRIGE


def serpapi_seite(query, key, fenster, start):
    """Eine Ergebnisseite. start=0 ist die erste, dann 10, 20, ..."""
    q = urllib.parse.urlencode({
        "engine": "google", "q": query, "hl": "de", "gl": "de",
        # num ist bewusst NICHT mehr gesetzt - der Parameter ist wirkungslos
        # (siehe oben) und wuerde nur vortaeuschen, es sei etwas geregelt.
        "filter": "0",   # Googles Aehnlichkeits-Ausduennung aus; wirkt weiterhin
        # 20.08.2026: deutschsprachig einschraenken. Im Tiefentest gemessen -
        # ohne diese Grenze gingen Plaetze an gleichnamige Treffer aus anderen
        # Maerkten (Allianz Parque, Sao Paulo; Allianz Life, USA). Bei zehn
        # Plaetzen je Seite ist jeder davon zu teuer fuer ein Fussballstadion.
        # Preis der Regel: ein deutscher Absender, der englisch postet, faellt
        # heraus. Das ist bei einem Deutschland-Vergleich der bessere Fehler.
        "lr": "lang_de",
        "start": str(start),
        # Fenster haengt am TATSAECHLICHEN Abstand zum letzten Lauf, nicht an
        # der Existenz der State-Datei - ein verlorener Nightly-Commit erzwang
        # sonst still ein neues Monatsfenster.
        "tbs": ("qdr:w" if fenster == "woche" else "qdr:m"),
        "api_key": key,
    })
    req = urllib.request.Request("https://serpapi.com/search.json?" + q,
                                 headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


def serpapi(query, key, fenster, max_seiten=SEITEN_KERN):
    """Blaettert bis zu max_seiten durch.
    -> (treffer, fehlertext_oder_None, anzahl_suchen, erschoepft)

    "erschoepft" beantwortet die Frage, auf die es fuer die Anzeige ankommt:
    Haben wir aufgehoert, weil GOOGLE nichts mehr hatte (True), oder weil
    unser Seitenbudget zu Ende war (False)? Nur im zweiten Fall ist die Zahl
    eine Untergrenze. Vorher wurde das aus der Trefferzahl geschaetzt
    ("volle Ausbeute = gekappt") - das ging schief, sobald das Dedup ueber
    die Seiten hinweg ein paar Wiederholungen entfernte: Allianz kam am
    20.08. mit 37 statt 40 Treffern zurueck und galt damit faelschlich als
    vollstaendig, obwohl vier von vier erlaubten Seiten voll waren.

    "Keine Ergebnisse" ist KEIN Fehler, sondern das Ende der Liste. Alles
    andere (Kontingent, Parameter) ist einer und wird nach oben gereicht -
    damit ein leerer Lauf nie als erfolgreicher durchgeht."""
    alle, gesehen, anzahl_suchen = [], set(), 0
    erschoepft = False
    for i in range(max_seiten):
        antwort = serpapi_seite(query, key, fenster, i * TREFFER_JE_SEITE)
        anzahl_suchen += 1
        fehlertext = antwort.get("error")
        if fehlertext:
            if "any results" in str(fehlertext):
                erschoepft = True
                break
            return alle, str(fehlertext), anzahl_suchen, erschoepft
        seite = antwort.get("organic_results") or []
        frisch = [t for t in seite if t.get("link") not in gesehen]
        for t in seite:
            gesehen.add(t.get("link"))
        alle.extend(frisch)
        # Nicht volle Seite oder nur Wiederholungen: hier ist Schluss. Google
        # liefert bei site:-Abfragen gern dieselbe Seite noch einmal statt
        # einer leeren - beides heisst dasselbe.
        if len(seite) < TREFFER_JE_SEITE or not frisch:
            erschoepft = True
            break
    return alle, None, anzahl_suchen, erschoepft


def main():
    key = os.environ.get("SERPAPI_KEY", "").strip()
    if not key:
        print("[LinkedIn] Kein SERPAPI_KEY gesetzt — Lauf uebersprungen. "
              "Secret SERPAPI_KEY im LLM-Cockpit-Repo hinterlegen (gleicher "
              "Schluessel wie im geo-visibility-tool).")
        return 0

    # Wochen-Takt: fruehestens 6 Tage nach dem letzten erfolgreichen Lauf.
    force = os.environ.get("FORCE_LINKEDIN") == "1"
    heute = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    abstand = None
    if STATE.exists():
        try:
            letzte = json.loads(STATE.read_text(encoding="utf-8")).get("letzter_lauf", "")
            if letzte:
                abstand = (datetime.fromisoformat(heute) -
                           datetime.fromisoformat(letzte)).days
        except Exception:
            pass
    if abstand is not None and abstand < 6 and not force:
        print("[LinkedIn] Letzter Lauf vor %d Tag(en) — naechster fruehestens 6 Tage "
              "spaeter. Uebersprungen (FORCE_LINKEDIN=1 erzwingt)." % abstand)
        return 0
    # Fenster: Woche nur, wenn der letzte Lauf nachweislich hoechstens 8 Tage
    # zurueckliegt - sonst Monat, und die Events tragen das Fenster im detail,
    # damit die Engine undatierte Monats-Batches ausschliessen kann.
    fenster = "woche" if (abstand is not None and abstand <= 8) else "monat"

    # 18.08.2026 (Opus-Review #9): Dedup JE MARKE statt global. Vorher bekam
    # die zuerst abgefragte Marke (ERGO) jeden Mehrmarkennennungs-Post exklusiv
    # zugeschrieben - bei einem Reiter, dessen Kernaussage der Markenvergleich
    # ist, eine systematische Verzerrung zugunsten von ERGO.
    bekannt = {}
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                p = json.loads(line)
                bekannt.setdefault(p.get("brand"), set()).add(kanon_url(p.get("url")))
            except Exception:
                pass

    neu, fehler, fehler_texte = [], 0, []
    gekappt = []   # Marken, bei denen Google noch mehr gehabt haette
    n_suchen = 0   # SerpAPI-Verbrauch dieses Laufs (eine Seite = eine Suche)
    for brand, query in BRANDS:
        try:
            # Budget-Notbremse: schon Verbrauchtes plus die tiefste moegliche
            # Abfrage dieser Marke darf BUDGET_JE_LAUF nicht sprengen. Lieber
            # eine Marke ohne Tiefe als ein leergeraeumtes Kontingent.
            tiefe = seiten_fuer(brand)
            if n_suchen + tiefe > BUDGET_JE_LAUF:
                tiefe = max(0, BUDGET_JE_LAUF - n_suchen)
            if tiefe < 1:
                print("[LinkedIn] %s: Budget von %d Suchen erreicht - uebersprungen."
                      % (brand, BUDGET_JE_LAUF))
                gekappt.append(brand)
                continue
            treffer, fehlertext, seiten, erschoepft = serpapi(
                "site:linkedin.com/posts %s" % query, key, fenster, max_seiten=tiefe)
            n_suchen += seiten
            # Gekappt heisst: nicht Google war am Ende, sondern unser Budget.
            if not erschoepft:
                gekappt.append(brand)
        except Exception as e:
            print("[LinkedIn] %s: Abfrage fehlgeschlagen: %s" % (brand, str(e)[:100]))
            fehler += 1
            fehler_texte.append("%s: %s" % (brand, str(e)[:80]))
            continue
        # 18.08.2026 (Opus-Review #5): SerpAPI transportiert Fehler auch in einer
        # HTTP-200-Antwort. "Keine Ergebnisse" ist ein gueltiges leeres Ergebnis;
        # alles andere (Kontingent, Parameter) ist ein Abfragefehler und darf den
        # Wochentakt nicht fortschreiben - sonst faellt eine Woche still aus.
        if fehlertext:
            print("[LinkedIn] %s: SerpAPI-Fehler: %s" % (brand, str(fehlertext)[:100]))
            fehler += 1
            fehler_texte.append("%s: %s" % (brand, str(fehlertext)[:80]))
            continue
        n_neu = 0
        seen_b = bekannt.setdefault(brand, set())
        for t in treffer:
            url = kanon_url(t.get("link"))
            if not url or not ist_linkedin(url) or url in seen_b:
                continue
            seen_b.add(url)
            datum = parse_datum(t.get("date"))
            _tit = (t.get("title") or "")[:300]
            _snip = (t.get("snippet") or "")[:500]
            _abs, _abs_typ = absender(url, _tit)
            _ptyp = post_typ(_tit, _snip)
            _thema = thema(_tit, _snip)
            post = {
                "url": url, "brand": brand,
                "title": _tit,
                "snippet": _snip,
                "date": datum,                 # Erscheinungstag, wenn parsebar
                "first_seen": heute,           # Fund-Tag (immer)
                "quelle": "serpapi_google",
                "absender": _abs, "absender_typ": _abs_typ,
                "post_typ": _ptyp, "thema": _thema,
            }
            neu.append(post)
            n_neu += 1
            if HAS_EVENTS:
                emit_event(
                    event_type="linkedin_post", brand=brand,
                    source="linkedin_via_google", crawler="update_linkedin",
                    magnitude=1.0, url=url,
                    detail={"title": post["title"], "date": datum,
                            "datierung": ("post" if datum else "erstsichtung"),
                            "fenster": fenster,
                            # Merkmale mit ins Event: nur so kann die
                            # Korrelations-Engine spaeter nach Post-Typ
                            # schichten ("welche Art Post wirkt?").
                            "absender": _abs, "absender_typ": _abs_typ,
                            "post_typ": _ptyp, "thema": _thema},
                )
        print("[LinkedIn] %-13s %d Treffer, %d neu" % (brand, len(treffer), n_neu))

    if neu:
        with open(OUT, "a", encoding="utf-8") as f:
            for p in neu:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
    # Der Lauf zaehlt nur als erfolgt, wenn hoechstens ein Drittel der Abfragen
    # scheiterte (Opus-Review #5: vorher genuegte EINE erfolgreiche von zehn,
    # und neun Marken haetten still eine Woche verloren). Fehlertexte stehen im
    # State, damit der Pipeline-Health-Check sie sieht.
    if len(BRANDS) - fehler >= (2 * len(BRANDS)) // 3:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({"letzter_lauf": heute, "fenster": fenster,
                                     "neu": len(neu), "suchen": n_suchen, "fehler": fehler,
                                     # Marken, bei denen die Ausbeute die
                                     # erlaubte Tiefe voll ausschoepfte - dort
                                     # haette Google mehr gehabt. Der Reiter
                                     # weist diese Zahlen als Untergrenze aus.
                                     "gekappt": sorted(set(gekappt)),
                                     "fehler_texte": fehler_texte[:10]},
                         ensure_ascii=False), encoding="utf-8")
    elif fehler:
        print("[LinkedIn] WARNUNG: %d/%d Abfragen fehlgeschlagen — Takt NICHT "
              "fortgeschrieben, naechster Nightly versucht erneut." % (fehler, len(BRANDS)))
    print("[LinkedIn] fertig: %d neue Posts, %d Abfragefehler" % (len(neu), fehler))
    return 0


if __name__ == "__main__":
    sys.exit(main())
