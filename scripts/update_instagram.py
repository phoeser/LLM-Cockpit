#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Instagram-Aktivitaet je Marke sammeln (20.08.2026, Pauls Auftrag).

Warum dieses Skript aussieht wie update_linkedin.py — und wo es abweicht
----------------------------------------------------------------------
Der Weg ist derselbe: Instagram laesst sich nicht direkt auslesen, also fragen
wir die GOOGLE-SUCHE nach oeffentlichen Beitraegen (site:instagram.com/p/) je
Marke, ueber SerpAPI. Paul am 20.08.2026: ohne offiziellen Account-Zugang, und
die Wettbewerber muessen mit hinein — genau das kann nur der oeffentliche Weg,
denn die offizielle Graph API zeigt ausschliesslich das eigene Konto.

Der Unterschied zu LinkedIn, und er ist wichtig genug fuer den Reiter:
ES GIBT KEINE ENGAGEMENT-ZAHLEN. Am 20.08.2026 an echten Post-URLs geprueft,
mit normaler Browser-Kennung und mit Crawler-Kennung (facebookexternalhit):
Instagram liefert oeffentlich nur die Login-Huelle — kein og:title, kein
og:description, keine like_count/comment_count. Bei LinkedIn stehen genau
diese Zahlen offen auf der Seite, hier nicht. Ein "0 Likes" waere deshalb
erfunden; das Feld existiert hier gar nicht erst.

