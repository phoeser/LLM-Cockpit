# LLM-Cockpit

Das ERGO LLM-Sichtbarkeits-Cockpit: misst, wie sichtbar ERGO in den Antworten
großer Sprachmodelle ist, und wertet aus, welche Maßnahmen darauf wirken.

**Live:** `https://phoeser.github.io/LLM-Cockpit/` (passwortgeschützt)

---

## Dokumentation

| Datei | Inhalt |
|---|---|
| **[45_PROJEKTDOKUMENTATION.md](45_PROJEKTDOKUMENTATION.md)** | **Der Einstieg.** Auftrag, Aufbau, Datenquellen, Auswertung, Befunde, Grenzen, Glossar, Dateiverzeichnis |
| [44_UEBERGABE.md](44_UEBERGABE.md) | Betriebsstand: wo das System heute steht, wie man es bedient, wo es beißt |
| [43_TECHNISCHE_DOKUMENTATION.md](43_TECHNISCHE_DOKUMENTATION.md) | Technische Tiefe: wie die Modelle rechnen (Stand 18.08.2026) |
| [42_TREIBER_SCHAERFEN_2026-08-17.md](42_TREIBER_SCHAERFEN_2026-08-17.md) | Vorgeschichte der Treiber-Analyse |
| Dieser README | Erstaufsetzung des Deployments |

---

## Wann läuft was

| Workflow | Takt (UTC) |
|---|---|
| `nightly-update.yml` — Sammler, Auswertung, Dashboard-Neubau | täglich 05:30 (real ~06:29) |
| `peec-daily-sources.yml` — Peec-Quellen | täglich 04:00 |
| `pipeline-waechter.yml` — Frischeprüfung | täglich 09:00 |
| `weekly-prices.yml` — Check24 | montags 05:45 |
| `analyze.yml` (Repo `geo-visibility-tool`) — **der eigentliche Messlauf** | montags 23:10 |
| `dashboard-deploy.yml` — Auslieferung | **nur manuell** |

Die vollständige Liste steht in Kapitel 5 der Projektdokumentation. Wichtig:
Der Messlauf ist **wöchentlich**; das Dashboard aktualisiert sich täglich, die
Messung dahinter nicht. Und der Deploy löst nicht automatisch aus — nach jeder
Anzeige-Änderung muss „Dashboard ausliefern" von Hand gestartet werden.

---

## Erstaufsetzung des Deployments

Dieser Abschnitt ist die ursprüngliche Einrichtungsanleitung. Er wird nur
gebraucht, wenn das Cockpit neu aufgesetzt wird.

**Zielsetzung:**
- Dashboard liegt auf GitHub Pages unter `https://phoeser.github.io/LLM-Cockpit/`
- Zugriff nur mit Passwort (Secret `DASHBOARD_PASSWORD`)
- Ein nächtlicher Job lädt die neuesten GEO-Daten und aktualisiert das Dashboard

### Schritt 1 — Neues GitHub-Repository anlegen

