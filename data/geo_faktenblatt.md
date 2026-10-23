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

Dieses Faktenblatt wurde am 23.10.2026 um 10:58 Uhr UTC erzeugt. Die Auswertung stammt vom 2026-10-23.

Gemessen wird seit 74 Messtagen, von 2026-05-14 bis 2026-10-20. Daraus entstehen 740 Intervall-Beobachtungen ueber 26 Marken.

Der eigene Crawl laeuft seit dem 10.08.2026 woechentlich statt taeglich, sonntags gegen 23:10 UTC. Presse, News und Bewertungen werden weiterhin taeglich erhoben. Wenn also in einer Tagesuebersicht an mehreren Tagen kaum Seiten-Ereignisse stehen, ist das der Normalzustand zwischen zwei Laeufen und kein Ausfall.

Achtung, veraltete Bestandteile: Peec-Wochenexport (letzter Stand 2026-10-11). Auskuenfte, die darauf beruhen, sind entsprechend zu kennzeichnen.


## Was die Sichtbarkeit treibt — die Kernaussage

Die kuerzeste ehrliche Zusammenfassung lautet: Ein einziger Treiber traegt fast alles, und er heisst Quellpraesenz. Damit ist nicht die Zahl der eigenen Seiten gemeint, sondern wie oft die Marke in dem vorkommt, was Sprachmodelle zitieren. Alle einzelnen operativen Massnahmen sind dagegen zu klein, um in dieser Messung ueberhaupt sichtbar zu werden.

**Quellpraesenz.** Marken mit hoeherer Quellpraesenz sind sichtbarer: +5,81 Prozentpunkte Sichtbarkeit je einer Standardabweichung mehr Zitations-Footprint, gerechnet ueber 26 Marken. Der Befund ist nach Korrektur fuer Mehrfachtests gesichert (Wild-Cluster-p 0,0051, q 0,0102). Es bleibt ein beobachteter Zusammenhang, kein Kausalnachweis: gemessen wurde, nicht eingegriffen.


## Der einzige kausal belegte Befund: die Websuche

Dies ist die einzige Stelle im gesamten Cockpit, an der eingegriffen und gegen eine Kontrollbedingung verglichen wurde — und damit die einzige, an der von Wirkung statt von Zusammenhang gesprochen werden darf.

Jeder von 150 Prompts lief zweimal: einmal mit erzwungener Websuche, einmal ohne jedes Werkzeug, sonst identisch. Mit Suche erreicht ERGO 8,9 Prozent Anteil an den Antworten, ohne Suche 3,1 Prozent. Der Unterschied betraegt +5,8 Prozentpunkte, das 95-Prozent-Intervall reicht von +3,2 Prozentpunkte bis +8,6 Prozentpunkte (p 0,0004).

Drei Einschraenkungen gehoeren zu diesem Befund und muessen mitgenannt werden, wenn danach gefragt wird. Erzwungene Suche ist nicht der Normalfall — im echten Betrieb entscheidet das Modell selbst, ob es sucht. Das Experiment lief auf einem anderen Modell als der laufende Messkanal, die Richtung ist uebertragbar, die Hoehe nicht eins zu eins. Und es gehoert ausdruecklich nicht in die Zeitreihe des Cockpits.


## Wo ERGO verliert: die Themen im Einzelnen

Je Thema, sortiert nach dem groessten Rueckstand zu Allianz:


Die Lesart dieser Tabelle: Ein grosser Rueckstand bei zugleich sehr kleinem eigenem Zitatanteil deutet auf eine Content- und Quellenluecke hin — dort wird ERGO in den Quellen, aus denen die Modelle schoepfen, schlicht nicht gefunden. Ein Rueckstand bei bereits ordentlichem Zitatanteil hat eher andere Ursachen.


## Einzelne Ereignisse: warum hier nichts nachweisbar ist

Geprueft wurden 13 Ereignisarten daraufhin, ob sie die Sichtbarkeit kurzfristig bewegen: Pressemitteilungen, News-Erwaehnungen, neue Seiten, Seitenaenderungen, geloeschte Seiten, Bewertungs-Trend, Bewertungs-Volumen, Wikipedia-Ausbau und Portal-Rang. Davon ist keine einzige gesichert.

