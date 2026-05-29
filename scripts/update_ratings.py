"""
Aktualisiert die externen Produktratings (Finanztip, Warentest, M&M, Verivox, DFSI).

- Finanztip: automatischer Scrape (empfohlene Versicherer parsen)
- Warentest, M&M, Verivox, DFSI: aus data/ratings_external.json (manuell pflegbar)

Ergebnis:
- data/ratings_external.json wird aktualisiert (Finanztip-Spalte)
- RATINGS_EXTERNAL wird in dashboard_template.html injiziert
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RATINGS_FILE = Path("data/ratings_external.json")
TEMPLATE_FILE = Path("dashboard_template.html")

# Finanztip-Seiten pro Produkt
FINANZTIP_URLS = {
    "zahnzusatz": "https://www.finanztip.de/zahnzusatzversicherung/",
    "risikoleben": "https://www.finanztip.de/risikolebensversicherung/",
    # Sterbegeld wird von Finanztip nicht getestet
}

# Bekannte Versicherer-Namen und Aliase fuer Finanztip-Parsing
BRAND_ALIASES = {
    "ergo": "ERGO",
    "ergo direkt": "ERGO",
    "allianz": "Allianz",
    "axa": "AXA",
    "huk-coburg": "HUK-Coburg",
    "huk24": "HUK-Coburg",
    "huk coburg": "HUK-Coburg",
    "generali": "Generali",
    "signal iduna": "Signal Iduna",
    "r+v": "R+V",
    "r + v": "R+V",
    "devk": "DEVK",
    "dfv": "DFV",
    "barmenia": "Barmenia",
    "hannoversche": "Hannoversche",
    "cosmosdirekt": "Cosmosdirekt",
    "cosmos direkt": "Cosmosdirekt",
    "europa": "Europa",
    "monuta": "Monuta",
    "ideal": "Ideal",
    "württembergische": "Württembergische",
    "gothaer": "Gothaer",
    "nürnberger": "Nürnberger",
    "alte leipziger": "Alte Leipziger",
    "dialog": "Dialog",
    "wgv": "WGV",
}


def _fetch(url: str) -> str:
    """HTML einer Seite laden."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "de-DE,de;q=0.9",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  WARNUNG: {url} nicht erreichbar: {e}")
        return ""


def scrape_finanztip(product: str, url: str) -> list:
    """Parst Finanztip-Seite nach empfohlenen Versicherern.
    Gibt Liste der empfohlenen Brand-Namen zurueck."""
    html = _fetch(url)
    if not html:
        return []

    # HTML-Tags entfernen fuer einfacheres Text-Parsing
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)

    empfohlen = set()

    # Pattern 1: "Wir empfehlen" / "Unsere Empfehlung" / "empfehlen wir" Abschnitte
    patterns = [
        r"(?:empfehlen wir|wir empfehlen|unsere empfehlung|empfohlene tarife|empfohlene anbieter)[:\s]+(.*?)(?:\.|$)",
        r"(?:preissieger|leistungssieger|testsieger)[:\s]+(?:ist|sind)?[:\s]*(.*?)(?:\.|,|$)",
        r"(?:bester?|günstigster?)\s+(?:tarif|anbieter|versicher)\w*[:\s]+(.*?)(?:\.|,|$)",
    ]

    text_lower = text.lower()
    for pattern in patterns:
        for m in re.finditer(pattern, text_lower):
            snippet = m.group(1)
            # Suche nach bekannten Versicherern im Snippet
            for alias, brand in BRAND_ALIASES.items():
                if alias in snippet:
                    empfohlen.add(brand)

    # Pattern 2: Suche in strukturierten Listen/Tabellen
    # Finanztip listet oft Empfehlungen in <li> oder <td> Tags
    for m in re.finditer(r'(?:empf[oö]hl|empfehlung|sieger|top-tarif)\w*[^.]*?(?:' +
                          '|'.join(re.escape(a) for a in BRAND_ALIASES.keys()) +
                          r')', text_lower):
        snippet = m.group(0)
        for alias, brand in BRAND_ALIASES.items():
            if alias in snippet:
                empfohlen.add(brand)

    print(f"  Finanztip/{product}: {len(empfohlen)} empfohlene Marken: {', '.join(sorted(empfohlen)) or 'keine gefunden'}")
    return list(empfohlen)


