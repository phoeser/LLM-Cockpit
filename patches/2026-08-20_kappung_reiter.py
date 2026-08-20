#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kappungs-Markierung in LinkedIn- und Instagram-Reiter (20.08.2026).

Seit dem gestaffelten Sammeln vermerkt jeder Sammler im State, bei welchen
Marken die erlaubte Seitentiefe voll ausgeschoepft wurde - dort hatte Google
mehr Beitraege, als geholt wurden. Diese Zahlen sind Untergrenzen.

Warum das sichtbar sein MUSS: Der Tiefentest vom 20.08. hat ERGO auf LinkedIn
mit neun Posts der Woche VOLLSTAENDIG erfasst, Allianz dagegen mit zehn von
mindestens 37. Ohne Markierung liest man daraus einen Gleichstand, den es
nicht gibt - und zwar einen, der ERGO schmeichelt.

Dieser Patch laedt in beiden Reitern die State-Datei mit, stellt gekappte
Zahlen mit vorangestelltem Groesser-Gleich dar (Erklaerung im Tooltip) und
setzt unter die Aktivitaets-Tabelle einen Hinweis, welche Marken betroffen
sind.

Idempotent; bricht laut ab, wenn eine Textstelle nicht genau einmal passt.
"""
import sys
from pathlib import Path

HELFER = '''
  /* ---- Kappung: welche Marken sind Untergrenzen? (20.08.2026) ----
     Seit dem gemessenen Tiefentest blaettert der Sammler gestaffelt: vier
     Seiten fuer ERGO, Allianz, AXA und HUK-Coburg, eine Seite fuer die
     uebrigen sechs. Wo die Ausbeute die erlaubte Tiefe voll ausschoepfte,
     hatte Google mehr - der Sammler vermerkt das im State unter "gekappt".

     Warum das im Reiter stehen MUSS: Der Tiefentest hat ERGO auf LinkedIn mit
     neun Posts der Woche vollstaendig erfasst, Allianz dagegen mit zehn von
     mindestens 37. Ohne Markierung liest man daraus einen Gleichstand, den es
     nicht gibt - und zwar einen, der uns schmeichelt. */
  function istGekappt(marke){
    var g=(STATE&&STATE.gekappt)||null;
    return !!(g && g.indexOf(marke)>=0);
  }
  function zahlMitKappung(marke, n){
    return istGekappt(marke) ? ('<span title="Die erlaubte Seitentiefe war ausgeschöpft — Google hatte mehr. Untergrenze, keine Zählung.">≥ '+n+'</span>') : String(n);
  }
  function kappungsHinweis(){
    var g=(STATE&&STATE.gekappt)||[];
    if(!g.length) return '';
    return '<div class="text-xs text-amber-700 bg-amber-50 border-l-4 border-amber-400 rounded p-2 mt-2">'
      +'<b>≥ bedeutet Untergrenze.</b> Bei '+g.length+' Marke'+(g.length===1?'':'n')+' war die erlaubte Seitentiefe ausgeschöpft ('
      +g.map(esc).join(', ')+') — dort hatte Google mehr Beiträge, als wir geholt haben. '
      +'Die Tiefe ist bewusst gestaffelt, um im freien SerpAPI-Kontingent zu bleiben: vier Ergebnisseiten für ERGO, Allianz, AXA und HUK-Coburg, eine für die übrigen. '
      +'Ein Markenvergleich zwischen einer vollständigen und einer gekappten Zahl ist deshalb nicht belastbar.</div>';
  }

'''

LI_LADEN_ALT = '''      fetch("data/linkedin_kpis.jsonl?t="+Date.now(),{cache:"no-store"}).then(function(r){ return r.ok?r.text():null; }).catch(function(){ return null; })
    ]).then(function(res){
      GELADEN=true;'''

LI_LADEN_NEU = '''      fetch("data/linkedin_kpis.jsonl?t="+Date.now(),{cache:"no-store"}).then(function(r){ return r.ok?r.text():null; }).catch(function(){ return null; }),
      /* 20.08.2026: Der State weist aus, bei welchen Marken die erlaubte
         Seitentiefe voll ausgeschoepft wurde - dort hatte Google mehr, als wir
         geholt haben. Diese Zahlen sind Untergrenzen und muessen im Reiter auch
         so aussehen, sonst liest man sie als Zaehlung. */
      fetch("data/linkedin_state.json?t="+Date.now(),{cache:"no-store"}).then(function(r){ return r.ok?r.json():null; }).catch(function(){ return null; })
    ]).then(function(res){
      GELADEN=true;
      STATE=res[2]||null;'''

IG_LADEN_ALT = '''    fetch("data/instagram_posts.jsonl?t="+Date.now(),{cache:"no-store"})
      .then(function(r){ return r.ok?r.text():null; })
      .catch(function(){ return null; })
      .then(function(t){
        GELADEN=true;
        if(t==null){ LADEFEHLER=true; POSTS=null; cb(); return; }'''

IG_LADEN_NEU = '''    Promise.all([
      fetch("data/instagram_posts.jsonl?t="+Date.now(),{cache:"no-store"})
        .then(function(r){ return r.ok?r.text():null; }).catch(function(){ return null; }),
      /* 20.08.2026: Der State weist aus, bei welchen Marken die erlaubte
         Seitentiefe voll ausgeschoepft wurde - dort hatte Google mehr, als wir
         geholt haben. Diese Zahlen sind Untergrenzen und muessen im Reiter auch
         so aussehen, sonst liest man sie als Zaehlung. */
      fetch("data/instagram_state.json?t="+Date.now(),{cache:"no-store"})
        .then(function(r){ return r.ok?r.json():null; }).catch(function(){ return null; })
    ])
      .then(function(res){
        var t=res[0];
        STATE=res[1]||null;
        GELADEN=true;
        if(t==null){ LADEFEHLER=true; POSTS=null; cb(); return; }'''

ZELLEN_ALT = """        +'<td class="py-1.5 pr-2 text-right">'+(je30[b]||0)+'</td>'
        +'<td class="py-1.5 pr-2 text-right">'+(je90[b]||0)+'</td>'
        +'<td class="py-1.5 pr-2 text-right text-gray-500">'+(je[b]||0)+'</td>'"""

ZELLEN_NEU = """        +'<td class="py-1.5 pr-2 text-right">'+zahlMitKappung(b,je30[b]||0)+'</td>'
        +'<td class="py-1.5 pr-2 text-right">'+zahlMitKappung(b,je90[b]||0)+'</td>'
        +'<td class="py-1.5 pr-2 text-right text-gray-500">'+zahlMitKappung(b,je[b]||0)+'</td>'"""

ANKER_TAGVON = "  function tagVon(p){ return p.date || p.first_seen || null; }"
STATE_ALT = "  var POSTS=null, GELADEN=false, LADEFEHLER=false;"

HINWEIS_ALT_LI = """    h+='</tbody></table></div>'
      +'<div class="text-xs text-gray-400 mt-2">Datierung: Erscheinungstag, wenn Google ihn liefert, sonst Fund-Tag — grosse Marken"""

