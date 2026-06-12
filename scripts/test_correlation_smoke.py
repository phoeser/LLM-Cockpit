#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke- und Placebo-Test fuer correlation_impact.py (Review 2026-06-12).

Validiert die Analyse-Engine mit synthetischen Daten in einem Temp-Verzeichnis
(beruehrt KEINE echten Daten):
  1. Smoke-Test:  injizierter, bekannter Effekt (+1.5 Pp je press_mention)
                  muss erkannt werden (Effekt > 0.8, signifikant).
  2. Placebo-Test: dieselben Events auf Zufallstage verschoben duerfen
                  KEINEN signifikanten Effekt zeigen.

Aufruf:  python scripts/test_correlation_smoke.py   (Exit 0 = OK)
Kann optional als CI-Step vor dem Nightly-Deploy laufen.
"""
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "correlation_impact.py"


def make_data(tmp, placebo=False, seed=7):
    random.seed(seed)
    brands = ["ERGO", "Allianz", "AXA"]
    days = ["2026-05-%02d" % d for d in range(10, 32)] + \
           ["2026-06-%02d" % d for d in range(1, 12)]
    hist, evts = [], []
    sov = {b: 20.0 for b in brands}
    for day in days:
        for b in brands:
            hist.append({"date": day, "brand": b,
                         "sov_pct": round(sov[b], 2), "source": "snapshot"})
            if random.random() < 0.3:
                evts.append({"id": "e%d" % len(evts),
                             "timestamp": day + "T05:00:00Z",
                             "event_type": "press_mention", "brand": b,
                             "source": "t", "crawler": "t",
                             "magnitude": 1.0, "detail": {}})
                sov[b] += 1.5  # echter Effekt
            sov[b] += random.gauss(0, 0.8)
    if placebo:
        random.seed(42)
        for e in evts:
            e["timestamp"] = random.choice(days) + "T05:00:00Z"
    (tmp / "data").mkdir(exist_ok=True)
    (tmp / "shared").mkdir(exist_ok=True)
    (tmp / "data/sov_history.jsonl").write_text(
        "\n".join(json.dumps(r) for r in hist) + "\n", encoding="utf-8")
    (tmp / "shared/events.jsonl").write_text(
        "\n".join(json.dumps(r) for r in evts) + "\n", encoding="utf-8")


def run_case(placebo):
    tmp = Path(tempfile.mkdtemp(prefix="corrtest_"))
    try:
        make_data(tmp, placebo=placebo)
        shutil.copy2(SCRIPT, tmp / "correlation_impact.py")
        subprocess.run([sys.executable, "correlation_impact.py"],
                       cwd=tmp, check=True, capture_output=True)
        res = json.loads((tmp / "data/correlation_impact.json").read_text(encoding="utf-8"))
        return res["impact"]["press_mention"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    imp = run_case(placebo=False)
    print("Smoke:   Effekt=%s Pp/Tag, KI=[%s..%s], signifikant=%s"
          % (imp["avg_sov_effect_pp"], imp["ci95_low_pp"], imp["ci95_high_pp"], imp["significant"]))
    assert imp["avg_sov_effect_pp"] and imp["avg_sov_effect_pp"] > 0.8 and imp["significant"], \
        "FEHLER: bekannter +1.5-Effekt nicht erkannt"

    imp = run_case(placebo=True)
    print("Placebo: Effekt=%s Pp/Tag, signifikant=%s"
          % (imp["avg_sov_effect_pp"], imp["significant"]))
    assert not imp["significant"], "FEHLER: Placebo faelschlich signifikant"

    print("OK: Smoke- und Placebo-Test bestanden")
    return 0


if __name__ == "__main__":
    sys.exit(main())
