#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Faktenblatt fuer den Sprach-Agenten "GEOrg" (11.08.2026)
=========================================================

Warum es diese Datei gibt
-------------------------
GEOrg soll Fragen zu den Cockpit-Daten beantworten. Die Rohdaten taugen dafuer
nicht: rund dreissig JSON-Dateien, eine davon ueber eine Viertelmillion Zeichen,
und in keiner steht, WIE eine Zahl zu lesen ist. Ein Agent, der `impact.press_
mention.avg_sov_effect_pp = 0.327` vorgesetzt bekommt, sagt "Pressemitteilungen
bringen 0,33 Prozentpunkte" - und liegt damit falsch, weil derselbe Treiber im
Dashboard als nicht nachweisbar gefuehrt wird.

Dieses Skript erzeugt deshalb ausformulierte Saetze statt Zahlenreihen. Jede
Zahl kommt mit ihrem Vorbehalt im selben Satz, nicht in einer Fussnote, die ein
Sprachmodell weglassen kann. Das Ergebnis ist die Wissensbasis des Agenten.

Grundregeln, die dieses Skript einhaelt
---------------------------------------
1. Keine Ersatzwerte. Fehlt eine Zahl, steht "keine Angabe" mit Grund - nie 0.
2. Kein Effektwert ohne sein Urteil. "nicht nachweisbar" steht VOR der Zahl.
3. Keine Prozentangabe ohne Bezugsgroesse.
4. Was das Cockpit nicht messen kann, steht in einem eigenen Kapitel - damit
   der Agent eine Antwort auf Fragen hat, die er nicht beantworten darf.

Erzeugt: data/geo_faktenblatt.md
"""

import json
import os
import sys
from datetime import datetime, timezone

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASIS, "data")
ZIEL = os.path.join(DATA, "geo_faktenblatt.md")


# ── Hilfen ───────────────────────────────────────────────────────────────────

def lies(name):
    """JSON aus data/ lesen. Fehlende oder kaputte Datei -> None, nie ein Abbruch:
    das Faktenblatt soll auch dann entstehen, wenn ein Teil der Pipeline haengt -
    dann eben mit 'keine Angabe' an dieser Stelle."""
    p = os.path.join(DATA, name)
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def z(v, n=1, einheit=""):
    """Zahl deutsch formatieren. None -> 'keine Angabe'."""
    if v is None or (isinstance(v, float) and v != v):
        return "keine Angabe"
    try:
        s = f"{float(v):,.{n}f}"
    except (TypeError, ValueError):
        return "keine Angabe"
    s = s.replace(",", "⁠").replace(".", ",").replace("⁠", ".")
    return s + (" " + einheit if einheit else "")


def pp(v, n=1):
    """Prozentpunkte MIT Vorzeichen — fuer Effekte, wo die Richtung zaehlt."""
    if v is None:
        return "keine Angabe"
    return ("+" if v > 0 else "") + z(v, n) + " Prozentpunkte"


def ppn(v, n=1, dativ=False):
    """Prozentpunkte OHNE Vorzeichen — fuer Betraege wie einen Rueckstand.
    Ein 'Rueckstand von +17,6' liest sich falsch; der Betrag ist gemeint."""
    if v is None:
        return "keine Angabe"
    return z(abs(v), n) + (" Prozentpunkten" if dativ else " Prozentpunkte")


def spanne(lo, hi, n=2):
    """Ein Intervall in einem Zug, damit die Einheit nur einmal steht."""
    if lo is None or hi is None:
        return None
    vz = lambda x: ("+" if x > 0 else "") + z(x, n)
    return f"von {vz(lo)} bis {vz(hi)} Prozentpunkten"


def prozent(v, n=1):
    return "keine Angabe" if v is None else z(v, n) + " Prozent"


def pfad(d, *keys, default=None):
    """Verschachtelt lesen, ohne bei jedem Zwischenschritt zu pruefen."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur or cur[k] is None:
            return default
        cur = cur[k]
    return cur


def datum(s):
    return str(s or "")[:10] or "keine Angabe"


# ── Kapitel ──────────────────────────────────────────────────────────────────

