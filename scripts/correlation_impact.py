#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Korrelations-/Impact-Analyse (Event-Study).

Ziel: Schaetzt den Einfluss von Ereignissen (Seitenaenderungen, Presse, News,
neue Seiten, Domain-/Bewertungs-Aenderungen, Preis-Events) auf die LLM-Sichtbarkeit
(Share of Voice, SoV) JE MARKE — methodisch sauber UND ehrlich ueber die Unsicherheit.

Methode (interval-basierte Event-Study):
  1. SoV-Zeitreihe je Marke aus 'sov_change'-Events (metric=share_of_voice_pct, new_pct)
     rekonstruieren -> SoV(brand, measurement_day).
  2. Aufeinanderfolgende Messtage bilden INTERVALLE. Pro Intervall + Marke:
       - delta_sov = SoV(ende) - SoV(start)        (Zielgroesse)
       - count[event_type] = Anzahl Events dieses Typs der Marke im Intervall
         (Events im Fenster [start, ende), inkl. optionalem Lag).
  3. Pro Event-Typ ueber alle (Intervall x Marke)-Punkte:
       - Pearson-Korrelation(count, delta_sov)
       - Event-Study-Mittelwert: mean(delta_sov | count>0) - mean(delta_sov | count==0)
         = durchschnittlicher SoV-Effekt von Intervallen MIT Event ggü. OHNE (in Pp)
       - n = Anzahl Datenpunkte, n_with = Punkte mit Event
  4. KONFIDENZ ehrlich nach Datenmenge (Anzahl SoV-Messtage / Datenpunkte):
       - < 6 Messtage         -> "unzureichend"
       - 6..14 Messtage        -> "vorlaeufig"
       - 15..29 Messtage       -> "moderat"
       - >= 30 Messtage        -> "belastbar"
     (Mit nur wenigen Messpunkten sind alle Werte explizit als vorlaeufig markiert.)

Ausgabe: data/correlation_impact.json  (vom Dashboard gelesen).

