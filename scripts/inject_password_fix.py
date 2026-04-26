"""Injiziert nach StatiCrypt-Encryption ein <script>-Tag in index.html,
das das Passwort-Feld zur Laufzeit leert und Remember-Me-Checkbox checked."""
import sys
from pathlib import Path

html_path = Path("index.html")
if not html_path.exists():
    print("FEHLER: index.html nicht gefunden")
    sys.exit(1)

html = html_path.read_text(encoding="utf-8")

inject = (
    '<script>function _ergoFix(){'
    'var p=document.getElementById("staticrypt-password");'
    'if(p){p.value="";p.setAttribute("autocomplete","new-password");}'
    'var c=document.getElementById("staticrypt-remember");'
    'if(c){c.checked=true;}'
    '}'
    'setTimeout(_ergoFix,150);'
    'setTimeout(_ergoFix,500);'
    'setTimeout(_ergoFix,1200);'
    '</script>'
)

idx = html.rfind('</body>')
if idx == -1:
    print("FEHLER: kein </body> gefunden")
    sys.exit(1)

html = html[:idx] + inject + html[idx:]
html_path.write_text(html, encoding="utf-8")
print(f"Passwort-Patch eingefuegt, neue Groesse: {len(html)} chars")
