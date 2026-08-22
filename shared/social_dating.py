#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Erscheinungsdatum von Social-Posts aus der URL ableiten (21.08.2026).

Das Problem, das dieses Modul loest
-----------------------------------
Von 184 gesammelten LinkedIn-Posts trug genau EINER ein Erscheinungsdatum aus
der Google-Trefferliste, bei Instagram waren es 5 von 274. Alle anderen hingen
am Fund-Tag. Bei woechentlichem Messtakt heisst das: Der Versatz zwischen Post
und zugeordnetem Messintervall ist so gross wie das Intervall selbst - die
Frage "hat DIESER Post gewirkt?" liess sich damit nicht sauber stellen.

Die Loesung braucht keinen einzigen zusaetzlichen Abruf: Beide Plattformen
tragen den Erstellungszeitpunkt in der Beitrags-URL.

LinkedIn
--------
  .../feed/update/urn:li:activity:7362514...  bzw. .../posts/<slug>_...-activity-7362514...
Die Activity-ID ist eine Snowflake-artige Zahl; ihre oberen Bits sind die
Unix-Zeit in Millisekunden. Verschiebung: 22 Bit.

Instagram
---------
  instagram.com/p/DbQzy-jjFam/
Der Shortcode ist die Media-ID in Base64 (Alphabet A-Za-z0-9-_). Die oberen
Bits sind die Zeit seit Instagrams eigener Epoche (24.08.2011). Verschiebung:
23 Bit - nicht 22 wie bei LinkedIn; genau daran scheiterte der erste Versuch.

Nachgeprueft, nicht angenommen (21.08.2026)
-------------------------------------------
Beide Deutungen wurden gegen die Faelle geprueft, in denen Google ein Datum
mitgeliefert hat - die einzige unabhaengige Quelle, die wir haben:

  LinkedIn   1 von 1 Faellen exakt getroffen
  Instagram  5 von 5 Faellen exakt getroffen

Dazu drei Plausibilitaets-Pruefungen ueber ALLE 458 Posts:
  - kein einziges Datum liegt in der Zukunft
  - kein einziges Datum liegt nach seinem eigenen Fund-Tag
  - die Verteilung ist keine Zufallsverteilung: LinkedIn 85 % der Posts
    zwischen 07 und 17 Uhr MESZ (Zufall waere 46 %) und nur 11 % am
    Wochenende (Zufall 29 %); Instagram 77 % Buerozeit.

Eine falsche Deutung wuerde all das nicht gleichzeitig erfuellen.

Grenzen, die bleiben
--------------------
- Es ist der ERSTELLUNGS-Zeitpunkt des Beitrags-Objekts. Bei einem geteilten
  oder bearbeiteten Post kann das vom sichtbaren Datum abweichen.
- Aendert eine Plattform ihr ID-Schema, liefert dieses Modul still falsche
  Daten. Deshalb pruefen die Aufrufer das Ergebnis gegen den Fund-Tag: ein
  Datum in der Zukunft oder nach dem Fund wird verworfen, nicht verwendet.
"""
import re
from datetime import datetime, timezone

# Instagram rechnet ab dem 24.08.2011 (Millisekunden).
IG_EPOCHE_MS = 1314220021721
IG_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

_LI_ID = re.compile(r"(?:activity|ugcPost)[-:](\d{15,25})")
_IG_CODE = re.compile(r"/(?:p|reel)/([A-Za-z0-9_-]{5,30})")


def _sicher(ms):
    """Millisekunden -> datetime, oder None wenn ausserhalb des Sinnvollen."""
    try:
        dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    except (OSError, ValueError, OverflowError):
        return None
    # Social-Posts vor 2005 oder in der Zukunft gibt es nicht.
    if not (2005 <= dt.year <= datetime.now(timezone.utc).year + 1):
        return None
    return dt


def linkedin_zeit(url):
    m = _LI_ID.search(url or "")
    if not m:
        return None
    return _sicher((int(m.group(1)) >> 22))


def instagram_zeit(url):
    m = _IG_CODE.search(url or "")
    if not m:
        return None
    n = 0
    for zeichen in m.group(1):
        i = IG_ALPHABET.find(zeichen)
        if i < 0:
            return None
        n = n * 64 + i
    return _sicher((n >> 23) + IG_EPOCHE_MS)


def datum_aus_url(url, fund_tag=None):
    """'YYYY-MM-DD' oder None. Erkennt die Plattform selbst.

    fund_tag (optional, 'YYYY-MM-DD'): Sicherung gegen ein geaendertes
    ID-Schema. Ein abgeleitetes Datum NACH dem Fund-Tag kann nicht stimmen -
    dann lieber kein Datum als ein falsches."""
    u = url or ""
    dt = linkedin_zeit(u) if "linkedin.com" in u else (
        instagram_zeit(u) if "instagram.com" in u else None)
    if dt is None:
        return None
    tag = dt.strftime("%Y-%m-%d")
    heute = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if tag > heute:
        return None
    if fund_tag and tag > fund_tag:
        return None
    return tag
