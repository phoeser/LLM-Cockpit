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


def fetch_latest_geo_snapshot(repo: str, token: str) -> dict:
    """Lade die aktuellste latest.json aus dem GEO-Repo via GitHub API."""
    url = f"https://api.github.com/repos/{repo}/contents/Geo/data/runs/latest.json"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github.v3.raw",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "LLM-Cockpit-Updater",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as exc:
        # Fallback: vielleicht liegt latest.json direkt in /data/runs/
        url2 = f"https://api.github.com/repos/{repo}/contents/data/runs/latest.json"
        req2 = urllib.request.Request(
            url2,
            headers={
                "Accept": "application/vnd.github.v3.raw",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "LLM-Cockpit-Updater",
            },
        )
        with urllib.request.urlopen(req2, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))


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
    out["executive_summary"] = es if isinstance(es, str) else str(es)[:2000]
    return out


def inject_into_template(template_path: Path, snapshot: dict, out_path: Path) -> None:
    """Patcht GEO_SNAPSHOT IN-PLACE in dashboard_template.html.
    Nutzt out_path NUR fuer Backwards-Compat (falls Workflow sie erwartet)."""
    html = template_path.read_text(encoding="utf-8")
    new_line = "const GEO_SNAPSHOT = " + json.dumps(snapshot, ensure_ascii=False) + ";"
    pattern = re.compile(r"const GEO_SNAPSHOT\s*=\s*\{.*?\};", re.DOTALL)
    new_html, n = pattern.subn(lambda m: new_line, html, count=1)
    if n != 1:
        sys.exit("FEHLER: GEO_SNAPSHOT-Zeile im Template nicht gefunden.")
    # Patch IN-PLACE (NULL-byte safe)
    template_path.write_bytes(new_html.encode("utf-8").replace(b"\x00", b"").rstrip() + b"\n")
    print(f"OK - Snapshot eingebettet IN dashboard_template.html ({len(json.dumps(snapshot)):,} Zeichen JSON)")


def main():
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GEO_REPO", "phoeser/Geo")
    if not token:
        sys.exit("FEHLER: GITHUB_TOKEN fehlt (Repo-Secret GEO_REPO_TOKEN).")

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


if __name__ == "__main__":
    main()
