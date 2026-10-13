"""Patch 13.10.2026: 48_BEFUNDE (Lauf 13.10., Entscheidung E) und 45 (Grenze allianz.de, Chronik).
Idempotent ueber Hashes; abweichender Ausgangsstand -> Abbruch ohne Schreiben."""
import hashlib, sys
def h(s): return hashlib.sha256(s.encode("utf-8")).hexdigest()
PLAN = []
PLAN.append(("48_BEFUNDE_2026-10-09.md", "ddac40f0be110fe95365e3ae9e201825c277c8af1b4c8ccb2fbf5358d56476dd", "588982e3027d2d170ba85a633ca22d0cfdec2395b3bc7462cc2d0bc0b4e11bdb", [
(r'''# 48 — Befunde 09.10.2026 (Abendrunde)
''',
 r'''# 48 — Befunde 09.10.2026 (Abendrunde, ergänzt 13.10.)
'''),
(r'''**Nichts geändert.** Paul entscheidet.
''',
 r'''**Nachtrag 13.10.: Paul hat sich für E entschieden, umgesetzt** (siehe 1a).
'''),
(r'''**Empfehlung:** A bis zum Lauf am 13.10., danach E, falls die Sperre bleibt.
''',
 r'''**Empfehlung (09.10.):** A bis zum Lauf am 13.10., danach E, falls die Sperre bleibt.
'''),
(r'''B nur zusammen mit E, weil B allein die Ursache rät.
''',
 r'''B nur zusammen mit E, weil B allein die Ursache rät.

### 1a · Nachtrag 13.10.: Versuch gescheitert, Option E umgesetzt

| Prüfung | Ergebnis |
|---|---|
| Lauf 13.10. (03:30–04:25 UTC) | nur ChatGPT, keine Fortschreibung; ERGO 8,71 % (06.10.: 9,27 %; 160 statt 167 Nennungen), Platz 5 wie in der Vorwoche |
| Allianz-Versuch | **gescheitert**: 713 Allianz-Adressen, 0 erreichbar, 668 × HTTP 403. 665 Adressen jetzt mit 3 Fehlschlägen → 28 Tage Sperre, nächster Versuch ≈ 10.11. |
| Ampel des Laufs | rot, Score 86, Erreichbarkeit 70,8 % (1.771 / 2.501) |
| Ohne allianz.de | 99,0 % erreichbar (1.771 / 1.788) |

**Entscheidung Paul 13.10.: Option E.** Umgesetzt in `geo-visibility-tool`,
`analyzer/data_quality.py` (Commit `e7f7f77`): Domains mit bekannter
Dauer-Sperre zählen nicht in die Erreichbarkeits-Quote; jede ausgenommene
Domain steht mit eigenen Zahlen in den Warnungen und in
`details.urls_excluded`. Gegenprobe am Lauf 13.10.: neu grün, Score 100;
ohne Ausnahme rechnet der Code wie vorher (rot, 86). Gilt ab dem Lauf 20.10.;
der Lauf 13.10. bleibt rot gespeichert.

**Nebenbefund (nicht untersucht):** Rund 15 wgv.de-Adressen im Seiten-Crawl sind
kaputt zusammengesetzt (z. B. `www.wgv.decht-eigentum`) und daher nie erreichbar.
'''),
(r'''| allianz.de-Sperre | Lauf 13.10. prüfen, dann A/E entscheiden | Claude prüft, Paul entscheidet |
| Voll-Zerlegung zurück? | Nightly 20.10. prüfen; Option „Bruch nur grounded“ | Claude prüft, Paul entscheidet |
''',
 r'''| allianz.de-Sperre | **erledigt 13.10.:** E umgesetzt; Lauf 20.10. prüfen (Ampel ohne allianz.de) | Claude |
| Voll-Zerlegung zurück? | 13.10.: 2 von 3 Messtagen; Nightly 20.10. prüfen; Option „Bruch nur grounded“ | Claude prüft, Paul entscheidet |
| wgv.de-Adressen kaputt | Ursache suchen (Adress-Zusammensetzung im Seiten-Crawl) | Claude, wenn Paul will |
'''),
]))
PLAN.append(("45_PROJEKTDOKUMENTATION.md", "598f4bc1cb05587b2d821fb7ed4b01e6e630dd5f5d4ab7203afb58ce7d144e38", "54f698fe93fdddaf5053b39f36c0cdb3e5e4b0b1edf0aebb293757b5444f0152", [
(r'''| **allianz.de sperrt den Seiten-Crawl** (seit 22.09.2026) | Rund 670 Allianz-Adressen antworten aus GitHub Actions nicht; Ursache nicht belegt. | Die Seiten-Erreichbarkeit fällt unter die Schwelle, die Laufampel steht deshalb auf Rot. Die Analysen nutzen die Ampel nicht. Optionen in `48_BEFUNDE_2026-10-09.md`. |
''',
 r'''| **allianz.de sperrt den Seiten-Crawl** (seit 22.09.2026) | Rund 700 Allianz-Adressen antworten aus GitHub Actions mit HTTP 403; Ursache nicht belegt. Nächster automatischer Versuch ≈ 10.11. | Seit 13.10.2026 (Entscheidung Paul) zählt allianz.de nicht in die Erreichbarkeits-Quote der Laufampel und wird dort als Warnung mit eigenen Zahlen ausgewiesen. Seitenänderungen der Allianz fehlen. Details `48_BEFUNDE_2026-10-09.md`, Abschnitt 1a. |
'''),
(r'''| 09.10. | Doku fortgeschrieben; Allianz-Sperre und Modell-Abkündigungen geprüft; MCP-Server v1.1 (Lesart „nur ChatGPT seit 05.10."); Voll-Zerlegung pausiert bis drei Messtage nach dem Bruch (`48_BEFUNDE_2026-10-09.md`) |
''',
 r'''| 09.10. | Doku fortgeschrieben; Allianz-Sperre und Modell-Abkündigungen geprüft; MCP-Server v1.1 (Lesart „nur ChatGPT seit 05.10."); Voll-Zerlegung pausiert bis drei Messtage nach dem Bruch (`48_BEFUNDE_2026-10-09.md`) |
| 13.10. | Allianz-Versuch gescheitert; **Entscheidung Paul:** allianz.de aus der Erreichbarkeits-Quote der Ampel (geo-visibility-tool `e7f7f77`, wirkt ab Lauf 20.10.) |
'''),
]))

neu = {}
for f, alt, ziel, reps in PLAN:
    t = open(f, encoding="utf-8").read()
    if h(t) == ziel:
        print("schon aktuell", f); continue
    if h(t) != alt:
        sys.exit("Ausgangsstand weicht ab: " + f)
    for o, n in reps:
        if t.count(o) != 1:
            sys.exit("Stelle nicht eindeutig in " + f)
        t = t.replace(o, n)
    if h(t) != ziel:
        sys.exit("Ergebnis-Hash falsch: " + f)
    neu[f] = t
for f, t in neu.items():
    open(f, "w", encoding="utf-8", newline="\n").write(t); print("geaendert", f)
