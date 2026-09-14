# 44 — Übergabe: Betriebsstand LLM-Cockpit

**Stand 13.09.2026.** Diese Datei ist der **Betriebsstand** — sie sagt, wo das
System gerade steht, wie man es bedient und wo es beißt. Sie wiederholt die
beiden anderen Dokumente nicht:

- [45_PROJEKTDOKUMENTATION.md](45_PROJEKTDOKUMENTATION.md) — das Gesamtbild:
  Auftrag, Aufbau, Befunde, Grenzen. **Der Einstieg.**
- [43_TECHNISCHE_DOKUMENTATION.md](43_TECHNISCHE_DOKUMENTATION.md) — die
  technische Tiefe: wie die Modelle rechnen (Stand 18.08.2026).
- **diese Datei (44)** — was heute gilt. Wird laufend fortgeschrieben.

Wer übernimmt, liest 45, dann diese Datei, und 43 nur bei Bedarf.

---

## 1 · Status in drei Sätzen

Das System läuft störungsfrei: alle sechs Datenquellen frisch, keine
ausgefallene Engine, tägliche Läufe seit dem 01.09. lückenlos. Die zuletzt
offene Baustelle — der Perplexity-Ausfall Anfang September — ist behoben und
verifiziert. Die einzige noch unbestätigte Änderung ist der Fix an der
Executive Summary vom 11.09.; sein Beweis kommt mit dem Wochenlauf in der
Nacht zum 15.09. (Montag 23:10 UTC), ausgewertet im Nightly am Dienstagvormittag.

---

## 2 · Zahlen, auf denen der aktuelle Stand steht

Alle Werte aus dem Lauf `2026-09-08T13-14-40Z` (Qualität green, Score 100,
alle drei Engines mit frischen Daten) und aus `data/correlation_impact.json`
vom 13.09.

### Sichtbarkeit

| Marke | Share of Voice | Zitatrate |
|---|---:|---:|
| Allianz | 33,76 % | 46,4 % |
| HUK-Coburg | 22,64 % | 32,1 % |
| **ERGO** | **12,06 %** | **15,2 %** |
| AXA | 11,99 % | 17,2 % |
| Signal Iduna | 7,60 % | 13,3 % |

**Wichtig für die Lesart:** ERGO steht formal auf Platz 3 vor AXA — der
Abstand sind 4 Nennungen (657 zu 653). Das ist Tagesrauschen, kein Überholen,
und zustande kommt es durch einen AXA-Rückgang, nicht durch ERGO-Zuwachs. So
und nicht anders weitergeben.

### Preis-Modell (`price_level_pooled`)

Fünf saubere Messtage seit dem Strukturbruch vom 19.08. (23.08. bis 08.09.):

- **Marktmuster, roh:** −8,63 SoV-Punkte je Preiseinheit, Streuung 0,68, an
  allen fünf Tagen gleiches Vorzeichen. Stabil, aber ohne Kontrollen — kein
  Kausalnachweis.
- **Eigener Effekt, alle Engines:** −0,75 pp je 1 SD, p = 0,2205, q = 0,3307 —
  trägt nicht.
- **Eigener Effekt, Kanal mit Web-Suche:** −1,49 pp je 1 SD, p = 0,0154,
  **q = 0,0462** — seit dem 5. Messtag (08.09.) erstmals auch nach
  FDR-Korrektur gesichert.

Das Dashboard formuliert diesen Zwischenzustand seit dem Patch vom 08.09.
selbst: ein gesicherter Einzelkanal, keine Bestätigung im Mittel, „ein Kanal
allein ist ein starker Hinweis, kein Beweis". Kippt einer der Werte, kippt der
Satz mit — er ist aus der JSON abgeleitet, nicht getextet.

### Der Hebel, der trägt

Unverändert die **Quellpräsenz** (Zitatanteil) — aber kanalabhängig, und das
gehört bei jeder Weitergabe dazu:

