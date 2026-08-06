#!/usr/bin/env python3
"""
Hält die aufgezeichneten Hochlagen gegen bestätigte Tornado-Meldungen.

Das ist der Punkt, an dem sich entscheidet, ob der TPI etwas taugt. Bis dahin
ist er eine begründete Vermutung — nicht mehr.

Eingaben
--------
pipeline/ereignisse.db   — von rechne_gitter.py fortgeschrieben
pipeline/bestaetigt.csv  — die bestätigten Fälle, von Hand gepflegt:

    datum_utc,lat,lon,typ,quelle
    2026-06-21T15:40,51.12,7.31,T,ESWD
    2026-07-04T13:05,48.77,9.18,W,Skywarn

    typ: T = Tornado über Land, W = Wasserhose, V = Verdachtsfall

Warum von Hand? Die ESWD hat keine offene Schnittstelle zum Massenabruf, und
die Weiterverwendung der Daten ist lizenzrechtlich geregelt. Für die eigene
Auswertung darfst du die Fälle eintragen; bevor daraus etwas Öffentliches wird,
muss die Lizenzfrage geklärt sein.

Aufruf
------
    python3 abgleich.py
    python3 abgleich.py --radius 60 --stunden 4
"""

import argparse
import csv
import math
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

HIER = Path(__file__).parent
DB = HIER / "ereignisse.db"
CSV_DATEI = HIER / "bestaetigt.csv"

SCHWELLEN = [25, 35, 45, 55, 70]


def km_abstand(lat1, lon1, lat2, lon2):
    kx = math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot((lat1 - lat2) * 111.0, (lon1 - lon2) * 111.0 * kx)


def faelle_laden():
    if not CSV_DATEI.exists():
        return []
    faelle = []
    with CSV_DATEI.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r.get("datum_utc"):
                continue
            zeit = datetime.fromisoformat(r["datum_utc"])
            if zeit.tzinfo is None:
                zeit = zeit.replace(tzinfo=timezone.utc)
            faelle.append({"zeit": zeit, "lat": float(r["lat"]), "lon": float(r["lon"]),
                           "typ": (r.get("typ") or "T").strip(), "quelle": r.get("quelle", "")})
    return faelle


def lagen_laden(con):
    """Je Vorhersagezeitpunkt und Ort nur den jüngsten Modelllauf — sonst zählt
    dieselbe Lage acht Mal, und die Statistik wird geschönt."""
    besen = {}
    for gilt, lat, lon, tpi, lauf in con.execute(
            "SELECT gilt_fuer, lat, lon, tpi, lauf FROM lagen"):
        zeit = datetime.fromisoformat(gilt)
        if zeit.tzinfo is None:
            zeit = zeit.replace(tzinfo=timezone.utc)
        schluessel = (gilt, round(lat, 2), round(lon, 2))
        if schluessel not in besen or lauf > besen[schluessel][4]:
            besen[schluessel] = (zeit, lat, lon, tpi, lauf)
    return list(besen.values())


