"""
Holt den juengsten Websuche-A/B-Datensatz (gepaartes Experiment) aus dem
GEO-Repo und schreibt eine KOMPAKTE data/search_ab.json fuer das Dashboard.

Warum ein eigenes Skript: die Rohdatei im GEO-Repo ist ~2,8 MB gross, weil
sie alle 600 Modellantworten im Volltext enthaelt. Ins Cockpit gehoeren nur
die Aggregate — Kennzahlentabelle, Je-Produkt-Zeilen, Gegenproben, Grenzen.
Es werden KEINE Rohantworten uebernommen; die Zieldatei bleibt < 100 KB.

Ablauf (Datenbezug identisch zu scripts/merge_geo_page_events.py):
1. GitHub Trees API: rekursiver Dateibaum des GEO-Repos
2. Filtere auf data/experiments/search_ab_*.json, waehle den juengsten
   (Dateiname traegt einen ISO-Zeitstempel und sortiert damit lexikografisch)
3. Lade den Blob via Blobs API (base64) — die Contents-API scheitert an der
   1-MB-Grenze, die Blobs-API traegt bis 100 MB
4. Lade die gleichnamige .md daneben, um die redaktionellen Texte
   (Lesehilfe / Grenzen) uebernehmen zu koennen statt sie zu doppeln
5. Verdichte zu data/search_ab.json

Fehlt die Quelle, wird available:false MIT Grund geschrieben — nie Nullen.
Existiert bereits eine gute Datei, bleibt sie bei einem Fehlversuch stehen
("keine Daten ist kein Befund"), das Dashboard zeigt dann den alten Stand
samt seinem Datum.

Test/Offline: GEO_LOCAL_DIR=<pfad zu einem geo-visibility-tool-Klon> nutzt
den lokalen Klon statt der API (die API ist nicht ueberall erreichbar).
"""
import base64
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GEO_REPO = os.environ.get("GEO_REPO", "phoeser/geo-visibility-tool")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GEO_LOCAL_DIR = os.environ.get("GEO_LOCAL_DIR", "")
OUT_FILE = Path(os.environ.get("SEARCH_AB_FILE", "data/search_ab.json"))
EXP_DIR = "data/experiments"
EXP_PREFIX = "search_ab_"

# Produktivkanal des Cockpits. Steht bewusst hier und nicht im Experiment:
# das Experiment weiss nichts ueber den Kanal, gegen den es gelesen wird.
# Quelle: geo-visibility-tool/analyzer/llm_clients.py (ChatGPT-Client
# gpt-4o-mini bzw. gpt-4o-mini-search-preview fuer den grounded-Kanal).
PROD_MODELL = "gpt-4o-mini"
PROD_MODELL_QUELLE = "geo-visibility-tool/analyzer/llm_clients.py"

# Reihenfolge und Beschriftung der Kennzahlen im Dashboard.
# einheit: "anteil" = Bruch (0..1, wird als % gezeigt), "zahl", "rang"
METRIK_ORDER = [
    ("sov_pooled", "Share of Voice (gepoolt, wie im Crawl)", "anteil", True),
    ("sov", "Share of Voice (Mittel je Prompt)", "anteil", False),
    ("mentioned", "genannt in", "anteil", False),
    ("mentions", "ERGO-Nennungen je Antwort", "zahl", False),
    ("rank", "Rang (kleiner = besser)", "rang", False),
    ("cited", "zitiert", "anteil", False),
]


# ---------------------------------------------------------------------------
# GitHub-Zugriff (Helfer wie in merge_geo_page_events.py)
# ---------------------------------------------------------------------------
def _headers() -> dict:
    h = {
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "LLM-Cockpit-SearchAB",
    }
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def _api(url: str) -> dict:
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8"))


def _api_raw(url: str) -> bytes:
    """Blob-/Contents-Antwort (base64) als Bytes."""
    blob = _api(url)
    return base64.b64decode(blob.get("content", ""))


def _find_experiments_remote() -> list:
    """Liefert [(pfad, blob_url), ...] aller search_ab_*.json im GEO-Repo."""
    tree_url = f"https://api.github.com/repos/{GEO_REPO}/git/trees/main?recursive=1"
    tree = _api(tree_url)
    if tree.get("truncated"):
        print("[search_ab] WARNUNG: Trees-API truncated=true — Dateibaum "
              "unvollstaendig, der juengste Lauf koennte fehlen")
    out = []
    for item in tree.get("tree", []):
        p = item.get("path", "")
        if (item.get("type") == "blob"
                and p.startswith(EXP_DIR + "/" + EXP_PREFIX)
                and p.endswith(".json")):
            out.append((p, item.get("url")))
    return out


