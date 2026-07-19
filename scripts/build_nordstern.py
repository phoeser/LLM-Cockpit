#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Erzeugt/erweitert data/peec_nordstern.json ADDITIV aus data/peec_prompt_level.csv.
Methodik identisch zu den bestehenden Kanal-Bloecken (grounded/ui_mixed/alle):
  Beobachtung = eine Prompt x Kanal-Zeile mit Daten (Nenner).
  Nennung  = mention_count > 0.
  Positiv  = zusaetzlich sentiment >= 60, nur wo sentiment_count > 0.
  Fehlt ein Kanal komplett -> Werte null + keine_daten:true (NIE 0).
Neu (rein additiv):
  - ergo.je_thema / allianz_benchmark.je_thema : je Topic {grounded/ui_mixed/alle}
  - vorwoche : Trend-Platzhalter; der Wochen-Task befuellt ihn aus der ALTEN Datei,
    BEVOR er sie ueberschreibt.
Bestehende Felder werden per Round-Trip (indent=2, ensure_ascii=False, keine
End-Newline) byte-gleich erhalten; es kommen nur Schluessel hinzu.
"""
import csv, json, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV  = os.path.join(BASE, "data", "peec_prompt_level.csv")
OUT  = os.path.join(BASE, "data", "peec_nordstern.json")
CLASSES = ["grounded", "ui_mixed", "alle"]

def _num(s):
    s = (s or "").strip()
    if s == "": return None
    try: return float(s)
    except ValueError: return None

def _round1(x): return round(x, 1)

def load_rows():
    with open(CSV, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))

def agg(rows):
    """rows -> dict(n_prompts,n_genannt,n_positiv,...) oder keine_daten-Block."""
    n = gen = pos = 0
    for d in rows:
        n += 1
        mc = _num(d.get("mention_count")) or 0
        if mc > 0:
            gen += 1
            sent = _num(d.get("sentiment")); sc = _num(d.get("sentiment_count"))
            if sc and sc > 0 and sent is not None and sent >= 60:
                pos += 1
    if n == 0:
        return {"n_prompts": 0, "n_genannt": None, "n_positiv": None,
                "empfehlungsrate_light_pct": None, "nennrate_pct": None, "keine_daten": True}
    return {"n_prompts": n, "n_genannt": gen, "n_positiv": pos,
            "empfehlungsrate_light_pct": _round1(100 * pos / n),
            "nennrate_pct": _round1(100 * gen / n), "keine_daten": False}

def rows_for(rows, marke, cls, topic=None):
    out = []
    for d in rows:
        if d["marke"] != marke: continue
        if topic is not None and (d.get("topic") or "").strip() != topic: continue
        et = (d.get("engine_typ") or "").strip()
        if cls != "alle" and et != cls: continue
        out.append(d)
    return out

def je_thema(rows, marke):
    topics = sorted({(d.get("topic") or "").strip() for d in rows if d["marke"] == marke and (d.get("topic") or "").strip()})
    res = {}
    for t in topics:
        res[t] = {cls: agg(rows_for(rows, marke, cls, t)) for cls in CLASSES}
    return res

def empty_vorwoche_side():
    return {cls: {"empfehlungsrate_light_pct": None, "nennrate_pct": None} for cls in CLASSES}

def main():
    rows = load_rows()
    with open(OUT, encoding="utf-8") as f:
        j = json.load(f)

    # --- je_thema additiv (nach je_kanal einsortiert, ohne Bestehendes zu aendern) ---
    for side, marke in (("ergo", "ERGO"), ("allianz_benchmark", "Allianz")):
        jt = je_thema(rows, marke)
        blk = j[side]
        # neuen, geordneten Block bauen: je_kanal, je_thema, grounded, ui_mixed, alle
        newblk = {}
        for k in blk:
            newblk[k] = blk[k]
            if k == "je_kanal":
                newblk["je_thema"] = jt
        if "je_thema" not in newblk:  # Fallback, falls je_kanal fehlt
            newblk["je_thema"] = jt
        j[side] = newblk

    # --- vorwoche additiv ---
    carry = None
    for a in sys.argv:
        if a.startswith("--carry-from="):
            carry = a.split("=", 1)[1]
    if carry and os.path.exists(carry):
        # Wochen-Task: Kanal-Raten der ALTEN Datei als Vorwoche uebernehmen (vor dem Ueberschreiben).
        old = json.load(open(carry, encoding="utf-8"))
        def side_from(o):
            return {cls: {"empfehlungsrate_light_pct": (o.get(cls) or {}).get("empfehlungsrate_light_pct"),
                          "nennrate_pct": (o.get(cls) or {}).get("nennrate_pct")} for cls in CLASSES}
        j["vorwoche"] = {
            "as_of": old.get("as_of"),
            "ergo": side_from(old.get("ergo", {})),
            "allianz_benchmark": side_from(old.get("allianz_benchmark", {})),
        }
    elif "vorwoche" not in j:
        # Erstlauf / Backfill: leerer Platzhalter, NIE 0 (Trend ab naechster Woche).
        j["vorwoche"] = {
            "as_of": None,
            "hinweis": "erste Messung 17.07., Trend ab naechstem Wochen-Export",
            "ergo": empty_vorwoche_side(),
            "allianz_benchmark": empty_vorwoche_side(),
        }

    s = json.dumps(j, indent=2, ensure_ascii=False)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(s)   # keine End-Newline (wie Original)

    # --- Plausibilisierung: gewichtetes Mittel der Themen-Raten ~ Kanal-Rate ---
    if "--check" in sys.argv:
        for side, marke in (("ergo", "ERGO"), ("allianz_benchmark", "Allianz")):
            print("==", marke)
            jt = j[side]["je_thema"]
            for cls in CLASSES:
                chan = j[side][cls]
                wn = we = 0
                for t, tb in jt.items():
                    b = tb[cls]
                    if b["keine_daten"]: continue
                    wn += b["n_prompts"]
                    we += b["n_positiv"]
                wmean = 100 * we / wn if wn else None
                print(f"  {cls:8s} Kanal empf={chan.get('empfehlungsrate_light_pct')}  "
                      f"gew.Mittel Themen={None if wmean is None else round(wmean,1)}  "
                      f"(n Kanal={chan.get('n_prompts')} n Themen-Summe={wn})")

if __name__ == "__main__":
    main()