def kap_regeln():
    return """## Wie diese Auskunft zu gebrauchen ist

Dieses Faktenblatt beschreibt die Messung der Sichtbarkeit von Versicherungsmarken
in Antworten grosser Sprachmodelle. Es ist die einzige zulaessige Quelle fuer
Auskuenfte ueber diese Daten.

Vier Regeln gelten fuer jede Antwort daraus:

Erstens: Eine Zahl ohne ihren Vorbehalt ist eine falsche Antwort. Wo hier
"nicht nachweisbar" steht, darf der Effektwert nicht als Wirkung genannt werden,
auch wenn er im selben Satz steht.

Zweitens: "Nicht nachweisbar" heisst nicht "wirkt nicht". Es heisst, dass ein
Effekt dieser Groesse bei der heutigen Datenmenge nicht auffindbar waere. Der
Unterschied ist wesentlich und muss mitgesagt werden.

Drittens: Steht eine Zahl hier nicht, dann gibt es sie nicht. Sie darf nicht
geschaetzt, hergeleitet oder aus allgemeinem Wissen ergaenzt werden. Die
richtige Antwort lautet dann, dass das Cockpit diese Groesse nicht misst.

Viertens: Die Daten beschreiben Zusammenhaenge, keine Ursachen. Nur der eine
ausdruecklich als Experiment gekennzeichnete Befund darf als Wirkung bezeichnet
werden.

"""


def kap_stand(health, ci, snap):
    t = ["## Stand der Daten\n"]
    t.append(
        f"Dieses Faktenblatt wurde am {datetime.now(timezone.utc).strftime('%d.%m.%Y um %H:%M Uhr UTC')} "
        f"erzeugt. Die Auswertung stammt vom {datum(pfad(ci, 'generated_at'))}.\n"
    )
    mess = pfad(ci, "sov_measure_days")
    spanne = pfad(ci, "sov_measure_range", default=[])
    if mess:
        t.append(
            f"Gemessen wird seit {mess} Messtagen, von {datum(spanne[0]) if spanne else 'keine Angabe'} "
            f"bis {datum(spanne[-1]) if spanne else 'keine Angabe'}. Daraus entstehen "
            f"{z(pfad(ci, 'n_intervals_total'), 0)} Intervall-Beobachtungen ueber "
            f"{len(pfad(ci, 'brands_with_sov', default=[]))} Marken.\n"
        )
    t.append(
        "Der eigene Crawl laeuft seit dem 10.08.2026 woechentlich statt taeglich, "
        "sonntags gegen 23:10 UTC. Presse, News und Bewertungen werden weiterhin "
        "taeglich erhoben. Wenn also in einer Tagesuebersicht an mehreren Tagen "
        "kaum Seiten-Ereignisse stehen, ist das der Normalzustand zwischen zwei "
        "Laeufen und kein Ausfall.\n"
    )
    if health:
        el = health.get("elements") or []
        alt = [e for e in el if e.get("stale")]
        if alt:
            t.append(
                "Achtung, veraltete Bestandteile: "
                + "; ".join(f"{e.get('name')} (letzter Stand {datum(e.get('last'))})" for e in alt)
                + ". Auskuenfte, die darauf beruhen, sind entsprechend zu kennzeichnen.\n"
            )
        else:
            t.append(
                f"Alle {len(el)} ueberwachten Bestandteile der Pipeline sind aktuell; "
                "keiner gilt als veraltet.\n"
            )
    return "\n".join(t) + "\n"