def update_finanztip_ratings(ratings: dict) -> bool:
    """Aktualisiert Finanztip-Spalte in allen Produkten."""
    changed = False

    for product, url in FINANZTIP_URLS.items():
        if product not in ratings:
            continue

        empfohlen = scrape_finanztip(product, url)
        if not empfohlen:
            print(f"  Finanztip/{product}: Keine Empfehlungen gefunden — behalte bestehende Daten")
            continue

        for v in ratings[product]["versicherer"]:
            name = v["name"]
            old = v.get("finanztip", "—")
            if name in empfohlen:
                v["finanztip"] = "Empfohlen"
            else:
                # Nur ueberschreiben wenn vorher auch schon ein Wert da war
                if old not in ("Nicht getestet", "—", None):
                    v["finanztip"] = "Nicht empfohlen"
            if v["finanztip"] != old:
                changed = True
                print(f"    {name}: '{old}' -> '{v['finanztip']}'")

    return changed


def inject_into_dashboard(ratings: dict) -> bool:
    """Injiziert RATINGS_EXTERNAL in dashboard_template.html."""
    if not TEMPLATE_FILE.exists():
        print("[ratings] dashboard_template.html nicht gefunden — ueberspringe Injection")
        return False

    content = TEMPLATE_FILE.read_text(encoding="utf-8")

    # Marker suchen
    marker = "var RATINGS_DB = {"
    if marker not in content:
        # Alternativ: Suche nach bereits injiziertem RATINGS_EXTERNAL
        alt_marker = "var RATINGS_DB = (typeof RATINGS_EXTERNAL"
        if alt_marker in content:
            print("[ratings] RATINGS_DB ist bereits dynamisch — aktualisiere RATINGS_EXTERNAL")
        else:
            print("[ratings] RATINGS_DB Marker nicht gefunden")
            return False

    # RATINGS_EXTERNAL injizieren (als window-Variable)
    ratings_json = json.dumps(ratings, ensure_ascii=False, separators=(",", ":"))

    # Alte Injection entfernen
    cleaned_lines = []
    for line in content.split("\n"):
        if "window.RATINGS_EXTERNAL = {" in line:
            continue
        cleaned_lines.append(line)
    content = "\n".join(cleaned_lines)

    # Vor RATINGS_DB injizieren
    inject_line = f"  window.RATINGS_EXTERNAL = {ratings_json};"

    # Suche nach der RATINGS_DB Zeile und fuege davor ein
    if marker in content:
        content = content.replace(
            marker,
            inject_line + "\n  " + marker,
            1
        )
    elif "var RATINGS_DB = (typeof RATINGS_EXTERNAL" in content:
        # Bereits umgebaut — nur RATINGS_EXTERNAL aktualisieren
        content = content.replace(
            "var RATINGS_DB = (typeof RATINGS_EXTERNAL",
            inject_line + "\n  var RATINGS_DB = (typeof RATINGS_EXTERNAL",
            1
        )

    TEMPLATE_FILE.write_text(content, encoding="utf-8")
    print(f"[ratings] RATINGS_EXTERNAL in dashboard_template.html injiziert")
    return True


def main():
    print("=" * 60)
    print("[ratings] Externe Produktratings aktualisieren")
    print("=" * 60)

    # 1. Aktuelle Ratings laden
    if not RATINGS_FILE.exists():
        print(f"[ratings] {RATINGS_FILE} nicht gefunden — abbruch")
        return

    ratings = json.loads(RATINGS_FILE.read_text(encoding="utf-8"))
    print(f"[ratings] {RATINGS_FILE} geladen: {sum(len(r.get('versicherer', [])) for k, r in ratings.items() if isinstance(r, dict) and 'versicherer' in r)} Eintraege")

    # 2. Finanztip aktualisieren
    print("\n--- Finanztip Scraping ---")
    ft_changed = update_finanztip_ratings(ratings)

    # 3. Timestamp aktualisieren
    ratings["_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 4. Zurueckschreiben
    RATINGS_FILE.write_text(
        json.dumps(ratings, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n[ratings] {RATINGS_FILE} gespeichert")

    # 5. In Dashboard injizieren
    # Nur die Produkt-Daten (ohne _info/_updated Meta-Felder)
    inject_data = {}
    for key in ("zahnzusatz", "sterbegeld", "risikoleben"):
        if key in ratings:
            inject_data[key] = ratings[key]

    inject_into_dashboard(inject_data)
    print("[ratings] Fertig!")


if __name__ == "__main__":
    main()
