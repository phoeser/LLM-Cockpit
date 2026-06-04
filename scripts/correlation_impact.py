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


def analyze(events, llm=None):
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

    # Event-Counts je (brand, day, type)
    counts = {}
    for e in events:
        t = e.get("event_type")
        if t not in IMPACT_TYPES:
            continue
        # Review-Fix 2026-06-04: historische Subdomain-Events des alten
        # Domain-Footprint-Crawlers sind KEINE Inhaltsseiten -> ausschliessen
        if e.get("crawler") == "update_domain_footprint" and t in ("page_new", "page_change"):
            continue
        b = e.get("brand")
        day = _day(e.get("timestamp"))
        if not b or not day:
            continue
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
    intervals_total = len(points_raw)

    # Brand-Demeaning
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
        results[t] = {
            "label": TYPE_LABEL.get(t, t),
            "pearson_r": round(r, 3) if r is not None else None,
            "spearman_r": round(rho, 3) if rho is not None else None,
            "avg_sov_effect_pp": round(eff, 3) if eff is not None else None,
            "effect_se_pp": round(se, 3) if se is not None else None,
            "n_intervals": n,
            "n_with_event": n_with,
            "type_confidence": type_confidence(n_with),
        }

    # nach |Effekt| sortiert
    ordered = dict(sorted(results.items(),
                          key=lambda kv: -abs(kv[1]["avg_sov_effect_pp"] or 0)))
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": "interval-event-study v2 (Raten/Tag, brand-demeaned, Spearman, SE)",
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
            by_llm[llm] = {k: r[k] for k in ("impact", "confidence", "confidence_note",
                                             "sov_measure_days", "sov_measure_range",
                                             "n_intervals_total", "brands_with_sov") if k in r}
        except Exception as e:
            print("WARN per-LLM (%s): %s" % (llm, str(e)[:80]))
    res["by_llm"] = by_llm
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
