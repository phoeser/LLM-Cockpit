"""
Holt GEO Page-Tracker Events aus dem GEO-Repo via GitHub API
und fuegt sie als page_change / page_new Events in shared/events.jsonl ein.

Zusaetzlich wird data/geo_page_changes.json mit vollen Diff-Details erzeugt
und als GEO_PAGE_CHANGES in dashboard_template.html injiziert (fuer den
Content-GEO Tab).

Ablauf:
1. GitHub Trees API: hole rekursiven Dateibaum des GEO-Repos
2. Filtere auf data/pages/*/events.jsonl Dateien
3. Lade jede events.jsonl via Blobs API (base64)
4. Parse Events, mappe Typen (change -> page_change, first_seen -> page_new)
5. Dedupliziere gegen bestehende shared/events.jsonl
6. Haenge neue Events an
7. Schreibe data/geo_page_changes.json mit vollen Diff-Details
8. Injiziere GEO_PAGE_CHANGES in dashboard_template.html
"""
import base64
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GEO_REPO = os.environ.get("GEO_REPO", "phoeser/geo-visibility-tool")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
EVENTS_FILE = Path(os.environ.get("EVENTS_FILE", "shared/events.jsonl"))
PAGE_CHANGES_FILE = Path("data/geo_page_changes.json")
TEMPLATE_FILE = Path("dashboard_template.html")

# Nur Events der letzten N Tage importieren
MAX_AGE_DAYS = 180
# Fuer den Dashboard-Tab: nur letzte 90 Tage mit vollen Details
DETAIL_AGE_DAYS = 45  # 2026-06-04: von 14 auf 45 erhoeht, damit auch selten geaenderte Marken (Generali, HUK) mit ihren page_new-Events sichtbar sind
# Max Diff-Zeilen pro Event (verhindert Datei-Explosion)
MAX_DIFF_LINES = 20

# Rauschfilter: identisch zum GEO page_tracker
NOISE_SIMILARITY = 0.97
NOISE_MAX_LINES = 10

# Brand-Slug -> kanonischer Name (wie im Cockpit verwendet)
BRAND_CANONICALIZE = {
    "ergo": "ERGO",
    "allianz": "Allianz",
    "axa": "AXA",
    "generali": "Generali",
    "huk_coburg": "HUK-Coburg",
    "huk": "HUK-Coburg",
    "cosmos_direkt": "Cosmos Direkt",
    "devk": "DEVK",
    "hannoversche": "Hannoversche",
    "r_v": "R+V",
    "signal_iduna": "Signal Iduna",
}

# Event-ID Zaehler
_seq = 0


def _next_id(brand: str, event_type: str) -> str:
    global _seq
    _seq += 1
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    slug = re.sub(r"[^a-z0-9]+", "_", (brand or "").lower()).strip("_")
    return f"evt_{today}_{slug}_{event_type}_{_seq:03d}"


