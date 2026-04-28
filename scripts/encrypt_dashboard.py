"""
Verschluesselt dashboard_template.html mit AES-256-GCM und erzeugt eine
ERGO-branded Login-Seite als index.html.

Ersetzt StatiCrypt + inject_password_fix.py komplett.

Verwendung:
    python scripts/encrypt_dashboard.py <passwort>
    # oder via Umgebungsvariable:
    DASHBOARD_PASSWORD=LLM2026 python scripts/encrypt_dashboard.py
"""
import sys
import os
import json
import base64
import hashlib
import secrets
from pathlib import Path


def encrypt_aes_gcm(plaintext_bytes: bytes, password: str) -> dict:
    """Verschluesselt mit AES-256-GCM, gibt salt+iv+ciphertext+tag zurueck."""
    salt = secrets.token_bytes(16)
    iv = secrets.token_bytes(12)

    # PBKDF2 Key-Ableitung — gleicher Algorithmus wie Web Crypto API
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000, dklen=32)

    # AES-256-GCM via PyCryptodome ODER openssl-Fallback
    try:
        from Crypto.Cipher import AES
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext_bytes)
    except ImportError:
        # Fallback: cryptography-Paket
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            aesgcm = AESGCM(key)
            ct_with_tag = aesgcm.encrypt(iv, plaintext_bytes, None)
            # cryptography haengt den Tag an den Ciphertext an (letzte 16 Bytes)
            ciphertext = ct_with_tag[:-16]
            tag = ct_with_tag[-16:]
        except ImportError:
            print("FEHLER: Weder pycryptodome noch cryptography installiert.")
            print("  pip install pycryptodome  ODER  pip install cryptography")
            sys.exit(1)

    return {
        "salt": base64.b64encode(salt).decode(),
        "iv": base64.b64encode(iv).decode(),
        "ct": base64.b64encode(ciphertext).decode(),
        "tag": base64.b64encode(tag).decode(),
    }


