# Faktenblatt LLM-Sichtbarkeit — Wissensbasis fuer GEOrg

## Wie diese Auskunft zu gebrauchen ist

Dieses Faktenblatt beschreibt die Messung der Sichtbarkeit von Versicherungsmarken
in Antworten grosser Sprachmodelle. Es ist die einzige zulaessige Quelle fuer
Auskuenfte ueber diese Daten.

Vier Regeln gelten fuer jede Antwort daraus:

Erstens: Eine Zahl ohne ihren Vorbehalt ist eine falsche Antwort. Wo hier
"nicht nachweisbar" steht, darf der Effektwert nicht als Wirkung genannt werden,
auch wenn er im selben Satz steht.

Zweitens: "Nicht nachweisbar" heisst nicht "wirkt nicht". Es heisst, dass ein
Effekt dieser Groesse bei der heutigen Datenmenge nicht auffindbar waere. Der
Unterschied ist wesentlich und muss mitgesagt werden.

Drittens: Steht eine Zahl hier nicht, dann gibt es sie nicht. Sie darf nicht
geschaetzt, hergeleitet oder aus allgemeinem Wissen ergaenzt werden. Die
richtige Antwort lautet dann, dass das Cockpit diese Groesse nicht misst.

Viertens: Die Daten beschreiben Zusammenhaenge, keine Ursachen. Nur der eine
ausdruecklich als Experiment gekennzeichnete Befund darf als Wirkung bezeichnet
werden.


## Stand der Daten

Dieses Faktenblatt wurde am 14.08.2026 um 07:32 Uhr UTC erzeugt. Die Auswertung stammt vom 2026-08-14.

Gemessen wird seit 61 Messtagen, von 2026-05-14 bis 2026-08-13. Daraus entstehen 668 Intervall-Beobachtungen ueber 25 Marken.

Der eigene Crawl laeuft seit dem 10.08.2026 woechentlich statt taeglich, sonntags gegen 23:10 UTC. Presse, News und Bewertungen werden weiterhin taeglich erhoben. Wenn also in einer Tagesuebersicht an mehreren Tagen kaum Seiten-Ereignisse stehen, ist das der Normalzustand zwischen zwei Laeufen und kein Ausfall.

Alle 6 ueberwachten Bestandteile der Pipeline sind aktuell; keiner gilt als veraltet.


## Was die Sichtbarkeit treibt — die Kernaussage

Die kuerzeste ehrliche Zusammenfassung lautet: Ein einziger Treiber traegt fast alles, und er heisst Quellpraesenz. Damit ist nicht die Zahl der eigenen Seiten gemeint, sondern wie oft die Marke in dem vorkommt, was Sprachmodelle zitieren. Alle einzelnen operativen Massnahmen sind dagegen zu klein, um in dieser Messung ueberhaupt sichtbar zu werden.

**Quellpraesenz.** Marken mit hoeherer Quellpraesenz sind sichtbarer: +5,54 Prozentpunkte Sichtbarkeit je einer Standardabweichung mehr Zitations-Footprint, gerechnet ueber 25 Marken. Der Befund ist nach Korrektur fuer Mehrfachtests gesichert (Wild-Cluster-p 0,0007, q 0,0014). Es bleibt ein beobachteter Zusammenhang, kein Kausalnachweis: gemessen wurde, nicht eingegriffen.

**Der Abstand zum Marktfuehrer.** ERGO liegt bei 7,4 Prozent Sichtbarkeit, Allianz bei 17,5 Prozent. Der Abstand von 10,1 Prozentpunkten zerlegt sich naeherungsweise so: Quellpraesenz +8,5 Prozentpunkte (rund 85 Prozent des Abstands); Bekanntheit und Groesse +1,3 Prozentpunkte (rund 13 Prozent des Abstands); Preisniveau +0,3 Prozentpunkte (rund 3 Prozent des Abstands). Das ist eine Zerlegung, kein Kausalnachweis. Wichtig fuer die Einordnung: ein zweites Modell im selben Nightly teilt denselben Abstand etwas anders auf und schreibt der Groesse einen kleineren Anteil zu. Der Anteil der Groesse ist deshalb als Spanne zu verstehen, nicht als Punktwert. An der Kernaussage aendert das nichts: die Quellpraesenz traegt in beiden Modellen den weitaus groessten Teil.


