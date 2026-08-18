# Die Treiber der LLM-Sichtbarkeit statistisch schärfer bekommen

**Stand 17.08.2026 · Datenbasis: 62 Messtage (14.05.–15.08.), 675 Intervalle, 25 Marken, 3 aktive LLMs**

## Wo wir stehen — ehrlich bilanziert

Das Modell hat heute genau einen strukturell gesicherten Treiber: die Quellpräsenz. Marken, die in den zitierten Quellen stärker vertreten sind, sind sichtbarer — +5,94 Prozentpunkte Sichtbarkeit je Standardabweichung, q = 0,002 nach FDR-Korrektur, über 25 Marken-Cluster, und der unabhängige Gegentest gegen Peec bestätigt die Größenordnung (r = 0,80 auf Markenebene). Das Preisniveau trägt als zweiter Befund: über 20 saubere Messtage durchgehend negativ (teurer = weniger sichtbar, Tagesmittel −4,34, vorzeichenstabil), aber als Between-Vergleich, der alles aufsammeln kann, was teure von günstigen Anbietern unterscheidet.

Auf der Ereignis-Seite ist dagegen **kein einziger Typ gesichert**: Presse +0,40 pp (69 Ereignis-Intervalle), News +0,17 pp (123), Seitenänderungen −0,16 pp (295) — alle Intervalle überspannen die Null. Die Placebo-Rate von 1,8 % zeigt, dass der Test ehrlich konservativ ist, und das Out-of-Sample-r² von −0,03 sagt klar: Für die **Tagesprognose** verbessern die Ereignis-Treiber heute nichts.

Wichtig für alles Weitere: Das ist kein Rechenfehler und kein Datenleck. Effekte von 0,2–0,4 pp gegen ein Tagesrauschen von rund 1 pp, verteilt auf wenige Dutzend Ereignis-Intervalle — das **kann** diese Messung noch nicht sichern. Es gibt exakt drei Auswege, und sie sind Arithmetik, keine Meinung: größere Effekte, mehr Beobachtungen, weniger Rauschen. Die sechs Hebel unten sortieren sich alle in diese drei Schubladen.

Genauso wichtig, was **nicht** fehlt: Methoden. Wild-Cluster-Bootstrap, FDR über korrekt benannte Familien, Leave-one-out, Mundlak-Zerlegung, Placebo- und Out-of-Sample-Validierung — die Statistik schöpft die vorhandene Datenmenge bereits aus. Der Engpass liegt im Messdesign und in den Daten, nicht im Verfahren.

## Hebel 1 — Das Maßnahmen-Tagging füllen (kostenlos, sofort, größter Einzelhebel)

Seit heute steht das Erfassungs-Panel im Korrelationsreiter. Was es braucht, ist Disziplin, keine Technik: Jede Kampagne, jeden Relaunch, jede PR-Aktion mit Datum eintragen — auch rückwirkend, der Kampagnenkalender der letzten Monate ist sofort verwertbares Material. Damit wandert die Frage von „korreliert X mit Y?" zu „was ist nach unserer Maßnahme passiert, verglichen mit den Wettbewerbern, bei denen nichts passierte?" — eine strukturell stärkere Frage bei identischer Datenlage.

Dazu eine Design-Empfehlung, die die Effektgröße direkt steuert (der einzige der drei Auswege, den ihr selbst in der Hand habt): Maßnahmen **bündeln statt tröpfeln**. Ein Thema, ein Stichtag, alles zusammen (Content, Schema.org, PR, Portale) erzeugt einen messbaren Sprung. Dieselbe Arbeit über acht Wochen verteilt verschwindet im Rauschen.

## Hebel 2 — Das Experiment ausweiten (der einzige kausale Pfad)

Das Websuche-A/B (150 Prompt-Paare, 2 Wiederholungen, 11 Produkte) ist der einzige Baustein mit Kausal-Stufe — und er ist ausbaufähig: mehr Wiederholungen je Prompt drücken die Varianz mit √n, die beiden SOHO-Themen fehlen noch (gerade dort, wo ChatGPT ERGO gar nicht kennt, wäre der Suche-Effekt am aufschlussreichsten), und derselbe Aufbau lässt sich auf eine zweite Engine spiegeln.

Die drei vorbereiteten Feld-Experimente in `interventions.json` (Rechtsschutz-Hub gegen Sterbegeld, BU-Onpage gegen Risikoleben, Zahnzusatz-Portale gegen Reise) sind das eigentliche Prunkstück dieses Ansatzes: ein behandeltes Thema, ein unbehandeltes Kontrollthema, ein Datum. Sobald das erste davon live geht, bekommt der Reiter seinen zweiten kausalen Befund.

## Hebel 3 — Rauschen an der Quelle senken (Prompts und Wiederholungen)

