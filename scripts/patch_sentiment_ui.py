"""Patcht die erweiterte Sentiment-UI in dashboard_template.html ein.

Fuegt unter der bestehenden Sentiment-Analyse Section eine neue
Quellen-Detail-Section ein mit:
- Pro Versicherer: Trustpilot, eKomi, Google, Finanztip Einzelwerte
- Sterne-Anzeige, Review-Counts, Links
- Responsive Grid-Layout

Dieses Script wird EINMALIG manuell ausgefuehrt, nicht im Nightly-Workflow.
"""
import re
from pathlib import Path

template = Path("dashboard_template.html")
if not template.exists():
    # Fallback Pfad
    template = Path("github-deployment/dashboard_template.html")

content = template.read_text(encoding="utf-8")

# ── 1) Neue HTML-Section nach dem Sentiment-Chart einfuegen ──────────────
NEW_SECTION = '''
  <!-- ===== SENTIMENT QUELLEN-DETAILS ===== -->
  <div class="bg-white rounded-xl p-6 shadow mb-6">
    <div class="flex items-start justify-between flex-wrap gap-3 mb-3">
      <div>
        <h3 class="text-lg font-bold text-ergo-dark">Bewertungen nach Quelle</h3>
        <p class="text-xs text-gray-500">Echte Bewertungsdaten aus Trustpilot, eKomi, Google und Finanztip · <span id="sentimentSourceDate"></span></p>
      </div>
      <div class="flex gap-2 flex-wrap">
        <span class="text-xs px-2 py-1 rounded" style="background:#f0fdf4;color:#166534">Trustpilot</span>
        <span class="text-xs px-2 py-1 rounded" style="background:#eff6ff;color:#1e40af">eKomi</span>
        <span class="text-xs px-2 py-1 rounded" style="background:#fef3c7;color:#92400e">Google</span>
        <span class="text-xs px-2 py-1 rounded" style="background:#f3e8ff;color:#6b21a8">Finanztip</span>
      </div>
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-sm" id="sentimentSourceTable">
        <thead>
          <tr class="bg-gray-100 text-left">
            <th class="px-3 py-2 font-semibold">Versicherer</th>
            <th class="px-3 py-2 font-semibold text-center" title="Trustpilot">Trustpilot</th>
            <th class="px-3 py-2 font-semibold text-center" title="eKomi">eKomi</th>
            <th class="px-3 py-2 font-semibold text-center" title="Google Places">Google</th>
            <th class="px-3 py-2 font-semibold text-center" title="Finanztip Verdict">Finanztip</th>
            <th class="px-3 py-2 font-semibold text-center" title="Anzahl Quellen mit Daten">Quellen</th>
          </tr>
        </thead>
        <tbody id="sentimentSourceTableBody"></tbody>
      </table>
    </div>
  </div>
'''

# Einfuegen nach dem "Sentiment je Produkt" Block
anchor = '</div>\n  </div>\n\n  <!-- ====='
# Suche das Ende der Sentiment-Produkt-Section
# Marker: sentimentByProduct div schliessen, dann naechste Section
insert_point = content.find('id="sentimentByProduct"')
if insert_point == -1:
    print("WARN: sentimentByProduct nicht gefunden, versuche Alternative")
    insert_point = content.find('Sentiment je Produkt')

if insert_point != -1:
    # Finde das Ende des umgebenden <div>-Blocks
    # Gehe zum naechsten "</div>\n  </div>" nach sentimentByProduct
    pos = insert_point
    depth = 0
    # Einfacher: suche das naechste "<!-- =====" nach sentimentByProduct
    next_section = content.find('<!-- =====', pos + 100)
    if next_section != -1:
        # Gehe zurueck zum letzten newline vor dem Kommentar
        while next_section > 0 and content[next_section-1] == ' ':
            next_section -= 1
        if content[next_section-1] == '\n':
            next_section -= 1
        # Suche eigentlich den Schluss-Tag der Produkt-Section
        close_marker = content.rfind('</div>', pos, next_section)
        close_marker2 = content.rfind('</div>', pos, close_marker)
        # Am sichersten: fuege nach "</div>\n\n  <!--" ein
        insert_at = content.rfind('\n', pos, next_section)
        # Noch besser: Direkt vor dem naechsten "<!-- =====" 
        insert_at = next_section + 1  # nach dem \n
        if content[insert_at:insert_at+1] == '\n':
            insert_at += 1
        content = content[:insert_at] + NEW_SECTION + '\n' + content[insert_at:]
        print("Quellen-Detail-Section eingefuegt bei Position %d" % insert_at)
    else:
        print("WARN: Naechste Section nach sentimentByProduct nicht gefunden")
else:
    print("ERROR: Konnte Insert-Position nicht finden")


