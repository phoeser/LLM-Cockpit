#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Performance-KPIs fuer die gesammelten LinkedIn-Posts (18.08.2026, Pauls Auftrag
"bei den LinkedIn Posts braeuchten wir noch Performance KPIs").

Was gemessen wird — und woher
-----------------------------
LinkedIn zeigt fuer OEFFENTLICHE Posts auch ohne Login eine Reaktions- und
Kommentarzahl auf der Post-Seite an. Genau diese zwei Zahlen holt dieses
Skript — mehr gibt es von aussen ehrlich nicht:

  reactions   Anzahl Reaktionen (Like, Celebrate, ... zusammen)
  comments    Anzahl Kommentare

Machbarkeit am 18.08.2026 an 8 Stichproben-Posts verifiziert: 8/8 lieferten
die Reaktionszahl (kein Authwall). Das kann sich aendern — LinkedIn drosselt
und mauert nach Laune. Deshalb: jede Antwort mit Authwall/Fehler wird GEZAEHLT
und ausgewiesen, nie stillschweigend als 0 gewertet.

Was es NICHT gibt (und warum es nicht hier steht): Impressionen, Reichweite,
Klicks. Die kennt nur der Seiten-Admin. Fuer ERGOs EIGENE Posts koennte Paul
sie als Page-Analytics-Export nachliefern — dafuer gaebe es einen eigenen
Importer, nicht diesen Scraper.

Arbeitsweise
------------
- Laeuft im Nightly direkt nach update_linkedin.py, drosselt sich wie dieser
  selbst auf einen Lauf je Woche (eigener STATE), FORCE_LINKEDIN_KPIS=1
  erzwingt.
- Geprueft werden Posts, deren Fund-Tag hoechstens NACHLAUF_TAGE zurueckliegt:
  Engagement waechst in den ersten Wochen — jede Woche ein Messpunkt ergibt
  je Post eine kleine Wachstumskurve statt eines zufaelligen Schnappschusses.
- Zwischen zwei Abrufen liegen SLEEP_S Sekunden (hoeflich bleiben; ausserdem
  faellt eine Drossel-Sperre sonst auf alle folgenden Abrufe).
- Ausgabe data/linkedin_kpis.jsonl, EIN Messpunkt pro Zeile:
    {"url", "brand", "checked", "reactions", "comments", "status",
     "text", "autor_name"}
  status: "ok" | "authwall" | "fehler". Bei authwall/fehler sind die
  Zahlfelder null — kein Wert ist keine Null. "text" ist der oeffentliche
  Beitragstext (bis 600 Zeichen) aus derselben Seite; er speist im Dashboard
  die Einordnung nach Post-Typ und das Event-Log.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

POSTS = Path("data/linkedin_posts.jsonl")
OUT = Path("data/linkedin_kpis.jsonl")
STATE = Path("data/linkedin_kpis_state.json")

NACHLAUF_TAGE = 28
SLEEP_S = 2.0
MAX_ABRUFE = 120   # Obergrenze je Lauf — haelt den Nightly-Step unter ~5 Min.

UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
      "Accept-Language": "de-DE,de;q=0.9"}


def kpis_aus_html(html):
    """(reactions, comments) aus der oeffentlichen Post-Seite. None = nicht da."""
    rx = re.search(r'data-num-reactions="(\d+)"', html)
    cm = re.search(r'data-num-comments="(\d+)"', html)
    if not cm:
        # Fallback: sichtbarer Kommentar-Zaehler. Bewusst NUR der erste Treffer
        # nahe am Reaktions-Block; die Seite fuehrt auch Zaehler je Kommentar.
        cm = re.search(r'comments?-count[^>]*>\s*([\d.]+)', html)
    r = int(rx.group(1)) if rx else None
    c = int(cm.group(1).replace(".", "")) if cm else None
    return r, c