Was wir bekommen, reicht fuer die eigentliche Frage: WANN hat WER WAS gepostet.
Googles Trefferliste traegt den Beitragstext im Titel ("ERGO Versicherung
Lohfelden | Wir stellen ein! ..."), daraus lassen sich Konto, Post-Typ und
Thema ableiten — und daraus wiederum das Ereignis, mit dem die
Korrelations-Engine rechnet.

Takt: WOECHENTLICH, gleiche Selbstdrosselung wie bei LinkedIn (eigener STATE).
FORCE_INSTAGRAM=1 erzwingt einen Lauf.

Ausgabe:
- data/instagram_posts.jsonl   ein Post pro Zeile, dedupliziert je (Marke, URL)
- shared/events.jsonl          event_type "instagram_post" je NEUEM Post

Kontingent: seit dem 20.08.2026 blaettert der Sammler bis zu fuenf Seiten je
Marke (Pauls Entscheidung, siehe Kommentar bei SEITEN_MAX) - ein Lauf kostet
also bis zu 50 SerpAPI-Suchen statt 10. In ruhigen Wochen deutlich weniger,
weil bei der ersten nicht vollen Seite abgebrochen wird. Dieselbe Kasse wie
LinkedIn und das GEO-Tool; der State-Eintrag "suchen" weist den tatsaechlichen
Verbrauch je Lauf aus. Wenn es eng wird, ist der erste Hebel der Takt
(14-taegig), dann SEITEN_MAX - nicht die Markenzahl.
"""
import json
import os
import re
import sys
import unicodedata
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
try:
    from shared.social_dating import datum_aus_url
except ImportError:                      # Modul fehlt -> alter Zustand, kein Absturz
    datum_aus_url = lambda url, fund_tag=None: None

# Stand der Einordnungs-Regeln. Wird je Beitrag mitgeschrieben, damit das
# Dashboard erkennt, ob eine gespeicherte Einordnung noch der aktuellen Regel
# entspricht - sonst rechnet es sie zur Laufzeit neu. Ohne diese Marke wuerden
# alte Beitraege ihre veraltete Einordnung fuer immer behalten, denn ein
# einmal gefundener Beitrag wird nie noch einmal gecrawlt.
REGELSTAND = "2026-08-20b"

OUT = Path("data/instagram_posts.jsonl")
STATE = Path("data/instagram_state.json")

# Dieselben zehn Marken wie beim Presse- und LinkedIn-Crawl.
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


def norm(s):
    """Schriftschnitt-Spielereien einebnen. Instagram-Bios stecken voller
    mathematischer Fettschrift (20.08.2026 real gesehen: "\U0001d400\U0001d411\U0001d418\U0001d40e
    \U0001d417\U0001d452\U0001d45f\U0001d460..."). Fuer den Menschen ist das "ERGO Versicherung", fuer
    jede Regex ohne Normalisierung sind es voellig andere Zeichen - und der
    Beitrag faellt still in "Sonstiges"."""
    return unicodedata.normalize("NFKC", s or "")


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


def ist_instagram(u):
    """Echte Host-Pruefung statt Substring, und nur Beitrags-URLs
    (/p/ oder /reel/) - Profil- und Story-Links sind keine Posts."""
    try:
        p = urllib.parse.urlparse(u)
        if p.scheme != "https":
            return False
        if not (p.netloc == "instagram.com" or p.netloc.endswith(".instagram.com")):
            return False
        return bool(re.match(r"^/(p|reel)/[A-Za-z0-9_-]+/?$", p.path))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 20.08.2026 (Pauls Auftrag): Jeder Post bekommt ableitbare Merkmale mit -
# Absender, Absender-Typ, Post-Typ, Thema - und ein Relevanz-Urteil. Ziel:
# nicht nur "Instagram wirkt / wirkt nicht", sondern "WELCHE Art von Post
# wirkt". Die Merkmale muessen IM EVENT stehen, sonst kann die
# Korrelations-Engine spaeter nicht danach schichten.
#
# Alles wird aus Titel und Snippet abgeleitet; der Post-Volltext liegt uns
# nicht vor (anders als bei LinkedIn, wo wir die Post-Seite ohnehin fuer die
# Reaktionszahlen abrufen). Das ist eine Heuristik, keine Inhaltsanalyse, und
# steht im Reiter auch so dran.
#
# An echten Google-Treffern kalibriert (20.08.2026: erst 20 Titel von ERGO
# und Allianz, dann am vollen Erstbestand von 100 Beitraegen nachgeschaerft).
# Zwei Befunde aus der ersten Stichprobe, die den Entwurf widerlegt haben:
#
# 1. DER TITEL IST NICHT IMMER DER KONTONAME. Google liefert zwei Formen:
#       "ERGO Versicherung | Der langersehnte #Fruehling steht ..."   <- Konto | Text
#       "Das ERGO Kundenportal Meine Versicherung schnell ..."        <- nur Text
#    Der erste Entwurf nahm bei fehlendem Trenner die ersten 60 Zeichen als
#    Konto - und hielt damit halbe Werbesaetze fuer Accountnamen. Jetzt gilt
#    ein Kontoname nur als solcher, wenn er auch wie einer aussieht
#    (kurz, wenige Woerter, keine Satzzeichen, kein Satzanfangswort).
#
# 2. MARKENNAMEN SIND MEHRDEUTIG. "Allianz" liefert das Fussballstadion
#    Allianz Parque (Sao Paulo), Allianz Life (USA) und spanischsprachige
#    Werbung. Wuerde man das mitzaehlen, haette Allianz per Namensrecht mehr
#    "Aktivitaet" als ERGO - ein systematischer Markenvergleichs-Fehler,
#    nicht nur Rauschen. Deshalb bekommt jeder Post ein Sprach-Urteil; nur
#    deutschsprachige (oder sprachlich neutrale) Posts loesen ein Ereignis
#    aus. Verworfene verschwinden NICHT, sie stehen mit relevant=false und
#    Grund in der Datei und werden im Reiter gezaehlt.
#
# Dieselben Regeln laufen im Dashboard (instagram_tab.js) noch einmal zur
# Laufzeit, damit Altbestand ohne diese Felder nicht leer bleibt.
# ---------------------------------------------------------------------------

# Explizite Handles offizieller Markenkonten. Ergaenzt die Token-Regel unten,
# faengt aber die Faelle ab, die sie nicht kennt.
MARKEN_KONTEN = (
    "ergo", "ergoversicherung", "ergogroup", "ergodeutschland", "ergodirekt",
    "dkv", "dkvdeutschland", "allianz", "allianzdeutschland", "axa",
    "axade", "axadeutschland", "hukcoburg", "generali", "generalideutschland",
    "signaliduna", "ruv", "ruvversicherung", "devk", "hannoversche",
    "cosmosdirekt",
)

# Markenwoerter (normalisiert) und generische Zusaetze. Konto = Marke + nur
# generische Zusaetze -> Unternehmensaccount. Marke + irgendetwas anderes
# (Ort, Personenname) -> Vertriebspartner: genau so heissen die Agenturkonten
# ("ERGO Versicherung Lohfelden", "Allianz Henze & Klassen Aschersleben").
MARKEN_TOKEN = ("ergo", "dkv", "allianz", "axa", "huk", "hukcoburg", "coburg",
                "generali", "signal", "iduna", "signaliduna", "ruv", "rv",
                "devk", "hannoversche", "cosmosdirekt", "cosmos")
GENERISCHE_ZUSAETZE = ("versicherung", "versicherungen", "versicherungsag",
                       "versicherungs", "group", "gruppe", "ag", "se",
                       "deutschland", "de", "official", "offiziell", "karriere",
                       "insurance", "direkt", "vertrieb", "leben", "kranken")

PARTNER_WORT = re.compile(
    r"bezirksdirektion|generalvertretung|agentur|gesch(ae|ä)ftsstelle|vertretung|"
    r"versicherungsb(ue|ü)ro|makler|hauptvertretung|beratungsstelle|"
    r"versicherungsmakler|finanzberatung", re.I)

# Satzanfangswoerter: faengt "Das ERGO Kundenportal ..." ab, das kein Konto ist.
SATZ_START = re.compile(
    r"^(der|die|das|den|dem|ein|eine|einen|einem|wir|ihr|ihre|du|dein|deine|"
    r"mit|bei|f(ue|ü)r|jetzt|heute|hier|so|wenn|weil|am|im|un(ser|sere)|neu|"
    r"neue|mehr|was|wie|warum|wer|wann|ob|und|oder|auch|noch|schon|nur|"
    r"endlich|egal|kein|keine)\b", re.I)


def ist_kontoname(s):
    """Sieht dieser Textteil wie ein Instagram-Kontoname aus - oder wie der
    Anfang eines Werbesatzes? Konservativ: im Zweifel KEIN Konto, dann bleibt
    das Feld leer statt falsch gefuellt."""
    s = (s or "").strip()
    if not (2 <= len(s) <= 50):
        return False
    if len(s.split()) > 5:
        return False
    if re.search(r"[.!?…„“”\"]", s):
        return False
    if SATZ_START.match(s):
        return False
    return True


def titel_teile(titel):
    """(konto, posttext) aus dem Google-Titel.

    Drei Formen kommen vor:
      "<Konto> | <Posttext>"        haeufigste Form
      "<Konto> on Instagram: ..."   englische Oberflaeche
      "<Posttext>"                  gar kein Konto im Titel
    Ohne erkennbares Konto ist der GANZE Titel Posttext - wichtig, weil der
    Post-Typ sonst am Firmennamen statt am Inhalt haengt."""
    t = norm(titel).strip()
    if not t:
        return "", ""
    m = re.match(r"^(.{2,50}?)\s+(?:on|auf)\s+Instagram\s*[:\-]", t, re.I)
    if m:
        return m.group(1).strip(), t[m.end():].strip().strip('"“”').strip()
    if "|" in t:
        links, rechts = t.split("|", 1)
        if ist_kontoname(links):
            return links.strip(), rechts.strip()
    return "", t


def _tokens(konto):
    k = re.sub(r"[^a-z0-9äöüß+ ]", " ", (konto or "").lower())
    k = k.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return [w for w in k.split() if w]


def absender(konto):
    """(Konto, Typ). Ohne erkanntes Konto: "Unbekannt" - nicht geraten."""
    konto = (konto or "").strip()
    if not konto:
        return "", "Unbekannt"
    toks = _tokens(konto)
    flach = "".join(toks)
    if flach in MARKEN_KONTEN:
        return konto, "Unternehmensaccount"
    if PARTNER_WORT.search(konto):
        return konto, "Vertriebspartner"
    marke = [w for w in toks if w in MARKEN_TOKEN]
    if marke:
        rest = [w for w in toks if w not in MARKEN_TOKEN and w not in GENERISCHE_ZUSAETZE]
        return konto, ("Unternehmensaccount" if not rest else "Vertriebspartner")
    return konto, "Mitarbeitende/Sonstige"


# --- Sprach-Urteil (Befund 2 oben) -----------------------------------------
DE_MARKER = re.compile(
    r"\b(der|die|das|den|dem|des|und|oder|nicht|ist|sind|war|wir|ihr|ihre|ihren|"
    r"du|dein|deine|dich|uns|unser|unsere|mit|bei|f(ue|ü)r|auf|aus|vom|zum|zur|"
    r"im|ein|eine|einen|einem|kein|keine|schon|mehr|wie|was|wenn|weil|damit|"
    r"jetzt|heute|hier|sich|auch|noch|sehr|beim|durch|gegen|ohne|(ue|ü)ber|"
    r"versicherung|versicherungen|beratung|kunden|jahre|wir(d|st)|haben|hat)\b",
    re.I)
FX_MARKER = re.compile(
    r"\b(the|and|our|we|you|your|are|for|with|at|from|this|that|about|"
    r"con|nuestro|nuestra|para|por|los|las|el|una|nuestros|"
    r"do|dos|no|na|com|em|mais|que|sua|seu|"
    r"le|les|pour|avec|della|nel|gli|il|"
    r"by|of|to|all|how|what|why|get|more|best|world|now)\b", re.I)
# Buchstaben, die im Deutschen nicht vorkommen - starkes Fremdsprachsignal.
FX_ZEICHEN = re.compile(r"[ãõñçáíóúêôàèìò]", re.I)


def sprachurteil(posttext, snippet, konto):
    """(relevant, grund). Deutsch schlaegt alles; ohne jedes Sprachsignal
    bleibt der Post drin (z.B. reine Agenturnamen wie "Allianz Henze &
    Klassen Aschersleben"). Verworfen wird nur, wo ein Fremdsprachsignal
    steht und KEIN deutsches - so faellt das Stadion Allianz Parque raus,
    ohne dass ein deutscher Post mit englischem Hashtag mitfaellt."""
    t = " ".join([norm(posttext), norm(snippet), norm(konto)])
    if DE_MARKER.search(t):
        return True, "deutsch"
    if FX_ZEICHEN.search(t):
        return False, "fremdsprachige Sonderzeichen"
    if FX_MARKER.search(t):
        return False, "fremdsprachige Signalwoerter"
    return True, "kein Sprachsignal (behalten)"


# Reihenfolge zaehlt: die erste passende Regel gewinnt.
#
# 20.08.2026 an den ERSTEN 100 echten Beitraegen nachkalibriert. Der erste
# Wurf sortierte 57 % aller Beitraege als "Sonstiges" ein - eine Einordnung,
# die vier von sieben Beitraegen nicht einordnet, taugt nicht zum Schichten
# ("welche Art Post wirkt?"). Nach der Nachkalibrierung sind es 18 %.
#
# Was der echte Bestand gezeigt hat und der Entwurf nicht kannte:
#   - Aktions- und Rabatt-Posts sind eine eigene, haeufige Gattung
#     ("Monatspraemien gratis", "bis zu 25 % Nachlass", "BonusDrive").
#   - Service/App-Posts ebenso ("Meine Allianz App", "ERGO Kundenportal").
#   - Ein erheblicher Teil ist Sponsoring: Reitsport, Festivals, Stadion.
#     Ohne eigene Kategorie landete das alles im Restehaufen.
#   - "Beratung", "Baustein", "Schutz" fehlten im Produkt-Muster, obwohl das
#     die haeufigsten Produktwoerter im Bestand sind.
# Die verbleibenden 18 % sind ehrlicher Rest: abgeschnittene Titel,
# Kontaktangaben, allgemeine Markensaetze - da ist nichts zu erkennen.
POST_TYPEN = [
    ("Recruiting & Karriere", r"\bm/w/d\b|karriere|\bjobs?\b|stelle\b|bewerb|ausbildung|duales studium|wir stellen ein|wir suchen|hiring|arbeitgeber|azubi|willkommen im team|neue kolleg|arbeiten bei|mein job|unser team|praktik"),
    ("Aktion & Rabatt", r"\bgratis\b|kostenlos|nachlass|rabatt|\baktion\b|gewinnspiel|sparen|bonus\w*|pr(ae|ä)mien?\s*(frei|gratis)|% \w*sparen|bis zu \d+\s*%|sonderkondition"),
    ("Auszeichnung & Test", r"testsieger|auszeichnung|\baward\b|pr(ae|ä)miert|zertifi|siegel|ausgezeichnet|note sehr gut|\bstiftung warentest\b"),
    ("Unternehmensnews & Zahlen", r"quartal|halbjahr|gesch(ae|ä)ftsjahr|bilanz|umsatz|gewinn\b|vorstand|aufsichtsrat|ernennung|(ue|ü)bernahme|fusion|rekord"),
    ("Studie & Daten", r"studie|umfrage|\breport\b|analyse|tacho|barometer|\bindex\b|zahlen zeigen"),
    ("Jubiläum & Team", r"\d+\s*jahre\b.{0,25}(bei|im team|dabei)|jubil(ae|ä)um|j-u-b-e-l|herzlichen gl(ue|ü)ckwunsch|betriebsjubil"),
    ("Event, Sport & Sponsoring", r"messe|kongress|tagung|maklertreff|netzwerk|konferenz|roadshow|\bevent\b|\barena\b|sponsor|\btickets?\b|turnier|championat|meisterschaft|festival|konzert|reitsport|springreit|dressur|reiterin|wallach|stute|cruise|\bstadion\b|\bliga\b"),
    ("Kooperation & Partner", r"kooperation|partnerschaft|gemeinsam mit|zusammenarbeit|volksbank|sparkasse|partner von"),
    ("Standort & Vertrieb", r"bezirksdirektion|generalvertretung|subdirektion|gesch(ae|ä)ftsstelle|neuer standort|\bstandort\b|er(oe|ö)ffnung|neues kapitel|umzug|neue r(ae|ä)ume"),
    ("Nachhaltigkeit & Engagement", r"nachhaltig|\bklima\b|\besg\b|spende|ehrenamt|soziales engagement|diversity|inklusion|charity"),
    ("Service & App", r"\bapp\b|kundenportal|meine versicherung|meine allianz|online[- ]service|digital(e|es)? (service|zugang)|vertragsunterlagen|versicherungsunterlagen|selfservice|\blogin\b|schaden melden"),
    ("Saison & Gruß", r"frohe (ostern|weihnachten)|frohes neues|fr(ue|ü)hling|sommerzeit|adventszeit|guten rutsch|feiertag|w(ue|ü)nscht (ihnen|euch)|\bsommerpause\b"),
    ("Ratgeber & Wissen", r"tipps?\b|ratgeber|wusstest du|erkl(ae|ä)r|\bwarum\b|so geht|checkliste|finanzbildung|worauf (du|sie)|\bwissen\b|achten sie|darauf kommt es an|grundlagen|ist eigentlich|was tun (bei|wenn)|was ist\b|denk dran|nicht vergessen|swipe|urlaubsbereit|koffer sind gepackt"),
    ("Produkt & Beratung", r"tarif|absicherung|vorsorge|schadenfall|leistung(en)?\b|police|versichert\b|sch(ue|ü)tzt|schutz\b|deckung|pr(ae|ä)mie|neue[rs]? produkt|baustein|beratung|beraten|\bbu\b|berufsunf|kasko|haftpflicht|zahnversicherung|kfz-versicherung|versicherung f(ue|ü)r|abschlie(ss|ß)en|\bschaden\b"),
]


def post_typ(posttext, snippet):
    """Heuristik aus Posttext + Snippet - NICHT aus dem Kontonamen (sonst
    entscheidet der Firmenname ueber den Post-Typ). Kein Volltext, deshalb
    gibt es bewusst einen ehrlichen Rest: Titel ohne inhaltliches Signal als
    "Produkt" zu raten waere schlechter als zuzugeben, dass man es nicht
    weiss."""
    t = (norm(posttext) + " " + norm(snippet)).lower()
    for name, pat in POST_TYPEN:
        if re.search(pat, t):
            return name
    if len(t.strip()) < 25:
        return "Ohne Textsignal"
    return "Sonstiges"


THEMEN = [
    ("Kfz", r"\bkfz\b|\bauto\b|mobilit|e-auto|verbrenner|motorrad|f(ue|ü)hrerschein"),
    ("Gesundheit & Kranken", r"krank|gesundheit|zahn|pflege|klinik|\bdkv\b"),
    ("Leben & Vorsorge", r"lebensvers|rente|vorsorge|altersvorsorge|berufsunf|hinterblieben"),
    ("Wohnen & Sach", r"hausrat|geb(ae|ä)ude|wohn|haftpflicht|elementar|unwetter|bankschliessfach|bankschließfach"),
    ("Recht", r"rechtsschutz|\brecht\b|urteil"),
    ("Reise", r"reise|urlaub"),
    ("Gewerbe & Firmen", r"gewerbe|firmenkunden|betriebs|cyber"),
]


def thema(posttext, snippet):
    t = (norm(posttext) + " " + norm(snippet)).lower()
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
        print("[Instagram] Kein SERPAPI_KEY gesetzt — Lauf uebersprungen. "
              "Secret SERPAPI_KEY im LLM-Cockpit-Repo hinterlegen (gleicher "
              "Schluessel wie im geo-visibility-tool).")
        return 0

    # Wochen-Takt: fruehestens 6 Tage nach dem letzten erfolgreichen Lauf.
    force = os.environ.get("FORCE_INSTAGRAM") == "1"
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
        print("[Instagram] Letzter Lauf vor %d Tag(en) — naechster fruehestens 6 Tage "
              "spaeter. Uebersprungen (FORCE_INSTAGRAM=1 erzwingt)." % abstand)
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

    neu, fehler, fehler_texte, n_weg = [], 0, [], 0
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
                print("[Instagram] %s: Budget von %d Suchen erreicht - uebersprungen."
                      % (brand, BUDGET_JE_LAUF))
                gekappt.append(brand)
                continue
            treffer, fehlertext, seiten, erschoepft = serpapi(
                "site:instagram.com/p %s" % query, key, fenster, max_seiten=tiefe)
            n_suchen += seiten
            # Gekappt heisst: nicht Google war am Ende, sondern unser Budget.
            if not erschoepft:
                gekappt.append(brand)
        except Exception as e:
            print("[Instagram] %s: Abfrage fehlgeschlagen: %s" % (brand, str(e)[:100]))
            fehler += 1
            fehler_texte.append("%s: %s" % (brand, str(e)[:80]))
            continue
        # 18.08.2026 (Opus-Review #5): SerpAPI transportiert Fehler auch in einer
        # HTTP-200-Antwort. "Keine Ergebnisse" ist ein gueltiges leeres Ergebnis;
        # alles andere (Kontingent, Parameter) ist ein Abfragefehler und darf den
        # Wochentakt nicht fortschreiben - sonst faellt eine Woche still aus.
        if fehlertext:
            print("[Instagram] %s: SerpAPI-Fehler: %s" % (brand, str(fehlertext)[:100]))
            fehler += 1
            fehler_texte.append("%s: %s" % (brand, str(fehlertext)[:80]))
            continue
        n_neu = 0
        seen_b = bekannt.setdefault(brand, set())
        for t in treffer:
            url = kanon_url(t.get("link"))
            if not url or not ist_instagram(url) or url in seen_b:
                continue
            seen_b.add(url)
            datum = parse_datum(t.get("date"))
            # 21.08.2026: Liefert Google kein Datum - und das ist der Normalfall
            # (1 von 184 bei LinkedIn, 5 von 274 bei Instagram) -, wird es aus
            # der Beitrags-URL abgeleitet. Beide Plattformen tragen den
            # Erstellungszeitpunkt in der ID; siehe shared/social_dating.py,
            # dort steht auch, wogegen die Deutung geprueft wurde. Kostet keinen
            # zusaetzlichen Abruf. "heute" ist der Fund-Tag und dient als
            # Sicherung: ein spaeteres Datum kann nicht stimmen.
            datierung = "post" if datum else None
            if not datum:
                datum = datum_aus_url(url, heute)
                if datum:
                    datierung = "url"
            if not datierung:
                datierung = "erstsichtung"
            _tit = (t.get("title") or "")[:300]
            _snip = (t.get("snippet") or "")[:500]
            _konto, _ptext = titel_teile(_tit)
            _abs, _abs_typ = absender(_konto)
            _ptyp = post_typ(_ptext, _snip)
            _thema = thema(_ptext, _snip)
            _rel, _grund = sprachurteil(_ptext, _snip, _konto)
            post = {
                "url": url, "brand": brand,
                "title": _tit,
                "post_text": _ptext,           # Titel ohne Kontonamen
                "snippet": _snip,
                "date": datum,                 # Erscheinungstag, wenn parsebar
                "first_seen": heute,           # Fund-Tag (immer)
                "quelle": "serpapi_google", "plattform": "instagram",
                "absender": _abs, "absender_typ": _abs_typ,
                "post_typ": _ptyp, "thema": _thema,
                "regeln": REGELSTAND,
                # Markennamen sind mehrdeutig (Allianz Parque, Allianz Life).
                # Verworfene Posts bleiben in der Datei - sichtbar, nicht still.
                "relevant": _rel, "relevanz_grund": _grund,
            }
            neu.append(post)
            n_neu += 1
            if not _rel:
                n_weg += 1
                continue
            if HAS_EVENTS:
                emit_event(
                    event_type="instagram_post", brand=brand,
                    source="instagram_via_google", crawler="update_instagram",
                    magnitude=1.0, url=url,
                    detail={"title": post["title"], "date": datum,
                            "datierung": datierung,
                            "fenster": fenster,
                            # Merkmale mit ins Event: nur so kann die
                            # Korrelations-Engine spaeter nach Post-Typ
                            # schichten ("welche Art Post wirkt?").
                            "absender": _abs, "absender_typ": _abs_typ,
                            "post_typ": _ptyp, "thema": _thema},
                )
        print("[Instagram] %-13s %d Treffer, %d neu" % (brand, len(treffer), n_neu))

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
                                     "neu": len(neu), "verworfen_sprache": n_weg,
                                     "suchen": n_suchen, "fehler": fehler,
                                     # Marken, bei denen die Ausbeute die
                                     # erlaubte Tiefe voll ausschoepfte - dort
                                     # haette Google mehr gehabt. Der Reiter
                                     # weist diese Zahlen als Untergrenze aus.
                                     "gekappt": sorted(set(gekappt)),
                                     "fehler_texte": fehler_texte[:10]},
                         ensure_ascii=False), encoding="utf-8")
    elif fehler:
        print("[Instagram] WARNUNG: %d/%d Abfragen fehlgeschlagen — Takt NICHT "
              "fortgeschrieben, naechster Nightly versucht erneut." % (fehler, len(BRANDS)))
    print("[Instagram] fertig: %d neue Posts (davon %d ohne Ereignis: "
          "nicht deutschsprachig), %d Abfragefehler" % (len(neu), n_weg, fehler))
    return 0


if __name__ == "__main__":
    sys.exit(main())