# ── 2) JS-Funktion fuer Quellen-Tabelle einfuegen ────────────────────────
NEW_JS = '''
// ============= SENTIMENT QUELLEN-DETAILS (Live-Daten) =============
function buildSentimentSourceTable() {
  if (typeof SENTIMENT_DATA === 'undefined' || !SENTIMENT_DATA.by_source) return;
  const src = SENTIMENT_DATA.by_source;
  const keys = Object.keys(src);
  
  // Datum anzeigen
  const dateEl = document.getElementById('sentimentSourceDate');
  if (dateEl) dateEl.textContent = 'Stand: ' + (SENTIMENT_DATA.as_of || '?');
  const dateEl2 = document.getElementById('sentimentDate');
  if (dateEl2) dateEl2.textContent = SENTIMENT_DATA.as_of || '?';

  function stars(score, maxStars) {
    if (score === null || score === undefined) return '<span class="text-gray-300">—</span>';
    const full = Math.floor(score);
    const half = score - full >= 0.3 ? 1 : 0;
    const empty = (maxStars || 5) - full - half;
    return '<span class="text-yellow-500">' + '★'.repeat(full) + (half ? '½' : '') + '</span>' +
           '<span class="text-gray-300">' + '☆'.repeat(Math.max(0, empty)) + '</span>' +
           ' <span class="font-semibold">' + score.toFixed(1) + '</span>';
  }

  function count(n) {
    if (!n) return '';
    return '<div class="text-xs text-gray-400">' + n.toLocaleString('de-DE') + ' Reviews</div>';
  }

  function verdict(v) {
    if (!v) return '<span class="text-gray-300">—</span>';
    const map = {
      'empfehlung': { label: 'Empfohlen', cls: 'bg-green-100 text-green-800' },
      'alternativ': { label: 'Alternative', cls: 'bg-yellow-100 text-yellow-800' },
      'nicht-empfohlen': { label: 'Nicht empfohlen', cls: 'bg-red-100 text-red-800' },
      'keine-klare-empfehlung': { label: 'Keine Empf.', cls: 'bg-gray-100 text-gray-600' },
    };
    const m = map[v] || { label: v, cls: 'bg-gray-100 text-gray-600' };
    return '<span class="px-2 py-0.5 rounded text-xs font-medium ' + m.cls + '">' + m.label + '</span>';
  }

  function link(url, label) {
    if (!url) return '';
    return '<div class="mt-0.5"><a href="' + url + '" target="_blank" class="text-xs text-blue-500 hover:underline">' + (label || 'Details') + ' →</a></div>';
  }

  function srcBadge(n) {
    const cls = n >= 3 ? 'bg-green-100 text-green-700' : (n >= 2 ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700');
    return '<span class="px-2 py-0.5 rounded text-xs font-bold ' + cls + '">' + n + '/4</span>';
  }

  const tbody = document.getElementById('sentimentSourceTableBody');
  if (!tbody) return;

  let html = '';
  keys.forEach(k => {
    const b = src[k];
    const isErgo = k === 'ergo';
    const rowCls = isErgo ? 'font-semibold bg-red-50' : '';
    const tp = b.trustpilot || {};
    const ek = b.ekomi || {};
    const gp = b.google || {};
    const ft = b.finanztip || {};

    html += '<tr class="border-b hover:bg-gray-50 ' + rowCls + '">';
    html += '<td class="px-3 py-2">' + (b.name || k) + '</td>';
    html += '<td class="px-3 py-2 text-center">' + stars(tp.score, 5) + count(tp.count) + link(tp.url, 'Trustpilot') + '</td>';
    html += '<td class="px-3 py-2 text-center">' + stars(ek.score, 5) + count(ek.count) + link(ek.url, 'eKomi') + '</td>';
    html += '<td class="px-3 py-2 text-center">' + stars(gp.score, 5) + count(gp.count) + '</td>';
    html += '<td class="px-3 py-2 text-center">' + verdict(ft.verdict) + link(ft.url, 'Finanztip') + '</td>';
    html += '<td class="px-3 py-2 text-center">' + srcBadge(b.sources_count || 0) + '</td>';
    html += '</tr>';
  });
  tbody.innerHTML = html;
}
'''

# JS einfuegen nach buildSentimentChart()
js_anchor = "// ============= DOMAIN FOOTPRINT"
js_pos = content.find(js_anchor)
if js_pos != -1:
    content = content[:js_pos] + NEW_JS + '\n' + content[js_pos:]
    print("JS-Funktion buildSentimentSourceTable() eingefuegt")
else:
    print("WARN: JS-Anker nicht gefunden")


# ── 3) Aufruf in der Init-Funktion hinzufuegen ───────────────────────────
# Suche buildSentimentChart() Aufruf und fuege darunter buildSentimentSourceTable() ein
if 'buildSentimentSourceTable()' not in content:
    call_anchor = 'buildSentimentChart();'
    call_pos = content.find(call_anchor)
    if call_pos != -1:
        insert = call_pos + len(call_anchor)
        content = content[:insert] + '\n  buildSentimentSourceTable();' + content[insert:]
        print("buildSentimentSourceTable() Aufruf eingefuegt")
    else:
        print("WARN: buildSentimentChart() Aufruf nicht gefunden")
else:
    print("buildSentimentSourceTable() Aufruf bereits vorhanden")


# ── 4) Beschreibungstext aktualisieren ────────────────────────────────────
old_desc = 'Wie wird die Marke in LLM-Antworten charakterisiert? Positiv (lobend), neutral (faktisch), kritisch (mit Einschränkungen)'
new_desc = 'Gewichtete Analyse aus 4 Quellen: Trustpilot (35%), eKomi (20%), Google (15%), Finanztip (30%)'
content = content.replace(old_desc, new_desc, 1)


# Speichern
template.write_bytes(content.encode("utf-8").replace(b"\x00", b"").rstrip() + b"\n")
print("\nFertig. Template gespeichert: %d bytes" % template.stat().st_size)
