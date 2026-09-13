# 45 — Projektdokumentation: ERGO LLM-Sichtbarkeits-Cockpit

**Stand 13.09.2026.** Dieses Dokument beschreibt das Projekt als Ganzes: warum
es existiert, was es misst, wie es gebaut ist, was es bisher herausgefunden hat
und wie man es betreibt. Es ist der Einstieg — die beiden anderen Dokumente
gehen tiefer beziehungsweise näher an den Tagesbetrieb.

---

## 0 · Leseanleitung

| Wenn Sie … | dann lesen Sie |
|---|---|
| das Projekt zum ersten Mal verstehen wollen | **dieses Dokument (45)** |
| wissen wollen, wie eine Kennzahl technisch entsteht, welches Modell wie rechnet | [43_TECHNISCHE_DOKUMENTATION.md](43_TECHNISCHE_DOKUMENTATION.md) (Stand 18.08.2026) |
| das System übernehmen und morgen früh bedienen müssen | [44_UEBERGABE.md](44_UEBERGABE.md) (Betriebsstand, wird laufend fortgeschrieben) |
| die Vorgeschichte der Treiber-Analyse suchen | [42_TREIBER_SCHAERFEN_2026-08-17.md](42_TREIBER_SCHAERFEN_2026-08-17.md) |
| das Cockpit erstmalig aufsetzen wollen | [README.md](README.md) (Deployment-Anleitung) |

**Zur Arbeitsteilung der Dokumente:** 45 ist strukturell und ändert sich selten.
44 ist datiert und ändert sich oft. 43 ist technisch und ändert sich, wenn die
Rechenwege sich ändern. Wo Zahlen in 45 stehen, sind sie als Größenordnung und
mit Datum zu lesen — die gültige Zahl steht immer im Dashboard, nie in einer
Dokumentation.

---

## 1 · Worum es geht

### 1.1 Die Ausgangsfrage

Kundinnen und Kunden recherchieren Versicherungen zunehmend nicht mehr über eine
Trefferliste, sondern über eine Antwort. Wer ChatGPT, Gemini oder Perplexity
fragt „Welche Zahnzusatzversicherung ist gut?", bekommt drei bis acht Namen
genannt — und ERGO ist in dieser Antwort entweder dabei oder nicht. Anders als
bei Google gibt es keine zweite Seite.

Daraus folgt die Frage, die dieses Projekt beantwortet:

> **Wie sichtbar ist ERGO in den Antworten großer Sprachmodelle, wie verändert
> sich das, und welche unserer Maßnahmen wirken darauf?**

### 1.2 Was das Projekt ausdrücklich nicht ist

- **Keine SEO-Messung.** Gemessen werden Modellantworten, nicht Rankings.
- **Kein Kausalbeweis per Konstruktion.** Das System beobachtet einen Markt, in
  dem es keine Kontrollgruppe gibt. Es rechnet mit der bestmöglichen Methodik
  gegen dieses Problem an und benennt offen, wo die Grenze liegt.
- **Keine Kampagnensteuerung.** Es liefert Befunde und Priorisierung; die
  Umsetzung passiert in den Fachbereichen.

### 1.3 Adressaten

Primär Marketing und Direktvertrieb bei ERGO. Das Dashboard ist so gebaut, dass
die oberste Ebene jedes Blocks ohne Statistikkenntnisse lesbar ist und die
Methodik im Aufklapper darunter liegt. Jede Aussage, die eine Wertung enthält,
wird zur Laufzeit aus den Daten abgeleitet — sie kippt mit, wenn die Zahlen
kippen.

---

## 2 · Was gemessen wird

### 2.1 Der Messgegenstand

Der eigene Crawl stellt Sprachmodellen echte Kundenfragen und wertet die
Antworten aus. Umfang des laufenden Messaufbaus:

| Dimension | Umfang |
|---|---|
| Produktlinien | 13 (Zahnzusatz, Berufsunfähigkeit, Kfz, Hausrat, Haftpflicht, Rechtsschutz, Reise, Risikoleben, Unfall, Sterbegeld, Krankenhauszusatz, Betriebshaftpflicht, Firmenrechtsschutz) |
| Fragen (Prompts) | 383, je Produktlinie 28–30 |
| Aktive Engines | 3: Gemini 2.5 Flash, GPT-4o mini, Perplexity Sonar |
| Konfiguriert, aber aus | Claude, Grok, Google AI Overview, Google AI Mode |
| Beobachtete Marken (Crawl) | ERGO + 7 Wettbewerber (Allianz, AXA, Generali, HUK-Coburg, Signal Iduna, CosmosDirekt, DKV) |
| Marken im Auswertungs-Panel | 26 (inkl. der über Peec erfassten) |
| Geprüfte URLs je Lauf | rund 2.660 |

### 2.2 Die Kennzahlen

| Kennzahl | Bedeutung |
|---|---|
| **Share of Voice (SoV)** | Anteil der eigenen Nennungen an allen Marken-Nennungen über alle Antworten. Die Leitkennzahl. |
| **Zitatrate** | Anteil der Antworten, in denen eine markeneigene Domain als Quelle verlinkt wird. |
| **Appearance Rate** | Anteil der Antworten, in denen die Marke überhaupt vorkommt. |
| **Durchschnittsrang** | Wie weit vorne in der Aufzählung die Marke genannt wird. |
| **Zitatanteil (cite_share)** | Zitate der eigenen Domains / alle Zitate eines Themas. Der wichtigste Treiber im Modell. |

### 2.3 Die zwei Kanäle — und warum die Unterscheidung zählt

Die Engines verhalten sich grundverschieden, je nachdem ob sie während der
Antwort im Web suchen:

- **grounded** (Gemini, Perplexity): sucht live, zitiert Quellen. Hier zählt,
  was im Netz auffindbar und zitierfähig ist.
- **ungrounded** (ChatGPT ohne Websuche): antwortet aus dem Modellwissen. Hier
  zählt, was zum Trainingszeitpunkt im Netz stand und wie oft.

