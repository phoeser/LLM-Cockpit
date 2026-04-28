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
/* ERGO Brand Reset — ueberschreibt StatiCrypt-Defaults */
html, body { margin: 0 !important; padding: 0 !important; min-height: 100vh !important; }
body.staticrypt-body { background: #1a1a2e !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important; }

/* StatiCrypt-Content: das Gruen entfernen */
.staticrypt-content { background: transparent !important; display: flex !important; align-items: center !important; justify-content: center !important; min-height: 100vh !important; padding: 20px !important; box-sizing: border-box !important; }

/* Hintergrund-Effekt */
body.staticrypt-body::before { content: ""; position: fixed; top: 0; left: 0; right: 0; height: 45vh; background: linear-gradient(135deg, #DC0028 0%, #a30020 100%); z-index: 0; }
body.staticrypt-body::after { content: ""; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: radial-gradient(ellipse at 50% 0%, rgba(220,0,40,0.15) 0%, transparent 70%); z-index: 0; pointer-events: none; }

/* Login-Card */
.staticrypt-page { position: relative !important; z-index: 1 !important; max-width: 420px !important; width: 100% !important; margin: 0 auto !important; padding: 48px 40px 40px !important; background: #fff !important; border-radius: 20px !important; box-shadow: 0 25px 80px rgba(0,0,0,0.25), 0 8px 24px rgba(0,0,0,0.12) !important; }

/* Titel */
.staticrypt-page h1, .staticrypt-page h2 { color: #1a1a2e !important; font-size: 18px !important; font-weight: 600 !important; margin: 0 0 4px !important; text-align: center; letter-spacing: -0.01em; }
.staticrypt-page p { color: #6b7280 !important; font-size: 13px !important; text-align: center; margin: 0 0 24px !important; }
.staticrypt-page hr { border: none !important; border-top: 1px solid #f0f0f0 !important; margin: 20px 0 !important; }

/* Input */
.staticrypt-page input[type=password],
.staticrypt-page input[type=text] { width: 100% !important; padding: 14px 16px !important; font-size: 15px !important; border: 1.5px solid #e5e7eb !important; border-radius: 12px !important; box-sizing: border-box !important; transition: all .2s ease !important; margin: 6px 0 !important; background: #fafafa !important; color: #1a1a2e !important; }
.staticrypt-page input[type=password]:focus,
.staticrypt-page input[type=text]:focus { border-color: #DC0028 !important; outline: none !important; background: #fff !important; box-shadow: 0 0 0 3px rgba(220,0,40,0.08) !important; }
.staticrypt-page input[type=password]::placeholder { color: #9ca3af !important; }

/* Button */
.staticrypt-page button,
.staticrypt-page input[type=submit] { width: 100% !important; padding: 14px 24px !important; background: linear-gradient(135deg, #DC0028, #b00020) !important; color: #fff !important; border: 0 !important; border-radius: 12px !important; font-size: 15px !important; font-weight: 700 !important; cursor: pointer !important; transition: all .2s ease !important; margin-top: 12px !important; letter-spacing: 0.04em !important; text-transform: uppercase !important; box-shadow: 0 4px 14px rgba(220,0,40,0.3) !important; }
.staticrypt-page button:hover,
.staticrypt-page input[type=submit]:hover { background: linear-gradient(135deg, #c50024, #9a001a) !important; transform: translateY(-1px) !important; box-shadow: 0 6px 20px rgba(220,0,40,0.4) !important; }
.staticrypt-page button:active,
.staticrypt-page input[type=submit]:active { transform: translateY(0) !important; }

/* Label + Checkbox */
.staticrypt-page label { color: #6b7280 !important; font-size: 13px !important; }
.staticrypt-page input[type=checkbox] { accent-color: #DC0028 !important; }

/* ERGO Brand Header */
.ergo-brand-header { text-align: center; margin-bottom: 28px; }
.ergo-brand-logo { display: inline-block; background: #DC0028; color: #fff; font-weight: 900; font-size: 26px; padding: 10px 24px; border-radius: 8px; letter-spacing: 0.02em; box-shadow: 0 4px 12px rgba(220,0,40,0.25); }
.ergo-brand-tagline { color: #9ca3af; font-size: 11px; margin-top: 10px; text-transform: uppercase; letter-spacing: 0.2em; font-weight: 600; }

/* Passwort-Container Hintergrund entfernen */
.staticrypt-password-container { background: transparent !important; }

/* Footer-Link */
.ergo-footer { text-align: center; margin-top: 20px; }
.ergo-footer a { color: #9ca3af; font-size: 11px; text-decoration: none; }
.ergo-footer a:hover { color: #DC0028; }

/* Responsive */
@media (max-width: 480px) {
  .staticrypt-page { padding: 32px 24px 28px !important; border-radius: 16px !important; }
  .ergo-brand-logo { font-size: 22px; padding: 8px 18px; }
}
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
if(p && document.activeElement!==p){p.value="";p.setAttribute("autocomplete","new-password");p.setAttribute("placeholder","Passwort eingeben");}
var c=document.getElementById("staticrypt-remember");
if(c && !c.checked){c.checked=true;}
var page=document.querySelector(".staticrypt-page");
if(page && !document.getElementById("ergoBrandHeader")){
  var hdr=document.createElement("div");
  hdr.id="ergoBrandHeader";
  hdr.className="ergo-brand-header";
  hdr.innerHTML='<div class="ergo-brand-logo">ERGO</div><div class="ergo-brand-tagline">LLM-Sichtbarkeits-Cockpit</div>';
  page.insertBefore(hdr, page.firstChild);
}
var btn=page?page.querySelector(".staticrypt-decrypt-button"):null;
if(btn && btn.value==="DECRYPT"){btn.value="ANMELDEN";}
if(btn && btn.textContent==="DECRYPT"){btn.textContent="ANMELDEN";}
var form=page?page.querySelector(".staticrypt-form"):null;
if(form){form.style.background="transparent";}
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