def treffer_pruefen(fall, lagen, radius, stunden):
    """Höchster vorhergesagter TPI im Umkreis und Zeitfenster des Falls."""
    bester = 0.0
    fenster = timedelta(hours=stunden)
    for zeit, lat, lon, tpi, _ in lagen:
        if abs(zeit - fall["zeit"]) > fenster:
            continue
        if km_abstand(fall["lat"], fall["lon"], lat, lon) > radius:
            continue
        bester = max(bester, tpi)
    return bester


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--radius", type=float, default=50.0, help="Umkreis in km")
    ap.add_argument("--stunden", type=float, default=3.0, help="Zeitfenster ± Stunden")
    args = ap.parse_args()

    if not DB.exists():
        raise SystemExit("Keine Aufzeichnung gefunden — erst rechne_gitter.py laufen lassen.")

    con = sqlite3.connect(DB)
    lagen = lagen_laden(con)
    zeitraum = con.execute("SELECT MIN(gilt_fuer), MAX(gilt_fuer) FROM lagen").fetchone()
    con.close()

    faelle = faelle_laden()

    print("═" * 66)
    print("ABGLEICH — Vorhersage gegen bestätigte Fälle")
    print("═" * 66)
    print(f"Aufzeichnung : {len(lagen)} Lagen ab TPI 25")
    print(f"Zeitraum     : {zeitraum[0]} bis {zeitraum[1]}")
    print(f"Bestätigt    : {len(faelle)} Fälle in {CSV_DATEI.name}")
    print(f"Fenster      : {args.radius:g} km, ± {args.stunden:g} h")
    print()

    if not faelle:
        print("Noch keine bestätigten Fälle eingetragen.")
        print()
        print("So füllst du die Liste — einmal pro Woche reicht:")
        print("  1. eswd.eu öffnen, Zeitraum und Deutschland wählen")
        print("  2. je Fall Datum (UTC), Breite, Länge und Typ übernehmen")
        print(f"  3. als Zeile in {CSV_DATEI} eintragen")
        print()
        print("Ohne diese Gegenprobe bleibt jede Aussage über die Trefferquote")
        print("unbelegt — auch meine.")
        return

    # Trefferprüfung je Fall
    print(f"{'Fall':<20}{'Typ':<5}{'höchster TPI':>14}   Bewertung")
    print("─" * 66)
    treffer_werte = []
    for fall in sorted(faelle, key=lambda f: f["zeit"]):
        tpi = treffer_pruefen(fall, lagen, args.radius, args.stunden)
        treffer_werte.append(tpi)
        bewertung = ("nichts gesehen" if tpi < 25 else
                     "angedeutet" if tpi < 45 else
                     "klar getroffen")
        print(f"{fall['zeit']:%d.%m.%Y %H:%M}   {fall['typ']:<5}{tpi:>11.1f}     {bewertung}")

    # Kontingenz je Schwelle. Fehlalarm = Tag+Rasterzelle über Schwelle ohne Fall.
    raster = defaultdict(float)
    for zeit, lat, lon, tpi, _ in lagen:
        raster[(zeit.date(), round(lat * 2) / 2, round(lon * 2) / 2)] = max(
            raster[(zeit.date(), round(lat * 2) / 2, round(lon * 2) / 2)], tpi)
    fall_zellen = {(f["zeit"].date(), round(f["lat"] * 2) / 2, round(f["lon"] * 2) / 2)
                   for f in faelle}

    print()
    print(f"{'Schwelle':>9}{'Treffer':>9}{'Verpasst':>10}{'Fehlalarm':>11}"
          f"{'POD':>8}{'FAR':>8}{'CSI':>8}")
    print("─" * 66)
    for s in SCHWELLEN:
        treffer = sum(1 for t in treffer_werte if t >= s)
        verpasst = len(treffer_werte) - treffer
        gewarnt = {z for z, t in raster.items() if t >= s}
        fehl = len(gewarnt - fall_zellen)
        pod = treffer / len(treffer_werte) if treffer_werte else 0
        far = fehl / (fehl + treffer) if (fehl + treffer) else 0
        csi = treffer / (treffer + verpasst + fehl) if (treffer + verpasst + fehl) else 0
        print(f"{s:>9}{treffer:>9}{verpasst:>10}{fehl:>11}{pod:>8.2f}{far:>8.2f}{csi:>8.2f}")

    print()
    print("POD = Anteil der Fälle, die der Index vorher hatte (je höher, desto besser)")
    print("FAR = Anteil der Warnungen, aus denen nichts wurde")
    print("CSI = beides zusammen; das ist die Zahl, die es zu verbessern gilt")
    print()
    print("Bei den wenigen Tornados pro Jahr sind zweistellige Fallzahlen nötig,")
    print("bevor diese Werte belastbar sind. Vorher zeigen sie nur die Richtung.")


if __name__ == "__main__":
    main()