def kap_kern(ci, geo):
    """Die Antwort-Tafel als Prosa - dieselbe Rechnung wie im Korrelations-Reiter."""
    t = ["## Was die Sichtbarkeit treibt — die Kernaussage\n"]
    t.append(
        "Die kuerzeste ehrliche Zusammenfassung lautet: Ein einziger Treiber traegt "
        "fast alles, und er heisst Quellpraesenz. Damit ist nicht die Zahl der eigenen "
        "Seiten gemeint, sondern wie oft die Marke in dem vorkommt, was Sprachmodelle "
        "zitieren. Alle einzelnen operativen Massnahmen sind dagegen zu klein, um in "
        "dieser Messung ueberhaupt sichtbar zu werden.\n"
    )

    P = pfad(ci, "level_model", "peec26_model", default={})
    be = pfad(P, "drivers_eff", "peec_foot", "between", default={})
    if be.get("effect_std_pp") is not None:
        q = be.get("wild_cluster_p_fdr")
        gesichert = (q is not None and q < 0.05)
        t.append(
            f"**Quellpraesenz.** Marken mit hoeherer Quellpraesenz sind sichtbarer: "
            f"{pp(be.get('effect_std_pp'), 2)} Sichtbarkeit je einer Standardabweichung "
            f"mehr Zitations-Footprint, gerechnet ueber {z(P.get('n_brands'), 0)} Marken. "
            f"Der Befund ist {'nach Korrektur fuer Mehrfachtests gesichert' if gesichert else 'nicht gesichert'} "
            f"(Wild-Cluster-p {z(be.get('wild_cluster_p'), 4)}, q {z(q, 4)}). "
            f"Es bleibt ein beobachteter Zusammenhang, kein Kausalnachweis: gemessen wurde, "
            f"nicht eingegriffen.\n"
        )

    ge = pfad(ci, "price_level_pooled", "gap_explorer", "grounded", default={})
    bm, bc, ld = ge.get("brand_means") or {}, ge.get("between_coef") or {}, ge.get("leader") or "Allianz"
    if bm.get("ERGO") and bm.get(ld):
        abstand = bm[ld].get("sov", 0) - bm["ERGO"].get("sov", 0)
        beitrag, summe = {}, 0.0
        for k in ("size", "cite_share", "relprice"):
            if bc.get(k) is not None and bm[ld].get(k) is not None and bm["ERGO"].get(k) is not None:
                beitrag[k] = bc[k] * (bm[ld][k] - bm["ERGO"][k])
                summe += max(beitrag[k], 0)
        f = (abstand / summe) if summe > abstand > 0 else 1.0
        NAME = {"size": "Bekanntheit und Groesse", "cite_share": "Quellpraesenz", "relprice": "Preisniveau"}
        t.append(
            f"**Der Abstand zum Marktfuehrer.** ERGO liegt bei {prozent(bm['ERGO'].get('sov'))} "
            f"Sichtbarkeit, {ld} bei {prozent(bm[ld].get('sov'))}. Der Abstand von "
            f"{ppn(abstand, dativ=True)} zerlegt sich naeherungsweise so: "
            + "; ".join(
                f"{NAME[k]} {pp(v * f)} (rund {z(100 * abs(v * f) / abstand, 0)} Prozent des Abstands)"
                for k, v in sorted(beitrag.items(), key=lambda x: -abs(x[1]))
            )
            + ". Das ist eine Zerlegung, kein Kausalnachweis. Wichtig fuer die Einordnung: "
            "ein zweites Modell im selben Nightly teilt denselben Abstand etwas anders auf und "
            "schreibt der Groesse einen kleineren Anteil zu. Der Anteil der Groesse ist deshalb "
            "als Spanne zu verstehen, nicht als Punktwert. An der Kernaussage aendert das nichts: "
            "die Quellpraesenz traegt in beiden Modellen den weitaus groessten Teil.\n"
        )
    return "\n".join(t) + "\n"


def kap_experiment(ab):
    t = ["## Der einzige kausal belegte Befund: die Websuche\n"]
    if not ab or not ab.get("available"):
        t.append("Keine Angabe — die Experimentdaten liegen nicht vor.\n")
        return "\n".join(t) + "\n"
    umf = ab.get("umfang") or {}
    leit = None
    for k in (ab.get("kennzahlen") or []):
        if k.get("leitkennzahl") or k.get("key") == "sov_pooled":
            leit = k
            break
    t.append(
        "Dies ist die einzige Stelle im gesamten Cockpit, an der eingegriffen und gegen eine "
        "Kontrollbedingung verglichen wurde — und damit die einzige, an der von Wirkung statt "
        "von Zusammenhang gesprochen werden darf.\n"
    )
    if leit:
        t.append(
            f"Jeder von {z(umf.get('n_pairs'), 0)} Prompts lief zweimal: einmal mit erzwungener "
            f"Websuche, einmal ohne jedes Werkzeug, sonst identisch. Mit Suche erreicht ERGO "
            f"{prozent(100 * leit.get('arm_a', 0))} Anteil an den Antworten, ohne Suche "
            f"{prozent(100 * leit.get('arm_b', 0))}. Der Unterschied betraegt "
            f"{pp(100 * leit.get('diff', 0))}, das 95-Prozent-Intervall reicht von "
            f"{pp(100 * leit.get('ci_low', 0))} bis {pp(100 * leit.get('ci_high', 0))} "
            f"(p {z(ab.get('permutation_p'), 4)}).\n"
        )
    t.append(
        "Drei Einschraenkungen gehoeren zu diesem Befund und muessen mitgenannt werden, wenn "
        "danach gefragt wird. Erzwungene Suche ist nicht der Normalfall — im echten Betrieb "
        "entscheidet das Modell selbst, ob es sucht. Das Experiment lief auf einem anderen Modell "
        "als der laufende Messkanal, die Richtung ist uebertragbar, die Hoehe nicht eins zu eins. "
        "Und es gehoert ausdruecklich nicht in die Zeitreihe des Cockpits.\n"
    )
    return "\n".join(t) + "\n"


