#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Preis-Zeitreihe archivieren (Grundlage der KAUSALEN Within-Preis-Identifikation).

Warum: Das gepoolte Preis-Levelmodell zeigt den Preis heute nur als BETWEEN-Effekt
(guenstigere Marken sind sichtbarer) — keine Kausalaussage. Der kausal saubere
WITHIN-Kanal (eine Marke mit sich selbst) ist leer, solange Preise im Messfenster
nicht variieren. Diese Zeitreihe haelt den Relativpreis je Marke x Produkt Tag fuer
Tag fest; sobald eine Marke ihren Relativpreis aendert, wird die Sichtbarkeits-
Reaktion messbar (Event-Study / Within-Panel).

Quelle: dieselbe Logik wie das Modell — correlation_impact._relprice_map() (Crawler
price_comparison.json + manuelle Vollerhebung price_manual.json, Alias-/Keymap-
Aufloesung). Bewusst importiert statt dupliziert, damit Preis-Zuordnung und Modell
NIE auseinanderlaufen.

Aufruf im Nightly NACH scripts/update_prices.py, VOR scripts/correlation_impact.py.
Ausgabe: data/price_history.jsonl (append-only, idempotent je date x brand x product).
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from correlation_impact import _relprice_map  # noqa: E402

HIST = Path("data/price_history.jsonl")


def _load_keys():
    keys = set()
    if HIST.exists():
        for line in HIST.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                keys.add((r.get("date"), r.get("brand"), r.get("product")))
            except Exception:
                pass
    return keys


def main():
    try:
        rp = _relprice_map()  # {product_id: {brand: relprice}}
    except Exception as e:
        print("archive_price_cells: _relprice_map fehlgeschlagen: %s" % str(e)[:120])
        return 0
    if not rp:
        print("archive_price_cells: keine Preisdaten (rp leer) — nichts archiviert.")
        return 0
    day = datetime.now(timezone.utc).date().isoformat()
    seen = _load_keys()
    new = []
    for product, brands in rp.items():
        for brand, relp in (brands or {}).items():
            if relp is None:
                continue
            key = (day, brand, product)
            if key in seen:
                continue
            new.append({"date": day, "brand": brand, "product": product,
                        "relprice": round(float(relp), 4)})
    if new:
        HIST.parent.mkdir(parents=True, exist_ok=True)
        with HIST.open("a", encoding="utf-8") as f:
            f.write("\n".join(json.dumps(r, ensure_ascii=False) for r in new) + "\n")
    total = _load_keys()
    n_days = len({k[0] for k in total})
    n_brands = len({k[1] for k in total})
    print("archive_price_cells: %s — %d neue Zellen (Reihe jetzt %d Zeilen, %d Tage, %d Marken, %d Produkte heute)"
          % (day, len(new), len(total), n_days, n_brands,
             len({p for p in rp})))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