def build_login_page(encrypted_data: dict) -> str:
    """Baut die komplette Login-Seite mit ERGO-Branding."""

    enc_json = json.dumps(encrypted_data)

    return f'''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ERGO LLM-Cockpit</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ min-height: 100vh; }}
body {{
  background: #1a1a2e;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
}}
body::before {{
  content: ""; position: fixed; top: 0; left: 0; right: 0; height: 45vh;
  background: linear-gradient(135deg, #DC0028 0%, #a30020 100%); z-index: 0;
}}
body::after {{
  content: ""; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: radial-gradient(ellipse at 50% 0%, rgba(220,0,40,0.15) 0%, transparent 70%);
  z-index: 0; pointer-events: none;
}}
.login-card {{
  position: relative; z-index: 1; max-width: 420px; width: 100%;
  padding: 48px 40px 40px; background: #fff; border-radius: 20px;
  box-shadow: 0 25px 80px rgba(0,0,0,0.25), 0 8px 24px rgba(0,0,0,0.12);
}}
.brand-header {{ text-align: center; margin-bottom: 28px; }}
.brand-logo {{
  display: inline-block; background: #DC0028; color: #fff;
  font-weight: 900; font-size: 26px; padding: 10px 24px;
  border-radius: 8px; letter-spacing: 0.02em;
  box-shadow: 0 4px 12px rgba(220,0,40,0.25);
}}
.brand-tagline {{
  color: #9ca3af; font-size: 11px; margin-top: 10px;
  text-transform: uppercase; letter-spacing: 0.2em; font-weight: 600;
}}
h1 {{ color: #1a1a2e; font-size: 18px; font-weight: 600; text-align: center; margin-bottom: 4px; }}
.subtitle {{ color: #6b7280; font-size: 13px; text-align: center; margin-bottom: 24px; }}
hr {{ border: none; border-top: 1px solid #f0f0f0; margin: 20px 0; }}
input[type=password] {{
  width: 100%; padding: 14px 16px; font-size: 15px;
  border: 1.5px solid #e5e7eb; border-radius: 12px;
  background: #fafafa; color: #1a1a2e; transition: all .2s ease;
}}
input[type=password]:focus {{
  border-color: #DC0028; outline: none; background: #fff;
  box-shadow: 0 0 0 3px rgba(220,0,40,0.08);
}}
input[type=password]::placeholder {{ color: #9ca3af; }}
button {{
  width: 100%; padding: 14px 24px; margin-top: 12px;
  background: linear-gradient(135deg, #DC0028, #b00020); color: #fff;
  border: 0; border-radius: 12px; font-size: 15px; font-weight: 700;
  cursor: pointer; transition: all .2s ease;
  letter-spacing: 0.04em; text-transform: uppercase;
  box-shadow: 0 4px 14px rgba(220,0,40,0.3);
}}
button:hover {{
  background: linear-gradient(135deg, #c50024, #9a001a);
  transform: translateY(-1px); box-shadow: 0 6px 20px rgba(220,0,40,0.4);
}}
button:active {{ transform: translateY(0); }}
button:disabled {{ opacity: 0.6; cursor: wait; }}
.remember-row {{
  display: flex; align-items: center; gap: 8px; margin-top: 14px;
}}
.remember-row input[type=checkbox] {{ accent-color: #DC0028; }}
.remember-row label {{ color: #6b7280; font-size: 13px; cursor: pointer; }}
.error-msg {{
  color: #DC0028; font-size: 13px; text-align: center;
  margin-top: 12px; display: none;
}}
.spinner {{
  display: inline-block; width: 16px; height: 16px;
  border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff;
  border-radius: 50%; animation: spin .6s linear infinite;
  vertical-align: middle; margin-right: 8px;
}}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
@media (max-width: 480px) {{
  .login-card {{ padding: 32px 24px 28px; border-radius: 16px; }}
  .brand-logo {{ font-size: 22px; padding: 8px 18px; }}
}}
</style>
</head>
<body>
<div class="login-card" id="loginCard">
  <div class="brand-header">
    <div class="brand-logo">ERGO</div>
    <div class="brand-tagline">LLM-Sichtbarkeits-Cockpit</div>
  </div>
  <h1>ERGO LLM-Cockpit</h1>
  <p class="subtitle">Bitte Passwort eingeben.</p>
  <hr>
  <form id="loginForm" autocomplete="off">
    <input type="password" id="pw" placeholder="Passwort eingeben"
           autocomplete="new-password" autofocus>
    <div class="remember-row">
      <input type="checkbox" id="remember" checked>
      <label for="remember">Angemeldet bleiben (30 Tage)</label>
    </div>
    <button type="submit" id="btn">Anmelden</button>
  </form>
  <div class="error-msg" id="errMsg">Falsches Passwort.</div>
</div>

<script>
(function() {{
  "use strict";

  var ENC = {enc_json};

  // --- Crypto-Helfer (Web Crypto API) ---
  function b64ToBytes(b64) {{
    return Uint8Array.from(atob(b64), function(c) {{ return c.charCodeAt(0); }});
  }}

  async function deriveKey(password, saltB64) {{
    var enc = new TextEncoder();
    var keyMaterial = await crypto.subtle.importKey(
      "raw", enc.encode(password), "PBKDF2", false, ["deriveKey"]
    );
    return crypto.subtle.deriveKey(
      {{ name: "PBKDF2", salt: b64ToBytes(saltB64), iterations: 100000, hash: "SHA-256" }},
      keyMaterial,
      {{ name: "AES-GCM", length: 256 }},
      false,
      ["decrypt"]
    );
  }}

  async function decrypt(password) {{
    try {{
      var key = await deriveKey(password, ENC.salt);
      var iv = b64ToBytes(ENC.iv);
      var ct = b64ToBytes(ENC.ct);
      var tag = b64ToBytes(ENC.tag);

      // Web Crypto erwartet ciphertext+tag zusammen
      var combined = new Uint8Array(ct.length + tag.length);
      combined.set(ct);
      combined.set(tag, ct.length);

      var plainBuf = await crypto.subtle.decrypt(
        {{ name: "AES-GCM", iv: iv }}, key, combined
      );
      return new TextDecoder().decode(plainBuf);
    }} catch (e) {{
      return null;
    }}
  }}

  // --- Remember-Me ---
  var STORAGE_KEY = "ergo_cockpit_pw";
  var STORAGE_EXP = "ergo_cockpit_exp";

  function savePw(pw) {{
    try {{
      var exp = Date.now() + 30 * 24 * 60 * 60 * 1000;
      localStorage.setItem(STORAGE_KEY, btoa(pw));
      localStorage.setItem(STORAGE_EXP, exp.toString());
    }} catch(e) {{}}
  }}

  function loadPw() {{
    try {{
      var exp = parseInt(localStorage.getItem(STORAGE_EXP) || "0");
      if (Date.now() > exp) {{ clearPw(); return null; }}
      var b = localStorage.getItem(STORAGE_KEY);
      return b ? atob(b) : null;
    }} catch(e) {{ return null; }}
  }}

  function clearPw() {{
    try {{
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(STORAGE_EXP);
    }} catch(e) {{}}
  }}

  // --- Seite ersetzen ---
  function replaceContent(html) {{
    document.open();
    document.write(html);
    document.close();
  }}

  // --- Login-Handler ---
  async function handleLogin(pw, fromRemember) {{
    var btn = document.getElementById("btn");
    var errMsg = document.getElementById("errMsg");
    if (btn) {{
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span>Entschluessle...';
    }}
    if (errMsg) errMsg.style.display = "none";

    var result = await decrypt(pw);

    if (result) {{
      // Passwort merken?
      var cb = document.getElementById("remember");
      if (cb && cb.checked) {{ savePw(pw); }}
      replaceContent(result);
    }} else {{
      if (fromRemember) {{ clearPw(); }}
      if (btn) {{
        btn.disabled = false;
        btn.textContent = "ANMELDEN";
      }}
      if (errMsg) errMsg.style.display = "block";
      var pwField = document.getElementById("pw");
      if (pwField) {{ pwField.value = ""; pwField.focus(); }}
    }}
  }}

  // --- Form ---
  var form = document.getElementById("loginForm");
  if (form) {{
    form.addEventListener("submit", function(e) {{
      e.preventDefault();
      var pw = document.getElementById("pw").value;
      if (pw) handleLogin(pw, false);
    }});
  }}

  // --- Auto-Login bei gespeichertem Passwort ---
  var saved = loadPw();
  if (saved) {{
    handleLogin(saved, true);
  }}
}})();
</script>
</body>
</html>'''