def _entschaerfen(s):
    """HTML-Schnipsel -> lesbarer Text."""
    s = re.sub(r"<[^>]+>", " ", s or "")
    for a, b in (("&amp;", "&"), ("&quot;", '"'), ("&#39;", "'"), ("&lt;", "<"),
                 ("&gt;", ">"), ("&nbsp;", " ")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def inhalt_aus_html(html):
    """(post_text, autor_name) aus derselben Seite, die wir ohnehin laden.

    20.08.2026, Pauls Auftrag "Event-Log mit wann, von wem, Thema": Googles
    Snippets liefern bei rund der Haelfte der Posts nur Navigationstext
    ("Menue schliessen. ERGO Versicherung AG ..."). Der echte Beitragstext
    steht dagegen in der oeffentlichen Post-Seite - und die rufen wir fuer die
    Reaktionszahlen sowieso ab. Kein zusaetzlicher Request, aber der
    Unterschied zwischen "Sonstiges" und einer echten Einordnung.

    Nichts davon wird erraten: Findet sich kein Text, bleibt das Feld leer."""
    txt = ""
    m = re.search(r'<p class="attributed-text-segment-list__content[^"]*"[^>]*>(.*?)</p>',
                  html, re.S)
    if m:
        txt = _entschaerfen(m.group(1))[:600]
    autor = ""
    a = re.search(r'data-tracking-control-name="public_post_feed-actor-name"[^>]*>\s*([^<]{2,80})', html)
    if a:
        autor = _entschaerfen(a.group(1))[:80]
    return txt, autor


def main():
    if not POSTS.exists():
        print("[LinkedIn-KPIs] Keine Post-Sammlung vorhanden — nichts zu tun.")
        return 0

    force = os.environ.get("FORCE_LINKEDIN_KPIS") == "1"
    heute = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    st = {}
    if STATE.exists():
        try:
            st = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            st = {}
    if st.get("letzter_lauf") and not force:
        try:
            if (datetime.fromisoformat(heute) -
                    datetime.fromisoformat(st["letzter_lauf"])).days < 6:
                print("[LinkedIn-KPIs] Letzter Lauf %s — uebersprungen "
                      "(FORCE_LINKEDIN_KPIS=1 erzwingt)." % st["letzter_lauf"])
                return 0
        except Exception:
            pass

    grenze = (datetime.now(timezone.utc) - timedelta(days=NACHLAUF_TAGE)).strftime("%Y-%m-%d")
    posts = []
    for line in POSTS.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            p = json.loads(line)
        except Exception:
            continue
        if p.get("url") and (p.get("first_seen") or "") >= grenze:
            posts.append(p)
    # Aelteste zuerst: falls die MAX_ABRUFE-Grenze greift, fehlen eher die
    # juengsten (die kommen naechste Woche wieder dran) als die, deren
    # Nachlauf-Fenster gerade ablaeuft.
    posts.sort(key=lambda p: p.get("first_seen") or "")
    if len(posts) > MAX_ABRUFE:
        print("[LinkedIn-KPIs] %d Kandidaten, gekappt auf %d (aelteste zuerst)."
              % (len(posts), MAX_ABRUFE))
        posts = posts[:MAX_ABRUFE]

    n_ok = n_wall = n_err = 0
    zeilen = []
    for p in posts:
        status, r, c = "fehler", None, None
        text, autor_name = "", ""
        # Host-Pruefung (Opus-Review #16): nur https auf *.linkedin.com abrufen.
        try:
            _pu = urllib.parse.urlparse(p["url"])
            if _pu.scheme != "https" or not (_pu.netloc == "linkedin.com"
                                             or _pu.netloc.endswith(".linkedin.com")):
                raise ValueError("kein LinkedIn-Host")
        except Exception:
            zeilen.append({"url": p["url"], "brand": p.get("brand"),
                           "checked": heute, "reactions": None, "comments": None,
                           "status": "fehler"})
            n_err += 1
            continue
        try:
            req = urllib.request.Request(p["url"], headers=UA)
            with urllib.request.urlopen(req, timeout=25) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            if "authwall" in html[:3000] or "auth_wall" in html[:3000]:
                status = "authwall"
            else:
                r, c = kpis_aus_html(html)
                text, autor_name = inhalt_aus_html(html)
                status = "ok" if r is not None else "fehler"
        except Exception:
            status = "fehler"
        if status == "ok":
            n_ok += 1
        elif status == "authwall":
            n_wall += 1
        else:
            n_err += 1
        zeilen.append({"url": p["url"], "brand": p.get("brand"),
                       "checked": heute, "reactions": r, "comments": c,
                       "status": status, "text": text, "autor_name": autor_name})
        time.sleep(SLEEP_S)

    if zeilen:
        with open(OUT, "a", encoding="utf-8") as f:
            for z in zeilen:
                f.write(json.dumps(z, ensure_ascii=False) + "\n")
    # Lauf zaehlt als erfolgt, wenn er ueberwiegend durchkam. Sonst darf der
    # naechste Nightly EINMAL nachfassen — nach dem zweiten Fehlversuch in Folge
    # wird der Takt trotzdem fortgeschrieben (Opus-Review #10: sonst liefe der
    # Step bei dauerhaftem Authwall auf Runner-IPs JEDE Nacht mit 120 Abrufen
    # und vier Minuten Sleep, fuer immer, ohne je einen Wert zu liefern).
    STATE.parent.mkdir(parents=True, exist_ok=True)
    if zeilen and (n_ok >= len(zeilen) * 0.5):
        STATE.write_text(json.dumps({"letzter_lauf": heute, "ok": n_ok,
                                     "authwall": n_wall, "fehler": n_err,
                                     "fehlversuche_in_folge": 0}),
                         encoding="utf-8")
    elif zeilen:
        _f = int(st.get("fehlversuche_in_folge") or 0) + 1
        if _f >= 2:
            STATE.write_text(json.dumps({"letzter_lauf": heute, "ok": n_ok,
                                         "authwall": n_wall, "fehler": n_err,
                                         "fehlversuche_in_folge": 0,
                                         "grund": ("Takt nach %d Fehlversuchen in Folge "
                                                   "trotzdem fortgeschrieben — Abrufe von "
                                                   "dieser Umgebung scheitern derzeit "
                                                   "(Authwall/Netz)." % _f)},
                             ensure_ascii=False), encoding="utf-8")
            print("[LinkedIn-KPIs] %d. Fehlversuch in Folge — Takt fortgeschrieben, "
                  "naechster Versuch in einer Woche." % _f)
        else:
            st["fehlversuche_in_folge"] = _f
            STATE.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
            print("[LinkedIn-KPIs] WARNUNG: nur %d/%d ok — Fehlversuch %d, "
                  "naechster Nightly fasst einmal nach." % (n_ok, len(zeilen), _f))
    print("[LinkedIn-KPIs] fertig: %d ok, %d Authwall, %d Fehler (von %d geprueft)"
          % (n_ok, n_wall, n_err, len(zeilen)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
