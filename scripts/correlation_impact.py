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
LAG_DAYS = 0
# Event-Typen, deren Wirkung auf SoV untersucht wird (sov_change selbst ist die Zielgroesse).
IMPACT_TYPES = [
    "page_change", "page_new", "press_mention", "news_mention",
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
        day, brand, pct = r.get("date"), r.get("brand"), r.get("sov_pct")
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
        day, brand, pct = r.get("date"), r.get("brand"), r.get("sov_pct")
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
        brand = e.get("brand")
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
        if e.get("crawler") == "update_domain_footprint" and t in ("page_new", "page_change"):
            continue
        if not e.get("brand") or not _day(e.get("timestamp")):
            continue
        k = _content_key(e)
        ts = e.get("timestamp", "")
        if k not in seen or ts < seen[k].get("timestamp", ""):
            seen[k] = e
    return list(seen.values())


def _solve_ridge(Xs, Y, lam):
    """Ridge per Normalengleichung (X'X + lam I) b = X'Y, Gauss-Jordan."""
    n = len(Xs); m = len(Xs[0]) if Xs else 0
    if n == 0 or m == 0:
        return [0.0] * m
    A = [[sum(Xs[i][a] * Xs[i][b] for i in range(n)) + (lam if a == b else 0.0)
          for b in range(m)] for a in range(m)]
    bv = [sum(Xs[i][a] * Y[i] for i in range(n)) for a in range(m)]
    M = [A[k][:] + [bv[k]] for k in range(m)]
    for c in range(m):
        piv = max(range(c, m), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        pv = M[c][c]
        if abs(pv) < 1e-12:
            continue
        M[c] = [v / pv for v in M[c]]
        for r in range(m):
            if r != c:
                fct = M[r][c]
                M[r] = [M[r][k] - fct * M[c][k] for k in range(m + 1)]
    return [M[i][m] for i in range(m)]


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
    return Y, Xs, sd


def _ridge_posterior(Xs, Y, lam, center=None):
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
    sig2 = ss / max(n - m, 1)
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


def _cluster_robust_var(Xs, Y, beta, Ainv, clusters):
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
    c = (G / (G - 1.0)) * ((n - 1.0) / max(n - m, 1))
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
    if G < 2 or G > max_exact:
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
    for mask in range(1 << G):
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
    Y, Xs, sd = _design(points_raw, use, feature_key)
    m = len(use)
    lam = len(Xs) * 0.5
    center = None
    if prior_mean:
        center = [(prior_mean.get(use[j], 0.0)) * sd[j] for j in range(m)]
    beta, Ainv, sig2 = _ridge_posterior(Xs, Y, lam, center)

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
    Y, Xs, sd = _design(points_raw, use, feature_key)
    n, m = len(Y), len(use)
    if n < 12 or m == 0:
        return None
    lam = n * 0.5
    hits = 0; total = 0
    for _ in range(n_perm):
        Yp = Y[:]; rnd.shuffle(Yp)
        beta, Ainv, sig2 = _ridge_posterior(Xs, Yp, lam)
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
        Yt, Xt, sdt = _design(train, use, feature_key, twoway=False)
        beta, _A, _s = _ridge_posterior(Xt, Yt, n=None) if False else _ridge_posterior(Xt, Yt, len(Xt) * 0.5)
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
             "devk": "DEVK", "hannoversche": "Hannoversche", "cosmosdirekt": "Cosmos Direkt"}


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
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": "interval-event-study v2 (Raten/Tag, brand-demeaned, Spearman, SE) + Panel-Ridge multivariat",
        "multivariate": multivar,
        "validation": validation,
        "sov_source": sov_source,
        "lag_days": LAG_DAYS,
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
                   "prob_direction": round(pdir, 3), "significant": bool(pdir >= 0.975)}
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
                   "share_explained": round(expl / actual, 2) if abs(actual) > 1e-6 else None}
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
    keymap = {"allianz": "Allianz", "ergo": "ERGO", "axa": "AXA", "generali": "Generali",
              "huk": "HUK-Coburg", "signal-iduna": "Signal Iduna", "cosmosdirekt": "CosmosDirekt"}

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
                if k.startswith("_other_"):
                    continue
                p = v.get("price"); nm = keymap.get(k)
                if nm and isinstance(p, (int, float)) and p > 0:
                    prices[nm] = p
            if len(prices) >= 2:
                res[pid] = prices
        return res

    crawler = _extract(PRICE_FILE)
    manual = _extract(PRICE_MANUAL_FILE)
    merged = dict(crawler)
    for pid, prices in manual.items():
        if pid not in merged or len(prices) > len(merged[pid]):
            merged[pid] = prices
    # DKV-Ausschluss (15.07.2026): Krankenhauszusatz laeuft im ERGO-Konzern unter der
    # Marke DKV — die Nennung zahlt nicht auf die ERGO-Markensichtbarkeit ein, der
    # Preis darf ERGO daher nicht zugerechnet werden.
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
}


