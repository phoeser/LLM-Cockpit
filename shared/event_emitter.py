"""Shared Event-Emitter für alle Cockpit-Crawler.

Jeder Crawler importiert dieses Modul und ruft emit_event() auf,
um standardisierte Events in shared/events.jsonl zu schreiben.

Events werden chronologisch angehängt (append). Beim Start des
Nightly-Workflows wird die Datei NICHT gelöscht — so entsteht
eine wachsende Timeline.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

# Event-Datei: relativ zum github-deployment/ Verzeichnis
EVENTS_FILE = Path(os.environ.get("EVENTS_FILE", "shared/events.jsonl"))

# Zähler für Event-IDs innerhalb eines Laufs
_seq = 0


def _next_id(brand: str, event_type: str) -> str:
    """Generiert eine eindeutige Event-ID."""
    global _seq
    _seq += 1
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"evt_{today}_{brand.lower().replace(' ', '_').replace('-', '_')}_{event_type}_{_seq:03d}"


def emit_event(
    event_type: str,
    brand: str,
    source: str,
    crawler: str,
    magnitude: float = 1.0,
    product: str = None,
    detail: dict = None,
    url: str = None,
    sentiment: str = None,
):
    """Schreibt ein standardisiertes Event in die events.jsonl.

    Args:
        event_type: review_change | review_volume | press_mention | 
                    rating_update | page_change | page_new | berater_shift |
                    domain_change | sov_change | news_mention
        brand: ERGO | Allianz | AXA | Generali | HUK-Coburg | ...
        source: Name der Datenquelle (z.B. google_places, trustpilot, google_news)
        crawler: Name des aufrufenden Scripts (z.B. update_sentiment)
        magnitude: Normalisierte Stärke 0.0-2.0 (höher = wichtiger)
        product: zahnzusatz | sterbegeld | risikoleben | None
        detail: Dict mit typ-spezifischen Detaildaten
        url: Relevante URL (bei press_mention, page_change)
        sentiment: positive | negative | neutral (bei press/review)
    """
    event = {
        "id": _next_id(brand, event_type),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event_type": event_type,
        "brand": brand,
        "product": product,
        "source": source,
        "crawler": crawler,
        "magnitude": round(min(max(magnitude, 0.0), 2.0), 3),
        "detail": detail or {},
    }
    if url:
        event["url"] = url
    if sentiment:
        event["sentiment"] = sentiment

    # Append to JSONL
    events_path = EVENTS_FILE
    # Falls über Env-Variable ein absoluter Pfad gesetzt ist, nutze diesen
    if not events_path.is_absolute():
        # Relativ zu CWD (github-deployment/)
        pass
    events_path.parent.mkdir(parents=True, exist_ok=True)

    with open(events_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    return event


def load_events(events_file: Path = None, max_age_days: int = None) -> list:
    """Lädt alle Events aus der JSONL-Datei.
    
    Args:
        events_file: Pfad zur Events-Datei (default: EVENTS_FILE)
        max_age_days: Nur Events der letzten N Tage laden
    """
    fp = events_file or EVENTS_FILE
    if not fp.exists():
        return []
    
    events = []
    cutoff = None
    if max_age_days:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).strftime("%Y-%m-%dT")
    
    for line in fp.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
            if cutoff and ev.get("timestamp", "") < cutoff:
                continue
            events.append(ev)
        except json.JSONDecodeError:
            continue
    
    return events


def load_previous_data(json_path: Path) -> dict:
    """Lädt die vorherige Version einer Datendatei zum Vergleich.
    
    Sucht nach <filename>.previous.json neben der aktuellen Datei.
    Wird vom Workflow angelegt, bevor der neue Crawl startet.
    """
    prev_path = json_path.with_suffix(".previous.json")
    if prev_path.exists():
        try:
            return json.loads(prev_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_for_comparison(json_path: Path):
    """Sichert die aktuelle Datei als .previous.json für den nächsten Vergleich."""
    if json_path.exists():
        import shutil
        prev_path = json_path.with_suffix(".previous.json")
        shutil.copy2(json_path, prev_path)