| Kanal | Effekt je 1 SD | p | q (FDR) |
|---|---:|---:|---:|
| ungrounded (ohne Websuche), within | +6,22 pp | 0,0085 | **0,0319** |
| ungrounded, between | +6,76 pp | 0,0046 | **0,0230** |
| combined, within | +2,96 pp | 0,0554 | 0,0871 |
| grounded (mit Websuche), within | +1,75 pp | 0,0398 | 0,0746 |

Der gerne zitierte Wert „rund +6 pp je Standardabweichung" ist der
**ungrounded**-Kanal. Im grounded-Kanal ist derselbe Treiber deutlich kleiner
und nach FDR-Korrektur **nicht** gesichert. (Prüfung 13.09. an
`level_model.full_joint`; eine frühere Fassung dieser Datei nannte die Zahl
ohne Kanal.)

Bei den Ereignis-Treibern (Pressemitteilung, neue Seite, Bewertung,
Seitenänderung …) ist weiterhin **keiner** unter p = 0,05 — konsistent seit der
90-%-Analyse im August.

---

## 3 · Was seit Doku 43 (18.08.) passiert ist

| Datum | Änderung | Warum |
|---|---|---|
| 23.08. | 90-%-Sicht im Korrelations-Reiter (Richtungswahrscheinlichkeit, empirisches Bayes, Obergrenzen-Lesart) | Paul braucht belastbare Aussagen auch unterhalb von p < 0,05 |
| 23.08. | Ko-Okkurrenz-Spalte „gleichzeitig anderes" im Nightly-JSON | Treiber treten selten allein auf; ohne diese Spalte wirken Einzeleffekte sauberer, als sie sind |
| 23.08. | Presse-Query angeglichen (`+Presse OR Pressemitteilung` auch für ERGO), Regimewechsel in `PRESS_QUERY_REGIME` dokumentiert | vorher asymmetrische Messung ERGO vs. Wettbewerb |
| 23.08. | Presse-Zuordnung über Verlagsnamen-Fallback: unbekannt 1.775 → ~344 | Titel-Join allein traf nur 37 % |
| 27.08. | Externe „Berichte über uns"-Tabelle im Content-Reiter | Lücke: zitierte Fremdseiten über ERGO waren nirgends sichtbar |
| 31.08. | Preisniveau-Block konsolidiert: Kurz-Antwort + 2 Karten, 12-Zeilen-Tabelle in den Aufklapper | Block war als Einstieg zu voll |
| 08.09. | UX-Durchgang über alle Reiter: lange Listen scrollbar (Content, Maßnahmen, LinkedIn, Presse, GEO-Karten, Check24), Sticky-Header | Content-Reiter 14.200 → 7.100 px, Maßnahmen 12.900 → 940 px |
| 08.09. | Korrelations-Reiter auf Klartext: Antwort + Hebel sichtbar, fünf Analyse-Abschnitte in benannte Aufklapper | 9.400 → 4.300 px, nichts gelöscht |
| 08.09. | Preis-Kernaussage um den FDR-gesicherten Einzelkanal erweitert | der 5. Messtag riss die Schwelle, der alte Text untertrieb den Befund |
| 11.09. | **GEO-Repo:** Executive Summary nutzt den konfigurierten Auswerte-LLM statt des abgeschalteten Claude-Clients | siehe Abschnitt 6 |

---

## 4 · Betriebshandbuch

### Die beiden Repos

| Repo | Rolle | Klon in dieser Session |
|---|---|---|
| `phoeser/LLM-Cockpit` | Dashboard, Auswertung, Deploy | `/tmp/n1` |
| `phoeser/geo-visibility-tool` | Messung (der eigentliche Crawl) | `/tmp/geo` |

### Taktung

- **GEO-Crawl:** wöchentlich, Montag 23:10 UTC (`analyze.yml`). Entscheidung
  Pauls vom 18.07. aus Kostengründen. Ein Zusatzlauf am selben Kalendertag
  bringt **keinen** neuen Messtag — Messtage zählen je Kalendertag.