Fast jeder Befund dieses Projekts fällt in den beiden Kanälen unterschiedlich
aus. Wer eine Zahl weitergibt, muss den Kanal mitnennen — das ist die häufigste
Fehlerquelle beim Zitieren aus dem Cockpit.

---

## 3 · Architektur

### 3.1 Zwei Repositories, klare Rollen

| Repo | Rolle | Schreibt | Liest |
|---|---|---|---|
| `phoeser/geo-visibility-tool` | **Messung.** Fragt die Modelle, crawlt Seiten, klassifiziert Änderungen | `data/runs/*.json` | Prompt-Dateien, `config.json` |
| `phoeser/LLM-Cockpit` | **Auswertung und Anzeige.** Rechnet Modelle, baut das Dashboard, liefert aus | `data/*.json`, `index.html` | die Messdaten aus dem GEO-Repo |

Die Grenze ist bewusst: Messung und Auswertung sind getrennt, damit ein Fehler
in der Auswertung nie die Rohdaten beschädigt. Der Weg über die Repo-Grenze
läuft über ein Lese-Token (`GEO_REPO_TOKEN`, nur `Contents: Read`).

### 3.2 Der Weg einer Zahl

```
Prompt-Datei  →  Engine-Antwort  →  runs/<ID>.json   (GEO-Repo)
                                         ↓
                        Nightly holt latest.json ab
                                         ↓
        correlation_impact.py + Sammler → data/*.json   (Cockpit-Repo)
                                         ↓
              dashboard_template.html + Snapshot eingebettet
                                         ↓
                 StatiCrypt-Verschlüsselung → index.html
                                         ↓
                      GitHub Pages, passwortgeschützt
```

### 3.3 Das Runtime-Nachlade-Muster

`dashboard_template.html` ist rund 13,3 MB groß und lässt sich über den
GitHub-Konnektor nicht schreiben. Deshalb liegen fast alle jüngeren Bausteine
als eigenständige JS-Module daneben, die sich zur Laufzeit selbst in die Seite
einhängen. Geladen werden sie in Kette aus `health_banner.js` — diese Datei ist
auf jeder Dashboard-Variante eingebunden und braucht keinen Template-Edit.

Die Kette: `health_banner.js` → `nav_redesign.js` → `soho_tab.js` →
`linkedin_tab.js` → `instagram_tab.js`. Die Reihenfolge ist nicht beliebig: das
Instagram-Modul hängt seinen Knopf hinter den LinkedIn-Knopf und fällt nur
ersatzweise ans Reiter-Ende zurück.

### 3.4 Auslieferung und Zugriffsschutz

Das Dashboard liegt auf GitHub Pages unter
`https://phoeser.github.io/LLM-Cockpit/` und ist mit StatiCrypt
passwortverschlüsselt (Secret `DASHBOARD_PASSWORD`). Das Repo ist öffentlich,
der Inhalt nicht lesbar — diese Konstruktion spart eine GitHub-Pro-Lizenz.

---

## 4 · Die Datenquellen

Das Cockpit führt sieben unabhängige Quellen zusammen. Keine davon ist für sich
ausreichend; die Aussagekraft entsteht aus dem Abgleich.

| Quelle | Was sie liefert | Takt | Ablage |
|---|---|---|---|
| **Eigener GEO-Crawl** | SoV, Zitate, Antworttexte, Seitenänderungen | wöchentlich Mo | `data/geo_snapshot.json`, `sov_history.jsonl` |
| **Peec** | zweite, unabhängige Sichtbarkeitsmessung; Quellen-Snapshots, Funnel-Segmente | täglich | `data/peec_*.json/.csv`, `data/peec_snapshots/` |
| **Check24** | Marktpreise und Portal-Bewertungen der Wettbewerber | wöchentlich Mo | `data/price_comparison.json`, `price_history.jsonl` |
| **Presse-Feed** | Presse- und News-Erwähnungen je Marke | täglich | `data/press_data.json`, `press_history.json` |
| **LinkedIn / Instagram** | eigene Social-Aktivität als Ereignisstrom | täglich | `data/linkedin_posts.jsonl`, `instagram_posts.jsonl` |
| **Google Reviews (Berater)** | Bewertungen der Vertriebsorganisation | wöchentlich So | `data/berater_reviews.json` |
| **Externe Ratings** | Testurteile und Siegel | monatlich | `data/ratings_external.json` |

Dazu ein monatlicher Sitemap-Crawl aller Anbieter-Domains
(`data/providers.json`, `sitemaps/`), der die Seitenbestände vergleichbar hält.

### 4.1 Warum zwei Sichtbarkeitsmessungen

Der eigene Crawl und Peec messen dasselbe mit unterschiedlicher Methode. Wenn
beide in dieselbe Richtung zeigen, ist ein Befund belastbar; wenn nicht, ist
zuerst die Messung verdächtig, nicht der Markt. Der Abweichungsvergleich steht
im Reiter „LLM-Sichtbarkeit" zwischen beiden Quellen.

---

## 5 · Taktung und Workflows

### 5.1 Repo `LLM-Cockpit`

| Workflow | Zweck | Takt (UTC) |
|---|---|---|
| `nightly-update.yml` | Alle Sammler, Auswertung, Dashboard-Neubau | täglich 05:30 (läuft real ~06:29, 30–45 min) |
| `peec-daily-sources.yml` | Peec-Quellen und Snapshot | täglich 04:00 |
| `pipeline-waechter.yml` | Frischeprüfung, füllt `pipeline_health.json` | täglich 09:00 |
| `weekly-prices.yml` | Check24-Preise und Bewertungen | montags 05:45 |
| `berater-reviews.yml` | Google Reviews der Berater | sonntags 05:00 |
| `monthly-urls.yml` | Sitemap-Crawl der Anbieter | 1. des Monats 06:45 |
| `monthly-ratings-research.yml` | Ratings-Recherche | 1. des Monats 02:00 |
| `dashboard-deploy.yml` | Auslieferung | **nur manuell** |
| `apply-patch.yml` | Patches aus `patches/` anwenden | **nur manuell** |
| `georg-sync.yml`, `berater-update.yml`, `measure-serp-depth.yml` | Sonderläufe | manuell |

### 5.2 Repo `geo-visibility-tool`