def _load_source() -> tuple:
    """Holt (daten, md_text, pfad, bezugsweg). Wirft bei Misserfolg."""
    if GEO_LOCAL_DIR:
        base = Path(GEO_LOCAL_DIR)
        cands = sorted((base / EXP_DIR).glob(EXP_PREFIX + "*.json"))
        if not cands:
            raise RuntimeError(
                f"keine {EXP_PREFIX}*.json in {base / EXP_DIR}")
        newest = cands[-1]
        data = json.loads(newest.read_text(encoding="utf-8"))
        md_path = newest.with_suffix(".md")
        md = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
        rel = f"{EXP_DIR}/{newest.name}"
        return data, md, rel, f"lokaler Klon ({base})"

    files = _find_experiments_remote()
    if not files:
        raise RuntimeError(
            f"keine {EXP_PREFIX}*.json unter {EXP_DIR} in {GEO_REPO}")
    # Dateiname traegt den ISO-Zeitstempel -> lexikografisch = chronologisch
    files.sort(key=lambda t: t[0])
    path, blob_url = files[-1]
    print(f"[search_ab] {len(files)} Experimente gefunden, juengstes: {path}")
    data = json.loads(_api_raw(blob_url).decode("utf-8"))

    md = ""
    md_path = path[:-5] + ".md"
    try:
        md_url = (f"https://api.github.com/repos/{GEO_REPO}/contents/"
                  f"{md_path}?ref=main")
        md = _api_raw(md_url).decode("utf-8")
    except Exception as e:
        print(f"[search_ab] Begleit-.md nicht ladbar ({e}) — Texte aus dem "
              "JSON allein")
    return data, md, path, f"GitHub API ({GEO_REPO})"


# ---------------------------------------------------------------------------
# Verdichtung
# ---------------------------------------------------------------------------
def _md_section(md: str, ueberschrift: str) -> str:
    """Zieht den Fliesstext einer ##-Sektion aus der Begleit-Markdown."""
    if not md:
        return ""
    m = re.search(r"^##\s+" + re.escape(ueberschrift) + r"\s*$(.*?)(?=^##\s|\Z)",
                  md, re.M | re.S)
    if not m:
        return ""
    return "\n".join(l.strip() for l in m.group(1).strip().splitlines()
                     if l.strip())


def _split_grenzen(lesehilfe: str) -> tuple:
    """Trennt den Lesehilfe-Block in Einordnung und 'Grenzen:'-Absatz."""
    if not lesehilfe:
        return "", ""
    i = lesehilfe.find("Grenzen:")
    if i < 0:
        return lesehilfe, ""
    g = lesehilfe[i + len("Grenzen:"):].strip()
    if g:
        g = g[0].upper() + g[1:]
    return lesehilfe[:i].strip(), g


def _product_names(data: dict) -> dict:
    """product_id -> Anzeigename, aus den Rohantworten (die selbst nicht
    uebernommen werden)."""
    names = {}
    for r in data.get("responses") or []:
        pid, pname = r.get("product_id"), r.get("product_name")
        if pid and pname and pid not in names:
            names[pid] = pname
    return names


def _metrik_rows(metrics: dict) -> list:
    rows = []
    for key, label, einheit, leit in METRIK_ORDER:
        m = (metrics or {}).get(key)
        if not isinstance(m, dict):
            continue
        rows.append({
            "key": key,
            "label": label,
            "einheit": einheit,
            "leitkennzahl": leit,
            "arm_a": m.get("arm_a"),
            "arm_b": m.get("arm_b"),
            "diff": m.get("diff"),
            "ci_low": m.get("ci_low"),
            "ci_high": m.get("ci_high"),
            "ci_excludes_zero": m.get("ci_excludes_zero"),
            "n": m.get("n"),
            "hinweis": m.get("hinweis"),
        })
    return rows


