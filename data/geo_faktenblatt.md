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

Dieses Faktenblatt wurde am 31.10.2026 um 12:04 Uhr UTC erzeugt. Die Auswertung stammt vom 2026-10-31.

Gemessen wird seit 75 Messtagen, von 2026-05-14 bis 2026-10-27. Daraus entstehen 748 Intervall-Beobachtungen ueber 26 Marken.

Der eigene Crawl laeuft seit dem 10.08.2026 woechentlich statt taeglich, sonntags gegen 23:10 UTC. Presse, News und Bewertungen werden weiterhin taeglich erhoben. Wenn also in einer Tagesuebersicht an mehreren Tagen kaum Seiten-Ereignisse stehen, ist das der Normalzustand zwischen zwei Laeufen und kein Ausfall.

Alle 8 ueberwachten Bestandteile der Pipeline sind aktuell; keiner gilt als veraltet.


## Was die Sichtbarkeit treibt — die Kernaussage

Die kuerzeste ehrliche Zusammenfassung lautet: Ein einziger Treiber traegt fast alles, und er heisst Quellpraesenz. Damit ist nicht die Zahl der eigenen Seiten gemeint, sondern wie oft die Marke in dem vorkommt, was Sprachmodelle zitieren. Alle einzelnen operativen Massnahmen sind dagegen zu klein, um in dieser Messung ueberhaupt sichtbar zu werden.

**Quellpraesenz.** Marken mit hoeherer Quellpraesenz sind sichtbarer: +5,91 Prozentpunkte Sichtbarkeit je einer Standardabweichung mehr Zitations-Footprint, gerechnet ueber 26 Marken. Der Befund ist nach Korrektur fuer Mehrfachtests gesichert (Wild-Cluster-p 0,0098, q 0,0196). Es bleibt ein beobachteter Zusammenhang, kein Kausalnachweis: gemessen wurde, nicht eingegriffen.


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

- Bewertungs-Trend (±): nicht nachweisbar. Punktschaetzer -0,23 Prozentpunkte, 95-Prozent-Intervall von -0,73 bis +0,09 Prozentpunkten, beobachtet in 71 von 748 Intervallen ueber 9 Marken.
- Neue Seiten: nicht nachweisbar. Punktschaetzer -0,20 Prozentpunkte, 95-Prozent-Intervall von -0,52 bis +0,08 Prozentpunkten, beobachtet in 84 von 748 Intervallen ueber 17 Marken.
- Pressemitteilungen: nicht nachweisbar. Punktschaetzer +0,19 Prozentpunkte, 95-Prozent-Intervall von -0,20 bis +0,64 Prozentpunkten, beobachtet in 113 von 748 Intervallen ueber 9 Marken.
- Bewertungs-Volumen: nicht nachweisbar. Punktschaetzer -0,19 Prozentpunkte, 95-Prozent-Intervall von -1,04 bis +0,28 Prozentpunkten, beobachtet in 58 von 748 Intervallen ueber 7 Marken.
- Beitragsanpassung (angekuendigt): nicht nachweisbar. Punktschaetzer +0,14 Prozentpunkte, 95-Prozent-Intervall von -0,63 bis +0,93 Prozentpunkten, beobachtet in 6 von 748 Intervallen ueber 2 Marken.
- Portal-Rang Check24 (±): nicht nachweisbar. Punktschaetzer -0,10 Prozentpunkte, 95-Prozent-Intervall von -0,58 bis +0,36 Prozentpunkten, beobachtet in 20 von 748 Intervallen ueber 4 Marken.
- Seitenaenderungen (Wettbewerb): nicht nachweisbar. Punktschaetzer -0,10 Prozentpunkte, 95-Prozent-Intervall von -0,36 bis +0,08 Prozentpunkten, beobachtet in 351 von 748 Intervallen ueber 23 Marken.
- News-Erwaehnungen: nicht nachweisbar. Punktschaetzer +0,07 Prozentpunkte, 95-Prozent-Intervall von -0,41 bis +0,62 Prozentpunkten, beobachtet in 176 von 748 Intervallen ueber 9 Marken.
- Geloeschte Seiten: nicht nachweisbar. Punktschaetzer +0,06 Prozentpunkte, 95-Prozent-Intervall von -0,22 bis +0,35 Prozentpunkten, beobachtet in 10 von 748 Intervallen ueber 4 Marken.
- Preis-Aenderungen (gemessen): nicht nachweisbar. Punktschaetzer -0,06 Prozentpunkte, 95-Prozent-Intervall von -0,58 bis +0,46 Prozentpunkten, beobachtet in 4 von 748 Intervallen ueber 3 Marken.
- LinkedIn-Posts: nicht nachweisbar. Punktschaetzer -0,02 Prozentpunkte, 95-Prozent-Intervall von -0,21 bis +0,17 Prozentpunkten, beobachtet in 100 von 748 Intervallen ueber 9 Marken.
- Instagram-Posts: nicht nachweisbar. Punktschaetzer +0,01 Prozentpunkte, 95-Prozent-Intervall von -0,14 bis +0,17 Prozentpunkten, beobachtet in 104 von 748 Intervallen ueber 10 Marken.
- Wikipedia-Ausbau (±): nicht nachweisbar. Punktschaetzer -0,01 Prozentpunkte, 95-Prozent-Intervall von -0,21 bis +0,19 Prozentpunkten, beobachtet in 15 von 748 Intervallen ueber 6 Marken.