## Der einzige kausal belegte Befund: die Websuche

Dies ist die einzige Stelle im gesamten Cockpit, an der eingegriffen und gegen eine Kontrollbedingung verglichen wurde — und damit die einzige, an der von Wirkung statt von Zusammenhang gesprochen werden darf.

Jeder von 150 Prompts lief zweimal: einmal mit erzwungener Websuche, einmal ohne jedes Werkzeug, sonst identisch. Mit Suche erreicht ERGO 8,9 Prozent Anteil an den Antworten, ohne Suche 3,1 Prozent. Der Unterschied betraegt +5,8 Prozentpunkte, das 95-Prozent-Intervall reicht von +3,2 Prozentpunkte bis +8,6 Prozentpunkte (p 0,0004).

Drei Einschraenkungen gehoeren zu diesem Befund und muessen mitgenannt werden, wenn danach gefragt wird. Erzwungene Suche ist nicht der Normalfall — im echten Betrieb entscheidet das Modell selbst, ob es sucht. Das Experiment lief auf einem anderen Modell als der laufende Messkanal, die Richtung ist uebertragbar, die Hoehe nicht eins zu eins. Und es gehoert ausdruecklich nicht in die Zeitreihe des Cockpits.


## Wo ERGO verliert: die Themen im Einzelnen

Ueber alle Themen und Marken hinweg gilt: je Prozentpunkt hoeherem Anteil an den zitierten Quellen liegt die Sichtbarkeit im Schnitt um 1,71 Prozentpunkte hoeher (Korrelation r 0,75 ueber 91 Marken-Thema-Zellen). Das ist ein beschreibender Zusammenhang aus dem Querschnitt, kein Versprechen fuer den Fall, dass ERGO seinen Zitatanteil erhoeht.

Je Thema, sortiert nach dem groessten Rueckstand zu Allianz:

- Firmen-Rechtsschutzversicherung: ERGO 19,7 Prozent Sichtbarkeit, Allianz 57,4 Prozent — Rueckstand 37,7 Prozentpunkte. Zitatanteil ERGO 0,0 Prozent, Allianz 23,7 Prozent.
- Berufsunfähigkeitsversicherung: ERGO 8,9 Prozent Sichtbarkeit, Allianz 45,6 Prozent — Rueckstand 36,7 Prozentpunkte. Zitatanteil ERGO 6,1 Prozent, Allianz 14,7 Prozent.
- Kfz-Versicherung: ERGO 3,8 Prozent Sichtbarkeit, Allianz 34,8 Prozent — Rueckstand 31,0 Prozentpunkte. Zitatanteil ERGO 0,0 Prozent, Allianz 12,5 Prozent.
- Privathaftpflichtversicherung: ERGO 1,1 Prozent Sichtbarkeit, Allianz 29,7 Prozent — Rueckstand 28,6 Prozentpunkte. Zitatanteil ERGO 0,0 Prozent, Allianz 13,6 Prozent.
- Unfallversicherung: ERGO 9,8 Prozent Sichtbarkeit, Allianz 35,9 Prozent — Rueckstand 26,1 Prozentpunkte. Zitatanteil ERGO 6,5 Prozent, Allianz 17,1 Prozent.
- Risikolebensversicherung: ERGO 12,3 Prozent Sichtbarkeit, Allianz 35,6 Prozent — Rueckstand 23,3 Prozentpunkte. Zitatanteil ERGO 11,7 Prozent, Allianz 17,3 Prozent.
- Rechtsschutzversicherung: ERGO 15,1 Prozent Sichtbarkeit, Allianz 37,4 Prozent — Rueckstand 22,3 Prozentpunkte. Zitatanteil ERGO 0,0 Prozent, Allianz 13,2 Prozent.
- Betriebshaftpflichtversicherung: ERGO 26,7 Prozent Sichtbarkeit, Allianz 46,7 Prozent — Rueckstand 20,0 Prozentpunkte. Zitatanteil ERGO 0,0 Prozent, Allianz 19,6 Prozent.
- Hausratversicherung: ERGO 9,2 Prozent Sichtbarkeit, Allianz 21,9 Prozent — Rueckstand 12,8 Prozentpunkte. Zitatanteil ERGO 0,0 Prozent, Allianz 12,8 Prozent.
- Zahnzusatzversicherung: ERGO 32,9 Prozent Sichtbarkeit, Allianz 43,0 Prozent — Rueckstand 10,1 Prozentpunkte. Zitatanteil ERGO 0,0 Prozent, Allianz 16,0 Prozent.
- Sterbegeldversicherung: ERGO 29,8 Prozent Sichtbarkeit, Allianz 33,1 Prozent — Rueckstand 3,2 Prozentpunkte. Zitatanteil ERGO 10,2 Prozent, Allianz 19,5 Prozent.
- Reiseversicherung: ERGO 35,1 Prozent Sichtbarkeit, Allianz 24,7 Prozent — ERGO liegt 10,4 Prozentpunkte vorn. Zitatanteil ERGO 12,6 Prozent, Allianz 5,1 Prozent.
- Krankenhauszusatzversicherung: ERGO 47,6 Prozent Sichtbarkeit, Allianz 3,4 Prozent — ERGO liegt 44,3 Prozentpunkte vorn. Zitatanteil ERGO 4,4 Prozent, Allianz 11,0 Prozent.

