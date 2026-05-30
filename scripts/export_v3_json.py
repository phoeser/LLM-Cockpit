#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3-Export: schreibt die dashboard-fertigen JSON-Dateien, die dashboard_v3.html
per fetch() laedt.

update_sentiment.py / update_press.py injizieren ein dashboard-fertiges Payload
als `const SENTIMENT_DATA = {...}` / `const PRESS_DATA = {...}` in
dashboard_template.html. Dieses Skript extrahiert die fertigen Bloecke und
schreibt sie als eigene Dateien:
  - data/sentiment_dashboard.json
  - data/press_dashboard.json

Additiv; kein Eingriff in die Crawler-Skripte. Aufruf NACH update_sentiment.py
und update_press.py.
"""
import json
import re
import sys
from pathlib import Path

TEMPLATE = Path("dashboard_template.html")

TARGETS = [
    (r"const SENTIMENT_DATA\s*=\s*", Path("data/sentiment_dashboard.json")),
    (r"const PRESS_DATA\s*=\s*",     Path("data/press_dashboard.json")),
]


def extract_object(text, marker_regex):
    m = re.search(marker_regex, text)
    if not m:
        return None
    start = text.find("{", m.start())
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for j in range(start, len(text)):
        c = text[j]
        if esc:
            esc = False
            continue
        if c == "\\" and in_str:
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:j + 1]
    return None


def main():
    if not TEMPLATE.exists():
        print("FEHLER: dashboard_template.html nicht gefunden — Export uebersprungen")
        return 0
    html = TEMPLATE.read_text(encoding="utf-8")
    ok = 0
    for rgx, out_path in TARGETS:
        blob = extract_object(html, rgx)
        if blob is None:
            print("WARN: Block nicht gefunden: %s (uebersprungen)" % rgx)
            continue
        try:
            obj = json.loads(blob)
        except Exception as e:
            print("WARN: JSON-Parse fehlgeschlagen fuer %s: %s" % (rgx, e))
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        print("v3-Export: %s (%d Bytes)" % (out_path, out_path.stat().st_size))
        ok += 1
    print("v3-Export fertig: %d/%d Dateien geschrieben" % (ok, len(TARGETS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
