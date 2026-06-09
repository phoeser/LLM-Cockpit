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


def multivariate_impact(points_raw, min_with=6, bootstrap=800, seed=1):
    """Regularisierte Panel-Regression (Marken-Fixed-Effects via Within-Transform):
    schaetzt ALLE Event-Typen GLEICHZEITIG -> isolierter Effekt je Kategorie,
    kontrolliert um die jeweils anderen Typen + markeneigene Trends.
    95%-KI per Bootstrap (robust bei kleiner Stichprobe)."""
    import random as _rnd
    rnd = _rnd.Random(seed)
    brands = sorted({p["brand"] for p in points_raw})
    use = [t for t in IMPACT_TYPES
           if sum(1 for p in points_raw if p["x"].get(t, 0) > 0) >= min_with]
    if len(points_raw) < 8 or len(brands) < 1 or not use:
        return {"available": False,
                "note": "Zu wenige Datenpunkte/Marken fuer das multivariate Modell.",
                "n_points": len(points_raw), "n_brands": len(brands),
                "types_used": use, "coefficients": {}}
    # Within-Brand-Transform (= Marken-Fixed-Effects)
    from collections import defaultdict as _dd
    by = _dd(list)
    for p in points_raw:
        by[p["brand"]].append(p)
    ymean = {b: sum(p["y"] for p in ps) / len(ps) for b, ps in by.items()}
    xmean = {b: {t: sum(p["x"].get(t, 0) for p in ps) / len(ps) for t in use}
             for b, ps in by.items()}
    X, Y = [], []
    for p in points_raw:
        Y.append(p["y"] - ymean[p["brand"]])
        X.append([p["x"].get(t, 0) - xmean[p["brand"]][t] for t in use])
    m = len(use)
    sd = []
    for j in range(m):
        col = [X[i][j] for i in range(len(X))]
        v = sum(c * c for c in col) / max(len(X) - 1, 1)
        sd.append(v ** 0.5 if v > 1e-12 else 1.0)
    Xs = [[X[i][j] / sd[j] for j in range(m)] for i in range(len(X))]
    lam = len(Xs) * 0.5
    beta = [b / sd[j] for j, b in enumerate(_solve_ridge(Xs, Y, lam))]
    # Bootstrap-KI
    boots = [[] for _ in range(m)]
    idx = list(range(len(Xs)))
    for _ in range(bootstrap):
        smp = [rnd.choice(idx) for _ in idx]
        bs = _solve_ridge([Xs[i] for i in smp], [Y[i] for i in smp], lam)
        for j in range(m):
            boots[j].append(bs[j] / sd[j])
    coeffs = {}
    for j, t in enumerate(use):
        v = sorted(boots[j])
        lo = v[int(0.025 * len(v))]; hi = v[min(int(0.975 * len(v)), len(v) - 1)]
        nw = sum(1 for p in points_raw if p["x"].get(t, 0) > 0)
        coeffs[t] = {
            "label": TYPE_LABEL.get(t, t),
            "coef_pp_per_event_day": round(beta[j], 4),
            "ci95_low": round(lo, 4), "ci95_high": round(hi, 4),
            "significant": bool(lo > 0 or hi < 0),
            "n_with_event": nw,
        }
    coeffs = dict(sorted(coeffs.items(), key=lambda kv: -abs(kv[1]["coef_pp_per_event_day"])))
    excluded = [t for t in IMPACT_TYPES if t not in use]
    return {"available": True,
            "method": "Panel-Ridge (within-brand FE, standardisiert, Bootstrap-95%-KI)",
            "lambda": round(lam, 2), "bootstrap": bootstrap,
            "n_points": len(points_raw), "n_brands": len(brands),
            "types_used": use, "types_excluded_too_few": excluded,
            "coefficients": coeffs,
            "note": "Isolierter Effekt je Kategorie (alle gleichzeitig geschaetzt). "
                    "Wird mit mehr SoV-Messtagen belastbarer; Signifikanz erst wenn KI die Null ausschliesst."}


def analyze(events, llm=None, brand_filter=None):
    # Vorrang: dichte SoV-Historie; Fallback: sov_change-Events (nur Gesamt)
    sov = build_sov_series_from_history(llm=llm)
    sov_source = "sov_history" if llm is None else ("sov_history_llm:" + llm)
    if not sov and llm is None:
        sov = build_sov_series(events)
        sov_source = "sov_change_events"
    mdays = set()
    for ser in sov.values():
        for day, _pct in ser:
            mdays.add(day)
    measure_days = sorted(mdays)
    conf_label, conf_note = confidence(len(measure_days))

    # Event-Counts je (brand, day, type) — DEDUPLIZIERT (Re-Emissionen entfernt)
    counts = {}
    for e in dedup_impact_events(events):
        t = e.get("event_type")
        b = e.get("brand")
        day = _day(e.get("timestamp"))
        counts.setdefault(b, {}).setdefault(day, {})
        counts[b][day][t] = counts[b][day].get(t, 0) + 1

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
            for t in IMPACT_TYPES:
                c = 0
                for day, tc in bydays.items():
                    if start_day <= day < end_day:
                        c += tc.get(t, 0)
                cnt[t] = c / days
            points_raw.append({"brand": brand, "days": days,
                               "y": (end_pct - start_pct) / days, "x": cnt})
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
    multivar = multivariate_impact(points_raw, min_with=(4 if brand_filter else 6))
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": "interval-event-study v2 (Raten/Tag, brand-demeaned, Spearman, SE) + Panel-Ridge multivariat",
        "multivariate": multivar,
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
    res = analyze(events)
    # 2026-06-04: zusaetzlich Impact je LLM (fuer die LLM-Auswahl im Dashboard)
    by_llm = {}
    for llm in list_llms_in_history():
        try:
            r = analyze(events, llm=llm)
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
            rb = analyze(events, brand_filter=b)
            by_brand[b] = {k: rb[k] for k in ("impact", "multivariate", "confidence", "confidence_note",
                                              "sov_measure_days", "sov_measure_range",
                                              "n_intervals_total") if k in rb}
        except Exception as e:
            print("WARN per-Brand (%s): %s" % (b, str(e)[:80]))
    res["by_brand"] = by_brand
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