- **Nightly** (`nightly-update.yml`): geplant 05:30 UTC, **fertig aber erst
  gegen 10:00–11:50 UTC** — GitHub verzögert geplante Läufe erheblich
  (gemessen 09.–14.09.). Wer den Tagesstand prüft, darf das nicht vor Mittag
  tun.
- **Peec Quellen täglich** (`peec-daily-sources.yml`): geplant 04:00 UTC,
  fertig gegen 08:30–09:45 UTC.
- **Deploy** (`dashboard-deploy.yml`): **nur manuell.** Bot-Commits aus
  apply-patch lösen ihn nicht aus — nach jedem Patch selbst anstoßen.

### Änderungen einspielen

1. **Kleine oder neue Dateien** → direkt per GitHub-Konnektor
   (`create_or_update_file`). Der Standardweg.
2. **Große Dateien** (`dashboard_v3.html`, ~480 KB) → Patch-Skript nach
   `patches/`, dann Workflow „Patch anwenden" starten. Der Workflow wendet
   alles in `patches/` an, committet und leert den Ordner.
3. **Workflow-Dateien** (`.github/workflows/`) → gehen **nicht** per
   Konnektor (die GitHub-App hat keinen Workflow-Scope, das kann Paul nicht
   einstellen). Weg: Chrome-Web-Editor.

### Das Patch-Muster (bewährt, bitte beibehalten)

```python
# Kopf: Datum, was, warum. Idempotenz über eine Signatur aus dem NEUEN Text.
import base64, sys
s = open("dashboard_v3.html", "rb").read()
if b"<signatur aus dem neuen Code>" in s:
    print("SKIP: bereits angewendet"); sys.exit(0)
# Paare (alt, neu) base64-kodiert; jedes muss exakt 1x vorkommen
```

Vor dem Push **immer**: Ersetzungen lokal auf den Repo-Stand anwenden und das
Ergebnis byte-genau gegen die getestete Fassung prüfen, dann das Skript
zweimal laufen lassen (2. Lauf muss SKIP sagen).

### Lokale Testumgebung

Das Dashboard lädt Tailwind und Chart.js per CDN — in der Sandbox nicht
erreichbar. Deshalb `/tmp/work/site/` mit lokalem `tailwind.css`
(v3-CLI, Content-Scan statt Safelist — die Safelist-Regex hängt) und
`chart.umd.js`. Playwright braucht einen expliziten Pfad:

```js
chromium.launch({
  executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
  args: ['--no-sandbox', '--disable-dev-shm-usage']
})
```

**Wichtig:** Die CDN-Ersetzung ist nur für den Test. Die Produktionsfassung
behält die CDN-Links — sonst deployt man eine kaputte Seite.

---

## 5 · Fallstricke, die schon Zeit gekostet haben

- **`git -C <repo> hash-object <relpfad>`** löst den Pfad gegen das
  Repo-Verzeichnis auf, nicht gegen das aktuelle. Zweimal falschen
  „ABWEICHEND"-Alarm ausgelöst. → **immer absolute Pfade.**
- **Idempotenz-Prüfung eines Patches** muss zwischen additiv (alt ⊂ neu) und
  subtraktiv unterscheiden. Eine reine `neu in s`-Prüfung lässt additive
  Patches beim zweiten Lauf erneut greifen. → Signatur-Marker statt
  Text-Vergleich.
- **CodeMirror im GitHub-Web-Editor** rückt automatisch ein und zerschießt
  YAML beim mehrzeiligen Tippen. → nur einzeilige Ersetzungen, danach den
  Byte-Inhalt prüfen.
- **Push-Race:** Ein manueller „Patch anwenden"-Klick kann mit einem
  gleichzeitigen Konnektor-Push kollidieren (`! [rejected] fetch first`).
  Seit dem 27.08. hat `apply-patch.yml` eine Retry-Schleife (rebase + 3
  Versuche).