Die Lesart dieser Tabelle: Ein grosser Rueckstand bei zugleich sehr kleinem eigenem Zitatanteil deutet auf eine Content- und Quellenluecke hin — dort wird ERGO in den Quellen, aus denen die Modelle schoepfen, schlicht nicht gefunden. Ein Rueckstand bei bereits ordentlichem Zitatanteil hat eher andere Ursachen.


## Einzelne Ereignisse: warum hier nichts nachweisbar ist

Geprueft wurden 9 Ereignisarten daraufhin, ob sie die Sichtbarkeit kurzfristig bewegen: Pressemitteilungen, News-Erwaehnungen, neue Seiten, Seitenaenderungen, geloeschte Seiten, Bewertungs-Trend, Bewertungs-Volumen, Wikipedia-Ausbau und Portal-Rang. Davon ist keine einzige gesichert.

Der Grund dafuer ist rechnerisch und war vorher absehbar. Zu jeder Ereignisart gehoert eine Nachweisgrenze: die Effektgroesse, ab der ein echter Effekt bei der heutigen Datenmenge ueberhaupt auffindbar waere. Diese Grenzen liegen zwischen etwa 0,4 und 1,0 Prozentpunkten. Die tatsaechlich gemessenen Effekte liegen zwischen 0,03 und 0,56 Prozentpunkten — also durchweg darunter. Eine einzelne Pressemitteilung kann diese Messung nicht bewegen, unabhaengig davon, ob sie wirkt.

Die Einzelwerte, jeweils mit ihrem Urteil:

- Portal-Rang Check24 (±): nicht nachweisbar. Punktschaetzer -0,61 Prozentpunkte, 95-Prozent-Intervall von -9,35 bis +8,12 Prozentpunkten, beobachtet in 4 von 668 Intervallen ueber 2 Marken.
- Pressemitteilungen: nicht nachweisbar. Punktschaetzer +0,40 Prozentpunkte, 95-Prozent-Intervall von -0,30 bis +1,10 Prozentpunkten, beobachtet in 67 von 668 Intervallen ueber 9 Marken.
- Wikipedia-Ausbau (±): nicht nachweisbar. Punktschaetzer -0,31 Prozentpunkte, 95-Prozent-Intervall von -0,77 bis +0,14 Prozentpunkten, beobachtet in 4 von 668 Intervallen ueber 3 Marken.
- Neue Seiten: nicht nachweisbar. Punktschaetzer -0,30 Prozentpunkte, 95-Prozent-Intervall von -0,68 bis +0,09 Prozentpunkten, beobachtet in 62 von 668 Intervallen ueber 16 Marken.
- Bewertungs-Trend (±): nicht nachweisbar. Punktschaetzer -0,23 Prozentpunkte, 95-Prozent-Intervall von -0,82 bis +0,37 Prozentpunkten, beobachtet in 52 von 668 Intervallen ueber 8 Marken.
- Bewertungs-Volumen: nicht nachweisbar. Punktschaetzer -0,19 Prozentpunkte, 95-Prozent-Intervall von -1,05 bis +0,66 Prozentpunkten, beobachtet in 46 von 668 Intervallen ueber 7 Marken.
- News-Erwaehnungen: nicht nachweisbar. Punktschaetzer +0,19 Prozentpunkte, 95-Prozent-Intervall von -0,48 bis +0,85 Prozentpunkten, beobachtet in 117 von 668 Intervallen ueber 8 Marken.
- Seitenaenderungen (Wettbewerb): nicht nachweisbar. Punktschaetzer -0,17 Prozentpunkte, 95-Prozent-Intervall von -0,53 bis +0,20 Prozentpunkten, beobachtet in 292 von 668 Intervallen ueber 22 Marken.
- Geloeschte Seiten: nicht nachweisbar. Punktschaetzer -0,02 Prozentpunkte, 95-Prozent-Intervall von -0,53 bis +0,49 Prozentpunkten, beobachtet in 5 von 668 Intervallen ueber 3 Marken.