| Workflow | Zweck | Takt (UTC) |
|---|---|---|
| `analyze.yml` | Der eigentliche Messlauf | **wöchentlich, Montag 23:10** |
| `backfill.yml`, `revert-backfill.yml` | Historische Nachträge | manuell |
| `search-ab-test.yml` | Websuche-A/B-Experiment | manuell |

### 5.3 Drei Regeln zur Taktung, die immer wieder Ärger machen

1. **Der Messlauf ist wöchentlich, nicht täglich.** Entscheidung Pauls vom
   18.07.2026 aus Kostengründen. Das Dashboard aktualisiert sich täglich —
   die *Messung* dahinter aber nicht.
2. **Ein Zusatzlauf am selben Kalendertag bringt keinen neuen Messtag.**
   Messtage zählen je Kalendertag. Wer die Statistik beschleunigen will, muss
   an einem anderen Tag laufen lassen.
3. **Der Deploy löst nicht automatisch aus.** Bot-Commits triggern ihn nicht.
   Nach jedem Patch muss „Dashboard ausliefern" von Hand gestartet werden,
   sonst sieht niemand die Änderung.

---

## 6 · Die Auswertung

Die Rechenlogik liegt in `scripts/correlation_impact.py` (Cockpit-Repo) und
schreibt eine einzige Datei: `data/correlation_impact.json`. Deren Struktur ist
gleichzeitig die Gliederung der Analyse. Die mathematischen Details stehen in
Doku 43, Kapitel 4; hier steht, **welche Frage welcher Block beantwortet**.

### 6.1 Ebene 1 — Wirkt ein einzelnes Ereignis?

**Frage:** Bringt eine Pressemitteilung, eine neue Seite, eine Seitenänderung,
ein Post kurzfristig Sichtbarkeit?

**Methode:** Ereignis-Studie auf Tagesintervallen. Je Marke und Intervall wird
die Änderungsrate des SoV gegen die Ereigniszahl im selben Fenster gestellt,
markenweise zentriert, cluster-robust je Marke, mit Wild-Cluster-Bootstrap und
FDR-Korrektur über die Treiberfamilie.

**Erweiterungen:** Ko-Okkurrenz (treten Treiber gemeinsam auf?), Dosis-Wirkung
(bringt die zwanzigste Pressemitteilung so viel wie die erste?),
Versatz-Analyse (wirkt es mit Verzögerung?), Entrauschung (grounded-only,
Wochenmittel), Änderungsart je Seitenänderung.

### 6.2 Ebene 2 — Was erklärt das Niveau?

**Frage:** Nicht „was bewegt heute", sondern „warum liegt eine Marke überhaupt
dort, wo sie liegt".

**Methode:** Niveau-Modell nach Mundlak/CRE auf Zellen aus Marke × Thema. Der
Effekt wird zerlegt in

- **within** — dieselbe Marke über ihre Themen hinweg. Die sauberere
  Identifikation, weil markenfeste Eigenschaften herausfallen.
- **between** — der Vergleich zwischen Marken. Aussagekräftig für das
  Marktmuster, aber niemals kausal: günstige Anbieter unterscheiden sich auch
  in Größe, Vertrieb und Bekanntheit.

Treiber sind Zitatanteil (`cite_share`), Markengröße und Relativpreis — im
Verbundmodell `full_joint` kontrollieren sie einander.

### 6.3 Ebene 3 — Das Preis-Modell

Ein eigener Block (`price_level_pooled`), weil die Preisdaten einen anderen
Takt haben und seit dem Strukturbruch vom 19.08.2026 (DKV als eigene Marke)
über saubere Tage gepoolt werden. Stand 13.09.: fünf Messtage, 23.08.–08.09.

### 6.4 Gütesicherung

Das ist der Teil, der das Projekt von einer Auswertung zu einem belastbaren
Instrument macht:

| Prüfung | Was sie leistet | Stand 13.09. |
|---|---|---|
| **Placebo-Test** | Zufallsdaten dürfen kaum „gesicherte" Effekte erzeugen | Falsch-Positiv-Rate 2,6 % (erwartet ~5 %) |
| **Out-of-Sample** | Sagen die Treiber den SoV besser voraus als die reine Marken-Basislinie? | r² = −0,026 — **nein**, die Treiber schlagen die Basislinie nicht |
| **Wild-Cluster-Bootstrap** | Korrigiert zu optimistische Standardfehler bei wenigen Marken | fester Seed 42, 4.095 Ziehungen, reproduzierbar |
| **FDR (Benjamini-Hochberg)** | Verhindert Zufallsfunde beim Vieltesten | über die Testfamilie je Modellblock |
| **Strukturbruch-Filter** | Schneidet Intervalle heraus, in denen sich die Messung selbst geändert hat | 6 dokumentierte Brüche, 28 Intervalle übersprungen |
| **Leave-one-out** | Hängt ein Effekt an einer einzelnen Marke? | je Between-Effekt ausgewiesen |

Der Out-of-Sample-Wert ist bewusst so stehengelassen und nicht geschönt. Er
sagt: Die kurzfristigen Ereignis-Treiber erklären den SoV **nicht** besser als
die schlichte Annahme „jede Marke bleibt ungefähr, wo sie ist". Das ist kein
Fehler im Modell, sondern der zentrale inhaltliche Befund dieses Projekts —
siehe Kapitel 7.

---

## 7 · Der Befundstand

Alle Zahlen dieses Kapitels stammen aus `data/correlation_impact.json`
(erzeugt 13.09.2026, 11:16 UTC) und dem Messlauf `2026-09-08T13-14-40Z`
(Datenqualität green, Score 100, alle drei Engines mit frischen Daten).
Datenbasis der Panel-Auswertung: 68 Messtage vom 14.05. bis 08.09.2026,
700 Intervalle, 26 Marken.

### 7.1 Wo ERGO steht

