#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neutrale Peec-SoV aus der Prompt-Ebene rechnen.

HINTERGRUND (Pruefung 31.07.2026): Peecs Share of Voice im Projekt "ERGO Germany"
ist kein neutrales Marktranking. 132 von 614 Prompts (21 %) nennen ERGO ausdruecklich
im Text, kein einziger einen Wettbewerber. Dadurch steht ERGO in Peec auf Platz 1
(~23 %), waehrend der neutrale eigene Crawl Allianz und HUK vorn sieht (ERGO ~7 %).

Dieses Skript zerlegt die Peec-SoV in
  - overall_sov : alle Prompts (= die bisher gezeigte, ERGO-zentrierte Zahl)
  - neutral_sov : NUR Prompts OHNE Markennamen im Text (fairer Marktvergleich)
und schreibt data/peec_neutral_sov.json (Runtime-Fetch fuers Dashboard).

EINGABE: data/peec_prompt_level.csv (Spalten: marke;prompt_id;prompt_text;mention_count;...)

WICHTIG: Der Prompt-Level-Export muss ALLE getrackten Marken enthalten, nicht nur
ERGO + Allianz. Solange nur zwei Marken drin sind, ist neutral_sov nur ein
ERGO-vs-Allianz-Vergleich (das Feld `brands_in_export` weist das aus).
"""
import csv
import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(BASE, "data", "peec_prompt_level.csv")
OUT = os.path.join(BASE, "data", "peec_neutral_sov.json")

# Markennamen, deren Vorkommen im Prompt-Text den Prompt als "markiert" kennzeichnet.
# Bewusst breit: jeder Prompt, der IRGENDEINE Marke nennt, ist nicht neutral.
BRAND_TOKENS = [
    "ergo", "allianz", "huk", "axa", "generali", "signal iduna", "cosmos",
    "debeka", "gothaer", "zurich", "barmenia", "arag", "adac", "devk", "r+v",
    "hdi", "vhv", "wgv", "hansemerkur", "lv 1871", "hannoversche", "dkv",
    "alte leipziger", "die bayerische", "württembergische", "wuerttembergische",
]


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


_BRAND_RE = re.compile(r"\\b(" + "|".join(re.escape(t) for t in BRAND_TOKENS) + r")\\b")


def _is_branded(text):
    # Wortgrenzen statt Substring: sonst trifft "ergo" auch "ergonomisch" und das
    # gewoehnliche Fuellwort "ergo" (= also/folglich) und wuerde neutrale Prompts
    # faelschlich als markiert aussortieren (Review-Befund 01.08.2026).
    return bool(_BRAND_RE.search((text or "").lower()))


def main():
    if not os.path.exists(CSV):
        print("FEHLER: %s fehlt — erst den Peec-Prompt-Level-Export laufen lassen." % CSV)
        return 1
    with open(CSV, encoding="utf-8-sig") as f:
        first = f.readline()
    delim = ";" if first.count(";") >= first.count(",") else ","
    rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig"), delimiter=delim))

    prompt_text = {}
    for r in rows:
        prompt_text[r.get("prompt_id")] = r.get("prompt_text", "")
    branded = {pid for pid, t in prompt_text.items() if _is_branded(t)}

    # mentions je Marke, gesamt und nur-neutral
    all_men = {}
    neu_men = {}
    for r in rows:
        b = r.get("marke")
        m = _num(r.get("mention_count"))
        if not b:
            continue
        all_men[b] = all_men.get(b, 0.0) + m
        if r.get("prompt_id") not in branded:
            neu_men[b] = neu_men.get(b, 0.0) + m

    def _sov(men):
        tot = sum(men.values()) or 1.0
        return {b: round(100 * v / tot, 2) for b, v in men.items()}

    overall = _sov(all_men)
    neutral = _sov(neu_men)
    brands = sorted(all_men, key=lambda b: -overall.get(b, 0))
    n_prompts = len(prompt_text)
    out = {
        "as_of": None,
        "n_prompts": n_prompts,
        "n_branded_prompts": len(branded),
        "n_neutral_prompts": n_prompts - len(branded),
        "brands_in_export": brands,
        "complete": len(brands) >= 10,  # Flag: genug Marken fuer ein echtes Ranking?
        "overall_sov": {b: overall.get(b) for b in brands},
        "neutral_sov": {b: neutral.get(b) for b in brands},
        "note": ("overall_sov = alle Prompts (ERGO-zentriert). neutral_sov = nur Prompts "
                 "OHNE Markennamen im Text. Aussagekraeftig erst, wenn der Prompt-Level-"
                 "Export ALLE Marken enthaelt (complete=true)."),
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("OK: %s" % OUT)
    print("  Prompts: %d gesamt, %d markiert, %d neutral | Marken im Export: %d (complete=%s)"
          % (n_prompts, len(branded), n_prompts - len(branded), len(brands), out["complete"]))
    for b in brands[:8]:
        print("  %-16s overall %5s%%  neutral %5s%%" % (b, overall.get(b), neutral.get(b)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