Nicht schaetzbar, mit Grund — diese Arten verschwinden nicht aus der Auswertung, sondern stehen mit ihrer Begruendung da:

- Domain-/Subdomain-Aenderungen: Cluster-robuste Schaetzung nicht moeglich (1 Marke(n) mit Ereignis, 26 Cluster insgesamt). Ohne Variation zwischen Marken laesst sich die Unsicherheit nicht ehrlich beziffern; die iid-Felder unterstellen Unabhaengigkeit, die hier nicht gegeben ist.

Zur Guete des Modells insgesamt: Die Vorhersagekraft der Treiber liegt bei R² -0,023 gegenueber einer reinen Marken-Basislinie — die Treiber verbessern die Vorhersage also nicht. Die Placebo-Rate betraegt 2,2 Prozent: so oft erzeugen reine Zufallsdaten einen scheinbar gesicherten Effekt. Erwartet waeren rund fuenf Prozent, der niedrigere Wert spricht fuer eine eher konservative Rechnung.


## Was es in die Zitate schafft

- ERGO: 48 von 1.172 getrackten Seiten sind in Zitaten aufgetaucht, also 4,10 Prozent. Das ist die eigene Marke.
- Allianz: 62 von 896 getrackten Seiten sind in Zitaten aufgetaucht, also 6,92 Prozent.
- ADAC: 8 von 647 getrackten Seiten sind in Zitaten aufgetaucht, also 1,24 Prozent.
- LV 1871: 15 von 537 getrackten Seiten sind in Zitaten aufgetaucht, also 2,79 Prozent.
- ARAG: 12 von 469 getrackten Seiten sind in Zitaten aufgetaucht, also 2,56 Prozent.
- HDI: 0 von 288 getrackten Seiten sind in Zitaten aufgetaucht, also 0,00 Prozent.
- Die Bayerische: 4 von 285 getrackten Seiten sind in Zitaten aufgetaucht, also 1,40 Prozent.
- R+V: 2 von 240 getrackten Seiten sind in Zitaten aufgetaucht, also 0,83 Prozent.

Drei Einschraenkungen zu diesen Quoten. Der Datenlieferant gibt nur die meistzitierten Seiten eines rollierenden Fensters heraus, der lange Schwanz selten zitierter Seiten fehlt — die Quoten sind deshalb Untergrenzen. Der Nenner ist die vom Crawl verfolgte Seitenauswahl je Marke, nicht die vollstaendige Website. Und dass eine Seite zitiert und eine Marke genannt wird, ist ein gemeinsames Auftreten, kein Nachweis, dass das eine das andere verursacht.


## Preise

Die Preise stammen aus einer Erhebung bei einem Vergleichsportal, je Produkt und Altersprofil. Drei Produkte — Haftpflicht, Hausrat und Rechtsschutz — sind bewusst altersunabhaengig, dort gilt derselbe Wert fuer alle Profile.

ERGO im Vergleich zur jeweils guenstigsten erhobenen Marke:

- Privathaftpflichtversicherung: ERGO 11,09 Euro, guenstigster Anbieter 4,02 Euro — Faktor 2,76 ueber 3 erhobenen Marken.
- Zahnzusatzversicherung: ERGO 37,80 Euro, guenstigster Anbieter 20,25 Euro — Faktor 1,87 ueber 6 erhobenen Marken.
- Risikolebensversicherung: ERGO 69,24 Euro, guenstigster Anbieter 56,73 Euro — Faktor 1,22 ueber 4 erhobenen Marken.
- Krankenhauszusatzversicherung: ERGO 42,57 Euro, guenstigster Anbieter 42,57 Euro — Faktor 1,00 ueber 4 erhobenen Marken.
- Rechtsschutzversicherung: ERGO 27,21 Euro, guenstigster Anbieter 27,21 Euro — Faktor 1,00 ueber 2 erhobenen Marken.

