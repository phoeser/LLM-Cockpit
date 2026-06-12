#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Maßnahmen-/Interventions-Analyse (Roadmap Punkt 5): schaetzt den KAUSALEN Effekt
datierter Maßnahmen auf den Share of Voice via Difference-in-Differences (DiD)
gegen die anderen Marken als Kontrollgruppe, mit Placebo-Inferenz
(Synthetic-Control-Logik: wie aussergewoehnlich ist der Effekt ggü. den Kontrollen?).

Quellen:
  - data/interventions.json : MANUELL getaggte Maßnahmen [{date,brand,label,product?}]
  - shared/events.jsonl     : zusaetzlich automatisch erkannte Aktivitaets-Spitzen
  - data/sov_history.jsonl  : SoV-Zeitreihe je Marke (Zielgroesse)

Annahme (DiD): ohne die Maßnahme waeren Marke und Kontrollen parallel verlaufen.
Bei wenigen Messtagen sind die Werte als Tendenz zu lesen (p_placebo zeigt Sicherheit).

Aufruf im Nightly NACH sov_history.py.
"""
import json
from collections import defaultdict
from datetime import date as _date
from pathlib import Path

SOV = Path("data/sov_history.jsonl")
EVENTS = Path("shared/events.jsonl")
MANUAL = Path("data/interventions.json")
OUT = Path("data/intervention_results.json")

WINDOW = 7          # max Tage pre/post
MIN_SIDE = 2        # min Messpunkte je Seite
ACTIVITY_TYPES = ("press_mention", "news_mention", "page_new", "page_change",
                  "review_change", "review_volume", "rating_status_change",
                  "wikipedia_change", "portal_rank_change")


def sov_series():
    ser = defaultdict(dict)
    if not SOV.exists():
        return ser
    for line in SOV.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("llm"):
            continue
        if r.get("sov_pct") is not None and r.get("brand") and r.get("date"):
            ser[r["brand"]][r["date"][:10]] = float(r["sov_pct"])
    return ser


def _delta(series_for_brand, d):
    days = sorted(series_for_brand)
    pre = [x for x in days if x < d][-WINDOW:]
    post = [x for x in days if x >= d][:WINDOW]
    if len(pre) < MIN_SIDE or len(post) < MIN_SIDE:
        return None
    pre_m = sum(series_for_brand[x] for x in pre) / len(pre)
    post_m = sum(series_for_brand[x] for x in post) / len(post)
    return post_m - pre_m, len(pre), len(post)


def did_for(brand, d, ser):
    t = _delta(ser.get(brand, {}), d)
    if not t:
        return None
    t_delta, n_pre, n_post = t
    ctrl = {}
    for b, s in ser.items():
        if b == brand:
            continue
        r = _delta(s, d)
        if r:
            ctrl[b] = r[0]
    if len(ctrl) < 2:
        return None
    ctrl_mean = sum(ctrl.values()) / len(ctrl)
    did = t_delta - ctrl_mean
    # Placebo: jede Kontrolle als Pseudo-Treated gegen den Rest
    placebo = []
    allb = {brand: t_delta, **ctrl}
    for b, dlt in ctrl.items():
        others = [v for k, v in allb.items() if k != b]
        placebo.append(dlt - sum(others) / len(others))
    p = (sum(1 for x in placebo if abs(x) >= abs(did)) + 1) / (len(placebo) + 1)
    return {"did_pp": round(did, 2), "treated_delta_pp": round(t_delta, 2),
            "control_delta_pp": round(ctrl_mean, 2), "p_placebo": round(p, 3),
            "n_pre": n_pre, "n_post": n_post, "n_controls": len(ctrl)}


def auto_candidates(ser):
    """Aktivitaets-Spitzen je Marke aus dem Event-Log als Quasi-Maßnahmen."""
    if not EVENTS.exists():
        return []
    daily = defaultdict(lambda: defaultdict(int))
    for line in EVENTS.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("event_type") in ACTIVITY_TYPES and e.get("brand") and e.get("timestamp"):
            daily[e["brand"]][e["timestamp"][:10]] += 1
    out = []
    for brand, dd in daily.items():
        if brand not in ser:
            continue
        vals = list(dd.values())
        if not vals:
            continue
        mean = sum(vals) / len(vals)
        sd = (sum((v - mean) ** 2 for v in vals) / max(len(vals) - 1, 1)) ** 0.5
        thr = max(3, mean + 1.5 * sd)
        spikes = sorted([(d, c) for d, c in dd.items() if c >= thr], key=lambda kv: -kv[1])[:2]
        for d, c in spikes:
            out.append({"date": d, "brand": brand,
                        "label": "Aktivitaets-Spitze (%d Events)" % c, "source": "auto"})
    return out


def main():
    ser = sov_series()
    interventions = []
    if MANUAL.exists():
        try:
            mj = json.loads(MANUAL.read_text(encoding="utf-8"))
            for it in (mj.get("interventions") or []):
                if it.get("date") and it.get("brand"):
                    it = dict(it); it["source"] = "manuell"
                    interventions.append(it)
        except Exception as e:
            print("WARN interventions.json:", str(e)[:80])
    interventions += auto_candidates(ser)

    results = []
    for it in interventions:
        r = did_for(it["brand"], it["date"][:10], ser)
        if not r:
            continue
        r.update({"date": it["date"][:10], "brand": it["brand"],
                  "label": it.get("label", ""), "product": it.get("product"),
                  "source": it.get("source", "manuell")})
        results.append(r)
    # dedupe (brand,date,source) + nach |Effekt| sortieren
    seen = set(); uniq = []
    for r in sorted(results, key=lambda x: -abs(x["did_pp"])):
        k = (r["brand"], r["date"], r["source"])
        if k in seen:
            continue
        seen.add(k); uniq.append(r)
    out = {"generated_at": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
           "method": "Difference-in-Differences gg. andere Marken + Placebo-Inferenz",
           "window_days": WINDOW, "n_results": len(uniq),
           "measure_days": len({d for m in ser.values() for d in m}),
           "results": uniq,
           "note": "did_pp = kausaler Effekt der Maßnahme auf den SoV (Prozentpunkte) ggü. "
                   "der Kontrollgruppe. p_placebo < 0,1 = der Effekt hebt sich klar von "
                   "zufaelligen Kontroll-Schwankungen ab. Wenige Messtage -> als Tendenz lesen."}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OK: %d Maßnahmen ausgewertet -> %s" % (len(uniq), OUT))
    for r in uniq[:8]:
        print("  %-12s %s %-28s DiD=%+.2f Pp  p=%.2f" %
              (r["brand"], r["date"], r["label"][:28], r["did_pp"], r["p_placebo"]))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
