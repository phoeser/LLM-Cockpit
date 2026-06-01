"""
Preisvergleich-Crawler: Holt Tarif-Preise und Bewertungen aus dem Check24
Vergleichsrechner via Playwright fuer 3 Produkte x 3 Altersprofile.

Ergebnis: data/price_comparison.json + Injection in Dashboard als PRICE_DATA.

Produkte: Zahnzusatz, Sterbegeld, Risikoleben
Altersprofile: 30 Jahre, 50 Jahre, 65 Jahre
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PRICE_FILE = Path("data/price_comparison.json")
TEMPLATE_FILE = Path("dashboard_template.html")

# Check24 Vergleichsrechner URLs pro Produkt
# Jedes Produkt hat eigene Parameter
PRODUCTS = {
    "zahnzusatz": {
        "name": "Zahnzusatzversicherung",
        # Check24 hat Zahnzusatz auf ein mehrstufiges Formular umgestellt (2026).
        # Wir fuellen das Formular ueber Playwright aus statt eines Deep-Links.
        "flow": "form",
        "url_tpl": "https://zusatzversicherung.check24.de/zahn/benutzereingaben/?c24api_birthdate={birth_de}",
        "form": {
            "radio_labels": ["Gesetzliche Krankenkasse", "nein", "nein", "nein", "nein"],
        },
    },
    "sterbegeld": {
        "name": "Sterbegeldversicherung",
        "flow": "deeplink",
        "url_tpl": (
            "https://sterbegeldversicherung.check24.de/desktop/calculation/result/check24?"
            "cbirth={birth}&cinssum=8000&prefill=true&waitingPeriodInMonths=36&"
            "cinception=20260601&cpayment=1&csort=4"
        ),
    },
    "risikoleben": {
        "name": "Risikolebensversicherung",
        # ALT (funktioniert nicht mehr): risikolebensversicherung.check24.de existiert nicht mehr.
        # Neuer Rechner: vorsorge.check24.de/risikoleben/benutzereingaben (Formular-Flow).
        # Wird nach erfolgreichem Zahn-PoC analog umgestellt.
        "flow": "deeplink",
        "url_tpl": (
            "https://risikolebensversicherung.check24.de/desktop/calculation/result/check24?"
            "cbirth={birth}&cinssum=100000&prefill=true&cinception=20260601&cpayment=1&csort=4"
        ),
    },
}

# Altersprofile (Geburtsdatum im Check24-Format YYYYMMDD)
AGE_PROFILES = [
    {"label": "30 Jahre", "birth": "19960530", "key": "age_30"},
    {"label": "50 Jahre", "birth": "19760530", "key": "age_50"},
    {"label": "65 Jahre", "birth": "19610530", "key": "age_65"},
]

# Unsere 10 Haupt-Versicherer (Check24-Name -> unser Brand-Key)
BRAND_MAP = {
    "ergo": "ergo", "ERGO": "ergo",
    "allianz": "allianz", "Allianz": "allianz",
    "axa": "axa", "AXA": "axa",
    "huk-coburg": "huk", "HUK-Coburg": "huk", "HUK24": "huk", "HUK": "huk",
    "generali": "generali", "Generali": "generali",
    "signal iduna": "signal-iduna", "Signal Iduna": "signal-iduna",
    "cosmosdirekt": "cosmosdirekt", "CosmosDirekt": "cosmosdirekt",
    "Cosmos Direkt": "cosmosdirekt", "COSMOS DIREKT": "cosmosdirekt",
    "r+v": "ruv", "R+V": "ruv",
    "devk": "devk", "DEVK": "devk",
    "hannoversche": "hannoversche", "Hannoversche": "hannoversche",
}

# JS-Code fuer DOM-Extraktion (Preise + Ratings + Bewertung pro Versicherer)
JS_EXTRACT = """() => {
    var results = [];
    // Finde alle Preis-Elemente und matche mit Versicherer-Logos
    document.querySelectorAll('*').forEach(function(el) {
        if (el.children.length > 0) return;
        var t = el.textContent.trim();
        // Preis: "20,59 €" Pattern
        if (!t.match(/^\\d{2,3},\\d{2}\\s*€$/)) return;
        var price = parseFloat(t.replace(',','.').replace('€','').trim());
        if (price < 1 || price > 500) return;

        var node = el;
        for (var i = 0; i < 12; i++) {
            node = node.parentElement;
            if (!node) break;
            var logo = node.querySelector('img[alt*="Logo"]');
            if (!logo) continue;
            var name = logo.alt.replace(/\\s*Logo\\s*/gi, '').trim();

            // Suche auch nach Tarifbewertung und Kundenbewertung
            var gradeEl = node.querySelector('[class*="tariffGrade"], [class*="grade"]');
            var grade = null;
            var gradeLabel = null;
            // Suche nach dem Muster "7.4 Gut" oder "9.4 Hervorragend"
            var gradeText = node.textContent || '';
            var gm = gradeText.match(/(\\d[.,]\\d)\\s*(Exzellent|Hervorragend|Sehr gut|Gut|Befriedigend|Ausreichend)/i);
            if (gm) {
                grade = parseFloat(gm[1].replace(',','.'));
                gradeLabel = gm[2];
            }

            // Kundenbewertung (Sterne)
            var ratingText = node.textContent || '';
            var rm = ratingText.match(/\\((\\d[.,]\\d)\\)\\s*([\\d.]+)/);
            var customerScore = rm ? parseFloat(rm[1].replace(',','.')) : null;
            var customerCount = rm ? parseInt(rm[2].replace(/\\./g,'')) : null;

            results.push({
                name: name,
                price: price,
                grade: grade,
                gradeLabel: gradeLabel,
                customerScore: customerScore,
                customerCount: customerCount
            });
            break;
        }
    });

    // Pro Versicherer: guenstigster Tarif
    var best = {};
    results.forEach(function(r) {
        if (!best[r.name] || r.price < best[r.name].price) {
            best[r.name] = r;
        }
    });
    return best;
}"""


def _drive_form(page):
    """Fuellt das Check24-Eingabeformular (benutzereingaben) aus und navigiert zum Ergebnis.
    Heuristisch + defensiv: Standard-Optionen waehlen, dann Weiter/Vergleichen klicken."""
    # 1) Krankenkasse-Typ: 'Gesetzliche Krankenkasse'
    try:
        page.get_by_text("Gesetzliche Krankenkasse", exact=False).first.click(timeout=4000)
        page.wait_for_timeout(300)
    except Exception:
        pass
    # 2) Alle ja/nein-Fragen mit 'nein' beantworten (je Frage eine Option)
    try:
        neins = page.locator("label", has_text=re.compile(r"^\s*nein\s*$", re.I))
        cnt = neins.count()
        for i in range(cnt):
            try:
                neins.nth(i).click(timeout=3000)
                page.wait_for_timeout(250)
            except Exception:
                pass
    except Exception:
        pass
    # 3) Weiter/Vergleichen-Button(s) klicken bis Ergebnisseite erreicht (mehrstufige Wizards)
    btn_re = re.compile(r"zum ergebnis|tarife (anzeigen|vergleichen)|jetzt vergleichen|vergleichen|weiter", re.I)
    for _ in range(6):
        if re.search(r"ergebnis|result|tarife|vergleich", page.url, re.I):
            break
        clicked = False
        try:
            b = page.locator("button:visible, a:visible", has_text=btn_re)
            if b.count() > 0:
                b.first.click(timeout=4000)
                clicked = True
                page.wait_for_timeout(2500)
        except Exception:
            pass
        if not clicked:
            break


def crawl_product_prices(product_key, product_config):
    """Crawlt Preise fuer ein Produkt ueber alle Altersprofile."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  Playwright nicht installiert — ueberspringe")
        return None

    product_data = {"name": product_config["name"], "profiles": {}}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            is_form = product_config.get("flow") == "form"
            for profile in AGE_PROFILES:
                b = profile["birth"]
                birth_de = "%s.%s.%s" % (b[6:8], b[4:6], b[0:4])  # YYYYMMDD -> DD.MM.YYYY
                url = product_config["url_tpl"].format(birth=b, birth_de=birth_de)
                print("  [%s] %s: %s" % (product_key, profile["label"], url[:90]))

                page = browser.new_page()
                try:
                    page.goto(url, timeout=45000)
                    try:
                        page.wait_for_load_state("networkidle", timeout=20000)
                    except Exception:
                        pass
                    page.wait_for_timeout(7000)

                    # Formular-Flow (Zahn/Risiko): Eingaben ausfuellen + zum Ergebnis navigieren
                    if is_form:
                        _drive_form(page)
                        try:
                            page.wait_for_load_state("networkidle", timeout=25000)
                        except Exception:
                            pass
                        page.wait_for_timeout(9000)

                    raw = page.evaluate(JS_EXTRACT)
                    # Falls noch keine Tarife: einmal nachladen + laenger warten
                    if not raw:
                        page.wait_for_timeout(6000)
                        raw = page.evaluate(JS_EXTRACT)

                    # Auf unsere Brands mappen
                    profile_data = {}
                    for c24_name, data in raw.items():
                        c24_lower = c24_name.lower().strip()
                        brand_key = BRAND_MAP.get(c24_name) or BRAND_MAP.get(c24_lower)
                        if brand_key:
                            profile_data[brand_key] = {
                                "price": data["price"],
                                "grade": data.get("grade"),
                                "grade_label": data.get("gradeLabel"),
                                "customer_score": data.get("customerScore"),
                                "customer_count": data.get("customerCount"),
                                "c24_name": c24_name,
                            }
                        else:
                            # Auch nicht-getrackte Versicherer speichern (fuer Kontext)
                            profile_data["_other_" + c24_name] = {
                                "price": data["price"],
                                "grade": data.get("grade"),
                                "grade_label": data.get("gradeLabel"),
                                "c24_name": c24_name,
                            }

                    product_data["profiles"][profile["key"]] = {
                        "label": profile["label"],
                        "birth": profile["birth"],
                        "brands": profile_data,
                        "total_tariffs": len(raw),
                    }
                    tracked = {k: v for k, v in profile_data.items() if not k.startswith("_other_")}
                    print("    %d Tarife, %d unsere Brands" % (len(raw), len(tracked)))
                    for bk, bv in sorted(tracked.items(), key=lambda x: x[1]["price"]):
                        print("      %s: %.2f EUR/Monat" % (bk, bv["price"]))

                except Exception as e:
                    print("    FEHLER: %s" % str(e)[:150])
                    product_data["profiles"][profile["key"]] = {
                        "label": profile["label"], "brands": {}, "error": str(e)[:200]
                    }
                finally:
                    page.close()

            browser.close()
    except Exception as e:
        print("  Playwright-Fehler: %s" % str(e)[:200])
        return None

    return product_data


