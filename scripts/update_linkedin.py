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
sich sonst wortlos mit Exit 0. Grund: SerpAPI-Kontingent (die ~10 Abfragen je
Lauf teilen sich das Budget mit dem GEO-Tool). FORCE_LINKEDIN=1 erzwingt einen
Lauf, z. B. fuer den allerersten.

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


def serpapi(query, key, fenster):
    # 18.08.2026, Befund Paul nach dem ersten Lauf ("haben wirklich alle genau
    # 10 Posts?"): Sieben Marken mit EXAKT 10 Treffern - das war die Google-
    # Seitengroesse, keine Zaehlung. num=20 hatte Google schlicht ignoriert.
    # Drei Aenderungen, alle zum gleichen API-Preis (SerpAPI rechnet pro Suche
    # ab, nicht pro Ergebnis):
    #   num=100    bis zu 100 Treffer je Abfrage statt der 10er-Seite
    #   filter=0   Googles Aehnlichkeits-Ausduennung aus - die frisst bei
    #              site:-Abfragen sonst still Ergebnisse
    #   qdr:w      NACH dem Erstlauf nur noch die letzte Woche: so ist der
    #              Fund-Tag hoechstens ~7 Tage nach dem Post (dokumentierter
    #              Versatz), und der alte Monats-Backlog kann nicht bei jedem
    #              Lauf als neuer "Ereignis-Schub" wiederauftauchen - genau
    #              das Import-Artefakt, das die Engine beim Erstlauf abfangen
    #              musste. Der ERSTE Lauf (kein STATE) holt weiter qdr:m als
    #              Archiv-Grundstock.
    q = urllib.parse.urlencode({
        "engine": "google", "q": query, "hl": "de", "gl": "de",
        "num": "100",
        "filter": "0",
        # 18.08.2026 (Opus-Review #6): Fenster haengt jetzt am TATSAECHLICHEN
        # Abstand zum letzten Lauf (Parameter), nicht mehr an der Existenz der
        # State-Datei - ein verlorener Nightly-Commit erzwang sonst still ein
        # neues Monatsfenster.
        "tbs": ("qdr:w" if fenster == "woche" else "qdr:m"),
        "api_key": key,
    })
    req = urllib.request.Request("https://serpapi.com/search.json?" + q,
                                 headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


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
    for brand, query in BRANDS:
        try:
            res = serpapi("site:linkedin.com/posts %s" % query, key, fenster)
        except Exception as e:
            print("[LinkedIn] %s: Abfrage fehlgeschlagen: %s" % (brand, str(e)[:100]))
            fehler += 1
            fehler_texte.append("%s: %s" % (brand, str(e)[:80]))
            continue
        # 18.08.2026 (Opus-Review #5): SerpAPI transportiert Fehler auch in einer
        # HTTP-200-Antwort. "Keine Ergebnisse" ist ein gueltiges leeres Ergebnis;
        # alles andere (Kontingent, Parameter) ist ein Abfragefehler und darf den
        # Wochentakt nicht fortschreiben - sonst faellt eine Woche still aus.
        _err = res.get("error")
        if _err and "any results" not in str(_err):
            print("[LinkedIn] %s: SerpAPI-Fehler: %s" % (brand, str(_err)[:100]))
            fehler += 1
            fehler_texte.append("%s: %s" % (brand, str(_err)[:80]))
            continue
        treffer = res.get("organic_results") or []
        n_neu = 0
        seen_b = bekannt.setdefault(brand, set())
        for t in treffer:
            url = kanon_url(t.get("link"))
            if not url or not ist_linkedin(url) or url in seen_b:
                continue
            seen_b.add(url)
            datum = parse_datum(t.get("date"))
            post = {
                "url": url, "brand": brand,
                "title": (t.get("title") or "")[:300],
                "snippet": (t.get("snippet") or "")[:500],
                "date": datum,                 # Erscheinungstag, wenn parsebar
                "first_seen": heute,           # Fund-Tag (immer)
                "quelle": "serpapi_google",
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
                            "fenster": fenster},
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
                                     "neu": len(neu), "fehler": fehler,
                                     "fehler_texte": fehler_texte[:10]},
                         ensure_ascii=False), encoding="utf-8")
    elif fehler:
        print("[LinkedIn] WARNUNG: %d/%d Abfragen fehlgeschlagen — Takt NICHT "
              "fortgeschrieben, naechster Nightly versucht erneut." % (fehler, len(BRANDS)))
    print("[LinkedIn] fertig: %d neue Posts, %d Abfragefehler" % (len(neu), fehler))
    return 0


if __name__ == "__main__":
    sys.exit(main())