Der Grund dafuer ist rechnerisch und war vorher absehbar. Zu jeder Ereignisart gehoert eine Nachweisgrenze: die Effektgroesse, ab der ein echter Effekt bei der heutigen Datenmenge ueberhaupt auffindbar waere. Diese Grenzen liegen zwischen etwa 0,4 und 1,0 Prozentpunkten. Die tatsaechlich gemessenen Effekte liegen zwischen 0,03 und 0,56 Prozentpunkten — also durchweg darunter. Eine einzelne Pressemitteilung kann diese Messung nicht bewegen, unabhaengig davon, ob sie wirkt.

Die Einzelwerte, jeweils mit ihrem Urteil:

- Bewertungs-Trend (±): nicht nachweisbar. Punktschaetzer -0,23 Prozentpunkte, 95-Prozent-Intervall von -0,74 bis +0,08 Prozentpunkten, beobachtet in 70 von 740 Intervallen ueber 9 Marken.
- Pressemitteilungen: nicht nachweisbar. Punktschaetzer +0,20 Prozentpunkte, 95-Prozent-Intervall von -0,20 bis +0,66 Prozentpunkten, beobachtet in 109 von 740 Intervallen ueber 9 Marken.
- Neue Seiten: nicht nachweisbar. Punktschaetzer -0,20 Prozentpunkte, 95-Prozent-Intervall von -0,52 bis +0,09 Prozentpunkten, beobachtet in 82 von 740 Intervallen ueber 17 Marken.
- Bewertungs-Volumen: nicht nachweisbar. Punktschaetzer -0,19 Prozentpunkte, 95-Prozent-Intervall von -1,06 bis +0,29 Prozentpunkten, beobachtet in 57 von 740 Intervallen ueber 7 Marken.
- Beitragsanpassung (angekuendigt): nicht nachweisbar. Punktschaetzer +0,14 Prozentpunkte, 95-Prozent-Intervall von -0,64 bis +0,94 Prozentpunkten, beobachtet in 6 von 740 Intervallen ueber 2 Marken.
- Portal-Rang Check24 (±): nicht nachweisbar. Punktschaetzer -0,14 Prozentpunkte, 95-Prozent-Intervall von -0,72 bis +0,42 Prozentpunkten, beobachtet in 16 von 740 Intervallen ueber 4 Marken.
- Seitenaenderungen (Wettbewerb): nicht nachweisbar. Punktschaetzer -0,10 Prozentpunkte, 95-Prozent-Intervall von -0,38 bis +0,08 Prozentpunkten, beobachtet in 346 von 740 Intervallen ueber 23 Marken.
- News-Erwaehnungen: nicht nachweisbar. Punktschaetzer +0,09 Prozentpunkte, 95-Prozent-Intervall von -0,40 bis +0,65 Prozentpunkten, beobachtet in 170 von 740 Intervallen ueber 9 Marken.
- Geloeschte Seiten: nicht nachweisbar. Punktschaetzer +0,06 Prozentpunkte, 95-Prozent-Intervall von -0,22 bis +0,35 Prozentpunkten, beobachtet in 10 von 740 Intervallen ueber 4 Marken.
- Wikipedia-Ausbau (±): nicht nachweisbar. Punktschaetzer -0,05 Prozentpunkte, 95-Prozent-Intervall von -0,27 bis +0,18 Prozentpunkten, beobachtet in 13 von 740 Intervallen ueber 5 Marken.
- LinkedIn-Posts: nicht nachweisbar. Punktschaetzer -0,03 Prozentpunkte, 95-Prozent-Intervall von -0,22 bis +0,16 Prozentpunkten, beobachtet in 91 von 740 Intervallen ueber 9 Marken.
- Preis-Aenderungen (gemessen): nicht nachweisbar. Punktschaetzer -0,02 Prozentpunkte, 95-Prozent-Intervall von -3,24 bis +3,21 Prozentpunkten, beobachtet in 2 von 740 Intervallen ueber 2 Marken.
- Instagram-Posts: nicht nachweisbar. Punktschaetzer +0,00 Prozentpunkte, 95-Prozent-Intervall von -0,16 bis +0,16 Prozentpunkten, beobachtet in 94 von 740 Intervallen ueber 10 Marken.