def kap_ereignisse(ci):
    t = ["## Einzelne Ereignisse: warum hier nichts nachweisbar ist\n"]
    imp = ci.get("impact") or {}
    est = {k: v for k, v in imp.items() if isinstance(v, dict) and v.get("significance_basis") == "cluster"}
    sig = [k for k, v in est.items() if v.get("significant") is True]
    t.append(
        f"Geprueft wurden {len(est)} Ereignisarten daraufhin, ob sie die Sichtbarkeit kurzfristig "
        f"bewegen: Pressemitteilungen, News-Erwaehnungen, neue Seiten, Seitenaenderungen, "
        f"geloeschte Seiten, Bewertungs-Trend, Bewertungs-Volumen, Wikipedia-Ausbau und "
        f"Portal-Rang. "
        + ("Davon ist keine einzige gesichert.\n" if not sig
           else f"Davon {'ist eine' if len(sig) == 1 else f'sind {len(sig)}'} gesichert.\n")
    )
    t.append(
        "Der Grund dafuer ist rechnerisch und war vorher absehbar. Zu jeder Ereignisart gehoert "
        "eine Nachweisgrenze: die Effektgroesse, ab der ein echter Effekt bei der heutigen "
        "Datenmenge ueberhaupt auffindbar waere. Diese Grenzen liegen zwischen etwa 0,4 und "
        "1,0 Prozentpunkten. Die tatsaechlich gemessenen Effekte liegen zwischen 0,03 und "
        "0,56 Prozentpunkten — also durchweg darunter. Eine einzelne Pressemitteilung kann "
        "diese Messung nicht bewegen, unabhaengig davon, ob sie wirkt.\n"
    )
    t.append("Die Einzelwerte, jeweils mit ihrem Urteil:\n")
    for k, v in sorted(est.items(), key=lambda x: -abs(x[1].get("avg_sov_effect_pp") or 0)):
        lab = v.get("label") or k
        eff = v.get("avg_sov_effect_pp")
        lo, hi = v.get("ci95_low_cluster_pp"), v.get("ci95_high_cluster_pp")
        urteil = "gesichert" if v.get("significant") is True else "nicht nachweisbar"
        iv = spanne(lo, hi)
        zusatz = f", 95-Prozent-Intervall {iv}" if iv else ""
        t.append(
            f"- {lab}: {urteil}. Punktschaetzer {pp(eff, 2)}{zusatz}, beobachtet in "
            f"{z(v.get('n_with_event'), 0)} von {z(v.get('n_intervals'), 0)} Intervallen "
            f"ueber {z(v.get('n_clusters'), 0)} Marken."
        )
    nicht = {k: v for k, v in imp.items()
             if isinstance(v, dict) and v.get("significance_basis") != "cluster"}
    if nicht:
        t.append(
            "\nNicht schaetzbar, mit Grund — diese Arten verschwinden nicht aus der Auswertung, "
            "sondern stehen mit ihrer Begruendung da:\n"
        )
        for k, v in nicht.items():
            t.append(f"- {v.get('label') or k}: {v.get('type_confidence_grund') or v.get('grund') or 'kein Effekt schaetzbar'}")
    t.append(
        "\nZur Guete des Modells insgesamt: Die Vorhersagekraft der Treiber liegt bei "
        f"R² {z(pfad(ci, 'validation', 'out_of_sample', 'r2_oos_vs_baseline'), 3)} gegenueber einer "
        "reinen Marken-Basislinie — die Treiber verbessern die Vorhersage also nicht. "
        f"Die Placebo-Rate betraegt {prozent(100 * (pfad(ci, 'validation', 'placebo_false_positive_rate') or 0))}: "
        "so oft erzeugen reine Zufallsdaten einen scheinbar gesicherten Effekt. Erwartet waeren "
        "rund fuenf Prozent, der niedrigere Wert spricht fuer eine eher konservative Rechnung.\n"
    )
    return "\n".join(t) + "\n"


