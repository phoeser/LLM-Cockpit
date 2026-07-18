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
