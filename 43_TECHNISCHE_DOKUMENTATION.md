# 43 — Technische Dokumentation des ERGO LLM-Sichtbarkeits-Projekts

**Stand 18.08.2026.** Diese Datei beschreibt das Gesamtsystem so, dass zwei
verschiedene Leser damit arbeiten können: Paul, der wissen muss, was gemessen
wird, was das Cockpit behaupten darf und wo die Grenzen liegen — und ein
Entwickler, der das System nach einer Übergabe weiterbauen soll, ohne die
Entscheidungen der letzten vier Monate neu erfinden zu müssen.

Sie ersetzt keine der bestehenden Berichte, sondern bindet sie zusammen. Die
Berichtsreihe (31 bis 42) ist die Chronik einzelner Prüfungen und Umbauten;
diese Datei ist der Querschnitt. Wo eine Entscheidung ein Datum hat, steht das
Datum dabei — das ist im Projekt Konvention und kein Schmuck: Fast jeder Fehler,
der hier Tage gekostet hat, war ein Satz, der einmal richtig war und dann still
falsch wurde.

---

## 1 · Was das System misst und wozu

Die Ausgangsfrage ist einfach zu stellen und schwer zu messen: **Wenn ein Mensch
ein Sprachmodell nach einer Versicherung fragt — kommt ERGO vor?** Nicht, ob
ERGO auf Google rankt, sondern ob ChatGPT, Gemini oder Perplexity ERGO in der
Antwort nennen, an welcher Stelle, und ob sie dabei eine ERGO-Seite als Quelle
zitieren.

Daraus werden drei Kennzahlen gebaut, die im ganzen System durchgängig benutzt
werden:

- **Share of Voice (SoV)** — der Anteil der Nennungen einer Marke an allen
  gezählten Markennennungen. Ein Anteil, kein Absolutwert: Wächst der Nenner
  (mehr Wettbewerber in der Zählung), fällt der Wert jeder Marke, ohne dass
  sich real etwas geändert hätte. Genau daran hängen zwei der drei registrierten
  Strukturbrüche (Abschnitt 4.2).
- **Zitatanteil** — der Anteil der markeneigenen Domains an den Quellen, die die
  Modelle in ihren Antworten verlinken. Diese Größe liegt in der Wirkungskette
  eine Stufe **früher** als der SoV und ist deshalb seit dem 18.08.2026 eigene
  Zielgröße (Hebel 6 aus Bericht 42).
- **Rang / Position** — an welcher Stelle einer Aufzählung eine Marke steht.

Der Zweck ist nicht Berichterstattung, sondern **Treiber-Analyse**: Welche
Maßnahme bewegt diese Zahlen? Deshalb sammelt das System parallel zu den
Messwerten datierte Ereignisse (Pressemitteilungen, News, Seitenänderungen,
Bewertungen, Preisänderungen, seit dem 18.08. auch LinkedIn-Posts) und rechnet
sie gegen die Sichtbarkeit.

Es gibt **zwei unabhängige Messquellen**, und das ist Absicht:

1. **Der eigene Crawl** (`geo-visibility-tool`): 13 Versicherungsprodukte, je
   rund 30 realistische Nutzerfragen, an drei aktive Modelle geschickt, die
   Antworten ausgewertet. Vollständig unter eigener Kontrolle, methodisch
   nachvollziehbar, aber auf die eigenen Prompts beschränkt.
2. **Der Peec-Export**: das kommerzielle Werkzeug peec.ai misst dasselbe Feld
   mit eigenem Prompt-Satz, eigenen Engines (inkl. Google AI Overview/AI Mode
   per UI-Scraping) und eigener Quellen-Auswertung.

Beide zusammen erlauben den einzigen zirkularitätsfreien Test, den das Projekt
hat: Treiber aus der einen Quelle, Zielgröße aus der anderen
(`_cross_source_check`, Abschnitt 4.6). Alle Einzelquellen-Belege für den
Zusammenhang „Quellpräsenz → Sichtbarkeit" sind zu einem unbekannten Teil
Messartefakt, weil Zitate und Nennungen aus demselben Antworttext stammen.

Ein Hinweis zur Peec-Zahl selbst, der in jeder Auswertung mitgeführt wird: Peecs
Projekt „ERGO Germany" ist **nicht neutral**. 132 von 614 Prompts nennen ERGO
ausdrücklich im Fragetext, kein einziger einen Wettbewerber. Deshalb steht ERGO
bei Peec auf Platz 1 (~23 % SoV), während der neutrale eigene Crawl Allianz und
HUK-Coburg vorn sieht (ERGO ~7 %). `scripts/build_peec_neutral_sov.py` zerlegt
das in `overall_sov` und `neutral_sov` — nur Prompts ohne Markennamen im Text.

---

## 2 · Architektur in Worten

### 2.1 Die beiden Repositories

**`phoeser/geo-visibility-tool`** (Arbeitskopie: `/tmp/geo`) ist die
**Messstation**. Ein Python-Paket `analyzer/` befragt die Sprachmodelle, wertet
die Antworten aus, verfolgt außerdem die Produktseiten von ERGO und den
Wettbewerbern (Snapshots, Diffs, Klassifikation der Änderungsart) und schreibt
alles als Lauf-Datei nach `data/runs/<Zeitstempel>.json` plus eine Kopie als
`data/runs/latest.json`. Ein Lauf dauert inzwischen 4 bis 4,5 Stunden; aktuell
liegen 137 Läufe im Repo. Das Repo ist öffentlich — das ist ausgenutzt, weil
`raw.githubusercontent.com` dadurch ohne Token und ohne Größenlimit erreichbar
ist (Bericht 32).

**`phoeser/LLM-Cockpit`** (Arbeitskopie: `/tmp/n1`) ist die **Auswertung und die
Auslieferung**. Es holt den GEO-Stand ab, sammelt eigene Datenquellen (Presse,
Bewertungen, Ratings, Preise, Domain-Footprint, LinkedIn), führt den
Peec-Export, rechnet das komplette statistische Modell und baut daraus die
passwortgeschützte GitHub-Pages-Seite. Auch dieses Repo ist öffentlich; die
README begründet das damit, dass GitHub Pages für private Repos eine
Pro-Lizenz verlangt und stattdessen der Inhalt verschlüsselt wird.

### 2.2 Die Workflows und ihr Takt

| Workflow | Repo | Takt (UTC) | Was er tut |
|---|---|---|---|
| `analyze.yml` — „Analyze Visibility" | GEO | Mo 23:10, wöchentlich | Der komplette Crawl: LLM-Abfragen, Seiten-Tracking, Impact-Analyse, Korrelation |
| `peec-daily-sources.yml` | Cockpit | täglich 04:00 | Peec-Quellenreport + versionierter Tagessnapshot |
| `nightly-update.yml` — „Nightly Dashboard Update" | Cockpit | täglich 05:30 | Alles andere: Snapshot holen, eigene Crawler, Modellrechnung, Faktenblatt, Bauen und Ausliefern |
| `pipeline-waechter.yml` | Cockpit | täglich 09:00 | Wächter *neben* der Pipeline (siehe 7.4) |
| `weekly-prices.yml` | Cockpit | Mo 05:45 (Okt/Nov zusätzlich täglich) | Check24-Preise |
| `berater-reviews.yml` | Cockpit | So 05:00 | Google-Reviews der Berater-Stichprobe |
| `monthly-urls.yml` | Cockpit | 1. des Monats 06:45 | Anbieter-Sitemaps |
| `monthly-ratings-research.yml` | Cockpit | 1. des Monats 02:00 | Test-/Rating-Recherche |
| `dashboard-deploy.yml`, `georg-sync.yml`, `berater-update.yml` | Cockpit | nur manuell | Einzelschritte ohne vollen Nightly |
| `backfill.yml`, `revert-backfill.yml`, `search-ab-test.yml` | GEO | nur manuell | Nachrechnungen und das A/B-Experiment |