def _api(url: str, accept: str = "application/vnd.github.v3+json") -> dict:
    """GitHub API GET mit optionalem Token."""
    headers = {
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "LLM-Cockpit-GEO-Merge",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _api_raw(url: str) -> bytes:
    """GitHub API GET fuer Blob-Inhalt (base64)."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "LLM-Cockpit-GEO-Merge",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        blob = json.loads(r.read().decode("utf-8"))
        return base64.b64decode(blob.get("content", ""))


def _canonicalize_brand(raw: str) -> str:
    """Wandelt Brand-String in kanonischen Cockpit-Namen um."""
    if not raw:
        return "Unknown"
    if raw in BRAND_CANONICALIZE.values():
        return raw
    slug = re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")
    return BRAND_CANONICALIZE.get(slug, raw)


def _is_noise(ev: dict) -> bool:
    """Rauschfilter: identisch zum GEO page_tracker."""
    if ev.get("event_type") != "change":
        return False
    sim = ev.get("similarity")
    added = ev.get("added_lines_count") or len(ev.get("added_lines") or [])
    removed = ev.get("removed_lines_count") or len(ev.get("removed_lines") or [])
    return (
        isinstance(sim, (int, float))
        and sim >= NOISE_SIMILARITY
        and (added + removed) <= NOISE_MAX_LINES
    )


def load_existing_keys(events_file: Path) -> set:
    """Laedt existierende Event-Keys fuer Deduplizierung."""
    keys = set()
    if not events_file.exists():
        return keys
    for line in events_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
            url = ev.get("url") or (ev.get("detail") or {}).get("url") or ""
            key = f"{ev.get('timestamp', '')}|{url}|{ev.get('event_type', '')}"
            keys.add(key)
        except json.JSONDecodeError:
            continue
    return keys


def fetch_geo_page_events() -> list:
    """Holt alle Page-Events aus dem GEO-Repo via GitHub API."""
    print(f"[merge_geo] Hole Dateibaum von {GEO_REPO} ...")

    tree_url = f"https://api.github.com/repos/{GEO_REPO}/git/trees/main?recursive=1"
    try:
        tree = _api(tree_url)
    except Exception as e:
        print(f"[merge_geo] FEHLER beim Laden des Trees: {e}")
        return []

    event_files = []
    for item in tree.get("tree", []):
        path = item.get("path", "")
        if (
            item.get("type") == "blob"
            and path.startswith("data/pages/")
            and path.endswith("/events.jsonl")
        ):
            event_files.append(item)

    print(f"[merge_geo] {len(event_files)} events.jsonl Dateien gefunden")
    if not event_files:
        return []

    cutoff = (datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)).strftime(
        "%Y-%m-%dT"
    )

    all_events = []
    errors = 0
    for item in event_files:
        blob_url = item.get("url")
        if not blob_url:
            continue
        try:
            raw = _api_raw(blob_url)
            text = raw.decode("utf-8", errors="replace")
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                    ts = ev.get("timestamp", "")
                    if ts < cutoff:
                        continue
                    all_events.append(ev)
                except json.JSONDecodeError:
                    continue
        except Exception:
            errors += 1
            continue

    if errors:
        print(f"[merge_geo] {errors} Dateien konnten nicht geladen werden")
    print(f"[merge_geo] {len(all_events)} Events (< {MAX_AGE_DAYS} Tage) geladen")
    return all_events


def convert_to_cockpit_format(geo_events: list) -> list:
    """Konvertiert GEO Page-Events ins Cockpit event_emitter Format (fuer events.jsonl)."""
    converted = []
    for ev in geo_events:
        etype = ev.get("event_type")
        if etype not in ("change", "first_seen", "removed"):
            continue
        if _is_noise(ev):
            continue

        brand = _canonicalize_brand(ev.get("brand", ""))
        cockpit_type = ("page_change" if etype == "change" else ("page_removed" if etype == "removed" else "page_new"))
        url = ev.get("url", "")

        if etype == "change":
            sim = ev.get("similarity") or 0.0
            magnitude = round(min(max(1.0 - sim, 0.1), 2.0), 3)
        else:
            magnitude = 1.0

        cockpit_event = {
            "id": _next_id(brand, cockpit_type),
            "timestamp": ev.get("timestamp", ""),
            "event_type": cockpit_type,
            "brand": brand,
            "product": None,
            "source": "geo_page_tracker",
            "crawler": "merge_geo_page_events",
            "magnitude": magnitude,
            "detail": {
                "url": url,
                "similarity": ev.get("similarity"),
                "added_lines": ev.get("added_lines_count") or len(ev.get("added_lines") or []),
                "removed_lines": ev.get("removed_lines_count") or len(ev.get("removed_lines") or []),
                "classification": ev.get("classification"),
                "summary": ev.get("summary"),
            },
        }
        if url:
            cockpit_event["url"] = url
        converted.append(cockpit_event)
    return converted


def build_detailed_changes(geo_events: list) -> list:
    """Baut detaillierte Aenderungsliste MIT vollen Diff-Zeilen fuer den Dashboard-Tab."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=DETAIL_AGE_DAYS)).strftime(
        "%Y-%m-%dT"
    )
    changes = []
    for ev in geo_events:
        etype = ev.get("event_type")
        if etype not in ("change", "first_seen", "removed"):
            continue
        ts = ev.get("timestamp", "")
        if ts < cutoff:
            continue
        if _is_noise(ev):
            continue

        brand = _canonicalize_brand(ev.get("brand", ""))

        # Diff-Zeilen mit Limit
        added = (ev.get("added_lines") or [])[:MAX_DIFF_LINES]
        removed = (ev.get("removed_lines") or [])[:MAX_DIFF_LINES]
        total_added = ev.get("added_lines_count") or len(ev.get("added_lines") or [])
        total_removed = ev.get("removed_lines_count") or len(ev.get("removed_lines") or [])

        changes.append({
            "ts": ts,
            "t": ("page_change" if etype == "change" else ("page_removed" if etype == "removed" else "page_new")),
            "b": brand,
            "u": ev.get("url", ""),
            "sim": ev.get("similarity"),
            "al": added,
            "rl": removed,
            "ac": total_added,
            "rc": total_removed,
            "s": ev.get("summary"),
            "cl": ev.get("classification"),
            "p": ev.get("product_ids"),
        })

    changes.sort(key=lambda e: e.get("ts", ""), reverse=True)
    return changes