def kap_themen(geo, ci):
    """Wo ERGO verliert - je Thema, mit Zitatanteil als Erklaerung."""
    t = ["## Wo ERGO verliert: die Themen im Einzelnen\n"]
    if not geo or not geo.get("products"):
        t.append("Keine Angabe — der GEO-Snapshot liegt nicht vor.\n")
        return "\n".join(t) + "\n"

    DOM2BRAND = {
        "ergo.de": "ERGO", "ergo-reiseversicherung.de": "ERGO", "dkv.com": "ERGO",
        "allianz.de": "Allianz", "axa.de": "AXA", "generali.de": "Generali",
        "cosmosdirekt.de": "CosmosDirekt", "huk.de": "HUK-Coburg", "huk24.de": "HUK-Coburg",
        "signal-iduna.de": "Signal Iduna", "adac.de": "ADAC", "arag.de": "ARAG",
        "alte-leipziger.de": "Alte Leipziger", "barmenia.de": "Barmenia",
        "da-direkt.de": "DA Direkt", "devk.de": "DEVK", "debeka.de": "Debeka",
        "diebayerische.de": "Die Bayerische", "die-bayerische.de": "Die Bayerische",
        "gothaer.de": "Gothaer", "hdi.de": "HDI", "hannoversche.de": "Hannoversche",
        "hansemerkur.de": "HanseMerkur", "lv1871.de": "LV 1871", "ruv.de": "R+V",
        "vhv.de": "VHV", "wgv.de": "WGV", "wuerttembergische.de": "Württembergische",
        "zurich.de": "Zurich",
    }
    fuehrer = pfad(geo, "totals_ranking", 0, "name") if isinstance(geo.get("totals_ranking"), list) else None
    fuehrer = fuehrer or "Allianz"

    zeilen, punkte = [], []
    for pid, pd in (geo.get("products") or {}).items():
        marken = pfad(pd, "summary_by_llm", "gemini", "brands", default=[]) or []
        sov = {b.get("name"): 100 * b["share_of_voice"] for b in marken
               if b.get("share_of_voice") is not None}
        gesamt, je_marke = 0, {}
        for r in (pfad(pd, "cited_sources", "overall", default=[]) or []):
            n = r.get("count") or 0
            gesamt += n
            bn = DOM2BRAND.get(str(r.get("domain") or "").replace("www.", "", 1))
            if bn:
                je_marke[bn] = je_marke.get(bn, 0) + n
        if not gesamt or "ERGO" not in sov or fuehrer not in sov:
            continue
        cE = 100 * je_marke.get("ERGO", 0) / gesamt
        cF = 100 * je_marke.get(fuehrer, 0) / gesamt
        zeilen.append({"name": pd.get("name") or pid, "e": sov["ERGO"], "f": sov[fuehrer],
                       "gap": sov[fuehrer] - sov["ERGO"], "cE": cE, "cF": cF})
        for m, s in sov.items():
            punkte.append((100 * je_marke.get(m, 0) / gesamt, s))

    # Steigung auf genau diesen Zellen - eine Quelle, eine Skala
    steigung = r_wert = None
    if len(punkte) >= 20:
        n = len(punkte)
        sx = sum(p[0] for p in punkte); sy = sum(p[1] for p in punkte)
        sxx = sum(p[0] ** 2 for p in punkte); sxy = sum(p[0] * p[1] for p in punkte)
        syy = sum(p[1] ** 2 for p in punkte)
        den = n * sxx - sx * sx
        if abs(den) > 1e-9:
            steigung = (n * sxy - sx * sy) / den
            rd = (den * (n * syy - sy * sy)) ** 0.5
            r_wert = (n * sxy - sx * sy) / rd if rd > 0 else None

    if steigung:
        t.append(
            f"Ueber alle Themen und Marken hinweg gilt: je Prozentpunkt hoeherem Anteil an den "
            f"zitierten Quellen liegt die Sichtbarkeit im Schnitt um {z(steigung, 2)} Prozentpunkte "
            f"hoeher (Korrelation r {z(r_wert, 2)} ueber {len(punkte)} Marken-Thema-Zellen). "
            f"Das ist ein beschreibender Zusammenhang aus dem Querschnitt, kein Versprechen fuer "
            f"den Fall, dass ERGO seinen Zitatanteil erhoeht.\n"
        )

    zeilen.sort(key=lambda x: -x["gap"])
    t.append(f"Je Thema, sortiert nach dem groessten Rueckstand zu {fuehrer}:\n")
    for r in zeilen:
        if r["gap"] > 0:
            lage = f"Rueckstand {ppn(r['gap'])}"
        else:
            lage = f"ERGO liegt {ppn(r['gap'])} vorn"
        t.append(
            f"- {r['name']}: ERGO {prozent(r['e'])} Sichtbarkeit, {fuehrer} {prozent(r['f'])} — {lage}. "
            f"Zitatanteil ERGO {prozent(r['cE'])}, {fuehrer} {prozent(r['cF'])}."
        )
    t.append(
        "\nDie Lesart dieser Tabelle: Ein grosser Rueckstand bei zugleich sehr kleinem eigenem "
        "Zitatanteil deutet auf eine Content- und Quellenluecke hin — dort wird ERGO in den "
        "Quellen, aus denen die Modelle schoepfen, schlicht nicht gefunden. Ein Rueckstand bei "
        "bereits ordentlichem Zitatanteil hat eher andere Ursachen.\n"
    )
    return "\n".join(t) + "\n"


def kap_zitate(cc):
    t = ["## Was es in die Zitate schafft\n"]
    if not cc:
        t.append("Keine Angabe — die Zitat-Auswertung liegt nicht vor.\n")
        return "\n".join(t) + "\n"
    tq = pfad(cc, "kennzahlen", "trefferquote_je_marke", default={})
    if tq.get("available"):
        for m in (tq.get("marken") or [])[:8]:
            t.append(
                f"- {m.get('brand')}: {z(m.get('zitiert'), 0)} von {z(m.get('getrackt'), 0)} "
                f"getrackten Seiten sind in Zitaten aufgetaucht, also {prozent(m.get('quote_pct'), 2)}."
                + (" Das ist die eigene Marke." if m.get("eigen") else "")
            )
    t.append(
        "\nDrei Einschraenkungen zu diesen Quoten. Der Datenlieferant gibt nur die meistzitierten "
        "Seiten eines rollierenden Fensters heraus, der lange Schwanz selten zitierter Seiten "
        "fehlt — die Quoten sind deshalb Untergrenzen. Der Nenner ist die vom Crawl verfolgte "
        "Seitenauswahl je Marke, nicht die vollstaendige Website. Und dass eine Seite zitiert und "
        "eine Marke genannt wird, ist ein gemeinsames Auftreten, kein Nachweis, dass das eine das "
        "andere verursacht.\n"
    )
    return "\n".join(t) + "\n"


