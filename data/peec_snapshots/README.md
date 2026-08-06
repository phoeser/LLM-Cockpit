# Peec-Snapshots — versionierte Historie

Eingeführt 18.07.2026 (Punkt 3 der 7er-Liste). Ziel: über die Wochen wächst hier ein
unveränderliches Panel der Peec-Exporte, damit später Lag-Modelle/Staggered-DiD
möglich werden (die überschreibbare data/peec_cells.csv taugt dafür nicht).

## Konvention
- `YYYY-MM-DD_zellen.csv` — 30-Tage-Zellen-Export, Dateiname = **Enddatum** des Export-Fensters. Format identisch zu `data/peec_cells.csv` (Semikolon, UTF-8 mit BOM, Spalten siehe scripts/correlation_impact.py `_load_peec_cells`).
- `YYYY-MM-DD_footprint.json` — zugehöriger Footprint-Stand, Schema wie `data/peec_footprint.json`.
- Snapshots werden **nie überschrieben** (nur angelegt, wenn noch nicht vorhanden).

## Wer schreibt hier?
Der Cowork-Scheduled-Task `peec-weekly-export` (Mo 07:07, läuft auf Pauls Rechner)
per GitHub Contents API. Er pusht außerdem das komplette Wochen-Panel ab 2026-04-01
nach `data/peec_history_weekly.csv` (wird wöchentlich überschrieben — die Snapshots
hier sind die unveränderliche Referenz).

Hinweis: Der Nightly-Workflow committet nur explizit gelistete Dateien — dieser
Ordner wird bewusst NICHT von der Pipeline befüllt, sondern nur vom Export-Task.

## Kadenz (Korrektur 05.08.2026)

**Peec misst taeglich, nicht woechentlich.** Belegt an den eigenen Exporten:
`data/peec_history_daily.csv` enthaelt 30 Tageswerte, `data/peec_segments_history.csv` 31 —
Peec liefert die Historie rueckwirkend tagesscharf.

Fuer die Kennzahlen ist die Abrufkadenz deshalb egal. Fuer die **Zitatdaten nicht**:
`peec_sources.json` ist eine Momentaufnahme ueber ein rollierendes 30-Tage-Fenster.
Einen Verlauf gibt es nur ueber die Snapshots in diesem Ordner. Bei woechentlichem
Abruf entstehen 4 statt 30 Stuetzstellen — `citation_target` im Treibermodell rechnete
dadurch auf 3 Messpunkten, die sich zu ueber 90 % ueberlappen, und "Tage bis zum ersten
Zitat" ist auf diese Staende gerastert.

**Merke: Die zeitliche Aufloesung der Zitat-Zeitreihe bestimmt UNSERE Abrufkadenz,
nicht Peec.** Seit 05.08.2026 legt ein taeglicher Cowork-Task (`peec-daily-snapshot`,
laeuft auf Pauls Rechner, weil der persoenliche Peec-Token nicht in GitHub-Secrets
gehoert) den Tages-Snapshot an; der Montags-Task bleibt fuer das volle Wochenpanel
zustaendig. Fehlende Tage lassen sich NICHT nachholen — ein rollierendes Fenster gibt
es nur zum Abrufzeitpunkt.