Nicht schaetzbar, mit Grund — diese Arten verschwinden nicht aus der Auswertung, sondern stehen mit ihrer Begruendung da:

- Domain-/Subdomain-Aenderungen: Cluster-robuste Schaetzung nicht moeglich (1 Marke(n) mit Ereignis, 25 Cluster insgesamt). Ohne Variation zwischen Marken laesst sich die Unsicherheit nicht ehrlich beziffern; die iid-Felder unterstellen Unabhaengigkeit, die hier nicht gegeben ist.
- Preis-Aenderungen (gemessen): 21 der 22 Preis-Ereignisse waren eine oszillierende Rueckkehr auf den Vorwert (Scraper-Artefakt) und wurden ausgeschlossen.

Zur Guete des Modells insgesamt: Die Vorhersagekraft der Treiber liegt bei R² -0,026 gegenueber einer reinen Marken-Basislinie — die Treiber verbessern die Vorhersage also nicht. Die Placebo-Rate betraegt 1,9 Prozent: so oft erzeugen reine Zufallsdaten einen scheinbar gesicherten Effekt. Erwartet waeren rund fuenf Prozent, der niedrigere Wert spricht fuer eine eher konservative Rechnung.


## Was es in die Zitate schafft

- ERGO: 55 von 1.099 getrackten Seiten sind in Zitaten aufgetaucht, also 5,00 Prozent. Das ist die eigene Marke.
- Allianz: 110 von 891 getrackten Seiten sind in Zitaten aufgetaucht, also 12,35 Prozent.
- ADAC: 16 von 647 getrackten Seiten sind in Zitaten aufgetaucht, also 2,47 Prozent.
- LV 1871: 28 von 537 getrackten Seiten sind in Zitaten aufgetaucht, also 5,21 Prozent.
- ARAG: 30 von 469 getrackten Seiten sind in Zitaten aufgetaucht, also 6,40 Prozent.
- HDI: 3 von 288 getrackten Seiten sind in Zitaten aufgetaucht, also 1,04 Prozent.
- Die Bayerische: 20 von 285 getrackten Seiten sind in Zitaten aufgetaucht, also 7,02 Prozent.
- R+V: 9 von 240 getrackten Seiten sind in Zitaten aufgetaucht, also 3,75 Prozent.

Drei Einschraenkungen zu diesen Quoten. Der Datenlieferant gibt nur die meistzitierten Seiten eines rollierenden Fensters heraus, der lange Schwanz selten zitierter Seiten fehlt — die Quoten sind deshalb Untergrenzen. Der Nenner ist die vom Crawl verfolgte Seitenauswahl je Marke, nicht die vollstaendige Website. Und dass eine Seite zitiert und eine Marke genannt wird, ist ein gemeinsames Auftreten, kein Nachweis, dass das eine das andere verursacht.


## Preise

Die Preise stammen aus einer Erhebung bei einem Vergleichsportal, je Produkt und Altersprofil. Drei Produkte — Haftpflicht, Hausrat und Rechtsschutz — sind bewusst altersunabhaengig, dort gilt derselbe Wert fuer alle Profile.

