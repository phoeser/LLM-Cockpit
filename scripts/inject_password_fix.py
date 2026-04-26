"""Injiziert nach StatiCrypt-Encryption ein <script>-Tag in index.html.
Leert das Passwort-Feld + setzt Remember-Me-Checkbox auf checked,
ABER nur wenn das Feld nicht im Focus ist (User tippt gerade nicht)."""
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
    'if(p && document.activeElement!==p){'
    'p.value="";p.setAttribute("autocomplete","new-password");}'
    'var c=document.getElementById("staticrypt-remember");'
    'if(c && !c.checked){c.checked=true;}'
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
htm