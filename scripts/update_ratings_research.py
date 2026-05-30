"""
Monatlicher Ratings-Research via Gemini API mit Websuche.

Recherchiert aktuelle Produktratings von Stiftung Warentest, Morgen & Morgen,
Verivox und DFSI fuer Zahnzusatz, Sterbegeld und Risikoleben.

Nutzt Gemini 2.0 Flash mit Google Search Grounding um aktuelle Testergebnisse
zu finden und strukturiert zurueckzugeben.

Ablauf:
1. Laedt aktuelle ratings_external.json als Basis
2. Fragt Gemini pro Produkt nach aktuellen Ratings aller 4 Quellen
3. Vergleicht mit bestehenden Daten
4. Aktualisiert nur bei Aenderungen (mit Timestamp)
5. Schreibt ratings_external.json zurueck
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RATINGS_FILE = Path("data/ratings_external.json")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Produkte und deren deutsche Bezeichnungen
PRODUCTS = {
    "zahnzusatz": "Zahnzusatzversicherung",
    "sterbegeld": "Sterbegeldversicherung",
    "risikoleben": "Risikolebensversicherung",
}

# Versicherer pro Produkt (aus ratings_external.json)
# Wird dynamisch geladen


def gemini_research(product_name: str, versicherer_names: list) -> dict:
    """Fragt Gemini nach aktuellen Ratings von 4 Quellen fuer ein Produkt."""
    if not GEMINI_API_KEY:
        print("  WARNUNG: Kein GEMINI_API_KEY gesetzt")
        return {}

    names_str = ", ".join(versicherer_names)

    prompt = (
        f"Recherchiere die aktuellen Produktratings fuer {product_name} in Deutschland.\n\n"
        f"Versicherer: {names_str}\n\n"
        f"Quellen (nur diese 4):\n"
        f"1. **Stiftung Warentest / Finanztest**: Schulnote oder Qualitaetsurteil (z.B. 'Sehr Gut (0,5)', 'Gut (1,7)', 'Befriedigend'). "
        f"   Bei Zahnzusatz: Finanztest-Ausgabe 2024 oder neuer. Bei Risikoleben: aktuelle Bewertungen.\n"
        f"2. **Morgen & Morgen (M&M)**: Sterne-Rating 1-5 (z.B. 5 Sterne = ausgezeichnet). "
        f"   M&M bewertet Tarife, nicht Unternehmen. Gib die hoechste Sternezahl an, die ein Tarif des Versicherers erreicht hat.\n"
        f"3. **Verivox**: Ranking-Position im Tarifvergleich (z.B. '#1', 'Top 5', 'Top 10', 'Top 20'). "
        f"   Falls nicht gelistet: '---'.\n"
        f"4. **DFSI (Deutsches Finanz-Service Institut)**: Qualitaetsbewertung (z.B. 'Hervorragend', 'Sehr Gut', 'Gut', 'Befriedigend'). "
        f"   DFSI veroeffentlicht in Focus Money.\n\n"
        f"Antworte als JSON-Array. Pro Versicherer ein Objekt:\n"
        f'{{"name": "ERGO", "warentest": "Gut (1,7-2,4)", "mm": 5, "verivox": "Top 10", "dfsi": "Sehr Gut"}}\n\n'
        f"Regeln:\n"
        f"- Nutze nur verifizierbare, aktuelle Daten (2024-2026)\n"
        f"- Wenn fuer einen Versicherer bei einer Quelle KEIN Rating existiert, setze den Wert auf '---'\n"
        f"- Bei M&M: Zahl 1-5 oder '---' (kein Text)\n"
        f"- Bei Sterbegeld: Stiftung Warentest raet generell von Sterbegeldversicherungen ab → setze 'Nicht empfohlen'\n"
        f"- Liefere NUR das JSON-Array, keinen weiteren Text\n"
    )

    try:
        # Gemini 2.0 Flash mit Google Search Grounding
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=%s" % GEMINI_API_KEY
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 2000,
                "responseMimeType": "application/json",
            },
            "tools": [{"google_search": {}}],
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers={
            "Content-Type": "application/json",
        })
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        # Antwort parsen
        text_resp = (
            result.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        text_resp = text_resp.strip()

        # JSON extrahieren (Gemini kann Markdown-Bloecke drumrum setzen)
        if text_resp.startswith("```"):
            text_resp = text_resp.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        ratings_list = json.loads(text_resp)
        if isinstance(ratings_list, list):
            return {r["name"]: r for r in ratings_list if "name" in r}
        elif isinstance(ratings_list, dict) and "name" in ratings_list:
            return {ratings_list["name"]: ratings_list}
        else:
            print(f"  Unerwartetes Format: {type(ratings_list)}")
            return {}

    except Exception as e:
        print(f"  Gemini-Fehler: {e}")
        return {}


def update_product_ratings(ratings: dict, product_key: str, product_name: str) -> int:
    """Aktualisiert Ratings fuer ein Produkt. Gibt Anzahl Aenderungen zurueck."""
    if product_key not in ratings:
        return 0

    versicherer = ratings[product_key]["versicherer"]
    names = [v["name"] for v in versicherer]

    print(f"\n--- {product_name} ({len(names)} Versicherer) ---")
    gemini_data = gemini_research(product_name, names)

    if not gemini_data:
        print(f"  Keine Daten von Gemini erhalten — behalte bestehende Werte")
        return 0

    changes = 0
    for v in versicherer:
        name = v["name"]
        if name not in gemini_data:
            # Versuche Case-insensitive Match
            matched = None
            for gn in gemini_data:
                if gn.lower() == name.lower():
                    matched = gn
                    break
            if not matched:
                continue
            name_key = matched
        else:
            name_key = name

        new_data = gemini_data[name_key]

        for field in ("warentest", "verivox", "dfsi"):
            new_val = new_data.get(field, "---")
            old_val = v.get(field, "---")
            # Normalisierung
            if new_val in (None, "", "null", "N/A", "k.A.", "keine Angabe"):
                new_val = "---"
            if str(new_val).strip() == "---" and str(old_val).strip() == "---":
                continue
            if str(new_val).strip() != "---" and str(new_val) != str(old_val):
                print(f"  {v['name']}/{field}: '{old_val}' -> '{new_val}'")
                v[field] = new_val
                changes += 1

        # M&M: Zahl oder "---"
        new_mm = new_data.get("mm", "---")
        old_mm = v.get("mm", "---")
        if isinstance(new_mm, (int, float)) and new_mm > 0:
            new_mm = int(new_mm)
            if new_mm != old_mm:
                print(f"  {v['name']}/mm: '{old_mm}' -> '{new_mm}'")
                v["mm"] = new_mm
                changes += 1

    return changes


def main():
    print("=" * 60)
    print("[ratings-research] Monatlicher Ratings-Research via Gemini")
    print("=" * 60)

    if not GEMINI_API_KEY:
        print("FEHLER: GEMINI_API_KEY nicht gesetzt — abbruch")
        sys.exit(0)  # Kein Fehler, damit Workflow weiterlaeuft

    if not RATINGS_FILE.exists():
        print(f"FEHLER: {RATINGS_FILE} nicht gefunden")
        sys.exit(0)

    ratings = json.loads(RATINGS_FILE.read_text(encoding="utf-8"))
    total_changes = 0

    for product_key, product_name in PRODUCTS.items():
        changes = update_product_ratings(ratings, product_key, product_name)
        total_changes += changes

    # Timestamp und speichern
    ratings["_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ratings["_last_research"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    RATINGS_FILE.write_text(
        json.dumps(ratings, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n{'=' * 60}")
    print(f"[ratings-research] {total_changes} Aenderungen gefunden und gespeichert")
    if total_changes == 0:
        print("[ratings-research] Keine neuen Ratings — alles aktuell")
    print("=" * 60)


if __name__ == "__main__":
    main()