| Marke | Share of Voice | Zitatrate | Nennungen |
|---|---:|---:|---:|
| Allianz | 33,76 % | 46,4 % | 1.839 |
| HUK-Coburg | 22,64 % | 32,1 % | 1.233 |
| **ERGO** | **12,06 %** | **15,2 %** | **657** |
| AXA | 11,99 % | 17,2 % | 653 |
| Signal Iduna | 7,60 % | 13,3 % | 414 |
| CosmosDirekt | 6,57 % | 7,2 % | 358 |
| DKV | 3,78 % | 1,4 % | 206 |
| Generali | 1,60 % | 2,8 % | 87 |

**Zur Lesart des dritten Platzes:** Der Abstand zu AXA sind vier Nennungen
(657 zu 653). Das ist Tagesrauschen, kein Überholen — und es entsteht durch
einen AXA-Rückgang, nicht durch ERGO-Zuwachs. So und nicht anders weitergeben.

**Die auffälligste Zahl** ist nicht der SoV, sondern die Zitatrate: ERGO wird
in 15,2 % der Antworten als Quelle verlinkt, die Allianz in 46,4 %. Das ist ein
Faktor drei und deckt sich mit dem, was das Niveau-Modell als Haupttreiber
ausweist.

### 7.2 Woraus der Abstand zur Allianz besteht

Zerlegung des Rückstands im grounded-Kanal, aus dem Drei-Treiber-Modell
(alle Treiber kontrollieren einander), über fünf saubere Tage gemittelt:

| Bestandteil | Beitrag |
|---|---:|
| Gesamtabstand ERGO → Allianz | **18,99 pp** |
| davon Autorität | 15,42 pp |
| — Quellpräsenz (Zitatanteil) | 4,46 pp |
| — Markengröße | 10,96 pp |
| davon Preis | 0,75 pp |
| unerklärter Rest | 2,82 pp |

Im ungrounded-Kanal ist der Abstand größer (24,70 pp) und die Gewichte drehen
sich: dort erklärt die Quellpräsenz 14,61 pp und die Größe nur 6,83 pp. Das ist
plausibel — ein Modell ohne Websuche kennt nur, was oft genug im Trainingsnetz
stand.

**Die praktische Übersetzung:** Rund vier Fünftel des Rückstands hängen an
Autorität, und der Teil davon, den man beeinflussen kann, ist die Quellpräsenz.
Markengröße lässt sich nicht kampagnenweise ändern; Zitierfähigkeit schon.

### 7.3 Der Hebel, der trägt

**Quellpräsenz (Zitatanteil) ist der einzige Treiber, der die Prüfungen
übersteht** — und auch er nicht in jedem Kanal:

| Kanal | Effekt je 1 Standardabweichung | p | q (FDR) |
|---|---:|---:|---:|
| ungrounded, within | **+6,22 pp** | 0,0085 | **0,0319** |
| ungrounded, between | +6,76 pp | 0,0046 | **0,0230** |
| combined, within | +2,96 pp | 0,0554 | 0,0871 |
| grounded, within | +1,75 pp | 0,0398 | 0,0746 |

Der oft zitierte Wert „rund +6 pp je Standardabweichung" ist der
**ungrounded**-Kanal. Im grounded-Kanal ist derselbe Treiber viel kleiner und
nach FDR-Korrektur nicht gesichert. Wer die Zahl weitergibt, muss den Kanal
dazusagen.

Zusätzlich gesichert ist die **Markengröße** im Between-Vergleich (grounded
+8,10 pp je SD, q = 0,003) — kein Hebel, sondern eine Randbedingung.

### 7.4 Was nicht wirkt — und warum das der wichtigste Befund ist

**Kein einziger Kurzfrist-Treiber ist gesichert.** Nicht Pressemitteilung,
nicht neue Seite, nicht Seitenänderung, nicht Bewertung, nicht LinkedIn- oder
Instagram-Post, nicht Portal-Rangänderung, nicht Wikipedia-Änderung. Das gilt

- über alle getesteten Zeitversätze,
- nach Entrauschung (nur grounded, Wochenmittel statt Tagesmittel),
- in der Dosis-Wirkungs-Rechnung (0 von 8 gesichert nach FDR),
- und es wird durch den Out-of-Sample-Test gestützt (r² = −0,026).

Für die Presse gibt es dafür eine **belegte Erklärung**: Von 2.990 erfassten
Presse- und News-Ereignissen liegen nur 212 — **7,1 %** — auf Domains, die von
den Sprachmodellen überhaupt zitiert werden. Die übrigen 93 % erscheinen in
Fachpresse- und PR-Kanälen, die in keiner Modellantwort auftauchen. Eine
Wirkung, die nicht messbar ist, weil der Kanal nicht gelesen wird, ist keine
schwache Wirkung — sie ist keine.

**Die Konsequenz für die Steuerung:** Sichtbarkeit in LLM-Antworten entsteht
nicht aus Aktivität, sondern aus Bestand. Nicht „was haben wir diese Woche
veröffentlicht", sondern „auf welchen zitierfähigen Quellen stehen wir".

### 7.5 Der Preis

Der Preis-Effekt ist der methodisch heikelste Block, weil drei Zahlen
unterschiedliche Dinge sagen:

| Sicht | Wert | Aussage |
|---|---|---|
| **Marktmuster, roh** | −8,63 SoV-Punkte je Preiseinheit, Streuung 0,68, an allen fünf Tagen gleiches Vorzeichen | Günstigere Marken sind sichtbarer. Stabil, aber ohne Kontrollen — kein Kausalnachweis. |
| **Eigener Effekt, alle Engines** | −0,75 pp je 1 SD, p = 0,2205, q = 0,3307 | trägt nicht |
| **Eigener Effekt, Kanal mit Websuche** | −1,49 pp je 1 SD, p = 0,0154, **q = 0,0462** | seit dem fünften Messtag (08.09.) erstmals auch nach FDR-Korrektur gesichert |

Das Dashboard formuliert diesen Zwischenzustand seit dem 08.09. selbst: ein
gesicherter Einzelkanal, keine Bestätigung im Mittel, „ein Kanal allein ist ein
starker Hinweis, kein Beweis". Der Satz ist aus der JSON abgeleitet, nicht
getextet — kippt einer der Werte, kippt er mit.

### 7.6 Der Tarifrechner-Befund

