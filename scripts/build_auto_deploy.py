#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto-Deploy-Seite erzeugen (12.08.2026)
=======================================

Was das ist
-----------
Eine einzelne HTML-Datei zum Doppelklicken. Sie traegt die zu deployenden
Dateien base64-kodiert in sich, schickt sie mit einem GitHub-PAT ueber die
Contents-API nach phoeser/LLM-Cockpit und kann anschliessend Workflows
anstossen. Kein Git, keine Kommandozeile.

Warum es dieses Skript gibt
---------------------------
Die bisherige Auto-Deploy_v3.html wurde einmal von Hand befuellt (Stand
27.04.2026) und danach nie wieder. Am 12.08.2026 nachgemessen: ALLE elf
eingebetteten Dateien waren veraltet, und die Kaestchen "yml-Workflows",
"Python-Skripte" und "dashboard_template.html" waren VORAUSGEWAEHLT. Ein Klick
auf "Push starten" haette unter anderem

    scripts/update_sentiment.py     97.805 Bytes im Repo  <-  6.427 Bytes
    dashboard_template.html      13.340.705 Bytes im Repo  <- 94.418 Bytes

ueberschrieben, also vier Monate Arbeit in einem Zug. Nicht durch einen Fehler
im Code - der Code funktionierte einwandfrei. Sondern weil eine Momentaufnahme
mit der Zeit still falsch wird und nichts sie daran gehindert hat.

Zwei Konsequenzen, beide hier eingebaut:

1. Die Seite wird ERZEUGT, nicht gepflegt. Eingebettet wird genau das, was sich
   zwischen Arbeitsstand und origin/main unterscheidet - das ist die ehrliche
   Definition von "muss noch raus". Wer sie neu braucht, ruft dieses Skript auf.

2. Die Seite prueft vor jedem Push, ob sich die Datei im Repo seit ihrer
   Erzeugung geaendert hat. Dafuer wird zu jeder Datei die Blob-SHA des Standes
   auf origin/main mitgegeben. Stimmt sie beim Push nicht mehr, ist jemand
   anderes (typisch: der Nightly) dazwischengekommen - dann sperrt die Seite
   die Datei und verlangt eine ausdrueckliche Bestaetigung.

Ausserdem ist nichts mehr vorausgewaehlt. Wer alles pushen will, sagt das.

Aufruf
------
    python3 scripts/build_auto_deploy.py                  # gegen origin/main
    python3 scripts/build_auto_deploy.py --out X.html
    python3 scripts/build_auto_deploy.py --datei a.js --datei b.py

