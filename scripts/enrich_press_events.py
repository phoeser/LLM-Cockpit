#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Publikations-Domain in die Presse-Ereignisse schreiben (12.08.2026)
===================================================================

Warum das noetig war
--------------------
Presse- und News-Ereignisse trugen bisher nur die Google-News-Weiterleitung
(news.google.com/rss/articles/CBMi...), nicht die Domain, auf der der Artikel
tatsaechlich erschienen ist. Fuer die Korrelationsrechnung war damit ein
Artikel auf ad-hoc-news.de — davon liegen 132 im Bestand — exakt dasselbe wie
einer auf finanztip.de, das im 30-Tage-Fenster 28.306 Zitate auf sich zieht.

Das ist die wahrscheinlichste Erklaerung dafuer, warum "Presse" im Modell als
nicht nachweisbar dasteht: Der Topf mischt Artikel, die in den Antworten der
Sprachmodelle ueberhaupt vorkommen koennen, mit solchen, die es nie tun.
Mittelt man beide, bleibt die Null uebrig, die das Dashboard heute zeigt.

Die Aufloesung auf die echte Domain passiert bereits — update_press.py schreibt
sie als `domain` in data/press_history.json. Sie wurde nur nie ins Ereignis
durchgereicht. Dieses Skript holt das nach.

Zuordnung
---------
Ueber den Artikeltitel, der in beiden Quellen steht — und seit 23.08.2026
zusaetzlich ueber den Verlagsnamen als Fallback (siehe quellen_index).
Was nicht zugeordnet werden kann, bekommt ausdruecklich
`zitat_klasse: unbekannt` — NICHT "nicht zitiert". Der Unterschied ist
wesentlich: eine fehlende Zuordnung ist keine Aussage ueber das Medium.

Klassen
-------
  zitiert_redaktionell — Domain wird von den Sprachmodellen zitiert und ist ein
                         redaktionelles Medium (finanztip, test.de, Fachpresse)
  zitiert_marke        — zitierte Domain, aber die eigene oder eine
                         Wettbewerber-Seite; ein Newsroom-Beitrag, kein
                         redaktioneller Artikel
  nicht_zitiert        — Domain taucht in den Zitaten nicht auf
  unbekannt            — keine Zuordnung moeglich

Idempotent: mehrfaches Laufen aendert nichts. Schreibt erst nach vollstaendiger
Pruefung und nur, wenn die Zeilenzahl unveraendert ist.