Zur Wirkung des Preises auf die Sichtbarkeit: Gemeint ist nicht das Ereignis 'Preis geaendert', sondern das Preisniveau im Vergleich zum Wettbewerb. Die Richtung ist ueber alle Messtage stabil — teurer geht mit weniger Sichtbarkeit einher —, aber nach Korrektur fuer Mehrfachtests uebersteht kein Schnitt die Signifikanzschwelle. Richtung ja, Nachweis nein. Als Ereignis betrachtet ist der Preis gar nicht schaetzbar: an den meisten Tagen aendert sich keine einzige Zelle, und die wenigen Aenderungen waren ueberwiegend ein Hin- und Zurueckspringen auf den Vorwert, also ein Messartefakt des Erhebungsverfahrens.


## Presse, News und Bewertungen

Stand der Presseauswertung: 2026-10-31.

Erfasst werden je Marke eigene Pressemitteilungen und externe Berichterstattung. Die Gesamtzahlen sind gedeckelt und deshalb nicht als Marktanteil an der Berichterstattung lesbar — aussagekraeftig ist der Vergleich der letzten 30 Tage:

- ERGO: 4 Beitraege in den letzten 30 Tagen, 8 in 90 Tagen. Davon insgesamt 53 eigene Mitteilungen und 31 externe Berichte. Juengster Beitrag 2026-10-14. Haeufigste Themen: Allgemein (53), Gesundheit & Pflege (14), Digitalisierung & KI (8).
- Allianz: 15 Beitraege in den letzten 30 Tagen, 21 in 90 Tagen. Davon insgesamt 89 eigene Mitteilungen und 20 externe Berichte. Juengster Beitrag 2026-10-31. Haeufigste Themen: Allgemein (83), Digitalisierung & KI (8), Gesundheit & Pflege (6).
- AXA: 5 Beitraege in den letzten 30 Tagen, 11 in 90 Tagen. Davon insgesamt 98 eigene Mitteilungen und 89 externe Berichte. Juengster Beitrag 2026-10-19. Haeufigste Themen: Allgemein (115), Digitalisierung & KI (20), Finanzen & Vorsorge (19).
- HUK-Coburg: 12 Beitraege in den letzten 30 Tagen, 44 in 90 Tagen. Davon insgesamt 100 eigene Mitteilungen und 96 externe Berichte. Juengster Beitrag 2026-10-28. Haeufigste Themen: Allgemein (108), KFZ & Mobilität (49), Digitalisierung & KI (12).
- Generali: 19 Beitraege in den letzten 30 Tagen, 26 in 90 Tagen. Davon insgesamt 96 eigene Mitteilungen und 93 externe Berichte. Juengster Beitrag 2026-10-26. Haeufigste Themen: Allgemein (130), Finanzen & Vorsorge (19), Unternehmen & Strategie (13).
- Signal Iduna: 8 Beitraege in den letzten 30 Tagen, 9 in 90 Tagen. Davon insgesamt 99 eigene Mitteilungen und 36 externe Berichte. Juengster Beitrag 2026-10-30. Haeufigste Themen: Allgemein (80), Gesundheit & Pflege (11), Finanzen & Vorsorge (10).
- R+V: 7 Beitraege in den letzten 30 Tagen, 8 in 90 Tagen. Davon insgesamt 99 eigene Mitteilungen und 12 externe Berichte. Juengster Beitrag 2026-10-30. Haeufigste Themen: Allgemein (87), Finanzen & Vorsorge (6), Unternehmen & Strategie (5).
- DEVK: 2 Beitraege in den letzten 30 Tagen, 4 in 90 Tagen. Davon insgesamt 4 eigene Mitteilungen und 33 externe Berichte. Juengster Beitrag 2026-10-30. Haeufigste Themen: Allgemein (21), KFZ & Mobilität (6), Finanzen & Vorsorge (4).
- Hannoversche: 3 Beitraege in den letzten 30 Tagen, 6 in 90 Tagen. Davon insgesamt 100 eigene Mitteilungen und 58 externe Berichte. Juengster Beitrag 2026-10-29. Haeufigste Themen: Allgemein (92), Finanzen & Vorsorge (34), Gesundheit & Pflege (10).
- Cosmos Direkt: 1 Beitraege in den letzten 30 Tagen, 3 in 90 Tagen. Davon insgesamt 57 eigene Mitteilungen und 45 externe Berichte. Juengster Beitrag 2026-10-13. Haeufigste Themen: Allgemein (69), KFZ & Mobilität (13), Finanzen & Vorsorge (11).