Ohne --datei nimmt das Skript alle gegenueber origin/main geaenderten Dateien,
laesst dabei aber data/ und die verschluesselte index.html aussen vor: die
schreibt der Nightly selbst, und sie ueber diese Seite zu pushen hiesse, dem
Nightly ins Steuer zu greifen.
"""

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "phoeser/LLM-Cockpit"

# 13.08.2026: Der Dateiname war fest "Auto-Deploy_v3.html". Im Download-Ordner
# lagen dadurch heute Abend Auto-Deploy_v3.html, _v3_1 bis _v3_6 - der Browser
# haengt bei gleichem Namen eine Nummer an. Welche davon die neueste ist, sieht
# man dem Namen nicht an; die Zaehlung sagt nur, in welcher Reihenfolge geladen
# wurde, nicht wann gebaut. Paul hat folgerichtig _v3_5 geoeffnet, waehrend _v3_6
# die aktuelle war, und bekam eine Fehlermeldung - zu Recht, denn _v3_5 trug
# einen aelteren Stand von build_auto_deploy.py als der, der laengst im Repo lag.
# Ein Push haette die Datei zurueckgedreht.
# Der Bauzeitpunkt gehoert deshalb in den Dateinamen. Dann sortiert der Ordner
# von selbst richtig und die juengste Datei ist die unterste.
STANDARD_OUT_MUSTER = "Auto-Deploy_%s.html"   # %s = 2026-08-13_1408

# Vom Nightly geschrieben - gehoert nicht ueber diese Seite gepusht.
AUSGENOMMEN_PREFIX = ("data/", "shared/")
AUSGENOMMEN_DATEI = ("index.html", "data.enc")
# Die erzeugte Seite selbst - unabhaengig davon, wie sie gerade heisst.
AUSGENOMMEN_MUSTER = ("Auto-Deploy_", "auto_deploy_")

WORKFLOWS = [
    ("nightly-update.yml", "Nightly", "~25 Min"),
    ("peec-daily-sources.yml", "Peec-Quellen", "~3 Min"),
    ("dashboard-deploy.yml", "Nur Dashboard bauen", "~2 Min"),
    ("georg-sync.yml", "GEOrg-Wissensbasis", "~2 Min"),
    # 20.08.2026: wendet Patch-Skripte aus patches/ IM Repo an - der Weg fuer
    # grosse Dateien, deren Aenderung klein ist (siehe apply-patch.yml).
    ("apply-patch.yml", "Patch anwenden", "~1 Min"),
    ("measure-serp-depth.yml", "Tiefentest Social (einmalig)", "~1 Min"),
    # 22.08.2026: Der Preislauf laeuft nur montags. Faellt er aus - wie am
    # 17.08. -, muss man ihn von Hand nachholen koennen, ohne in die
    # GitHub-Oberflaeche zu wechseln.
    ("weekly-prices.yml", "Check24-Preise + Reviews", "~30 Min"),
    # 20.08.2026, Pauls Ansage ("hoer auf, mich alles im GitHub machen zu
    # lassen"): Ein Workflow-Eintrag darf jetzt ein VIERTES Feld tragen - die
    # Dispatch-Inputs. Damit lassen sich auch Laeufe mit gesetzten Schaltern
    # direkt von dieser Seite starten. Vorher ging das nur in der
    # GitHub-Oberflaeche, weil die Seite immer nur {"ref": "main"} schickte.
    #
    # Konkreter Anlass: Beide Social-Sammler drosseln sich selbst auf einen
    # Lauf je Woche. Nach einer Aenderung am Sammler will man das Ergebnis
    # heute sehen und nicht am Wochenende.
    ("nightly-update.yml", "Nightly MIT Social-Force", "~25 Min",
     {"force_linkedin": "true", "force_instagram": "true"}),
]


def git(*args):
    return subprocess.run(["git"] + list(args), cwd=str(ROOT),
                          capture_output=True, text=True)


def geaenderte_dateien():
    # 13.08.2026: Hier stand "git diff origin/main HEAD" (zwei Punkte). Das ist
    # der Unterschied ZWISCHEN beiden Staenden - und der zeigt in BEIDE
    # Richtungen. Ist der lokale Stand hinter origin/main, weil dort inzwischen
    # ein Nightly committet hat, tauchen DESSEN Aenderungen als "muss noch raus"
    # auf. Die Seite haette dann angeboten, den frischen Stand mit dem eigenen
    # aelteren zu ueberschreiben - genau der Fehler, gegen den dieses Werkzeug
    # gebaut wurde, nur eine Ebene hoeher. Aufgefallen, weil auf einmal
    # dashboard_template.html mit 13,3 MB in der Liste stand.
    #
    # Drei Punkte heisst: nur was auf HEAD seit dem gemeinsamen Vorfahren
    # dazugekommen ist. Das ist die richtige Frage.
    r = git("diff", "--name-only", "origin/main...HEAD")
    if r.returncode != 0:
        sys.exit("FEHLER: git diff gegen origin/main fehlgeschlagen. Erst "
                 "'git fetch origin' laufen lassen.\n" + r.stderr[:400])
    aus = [p for p in r.stdout.splitlines() if p.strip()]
    # Und ausdruecklich melden, wenn der lokale Stand hinterherhinkt - dann
    # gehoert rebased, bevor irgendetwas gepusht wird.
    z = git("rev-list", "--count", "HEAD..origin/main")
    if z.returncode == 0 and z.stdout.strip() not in ("", "0"):
        print("HINWEIS: origin/main ist %s Commit(s) voraus. Vor dem Push "
              "'git pull --rebase' - sonst pusht die Seite gegen einen "
              "veralteten Ausgangsstand." % z.stdout.strip())
    r2 = git("status", "--porcelain")
    for line in r2.stdout.splitlines():
        p = line[3:].strip()
        if p and p not in aus:
            aus.append(p)
    return sorted(aus)


def erlaubt(pfad):
    if pfad.startswith(AUSGENOMMEN_PREFIX):
        return False
    if pfad in AUSGENOMMEN_DATEI:
        return False
    if os.path.basename(pfad).startswith(AUSGENOMMEN_MUSTER):
        return False
    return True


def basis_sha(pfad):
    """Blob-SHA des Standes auf origin/main. None = Datei dort noch nicht."""
    r = git("rev-parse", "origin/main:%s" % pfad)
    return r.stdout.strip() if r.returncode == 0 else None


def inhalt_sha(roh):
    """Blob-SHA des Inhalts, den DIESE Seite traegt - nach Git-Formel, damit er
    direkt mit dem vergleichbar ist, was die GitHub-API zurueckmeldet.

    13.08.2026 ergaenzt. Bis hierher kannte die Seite nur zwei SHAs: den Stand,
    gegen den sie gebaut wurde (base_sha), und den, der gerade im Repo liegt.
    Weichen die voneinander ab, meldete sie "im Repo geaendert - Push wuerde das
    ueberschreiben". Das stimmt - ausser im haeufigsten Fall ueberhaupt: die
    Seite hat ihre Dateien selbst gepusht, danach ist der Repo-Stand
    zwangslaeufig ein anderer als die Basis, und beim naechsten Oeffnen warnt sie
    vor sich selbst. Genau das ist Paul heute zweimal passiert.
    Mit dem dritten SHA laesst sich der Fall sauber unterscheiden: Ist der Stand
    im Repo identisch mit dem, was die Seite traegt, ist nichts zu tun und nichts
    zu warnen. Eine Warnung, die immer kommt, wird nicht mehr gelesen - und dann
    fehlt sie an dem Tag, an dem sie zutrifft."""
    return hashlib.sha1(b"blob %d\0" % len(roh) + roh).hexdigest()


def gruppe_von(pfad):
    if pfad.startswith(".github/"):
        return ("workflow", "Workflows und Actions")
    if pfad.startswith("scripts/"):
        return ("skript", "Python-Skripte")
    if pfad.endswith(".js"):
        return ("js", "Dashboard-Bausteine (JS)")
    if pfad.endswith((".html", ".css")):
        return ("seite", "Dashboard-Seiten")
    return ("sonst", "Sonstige")


def sammeln(pfade):
    dateien = []
    for p in pfade:
        f = ROOT / p
        if not f.exists():
            print("   uebersprungen (nicht vorhanden): %s" % p)
            continue
        roh = f.read_bytes()
        gid, glabel = gruppe_von(p)
        dateien.append({
            "remote": p,
            "size": len(roh),
            "b64": base64.b64encode(roh).decode("ascii"),
            "base_sha": basis_sha(p),
            "inhalt_sha": inhalt_sha(roh),
            "gruppe": gid,
            "gruppe_label": glabel,
        })
    return dateien


HTML = u"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>LLM-Cockpit Auto-Deploy</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, Segoe UI, sans-serif; max-width: 820px; margin: 30px auto; padding: 20px; background: #f5f5f5; color: #1f2937; }
  h1 { color: #DC0028; margin-bottom: 4px; font-size: 28px; }
  .subtitle { color: #666; margin-bottom: 6px; }
  .card { background: #fff; padding: 22px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 14px; }
  .card h3 { margin: 0 0 12px; color: #282D37; font-size: 16px; }
  label { display: block; font-weight: 600; margin-bottom: 6px; font-size: 13px; }
  input[type=password] { width: 100%; padding: 10px; border: 2px solid #ddd; border-radius: 6px; font-family: monospace; font-size: 13px; }
  input:focus { outline: none; border-color: #DC0028; }
  button { background: #DC0028; color: #fff; border: 0; padding: 12px 24px; border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer; margin-right: 6px; margin-bottom: 6px; }
  button:hover:not(:disabled) { background: #b1001f; }
  button:disabled { background: #aaa; cursor: not-allowed; }
  button.secondary { background: #4b5563; }
  .file-row { display: flex; justify-content: space-between; gap: 12px; padding: 7px 0; border-bottom: 1px solid #eee; font-family: monospace; font-size: 12px; }
  .file-row .pending { color: #999; } .file-row .running { color: #f5a623; }
  .file-row .ok { color: #2bb673; font-weight: 600; } .file-row .err { color: #DC0028; font-weight: 600; }
  .file-row .warn { color: #b45309; font-weight: 600; }
  .help { font-size: 12px; color: #666; line-height: 1.5; }
  .help a { color: #DC0028; }
  code { background: #eee; padding: 2px 6px; border-radius: 3px; font-size: 11px; }
  fieldset { border: 1px solid #ddd; border-radius: 8px; padding: 10px 14px; margin: 10px 0; }
  legend { font-weight: 600; color: #DC0028; padding: 0 6px; font-size: 13px; }
  .ok-banner { background: #d1fae5; border-left: 3px solid #10b981; padding: 10px 14px; border-radius: 4px; font-size: 13px; }
  .err-banner { background: #fee2e2; border-left: 3px solid #ef4444; padding: 10px 14px; border-radius: 4px; font-size: 13px; }
  .warn-banner { background: #fff8ed; border-left: 3px solid #b45309; padding: 10px 14px; border-radius: 4px; font-size: 13px; color: #7a4a12; }
  .meta { font-size: 11px; color: #888; }
  .runbox { border-left: 4px solid #999; padding: 8px 12px; margin-bottom: 6px; background: #fafafa; border-radius: 4px; font-size: 13px; }
  .btn-link { background: #10b981; color: #fff; padding: 10px 18px; border-radius: 6px; text-decoration: none; font-weight: 600; display: inline-block; }
  .btn-link.gray { background: #4b5563; margin-left: 6px; }
  .dateiz { font-family: monospace; font-size: 12px; padding: 3px 0; }
</style>
</head>
<body>
<h1>LLM-Cockpit Auto-Deploy</h1>
<p class="subtitle">Token eingeben &rarr; prüfen &rarr; pushen &rarr; Workflow anstoßen.</p>
<p class="meta">Erzeugt __STAND__ aus dem Arbeitsstand, __NDATEIEN__ Dateien, __NBYTES__ Bytes. Gegenstand: alles, was sich zu diesem Zeitpunkt gegenüber <code>origin/main</code> unterschied.</p>

<div class="card">
  <div class="warn-banner">
    <b>Diese Seite ist eine Momentaufnahme.</b> Sie pusht genau den Stand von __STAND__ — nicht mehr und nicht weniger.
    Bevor etwas geschrieben wird, vergleicht sie jede Datei mit dem Repo. Hat sich dort seither etwas geändert
    (typisch: der Nightly war schneller), wird die Datei <b>gesperrt</b> und muss einzeln freigegeben werden.
    <br><br>
    Neu erzeugen mit <code>python3 scripts/build_auto_deploy.py</code>. Eine alte Auto-Deploy-Datei bitte löschen statt
    aufheben — genau daran ist die Vorgängerversion gescheitert: Sie trug vier Monate alte Dateien und hätte
    <code>update_sentiment.py</code> von 97.805 auf 6.427 Bytes zurückgesetzt, mit einem Klick.
  </div>
</div>

<div class="card">
  <h3>1. GitHub Token</h3>
  <label for="token">Personal Access Token (PAT)</label>
  <input type="password" id="token" placeholder="github_pat_... oder ghp_...">
  <div style="margin-top:8px;">
    <label style="display:inline;font-weight:400;">
      <input type="checkbox" id="rememberToken" style="margin-right:6px;"> Token in diesem Browser speichern (localStorage, nur dieser PC)
    </label>
  </div>
  <p class="help">Braucht <strong>Contents: Read+Write</strong>; für Dateien unter <code>.github/</code> zusätzlich <strong>Workflows: Read+Write</strong>; zum Anstoßen in Abschnitt 3 ausserdem <strong>Actions: Read+Write</strong> — ein anderes Häkchen als "Workflows". <a href="https://github.com/settings/tokens?type=beta" target="_blank">Token erstellen</a></p>
</div>

<div class="card">
  <h3>2. Was pushen?</h3>
  <p class="help" style="margin-top:0">Bewusst nichts vorausgewählt.</p>
  <div id="gruppen"></div>
  <div style="margin-top:10px">
    <button class="secondary" onclick="pruefen()">Erst prüfen (schreibt nichts)</button>
    <button onclick="startDeploy()">Push starten</button>
  </div>
</div>

<div class="card">
  <h3>3. Workflow anstoßen</h3>
  <div id="wfBtns"></div>
  <p class="help">Stößt ohne Push an. Status unten, Auto-Refresh alle 8 Sek. Klappt das nicht, geht es immer auch ohne Token über die <a href="https://github.com/phoeser/LLM-Cockpit/actions" target="_blank">Actions-Oberfläche</a> (Workflow wählen &rarr; <b>Run workflow</b>).</p>
</div>

<div class="card">
  <h3>4. Workflow-Status (live)</h3>
  <button class="secondary" onclick="refreshStatus()">Status aktualisieren</button>
  <span class="meta" id="lastRefresh" style="margin-left:8px"></span>
  <div id="runDetails" style="margin-top:10px;"><em>Status aktualisieren oder einen Workflow anstoßen.</em></div>
  <p style="margin-top:14px;">
    <a href="https://phoeser.github.io/LLM-Cockpit/" target="_blank" class="btn-link">Cockpit öffnen</a>
    <a href="https://github.com/phoeser/LLM-Cockpit/actions" target="_blank" class="btn-link gray">GitHub Actions</a>
  </p>
  <p class="help">Nach grünem Lauf im Cockpit <strong>STRG+SHIFT+R</strong> (Hard-Reload).</p>
</div>

<div class="card" id="statusCard" style="display:none;">
  <h3>Status</h3>
  <div id="fileList"></div>
  <p id="finalStatus" style="margin-top:14px;"></p>
</div>

<script>
const REPO = "__REPO__";
const STAND = "__STAND__";
const FILES = __FILES__;
const WORKFLOWS = __WORKFLOWS__;
/* Dateien, die der Nutzer nach einer Warnung ausdruecklich freigegeben hat. */
const FREIGABE = new Set();

window.addEventListener('DOMContentLoaded', function () {
  var t = localStorage.getItem('llm_cockpit_token');
  if (t) { document.getElementById('token').value = t; document.getElementById('rememberToken').checked = true; }
  document.getElementById('rememberToken').addEventListener('change', function (e) {
    if (!e.target.checked) localStorage.removeItem('llm_cockpit_token');
  });
  bauGruppen(); bauWorkflows();
});
function saveTokenIfWanted() {
  var t = document.getElementById('token').value.trim();
  if (document.getElementById('rememberToken').checked && t) localStorage.setItem('llm_cockpit_token', t);
}
function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
function id4(p){ return "f_" + p.replace(/[^a-z0-9]/gi, "_"); }

function bauGruppen() {
  var g = {};
  FILES.forEach(function (f) { (g[f.gruppe] = g[f.gruppe] || {label: f.gruppe_label, files: []}).files.push(f); });
  var h = "";
  Object.keys(g).forEach(function (k) {
    h += '<fieldset><legend>' + esc(g[k].label) + ' (' + g[k].files.length + ')</legend>';
    g[k].files.forEach(function (f) {
      h += '<div class="dateiz"><label style="display:inline;font-weight:400">'
        + '<input type="checkbox" style="margin-right:7px" id="' + id4(f.remote) + '" data-remote="' + esc(f.remote) + '">'
        + esc(f.remote) + ' <span class="meta">(' + f.size.toLocaleString('de-DE') + ' B'
        + (f.base_sha ? '' : ', neu im Repo') + ')</span></label></div>';
    });
    h += '</fieldset>';
  });
  if (h) { document.getElementById("gruppen").innerHTML = h; return; }
  /* Leerer Zustand ist der NORMALFALL, sobald alles draussen ist - er darf nicht
     wie ein Fehler aussehen. Die Seite bleibt trotzdem nuetzlich: Workflows
     anstossen und Status beobachten braucht keine eingebetteten Dateien. */
  document.getElementById("gruppen").innerHTML =
    '<div class="ok-banner"><b>Nichts zu pushen.</b> Beim Erzeugen dieser Seite (' + STAND + ') war der '
    + 'Arbeitsstand deckungsgleich mit <code>origin/main</code> — alles ist bereits im Repo. '
    + 'Die Seite bleibt für Abschnitt 3 und 4 nutzbar: Workflow anstoßen und Status beobachten.</div>';
  Array.prototype.forEach.call(document.querySelectorAll('button'), function (x) {
    if (/Push starten|Erst prüfen/.test(x.textContent)) { x.disabled = true; x.title = "Keine Dateien eingebettet"; }
  });
}
function bauWorkflows() {
  document.getElementById("wfBtns").innerHTML = WORKFLOWS.map(function (w, i) {
    return '<button class="secondary" data-wf="' + i + '" onclick="triggerWf(this)">' + esc(w[1]) + ' (' + esc(w[2]) + ')</button>';
  }).join("");
}
function gewaehlt() {
  return FILES.filter(function (f) { var e = document.getElementById(id4(f.remote)); return e && e.checked; });
}

function gh(method, path, body, token) {
  return fetch("https://api.github.com" + path, {
    method: method,
    headers: {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
    body: body ? JSON.stringify(body) : undefined
  });
}

/* Holt die aktuelle Blob-SHA im Repo. null = Datei dort nicht vorhanden.

   20.08.2026, Pauls Befund: Beim Deploy des Instagram-Stands meldete GENAU die
   groesste Datei (correlation_impact.py, 300 KB) "Pruefung fehlgeschlagen:
   Failed to fetch", die acht kleineren gingen durch. Der Grund liegt in der
   alten Zeile darunter: die Contents-API liefert bei einer GET-Abfrage den
   VOLLSTAENDIGEN Dateiinhalt base64-kodiert mit - fuer 300 KB Quelltext also
   rund 400 KB Antwort, nur um daraus ein 40 Zeichen langes SHA zu lesen.
   "Failed to fetch" ist kein HTTP-Status, sondern der Abbruch der Verbindung
   selbst; je groesser die Antwort, desto wahrscheinlicher.

   Zwei Aenderungen, die das an der Wurzel beheben:

   1. Die SHAs kommen jetzt aus der Git-Trees-API - EIN Aufruf fuer das ganze
      Repo, der nur Pfade und SHAs enthaelt, keinen Dateiinhalt. Die Antwort
      ist damit unabhaengig von der Dateigroesse, und neun Einzelabfragen
      werden zu einer.
   2. Falls dieser Weg nicht geht (abgeschnittener Baum bei sehr grossen
      Repos), faellt die Pruefung auf die Einzelabfrage zurueck - dann aber
      mit einem zweiten Versuch nach kurzer Pause, statt beim ersten
      Netz-Zucken aufzugeben. */
var TREE_CACHE = null;
async function ladeBaum(token) {
  if (TREE_CACHE) return TREE_CACHE;
  var r = await gh("GET", "/repos/" + REPO + "/git/trees/main?recursive=1", null, token);
  if (!r.ok) throw new Error("HTTP " + r.status);
  var j = await r.json();
  if (j.truncated) return null;   /* Repo zu gross fuer einen Baum -> Einzelweg */
  var m = {};
  (j.tree || []).forEach(function (e) { if (e.type === "blob") m[e.path] = e.sha; });
  TREE_CACHE = m;
  return m;
}
async function repoShaEinzeln(remote, token) {
  var letzter = null;
  for (var v = 0; v < 2; v++) {
    try {
      var r = await gh("GET", "/repos/" + REPO + "/contents/" + remote + "?ref=main", null, token);
      if (r.status === 404) return null;
      if (!r.ok) throw new Error("HTTP " + r.status);
      return (await r.json()).sha;
    } catch (e) {
      letzter = e;
      await new Promise(function (s) { setTimeout(s, 900); });
    }
  }
  throw letzter;
}
async function repoSha(remote, token) {
  try {
    var baum = await ladeBaum(token);
    if (baum) return Object.prototype.hasOwnProperty.call(baum, remote) ? baum[remote] : null;
  } catch (e) { /* bewusst still: der Einzelweg unten ist die Antwort darauf */ }
  return await repoShaEinzeln(remote, token);
}

/* Kern der Absicherung: stimmt die Repo-SHA noch mit dem Stand ueberein, gegen
   den diese Seite gebaut wurde? Wenn nicht, ist seither jemand anderes dran
   gewesen und ein Push wuerde dessen Arbeit ueberschreiben. */
async function pruefeEine(f, token) {
  var sha = await repoSha(f.remote, token);
  /* Zuerst die Frage, die alles andere erledigt: liegt im Repo bereits genau
     das, was diese Seite trägt? Dann ist nichts zu tun — egal, ob die Basis
     noch stimmt. Diese Prüfung stand hier bis zum 13.08.2026 nicht, und genau
     deshalb warnte die Seite nach jedem erfolgreichen Push vor sich selbst. */
  if (sha !== null && sha === f.inhalt_sha) return {stand: "deployt", sha: sha};
  if (f.base_sha === null && sha === null) return {stand: "neu", sha: null};
  if (f.base_sha === null && sha !== null) return {stand: "fremd", sha: sha};
  if (sha === null) return {stand: "geloescht", sha: null};
  if (sha === f.base_sha) return {stand: "unveraendert", sha: sha};
  return {stand: "fremd", sha: sha};
}

function zeileSetzen(remote, text, klasse) {
  var e = document.getElementById("s_" + id4(remote));
  if (e) { e.textContent = text; e.className = klasse; }
}
function listeAufbauen(todo) {
  document.getElementById("statusCard").style.display = "block";
  var list = document.getElementById("fileList"); list.innerHTML = "";
  todo.forEach(function (f) {
    var row = document.createElement("div");
    row.className = "file-row";
    row.innerHTML = '<span>' + esc(f.remote) + ' (' + f.size.toLocaleString('de-DE') + ' B)</span>'
                  + '<span class="pending" id="s_' + id4(f.remote) + '">wartet</span>';
    list.appendChild(row);
  });
  document.getElementById("finalStatus").innerHTML = "";
}

async function pruefen() {
  var token = document.getElementById("token").value.trim();
  if (!token) { alert("Bitte Token eingeben."); return; }
  saveTokenIfWanted();
  var todo = gewaehlt();
  if (!todo.length) { alert("Keine Datei ausgewählt."); return; }
  listeAufbauen(todo);
  TREE_CACHE = null;   /* jeder Lauf sieht den frischen Repo-Stand */
  /* 13.08.2026: Warnung und Fehler standen beide in Rot. Paul hat die Meldung
     "IM REPO GEÄNDERT" folgerichtig als "2 Fehler" gelesen und eine Stunde nach
     einem Fehler gesucht, den es nicht gab - der Push war laengst durch. Eine
     Warnung, die aussieht wie ein Fehler, ist ein Fehler im Werkzeug, nicht im
     Verstaendnis des Lesers. Jetzt: Bernstein mit Warndreieck fuer "muss
     bestaetigt werden", Rot ausschliesslich fuer "hat nicht funktioniert". */
  var fremd = 0, fehlerhaft = 0, deployt = 0;
  for (var i = 0; i < todo.length; i++) {
    var f = todo[i];
    zeileSetzen(f.remote, "prüfe…", "running");
    try {
      var p = await pruefeEine(f, token);
      if (p.stand === "deployt") { zeileSetzen(f.remote, "✓ bereits im Repo — identisch, nichts zu tun", "ok"); deployt++; }
      else if (p.stand === "unveraendert") zeileSetzen(f.remote, "im Repo unverändert seit " + STAND + " — sicher", "ok");
      else if (p.stand === "neu") zeileSetzen(f.remote, "wird neu angelegt", "ok");
      else if (p.stand === "geloescht") { zeileSetzen(f.remote, "im Repo gelöscht — wird wieder angelegt", "warn"); fremd++; }
      else { zeileSetzen(f.remote, "⚠ Achtung: im Repo geändert — Push würde das überschreiben", "warn"); fremd++; }
    } catch (e) { zeileSetzen(f.remote, "FEHLER — Prüfung fehlgeschlagen: " + e.message, "err"); fehlerhaft++; }
  }
  var s = "";
  if (fehlerhaft) {
    s += '<div class="err-banner"><b>' + fehlerhaft + ' Prüfung(en) fehlgeschlagen.</b> Das ist ein echter Fehler — '
       + 'Token, Berechtigung oder Netz. Details in der Liste oben.</div>';
  }
  if (fremd) {
    s += '<div class="warn-banner"><b>⚠ ' + fremd + ' Datei(en) haben sich im Repo geändert</b>, seit diese Seite erzeugt wurde — '
       + '<b>kein Fehler</b>, sondern die Sicherung, die anschlägt. Ein Push würde diese Änderungen überschreiben. '
       + 'Entweder die Seite neu erzeugen (<code>python3 scripts/build_auto_deploy.py</code>) oder beim Push einzeln bestätigen.</div>';
  }
  if (deployt === todo.length && !fehlerhaft) {
    s = '<div class="ok-banner"><b>Diese Seite ist erledigt.</b> Alle ' + deployt + ' Datei(en) liegen bereits '
      + 'unverändert im Repo — sie wurden von dieser Seite gepusht. Es gibt nichts mehr zu tun; '
      + 'du kannst sie löschen. Workflows in Abschnitt 3 funktionieren weiterhin.</div>';
  } else if (deployt) {
    s = '<div class="ok-banner"><b>' + deployt + ' Datei(en) liegen bereits im Repo</b> und werden übersprungen.</div>' + s;
  }
  if (!fremd && !fehlerhaft && !deployt) {
    s = '<div class="ok-banner"><b>Alles unverändert.</b> Push ist gefahrlos.</div>';
  }
  document.getElementById("finalStatus").innerHTML = s;
}

async function pushOne(f, token, sha) {
  var body = {message: "chore: " + f.remote + " via Auto-Deploy (" + STAND + ")", content: f.b64, branch: "main"};
  if (sha) body.sha = sha;
  var p = await gh("PUT", "/repos/" + REPO + "/contents/" + f.remote, body, token);
  if (!p.ok) throw new Error("HTTP " + p.status + ": " + (await p.text()).substring(0, 140));
  /* Nach jedem Push ist der zwischengespeicherte Baum veraltet. */
  TREE_CACHE = null;
}

async function startDeploy() {
  var token = document.getElementById("token").value.trim();
  if (!token || (token.indexOf("ghp_") !== 0 && token.indexOf("github_pat_") !== 0)) { alert("Bitte gültigen GitHub-PAT eingeben."); return; }
  saveTokenIfWanted();
  var todo = gewaehlt();
  if (!todo.length) { alert("Keine Datei ausgewählt."); return; }
  listeAufbauen(todo);
  TREE_CACHE = null;   /* jeder Lauf sieht den frischen Repo-Stand */
  var ok = 0, err = 0, uebersprungen = 0, deployt = 0;
  for (var i = 0; i < todo.length; i++) {
    var f = todo[i];
    zeileSetzen(f.remote, "prüfe…", "running");
    var p;
    try { p = await pruefeEine(f, token); }
    catch (e) { zeileSetzen(f.remote, "Prüfung fehlgeschlagen: " + e.message, "err"); err++; continue; }

    /* Schon identisch im Repo: nicht schreiben. Ein Commit, der nichts aendert,
       ist kein harmloser Leerlauf - er laesst die Datei frisch angefasst
       aussehen und macht spaeter die Frage "wer war da zuletzt dran" unbrauchbar. */
    if (p.stand === "deployt") { zeileSetzen(f.remote, "✓ bereits im Repo — übersprungen", "ok"); deployt++; continue; }

    if (p.stand === "fremd" || p.stand === "geloescht") {
      if (!FREIGABE.has(f.remote)) {
        var frage = p.stand === "geloescht"
          ? (f.remote + "\\n\\nDiese Datei wurde im Repo GELÖSCHT, seit diese Seite erzeugt wurde.\\n\\nWieder anlegen?")
          : (f.remote + "\\n\\nDiese Datei wurde im Repo GEÄNDERT, seit diese Seite erzeugt wurde (" + STAND + ").\\n\\n"
             + "Ein Push macht diese Änderung rückgängig. Wirklich überschreiben?");
        if (!window.confirm(frage)) { zeileSetzen(f.remote, "übersprungen (nicht bestätigt)", "warn"); uebersprungen++; continue; }
        FREIGABE.add(f.remote);
      }
    }
    zeileSetzen(f.remote, "pusht…", "running");
    try { await pushOne(f, token, p.sha); zeileSetzen(f.remote, "OK", "ok"); ok++; }
    catch (e) { zeileSetzen(f.remote, "FEHLER: " + e.message.substring(0, 90), "err"); err++; }
  }
  var s = "<b>" + ok + " gepusht</b>";
  if (deployt) s += ", " + deployt + " lagen bereits identisch im Repo";
  if (uebersprungen) s += ", " + uebersprungen + " auf deinen Wunsch übersprungen";
  if (err) s += ", " + err + " fehlgeschlagen";
  document.getElementById("finalStatus").innerHTML = (err === 0)
    ? '<div class="' + (uebersprungen ? 'warn-banner' : 'ok-banner') + '">' + s + '. '
      + (uebersprungen ? 'Übersprungen heißt: nichts kaputt, nur nicht geschrieben. ' : '')
      + (ok === 0 && !uebersprungen ? 'Diese Seite hat ihre Arbeit hinter sich — du kannst sie löschen. ' : 'Workflow in Abschnitt 3 anstoßen.')
      + '</div>'
    : '<div class="err-banner">' + s + '.</div>';
}

var autoPoll = false, pollTimer = null;

/* 13.08.2026: Hier stand kein try/catch. Schlaegt fetch auf NETZWERKEBENE fehl -
   und genau das passiert, wenn die Seite per file:// geoeffnet ist, weil der
   Browser dann ohne Herkunftsangabe anfragt -, wirft der Aufruf eine Ausnahme,
   die nirgends aufgefangen wurde. Der Klick tat sichtbar GAR NICHTS: keine
   Meldung, kein Fehler, nichts. Fuer den Push war die Fehlerbehandlung sorgfaeltig,
   fuers Anstossen fehlte sie ganz - der klassische Fall, dass die Sorgfalt am
   Hauptweg endet. Jetzt sagt jeder Fehlschlag, was los ist und was zu tun ist. */
function wfFehler(text) {
  document.getElementById("runDetails").innerHTML = '<div class="err-banner">' + text + '</div>';
}
async function triggerWf(el) {
  var token = document.getElementById("token").value.trim();
  if (!token) { alert("Token eingeben."); return; }
  saveTokenIfWanted();
  /* el ist der Knopf; sein data-wf zeigt auf den WORKFLOWS-Eintrag. Ein
     vierter Eintrag darin sind die Dispatch-Inputs (z.B. Force-Schalter). */
  var eintrag = WORKFLOWS[parseInt(el.getAttribute("data-wf"), 10)] || [];
  var wf = eintrag[0], inputs = eintrag[3] || null;
  var koerper = {ref: "main"};
  if (inputs) koerper.inputs = inputs;
  var r;
  try {
    r = await gh("POST", "/repos/" + REPO + "/actions/workflows/" + wf + "/dispatches", koerper, token);
  } catch (e) {
    wfFehler('<b>Die Anfrage kam nicht bei GitHub an.</b> Meldung des Browsers: <code>' + esc(e.message) + '</code>.<br><br>'
      + (location.protocol === "file:"
         ? 'Diese Seite ist per <code>file://</code> geöffnet. Dabei schickt der Browser die Anfrage ohne Herkunftsangabe, und GitHub weist sie je nach Browser ab. '
         : '')
      + 'Sicherer Weg ohne Token: <a href="https://github.com/' + REPO + '/actions/workflows/' + esc(wf) + '" target="_blank">'
      + 'diesen Workflow auf GitHub öffnen</a> und dort rechts auf <b>Run workflow</b> klicken.');
    return;
  }
  if (r.ok) {
    document.getElementById("runDetails").innerHTML = "<em>" + esc(wf) + " angestoßen. Status in 5 Sek…</em>";
    setTimeout(function () { autoPoll = true; pollLoop(); }, 5000);
    return;
  }
  var txt = "";
  try { txt = (await r.text()).substring(0, 200); } catch (e) {}
  if (r.status === 403 || r.status === 404) {
    /* GitHub antwortet bei fehlender Actions-Berechtigung mit 404, nicht mit 403 -
       es gibt nicht preis, dass es die Ressource gibt. Deshalb beide Faelle
       gemeinsam erklaeren, statt bei 404 "gibt es nicht" zu behaupten. */
    wfFehler('<b>GitHub hat abgelehnt (HTTP ' + r.status + ').</b> Fast immer fehlt dem Token die Berechtigung '
      + '<b>Actions: Read and write</b>. Das ist ein ANDERES Häkchen als <i>Workflows: Read and write</i> — '
      + 'letzteres erlaubt nur, Workflow-<i>Dateien</i> zu ändern, nicht sie zu starten. Die Namen laden zum Verwechseln ein.<br><br>'
      + 'Entweder das Häkchen unter <a href="https://github.com/settings/tokens?type=beta" target="_blank">Token-Einstellungen</a> ergänzen, '
      + 'oder ohne Token: <a href="https://github.com/' + REPO + '/actions/workflows/' + esc(wf) + '" target="_blank">Workflow auf GitHub öffnen</a> → <b>Run workflow</b>.'
      + (txt ? '<br><br><span class="meta">Antwort: ' + esc(txt) + '</span>' : ''));
  } else {
    wfFehler('<b>Fehler HTTP ' + r.status + '.</b> ' + esc(txt));
  }
}
async function refreshStatus() {
  var token = document.getElementById("token").value.trim();
  if (!token) { alert("Token eingeben."); return; }
  var r;
  try { r = await gh("GET", "/repos/" + REPO + "/actions/runs?per_page=5", null, token); }
  catch (e) { autoPoll = false; wfFehler('<b>Statusabfrage kam nicht bei GitHub an.</b> <code>' + esc(e.message) + '</code>. '
      + 'Direkt nachsehen: <a href="https://github.com/' + REPO + '/actions" target="_blank">Actions-Übersicht</a>.'); return; }
  if (!r.ok) { autoPoll = false; wfFehler('Statusabfrage fehlgeschlagen: HTTP ' + r.status
      + (r.status === 403 || r.status === 404 ? ' — dem Token fehlt vermutlich <b>Actions: Read</b>.' : '')); return; }
  var runs = (await r.json()).workflow_runs || [];
  document.getElementById("runDetails").innerHTML = runs.map(function (x) {
    var farbe = x.status !== "completed" ? "#f5a623" : (x.conclusion === "success" ? "#2bb673" : "#DC0028");
    var txt = x.status !== "completed" ? "läuft…" : (x.conclusion === "success" ? "grün" : ("rot — " + esc(x.conclusion || "")));
    return '<div class="runbox" style="border-left-color:' + farbe + '"><b>' + esc(x.name) + '</b> — ' + txt
         + ' <span class="meta">' + esc((x.created_at || "").replace("T", " ").replace("Z", " UTC")) + '</span> '
         + '<a href="' + x.html_url + '" target="_blank">öffnen</a></div>';
  }).join("") || "<em>Keine Läufe gefunden.</em>";
  document.getElementById("lastRefresh").textContent = "zuletzt " + new Date().toLocaleTimeString("de-DE");
  var laeuft = runs.some(function (x) { return x.status !== "completed"; });
  if (!laeuft) autoPoll = false;
}
function pollLoop() {
  if (pollTimer) clearTimeout(pollTimer);
  refreshStatus();
  if (autoPoll) pollTimer = setTimeout(pollLoop, 8000);
}
</script>
</body>
</html>
"""