def verdichte(data: dict, md: str, quell_pfad: str, bezug: str) -> dict:
    bs = data.get("bootstrap") or {}
    metrics = bs.get("metrics") or {}
    cc = data.get("counter_checks") or {}
    err = data.get("errors") or {}
    params = data.get("params") or {}
    arms = data.get("arms") or {}
    names = _product_names(data)

    lesehilfe = _md_section(md, "Lesehilfe")
    einordnung, grenzen_txt = _split_grenzen(lesehilfe)

    je_produkt = []
    for pid, blk in sorted((data.get("by_product") or {}).items()):
        m = ((blk or {}).get("metrics") or {}).get("sov_pooled") or {}
        je_produkt.append({
            "product_id": pid,
            "name": names.get(pid, pid),
            "n_pairs": blk.get("n_pairs"),
            "arm_a": m.get("arm_a"),
            "arm_b": m.get("arm_b"),
            "diff": m.get("diff"),
            "ci_low": m.get("ci_low"),
            "ci_high": m.get("ci_high"),
            "ci_excludes_zero": m.get("ci_excludes_zero"),
            "permutation_p": blk.get("permutation_p"),
            "hinweis": m.get("hinweis"),
        })
    # Groesster Effekt oben — im Dashboard als Forest von oben nach unten
    je_produkt.sort(key=lambda r: (r["diff"] is None, -(r["diff"] or 0)))

    out = {
        "available": True,
        "erzeugt_am": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "quelle": {
            "repo": GEO_REPO,
            "pfad": quell_pfad,
            "bezug": bezug,
            "experiment": data.get("experiment"),
            "experiment_id": data.get("experiment_id"),
            "created_at": data.get("created_at"),
            "datum": str(data.get("created_at") or "")[:10],
            "enthaelt_rohantworten": False,
        },
        "modell": data.get("model"),
        "params": {
            "api": params.get("api"),
            "tool_choice": params.get("tool_choice"),
            "temperature": params.get("temperature"),
            "max_tokens": params.get("max_tokens"),
            "search_context_size": params.get("search_context_size"),
        },
        "marke": data.get("brand"),
        "arme": {
            "a": {"key": "forced_search",
                  "label": "mit Suche (erzwungen)",
                  "definition": arms.get("forced_search")},
            "b": {"key": "no_tools",
                  "label": "ohne Suche",
                  "definition": arms.get("no_tools")},
        },
        "umfang": {
            "n_prompts": data.get("n_prompts"),
            "n_prompts_available": data.get("n_prompts_available"),
            "repeats": data.get("repeats"),
            "n_calls": data.get("n_calls"),
            "n_pairs": bs.get("n_pairs"),
            "n_dropped_pairs": len(data.get("dropped_pairs") or []),
            "n_produkte": len(data.get("by_product") or {}),
            "seed": data.get("seed"),
            "prompts_je_produkt": data.get("prompts_per_product") or {},
            "n_bootstrap": bs.get("n_bootstrap"),
            "alpha": bs.get("alpha"),
            "dauer_sekunden": data.get("duration_seconds"),
        },
        "fehler": {
            "n_failed": err.get("n_failed"),
            "arm_a": err.get("arm_a"),
            "arm_b": err.get("arm_b"),
        },
        "kennzahlen": _metrik_rows(metrics),
        "permutation_p": bs.get("permutation_p"),
        "permutation_p_hinweis": bs.get("permutation_p_hinweis"),
        "je_produkt": je_produkt,
        "je_produkt_hinweis": (
            "Rund 30 Antworten je Produkt: diese Intervalle sind breit. Sie "
            "taugen zum Ausschliessen grosser Unterschiede, nicht zum "
            "Rangieren der Produkte untereinander."),
        "gegenproben": {
            "arm_a_ohne_quellen": cc.get("arm_a_ohne_quellen"),
            "arm_a_ok": cc.get("arm_a_ok"),
            "arm_a_ohne_quellen_rate": cc.get("arm_a_ohne_quellen_rate"),
            "arm_a_hinweis": cc.get("arm_a_hinweis"),
            "arm_b_mit_fliesstext_urls": cc.get("arm_b_mit_fliesstext_urls"),
            "arm_b_ok": cc.get("arm_b_ok"),
            "arm_b_mit_fliesstext_urls_rate": cc.get(
                "arm_b_mit_fliesstext_urls_rate"),
            "arm_b_hinweis": cc.get("arm_b_hinweis"),
        },
        "einordnung": einordnung,
        "grenzen_text": grenzen_txt,
        "hinweis": data.get("hinweis"),
        "kosten_usd": (data.get("cost_actual") or {}).get("usd_total_mind"),
    }

    # Vorbehalte: was das Dashboard sichtbar tragen muss, mit Herkunft.
    vorbehalte = []
    if grenzen_txt:
        vorbehalte.append({
            "titel": "Erzwungene Suche ist nicht der Normalfall",
            "text": grenzen_txt,
            "quelle": quell_pfad.replace(".json", ".md"),
        })
    vorbehalte.append({
        "titel": "Anderes Modell als der Produktivkanal",
        "text": (f"Das Experiment lief auf {data.get('model')}; der "
                 f"Produktivkanal des Cockpits misst mit {PROD_MODELL}. "
                 "Die Richtung des Effekts ist uebertragbar, die Hoehe nicht "
                 "eins zu eins."),
        "quelle": PROD_MODELL_QUELLE,
    })
    if cc.get("arm_b_hinweis"):
        rate = cc.get("arm_b_mit_fliesstext_urls_rate")
        vorbehalte.append({
            "titel": ("„zitiert“ ist die unzuverlaessigste Kennzahl"
                      + (f" ({round(rate * 100)} % in Arm B)" if rate else "")),
            "text": cc.get("arm_b_hinweis"),
            "quelle": quell_pfad,
        })
    if cc.get("arm_a_hinweis"):
        vorbehalte.append({
            "titel": "Die Arme trennen nicht perfekt",
            "text": cc.get("arm_a_hinweis"),
            "quelle": quell_pfad,
        })
    out["vorbehalte"] = vorbehalte
    return out


