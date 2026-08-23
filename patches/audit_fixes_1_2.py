# -*- coding: utf-8 -*-
"""Modell-Audit 23.08.2026, Fixes 1+2 (Pauls Go) — ein Patch, zwei Dateien.

FIX 1 — scripts/correlation_impact.py: Ko-Okkurrenz je Treiber.
Die einzige Luecke, die der Code nicht selbst benennt: Die Einzeltabelle
rechnet jeden Treiber allein, aber die Ereignistypen fallen massiv zusammen
(vorab auf dem echten Bestand gemessen: Preisaenderungen zu 95 % an Tagen mit
anderen Ereignissen derselben Marke, Bewertungen 85 %, LinkedIn 84 %;
review_change x review_volume phi=0,51, linkedin x instagram phi=0,42).
Jeder Einzeleffekt traegt also unbenannt die Wirkung seiner Nachbarn.
Neu: event_co_occurrence im JSON — je Treiber der Anteil der Ereigniszellen
(Marke x Tag) mit gleichzeitig anderem Typ plus die haeufigsten Begleiter,
dazu die auffaelligen Paar-Korrelationen. Gerechnet auf EXAKT den counts-
Zellen, die auch das Modell nutzt (dedupliziert, umdatiert).

FIX 2 — scripts/update_press.py: ERGO-Presse-Query angleichen.
Die ERGO-own_query lief ohne den Zusatz "+Presse OR Pressemitteilung", den
Allianz, AXA und Generali tragen — ERGO zaehlte alles auf ergo.com, die
Wettbewerber nur Presse-Seiten. Regimewechsel wird datiert im JSON
ausgewiesen (press_query_regime).

Sicherheitsnetz wie immer: jede Textstelle genau einmal, sonst Abbruch;
idempotent; Syntax-Pruefung beider Dateien am Ende.
"""
import ast
import io
import sys

def patch(pfad, ersetzungen):
    s=io.open(pfad,encoding='utf-8').read(); orig=s
    for name,alt,neu in ersetzungen:
        if alt in neu:
            if neu in s: print('schon da %-30s'%name); continue
        else:
            if alt not in s and neu in s: print('schon da %-30s'%name); continue
        n=s.count(alt)
        if n!=1:
            print('FEHLER   %-30s Treffer=%d in %s'%(name,n,pfad)); sys.exit(1)
        s=s.replace(alt,neu); print('ok       %-30s %+d'%(name,len(neu)-len(alt)))
    if s!=orig:
        ast.parse(s)   # bricht bei Syntaxfehler ab, BEVOR geschrieben wird
        io.open(pfad,'w',encoding='utf-8').write(s)
    return s!=orig

# ================= FIX 1: correlation_impact.py =================
CO_FUNC = '''

def _event_co_occurrence(counts, max_paare=8):
    """Ko-Okkurrenz der Ereignistypen auf den Modell-Zellen (Marke x Tag).

    23.08.2026 (Modell-Audit, Pauls Go): Die Einzeltabelle `impact` rechnet
    jeden Treiber fuer sich - was am selben Tag bei derselben Marke sonst noch
    passiert, steckt unbenannt im Schaetzer. Diese Auswertung macht das
    Ausmass sichtbar, damit das Dashboard es je Treiber ausweisen kann.
    Gerechnet wird auf denselben counts-Zellen wie das Modell selbst
    (nach Dedup und Presse-Umdatierung), sov_change ausgenommen.
    """
    zellen = []
    for b, tage in (counts or {}).items():
        for day, typen in tage.items():
            t = {k for k, v in typen.items() if v and k != "sov_change"}
            if t:
                zellen.append(t)
    if not zellen:
        return {"available": False, "grund": "keine Ereigniszellen"}
    alle_typen = sorted({t for z in zellen for t in z})
    je_typ = {}
    for t in alle_typen:
        mit_t = [z for z in zellen if t in z]
        n = len(mit_t)
        mit_anderen = sum(1 for z in mit_t if len(z) > 1)
        begleiter = {}
        for z in mit_t:
            for o in z:
                if o != t:
                    begleiter[o] = begleiter.get(o, 0) + 1
        top = sorted(begleiter.items(), key=lambda kv: -kv[1])[:3]
        je_typ[t] = {
            "label": TYPE_LABEL.get(t, t),
            "n_zellen": n,
            "anteil_mit_anderen": round(mit_anderen / n, 3) if n else None,
            "haeufigste_begleiter": [
                {"type": o, "label": TYPE_LABEL.get(o, o), "n_gemeinsam": c}
                for o, c in top],
        }
    # Paarweise phi-Korrelation der Inzidenzen; nur belastbare und auffaellige
    # Paare (beide Typen >= 10 Zellen, |phi| >= 0.15).
    paare = []
    nz = len(zellen)
    for i, a in enumerate(alle_typen):
        na = sum(1 for z in zellen if a in z)
        if na < 10:
            continue
        for b2 in alle_typen[i + 1:]:
            nb = sum(1 for z in zellen if b2 in z)
            if nb < 10:
                continue
            nab = sum(1 for z in zellen if a in z and b2 in z)
            pa, pb = na / nz, nb / nz
            nenner = (pa * (1 - pa) * pb * (1 - pb)) ** 0.5
            if nenner <= 0:
                continue
            phi = (nab / nz - pa * pb) / nenner
            if abs(phi) >= 0.15:
                paare.append({"a": a, "b": b2, "phi": round(phi, 2),
                              "n_gemeinsam": nab})
    paare.sort(key=lambda p: -abs(p["phi"]))
    return {
        "available": True,
        "n_zellen_mit_ereignis": nz,
        "je_typ": je_typ,
        "auffaellige_paare": paare[:max_paare],
        "hinweis": ("Anteil der Ereigniszellen (Marke x Tag) eines Typs, in denen "
                    "gleichzeitig mindestens ein anderer Typ auftritt. Ein hoher "
                    "Wert heisst: der Einzeleffekt dieses Treibers in der "
                    "impact-Tabelle traegt die Wirkung der Begleiter mit - nur "
                    "das multivariate Modell trennt sie."),
    }


def analyze(events, llm=None, brand_filter=None, llm_set=None, scope_label=None, prior_mean=None, validate=False):'''