ERGO im Vergleich zur jeweils guenstigsten erhobenen Marke:

- Zahnzusatzversicherung: ERGO 37,80 Euro, guenstigster Anbieter 20,25 Euro — Faktor 1,87 ueber 6 erhobenen Marken.
- Risikolebensversicherung: ERGO 69,24 Euro, guenstigster Anbieter 56,73 Euro — Faktor 1,22 ueber 4 erhobenen Marken.
- Krankenhauszusatzversicherung: ERGO 42,57 Euro, guenstigster Anbieter 42,57 Euro — Faktor 1,00 ueber 4 erhobenen Marken.
- Rechtsschutzversicherung: ERGO 27,21 Euro, guenstigster Anbieter 27,21 Euro — Faktor 1,00 ueber 2 erhobenen Marken.

Zur Wirkung des Preises auf die Sichtbarkeit: Gemeint ist nicht das Ereignis 'Preis geaendert', sondern das Preisniveau im Vergleich zum Wettbewerb. Die Richtung ist ueber alle Messtage stabil — teurer geht mit weniger Sichtbarkeit einher —, aber nach Korrektur fuer Mehrfachtests uebersteht kein Schnitt die Signifikanzschwelle. Richtung ja, Nachweis nein. Als Ereignis betrachtet ist der Preis gar nicht schaetzbar: an den meisten Tagen aendert sich keine einzige Zelle, und die wenigen Aenderungen waren ueberwiegend ein Hin- und Zurueckspringen auf den Vorwert, also ein Messartefakt des Erhebungsverfahrens.

Zahlenbeleg dazu: Wild-Cluster-p 0,4420, Richtungswahrscheinlichkeit 82,7 Prozent.


## Presse, News und Bewertungen

Stand der Presseauswertung: 2026-08-14.

Erfasst werden je Marke eigene Pressemitteilungen und externe Berichterstattung. Die Gesamtzahlen sind gedeckelt und deshalb nicht als Marktanteil an der Berichterstattung lesbar — aussagekraeftig ist der Vergleich der letzten 30 Tage:

- ERGO: 11 Beitraege in den letzten 30 Tagen, 36 in 90 Tagen. Davon insgesamt 100 eigene Mitteilungen und 100 externe Berichte. Juengster Beitrag 2026-08-13. Haeufigste Themen: Allgemein (130), Digitalisierung & KI (32), Finanzen & Vorsorge (12).
- Allianz: 8 Beitraege in den letzten 30 Tagen, 15 in 90 Tagen. Davon insgesamt 90 eigene Mitteilungen und 98 externe Berichte. Juengster Beitrag 2026-08-11. Haeufigste Themen: Allgemein (125), Digitalisierung & KI (17), KFZ & Mobilität (15).
- AXA: 7 Beitraege in den letzten 30 Tagen, 9 in 90 Tagen. Davon insgesamt 98 eigene Mitteilungen und 100 externe Berichte. Juengster Beitrag 2026-08-13. Haeufigste Themen: Allgemein (121), Finanzen & Vorsorge (22), Digitalisierung & KI (19).
- HUK-Coburg: 14 Beitraege in den letzten 30 Tagen, 32 in 90 Tagen. Davon insgesamt 100 eigene Mitteilungen und 98 externe Berichte. Juengster Beitrag 2026-08-13. Haeufigste Themen: Allgemein (122), KFZ & Mobilität (41), Digitalisierung & KI (9).
- Generali: 5 Beitraege in den letzten 30 Tagen, 14 in 90 Tagen. Davon insgesamt 96 eigene Mitteilungen und 89 externe Berichte. Juengster Beitrag 2026-08-06. Haeufigste Themen: Allgemein (121), Finanzen & Vorsorge (20), Digitalisierung & KI (17).
- Signal Iduna: 8 Beitraege in den letzten 30 Tagen, 26 in 90 Tagen. Davon insgesamt 100 eigene Mitteilungen und 99 externe Berichte. Juengster Beitrag 2026-08-14. Haeufigste Themen: Allgemein (116), Digitalisierung & KI (25), Produkt & Innovation (15).
- R+V: 14 Beitraege in den letzten 30 Tagen, 33 in 90 Tagen. Davon insgesamt 100 eigene Mitteilungen und 100 externe Berichte. Juengster Beitrag 2026-08-12. Haeufigste Themen: Allgemein (135), Finanzen & Vorsorge (21), Unternehmen & Strategie (16).
- DEVK: 4 Beitraege in den letzten 30 Tagen, 15 in 90 Tagen. Davon insgesamt 7 eigene Mitteilungen und 100 externe Berichte. Juengster Beitrag 2026-08-11. Haeufigste Themen: Allgemein (64), KFZ & Mobilität (11), Digitalisierung & KI (9).
- Hannoversche: 5 Beitraege in den letzten 30 Tagen, 6 in 90 Tagen. Davon insgesamt 100 eigene Mitteilungen und 65 externe Berichte. Juengster Beitrag 2026-08-11. Haeufigste Themen: Allgemein (95), Finanzen & Vorsorge (34), Digitalisierung & KI (12).
- Cosmos Direkt: 1 Beitraege in den letzten 30 Tagen, 3 in 90 Tagen. Davon insgesamt 99 eigene Mitteilungen und 55 externe Berichte. Juengster Beitrag 2026-08-03. Haeufigste Themen: Allgemein (105), KFZ & Mobilität (19), Finanzen & Vorsorge (14).

