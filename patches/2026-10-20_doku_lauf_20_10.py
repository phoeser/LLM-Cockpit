"""Patch 20.10.2026: 48_BEFUNDE – Lauf 20.10. (Option E wirkt, Ampel gruen), Voll-Zerlegung wieder da.
Idempotent ueber Hashes; abweichender Ausgangsstand -> Abbruch ohne Schreiben."""
import hashlib, sys
def h(s): return hashlib.sha256(s.encode("utf-8")).hexdigest()
PLAN = []
PLAN.append(("48_BEFUNDE_2026-10-09.md", "588982e3027d2d170ba85a633ca22d0cfdec2395b3bc7462cc2d0bc0b4e11bdb", "ea95ea95f4982706b0c84f662502ee57860cc91bc5399d5eb77e4a5c56b0b4b0", [
(r'''# 48 — Befunde 09.10.2026 (Abendrunde, ergänzt 13.10.)
''',
 r'''# 48 — Befunde 09.10.2026 (Abendrunde, ergänzt 13.10. und 20.10.)
'''),
(r'''kaputt zusammengesetzt (z. B. `www.wgv.decht-eigentum`) und daher nie erreichbar.

''',
 r'''kaputt zusammengesetzt (z. B. `www.wgv.decht-eigentum`) und daher nie erreichbar.

### 1b · Nachtrag 20.10.: Option E wirkt

| Prüfung | Ergebnis |
|---|---|
| Lauf 20.10. (01:44–02:08 UTC) | nur ChatGPT, keine Fortschreibung; ERGO 8,88 % (159 Nennungen), Platz 5 |
| Ampel | **grün, Score 100** — 99 % erreichbar (1.773 / 1.790) |
| allianz.de | als Warnung ausgewiesen: 0 / 714 erreichbar, `details.urls_excluded` gefüllt |

'''),
(r'''sofort wieder da. Das ändert die Auswertung — Paul entscheidet.

''',
 r'''sofort wieder da. Das ändert die Auswertung — Paul entscheidet.

**Nachtrag 20.10.:** Mit dem Lauf 20.10. liegen drei Messtage nach dem Bruch
vor; die Voll-Zerlegung rechnet wieder (Nightly 20.10., 10:42 UTC). Kanal ohne
Websuche, Effekt je Standardabweichung:

| Treiber | within | between |
|---|---|---|
| Quellpräsenz | +7,48 pp (q = 0,031) | +4,85 pp (q = 0,031) |
| Markengröße | — | +6,40 pp (q = 0,031) |
| Relativpreis | +0,76 pp (q = 0,51) | −1,00 pp (q = 0,51) |

Basis sind nur drei Messtage (06.–20.10.); die Werte werden mit jeder Woche
stabiler. „combined“ liefert dieselben Zahlen, weil es nur noch einen Kanal gibt.
Die Option oben ist damit erledigt.

'''),
(r'''| allianz.de-Sperre | **erledigt 13.10.:** E umgesetzt; Lauf 20.10. prüfen (Ampel ohne allianz.de) | Claude |
| Voll-Zerlegung zurück? | 13.10.: 2 von 3 Messtagen; Nightly 20.10. prüfen; Option „Bruch nur grounded“ | Claude prüft, Paul entscheidet |
''',
 r'''| allianz.de-Sperre | **erledigt:** E umgesetzt 13.10., wirkt seit Lauf 20.10. (grün, 100); nächster Allianz-Versuch ≈ 10.11. | — |
| Voll-Zerlegung zurück? | **ja, seit Nightly 20.10.** (3 Messtage nach dem Bruch) für ungrounded; „combined“ ist jetzt identisch mit ungrounded, weil nur noch ChatGPT gemessen wird. grounded bleibt aus. Option „Bruch nur grounded“ damit hinfällig | — |
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
