# -*- coding: utf-8 -*-
"""Berichte-ueber-ERGO-Tabelle in den Reiter Content & Zitate (24.08.2026).

Pauls Frage: "hast du klar gekennzeichnet, welche Seiten, Presseartikel und
Berichte ueber uns wie oft zitiert werden?" - Seiten und Presseartikel: ja.
Externe BERICHTE ueber ERGO: die Daten lagen laengst je URL in
content_citations.json (peec_brands), das Dashboard zeigte sie aber nur auf
Domain-Ebene. Diese Tabelle schliesst die Luecke: 391 externe zitierte Seiten
mit ERGO-Erwaehnung, je URL mit Zitatzahl, Verlauf und den anderen Marken in
denselben Antworten. Im Browser gegen die echten Daten getestet.

Idempotent; Ziel-Blob nach Anwendung: 80c62b2d1d9b7f10c39ba4cf6db63faa008ed05c (im Trockenlauf verifiziert)
"""
import io, sys
P='content_citations.js'
s=io.open(P,encoding='utf-8').read()
BLOCK="  /* 24.08.2026 (Frage Paul: \"welche Berichte ueber uns werden wie oft zitiert?\"):\n     Die Daten lagen laengst in data/content_citations.json (seiten[] mit\n     peec_brands je URL), aber das Dashboard zeigte externe Quellen nur auf\n     Domain-Ebene. Diese Tabelle schliesst die Luecke: externe zitierte Seiten,\n     in deren Antworten ERGO vorkommt - je URL mit Zitatzahl und Verlauf.\n     Dieselben Kappungs-Regeln wie bei den eigenen Seiten: \"nicht in Auswahl\"\n     heisst unbekannt, nie 0. */\n  function blockUeberUns(d) {\n    var staende = ((d.meta.quellen || {}).peec_snapshots || {}).staende || [];\n    var rows = (d.seiten || []).filter(function (r) {\n      return !r.ist_eigene_seite && (r.peec_brands || []).indexOf(\"ERGO\") >= 0 && (r.peec_cit || 0) > 0;\n    });\n    var html = h3(\"Berichte über ERGO: meistzitierte externe Seiten (\" + rows.length + \")\");\n    if (!rows.length) {\n      return html + missing(\"Keine externe zitierte Seite nennt ERGO in den zugehörigen Antworten.\");\n    }\n    rows.sort(function (a, b) { return (b.peec_cit || 0) - (a.peec_cit || 0); });\n    html += '<div style=\"font-size:11px;color:#6b7280;margin-bottom:6px\">Externe Quellen aus der Peec-Auswahl, ' +\n      \"in deren KI-Antworten ERGO erwähnt wird — das sind die Seiten, aus denen die Modelle ihr ERGO-Bild beziehen. \" +\n      \"Sortiert nach Zitaten im rollierenden 30-Tage-Fenster.</div>\";\n    html += '<div style=\"overflow-x:auto\"><table style=\"width:100%;border-collapse:collapse;font-size:11.5px\">' +\n      '<thead><tr style=\"text-align:left;color:#6b7280\">' +\n      '<th style=\"padding:5px 6px\">Seite</th>' +\n      '<th style=\"padding:5px 6px\">Typ</th>' +\n      '<th style=\"padding:5px 6px;text-align:right\">Zitate</th>' +\n      '<th style=\"padding:5px 6px\">Verlauf ' + esc((staende[0] || \"\").slice(5)) + \"–\" + esc((staende[staende.length - 1] || \"\").slice(5)) + \"</th>\" +\n      '<th style=\"padding:5px 6px\">weitere Marken in den Antworten</th></tr></thead><tbody>';\n    rows.slice(0, 25).forEach(function (r) {\n      var andere = (r.peec_brands || []).filter(function (b) { return b !== \"ERGO\"; });\n      var typ = r.peec_cls ? esc(r.peec_cls) : (r.seitentyp ? esc(r.seitentyp) : '<span style=\"color:#b0b4bb\">–</span>');\n      html += '<tr style=\"border-top:1px solid #f0f0f0\">' +\n        '<td style=\"padding:6px\"><a href=\"' + esc(r.url_raw) + '\" target=\"_blank\" rel=\"noopener\" style=\"color:' + COL.text + ';text-decoration:none\">' +\n        esc(shortUrl(r.url_norm)) + \"</a>\" +\n        (r.peec_title ? '<div style=\"color:#9ca3af;font-size:10px\">' + esc(r.peec_title) + \"</div>\" : \"\") + \"</td>\" +\n        '<td style=\"padding:6px\">' + typ + \"</td>\" +\n        '<td style=\"padding:6px;text-align:right;font-weight:700\">' + num(r.peec_cit) + \"</td>\" +\n        '<td style=\"padding:6px\">' + sparkline(r.peec_cit_verlauf, staende) + \"</td>\" +\n        '<td style=\"padding:6px;color:#6b7280\">' + (andere.length ? esc(andere.slice(0, 4).join(\", \")) + (andere.length > 4 ? \" +\" + (andere.length - 4) : \"\") : \"nur ERGO\") + \"</td></tr>\";\n    });\n    html += \"</tbody></table></div>\";\n    if (rows.length > 25) {\n      html += note(\"Angezeigt: die 25 meistzitierten von \" + num(rows.length) + \" externen Seiten mit ERGO-Erwähnung.\");\n    }\n    html += note(\"»ERGO wird erwähnt« heisst: In den KI-Antworten, die diese Seite zitieren, kommt die Marke vor (Feld peec_brands) — \" +\n      \"nicht zwingend, dass die Seite selbst von ERGO handelt. Trustpilot-/Bewertungsseiten und Vergleichsportale zählen dazu.\");\n    return html;\n  }\n\n  function build(d) {"
A1="  function build(d) {"
A2="blockTrefferquote(d) + blockVerlauf(d) + blockPresse(d) + blockEngines(d) +"
N2="blockTrefferquote(d) + blockVerlauf(d) + blockUeberUns(d) + blockPresse(d) + blockEngines(d) +"
if 'function blockUeberUns' in s and N2 in s:
    print('schon da - nichts zu tun'); sys.exit(0)
if s.count(A1)!=1 or s.count(A2)!=1:
    print('FEHLER: Anker nicht eindeutig (%d/%d)'%(s.count(A1),s.count(A2))); sys.exit(1)
s=s.replace(A1, BLOCK).replace(A2, N2)
io.open(P,'w',encoding='utf-8').write(s)
print('ok, +%d Zeichen' % (len(BLOCK)-len(A1)+len(N2)-len(A2)))