def inject_into_dashboard(changes: list):
    """Injiziert GEO_PAGE_CHANGES in dashboard_template.html."""
    if not TEMPLATE_FILE.exists():
        print("[merge_geo] dashboard_template.html nicht gefunden — ueberspringe Injection")
        return False

    content = TEMPLATE_FILE.read_text(encoding="utf-8")
    marker = "const GEO_PAGE_CHANGES = window.GEO_PAGE_CHANGES || [];"
    if marker not in content:
        print("[merge_geo] GEO_PAGE_CHANGES Marker nicht gefunden — ueberspringe Injection")
        return False

    # Alte Injection entfernen
    cleaned = []
    for line in content.split("\n"):
        if "window.GEO_PAGE_CHANGES = [" in line:
            continue
        cleaned.append(line)
    content = "\n".join(cleaned)

    # Neue Daten injizieren
    changes_json = json.dumps(changes, ensure_ascii=False, separators=(",", ":"))
    inject = "  window.GEO_PAGE_CHANGES = %s;" % changes_json
    content = content.replace(marker, inject + "\n  " + marker)

    TEMPLATE_FILE.write_text(content, encoding="utf-8")
    print(f"[merge_geo] {len(changes)} Detail-Events in dashboard_template.html injiziert")
    return True


def main():
    print("=" * 60)
    print("[merge_geo] GEO Page-Events -> Cockpit events.jsonl + Dashboard")
    print("=" * 60)

    if not GITHUB_TOKEN:
        print("[merge_geo] WARNUNG: Kein GITHUB_TOKEN — nur public repos moeglich")

    # 1. GEO Events holen
    geo_events = fetch_geo_page_events()
    if not geo_events:
        print("[merge_geo] Keine Events gefunden — fertig.")
        return

    # 2. Ins Cockpit-Format konvertieren (Kurzform fuer events.jsonl)
    cockpit_events = convert_to_cockpit_format(geo_events)
    print(f"[merge_geo] {len(cockpit_events)} Events nach Rauschfilter")

    # 3. Deduplizieren und an events.jsonl anhaengen
    existing_keys = load_existing_keys(EVENTS_FILE)
    new_events = []
    for ev in cockpit_events:
        url = ev.get("url") or (ev.get("detail") or {}).get("url") or ""
        key = f"{ev['timestamp']}|{url}|{ev['event_type']}"
        if key not in existing_keys:
            new_events.append(ev)
            existing_keys.add(key)

    print(f"[merge_geo] {len(new_events)} neue Events (nach Deduplizierung)")

    if new_events:
        EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(EVENTS_FILE, "a", encoding="utf-8") as f:
            for ev in sorted(new_events, key=lambda e: e.get("timestamp", "")):
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        print(f"[merge_geo] {len(new_events)} Events angehaengt an {EVENTS_FILE}")

    # 4. Detaillierte Changes fuer Dashboard-Tab (mit vollen Diff-Zeilen)
    detailed = build_detailed_changes(geo_events)
    print(f"[merge_geo] {len(detailed)} Detail-Events fuer Dashboard")

    # 5. JSON-Datei schreiben
    PAGE_CHANGES_FILE.parent.mkdir(parents=True, exist_ok=True)
    PAGE_CHANGES_FILE.write_text(
        json.dumps(detailed, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"[merge_geo] {PAGE_CHANGES_FILE} geschrieben ({PAGE_CHANGES_FILE.stat().st_size // 1024} KB)")

    # 6. In Dashboard injizieren
    inject_into_dashboard(detailed)

    # Stats
    brands = {}
    for ev in cockpit_events:
        b = ev.get("brand", "?")
        brands[b] = brands.get(b, 0) + 1
    for b, c in sorted(brands.items(), key=lambda x: -x[1]):
        print(f"  {b}: {c} Events")


if __name__ == "__main__":
    main()