Wichtig zur Einordnung von Presse-Arbeit: Der weit ueberwiegende Teil der erfassten Presse- und News-Ereignisse liegt auf Quellen, die Sprachmodelle gar nicht zitieren. Die Quellen, die tatsaechlich zitiert werden — die eigenen Markenseiten, grosse Ratgeber- und Testportale — werden bisher nicht als Ereignis verfolgt. Das ist die wahrscheinlichste Erklaerung dafuer, warum externe Ereignisse in der Messung so wenig bewegen: nicht weil Presse nicht wirkt, sondern weil die gemessene Presse nicht dort stattfindet, wo die Modelle schoepfen.


Stimmungsbild aus den erfassten Kundenbewertungen, in Prozent der Bewertungen je Marke (positiv / neutral / kritisch):

- ERGO: 65 Prozent positiv, 16 Prozent neutral, 19 Prozent kritisch.
- Allianz: 76 Prozent positiv, 11 Prozent neutral, 13 Prozent kritisch.
- AXA: 52 Prozent positiv, 22 Prozent neutral, 27 Prozent kritisch.
- HUK-Coburg: 71 Prozent positiv, 13 Prozent neutral, 16 Prozent kritisch.
- Generali: 52 Prozent positiv, 22 Prozent neutral, 26 Prozent kritisch.
- Signal Iduna: 54 Prozent positiv, 21 Prozent neutral, 25 Prozent kritisch.
- R+V: 45 Prozent positiv, 25 Prozent neutral, 30 Prozent kritisch.
- DEVK: 72 Prozent positiv, 13 Prozent neutral, 15 Prozent kritisch.
- Hannoversche: 69 Prozent positiv, 14 Prozent neutral, 17 Prozent kritisch.
- Cosmos Direkt: 61 Prozent positiv, 18 Prozent neutral, 22 Prozent kritisch.

Die Quellenabdeckung unterscheidet sich je Marke — die Anteile sind untereinander nur grob vergleichbar. Ein Zusammenhang zwischen Bewertungslage und LLM-Sichtbarkeit ist in der Messung nicht nachweisbar.

## Zwei Messquellen — und wo sie sich unterscheiden

Die Sichtbarkeit wird doppelt gemessen. Die primaere Quelle ist ein kommerzieller Dienst, der echte Nutzerinteraktion im Browser nachbildet und mehr Engines abdeckt, dafuer seine Erhebungs- und Bewertungsformeln nicht offenlegt. Die zweite Quelle ist der eigene Crawl ueber die Programmierschnittstellen der Modelle, vollstaendig offengelegt und bis zur einzelnen Antwort nachvollziehbar. Der eigene Crawl dient als Gegenprobe und Auditgrundlage.

Seit dem 05.10.2026 fragt der eigene Crawl aus Kostengruenden nur noch ChatGPT ohne Websuche ab. Den Kanal mit Websuche (Gemini, Google AI Overview, AI Mode) misst seither nur noch der kommerzielle Dienst; Perplexity misst keine der beiden Quellen mehr. Die Gegenprobe gibt es damit nur noch im Kanal ohne Websuche, fuer den Kanal mit Websuche reicht sie bis zum Lauf vom 29.09.2026.

Die beiden Quellen kommen bei den absoluten Niveaus zu deutlich verschiedenen Werten. Das ist erwartbar und kein Fehler: Sie messen ueber unterschiedliche Engines, mit unterschiedlichen Prompt-Saetzen und unterschiedlichen Zaehlweisen. Verlaesslich vergleichbar ist die Rangfolge je Thema, nicht die Hoehe. Wer eine einzelne Prozentzahl aus einer der beiden Quellen zitiert, muss dazusagen, aus welcher sie stammt.

Ein wichtiger Unterschied betrifft die Prompts selbst: Enthaelt ein Prompt bereits den Markennamen, faellt die gemessene Sichtbarkeit der Marke naturgemaess viel hoeher aus. Als Marktbild gilt deshalb ausschliesslich die branding-neutrale Auswertung — nur Prompts ohne Markennamen. Zahlen aus der Ansicht mit Markennennung beantworten die Frage 'wie sichtbar sind wir, wenn gezielt nach uns gefragt wird' und duerfen nicht als Marktanteil ausgegeben werden.


Stand der Zweitquellen-Auswertung: 2026-10-28, Fenster 2026-09-29..2026-10-28.


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