- **Deploy-Verwechslung:** Bei mehreren offenen Auto-Deploy-Seiten wurde
  einmal die ältere deployt. → alte Seiten explizit verwerfen.
- **Ein „Ausfall" ist nicht automatisch ein Defekt.** Ende August fielen
  geplante Läufe tagelang aus; Ursache waren bestätigte
  GitHub-Actions-Incidents (26./27.08.), nicht das Kontingent — Billing zeigte
  0 $ und unangetastete Included-Minuten. Erst prüfen, dann behaupten.

---

## 6 · Offene Punkte

| Punkt | Stand | Nächster Schritt |
|---|---|---|
| **Executive-Summary-Fix** | 11.09. gepusht (Commit `526cb679` im GEO-Repo), lokal mit Fake-Client getestet, echter API-Call steht aus | Verifikation ist für Di 15.09. 06:30 UTC terminiert — prüft den Montagslauf |
| **6. Messtag Preis-Modell** | Wochenlauf Nacht zum 15.09. (Mo 23:10 UTC) | danach `n_days` = 6; hält der Grounded-Kanal unter q = 0,05? |
| **Produktlinien-Analyse** | fertig, als Artefakt „Wer beantwortet die Preisfrage?" veröffentlicht | Welle 1 (vier „Was kostet …"-Seiten) liegt beim Content-Team |
| **WhatsApp-GEOrg** | blockiert | wartet auf Meta-Business-Zugang, den Paul derzeit nicht bekommt |
| **Deploy-Seite Kosmetik** | HTTP 409 wird rot statt grün angezeigt | unkritisch, kein Termin |

### Der Befund, der noch aussteht

Die Produktlinien-Analyse hat einen Punkt geliefert, der bisher nur
dokumentiert und nicht bearbeitet ist: **In allen 13 gemessenen Produktlinien
gibt es keine einzige zitierte ERGO-Seite mit Preisbezug.** 973 Zitate gehen
an fremde Preisquellen (check24, verivox, finanztip, test.de). Die
Abschlussstrecken sind zusätzlich per `robots.txt` gesperrt
(`/ecapp*`, `/ecsp*`, `/webforms/`) und liefern einem Crawler 47 Zeichen
sichtbaren Text. Die Allianz macht es anders und wird dafür zitiert
(`/risikolebensversicherung/beitrag`: 227 Zitate).

---

## 7 · Feste Regeln in diesem Projekt

Diese Regeln stammen aus konkreten Vorfällen und gelten weiter:

1. **API-Schlüssel und Tokens werden nicht angefasst** — nicht gelesen, nicht
   kopiert, nicht „zum Prüfen" weitergereicht. Rotationen macht Paul selbst,
   mit direkter URL und Schritt-für-Schritt-Begleitung.
2. **Keine eingefrorenen Zahlen im Dashboard.** Fehlt ein Feld, steht dort
   „keine Angabe" **mit Grund** — nie eine Null, nie ein Ersatzwert.
3. **Nie eine Ursache benennen, die nicht ausgeführt oder belegt ist.** Bei
   roten Läufen: diagnostizieren und berichten, nichts eigenmächtig ändern,
   was Messungen betrifft.
4. **Jede Zahl im Dashboard kommt zur Laufzeit aus einer JSON.** Auch Texte,
   die eine Aussage treffen, werden aus den Werten abgeleitet — damit sie
   mitkippen, wenn die Daten kippen.
5. **Befunde ehrlich einordnen.** Ein signifikanter Einzelkanal ist kein
   Beweis; ein Rangwechsel um 4 Nennungen ist kein Überholen; eine Korrelation
   ist keine Wirkung. Das Dashboard sagt das selbst, und Berichte an Dritte
   sollten es auch tun.

---

*Diese Datei wird bei größeren Änderungen fortgeschrieben. Wer sie ändert:
Datum an die Aussage schreiben, nicht nur oben in den Kopf — fast jeder Fehler,
der hier Zeit gekostet hat, war ein Satz, der einmal richtig war und dann still
falsch wurde.*
