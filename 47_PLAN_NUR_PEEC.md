# 47 — Plan: Sichtbarkeit nur noch über Peec (Option C)

**Stand 28.09.2026 (Abschnitt 5 korrigiert) · Umgesetzt 04.10.2026 in einer
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

## Kernaussage

C ist machbar, aber **kein Kostenhebel**, sondern ein Vereinfachungshebel.
Die eigenen Modellaufrufe kosten zweistellige Dollarbeträge im Monat.
Dafür verlieren wir drei Dinge, die Peec in unserem Vertrag nicht liefert:
den **ungegroundeten Kanal** (ChatGPT ohne Websuche), **Perplexity** und die
**Gewerbe-Themen**. Deshalb gibt es unten eine Variante C-light.

---

## 1 · Was wegfällt und was es spart

| | Eigener Crawl heute | Peec heute |
|---|---|---|
| Fragen | 383 | 528 (396 neutral, 132 markenbezogen) |
| Engines | Gemini 2.5 Flash, GPT-4o mini (ohne Websuche), Perplexity Sonar | ChatGPT (Oberfläche, gemischt), Gemini, AI Overview, AI Mode |
| Perplexity | ja | **nein** — Daten nur bis Woche 15.06.2026 |
| Ungegroundeter Kanal | ja (GPT-4o mini) | **nein** — ChatGPT ist „ui_mixed" |
| Marken | 8 | 30 |
| Themen | 13, darunter Betriebshaftpflicht, Firmenrechtsschutz (SOHO) | 13, darunter Corporate, Wohngebäude — **keine Gewerbe-Themen** |
| Antworttexte, Why-Analyse | ja | nicht in unseren Exporten |
| Zitate | je Antwort, vollständig | Top 1.500 URLs, rollierendes 30-Tage-Fenster |
| Taktung | wöchentlich | täglich |
| Historie | ab 14.05.2026 | wöchentlich ab 13.04.2026 |

**Ersparnis:** Perplexity rund 2,30 $ je Lauf (383 Anfragen, Tokens aus dem
Lauf vom 22.09. × Listenpreis), also 10–14 $ im Monat. Gemini und GPT-4o mini
kommen dazu; genaue Zahlen stehen auf den Google- und OpenAI-Rechnungen.
Größenordnung zusammen: zweistellig im Monat, nicht dreistellig.

**Kostet eventuell zusätzlich:** Perplexity bei Peec wieder einschalten ist
ein Zusatzmodell mit Aufpreis. Der Preis steht im Peec-Konto, nicht öffentlich.

## 2 · Was im Cockpit am eigenen Crawl hängt

- **Skripte:** `update_snapshot`, `sov_history`, `correlation_impact`
  (Treibermodell), `intervention_analysis`, `pipeline_health`,
  `archive_level_cells`, `geo_faktenblatt`
- **Dashboard-Module:** `geo_wirkung`, `citation_channels`, `footprint_chart`,
  `korrelation_upgrade`, `health_banner`, `geo_doku_tab`, `soho_tab`
- **MCP-Server:** alle fünf Werkzeuge lesen `geo_snapshot.json`,
  `sov_history.jsonl` oder `correlation_impact.json`

Der Seiten- und Sitemap-Crawl (Wettbewerber-Webseiten, Seitenänderungen)
nutzt keine bezahlten Dienste und kann **unabhängig weiterlaufen**.

## 3 · Ablauf

| Phase | Was | Wer | Dauer |
|---|---|---|---|
| 0 · Klären | Peec-Tarif, Aufpreis für Perplexity, Vertragslaufzeit; ist Peec als einzige Quelle bei ERGO in Ordnung? | Paul | 1 Tag |
| 1 · Parallel messen | 4 Wochen beide Quellen, Brücke je Thema und Engine rechnen, Bruchdatum festlegen | Claude | 4 Wochen, läuft nebenher |
| 2 · Umbauen | Treibermodell auf Peec-Zellen und -Quellen; Wächter auf Peec-Prüfungen; alte GEO-Zeitreihe mit Enddatum einfrieren; Module umstellen oder „Messung eingestellt seit …" zeigen; MCP-Server v1.1 | Claude | 2–3 Arbeitssitzungen |
| 3 · Abschalten | Modellaufrufe in `config.json` aus, Seiten-Crawl bleibt; Perplexity-Guthaben nicht mehr aufladen | Claude, Paul nur Guthaben | 1 Lauf |
| 4 · Nachkontrolle | 2 Wochen: Wächter grün, keine Lücken, Doku | Claude | 2 Wochen |

## 4 · Risiken

1. **Abhängigkeit von einem Anbieter.** Fällt Peec aus oder ändert die
   Methode, gibt es keine Gegenprobe mehr (heute Kapitel 4.1 der Doku).
2. **Wochen-Export auf Pauls Rechner.** Der Montags-Export läuft als
   Cowork-Aufgabe mit persönlichem Token; ist der Rechner aus, fehlt die Woche.
3. **Rollierendes Zitat-Fenster.** Verpasste Tage lassen sich nicht nachholen.
4. **Strukturbruch.** Der Wechsel ist der siebte dokumentierte Bruch; Vergleiche
   über das Datum hinweg nur mit Brücke.

## 5 · Variante C-light (Empfehlung, korrigiert 28.09.)

**Korrektur:** Die erste Fassung schaltete Gemini **und** Perplexity im eigenen
Crawl ab. Weil Peec Perplexity seit Juni nicht mehr misst, wäre Perplexity damit
ganz verschwunden. Richtig ist: nur abschalten, was Peec doppelt misst.

| Engine | Eigener Crawl | Peec | C-light |
|---|---|---|---|
| Gemini (grounded) | ja | ja | **aus** — Peec übernimmt |
| GPT-4o mini ohne Websuche | ja | nein | **bleibt** |
| Perplexity (grounded) | ja | nein (seit Juni) | **bleibt** |

- spart die Engine mit dem größten Verbrauch (Gemini, 613.000 Ausgabetokens je Lauf)
- behält die Zwei-Kanal-Logik, Perplexity und die SOHO-Themen
- Teil-Gegenprobe bleibt: eigenes ChatGPT gegen Peec-ChatGPT; die
  Gemini-Gegenprobe gibt es danach nur noch für die Zeit bis zur Umstellung
- Umbau kleiner: grounded-Anteil im Treibermodell rechnet dann auf Perplexity
  plus Peec-Gemini; Strukturbruch am Umstellungsdatum eintragen

**Alternative:** Perplexity bei Peec wieder zubuchen und im eigenen Crawl
abschalten. Lohnt nur, wenn der Peec-Aufpreis unter rund 10–14 $ im Monat
liegt — das kostet Perplexity im eigenen Crawl.

## 6 · Entscheidung

A so lassen · C-light · C vollständig — Paul entscheidet.

**Entschieden 01.10.2026:** C-light ohne Perplexity (siehe Kopf).