Wichtig zur Einordnung von Presse-Arbeit: Der weit ueberwiegende Teil der erfassten Presse- und News-Ereignisse liegt auf Quellen, die Sprachmodelle gar nicht zitieren. Die Quellen, die tatsaechlich zitiert werden — die eigenen Markenseiten, grosse Ratgeber- und Testportale — werden bisher nicht als Ereignis verfolgt. Das ist die wahrscheinlichste Erklaerung dafuer, warum externe Ereignisse in der Messung so wenig bewegen: nicht weil Presse nicht wirkt, sondern weil die gemessene Presse nicht dort stattfindet, wo die Modelle schoepfen.


Stimmungsbild aus den erfassten Kundenbewertungen, in Prozent der Bewertungen je Marke (positiv / neutral / kritisch):

- ERGO: 65 Prozent positiv, 16 Prozent neutral, 19 Prozent kritisch.
- Allianz: 75 Prozent positiv, 11 Prozent neutral, 14 Prozent kritisch.
- AXA: 51 Prozent positiv, 22 Prozent neutral, 27 Prozent kritisch.
- HUK-Coburg: 52 Prozent positiv, 22 Prozent neutral, 26 Prozent kritisch.
- Generali: 51 Prozent positiv, 22 Prozent neutral, 27 Prozent kritisch.
- Signal Iduna: 58 Prozent positiv, 19 Prozent neutral, 23 Prozent kritisch.
- R+V: 41 Prozent positiv, 27 Prozent neutral, 32 Prozent kritisch.
- DEVK: 71 Prozent positiv, 13 Prozent neutral, 16 Prozent kritisch.
- Hannoversche: 69 Prozent positiv, 14 Prozent neutral, 17 Prozent kritisch.
- Cosmos Direkt: 63 Prozent positiv, 17 Prozent neutral, 20 Prozent kritisch.

Die Quellenabdeckung unterscheidet sich je Marke — die Anteile sind untereinander nur grob vergleichbar. Ein Zusammenhang zwischen Bewertungslage und LLM-Sichtbarkeit ist in der Messung nicht nachweisbar.

## Zwei Messquellen — und wo sie sich unterscheiden

Die Sichtbarkeit wird doppelt gemessen. Die primaere Quelle ist ein kommerzieller Dienst, der echte Nutzerinteraktion im Browser nachbildet und mehr Engines abdeckt, dafuer seine Erhebungs- und Bewertungsformeln nicht offenlegt. Die zweite Quelle ist der eigene Crawl ueber die Programmierschnittstellen der Modelle, vollstaendig offengelegt und bis zur einzelnen Antwort nachvollziehbar. Der eigene Crawl dient als Gegenprobe und Auditgrundlage.