Nicht schaetzbar, mit Grund — diese Arten verschwinden nicht aus der Auswertung, sondern stehen mit ihrer Begruendung da:

- Domain-/Subdomain-Aenderungen: Cluster-robuste Schaetzung nicht moeglich (1 Marke(n) mit Ereignis, 26 Cluster insgesamt). Ohne Variation zwischen Marken laesst sich die Unsicherheit nicht ehrlich beziffern; die iid-Felder unterstellen Unabhaengigkeit, die hier nicht gegeben ist.

Zur Guete des Modells insgesamt: Die Vorhersagekraft der Treiber liegt bei R² -0,023 gegenueber einer reinen Marken-Basislinie — die Treiber verbessern die Vorhersage also nicht. Die Placebo-Rate betraegt 1,7 Prozent: so oft erzeugen reine Zufallsdaten einen scheinbar gesicherten Effekt. Erwartet waeren rund fuenf Prozent, der niedrigere Wert spricht fuer eine eher konservative Rechnung.


## Was es in die Zitate schafft

- ERGO: 48 von 1.172 getrackten Seiten sind in Zitaten aufgetaucht, also 4,10 Prozent. Das ist die eigene Marke.
- Allianz: 65 von 896 getrackten Seiten sind in Zitaten aufgetaucht, also 7,25 Prozent.
- ADAC: 10 von 647 getrackten Seiten sind in Zitaten aufgetaucht, also 1,55 Prozent.
- LV 1871: 16 von 537 getrackten Seiten sind in Zitaten aufgetaucht, also 2,98 Prozent.
- ARAG: 13 von 469 getrackten Seiten sind in Zitaten aufgetaucht, also 2,77 Prozent.
- HDI: 0 von 288 getrackten Seiten sind in Zitaten aufgetaucht, also 0,00 Prozent.
- Die Bayerische: 4 von 285 getrackten Seiten sind in Zitaten aufgetaucht, also 1,40 Prozent.
- R+V: 2 von 240 getrackten Seiten sind in Zitaten aufgetaucht, also 0,83 Prozent.

Drei Einschraenkungen zu diesen Quoten. Der Datenlieferant gibt nur die meistzitierten Seiten eines rollierenden Fensters heraus, der lange Schwanz selten zitierter Seiten fehlt — die Quoten sind deshalb Untergrenzen. Der Nenner ist die vom Crawl verfolgte Seitenauswahl je Marke, nicht die vollstaendige Website. Und dass eine Seite zitiert und eine Marke genannt wird, ist ein gemeinsames Auftreten, kein Nachweis, dass das eine das andere verursacht.


## Preise

Die Preise stammen aus einer Erhebung bei einem Vergleichsportal, je Produkt und Altersprofil. Drei Produkte — Haftpflicht, Hausrat und Rechtsschutz — sind bewusst altersunabhaengig, dort gilt derselbe Wert fuer alle Profile.

ERGO im Vergleich zur jeweils guenstigsten erhobenen Marke:

- Zahnzusatzversicherung: ERGO 37,80 Euro, guenstigster Anbieter 20,25 Euro — Faktor 1,87 ueber 6 erhobenen Marken.
- Risikolebensversicherung: ERGO 69,24 Euro, guenstigster Anbieter 56,73 Euro — Faktor 1,22 ueber 4 erhobenen Marken.
- Krankenhauszusatzversicherung: ERGO 42,57 Euro, guenstigster Anbieter 42,57 Euro — Faktor 1,00 ueber 4 erhobenen Marken.
- Rechtsschutzversicherung: ERGO 27,21 Euro, guenstigster Anbieter 27,21 Euro — Faktor 1,00 ueber 2 erhobenen Marken.

Zur Wirkung des Preises auf die Sichtbarkeit: Gemeint ist nicht das Ereignis 'Preis geaendert', sondern das Preisniveau im Vergleich zum Wettbewerb. Die Richtung ist ueber alle Messtage stabil — teurer geht mit weniger Sichtbarkeit einher —, aber nach Korrektur fuer Mehrfachtests uebersteht kein Schnitt die Signifikanzschwelle. Richtung ja, Nachweis nein. Als Ereignis betrachtet ist der Preis gar nicht schaetzbar: an den meisten Tagen aendert sich keine einzige Zelle, und die wenigen Aenderungen waren ueberwiegend ein Hin- und Zurueckspringen auf den Vorwert, also ein Messartefakt des Erhebungsverfahrens.


