"""Patch index.html: leere Passwort-Feld + Remember-Me checked."""
import sys
from pathlib import Path
p = Path("index.html")
if not p.exists(): print("FEHLER: kein index.html"); sys.exit(1)
h = p.read_text(encoding="utf-8")
inj = '<script>function _ergoFix(){var p=document.getElementById("staticrypt-password");if(p && document.activeElement!==p){p.value="";p.setAttribute("autocomplete","new-password");}var c=document.getElementById("staticrypt-remember");if(c && !c.checked){c.checked=true;}}setTimeout(_ergoFix,150);setTimeout(_ergoFix,500);setTimeout(_ergoFix,1200);</script>'
i = h.rfind('</body>')
if i == -1: print("FEHLER: kein </body>"); sys.exit(1)
h = h[:i] + inj + h[i:]
p.write_text(h, encoding="utf-8")
print(f"OK Patch eingefuegt, {len(h)} chars")
