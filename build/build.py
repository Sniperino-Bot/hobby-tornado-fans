#!/usr/bin/env python3
"""
Baut prototyp/index.html aus index.template.html + den Quelldaten in quellen/.

Ein einziger Aufruf, keine Shell-Ketten:
    python3 build.py

Erzeugt:
  - Bundesland-Geometrie, vereinfacht (Douglas-Peucker), delta-kodiert
  - Ortsliste ab MIN_POP Einwohnern aus dem GeoNames-Dump
und ersetzt die Marker /*@GEO@*/ und /*@PLACES@*/ in der Vorlage.
"""

import json
import zipfile
from pathlib import Path

HIER      = Path(__file__).parent
QUELLEN   = HIER / "quellen"
VORLAGE   = HIER / "index.template.html"
ZIEL      = HIER.parent / "prototyp" / "index.html"

TOLERANZ  = 0.0018      # Grad ≈ 200 m — fein genug bis Stadtplan-Zoom
PRAEZ     = 10000       # Koordinaten-Quantisierung (1e-4 Grad ≈ 11 m)
MIN_POP   = 1000        # Ortschaften ab dieser Einwohnerzahl


# ── Geometrie ────────────────────────────────────────────────────────────────
def abstand_zur_strecke(p, a, b):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
    t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return ((x - (x1 + t * dx)) ** 2 + (y - (y1 + t * dy)) ** 2) ** 0.5


def vereinfachen(punkte, tol):
    """Douglas-Peucker, iterativ (die Ringe sind zu lang für Rekursion)."""
    if len(punkte) < 3:
        return punkte
    behalten = [False] * len(punkte)
    behalten[0] = behalten[-1] = True
    stapel = [(0, len(punkte) - 1)]
    while stapel:
        i, j = stapel.pop()
        if j <= i + 1:
            continue
        max_d, max_i = 0.0, i
        for k in range(i + 1, j):
            d = abstand_zur_strecke(punkte[k], punkte[i], punkte[j])
            if d > max_d:
                max_d, max_i = d, k
        if max_d > tol:
            behalten[max_i] = True
            stapel.append((i, max_i))
            stapel.append((max_i, j))
    return [p for p, k in zip(punkte, behalten) if k]


def ring_kodieren(punkte):
    """Erster Punkt absolut, danach Deltas — spart rund zwei Drittel."""
    werte = []
    vx = vy = 0
    for lon, lat in punkte:
        x = round(lon * PRAEZ)
        y = round(lat * PRAEZ)
        werte.append(x - vx)
        werte.append(y - vy)
        vx, vy = x, y
    return ",".join(str(w) for w in werte)


def ringe_aus_feature(f, tol):
    geo = f["geometry"]
    polygone = geo["coordinates"] if geo["type"] == "MultiPolygon" else [geo["coordinates"]]
    ringe, roh_n, fein_n = [], 0, 0
    for poly in polygone:
        for ring in poly:
            if len(ring) < 8:
                continue
            punkte = [(float(p[0]), float(p[1])) for p in ring]
            roh_n += len(punkte)
            schlank = vereinfachen(punkte, tol)
            if len(schlank) < 4:
                continue
            fein_n += len(schlank)
            ringe.append(ring_kodieren(schlank))
    return ringe, roh_n, fein_n


def geometrie_bauen():
    """Zwei getrennte Geometrien:

    LAND  — der Bundes-Umriss (77 Inseln/Festland, ohne Löcher). Nur daraus
            werden Fläche, Clip und der Punkt-in-Deutschland-Test gebaut.
    GEO   — die Landesgrenzen, ausschließlich als Linie gezeichnet.

    Getrennt, weil die Vereinigung der 16 Länderpolygone mit der Even-Odd-Regel
    Berlin, Bremen und Hamburg als Loch ausstanzt.
    """
    roh_land = json.loads((QUELLEN / "deutschland_hoch.geo.json").read_text("utf-8"))
    land_ringe, r1, f1 = ringe_aus_feature(roh_land["features"][0], TOLERANZ)
    print(f"  Bundes-Umriss: {f1} von {r1} Punkten, {len(land_ringe)} Ringe")

    roh_bl = json.loads((QUELLEN / "bundeslaender_hoch.geo.json").read_text("utf-8"))
    laender, r2, f2 = [], 0, 0
    for f in roh_bl["features"]:
        ringe, a, b = ringe_aus_feature(f, TOLERANZ * 2)   # Innengrenzen dürfen gröber sein
        r2 += a
        f2 += b
        if ringe:
            laender.append({"n": f["properties"]["name"], "r": ringe})
    print(f"  Landesgrenzen: {f2} von {r2} Punkten, {len(laender)} Länder")

    return ("const LAND=" + json.dumps(land_ringe, separators=(",", ":")) + ";\n"
            + "const GEO=" + json.dumps(laender, ensure_ascii=False, separators=(",", ":")) + ";")


