# -*- coding: utf-8 -*-
"""Ko-Okkurrenz-Spalte in die 90-%-Tabelle des Dashboards (23.08.2026).

Nachzuegler zu patches/audit_fixes_1_2.py: Beim Deploy ging die Deploy-Seite
vom Vormittag durch, die die 90-%-Sicht OHNE die Spalte "gleichzeitig anderes"
enthielt. Dieses Skript traegt genau die vier fehlenden Ersetzungen nach -
dieselben, die im Browser gegen echte und simulierte Daten getestet wurden.

Die Spalte liest das Feld event_co_occurrence, das audit_fixes_1_2.py in
correlation_impact.py einbaut. Bis zum ersten Nightly danach zeigt sie
"keine Angabe" mit Hinweis - nie einen Ersatzwert.

WICHTIG fuer den Betreiber: Der Commit dieses Workflows loest den
Dashboard-Build NICHT automatisch aus (Bot-Pushes starten keine Workflows).
Nach "Patch anwenden" einmal "Dashboard ausliefern" starten.
"""
import io
import sys

P = 'dashboard_v3.html'
s = io.open(P, encoding='utf-8').read()
orig = s

if 'Die 90-%-Sicht' not in s:
    print('FEHLER: Die 90-%-Tabelle fehlt im Dashboard - dieses Skript setzt '
          'den Deploy vom 23.08. voraus. Nichts geaendert.')
    sys.exit(1)

def rep(alt, neu, name):
    global s
    if neu in s:
        print('schon da %-22s' % name); return
    n = s.count(alt)
    if n != 1:
        print('FEHLER   %-22s Treffer=%d' % (name, n)); sys.exit(1)
    s = s.replace(alt, neu); print('ok       %-22s %+d' % (name, len(neu)-len(alt)))

rep("""      est.sort(function(a,b){ return b.pRoh-a.pRoh; });""",
"""      /* 23.08.2026: Ko-Okkurrenz aus dem Nightly (event_co_occurrence, Fix 1
         des Modell-Audits). Bis der erste Nightly nach dem Patch gelaufen ist,
         fehlt das Feld — dann steht "keine Angabe", nie ein Ersatzwert. */
      var co=(ci.event_co_occurrence&&ci.event_co_occurrence.available)?ci.event_co_occurrence:null;
      est.forEach(function(x){
        var j=co&&co.je_typ&&co.je_typ[x.k];
        x.koAnteil=(j&&j.anteil_mit_anderen!=null)?j.anteil_mit_anderen:null;
        x.koBegleiter=(j&&j.haeufigste_begleiter||[]).map(function(b){return b.label||b.type;}).slice(0,2).join(', ');
      });
      est.sort(function(a,b){ return b.pRoh-a.pRoh; });""", 'Ko-Daten anreichern')

rep("""        +'<th class="px-2 text-right">gedämpft</th><th class="px-2 text-right">90-%-Intervall</th><th class="px-2">Lesart (90 % Sicherheit)</th></tr></thead><tbody>';""",
"""        +'<th class="px-2 text-right">gedämpft</th><th class="px-2 text-right">90-%-Intervall</th>'
        +'<th class="px-2 text-right" title="Anteil der Ereignistage (Marke × Tag) dieses Treibers, an denen gleichzeitig mindestens ein anderer Ereignistyp auftritt. Hoch = der Einzeleffekt trägt die Wirkung der Begleiter mit.">gleichzeitig anderes</th>'
        +'<th class="px-2">Lesart (90 % Sicherheit)</th></tr></thead><tbody>';""", 'Spaltenkopf')

rep("""          +'<td class="px-2 text-right text-gray-500">'+_sgn(x.lo90,2)+' … '+_sgn(x.hi90,2)+'</td>'
          +'<td class="px-2 text-xs text-gray-600">'+lesart+'</td></tr>';""",
"""          +'<td class="px-2 text-right text-gray-500">'+_sgn(x.lo90,2)+' … '+_sgn(x.hi90,2)+'</td>'
          +'<td class="px-2 text-right'+(x.koAnteil!=null&&x.koAnteil>=0.8?' text-amber-700 font-semibold':' text-gray-500')+'"'+(x.koBegleiter?(' title="meist zusammen mit: '+_esc(x.koBegleiter)+'"'):'')+'>'
          +(x.koAnteil!=null?(_kv(100*x.koAnteil,0)+'&nbsp;%'):'<span class="text-gray-400">keine Angabe</span>')+'</td>'
          +'<td class="px-2 text-xs text-gray-600">'+lesart+'</td></tr>';""", 'Zelle')

rep("""        +'Belastbar bleiben die Obergrenzen (die gelten je Treiber für sich) und alles, was oben die cluster-robuste 95-%-Schwelle nimmt.</div>'
        +'</div>';
      h+=h2;""",
"""        +'Belastbar bleiben die Obergrenzen (die gelten je Treiber für sich) und alles, was oben die cluster-robuste 95-%-Schwelle nimmt.'
        +(co
          ? ((co.auffaellige_paare&&co.auffaellige_paare.length)
              ? (' <b>Verbandelte Treiber</b> (φ der Tages-Inzidenzen): '+co.auffaellige_paare.slice(0,4).map(function(p){
                  var la=(co.je_typ[p.a]||{}).label||p.a, lb=(co.je_typ[p.b]||{}).label||p.b;
                  return _esc(la)+' × '+_esc(lb)+' ('+(p.phi>0?'+':'')+String(p.phi).replace('.',',')+')';
                }).join(' · ')+' — deren Einzeleffekte sind nicht sauber trennbar.')
              : '')
          : ' <span class="text-gray-400">Die Spalte „gleichzeitig anderes“ füllt sich mit dem nächsten Nightly (Feld event_co_occurrence).</span>')
        +'</div>'
        +'</div>';
      h+=h2;""", 'Fusszeile')

if s != orig:
    io.open(P, 'w', encoding='utf-8').write(s)
print('Fertig. Geaendert:', s != orig)