1. Auf [github.com](https://github.com) anmelden
2. Oben rechts auf **+** → **New repository** klicken
3. **Repository name:** `LLM-Cockpit`
4. Auf **Public** setzen (wir nutzen StatiCrypt-Verschlüsselung statt privater
   Repos, weil Pages sonst Pro braucht)
5. Häkchen bei „Add a README file" entfernen
6. **Create repository** klicken

### Schritt 2 — Diesen Ordner ins Repo hochladen

1. Im neuen Repo auf **„uploading an existing file"** klicken
2. **Den kompletten Inhalt** des `github-deployment/`-Ordners hochziehen
   (Dateien: `README.md`, `index.html`, `scripts/`, `.github/workflows/`)
3. Unten **Commit changes** klicken

### Schritt 3 — Secrets im Repo hinterlegen

GitHub muss zwei Werte kennen, die NICHT im Code stehen sollen:

1. Im Repo oben: **Settings** → linke Seitenleiste **Secrets and variables → Actions**
2. Knopf **„New repository secret"** drücken und anlegen:

| Name | Wert |
|------|------|
| `DASHBOARD_PASSWORD` | das gewünschte Dashboard-Passwort |
| `GEO_REPO_TOKEN` | Personal Access Token mit Lesezugriff auf das GEO-Repo (siehe Schritt 4) |

### Schritt 4 — Personal Access Token (PAT) erstellen

Damit die GitHub-Action das GEO-Repo lesen kann:

1. Profil oben rechts → **Settings** → **Developer settings** (ganz unten links)
2. **Personal access tokens** → **Fine-grained tokens** → **Generate new token**
3. **Token name:** `LLM-Cockpit Update`
4. **Resource owner:** `phoeser`
5. **Repository access:** „Only select repositories" → das GEO-Repo auswählen
6. **Permissions:** unter „Repository permissions" → **Contents: Read-only**
7. **Generate token** → den Token kopieren und als Secret `GEO_REPO_TOKEN`
   (Schritt 3) hinterlegen
   *(Achtung: Token wird nur einmal angezeigt!)*

### Schritt 5 — GitHub Pages aktivieren

1. Im LLM-Cockpit-Repo: **Settings → Pages**
2. **Source:** „Deploy from a branch" auswählen
3. **Branch:** `main`, **Folder:** `/ (root)`
4. **Save**
5. Nach ca. 1 Minute erscheint oben der Link:
   `https://phoeser.github.io/LLM-Cockpit/`

### Schritt 6 — Erster Deployment-Run starten

1. Im Repo: **Actions**
2. Falls Hinweis erscheint: **„I understand my workflows, go ahead and enable them"** klicken
3. In der Liste **„Nightly Dashboard Update"** auswählen
4. Rechts oben **Run workflow** → **Run workflow** drücken
5. Nach einigen Minuten ist der Lauf grün

### Schritt 7 — Testen

1. `https://phoeser.github.io/LLM-Cockpit/` in einem Browser öffnen
   (auch auf dem Smartphone möglich)
2. Es erscheint ein Passwort-Feld
3. Passwort eingeben
4. Dashboard wird entschlüsselt und angezeigt

---

## Passwort später ändern

1. Im Repo: **Settings → Secrets and variables → Actions**
2. Bei `DASHBOARD_PASSWORD`: **Update**
3. Neues Passwort speichern
4. **Actions → Nightly Dashboard Update → Run workflow** (einmal manuell, damit
   das neue Passwort sofort angewendet wird)

---

## Was bei jedem Lauf passiert

1. die neueste `data/runs/latest.json` aus dem GEO-Repo wird geholt,
2. alle Sammler und die Auswertung laufen,
3. der Snapshot wird ins Dashboard-HTML eingebettet,
4. das Ergebnis wird mit StatiCrypt verschlüsselt,
5. als `index.html` im Repo gespeichert,
6. und von GitHub Pages ausgeliefert.

---

## Hilfe / Probleme

**„Workflow schlägt fehl mit Status 401"** → Token-Secret falsch oder
abgelaufen, oder das API-Guthaben eines Anbieters ist aufgebraucht. Erst im
Run-Protokoll nachsehen, welche der beiden Ursachen zutrifft — beide sehen von
außen gleich aus.

**„Dashboard zeigt nur das Passwort-Feld an, Eingabe funktioniert nicht"** →
Browser-JS deaktiviert oder Cache-Problem. Hard-Refresh (Strg+F5).

**„Daten sind nicht aktuell"** → Der Messlauf ist wöchentlich. Ein neuer
Nightly-Lauf bringt keine neuen Messdaten, wenn im GEO-Repo kein neuer Run
liegt.

**„Meine Änderung am Dashboard ist nicht sichtbar"** → Der Deploy löst nicht
automatisch aus. **Actions → „Dashboard ausliefern" → Run workflow.**
