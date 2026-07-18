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
    # 17.07.2026: Legacy-Pfad "Geo/data/runs/latest.json" ENTFERNT. Dieser tote Baum
    # existiert im GEO-Repo noch und steht seit dem 22.04.2026 still. Bei einem 404 im
    # Primaerpfad zog das Cockpit klaglos drei Monate alte Daten und wies sie als
    # aktuellen Stand aus - ohne Warnung, ohne dass jemand es haette merken koennen.
    # Ein fehlender Snapshot muss als Luecke sichtbar werden, nicht als alter Befund.
    paths = [
        f"https://api.github.com/repos/{repo}/contents/data/runs/latest.json",
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

    print("WARN: latest.json nicht ladbar (alle Pfade/Token) -- behalte letzten Stand, kein Abbruch.")
    return None


# Maximales Alter eines GEO-Snapshots. Der Crawl laeuft naechtlich; alles jenseits
# weniger Tage bedeutet, dass die Kette stillsteht. Grosszuegig gewaehlt, damit ein
# einzelner Ausfall (oder die eingestandene Free-Tier-Verzoegerung von 4-8 h) nicht
# gleich blockiert.
MAX_SNAPSHOT_AGE_DAYS = 7


def _snapshot_age_days(geo: dict):
    """Alter des Snapshots in Tagen, oder None wenn kein Zeitstempel lesbar ist."""
    import datetime as _dt
    raw = (geo or {}).get("started_at") or (geo or {}).get("finished_at")
    if not raw:
        rid = (geo or {}).get("run_id") or ""
        try:
            raw = _dt.datetime.strptime(rid[:20], "%Y-%m-%dT%H-%M-%SZ").replace(
                tzinfo=_dt.timezone.utc).isoformat()
        except Exception:
            return None
    try:
        ts = _dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=_dt.timezone.utc)
        return (_dt.datetime.now(_dt.timezone.utc) - ts).total_seconds() / 86400.0
    except Exception:
        return None


# ── Zitierte-Quellen-Auswertung (Roadmap Punkt 2) ───────────────────────────
# latest.json enthaelt je Antwort 'sources'; wir aggregieren, WELCHE Quellen die
# LLMs ziehen (Treiber der Sichtbarkeit). Grounding-Redirects sind Rauschen.
from urllib.parse import urlparse as _urlparse

_SOURCE_NOISE = ("vertexaisearch.cloud.google.com", "grounding-api-redirect",
                 "googleapis.com", "google.com/search", "bing.com/search")

# Unsere 10 Haupt-Marken: Domain -> Anzeigename
_BRAND_DOMAINS = {
    "ergo.de": "ERGO", "ergo.com": "ERGO",
    "allianz.de": "Allianz", "allianz.com": "Allianz", "allianzdirect.de": "Allianz",
    "huk.de": "HUK-Coburg", "huk24.de": "HUK-Coburg", "huk-coburg.de": "HUK-Coburg",
    "axa.de": "AXA", "axa.com": "AXA",
    "generali.de": "Generali", "generali.com": "Generali",
    "signal-iduna.de": "Signal Iduna",
    "ruv.de": "R+V", "devk.de": "DEVK", "hannoversche.de": "Hannoversche",
    "cosmosdirekt.de": "Cosmos Direkt",
    # 18.07.2026: additive Markenerweiterung (Crawl 7->25). Anzeigenamen = Crawl-Namen.
    "adac.de": "ADAC", "arag.de": "ARAG", "alte-leipziger.de": "Alte Leipziger",
    "barmenia.de": "Barmenia", "da-direkt.de": "DA Direkt", "debeka.de": "Debeka",
    "diebayerische.de": "Die Bayerische", "die-bayerische.de": "Die Bayerische",
    "gothaer.de": "Gothaer", "hdi.de": "HDI", "hansemerkur.de": "HanseMerkur",
    "lv1871.de": "LV 1871", "vhv.de": "VHV", "wgv.de": "WGV",
    "wuerttembergische.de": "Württembergische", "zurich.de": "Zurich",
}
# Bekannte Portale / Vergleichs- / Verbraucher- / Test-Quellen
_PORTAL_DOMAINS = {
    "check24.de", "verivox.de", "finanztip.de", "verbraucherzentrale.de",
    "test.de", "stiftung-warentest.de", "focus.de", "focus-money.de",
    "handelsblatt.com", "wikipedia.org", "de.wikipedia.org", "transparent-beraten.de",
    "versicherungsbote.de", "morgenundmorgen.com", "franke-bornberg.de", "dfsi-institut.de",
    " assekurata.de".strip(), "biallo.de", "finanztest.de", "ariva.de", "wiwo.de",
}
_PORTAL_HINTS = ("vergleich", "test-", "-test", "-experten", "ratgeber", "tarif",
                 "finanz", "versicherung-", "-versicherung", "bestattung")


def _src_domain(url):
    try:
        n = _urlparse(url if str(url).startswith("http") else "http://" + str(url)).netloc.lower()
        return n[4:] if n.startswith("www.") else n
    except Exception:
        return ""


def _classify_source(domain):
    """-> (kategorie, label). Kategorien: eigen | wettbewerber | portal | sonstige."""
    if domain in _BRAND_DOMAINS:
        b = _BRAND_DOMAINS[domain]
        return ("eigen" if b == "ERGO" else "wettbewerber", b)
    if domain in _PORTAL_DOMAINS or any(h in domain for h in _PORTAL_HINTS):
        return ("portal", domain)
    # generische .de mit insurer-typischem Namen? -> sonstige (kein Rateschluss)
    return ("sonstige", domain)