def inject_into_dashboard(price_data):
    """Injiziert PRICE_DATA in dashboard_template.html."""
    if not TEMPLATE_FILE.exists():
        print("[prices] Template nicht gefunden")
        return False

    content = TEMPLATE_FILE.read_text(encoding="utf-8")
    marker = "const PRICE_DATA = window.PRICE_DATA || {};"
    if marker not in content:
        print("[prices] PRICE_DATA Marker nicht gefunden — ueberspringe")
        return False

    # Alte Injection entfernen
    cleaned = []
    for line in content.split("\n"):
        if "window.PRICE_DATA = {" in line:
            continue
        cleaned.append(line)
    content = "\n".join(cleaned)

    price_json = json.dumps(price_data, ensure_ascii=False, separators=(",", ":"))
    inject = "  window.PRICE_DATA = %s;" % price_json
    content = content.replace(marker, inject + "\n  " + marker)

    TEMPLATE_FILE.write_text(content, encoding="utf-8")
    print("[prices] PRICE_DATA injiziert")
    return True


def main():
    print("=" * 60)
    print("[prices] Check24 Preisvergleich-Crawler")
    print("=" * 60)

    all_data = {
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "profiles": [{"key": p["key"], "label": p["label"]} for p in AGE_PROFILES],
        "products": {},
    }

    for product_key, product_config in PRODUCTS.items():
        print("\n--- %s ---" % product_config["name"])
        result = crawl_product_prices(product_key, product_config)
        if result:
            all_data["products"][product_key] = result

    # Speichern
    PRICE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PRICE_FILE.write_text(json.dumps(all_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n[prices] %s gespeichert (%d KB)" % (PRICE_FILE, PRICE_FILE.stat().st_size // 1024))

    # In Dashboard injizieren
    inject_into_dashboard(all_data)

    print("[prices] Fertig!")


if __name__ == "__main__":
    main()