Der SoV eines Tages ist eine Stichprobe aus ~30 Prompts je Produkt. Das Sampling-Rauschen sinkt mit der Wurzel der Prompt-Zahl: doppelt so viele Prompts (oder jede Frage zweimal gestellt) senken das Rauschen um Faktor 1,4 — jeder Messtag wird präziser, ohne dass ein Tag mehr vergeht. Das ist der schnellste Weg, die Nachweisgrenze zu drücken, und eine reine Kostenfrage (API-Calls), keine Wartefrage. Die Rückkehr von Perplexity hilft hier bereits: drei Engines mitteln unabhängige Fehlerquellen weg.

## Hebel 4 — Eigene Frühindikatoren anschließen (neue Datenquelle mit dem besten Verhältnis von Aufwand zu Erkenntnis)

Alle heutigen Ereignistypen beobachten die **Außenwelt** (Presse, Reviews, Seitenänderungen der Wettbewerber). Was fehlt, sind die **eigenen** Stellgrößen: Die Google Search Console für ergo.de würde Impressionen und Klicks je Themenfeld liefern — ein Frühindikator, der Tage vor der LLM-Sichtbarkeit reagieren dürfte und direkt an die bestehende Themen-Struktur andockt. Gleiches gilt für den internen Media-/Kampagnenkalender (das ist letztlich Hebel 1 aus anderer Quelle) und, falls verfügbar, Werbedruck-Daten. Ein einziger wöchentlicher GSC-Export je Themenfeld genügt für den Anfang.

## Hebel 5 — Mehr Marken-Cluster (die offene Wettbewerber-Entscheidung)

Die Zahl unabhängiger Cluster ist der härteste Deckel auf der Ereignis-Statistik. ARAG, Gothaer, HDI und Hiscox werden bereits gecrawlt, zählen aber nicht in die Anteilsrechnung — die Entscheidung liegt bei dir, weil sie die Zeitreihe bricht. Der Bruch ist handhabbar (Strukturbruch-Datum dokumentieren, wie beim Umbau am 10.08. geschehen); der Gewinn sind vier zusätzliche Cluster und speziell im Gewerbe die relevanteren Vergleichsmarken (Hiscox!). Meine Empfehlung: mit dem SOHO-Bestandsaufnahme-Stichtag zusammenlegen, dann gibt es einen sauberen gemeinsamen Bruchpunkt.

## Hebel 6 — Die Wirkkette über Zitate messen statt nur das Endergebnis

Heute prüfen alle Ereignis-Modelle den direkten Sprung Ereignis → Sichtbarkeit. Die Wirkkette läuft aber plausibel über eine Zwischenstufe: Maßnahme → **Zitatanteil** → Sichtbarkeit. Der Zitatanteil (cited_sources, liegt je Messtag vor) reagiert vermutlich schneller und rauscht weniger als der SoV, und die zweite Kettenhälfte ist mit +5,94 pp/SD bereits gesichert. Ereignisse gegen den Zitatanteil zu rechnen — mit derselben Cluster-Maschinerie, die schon da ist — würde die Nachweisgrenze für die erste Kettenhälfte deutlich senken. Das ist die eine Modell-Erweiterung, die ich noch für lohnend halte; sie braucht keinen neuen Datenpunkt, nur einen Rechenlauf gegen eine andere Zielgröße.

Ergänzend auf der Auswerte-Seite: Das Wochen-Aggregat (die „Gegenprobe nach Entrauschung" existiert schon) sollte für Ereignis-Effekte zur Hauptdarstellung werden — seit der GEO-Crawl wöchentlich läuft, ist die Woche ohnehin der ehrliche Takt der Seiten-Ereignisse, und das Tagesmodell darf Drilldown bleiben.

## Priorisierung

Sofort und kostenlos: Hebel 1 (Kampagnenkalender rückwirkend eintragen — eine Stunde Arbeit, wirkt ab dem nächsten Nightly) und Hebel 6 (rechne ich, sobald du grünes Licht gibst). Kurzfristig mit kleinem Budget: Hebel 3 (Prompt-Wiederholungen) und Hebel 2 (A/B auf SOHO ausweiten, erstes Feld-Experiment datieren). Eine Entscheidung von dir: Hebel 5 (Wettbewerber in die Anteilsrechnung, idealerweise gebündelt mit dem SOHO-Stichtag). Mittelfristig der stärkste neue Datenstrom: Hebel 4 (Search Console).

Was ich bewusst **nicht** empfehle: weitere Statistik-Verfahren auf die heutige Datenmenge zu werfen. Jede zusätzliche Rechnung auf denselben 675 Intervallen erhöht die Zahl der Tests, nicht die der Erkenntnisse — die FDR-Korrektur würde den Zugewinn zu Recht wieder einkassieren.