def _nicht_verfuegbar(grund: str) -> dict:
    return {
        "available": False,
        "grund": grund,
        "erzeugt_am": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "quelle": {"repo": GEO_REPO, "pfad": EXP_DIR + "/" + EXP_PREFIX + "*.json"},
    }


def main():
    print("=" * 60)
    print("[search_ab] Websuche-A/B aus dem GEO-Repo -> " + str(OUT_FILE))
    print("=" * 60)
    if not GITHUB_TOKEN and not GEO_LOCAL_DIR:
        print("[search_ab] WARNUNG: Kein GITHUB_TOKEN — nur public repos moeglich")

    try:
        data, md, path, bezug = _load_source()
        out = verdichte(data, md, path, bezug)
    except Exception as e:
        grund = f"{type(e).__name__}: {e}"
        print(f"[search_ab] FEHLER beim Laden: {grund}")
        if OUT_FILE.exists():
            try:
                alt = json.loads(OUT_FILE.read_text(encoding="utf-8"))
            except Exception:
                alt = None
            if isinstance(alt, dict) and alt.get("available"):
                print("[search_ab] vorhandene Datei bleibt stehen "
                      "(keine Daten ist kein Befund) — Stand: "
                      f"{alt.get('erzeugt_am')}")
                return 0
        OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUT_FILE.write_text(
            json.dumps(_nicht_verfuegbar(grund), ensure_ascii=False, indent=1),
            encoding="utf-8")
        print(f"[search_ab] {OUT_FILE} mit available:false und Grund geschrieben")
        return 1

    if not out.get("kennzahlen") or not out.get("je_produkt"):
        OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUT_FILE.write_text(
            json.dumps(_nicht_verfuegbar(
                "Quelldatei ohne bootstrap.metrics oder by_product — nichts "
                "zu zeigen"), ensure_ascii=False, indent=1), encoding="utf-8")
        print("[search_ab] Quelle unvollstaendig — available:false geschrieben")
        return 1

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    kb = OUT_FILE.stat().st_size / 1024
    lead = next((m for m in out["kennzahlen"] if m.get("leitkennzahl")), {})
    print(f"[search_ab] {OUT_FILE} geschrieben ({kb:.1f} KB)")
    print(f"[search_ab] Modell {out['modell']}, {out['umfang']['n_calls']} "
          f"Aufrufe, {out['umfang']['n_pairs']} Paare, "
          f"{out['fehler']['n_failed']} Fehler")
    print(f"[search_ab] SoV A {lead.get('arm_a')} vs B {lead.get('arm_b')}, "
          f"Diff {lead.get('diff')} [{lead.get('ci_low')}; "
          f"{lead.get('ci_high')}], p = {out['permutation_p']}")
    print(f"[search_ab] {len(out['je_produkt'])} Produktzeilen, "
          f"{len(out['vorbehalte'])} Vorbehalte")
    if kb > 100:
        print("[search_ab] WARNUNG: Datei ueber 100 KB — Verdichtung pruefen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
