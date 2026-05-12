"""
Holt das aktuellste latest.json aus dem GEO-Repo und bettet es ins Dashboard-Template ein.

Schritte:
1. GitHub-API: hole rohen Inhalt von <GEO_REPO>/data/runs/latest.json
2. Lese dashboard_template.html
3. Ersetze die Zeile "const GEO_SNAPSHOT = {...}" durch die neuen Daten
4. Speichere als dashboard_unencrypted.html (Input fuer StatiCrypt)
"""
import os
import json
import re
import sys
import urllib.request
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from shared.event_emitter import emit_event, load_previous_data, save_for_comparison
except ImportError:
    emit_event = None


def _build_headers(token: str = None) -> dict:
    """Baut GitHub-API-Headers, optional mit Auth-Token."""
    h = {
        "Accept": "application/vnd.github.v3.raw",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "LLM-Cockpit-Updater",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def fetch_latest_geo_snapshot(repo: str, token: str = None) -> dict:
    """Lade die aktuellste latest.json aus dem GEO-Repo via GitHub API.
    Token ist optional -- fuer oeffentliche Repos nicht noetig.
    Falls Token ungueltig (401/403), wird ohne Token nochmal versucht."""
    paths = [
        f"https://api.github.com/repos/{repo}/contents/data/runs/latest.json",
        f"https://api.github.com/repos/{repo}/contents/Geo/data/runs/latest.json",
    ]
    # Versuch 1: mit Token (falls gesetzt)
    for url in paths:
        try:
            req = urllib.request.Request(url, headers=_build_headers(token))
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as he:
            if he.code in (401, 403) and token:
                print(f"   Token-Fehler ({he.code}) -- versuche ohne Token...")
                break  # ohne Token nochmal
            continue  # naechster Pfad
        except Exception:
            continue

    # Versuch 2: ohne Token (public repo)
    for url in paths:
        try:
            req = urllib.request.Request(url, headers=_build_headers(None))
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as exc:
            print(f"   Fehler bei {url}: {exc}")
            continue

    sys.exit("FEHLER: latest.json konnte nicht geladen werden (alle Pfade/Token fehlgeschlagen).")


def transform_to_dashboard_format(geo: dict) -> dict:
    """Verkleinere geo-Snapshot zu der Form, die das Dashboard erwartet."""
    out = {
        "run_id": geo.get("run_id"),
        "started_at": geo.get("started_at"),
        "finished_at": geo.get("finished_at"),
        "dry_run": geo.get("dry_run", False),
        "brand": geo.get("brand"),
        "competitors": geo.get("competitors", []),
        "llms": geo.get("llms", []),
        "totals_ranking": geo.get("totals", {}).get("ranking", []),
        "products": {},
    }
    for pid, pdata in geo.get("products", {}).items():
        out["products"][pid] = {
            "name": pdata.get("name"),
            "url": pdata.get("url"),
            "summary_by_llm": {
                llm: {
                    "prompts_total": s.get("prompts_total", 0),
                    "brands": s.get("brands", []),
                }
                for llm, s in pdata.get("summary_by_llm", {}).items()
            },
        }
    es = geo.get("impact", {}).get("executive_summary", "")
    # Executive-Summary sanitizen: Newlines/Tabs durch Leerzeichen ersetzen,
    # damit der JSON-String in JS-Code eingebettet werden kann
    if isinstance(es, str):
        es = es.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").replace("\t", " ")
        es = re.sub(r"  +", " ", es).strip()[:2000]
    else:
        es = str(es)[:2000]
    out["executive_summary"] = es
    return out


def inject_into_template(template_path: Path, snapshot: dict, out_path: Path) -> None:
    """Patcht GEO_SNAPSHOT IN-PLACE in dashboard_template.html.
    Nutzt out_path NUR fuer Backwards-Compat (falls Workflow sie erwartet)."""
    html = template_path.read_text(encoding="utf-8")
    new_line = "const GEO_SNAPSHOT = " + json.dumps(snapshot, ensure_ascii=True) + ";"
    pattern = re.compile(r"const GEO_SNAPSHOT\s*=\s*\{.*?\};", re.DOTALL)
    new_html, n = pattern.subn(lambda m: new_line, html, count=1)
    if n != 1:
        sys.exit("FEHLER: GEO_SNAPSHOT-Zeile im Template nicht gefunden.")
    # Patch IN-PLACE (NULL-byte safe)
    template_path.write_bytes(new_html.encode("utf-8").replace(b"\x00", b"").rstrip() + b"\n")
    print(f"OK - Snapshot eingebettet IN dashboard_template.html ({len(json.dumps(snapshot)):,} Zeichen JSON)")


def main():
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GEO_REPO", "phoeser/geo-visibility-tool")
    if not token:
        print("WARN: GITHUB_TOKEN nicht gesetzt -- versuche ohne Token (ok fuer public Repos)")

    print(f"-> Hole latest.json aus {repo} ...")
    geo = fetch_latest_geo_snapshot(repo, token)
    print(f"   Run-ID: {geo.get('run_id')}, dry_run={geo.get('dry_run')}")

    snapshot = transform_to_dashboard_format(geo)

    template = Path("dashboard_template.html")
    if not template.exists():
        sys.exit("FEHLER: dashboard_template.html fehlt im Repo-Root.")

    # Patch in-place (template = dashboard_template.html)
    inject_into_template(template, snapshot, template)
    print(f"   Patched: {template} ({template.stat().st_size:,} Bytes)")

    # --- Event-Emitter: sov_change Events ---
    if emit_event:
        _emit_sov_events(snapshot)


def _emit_sov_events(snapshot: dict) -> None:
    """Vergleicht GEO-Snapshot mit vorherigem und emittiert sov_change Events."""
    prev_path = Path("data/geo_snapshot.previous.json")
    curr_path = Path("data/geo_snapshot.json")

    # Aktuellen Snapshot speichern fuer naechsten Vergleich
    curr_path.parent.mkdir(parents=True, exist_ok=True)
    if curr_path.exists():
        save_for_comparison(curr_path)
    curr_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")

    prev = load_previous_data(curr_path)
    if not prev:
        print("   Kein vorheriger GEO-Snapshot -- ueberspringe Event-Emission")
        return

    event_count = 0

    # 1. Gesamt-Ranking Veraenderungen
    # GEO-Daten nutzen "name" statt "brand" als Key
    curr_ranking_list = snapshot.get("totals_ranking", [])
    prev_ranking_list = prev.get("totals_ranking", [])
    curr_ranking = {r.get("name", r.get("brand", "")): r for r in curr_ranking_list}
    prev_ranking = {r.get("name", r.get("brand", "")): r for r in prev_ranking_list}
    # Rank aus Position im Array ableiten (1-basiert)
    curr_rank_pos = {r.get("name", r.get("brand", "")): i + 1 for i, r in enumerate(curr_ranking_list)}
    prev_rank_pos = {r.get("name", r.get("brand", "")): i + 1 for i, r in enumerate(prev_ranking_list)}

    for brand, curr_r in curr_ranking.items():
        if not brand:
            continue
        prev_r = prev_ranking.get(brand)
        if not prev_r:
            continue

        curr_rank = curr_rank_pos.get(brand, 0)
        prev_rank = prev_rank_pos.get(brand, 0)
        if curr_rank and prev_rank and curr_rank != prev_rank:
            delta = prev_rank - curr_rank  # positiv = Verbesserung
            emit_event(
                event_type="sov_change",
                brand=brand,
                source="geo_snapshot",
                crawler="update_snapshot",
                magnitude=min(abs(delta) * 0.5, 2.0),
                detail={
                    "metric": "overall_rank",
                    "old_rank": prev_rank,
                    "new_rank": curr_rank,
                    "direction": "up" if delta > 0 else "down",
                },
            )
            event_count += 1

        # Share-of-Voice Prozent (Feld heisst "share_of_voice" in GEO-Daten)
        curr_pct = curr_r.get("share_of_voice", curr_r.get("mention_pct", curr_r.get("pct", 0)))
        prev_pct = prev_r.get("share_of_voice", prev_r.get("mention_pct", prev_r.get("pct", 0)))
        # share_of_voice ist 0-1 Ratio, umrechnen in Prozent fuer Vergleich
        if curr_pct and curr_pct <= 1:
            curr_pct = curr_pct * 100
        if prev_pct and prev_pct <= 1:
            prev_pct = prev_pct * 100
        if curr_pct and prev_pct and abs(curr_pct - prev_pct) >= 1.0:
            emit_event(
                event_type="sov_change",
                brand=brand,
                source="geo_snapshot",
                crawler="update_snapshot",
                magnitude=min(abs(curr_pct - prev_pct) / 5, 2.0),
                detail={
                    "metric": "share_of_voice_pct",
                    "old_pct": round(prev_pct, 1),
                    "new_pct": round(curr_pct, 1),
                },
            )
            event_count += 1

    # 2. Produkt-spezifische Veraenderungen
    for pid, pdata in snapshot.get("products", {}).items():
        prev_pdata = prev.get("products", {}).get(pid, {})
        if not prev_pdata:
            continue

        for llm, curr_s in pdata.get("summary_by_llm", {}).items():
            prev_s = prev_pdata.get("summary_by_llm", {}).get(llm, {})
            if not prev_s:
                continue

            # Ranking-Veraenderungen pro LLM+Produkt
            curr_brands = {b.get("name", b.get("brand", "")): b for b in curr_s.get("brands", [])}
            prev_brands = {b.get("name", b.get("brand", "")): b for b in prev_s.get("brands", [])}

            for brand, cb in curr_brands.items():
                pb = prev_brands.get(brand)
                if not pb:
                    continue
                curr_mentions = cb.get("mentions", 0)
                prev_mentions = pb.get("mentions", 0)
                if curr_mentions != prev_mentions and abs(curr_mentions - prev_mentions) >= 2:
                    emit_event(
                        event_type="sov_change",
                        brand=brand,
                        source="geo_snapshot",
                        crawler="update_snapshot",
                        product=pid,
                        magnitude=min(abs(curr_mentions - prev_mentions) / 5, 2.0),
                        detail={
                            "metric": "mentions",
                            "llm": llm,
                            "product": pid,
                            "old_mentions": prev_mentions,
                            "new_mentions": curr_mentions,
                        },
                    )
                    event_count += 1

    print(f"   {event_count} sov_change Events emittiert")


if __name__ == "__main__":
    main()