Aufruf:  python3 scripts/enrich_press_events.py
"""

import json
import os
import sys

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS = os.path.join(BASIS, "shared", "events.jsonl")
HISTORIE = os.path.join(BASIS, "data", "press_history.json")
ZITATE = os.path.join(BASIS, "data", "content_citations.json")

PRESSE_TYPEN = {"press_mention", "news_mention", "price_announcement"}


def lies_json(pfad, standard=None):
    try:
        with open(pfad, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return standard


def domain_klassen():
    """{domain: klasse} aus der Zitat-Auswertung."""
    cc = lies_json(ZITATE, {}) or {}
    presse = (cc.get("presse") or {})
    out = {}
    for d in (presse.get("domains") or []):
        dom = str(d.get("domain") or "").replace("www.", "").lower()
        if not dom:
            continue
        cls = str(d.get("cls") or "")
        # "You" und "Competitor" sind Markenseiten - ein Beitrag dort ist ein
        # Newsroom-Eintrag, kein redaktioneller Artikel. Der Unterschied ist
        # fuer die Frage "wirkt Presse" entscheidend.
        out[dom] = ("zitiert_redaktionell" if cls == "Editorial" else "zitiert_marke")
    return out, {k: (v.get("zitate") or 0) for k, v in
                 {d["domain"].replace("www.", "").lower(): d
                  for d in (presse.get("domains") or []) if d.get("domain")}.items()}


def quellen_index():
    """{quellen-name: domain} aus der Presse-Historie — der Fallback fuer alles,
    was der Titel-Abgleich nicht trifft.

    23.08.2026 (Modell-Audit, Pauls Go): Der Titel-Abgleich liess 63 % der
    2.813 Presse-Ereignisse unklassifiziert. Vor dem Umbau gemessen, auf dem
    echten Bestand: Die Google-News-URL ist seit dem Formatwechsel NICHT mehr
    dekodierbar (0 % Zugewinn) — der Verlagsname aus detail.media_source
    dagegen hebt die Abdeckung von 37 % auf 88 %.

    Sicherung gegen mehrdeutige Verlagsnamen: Ein Name wird nur uebernommen,
    wenn mindestens 90 % seiner Artikel in der Historie auf DIESELBE Domain
    zeigen. "t-online" -> t-online.de ist eindeutig; ein Name, der auf mehrere
    Domains streut, liefert bewusst keinen Treffer und das Ereignis bleibt
    "unbekannt" — eine fehlende Zuordnung ist keine Aussage ueber das Medium.
    """
    h = lies_json(HISTORIE, []) or []
    zaehl = {}
    for a in h:
        if not isinstance(a, dict):
            continue
        q = str(a.get("source") or "").strip().lower()
        dom = str(a.get("domain") or "").replace("www.", "").lower()
        if not q or not dom:
            continue
        zaehl.setdefault(q, {}).setdefault(dom, 0)
        zaehl[q][dom] += 1
    out = {}
    for q, doms in zaehl.items():
        gesamt = sum(doms.values())
        dom, n = max(doms.items(), key=lambda kv: kv[1])
        if gesamt and n / gesamt >= 0.9:
            out[q] = dom
    return out


def titel_index():
    """{titel: domain} aus der Presse-Historie."""
    h = lies_json(HISTORIE, []) or []
    idx = {}
    for a in h:
        if not isinstance(a, dict):
            continue
        t = (a.get("title") or "").strip()
        dom = str(a.get("domain") or "").replace("www.", "").lower()
        if t and dom and t not in idx:
            idx[t] = dom
    return idx


def main():
    if not os.path.exists(EVENTS):
        print("FEHLER: shared/events.jsonl fehlt.", file=sys.stderr)
        return 1

    klassen, gewichte = domain_klassen()
    idx = titel_index()
    q_idx = quellen_index()
    if not idx:
        print("Keine Presse-Historie mit Domains — nichts anzureichern.")
        return 0
    if not klassen:
        print("Keine Zitat-Auswertung (data/content_citations.json) — ohne sie laesst sich "
              "keine Klasse vergeben. Schritt uebersprungen.")
        return 0

    zeilen_neu = []
    n_gesamt = n_presse = n_gesetzt = n_schon = 0
    stat = {}

    with open(EVENTS, encoding="utf-8") as f:
        for L in f:
            roh = L.rstrip("\n")
            n_gesamt += 1
            if not roh.strip():
                zeilen_neu.append(roh)
                continue
            try:
                e = json.loads(roh)
            except Exception:
                zeilen_neu.append(roh)     # unveraendert durchreichen
                continue
            if e.get("event_type") not in PRESSE_TYPEN:
                zeilen_neu.append(roh)
                continue

            n_presse += 1
            d = e.setdefault("detail", {})
            # Bewusst KEIN Ueberspringen bereits klassifizierter Ereignisse:
            # Die Klasse haengt daran, welche Domains die Sprachmodelle gerade
            # zitieren, und das aendert sich. Ein Medium, das heute neu in den
            # Zitaten auftaucht, soll auch rueckwirkend richtig eingeordnet
            # sein - sonst zementiert der erste Lauf einen veralteten Stand.
            # Ausserdem waechst die Presse-Historie, wodurch frueher
            # unzuordenbare Ereignisse spaeter doch einen Partner finden.
            if d.get("zitat_klasse"):
                n_schon += 1

            titel = (d.get("title") or "").strip()
            dom = idx.get(titel)
            weg = "titel" if dom else None
            if not dom:
                # Fallback ueber den Verlagsnamen (siehe quellen_index-Kommentar).
                quelle = str(d.get("media_source") or "").strip().lower()
                dom = q_idx.get(quelle)
                weg = "quelle" if dom else None
            if dom:
                d["domain"] = dom
                d["zitat_klasse"] = klassen.get(dom, "nicht_zitiert")
                d["domain_zitate"] = gewichte.get(dom, 0)
                d["zuordnung_weg"] = weg
            else:
                # Ausdruecklich "unbekannt", nicht "nicht_zitiert": eine fehlende
                # Zuordnung ist keine Aussage ueber das Medium.
                d["zitat_klasse"] = "unbekannt"
                d.pop("zuordnung_weg", None)
            n_gesetzt += 1
            stat[d["zitat_klasse"]] = stat.get(d["zitat_klasse"], 0) + 1
            if weg:
                stat["_weg_" + weg] = stat.get("_weg_" + weg, 0) + 1
            zeilen_neu.append(json.dumps(e, ensure_ascii=False))

    # Nie eine funktionierende Datei durch eine kuerzere ersetzen.
    if len(zeilen_neu) != n_gesamt:
        print(f"FEHLER: Zeilenzahl weicht ab ({len(zeilen_neu)} statt {n_gesamt}) — "
              "es wird nichts geschrieben.", file=sys.stderr)
        return 1

    tmp = EVENTS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(zeilen_neu) + "\n")
    os.replace(tmp, EVENTS)

    print(f"Presse-Ereignisse klassifiziert: {n_gesetzt} gesamt, davon {n_schon} schon zuvor eingeordnet "
          f"(von {n_presse} Presse-/News-Ereignissen, {n_gesamt} Zeilen gesamt).")
    for k, v in sorted(stat.items(), key=lambda kv: -kv[1]):
        print(f"   {k:22s} {v:5d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
