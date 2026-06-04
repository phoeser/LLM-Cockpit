"""
Preisvergleich-Crawler: Holt Tarif-Preise aus den Check24-Vergleichsrechnern
via Playwright fuer 3 Produkte x 3 Altersprofile.

Ergebnis: data/price_comparison.json + Injection in Dashboard als PRICE_DATA.

Produkte: Zahnzusatz (Form-Flow), Sterbegeld (Deeplink), Risikoleben (Deeplink)
Altersprofile: 30 Jahre, 50 Jahre, 65 Jahre

Fixes 2026-06-04 (per Live-Browser-Analyse verifiziert):
- Cookie-Consent-Layer blockierte alle Klicks -> wird per DOM-remove entfernt (ohne Einwilligung).
- Zahnzusatz: Pflicht-Checkbox 'Erstinformationen' wird jetzt gecheckt (war DER Submit-Blocker),
  Submit ist ein <a class="next_button"> ohne href (weder role=button noch role=link!).
- Risikoleben: vorsorge.check24.de gab 403 (Headless-UA) -> realistischer User-Agent;
  Ergebnisseite ist per GET-Deeplink mit c24api_*-Parametern erreichbar (kein Formular noetig).
- 'OK, verstanden'-Erstinformations-Modal auf Ergebnisseiten wird weggeklickt.
- Neuer primaerer Extraktor: Provider-Chips ('ab X,XX EUR' je Anbieter-Logo) — existieren
  auf Zahn- UND Risikoleben-Ergebnisseiten. Fallback: alter Karten-Extraktor (Sterbegeld).
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PRICE_FILE = Path("data/price_comparison.json")
TEMPLATE_FILE = Path("dashboard_template.html")

# Realistischer Desktop-UA gegen Bot-Erkennung (vorsorge.check24.de gab 403 bei Headless-UA)
REAL_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def _first_of_next_month():
    today = datetime.now(timezone.utc).date()
    if today.month == 12:
        return "%04d-01-01" % (today.year + 1)
    return "%04d-%02d-01" % (today.year, today.month + 1)


# Check24 Vergleichsrechner URLs pro Produkt
PRODUCTS = {
    "zahnzusatz": {
        "name": "Zahnzusatzversicherung",
        "params": "Profil: gesetzlich versichert, keine fehlenden Zaehne, kein Zahnersatz, keine Behandlung — guenstigster Tarif je Anbieter",
        # Einstufiges Angular-Formular. Geburtsdatum kommt per URL-Parameter an,
        # Radios sind sinnvoll vorbelegt, aber Angular-State ist 'pristine' ->
        # alle Gruppen muessen per trusted Click gesetzt werden + Erstinfo-Checkbox.
        "flow": "form",
        "url_tpl": "https://zusatzversicherung.check24.de/zahn/benutzereingaben/?c24api_birthdate={birth_de}",
    },
    "sterbegeld": {
        "name": "Sterbegeldversicherung",
        "params": "Profil: 8.000 EUR Versicherungssumme, monatliche Zahlweise — guenstigster Tarif je Anbieter",
        "flow": "deeplink",
        "url_tpl": (
            "https://sterbegeldversicherung.check24.de/desktop/calculation/result/check24?"
            "cbirth={birth}&cinssum=8000&prefill=true&waitingPeriodInMonths=36&"
            "cinception={inception}&cpayment=1&csort=4"
        ),
    },
    "risikoleben": {
        "name": "Risikolebensversicherung",
        "params": "Profil: konstante Summe 100.000 EUR, 20 Jahre Laufzeit, Nichtraucher, Bueroangestellte/r — guenstigster Tarif je Anbieter",
        # GET-Deeplink auf die Ergebnisseite (Form-Action des Onboarding-Formulars).
        # WICHTIG: Die leeren Parameter (rs_lang, rs_session, ...) sind Pflicht —
        # ohne sie liefert die Berechnung '0 Ergebnisse' (live verifiziert 2026-06-04).
        "flow": "deeplink",
        "url_tpl": (
            "https://vorsorge.check24.de/risikoleben/vergleichsergebnis/?"
            "c24api_rs_lang=&c24api_rs_session=&c24login_type=none&c24_controller=result&"
            "c24_calculate=x&c24api_currentinsurancetype=&c24api_smoker=no&c24api_nonsmokeryears=&"
            "c24api_birthdate={birth_de}&c24api_protectiontype=constant&c24api_protectiontarget=family&"
            "c24api_occupation_id=6194&c24api_sum_course=decreasing_linearly&c24api_sortfield=price&"
            "c24api_sortorder=asc&c24api_loannotolderthansixmonths=no&c24api_realestateproprietor=no&"
            "c24api_referringleadid=&c24api_children_discount=no&c24api_childnotolderthansixmonths=no&"
            "c24api_insure_sum=100.000&c24api_insure_period=20&c24api_paymentperiod=month&"
            "c24api_occupation_name=Angestellte%2Fr+%28%C3%BCber+90%25+B%C3%BCrot%C3%A4tigkeit%29&"
            "c24api_insure_date={insure_date}"
        ),
    },
}

def _birth_for_age(years):
    """Geburtsdatum YYYYMMDD, sodass die Person heute sicher N Jahre alt ist
    (Review-Fix 2026-06-04: vorher hartkodiert -> Profile alterten mit)."""
    from datetime import timedelta
    d = datetime.now(timezone.utc).date() - timedelta(days=int(years * 365.25) + 14)
    return d.strftime("%Y%m%d")


# Altersprofile (Geburtsdatum dynamisch, Check24-Format YYYYMMDD)
AGE_PROFILES = [
    {"label": "30 Jahre", "birth": _birth_for_age(30), "key": "age_30"},
    {"label": "50 Jahre", "birth": _birth_for_age(50), "key": "age_50"},
    {"label": "65 Jahre", "birth": _birth_for_age(65), "key": "age_65"},
]

# Unsere 10 Haupt-Versicherer (Check24-Name -> unser Brand-Key), exakte Treffer
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

# Substring-Matching fuer zusammengesetzte Check24-Namen
# (z.B. 'ERGO Vorsorge', 'Allianz Private Krankenversicherung AG')
BRAND_KEYWORDS = [
    ("signal iduna", "signal-iduna"),
    ("signal-iduna", "signal-iduna"),
    ("hannoversche", "hannoversche"),
    ("cosmos", "cosmosdirekt"),
    ("generali", "generali"),
    ("allianz", "allianz"),
    ("ergo", "ergo"),
    ("axa", "axa"),
    ("huk", "huk"),
    ("devk", "devk"),
    ("r+v", "ruv"),
]


def map_brand(c24_name):
    """Mappt einen Check24-Anbieternamen auf unseren Brand-Key (oder None)."""
    if c24_name in BRAND_MAP:
        return BRAND_MAP[c24_name]
    n = c24_name.lower().strip()
    if n in BRAND_MAP:
        return BRAND_MAP[n]
    for kw, key in BRAND_KEYWORDS:
        # Wortgrenzen, damit z.B. 'axa' nicht in 'Maxalta' matcht
        if re.search(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])", n):
            return key
    return None


# PRIMAERER Extraktor: Provider-Chips ('ab X,XX EUR' neben genau einem Anbieter-Logo).
# Existiert auf zahn- (zzv-frontend-provider-chip) und risikoleben-Ergebnisseiten
# (div.chips-provider__wrapper__option) — Selektor generisch ueber Struktur statt Klassen.
JS_EXTRACT_CHIPS = """() => {
    var out = {};
    document.querySelectorAll('*').forEach(function(el) {
        if (el.children.length > 2) return;
        var t = (el.textContent || '').trim();
        var m = t.match(/^ab\\s*(\\d{1,3}(?:\\.\\d{3})?,\\d{2})\\s*€$/);
        if (!m) return;
        var node = el;
        for (var i = 0; i < 5; i++) {
            node = node.parentElement;
            if (!node) break;
            var imgs = node.querySelectorAll('img[alt]:not([alt=""])');
            if (imgs.length === 1) {
                var name = imgs[0].alt.replace(/anbieter\\s*logo\\s*/gi, '')
                                       .replace(/\\s*logo\\s*/gi, ' ').trim();
                var price = parseFloat(m[1].replace('.', '').replace(',', '.'));
                if (name && price > 0 && (!(name in out) || price < out[name].price)) {
                    out[name] = {price: price, grade: null, gradeLabel: null,
                                 customerScore: null, customerCount: null};
                }
                break;
            }
            if (imgs.length > 1) break;
        }
    });
    return out;
}"""

# ZAHN-TILES: Tarif-Kacheln der Zahn-Ergebnisseite (Top-Anbieter) mit Tarifname
# und Leistungsumfang (Zahnersatz/Zahnbehandlung/Zahnreinigung) — ergaenzt die Chips.
JS_EXTRACT_ZAHN_TILES = """() => {
    var out = {};
    document.querySelectorAll('zzv-frontend-tariff-tile-container').forEach(function(tile) {
        var ln = tile.querySelector('zzv-frontend-tariff-tile-logo-and-name');
        var pr = tile.querySelector('zzv-frontend-tariff-tile-price');
        if (!ln || !pr) return;
        var img = ln.querySelector('img[alt]:not([alt=""])');
        var name = img ? img.alt.trim() : null;
        if (!name) return;
        var pm = (pr.textContent || '').match(/(\\d{1,3},\\d{2})\\s*€/);
        if (!pm) return;
        var price = parseFloat(pm[1].replace(',', '.'));
        var tarif = null;
        var lines = (ln.innerText || '').split('\\n').map(function(s){return s.trim();}).filter(Boolean);
        if (lines.length > 1) tarif = lines[lines.length - 1].slice(0, 60);
        var leistung = null;
        var sc = tile.querySelector('zzv-frontend-tariff-tile-service-summary-chips');
        if (sc) leistung = (sc.innerText || '').split('\\n').map(function(s){return s.trim();}).filter(Boolean).join(' / ').slice(0, 180);
        var grade = null;
        var gr = tile.querySelector('zzv-frontend-tariff-tile-grade');
        if (gr) { var gm = (gr.textContent || '').match(/(\\d[.,]\\d)/); if (gm) grade = parseFloat(gm[1].replace(',', '.')); }
        if (!(name in out) || price < out[name].price) {
            out[name] = {price: price, tarif: tarif, leistung: leistung, grade: grade};
        }
    });
    return out;
}"""


# FALLBACK-Extraktor (bisheriges Verfahren, funktioniert auf Sterbegeld-Seite):
# Preis-Element -> Vorfahr mit Versicherer-Logo, plus Tarifnote/Kundenbewertung
JS_EXTRACT = """() => {
    var results = [];
    document.querySelectorAll('*').forEach(function(el) {
        if (el.children.length > 0) return;
        var t = el.textContent.trim();
        if (!t.match(/^\\d{2,3},\\d{2}\\s*€$/)) return;
        var price = parseFloat(t.replace(',','.').replace('€','').trim());
        if (price < 1 || price > 500) return;

        var node = el;
        for (var i = 0; i < 12; i++) {
            node = node.parentElement;
            if (!node) break;
            var logo = node.querySelector('img[alt*="Logo"]');
            if (!logo) continue;
            var name = logo.alt.replace(/anbieter\\s*logo\\s*/gi, '').replace(/\\s*Logo\\s*/gi, '').trim();

            var gradeText = node.textContent || '';
            var gm = gradeText.match(/(\\d{1,2}(?:[.,]\\d)?)\\s*(Exzellent|Hervorragend|Sehr gut|Gut|Befriedigend|Ausreichend)/i);
            var grade = gm ? parseFloat(gm[1].replace(',','.')) : null;
            var gradeLabel = gm ? gm[2] : null;

            var rm = gradeText.match(/\\((\\d[.,]\\d)\\)\\s*([\\d.]+)/);
            var customerScore = rm ? parseFloat(rm[1].replace(',','.')) : null;
            var customerCount = rm ? parseInt(rm[2].replace(/\\./g,'')) : null;

            // Tarifname: Listen-Karten = Zeile nach Positionsnummer ('1.'),
            // Empfehlungs-Karten = Zeile nach 'monatlich' (live verifiziert 2026-06-04)
            var tarif = null;
            try {
                var lines = (node.innerText || '').split('\\n').map(function(s){return s.trim();}).filter(Boolean);
                var okName = function(c){ return c && c.length >= 3 && c.length <= 60 &&
                    !/€|%|Tarifbewertung|Wartezeit|beitragsfrei|Auszahlung|Weiterempfehlung|Gesundheits|Sonderzahlung|vergleichen/i.test(c); };
                for (var li = 0; li < lines.length - 1 && !tarif; li++) {
                    if (/^\\d+\\.$/.test(lines[li]) && okName(lines[li + 1])) tarif = lines[li + 1];
                }
                for (var li = 0; li < lines.length - 1 && !tarif; li++) {
                    if (/^monatlich/i.test(lines[li]) && okName(lines[li + 1])) tarif = lines[li + 1];
                }
            } catch(e) {}
            // Wartezeit: 'Keine Wartezeit' oder 'X Monate Wartezeit'
            var wz = null;
            var wm = gradeText.match(/(keine|\\d{1,2}\\s*Monate?n?)\\s*Wartezeit/i);
            if (wm) wz = /keine/i.test(wm[1]) ? 'keine' : wm[1].replace(/\\s+/g, ' ') + '';

            results.push({
                name: name, price: price, grade: grade, gradeLabel: gradeLabel,
                customerScore: customerScore, customerCount: customerCount,
                tarif: tarif, wartezeit: wz
            });
            break;
        }
    });

    var best = {};
    results.forEach(function(r) {
        if (!best[r.name] || r.price < best[r.name].price) {
            best[r.name] = r;
        }
    });
    // Fehlende Felder (Note/Tarif/Wartezeit/Bewertung) aus anderen Karten
    // derselben Marke auffuellen (z.B. Empfehlungs- vs. Listen-Karte)
    results.forEach(function(r) {
        var b = best[r.name];
        if (!b || b === r) return;
        ['grade','gradeLabel','customerScore','customerCount','tarif','wartezeit'].forEach(function(f){
            if ((b[f] === null || b[f] === undefined) && r[f] !== null && r[f] !== undefined) b[f] = r[f];
        });
    });
    return best;
}"""


# Diagnose-JS: erfasst bei 0 Tarifen, WAS auf der Seite ist (fuer gezielten Fix statt Raten)
JS_DIAG = """() => {
  function cnt(sel){ try{ return document.querySelectorAll(sel).length; }catch(e){ return -1; } }
  var heads = [].slice.call(document.querySelectorAll('h1,h2,h3,legend'))
    .map(function(h){ return (h.textContent||'').trim().slice(0,45); }).filter(Boolean).slice(0,12);
  var btns = [].slice.call(document.querySelectorAll('button,[role=button]'))
    .map(function(b){ return (b.textContent||'').trim().slice(0,30); }).filter(Boolean).slice(0,12);
  var body = (document.body && document.body.innerText) || '';
  return {
    title: (document.title||'').slice(0,70),
    radios: cnt('[role=radio],input[type=radio]'),
    inputs: cnt('input:not([type=hidden])'),
    buttons: cnt('button'),
    logos: cnt('img[alt*="Logo"]'),
    chips: cnt('[class*="provider-chip"],[class*="chips-provider"]'),
    price_like: (body.match(/\\d{1,3},\\d{2}\\s*€/g) || []).length,
    body_len: body.length,
    headings: heads,
    button_texts: btns,
    still_benutzereingaben: location.href.indexOf('benutzereingaben') >= 0
  };
}"""


def _dismiss_overlays(page):
    """Entfernt den C24-Cookie-Consent-Layer (per DOM-remove, OHNE Einwilligung — es
    werden keine Consent-Cookies gesetzt) und klickt das 'OK, verstanden'-Modal weg.
    Beide Overlays blockieren sonst saemtliche Klicks/Inhalte."""
    try:
        page.evaluate(
            "() => { document.querySelectorAll('[class*=cookie-consent],[id*=cookie-consent]')"
            ".forEach(function(e){e.remove()});"
            " if (document.body) document.body.style.overflow='auto'; }"
        )
    except Exception as e:
        print("    [overlay] cookie-remove: %s" % str(e)[:60])
    try:
        btn = page.get_by_role("button", name=re.compile(r"OK,?\s*verstanden", re.I))
        if btn.count() > 0:
            btn.first.click(timeout=3000)
            page.wait_for_timeout(1500)
            print("    [overlay] 'OK, verstanden'-Modal geschlossen")
    except Exception:
        pass


def _real_click(page, loc, what):
    """Echter Maus-Klick auf die Element-Mitte (trusted, ohne Actionability-Haenger).
    Angular Material ignoriert synthetische Events und Playwrights .check() scheitert
    an den versteckten Inputs — Koordinaten-Klick funktioniert (live verifiziert)."""
    try:
        el = loc.first
        el.scroll_into_view_if_needed(timeout=4000)
        page.wait_for_timeout(300)
        box = el.bounding_box()
        if not box:
            print("    [click] %s: keine bounding box" % what)
            return False
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.wait_for_timeout(300)
        return True
    except Exception as e:
        print("    [click] %s: %s" % (what, str(e)[:80]))
        return False


def _drive_form_zahn(page):
    """Fuellt das Zahnzusatz-Formular per echten Maus-Klicks aus und submittet.
    Reihenfolge: Krankenkasse-Radio -> 4x 'nein' -> Erstinfo-Checkbox -> a.next_button."""
    # 1) Krankenkasse: 'Gesetzliche Krankenkasse'
    _real_click(page, page.locator("mat-radio-button", has_text=re.compile("Gesetzliche", re.I)), "Krankenkasse")
    # 2) Alle 'nein'-Radios (je Frage eine Gruppe)
    try:
        neins = page.locator("mat-radio-button").filter(has_text=re.compile(r"^\s*nein\s*$", re.I))
        cnt = neins.count()
        print("    [form] %d 'nein'-Radios gefunden" % cnt)
        for i in range(cnt):
            _real_click(page, neins.nth(i), "nein-Radio %d" % i)
    except Exception as e:
        print("    [form] nein-Radios: %s" % str(e)[:70])
    # 3) Erstinformations-Checkbox (Pflicht)
    ok = _real_click(page, page.locator("mat-checkbox"), "Erstinfo-Checkbox")
    try:
        checked = page.locator("mat-checkbox input[type=checkbox]").first.is_checked()
    except Exception:
        checked = None
    print("    [form] Erstinfo-Checkbox gecheckt: %s (Klick: %s)" % (checked, ok))
    # Falls noch nicht gecheckt: zweiter Versuch direkt auf das innere Quadrat
    if not checked:
        _real_click(page, page.locator("mat-checkbox .mat-checkbox-inner-container, mat-checkbox [class*=checkbox-frame], mat-checkbox label"), "Checkbox-2.Versuch")
    # Formular-Status loggen
    try:
        st = page.evaluate("() => { var f=document.querySelector('#c24StartForm');"
                           " return f ? f.className : 'kein #c24StartForm'; }")
        print("    [form] Status: %s" % str(st)[:90])
    except Exception:
        pass
    # 4) Submit: <a class="next_button">
    clicked = _real_click(page, page.locator("a.next_button"), "Submit a.next_button")
    if not clicked:
        clicked = _real_click(page, page.get_by_text(re.compile("Tarife anzeigen", re.I)), "Submit Text-Fallback")
    print("    [form] Submit geklickt: %s" % clicked)
    # 5) Auf Ergebnisseite warten
    try:
        page.wait_for_url(re.compile(r"vergleichsergebnis|ergebnis|result"), timeout=30000)
        print("    [form] Ergebnisseite erreicht")
    except Exception:
        print("    [form] WARNUNG: Ergebnisseite nicht erreicht (URL: %s)" % page.url[:90])


def crawl_product_prices(product_key, product_config):
    """Crawlt Preise fuer ein Produkt ueber alle Altersprofile."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  Playwright nicht installiert — ueberspringe")
        return None

    product_data = {"name": product_config["name"], "params": product_config.get("params"), "profiles": {}}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                user_agent=REAL_UA,
                locale="de-DE",
                viewport={"width": 1440, "height": 1800},
                extra_http_headers={"Accept-Language": "de-DE,de;q=0.9"},
            )

            is_form = product_config.get("flow") == "form"
            for profile in AGE_PROFILES:
                b = profile["birth"]
                birth_de = "%s.%s.%s" % (b[6:8], b[4:6], b[0:4])  # YYYYMMDD -> DD.MM.YYYY
                url = product_config["url_tpl"].format(
                    birth=b, birth_de=birth_de, insure_date=_first_of_next_month(),
                    inception=_first_of_next_month().replace("-", ""),
                )
                print("  [%s] %s: %s" % (product_key, profile["label"], url[:90]))

                page = context.new_page()
                try:
                    page.goto(url, timeout=45000)
                    try:
                        page.wait_for_load_state("networkidle", timeout=20000)
                    except Exception:
                        pass
                    page.wait_for_timeout(5000)
                    _dismiss_overlays(page)

                    # Formular-Flow (Zahn): Eingaben ausfuellen + zum Ergebnis navigieren
                    if is_form:
                        _drive_form_zahn(page)
                        try:
                            page.wait_for_load_state("networkidle", timeout=25000)
                        except Exception:
                            pass
                        page.wait_for_timeout(7000)
                        _dismiss_overlays(page)  # Modal kann auf Ergebnisseite erscheinen
                    else:
                        # Deeplink: Preise werden asynchron berechnet — warten,
                        # Modal schliessen, nochmal warten
                        page.wait_for_timeout(6000)
                        _dismiss_overlays(page)
                        page.wait_for_timeout(6000)

                    # 1) Primaer: Provider-Chips ('ab X EUR' je Anbieter)
                    raw = page.evaluate(JS_EXTRACT_CHIPS)
                    src = "chips"
                    # Zahn: Tarif-Kacheln liefern Tarifname + Leistungsumfang -> anreichern
                    if product_key == "zahnzusatz" and raw:
                        try:
                            # Virtuelles Rendering: schrittweise scrollen und Kacheln einsammeln
                            tiles = {}
                            for step in range(14):
                                part = page.evaluate(JS_EXTRACT_ZAHN_TILES) or {}
                                for tn, tv in part.items():
                                    if tn not in tiles or tv["price"] < tiles[tn]["price"]:
                                        tiles[tn] = tv
                                page.mouse.wheel(0, 1000)
                                page.wait_for_timeout(450)
                            page.evaluate("window.scrollTo(0,0)")
                            tile_by_brand = {}
                            for tn, tv in (tiles or {}).items():
                                bk = map_brand(tn) or ("_other_" + tn)
                                if bk not in tile_by_brand or tv["price"] < tile_by_brand[bk]["price"]:
                                    tile_by_brand[bk] = tv
                            for c24_name, data in raw.items():
                                bk = map_brand(c24_name) or ("_other_" + c24_name)
                                tv = tile_by_brand.get(bk)
                                if tv:
                                    data["tarif"] = tv.get("tarif")
                                    data["leistung"] = tv.get("leistung")
                                    if data.get("grade") is None:
                                        data["grade"] = tv.get("grade")
                            print("    [zahn] %d Kacheln mit Tarifdetails gemergt" % len(tile_by_brand))
                        except Exception as te:
                            print("    [zahn] Tile-Merge: %s" % str(te)[:80])
                    # 2) Fallback: Karten-Extraktor (Sterbegeld-Layout)
                    if not raw:
                        raw = page.evaluate(JS_EXTRACT)
                        src = "cards"
                    # 3) Letzte Chance: laenger warten + beide nochmal
                    if not raw:
                        page.wait_for_timeout(8000)
                        _dismiss_overlays(page)
                        raw = page.evaluate(JS_EXTRACT_CHIPS) or page.evaluate(JS_EXTRACT)
                        src = "retry"

                    # Diagnose erfassen, wenn 0 Tarife (zeigt, woran der Crawl haengt)
                    diag = None
                    if not raw:
                        try:
                            diag = page.evaluate(JS_DIAG)
                            diag["final_url"] = page.url[:160]
                        except Exception as de:
                            diag = {"diag_error": str(de)[:120]}
                        print("    [diag] %s" % json.dumps(diag, ensure_ascii=False)[:300])

                    # Auf unsere Brands mappen
                    profile_data = {}
                    for c24_name, data in raw.items():
                        brand_key = map_brand(c24_name)
                        entry = {
                            "price": data["price"],
                            "grade": data.get("grade"),
                            "grade_label": data.get("gradeLabel"),
                            "customer_score": data.get("customerScore"),
                            "customer_count": data.get("customerCount"),
                            "tariff": data.get("tarif"),
                            "leistung": data.get("leistung"),
                            "waiting_period": data.get("wartezeit"),
                            "c24_name": c24_name,
                        }
                        if brand_key:
                            # guenstigster Preis gewinnt, falls mehrere C24-Namen auf
                            # denselben Brand mappen (z.B. 'ERGO' + 'ERGO Vorsorge')
                            if brand_key not in profile_data or entry["price"] < profile_data[brand_key]["price"]:
                                profile_data[brand_key] = entry
                        else:
                            entry.pop("customer_score", None)
                            entry.pop("customer_count", None)
                            profile_data["_other_" + c24_name] = entry

                    product_data["profiles"][profile["key"]] = {
                        "label": profile["label"],
                        "birth": profile["birth"],
                        "brands": profile_data,
                        "total_tariffs": len(raw),
                        "extractor": src if raw else None,
                    }
                    if diag:
                        product_data["profiles"][profile["key"]]["_diag"] = diag
                    tracked = {k: v for k, v in profile_data.items() if not k.startswith("_other_")}
                    print("    %d Anbieter (%s), %d unsere Brands" % (len(raw), src, len(tracked)))
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