def main():
    jetzt = datetime.now(timezone.utc)
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / (STANDARD_OUT_MUSTER % jetzt.strftime("%Y-%m-%d_%H%M"))))
    ap.add_argument("--datei", action="append", default=None,
                    help="Einzelne Datei einbetten (mehrfach moeglich). Ohne Angabe: "
                         "alles, was sich gegenueber origin/main unterscheidet.")
    args = ap.parse_args()

    if args.datei:
        pfade = args.datei
    else:
        pfade = [p for p in geaenderte_dateien() if erlaubt(p)]
        raus = [p for p in geaenderte_dateien() if not erlaubt(p)]
        if raus:
            print("Nicht eingebettet (schreibt der Nightly selbst): %s" % ", ".join(raus))

    if not pfade:
        # 13.08.2026: Bis hierher wurde auch dann eine Seite geschrieben, die
        # nichts enthielt. Im Download-Ordner ist die von einer echten nicht zu
        # unterscheiden - man klickt sie an, es passiert nichts, und man sucht
        # den Fehler bei sich. Eine leere Seite ist kein Ergebnis, sondern ein
        # Missverstaendnis in Dateiform.
        print("Nichts einzubetten - Arbeitsstand und origin/main sind deckungsgleich.")
        print("Es wird KEINE Seite geschrieben: eine leere Auto-Deploy waere nicht")
        print("von einer gefuellten zu unterscheiden und wuerde nur Verwirrung stiften.")
        return 0
    dateien = sammeln(pfade)

    stand = jetzt.strftime("%d.%m.%Y %H:%M UTC")
    html = (HTML
            .replace("__REPO__", REPO)
            .replace("__FILES__", json.dumps(dateien, ensure_ascii=False))
            .replace("__WORKFLOWS__", json.dumps(WORKFLOWS, ensure_ascii=False))
            .replace("__NDATEIEN__", str(len(dateien)))
            .replace("__NBYTES__", "{:,}".format(sum(d["size"] for d in dateien)).replace(",", "."))
            .replace("__STAND__", stand))

    out = Path(args.out)
    out.write_text(html, encoding="utf-8")
    print("\nAuto-Deploy geschrieben: %s (%d KB)" % (out, out.stat().st_size // 1024))
    print("Stand: %s" % stand)
    for d in dateien:
        print("   %-52s %9d B   origin/main-SHA %s" %
              (d["remote"], d["size"], (d["base_sha"] or "-")[:8]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