## Presse, News und Bewertungen

Stand der Presseauswertung: 2026-10-23.

Erfasst werden je Marke eigene Pressemitteilungen und externe Berichterstattung. Die Gesamtzahlen sind gedeckelt und deshalb nicht als Marktanteil an der Berichterstattung lesbar — aussagekraeftig ist der Vergleich der letzten 30 Tage:

- ERGO: 10 Beitraege in den letzten 30 Tagen, 19 in 90 Tagen. Davon insgesamt 49 eigene Mitteilungen und 100 externe Berichte. Juengster Beitrag 2026-10-20. Haeufigste Themen: Allgemein (83), Digitalisierung & KI (24), Gesundheit & Pflege (16).
- Allianz: 10 Beitraege in den letzten 30 Tagen, 19 in 90 Tagen. Davon insgesamt 89 eigene Mitteilungen und 97 externe Berichte. Juengster Beitrag 2026-10-21. Haeufigste Themen: Allgemein (130), Digitalisierung & KI (15), KFZ & Mobilität (13).
- AXA: 4 Beitraege in den letzten 30 Tagen, 12 in 90 Tagen. Davon insgesamt 96 eigene Mitteilungen und 100 externe Berichte. Juengster Beitrag 2026-10-19. Haeufigste Themen: Allgemein (118), Finanzen & Vorsorge (22), Digitalisierung & KI (21).
- HUK-Coburg: 12 Beitraege in den letzten 30 Tagen, 44 in 90 Tagen. Davon insgesamt 100 eigene Mitteilungen und 97 externe Berichte. Juengster Beitrag 2026-10-22. Haeufigste Themen: Allgemein (112), KFZ & Mobilität (45), Digitalisierung & KI (12).
- Generali: 7 Beitraege in den letzten 30 Tagen, 16 in 90 Tagen. Davon insgesamt 96 eigene Mitteilungen und 95 externe Berichte. Juengster Beitrag 2026-10-23. Haeufigste Themen: Allgemein (127), Finanzen & Vorsorge (20), Unternehmen & Strategie (12).
- Signal Iduna: 7 Beitraege in den letzten 30 Tagen, 19 in 90 Tagen. Davon insgesamt 99 eigene Mitteilungen und 99 externe Berichte. Juengster Beitrag 2026-10-20. Haeufigste Themen: Allgemein (113), Digitalisierung & KI (19), Produkt & Innovation (16).
- R+V: 14 Beitraege in den letzten 30 Tagen, 37 in 90 Tagen. Davon insgesamt 98 eigene Mitteilungen und 100 externe Berichte. Juengster Beitrag 2026-10-23. Haeufigste Themen: Allgemein (129), Finanzen & Vorsorge (31), Digitalisierung & KI (14).
- DEVK: 10 Beitraege in den letzten 30 Tagen, 18 in 90 Tagen. Davon insgesamt 5 eigene Mitteilungen und 99 externe Berichte. Juengster Beitrag 2026-10-22. Haeufigste Themen: Allgemein (61), Finanzen & Vorsorge (14), KFZ & Mobilität (8).
- Hannoversche: 5 Beitraege in den letzten 30 Tagen, 6 in 90 Tagen. Davon insgesamt 100 eigene Mitteilungen und 68 externe Berichte. Juengster Beitrag 2026-10-07. Haeufigste Themen: Allgemein (96), Finanzen & Vorsorge (38), Gesundheit & Pflege (10).
- Cosmos Direkt: 2 Beitraege in den letzten 30 Tagen, 4 in 90 Tagen. Davon insgesamt 94 eigene Mitteilungen und 28 externe Berichte. Juengster Beitrag 2026-10-13. Haeufigste Themen: Allgemein (85), Finanzen & Vorsorge (14), KFZ & Mobilität (13).