FIX1 = [
    ('co_occurrence-Funktion',
     'def analyze(events, llm=None, brand_filter=None, llm_set=None, scope_label=None, prior_mean=None, validate=False):',
     CO_FUNC),
    ('co_occurrence ins JSON',
     '        "event_load_audit": EVENT_LOAD_AUDIT,',
     '        "event_load_audit": EVENT_LOAD_AUDIT,\n'
     '        "event_co_occurrence": _event_co_occurrence(counts),'),
]

# ================= FIX 2: update_press.py =================
FIX2 = [
    ('ERGO-Query angleichen',
     '        "own_query": "site:ergo.com+OR+site:ergo-group.com",',
     '''        # 23.08.2026 REGIMEWECHSEL (Modell-Audit, Pauls Go): Bis heute lief die
        # ERGO-Anfrage OHNE den Zusatz "+Presse OR Pressemitteilung", den
        # Allianz, AXA und Generali seit jeher tragen. Folge: ERGO zaehlte
        # ALLES, was Google auf ergo.com/ergo-group.com indexiert (auch
        # Magazin- und Ratgeberartikel), die Wettbewerber nur Presse-Seiten -
        # die press_mention-Zaehlbasis war systematisch asymmetrisch und der
        # ERGO-Vergleich damit unfair NACH OBEN verzerrt.
        # Ereignisse vor dem 23.08.2026 bleiben unveraendert im Bestand; wer
        # press_mention ueber diesen Tag hinweg vergleicht, vergleicht zwei
        # Erhebungsregime. Das JSON weist das unter press_query_regime aus.
        "own_query": "site:ergo.com+OR+site:ergo-group.com+Presse+OR+Pressemitteilung",'''),
    ('Regime-Konstante',
     'UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"',
     '''UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# Erhebungsregime der eigenen Pressemitteilungen - wird in die Ausgabe-JSON
# geschrieben, damit nachgelagerte Auswertungen den Bruch kennen, ohne diesen
# Code zu lesen.
PRESS_QUERY_REGIME = {
    "ergo_query_angeglichen_am": "2026-08-23",
    "hinweis": ("Bis 22.08.2026 lief die ERGO-own_query ohne '+Presse OR "
                "Pressemitteilung'; press_mention-Zahlen vor/nach diesem Tag "
                "entstammen verschiedenen Erhebungsregimen."),
}'''),
    ('Regime in out_data',
     '''    out_data = {
        "as_of": today,
        "sources": ["Google News RSS (Medien)", "Google News RSS (Eigene PMs via site:-Filter)"],
        "brands": brand_meta,''',
     '''    out_data = {
        "as_of": today,
        "sources": ["Google News RSS (Medien)", "Google News RSS (Eigene PMs via site:-Filter)"],
        "press_query_regime": PRESS_QUERY_REGIME,
        "brands": brand_meta,'''),
]

g1 = patch('scripts/correlation_impact.py', FIX1)
g2 = patch('scripts/update_press.py', FIX2)
print('Fertig. Geaendert: correlation_impact=%s update_press=%s' % (g1, g2))