def main():
    # Passwort aus Argument oder Umgebungsvariable
    password = None
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        password = os.environ.get("DASHBOARD_PASSWORD", "").strip()

    if not password:
        print("FEHLER: Kein Passwort angegeben.")
        print("  Verwendung: python encrypt_dashboard.py <passwort>")
        print("  Oder:       DASHBOARD_PASSWORD=xxx python encrypt_dashboard.py")
        sys.exit(1)

    # Dashboard-Template lesen
    template_path = Path("dashboard_template.html")
    if not template_path.exists():
        print("FEHLER: dashboard_template.html nicht gefunden")
        sys.exit(1)

    print(f"Lese {template_path} ...")
    html_content = template_path.read_text(encoding="utf-8")
    print(f"  {len(html_content)} Zeichen gelesen")

    # Verschluesseln
    print(f"Verschluessele mit AES-256-GCM (PBKDF2, 100k Iterationen) ...")
    encrypted = encrypt_aes_gcm(html_content.encode("utf-8"), password)
    print(f"  Salt: {encrypted['salt'][:16]}...")
    print(f"  Ciphertext: {len(encrypted['ct'])} Base64-Zeichen")

    # Login-Seite erzeugen
    login_html = build_login_page(encrypted)

    # Schreiben
    out_path = Path("index.html")
    out_path.write_text(login_html, encoding="utf-8")
    print(f"index.html geschrieben: {len(login_html)} Zeichen")
    print("Fertig!")


if __name__ == "__main__":
    main()