Wichtig zur Einordnung von Presse-Arbeit: Der weit ueberwiegende Teil der erfassten Presse- und News-Ereignisse liegt auf Quellen, die Sprachmodelle gar nicht zitieren. Die Quellen, die tatsaechlich zitiert werden — die eigenen Markenseiten, grosse Ratgeber- und Testportale — werden bisher nicht als Ereignis verfolgt. Das ist die wahrscheinlichste Erklaerung dafuer, warum externe Ereignisse in der Messung so wenig bewegen: nicht weil Presse nicht wirkt, sondern weil die gemessene Presse nicht dort stattfindet, wo die Modelle schoepfen.


Stimmungsbild aus den erfassten Kundenbewertungen, in Prozent der Bewertungen je Marke (positiv / neutral / kritisch):

- ERGO: 65 Prozent positiv, 16 Prozent neutral, 19 Prozent kritisch.
- Allianz: 76 Prozent positiv, 11 Prozent neutral, 13 Prozent kritisch.
- AXA: 52 Prozent positiv, 22 Prozent neutral, 27 Prozent kritisch.
- HUK-Coburg: 71 Prozent positiv, 13 Prozent neutral, 16 Prozent kritisch.
- Generali: 52 Prozent positiv, 22 Prozent neutral, 26 Prozent kritisch.
- Signal Iduna: 54 Prozent positiv, 21 Prozent neutral, 25 Prozent kritisch.
- R+V: 43 Prozent positiv, 26 Prozent neutral, 31 Prozent kritisch.
- DEVK: 72 Prozent positiv, 13 Prozent neutral, 15 Prozent kritisch.
- Hannoversche: 69 Prozent positiv, 14 Prozent neutral, 17 Prozent kritisch.
- Cosmos Direkt: 61 Prozent positiv, 18 Prozent neutral, 22 Prozent kritisch.

Die Quellenabdeckung unterscheidet sich je Marke — die Anteile sind untereinander nur grob vergleichbar. Ein Zusammenhang zwischen Bewertungslage und LLM-Sichtbarkeit ist in der Messung nicht nachweisbar.

## Zwei Messquellen — und wo sie sich unterscheiden

Die Sichtbarkeit wird doppelt gemessen. Die primaere Quelle ist ein kommerzieller Dienst, der echte Nutzerinteraktion im Browser nachbildet und mehr Engines abdeckt, dafuer seine Erhebungs- und Bewertungsformeln nicht offenlegt. Die zweite Quelle ist der eigene Crawl ueber die Programmierschnittstellen der Modelle, vollstaendig offengelegt und bis zur einzelnen Antwort nachvollziehbar. Der eigene Crawl dient als Gegenprobe und Auditgrundlage.

Seit dem 05.10.2026 fragt der eigene Crawl aus Kostengruenden nur noch ChatGPT ohne Websuche ab. Den Kanal mit Websuche (Gemini, Google AI Overview, AI Mode) misst seither nur noch der kommerzielle Dienst; Perplexity misst keine der beiden Quellen mehr. Die Gegenprobe gibt es damit nur noch im Kanal ohne Websuche, fuer den Kanal mit Websuche reicht sie bis zum Lauf vom 29.09.2026.

Die beiden Quellen kommen bei den absoluten Niveaus zu deutlich verschiedenen Werten. Das ist erwartbar und kein Fehler: Sie messen ueber unterschiedliche Engines, mit unterschiedlichen Prompt-Saetzen und unterschiedlichen Zaehlweisen. Verlaesslich vergleichbar ist die Rangfolge je Thema, nicht die Hoehe. Wer eine einzelne Prozentzahl aus einer der beiden Quellen zitiert, muss dazusagen, aus welcher sie stammt.

Ein wichtiger Unterschied betrifft die Prompts selbst: Enthaelt ein Prompt bereits den Markennamen, faellt die gemessene Sichtbarkeit der Marke naturgemaess viel hoeher aus. Als Marktbild gilt deshalb ausschliesslich die branding-neutrale Auswertung — nur Prompts ohne Markennamen. Zahlen aus der Ansicht mit Markennennung beantworten die Frage 'wie sichtbar sind wir, wenn gezielt nach uns gefragt wird' und duerfen nicht als Marktanteil ausgegeben werden.


Stand der Zweitquellen-Auswertung: 2026-10-11, Fenster 2026-09-12..2026-10-11.


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
