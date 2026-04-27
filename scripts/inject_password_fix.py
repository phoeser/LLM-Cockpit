"""Injiziert nach StatiCrypt-Encryption: Passwort-Fix + ERGO-Branding."""
import sys
from pathlib import Path

html_path = Path("index.html")
if not html_path.exists():
    print("FEHLER: index.html nicht gefunden")
    sys.exit(1)

html = html_path.read_text(encoding="utf-8")

ergo_brand_css = """
<style>
body { background: linear-gradient(135deg, #DC0028 0%, #8b0017 100%) !important; min-height: 100vh; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important; margin: 0; }
.staticrypt-page { max-width: 480px !important; margin: 80px auto !important; padding: 40px !important; background: #fff !important; border-radius: 16px !important; box-shadow: 0 20px 60px rgba(0,0,0,0.3) !important; }
.staticrypt-page h1, .staticrypt-page h2 { color: #DC0028 !important; font-size: 24px !important; font-weight: 700 !important; margin-top: 0 !important; text-align: center; }
.staticrypt-page p { color: #555 !important; font-size: 14px; text-align: center; }
.staticrypt-page input[type=password], .staticrypt-page input[type=text] { width: 100% !important; padding: 14px 18px !important; font-size: 15px !important; border: 2px solid #e5e7eb !important; border-radius: 10px !important; box-sizing: border-box; transition: border-color .15s; margin: 8px 0 !important; }
.staticrypt-page input[type=password]:focus, .staticrypt-page input[type=text]:focus { border-color: #DC0028 !important; outline: none !important; }
.staticrypt-page button, .staticrypt-page input[type=submit] { width: 100% !important; padding: 14px 24px !important; background: #DC0028 !important; color: #fff !important; border: 0 !important; border-radius: 10px !important; font-size: 16px !important; font-weight: 700 !important; cursor: pointer; transition: .15s; margin-top: 8px !important; }
.staticrypt-page button:hover, .staticrypt-page input[type=submit]:hover { background: #b00020 !important; transform: translateY(-1px); }
.staticrypt-page label { color: #666 !important; font-size: 13px !important; }
.ergo-brand-header { text-align: center; margin-bottom: 24px; }
.ergo-brand-logo { display: inline-block; background: #DC0028; color: #fff; font-weight: 900; font-size: 28px; padding: 8px 20px; border-radius: 6px; letter-spacing: -0.02em; }
.ergo-brand-tagline { color: #888; font-size: 11px; margin-top: 8px; text-transform: uppercase; letter-spacing: 0.15em; font-weight: 600; }
</style>
"""

# CSS in <head> einfuegen
head_close = html.find("</head>")
if head_close > 0:
    html = html[:head_close] + ergo_brand_css + html[head_close:]
    print("ERGO-Branding-CSS eingefuegt")
else:
    print("WARN: kein </head> gefunden")

# JS-Inject: Passwort leeren + Remember setzen + ERGO-Header DOM einfuegen
inject = """<script>function _ergoFix(){
var p=document.getElementById("staticrypt-password");
if(p && document.activeElement!==p){p.value="";p.setAttribute("autocomplete","new-password");}
var c=document.getElementById("staticrypt-remember");
if(c && !c.checked){c.checked=true;}
var page=document.querySelector(".staticrypt-page");
if(page && !document.getElementById("ergoBrandHeader")){
  var hdr=document.createElement("div");
  hdr.id="ergoBrandHeader";
  hdr.className="ergo-brand-header";
  hdr.innerHTML='<div class="ergo-brand-logo">ERGO</div><div class="ergo-brand-tagline">LLM-Cockpit</div>';
  page.insertBefore(hdr, page.firstChild);
}
}
setTimeout(_ergoFix,150);
setTimeout(_ergoFix,500);
setTimeout(_ergoFix,1200);
</script>"""

idx = html.rfind("</body>")
if idx == -1:
    print("FEHLER: kein </body>")
    sys.exit(1)
html = html[:idx] + inject + html[idx:]
html_path.write_text(html, encoding="utf-8")
print("Patch+Branding eingefuegt, neue Groesse:", len(html), "chars")
