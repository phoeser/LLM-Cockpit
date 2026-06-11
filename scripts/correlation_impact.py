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
OUT_FILE = Path("data/correlation_impact.json")

# Optionaler Lag in Tagen: Wirkung tritt evtl. verzoegert auf. 0 = gleiches Intervall.
LAG_DAYS = 0
# Event-Typen, deren Wirkung auf SoV untersucht wird (sov_change selbst ist die Zielgroesse).
IMPACT_TYPES = [
    "page_change", "page_new", "press_mention", "news_mention",
    "domain_change", "review_change", "review_volume", "price_change",
    "wikipedia_change", "portal_rank_change", "rating_status_change",
]
TYPE_LABEL = {
    "page_change": "Seitenaenderungen (Wettbewerb)",
    "page_new": "Neue Seiten",
    "press_mention": "Pressemitteilungen",
    "news_mention": "News-Erwaehnungen",
    "domain_change": "Domain-/Subdomain-Aenderungen",
    "review_change": "Bewertungs-Aenderungen",
    "review_volume": "Bewertungs-Volumen",
    "price_change": "Preis-Aenderungen",
    "wikipedia_change": "Wikipedia-Aenderungen",
    "portal_rank_change": "Portal-Rang (Check24)",
    "rating_status_change": "Testsieger-/Rating-Status",
    "media_sentiment": "Medien-Sentiment (netto +/−)",
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

    MIN_NWITH, MIN_NPTS, MIN_TIMES = 10, 20, 12
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
                    "'Gesichert' = P(Richtung) >= 97,5 %, >=10 Intervalle mit Event, "
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
    senti = {}
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
        wmag[b][day][t] = wmag[b][day].get(t, 0.0) + (mg if mg > 0 else 1.0)
        if t in ("press_mention", "news_mention"):
            sv = {"positive": 1, "negative": -1}.get(e.get("sentiment"), 0)
            if sv:
                senti.setdefault(b, {}).setdefault(day, 0)
                senti[b][day] += sv

    # v2 (Review-Fixes 2026-06-04):
    #  - Intervalle ungleicher Laenge werden auf RATEN pro Tag normalisiert
    #  - Brand-Demeaning: delta je Marke um den Markenmittelwert zentriert
    #    (verhindert Scheinkorrelation durch markenspezifische Trends)
    #  - Spearman statt nur Pearson (robust bei nullinflationierten Counts)
    #  - Standardfehler (SE) des Effekts + Konfidenz JE TYP (aus n_with)
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
            snet = 0
            for day, sv in (senti.get(brand, {}) or {}).items():
                if start_day <= day < end_day:
                    sent_total = sv if not isinstance(sv, dict) else 0
                    snet += sent_total
            xmv["media_sentiment"] = snet / days
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
                                   candidate_types=IMPACT_TYPES + ["media_sentiment"],
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


def main():
    events = load_events()
    if not events:
        print("Keine Events — Abbruch")
        return 0
    res = analyze(events, validate=True)
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
