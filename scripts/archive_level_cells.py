#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Archiviert je Nacht die Level-Modell-Zellen (Marke x Thema, Engine-aggregiert) aus
data/geo_snapshot.json nach data/level_cells_history.jsonl (append-only, idempotent
je date x brand x topic).

Zweck: Das Preis-Level-Modell (correlation_impact.level_model_mundlak) laeuft bisher
auf EINEM Snapshot. Dessen SoV je Zelle schwankt taeglich (LLM-Nichtdeterminismus).
Ein ueber mehrere saubere Tage gemittelter Zellwert senkt dieses Messrauschen — die
statistisch ehrliche Form von "Pooling" (kein Stapeln abhaengiger Tageszeilen, sondern
Mittelung der Messgroesse je Zelle). Dieses Skript legt die dafuer noetige Reihe an.

Gespeichert werden nur Roh-Messgroessen (SoV, Zitatzahlen je Engine-Gruppe); Relativpreis
und Groesse werden erst im Modell dazugejoint (statisch), damit sich Preis-Verbesserungen
rueckwirkend auf die ganze Reihe auswirken.

Aufruf im Nightly NACH scripts/update_snapshot.py, VOR scripts/correlation_impact.py.
Backfill aus der Git-Historie: python archive_level_cells.py <pfad_zu_snapshot.json>
(mehrfach aufrufbar, idempotent).
"""
import json
import sys
from pathlib import Path

GROUNDED = {"gemini", "perplexity"}
SNAP_DEFAULT = Path("data/geo_snapshot.json")
HIST = Path("data/level_cells_history.jsonl")

# Spiegel von correlation_impact.FP_BRAND_DOMAINS — bewusst dupliziert, damit dieses
# Skript ohne Import laeuft. Bei Aenderung BEIDE Stellen pflegen.
FP_BRAND_DOMAINS = {
    "ergo.de": "ERGO", "ergo.com": "ERGO", "ergodirekt.de": "ERGO",
    "ergo-reiseversicherung.de": "ERGO",
    "allianz.de": "Allianz", "allianzdirect.de": "Allianz",
    "allianz-reiseversicherung.de": "Allianz",
    "huk.de": "HUK-Coburg", "huk24.de": "HUK-Coburg", "huk-coburg.de": "HUK-Coburg",
    "axa.de": "AXA", "generali.de": "Generali", "signal-iduna.de": "Signal Iduna",
    "cosmosdirekt.de": "CosmosDirekt", "cosmos-direkt.de": "CosmosDirekt",
    "hannoversche.de": "Hannoversche", "ruv.de": "R+V", "devk.de": "DEVK",
    "adac.de": "ADAC", "arag.de": "ARAG", "alte-leipziger.de": "Alte Leipziger",
    "barmenia.de": "Barmenia", "da-direkt.de": "DA Direkt", "debeka.de": "Debeka",
    "diebayerische.de": "Die Bayerische", "die-bayerische.de": "Die Bayerische",
    "gothaer.de": "Gothaer", "hdi.de": "HDI", "hansemerkur.de": "HanseMerkur",
    "lv1871.de": "LV 1871", "vhv.de": "VHV", "wgv.de": "WGV",
    "wuerttembergische.de": "Württembergische", "zurich.de": "Zurich",
}


def _dom2brand(d):
    return FP_BRAND_DOMAINS.get(str(d or "").replace("www.", ""))


def extract_cells(snap):
    """-> (day, [row,...]); row je Marke x Thema mit Engine-aggregierten Messgroessen."""
    day = (snap.get("finished_at") or snap.get("started_at") or "")[:10]
    prods = snap.get("products") or {}
    llms = snap.get("llms") or []
    if not llms:
        for pd in prods.values():
            for k in (pd.get("summary_by_llm") or {}):
                if k not in llms:
                    llms.append(k)
    rows = []
    for pid, pd in prods.items():
        sbl = pd.get("summary_by_llm") or {}
        # SoV je Marke je Engine (in %)
        sov = {}
        for eng in llms:
            for br in ((sbl.get(eng) or {}).get("brands") or []):
                nm = br.get("name")
                if nm:
                    sov.setdefault(nm, {})[eng] = (br.get("share_of_voice") or 0.0) * 100.0
        # Zitationen je Marke je Engine + Gesamtzitate je Engine (aus cited_sources.by_llm)
        cs = pd.get("cited_sources") or {}
        byl = cs.get("by_llm") or {}
        cite = {}      # brand -> {eng: count}
        citetot = {}   # eng -> total citations dieses Produkts
        for eng, rowsl in byl.items():
            for r in (rowsl or []):
                cnt = r.get("count") or 0
                citetot[eng] = citetot.get(eng, 0) + cnt
                b = _dom2brand(r.get("domain"))
                if b:
                    cite.setdefault(b, {})
                    cite[b][eng] = cite[b].get(eng, 0) + cnt

        # Ausfall-Guard: Engine mit 0 SoV ueber ALLE Marken zaehlt als "nicht praesent"
        # (Regel: keine Daten ist kein Befund).
        def _present(group):
            out = []
            for e in group:
                if sum(sov.get(b, {}).get(e, 0.0) for b in sov) > 1e-9:
                    out.append(e)
            return out
        g_eng = _present([e for e in llms if e in GROUNDED])
        u_eng = _present([e for e in llms if e not in GROUNDED])
        a_eng = _present(list(llms))

        for b in (set(sov) | set(cite)):
            def _sov(engs):
                if not engs:
                    return None
                vals = [sov.get(b, {}).get(e, 0.0) for e in engs]
                return round(sum(vals) / len(vals), 4)

            def _cite(engs):
                return sum(cite.get(b, {}).get(e, 0) for e in engs)

            def _tot(engs):
                return sum(citetot.get(e, 0) for e in engs)
            rows.append({
                "date": day, "brand": b, "topic": pid,
                "sov_g": _sov(g_eng), "sov_u": _sov(u_eng), "sov_c": _sov(a_eng),
                "cite_g": _cite(g_eng), "cite_u": _cite(u_eng), "cite_c": _cite(a_eng),
                "ctot_g": _tot(g_eng), "ctot_u": _tot(u_eng), "ctot_c": _tot(a_eng),
            })
    return day, rows


def _load_keys():
    keys = set()
    if HIST.exists():
        for line in HIST.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                keys.add((r.get("date"), r.get("brand"), r.get("topic")))
            except Exception:
                pass
    return keys


def main(argv):
    snap_path = Path(argv[1]) if len(argv) > 1 else SNAP_DEFAULT
    try:
        snap = json.loads(snap_path.read_text(encoding="utf-8"))
    except Exception as e:
        print("WARN: %s nicht lesbar: %s" % (snap_path, str(e)[:80]))
        return 0
    day, rows = extract_cells(snap)
    if not day:
        print("WARN: kein Datum im Snapshot — nichts geschrieben")
        return 0
    seen = _load_keys()
    new = [r for r in rows if (r["date"], r["brand"], r["topic"]) not in seen]
    if new:
        HIST.parent.mkdir(parents=True, exist_ok=True)
        with HIST.open("a", encoding="utf-8") as f:
            f.write("\n".join(json.dumps(r, ensure_ascii=False) for r in new) + "\n")
    total = len(_load_keys())
    print("archive_level_cells: %s — %d neue Zellen (Reihe jetzt %d Zellen, %d Tage)"
          % (day, len(new), total,
             len({k[0] for k in _load_keys()})))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