# ── Ortschaften ──────────────────────────────────────────────────────────────
def deutsche_namen():
    """GeoNames führt große Städte unter ihrem internationalen Namen (Munich).
    Aus der Alternativnamen-Tabelle den deutschen holen."""
    bevorzugt, irgendein = {}, {}
    with zipfile.ZipFile(QUELLEN / "geonames_alt_DE.zip") as z:
        for zeile in z.read("DE.txt").decode("utf-8").split("\n"):
            f = zeile.split("\t")
            if len(f) < 4 or f[2] != "de":
                continue
            if len(f) > 6 and f[6] == "1":      # umgangssprachlich
                continue
            if len(f) > 7 and f[7] == "1":      # historisch
                continue
            if len(f) > 4 and f[4] == "1":
                bevorzugt[f[1]] = f[3]
            irgendein.setdefault(f[1], f[3])
    return bevorzugt, irgendein


def orte_bauen():
    bevorzugt, irgendein = deutsche_namen()

    with zipfile.ZipFile(QUELLEN / "geonames_DE.zip") as z:
        text = z.read("DE.txt").decode("utf-8")

    orte, umbenannt = [], 0
    for zeile in text.split("\n"):
        f = zeile.split("\t")
        if len(f) < 15 or f[6] != "P":
            continue
        if f[7] == "PPLX":          # Stadtbezirke doppeln die Kernstadt auf der Karte
            continue
        try:
            pop = int(f[14])
        except ValueError:
            continue
        if pop < MIN_POP:
            continue

        name = f[1]
        deutsch = bevorzugt.get(f[0]) or irgendein.get(f[0])
        # Nur übernehmen, wenn es wirklich ein anderer Name ist — nicht, wenn der
        # Datensatz bloß eine Verwaltungsform davorsetzt ("Bezirk Hamburg-Mitte").
        if deutsch and deutsch != name and name not in deutsch:
            name = deutsch
            umbenannt += 1
        orte.append((name, float(f[5]), float(f[4]), pop))

    print(f"  Ortsnamen eingedeutscht: {umbenannt}")

    # Nach Einwohnerzahl absteigend: die Beschriftung nimmt von vorn, was passt.
    orte.sort(key=lambda o: -o[3])
    zeilen = [
        f"{name}|{round(lon * PRAEZ)}|{round(lat * PRAEZ)}|{pop}"
        for name, lon, lat, pop in orte
    ]
    print(f"  Ortschaften: {len(orte)} ab {MIN_POP} Einwohnern")
    return "const PLACES=" + json.dumps("\n".join(zeilen), ensure_ascii=False) + ";"


# ── Bestätigte Tornados ──────────────────────────────────────────────────────
def tornados_bauen():
    """Aus tornados.py erzeugt. Fehlt die Datei, bleibt die Ebene einfach leer."""
    datei = QUELLEN / "tornados_de.csv"
    if not datei.exists():
        print("  Tornado-Liste fehlt (erst tornados.py laufen lassen) — Ebene bleibt leer")
        return "const TORNADOS=\"\";"

    import csv
    zeilen = []
    with datei.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            zeilen.append("|".join([
                r["datum"], r["ort"], r["bundesland"],
                str(round(float(r["lon"]) * PRAEZ)), str(round(float(r["lat"]) * PRAEZ)),
                r["staerke"]]))
    print(f"  Bestätigte Tornados: {len(zeilen)}")
    return "const TORNADOS=" + json.dumps("\n".join(zeilen), ensure_ascii=False) + ";"


# ── Zusammenbau ──────────────────────────────────────────────────────────────
def main():
    print("Baue TORNADO//DE …")
    vorlage = VORLAGE.read_text("utf-8")
    seite = (vorlage.replace("/*@GEO@*/", geometrie_bauen())
                    .replace("/*@PLACES@*/", orte_bauen())
                    .replace("/*@TORNADOS@*/", tornados_bauen()))

    if "/*@" in seite:
        raise SystemExit("FEHLER: nicht alle Marker ersetzt")

    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    ZIEL.write_text(seite, "utf-8")
    print(f"  → {ZIEL} ({len(seite.encode('utf-8')) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