def _mundlak_multi(cells, xkeys, ykey, _loo_depth=0):
    """Mundlak/CRE mit MEHREREN Treibern gemeinsam: je Treiber Within+Between, die
    Between-Effekte kontrollieren einander (so trennt sich z.B. Groesse vom Footprint)."""
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
        # Wild-Cluster-Bootstrap nur fuer die Between-Effekte: Das sind die Aussagen
        # ueber MARKEN, und genau dort ist G=7 die eigentliche Fallzahl. Fuer Within
        # (Marke gegen sich selbst ueber Themen) traegt die Zellzahl.
        if kind == "between" and _loo_depth < 1:
            _p, _g, _t = _wild_cluster_p(Xs, Yc, Ainv, _clusters, j, _lam)
            if _p is not None:
                rec["wild_cluster_p"] = round(_p, 4)
                rec["wild_cluster_t"] = _t
                rec["wild_cluster_note"] = (
                    "Exakter Wild-Cluster-Bootstrap ueber alle %d Vorzeichen-Vektoren (G=%d Marken). "
                    "Kleinstmoeglicher p-Wert bei dieser Fallzahl: %.4f." % (2 ** _g, _g, 1.0 / (2 ** _g)))
        eff.setdefault(k, {})[kind] = rec
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
            "berufsunfaehigkeit": "Berufsunf\u00e4higkeit", "rechtsschutz": "Rechtsschutz",
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
            "Berufsunf\u00e4higkeit": "berufsunfaehigkeit", "Berufsunfaehigkeit": "berufsunfaehigkeit",
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
    fit_g = _mundlak_fit(cells_g, "cite_share", "sov")
    fit_u = _mundlak_fit(cells_u, "cite_share", "sov")
    fit_c = _mundlak_fit(cells_c, "cite_share", "sov")
    # #17: Relativpreis als zusaetzlicher Treiber (nur Produkte mit Preisdaten)
    _rp = _relprice_map()
    for _cs in (cells_g, cells_u, cells_c):
        for c in _cs:
            v = _rp.get(c["topic"], {}).get(c["brand"])
            if v is not None:
                c["relprice"] = v
    price_model = {}
    for _en, _cs in (("grounded", cells_g), ("ungrounded", cells_u), ("combined", cells_c)):
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
        _pc = [c for c in _cs if "relprice" in c]
        price_footprint_joint[_en] = (_mundlak_multi(_pc, ["cite_share", "relprice"], "sov")
                                      if len(_pc) >= 10 else
                                      {"available": False, "n_cells": len(_pc),
                                       "note": "Zu wenige Zellen mit Preis UND Footprint."})

    # (15.07.2026) Voll-Zerlegung fuer die Ursachenanalyse vs. Marktfuehrer:
    # Groesse + Footprint + Preis GEMEINSAM (kontrollieren einander). Achtung
    # Kollinearitaet Groesse<->Footprint bei n eff.=6-7 Marken — die interne
    # Aufteilung dieser beiden ist nur als Tendenz zu lesen (im UI kenntlich machen).
    full_joint = {}
    for _en, _cs in (("grounded", cells_g), ("ungrounded", cells_u), ("combined", cells_c)):
        _fc = [c for c in _cs if ("relprice" in c and c["brand"] in BRAND_SIZE)]
        for c in _fc:
            c["size"] = BRAND_SIZE[c["brand"]]
        full_joint[_en] = (_mundlak_multi(_fc, ["cite_share", "size", "relprice"], "sov")
                           if len(_fc) >= 12 else
                           {"available": False, "n_cells": len(_fc),
                            "note": "Zu wenige Zellen mit Preis+Groesse+Footprint."})

    # #16 2. Treiber: Groesse/Bekanntheit gemeinsam mit Footprint (Effekte kontrollieren einander)
    for c in cells_c:
        if c["brand"] in BRAND_SIZE:
            c["size"] = BRAND_SIZE[c["brand"]]
    _joint_cells = [c for c in cells_c if ("size" in c and "cite_share" in c)]
    joint_model = _mundlak_multi(_joint_cells, ["cite_share", "size"], "sov")
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
                "grounded": _mundlak_multi(aug_g, ["cite_share", "src_peec"], "sov"),
                "combined": _mundlak_multi(aug_c, ["cite_share", "src_peec"], "sov"),
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

    return {"available": True, "driver": "cite_share",
            "citation_engine_mix": _cmix,
            "cross_source_validation": _xsrc,
            "grounded": fit_g, "ungrounded": fit_u, "combined": fit_c,
            "price_model": price_model, "joint_model": joint_model,
            "with_peec": with_peec, "price_footprint_joint": price_footprint_joint,
            "full_joint": full_joint,
            "note": ("Level-Modell (Mundlak/CRE): Zielgroesse = SoV-NIVEAU je Marke x Thema; Treiber = "
                     "Zitations-Footprint (cite_share = eigene-Domain-Zitate / alle Zitate im Thema). "
                     "WITHIN = bewegt mehr eigener Footprint im Thema die Sichtbarkeit (Marke gegen sich selbst "
                     "ueber Themen, Themen-FE kontrolliert). BETWEEN = Marken-Mittel des Footprints; erklaert den "
                     "Autoritaets-/Marken-Vorsprung (warum Allianz sichtbarer ist) statt ihn wie ein reiner "
                     "Marken-FE zu verstecken. gap_decomposition = Anteil des SoV-Abstands zum Marktfuehrer, der "
                     "durch Footprint erklaert ist. coef-Einheit = Pp SoV je Pp Zitationsanteil. Mit 6 Themen "
                     "explorativ. Quelle: data/geo_snapshot.json.")}


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
    for t, r in res["impact"].items():
        print("  %-32s r=%s  Effekt=%s Pp  (n=%d, mit Event=%d)"
              % (r["label"], r["pearson_r"], r["avg_sov_effect_pp"], r["n_intervals"], r["n_with_event"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