Aufruf im Nightly NACH der Event-Sammlung (events.jsonl).
"""
import json
import math
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

EVENTS_FILE = Path("shared/events.jsonl")
HISTORY_FILE = Path("data/sov_history.jsonl")  # dichte SoV-Messreihe (Vorrang)
REVIEW_HISTORY_FILE = Path("data/review_history.json")
OUT_FILE = Path("data/correlation_impact.json")
PRICE_FILE = Path("data/price_comparison.json")  # #17: Preis als Treiber
PEEC_FILE = Path("data/peec_cells.csv")  # Peec-AI-Export (2. Messquelle, 2026-07-15)
PEEC_FOOTPRINT_FILE = Path("data/peec_footprint.json")  # Peec-URL-Footprint (17.07.2026)
PRICE_MANUAL_FILE = Path("data/price_manual.json")  # manuelle Preis-Vollerhebung 14.07.2026

# Optionaler Lag in Tagen: Wirkung tritt evtl. verzoegert auf. 0 = gleiches Intervall.
# ---------------------------------------------------------------------------
# STRUKTURBRUECHE — Definitionsaenderungen, die die Zeitreihe einer Marke
# unstetig machen. Ein Intervall, das ueber ein solches Datum laeuft, misst
# nicht Wirkung, sondern die Umstellung selbst. Es wird deshalb aus dem
# Treibermodell ausgeschlossen (nicht aus der Anzeige).
#
# Warum eine Registry und kein stiller Fix: Solche Bruecke sind der gefaehrlichste
# Fehlertyp in diesem Projekt — sie sehen aus wie ein Effekt. Sie gehoeren
# benannt, datiert und begruendet an EINE Stelle.
STRUCTURAL_BREAKS = [
    {
        "brand": "*",
        "date": "2026-07-21",
        "grund": ("Domain-Aliase zaehlen nicht mehr als Textnennung (Entscheidung Paul, "
                  "Code-Review-Befund A1). Der Matcher lief ueber den ganzen Antworttext "
                  "inklusive Quellenliste — jede zitierte URL zaehlte zusaetzlich als "
                  "Nennung. Gemessen am Lauf 17.07.: 15,2 % aller Nennungen ueber alle "
                  "646 Antworten, auf den 148 UNGEKAPPTEN Antworten sogar 29,7 % (die "
                  "gekappten verlieren ihre Quellenliste, der Wert ist dort untererfasst). "
                  "Wirkung auf den SoV: ERGO 7,01 % -> 7,26 %, Allianz 22,03 % -> 21,33 %. "
                  "Zugleich messen 'Nennungen' und 'Zitate' jetzt getrennte Dinge — vorher "
                  "ueberlappten sie zu rund einem Drittel."),
        "nachrechenbar": False,
        "warum_nicht": ("Wie beim DKV-Bruch: Alt-Laeufe speichern nur 1.500 Zeichen je "
                        "Antwort, 77 % sind gekappt. Eine Neuberechnung saehe nur den "
                        "Anfang. Ab 20.07. werden 20.000 Zeichen gespeichert."),
    },
    {
        "brand": "*",   # betrifft ALLE Marken
        "date": "2026-07-21",
        "grund": ("Markenerweiterung des Crawls von 7 auf 25 Marken (geo-visibility-tool "
                  "ee3c2fb, wirksam mit dem ersten Lauf danach). Share of Voice ist ein "
                  "ANTEIL an allen gezaehlten Nennungen — waechst der Nenner, faellt der "
                  "Wert jeder Marke, ohne dass sich real etwas geaendert haette. "
                  "Simuliert am Lauf 2026-07-17: ERGO 13,96 % (7 Marken) -> 7,01 % "
                  "(25 Marken), Allianz 31,6 % -> 22,0 %. Ein Intervall ueber diesem Datum "
                  "misst die Umstellung, nicht Wirkung."),
        "nachrechenbar": False,
        "warum_nicht": ("Rueckwaerts nicht moeglich: Fuer die 18 neuen Marken existieren in "
                        "den Alt-Laeufen keine Nennungszahlen, sie wurden damals nicht "
                        "gezaehlt. VORWAERTS waere eine durchgehende Reihe herstellbar, indem "
                        "SoV zusaetzlich nur ueber die urspruenglichen 7 Marken gerechnet wird "
                        "— die Einzelzahlen liegen je Lauf vor. Bisher nicht umgesetzt."),
    },
    {
        "brand": "ERGO",
        "date": "2026-07-20",
        "grund": ("DKV aus den ERGO-Aliasen entfernt (Entscheidung Paul). Vorher zaehlte "
                  "jede DKV-Nennung als ERGO-Nennung. Gemessen am Lauf 2026-07-17: "
                  "343 -> 288 Nennungen, also -16 %."),
        "nachrechenbar": False,
        "warum_nicht": ("Alt-Laeufe speichern nur 1.500 Zeichen je Antwort (77 % gekappt); "
                        "eine Neuberechnung saehe nur den Anfang und wuerde die Historie "
                        "beschaedigen. Ab 2026-07-20 werden Volltexte gespeichert, kuenftige "
                        "Definitionsaenderungen sind damit rueckwirkend nachrechenbar."),
    },
]


def _spans_break(brand, start_day, end_day):
    """True, wenn ein Intervall ueber einen Strukturbruch dieser Marke laeuft."""
    for b in STRUCTURAL_BREAKS:
        if b["brand"] not in ("*", brand):
            continue
        if start_day < b["date"] <= end_day:
            return b
    return None


LAG_DAYS = 0
# Event-Typen, deren Wirkung auf SoV untersucht wird (sov_change selbst ist die Zielgroesse).
IMPACT_TYPES = [
    # 20.07.2026: "page_removed" ergaenzt. Die Loeschungs-Erkennung wurde am selben
    # Tag gebaut (geo-visibility-tool 86b1344) und emittiert page_removed-Events —
    # als Treibertyp war der Typ aber nie aufgenommen. Folge: Sobald die ersten
    # Loeschungen auftreten, waeren sie stillschweigend ignoriert worden. Noch gibt
    # es keine (der erste Lauf mit Orphan-Pruefung ist #166), der Typ wird also
    # zunaechst mit n_with_event = 0 gefuehrt und gar nicht ausgewiesen.
    "page_change", "page_new", "page_removed", "press_mention", "news_mention",
    "domain_change", "review_change", "review_volume", "price_change",
    "wikipedia_change", "portal_rank_change", "rating_status_change",
]
# Treiber mit Valenz: Feature wird vorzeichenbehaftet (positiv/negativ aus Event-Sentiment)
SIGNED_DRIVER_TYPES = {"wikipedia_change", "portal_rank_change", "rating_status_change"}
# 2026-06-26 Fix: Die signierte Presse-Aufteilung (media_positive/negative) ERSETZT im
# multivariaten Modell die ungezeichneten press_mention/news_mention; analog ersetzt die
# review_positive/negative-Aufteilung das ungezeichnete review_volume. Beides zusammen ist
# kollinear (positiv+negativ+neutral ~ Presse+News) und erzeugt instabile, scheinbar
# vertauschte Vorzeichen. One-at-a-time-Tabelle (results) zeigt Presse/News weiterhin.
_MV_TYPES = [t for t in IMPACT_TYPES if t not in ("press_mention", "news_mention", "review_volume")] \
    + ["media_positive", "media_negative", "review_positive", "review_negative"]
TYPE_LABEL = {
    "page_change": "Seitenaenderungen (Wettbewerb)",
    "page_new": "Neue Seiten",
    "page_removed": "Geloeschte Seiten",
    "press_mention": "Pressemitteilungen",
    "news_mention": "News-Erwaehnungen",
    "domain_change": "Domain-/Subdomain-Aenderungen",
    "review_change": "Bewertungs-Trend (±)",
    "review_volume": "Bewertungs-Volumen",
    "price_change": "Preis-Aenderungen",
    "wikipedia_change": "Wikipedia-Ausbau (±)",
    "portal_rank_change": "Portal-Rang Check24 (±)",
    "rating_status_change": "Testsieger-/Rating-Trend (±)",
    "media_positive": "Presse/News: Produkt/Strategie",
    "media_negative": "Presse/News: Schaden/Leistung",
    "review_positive": "Positive Bewertungen",
    "review_negative": "Negative Bewertungen",
}


def _day(ts):
    return (ts or "")[:10]


# 17.07.2026 (Audit A2): Marken-Namen aus Events/History normalisieren, damit
# dieselbe Marke nicht doppelt gezaehlt wird ("Cosmos Direkt" vs. "CosmosDirekt").
# .strip() gegen Rand-Whitespace + explizite Alias-Zusammenfuehrung.
_BRAND_ALIASES = {
    "Cosmos Direkt": "CosmosDirekt",
    "cosmos direkt": "CosmosDirekt",
}


def _norm_brand(name):
    if name is None:
        return name
    s = str(name).strip()
    return _BRAND_ALIASES.get(s, s)


def load_events():
    if not EVENTS_FILE.exists():
        print("FEHLER: %s nicht gefunden" % EVENTS_FILE)
        return []
    out = []
    for line in EVENTS_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def build_sov_series_from_history(llm=None):
    """SoV(brand) -> sortierte (day, pct) aus sov_history.jsonl.
    llm=None -> Gesamt-Zeilen (ohne llm-Feld); sonst nur Zeilen des LLMs."""
    if not HISTORY_FILE.exists():
        return {}
    series = {}
    for line in HISTORY_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if (r.get("llm") or None) != llm:
            continue
        day, brand, pct = r.get("date"), _norm_brand(r.get("brand")), r.get("sov_pct")
        if not day or not brand or pct is None:
            continue
        series.setdefault(brand, {})[day] = float(pct)  # letzter Wert/Tag gewinnt
    return {b: sorted(m.items()) for b, m in series.items()}


# Web-gestuetzte (grounded) LLMs — verifiziert aus geo-visibility-tool/analyzer/llm_clients.py:
#   gemini (googleSearch-Tool) + perplexity (Sonar, Web-Suche integriert) = grounded;
#   chatgpt (gpt-4o-mini ohne Suche) + grok = ungrounded (nur Trainingsstand).
# Grounded reagieren schnell auf Content/Presse, ungrounded erst beim naechsten Modell-Update.
GROUNDED_LLMS = {"gemini", "perplexity"}


def _citation_engine_mix(products):
    """Wie viele Zitate stammen aus welcher Engine? (Grundlage der Zirkularitaets-Pruefung)"""
    mix = {}
    for pd in (products or {}).values():
        by = ((pd.get("cited_sources") or {}).get("by_llm") or {})
        for eng, v in by.items():
            # Summe der counts, nicht Anzahl der Domains: cite_share summiert ebenfalls
            # count. Heute identisch (max(count)==1), aber sonst latent inkonsistent.
            if isinstance(v, dict):
                n = v.get("total")
            elif isinstance(v, list):
                n = sum((r or {}).get("count", 1) or 1 for r in v)
            else:
                n = v
            mix[eng] = mix.get(eng, 0) + (n or 0)
    return mix


def _circularity(cite_mix, sov_engines):
    """Anteil der Zitate, der aus genau den Engines stammt, die auch den SoV liefern.

    17.07.2026 — Kern von Review-Punkt 1, jetzt gemessen statt vermutet.
    Der Footprint-Treiber (cite_share) und die Zielgroesse (SoV) werden aus LLM-Antworten
    gebildet. Stammen beide aus DERSELBEN Engine, regressiert das Modell eine Messung
    gegen eine zweite Zusammenfassung derselben Antworten: Eine Antwort, die Allianz
    nennt, verlinkt im selben Atemzug allianz.de. Das erzeugt r-Werte um 0,98, die wie
    ein starker Befund aussehen und keiner sind.

    Am Lauf 2026-07-16 gemessen (60 Zitate: 59 chatgpt, 1 gemini):
        ungrounded (SoV=chatgpt):            98,3 % der Zitate aus derselben Engine
                                             -> r=+0,984, p<0,001   ZIRKULAER
        grounded  (SoV=gemini/perplexity):    1,7 % der Zitate aus derselben Engine
                                             -> r=+0,489, p=0,265   NICHT signifikant
    Der Effekt verschwindet also genau dort, wo er unabhaengig gemessen wird. Solange
    das so ist, darf "Quellpraesenz erklaert den Rueckstand" nicht als Befund
    kommuniziert werden — das Frontend liest dieses Feld und schreibt es dazu.
    """
    total = sum(cite_mix.values()) or 0
    if not total:
        return {"share_same_engine": None, "level": "unknown", "n_citations": 0,
                "note": "Keine Zitate im Lauf — Zirkularitaet nicht pruefbar."}
    same = sum(n for e, n in cite_mix.items() if e in set(sov_engines or []))
    share = same / total
    if share >= 0.5:
        lvl = "high"
        note = ("%.0f %% der Zitate stammen aus derselben Engine, die hier auch die Sichtbarkeit "
                "misst. Treiber und Zielgroesse sind zwei Zusammenfassungen derselben Antworten — "
                "der Zusammenhang ist zu einem unbekannten Teil ein Messartefakt und darf nicht "
                "als Befund gelesen werden.") % (100 * share)
    elif share >= 0.15:
        lvl = "partial"
        note = ("%.0f %% der Zitate stammen aus einer Engine, die hier auch die Sichtbarkeit misst — "
                "der Zusammenhang ist teilweise selbstbezueglich.") % (100 * share)
    else:
        lvl = "none"
        note = ("Nur %.0f %% der Zitate stammen aus einer Engine, die hier auch die Sichtbarkeit misst. "
                "Der Zusammenhang ist in diesem Kanal unabhaengig gemessen.") % (100 * share)
    return {"share_same_engine": round(share, 4), "level": lvl,
            "n_citations": total, "n_same_engine": same,
            "cite_mix": dict(sorted(cite_mix.items(), key=lambda kv: -kv[1])),
            "sov_engines": list(sov_engines or []), "note": note}


def _engines_present(sbl, engines):
    """Nur die Engines, die fuer dieses Produkt wirklich ausgewertet haben.

    17.07.2026. Vorher wurde ueber die KONFIGURIERTE Engine-Liste gemittelt:
        gv = [s.get(e, 0.0) for e in grounded]      # grounded = [gemini, perplexity]
        sov = sum(gv) / len(gv)
    perplexity steht in `llms`, lieferte aber in 0 von 11 Produkten Daten. Sein Fehlen
    ging als 0.0 in den Mittelwert und der Divisor blieb 2 - **jeder grounded-SoV war
    exakt halbiert** (verifiziert an allen 7 Marken: ERGO 4,96 statt 9,92 %).
    Rangfolge und Korrelation bleiben unberuehrt (alle Marken derselbe Faktor), die
    ausgewiesenen Prozentwerte und die Steigung nicht.

    Wichtige Unterscheidung: Eine Engine, die gelaufen ist und die Marke NICHT genannt
    hat, gehoert mit 0.0 in den Mittelwert - das ist ein echtes Ergebnis. Nur eine
    Engine, die gar nicht ausgewertet hat (fehlt in summary_by_llm) oder deren Prompts
    allesamt gescheitert sind (prompts_total == 0, siehe metrics.py-Fix vom selben Tag),
    darf den Nenner nicht aufblaehen. Deshalb wird auf summary_by_llm geprueft und nicht
    auf die Marken-Treffer.
    """
    out = []
    for e in engines:
        blk = (sbl or {}).get(e)
        if not isinstance(blk, dict):
            continue                      # Engine hat fuer dieses Produkt nicht geliefert
        pt = blk.get("prompts_total")
        if pt is not None and pt <= 0:
            continue                      # Engine gelistet, aber alle Prompts gescheitert
        # Dritter Fall, gleiche Klasse: Engine gelistet, prompts_total>0, aber KEINE
        # einzige Marke genannt. pipeline_health.py klassifiziert das als broken_llm.
        # Eine Antwort, in der keine der 7 Marken vorkommt, ist praktisch immer ein
        # Ausfall (Fehlermeldung, Themenverfehlung) - und ginge sonst als "alle Marken
        # bei 0 %" in den Mittelwert. Genau der Halbierungs-Bug in neuer Gestalt.
        _brands = blk.get("brands")
        if isinstance(_brands, list) and _brands and not any(
                (br or {}).get("mentions") or (br or {}).get("share_of_voice") for br in _brands):
            continue
        out.append(e)
    return out


def build_sov_series_for_llms(llm_set):
    """SoV je Marke gemittelt ueber die LLMs in llm_set (z.B. alle grounded).
    Mittelt die per-LLM-SoV pro (Tag, Marke)."""
    if not HISTORY_FILE.exists() or not llm_set:
        return {}
    series = {}
    for line in HISTORY_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        llm = r.get("llm")
        if not llm or llm not in llm_set:
            continue
        day, brand, pct = r.get("date"), _norm_brand(r.get("brand")), r.get("sov_pct")
        if not day or not brand or pct is None:
            continue
        series.setdefault(brand, {}).setdefault(day, []).append(float(pct))
    out = {}
    for b, m in series.items():
        out[b] = sorted((d, sum(v) / len(v)) for d, v in m.items())
    return out


def list_llms_in_history():
    out = set()
    if not HISTORY_FILE.exists():
        return []
    for line in HISTORY_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("llm"):
            out.add(r["llm"])
    return sorted(out)


def build_sov_series(events):
    """SoV(brand) -> sortierte Liste (day, pct) aus sov_change-Events (Fallback)."""
    series = {}
    for e in events:
        if e.get("event_type") != "sov_change":
            continue
        d = (e.get("detail") or {})
        if d.get("metric") != "share_of_voice_pct":
            continue
        pct = d.get("new_pct")
        if pct is None:
            continue
        day = _day(e.get("timestamp"))
        brand = _norm_brand(e.get("brand"))
        if not day or not brand:
            continue
        series.setdefault(brand, {})[day] = float(pct)
    # je Marke: nach Tag sortierte (day, pct)
    out = {}
    for b, m in series.items():
        out[b] = sorted(m.items())
    return out


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


# t-kritische Werte (zweiseitig, 95%-Konfidenz) nach Freiheitsgraden df.
# Fuer kleine Stichproben deutlich groesser als der Normalwert 1.96 -> ehrlich breitere
# Konfidenzintervalle. df>30: Normalapproximation 1.96.
_T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
        8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145,
        15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
        21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056,
        27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042}


def t_critical(df):
    if df < 1:
        return None
    if df > 30:
        return 1.96
    return _T95[df]


def spearman(xs, ys):
    """Spearman-Rangkorrelation (robust bei nullinflationierten Zaehldaten,
    Review-Fix 2026-06-04: Pearson auf Counts war hebelpunkt-getrieben)."""
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    return pearson(ranks(list(xs)), ranks(list(ys)))


def type_confidence(n_with):
    """Konfidenz JE EVENT-TYP nach effektiver Stichprobe (Intervalle mit Event)."""
    if n_with < 5:
        return "unzureichend"
    if n_with < 10:
        return "vorlaeufig"
    if n_with < 20:
        return "moderat"
    return "belastbar"


def _days_between(a, b):
    from datetime import date as _date
    try:
        return max((_date.fromisoformat(b) - _date.fromisoformat(a)).days, 1)
    except Exception:
        return 1


def confidence(n_measure_days):
    if n_measure_days < 6:
        return ("unzureichend", "Zu wenige SoV-Messpunkte fuer eine belastbare Aussage.")
    if n_measure_days < 15:
        return ("vorlaeufig", "Erste Tendenz — noch nicht statistisch belastbar.")
    if n_measure_days < 30:
        return ("moderat", "Tendenz mit mittlerer Sicherheit.")
    return ("belastbar", "Ausreichend Messpunkte fuer eine belastbare Aussage.")



def _content_key(e):
    """Stabiler Schluessel zur Dedup von Wieder-Emissionen.
    Presse/News: ein Artikel = ein Event (ueber alle Tage). Sonst: pro Tag."""
    d = e.get("detail") or {}
    cid = e.get("url") or d.get("url") or d.get("title") or e.get("id")
    t = e.get("event_type")
    if t in ("press_mention", "news_mention"):
        return (t, e.get("brand"), cid)
    return (t, e.get("brand"), cid, _day(e.get("timestamp")))


def dedup_impact_events(events):
    """Behaelt je content_key die FRUEHESTE Instanz (entfernt taegliche Re-Emissionen
    von Presse/News etc.). Liefert nur IMPACT_TYPES-Events zurueck."""
    seen = {}
    for e in events:
        t = e.get("event_type")
        if t not in IMPACT_TYPES:
            continue
        if e.get("crawler") == "update_domain_footprint" and t in ("page_new", "page_change", "page_removed"):
            continue
        if not e.get("brand") or not _day(e.get("timestamp")):
            continue
        # 20.07.2026 Review-Fix: Die SoV-Reihen normalisieren die Marke (_norm_brand),
        # die Event-Seite tat es nicht. events.jsonl enthaelt beide Schreibweisen —
        # "CosmosDirekt" 1.017x und "Cosmos Direkt" 405x. Die 405 wurden nie gefunden,
        # also als "0 Ereignisse" behandelt: 351 Impact-Events fielen still weg und
        # verduennten die Effekte Richtung Null. Genau das Anti-Muster, das dieses
        # Projekt sonst ueberall bekaempft. Einmal hier zentral normalisieren wirkt
        # auf alle nachgelagerten Aggregationen.
        e = dict(e)
        e["brand"] = _norm_brand(e["brand"])
        k = _content_key(e)
        ts = e.get("timestamp", "")
        if k not in seen or ts < seen[k].get("timestamp", ""):
            seen[k] = e
    return list(seen.values())



import math as _math


def _norm_cdf(z):
    return 0.5 * (1.0 + _math.erf(z / _math.sqrt(2.0)))


def _mat_inv(A):
    n = len(A)
    M = [list(A[i]) + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        d = M[c][c] or 1e-12
        M[c] = [v / d for v in M[c]]
        for r in range(n):
            if r != c and M[r][c]:
                fct = M[r][c]
                M[r] = [M[r][k] - fct * M[c][k] for k in range(2 * n)]
    return [row[n:] for row in M]


def _design(points_raw, use, feature_key, twoway=True):
    """Zwei-Wege-Within-Transform (Marke + Zeit) + Standardisierung. Liefert Y, Xs, sd."""
    n = len(points_raw)
    def xv(p, t):
        return (p.get(feature_key) or p.get("x") or {}).get(t, 0)
    def grand(g):
        return sum(g(p) for p in points_raw) / n
    def gmeans(g, key):
        acc, cnt = {}, {}
        for p in points_raw:
            k = p.get(key); acc[k] = acc.get(k, 0.0) + g(p); cnt[k] = cnt.get(k, 0) + 1
        return {k: acc[k] / cnt[k] for k in acc}
    def tw(g):
        gm = grand(g); bm = gmeans(g, "brand"); tm = gmeans(g, "time") if twoway else {}
        return [g(p) - bm.get(p["brand"], gm) - (tm.get(p.get("time"), gm) - gm if twoway else 0)
                for p in points_raw]
    Y = tw(lambda p: p["y"])
    Xc = [tw((lambda tt: (lambda p: xv(p, tt)))(t)) for t in use]
    X = [[Xc[j][i] for j in range(len(use))] for i in range(n)]
    sd = []
    for j in range(len(use)):
        col = [X[i][j] for i in range(n)]
        v = sum(c * c for c in col) / max(n - 1, 1)
        sd.append(v ** 0.5 if v > 1e-12 else 1.0)
    Xs = [[X[i][j] / sd[j] for j in range(len(use))] for i in range(n)]
    # 20.07.2026 Review-Fix: Der Zwei-Wege-Within-Transform verbraucht Parameter, die
    # in m (Zahl der Treiber) nicht auftauchen: (Marken-1) + (Zeitpunkte-1). Wurden sie
    # bei den Freiheitsgraden ignoriert, war sigma zu klein und JEDES Konfidenzintervall
    # zu schmal — am Hauptmodell gemessen um 12 %. Genau dadurch galt "review_positive"
    # als einziger gesicherter Treiber. Mit korrekten df schliesst sein Intervall die
    # Null nicht mehr aus.
    k_abs = (len({p["brand"] for p in points_raw}) - 1)
    if twoway:
        k_abs += (len({p.get("time") for p in points_raw}) - 1)
    return Y, Xs, sd, max(k_abs, 0)


def _ridge_posterior(Xs, Y, lam, center=None, k_absorbed=0):
    """Analytisches Bayes-Posterior der ridge-Regression.
    Rueckgabe: beta (Posterior-Mittel, standardisiert), Ainv, sigma2."""
    n = len(Xs); m = len(Xs[0]) if Xs else 0
    A = [[sum(Xs[i][a] * Xs[i][b] for i in range(n)) + (lam if a == b else 0.0)
          for b in range(m)] for a in range(m)]
    rhs = [sum(Xs[i][a] * Y[i] for i in range(n)) for a in range(m)]
    if center:
        for a in range(m):
            rhs[a] += lam * center[a]
    Ainv = _mat_inv(A)
    beta = [sum(Ainv[a][b] * rhs[b] for b in range(m)) for a in range(m)]
    yhat = [sum(Xs[i][a] * beta[a] for a in range(m)) for i in range(n)]
    ss = sum((Y[i] - yhat[i]) ** 2 for i in range(n))
    # df: Treiber (m) PLUS die vom Within-Transform absorbierten Fixed Effects.
    sig2 = ss / max(n - m - k_absorbed, 1)
    return beta, Ainv, sig2


def _apply_fdr(res, key="wild_cluster_p", out="wild_cluster_p_fdr", alpha=0.05):
    """Benjamini-Hochberg ueber ALLE Between-Tests im Ergebnisbaum.

    17.07.2026, Review #3: "Keine Mehrfachtest-Korrektur - 130 Effekte mit
    prob_direction, 74 als signifikant ausgewiesen." Wer genug Effekte rechnet, findet
    zwangslaeufig welche. Bei 130 Tests und alpha=0,05 sind rund 7 Zufallstreffer zu
    erwarten - man weiss nur nicht, welche.

    BH kontrolliert die False-Discovery-Rate: Von den als signifikant ausgewiesenen
    Effekten sind im Erwartungswert hoechstens alpha falsch positiv. Weniger streng als
    Bonferroni und fuer diesen Zweck das passende Mass - wir wollen Kandidaten finden,
    nicht eine einzelne Hypothese absichern.

    Gerechnet wird ueber die Wild-Cluster-p-Werte (nicht ueber prob_direction): Nur die
    sind echte p-Werte. prob_direction ist ein Posterior-Mass und war ausserdem in 61
    von 130 Faellen exakt 1,0.
    """
    found = []

    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get(key), (int, float)):
                found.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(res)
    if not found:
        return res
    ordered = sorted(found, key=lambda d: d[key])
    n = len(ordered)
    # BH: q_i = min over j>=i von (p_j * n / j), monoton von hinten
    prev = 1.0
    for i in range(n - 1, -1, -1):
        q = min(prev, ordered[i][key] * n / (i + 1))
        ordered[i][out] = round(min(q, 1.0), 4)
        prev = q
    for d in ordered:
        d["fdr_note"] = ("Benjamini-Hochberg ueber die %d Between-Tests dieses Modellblocks. "
                         "Signifikant nach Korrektur: %s (alpha=%.2f). "
                         "EINSCHRAENKUNG: BH setzt unabhaengige (oder positiv abhaengige) Tests "
                         "voraus. Die Kanaele hier sind es nicht - 'combined' ist eine Mischung "
                         "aus 'grounded' und 'ungrounded' und teilt deren Daten. Die Korrektur "
                         "ist deshalb eine Naeherung; q-Werte knapp um 0,05 nicht ueberinterpretieren."
                         % (n, "ja" if d[out] < alpha else "nein", alpha))
        d["fdr_n_tests"] = n
        d["fdr_family"] = "Between-Tests dieses Modellblocks (Kanaele nicht unabhaengig)"
    return res


def _cluster_robust_var(Xs, Y, beta, Ainv, clusters, k_absorbed=0):
    """Cluster-robuste Sandwich-Varianz. Rueckgabe: (V, G) oder (None, G).

    17.07.2026, Review #3. Vorher: sig2 = ss/(n-m) — iid-Residualvarianz. Die
    unterstellt, dass jede Zelle eine unabhaengige Beobachtung ist. Sie ist es nicht:
    Die 77 Zellen stammen aus 7 Marken; Zellen derselben Marke sind korreliert. Die
    Freiheitsgrade rechneten mit n=53 statt mit 7 Marken, die Themen-Fixed-Effects
    waren nicht abgezogen. Nachgerechnet: SE_iid 0,044 vs. SE_cluster 0,073 - Faktor 1,6.

    Cluster = Marke. Kleinstichproben-Korrektur wie ueblich: G/(G-1) * (n-1)/(n-m).
    ACHTUNG: Mit G=7 ist die asymptotische Cluster-Inferenz unzuverlaessig (Faustregel
    G>=30). Deshalb wird zusaetzlich der Wild-Cluster-Bootstrap gerechnet, siehe
    _wild_cluster_p(); der ist bei kleinem G das richtige Werkzeug.
    """
    n = len(Xs); m = len(Xs[0]) if Xs else 0
    if not n or not m:
        return None, 0
    resid = [Y[i] - sum(Xs[i][a] * beta[a] for a in range(m)) for i in range(n)]
    scores = {}
    for i in range(n):
        g = clusters[i]
        row = scores.setdefault(g, [0.0] * m)
        for a in range(m):
            row[a] += Xs[i][a] * resid[i]
    G = len(scores)
    if G < 2:
        return None, G
    meat = [[0.0] * m for _ in range(m)]
    for row in scores.values():
        for a in range(m):
            for b in range(m):
                meat[a][b] += row[a] * row[b]
    c = (G / (G - 1.0)) * ((n - 1.0) / max(n - m - k_absorbed, 1))
    V = [[c * sum(Ainv[a][k] * meat[k][l] * Ainv[l][b]
                  for k in range(m) for l in range(m)) for b in range(m)] for a in range(m)]
    return V, G


def _wild_cluster_p(Xs, Y, Ainv_unused, clusters, j, lam, max_exact=12):
    """Wild-Cluster-Bootstrap (Rademacher, restringiert auf H0: beta_j = 0).

    Bei kleinem G (hier 7 Marken) ist das der Standard statt asymptotischer
    Cluster-SE. Charme dieser Fallzahl: Mit G Clustern gibt es nur 2^G Vorzeichen-
    Vektoren - bei G=7 also 128. Die zaehlen wir VOLLSTAENDIG durch, statt zufaellig
    zu ziehen. Der Test ist damit exakt und reproduzierbar (kein Seed noetig).

    Grenze der Methode, die mitberichtet wird: Der kleinstmoegliche p-Wert ist
    1/2^G = 0,0078 bei G=7. Ein Effekt kann hier also nie "p < 0,001" erreichen,
    egal wie stark er ist. Das ist keine Schwaeche des Effekts, sondern der Fallzahl.
    """
    n = len(Xs); m = len(Xs[0]) if Xs else 0
    gs = sorted({c for c in clusters})
    G = len(gs)
    if G < 2:
        return None, G, None

    def _fit(yv):
        b, Ai, _ = _ridge_posterior(Xs, yv, lam)
        V, _ = _cluster_robust_var(Xs, yv, b, Ai, clusters)
        if V is None or V[j][j] <= 0:
            return None
        return b[j] / (V[j][j] ** 0.5)

    t_obs = _fit(Y)
    if t_obs is None:
        return None, G, None

    # Restringiertes Modell: Spalte j raus -> Residuen unter H0
    idx = [a for a in range(m) if a != j]
    Xr = [[row[a] for a in idx] for row in Xs]
    br, _, _ = _ridge_posterior(Xr, Y, lam)
    yhat_r = [sum(Xr[i][a] * br[a] for a in range(len(idx))) for i in range(n)]
    ur = [Y[i] - yhat_r[i] for i in range(n)]

    gi = {g: k for k, g in enumerate(gs)}
    hits = 0; total = 0
    if G <= max_exact:
        # Exakte Enumeration aller 2^G Vorzeichen-Vektoren (bei G<=12 bezahlbar).
        masks = range(1 << G)
    else:
        # 18.07.2026: Fuer G>12 (Peec-26-Modell, G=26) ist die vollstaendige
        # Enumeration zu teuer (2^26 = 67 Mio Fits). Deterministische Rademacher-
        # Stichprobe: fester Seed 42, 4095 Draws (= 2^12 - 1). Reproduzierbar trotz
        # Sampling; kleinstmoeglicher p-Wert entsprechend ~1/4096.
        import random as _rnd
        _r = _rnd.Random(42)
        masks = [_r.getrandbits(G) for _ in range(4095)]
    for mask in masks:
        w = [1.0 if (mask >> gi[clusters[i]]) & 1 else -1.0 for i in range(n)]
        ystar = [yhat_r[i] + w[i] * ur[i] for i in range(n)]
        t_b = _fit(ystar)
        if t_b is None:
            continue
        total += 1
        if abs(t_b) >= abs(t_obs) - 1e-12:
            hits += 1
    if not total:
        return None, G, None
    return hits / total, G, round(t_obs, 3)


def multivariate_impact(points_raw, min_with=6, candidate_types=None, feature_key="x",
                        prior_mean=None, **_kw):
    """Bayesianische Panel-Regression (Marken- + Zeit-Fixed-Effects).
    - Schaetzt alle Treiber GLEICHZEITIG (isolierte Effekte).
    - Analytisches Posterior -> Glaubwuerdigkeitsintervall + P(Effekt>0).
    - Partial Pooling: prior_mean (= Gesamteffekt) zieht Segment-Schaetzer zum
      gemeinsamen Wert (leiht Staerke; stabilisiert duenne Segmente)."""
    cand = candidate_types or IMPACT_TYPES
    def _xv(p, t):
        return (p.get(feature_key) or p.get("x") or {}).get(t, 0)
    brands = sorted({p["brand"] for p in points_raw})
    use = [t for t in cand if sum(1 for p in points_raw if _xv(p, t) != 0) >= min_with]
    if len(points_raw) < 8 or len(brands) < 1 or not use:
        return {"available": False,
                "note": "Zu wenige Datenpunkte/Marken fuer das multivariate Modell.",
                "n_points": len(points_raw), "n_brands": len(brands),
                "types_used": use, "coefficients": {}}
    Y, Xs, sd, k_abs = _design(points_raw, use, feature_key)
    m = len(use)
    lam = len(Xs) * 0.5
    center = None
    if prior_mean:
        center = [(prior_mean.get(use[j], 0.0)) * sd[j] for j in range(m)]
    beta, Ainv, sig2 = _ridge_posterior(Xs, Y, lam, center, k_absorbed=k_abs)

    MIN_NWITH, MIN_NPTS, MIN_TIMES = 15, 20, 12
    n_times = len({p.get("time") for p in points_raw})
    enough_data = len(points_raw) >= MIN_NPTS and n_times >= MIN_TIMES

    coeffs = {}
    for j, t in enumerate(use):
        mu = beta[j] / sd[j]
        var = max(sig2 * Ainv[j][j], 0.0)
        sigma = (var ** 0.5) / sd[j]
        if sigma > 1e-12:
            p_pos = _norm_cdf(mu / sigma)
        else:
            p_pos = 1.0 if mu > 0 else 0.0
        p_dir = max(p_pos, 1.0 - p_pos)
        nw = sum(1 for pt in points_raw if _xv(pt, t) != 0)
        coeffs[t] = {
            "label": TYPE_LABEL.get(t, t),
            "coef_pp_per_event_day": round(mu, 4),
            "ci95_low": round(mu - 1.96 * sigma, 4),
            "ci95_high": round(mu + 1.96 * sigma, 4),
            "prob_positive": round(p_pos, 3),
            "prob_direction": round(p_dir, 3),
            "significant": bool(p_dir >= 0.975 and nw >= MIN_NWITH and enough_data),
            "n_with_event": nw,
        }
    coeffs = dict(sorted(coeffs.items(), key=lambda kv: -abs(kv[1]["coef_pp_per_event_day"])))
    excluded = [t for t in IMPACT_TYPES if t not in use]
    exploratory = len(points_raw) < MIN_NPTS or n_times < MIN_TIMES
    return {"available": True,
            "method": "Bayes-Panel-Ridge (Marken-+Zeit-FE, analytisches Posterior, Partial Pooling)",
            "lambda": round(lam, 2),
            "pooled_prior": bool(prior_mean),
            "n_points": len(points_raw), "n_brands": len(brands),
            "types_used": use, "types_excluded_too_few": excluded,
            "exploratory": exploratory,
            "coefficients": coeffs,
            "note": ("EXPLORATIV: zu wenige Intervalle/Messtage fuer gesicherte Aussagen. "
                     if exploratory else "")
                    + "Isolierter Effekt je Kategorie (Bayes, alle gleichzeitig). "
                    "P(Effekt>0) ist die Wahrscheinlichkeit eines positiven Effekts. "
                    "'Gesichert' = P(Richtung) >= 97,5 %, >=15 Intervalle mit Event, "
                    ">=20 Intervalle und >=12 Messtage. Segment-Schaetzer per Partial Pooling "
                    "zum Gesamteffekt stabilisiert."}


def _placebo_fpr(points_raw, use, feature_key, n_perm=200, seed=7, thr=0.975):
    """Permutationstest: y wird zufaellig gemischt -> es sollte (fast) nichts
    'gesichert' sein. Liefert die Falsch-Positiv-Rate (erwartet ~5 %)."""
    import random as _r
    rnd = _r.Random(seed)
    Y, Xs, sd, k_abs = _design(points_raw, use, feature_key)
    n, m = len(Y), len(use)
    if n < 12 or m == 0:
        return None
    lam = n * 0.5
    hits = 0; total = 0
    for _ in range(n_perm):
        Yp = Y[:]; rnd.shuffle(Yp)
        beta, Ainv, sig2 = _ridge_posterior(Xs, Yp, lam, k_absorbed=k_abs)
        for j in range(m):
            sigma = (max(sig2 * Ainv[j][j], 0.0) ** 0.5) / sd[j]
            mu = beta[j] / sd[j]
            if sigma > 1e-12:
                pd = max(_norm_cdf(mu / sigma), 1 - _norm_cdf(mu / sigma))
                if pd >= thr:
                    hits += 1
            total += 1
    return round(hits / total, 4) if total else None


def _oos_skill(points_raw, use, feature_key):
    """Leave-one-time-out: sagt y der ausgelassenen Messperiode aus Marken-Basis +
    Treiber-Effekten (Training) voraus. skill = 1 - SSE_modell/SSE_naiv (>0 = besser
    als die reine Marken-Basislinie)."""
    times = sorted({p.get("time") for p in points_raw})
    if len(times) < 6 or not use:
        return None
    sse_m = 0.0; sse_n = 0.0; n_test = 0
    for hold in times:
        train = [p for p in points_raw if p.get("time") != hold]
        test = [p for p in points_raw if p.get("time") == hold]
        if len(train) < 10 or not test:
            continue
        # Marken-Basis (Mittel je Marke) aus Training
        bm, bc = {}, {}
        for p in train:
            bm[p["brand"]] = bm.get(p["brand"], 0.0) + p["y"]; bc[p["brand"]] = bc.get(p["brand"], 0) + 1
        gmean = sum(p["y"] for p in train) / len(train)
        base = {b: bm[b] / bc[b] for b in bm}
        # Treiber-Effekte (brand-demeaned ridge auf Training)
        Yt, Xt, sdt, _kt = _design(train, use, feature_key, twoway=False)
        beta, _A, _s = _ridge_posterior(Xt, Yt, len(Xt) * 0.5, k_absorbed=_kt)
        def xv(p, t):
            return (p.get(feature_key) or p.get("x") or {}).get(t, 0)
        # mittlere x je Marke (Training) fuer Within-Korrektur der Vorhersage
        xbar = {}
        for t in use:
            for b in base:
                vals = [xv(p, t) for p in train if p["brand"] == b]
                xbar[(b, t)] = sum(vals) / len(vals) if vals else 0.0
        for p in test:
            b = p["brand"]
            pred = base.get(b, gmean)
            for j, t in enumerate(use):
                pred += (beta[j] / sdt[j]) * (xv(p, t) - xbar.get((b, t), 0.0))
            sse_m += (p["y"] - pred) ** 2
            sse_n += (p["y"] - base.get(b, gmean)) ** 2
            n_test += 1
    if n_test < 5 or sse_n <= 0:
        return None
    return {"r2_oos_vs_baseline": round(1 - sse_m / sse_n, 3), "n_test": n_test}


_BKEY2NAME = {"ergo": "ERGO", "allianz": "Allianz", "axa": "AXA", "huk": "HUK-Coburg",
             "generali": "Generali", "signal-iduna": "Signal Iduna", "ruv": "R+V",
             "devk": "DEVK", "hannoversche": "Hannoversche", "cosmosdirekt": "CosmosDirekt"}  # 20.07. Review-Fix: war "Cosmos Direkt" -> Schluessel wurde nie nachgeschlagen, 140 Reviews verloren


def review_posneg_by_day():
    """Positive/negative Einzel-Reviews je (Marke, Tag): >=4 Sterne -> pos, <=2 -> neg
    (3 = neutral, ignoriert). Schliesst eKomi-Aggregate und Berater-Reviews aus
    (zentrale Markensicht, marktvergleichbar)."""
    out = {}
    if not REVIEW_HISTORY_FILE.exists():
        return out
    try:
        rows = json.loads(REVIEW_HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return out
    for r in rows:
        if (r.get("source") or "") in ("eKomi", "Google (Berater)"):
            continue
        if "Aggregiertes Rating" in (r.get("text") or ""):
            continue
        sc = r.get("score")
        if sc is None:
            continue
        try:
            sc = float(sc)
        except (TypeError, ValueError):
            continue
        name = _BKEY2NAME.get(r.get("brand"))
        day = (r.get("date") or r.get("crawl_date") or "")[:10]
        if not name or not day:
            continue
        cell = out.setdefault(name, {}).setdefault(day, {"pos": 0, "neg": 0})
        if sc >= 4:
            cell["pos"] += 1
        elif sc <= 2:
            cell["neg"] += 1
    return out


def analyze(events, llm=None, brand_filter=None, llm_set=None, scope_label=None, prior_mean=None, validate=False):
    # Vorrang: dichte SoV-Historie; Fallback: sov_change-Events (nur Gesamt)
    if llm_set is not None:
        sov = build_sov_series_for_llms(llm_set)
        sov_source = "sov_history_grounding:" + (scope_label or ",".join(sorted(llm_set)))
    else:
        sov = build_sov_series_from_history(llm=llm)
        sov_source = "sov_history" if llm is None else ("sov_history_llm:" + llm)
    if not sov and llm is None and llm_set is None:
        sov = build_sov_series(events)
        sov_source = "sov_change_events"
    mdays = set()
    for ser in sov.values():
        for day, _pct in ser:
            mdays.add(day)
    measure_days = sorted(mdays)
    conf_label, conf_note = confidence(len(measure_days))

    # Event-Counts je (brand, day, type) — DEDUPLIZIERT (Re-Emissionen entfernt).
    # Zusaetzlich (fuer das multivariate Modell): magnitude-gewichtete Summe je Typ
    # + Netto-Medien-Sentiment (positive minus negative Presse/News).
    counts = {}
    wmag = {}
    mpos = {}
    mneg = {}
    for e in dedup_impact_events(events):
        t = e.get("event_type")
        b = e.get("brand")
        day = _day(e.get("timestamp"))
        counts.setdefault(b, {}).setdefault(day, {})
        counts[b][day][t] = counts[b][day].get(t, 0) + 1
        try:
            mg = float(e.get("magnitude") or 1.0)
        except (TypeError, ValueError):
            mg = 1.0
        wmag.setdefault(b, {}).setdefault(day, {})
        _sgn = 1.0
        if t in SIGNED_DRIVER_TYPES:
            _sgn = {"positive": 1.0, "negative": -1.0}.get(e.get("sentiment"), 0.0)
        elif t == "review_change":
            # 2026-06-26: Bewertungs-Aenderung vorzeichenbehaftet -> Richtung der
            # Durchschnitts-Bewertung aus dem Event-Detail (Delta). Wirkt direkt auf
            # bestehende Events (old_value/new_value/change bereits vorhanden).
            _d = e.get("detail") or {}
            _chg = _d.get("change")
            if _chg is None and _d.get("new_value") is not None and _d.get("old_value") is not None:
                try:
                    _chg = float(_d["new_value"]) - float(_d["old_value"])
                except (TypeError, ValueError):
                    _chg = None
            try:
                _chg = float(_chg)
            except (TypeError, ValueError):
                _chg = 0.0
            _sgn = 1.0 if _chg > 0 else (-1.0 if _chg < 0 else 0.0)
        wmag[b][day][t] = wmag[b][day].get(t, 0.0) + (mg if mg > 0 else 1.0) * _sgn
        if t in ("press_mention", "news_mention"):
            sn = e.get("sentiment")
            if sn == "positive":
                mpos.setdefault(b, {})[day] = mpos.setdefault(b, {}).get(day, 0) + 1
            elif sn == "negative":
                mneg.setdefault(b, {})[day] = mneg.setdefault(b, {}).get(day, 0) + 1

    # v2 (Review-Fixes 2026-06-04):
    #  - Intervalle ungleicher Laenge werden auf RATEN pro Tag normalisiert
    #  - Brand-Demeaning: delta je Marke um den Markenmittelwert zentriert
    #    (verhindert Scheinkorrelation durch markenspezifische Trends)
    #  - Spearman statt nur Pearson (robust bei nullinflationierten Counts)
    #  - Standardfehler (SE) des Effekts + Konfidenz JE TYP (aus n_with)
    review_pn = review_posneg_by_day()
    _skipped_breaks = []
    points_raw = []
    for brand, ser in sov.items():
        bydays = counts.get(brand, {})
        for i in range(len(ser) - 1):
            start_day, start_pct = ser[i]
            end_day, end_pct = ser[i + 1]
            days = _days_between(start_day, end_day)
            cnt = {}
            xmv = {}
            for t in IMPACT_TYPES:
                c = 0
                w = 0.0
                for day, tc in bydays.items():
                    if start_day <= day < end_day:
                        c += tc.get(t, 0)
                        w += (wmag.get(brand, {}).get(day, {}) or {}).get(t, 0.0)
                cnt[t] = c / days
                xmv[t] = w / days          # magnitude-gewichtete Rate
            mp = mn = rp = rn = 0
            for day, c in (mpos.get(brand, {}) or {}).items():
                if start_day <= day < end_day:
                    mp += c
            for day, c in (mneg.get(brand, {}) or {}).items():
                if start_day <= day < end_day:
                    mn += c
            for day, c in (review_pn.get(brand, {}) or {}).items():
                if start_day <= day < end_day:
                    rp += c.get("pos", 0); rn += c.get("neg", 0)
            xmv["media_positive"] = mp / days
            xmv["media_negative"] = mn / days
            xmv["review_positive"] = rp / days
            xmv["review_negative"] = rn / days
            # Intervalle ueber einem Strukturbruch messen die Umstellung, nicht Wirkung.
            if _spans_break(brand, start_day, end_day):
                _skipped_breaks.append({"brand": brand, "von": start_day, "bis": end_day})
                continue
            points_raw.append({"brand": brand, "days": days, "time": start_day,
                               "y": (end_pct - start_pct) / days, "x": cnt, "xmv": xmv})
    # Marken-Isolierung (optional): nur Intervalle dieser Marke
    if brand_filter:
        points_raw = [p for p in points_raw if p["brand"] == brand_filter]
    intervals_total = len(points_raw)

    # Brand-Demeaning (bei Einzelmarke = Zentrierung um deren Mittelwert)
    bsum, bn = {}, {}
    for p in points_raw:
        bsum[p["brand"]] = bsum.get(p["brand"], 0.0) + p["y"]
        bn[p["brand"]] = bn.get(p["brand"], 0) + 1
    for p in points_raw:
        p["yc"] = p["y"] - bsum[p["brand"]] / bn[p["brand"]]

    def _var(v, m):
        return sum((a - m) ** 2 for a in v) / (len(v) - 1) if len(v) > 1 else 0.0

    results = {}
    for t in IMPACT_TYPES:
        xs = [p["x"][t] for p in points_raw]
        ys = [p["yc"] for p in points_raw]
        n = len(xs)
        n_with = sum(1 for x in xs if x > 0)
        if n_with == 0:
            continue  # Typ kam in keinem Intervall vor -> nicht ausweisen
        r = pearson(xs, ys)
        rho = spearman(xs, ys)
        with_v = [y for x, y in zip(xs, ys) if x > 0]
        without_v = [y for x, y in zip(xs, ys) if x == 0]
        eff, se = None, None
        if with_v and without_v:
            m1 = sum(with_v) / len(with_v)
            m0 = sum(without_v) / len(without_v)
            eff = m1 - m0
            if len(with_v) > 1 and len(without_v) > 1:
                se = math.sqrt(_var(with_v, m1) / len(with_v) + _var(without_v, m0) / len(without_v))
        ci_low = ci_high = None
        significant = None
        if eff is not None and se is not None and se > 0:
            # Freiheitsgrade konservativ: kleinere der beiden Gruppen - 1
            df = min(len(with_v), len(without_v)) - 1
            tc = t_critical(df)
            if tc is not None:
                ci_low = round(eff - tc * se, 3)
                ci_high = round(eff + tc * se, 3)
                # "gesichert" nur, wenn das (t-basierte) KI die Null ausschliesst
                # UND mindestens 8 Intervalle mit Event vorliegen (Mindest-Datenbasis)
                excludes_zero = (ci_low > 0) or (ci_high < 0)
                significant = bool(excludes_zero and n_with >= 8)
        results[t] = {
            "label": TYPE_LABEL.get(t, t),
            "pearson_r": round(r, 3) if r is not None else None,
            "spearman_r": round(rho, 3) if rho is not None else None,
            "avg_sov_effect_pp": round(eff, 3) if eff is not None else None,
            "effect_se_pp": round(se, 3) if se is not None else None,
            "ci95_low_pp": ci_low,
            "ci95_high_pp": ci_high,
            "significant": significant,
            "n_intervals": n,
            "n_with_event": n_with,
            "type_confidence": type_confidence(n_with),
        }

    # nach |Effekt| sortiert
    ordered = dict(sorted(results.items(),
                          key=lambda kv: -abs(kv[1]["avg_sov_effect_pp"] or 0)))
    # Multivariat: pooled (alle Marken, Within-FE) ODER einzelmarken-zentriert bei brand_filter.
    multivar = multivariate_impact(points_raw, min_with=(4 if brand_filter else 6),
                                   candidate_types=_MV_TYPES,
                                   feature_key="xmv", prior_mean=prior_mean)
    # Validierung (nur Gesamtmodell): Placebo-Falsch-Positiv-Rate + Out-of-Sample-Skill
    validation = None
    if validate and multivar.get("available"):
        _use = multivar.get("types_used") or []
        try:
            validation = {
                "placebo_false_positive_rate": _placebo_fpr(points_raw, _use, "xmv"),
                "out_of_sample": _oos_skill(points_raw, _use, "xmv"),
                "note": "Placebo: erwartet ~0,05 (zufaellige Daten erzeugen kaum 'gesicherte' Effekte). "
                        "Out-of-Sample r2>0 = Treiber sagen SoV besser voraus als die reine Marken-Basislinie.",
            }
        except Exception as _e:
            validation = {"error": str(_e)[:120]}
    # 17.07.2026 (Audit A5): Wenn das Out-of-Sample-R2 <= 0 ist, sagen die Treiber
    # SoV NICHT besser voraus als die reine Marken-Basislinie -> die geschaetzten
    # Einzeleffekte sind nicht belastbar (Spurious-Gefahr, vgl. review_positive).
    # 'significant' NICHT umdefinieren, nur ein zusaetzliches reliable-Flag + Hinweis.
    if validate and isinstance(validation, dict) and multivar.get("available"):
        _oos_r2 = (validation.get("out_of_sample") or {}).get("r2_oos_vs_baseline")
        if _oos_r2 is not None and _oos_r2 <= 0:
            for _c in (multivar.get("coefficients") or {}).values():
                if isinstance(_c, dict):
                    _c["reliable"] = False
                    _prev = _c.get("note")
                    _c["note"] = ((_prev + " ") if _prev else "") + "OOS<=0: Einzeleffekte nicht belastbar"
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": "interval-event-study v2 (Raten/Tag, brand-demeaned, Spearman, SE) + Panel-Ridge multivariat",
        "multivariate": multivar,
        "validation": validation,
        "sov_source": sov_source,
        "lag_days": LAG_DAYS,  # Hauptmodell ohne Versatz; siehe Block "lag_analysis"
        "structural_breaks": STRUCTURAL_BREAKS,
        "intervals_skipped_breaks": _skipped_breaks,
        "sov_measure_days": len(measure_days),
        "sov_measure_range": [measure_days[0], measure_days[-1]] if measure_days else [],
        "brands_with_sov": sorted(sov.keys()),
        "n_intervals_total": intervals_total,
        "confidence": conf_label,
        "confidence_note": conf_note,
        "impact": ordered,
    }



# ── Zitations-Footprint als Level-Treiber (Schicht A, 2026-07-03) ──────────
# Footprint = wie oft die eigene Domain einer Marke in den von den LLMs
# zitierten Quellen auftaucht (Level/Stock). Zellen = Marke x Thema aus
# geo_snapshot.json. Liefert rohe Korrelation + isolierten Within-FE-Effekt.
GEO_SNAPSHOT_FILE = Path("data/geo_snapshot.json")
FP_BRAND_DOMAINS = {
    "ergo.de": "ERGO", "ergo.com": "ERGO", "ergodirekt.de": "ERGO",
    "ergo-reiseversicherung.de": "ERGO",
    "allianz.de": "Allianz", "allianzdirect.de": "Allianz",
    "allianz-reiseversicherung.de": "Allianz",
    "huk.de": "HUK-Coburg", "huk24.de": "HUK-Coburg", "huk-coburg.de": "HUK-Coburg",
    "axa.de": "AXA", "generali.de": "Generali", "signal-iduna.de": "Signal Iduna",
    "cosmosdirekt.de": "CosmosDirekt", "cosmos-direkt.de": "CosmosDirekt",
    "hannoversche.de": "Hannoversche", "ruv.de": "R+V", "devk.de": "DEVK",
    # 18.07.2026: Markenerweiterung Crawl 7->25 (geo-visibility-tool ee3c2fb). Namen
    # exakt wie BRAND_SIZE-Schluessel, sonst filtert footprint_level_analysis sie raus.
    "adac.de": "ADAC", "arag.de": "ARAG", "alte-leipziger.de": "Alte Leipziger",
    "barmenia.de": "Barmenia", "da-direkt.de": "DA Direkt", "debeka.de": "Debeka",
    "diebayerische.de": "Die Bayerische", "die-bayerische.de": "Die Bayerische",
    "gothaer.de": "Gothaer", "hdi.de": "HDI", "hansemerkur.de": "HanseMerkur",
    "lv1871.de": "LV 1871", "vhv.de": "VHV", "wgv.de": "WGV",
    "wuerttembergische.de": "Württembergische", "zurich.de": "Zurich",
}


def _fp_dom2brand(d):
    d = str(d or "").replace("www.", "")
    return FP_BRAND_DOMAINS.get(d)


def footprint_level_analysis():
    """Zitations-Footprint (eigene Domain in LLM-Quellen) als Level-Treiber der
    Sichtbarkeit. Roh-Korrelation + isolierter Effekt (Marken-+Themen-FE)."""
    try:
        g = json.loads(GEO_SNAPSHOT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    products = g.get("products") or {}
    if not products:
        return None
    llms = g.get("llms") or []
    if not llms:
        for pd in products.values():
            for k in (pd.get("summary_by_llm") or {}):
                if k not in llms:
                    llms.append(k)
    grounded = [l for l in llms if l in GROUNDED_LLMS]
    ungrounded = [l for l in llms if l not in GROUNDED_LLMS]
    cells = []
    for pid, pd in products.items():
        cs = pd.get("cited_sources") or {}
        cc = {}
        for row in (cs.get("overall") or []):
            b = _fp_dom2brand(row.get("domain"))
            if b:
                cc[b] = cc.get(b, 0) + (row.get("count") or 0)
        sbl = pd.get("summary_by_llm") or {}
        sov = {}
        for eng in llms:
            for br in ((sbl.get(eng) or {}).get("brands") or []):
                sov.setdefault(br.get("name"), {})[eng] = br.get("share_of_voice") or 0.0
        for b in set(list(sov.keys()) + list(cc.keys())):
            s = sov.get(b, {})
            gv = [s.get(e, 0.0) for e in _engines_present(sbl, grounded)]
            uv = [s.get(e, 0.0) for e in _engines_present(sbl, ungrounded)]
            cells.append({"brand": b, "time": pid, "footprint": cc.get(b, 0),
                          "sov_g": 100.0 * (sum(gv) / len(gv) if gv else 0.0),
                          "sov_u": 100.0 * (sum(uv) / len(uv) if uv else 0.0)})
    if len(cells) < 6:
        return {"available": False, "n_cells": len(cells),
                "note": "Zu wenige Marke-x-Thema-Zellen fuer die Footprint-Analyse."}

    def _target(key):
        xs = [c["footprint"] for c in cells]
        ys = [c[key] for c in cells]
        # Audit A1: Segment ohne einen einzigen Messwert (Engine-Ausfall) NICHT
        # als "0,0 — kein Effekt" ausweisen. Regel: keine Daten ist kein Befund.
        if sum(ys) <= 1e-9:
            return {"available": False,
                    "note": ("Segment ohne Messwerte im Snapshot (Engine-Ausfall?) — "
                             "nicht berechnet (Regel: keine Daten ist kein Befund).")}
        r = pearson(xs, ys)
        rho = spearman(xs, ys)
        pts = [{"brand": c["brand"], "time": c["time"], "y": c[key],
                "x": {"footprint": float(c["footprint"])}} for c in cells]
        within = multivariate_impact(pts, min_with=3, candidate_types=["footprint"], feature_key="x")
        return {"pearson_r": round(r, 3) if r is not None else None,
                "spearman_r": round(rho, 3) if rho is not None else None,
                "within_fe": within}

    per_topic = {}
    for pid in products:
        sub = [c for c in cells if c["time"] == pid]
        if len(sub) >= 3:
            rr = pearson([c["footprint"] for c in sub], [c["sov_g"] for c in sub])
            per_topic[pid] = {"name": products[pid].get("name"),
                              "pearson_r": round(rr, 3) if rr is not None else None, "n": len(sub)}
    return {"available": True, "n_cells": len(cells),
            "n_brands": len({c["brand"] for c in cells}),
            "n_topics": len({c["time"] for c in cells}),
            "grounded": _target("sov_g"), "ungrounded": _target("sov_u"),
            "per_topic_grounded": per_topic,
            "note": ("Zitations-Footprint = wie oft die eigene Domain einer Marke in den von den LLMs "
                     "zitierten Quellen auftaucht (Level, kein Ereignis). 'pearson_r' = roher Zusammenhang "
                     "ueber alle Marke-x-Thema-Zellen. 'within_fe' = isolierter Effekt mit Marken- UND "
                     "Themen-Fixed-Effects (Identifikation ueber Within-Marke-across-Themen-Variation; "
                     "kontrolliert generische Markenprominenz). Quelle: data/geo_snapshot.json.")}




# ── Zitationsanteil je Kategorie + normalisierter cite_share-Treiber (Schritt b, 2026-07-04) ──
def citation_category_analysis():
    """Zitationsanteil je Marke (normalisiert) als Treiber + Kategorien-Mix je Thema."""
    try:
        g = json.loads(GEO_SNAPSHOT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    products = g.get("products") or {}
    if not products:
        return None
    llms = g.get("llms") or []
    if not llms:
        for pd in products.values():
            for k in (pd.get("summary_by_llm") or {}):
                if k not in llms:
                    llms.append(k)
    grounded = [l for l in llms if l in GROUNDED_LLMS]
    ungrounded = [l for l in llms if l not in GROUNDED_LLMS]
    topic_mix = {}
    for pid, pd in products.items():
        cs = pd.get("cited_sources") or {}
        bc = cs.get("by_category") or {}
        shares = {k: round((v or {}).get("share", 0), 1) for k, v in bc.items()}
        portal = (bc.get("portal") or {}).get("share", 0)
        topic_mix[pid] = {"name": pd.get("name"), "total_citations": cs.get("total") or 0,
                          "shares_pct": shares, "portal_dominated": bool(portal >= 30)}
    cells = []
    for pid, pd in products.items():
        cs = pd.get("cited_sources") or {}
        total = cs.get("total") or 0
        cc = {}
        for row in (cs.get("overall") or []):
            b = _fp_dom2brand(row.get("domain"))
            if b:
                cc[b] = cc.get(b, 0) + (row.get("count") or 0)
        sbl = pd.get("summary_by_llm") or {}
        sov = {}
        for eng in llms:
            for br in ((sbl.get(eng) or {}).get("brands") or []):
                sov.setdefault(br.get("name"), {})[eng] = br.get("share_of_voice") or 0.0
        for b in set(list(sov.keys()) + list(cc.keys())):
            s = sov.get(b, {})
            gv = [s.get(e, 0.0) for e in _engines_present(sbl, grounded)]
            uv = [s.get(e, 0.0) for e in _engines_present(sbl, ungrounded)]
            share = (100.0 * cc.get(b, 0) / total) if total else 0.0
            cells.append({"brand": b, "time": pid, "cite_share": share,
                          "sov_g": 100.0 * (sum(gv) / len(gv) if gv else 0.0),
                          "sov_u": 100.0 * (sum(uv) / len(uv) if uv else 0.0)})
    if len(cells) < 6:
        return {"available": False, "n_cells": len(cells), "topic_citation_mix": topic_mix,
                "note": "Zu wenige Zellen fuer den cite_share-Treiber."}

    def _t(key):
        xs = [c["cite_share"] for c in cells]
        ys = [c[key] for c in cells]
        r = pearson(xs, ys); rho = spearman(xs, ys)
        pts = [{"brand": c["brand"], "time": c["time"], "y": c[key],
                "x": {"cite_share": c["cite_share"]}} for c in cells]
        within = multivariate_impact(pts, min_with=3, candidate_types=["cite_share"], feature_key="x")
        return {"pearson_r": round(r, 3) if r is not None else None,
                "spearman_r": round(rho, 3) if rho is not None else None, "within_fe": within}
    return {"available": True, "n_cells": len(cells),
            "topic_citation_mix": topic_mix,
            "cite_share_grounded": _t("sov_g"), "cite_share_ungrounded": _t("sov_u"),
            "note": ("Zitationsanteil je Marke = eigene-Domain-Zitate / alle Zitate im Thema (normalisiert, "
                     "ueber Themen vergleichbar). topic_citation_mix = je Thema Verteilung eigen/wettbewerber/"
                     "portal/sonstige + Flag portal_dominated (>=30% Portal), erklaert wo eigener Footprint "
                     "wenig bewegt (z.B. Reise). Quelle: data/geo_snapshot.json.")}




# ── Level-Modell (Mundlak / Correlated Random Effects) — Schicht A, 2026-07-05 ──
# Erklaert das SoV-NIVEAU (Stock) statt kurzfristiger Bewegungen. Zerlegt den
# Zitations-Footprint (cite_share) in einen WITHIN-Effekt (bewegt eigener Content
# im Thema die Sichtbarkeit?) und einen BETWEEN-Effekt (Marken-Mittel des Footprints
# — erklaert den Autoritaets-/Marken-Vorsprung, warum Allianz > ERGO, statt ihn wie
# ein reiner Marken-FE zu verstecken). Themen-Fixed-Effects bleiben drin.
def _mundlak_between_coef(cells, xkey, ykey):
    """Nur der Between-Koeffizient (fuer Leave-one-brand-out-Robustheit)."""
    brands = sorted({c["brand"] for c in cells})
    topics = sorted({c["topic"] for c in cells})
    n = len(cells)
    if n < 8 or len(brands) < 3 or len(topics) < 2:
        return None
    xb = {}; cb = {}
    for c in cells:
        xb[c["brand"]] = xb.get(c["brand"], 0.0) + c[xkey]; cb[c["brand"]] = cb.get(c["brand"], 0) + 1
    xbar = {b: xb[b] / cb[b] for b in xb}
    W = [c[xkey] - xbar[c["brand"]] for c in cells]
    B = [xbar[c["brand"]] for c in cells]
    Y = [c[ykey] for c in cells]
    def _tdm(v):
        tm = {}; tc = {}
        for c, val in zip(cells, v):
            tm[c["topic"]] = tm.get(c["topic"], 0.0) + val; tc[c["topic"]] = tc.get(c["topic"], 0) + 1
        tmean = {t: tm[t] / tc[t] for t in tm}
        return [val - tmean[c["topic"]] for c, val in zip(cells, v)]
    Yc = _tdm(Y); cols = [_tdm(W), _tdm(B)]
    sd = []
    for col in cols:
        v = sum(x * x for x in col) / max(n - 1, 1)
        sd.append(v ** 0.5 if v > 1e-12 else 1.0)
    Xs = [[cols[j][i] / sd[j] for j in range(2)] for i in range(n)]
    beta, Ainv, sig2 = _ridge_posterior(Xs, Yc, n * 0.1)
    return beta[1] / sd[1]


def _mundlak_fit(cells, xkey, ykey, min_cells=10):
    brands = sorted({c["brand"] for c in cells})
    topics = sorted({c["topic"] for c in cells})
    n = len(cells)
    if n < min_cells or len(brands) < 3 or len(topics) < 2:
        return {"available": False, "n_cells": n,
                "note": "Zu wenige Zellen fuer das Level-Modell."}
    ys = [float(c.get(ykey, 0.0) or 0.0) for c in cells]
    if ys and (max(ys) - min(ys)) < 1e-9:
        _allzero = all(abs(y) < 1e-12 for y in ys)
        return {"available": False, "n_cells": n, "n_brands": len(brands), "n_topics": len(topics),
                "note": ("Keine Daten fuer diesen Kanal: alle SoV-Werte sind 0 "
                         "(LLM-Ausfall - z.B. API-Limit/Fehler). Kein Modell gerechnet."
                         if _allzero else
                         "Zielgroesse ohne Variation in diesem Kanal - kein Modell gerechnet.")}
    xb = {}; cb = {}
    for c in cells:
        xb[c["brand"]] = xb.get(c["brand"], 0.0) + c[xkey]; cb[c["brand"]] = cb.get(c["brand"], 0) + 1
    xbar = {b: xb[b] / cb[b] for b in xb}
    yb = {}; cy = {}
    for c in cells:
        yb[c["brand"]] = yb.get(c["brand"], 0.0) + c[ykey]; cy[c["brand"]] = cy.get(c["brand"], 0) + 1
    ybar = {b: yb[b] / cy[b] for b in yb}
    W = [c[xkey] - xbar[c["brand"]] for c in cells]
    B = [xbar[c["brand"]] for c in cells]
    Y = [c[ykey] for c in cells]
    def _tdm(v):
        tm = {}; tc = {}
        for c, val in zip(cells, v):
            tm[c["topic"]] = tm.get(c["topic"], 0.0) + val; tc[c["topic"]] = tc.get(c["topic"], 0) + 1
        tmean = {t: tm[t] / tc[t] for t in tm}
        return [val - tmean[c["topic"]] for c, val in zip(cells, v)]
    Yc = _tdm(Y); cols = [_tdm(W), _tdm(B)]
    sd = []
    for col in cols:
        v = sum(x * x for x in col) / max(n - 1, 1)
        sd.append(v ** 0.5 if v > 1e-12 else 1.0)
    Xs = [[cols[j][i] / sd[j] for j in range(2)] for i in range(n)]
    lam = n * 0.1
    beta, Ainv, sig2 = _ridge_posterior(Xs, Yc, lam)
    eff = {}
    for j, nm in enumerate(("within", "between")):
        mu = beta[j] / sd[j]
        sigma = (max(sig2 * Ainv[j][j], 0.0) ** 0.5) / sd[j]
        pdir = max(_norm_cdf(mu / sigma), 1.0 - _norm_cdf(mu / sigma)) if sigma > 1e-12 else 1.0
        eff[nm] = {"coef_pp_sov_per_pp_citeshare": round(mu, 3),
                   "ci95_low": round(mu - 1.96 * sigma, 3), "ci95_high": round(mu + 1.96 * sigma, 3),
                   "prob_direction": round(pdir, 3),
                   # 20.07.2026 (Entscheidung Paul, Code-Review-Befund A5):
                   # Hier stand "significant": pdir >= 0.975 — allein aus dem
                   # iid-Posterior, OHNE Cluster-SE, ohne Wild-Cluster-Bootstrap und
                   # ohne Mehrfachtest-Korrektur. Der strengere Pfad (_mundlak_multi)
                   # widerlegte fuenf dieser sieben Flags AUF DENSELBEN DATEN
                   # (z. B. Wild-p = 0,31 gegen "significant: true"). Zwei Felder
                   # gleichen Namens mit gegenlaeufigem Ergebnis in einer Datei sind
                   # gegenueber Aktuaren nicht zu verteidigen. Das Feld heisst jetzt
                   # so, wie es gemeint ist, und das Dashboard rendert es nicht mehr
                   # als "gesichert".
                   "prob_direction_only": bool(pdir >= 0.975),
                   "inferenz_hinweis": ("Nur Bayes-Richtungswahrscheinlichkeit aus dem "
                                        "iid-Posterior — KEIN Signifikanztest. Fuer "
                                        "belastbare Aussagen den Block "
                                        "price_footprint_joint heranziehen, der "
                                        "cluster-robuste SE und Wild-Cluster-Bootstrap "
                                        "rechnet.")}
    def _sdraw(v):
        m = sum(v) / len(v)
        return (sum((x - m) ** 2 for x in v) / max(len(v) - 1, 1)) ** 0.5
    eff["within"]["effect_std_pp"] = round(eff["within"]["coef_pp_sov_per_pp_citeshare"] * _sdraw(W), 2)
    eff["between"]["effect_std_pp"] = round(eff["between"]["coef_pp_sov_per_pp_citeshare"] * _sdraw(B), 2)
    yhat = [sum(Xs[i][j] * beta[j] for j in range(2)) for i in range(n)]
    sse = sum((Yc[i] - yhat[i]) ** 2 for i in range(n)); sst = sum(v * v for v in Yc)
    r2 = round(1 - sse / sst, 3) if sst > 0 else None
    r_raw = pearson([c[xkey] for c in cells], [c[ykey] for c in cells])
    bb = eff["between"]["coef_pp_sov_per_pp_citeshare"]
    lead = max(ybar, key=lambda b: ybar[b])
    gaps = {}
    for b in brands:
        if b == lead:
            continue
        actual = ybar[lead] - ybar[b]; expl = bb * (xbar[lead] - xbar[b])
        gaps[b] = {"vs": lead, "actual_gap_pp": round(actual, 2),
                   "explained_by_footprint_pp": round(expl, 2),
                   # 17.07.2026 (Audit A4): share_explained bei 1.0 kappen (>100 % ist
                   # ein Overfitting-Symptom auf nur 7 Marken, vgl. Audit-Punkt E7).
                   "share_explained": round(min(expl / actual, 1.0), 2) if abs(actual) > 1e-6 else None}
    auth = sorted(brands, key=lambda b: -xbar[b])
    _loo = []
    for _drop in brands:
        _bc = _mundlak_between_coef([c for c in cells if c["brand"] != _drop], xkey, ykey)
        if _bc is not None:
            _loo.append(round(_bc, 3))
    _blo = ({"min": min(_loo), "max": max(_loo),
            "sign_stable": bool(all(x > 0 for x in _loo) or all(x < 0 for x in _loo))} if _loo else None)
    return {"available": True, "n_cells": n, "n_brands": len(brands), "n_topics": len(topics),
            "exploratory": bool(len(topics) < 12),
            "raw_pearson_r": round(r_raw, 3) if r_raw is not None else None,
            "within_effect": eff["within"], "between_effect": eff["between"],
            "r2_within_topics": r2, "leader": lead, "between_loo": _blo, "gap_decomposition": gaps,
            "authority_ranking": [{"brand": b, "mean_cite_share_pct": round(xbar[b], 2),
                                   "mean_sov_pct": round(ybar[b], 2)} for b in auth]}


def _conf_badge(pdir):
    if pdir is None:
        return "unbekannt"
    return "sehr sicher" if pdir >= 0.99 else ("wahrscheinlich" if pdir >= 0.90 else "noch unklar")


def _relprice_map():
    """{topic_id: {Anzeigename: relpreis}} — relpreis = Markenpreis / guenstigster Marktpreis (>=1).
    Quellen: Crawler (data/price_comparison.json) + manuelle Vollerhebung 14.07.2026
    (data/price_manual.json). Je Produkt gewinnt die Quelle mit MEHR Marken (die
    manuelle Erhebung deckt 7 zusaetzliche Produkte ab, u.a. Rechtsschutz/Kfz/BU)."""
    # 20.07.2026: Von 25 getrackten Marken hatten nur 7 Preise — nicht weil Daten
    # fehlten, sondern weil diese Liste sie verwarf. Zwei Luecken behoben:
    #   (a) "ruv" und "devk" stehen als regulaere Schluessel in price_comparison.json
    #   (b) 67 Eintraege lagen in _other_-Sammelfeldern und wurden pauschal
    #       uebersprungen; ueber das Feld c24_name sind sie aufloesbar (siehe unten).
    keymap = {"allianz": "Allianz", "ergo": "ERGO", "axa": "AXA", "generali": "Generali",
              "huk": "HUK-Coburg", "signal-iduna": "Signal Iduna", "cosmosdirekt": "CosmosDirekt",
              "ruv": "R+V", "devk": "DEVK"}
    # 20.07.2026: "dkv" bewusst NICHT mehr auf ERGO gemappt — DKV ist seit heute
    # keine ERGO-Marke mehr im Sichtbarkeits-Matcher (Entscheidung Paul). Preis- und
    # Sichtbarkeitsseite sind damit wieder deckungsgleich; der Widerspruch vom
    # 15.07. (Krankenhauszusatz-Ausschluss trotz DKV-Alias) ist aufgeloest.

    # Alias-Tabelle zur Aufloesung der _other_-Eintraege ueber c24_name.
    # HERKUNFT, nicht geraten: Jeder Anbietername aus price_comparison.json wurde am
    # 20.07.2026 durch den ECHTEN Sichtbarkeits-Matcher geschickt
    # (analyzer/metrics.count_mentions aus dem GEO-Repo, Wortgrenzen-Logik).
    # Uebernommen sind nur die 24 Namen, die GENAU EINE getrackte Marke trafen —
    # null Mehrdeutigkeiten. Damit ist die Projektregel eingehalten: Der Preis gehoert
    # zu der Marke, die der Sichtbarkeits-Matcher zaehlt, nicht zur juristischen
    # Gesellschaft. Die uebrigen 56 Namen (Continentale, DELA, SDK, Nuernberger, ...)
    # sind Anbieter ausserhalb unseres Trackings und bleiben draussen.
    # Fuer Direkttoechter heisst das bewusst: "Allianz Direct" -> Allianz,
    # "ERGO Vorsorge" -> ERGO. DKV gehört seit 20.07.2026 NICHT mehr dazu.
    ALIAS2BRAND = [
        ("allianz direct", "Allianz"), ("allianz", "Allianz"),
        ("ergo vorsorge", "ERGO"), ("ergo", "ERGO"),
        ("axa konzern", "AXA"), ("axa", "AXA"),
        ("signal iduna", "Signal Iduna"),
        ("cosmosdirekt", "CosmosDirekt"), ("cosmos direkt", "CosmosDirekt"),
        ("generali", "Generali"),
        ("hansemerkur", "HanseMerkur"),
        ("arag", "ARAG"), ("adac", "ADAC"), ("devk", "DEVK"),
        ("r+v", "R+V"), ("lv 1871", "LV 1871"),
        ("da direkt", "DA Direkt"), ("da-direkt", "DA Direkt"),
        ("die bayerische", "Die Bayerische"),
        ("barmenia allgemeine", "Barmenia"),
        ("vhv allgemeine", "VHV"), ("vhv", "VHV"),
        # ACHTUNG: "Wuerttembergische Gemeinde-Versicherung" ist juristisch eine
        # ANDERE Gesellschaft als die Wuerttembergische Versicherung. Der Matcher
        # zaehlt eine solche Nennung aber als "Wuerttembergische" — nach der
        # Projektregel folgt der Preis dieser Zuordnung. Bewusste Entscheidung.
        ("württembergische", "Württembergische"), ("wuerttembergische", "Württembergische"),
    ]

    def _brand_from_name(nm):
        """Loest einen c24-Anbieternamen auf die getrackte Marke auf.
        Laengster Alias zuerst, damit 'Allianz Direct' nicht schon bei 'allianz' greift.
        Wortgrenzen-Pruefung verhindert Treffer in Wortmitten."""
        t = " " + re.sub(r"[^a-zäöüß0-9+ ]+", " ", str(nm or "").lower()).strip() + " "
        for al, br in sorted(ALIAS2BRAND, key=lambda x: -len(x[0])):
            if (" " + al + " ") in t:
                return br
        return None

    def _extract(path):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        res = {}
        for pid, pr in (d.get("products") or {}).items():
            prof = (pr.get("profiles") or {}).get("age_50") or {}
            prices = {}
            for k, v in (prof.get("brands") or {}).items():
                p = v.get("price")
                if not isinstance(p, (int, float)) or p <= 0:
                    continue
                if k.startswith("_other_"):
                    # Sammeleintrag: ueber den Klarnamen aufloesen statt verwerfen.
                    nm = _brand_from_name(v.get("c24_name") or k.replace("_other_", ""))
                else:
                    nm = keymap.get(k) or _brand_from_name(k)
                if not nm:
                    continue
                # Mehrere Tarife derselben Marke je Produkt: guenstigsten nehmen
                # (entspricht der Logik "was ein Interessent als Marktpreis sieht").
                if nm not in prices or p < prices[nm]:
                    prices[nm] = p
            if len(prices) >= 2:
                res[pid] = prices
        return res

    crawler = _extract(PRICE_FILE)
    manual = _extract(PRICE_MANUAL_FILE)
    merged = dict(crawler)
    for pid, prices in manual.items():
        # 20.07.2026: >= statt > — bei GLEICHSTAND gewinnt die manuelle Vollerhebung.
        # Grund: Sie ist unter dokumentierten, einheitlichen Bedingungen erhoben
        # (gleiches Profil, gleiches Datum, Parameter im Feld "params" festgehalten),
        # waehrend der Crawler nimmt, was Check24 gerade ausspielt. Ohne diese Regel
        # kippte Rechtsschutz nach der Alias-Erweiterung vom manuellen Satz auf den
        # Crawler-Satz — gleiche Markenzahl, aber duennere Kernmarken-Abdeckung.
        if pid not in merged or len(prices) >= len(merged[pid]):
            merged[pid] = prices
    # DKV-Ausschluss (15.07.2026, seit 20.07. nur noch Sicherheitsnetz): Krankenhaus-
    # zusatz laeuft im ERGO-Konzern unter der Marke DKV. Seit DKV aus den ERGO-Aliasen
    # entfernt wurde, kommt hier ohnehin kein ERGO-Preis mehr an — die Zeile greift also
    # normalerweise ins Leere. Sie bleibt stehen, falls eine Quelle den DKV-Preis doch
    # einmal unter dem Schluessel "ergo" liefert.
    if "krankenhauszusatz" in merged:
        merged["krankenhauszusatz"] = {b: p for b, p in merged["krankenhauszusatz"].items() if b != "ERGO"}
        if len(merged["krankenhauszusatz"]) < 2:
            merged.pop("krankenhauszusatz")
    out = {}
    for pid, prices in merged.items():
        mn = min(prices.values())
        out[pid] = {nm: prices[nm] / mn for nm in prices}
    return out


# _driver_card entfernt (16.07.2026): hatte nach Wegfall der toten "drivers"-Liste
# keinen Aufrufer mehr.


BRAND_SIZE = {  # grobe Groessen-/Bekanntheits-Naeherung (0-100), Basis GDV-Marktanteile 2024
                # + Markenbekanntheit; bewusst als Naeherung, leicht editierbar.
    "Allianz": 100.0, "ERGO": 65.0, "HUK-Coburg": 60.0, "AXA": 55.0,
    "Generali": 50.0, "Signal Iduna": 35.0, "CosmosDirekt": 30.0,
    # 18.07.2026: Erweiterung auf alle 26 Peec-Marken. Quelle/Logik: grobe Groessen-/
    # Bekanntheits-Naeherung (0-100) auf Basis deutscher Bruttobeitraege ~2023/24
    # (GDV/Geschaeftsberichte) + Markenbekanntheit, konsistent zur bestehenden Skala
    # (Allianz=100 / ERGO=65 / Signal Iduna=35). Schreibweisen exakt wie die Peec-Namen
    # (data/peec_footprint.json). HUK24/CosmosDirekt/DA Direkt/Hannoversche = Direkt-
    # marken: Wert mischt Konzernpraemie anteilig mit eigenstaendiger Online-Bekanntheit.
    "R+V": 60.0, "Debeka": 55.0, "HDI": 45.0, "Zurich": 40.0, "Gothaer": 35.0,
    "Württembergische": 35.0, "DEVK": 35.0, "VHV": 30.0, "Barmenia": 28.0,
    "ARAG": 28.0, "Alte Leipziger": 28.0, "HanseMerkur": 25.0, "ADAC": 25.0,
    "HUK24": 25.0, "Hannoversche": 20.0, "Die Bayerische": 15.0, "LV 1871": 12.0,
    "WGV": 12.0, "DA Direkt": 12.0,
}


def _mundlak_multi(cells, xkeys, ykey, _loo_depth=0, leader_override=None):
    """Mundlak/CRE mit MEHREREN Treibern gemeinsam: je Treiber Within+Between, die
    Between-Effekte kontrollieren einander (so trennt sich z.B. Groesse vom Footprint).
    leader_override (Audit A3): Referenzmarke der gap_decomposition wird von aussen
    vorgegeben (Leader des VOLLEN Segments), damit alle abgeleiteten Modelle gegen
    dieselbe Marke zerlegen statt gegen den je-Subset wechselnden max(ybar)."""
    brands = sorted({c["brand"] for c in cells})
    topics = sorted({c["topic"] for c in cells})
    n = len(cells)
    if n < 10 or len(brands) < 3 or len(topics) < 2:
        return {"available": False, "n_cells": n, "note": "Zu wenige Zellen fuer das gemeinsame Modell."}
    ys = [float(c.get(ykey, 0.0) or 0.0) for c in cells]
    if ys and (max(ys) - min(ys)) < 1e-9:
        _allzero = all(abs(y) < 1e-12 for y in ys)
        return {"available": False, "n_cells": n, "n_brands": len(brands), "n_topics": len(topics),
                "note": ("Keine Daten fuer diesen Kanal: alle SoV-Werte sind 0 "
                         "(LLM-Ausfall - z.B. API-Limit/Fehler). Kein Modell gerechnet."
                         if _allzero else
                         "Zielgroesse ohne Variation in diesem Kanal - kein Modell gerechnet.")}
    cnt = {}
    xbar = {k: {} for k in xkeys}
    for c in cells:
        cnt[c["brand"]] = cnt.get(c["brand"], 0) + 1
        for k in xkeys:
            xbar[k][c["brand"]] = xbar[k].get(c["brand"], 0.0) + float(c.get(k, 0.0))
    for k in xkeys:
        for b in xbar[k]:
            xbar[k][b] /= cnt[b]
    yb = {}; cy = {}
    for c in cells:
        yb[c["brand"]] = yb.get(c["brand"], 0.0) + c[ykey]; cy[c["brand"]] = cy.get(c["brand"], 0) + 1
    ybar = {b: yb[b] / cy[b] for b in yb}
    def _tdm(v):
        tm = {}; tc = {}
        for c, val in zip(cells, v):
            tm[c["topic"]] = tm.get(c["topic"], 0.0) + val; tc[c["topic"]] = tc.get(c["topic"], 0) + 1
        tmean = {t: tm[t] / tc[t] for t in tm}
        return [val - tmean[c["topic"]] for c, val in zip(cells, v)]
    cols = []; names = []; rawcols = []
    for k in xkeys:
        W = [float(c.get(k, 0.0)) - xbar[k][c["brand"]] for c in cells]
        B = [xbar[k][c["brand"]] for c in cells]
        cols.append(_tdm(W)); names.append(("within", k)); rawcols.append(W)
        cols.append(_tdm(B)); names.append(("between", k)); rawcols.append(B)
    Yc = _tdm([c[ykey] for c in cells])
    sd = []
    for col in cols:
        v = sum(x * x for x in col) / max(n - 1, 1); sd.append(v ** 0.5 if v > 1e-12 else 1.0)
    p = len(cols)
    Xs = [[cols[j][i] / sd[j] for j in range(p)] for i in range(n)]
    _lam = n * 0.1
    beta, Ainv, sig2 = _ridge_posterior(Xs, Yc, _lam)
    # 17.07.2026 (Review #3): Cluster = Marke. Die Zellen einer Marke sind nicht
    # unabhaengig; die iid-Varianz unterschaetzt die Streuung um rund den Faktor 1,6.
    _clusters = [c["brand"] for c in cells]
    _V, _G = _cluster_robust_var(Xs, Yc, beta, Ainv, _clusters)
    def _sdraw(v):
        m = sum(v) / len(v); return (sum((x - m) ** 2 for x in v) / max(len(v) - 1, 1)) ** 0.5
    eff = {}
    for j, (kind, k) in enumerate(names):
        mu = beta[j] / sd[j]
        sigma_iid = (max(sig2 * Ainv[j][j], 0.0) ** 0.5) / sd[j]
        sigma_cl = ((max(_V[j][j], 0.0) ** 0.5) / sd[j]) if _V is not None else None
        sigma = sigma_cl if (sigma_cl and sigma_cl > 1e-12) else sigma_iid
        # 17.07.2026: Frueher stand hier "else 1.0" - eine entartete Streuung (sigma=0,
        # z.B. bei totem Kanal) wurde damit zu P=1,0 = "sehr sicher". Fehlende
        # Information darf nicht als maximale Sicherheit erscheinen. Jetzt None.
        pdir = (max(_norm_cdf(mu / sigma), 1.0 - _norm_cdf(mu / sigma))
                if (sigma and sigma > 1e-12) else None)
        rec = {"coef": round(mu, 3),
               "prob_direction": round(pdir, 3) if pdir is not None else None,
               "effect_std_pp": round(mu * _sdraw(rawcols[j]), 2),
               "se_iid": round(sigma_iid, 4) if sigma_iid else None,
               "se_cluster": round(sigma_cl, 4) if sigma_cl else None,
               "se_inflation": (round(sigma_cl / sigma_iid, 2)
                                if (sigma_cl and sigma_iid and sigma_iid > 1e-12) else None),
               "n_clusters": _G}
        # 18.07.2026: Wild-Cluster-Bootstrap jetzt fuer BEIDE Ebenen.
        # Vorher lief er nur auf Between, mit der Begruendung "fuer Within traegt die
        # Zellzahl". Das ist falsch: Die Zellen einer Marke sind nicht unabhaengig -
        # auch der Within-Effekt stuetzt sich effektiv auf G Cluster, nicht auf n Zellen.
        # Folge des Versaeumnisses: Der Preis-Within-Effekt (grounded) stand mit
        # prob_direction = 0,995 als "sehr sicher" da. Der ehrliche Wild-p ist 0,086 -
        # nicht signifikant. Dieselbe Scheinsicherheit, die dieser Code ueberall sonst
        # entfernt, nur eine Ebene tiefer.
        #
        # Der Within-Effekt ist trotzdem der wertvollste Preis-Test des Projekts: Er
        # vergleicht die Marke MIT SICH SELBST ueber Produkte, damit ist alles
        # Marken-Konstante (Groesse, Bekanntheit, Identitaet) per Konstruktion draussen -
        # nicht per Kontrollvariable. Am Lauf 2026-07-17 (54 Zellen, 7 Marken):
        #     grounded   relprice within: coef -3,66 (allein -3,05), Wild-p 0,086
        #                LOO ueber alle 7 Marken: -2,56 bis -4,98, kein Vorzeichenwechsel
        #     ungrounded relprice within: coef +0,58, Wild-p 0,69 (praezise Null)
        # Konsistent, robust, richtige Richtung - nur unterversorgt. 23 der 77
        # Marke-x-Produkt-Zellen haben keinen Preis (allein Generali fehlt in 10 von 11).
        if _loo_depth < 1:
            _p, _g, _t = _wild_cluster_p(Xs, Yc, Ainv, _clusters, j, _lam)
            if _p is not None:
                rec["wild_cluster_p"] = round(_p, 4)
                rec["wild_cluster_t"] = _t
                if _g <= 12:
                    rec["wild_cluster_note"] = (
                        "Exakter Wild-Cluster-Bootstrap ueber alle %d Vorzeichen-Vektoren (G=%d Marken). "
                        "Kleinstmoeglicher p-Wert bei dieser Fallzahl: %.4f." % (2 ** _g, _g, 1.0 / (2 ** _g)))
                else:
                    rec["wild_cluster_note"] = (
                        "Wild-Cluster-Bootstrap mit deterministischer Rademacher-Stichprobe "
                        "(G=%d Marken > 12: vollstaendige Enumeration von 2^%d zu teuer). Fester "
                        "Seed 42, 4095 Draws; reproduzierbar. Kleinstmoeglicher p-Wert ~%.4f."
                        % (_g, _g, 1.0 / 4096))
        eff.setdefault(k, {})[kind] = rec
    # 17.07.2026 (Audit A3): Referenzmarke konsistent halten. Wenn ein Leader des
    # vollen Segments vorgegeben ist und im Subset vorkommt, gegen ihn zerlegen;
    # sonst Fallback auf die sichtbarste Marke des Subsets.
    if leader_override and leader_override in ybar:
        lead = leader_override
    else:
        lead = max(ybar, key=lambda b: ybar[b])
    gaps = {}
    for b in brands:
        if b == lead:
            continue
        actual = ybar[lead] - ybar[b]
        contrib = {k: round(eff[k]["between"]["coef"] * (xbar[k][lead] - xbar[k][b]), 2) for k in xkeys}
        gaps[b] = {"vs": lead, "actual_gap_pp": round(actual, 2), "contrib_pp": contrib,
                   "explained_pp": round(sum(contrib.values()), 2)}
    # 17.07.2026: Leave-one-out AUCH im gemeinsamen Modell (Review #4).
    # Vorher gab es LOO nur im bivariaten _mundlak_fit. Das Frontend zeigte den
    # Schaetzwert aus DIESEM Modell und daneben das Stabilitaets-Chip aus dem
    # bivariaten price_model - zwei verschiedene Modelle in einer Zeile. Das Chip
    # meldete "stabil" ueber eine Zahl, deren Stabilitaet nie geprueft worden war.
    # Bei 6-7 Marken ist genau das die entscheidende Pruefung: Jede einzelne Marke
    # IST hier ein nennenswerter Teil der Stichprobe.
    if _loo_depth < 1:
        for k in xkeys:
            _vals = []
            for _drop in brands:
                _sub = [c for c in cells if c["brand"] != _drop]
                if len({c["brand"] for c in _sub}) < 3:
                    continue
                _f = _mundlak_multi(_sub, xkeys, ykey, _loo_depth=_loo_depth + 1)
                if not _f.get("available"):
                    continue
                _b = (_f.get("drivers_eff", {}).get(k) or {}).get("between") or {}
                if _b.get("coef") is not None:
                    _vals.append({"dropped": _drop, "coef": _b["coef"]})
            if _vals:
                _cs = [v["coef"] for v in _vals]
                eff[k]["between"]["between_loo"] = {
                    "min": min(_cs), "max": max(_cs),
                    "sign_stable": bool(all(x > 0 for x in _cs) or all(x < 0 for x in _cs)),
                    "n_refits": len(_cs),
                    "per_brand": {v["dropped"]: v["coef"] for v in _vals},
                    "note": ("Vorzeichen des Between-Effekts, wenn jeweils eine Marke weggelassen wird. "
                             "sign_stable=false heisst: Der Effekt haengt an einzelnen Marken.")}

    return {"available": True, "n_cells": n, "n_brands": len(brands), "n_topics": len(topics),
            "drivers_eff": eff, "leader": lead, "gap_decomposition": gaps,
            "note": "Gemeinsames Mundlak-Modell; Between-Effekte kontrollieren einander (Groesse vs. Footprint sauber getrennt)."}


def _card_from_joint(label, k, joint, controllability, plain_tmpl, unit):
    if not joint or not joint.get("available"):
        return {"label": label, "available": False, "note": (joint or {}).get("note", "nicht verfuegbar")}
    be = (joint.get("drivers_eff", {}).get(k) or {}).get("between") or {}
    es = be.get("effect_std_pp"); pdir = be.get("prob_direction")
    return {"label": label, "available": True, "effect_pp_per_unit": be.get("coef"),
            "effect_std_pp": es, "prob_direction": pdir, "confidence": _conf_badge(pdir),
            "sign_stable": None, "n_cells": joint.get("n_cells"), "controllability": controllability,
            "plain": (plain_tmpl.format(es=es) if es is not None else None), "unit": unit}


def _cross_source_check(own_cells):
    """Footprint aus Peec gegen den EIGENEN SoV — der zirkularitaetsfreie Test.

    17.07.2026, Antwort auf Review-Punkt 1. Alle bisherigen Belege fuer
    "Quellpraesenz -> Sichtbarkeit" hatten Treiber und Zielgroesse aus derselben
    Quelle und waren damit zu einem unbekannten Teil Messartefakt:

        eigener Crawl, ungrounded:  ChatGPT-Zitate vs. ChatGPT-SoV   r=+0,998
        eigener Crawl, grounded:    ChatGPT-Zitate vs. Gemini-SoV    r=+0,860
        Peec intern:                Peec-URLs      vs. Peec-SoV      r=+0,798

    Auch der Peec-interne Wert ist NICHT unabhaengig: Die zitierten URLs stammen aus
    denselben Peec-Antworten, die den SoV liefern. (Die Uebergabe vom 17.07. nannte ihn
    faelschlich eine "unabhaengige Replikation" — das ist hiermit korrigiert.)

    Dieser Test kreuzt zwei getrennte Messsysteme:
        Treiber    = Peec-Footprint (UI-Scraping, zitierte URLs, 366 Prompts, 5 Engines)
        Zielgroesse = eigener grounded-SoV (Gemini-API, eigener Crawl)
    Kein gemeinsames Antwortmaterial -> Zirkularitaet konstruktiv ausgeschlossen.

    Ergebnis am Lauf 2026-07-17: Zellebene r=+0,728 (n=70, p<1e-12),
    Markenebene r=+0,823 (n=7, p=0,023). Die Markenebene ist der ehrlichere Wert —
    die 70 Zellen stammen aus nur 7 Marken und sind nicht unabhaengig.
    """
    if not PEEC_FOOTPRINT_FILE.exists():
        return {"available": False, "note": "data/peec_footprint.json fehlt."}
    try:
        fp = json.loads(PEEC_FOOTPRINT_FILE.read_text(encoding="utf-8"))
        foot = fp.get("footprint_pct") or {}
    except Exception as exc:
        return {"available": False, "note": "peec_footprint.json nicht lesbar: " + str(exc)[:80]}
    if not foot:
        return {"available": False, "note": "Kein footprint_pct in peec_footprint.json."}

    tmap = {"zahnzusatz": "Zahnzusatz", "sterbegeld": "Sterbegeld", "risikoleben": "Risikoleben",
            "berufsunfaehigkeit": "Berufsunfähigkeit", "rechtsschutz": "Rechtsschutz",
            "haftpflicht": "Haftpflicht", "hausrat": "Hausrat", "kfz": "Kfz", "unfall": "Unfall",
            "krankenhauszusatz": "Krankenhauszusatz"}
    own = {}
    for c in own_cells:
        th = tmap.get(c.get("topic"))
        if th and isinstance(c.get("sov"), (int, float)):
            own.setdefault(c["brand"], {})[th] = c["sov"]

    xs = []; ys = []; brands = set()
    for b, tv in foot.items():
        for t, f in (tv or {}).items():
            v = (own.get(b) or {}).get(t)
            if isinstance(v, (int, float)) and isinstance(f, (int, float)):
                xs.append(f); ys.append(v); brands.add(b)
    r_cell = pearson(xs, ys) if len(xs) >= 4 else None

    bx = []; by = []
    for b in sorted(brands):
        fv = [f for t, f in (foot.get(b) or {}).items()
              if isinstance((own.get(b) or {}).get(t), (int, float))]
        tv = [own[b][t] for t in (foot.get(b) or {})
              if isinstance((own.get(b) or {}).get(t), (int, float))]
        if fv:
            bx.append(sum(fv) / len(fv)); by.append(sum(tv) / len(tv))
    r_brand = pearson(bx, by) if len(bx) >= 4 else None

    return {"available": bool(r_brand is not None or r_cell is not None),
            "driver": "Peec-Footprint (UI-Scraping, zitierte URLs)",
            "target": "eigener grounded-SoV (Gemini-API)",
            "n_cells": len(xs), "n_brands": len(bx),
            "pearson_r_cells": round(r_cell, 3) if r_cell is not None else None,
            "pearson_r_brands": round(r_brand, 3) if r_brand is not None else None,
            "circularity": {"share_same_engine": 0.0, "level": "none",
                            "note": "Treiber und Zielgroesse stammen aus getrennten Messsystemen "
                                    "(Peec-UI-Scraping vs. eigene Gemini-API). Kein gemeinsames "
                                    "Antwortmaterial - Zirkularitaet konstruktiv ausgeschlossen."},
            "note": ("Zirkularitaetsfreier Test des Kernbefunds. Markenebene ist der ehrlichere "
                     "Wert: Die Zellen stammen aus nur wenigen Marken und sind nicht unabhaengig. "
                     "Zum Vergleich: Peec-Footprint gegen Peec-eigenen SoV liegt hoeher, misst "
                     "aber dieselben Antworten gegen sich selbst.")}


def peec26_model():
    """Peec-26-Marken-Modell (18.07.2026). Datengrundlage NUR Peec (beide Groessen aus
    Peec — dokumentierte Absicht: interne Konsistenz, nicht Cross-Source). Zellen =
    Marke x Thema; y = Peec-SoV in % (mention_count-basiert je Thema neu berechnet, NIE
    Peec-SoV-Spalten mitteln). Treiber: peec_foot (footprint_pct je Marke x Thema) und
    size (BRAND_SIZE, jetzt 26). HUK24 ist hier eine EIGENE Marke (KEIN Merge zu
    HUK-Coburg). "Corporate" ist kein Produktthema und faellt raus.
    Der zirkularitaetsarme Gegentest bleibt cross_source_validation."""
    import csv as _csv
    if not PEEC_FOOTPRINT_FILE.exists():
        return {"available": False, "note": "data/peec_footprint.json fehlt."}
    if not PEEC_FILE.exists():
        return {"available": False, "note": "data/peec_cells.csv fehlt."}
    try:
        fp = json.loads(PEEC_FOOTPRINT_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"available": False, "note": "peec_footprint.json nicht lesbar: " + str(exc)[:80]}
    foot = fp.get("footprint_pct") or {}
    if not foot:
        return {"available": False, "note": "Kein footprint_pct in peec_footprint.json."}
    # grounded wie in _load_peec_cells (ChatGPT-UI zaehlt zu grounded, s. dort).
    _ground = {"Gemini", "Perplexity", "AI Overview", "AI Mode", "ChatGPT"}
    mc = {}; tot = {}
    try:
        with PEEC_FILE.open(encoding="utf-8-sig") as fh:
            for r in _csv.DictReader(fh, delimiter=";"):
                th = (r.get("thema") or "").strip()
                if not th or th == "Corporate":
                    continue
                if (r.get("engine") or "") not in _ground:
                    continue
                b = r.get("marke")
                try:
                    m = float(r.get("mention_count") or 0)
                except (TypeError, ValueError):
                    continue
                mc[(b, th)] = mc.get((b, th), 0.0) + m
                tot[th] = tot.get(th, 0.0) + m
    except Exception as exc:
        return {"available": False, "note": "peec_cells.csv nicht lesbar: " + str(exc)[:80]}
    if not mc:
        return {"available": False, "note": "Keine verwertbaren Peec-Zellen (mention_count)."}
    # Zellen: nur Marken mit Groesse (BRAND_SIZE) UND vorhandenem Footprint je Thema.
    cells = []
    for (b, th), m in mc.items():
        f = (foot.get(b) or {}).get(th)
        if f is None or b not in BRAND_SIZE:
            continue
        sov = (100.0 * m / tot[th]) if tot.get(th) else 0.0
        cells.append({"brand": b, "topic": th, "sov": sov,
                      "peec_foot": float(f), "size": float(BRAND_SIZE[b])})
    if len(cells) < 10:
        return {"available": False, "n_cells": len(cells),
                "note": "Zu wenige Peec-26-Zellen fuer das Modell."}
    # Leader = Marke mit hoechstem SoV-Markenmittel (leader_override).
    _bs = {}
    for c in cells:
        _bs.setdefault(c["brand"], []).append(c["sov"])
    _bmean = {b: sum(v) / len(v) for b, v in _bs.items()}
    _leader = max(_bmean, key=lambda b: _bmean[b])
    fit = _mundlak_multi(cells, ["peec_foot", "size"], "sov", leader_override=_leader)
    if not fit.get("available"):
        return {"available": False, "note": fit.get("note", "Mundlak-Fit fehlgeschlagen."),
                "n_cells": fit.get("n_cells")}
    de = fit.get("drivers_eff", {})
    be_foot = (de.get("peec_foot") or {}).get("between") or {}
    be_size = (de.get("size") or {}).get("between") or {}
    # FDR ueber die Between-Familie (peec_foot + size), Wild-Cluster-p als Basis.
    _apply_fdr({"peec_foot": be_foot, "size": be_size})
    wild_p = {"peec_foot": be_foot.get("wild_cluster_p"), "size": be_size.get("wild_cluster_p")}
    fdr_q = {"peec_foot": be_foot.get("wild_cluster_p_fdr"), "size": be_size.get("wild_cluster_p_fdr")}
    between_loo = be_foot.get("between_loo")
    # Markenebene: Markenmittel Footprint vs. Markenmittel SoV (n=26).
    _bf = {}
    for c in cells:
        _bf.setdefault(c["brand"], []).append(c["peec_foot"])
    _fmean = {b: sum(v) / len(v) for b, v in _bf.items()}
    _brs = sorted(_bmean)
    _bx = [_fmean[b] for b in _brs]; _by = [_bmean[b] for b in _brs]
    _pr = pearson(_bx, _by); _sr = spearman(_bx, _by)
    gap = (fit.get("gap_decomposition") or {}).get("ERGO")
    return {
        "available": True,
        "n_cells": fit.get("n_cells"),
        "n_brands": fit.get("n_brands"),
        "n_topics": fit.get("n_topics"),
        "leader": _leader,
        "drivers_eff": de,
        "wild_p": wild_p,
        "fdr_q": fdr_q,
        "between_loo": between_loo,
        "brand_level": {"pearson_r": round(_pr, 3) if _pr is not None else None,
                        "spearman_r": round(_sr, 3) if _sr is not None else None,
                        "n": len(_brs)},
        "gap_decomposition": gap,
        "circularity": {"level": "high",
                        "note": ("Footprint und SoV stammen aus denselben Peec-Antworten "
                                 "(interne Konsistenz); der zirkularitaetsarme Gegentest "
                                 "ist cross_source_validation.")},
        "note": ("Peec-26-Modell (18.07.2026): erstmals n=26 Marken mit Groessen-Kontrolle. "
                 "Hebt den Footprint-Befund von 'plausibel bei n=7' auf eine belastbare "
                 "Fallzahl - Between-Statistik mit Wild-Cluster-p statt Posterior-P."),
    }


def _load_peec_cells():
    """Peec-AI-Export (UI-Scraping, unabhaengige 2. Messquelle) -> SoV je Marke x Thema.
    grounded = Gemini/Perplexity/AI Overview/AI Mode/ChatGPT-UI. ChatGPT-UI zaehlt zu
    grounded, weil empirisch belegt (14.07.2026): r=0,86 zu eigenem Gemini-grounded
    vs. nur 0,71 zum eigenen ChatGPT-API-ungrounded — die UI nutzt faktisch Websuche.
    SoV wird mention_count-basiert je Thema neu berechnet (nie Peec-SoV mitteln)."""
    import csv as _csv
    if not PEEC_FILE.exists():
        return None
    tmap = {"Zahnzusatz": "zahnzusatz", "Sterbegeld": "sterbegeld", "Risikoleben": "risikoleben",
            "Berufsunfähigkeit": "berufsunfaehigkeit", "Berufsunfaehigkeit": "berufsunfaehigkeit",
            "Rechtsschutz": "rechtsschutz", "Haftpflicht": "haftpflicht", "Hausrat": "hausrat",
            "Kfz": "kfz", "Unfall": "unfall", "Krankenhauszusatz": "krankenhauszusatz", "Reise": "reise"}
    bmap = {"HUK24": "HUK-Coburg"}
    ground = {"Gemini", "Perplexity", "AI Overview", "AI Mode", "ChatGPT"}
    mc_g = {}; tot_g = {}; mc_all = {}; tot_all = {}
    try:
        with PEEC_FILE.open(encoding="utf-8-sig") as fh:
            for r in _csv.DictReader(fh, delimiter=";"):
                pid = tmap.get((r.get("thema") or "").strip())
                if not pid:
                    continue
                b = bmap.get(r.get("marke"), r.get("marke"))
                try:
                    m = float(r.get("mention_count") or 0)
                except (TypeError, ValueError):
                    continue
                key = (b, pid)
                mc_all[key] = mc_all.get(key, 0.0) + m
                tot_all[pid] = tot_all.get(pid, 0.0) + m
                if (r.get("engine") or "") in ground:
                    mc_g[key] = mc_g.get(key, 0.0) + m
                    tot_g[pid] = tot_g.get(pid, 0.0) + m
    except Exception:
        return None
    out = {}
    for (b, pid), m in mc_all.items():
        out[(b, pid)] = {
            "sov_g": (100.0 * mc_g.get((b, pid), 0.0) / tot_g[pid]) if tot_g.get(pid) else None,
            "sov_all": (100.0 * m / tot_all[pid]) if tot_all.get(pid) else None}
    return out or None


def _structure_segment(fit_x, pfj_seg, guard_note):
    """Audit A4: robuste, zweistufige Gap-Zerlegung fuers UI (kein Kausalnachweis).
    Autoritaet (Groesse+Footprint, statistisch nicht trennbar) kommt aus dem
    1-Treiber-Level-Fit des VOLLEN Segments; der Preis-Beitrag separat aus dem
    2-Treiber-Modell (price_footprint_joint, dank A3 gegen denselben Leader).
    Beide Beitraege werden auf [0, gap] bzw. das Restbudget gekappt."""
    if not (isinstance(fit_x, dict) and fit_x.get("available")):
        return {"available": False, "note": (fit_x or {}).get("note", guard_note)}
    gd = (fit_x.get("gap_decomposition") or {}).get("ERGO")
    if not gd:
        return {"available": False,
                "note": "ERGO ist Leader oder fehlt im Segment — keine Gap-Zerlegung."}
    gap = gd.get("actual_gap_pp")
    auth_raw = gd.get("explained_by_footprint_pp")
    if gap is None or auth_raw is None:
        return {"available": False, "note": "Gap/Autoritaets-Beitrag nicht bestimmbar."}
    leader = gd.get("vs") or fit_x.get("leader")
    auth = min(max(auth_raw, 0.0), gap) if gap > 0 else 0.0
    auth_capped = bool(abs(auth - auth_raw) > 1e-9)
    price_raw = 0.0
    if isinstance(pfj_seg, dict) and pfj_seg.get("available"):
        _pgd = (pfj_seg.get("gap_decomposition") or {}).get("ERGO")
        if _pgd:
            price_raw = (_pgd.get("contrib_pp") or {}).get("relprice", 0.0) or 0.0
    price = min(max(price_raw, 0.0), max(gap - auth, 0.0))
    price_capped = bool(abs(price - price_raw) > 1e-9)
    rest = max(gap - auth - price, 0.0)
    return {
        "available": True,
        "leader": leader,
        "gap_pp": round(gap, 2),
        "authority_pp": round(auth, 2),
        "authority_capped": auth_capped,
        "price_pp": round(price, 2),
        "price_capped": price_capped,
        "rest_pp": round(rest, 2),
        "note": ("Autoritaet = Groesse+Footprint (statistisch nicht trennbar, Audit 17.07.); "
                 "Preis separat aus dem 2-Treiber-Modell; Beitraege gekappt. "
                 "Zerlegung, kein Kausalnachweis."),
    }


def level_model_mundlak():
    """Level-Modell (Mundlak): erklaert das SoV-NIVEAU aus dem Zitations-Footprint,
    getrennt fuer grounded (Gemini/Perplexity) und ungrounded (ChatGPT)."""
    try:
        g = json.loads(GEO_SNAPSHOT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    products = g.get("products") or {}
    if not products:
        return None
    llms = g.get("llms") or []
    if not llms:
        for pd in products.values():
            for k in (pd.get("summary_by_llm") or {}):
                if k not in llms:
                    llms.append(k)
    grounded = [l for l in llms if l in GROUNDED_LLMS]
    ungrounded = [l for l in llms if l not in GROUNDED_LLMS]
    cells_g = []; cells_u = []; cells_c = []
    for pid, pd in products.items():
        cs = pd.get("cited_sources") or {}
        total = cs.get("total") or 0
        cc = {}
        for row in (cs.get("overall") or []):
            b = _fp_dom2brand(row.get("domain"))
            if b:
                cc[b] = cc.get(b, 0) + (row.get("count") or 0)
        sbl = pd.get("summary_by_llm") or {}
        sov = {}
        for eng in llms:
            for br in ((sbl.get(eng) or {}).get("brands") or []):
                nm = br.get("name")
                if nm:
                    sov.setdefault(nm, {})[eng] = br.get("share_of_voice") or 0.0
        for b in sov:
            s = sov[b]
            gv = [s.get(e, 0.0) for e in _engines_present(sbl, grounded)]
            uv = [s.get(e, 0.0) for e in _engines_present(sbl, ungrounded)]
            share = (100.0 * cc.get(b, 0) / total) if total else 0.0
            cells_g.append({"brand": b, "topic": pid, "cite_share": share,
                            "sov": 100.0 * (sum(gv) / len(gv) if gv else 0.0)})
            cells_u.append({"brand": b, "topic": pid, "cite_share": share,
                            "sov": 100.0 * (sum(uv) / len(uv) if uv else 0.0)})
            av = [s.get(e, 0.0) for e in _engines_present(sbl, llms)]
            cells_c.append({"brand": b, "topic": pid, "cite_share": share,
                            "sov": 100.0 * (sum(av) / len(av) if av else 0.0)})
    # ── 17.07.2026 (Audit A1): Ausfall-Guard ──────────────────────────────────
    # Am 16.07. lieferte Gemini fuer alle Themen 0. Die combined-Zelle mittelt
    # ueber alle Engines, hatte dadurch Varianz und wurde MIT den Nullen gerechnet
    # -> ein kuenstlicher 6,6-pp-Gap. Regel: "keine Daten ist kein Befund". Ein
    # Engine-Segment ohne einen einzigen Messwert (Summe aller SoV ~ 0) wird NICHT
    # berechnet, und combined mittelt nur ueber Segmente MIT Daten.
    _GUARD_NOTE = ("Segment ohne Messwerte im Snapshot (Engine-Ausfall?) — nicht "
                   "berechnet (Regel: keine Daten ist kein Befund).")
    seg_g_ok = sum(c["sov"] for c in cells_g) > 1e-9
    seg_u_ok = sum(c["sov"] for c in cells_u) > 1e-9
    fit_g = (_mundlak_fit(cells_g, "cite_share", "sov") if seg_g_ok
             else {"available": False, "n_cells": len(cells_g), "note": _GUARD_NOTE})
    fit_u = (_mundlak_fit(cells_u, "cite_share", "sov") if seg_u_ok
             else {"available": False, "n_cells": len(cells_u), "note": _GUARD_NOTE})
    # combined nur aus Engines mit Daten: faellt ein Segment aus, rechnet combined
    # allein auf dem verbleibenden Segment (statt die Nullen einzumischen).
    _combined_note = None
    if seg_g_ok and seg_u_ok:
        pass  # cells_c wie gebaut (alle Engines)
    elif seg_u_ok:
        cells_c = [dict(c) for c in cells_u]
        _combined_note = "Combined nutzt nur ungrounded (grounded-Segment ohne Messwerte im Snapshot)."
    elif seg_g_ok:
        cells_c = [dict(c) for c in cells_g]
        _combined_note = "Combined nutzt nur grounded (ungrounded-Segment ohne Messwerte im Snapshot)."
    seg_c_ok = seg_g_ok or seg_u_ok
    fit_c = (_mundlak_fit(cells_c, "cite_share", "sov") if seg_c_ok
             else {"available": False, "n_cells": len(cells_c), "note": _GUARD_NOTE})
    if _combined_note and isinstance(fit_c, dict):
        fit_c["combined_note"] = _combined_note
    _seg_ok = {"grounded": seg_g_ok, "ungrounded": seg_u_ok, "combined": seg_c_ok}
    # #17: Relativpreis als zusaetzlicher Treiber (nur Produkte mit Preisdaten)
    _rp = _relprice_map()
    for _cs in (cells_g, cells_u, cells_c):
        for c in _cs:
            v = _rp.get(c["topic"], {}).get(c["brand"])
            if v is not None:
                c["relprice"] = v
    # Audit A3: Leader je Segment EINMAL aus dem vollen Zellenset bestimmen und an
    # die abgeleiteten Modelle durchreichen (konsistente Referenzmarke, s. Audit E8).
    _full_leader = {"grounded": fit_g.get("leader") if isinstance(fit_g, dict) else None,
                    "ungrounded": fit_u.get("leader") if isinstance(fit_u, dict) else None,
                    "combined": fit_c.get("leader") if isinstance(fit_c, dict) else None}
    price_model = {}
    for _en, _cs in (("grounded", cells_g), ("ungrounded", cells_u), ("combined", cells_c)):
        if not _seg_ok[_en]:
            price_model[_en] = {"available": False, "note": _GUARD_NOTE}
            continue
        _pc = [c for c in _cs if "relprice" in c]
        price_model[_en] = (_mundlak_fit(_pc, "relprice", "sov", min_cells=6)
                            if len(_pc) >= 6 else
                            {"available": False, "n_cells": len(_pc),
                             "note": "Zu wenige Produkte mit Preisdaten fuer einen belastbaren Preis-Effekt."})
    # (b) 15.07.2026: Gemeinsames Modell Preis + Footprint — trennt die Ueberlappung
    # (guenstige Marken ranken auf Portalen besser -> mehr Zitate; erst das gemeinsame
    # Modell zeigt den Preis-Effekt BEREINIGT um den Footprint und umgekehrt).
    price_footprint_joint = {}
    for _en, _cs in (("grounded", cells_g), ("ungrounded", cells_u), ("combined", cells_c)):
        if not _seg_ok[_en]:
            price_footprint_joint[_en] = {"available": False, "note": _GUARD_NOTE}
            continue
        _pc = [c for c in _cs if "relprice" in c]
        price_footprint_joint[_en] = (
            _mundlak_multi(_pc, ["cite_share", "relprice"], "sov", leader_override=_full_leader[_en])
            if len(_pc) >= 10 else
            {"available": False, "n_cells": len(_pc),
             "note": "Zu wenige Zellen mit Preis UND Footprint."})

    # (15.07.2026) Voll-Zerlegung fuer die Ursachenanalyse vs. Marktfuehrer:
    # Groesse + Footprint + Preis GEMEINSAM (kontrollieren einander). Achtung
    # Kollinearitaet Groesse<->Footprint bei n eff.=6-7 Marken — die interne
    # Aufteilung dieser beiden ist nur als Tendenz zu lesen (im UI kenntlich machen).
    full_joint = {}
    for _en, _cs in (("grounded", cells_g), ("ungrounded", cells_u), ("combined", cells_c)):
        if not _seg_ok[_en]:
            full_joint[_en] = {"available": False, "note": _GUARD_NOTE}
            continue
        _fc = [c for c in _cs if ("relprice" in c and c["brand"] in BRAND_SIZE)]
        for c in _fc:
            c["size"] = BRAND_SIZE[c["brand"]]
        full_joint[_en] = (
            _mundlak_multi(_fc, ["cite_share", "size", "relprice"], "sov", leader_override=_full_leader[_en])
            if len(_fc) >= 12 else
            {"available": False, "n_cells": len(_fc),
             "note": "Zu wenige Zellen mit Preis+Groesse+Footprint."})

    # #16 2. Treiber: Groesse/Bekanntheit gemeinsam mit Footprint (Effekte kontrollieren einander)
    for c in cells_c:
        if c["brand"] in BRAND_SIZE:
            c["size"] = BRAND_SIZE[c["brand"]]
    _joint_cells = [c for c in cells_c if ("size" in c and "cite_share" in c)]
    # Audit A1: joint_model laeuft auf dem combined-Segment — nur rechnen, wenn dort Daten sind.
    joint_model = (_mundlak_multi(_joint_cells, ["cite_share", "size"], "sov")
                   if seg_c_ok else {"available": False, "note": _GUARD_NOTE})
    # 2026-07-16 entfernt: die frühere "drivers"-Kartenliste war toter Code — kein Frontend
    # hat sie je gelesen (gerendert wird ausschliesslich korrelation_upgrade.js aus
    # "drivers_eff" des Joint-Modells). Sie hat zweimal Arbeit verursacht, weil dort
    # "Fixes" gemacht wurden, die nie sichtbar wurden. Bewusst geloescht statt gepflegt.
    # ── Peec-Integration (2026-07-15): Source-augmentiertes Modell + Konvergenz ──
    with_peec = None
    try:
        _peec = _load_peec_cells()
        if _peec:
            _cs_map = {(c["brand"], c["topic"]): c["cite_share"] for c in cells_g}
            _own_g = {(c["brand"], c["topic"]): c["sov"] for c in cells_g}
            _own_c = {(c["brand"], c["topic"]): c["sov"] for c in cells_c}
            aug_g = [dict(c, src_peec=0.0) for c in cells_g]
            aug_c = [dict(c, src_peec=0.0) for c in cells_c]
            _n_add = 0
            _vx = []; _vy = []; _vcx = []; _vcy = []
            for (_b, _pid), _v in _peec.items():
                if (_b, _pid) in _own_g and _v.get("sov_g") is not None:
                    _vx.append(_own_g[(_b, _pid)]); _vy.append(_v["sov_g"])
                if (_b, _pid) in _own_c and _v.get("sov_all") is not None:
                    _vcx.append(_own_c[(_b, _pid)]); _vcy.append(_v["sov_all"])
                _cs = _cs_map.get((_b, _pid))
                if _cs is None:
                    continue  # nur Zellen mit bekanntem Footprint-Treiber
                if _v.get("sov_g") is not None:
                    aug_g.append({"brand": _b, "topic": _pid, "cite_share": _cs,
                                  "sov": _v["sov_g"], "src_peec": 1.0})
                if _v.get("sov_all") is not None:
                    aug_c.append({"brand": _b, "topic": _pid, "cite_share": _cs,
                                  "sov": _v["sov_all"], "src_peec": 1.0})
                _n_add += 1
            # 2026-07-16 Fix: Validierung war null, weil der eigene grounded-SoV im
            # aktuellen Snapshot komplett 0 ist (Gemini-Messung leer -> Varianz 0 ->
            # pearson() = None). Jetzt: grounded UND combined getrennt validieren,
            # Varianz-Wache mit explizitem data_health-Hinweis statt stillem null.
            _r = pearson(_vx, _vy) if len(_vx) >= 5 else None
            _rho = spearman(_vx, _vy) if len(_vx) >= 5 else None
            _rc = pearson(_vcx, _vcy) if len(_vcx) >= 5 else None
            _rhoc = spearman(_vcx, _vcy) if len(_vcx) >= 5 else None
            _health = None
            if _vx and max(_vx) == min(_vx):
                _health = ("Eigener grounded-SoV ohne Varianz (alle Werte %.2f) - Gemini-"
                           "Messung im geo_snapshot liefert aktuell keine SoV-Werte. "
                           "Grounded-Validierung und grounded-Level-Modell derzeit nicht "
                           "interpretierbar; bitte Crawl pruefen." % _vx[0])
            with_peec = {
                "available": _n_add > 0,
                "n_cells_added": _n_add,
                # Audit A1: nur rechnen, wenn das jeweilige Basis-Segment (eigener Crawl)
                # Messwerte hat — sonst wuerde der Peec-augmentierte Fit die 0-Zellen
                # des toten eigenen Kanals mitverrechnen.
                "grounded": (_mundlak_multi(aug_g, ["cite_share", "src_peec"], "sov")
                             if seg_g_ok else {"available": False, "note": _GUARD_NOTE}),
                "combined": (_mundlak_multi(aug_c, ["cite_share", "src_peec"], "sov")
                             if seg_c_ok else {"available": False, "note": _GUARD_NOTE}),
                "validation": {"n_common_cells": len(_vx),
                               "pearson_r": (round(_r, 3) if _r is not None
                                             else (round(_rc, 3) if _rc is not None else None)),
                               "spearman_r": (round(_rho, 3) if _rho is not None
                                              else (round(_rhoc, 3) if _rhoc is not None else None)),
                               "grounded": {"n": len(_vx),
                                            "pearson_r": round(_r, 3) if _r is not None else None,
                                            "spearman_r": round(_rho, 3) if _rho is not None else None},
                               "combined": {"n": len(_vcx),
                                            "pearson_r": round(_rc, 3) if _rc is not None else None,
                                            "spearman_r": round(_rhoc, 3) if _rhoc is not None else None},
                               "data_health": _health,
                               "criterion": "Rangfolgen-Konvergenz > 0,7 erwartet (13_PEEC_INTEGRATION_ANLEITUNG)"},
                "note": ("Peec AI (UI-Scraping, 366 Prompts, inkl. Google AI Overview/AI Mode) als zweite, "
                         "unabhaengige Messquelle. Zellen mit src_peec-Dummy (Mundlak-Kontrolle fuer "
                         "Niveau-Unterschiede UI vs. API) zum eigenen Crawl hinzugefuegt; Footprint-Treiber "
                         "stammt weiterhin aus dem eigenen Crawl. drivers_eff.cite_share = integrierter "
                         "Footprint-Effekt ueber beide Quellen.")}
    except Exception as _pe:
        with_peec = {"available": False, "note": "Peec-Integration fehlgeschlagen: " + str(_pe)[:120]}
    # 17.07.2026: Zirkularitaet je Kanal messen und an den Fit haengen (Review #1).
    _cmix = _citation_engine_mix(products)
    for _fit, _engs in ((fit_g, grounded), (fit_u, ungrounded), (fit_c, llms)):
        if isinstance(_fit, dict):
            _fit["circularity"] = _circularity(_cmix, _engs)
    for _blk in (price_footprint_joint, full_joint):
        for _en, _engs in (("grounded", grounded), ("ungrounded", ungrounded), ("combined", llms)):
            if isinstance(_blk.get(_en), dict):
                _blk[_en]["circularity"] = _circularity(_cmix, _engs)

    # FDR ueber alle Between-Tests des Level-Modells (nach dem Bau aller Bloecke)
    for _blk in (price_footprint_joint, full_joint):
        _apply_fdr(_blk)
    _apply_fdr(joint_model)

    try:
        _xsrc = _cross_source_check(cells_g)
    except Exception as _xe:
        _xsrc = {"available": False, "note": "Cross-Source-Check fehlgeschlagen: " + str(_xe)[:100]}

    # 18.07.2026: Peec-26-Marken-Modell (n=7 -> n=26 mit Groessen-Kontrolle).
    try:
        _p26 = peec26_model()
    except Exception as _p26e:
        _p26 = {"available": False, "note": str(_p26e)[:120]}

    # Audit A4: robuste Struktur-Zusammenfassung je Segment fuers UI (Autoritaet +
    # Preis + Rest, gekappt). Ersetzt die nicht kommunizierbare 3-Treiber-Zerlegung.
    structure_summary = {
        "grounded": _structure_segment(fit_g, price_footprint_joint.get("grounded"), _GUARD_NOTE),
        "ungrounded": _structure_segment(fit_u, price_footprint_joint.get("ungrounded"), _GUARD_NOTE),
        "combined": _structure_segment(fit_c, price_footprint_joint.get("combined"), _GUARD_NOTE),
    }

    return {"available": True, "driver": "cite_share",
            "citation_engine_mix": _cmix,
            "cross_source_validation": _xsrc,
            "peec26_model": _p26,
            "grounded": fit_g, "ungrounded": fit_u, "combined": fit_c,
            "price_model": price_model, "joint_model": joint_model,
            "with_peec": with_peec, "price_footprint_joint": price_footprint_joint,
            "full_joint": full_joint,
            "structure_summary": structure_summary,
            "note": ("Level-Modell (Mundlak/CRE): Zielgroesse = SoV-NIVEAU je Marke x Thema; Treiber = "
                     "Zitations-Footprint (cite_share = eigene-Domain-Zitate / alle Zitate im Thema). "
                     "WITHIN = bewegt mehr eigener Footprint im Thema die Sichtbarkeit (Marke gegen sich selbst "
                     "ueber Themen, Themen-FE kontrolliert). BETWEEN = Marken-Mittel des Footprints; erklaert den "
                     "Autoritaets-/Marken-Vorsprung (warum Allianz sichtbarer ist) statt ihn wie ein reiner "
                     "Marken-FE zu verstecken. gap_decomposition = Anteil des SoV-Abstands zum Marktfuehrer, der "
                     "durch Footprint erklaert ist. coef-Einheit = Pp SoV je Pp Zitationsanteil. Mit 6 Themen "
                     "explorativ. Quelle: data/geo_snapshot.json.")}


# ===========================================================================
# Erweiterungen 19.07.2026 — neue Peec-Datenquellen im Treibermodell
#
# Alle drei Auswertungen sind ADDITIV: sie lassen das bestehende Modell
# unberuehrt und schreiben eigene Bloecke in die Ausgabe. Jede meldet bei
# fehlender Datenbasis ausdruecklich available=False MIT GRUND — niemals eine
# 0.0, die wie "gesichert kein Effekt" aussieht (roter Faden dieses Projekts).
# ===========================================================================

PEEC_SNAP_DIR = Path("data/peec_snapshots")
PEEC_SEGMENTS_FILE = Path("data/peec_segments.json")
PEEC_SEGMENTS_HIST = Path("data/peec_segments_history.csv")

# Mindestzahl Messpunkte, ab der ueberhaupt gerechnet wird.
# 3 Punkte = 2 Intervalle: das ist die absolute Untergrenze fuer eine Steigung,
# und selbst dann nur explorativ (type_confidence weist es aus).
MIN_CITATION_POINTS = 3
MIN_FUNNEL_POINTS = 3
# Ab welchem Anteil brauchbarer Klassifikationen die Seitentyp-Aufschluesselung
# ueberhaupt berichtet wird. Darunter waere die Aufteilung eine Scheingenauigkeit.
MIN_CLASS_COVERAGE = 0.30
# Funnel-Stufen in Reihenfolge. Die uebrigen Tags sind Themenfelder (Corporate
# Trust, Sustainability, ...) — inhaltlich anders gelagert und deshalb beim
# teuren Wild-Cluster-Test nicht mitgerechnet.
FUNNEL_ORDER = ["Awareness", "Consideration", "Decision", "Retention"]


def _effect_ci(xs, ys, min_with_for_sig=8):
    """Effekt (mit vs. ohne Ereignis), Standardfehler und t-basiertes 95-%-KI.

    Bewusst dieselbe Rechnung wie im Hauptmodell (analyze), damit die neuen
    Bloecke nicht mit einer abweichenden Konvention danebenstehen: konservative
    Freiheitsgrade (kleinere Gruppe - 1), "gesichert" nur wenn das KI die Null
    ausschliesst UND genug Intervalle mit Ereignis vorliegen.
    """
    def _v(v, m):
        return sum((z - m) ** 2 for z in v) / (len(v) - 1) if len(v) > 1 else 0.0

    with_v = [y for x, y in zip(xs, ys) if x > 0]
    without_v = [y for x, y in zip(xs, ys) if x <= 0]
    if not with_v or not without_v:
        # 20.07.2026 Review-Fix: Hier standen 5 Rueckgabewerte, alle fuenf Aufrufer
        # entpacken aber 6. Der Pfad greift, sobald JEDES Intervall das Ereignis hat
        # (oder keines) — bei feinen Schichten jederzeit erreichbar. Weil main() jeden
        # Blockfehler abfaengt, waere der Block dann stillschweigend aus der Ausgabe
        # verschwunden statt einen Fehler zu zeigen.
        return None, None, None, None, None, None
    m1 = sum(with_v) / len(with_v)
    m0 = sum(without_v) / len(without_v)
    eff = m1 - m0
    se = None
    if len(with_v) > 1 and len(without_v) > 1:
        se = math.sqrt(_v(with_v, m1) / len(with_v) + _v(without_v, m0) / len(without_v))
    lo = hi = None
    sig = None
    pval = None
    if se is not None and se > 0:
        tc = t_critical(min(len(with_v), len(without_v)) - 1)
        if tc is not None:
            lo, hi = round(eff - tc * se, 3), round(eff + tc * se, 3)
            sig = bool(((lo > 0) or (hi < 0)) and len(with_v) >= min_with_for_sig)
        # Zweiseitiger p-Wert. Normalapproximation — bei den hier ueblichen
        # Gruppengroessen (dutzende bis hunderte Intervalle) vertretbar; sie ist
        # bei kleinen df etwas ZU optimistisch, was die FDR-Korrektur konservativ
        # nur teilweise auffaengt. Deshalb bleibt die KI-basierte Bewertung die
        # fuehrende Groesse, der p-Wert dient der Mehrfachtest-Korrektur.
        pval = round(2.0 * (1.0 - _norm_cdf(abs(eff / se))), 6)
    return round(eff, 3), (round(se, 3) if se is not None else None), lo, hi, sig, pval


def _citation_points():
    """Zitat-Zeitreihe je Marke aus den versionierten Peec-Quellen-Snapshots.

    Quelle: data/peec_snapshots/<ENDE>_sources.json (wird vom Montags-Task
    angelegt, eingefuehrt 19.07.2026). Je Snapshot und Marke die Summe der
    citation_count ueber alle Domains, die dieser Marke gehoeren.
    """
    pts = {}
    if not PEEC_SNAP_DIR.is_dir():
        return pts, []
    files = sorted(PEEC_SNAP_DIR.glob("*_sources.json"))
    stamps = []
    for f in files:
        stamp = f.name.split("_")[0]
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        stamps.append(stamp)
        for row in data.get("domains") or []:
            b = _fp_dom2brand(row.get("domain"))
            if not b:
                continue
            pts.setdefault(b, {})
            pts[b][stamp] = pts[b].get(stamp, 0) + (row.get("cit") or 0)
    return pts, sorted(set(stamps))



def build_intervals(series_by_brand, events_by_brand_day, types, lag_days=0,
                    respect_breaks=True, only_days=None):
    """Baut Intervall-Punkte aus einer SoV-Reihe und gezaehlten Ereignissen.

    20.07.2026: Diese Logik lag FUENFMAL nahezu identisch im Modul — im Hauptmodell,
    in der Funnel-Schichtung, in der Zitat-Zielgroesse, im Lag-Scan und in der
    Fanout-Sensitivitaet. Genau deshalb lief sie auseinander: Der Strukturbruch-Filter
    wurde nur an EINER der fuenf Stellen eingebaut, die Markennormalisierung an einer
    anderen. Der Sprung vom 21.07. (Markenerweiterung 7 -> 25, ERGO-SoV 13,96 % ->
    7,01 %) waere in den vier Nebenbloecken als Effekt gelesen worden.

    Parameter:
      series_by_brand      {marke: [(tag, wert), ...]} — aufsteigend sortiert
      events_by_brand_day  {marke: {tag: {typ: anzahl}}}
      types                Liste der zu zaehlenden Ereignistypen
      lag_days             Ereignisfenster um lag_days nach hinten verschieben
      respect_breaks       Intervalle ueber einem Strukturbruch verwerfen
      only_days            optional: nur Intervalle, deren SPANNE ausschliesslich
                           aus diesen Tagen besteht (nicht nur die Endpunkte —
                           das war der Fehler in der Fanout-Sensitivitaet)

    Liefert (punkte, verworfen_wegen_bruch).
    """
    points, skipped = [], []
    for brand, ser in (series_by_brand or {}).items():
        for i in range(len(ser) - 1):
            a, ya = ser[i]
            b, yb = ser[i + 1]
            if respect_breaks and _spans_break(brand, a, b):
                skipped.append({"brand": brand, "von": a, "bis": b})
                continue
            if only_days is not None:
                # Die ganze Spanne muss im erlaubten Tagesbereich liegen. Nur die
                # Endpunkte zu pruefen liesse Ereignisse aus ausgeschlossenen Tagen
                # weiterhin einfliessen.
                if not (a in only_days and b in only_days):
                    continue
            span = max(1, _days_between(a, b))
            wa = _shift_day(a, -lag_days) if lag_days else a
            wb = _shift_day(b, -lag_days) if lag_days else b
            cnt = {}
            for t in types:
                c = 0
                for day, tc in (events_by_brand_day.get(brand) or {}).items():
                    if wa <= day < wb:
                        c += tc.get(t, 0)
                cnt[t] = c / span
            points.append({"brand": brand, "days": span, "time": a,
                           "y": (yb - ya) / span, "x": cnt})
    return points, skipped


def count_events_by_brand_day(events, type_filter=None, key_fn=None):
    """{marke: {tag: {typ: anzahl}}} aus deduplizierten Impact-Events."""
    out = {}
    for e in dedup_impact_events(events):
        b, day = e.get("brand"), _day(e.get("timestamp"))
        if not b or not day:
            continue
        t = key_fn(e) if key_fn else e.get("event_type")
        if not t or (type_filter and t not in type_filter):
            continue
        out.setdefault(b, {}).setdefault(day, {})
        out[b][day][t] = out[b][day].get(t, 0) + 1
    return out


def citation_target_analysis(events):
    """Zitate als ZWEITE Zielgroesse neben Share of Voice.

    Warum: SoV ist ein traeger Anteil zwischen wenigen Marken; die gemessenen
    Effekte liegen bisher im Rauschen (Konfidenzintervalle ueberspannen die Null).
    Zitate sind Zaehlgroessen im vier- bis fuenfstelligen Bereich und liegen
    kausal NAEHER an der Ursache: Seitenaenderung -> Quelle wird gelesen/zitiert
    -> Marke wird genannt. Bisher testen wir Anfang gegen Ende der Kette.

    Der Block rechnet erst, wenn genug Snapshots vorliegen. Die Reihe beginnt
    mit dem ersten Snapshot (19.07.2026) — vorher gibt es hier bewusst NICHTS
    ausser einer Statusmeldung.
    """
    series, stamps = _citation_points()
    n_pts = len(stamps)
    base = {
        "ziel": "Zitate je Marke (Peec citation_count, Summe ueber die Domains der Marke)",
        "quelle": "data/peec_snapshots/<ENDE>_sources.json",
        "n_messpunkte": n_pts,
        "messpunkte": stamps,
        "min_messpunkte": MIN_CITATION_POINTS,
        "methode": ("Je Intervall zwischen zwei Snapshots: delta_Zitate je Marke gegen die "
                    "Ereigniszahl je Typ im selben Fenster — dieselbe Event-Study-Logik wie "
                    "beim SoV-Modell, nur mit der frueheren Zielgroesse in der Wirkungskette."),
        "grenzen": ("Peec-Zitatzahlen stammen aus einem rollierenden 30-Tage-Fenster; zwei "
                    "aufeinanderfolgende Snapshots ueberlappen sich also stark. Die Reihe ist "
                    "gegluettet und traege — Effekte zeigen sich verzoegert und daempft. "
                    "Ausserdem deckt der Export nur die Top-Domains ab, nicht den Long Tail."),
    }
    if n_pts < MIN_CITATION_POINTS:
        base["available"] = False
        base["grund"] = (
            f"Erst {n_pts} Snapshot(s) vorhanden, benoetigt werden {MIN_CITATION_POINTS}. "
            "Die Zitat-Zeitreihe beginnt mit dem ersten Quellen-Snapshot vom 19.07.2026 und "
            "waechst woechentlich mit dem Montags-Task. KEINE Aussage moeglich — "
            "das ist ausdruecklich kein gemessener Nulleffekt."
        )
        return base

    ev = dedup_impact_events(events)
    bydays = {}
    for e in ev:
        bydays.setdefault(e.get("brand"), {}).setdefault(_day(e.get("timestamp")), {})
        t = e.get("event_type")
        d = bydays[e["brand"]][_day(e.get("timestamp"))]
        d[t] = d.get(t, 0) + 1

    ser_map = {b: sorted(m.items()) for b, m in series.items()}
    points, _skip = build_intervals(ser_map, bydays, IMPACT_TYPES)
    if _skip:
        base["intervalle_uebersprungen_bruch"] = len(_skip)

    if len(points) < 4:
        base["available"] = False
        base["grund"] = (f"Nur {len(points)} Intervall-Punkte — zu wenig fuer eine Schaetzung. "
                         "KEINE Aussage, kein Nulleffekt.")
        return base

    res = {}
    for t in IMPACT_TYPES:
        xs = [p["x"].get(t, 0.0) for p in points]
        ys = [p["y"] for p in points]
        n_with = sum(1 for x in xs if x > 0)
        if n_with < 3:
            res[t] = {"label": TYPE_LABEL.get(t, t), "n_with_event": n_with,
                      "available": False,
                      "grund": "zu wenige Intervalle mit diesem Ereignis"}
            continue
        r = pearson(xs, ys)
        eff, se, lo, hi, sig, pv = _effect_ci(xs, ys)
        res[t] = {"label": TYPE_LABEL.get(t, t), "pearson_r": r,
                  "avg_citation_effect": eff, "effect_se": se,
                  "ci95_low": lo, "ci95_high": hi, "significant": sig, "p_value": pv,
                  "n_intervals": len(points),
                  "n_with_event": n_with, "type_confidence": type_confidence(n_with),
                  "available": True}
    base["available"] = True
    base["n_intervalle"] = len(points)
    base["marken"] = sorted(series)
    base["impact"] = res
    return base


def funnel_stratified_analysis(events, mv_prior=None):
    """Sichtbarkeit geschichtet nach Funnel-Stufe (Awareness/Consideration/Decision).

    Warum: Awareness und Decision verhalten sich nachweislich unterschiedlich
    (Sichtbarkeit 9,7 % vs. 20,9 %, Messung 18.06.-18.07.2026). Ein gemeinsames
    Modell mittelt das weg. Die Schichtung verdreifacht ausserdem die Datenpunkte
    bei gleichem Zeitraum.

    Braucht eine ZEITREIHE je Tag — data/peec_segments.json ist nur ein
    30-Tage-Aggregat und reicht dafuer NICHT. Der Montags-Task exportiert ab
    19.07.2026 zusaetzlich peec_segments_history.csv (Dimensionen date + tag_id).
    """
    base = {
        "quelle": "data/peec_segments_history.csv (Dimensionen date x tag_id)",
        "min_messpunkte": MIN_FUNNEL_POINTS,
        "methode": ("Je Funnel-Stufe eine eigene SoV-Zeitreihe je Marke; Event-Study wie im "
                    "Hauptmodell, aber innerhalb der Stufe. Ein Prompt kann mehrere Tags "
                    "tragen — die Schichten sind NICHT ueberschneidungsfrei."),
    }
    if not PEEC_SEGMENTS_HIST.exists():
        n_static = 0
        if PEEC_SEGMENTS_FILE.exists():
            try:
                n_static = len(json.loads(PEEC_SEGMENTS_FILE.read_text(encoding="utf-8"))
                               .get("segments") or [])
            except Exception:  # noqa: BLE001
                n_static = 0
        base["available"] = False
        base["grund"] = (
            "Noch keine Tag-Zeitreihe vorhanden. data/peec_segments.json enthaelt "
            f"{n_static} Marke-x-Tag-Zellen, aber nur als 30-Tage-Aggregat zu EINEM Stichtag — "
            "daraus laesst sich keine Veraenderung ueber die Zeit rechnen. Der Montags-Task "
            "exportiert ab 19.07.2026 zusaetzlich peec_segments_history.csv; die Reihe waechst "
            "ab dann woechentlich. KEINE Aussage moeglich — kein gemessener Nulleffekt."
        )
        return base

    rows = []
    try:
        import csv
        with open(PEEC_SEGMENTS_HIST, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh, delimiter=";"):
                rows.append(r)
    except Exception as ex:  # noqa: BLE001
        base["available"] = False
        base["grund"] = f"peec_segments_history.csv nicht lesbar: {str(ex)[:120]}"
        return base

    series = {}
    for r in rows:
        tag = (r.get("tag") or r.get("tag_name") or "").strip()
        brand = _norm_brand(r.get("marke") or r.get("brand") or "")
        day = (r.get("datum") or r.get("date") or "").strip()[:10]
        try:
            sov = float(str(r.get("share_of_voice") or "").replace(",", ".")) * 100.0
        except (TypeError, ValueError):
            continue
        if not (tag and brand and day):
            continue
        series.setdefault(tag, {}).setdefault(brand, {})[day] = sov

    days_per_tag = {t: len({d for b in v.values() for d in b}) for t, v in series.items()}
    usable = {t: n for t, n in days_per_tag.items() if n >= MIN_FUNNEL_POINTS}
    if not usable:
        base["available"] = False
        base["grund"] = (f"Tag-Zeitreihe vorhanden, aber kein Tag erreicht {MIN_FUNNEL_POINTS} "
                         f"Messtage (max. {max(days_per_tag.values()) if days_per_tag else 0}). "
                         "KEINE Aussage moeglich.")
        base["messtage_je_tag"] = days_per_tag
        return base

    # ---- Event-Study INNERHALB jeder Stufe ---------------------------------
    ev = dedup_impact_events(events)
    bydays = {}
    for e in ev:
        b = e.get("brand")
        day = _day(e.get("timestamp"))
        if not b or not day:
            continue
        bydays.setdefault(b, {}).setdefault(day, {})
        t = e.get("event_type")
        bydays[b][day][t] = bydays[b][day].get(t, 0) + 1

    per_tag = {}
    _skipped_total = 0
    for tag in sorted(usable):
        _sm = {b: sorted(m.items()) for b, m in series[tag].items()}
        points, _skip = build_intervals(_sm, bydays, IMPACT_TYPES)
        _skipped_total += len(_skip)
        if len(points) < 10:
            per_tag[tag] = {"available": False,
                            "grund": f"nur {len(points)} Intervall-Punkte",
                            "n_intervalle": len(points)}
            continue
        imp = {}
        for t in IMPACT_TYPES:
            xs = [pt["x"].get(t, 0.0) for pt in points]
            ys = [pt["y"] for pt in points]
            n_with = sum(1 for x in xs if x > 0)
            if n_with < 3:
                imp[t] = {"label": TYPE_LABEL.get(t, t), "n_with_event": n_with,
                          "available": False, "grund": "zu wenige Intervalle mit Ereignis"}
                continue
            r = pearson(xs, ys)
            eff, se, lo, hi, sig, pv = _effect_ci(xs, ys)
            imp[t] = {"label": TYPE_LABEL.get(t, t), "pearson_r": r,
                      "avg_sov_effect_pp": eff, "effect_se_pp": se,
                      "ci95_low_pp": lo, "ci95_high_pp": hi, "significant": sig, "p_value": pv,
                      "n_intervals": len(points),
                      "n_with_event": n_with, "type_confidence": type_confidence(n_with),
                      "available": True}
        # Niveau je Stufe (letzter Messtag) — fuer die Einordnung im Dashboard
        lvl = {}
        for brand, bs in series[tag].items():
            if bs:
                lvl[brand] = round(bs[max(bs)], 3)
        # Multivariat INNERHALB der Stufe: kontrolliert die Treiber gegeneinander
        # (Marken- + Zeit-Fixed-Effects). Ohne diesen Schritt bliebe die Schichtung
        # anfaellig fuer Scheinkorrelationen durch Drittvariablen — genau das, was
        # das Hauptmodell laengst abfaengt.
        mv = None
        try:
            mv = multivariate_impact(points, prior_mean=mv_prior)
            # Wild-Cluster-Bootstrap auch hier — sonst haetten die Stufenmodelle nur
            # prob_direction (ein Posterior-Mass) und waeren damit optimistischer
            # bewertet als das Hauptmodell. Geclustert nach Marke, wie dort.
            # Signifikanz je Stufe ueber CLUSTER-ROBUSTE Standardfehler (Cluster = Marke),
            # NICHT ueber den Wild-Cluster-Bootstrap wie im Hauptmodell.
            # Grund, offen benannt: Der exakte Bootstrap rechnet 2^G Ridge-Fits je Treiber.
            # Ueber die Stufen mit je 780 Punkten laeuft das minutenlang und sprengt den
            # Nightly. Die Sandwich-Variante kostet einen Bruchteil.
            # PREIS DIESER ENTSCHEIDUNG: Mit G=7 Marken ist die asymptotische
            # Cluster-Inferenz unzuverlaessig (Faustregel G>=30) und tendenziell ZU
            # optimistisch. Die Stufen-p-Werte sind deshalb schwaecher belegt als die
            # des Hauptmodells und ausdruecklich als indikativ zu lesen.
            if mv.get("available") and mv.get("types_used"):
                _use = mv["types_used"]
                _Y, _Xs, _sd, _kabs = _design(points, _use, "x")
                _lam = len(_Xs) * 0.5
                _beta, _Ai, _s2 = _ridge_posterior(_Xs, _Y, _lam)
                _cl = [pt["brand"] for pt in points]
                _V, _G = _cluster_robust_var(_Xs, _Y, _beta, _Ai, _cl)
                mv["inferenz"] = ("cluster-robuste Sandwich-SE, Cluster = Marke (G=%s). Das "
                                  "Hauptmodell nutzt den exakten Wild-Cluster-Bootstrap; der ist "
                                  "hier zu teuer (2^G Ridge-Fits je Treiber auf %d Punkten). "
                                  "Die Sandwich-Variante rechnet die Ridge-Schrumpfung nicht mit "
                                  "und unterschaetzt die Unsicherheit tendenziell — deshalb gilt "
                                  "ein Effekt hier nur als gesichert, wenn zusaetzlich die "
                                  "Bayes-Richtungswahrscheinlichkeit >= 97,5 %% liegt."
                                  % (_G, len(points)))
                if _V:
                    for _j, _t in enumerate(_use):
                        _var = _V[_j][_j] if _j < len(_V) else None
                        if not _var or _var <= 0:
                            continue
                        _se = (_var ** 0.5) / _sd[_j]
                        _mu = _beta[_j] / _sd[_j]
                        _z = abs(_mu / _se) if _se > 0 else 0.0
                        _pv = round(2.0 * (1.0 - _norm_cdf(_z)), 4)
                        _rec = mv["coefficients"].get(_t)
                        if _rec:
                            _rec["cluster_se"] = round(_se, 4)
                            _rec["cluster_p"] = _pv
                            # "significant" wird NICHT hier gesetzt — erst nach der
                            # FDR-Korrektur weiter unten, und dann nur bei Einigkeit
                            # beider Unsicherheitsmasse (siehe Begruendung dort).
                            _rec["significant"] = False
        except Exception as _ex:  # noqa: BLE001
            mv = {"available": False, "note": f"multivariat fehlgeschlagen: {str(_ex)[:120]}"}
        per_tag[tag] = {"available": True, "n_intervalle": len(points),
                        "marken": sorted(series[tag]), "niveau_letzter_tag": lvl,
                        "impact": imp, "multivariat": mv}

    # ---- Mehrfachtest-Korrektur ueber die GESAMTE Schichtung ----------------
    # Ohne sie waere der Block methodisch angreifbar: 10 Tags x 11 Treibertypen
    # sind rund 110 Tests. Bei alpha=0,05 waeren allein zufaellig ~5 "signifikante"
    # Ergebnisse zu erwarten. Das Hauptmodell korrigiert nach Benjamini-Hochberg —
    # die Schichtung muss es genauso tun, sonst produziert gerade der praezisere
    # Block die unsaubereren Aussagen.
    tests = []
    for _tag, _blk in per_tag.items():
        for _t, _im in (_blk.get("impact") or {}).items():
            if isinstance(_im.get("p_value"), (int, float)):
                tests.append(_im)
    # Die multivariaten Stufen-Tests werden separat korrigiert (eigene Familie,
    # anderes Verfahren) — ueber ihre Wild-Cluster-p-Werte.
    # Eigene Testfamilie, eigene Korrektur — ueber die cluster-robusten p-Werte.
    _apply_fdr({"funnel_mv": {t: (b.get("multivariat") or {}).get("coefficients") or {}
                              for t, b in per_tag.items()}},
               key="cluster_p", out="cluster_p_fdr")

    # "Gesichert" nur, wenn BEIDE Unsicherheitsmasse zustimmen:
    #   (a) FDR-korrigiertes q < 0,05 aus der cluster-robusten Sandwich-Varianz und
    #   (b) Bayes-Richtungswahrscheinlichkeit >= 97,5 % aus dem Ridge-Posterior.
    # Warum so konservativ: Beim ersten Lauf (20.07.2026) widersprachen sich die
    # beiden deutlich — "Unbranded / Seitenaenderungen" kam auf cluster_p = 0,0003
    # bei prob_direction 0,586, also praktisch einem Muenzwurf im Posterior. Solche
    # Widersprueche entstehen, wenn die Sandwich-Varianz die Ridge-Schrumpfung nicht
    # mitrechnet und die Unsicherheit dadurch unterschaetzt. Statt eines der beiden
    # Masse zu bevorzugen, verlangen wir Einigkeit — im Zweifel lieber kein Befund
    # als ein falscher.
    _mv_sig = 0
    for _tag, _blk in per_tag.items():
        for _t, _rec in ((_blk.get("multivariat") or {}).get("coefficients") or {}).items():
            _q = _rec.get("cluster_p_fdr")
            _pd = _rec.get("prob_direction")
            _ok = bool(isinstance(_q, (int, float)) and _q < 0.05
                       and isinstance(_pd, (int, float)) and _pd >= 0.975
                       and (_rec.get("n_with_event") or 0) >= 15)
            _rec["significant"] = _ok
            if not _ok and isinstance(_q, (int, float)) and _q < 0.05:
                _rec["hinweis"] = ("q < 0,05, aber die Bayes-Richtungswahrscheinlichkeit "
                                   "erreicht 97,5 % nicht — die beiden Unsicherheitsmasse sind "
                                   "sich uneinig, deshalb NICHT als gesichert gewertet.")
            _mv_sig += 1 if _ok else 0
    n_tests = len(tests)
    if n_tests:
        tests.sort(key=lambda d: d["p_value"])
        prev = 1.0
        for i in range(n_tests - 1, -1, -1):
            q = min(prev, tests[i]["p_value"] * n_tests / (i + 1))
            tests[i]["p_fdr"] = round(min(q, 1.0), 4)
            prev = q
        for d in tests:
            # "gesichert" nach Korrektur nur, wenn ZUSAETZLICH die Mindest-Datenbasis
            # steht — gleiche Konvention wie im Hauptmodell.
            d["significant_fdr"] = bool(d["p_fdr"] < 0.05 and (d.get("n_with_event") or 0) >= 8)
    base["intervalle_uebersprungen_bruch"] = _skipped_total
    base["fdr"] = {
        "n_gesichert_multivariat": _mv_sig,
        "n_tests": n_tests, "alpha": 0.05, "verfahren": "Benjamini-Hochberg",
        "n_signifikant_vor_korrektur": sum(1 for d in tests if (d.get("p_value") or 1) < 0.05),
        "n_signifikant_nach_korrektur": sum(1 for d in tests if d.get("significant_fdr")),
        "hinweis": ("Korrigiert wird ueber alle Tag-x-Treiber-Tests dieses Blocks. "
                    "EINSCHRAENKUNG: Benjamini-Hochberg setzt unabhaengige oder positiv "
                    "abhaengige Tests voraus. Die Stufen sind es nicht — ein Prompt kann "
                    "mehrere Tags tragen, die Schichten ueberlappen sich also. Die Korrektur "
                    "ist damit eine Naeherung; q-Werte knapp um 0,05 nicht ueberinterpretieren."),
    }

    base["available"] = True
    base["messtage_je_tag"] = days_per_tag
    base["auswertbare_tags"] = sorted(usable)
    base["je_tag"] = per_tag
    # Die vollen Reihen bewusst NICHT hier ablegen (8.000+ Zeilen blaehen die
    # Ausgabedatei auf) — sie stehen in data/peec_segments_history.csv.
    base["reihen_quelle"] = str(PEEC_SEGMENTS_HIST)
    return base


def page_change_by_type(events):
    """page_change nach Aenderungsart aufgeschluesselt (Preis/Leistung/FAQ/Copy/Struktur).

    Warum: page_change ist bisher EIN Topf. Wenn Preisaenderungen wirken und
    Copy-Aenderungen nicht, mittelt sich das im gemeinsamen Topf zu genau der
    Null heraus, die das Modell heute zeigt.

    Datenlage 19.07.2026: Der Gemini-Klassifikator war zu 99,7 % ausgefallen
    (Thinking-Tokens frassen maxOutputTokens auf, finishReason MAX_TOKENS —
    behoben in geo-visibility-tool 144b018). Brauchbare Klassifikationen
    entstehen daher erst ab dem naechsten Crawl; Alt-Events blieben unklassifiziert,
    ein Backfill ueber die gespeicherten added_lines/removed_lines waere moeglich.
    """
    total = 0
    classified = 0
    errors = 0
    by_type = {}
    for e in events:
        if e.get("event_type") != "page_change":
            continue
        total += 1
        c = (e.get("detail") or {}).get("classification")
        if isinstance(c, dict) and c.get("type"):
            classified += 1
            k = str(c.get("type")).lower()
            by_type.setdefault(k, {"n": 0, "brands": set()})
            by_type[k]["n"] += 1
            if e.get("brand"):
                by_type[k]["brands"].add(e["brand"])
        elif isinstance(c, dict):
            errors += 1
    cov = (classified / total) if total else 0.0
    out = {
        "n_page_change": total,
        "n_klassifiziert": classified,
        "n_klassifikations_fehler": errors,
        "abdeckung": round(cov, 4),
        "min_abdeckung": MIN_CLASS_COVERAGE,
        "methode": ("Aenderungsart kommt aus dem Gemini-Diff-Klassifikator des GEO-Crawls "
                    "(Feld detail.classification.type). Erst ab ausreichender Abdeckung wird "
                    "die Aufschluesselung berichtet."),
    }
    if cov < MIN_CLASS_COVERAGE:
        out["available"] = False
        out["grund"] = (
            f"Nur {classified} von {total} page_change-Events tragen eine brauchbare "
            f"Klassifikation ({cov*100:.1f} %), noetig sind {MIN_CLASS_COVERAGE*100:.0f} %. "
            f"Ursache: Der Klassifikator war zu 99,7 % ausgefallen (Thinking-Tokens von "
            "gemini-2.5-flash frassen maxOutputTokens auf, finishReason MAX_TOKENS) — behoben "
            "am 19.07.2026 (geo-visibility-tool 144b018). Ab dem naechsten Crawl entstehen "
            "brauchbare Klassifikationen; Alt-Events brauchen einen Backfill. KEINE Aussage "
            "zur Wirkung einzelner Aenderungsarten — kein gemessener Nulleffekt."
        )
        return out
    out["available"] = True
    out["nach_typ"] = {k: {"n": v["n"], "marken": sorted(v["brands"])}
                       for k, v in sorted(by_type.items(), key=lambda kv: -kv[1]["n"])}

    # ---- Event-Study JE AENDERUNGSART ---------------------------------------
    # Der eigentliche Zweck: Wenn Preisaenderungen wirken und Copy-Aenderungen
    # nicht, mittelt sich das im gemeinsamen page_change-Topf zu einer Null heraus.
    sov = build_sov_series_from_history()
    if not sov:
        out["wirkung_je_art"] = {"available": False,
                                 "grund": "Keine SoV-Historie verfuegbar."}
        return out
    bydays = {}
    for e in dedup_impact_events(events):
        if e.get("event_type") != "page_change":
            continue
        b, day = e.get("brand"), _day(e.get("timestamp"))
        c = (e.get("detail") or {}).get("classification")
        art = c.get("type") if isinstance(c, dict) else None
        if not (b and day and art):
            continue
        bydays.setdefault(b, {}).setdefault(day, {})
        bydays[b][day][art] = bydays[b][day].get(art, 0) + 1

    arten = sorted(by_type, key=lambda k: -by_type[k]["n"])
    points, _skip = build_intervals(sov, bydays, arten)
    res = {}
    for art in arten:
        xs = [pt["x"].get(art, 0.0) for pt in points]
        ys = [pt["y"] for pt in points]
        n_with = sum(1 for x in xs if x > 0)
        if n_with < 8:
            res[art] = {"available": False, "n_with_event": n_with,
                        "grund": "weniger als 8 Intervalle mit dieser Aenderungsart"}
            continue
        r = pearson(xs, ys)
        eff, se, lo, hi, sig, pv = _effect_ci(xs, ys)
        res[art] = {"available": True, "pearson_r": round(r, 3) if r is not None else None,
                    "avg_sov_effect_pp": eff, "effect_se_pp": se,
                    "ci95_low_pp": lo, "ci95_high_pp": hi,
                    "p_value": pv, "significant": sig,
                    "n_intervals": len(points), "n_with_event": n_with,
                    "n_events": by_type[art]["n"]}
    # Mehrfachtest-Korrektur ueber die Aenderungsarten
    tests = [v for v in res.values() if isinstance(v.get("p_value"), (int, float))]
    if tests:
        tests.sort(key=lambda d: d["p_value"])
        prev = 1.0
        for i in range(len(tests) - 1, -1, -1):
            q = min(prev, tests[i]["p_value"] * len(tests) / (i + 1))
            tests[i]["p_fdr"] = round(min(q, 1.0), 4)
            prev = q
        for d in tests:
            d["significant_fdr"] = bool(d["p_fdr"] < 0.05 and (d.get("n_with_event") or 0) >= 8)
    out["wirkung_je_art"] = {
        "available": True, "n_intervalle": len(points), "je_art": res,
        "n_tests": len(tests),
        "n_gesichert": sum(1 for d in tests if d.get("significant_fdr")),
        "methode": ("Wie das Hauptmodell, aber page_change nach Aenderungsart getrennt. "
                    "Benjamini-Hochberg ueber die Arten."),
        "grenzen": ("Die Zuordnung stammt aus einem LLM-Klassifikator (Gemini) und ist nicht "
                    "handgepruft. 'sonstiges' und 'struktur' sind Sammelkategorien und "
                    "inhaltlich schwach — Befunde dort sind mit Vorsicht zu lesen. Preis- und "
                    "Leistungsaenderungen sind die inhaltlich schaerfsten Kategorien, aber "
                    "auch die seltensten."),
    }
    return out



LAG_CANDIDATES = [0, 3, 7, 14, 28]


def _shift_day(day, delta):
    """Datum als YYYY-MM-DD um delta Tage verschieben."""
    from datetime import datetime as _dt, timedelta as _td
    try:
        return (_dt.strptime(day, "%Y-%m-%d") + _td(days=delta)).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return day


def lag_analysis(events):
    """Prueft, ob Wirkungen VERZOEGERT auftreten.

    Warum das noetig war: Das Modell unterstellte bisher, dass ein Ereignis im
    selben Intervall wirkt, in dem es stattfindet. Die Konstante LAG_DAYS stand
    zwar im Code und wurde in der Ausgabe als "lag_days: 0" berichtet — sie wurde
    beim Zaehlen aber NIE angewandt. Es war also keine gepruefte Entscheidung,
    sondern eine ungetestete Annahme, die wie eine Einstellung aussah.

    Plausibel ist eine Verzoegerung: Eine geaenderte Seite muss erst neu gecrawlt,
    indexiert und von den Engines abgerufen werden. Getestet werden deshalb
    mehrere Versaetze; je Versatz zaehlen Ereignisse aus dem um `lag` Tage NACH
    HINTEN verschobenen Fenster gegen die SoV-Aenderung im Originalfenster.

    Ausgewiesen wird der Versatz mit der staerksten Korrelation je Treiber —
    ausdruecklich als EXPLORATIVE Suche: Wer fuenf Versaetze durchprobiert und den
    besten meldet, findet auch in Rauschen ein Maximum. Deshalb steht neben dem
    besten Wert immer der Verlauf ueber alle Versaetze, damit erkennbar ist, ob
    ein Muster vorliegt oder nur ein Ausreisser.
    """
    sov = build_sov_series_from_history()
    if not sov:
        return {"available": False, "grund": "Keine SoV-Historie verfuegbar."}
    ev = dedup_impact_events(events)
    bydays = {}
    for e in ev:
        b, day = e.get("brand"), _day(e.get("timestamp"))
        if not b or not day:
            continue
        bydays.setdefault(b, {}).setdefault(day, {})
        t = e.get("event_type")
        bydays[b][day][t] = bydays[b][day].get(t, 0) + 1

    per_lag = {}
    for lag in LAG_CANDIDATES:
        points, _skip = build_intervals(sov, bydays, IMPACT_TYPES, lag_days=lag)
        res = {}
        for t in IMPACT_TYPES:
            xs = [pt["x"].get(t, 0.0) for pt in points]
            ys = [pt["y"] for pt in points]
            n_with = sum(1 for x in xs if x > 0)
            if n_with < 8:
                continue
            r = pearson(xs, ys)
            eff, se, lo, hi, sig, pv = _effect_ci(xs, ys)
            res[t] = {"label": TYPE_LABEL.get(t, t), "pearson_r": r,
                      "avg_sov_effect_pp": eff, "ci95_low_pp": lo, "ci95_high_pp": hi,
                      "p_value": pv, "significant": sig, "n_with_event": n_with}
        per_lag[lag] = {"n_intervalle": len(points), "impact": res}

    # Bester Versatz je Treiber (nach |r|), plus vollstaendiger Verlauf
    best = {}
    for t in IMPACT_TYPES:
        reihe = []
        for lag in LAG_CANDIDATES:
            rec = (per_lag.get(lag, {}).get("impact") or {}).get(t)
            if rec and rec.get("pearson_r") is not None:
                reihe.append({"lag": lag, "r": round(rec["pearson_r"], 3),
                              "effekt_pp": rec.get("avg_sov_effect_pp"),
                              "p": rec.get("p_value"), "gesichert": rec.get("significant")})
        if not reihe:
            continue
        top = max(reihe, key=lambda d: abs(d["r"]))
        # Musterbewertung: Eine echte Wirkungsverzoegerung sollte einen glatten
        # Verlauf zeigen (Anstieg, Gipfel, Abfall). Springt das Vorzeichen mehrfach,
        # ist der "beste" Versatz mit hoher Wahrscheinlichkeit ein Rauschmaximum.
        vz = [1 if x["r"] > 0 else (-1 if x["r"] < 0 else 0) for x in reihe]
        wechsel = sum(1 for i in range(1, len(vz)) if vz[i] != 0 and vz[i - 1] != 0 and vz[i] != vz[i - 1])
        if len(reihe) < 3:
            muster = "zu wenige Versaetze fuer eine Musterbewertung"
        elif wechsel >= 2:
            muster = ("springend — %d Vorzeichenwechsel ueber %d Versaetze. Der beste Versatz "
                      "ist hier hoechstwahrscheinlich ein Rauschmaximum, kein Wirkungsmuster."
                      % (wechsel, len(reihe)))
        elif wechsel == 1:
            muster = "ein Vorzeichenwechsel — uneindeutig"
        else:
            muster = "einheitliches Vorzeichen ueber alle Versaetze"
        best[t] = {"label": TYPE_LABEL.get(t, t), "bester_lag": top["lag"],
                   "r_bei_bestem_lag": top["r"], "effekt_pp": top["effekt_pp"],
                   "gesichert": top["gesichert"], "verlauf": reihe,
                   "vorzeichenwechsel": wechsel, "musterbewertung": muster,
                   "r_bei_lag0": (round(reihe[0]["r"], 3)
                                  if reihe and reihe[0]["lag"] == 0 else None)}

    n_sig = sum(1 for lag in per_lag for t, r in (per_lag[lag]["impact"] or {}).items()
                if r.get("significant"))
    return {
        "available": True,
        "getestete_lags": LAG_CANDIDATES,
        "je_lag": {str(k): {"n_intervalle": v["n_intervalle"],
                            "n_treiber": len(v["impact"])} for k, v in per_lag.items()},
        "bester_lag_je_treiber": best,
        "n_gesichert_ueber_alle_lags": n_sig,
        "fazit": (("Kein Treiber zeigt ueber die Versaetze ein glattes Muster "
                   "(%d von %d mit mehrfachem Vorzeichenwechsel) und keiner ist bei "
                   "irgendeinem Versatz gesichert. Es gibt damit AKTUELL keinen Hinweis "
                   "auf eine messbare Wirkungsverzoegerung — was nicht heisst, dass es "
                   "keine gibt: bei dieser Datenlage waere sie schlicht nicht sichtbar.")
                  % (sum(1 for b in best.values() if (b.get("vorzeichenwechsel") or 0) >= 2),
                     len(best))) if not n_sig else
                 ("%d Treiber-Versatz-Kombinationen sind gesichert — vor der Interpretation "
                  "die Musterbewertung im Verlauf pruefen." % n_sig),
        "methode": ("Je Versatz werden Ereignisse aus dem um `lag` Tage nach hinten "
                    "verschobenen Fenster gegen die SoV-Aenderung im Originalfenster "
                    "gezaehlt. Getestet: " + ", ".join(str(l) for l in LAG_CANDIDATES) + " Tage."),
        "grenzen": ("EXPLORATIVE Suche ueber mehrere Versaetze: Wer fuenf Varianten testet "
                    "und die staerkste meldet, findet auch in reinem Rauschen ein Maximum. "
                    "Der ausgewiesene beste Versatz ist deshalb ein HINWEIS, keine Schaetzung "
                    "der wahren Wirkungsverzoegerung. Aussagekraeftig wird er erst, wenn der "
                    "Verlauf ueber die Versaetze ein Muster zeigt (Anstieg, Gipfel, Abfall) "
                    "statt zu springen. Die p-Werte sind NICHT fuer die Mehrfachsuche "
                    "korrigiert."),
    }



PEEC_FANOUT_FILE = Path("data/peec_fanout_rate.csv")
# Ab welcher Web-Such-Rate ein Tag als "web-gestuetzt" gilt. 10 % trennt die
# gemessenen Regime sauber (Normalbetrieb 20-27 %, Einbruchphase 1-5 %).
FANOUT_HIGH = 0.10


def load_fanout_rate():
    """Taegliche Web-Such-Rate der Peec-Engines (Anteil Antworten mit Web-Suche)."""
    out = {}
    if not PEEC_FANOUT_FILE.exists():
        return out
    try:
        import csv
        with open(PEEC_FANOUT_FILE, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh, delimiter=";"):
                d = (r.get("datum") or "").strip()[:10]
                try:
                    v = float(str(r.get("fanout_rate") or "").replace(",", "."))
                except (TypeError, ValueError):
                    continue
                if d:
                    out[d] = v
    except Exception:  # noqa: BLE001
        return {}
    return out


def fanout_regime_analysis(events):
    """Web-Such-Rate der Engines als Stoergroesse — und was passiert, wenn man
    auf die Tage einschraenkt, an denen die Engines ueberhaupt im Web suchen.

    Hintergrund (gemessen 18.06.-18.07.2026): Der Anteil der Antworten mit
    Web-Suche schwankt massiv — rund 27 % Ende Juni, Einbruch auf 1-3 % vom
    03. bis 09.07., danach Erholung auf ~24 %. Das ist eine Verhaltensaenderung
    der Engines, kein Messfehler.

    Warum das fuer das Treibermodell zentral ist: Antwortet eine Engine ohne
    Web-Suche, stammt die Markennennung aus dem Modellgedaechtnis. Eine in dieser
    Zeit geaenderte Webseite kann die Antwort GAR NICHT beeinflusst haben — der
    Wirkungskanal ist physisch zu. Intervalle aus solchen Phasen verduennen jeden
    echten Effekt Richtung Null, ohne dass das Modell es merkt.

    WICHTIG zur Reichweite: Die Rate misst das Verhalten der PEEC-Engines. Die
    Zielgroesse dieses Blocks ist deshalb die Peec-Sichtbarkeit je Funnel-Stufe,
    NICHT die SoV-Reihe des eigenen Crawls — die stammt aus eigenen API-Abrufen
    mit eigenem Grounding-Verhalten. Beides zu mischen waere ein Quellenfehler.
    """
    rate = load_fanout_rate()
    base = {
        "quelle": str(PEEC_FANOUT_FILE),
        "schwelle": FANOUT_HIGH,
        "methode": ("Vergleicht die Event-Study je Funnel-Stufe auf ALLEN Tagen gegen die "
                    "Teilmenge der Tage mit hoher Web-Such-Rate. Ein Treiber, der nur ueber "
                    "Webinhalte wirken kann, sollte dort staerker sichtbar sein."),
        "reichweite": ("Gilt fuer die Peec-Sichtbarkeit. Die SoV-Reihe des eigenen Crawls "
                       "bleibt unberuehrt — dort gilt das Grounding-Verhalten der eigenen "
                       "API-Abrufe, das hier nicht gemessen wird."),
    }
    if not rate:
        base["available"] = False
        base["grund"] = ("Keine Fanout-Raten vorhanden. data/peec_fanout_rate.csv entsteht im "
                         "Montags-Export. KEINE Aussage moeglich — kein gemessener Nulleffekt.")
        return base

    days = sorted(rate)
    hi = [d for d in days if rate[d] >= FANOUT_HIGH]
    lo = [d for d in days if rate[d] < FANOUT_HIGH]
    base["n_tage"] = len(days)
    base["n_tage_web"] = len(hi)
    base["n_tage_ohne_web"] = len(lo)
    base["rate_min"] = round(min(rate.values()), 4)
    base["rate_max"] = round(max(rate.values()), 4)
    base["phasen_ohne_web"] = lo
    if len(hi) < 8 or len(lo) < 3:
        base["available"] = False
        base["grund"] = (f"Zu wenige Tage je Regime (web: {len(hi)}, ohne web: {len(lo)}) "
                         "fuer einen belastbaren Vergleich.")
        return base

    # Sensitivitaet: Funnel-Event-Study nur auf web-gestuetzten Tagen
    hist = PEEC_SEGMENTS_HIST
    if not hist.exists():
        base["available"] = False
        base["grund"] = "peec_segments_history.csv fehlt — Sensitivitaetsrechnung nicht moeglich."
        return base
    import csv as _csv
    series = {}
    with open(hist, encoding="utf-8-sig", newline="") as fh:
        for r in _csv.DictReader(fh, delimiter=";"):
            tag = (r.get("tag") or "").strip()
            brand = _norm_brand(r.get("marke") or "")
            day = (r.get("datum") or "").strip()[:10]
            try:
                sov = float(str(r.get("share_of_voice") or "").replace(",", ".")) * 100.0
            except (TypeError, ValueError):
                continue
            if tag and brand and day:
                series.setdefault(tag, {}).setdefault(brand, {})[day] = sov

    ev = dedup_impact_events(events)
    bydays = {}
    for e in ev:
        b, day = e.get("brand"), _day(e.get("timestamp"))
        if not b or not day:
            continue
        bydays.setdefault(b, {}).setdefault(day, {})
        t = e.get("event_type")
        bydays[b][day][t] = bydays[b][day].get(t, 0) + 1

    def study(tag, only_days=None):
        # 20.07.2026 Review-Fix (B7): Vorher wurden nur die INTERVALL-ENDEN gefiltert.
        # Ueberspannte ein Intervall die Einbruchphase, flossen deren Ereignisse
        # weiterhin ein — die Sensitivitaetsrechnung war schwaecher als beschrieben.
        # build_intervals verwirft jetzt Intervalle, deren ganze Spanne nicht im
        # erlaubten Tagesbereich liegt.
        _sm = {b: sorted(m.items()) for b, m in (series.get(tag) or {}).items()}
        pts, _sk = build_intervals(_sm, bydays, IMPACT_TYPES, only_days=only_days)
        return pts

    hiset = set(hi)
    verg = {}
    for tag in [t for t in FUNNEL_ORDER if t in series]:
        row = {}
        for label, sel in (("alle_tage", None), ("nur_web_tage", hiset)):
            pts = study(tag, sel)
            xs = [p["x"].get("page_change", 0.0) for p in pts]
            ys = [p["y"] for p in pts]
            n_with = sum(1 for x in xs if x > 0)
            if len(pts) < 10 or n_with < 5:
                row[label] = {"available": False, "n_punkte": len(pts), "n_mit_event": n_with}
                continue
            r = pearson(xs, ys)
            eff, se, lo_, hi_, sig, pv = _effect_ci(xs, ys)
            row[label] = {"available": True, "n_punkte": len(pts), "n_mit_event": n_with,
                          "pearson_r": round(r, 3) if r is not None else None,
                          "effekt_pp": eff, "ci95": [lo_, hi_], "p_value": pv,
                          "gesichert": sig}
        verg[tag] = row

    base["available"] = True
    base["sensitivitaet_seitenaenderungen"] = verg
    base["grenzen"] = ("Die Einschraenkung auf web-gestuetzte Tage ist eine Teilmengen-Analyse, "
                       "kein Experiment: Die Tage unterscheiden sich womoeglich noch in anderem "
                       "als der Web-Such-Rate. Ausserdem verkleinert sie die Datenbasis, was die "
                       "Konfidenzintervalle verbreitert — ein ausbleibender Effekt kann auch daran "
                       "liegen. Sie zeigt eine Richtung, sie beweist nichts.")
    return base



LEVEL_CELLS_FILE = Path("data/level_cells_history.jsonl")  # Marke x Thema x Tag (scripts/archive_level_cells.py)


def _load_level_cells():
    rows = []
    if not LEVEL_CELLS_FILE.exists():
        return rows
    for line in LEVEL_CELLS_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def price_level_pooled(max_days=45):
    """Gepooltes Preis-LEVEL-Modell (Panel Marke x Thema x Tag).

    Motivation: level_model_mundlak() laeuft auf EINEM Snapshot; dessen SoV je Zelle
    schwankt taeglich (LLM-Nichtdeterminismus). Der Ein-Tages-Within-Preis-Effekt lag
    dadurch grenzwertig bei p~0,06-0,1 - gemittelt ueber mehrere Tage bricht er nahe
    null zusammen, war also groesstenteils Tagesrauschen. Hier wird die Messgroesse JE
    ZELLE ueber mehrere saubere Tage GEMITTELT (ehrliche Rauschreduktion, kein Stapeln
    abhaengiger Tageszeilen), erst dann geschaetzt.

    Zwei Zielgroessen: Wirkung eines hoeheren/tieferen Relativpreises auf (a) die
    Sichtbarkeit (SoV) und (b) die Zitationen. Je grounded/ungrounded/combined, mit
    cluster-robuster SE, Wild-Cluster-Bootstrap, BH-FDR, Richtungswahrscheinlichkeit
    und Leave-one-out. Plus Tag-fuer-Tag-Stabilitaet des Between-Effekts.

    Quelle: data/level_cells_history.jsonl (scripts/archive_level_cells.py, taeglich)."""
    rows = _load_level_cells()
    if not rows:
        return {"available": False,
                "grund": ("Noch keine Level-Zellen-Historie (data/level_cells_history.jsonl). "
                          "Wird ab dem naechsten Nightly aufgebaut.")}
    days_all = sorted({r.get("date") for r in rows if r.get("date")})
    _breaks = [b["date"] for b in STRUCTURAL_BREAKS if b.get("brand") == "*" and b.get("date")]
    _last_break = max(_breaks) if _breaks else None
    days = [d for d in days_all if (not _last_break or d >= _last_break)]
    if max_days and len(days) > max_days:
        days = days[-max_days:]
    dayset = set(days)
    if len(days) < 3:
        return {"available": False, "n_days": len(days), "since_break": _last_break,
                "grund": ("Zu wenige saubere Messtage nach dem letzten markenweiten "
                          "Strukturbruch (%s) fuer stabiles Pooling — mindestens 3 noetig. "
                          "Reift mit jedem Nightly." % _last_break)}
    rp = _relprice_map()

    def _denoise(seg, dsub):
        acc = {}
        for r in rows:
            if r.get("date") not in dsub:
                continue
            sov = r.get("sov_%s" % seg)
            if sov is None:
                continue
            cite = r.get("cite_%s" % seg) or 0
            tot = r.get("ctot_%s" % seg) or 0
            cs = (100.0 * cite / tot) if tot else 0.0
            a = acc.setdefault((r.get("brand"), r.get("topic")), {"sov": [], "cs": []})
            a["sov"].append(sov)
            a["cs"].append(cs)
        cells = []
        for (b, t), v in acc.items():
            c = {"brand": b, "topic": t,
                 "sov": sum(v["sov"]) / len(v["sov"]),
                 "cite_share": sum(v["cs"]) / len(v["cs"])}
            pr = rp.get(t, {}).get(b)
            if pr is not None:
                c["relprice"] = pr
            if b in BRAND_SIZE:
                c["size"] = BRAND_SIZE[b]
            cells.append(c)
        return cells

    price_to_sov = {}
    price_to_citations = {}
    for seg, lab in (("g", "grounded"), ("u", "ungrounded"), ("c", "combined")):
        pcells = [c for c in _denoise(seg, dayset) if "relprice" in c]
        if len(pcells) >= 10:
            price_to_sov[lab] = _mundlak_multi(pcells, ["cite_share", "relprice"], "sov")
            price_to_citations[lab] = _mundlak_multi(pcells, ["relprice"], "cite_share")
        else:
            _msg = {"available": False, "n_cells": len(pcells),
                    "note": "Zu wenige Marke-x-Thema-Zellen mit Preisdaten (min. 10)."}
            price_to_sov[lab] = dict(_msg)
            price_to_citations[lab] = dict(_msg)

    _apply_fdr(price_to_sov)
    _apply_fdr(price_to_citations)

    stab = []
    for d in days:
        dc = [c for c in _denoise("g", {d}) if "relprice" in c]
        bc = _mundlak_between_coef(dc, "relprice", "sov")
        if bc is not None:
            stab.append({"date": d, "between_coef": round(bc, 2)})
    stability = None
    if stab:
        _cs = [s["between_coef"] for s in stab]
        _m = sum(_cs) / len(_cs)
        _sd = (sum((x - _m) ** 2 for x in _cs) / max(len(_cs) - 1, 1)) ** 0.5
        stability = {"metric": "between_coef_grounded_bivariat_price_to_sov",
                     "per_day": stab, "mean": round(_m, 2), "sd": round(_sd, 2),
                     "min": round(min(_cs), 2), "max": round(max(_cs), 2),
                     "sign_stable": bool(all(x > 0 for x in _cs) or all(x < 0 for x in _cs)),
                     "note": ("Between-Preis-Effekt (guenstiger Relativpreis -> mehr SoV), je "
                              "Einzeltag neu geschaetzt. Enge Streuung = stabiles Marktmuster. "
                              "Bivariat (ohne Footprint-Kontrolle), daher betragsmaessig groesser "
                              "als der bereinigte Wert in price_to_sov.")}

    # ── Gap-Explorer: 3-Treiber-Zerlegung (Bekanntheit/Groesse + Quellpraesenz + Preis) ──
    # Liefert Between-Koeffizienten + Markenmittel je Segment, damit sich der Abstand
    # ZWISCHEN BELIEBIGEN ZWEI MARKEN zerlegen laesst (nicht nur gegen den Leader) —
    # z.B. ERGO vs HUK. Groesse ist ein fester Naeherungswert (BRAND_SIZE), kein
    # geschaetzter; dadurch weniger kollinear mit der Quellpraesenz als zwei geschaetzte
    # Groessen. Trotzdem: die Trennung Groesse/Quellpraesenz bleibt eine Tendenz.
    gap_explorer = {}
    for seg, lab in (("g", "grounded"), ("u", "ungrounded"), ("c", "combined")):
        fcells = [c for c in _denoise(seg, dayset) if ("relprice" in c and "size" in c)]
        if len(fcells) < 12:
            gap_explorer[lab] = {"available": False, "n_cells": len(fcells),
                                 "note": "Zu wenige Zellen mit Preis UND Groesse (min. 12)."}
            continue
        fit = _mundlak_multi(fcells, ["size", "cite_share", "relprice"], "sov")
        if not fit.get("available"):
            gap_explorer[lab] = {"available": False, "note": fit.get("note")}
            continue
        de = fit.get("drivers_eff") or {}
        bc = {k: ((de.get(k) or {}).get("between") or {}).get("coef") for k in ("size", "cite_share", "relprice")}
        rel = {}
        for k in ("size", "cite_share", "relprice"):
            b = (de.get(k) or {}).get("between") or {}
            rel[k] = {"prob_direction": b.get("prob_direction"),
                      "wild_cluster_p": b.get("wild_cluster_p"),
                      "loo_sign_stable": (b.get("between_loo") or {}).get("sign_stable")}
        # Markenmittel (roh, ueber die gepoolten Zellen)
        _sum = {}; _cnt = {}
        for c in fcells:
            b = c["brand"]
            d = _sum.setdefault(b, {"sov": 0.0, "size": 0.0, "cite_share": 0.0, "relprice": 0.0})
            d["sov"] += c["sov"]; d["size"] += c["size"]
            d["cite_share"] += c["cite_share"]; d["relprice"] += c["relprice"]
            _cnt[b] = _cnt.get(b, 0) + 1
        means = {b: {k: round(_sum[b][k] / _cnt[b], 3) for k in _sum[b]} for b in _sum}
        gap_explorer[lab] = {
            "available": True, "n_cells": len(fcells),
            "brands": sorted(means.keys()), "leader": fit.get("leader"),
            "between_coef": {k: (round(bc[k], 4) if bc[k] is not None else None) for k in bc},
            "driver_reliability": rel, "brand_means": means,
            "drivers": ["size", "cite_share", "relprice"],
            "labels": {"size": "Bekanntheit/Groesse", "cite_share": "Quellpraesenz", "relprice": "Preisniveau"},
            "note": ("Zerlegung des Abstands zwischen zwei Marken in Bekanntheit/Groesse, "
                     "Quellpraesenz und Preis. Beitrag je Treiber = Between-Koeffizient x "
                     "Differenz der Markenmittel. Groesse ist eine feste Naeherung (BRAND_SIZE); "
                     "die Trennung Groesse/Quellpraesenz ist eine Tendenz, kein Kausalnachweis."),
        }

    return {"available": True, "n_days": len(days), "days_range": [days[0], days[-1]],
            "since_break": _last_break, "max_days_window": max_days,
            "price_to_sov": price_to_sov, "price_to_citations": price_to_citations,
            "gap_explorer": gap_explorer,
            "stability": stability,
            "interpretation": (
                "Gepoolt ueber %d saubere Tage. BEFUND: Der Within-Preis-Effekt (Marke mit "
                "sich selbst ueber Produkte — die saubere kausale Identifikation) faellt nach "
                "Rausch-Mittelung nahe null; der grenzwertige Ein-Tages-Within war groesstenteils "
                "Tagesrauschen. Der BETWEEN-Effekt (guenstigere Marken sichtbarer und haeufiger "
                "zitiert) ist stabil und richtungssicher, erlaubt aber keine Kausalaussage "
                "(guenstige Anbieter unterscheiden sich auch in Groesse, Vertrieb, Bekanntheit)." % len(days)),
            "note": ("Level-Modell auf ueber mehrere Tage GEMITTELTEN Zellwerten (Marke x Thema). "
                     "Mittelung reduziert das LLM-Tagesrauschen in der Zielgroesse; sie erzeugt "
                     "KEINE zusaetzlichen unabhaengigen Beobachtungen (Cluster bleibt die Marke). "
                     "Quelle: data/level_cells_history.jsonl.")}




def _augment_structure_with_pooled_price(res):
    """Speist den ueber mehrere Tage STABILISIERTEN Preis-Beitrag in die
    Ursachenanalyse-Zerlegung (level_model.structure_summary) ein.

    Vorher stammte der Preis-Beitrag aus EINEM verrauschten Snapshot und wurde als
    Rest NACH der Autoritaet gekappt — die Autoritaet ass den ganzen Gap, der Preis
    blieb fast immer 0. Jetzt kommen Autoritaet (Groesse+Footprint) UND Preis
    konsistent aus DEMSELBEN gemeinsamen Pooling-Modell (price_level_pooled), in dem
    sich beide Treiber gegenseitig kontrollieren, gemittelt ueber saubere Tage.
    Additiv: faellt das Pooling-Modell aus, bleibt die bisherige Zerlegung stehen."""
    p = res.get("price_level_pooled") or {}
    lm = res.get("level_model") or {}
    ss = lm.get("structure_summary")
    if not (isinstance(ss, dict) and p.get("available")):
        return
    pts = p.get("price_to_sov") or {}
    for segkey in ("grounded", "ungrounded", "combined"):
        blk = pts.get(segkey) or {}
        if not blk.get("available"):
            continue
        gd = (blk.get("gap_decomposition") or {}).get("ERGO")
        if not gd:
            continue
        gap = gd.get("actual_gap_pp")
        contrib = gd.get("contrib_pp") or {}
        foot_raw = contrib.get("cite_share")
        price_raw = contrib.get("relprice")
        if gap is None or foot_raw is None or price_raw is None:
            continue
        # KEINE sequentielle Kappung (die drueckte den Preis auf den Rest nach der
        # Autoritaet, fast immer ~0). Stattdessen die ROHEN gemeinsamen Beitraege
        # (nur negative auf 0 gefloort) uebergeben — das Frontend (gap_waterfall.js)
        # skaliert sie proportional auf 100 % des Gaps, wenn sie sich ueberlappen.
        # So bleibt der EHRLICHE relative Preis-Anteil sichtbar statt weggekappt.
        foot = max(foot_raw, 0.0)
        price = max(price_raw, 0.0)
        _sum = foot + price
        price_capped = bool(_sum > gap and gap > 0)  # Frontend skaliert dann proportional
        rest = max(gap - _sum, 0.0)
        ss[segkey] = {
            "available": True,
            "leader": gd.get("vs") or blk.get("leader") or "Allianz",
            "gap_pp": round(gap, 2),
            "authority_pp": round(foot, 2),
            "authority_capped": bool(abs(foot - foot_raw) > 1e-9),
            "price_pp": round(price, 2),
            "price_capped": price_capped,
            "rest_pp": round(rest, 2),
            "price_source": "pooled_joint",
            "n_days": p.get("n_days"),
            "days_range": p.get("days_range"),
            "note": ("Autoritaet (Groesse+Footprint) UND Preis aus DEMSELBEN gemeinsamen "
                     "Modell (Treiber kontrollieren einander), stabilisiert ueber %s saubere "
                     "Tage. Der Preis wird nicht mehr als blosser Rest nach der Autoritaet "
                     "gekappt. Zerlegung ueber gemittelte Zellwerte, kein Kausalnachweis." % p.get("n_days")),
        }





def _weekly_grounded_series(series_by_brand):
    """Aggregiert die (grounded-)SoV je Marke auf nicht-ueberlappende ISO-Wochen-Mittel.
    Bewusst NICHT ueberlappend: ein gleitendes Fenster wuerde Autokorrelation zwischen
    benachbarten Intervallen erzeugen und _effect_ci (das Intervalle als unabhaengig
    behandelt) kuenstlich zu kleine Standardfehler geben -> Scheinsignifikanz. Die
    Wochen-Mittelung senkt das LLM-Tagesrauschen der Zielgroesse OHNE diese Falle."""
    import datetime as _dt
    out = {}
    for b, pts in series_by_brand.items():
        wk = {}
        for day, val in pts:
            try:
                y, w, _ = _dt.date.fromisoformat(day).isocalendar()
            except Exception:
                continue
            wk.setdefault("%04d-W%02d" % (y, w), []).append((day, val))
        ser = []
        for key in sorted(wk):
            days = wk[key]
            ser.append((max(d for d, _ in days), sum(v for _, v in days) / len(days)))
        if ser:
            out[b] = ser
    return out


def event_impact_denoised(events):
    """Kurzfrist-Event-Study auf ENTRAUSCHTER, GROUNDED-SoV (Hebel 1+2, 01.08.2026).

    Motivation: Das tageweise Gesamtmodell (impact) findet keinen belastbaren
    Kurzfrist-Effekt — aber vermutlich, weil das Event-Signal im LLM-Tagesrauschen
    der SoV ertrinkt (dasselbe Problem, das den Preis-Effekt lange verdeckte).

    Zwei Hebel, additiv zum Hauptmodell:
      - Hebel 2 (Wirkkanal): nur GROUNDED-Engines (Gemini+Perplexity). Das ist der
        Web-Such-Kanal des eigenen Crawls; ungrounded (ChatGPT) kann auf eine
        Seitenaenderung physisch nicht reagieren und ist reines Rauschen fuer diesen
        Test. (Fuer den eigenen Crawl ersetzt das die tagesweise Web-Such-Bedingung,
        die fanout_regime_analysis fuer die PEEC-Reihe macht — Quellen sauber getrennt.)
      - Hebel 1 (Entrauschung): die grounded-SoV wird auf nicht-ueberlappende
        Wochen-Mittel aggregiert, bevor Intervall-Deltas gebildet werden. Weniger
        Rauschen je Punkt, keine kuenstliche Autokorrelation.

    Ausgabe vergleicht grounded-taeglich (Baseline) mit grounded-woechentlich
    (entrauscht). Weiterhin Korrelation, kein Kausalnachweis; Cluster ist die Marke.
    """
    raw = build_sov_series_for_llms(set(GROUNDED_LLMS))
    if not raw or sum(len(v) for v in raw.values()) < 20:
        return {"available": False,
                "grund": ("Zu wenig grounded-SoV-Historie (per-LLM) fuer die entrauschte "
                          "Event-Study — waechst mit jedem Crawl.")}
    ev = dedup_impact_events(events)
    bydays = {}
    for e in ev:
        b, day = e.get("brand"), _day(e.get("timestamp"))
        if not b or not day:
            continue
        bydays.setdefault(b, {}).setdefault(day, {})
        t = e.get("event_type")
        bydays[b][day][t] = bydays[b][day].get(t, 0) + 1

    def _study(series):
        pts, _sk = build_intervals(series, bydays, IMPACT_TYPES)
        res = {}
        for t in IMPACT_TYPES:
            xs = [p["x"].get(t, 0.0) for p in pts]
            ys = [p["y"] for p in pts]
            n_with = sum(1 for x in xs if x > 0)
            if n_with < 3:
                res[t] = {"label": TYPE_LABEL.get(t, t), "n_with_event": n_with,
                          "available": False,
                          "grund": "Zu wenige Intervalle mit diesem Ereignis (<3)."}
                continue
            eff, se, lo, hi, sig, pval = _effect_ci(xs, ys)
            res[t] = {"label": TYPE_LABEL.get(t, t), "n_with_event": n_with,
                      "avg_sov_effect_pp": eff, "se_pp": se,
                      "ci95_low_pp": lo, "ci95_high_pp": hi,
                      "significant": bool(sig), "p_value": pval}
        return res, len(pts)

    daily_res, n_daily = _study(raw)
    weekly = _weekly_grounded_series(raw)
    weekly_res, n_weekly = _study(weekly)

    n_sig_week = sum(1 for t in weekly_res if weekly_res[t].get("significant"))
    n_sig_day = sum(1 for t in daily_res if daily_res[t].get("significant"))
    # KI-Verengung je Typ (taeglich -> woechentlich)
    verengung = {}
    for t in IMPACT_TYPES:
        d = daily_res.get(t, {}); w = weekly_res.get(t, {})
        def _wid(x):
            a, b = x.get("ci95_low_pp"), x.get("ci95_high_pp")
            return (b - a) if (a is not None and b is not None) else None
        wd, ww = _wid(d), _wid(w)
        verengung[t] = round(wd / ww, 2) if (wd and ww and ww > 0) else None

    return {
        "available": True,
        "kanal": "grounded (Gemini+Perplexity) — Web-Such-Kanal des eigenen Crawls",
        "n_intervalle_taeglich": n_daily,
        "n_intervalle_woechentlich": n_weekly,
        "impact_grounded_taeglich": daily_res,
        "impact_grounded_woechentlich": weekly_res,
        "ci_verengung_tag_zu_woche": verengung,
        "n_gesichert_taeglich": n_sig_day,
        "n_gesichert_woechentlich": n_sig_week,
        "kernaussage": (
            "Auch nach Entrauschung (grounded-only + Wochen-Mittel) ist KEIN Kurzfrist-Event "
            "gesichert." if n_sig_week == 0 else
            "%d Kurzfrist-Effekt(e) ueberstehen die Entrauschung — vor Interpretation KI und "
            "Mehrfachtests pruefen." % n_sig_week),
        "note": (
            "Hebel 1+2 fuer die Kurzfrist-Events. WICHTIG: Es wird bewusst WOECHENTLICH und "
            "NICHT-UEBERLAPPEND gemittelt, kein gleitendes Fenster — ein ueberlappendes "
            "Fenster erzeugt Autokorrelation und damit kuenstlich zu enge Konfidenzintervalle "
            "(getestet, verworfen). Die Wochen-Aggregation reduziert das Rauschen ehrlich, "
            "kostet aber Intervalle (%d statt %d). Weiterhin Korrelation, kein Kausalnachweis; "
            "der eigentliche Wirkungsnachweis kaeme aus bewussten Interventionen." % (n_weekly, n_daily)),
    }


def main():
    events = load_events()
    if not events:
        print("Keine Events — Abbruch")
        return 0
    res = analyze(events, validate=True)
    try:
        res["footprint_analysis"] = footprint_level_analysis()
    except Exception as _e:
        print("WARN footprint_analysis:", str(_e)[:120])
    try:
        res["citation_category"] = citation_category_analysis()
    except Exception as _e:
        print("WARN citation_category:", str(_e)[:120])
    try:
        res["level_model"] = level_model_mundlak()
    except Exception as _e:
        print("WARN level_model:", str(_e)[:120])
    try:
        res["price_level_pooled"] = price_level_pooled()
    except Exception as _e:
        print("WARN price_level_pooled:", str(_e)[:120])
    try:
        _augment_structure_with_pooled_price(res)
    except Exception as _e:
        print("WARN augment_structure_price:", str(_e)[:120])
    # 19.07.2026: neue Peec-Datenquellen. Alle drei melden bei fehlender
    # Datenbasis available=False MIT Grund — nie eine 0.0.
    # Gesamteffekte als Prior fuer die Stufenmodelle (Partial Pooling: duenne
    # Schichten leihen Staerke vom Gesamtmodell, statt frei zu schwanken).
    _prior_fs = {t: c.get("coef_pp_per_event_day", 0.0)
                 for t, c in ((res.get("multivariate") or {}).get("coefficients") or {}).items()} or None
    try:
        res["citation_target"] = citation_target_analysis(events)
    except Exception as _e:
        print("WARN citation_target:", str(_e)[:120])
    try:
        res["funnel_stratified"] = funnel_stratified_analysis(events, mv_prior=_prior_fs)
    except Exception as _e:
        print("WARN funnel_stratified:", str(_e)[:120])
    try:
        res["fanout_regime"] = fanout_regime_analysis(events)
    except Exception as _e:
        print("WARN fanout_regime:", str(_e)[:120])
    try:
        res["event_impact_denoised"] = event_impact_denoised(events)
    except Exception as _e:
        print("WARN event_impact_denoised:", str(_e)[:120])
    try:
        res["lag_analysis"] = lag_analysis(events)
    except Exception as _e:
        print("WARN lag_analysis:", str(_e)[:120])
    try:
        res["page_change_types"] = page_change_by_type(events)
    except Exception as _e:
        print("WARN page_change_types:", str(_e)[:120])
    _prior = {t: c.get('coef_pp_per_event_day', 0.0)
              for t, c in ((res.get('multivariate') or {}).get('coefficients') or {}).items()} or None
    # 2026-06-04: zusaetzlich Impact je LLM (fuer die LLM-Auswahl im Dashboard)
    by_llm = {}
    for llm in list_llms_in_history():
        try:
            r = analyze(events, llm=llm, prior_mean=_prior)
            by_llm[llm] = {k: r[k] for k in ("impact", "multivariate", "confidence", "confidence_note",
                                             "sov_measure_days", "sov_measure_range",
                                             "n_intervals_total", "brands_with_sov") if k in r}
        except Exception as e:
            print("WARN per-LLM (%s): %s" % (llm, str(e)[:80]))
    res["by_llm"] = by_llm
    # 2026-06-05: zusaetzlich Impact JE MARKE (Anbieter-Isolierung im Dashboard).
    # Hinweis: pro Einzelmarke wenige Intervalle -> type_confidence weist das aus.
    by_brand = {}
    for b in res.get("brands_with_sov", []):
        try:
            rb = analyze(events, brand_filter=b, prior_mean=_prior)
            by_brand[b] = {k: rb[k] for k in ("impact", "multivariate", "confidence", "confidence_note",
                                              "sov_measure_days", "sov_measure_range",
                                              "n_intervals_total") if k in rb}
        except Exception as e:
            print("WARN per-Brand (%s): %s" % (b, str(e)[:80]))
    res["by_brand"] = by_brand
    # 2026-06-11: Impact getrennt nach web-gestuetzten (grounded) vs. nicht
    # web-gestuetzten (ungrounded) LLMs — Treiber wirken dort fundamental anders.
    all_llms = set(list_llms_in_history())
    grounded = all_llms & GROUNDED_LLMS
    ungrounded = all_llms - GROUNDED_LLMS
    by_grounding = {}
    for label, lset in (("grounded", grounded), ("ungrounded", ungrounded)):
        if not lset:
            continue
        try:
            rg = analyze(events, llm_set=lset, scope_label=label, prior_mean=_prior)
            rg_out = {k: rg[k] for k in ("impact", "multivariate", "confidence", "confidence_note",
                                         "sov_measure_days", "sov_measure_range",
                                         "n_intervals_total", "brands_with_sov") if k in rg}
            rg_out["llms"] = sorted(lset)
            by_grounding[label] = rg_out
        except Exception as e:
            print("WARN by_grounding (%s): %s" % (label, str(e)[:80]))
    res["by_grounding"] = by_grounding
    res["grounded_llms"] = sorted(grounded)
    res["ungrounded_llms"] = sorted(ungrounded)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OK: %s (Konfidenz=%s, SoV-Messtage=%d, Intervalle=%d)"
          % (OUT_FILE, res["confidence"], res["sov_measure_days"], res["n_intervals_total"]))
    for _k, _lbl in (("citation_target", "Zitat-Zielgroesse"),
                     ("funnel_stratified", "Funnel-Schichtung"),
                     ("page_change_types", "Seitentyp-Aufschluesselung")):
        _b = res.get(_k) or {}
        print("  [%s] %s" % (_lbl, "aktiv" if _b.get("available") else
                             ("noch keine Datenbasis: " + str(_b.get("grund", ""))[:110])))
    for t, r in res["impact"].items():
        print("  %-32s r=%s  Effekt=%s Pp  (n=%d, mit Event=%d)"
              % (r["label"], r["pearson_r"], r["avg_sov_effect_pp"], r["n_intervals"], r["n_with_event"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