HINWEIS_ALT_IG = """    h+='</tbody></table></div>'
      +'<div class="text-xs text-gray-400 mt-2">Datierung: Erscheinungstag, wenn Google ihn liefert, sonst Fund-Tag."""


def paare(datei):
    kurz = "linkedin" if "linkedin" in datei else "instagram"
    yield ("State-Variable", STATE_ALT,
           STATE_ALT + '\n  var STATE=null;   // data/%s_state.json - u.a. die Liste "gekappt"' % kurz)
    if kurz == "linkedin":
        yield ("State mitladen", LI_LADEN_ALT, LI_LADEN_NEU)
    else:
        yield ("State mitladen", IG_LADEN_ALT, IG_LADEN_NEU)
    yield ("Hilfsfunktionen", ANKER_TAGVON, HELFER + ANKER_TAGVON)
    yield ("Zahlen als Untergrenze", ZELLEN_ALT, ZELLEN_NEU)
    alt = HINWEIS_ALT_LI if kurz == "linkedin" else HINWEIS_ALT_IG
    neu = alt.replace("    h+='</tbody></table></div>'\n",
                      "    h+='</tbody></table></div>'\n      +kappungsHinweis()\n", 1)
    yield ("Hinweis unter der Tabelle", alt, neu)


def main():
    fertig = 0
    for datei in ("linkedin_tab.js", "instagram_tab.js"):
        p = Path(datei)
        if not p.exists():
            print("FEHLER: %s nicht gefunden." % datei)
            return 1
        s = p.read_text(encoding="utf-8")
        if "kappungsHinweis" in s:
            print("[Patch] %s: bereits angewandt." % datei)
            fertig += 1
            continue
        for beschreibung, alt, neu in paare(datei):
            n = s.count(alt)
            if n != 1:
                print("FEHLER in %s bei '%s': %d Treffer (erwartet 1) - nichts geaendert."
                      % (datei, beschreibung, n))
                return 1
            s = s.replace(alt, neu, 1)
        p.write_text(s, encoding="utf-8")
        print("[Patch] %s angepasst." % datei)
    if fertig == 2:
        print("[Patch] Nichts zu tun.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
