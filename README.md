# LLM-Cockpit – GitHub-Deployment

Dieses Paket macht aus dem lokalen Dashboard ein **passwortgeschütztes Web-Cockpit**, das über das Internet erreichbar ist und sich **jede Nacht automatisch aktualisiert**.

**Zielsetzung:**
- Dashboard liegt auf GitHub Pages unter `https://phoeser.github.io/LLM-Cockpit/`
- Zugriff nur mit Passwort `LLM2026` (kann später jederzeit geändert werden)
- Nächtlicher Auto-Update-Job um 02:00 Uhr lädt die neuesten GEO-Daten und aktualisiert das Dashboard

---

## Setup in 7 Schritten (einmalig, ca. 15 Minuten)

### Schritt 1 — Neues GitHub-Repository anlegen

1. Gehen Sie auf [github.com](https://github.com) und melden Sie sich an
2. Oben rechts auf **+** → **New repository** klicken
3. **Repository name:** `LLM-Cockpit`
4. Setzen Sie auf **Public** (wir nutzen StatiCrypt-Verschlüsselung statt private Repos, weil Pages sonst Pro braucht)
5. Häkchen bei „Add a README file" entfernen
6. **Create repository** klicken

### Schritt 2 — Diesen Ordner ins Repo hochladen

1. Im neuen Repo auf **„uploading an existing file"** klicken
2. **Den kompletten Inhalt** dieses `github-deployment/`-Ordners hochziehen
   (Dateien: `README.md`, `index.html`, `scripts/`, `.github/workflows/`)
3. Unten **Commit changes** klicken

### Schritt 3 — Secrets im Repo hinterlegen

GitHub muss zwei Werte kennen, die NICHT im Code stehen sollen:

1. Im Repo oben: **Settings** → linke Seitenleiste **Secrets and variables → Actions**
2. Knopf **„New repository secret"** drücken und folgendes anlegen:

| Name | Wert |
|------|------|
| `DASHBOARD_PASSWORD` | `LLM2026` (oder beliebig anderes) |
| `GEO_REPO_TOKEN` | Personal Access Token mit Zugriff auf das GEO-Repo (siehe Schritt 4) |

### Schritt 4 — Personal Access Token (PAT) erstellen

Damit die GitHub-Action das GEO-Repo lesen kann:

1. Profil oben rechts → **Settings** → **Developer settings** (ganz unten links)
2. **Personal access tokens** → **Fine-grained tokens** → **Generate new token**
3. **Token name:** `LLM-Cockpit Update`
4. **Resource owner:** `phoeser` (Ihr Benutzer)
5. **Repository access:** „Only select repositories" → wählen Sie Ihr GEO-Repo aus
6. **Permissions:** unter „Repository permissions" → **Contents: Read-only**
7. **Generate token** → den Token kopieren und als Secret `GEO_REPO_TOKEN` (Schritt 3) hinterlegen
   *(Achtung: Token wird nur einmal angezeigt!)*

### Schritt 5 — GitHub Pages aktivieren

1. Im LLM-Cockpit-Repo: **Settings → Pages**
2. **Source:** „Deploy from a branch" auswählen
3. **Branch:** `main`, **Folder:** `/ (root)`
4. **Save**
5. Nach ca. 1 Minute erscheint oben Ihr Link:
   `https://phoeser.github.io/LLM-Cockpit/`

### Schritt 6 — Erster Deployment-Run starten

1. Im Repo: **Actions**
2. Falls Hinweis erscheint: **„I understand my workflows, go ahead and enable them"** klicken
3. In der Liste **„Nightly Dashboard Update"** auswählen
4. Rechts oben **Run workflow** → **Run workflow** drücken
5. Nach ca. 2 Minuten ist der Lauf grün

### Schritt 7 — Testen

1. Öffnen Sie `https://phoeser.github.io/LLM-Cockpit/` in einem Browser (auch auf Smartphone möglich)
2. Es erscheint ein Passwort-Feld
3. Passwort eingeben (`LLM2026` oder Ihr neu gewähltes)
4. Dashboard wird entschlüsselt und angezeigt

**Fertig!** Ab jetzt aktualisiert sich das Dashboard jede Nacht um 02:00 Uhr automatisch.

---

## Passwort später ändern

1. Im Repo: **Settings → Secrets and variables → Actions**
2. Bei `DASHBOARD_PASSWORD`: **Update**
3. Neues Passwort speichern
4. **Actions → Nightly Dashboard Update → Run workflow** (einmal manuell, damit das neue Passwort sofort angewendet wird)

---

## Wann läuft das Update?

- **Automatisch:** Jede Nacht um **02:00 Uhr UTC** (= 03:00 MEZ / 04:00 MESZ)
- **Manuell:** Jederzeit über **Actions → Run workflow**
- Bei jedem Lauf wird:
  1. die neueste `data/runs/latest.json` aus dem GEO-Repo geholt,
  2. ins Dashboard-HTML eingebettet,
  3. mit StatiCrypt verschlüsselt,
  4. als `index.html` im Repo gespeichert,
  5. von GitHub Pages automatisch ausgeliefert.

---

## Dateien in diesem Paket

| Datei | Zweck |
|-------|-------|
| `README.md` | Diese Anleitung |
| `index.html` | Erste verschlüsselte Version (wird vom Workflow überschrieben) |
| `dashboard_template.html` | Unverschlüsseltes Template – Basis für jeden Run |
| `scripts/update_snapshot.py` | Holt latest.json aus GEO und bettet sie ins Template ein |
| `scripts/encrypt.py` | Verschlüsselt das Dashboard mit StatiCrypt |
| `.github/workflows/nightly-update.yml` | Der nächtliche Auto-Update-Workflow |
| `requirements.txt` | Python-Pakete für die Skripte |

---

## Hilfe / Probleme

**„Workflow schlägt fehl mit Status 401"** → Token-Secret falsch oder abgelaufen. Schritt 4 wiederholen.

**„Dashboard zeigt nur Passwort-Feld an, aber Eingabe funktioniert nicht"** → Browser-JS ist deaktiviert oder Cache-Problem. Hard-Refresh (Strg+F5).

**„Daten sind nicht aktuell"** → Im GEO-Repo gibt es keinen neuen Run. Erst dort einen neuen Lauf starten, dann hier den Workflow erneut auslösen.