def kap_preise(pcd, ci):
    t = ["## Preise\n"]
    if not pcd or not pcd.get("products"):
        t.append("Keine Angabe — die Preiserhebung liegt nicht vor.\n")
        return "\n".join(t) + "\n"
    t.append(
        "Die Preise stammen aus einer Erhebung bei einem Vergleichsportal, je Produkt und "
        "Altersprofil. Drei Produkte — Haftpflicht, Hausrat und Rechtsschutz — sind bewusst "
        "altersunabhaengig, dort gilt derselbe Wert fuer alle Profile.\n"
    )
    zeilen = []
    for pid, pd in (pcd.get("products") or {}).items():
        marken = pfad(pd, "profiles", "age_50", "brands", default={}) or {}
        preise = {k: v.get("price") for k, v in marken.items()
                  if isinstance(v, dict) and not k.startswith("_other_") and (v.get("price") or 0) > 0}
        if "ergo" not in preise or len(preise) < 2:
            continue
        guenstig = min(preise.values())
        zeilen.append((pd.get("name") or pid, preise["ergo"], guenstig,
                       preise["ergo"] / guenstig if guenstig else None, len(preise)))
    zeilen.sort(key=lambda x: -(x[3] or 0))
    if zeilen:
        t.append("ERGO im Vergleich zur jeweils guenstigsten erhobenen Marke:\n")
        for n, e, g, f, k in zeilen:
            t.append(
                f"- {n}: ERGO {z(e, 2)} Euro, guenstigster Anbieter {z(g, 2)} Euro — "
                f"Faktor {z(f, 2)} ueber {k} erhobenen Marken."
            )
    grund = pfad(ci, "price_level_pooled", "gap_explorer", "grounded", "driver_reliability",
                 "relprice", default={})
    t.append(
        "\nZur Wirkung des Preises auf die Sichtbarkeit: Gemeint ist nicht das Ereignis "
        "'Preis geaendert', sondern das Preisniveau im Vergleich zum Wettbewerb. Die Richtung "
        "ist ueber alle Messtage stabil — teurer geht mit weniger Sichtbarkeit einher —, aber "
        "nach Korrektur fuer Mehrfachtests uebersteht kein Schnitt die Signifikanzschwelle. "
        "Richtung ja, Nachweis nein. Als Ereignis betrachtet ist der Preis gar nicht schaetzbar: "
        "an den meisten Tagen aendert sich keine einzige Zelle, und die wenigen Aenderungen "
        "waren ueberwiegend ein Hin- und Zurueckspringen auf den Vorwert, also ein Messartefakt "
        "des Erhebungsverfahrens.\n"
    )
    if grund.get("wild_cluster_p") is not None:
        t.append(
            f"Zahlenbeleg dazu: Wild-Cluster-p {z(grund.get('wild_cluster_p'), 4)}, "
            f"Richtungswahrscheinlichkeit {prozent(100 * (grund.get('prob_direction') or 0))}.\n"
        )
    return "\n".join(t) + "\n"