Aus der Produktlinien-Analyse vom September, belegt durch Live-Abruf:

- In **allen 13 gemessenen Produktlinien** gibt es keine einzige zitierte
  ERGO-Seite mit Preisbezug. 973 Zitate zu Preisfragen gehen an fremde Quellen
  (check24, verivox, finanztip, test.de).
- Die ERGO-Abschlussstrecken sind doppelt verriegelt: per `robots.txt` gesperrt
  (`/ecapp*`, `/ecsp*`, `/webforms/`) **und** technisch leer — ein Crawler
  bekommt rund 47 Zeichen sichtbaren Text.
- Die Allianz macht es anders: eine indexierbare Beitrags-Seite vor dem
  Rechner, mit Preislogik im Text. `/risikolebensversicherung/beitrag` zählt
  227 Zitate; dieselbe Strecke liefert rund 27.700 Zeichen sichtbaren Text.

Daraus folgt die Empfehlung, die derzeit beim Content-Team liegt: eine
öffentliche, indexierbare Preis-Erklärseite vor jeden Rechner — nicht den
Rechner selbst öffnen.

---

## 8 · Das Dashboard

### 8.1 Aufbau

Die Navigation hat drei Ebenen: die Hauptreiter, ein Dropdown
„Anbieter-Webseiten" mit den zehn Wettbewerber-Reitern, und innerhalb jedes
Reiters aufklappbare Blöcke für die Methodik.

| Reiter | Inhalt |
|---|---|
| **Übersicht** | Kernzahlen, Ampel, Verlauf |
| **LLM-Sichtbarkeit** | SoV beider Quellen (Peec führend, eigener Crawl als zweite Quelle), Abweichungsanalyse, Wirkung & Hebel, Kreuz-Matrix |
| **Korrelationsanalyse** | Die komplette Auswertung aus Kapitel 6 — oben die Antwort, darunter fünf benannte Aufklapper |
| **Content Änderungen** | Zitierte eigene Seiten, externe „Berichte über uns", Seitenänderungen |
| **Empfehlungen** | Priorisierte Maßnahmenliste mit Rangfolge |
| **Presse** | Presse- und News-Erwähnungen, Zuordnung zu zitierten Quellen |
| **Preisvergleich** | Check24-Marktpreise und Preisniveau-Modell |
| **Bewertungen / Ratings / Berater** | Portal-Bewertungen, Testurteile, Google Reviews |
| **LinkedIn / Instagram / SOHO** | Social-Aktivität und Gewerbe-Segment |
| **Segmente / Quellen / Q&A / Dokumentation** | Funnel-Stufen, Zitatquellen, Prüffragen, Methodik |
| **Anbieter-Webseiten ▾** | zehn Wettbewerber-Reiter |

### 8.2 Die Runtime-Module

| Datei | Reiter / Block |
|---|---|
| `health_banner.js` | Frische-Banner **und Loader der Kette** |
| `nav_redesign.js` | Navigation, Reiter-Umbenennung, Anbieter-Dropdown |
| `geo_wirkung.js` | LLM-Sichtbarkeit: Wirkung & Hebel |
| `korrelation_upgrade.js` | Korrelationsanalyse |
| `content_citations.js` | Content: zitierte Seiten, externe Berichte |
| `gap_waterfall.js` | Ursachenanalyse „Warum liegt der Marktführer vorn?" |
| `level_model_chart.js`, `footprint_chart.js`, `citation_channels.js` | Grafiken im GEO-Reiter |
| `price_compare.js` | Preisvergleich |
| `massnahmen_liste.js`, `empfehlungen_dynamic.js` | Empfehlungen |
| `linkedin_tab.js`, `instagram_tab.js`, `soho_tab.js` | eigenständige Reiter |
| `search_ab_block.js` | Websuche-A/B im Korrelations-Reiter |
| `geo_doku_tab.js` | Reiter „Dokumentation" |
| `overview_upgrade.js` | Übersicht |
| `georg_widget.js` | Sprach-Agent |

### 8.3 Gestaltungsregeln

Diese Regeln sind aus konkreten Überarbeitungen entstanden und gelten weiter:

1. **Antwort zuerst, Methode danach.** Oben in jedem Block steht ein Satz in
   Klartext; alles Rechnerische liegt im Aufklapper.
2. **Lange Listen sind scrollbar,** nicht endlos. Container mit
   `max-height` und Sticky-Kopfzeile. Der UX-Durchgang vom 08.09. hat den
   Content-Reiter von 14.200 auf 7.100 px, die Maßnahmenliste von 12.900 auf
   940 px und den Korrelations-Reiter von 9.400 auf 4.300 px gebracht — ohne
   dass etwas gelöscht wurde.
3. **Keine eingefrorenen Zahlen.** Fehlt ein Wert, steht dort „keine Angabe"
   **mit Grund** — nie eine Null, nie ein Ersatzwert.
4. **Wertende Sätze werden abgeleitet, nicht getextet.** Damit sie mitkippen,
   wenn die Daten kippen.

---

## 9 · Betrieb

### 9.1 Die drei Einspielwege

| Was | Weg | Warum |
|---|---|---|
| kleine oder neue Dateien | GitHub-Konnektor (`create_or_update_file`) | der Standardweg |
| große Dateien (`dashboard_v3.html`, ~480 KB; `dashboard_template.html`, 13,3 MB) | Patch-Skript nach `patches/`, dann Workflow „Patch anwenden" | der Konnektor kann sie nicht schreiben |
| Workflow-Dateien (`.github/workflows/`) | Chrome-Web-Editor | die GitHub-App hat keinen Workflow-Scope |

### 9.2 Das Patch-Muster

```python
# Kopf: Datum, was, warum. Idempotenz über eine Signatur aus dem NEUEN Text.
import base64, sys
s = open("dashboard_v3.html", "rb").read()
if b"<signatur aus dem neuen Code>" in s:
    print("SKIP: bereits angewendet"); sys.exit(0)
# Paare (alt, neu) base64-kodiert; jedes muss exakt 1x vorkommen
```

Der Workflow „Patch anwenden" führt alles in `patches/` aus, committet und
leert den Ordner. Er hat seit dem 27.08. eine Retry-Schleife (Rebase, drei
Versuche) gegen Push-Kollisionen.

