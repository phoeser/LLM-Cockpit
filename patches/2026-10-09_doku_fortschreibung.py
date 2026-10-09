"""Patch 09.10.2026: Doku fortgeschrieben (45, 46, 47, README), 48_BEFUNDE neu.
Idempotent ueber Hashes; abweichender Ausgangsstand -> Abbruch ohne Schreiben."""
import hashlib, os, sys
def h(s): return hashlib.sha256(s.encode("utf-8")).hexdigest()
PLAN = []
PLAN.append(("45_PROJEKTDOKUMENTATION.md", "3f2ffdfd2aa6703eb30625260021c03616bcbe161d6b3ce5d6407802ca5172fa", "598f4bc1cb05587b2d821fb7ed4b01e6e630dd5f5d4ab7203afb58ce7d144e38", [
(r'''**Stand 13.09.2026.** Dieses Dokument beschreibt das Projekt als Ganzes: warum
''',
 r'''**Stand 13.09.2026, fortgeschrieben 09.10.2026** (Kostenbremse 26.09.,
Umstellung des eigenen Crawls auf ChatGPT ohne Websuche ab 05.10.).
Geänderte Aussagen tragen ihr Datum. Dieses Dokument beschreibt das Projekt als Ganzes: warum
'''),
(r'''| Aktive Engines | 3: Gemini 2.5 Flash, GPT-4o mini, Perplexity Sonar |
| Konfiguriert, aber aus | Claude, Grok, Google AI Overview, Google AI Mode |
''',
 r'''| Aktive Engines | **seit 05.10.2026: 1** — GPT-4o mini ohne Websuche. Bis 29.09.2026 drei: zusätzlich Gemini 2.5 Flash und Perplexity Sonar (abgeschaltet aus Kostengründen, Entscheidung Paul 01.10.) |
| Konfiguriert, aber aus | Gemini, Perplexity (seit 05.10.2026), Claude, Grok, Google AI Overview, Google AI Mode |
'''),
(r'''  was im Netz auffindbar und zitierfähig ist.
''',
 r'''  was im Netz auffindbar und zitierfähig ist. **Seit 05.10.2026 misst diesen
  Kanal nur noch Peec** (Gemini, AI Overview, AI Mode; Perplexity misst Peec
  seit 15.06.2026 nicht mehr). Der eigene Crawl liefert grounded-Werte nur bis
  29.09.2026.
'''),
(r'''| **Eigener GEO-Crawl** | SoV, Zitate, Antworttexte, Seitenänderungen | wöchentlich Mo | `data/geo_snapshot.json`, `sov_history.jsonl` |
''',
 r'''| **Eigener GEO-Crawl** | SoV, Zitate, Antworttexte, Seitenänderungen (seit 05.10.2026 nur noch ChatGPT ohne Websuche; Seiten-Crawl unverändert) | wöchentlich Mo | `data/geo_snapshot.json`, `sov_history.jsonl` |
'''),
(r'''| **Google Reviews (Berater)** | Bewertungen der Vertriebsorganisation | wöchentlich So | `data/berater_reviews.json` |
''',
 r'''| **Google Reviews (Berater)** | Bewertungen der Vertriebsorganisation | monatlich, 1. Sonntag (seit 27.09.2026; vorher wöchentlich) | `data/berater_reviews.json` |
'''),
(r'''im Reiter „LLM-Sichtbarkeit" zwischen beiden Quellen.

''',
 r'''im Reiter „LLM-Sichtbarkeit" zwischen beiden Quellen.

**Seit 05.10.2026 eingeschränkt:** Der eigene Crawl misst nur noch ChatGPT
ohne Websuche, Peec nur noch Kanäle mit Websuche (ChatGPT dort gemischt).
Eine Gegenprobe mit gleicher Methode gibt es für den grounded-Kanal nur für
die Zeit bis 29.09.2026. Plan und Abwägung: `47_PLAN_NUR_PEEC.md`.

'''),
(r'''| `nightly-update.yml` | Alle Sammler, Auswertung, Dashboard-Neubau | geplant 05:30, **fertig real 10:00–11:50** |
''',
 r'''| `nightly-update.yml` | Alle Sammler, Auswertung, Dashboard-Neubau. Marken-Stimmung (`update_sentiment.py`) seit 27.09.2026 nur wöchentlich — seit 04.10. im Montags-Nightly, Sicherheitsnetz ab 7 Tagen Datenalter | geplant 05:30, **fertig real 10:00–11:50** |
'''),
(r'''| `weekly-prices.yml` | Check24-Preise und Bewertungen | montags 05:45 |
| `berater-reviews.yml` | Google Reviews der Berater | sonntags 05:00 |
''',
 r'''| `weekly-prices.yml` | Check24-Preise und Bewertungen | montags 05:45; im Oktober und November täglich 05:45 (Kfz-Wechselsaison, kein bezahlter Dienst) |
| `berater-reviews.yml` | Google Reviews der Berater | startet sonntags 05:00, arbeitet seit 27.09.2026 nur am **ersten Sonntag des Monats** (Sperre im Skript; Handstart immer) |
'''),
(r'''| `analyze.yml` | Der eigentliche Messlauf | **wöchentlich, Montag 23:10** |
''',
 r'''| `analyze.yml` | Der eigentliche Messlauf (seit 05.10.2026 nur ChatGPT ohne Websuche) | **wöchentlich, Montag 23:10**; startet real gegen 02:30–03:00 UTC am Dienstag |
'''),
(r'''## 7 · Der Befundstand
''',
 r'''## 7 · Der Befundstand

> **Hinweis 09.10.2026:** Die Zahlen dieses Kapitels beruhen auf Daten bis
> 13.09.2026 mit drei Engines. Am 05.10.2026 liegt ein Strukturbruch
> (nur noch ChatGPT ohne Websuche im eigenen Crawl); Vergleiche über dieses
> Datum hinweg nur innerhalb der ChatGPT-Reihe. Das Treibermodell lässt das
> Intervall 29.09.→06.10. aus.
'''),
(r'''| **Explorative Versatz-Suche** | Wer acht Zeitversätze testet und den stärksten meldet, findet auch in reinem Rauschen etwas. | Der Block ist als explorativ gekennzeichnet und FDR-korrigiert. |
''',
 r'''| **Explorative Versatz-Suche** | Wer acht Zeitversätze testet und den stärksten meldet, findet auch in reinem Rauschen etwas. | Der Block ist als explorativ gekennzeichnet und FDR-korrigiert. |
| **Nur noch ein Kanal im eigenen Crawl** (seit 05.10.2026) | Mit Websuche misst nur noch Peec; Perplexity misst seither niemand mehr. | Keine methodengleiche Gegenprobe mehr für den grounded-Kanal; Befunde dort hängen an einem Anbieter. |
| **allianz.de sperrt den Seiten-Crawl** (seit 22.09.2026) | Rund 670 Allianz-Adressen antworten aus GitHub Actions nicht; Ursache nicht belegt. | Die Seiten-Erreichbarkeit fällt unter die Schwelle, die Laufampel steht deshalb auf Rot. Die Analysen nutzen die Ampel nicht. Optionen in `48_BEFUNDE_2026-10-09.md`. |
'''),
(r'''| 13.09. | Diese Projektdokumentation und die Übergabe-Datei |
''',
 r'''| 13.09. | Diese Projektdokumentation und die Übergabe-Datei |
| 22.09. | Lauf auf Rot: allianz.de sperrt den Seiten-Crawl (Erreichbarkeit 72,4 %) |
| 25.09. | MCP-Server auf den Cockpit-Daten (v1.0, Review → v1.0.1) |
| 26./27.09. | **Kostenbremse 1** (Entscheidung Paul): Berater-Bewertungen monatlich, Marken-Stimmung wöchentlich |
| 29.09. | Lauf wieder rot; Perplexity 0 Nennungen; Fortschreibungsfehler filtert ERGO heraus (8,83 % statt 13,1 %) |
| 01.10. | **Entscheidung Paul:** Gemini und Perplexity im eigenen Crawl aus, Sichtbarkeit mit Websuche nur noch über Peec, ChatGPT ohne Websuche bleibt |
| 02.10. | Fortschreibungsfehler behoben, Lauf 29.09. nachgerechnet (geo-visibility-tool `eb50be7`) |
| 04.10. | Umstellung live: Config `9090c1d`, Cockpit-Patch `4746421`, Strukturbruch 05.10. registriert |
| 06.10. | Erster Lauf nur mit ChatGPT: ERGO 9,27 % (29.09. ChatGPT allein 9,59 %), Treibermodell und Wächter fehlerfrei |
| 09.10. | Doku fortgeschrieben; Allianz-Sperre und Modell-Abkündigungen geprüft; MCP-Server v1.1 (Lesart „nur ChatGPT seit 05.10."); Voll-Zerlegung pausiert bis drei Messtage nach dem Bruch (`48_BEFUNDE_2026-10-09.md`) |
'''),
(r'''## 13 · Offene Punkte
''',
 r'''## 13 · Offene Punkte

**Stand 09.10.2026** — aktuelle Liste in `48_BEFUNDE_2026-10-09.md`:
allianz.de-Sperre (Optionen liegen bei Paul), Voll-Zerlegung im Treibermodell
pausiert bis voraussichtlich 20.10. (drei Messtage nach dem Bruch), Modellpflege `gpt-5-mini` (Abschaltung
11.12.2026) und `gemini-2.5-flash`, öffentliche Datendateien. MCP-Server v1.1 ist seit 09.10. live. Die Tabelle unten ist der Stand vom 13.09.
und bleibt zur Nachvollziehbarkeit stehen.
'''),
(r'''Dokument.
''',
 r'''Dokument, 46 der Nachtrag ab 25.09. (MCP-Server, Kostenbremse, Umstellung),
47 der Plan „nur Peec", 48 die Befunde vom 09.10. (Allianz-Sperre,
Modell-Abkündigungen).
'''),
]))
PLAN.append(("46_NACHTRAG_2026-09-25.md", "b6e6145031e2d6a72aedcca33c2ac04d154f49c2a60714e178da7895c08e0a40", "028ce4f9a737f01c98890b7ee505a8474c09209bfcf9b80129dbd344671ea262", [
(r'''| Treibermodell | laeuft fehlerfrei, Intervall 29.09.→06.10. als Strukturbruch ausgelassen |
''',
 r'''| Treibermodell | laeuft fehlerfrei, Intervall 29.09.→06.10. als Strukturbruch ausgelassen. **Nachtrag 09.10.:** Die Voll-Zerlegung (`full_joint`) ist seit 05.10. „keine Angabe“ — nach dem Bruch fehlen Messtage (1 von 3). Am 06.10. übersehen; Details `48_BEFUNDE_2026-10-09.md`, Abschnitt 3 |
'''),
(r'''## 9 · Offene Punkte (Stand 06.10.)
''',
 r'''## 9 · Offene Punkte (Stand 06.10.; aktualisiert in 48, Abschnitt 6)
'''),
]))
PLAN.append(("47_PLAN_NUR_PEEC.md", "83dbd71c3d9b181f315408fc2801c7d39c253aa1bb3ceb4d66f54a37d3dbab30", "21cf538b13a029ec98b2a0a6efbb6f605c7ef69b706f645e9edf6ed45e961cf5", [
(r'''**Stand 28.09.2026 (Abschnitt 5 korrigiert) · Entwurf, nicht beschlossen.** Nichts davon ist umgesetzt.
''',
 r'''**Stand 28.09.2026 (Abschnitt 5 korrigiert) · Umgesetzt 04.10.2026 in einer
schärferen Form als C-light** (Nachtrag 09.10., Entscheidung Paul 01.10.):

| Engine | Eigener Crawl ab 05.10.2026 |
|---|---|
| Gemini (grounded) | **aus** — Peec misst Gemini, AI Overview, AI Mode |
| Perplexity (grounded) | **aus** — aus Kostengründen, obwohl Peec Perplexity nicht misst. Perplexity wird damit von niemandem mehr gemessen. |
| GPT-4o mini ohne Websuche | **bleibt** |

Seiten-, Preis-, Presse- und alle übrigen Crawls laufen unverändert. Umsetzung
und erster Lauf (06.10.): `46_NACHTRAG_2026-09-25.md`, Abschnitt 8. Der Text
unten ist der Planungsstand vom 28.09. und bleibt zur Nachvollziehbarkeit
stehen.
'''),
(r'''A so lassen · C-light · C vollständig — Paul entscheidet.
''',
 r'''A so lassen · C-light · C vollständig — Paul entscheidet.

**Entschieden 01.10.2026:** C-light ohne Perplexity (siehe Kopf).
'''),
]))
PLAN.append(("README.md", "a43815d55b955d250dbc6d2f49193281a8b2695a5e5511604089d8edd65e47a1", "5d1a4e1879db00eb19e4727bf854d3466d9dddf3e622b8fe2ceb95dda6e70aae", [
(r'''| **[45_PROJEKTDOKUMENTATION.md](45_PROJEKTDOKUMENTATION.md)** | **Der Einstieg.** Auftrag, Aufbau, Datenquellen, Auswertung, Befunde, Grenzen, Glossar, Dateiverzeichnis |
''',
 r'''| **[45_PROJEKTDOKUMENTATION.md](45_PROJEKTDOKUMENTATION.md)** | **Der Einstieg.** Auftrag, Aufbau, Datenquellen, Auswertung, Befunde, Grenzen, Glossar, Dateiverzeichnis |
| [48_BEFUNDE_2026-10-09.md](48_BEFUNDE_2026-10-09.md) | Neuester Stand (09.10.2026): Sperre durch allianz.de mit Optionen, Abkündigungen der genutzten KI-Modelle, offene Punkte |
| [46_NACHTRAG_2026-09-25.md](46_NACHTRAG_2026-09-25.md) | Nachtrag ab 25.09.: MCP-Server, Kostenbremse, Umstellung des eigenen Crawls auf ChatGPT ohne Websuche |
| [47_PLAN_NUR_PEEC.md](47_PLAN_NUR_PEEC.md) | Plan und Abwägung „Sichtbarkeit mit Websuche nur über Peec" (umgesetzt 04.10.2026) |
'''),
(r'''| `nightly-update.yml` — Sammler, Auswertung, Dashboard-Neubau | täglich 05:30 (real ~06:29) |
''',
 r'''| `nightly-update.yml` — Sammler, Auswertung, Dashboard-Neubau | täglich 05:30 (fertig real 10:00–12:50); Marken-Stimmung nur montags |
'''),
(r'''| `weekly-prices.yml` — Check24 | montags 05:45 |
| `analyze.yml` (Repo `geo-visibility-tool`) — **der eigentliche Messlauf** | montags 23:10 |
''',
 r'''| `weekly-prices.yml` — Check24 | montags 05:45; Oktober/November täglich |
| `berater-reviews.yml` — Google Reviews der Berater | erster Sonntag im Monat 05:00 (seit 27.09.2026) |
| `analyze.yml` (Repo `geo-visibility-tool`) — **der eigentliche Messlauf**, seit 05.10.2026 nur ChatGPT ohne Websuche | montags 23:10 (Start real ~02:30 Di) |
'''),
(r'''Messung dahinter nicht. Und der Deploy löst nicht automatisch aus — nach jeder
''',
 r'''Messung dahinter nicht. Sichtbarkeit **mit** Websuche misst seit 05.10.2026
nur noch Peec. Und der Deploy löst nicht automatisch aus — nach jeder
'''),
]))
NEU_48 = r'''# 48 — Befunde 09.10.2026 (Abendrunde)

Vier Punkte: Sperre durch allianz.de, Abkündigungen der genutzten KI-Modelle,
eine Folge der Umstellung im Treibermodell, MCP-Server v1.1.
Vorgeschichte: `46_NACHTRAG_2026-09-25.md` (Abschnitte 7–9), `47_PLAN_NUR_PEEC.md`.

---

## 1 · allianz.de sperrt den Seiten-Crawl — Befund und Optionen

**Nichts geändert.** Paul entscheidet.

### Was belegt ist

| Prüfung | Ergebnis |
|---|---|
| Gesperrte Adressen (`data/blocked_urls.json`) | 1.201 insgesamt, davon **671 www.allianz.de** (danach lv1871.de 129, diebayerische.de 106) |
| Fehlversuche | 669 Allianz-Adressen mit 2 Fehlschlägen: zuerst am 22.09., erneut am 29.09. Im Protokoll vom 29.09. stehen 578 FlareSolverr-Fehler „challenge timeout“ |
| Nächster automatischer Versuch | Sperrfrist nach 2 Fehlschlägen 14 Tage, Zeitstempel 29.09. 03:02 UTC → frei ab **13.10. 03:02 UTC**. Der Seitenteil des Laufs beginnt rund 50 Minuten nach Laufstart (06.10.: Start 02:54), der Lauf am 13.10. versucht es also erneut. Scheitert er, folgen 28 Tage Sperre (nächster Versuch ≈ 10.11.) |
| Gegenprobe aus diesem Arbeitsbereich (US-Rechenzentrum, 1 Abruf/s) | 25 gesperrte Adressen abgerufen: **24 × HTTP 200**, 1 × 404 |
| Lauf 06.10. | 680 Adressen übersprungen, Erreichbarkeit 70,8 %, Ampel rot (Score 86) |
| Wirkung auf die Auswertung | keine — die Analysen nutzen die Ampel nicht (`baseline_eligible` wird im Cockpit nicht gelesen). Betroffen sind Ampel-Anzeige und Seitenänderungs-Ereignisse der Allianz |

**Nicht belegt:** die Ursache. Dass dieselben Seiten von hier antworten, spricht
für eine Sperre, die an GitHub-Actions-Adressen oder an der Abrufmenge hängt.
Geprüft ist das nicht.

Allianz-Adressen nach erstem Pfadteil: business 164, recht-und-eigentum 136,
vorsorge 131, gesundheit 100, ansprechpartner-vor-ort 64, presse 30, Rest kleiner.

### Optionen

| | Was | Aufwand | Kosten | Haken |
|---|---|---|---|---|
| **A** | Abwarten: Versuch am 13.10. abwarten | keiner | 0 € | bleibt die Sperre, ist die Ampel bis mindestens 10.11. rot |
| **B** | Allianz langsamer abrufen und/oder weniger Adressen (z. B. ohne Agentur- und Presseseiten, −94) | klein, Code im GEO-Repo | 0 € | Wirkung ungewiss, solange die Ursache unbekannt ist |
| **C** | Bezahlter Abrufdienst für allianz.de | klein | laufend | widerspricht der Kostenbremse |
| **D** | Allianz von Pauls Rechner abrufen (Cowork-Aufgabe), Ergebnis ins Repo | mittel | 0 € | hängt am eingeschalteten Rechner, wie der Peec-Export |
| **E** | Allianz aus der Erreichbarkeits-Quote der Ampel herausnehmen und das offen ausweisen | klein | 0 € | Allianz-Seitenänderungen fehlen weiter, nur ehrlicher beschriftet |

**Empfehlung:** A bis zum Lauf am 13.10., danach E, falls die Sperre bleibt.
B nur zusammen mit E, weil B allein die Ursache rät.

---

## 2 · Abkündigungen der genutzten KI-Modelle

Quellen: offizielle Abkündigungsseiten von OpenAI und Google (Stand 09.10.2026).

| Modell | Wo im Projekt | Stand | Handlungsbedarf |
|---|---|---|---|
| `gpt-4o-mini` | GEO-Messung (ChatGPT ohne Websuche), Why-Analyse, Klassifikation „ERGO fehlt“, Cockpit `fetch_search_ab` | **nicht** auf der Abkündigungsliste | keiner |
| `gpt-5-mini-2025-08-07` | GEO-A/B-Test `chatgpt_web` (nur Handstart), BK-Monatsmessung | **Abschaltung 11.12.2026**, Ersatz laut OpenAI `gpt-5.6-terra` | vor dem 11.12. umstellen — der Messlauf selbst ist nicht betroffen |
| `gemini-2.5-flash` | GEO `diff_classifier` (Seitenänderungen), BK-Monatsmessung | kein Abschaltdatum, laut Google „not deprecated“; seit 18.09.2026 nur noch für Bestandsnutzer | beobachten; ein GitHub-Issue nennt den 20.10., das ist **nicht offiziell** |
| `gemini-flash-latest` | Marken-Stimmung, Bewertungs-Themen, Übersetzung der Peec-Maßnahmen, Ratings-Recherche | Alias, zeigt seit 19.05.2026 auf **gemini-3.5-flash** | siehe Kostenhebel |
| `gpt-4o-mini-search-preview` | früher A/B-Test | abgeschaltet 23.07.2026 | erledigt (am 30.09. ersetzt) |

**Kostenhebel (Entscheidung Paul):** Der Alias `gemini-flash-latest` ist mit
der Umstellung auf 3.5 Flash teurer geworden (1,50 $ / 9,00 $ je Million Ein-/
Ausgabetokens). Alternativen: 3.5 Flash-Lite 0,30 $ / 2,50 $; 3.8 Flash
0,75 $ / 3,75 $ bis 31.12.2026, danach 1,50 $ / 7,50 $. Ein fester Modellname
statt Alias würde außerdem stille Modellwechsel verhindern. Die Stimmung läuft
seit 27.09. nur noch wöchentlich — der Betrag ist also klein. Die Qualität von
Flash-Lite für diese Aufgaben ist nicht getestet.

---

## 3 · Folge der Umstellung: Voll-Zerlegung im Treibermodell pausiert

Beim Test des MCP-Servers aufgefallen, am 06.10. von mir übersehen.

| Baustein (`correlation_impact.json`) | bis 03.10. | seit 05.10. | Grund |
|---|---|---|---|
| Voll-Zerlegung `full_joint` (alle Kanäle) | berechnet | **keine Angabe** | Nach dem Strukturbruch 05.10. zählen nur Messtage ab dem Bruch; nötig sind 3, vorhanden 1 (06.10.) |
| grounded-Teile (`price_model`, `structure_summary`, `price_footprint_joint`) | berechnet | keine Angabe | eigener Crawl hat keinen grounded-Kanal mehr — gewollte Folge |
| Gegenprobe eigener Crawl ↔ Peec (`cross_source_validation`) | berechnet | keine Angabe | braucht eigenes Gemini — gewollte Folge |
| ungrounded/combined in Preis- und Strukturmodell | berechnet | **berechnet** | — |

Das ist so gebaut („keine Daten ist kein Befund“), kein Fehler in den Zahlen.
Übersicht und Empfehlungen zeigen die Zerlegungs-Karten dann nicht an (im Code
geprüft); der Korrelations-Reiter ist nicht gesondert im Browser geprüft. Die Voll-Zerlegung kommt
**von selbst zurück**, sobald drei Messtage nach dem Bruch vorliegen: Läufe
13.10. und 20.10., also mit dem Nightly am 20.10. — wenn beide Läufe gelingen.

**Option (nicht umgesetzt):** Der Bruch gilt heute für alle Kanäle. Die
ChatGPT-Reihe läuft aber über den 05.10. unverändert weiter. Man könnte den
Bruch auf grounded und combined beschränken; dann wäre die ungrounded-Zerlegung
sofort wieder da. Das ändert die Auswertung — Paul entscheidet.

---

## 4 · MCP-Server v1.1 (ausgerollt am Abend des 09.10.)

| Änderung | Warum |
|---|---|
| Lesart nennt: seit 05.10. nur ChatGPT ohne Websuche, grounded nur bis 29.09., mit Websuche misst nur Peec, Gesamtwerte über den 05.10. nicht vergleichbar | jede Antwort gibt das weiter |
| Kanal-Zeile in `geo_sichtbarkeit`, `geo_themen`, `geo_datenstand` | aus der Engine-Liste des Laufs, nicht fest |
| `geo_verlauf` mit gemini/perplexity: Hinweis „nicht mehr abgefragt, letzte Messung 29.09.“ | sonst wirkt die Reihe wie abgebrochen |
| `geo_themen`: „über die eine Engine (chatgpt)“ statt fest „drei Engines“ | stimmte nicht mehr |
| `geo_treiber`: nennt je Kanal den Grund, wenn keine Effekte rechenbar sind | eine leere Tabelle sähe aus wie „kein Effekt“ (siehe 3) |

Tests: 43/43 gegen die Live-Daten, 9/9 gegen den ausgerollten Worker
(Version `a05505e5`). Quellen und Paket: Ordner „ERGO Content Analyse“ › `mcp`
(`ergo-geo-mcp-server-1.1.0.tar.gz`, 1.0.x im Unterordner `archiv`).

---

## 5 · Dokumentation fortgeschrieben

`45_PROJEKTDOKUMENTATION.md` (Engines, Kanäle, Datenquellen, Workflow-Takte,
Hinweis Befundstand, Grenzen, Chronik bis 09.10., offene Punkte),
`README.md` (Dokumentliste, Takte), `47_PLAN_NUR_PEEC.md` (als umgesetzt
markiert, mit Perplexity aus).

## 6 · Offene Punkte (Stand 09.10.)

| Punkt | Nächster Schritt | Wer |
|---|---|---|
| allianz.de-Sperre | Lauf 13.10. prüfen, dann A/E entscheiden | Claude prüft, Paul entscheidet |
| Voll-Zerlegung zurück? | Nightly 20.10. prüfen; Option „Bruch nur grounded“ | Claude prüft, Paul entscheidet |
| `gpt-5-mini-2025-08-07` | vor 11.12.2026 ersetzen (A/B-Test, BK-Monatsmessung) | Claude, Termin Ende November |
| `gemini-flash-latest` → festes Modell? | Kostenhebel, siehe 2 | Paul |
| Öffentliche Datendateien | Entscheidung offen (46, Abschnitt 3) | Paul |
'''

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
f48 = "48_BEFUNDE_2026-10-09.md"
if not (os.path.exists(f48) and open(f48, encoding="utf-8").read() == NEU_48):
    open(f48, "w", encoding="utf-8", newline="\n").write(NEU_48); print("neu", f48)

