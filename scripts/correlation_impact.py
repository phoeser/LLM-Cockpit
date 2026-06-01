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


def build_sov_series_from_history():
    """SoV(brand) -> sortierte (day, pct) aus der dichten sov_history.jsonl (1 Punkt/Tag)."""
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
        day, brand, pct = r.get("date"), r.get("brand"), r.get("sov_pct")
        if not day or not brand or pct is None:
            continue
        series.setdefault(brand, {})[day] = float(pct)  # letzter Wert/Tag gewinnt
    return {b: sorted(m.items()) for b, m in series.items()}


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


def confidence(n_measure_days):
    if n_measure_days < 6:
        return ("unzureichend", "Zu wenige SoV-Messpunkte fuer eine belastbare Aussage.")
    if n_measure_days < 15:
        return ("vorlaeufig", "Erste Tendenz — noch nicht statistisch belastbar.")
    if n_measure_days < 30:
        return ("moderat", "Tendenz mit mittlerer Sicherheit.")
    return ("belastbar", "Ausreichend Messpunkte fuer eine belastbare Aussage.")


def analyze(events):
    # Vorrang: dichte SoV-Historie; Fallback: sov_change-Events
    sov = build_sov_series_from_history()
    sov_source = "sov_history"
    if not sov:
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
        b = e.get("brand")
        day = _day(e.get("timestamp"))
        if not b or not day:
            continue
        counts.setdefault(b, {}).setdefault(day, {})
        counts[b][day][t] = counts[b][day].get(t, 0) + 1

    # Pro Marke Intervalle bilden, je Typ Datenpunkte (count_in_interval, delta_sov) sammeln
    points = {t: {"x": [], "y": []} for t in IMPACT_TYPES}
    intervals_total = 0
    for brand, ser in sov.items():
        for i in range(len(ser) - 1):
            start_day, start_pct = ser[i]
            end_day, end_pct = ser[i + 1]
            delta = end_pct - start_pct
            intervals_total += 1
            # Events der Marke im Fenster [start_day (+lag), end_day)
            for t in IMPACT_TYPES:
                c = 0
                bydays = counts.get(brand, {})
                for day, tc in bydays.items():
                    if start_day <= day < end_day:
                        c += tc.get(t, 0)
                points[t]["x"].append(c)
                points[t]["y"].append(delta)

    results = {}
    for t in IMPACT_TYPES:
        xs, ys = points[t]["x"], points[t]["y"]
        n = len(xs)
        n_with = sum(1 for x in xs if x > 0)
        r = pearson(xs, ys)
        with_mean = ([y for x, y in zip(xs, ys) if x > 0])
        without_mean = ([y for x, y in zip(xs, ys) if x == 0])
        eff = None
        if with_mean and without_mean:
            eff = (sum(with_mean) / len(with_mean)) - (sum(without_mean) / len(without_mean))
        if n_with == 0:
            continue  # Typ kam in keinem Intervall vor -> nicht ausweisen
        results[t] = {
            "label": TYPE_LABEL.get(t, t),
            "pearson_r": round(r, 3) if r is not None else None,
            "avg_sov_effect_pp": round(eff, 2) if eff is not None else None,
            "n_intervals": n,
            "n_with_event": n_with,
        }

    # nach |Effekt| sortiert
    ordered = dict(sorted(results.items(),
                          key=lambda kv: -abs(kv[1]["avg_sov_effect_pp"] or 0)))
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": "interval-event-study",
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