def _aggregate_cited_sources(per_llm_list, top_n=15):
    """Aggregiert zitierte Domains ueber alle Antworten eines Produkts.
    Liefert overall + je LLM + Kategorie-Summe (Anteile in %)."""
    from collections import Counter
    overall = Counter()
    by_llm = {}
    cat = Counter()
    total = 0
    for pl in (per_llm_list or []):
        llm = pl.get("llm")
        cc = Counter()
        for r in (pl.get("results") or []):
            for srow in (r.get("sources") or []):
                u = srow.get("url") if isinstance(srow, dict) else srow
                dom = _src_domain(u)
                if not dom or any(nz in dom for nz in _SOURCE_NOISE):
                    continue
                overall[dom] += 1
                cc[dom] += 1
                cat[_classify_source(dom)[0]] += 1
                total += 1
        if cc:
            by_llm[llm] = [{"domain": d, "count": n, "category": _classify_source(d)[0]}
                           for d, n in cc.most_common(top_n)]
    if not total:
        return None
    def _fmt(counter, n):
        return [{"domain": d, "count": c, "share": round(c / total * 100, 1),
                 "category": _classify_source(d)[0]} for d, c in counter.most_common(n)]
    return {
        "total": total,
        "overall": _fmt(overall, top_n),
        "by_llm": by_llm,
        "by_category": {k: {"count": v, "share": round(v / total * 100, 1)}
                        for k, v in cat.most_common()},
    }


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
        cs = _aggregate_cited_sources(pdata.get("per_llm"))
        out["products"][pid] = {
            "name": pdata.get("name"),
            "url": pdata.get("url"),
            "cited_sources": cs,
            "summary_by_llm": {
                llm: {
                    "prompts_total": s.get("prompts_total", 0),
                    "brands": s.get("brands", []),
                }
                for llm, s in pdata.get("summary_by_llm", {}).items()
            },
        }
    # Gesamt-Quellen ueber alle Produkte
    try:
        from collections import Counter as _C
        _ov = _C(); _cat = _C(); _tot = 0
        for _p in out["products"].values():
            _cs = _p.get("cited_sources")
            if not _cs:
                continue
            for _row in _cs.get("overall", []):
                _ov[_row["domain"]] += _row["count"]; _tot += _row["count"]
            for _k, _v in _cs.get("by_category", {}).items():
                _cat[_k] += _v.get("count", 0)
        if _tot:
            out["cited_sources_overall"] = {
                "total": _tot,
                "overall": [{"domain": d, "count": c, "share": round(c / _tot * 100, 1),
                             "category": _classify_source(d)[0]} for d, c in _ov.most_common(20)],
                "by_category": {k: {"count": v, "share": round(v / _tot * 100, 1)}
                                for k, v in _cat.most_common()},
            }
    except Exception as _e:
        print("WARN cited_sources_overall:", str(_e)[:80])
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
    # ensure_ascii=True + separators entfernt Whitespace; .replace() entfernt echte
    # Newlines aus LLM-Antwort-Strings, die JS-SyntaxErrors verursachen wuerden
    snapshot_json = json.dumps(snapshot, ensure_ascii=True, separators=(",", ":"))
    # Sicherheit: Restliche echte Newlines/Tabs in Strings escapen
    snapshot_json = snapshot_json.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    new_line = "const GEO_SNAPSHOT = " + snapshot_json + ";"
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
    if geo is None:
        print("WARN: Kein neuer GEO-Snapshot -- Nightly laeuft mit letztem Stand weiter (kein Abbruch).")
        return
    print(f"   Run-ID: {geo.get('run_id')}, dry_run={geo.get('dry_run')}")

    # 17.07.2026: Alter pruefen, egal aus welchem Pfad der Snapshot kam. Ein veralteter
    # Stand darf nicht als aktueller Befund durchgehen - das war der Weg, auf dem die
    # April-Daten ins Dashboard kamen.
    _age = _snapshot_age_days(geo)
    if _age is None:
        print("WARN: Snapshot ohne lesbaren Zeitstempel -- Alter nicht pruefbar, fahre fort.")
    elif _age > MAX_SNAPSHOT_AGE_DAYS:
        print(f"FEHLER: GEO-Snapshot ist {_age:.1f} Tage alt (Grenze {MAX_SNAPSHOT_AGE_DAYS}). "
              f"Run-ID {geo.get('run_id')}. Das Cockpit wuerde veraltete Zahlen als aktuellen "
              f"Stand ausweisen -- Abbruch, letzter Stand bleibt stehen.")
        return
    else:
        print(f"   Snapshot-Alter: {_age:.2f} Tage (ok)")

    # 17.07.2026 (Review #8): dry_run-Daten duerfen das Dashboard nicht anfassen. Bisher
    # wurde dry_run nur GEDRUCKT (Zeile darueber) und die Dummy-Daten dann ganz normal
    # verarbeitet und committet.
    if geo.get("dry_run"):
        print(f"ABBRUCH: Snapshot stammt aus einem dry_run (Run-ID {geo.get('run_id')}) und "
              f"enthaelt Dummy-Daten. Er wird nicht ins Dashboard uebernommen.")
        return

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
        # Immer ein Event schreiben wenn beide Werte vorhanden sind (auch bei Delta 0)
        # damit das SoV-Chart im Dashboard fuer jeden Run vollstaendig ist
        if curr_pct is not None and prev_pct is not None:
            emit_event(
                event_type="sov_change",
                brand=brand,
                source="geo_snapshot",
                crawler="update_snapshot",
                magnitude=min(abs(curr_pct - prev_pct) / 5, 2.0) if abs(curr_pct - prev_pct) > 0 else 0,
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
                    print(f"  EVENT: sov_change {brand} {llm}/{pid} mentions {prev_mentions}->{curr_mentions}")

    print(f"  Events emittiert fuer {len(curr_ranking)} Brands")


if __name__ == "__main__":
    main()