**Der Peec-Wochenexport ist kein Workflow.** Er läuft montags 07:07 als
geplanter Cowork-Task auf Pauls Rechner und produziert Zellen, Footprint,
Nordstern und Segmente. Grund: Peecs persönliche Zugangsschlüssel sind auf der
REST-API gesperrt („Personal API keys are not supported on this API yet"), nur
der MCP-Server akzeptiert sie — und der Token gehört Paul persönlich und darf
nicht als GitHub-Secret liegen. Dasselbe gilt für
`scripts/export_peec_actions.py` (die Peec-Empfehlungen).
`scripts/export_peec_sources.py` ist die Ausnahme: Für den Tagesabruf gibt es
inzwischen das Repository-Secret `PEEC_TOKEN`, deshalb läuft **nur dieser eine**
Export in Actions.

**Die Reihenfolge ist bewusst gewählt und trotzdem nicht garantiert.** Der
GEO-Crawl startet Montag 23:10 und braucht 4 bis 4,5 Stunden; der Nightly startet
05:30, also mit Absicht danach. Am 05.08.2026 hat der GEO-Lauf erst um 04:44
gepusht, der Nightly lief zu diesem Zeitpunkt schon 14 Minuten und rechnete auf
dem Vortagsstand — Lauf #475 hat daraufhin gar nichts committet. Deshalb wurde
der Nightly von 04:30 auf 05:30 gezogen. GitHub verzögert geplante Läufe im
Free-Tier aber typisch um Stunden; die Verschiebung macht die Reihenfolge
**wahrscheinlicher, nicht sicher**. Der robuste Weg wäre, dass der GEO-Lauf den
Nightly am Ende selbst anstößt. Das steht als offener Punkt im Kommentarkopf von
`nightly-update.yml`.

### 2.3 Wer schreibt, wer liest — und der Weg über die Repo-Grenze

Alle schreibenden Cockpit-Workflows teilen sich die concurrency-Gruppe
`repo-writes`, damit sie sich nicht gegenseitig den Push wegschießen. Im
GEO-Repo gilt dasselbe; `analyze.yml` war bis zum 15.08.2026 der einzige
schreibende Workflow **ohne** Gruppe — ein manuell gestarteter Backfill hätte
dem Wochenlauf per `force-with-lease` den Push überschreiben können.

Über die Repo-Grenze läuft der Datenverkehr in beide Richtungen, jeweils
lesend, jeweils mit einem eigenen Token:

- **Cockpit → GEO:** Secret `GEO_REPRO_TOKEN`. Damit holen
  `update_snapshot.py` (die Lauf-Datei), `merge_geo_page_events.py` (die
  Seiten-Ereignisse), `fetch_search_ab.py` (die A/B-Aggregate) und
  `content_citations.py` (die Rohantworten für die Zitat-Auswertung) ihre Daten
  über die GitHub-API. Der Name ist ein Tippfehler aus der Frühzeit
  (`GEO_REPRO_` statt `GEO_REPO_`) und wird nicht mehr korrigiert, weil er in
  mehreren Workflows steht.
- **GEO → Cockpit:** Secret `COCKPIT_REPO_TOKEN`. Der Crawl-Workflow lädt
  `shared/events.jsonl` aus dem Cockpit nach `data/cockpit_events.jsonl`, damit
  die GEO-seitige Unified-Korrelation die Ereignisse kennt. Fehlt der Token,
  rechnet der Lauf nur mit den eigenen Page-Events weiter und sagt das im
  Protokoll — er scheitert nicht.

Ein Detail mit Geschichte: Der Schritt „SoV-Historie + Korrelationsanalyse" im
Nightly bekam das Token erst am 12.08.2026. Vorher lief `content_citations.py`
über die **unauthentifizierte** GitHub-API — das funktioniert für ein
öffentliches Repo, aber mit 60 Anfragen pro Stunde je Runner-IP, geteilt mit
allen anderen GitHub-Nutzern dieser IP. Fiel das um, meldete das Skript
`eigener_crawl available=false`, rechnete stillschweigend ohne den halben
Datenbestand weiter (ERGO-Zitattrefferquote 5,0 % → 2,1 %), und
`continue-on-error` färbte den Lauf trotzdem grün.

---

## 3 · Datenflüsse

### 3.1 Der Weg einer Zahl vom Modell bis in den Reiter

Ein SoV-Wert legt folgenden Weg zurück:

1. **Frage stellen.** `analyzer/main.py` schickt die ~30 Prompts eines Produkts
   an die aktiven Engines (`data/prompts/<produkt>.json`,
   `runs_per_prompt: 1`, `temperature: 0.3`, `max_tokens: 1200`, 5 parallele
   Anfragen, 3 Wiederholversuche).
2. **Antwort auswerten.** `analyzer/metrics.py` zählt Markennennungen über
   Alias-Muster und liest die zitierten Quellen. Domain-Aliase (`ergo.de`)
   zählen seit dem 21.07.2026 **nicht mehr** als Textnennung — eine zitierte URL
   war vorher zusätzlich eine Nennung, das waren 15,2 % aller Nennungen.
3. **Lauf schreiben.** `data/runs/<Zeitstempel>.json` + `latest.json`, plus
   Seiten-Snapshots und Page-Events, und alles per Commit zurück ins GEO-Repo.
4. **Abholen.** `scripts/update_snapshot.py` zieht `latest.json` (inzwischen über
   30 MB) und legt sie als `data/geo_snapshot.json` ab, den Vorstand als
   `.previous.json` daneben. Der Download prüft Content-Length und wiederholt —
   am 13.08.2026 kam real eine `IncompleteRead` über 29.991.360 von 30.498.071
   Bytes; ohne Prüfung wäre das ein Parserfehler geworden und der Nightly hätte
   grün auf dem Vortagsstand weitergerechnet.
5. **Verdichten.** `scripts/sov_history.py` schreibt bei **jedem** Lauf den
   aktuellen Stand je Marke nach `data/sov_history.jsonl` — auch wenn sich nichts
   geändert hat, denn sonst gäbe es keine dichte Messreihe, sondern nur
   Änderungspunkte. Ein Eintrag je (Tag, Marke), idempotent.
6. **Rechnen.** `scripts/correlation_impact.py` liest die Reihe, die Ereignisse,
   die Preis- und Level-Zellen sowie die Peec-Dateien und schreibt **eine**
   Ergebnisdatei: `data/correlation_impact.json` (828 KB, aktuell 63 Messtage
   vom 14.05. bis 18.08., 682 Intervalle).
7. **Anzeigen.** Die Dashboard-Module holen diese Datei zur Laufzeit per
   `fetch()` und rendern daraus die Reiter.

Parallel dazu läuft der Peec-Strang: Der Wochen-Task erzeugt `peec_cells.csv`,
`peec_footprint.json`, `peec_nordstern.json`, `peec_segments.json` und die
Historien-CSVs; der Tages-Workflow erzeugt `peec_sources.json` und legt eine
versionierte Kopie in `data/peec_snapshots/` (aktuell 16 Quellen-Snapshots).
Warum die Snapshots: Peec liefert immer nur eine **Momentaufnahme über ein
rollierendes 30-Tage-Fenster** — einen Verlauf gibt es ausschließlich über
archivierte Stände. Beim wöchentlichen Abruf entstanden nur rund vier
Stützstellen, auf denen `citation_target_analysis` rechnen musste.

### 3.2 Die Event-Pipeline

`shared/event_emitter.py` ist das gemeinsame Nadelöhr: Jeder Crawler ruft
`emit_event()` auf, und die Funktion hängt eine Zeile an `shared/events.jsonl`
an. Die Datei wird **nie** geleert — sie ist die wachsende Chronik des Projekts
und liegt inzwischen bei 27.646 Zeilen / 16 MB.

Ein Event hat immer dieselbe Form: ID, Zeitstempel, Typ, Marke, Produkt
(optional), Quelle, erzeugendes Skript, `magnitude` (auf 0,0–2,0 begrenzt) und
einen typspezifischen `detail`-Block. Die ID enthält seit dem 12.06.2026 auch
die Uhrzeit — vorher kollidierten IDs deterministisch bei einem zweiten Lauf am
selben Tag.

**Die Typen und ihr heutiger Bestand:**

| Typ | Anzahl | Herkunft |
|---|---|---|
| `sov_change` | 8.893 | Sichtbarkeitsänderung (die Zielgröße selbst, kein Treiber) |
| `page_change` | 7.986 | GEO-Page-Tracker, importiert über `merge_geo_page_events.py` |
| `page_new` | 7.605 | dito — Erstsichtung einer URL |
| `news_mention` | 1.977 | `update_press.py`, Google-News-RSS |
| `press_mention` | 789 | dito, Pressemitteilungen |
| `review_change` / `review_volume` | 97 / 77 | `update_sentiment.py`, vier Bewertungsquellen |
| `linkedin_post` | 76 | **neu 18.08.2026**, `update_linkedin.py` |
| `domain_change` | 82 | `update_domain_footprint.py` |
| `price_change` / `price_announcement` | 22 / 7 | `update_prices.py` / `update_press.py` |
| `page_removed` | 21 | Löschungserkennung im GEO-Crawl |
| `portal_rank_change`, `wikipedia_change`, `rating_status_change` | 9 / 5 / 0 | `track_drivers.py` |

**Dedup-Regeln.** Nur Presse, News und LinkedIn werden dedupliziert, und zwar
über den Schlüssel (Typ, Marke, URL): **ein Artikel = ein Event, über alle
Läufe.** Alle anderen Typen werden immer geschrieben. Der Grund für die Regel
steht in `scripts/cleanup_events.py`: `update_press.py` verglich früher gegen
eine auf 80 Artikel gekappte Vorversion, jeder Artikel ab Position 81 wurde
jede Nacht erneut als „neu" gemeldet. Dieselbe Bereinigung hat doppelte
Berater-Events entfernt. `cleanup_events.py` ist ausdrücklich ein
Einmal-Werkzeug mit Dry-Run als Standard und Backup vor dem Schreiben.

**Umdatierung.** Presse-, News- und LinkedIn-Events tragen zunächst den
*Crawl*-Tag. Das ist für eine Event-Study falsch: Über 2.618 Presse-/News-Events
gemessen liegt der Median-Versatz zwischen Erscheinen und Fund bei **182 Tagen**
— ein Februar-Artikel wurde dem August-Intervall zugerechnet, die Wirkung also
systematisch dorthin gebucht, wo der Crawler zufällig hinsah. `_redate_media_events()`
schreibt den Zeitstempel deshalb beim **Einlesen** auf `detail.date` um, an genau
einer Stelle, sodass es rückwirkend für alle vorhandenen Events und alle
nachgelagerten Blöcke gilt, ohne die Datei zu migrieren. Übernommen wird das
Datum nur, wenn es parsebar ist, nicht in der Zukunft liegt und nicht nach dem
Crawl-Tag — sonst Fallback auf den Crawl-Tag, und die Fallback-Fälle werden
gezählt, damit ein kaputter Feed auffällt.

**Erstimport-Filter.** Beim ersten Sammellauf einer Marke holt der
LinkedIn-Sammler rückwirkend rund einen Monat öffentlicher Posts. Google liefert
für LinkedIn fast nie ein Erscheinungsdatum (im ersten Lauf: 1 von 76), also
tragen praktisch alle diese Events den Fund-Tag — ein Monat Aktivität,
komprimiert auf einen Tag, über acht Marken gleichzeitig. Ungefiltert wäre
daraus ein Schein-Treiber geworden, denn genau dieses Muster (viele Cluster,
viele Ereignis-Intervalle am selben Tag) passiert die Signifikanzregel.
`_drop_linkedin_erstimport()` bestimmt je Marke den frühesten Tag mit
LinkedIn-Events und wirft alle Events dieses Tages **ohne** echtes
Erscheinungsdatum aus den Wirkungsrechnungen. Spätere Wochen-Batches bleiben
drin — dort ist der Fund-Tag höchstens ~7 Tage nach dem Post. Die Events bleiben
in `events.jsonl` und im LinkedIn-Reiter sichtbar; entfernt sind sie nur aus der
Statistik. Praktische Folge heute: Von 76 LinkedIn-Events sind 75 gefiltert, ein
einziges hat ein echtes Datum. LinkedIn liefert also derzeit **noch keine**
Treiber-Aussage, und das ist der ehrliche Zustand, nicht ein Nullbefund.

---

## 4 · Die Analyse-Engine `scripts/correlation_impact.py`

5.717 Zeilen, 288 KB, rund 70 Funktionen. Sie ist mit Abstand die komplexeste
Datei des Projekts und schreibt eine einzige Ausgabedatei. Was folgt, beschreibt,
**was** gerechnet wird und **warum** — nicht, wie die Formeln hergeleitet sind.

### 4.1 Zielgrößen

Drei Größen werden erklärt, jede mit derselben Maschinerie:

- **Share of Voice** aus `data/sov_history.jsonl`. Wichtig: Die Datei mischt
  drei Auflösungen (markenweite Snapshot-Zeilen, rückwirkende Backfill-Zeilen,
  Zeilen je Marke **und Produkt**, Zeilen je Marke **und Engine**). Bis zum
  04.08.2026 nahm die Engine „letzter Wert des Tages gewinnt" — und das war bei
  ~13 Produktzeilen je Marke ein **zufälliges Einzelprodukt**. Seitdem gilt eine
  weiße Liste markenweiter Quellen; die Standardabweichung der Tagesdeltas fiel
  dadurch von 3,21 auf 2,00 Prozentpunkte.
- **Zitatanteil** aus den eigenen Level-Zellen (`zitatanteil_impact()`, seit
  18.08.2026). Die erste Hälfte der Wirkkette *Maßnahme → Zitatanteil →
  Sichtbarkeit*; die zweite Hälfte ist im Niveau-Modell bereits gesichert. Nur
  Themen, die an mindestens 90 % der sauberen Messtage gemessen wurden, kommen
  hinein — sonst ändert ein neu dazukommendes Thema still die Zusammensetzung
  der Tagesreihe, und der Sprung würde als Ereigniswirkung gelesen.
- **Peec-Zitate** aus den versionierten Quellen-Snapshots
  (`citation_target_analysis()`). Zählgrößen im vier- bis fünfstelligen Bereich
  und kausal näher an der Ursache als der SoV. Die Reihe beginnt mit dem ersten
  Snapshot am 19.07.2026; vorher steht dort bewusst nichts außer einer
  Statusmeldung.

### 4.2 Intervall-Bau und Strukturbrüche

`build_intervals()` ist die zentrale Werkstatt: Aufeinanderfolgende Messtage
bilden ein Intervall, je Marke wird die Änderung der Zielgröße gegen die Zahl
der Ereignisse im Fenster gestellt, wahlweise mit Zeitversatz. Diese Logik lag
bis zum 20.07.2026 **fünfmal** nahezu identisch im Modul und war deshalb
auseinandergelaufen — der Strukturbruch-Filter existierte nur an einer der fünf
Stellen. Jetzt gibt es sie einmal.

Die **Strukturbruch-Registry** (`STRUCTURAL_BREAKS`) ist eine der wichtigsten
Konstruktionen der Datei. Definitionsänderungen machen die Zeitreihe einer Marke
unstetig; ein Intervall, das über ein solches Datum läuft, misst nicht Wirkung,
sondern die Umstellung selbst — und sieht dabei aus wie ein Effekt. Solche
Brüche gehören benannt, datiert und begründet an **eine** Stelle. Eingetragen
sind heute drei:

- **21.07.2026, alle Marken:** Markenerweiterung des Crawls von 7 auf 25.
  Simuliert am Lauf vom 17.07.: ERGO 13,96 % → 7,01 %, Allianz 31,6 % → 22,0 %.
- **21.07.2026, alle Marken:** Domain-Aliase zählen nicht mehr als Textnennung.
- **20.07.2026, ERGO:** DKV aus den ERGO-Aliasen entfernt (343 → 288 Nennungen,
  −16 %).

Alle drei sind als „nicht nachrechenbar" markiert, mit Begründung: Alt-Läufe
speicherten nur 1.500 Zeichen je Antwort, 77 % waren gekappt. Seit dem
20.07.2026 werden 20.000 Zeichen gespeichert, künftige Definitionsänderungen
sind damit rückwirkend nachrechenbar. Wer diesen Mechanismus verstehen will,
sollte zusätzlich `revert-backfill.yml` im GEO-Repo lesen — dort steht, was
passiert, wenn man es doch versucht.

### 4.3 Cluster-robuste Inferenz

Die 682 Intervalle sind **nicht** 682 unabhängige Beobachtungen. Bei
`review_volume` stammen alle Intervalle mit Ereignis aus 7 Marken, bei
`portal_rank_change` aus 2. Die effektive Fallzahl ist die Zahl der **Marken**
mit Ereignis. `_cluster_effect()` rechnet deshalb den Standardweg:
Within-Transformation je Marke (Marken-Fixed-Effects), dann eine
CR1-Sandwich-Varianz über die Marken-Cluster, Konfidenzgrenzen aus der
t-Verteilung mit `min(Marken mit, Marken ohne) − 1` Freiheitsgraden.

Zwei Schutzregeln machen die Rechnung erst brauchbar:

1. **Der Cluster-Fehler darf die Unsicherheit nur vergrößern, nie verkleinern.**
   Die CR1-Varianz ist bei wenigen behandelten Clustern nachweislich nach unten
   verzerrt; an diesen Daten lieferte sie für `review_volume` ein dreimal
   engeres Intervall als die naive Rechnung — was den Treiber fälschlich zu
   „gesichert" befördert hätte. Der rohe Wert bleibt als
   `effect_se_cr1_roh_pp` in der Ausgabe, damit die Entscheidung nachprüfbar
   ist.
2. **Unter zwei Marken mit (oder ohne) Ereignis ist gar nichts schätzbar.** Dann
   steht `nicht_schaetzbar` mit Begründung in der Ausgabe, keine Zahl.

Seit dem 15.08.2026 liegen Intervall und p-Wert um den Within-Schätzer, nicht um
die rohe Gruppendifferenz. Beide unterschieden sich am 14.08. bei
`review_volume` um 87 % — das Intervall stand also spürbar neben dem Schätzer,
dessen Unsicherheit es beziffern sollte. Die rohe Differenz bleibt als
deskriptiver Wert erhalten.

**Als „gesichert" gilt ein Effekt nur, wenn das Konfidenzintervall die Null
ausschließt UND mindestens 8 Intervalle mit Ereignis UND mindestens 5
Marken-Cluster vorliegen.** Diese drei Bedingungen stehen an mehreren Stellen
identisch im Code und sind die Grundlage für jedes „gesichert/nicht nachweisbar"
im Dashboard.

### 4.4 Wild-Cluster-Bootstrap und FDR

Bei kleiner Clusterzahl ist der asymptotische Cluster-Standardfehler unzuverlässig.
`_wild_cluster_p()` zieht deshalb Rademacher-Vorzeichen über die Cluster unter
der Nullhypothese. Der Charme der Fallzahl: Bei 7 Marken gibt es nur
2⁷ = 128 Vorzeichenvektoren, die **vollständig** durchgezählt werden — der Test
ist exakt und braucht keinen Zufallsstartwert. Die Grenze wird mitberichtet: Der
kleinstmögliche p-Wert ist 1/128 = 0,0078; ein Effekt kann hier nie „p < 0,001"
erreichen, egal wie stark er ist. Für das Peec-26-Marken-Modell (2²⁶ = 67 Mio.
Anpassungen) wird stattdessen deterministisch mit festem Startwert 42 und 4.095
Ziehungen gesampelt.

`_apply_fdr()` legt Benjamini-Hochberg über die Ergebnisbäume. Anlass war Review #3
vom 17.07.2026: 130 Effekte mit Richtungswahrscheinlichkeit, 74 davon als
signifikant ausgewiesen — bei 130 Tests und α = 0,05 sind rund 7 Zufallstreffer
zu erwarten, man weiß nur nicht welche. Korrigiert wird über die
Wild-Cluster-p-Werte, nicht über die Richtungswahrscheinlichkeiten; nur erstere
sind echte p-Werte.

Die **Testfamilie** benennt seit dem 17.08.2026 jeder Aufrufer selbst. Vorher
behauptete die Fußnote für jeden Block, die Familie bestehe aus den drei
Kanälen — das stimmte nur für die Kanal-Blöcke. Das Peec-Modell korrigiert über
zwei Treiber in einem Kanal, die Funnel-Schichtung über Treiber × Schichten.
Eine Fußnote, die eine Familie benennt, über die gar nicht korrigiert wurde, ist
schlimmer als keine.

### 4.5 Niveau-Modell (Mundlak) und Preis-Modell

Die Ereignis-Modelle fragen: *Bewegt sich etwas, wenn etwas passiert?* Das
**Niveau-Modell** fragt etwas anderes: *Warum liegt eine Marke überhaupt vorn?*

`level_model_mundlak()` bildet Zellen aus Marke × Thema und erklärt das
SoV-**Niveau** aus dem Zitations-Footprint, getrennt nach `grounded`
(Gemini, Perplexity — die Web-Such-Engines) und `ungrounded` (ChatGPT). Die
Mundlak-Zerlegung trennt dabei zwei Fragen, die sonst zusammenfallen: den
**Within**-Effekt (bewegt mehr eigener Footprint *innerhalb* eines Themas die
Sichtbarkeit?) und den **Between**-Effekt (erklärt Quellpräsenz den
Marken-Vorsprung insgesamt?). Der Between-Effekt ist der heute einzige
strukturell gesicherte Treiber des Projekts: **+5,94 Prozentpunkte Sichtbarkeit
je Standardabweichung Quellpräsenz, q = 0,002 nach FDR-Korrektur, über 25
Marken-Cluster.**

Ein Ausfall-Guard schützt das Modell seit dem 17.07.2026: Am 16.07. lieferte
Gemini für alle Themen 0, die `combined`-Zelle mittelte diese Nullen mit und
erzeugte einen künstlichen 6,6-pp-Abstand. Regel seitdem: Ein Engine-Segment
ohne einen einzigen Messwert wird **nicht** berechnet, und `combined` mittelt
nur über Segmente mit Daten.

`price_level_pooled()` ist die Antwort auf ein verwandtes Problem. Das
Niveau-Modell läuft auf einem Snapshot, dessen SoV je Zelle täglich schwankt
(Modell-Nichtdeterminismus). Der Ein-Tages-Preis-Effekt lag deshalb grenzwertig
bei p ≈ 0,06–0,1 und brach über mehrere Tage gemittelt nahe null zusammen — er
war größtenteils Tagesrauschen. Das gepoolte Modell mittelt die Messgröße **je
Zelle** über mehrere saubere Tage, bevor geschätzt wird (ehrliche
Rauschreduktion, kein Stapeln abhängiger Tageszeilen), und schätzt dann zwei
Zielgrößen: Wirkung des Relativpreises auf die Sichtbarkeit und auf die
Zitationen. Der heutige Befund: über 20 saubere Messtage durchgehend negativ
(teurer = weniger sichtbar, Tagesmittel −4,34, vorzeichenstabil) — aber als
Between-Vergleich, der alles aufsammeln kann, was teure von günstigen Anbietern
unterscheidet.

Warum der Preis-Crawl **nicht** mehr täglich läuft, steht ausführlich als
Kommentar im Nightly: Versicherungstarife ändern sich ein- bis zweimal im Jahr,
an den meisten Tagen ändern sich null von rund 230 Zellen. Was sich sehr wohl
täglich änderte, war die *Zusammensetzung* — je Lauf tauchten 3 bis 14 % der
Zellen neu auf oder verschwanden, weil der Crawl mal mehr und mal weniger
Anbieter greift. Das Modell sah diese Fluktuation als Preisbewegung, und der
Artefaktfilter räumte sie korrekt wieder weg. Täglich zu messen erzeugte also
nicht mehr Signal, sondern mehr Rauschen. Im Oktober und November läuft der
Crawl zusätzlich täglich — dann bewegen sich die Kfz-Preise wegen des
Wechselstichtags 30.11. wirklich.

### 4.6 Streubild, Nachweisgrenze, Validierung

**Das Streubild** (Über-/Unterperformer-Scatter im Korrelationsreiter) stellt je
Marke die Quellpräsenz gegen die Sichtbarkeit und zeigt, wer über und wer unter
der Erwartungsgeraden liegt. Am 14./15.08.2026 wurde dort ein Fehler gefunden,
der exemplarisch ist: Die beiden neuen SOHO-Themen standen mit je **einem**
Messtag gleichberechtigt neben Themen mit 19 Messtagen. Wirkung allein daraus:
Steigung 1,83 → 2,58, ERGOs Abstand zur Erwartungsgeraden +2,2 → +4,2 pp — ohne
dass sich an der Sichtbarkeit irgendetwas geändert hätte. Seitdem kommt ein
Thema erst ab 3 Messtagen ins gepoolte Panel, und die Grafik weist die wartenden
Themen aus. Im Preis-Modell gilt dieser Filter bewusst **nicht** für die
Tag-für-Tag-Stabilitätsreihe, weil dort je Schätzung ein einziger Tag übergeben
wird — mit Filter wäre die Reihe still leergelaufen.

**Die Nachweisgrenze** ist der Begriff, mit dem das Projekt seine Nullbefunde
erklärt, und sie steht ausformuliert im Faktenblatt für den Sprachagenten: Zu
jeder Ereignisart gehört eine Effektgröße, ab der ein echter Effekt bei der
heutigen Datenmenge überhaupt auffindbar wäre. Diese Grenzen liegen zwischen
etwa 0,4 und 1,0 Prozentpunkten; die tatsächlich gemessenen Effekte liegen
zwischen 0,03 und 0,56 Prozentpunkten — durchweg darunter. **Eine einzelne
Pressemitteilung kann diese Messung nicht bewegen, unabhängig davon, ob sie
wirkt.** Das ist der wichtigste Satz für die Auslegung des Korrelationsreiters.

**Zwei Validierungen** laufen bei jedem Nightly mit und stehen im
`validation`-Block der Ausgabedatei:

- **Placebo** (`_placebo_fpr`): Die Zielgröße wird 200-mal zufällig gemischt; es
  sollte fast nichts „gesichert" sein. Erwartet wären ~5 %, gemessen werden
  aktuell **2,25 %** — die Rechnung ist eher konservativ als zu großzügig.
- **Out-of-Sample** (`_oos_skill`): Leave-one-time-out — die ausgelassene
  Messperiode wird aus Markenbasis plus Treiber-Effekten vorhergesagt. Aktuell
  **r² = −0,03** über 682 Testpunkte: Für die Tagesprognose verbessern die
  Ereignis-Treiber heute nichts. Auch das ist ein Befund und wird so
  ausgewiesen.

Ergänzend gibt es `scripts/test_correlation_smoke.py`: ein synthetischer
Datensatz mit bekanntem eingespeistem Effekt (+1,5 pp je Pressemitteilung), der
erkannt werden **muss**, plus eine Placebo-Gegenprobe auf verschobenen Tagen,
die nichts finden **darf**. Der Test war vom 04. bis 15.08.2026 dauerhaft rot,
weil die Fixture nur 3 Marken hatte, die Engine seit dem 04.08. aber mindestens
5 Cluster verlangt — der Fehler lag in der Fixture, nicht in der Engine, ist
inzwischen auf 6 Marken korrigiert. Der Test läuft **nicht** automatisch in
einem Workflow; er muss von Hand aufgerufen werden.

### 4.7 Die übrigen Blöcke

Die Ausgabedatei enthält rund zwanzig weitere Auswertungen. Kurz, was sie
beantworten:

- **`funnel_stratified`** — Sichtbarkeit nach Funnel-Stufe. Awareness und
  Decision verhalten sich messbar unterschiedlich (9,7 % vs. 20,9 %); ein
  gemeinsames Modell mittelt das weg.
- **`dose_response`** — *Wirkt mehr davon auch mehr?* Die binäre Frage trennt bei
  310 von 682 Intervallen mit Seitenänderung kaum noch etwas. Die Dosis-Rechnung
  stellt sich daneben, ersetzt aber nichts.
- **`lag_analysis`** — prüft Zeitversätze. `LAG_DAYS` stand lange im Code und
  wurde als „lag_days: 0" berichtet, beim Zählen aber nie angewandt: eine
  ungetestete Annahme, die wie eine Einstellung aussah. Ausgewiesen wird der
  beste Versatz **plus** der Verlauf über alle Versätze — explorativ, wer fünf
  Versätze durchprobiert, findet auch in Rauschen ein Maximum.
- **`press_by_citation`** und **`external_source_authority`** — Presse getrennt
  nach der Zitierautorität des Mediums. Im selben Topf lagen finanztip.de
  (28.306 Zitate im 30-Tage-Fenster) und ad-hoc-news.de (132 Artikel, null
  Zitate); der Großteil unserer externen Events liegt auf Quellen, die die
  Modelle gar nicht zitieren.
- **`fanout_regime`** — die Web-Such-Rate der Engines als Störgröße. Antwortet
  ein Modell ohne Web-Suche, kann eine geänderte Seite die Antwort physisch
  nicht beeinflusst haben. Die Rate misst Peec-Engines, also ist die Zielgröße
  hier auch die Peec-Sichtbarkeit — Quellen nicht mischen.
- **`event_impact_denoised`** — dieselbe Event-Study auf grounded-Engines und
  Wochenmitteln statt Tageswerten.
- **`new_page_did`** — Difference-in-Differences für Seiten, die **wirklich** neu
  veröffentlicht wurden (schema.org / OpenGraph), mit den anderen Themen
  derselben Marke als Kontrolle. Das Crawler-`first_seen` sagt nur „wir haben die
  URL erstmals gesehen".
- **`peec26_model`**, **`citation_authority_signal`**, **`page_change_types`**,
  **`citation_category`**, **`footprint_analysis`** — Peec-interne Modellierung,
  autoritätsgewichtete Zitatreihe, Änderungsart, Kategorien-Mix.

Jeder dieser Blöcke schreibt bei zu dünner Datenlage `available: false` **mit
Grund** statt einer Zahl.

---

## 5 · Das Dashboard

### 5.1 Aufbau und Reiter

Die Live-Datei ist **`dashboard_v3.html`** (448 KB, 6.675 Zeilen) — nicht
`dashboard_template.html`. Letztere ist die alte Variante mit hart injizierten
Daten, inzwischen 13,3 MB groß, und dient nur noch als Fallback;
`encrypt_dashboard.py` bevorzugt v3. Der entscheidende Unterschied: v3 lädt
seine Daten zur Laufzeit per `fetch()` aus `data/`, statt sie im HTML zu tragen.
Datendateien brauchen deshalb keinen Rebuild — sie werden direkt von GitHub
Pages ausgeliefert.

**Fest im HTML** liegen: Übersicht · Anbieter-Webseiten (die zehn Marken-Reiter,
von `nav_redesign.js` in ein Dropdown geschoben) · ERGO Berater ·
LLM-Sichtbarkeit (mit dem konsolidierten Peec-Block) · Empfehlungen ·
Bewertungen · Ratings · Presse · Content Änderungen · Preisvergleich · Peec AI ·
Funnel & Suchanfragen · Quellen & Zitate · Methodik & Fragen ·
Korrelationsanalyse. **Zur Laufzeit angehängt** werden Dokumentation
(`geo_doku_tab.js`), **SOHO (Gewerbe)** (`soho_tab.js`, seit 13.08.2026) und
**LinkedIn** (`linkedin_tab.js`, seit 18.08.2026). Drei Neuerungen verdienen
eine eigene Erklärung:

**SOHO.** Bis zum 13.08.2026 hat das Cockpit ausschließlich Privatkundenthemen
gemessen — nicht weil das Gewerbegeschäft unwichtig wäre, sondern weil nie
jemand danach gefragt hatte. Im Dashboard sah das aber genauso aus wie „gemessen
und nichts gefunden", und das ist der teuerste Irrtum, den eine Messstrecke
anbieten kann. Am 13.08. wurden 60 eigene Prompts geschrieben (30
Betriebshaftpflicht, 30 Firmen-Rechtsschutz), die Produkte in die
GEO-Konfiguration aufgenommen, und derselbe Abend brachte den ersten Lauf. Der
Reiter rechnet ausschließlich mit Engines, die für das jeweilige Thema
tatsächlich Prompts abgesetzt haben (`prompts_total > 0`), und schreibt darunter,
welche das waren — ein Anteil, der stillschweigend auf zwei statt drei Systemen
beruht, ist kein Anteil, sondern eine Falle. Als Maßstab dient der private
Rechtsschutz: gleiche Sparte, gleicher Lauf, gleiche Modelle, nur anderes
Segment.

**LinkedIn.** Zeigt öffentliche Posts mit Bezug zu ERGO oder einem Wettbewerber
— gesammelt **nicht** durch Crawlen von LinkedIn (das verbieten deren
Nutzungsbedingungen, und die Bot-Abwehr macht es ohnehin unzuverlässig), sondern
über die Google-Suche nach `site:linkedin.com/posts` je Marke, via SerpAPI. Der
Sammler drosselt sich selbst auf einen Lauf pro Woche (6-Tage-Abstand) und
überspringt wortlos, wenn `SERPAPI_KEY` fehlt — der tägliche Nightly-Schritt ist
also harmlos. `update_linkedin_kpis.py` misst zusätzlich die **öffentlichen**
Reaktions- und Kommentarzahlen nach; Impressionen und Reichweite kennt von außen
niemand, und Authwalls werden gezählt statt mit Nullen aufgefüllt.

**Das Maßnahmen-Tagging-Panel** im Korrelationsreiter (17.08.2026) ist der
Gegenzug zu einer Streichung: Am 12.08. flog der alte DiD-Block aus dem
Dashboard, weil er ausschließlich automatisch erkannte Aktivitätsspitzen zeigte
— nie eine echte Maßnahme. Übrig geblieben waren sechs Zufallszahlen mit vier
Absätzen Warnhinweisen darunter. Das neue Panel schließt die Lücke von der
anderen Seite: Es macht das **Taggen** echter Maßnahmen so einfach, dass die
Rechnung (`scripts/intervention_analysis.py`, läuft längst im Nightly) endlich
Futter bekommt. Datum, Produkt (optional), Kurzbeschreibung — der Knopf öffnet
eine vorbereitete E-Mail mit der fertigen JSON-Zeile, die Übernahme nach
`data/interventions.json` erfolgt kuratiert. Kein Backend, die Seite bleibt
statisch. Ergebnisse erscheinen im Panel **nur** für manuell getaggte Maßnahmen
(`source = manuell`), nie für Auto-Spitzen.

### 5.2 Das Runtime-Nachlade-Muster

Das Dashboard lädt seine Module in zwei Stufen nach, und zwar aus einem sehr
praktischen Grund: `dashboard_template.html` ist 13,3 MB groß und lässt sich
über den GitHub-Konnektor nicht schreiben. Ein Runtime-Modul hängt sich seinen
Reiter selbst an und kommt ganz ohne Template-Änderung aus.

```
dashboard_v3.html
  ├─ <script src="…"> : level_model_chart, citation_channels, price_compare,
  │                     korrelation_upgrade, gap_waterfall, content_citations,
  │                     search_ab_block, massnahmen_liste, georg_widget,
  │                     health_banner, footprint_chart
  └─ health_banner.js  (Loader am Dateiende)
       ├─ nav_redesign.js
       │    └─ overview_upgrade.js · empfehlungen_dynamic.js ·
       │       geo_wirkung.js · geo_doku_tab.js
       ├─ soho_tab.js
       └─ linkedin_tab.js
```

Jeder Loader hängt einen `<script>`-Knoten mit `?t=<Zeitstempel>` an, um den
Browser-Cache zu umgehen. Die Module sind bewusst eigenständig (IIFE,
`"use strict"`, eigener Escaper, eigene Retry-Schleife), weil sie zu nicht
vorhersagbaren Zeitpunkten fertig werden. `nav_redesign.js` wartet deshalb, bis
alle vier hinteren Reiterknöpfe existieren, und sortiert dann **einmal** um; ist
nach 50 Versuchen eines nicht da, wird sortiert, was da ist — eine halbe Ordnung
ist besser als gar keine.

`health_banner.js` ist zusätzlich das Frische-Banner: Es liest
`data/geo_snapshot.json` und warnt, wenn ein Modell keine Daten mehr liefert oder
der Snapshot überaltert ist. Die Altersgrenze steht auf 8 Tagen (7 Tage
Crawl-Takt + 1 Tag Luft). Sie stand vorher auf 2 — mit dem wöchentlichen Crawl
hätte das Banner fünf von sieben Tagen grundlos im Bild gestanden, und genau so
gewöhnt man sich ab hinzusehen. Bemerkenswert ist der Kommentar daneben: Der
Wochentag des Crawls stand einmal in dieser Datei und war 24 Stunden später
falsch, weil der Cron im GEO-Repo verschoben wurde. Seitdem steht er hier nicht
mehr — *was eine Datei nicht behauptet, kann nicht veralten.*

Ebenfalls in `health_banner.js`: eine Spiegelung von `GEO_SNAPSHOT` auf
`window`. Das Dashboard deklariert die Variable mit `let`, und `let` landet
nicht auf `window`; die Runtime-Module lasen `window.GEO_SNAPSHOT` und blieben
im echten Browser leer, während die jsdom-Tests grün waren, weil sie `window`
direkt setzten.

### 5.3 Verschlüsselung und Auslieferung

`scripts/encrypt_dashboard.py` nimmt `dashboard_v3.html`, verschlüsselt es mit
**AES-256-GCM** (Schlüssel per PBKDF2-HMAC-SHA256, 100.000 Runden, zufälliges
Salt und IV) und baut daraus eine ERGO-gebrandete Login-Seite als `index.html`
(aktuell 604 KB). Der Browser entschlüsselt per Web Crypto API im Client. Das
Passwort kommt aus dem Secret `DASHBOARD_PASSWORD` und steht nirgends im Code —
die frühere Nennung im Docstring wurde am 12.06.2026 entfernt.

Diese Verschlüsselung ersetzt StatiCrypt und das alte
`inject_password_fix.py`-Verfahren vollständig. Gebaut und gepusht wird über die
zusammengesetzte Action `.github/actions/build-and-deploy`, die vom Nightly und
vom manuellen `dashboard-deploy.yml` gleichermaßen benutzt wird.

**Wichtig für die Einschätzung:** Verschlüsselt ist die **Seite**, nicht die
Daten. Die Module holen `data/*.json` zur Laufzeit vom selben öffentlichen
Pages-Host; wer die Dateinamen kennt, kommt ohne Passwort an die Zahlen. Das
Passwort ist eine Zugangsschwelle für die Darstellung, kein Schutz der Daten.
Siehe Abschnitt 8.6.

---

## 6 · Deploy-Wege — und warum es zwei gibt

Es gibt zwei Wege, Code ins Repo zu bekommen, und die Regel dazwischen ist
schlicht:

**Kleine Dateien (bis ~15 KB) über den GitHub-Konnektor.** Direkt geschrieben,
sofort sichtbar. Danach gehört die Byte-Verifikation dazu: `git hash-object` auf
die lokale Datei berechnet die Blob-SHA nach der Git-Formel, und die muss mit der
SHA übereinstimmen, die die GitHub-API für die geschriebene Datei zurückmeldet.
Stimmt sie, sind die Bytes identisch — nicht „sieht gleich aus".

**Große Dateien und alles Grenzwertige über eine Auto-Deploy-Seite.** Erzeugt mit
`python3 scripts/build_auto_deploy.py`. Das Ergebnis ist eine einzelne
HTML-Datei zum Doppelklicken: Sie trägt die zu deployenden Dateien
base64-kodiert in sich, schickt sie mit einem persönlichen Zugangsschlüssel über
die Contents-API nach `phoeser/LLM-Cockpit` und kann anschließend Workflows
anstoßen. Kein Git, keine Kommandozeile.

**Warum diese Trennung existiert**, steht als Havarie-Bericht im Docstring des
Generators und lohnt die Lektüre auch für Nicht-Entwickler. Die alte
`Auto-Deploy_v3.html` wurde einmal von Hand befüllt (Stand 27.04.2026) und
danach nie wieder. Am 12.08.2026 nachgemessen: **alle elf** eingebetteten
Dateien waren veraltet, und die Kästchen „yml-Workflows", „Python-Skripte" und
„dashboard_template.html" waren **vorausgewählt**. Ein Klick auf „Push starten"
hätte unter anderem `scripts/update_sentiment.py` von 97.805 auf 6.427 Bytes und
`dashboard_template.html` von 13.340.705 auf 94.418 Bytes zurückgesetzt — vier
Monate Arbeit in einem Zug. Nicht durch einen Fehler im Code; der Code
funktionierte einwandfrei. Sondern weil eine Momentaufnahme mit der Zeit still
falsch wird und nichts sie daran gehindert hat.

Drei Konsequenzen sind daraufhin eingebaut worden:

1. **Die Seite wird erzeugt, nicht gepflegt.** Eingebettet wird genau das, was
   sich zwischen Arbeitsstand und `origin/main` unterscheidet — die ehrliche
   Definition von „muss noch raus". `data/`, `shared/` und die verschlüsselte
   `index.html` bleiben ausgenommen: Die schreibt der Nightly selbst, und sie
   über diese Seite zu pushen hieße, dem Nightly ins Steuer zu greifen.
2. **Drei SHAs statt zwei.** Die Seite kennt den Stand, gegen den sie gebaut
   wurde, den Stand, der gerade im Repo liegt, **und** den Inhalt, den sie selbst
   trägt. Ohne den dritten warnte sie nach jedem eigenen erfolgreichen Push vor
   sich selbst — und eine Warnung, die immer kommt, wird nicht mehr gelesen,
   dann fehlt sie an dem Tag, an dem sie zutrifft.
3. **Der Bauzeitpunkt steht im Dateinamen** (`Auto-Deploy_2026-08-18_1747.html`).
   Vorher hieß die Datei immer gleich, der Browser hängte `_1` bis `_6` an, und
   die Nummer sagt nur, in welcher Reihenfolge heruntergeladen wurde, nicht wann
   gebaut. Paul hat folgerichtig `_v3_5` geöffnet, während `_v3_6` die aktuelle
   war. Alte Fassungen gehören gelöscht, nicht aufgehoben; erzeugte Seiten sind
   per `.gitignore` aus dem Repo verbannt.

Nichts ist mehr vorausgewählt. Wer alles pushen will, sagt das.

**Der eigentliche Grund für den zweiten Weg** ist aber ein anderer, und er gilt
unabhängig von dieser Geschichte: Der Konnektor schreibt, was ihm übergeben wird
— bei großen Dateien heißt das faktisch Abtippen, und Abtippen erzeugt
Tippfehler in Code, den niemand ändern wollte. Die Auto-Deploy-Seite kopiert
Bytes.

---

## 7 · Betriebsregeln und Secrets

### 7.1 Secrets — Namen, niemals Werte

| Secret | Repo | Wofür |
|---|---|---|
| `DASHBOARD_PASSWORD` | Cockpit | Passwort der ausgelieferten Seite |
| `GEO_REPRO_TOKEN` | Cockpit | Lesezugriff auf das GEO-Repo |
| `GEMINI_API_KEY` | Cockpit | Sentiment-Auswertung, Übersetzung der Peec-Empfehlungen |
| `GOOGLE_PLACES_API_KEY` | Cockpit | Google-Bewertungen |
| `SERPAPI_KEY` | Cockpit + GEO | LinkedIn-Sammler; im GEO-Repo für Suchdienste |
| `PEEC_TOKEN` | Cockpit | Peec-Quellen-Tagesexport |
| `ELEVENLABS_API_KEY` | Cockpit | Wissensbasis des Sprachagenten GEOrg |
| `COCKPIT_REPO_TOKEN` | GEO | Lesezugriff auf `shared/events.jsonl` |
| `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `PERPLEXITY_API_KEY`, `XAI_API_KEY` | GEO | die Modell-Schnittstellen |

Werte stehen ausschließlich in den GitHub-Secrets. Kein Schlüssel gehört in
Code, Docstring, Commit-Nachricht oder Bericht. Zwei Zugangsschlüssel liegen
**bewusst nicht** als Secret: Pauls persönlicher Peec-Token für Empfehlungen und
Segmente (läuft als Cowork-Task) und der Zugangsschlüssel der Auto-Deploy-Seite
(wird beim Öffnen eingegeben). Für GEOrg gilt zusätzlich: Die Agenten-ID ist kein
Geheimnis — sie steht ohnehin im ausgelieferten HTML —, aber in ElevenLabs ist
eine Hostname-Allowlist auf `phoeser.github.io` hinterlegt, sonst könnte jeder,
der die ID ausliest, den Agenten auf ERGO-Kosten benutzen.

### 7.2 Was der Konnektor nicht kann

Der GitHub-Konnektor kann **keine Workflow-Dateien schreiben** und **keine
Workflows auslösen**. Workflow-Änderungen laufen über die Auto-Deploy-Seite oder
über die GitHub-Oberfläche. Zum Anstoßen von Workflows braucht ein
Zugangsschlüssel die Berechtigung **Actions: Read and write** — ein anderes
Häkchen als „Workflows: Read and write", was regelmäßig verwechselt wird. Ohne
Token geht es immer über den Actions-Reiter.

### 7.3 Keine berechneten Container-Ergebnisse ins Repo

Zahlen, die in einer Arbeitssitzung außerhalb der Pipeline gerechnet wurden,
gehören **nicht** ins Repo. Der Grund ist derselbe wie bei der alten
Auto-Deploy-Seite: Eine Momentaufnahme, die im Repository liegt, sieht dauerhaft
aus, ohne es zu sein. Alles Berechnete entsteht im Nightly aus den Rohdaten und
nur dort. Für Prüfrechnungen gilt: nachrechnen, das Ergebnis im Bericht nennen,
die Datei nicht anfassen.

### 7.4 Überwachung

`scripts/pipeline_health.py` prüft je Datenelement das echte Alter (Grenzen von
2 bis 9 Tagen, je nach Takt der Quelle) und läuft im Nightly zweimal: einmal
schreibend (`--write` → `data/pipeline_health.json`) und einmal als
Frische-Alarm (`--check`, färbt den Lauf rot).

Der **Pipeline-Wächter** steht bewusst daneben. Anlass: Vom 05. bis 09.08.2026
lief der Nightly vier Tage lang gar nicht, weil ein Schritt zweimal
`continue-on-error` trug, GitHub doppelte YAML-Schlüssel ablehnt und der gesamte
Workflow damit ungültig war. Niemand hat es gemerkt — der Frische-Alarm ist der
**letzte Schritt des Nightly selbst**, und ein Wächter, der im überwachten
Prozess sitzt, kann dessen Totalausfall nicht melden. Der eigene Workflow ist
absichtlich winzig, hat keine Secrets und keine Netzabhängigkeit außer dem
Checkout. Er wird rot, wenn eine Workflow-Datei ungültiges YAML enthält
(doppelte Schlüssel inklusive) oder wenn `data/correlation_impact.json` älter
als 2 Tage ist.

### 7.5 Ehrlichkeitskonventionen

Diese Regeln stehen in mehreren Dateien wortgleich und sind der eigentliche
Charakter des Projekts:

1. **„Keine Daten" ist nie 0,0.** Fehlt eine Zahl, steht „keine Angabe" mit
   Grund. Ein Nullwert bedeutet gemessene Null, nichts anderes. Ein Segment ohne
   Messwerte wird nicht berechnet, sondern als nicht berechenbar ausgewiesen.
2. **Kein Effektwert ohne sein Urteil.** „nicht nachweisbar" steht **vor** der
   Zahl, nicht in einer Fußnote.
3. **Keine Prozentangabe ohne Bezugsgröße.**
4. **Was das System nicht messen kann, bekommt ein eigenes Kapitel** — damit der
   Sprachagent GEOrg auf Fragen, die er nicht beantworten darf, eine Antwort hat
   statt einer Erfindung.
5. **Jede Zahl kommt zur Laufzeit aus einer Datei.** Keine eingefrorenen Werte,
   keine statischen Fallbacks im Code. Ein Reiter mit einprogrammierten Zahlen
   sähe in vier Wochen täglich frisch aus und wäre es nicht.
6. **Fehlt eine Datenquelle, sagt der Reiter das,** statt leer auszusehen wie
   ein kaputter.
7. **Datierung:** Jede Entscheidung im Code trägt Datum und Begründung. Wo ein
   Kommentar eine Tatsache behauptet, die woanders steht (ein Cron-Takt, eine
   Markenzahl), gehört sie entweder entfernt oder aktiv nachgeführt — sonst wird
   sie zur nächsten Fehlerquelle.

---

## 8 · Bekannte Grenzen

### 8.1 LinkedIn: Untererfassung und Fund-Tag-Versatz

Erfasst wird, was **öffentlich und von Google indexiert** ist — die
reichweitenstarken Posts, nicht jeder Beitrag. Die Untererfassung steht sichtbar
im Reiter, nicht nur im Code. Dazu kommt ein Datierungsproblem in zwei Stufen:
Google liefert für LinkedIn nur selten ein Erscheinungsdatum (erster Lauf: 1 von
76), und ein Post kann Tage vor seiner Indexierung erschienen sein. Ohne Datum
trägt das Event den Fund-Tag; die Engine zählt diese Fälle sichtbar mit. Der
Erstimport-Batch fliegt komplett aus den Wirkungsrechnungen (Abschnitt 3.2).
Praktisch heißt das: **LinkedIn ist als Anzeige da und als Treiber noch nicht
messbar.** Ab dem zweiten Wochen-Batch beträgt der Versatz höchstens ~7 Tage —
ein dokumentierter Lag, kein komprimierter Monat.

Bei den Performance-KPIs gilt dieselbe Ehrlichkeit: Von außen sind nur
Reaktions- und Kommentarzahlen sichtbar. Impressionen und Reichweite kennt nur
der Seiten-Administrator, und Authwalls werden gezählt statt mit Nullen
aufgefüllt.

### 8.2 Peec: das rollierende Fenster

`peec_sources.json` ist immer eine Momentaufnahme über die letzten 30 Tage. Zwei
aufeinanderfolgende Snapshots **überlappen sich zu 29/30** — Effekte verschmieren
über das Fenster, und zwei Stände sind alles andere als unabhängige
Beobachtungen. Deshalb rechnet `citation_target_analysis` mit Anteilen statt
Absolutzahlen und weist die Kopplung Zitatanteil → Sichtbarkeit erst aus, wenn
genügend **nicht** überlappende Snapshots vorliegen. Und deshalb ist der eigene
tägliche Zitatanteil (`zitatanteil_impact`, seit 18.08.) die methodisch bessere
Reihe: kein rollierendes Fenster, kein Top-Domain-Abschnitt, cluster-robuste
Inferenz.

Der Peec-Export liefert außerdem nur die Top-Domains und -URLs (aktuell 100
bzw. 1.500) — der Long Tail fehlt strukturell. Die
`classification` (You/Competitor/Editorial/Aggregator/…) ist eine
**Peec-Heuristik**, keine geprüfte Taxonomie, und `mentioned_brand_ids` sind
Ko-Vorkommen, keine Kausalität. Beides ist im Dashboard entsprechend
gekennzeichnet.

### 8.3 Perplexity: der Ausfall und die Carry-Forward-Regeln

Vom 06. bis mindestens 13.08.2026 lieferte Perplexity nichts: HTTP 401, „You
exceeded your current quota", sechzigfach im Lauf vom 13.08. Was das Cockpit acht
Tage lang zeigte, waren byte-identisch fortgeschriebene Werte vom 06.08. — bei
Qualitätsampel „green / 100". Der Ausfall war aus drei Gründen teuer: Er war
unsichtbar (die Fortschreibung hatte keine Altersgrenze, und das Feld, an dem man
ihn erkannt hätte, wurde beim Übertragen ins Cockpit weggeworfen), die
eingefrorenen Werte verzerrten die Metrik (der Block stammte aus der
25-Marken-Zeit und war gegen den alten Nenner gerechnet: 13,1 % statt 15,9 % für
ERGO/Zahnzusatz), und er kostete Laufzeit (~1.140 aussichtslose HTTP-Aufrufe und
~38 Minuten Wartezeit pro Lauf).

Am 15.08.2026 wurden zwei Absicherungen eingebaut (`_carry_forward_llm` in
`analyzer/main.py`):

- **Altersgrenze `MAX_CARRY_DAYS = 7`.** Das Ursprungsdatum der Daten wird als
  `carried_forward_from` mitgeführt, auch über Ketten hinweg (heute kopiert von
  gestern, gestern von vorgestern). Ist es älter als sieben Tage, wird **nicht
  mehr** fortgeschrieben — dann fehlt die Engine ehrlich, und das Fehlen ist
  sichtbar. Eine Woche deckt den geplanten Wochentakt ab; was älter ist, ist
  kein langsamer Bestandswert mehr, sondern ein Ausfall.
- **Marken-Filter beim Übernehmen.** Beim Fortschreiben wird auf die aktuelle
  Markenliste gefiltert und der Share of Voice gegen den gefilterten Nenner neu
  gerechnet, damit ein alter Block nicht mit einem alten Nenner weiterläuft.

`health_banner.js` zeigt fortgeschriebene Modelle seit dem 15.08. mit
Ursprungsdatum an. Perplexity ist im aktuellen Snapshot wieder mit eigenen Daten
vertreten (`carried_forward` ist leer).

### 8.4 Die Wettbewerber-Erweiterung ist eine offene Entscheidung

Die Zahl unabhängiger Marken-Cluster ist der härteste Deckel auf der
Ereignis-Statistik: Unter 5 Clustern ist gar nichts schätzbar, und die meisten
Ereignistypen liegen heute bei 7 bis 23. Mehr Marken hieße mehr Cluster.

Die Entscheidung liegt bei Paul, weil sie die Zeitreihe bricht. Der Bruch ist
handhabbar — Datum dokumentieren, wie beim Umbau am 10.08. geschehen —, aber er
gehört bewusst getroffen und nicht nebenbei. Empfehlung aus Bericht 42: mit dem
SOHO-Bestandsaufnahme-Stichtag zusammenlegen, dann gibt es einen sauberen
gemeinsamen Bruchpunkt.

**Achtung, hier hat sich die Faktenlage seit Bericht 42 verschoben** (Details in
8.5): Die Aussage „ARAG, Gothaer, HDI und Hiscox werden bereits gecrawlt, zählen
aber nicht in die Anteilsrechnung" trifft in dieser Form nicht mehr zu. In der
heutigen `data/config.json` stehen ERGO plus **sechs** Wettbewerber (Allianz,
AXA, Generali, HUK-Coburg, Signal Iduna, CosmosDirekt); Seiten getrackt werden
über `tracked_urls` sogar nur für fünf Marken. Hiscox kommt nirgends vor. Die
Erweiterung ist also nicht „Marken aus der Beobachtung in die Rechnung holen",
sondern „Marken wieder aufnehmen".

### 8.5 Zwei Befunde aus dieser Durchsicht, die bisher nirgends dokumentiert sind

Beim Einlesen sind zwei Dinge aufgefallen, die in keinem Bericht und in keinem
Docstring stehen. Beide hängen an **einem** Commit im GEO-Repo:
`0e759a1ef8` vom 13.08.2026, Betreff „feat: Perplexity wieder aktivieren".

**(a) Die Markenzahl ist von 25 auf 7 gefallen — ohne Eintrag in der
Strukturbruch-Registry.** Derselbe Commit, der Perplexity aktiviert, entfernt 18
Wettbewerber aus `data/config.json` (24 → 6). In `data/sov_history.jsonl` ist der
Sprung sichtbar: 13.08. noch 25 Marken, 15.08. nur noch 7. Die
**Gegenrichtung** (7 → 25 am 21.07.) ist in `STRUCTURAL_BREAKS` sauber
registriert und begründet, die Rückkehr war es bis zu dieser Durchsicht nicht —
Intervalle über dem 14.08. liefen fünf Tage lang ungefiltert durch das
Treibermodell, obwohl sich der SoV-Nenner zwischen ihren Endpunkten geändert
hatte. **Noch am 18.08. behoben:** Die Brüche 13.08. (Markenliste 25 → 7) und
15.08. (Perplexity als zweite grounded-Engine + Nenner-Neuberechnung) sind
seither registriert; die gepoolten Modelle (Preis, Streubild, Zitatanteil)
setzen dadurch ehrlich neu auf und reifen mit jedem Nightly nach. Nebenwirkung: Bericht 42 nennt „25 Marken" als
Datenbasis; das ist historisch korrekt (die Cluster stammen aus der Zeit vor dem
14.08.), beschreibt aber nicht mehr die laufende Messung. Ab jetzt wachsen nur
noch 7 Cluster nach.

**(b) DKV ist wieder in den ERGO-Aliasen.** Derselbe Commit trägt `DKV`,
`DKV Deutsche Krankenversicherung`, `dkv.de` und `dkv.com` wieder in
`brand.aliases` und `brand.extra_domains` ein — und entfernt dabei die
`_hinweis_dkv`-Zeile, die die Entscheidung vom 20.07.2026 festhielt. Jede
DKV-Nennung zählt seitdem wieder als ERGO-Nennung, obwohl der Cockpit-Code den
20.07. weiterhin als Strukturbruch führt („DKV aus den ERGO-Aliasen entfernt,
343 → 288 Nennungen") und die Preisseite ERGO beim Krankenhauszusatz genau
deshalb ausschließt. Das passt zu dem in Bericht 41 gemeldeten Widerspruch, dass
`citation_channels` `dkv.com` als Fremdquelle zählt und alle anderen Module als
ERGO.

Beides sieht nach einem versehentlich mit deployten älteren Konfigurationsstand
aus — also genau nach dem Schadensmuster, das der Auto-Deploy-Generator
verhindern soll, nur an einer Datei, die dort nicht überwacht wird. **Zu
entscheiden ist:** ob 7 Marken die gewollte Messbasis sind (dann gehört der
14.08. als Strukturbruch registriert) und ob DKV zu ERGO zählen soll (dann
gehört der Strukturbruch vom 20.07. überarbeitet — oder die Konfiguration
zurückgedreht).

### 8.6 Weitere Grenzen in Stichworten

- **Das Passwort schützt die Darstellung, nicht die Daten.** Repo und
  Pages-Site sind öffentlich, die Module holen `data/*.json` unverschlüsselt.
- **Kein Kausalnachweis außer im Experiment.** Der einzige kausal belegte
  Baustein ist das Websuche-A/B (`search-ab-test.yml`, 150 Prompt-Paare, 2
  Wiederholungen). Alles andere sind Beobachtungsdaten. Das Experiment läuft
  ausdrücklich **ohne** Zeitplan und schreibt nach `data/experiments/`, nicht in
  die Zeitreihe: Erzwungene Websuche ist nicht das, was ein Nutzer erlebt.
- **Zirkularität.** Zitate und Nennungen stammen aus demselben Antworttext
  (eigener Crawl, ungrounded: r = +0,998). Nur `_cross_source_check` (Peec-Treiber
  gegen eigenen SoV) ist konstruktiv zirkularitätsfrei.
- **`keywords` haben einen versteckten Nebeneffekt**: Sie schalten den Fallback
  auf die Produkt-URL ab. Fünf Produkte ohne `keywords` tracken genau eine URL —
  für sie ist die Event-Korrelation strukturell unmöglich, sie melden aber
  „keine Wirkung" statt „nicht gemessen".
- **`runs_per_prompt: 1`** — jede Frage wird einmal gestellt. Das Tagesrauschen
  liegt bei rund 1 Prozentpunkt; mehr Wiederholungen senken es mit der Wurzel
  der Anzahl und sind eine reine Kostenfrage, keine Wartefrage.
- **Der Smoke-Test läuft in keinem Workflow.** Er muss von Hand aufgerufen
  werden, und er war deshalb elf Tage unbemerkt rot.
- **Kleinere Doku-Drift:** Der Docstring von `zitatanteil_impact()` nennt
  `data/level_cells.jsonl`; die Datei heißt `data/level_cells_history.jsonl`.
  Ohne Wirkung auf die Rechnung, aber ein falscher Wegweiser.

---

## 9 · Wo finde ich was

### Repo `LLM-Cockpit` (`/tmp/n1`)

**Anzeige.** `dashboard_v3.html` ist die Live-Seite (Reitergerüst,
Ergebnis-Panel des Korrelationsreiters, Maßnahmen-Tagging-Panel).
`dashboard_template.html` ist die alte 13,3-MB-Variante mit injizierten Daten
und nur noch Fallback. `index.html` ist das ausgelieferte, verschlüsselte
Ergebnis — vom Workflow erzeugt, nie von Hand anfassen. Die Module:
`health_banner.js` (Frische-Banner **und** erster Loader), `nav_redesign.js`
(Umbenennung, Anbieter-Dropdown, zweiter Loader), `soho_tab.js` /
`linkedin_tab.js` (die jüngsten Reiter), `korrelation_upgrade.js` (Streubild und
Quellenvergleich), `gap_waterfall.js` / `level_model_chart.js` /
`footprint_chart.js` (Ursachenzerlegung), `geo_doku_tab.js` (Methodik),
`massnahmen_liste.js` (gebündelte Maßnahmenliste).

**Rechnen und Sammeln** (alles unter `scripts/`):

| Datei | Zweck |
|---|---|
| `correlation_impact.py` | **Die Analyse-Engine.** 5.717 Zeilen |
| `update_snapshot.py` · `sov_history.py` · `merge_geo_page_events.py` · `fetch_search_ab.py` | Alles, was aus dem GEO-Repo hereinkommt |
| `update_press.py` · `update_sentiment.py` · `update_prices.py` · `update_ratings.py` · `track_drivers.py` · `update_domain_footprint.py` | Die eigenen Crawler |
| `update_linkedin.py` · `update_linkedin_kpis.py` | LinkedIn-Sammler und KPI-Nachmessung |
| `export_peec_*.py` · `build_nordstern.py` · `build_peec_neutral_sov.py` · `translate_peec_actions.py` | Der Peec-Strang |
| `content_citations.py` | Welche konkreten URLs es in die Antworten schaffen |
| `intervention_analysis.py` | Difference-in-Differences für getaggte Maßnahmen |
| `geo_faktenblatt.py` · `georg_sync.py` | Wissensbasis des Sprachagenten GEOrg |
| `pipeline_health.py` | Frische je Datenelement, `--write` und `--check` |
| `encrypt_dashboard.py` | AES-256-GCM + Login-Seite |
| `build_auto_deploy.py` | Erzeugt die Auto-Deploy-Seite. **Docstring lesen** |
| `test_correlation_smoke.py` · `cleanup_events.py` | Engine-Test und Event-Bereinigung, beide nur manuell |

**Daten.** `shared/event_emitter.py` + `shared/events.jsonl` (die Chronik,
27.646 Zeilen, append-only). In `data/`: `correlation_impact.json` (Ergebnis der
Engine, Grundlage fast aller Reiter), `geo_snapshot.json` (+ `.previous.json`),
die Zeitreihen `sov_history.jsonl` / `level_cells_history.jsonl` /
`price_history.jsonl`, `interventions.json` + `intervention_results.json`, der
ganze `peec_*`-Block samt `peec_snapshots/` (16 Quellen-Stände),
`pipeline_health.json` und `geo_faktenblatt.md`.

**Betrieb.** `.github/workflows/` (elf Stück, jeder mit begründendem
Kopfkommentar) und `.github/actions/build-and-deploy/action.yml` (Verschlüsseln
und Push, von zwei Workflows genutzt).

### Repo `geo-visibility-tool` (`/tmp/geo`)

| Pfad | Inhalt |
|---|---|
| `analyzer/main.py` | Orchestrierung des Laufs, Carry-Forward-Regeln |
| `analyzer/llm_clients.py` · `metrics.py` | Modell-Schnittstellen; Nennungen zählen, Quellen lesen, SoV rechnen |
| `analyzer/page_tracker.py` · `sitemap_discovery.py` · `redirect_resolver.py` · `diff_classifier.py` | Seiten-Tracking und Klassifikation der Änderungsart |
| `analyzer/correlation.py` · `why_analysis.py` · `missing_ergo_analysis.py` · `data_quality.py` | GEO-seitige Auswertung |
| `data/config.json` | **Marke, Wettbewerber, 13 Produkte, Modelle, Einstellungen** |
| `data/prompts/*.json` · `data/runs/` | Die ~30 Fragen je Produkt; 137 Läufe + `latest.json` |
| `data/pages/` · `data/snapshots/` · `data/page_dates.json` | Seitenzustände und Publikationsdaten |
| `data/experiments/` · `tools/search_ab_test.py` | Das Websuche-A/B — bewusst außerhalb der Zeitreihe |
| `tools/backfill_brand_metrics.py` · `prune_runs.py` | Nachrechnen und Aufräumen |
| `.github/workflows/analyze.yml` | Der Wochenlauf |

### Die Berichtsreihe

`31_UEBERGABE` (09.08.) · `32_KORRELATIONSREITER_REVIEW` (10.08.) ·
`33_CHATGPT_WEB_AUSWERTUNG` (10.08.) · `34_KONSISTENZPRUEFUNG_ALLE_REITER`
(10.08.) · `35_PREISPUNKTE_BEFUELLUNG` (10.08.) ·
`36_KORRELATION_EMPFEHLUNG_REVIEW` (11.08.) · `38_UEBERGABE` (12.08.) ·
`39_NACHTRAG` (12.08.) · `40_UEBERGABE` (13.08.) · `41_REVISION` (15.08.) ·
`42_TREIBER_SCHAERFEN` (17.08.) · **`43` — diese Datei** (18.08.).

Wer neu einsteigt, liest in dieser Reihenfolge: diese Datei, dann 42 (wohin es
gehen soll), dann 41 (was zuletzt kaputt war), dann die Docstrings der drei
Dateien, die er anfassen will. Die Docstrings sind in diesem Projekt keine
Zusammenfassung des Codes, sondern das Protokoll seiner Entscheidungen — sie
sind fast immer die ergiebigere Quelle als der Code darunter.