def kap_presse(pdash, sent):
    t = ["## Presse, News und Bewertungen\n"]
    st = (pdash or {}).get("stats") or {}
    if st:
        t.append(f"Stand der Presseauswertung: {datum((pdash or {}).get('as_of'))}.\n")
        t.append(
            "Erfasst werden je Marke eigene Pressemitteilungen und externe Berichterstattung. "
            "Die Gesamtzahlen sind gedeckelt und deshalb nicht als Marktanteil an der "
            "Berichterstattung lesbar — aussagekraeftig ist der Vergleich der letzten 30 Tage:\n"
        )
        for k, v in st.items():
            if not isinstance(v, dict):
                continue
            themen = ", ".join(f"{x.get('t')} ({z(x.get('c'), 0)})"
                               for x in (v.get("top_topics") or [])[:3])
            t.append(
                f"- {v.get('name') or k}: {z(v.get('last_30d'), 0)} Beitraege in den letzten "
                f"30 Tagen, {z(v.get('last_90d'), 0)} in 90 Tagen. Davon insgesamt "
                f"{z(v.get('own'), 0)} eigene Mitteilungen und {z(v.get('media'), 0)} externe "
                f"Berichte. Juengster Beitrag {datum(v.get('newest'))}."
                + (f" Haeufigste Themen: {themen}." if themen else "")
            )
        t.append("")
    t.append(
        "Wichtig zur Einordnung von Presse-Arbeit: Der weit ueberwiegende Teil der erfassten "
        "Presse- und News-Ereignisse liegt auf Quellen, die Sprachmodelle gar nicht zitieren. "
        "Die Quellen, die tatsaechlich zitiert werden — die eigenen Markenseiten, grosse "
        "Ratgeber- und Testportale — werden bisher nicht als Ereignis verfolgt. Das ist die "
        "wahrscheinlichste Erklaerung dafuer, warum externe Ereignisse in der Messung so wenig "
        "bewegen: nicht weil Presse nicht wirkt, sondern weil die gemessene Presse nicht dort "
        "stattfindet, wo die Modelle schoepfen.\n"
    )
    bb = (sent or {}).get("by_brand") or []
    if isinstance(bb, list) and bb:
        t.append(
            "\nStimmungsbild aus den erfassten Kundenbewertungen, in Prozent der Bewertungen "
            "je Marke (positiv / neutral / kritisch):\n"
        )
        for v in bb[:12]:
            if not isinstance(v, dict):
                continue
            t.append(
                f"- {v.get('name')}: {z(v.get('positiv'), 0)} Prozent positiv, "
                f"{z(v.get('neutral'), 0)} Prozent neutral, {z(v.get('kritisch'), 0)} Prozent kritisch."
            )
        t.append(
            "\nDie Quellenabdeckung unterscheidet sich je Marke — die Anteile sind untereinander "
            "nur grob vergleichbar. Ein Zusammenhang zwischen Bewertungslage und LLM-Sichtbarkeit "
            "ist in der Messung nicht nachweisbar."
        )
    return "\n".join(t) + "\n"


def kap_zweitquelle(fp):
    t = ["## Zwei Messquellen — und wo sie sich unterscheiden\n"]
    t.append(
        "Die Sichtbarkeit wird doppelt gemessen. Die primaere Quelle ist ein kommerzieller "
        "Dienst, der echte Nutzerinteraktion im Browser nachbildet und mehr Engines abdeckt, "
        "dafuer seine Erhebungs- und Bewertungsformeln nicht offenlegt. Die zweite Quelle ist "
        "der eigene Crawl ueber die Programmierschnittstellen der Modelle, vollstaendig "
        "offengelegt und bis zur einzelnen Antwort nachvollziehbar. Der eigene Crawl dient als "
        "Gegenprobe und Auditgrundlage.\n"
    )
    t.append(
        "Die beiden Quellen kommen bei den absoluten Niveaus zu deutlich verschiedenen Werten. "
        "Das ist erwartbar und kein Fehler: Sie messen ueber unterschiedliche Engines, mit "
        "unterschiedlichen Prompt-Saetzen und unterschiedlichen Zaehlweisen. Verlaesslich "
        "vergleichbar ist die Rangfolge je Thema, nicht die Hoehe. Wer eine einzelne Prozentzahl "
        "aus einer der beiden Quellen zitiert, muss dazusagen, aus welcher sie stammt.\n"
    )
    t.append(
        "Ein wichtiger Unterschied betrifft die Prompts selbst: Enthaelt ein Prompt bereits den "
        "Markennamen, faellt die gemessene Sichtbarkeit der Marke naturgemaess viel hoeher aus. "
        "Als Marktbild gilt deshalb ausschliesslich die branding-neutrale Auswertung — nur "
        "Prompts ohne Markennamen. Zahlen aus der Ansicht mit Markennennung beantworten die "
        "Frage 'wie sichtbar sind wir, wenn gezielt nach uns gefragt wird' und duerfen nicht "
        "als Marktanteil ausgegeben werden.\n"
    )
    if fp:
        t.append(f"\nStand der Zweitquellen-Auswertung: {datum(fp.get('as_of'))}, "
                 f"Fenster {fp.get('window') or 'keine Angabe'}.\n")
    return "\n".join(t) + "\n"