**Pflichtschritte vor jedem Push:**

1. Ersetzungen lokal auf den aktuellen Repo-Stand anwenden.
2. Ergebnis **byte-genau** gegen die getestete Fassung prüfen
   (`git hash-object`, **immer mit absoluten Pfaden**).
3. Skript zweimal laufen lassen — der zweite Lauf muss `SKIP` melden.
4. Nach dem Anwenden: „Dashboard ausliefern" manuell starten.
5. Live-Stand prüfen (Salt-Abgleich in `index.html`).

### 9.3 Lokale Testumgebung

Das Dashboard lädt Tailwind und Chart.js per CDN; in der Sandbox ist das nicht
erreichbar. Deshalb eine lokale Testfassung mit eigenem `tailwind.css`
(v3-CLI, Content-Scan statt Safelist — die Safelist-Regex hängt) und
`chart.umd.js`. Playwright braucht einen expliziten Browser-Pfad:

```js
chromium.launch({
  executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
  args: ['--no-sandbox', '--disable-dev-shm-usage']
})
```

**Die CDN-Ersetzung ist ausschließlich für den Test.** Die Produktionsfassung
behält die CDN-Links — sonst wird eine kaputte Seite ausgeliefert. Testumbauten
müssen vor dem Patch-Bau zurückgenommen werden.

### 9.4 Überwachung

`pipeline-waechter.yml` prüft täglich um 09:00 UTC sechs Elemente gegen ein
maximales Alter und schreibt `data/pipeline_health.json`. Das Frische-Banner
im Dashboard liest diese Datei und blendet bei Überschreitung eine Warnung ein.

| Element | Datei | Maximalalter |
|---|---|---|
| GEO-Snapshot (SoV) | `data/geo_snapshot.json` | 9 Tage |
| SoV-Historie | `data/sov_history.jsonl` | 9 Tage |
| Korrelation/Impact | `data/correlation_impact.json` | 2 Tage |
| Sentiment-Export | `data/sentiment_dashboard.json` | 9 Tage |
| Event-Log | `shared/events.jsonl` | 3 Tage |
| Preise (Check24) | `data/price_comparison.json` | 9 Tage |

Stand 13.09.2026, 11:19 UTC: alle sechs frisch, keine ausgefallene Engine.

---

## 10 · Sicherheits- und Ehrlichkeitsregeln

Diese Regeln sind nicht dekorativ. Jede einzelne stammt aus einem Vorfall.

### 10.1 Schlüssel und Zugänge

1. **API-Schlüssel und Tokens werden nicht angefasst** — nicht gelesen, nicht
   kopiert, nicht „zum Prüfen" weitergereicht. Sie existieren ausschließlich
   als GitHub-Secrets. Betroffen sind SerpAPI, GitHub-PAT, Gemini, ElevenLabs,
   Peec, Google Places und Perplexity.
2. **Rotationen und Guthaben-Aufladungen macht Paul selbst**, mit direkter URL
   und Schritt-für-Schritt-Begleitung.
3. **Secrets werden in Dokumentation nur namentlich genannt**, nie mit Wert.

### 10.2 Aussagen über Ursachen

4. **Nie eine Ursache benennen, die nicht ausgeführt oder belegt ist.** Ende
   August fielen geplante Läufe tagelang aus; die naheliegende Vermutung war
   ein aufgebrauchtes Actions-Kontingent. Tatsächlich waren es bestätigte
   GitHub-Actions-Incidents am 26./27.08. — Billing zeigte 0 $ und
   unangetastete Included-Minuten. Anfang September sah es ähnlich aus und war
   diesmal wirklich ein Guthaben-Problem (Perplexity, HTTP 401
   `insufficient_quota`, belegt aus dem Run-JSON). Erst prüfen, dann behaupten.
5. **Bei roten Läufen: diagnostizieren und berichten** — nichts eigenmächtig
   ändern, was Messungen betrifft. Eine stillschweigend reparierte Messung ist
   ein Strukturbruch ohne Eintrag.
6. **Ein „Einbruch" ist nicht automatisch ein Einbruch.** Der SoV-Rückgang am
   01.09. war ein Messartefakt (`llms_state.perplexity = "fortgeschrieben"`),
   nachweisbar im Run-JSON.

### 10.3 Zahlen und Befunde

7. **Keine eingefrorenen Zahlen im Dashboard** — „keine Angabe" mit Grund statt
   Null oder Ersatzwert.
8. **Jede Zahl kommt zur Laufzeit aus einer JSON.** Auch wertende Texte werden
   aus Werten abgeleitet.
9. **Befunde ehrlich einordnen.** Ein signifikanter Einzelkanal ist kein
   Beweis; ein Rangwechsel um vier Nennungen ist kein Überholen; eine
   Korrelation ist keine Wirkung. Das Dashboard sagt das selbst — Berichte an
   Dritte sollten es auch tun.
10. **Strukturbrüche werden eingetragen, nicht geglättet.** Sechs sind
    dokumentiert; die Auswertung schneidet betroffene Intervalle heraus.

---

## 11 · Bekannte Grenzen