Die beiden Quellen kommen bei den absoluten Niveaus zu deutlich verschiedenen Werten. Das ist erwartbar und kein Fehler: Sie messen ueber unterschiedliche Engines, mit unterschiedlichen Prompt-Saetzen und unterschiedlichen Zaehlweisen. Verlaesslich vergleichbar ist die Rangfolge je Thema, nicht die Hoehe. Wer eine einzelne Prozentzahl aus einer der beiden Quellen zitiert, muss dazusagen, aus welcher sie stammt.

Ein wichtiger Unterschied betrifft die Prompts selbst: Enthaelt ein Prompt bereits den Markennamen, faellt die gemessene Sichtbarkeit der Marke naturgemaess viel hoeher aus. Als Marktbild gilt deshalb ausschliesslich die branding-neutrale Auswertung — nur Prompts ohne Markennamen. Zahlen aus der Ansicht mit Markennennung beantworten die Frage 'wie sichtbar sind wir, wenn gezielt nach uns gefragt wird' und duerfen nicht als Marktanteil ausgegeben werden.


Stand der Zweitquellen-Auswertung: 2026-08-10, Fenster 2026-07-11..2026-08-09.


## Was daraus folgt — die abgeleiteten Empfehlungen

Aus den Daten leitet das Cockpit Empfehlungen ab. Die Regel dafuer ist offengelegt: Ein Thema kommt auf die Liste, wenn der Rueckstand zum Marktfuehrer groesser als drei Prozentpunkte ist UND der eigene Zitatanteil unter acht Prozent liegt. Sortiert wird nach erwartetem Sichtbarkeitsgewinn.

Der erwartete Gewinn berechnet sich als der Abstand im Zitatanteil zum Marktfuehrer, multipliziert mit dem oben genannten Zusammenhang, und wird am tatsaechlichen Rueckstand gekappt. Er ist ausdruecklich kein Versprechen: die Steigung stammt aus dem Querschnitt ueber Marken, nicht aus einem Eingriff. Sie sagt, wie viel Sichtbarkeit Marken mit diesem Zitatanteil im Schnitt haben — nicht, was passiert, wenn ERGO seinen erhoeht.

Die inhaltliche Stossrichtung ist in allen Faellen dieselbe und folgt aus der Kernaussage: zitierfaehige Inhalte auf den eigenen Seiten aufbauen und Praesenz in genau den Portalen und Redaktionen herstellen, die in diesem Thema tatsaechlich zitiert werden. Nicht: mehr Seiten veroeffentlichen. Die Zahl der eigenen Seiten ist nicht der Treiber — das Vorkommen in zitierten Quellen ist es.

Fuer Massnahmen, deren Wirkung in der Messung nicht nachweisbar ist, gilt: Sie werden nicht deshalb empfohlen, weil eine Wirkung belegt waere, sondern weil ERGO dort hinter dem Aktivitaetsniveau des Wettbewerbs liegt. Das ist ein Rueckstandsargument, kein Wirkungsargument, und muss so benannt werden.


## Was dieses Cockpit nicht kann

Diese Liste ist genauso wichtig wie die Zahlen. Auf Fragen, die hierunter fallen,
lautet die richtige Antwort, dass das Cockpit es nicht misst.

Nicht gemessen werden Absatz, Leads, Abschluesse, Markenwert oder Werbewirkung.
Das Cockpit misst ausschliesslich, wie oft und wie prominent Marken in
LLM-Antworten vorkommen, und sucht Zusammenhaenge zu beobachtbaren Ereignissen.

Nicht gemessen wird, was einzelne Nutzer tatsaechlich fragen. Die Auswertung
beruht auf einem festen Satz von Prompts, nicht auf echtem Nutzerverhalten.

Nicht nachgewiesen werden Ursachen. Ereignisse treten auf, wie sie auftreten,
sie werden nicht zugelost. Alle Effekte ausser dem Websuche-Experiment sind
Zusammenhaenge unter Beobachtungsbedingungen.

Nicht beantwortet werden kann, was eine konkrete Massnahme bewirken wird. Das
Cockpit kann Hypothesen priorisieren; belegen kann es Wirkung nur ueber
Experimente, und davon gibt es bisher genau eines.

Nicht vorhanden sind Aussagen zu Zeitraeumen vor dem ersten Messtag. Was vorher
war, ist unbekannt und darf nicht rekonstruiert werden.