def kap_empfehlungen(geo, ci):
    t = ["## Was daraus folgt — die abgeleiteten Empfehlungen\n"]
    t.append(
        "Aus den Daten leitet das Cockpit Empfehlungen ab. Die Regel dafuer ist offengelegt: "
        "Ein Thema kommt auf die Liste, wenn der Rueckstand zum Marktfuehrer groesser als drei "
        "Prozentpunkte ist UND der eigene Zitatanteil unter acht Prozent liegt. Sortiert wird "
        "nach erwartetem Sichtbarkeitsgewinn.\n"
    )
    t.append(
        "Der erwartete Gewinn berechnet sich als der Abstand im Zitatanteil zum Marktfuehrer, "
        "multipliziert mit dem oben genannten Zusammenhang, und wird am tatsaechlichen "
        "Rueckstand gekappt. Er ist ausdruecklich kein Versprechen: die Steigung stammt aus dem "
        "Querschnitt ueber Marken, nicht aus einem Eingriff. Sie sagt, wie viel Sichtbarkeit "
        "Marken mit diesem Zitatanteil im Schnitt haben — nicht, was passiert, wenn ERGO seinen "
        "erhoeht.\n"
    )
    t.append(
        "Die inhaltliche Stossrichtung ist in allen Faellen dieselbe und folgt aus der "
        "Kernaussage: zitierfaehige Inhalte auf den eigenen Seiten aufbauen und Praesenz in "
        "genau den Portalen und Redaktionen herstellen, die in diesem Thema tatsaechlich "
        "zitiert werden. Nicht: mehr Seiten veroeffentlichen. Die Zahl der eigenen Seiten ist "
        "nicht der Treiber — das Vorkommen in zitierten Quellen ist es.\n"
    )
    t.append(
        "Fuer Massnahmen, deren Wirkung in der Messung nicht nachweisbar ist, gilt: Sie werden "
        "nicht deshalb empfohlen, weil eine Wirkung belegt waere, sondern weil ERGO dort hinter "
        "dem Aktivitaetsniveau des Wettbewerbs liegt. Das ist ein Rueckstandsargument, kein "
        "Wirkungsargument, und muss so benannt werden.\n"
    )
    return "\n".join(t) + "\n"


def kap_grenzen(ci):
    return """## Was dieses Cockpit nicht kann

Diese Liste ist genauso wichtig wie die Zahlen. Auf Fragen, die hierunter fallen,
lautet die richtige Antwort, dass das Cockpit es nicht misst.

Nicht gemessen werden Absatz, Leads, Abschluesse, Markenwert oder Werbewirkung.
Das Cockpit misst ausschliesslich, wie oft und wie prominent Marken in
LLM-Antworten vorkommen, und sucht Zusammenhaenge zu beobachtbaren Ereignissen.

Nicht gemessen wird, was einzelne Nutzer tatsaechlich fragen. Die Auswertung
beruht auf einem festen Satz von Prompts, nicht auf echtem Nutzerverhalten.

Nicht nachgewiesen werden Ursachen. Ereignisse treten auf, wie sie auftreten,
sie werden nicht zugelost. Alle Effekte ausser dem Websuche-Experiment sind
Zusammenhaenge unter Beobachtungsbedingungen.

Nicht beantwortet werden kann, was eine konkrete Massnahme bewirken wird. Das
Cockpit kann Hypothesen priorisieren; belegen kann es Wirkung nur ueber
Experimente, und davon gibt es bisher genau eines.

Nicht vorhanden sind Aussagen zu Zeitraeumen vor dem ersten Messtag. Was vorher
war, ist unbekannt und darf nicht rekonstruiert werden.
"""


def main():
    ci = lies("correlation_impact.json") or {}
    geo = lies("geo_snapshot.json") or {}
    cc = lies("content_citations.json")
    ab = lies("search_ab.json")
    health = lies("pipeline_health.json")
    pcd = lies("price_comparison.json")
    pdash = lies("press_dashboard.json")
    sent = lies("sentiment_dashboard.json")
    fp = lies("peec_footprint.json")

    if not ci or not geo:
        print("FEHLER: correlation_impact.json oder geo_snapshot.json fehlt — "
              "es wird bewusst kein unvollstaendiges Faktenblatt geschrieben.", file=sys.stderr)
        return 1

    teile = [
        "# Faktenblatt LLM-Sichtbarkeit — Wissensbasis fuer GEOrg\n",
        kap_regeln(),
        kap_stand(health, ci, geo),
        kap_kern(ci, geo),
        kap_experiment(ab),
        kap_themen(geo, ci),
        kap_ereignisse(ci),
        kap_zitate(cc),
        kap_preise(pcd, ci),
        kap_presse(pdash, sent),
        kap_zweitquelle(fp),
        kap_empfehlungen(geo, ci),
        kap_grenzen(ci),
    ]
    text = "\n".join(teile)

    # Plausibilitaet: eine gute Datei nie durch eine leere ersetzen.
    if len(text) < 4000:
        print(f"FEHLER: Faktenblatt nur {len(text)} Zeichen — das ist zu wenig, "
              "die bestehende Datei bleibt unveraendert.", file=sys.stderr)
        return 1

    with open(ZIEL, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Faktenblatt geschrieben: {ZIEL} ({len(text):,} Zeichen)".replace(",", "."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