| Grenze | Worum es geht | Konsequenz |
|---|---|---|
| **Zirkularität im Niveau-Modell** | 66 % der Zitate stammen aus derselben Engine, die auch die Sichtbarkeit misst (4.871 Zitate, davon 3.210 gleiche Engine). Treiber und Zielgröße sind zwei Zusammenfassungen derselben Antworten. | Der Zusammenhang Zitatanteil → Sichtbarkeit ist zu einem unbekannten Teil Messartefakt. Im Dashboard ausgewiesen, darf nicht als reiner Befund gelesen werden. |
| **Peec-Fenster** | Peec-Zitatzahlen stammen aus einem rollierenden 30-Tage-Fenster; aufeinanderfolgende Snapshots überlappen sich. | Deltas zwischen Snapshots sind gedämpft, nicht tagesscharf. |
| **Presse-Deckung** | Nur 7,1 % der erfassten Presse-Ereignisse liegen auf zitierten Domains. | Der Presse-Kanal ist mit diesem Feed praktisch nicht messbar. Empfohlener Ersatz: externe Ereignisse aus den Zitat-Snapshots ableiten. |
| **LinkedIn-Untererfassung** | Sammler erfasst nicht alle Posts, Fund-Tag und Veröffentlichungstag fallen auseinander. | LinkedIn-Ereignisse sind zeitlich unscharf. |
| **Wöchentlicher Messtakt** | Ein Messtag je Woche | Statistische Aussagen wachsen langsam. Das Preis-Modell brauchte vom Strukturbruch bis zum ersten gesicherten Kanal fünf Wochen. |
| **Keine Kontrollgruppe** | Beobachtungsstudie in einem Markt | Kein Design der Welt macht daraus einen Kausalnachweis. Deshalb Placebo, Out-of-Sample und Leave-one-out. |
| **Explorative Versatz-Suche** | Wer acht Zeitversätze testet und den stärksten meldet, findet auch in reinem Rauschen etwas. | Der Block ist als explorativ gekennzeichnet und FDR-korrigiert. |
| **Robots-Treue** | Der Crawl respektiert `robots.txt` (`respect_robots_txt: true`). | Gesperrte Strecken erscheinen nicht — das ist gewollt und zugleich der Grund, warum der Tarifrechner-Befund überhaupt sichtbar wurde. |

---

## 12 · Chronik

Die wichtigsten Weichenstellungen, jeweils mit dem Grund:

| Datum | Ereignis |
|---|---|
| 15.07.2026 | Navigations-Redesign; Anbieter-Reiter ins Dropdown |
| 17./18.07. | Peec als führende Quelle konsolidiert; LLM-Sichtbarkeits-Reiter nach GEO-Metrik-Logik umgebaut |
| 18.07. | **Messtakt auf wöchentlich** gesetzt (Kostenentscheidung Pauls) |
| 20.07. | **DKV aus den ERGO-Aliasen entfernt** — vorher zählte jede DKV-Nennung als ERGO-Nennung (Lauf 17.07.: 343 → 288 Nennungen) |
| 21.07. | **Domain-Aliase zählen nicht mehr als Textnennung**; Nennungen und Zitate messen seither getrennte Dinge. Markenerweiterung des Crawls von 7 auf 25 Marken |
| 13.08. | Rückbau der Markenerweiterung auf 7; SOHO-Reiter |
| 15.08. | Perplexity liefert erstmals seit dem 06.08. wieder eigene Daten — grounded-Mix seither zweistufig |
| 18.08. | LinkedIn-Reiter; **Doku 43 geschrieben** (Stand dieser technischen Beschreibung) |
| 19.08. | **DKV wird eigene Marke** — Strukturbruch, ab dem das Preis-Modell poolt |
| 20.08. | Instagram-Reiter |
| 23.08. | 90-%-Sicht im Korrelations-Reiter (Richtungswahrscheinlichkeit, empirisches Bayes); Ko-Okkurrenz-Spalte; Presse-Query symmetrisch für ERGO und Wettbewerb; Presse-Zuordnung über Verlagsnamen (unbekannt 1.775 → ~344) |
| 26./27.08. | GitHub-Actions-Incidents — mehrere Läufe fielen aus, keine Projektursache |
| 27.08. | Externe „Berichte über uns"-Tabelle; Retry-Schleife in `apply-patch.yml` |
| 31.08. | Preisniveau-Block konsolidiert (Kurzantwort + zwei Karten, Tabelle in den Aufklapper); Fanout-Rate korrigiert (18 falsche Null-Tage waren eine Paging-Kappung) |
| 01.–08.09. | **Perplexity-Ausfall** (HTTP 401, aufgebrauchtes Guthaben); der scheinbare SoV-Einbruch am 01.09. war die Fortschreibung, kein Markteffekt |
| 08.09. | UX-Durchgang über alle Reiter; Korrelations-Reiter auf Klartext; Preis-Kernaussage um den FDR-gesicherten Einzelkanal erweitert |
| 08.09. | Guthaben aufgeladen, Perplexity wieder grün (Lauf `2026-09-08T13-14-40Z`, Score 100) |
| 11.09. | **GEO-Repo:** Executive Summary nutzt den konfigurierten Auswerte-LLM statt des abgeschalteten Claude-Clients (Commit `526cb679`) |
| 13.09. | Diese Projektdokumentation und die Übergabe-Datei |

---

## 13 · Offene Punkte

| Punkt | Stand 13.09.2026 | Nächster Schritt |
|---|---|---|
| **Executive-Summary-Fix** | 11.09. gepusht, lokal mit Fake-Client getestet; echter API-Aufruf steht aus | Verifikation am Montagslauf (Nacht zum 14.09.), Prüfung terminiert für 15.09. |
| **6. Messtag im Preis-Modell** | Wochenlauf in der Nacht zum 14.09. | Hält der grounded-Kanal unter q = 0,05? |
| **Produktlinien-Welle 1** | vier „Was kostet …"-Seiten empfohlen | liegt beim Content-Team |
| **Presse-Ersatzmetrik** | Befund dokumentiert (7,1 % Deckung), Umsetzung offen | Externe Ereignisse aus den Zitat-Snapshots ableiten statt aus dem Presse-Feed |
| **Wettbewerber-Erweiterung** | offene Entscheidung seit dem Rückbau am 13.08. | Bewusst entscheiden, ob 7 oder mehr Marken gecrawlt werden — jede Änderung ist ein Strukturbruch |
| **WhatsApp-GEOrg** | blockiert | wartet auf Meta-Business-Zugang |
| **Deploy-Seite Kosmetik** | HTTP 409 wird rot statt grün angezeigt | unkritisch, kein Termin |

### Was das Projekt als Nächstes wirklich braucht

Die Befundlage ist eindeutig genug für eine Priorisierung:

1. **Zitierfähige Preisinhalte** — der einzige Hebel, der im Modell trägt, und
   gleichzeitig die größte belegte Lücke (0 zitierte ERGO-Seiten mit
   Preisbezug in 13 Produktlinien).
2. **Presse-Ersatzmetrik** — solange 93 % der Presse-Ereignisse auf nicht
   zitierten Domains liegen, misst das Projekt dort nichts.
3. **Messtage sammeln** — mehrere Befunde stehen kurz vor der Nachweisgrenze.
   Jede Woche liefert genau einen Messtag; das ist die harte Schranke.

---

## 14 · Glossar

| Begriff | Bedeutung |
|---|---|
| **SoV (Share of Voice)** | Anteil der eigenen Nennungen an allen Marken-Nennungen |
| **grounded / ungrounded** | Engine sucht während der Antwort im Web / antwortet aus dem Modellwissen |
| **cite_share (Zitatanteil)** | Zitate der eigenen Domains / alle Zitate eines Themas |
| **Zelle** | Kombination Marke × Thema (× Tag) — die Beobachtungseinheit des Niveau-Modells |
| **within / between** | Vergleich innerhalb einer Marke über ihre Themen / Vergleich zwischen Marken |
| **Mundlak / CRE** | Modellansatz, der within- und between-Anteil sauber trennt |
| **Wild-Cluster-Bootstrap** | Verfahren für belastbare p-Werte bei wenigen Clustern (hier: 16 Marken) |
| **FDR / q-Wert** | Korrektur für Vieltesten nach Benjamini-Hochberg; q ist der korrigierte p-Wert |
| **Effekt je 1 SD** | Wirkung in Prozentpunkten, wenn der Treiber um eine Standardabweichung steigt |
| **Richtungswahrscheinlichkeit** | Bayes-Wahrscheinlichkeit, dass der Effekt das gezeigte Vorzeichen hat — **kein** Signifikanztest |
| **Strukturbruch** | Datierte Änderung an der Messung selbst; betroffene Intervalle werden ausgeschnitten |
| **Fanout / Websuch-Rate** | Anteil der Antworten, in denen die Engine tatsächlich im Web gesucht hat |
| **Peec** | Externer Anbieter, zweite unabhängige Sichtbarkeitsmessung |
| **StatiCrypt** | Verschlüsselung der statischen Seite; schützt das Dashboard im öffentlichen Repo |
| **Patch-Weg** | Einspielweg für Dateien, die der GitHub-Konnektor nicht schreiben kann |

---

## 15 · Wo finde ich was

### Repo `LLM-Cockpit`

| Pfad | Inhalt |
|---|---|
| `dashboard_template.html` | Unverschlüsseltes Template (13,3 MB), Basis jedes Laufs |
| `dashboard_v3.html` | Arbeitsfassung des Dashboards (~480 KB) — hier landen die Patches |
| `index.html` | Ausgelieferte, verschlüsselte Fassung |
| `*.js` (19 Module) | Runtime-Bausteine, siehe Kapitel 8.2 |
| `data/*.json`, `*.jsonl`, `*.csv` | Alle ausgewerteten Daten; `correlation_impact.json` ist die zentrale Auswertungsdatei |
| `data/peec_snapshots/` | Tägliche Quellen-Snapshots von Peec |
| `scripts/correlation_impact.py` | Die Analyse-Engine |
| `scripts/update_snapshot.py`, `scripts/encrypt.py` | Einbetten und Verschlüsseln |
| `shared/events.jsonl` | Der Ereignisstrom aller Treiber |
| `sitemaps/` | Sitemap-Bestände der Anbieter |
| `patches/` | Ablage für den Patch-Weg (wird nach dem Anwenden geleert) |
| `.github/workflows/` | Zwölf Workflows, siehe Kapitel 5.1 |

### Repo `geo-visibility-tool`

| Pfad | Inhalt |
|---|---|
| `data/config.json` | Marken, Produkte, Engines, Einstellungen — **die zentrale Stellschraube der Messung** |
| `data/prompts/*.json` | 383 Fragen in 13 Dateien |
| `data/runs/*.json` | Alle Messläufe, `latest.json` zeigt auf den jüngsten |
| `data/snapshots/`, `data/pages/` | Seitenbestände und Änderungsverfolgung |
| `analyzer/main.py` | Ablauf des Messlaufs |
| `analyzer/llm_clients.py` | Anbindung der Engines |
| `analyzer/impact_analysis.py` | Executive Summary und Wirkungsanalyse |
| `analyzer/diff_classifier.py` | Klassifikation von Seitenänderungen |
| `analyzer/web_scraper.py`, `sitemap_discovery.py`, `redirect_resolver.py` | Crawl-Infrastruktur |
| `analyzer/data_quality.py` | Ampel, Score, Engine-Zustände |

### Die Berichtsreihe

Nummerierte Markdown-Dateien im Cockpit-Repo. 42 ist die Treiber-Schärfung vom
August, 43 die technische Dokumentation, 44 die laufende Übergabe, 45 dieses
Dokument.

---

## 16 · Für den Fall, dass jemand Neues übernimmt

Die kürzeste sinnvolle Einarbeitung:

1. Dashboard öffnen, den Reiter **Korrelationsanalyse** lesen — er beantwortet
   in einem Satz, was das ganze Projekt herausgefunden hat.
2. **Kapitel 7** dieses Dokuments lesen — dort stehen dieselben Befunde mit
   Zahlen und Einschränkungen.
3. **44_UEBERGABE.md** lesen — Betriebsstand und Fallstricke.
4. Einen Nightly-Lauf in den GitHub-Actions ansehen, um den Ablauf einmal
   gesehen zu haben.
5. **43** erst dann, und nur die Kapitel, die gerade gebraucht werden.

Und die eine Regel, die wichtiger ist als alle anderen: **Was nicht ausgeführt
oder belegt wurde, wird nicht behauptet.** Das Projekt lebt davon, dass seine
Zahlen stimmen — auch dann, wenn sie unbequem sind. Der Out-of-Sample-Wert von
−0,026 steht genau deshalb offen im Dashboard.

---

*Fortschreibung: Wer dieses Dokument ändert, schreibt das Datum an die Aussage,
nicht nur oben in den Kopf. Fast jeder Fehler, der in diesem Projekt Zeit
gekostet hat, war ein Satz, der einmal richtig war und dann still falsch wurde.*
