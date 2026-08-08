#!/usr/bin/env python3
"""
Rechnet das Vorhersagegitter vor und zeichnet jede Hochlage auf.

Zwei Aufgaben in einem Lauf:

1. prototyp/daten/gitter.json  — das feine Gitter fürs Frontend. Der Browser
   holt sonst selbst ~660 Punkte bei jedem Aufruf; hier gehen wir in Ruhe auf
   15 km, weil es nur einmal je Modelllauf passiert.

2. pipeline/ereignisse.db      — jede Zelle über der Schwelle mit allen
   Parametern. Das ist die Grundlage, um den Index später gegen bestätigte
   Tornados zu prüfen (siehe abgleich.py). Ohne diese Aufzeichnung bleibt der
   TPI für immer eine Behauptung.

Aufruf:
    python3 rechne_gitter.py              # 15 km, Standard
    python3 rechne_gitter.py --km 60      # grob, zum Testen
"""

import argparse
import base64
import json
import math
import sqlite3
import struct
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HIER    = Path(__file__).parent
PROJEKT = HIER.parent
# Als JS-Datei, nicht als JSON: ein <script src> lädt auch dann, wenn die Seite
# direkt vom Dateisystem geöffnet wird — fetch() ist unter file:// blockiert.
ZIEL    = PROJEKT / "prototyp" / "daten" / "gitter.js"
DB      = HIER / "ereignisse.db"
UMRISS  = PROJEKT / "build" / "quellen" / "deutschland_hoch.geo.json"

GB      = {"lat0": 47.25, "lat1": 55.05, "lon0": 5.85, "lon1": 15.05}
KX      = math.cos(math.radians(51.2))
STUNDEN = 49
CHUNK   = 350                 # Open-Meteo bricht bei ~9 kB URL mit HTTP 414 ab
SCHWELLE = 25                 # ab TPI 25 wird eine Lage aufgezeichnet
RAND_KM = 30                  # Saum um Deutschland, den wir noch mitabfragen
# 51 statt 72 Stunden: die Seite zeigt 49, der Rest war Nutzlast ohne Zweck —
# und Open-Meteo wiegt eine Anfrage nach Punkten × Stunden × Größen.
STUNDEN_ABRUF = 51

VARIABLEN = ("cape,convective_inhibition,wind_speed_10m,wind_direction_10m,"
             "wind_speed_500hPa,wind_direction_500hPa,temperature_2m,dew_point_2m")

# Konvektions-Gate: LPI und Aufwind gibt es nur bei ICON-D2, deshalb eine eigene
# Anfrage mit &models=icon_d2. Die Basisanfrage bleibt bewusst beim Modellmix —
# ICON-D2 endet 48 h nach dem Lauf und würde die hinteren Stunden abschneiden.
KONV_VARIABLEN = "lightning_potential,updraft,precipitation"

# Quantisierung: Faktor je Feld, damit alles in Int16 passt (±32767)
# cin bewusst nur 20: bei Faktor 50 klippt der Betrag ab 655 J/kg, und im
# Bestand stehen schon −531. Auflösung 0,05 J/kg ist immer noch reichlich.
SKALA = {"cape": 4, "cin": 20, "shear": 300, "lcl": 6, "u": 200, "v": 200,
         "konv": 1000, "gew": 100, "blitz": 100}

# Felder, die „keine Daten" kennen müssen. 0 wäre dort eine Lüge (hieße: kein
# Gewitter), 1 ebenso (hieße: überall Gewitter). Deshalb ein eigener Kennwert,
# den das Frontend erkennt und als Lücke behandelt.
KEINE_DATEN = -1.0
LUECKENFELDER = ("gew", "blitz")


# ── Geometrie: liegt der Punkt in Deutschland? ───────────────────────────────
def umriss_laden():
    geo = json.loads(UMRISS.read_text("utf-8"))["features"][0]["geometry"]
    polys = geo["coordinates"] if geo["type"] == "MultiPolygon" else [geo["coordinates"]]
    return [ring for poly in polys for ring in poly]


def in_deutschland(lon, lat, ringe):
    """Strahlverfahren. Reicht hier, weil der Umriss keine Löcher hat."""
    drin = False
    for ring in ringe:
        n = len(ring)
        j = n - 1
        for i in range(n):
            xi, yi = ring[i][0], ring[i][1]
            xj, yj = ring[j][0], ring[j][1]
            if (yi > lat) != (yj > lat):
                if lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                    drin = not drin
            j = i
    return drin


# ── Index ────────────────────────────────────────────────────────────────────
def konv_faktor(lpi, aufwind, nied):
    """Konvektions-Gate aus ICON-D2 — identisch zu konvFaktor() im Frontend.

    Die vier Umgebungsgrößen sagen nur, wie günstig die Luftmasse wäre, nicht ob
    das Modell dort ein Gewitter baut. LPI in J/kg, Aufwind in m/s, Nied. in mm/h.
    """
    return max(0.0, min(1.0, max(lpi / 5, (aufwind - 2) / 6, nied / 1.0)))


def zell_staerke(lpi, aufwind, nied):
    """Gewitterzelle als Stärke 0…100 — identisch zu zellStaerke() im Frontend.

    Getrennt vom Gate, weil das Gate absichtlich sättigt: es fragt nur „Gewitter
    ja/nein", und ab LPI 5 steht es auf 1. Für die Darstellung brauchen wir aber
    eine Skala, die zwischen Schauer und Superzelle noch unterscheidet.

    Zwei Anteile, weil beide für sich in die Irre führen:
      kern  — dass überhaupt ein Konvektionskern da ist (Aufwind oder Regen).
              Ein Starkregenkern ohne Blitze ist eine Zelle, nur eben keine
              elektrisch aktive.
      blitz — LPI, das eigentliche Gewittermerkmal. Hebt den Kern an, kann ihn
              aber nicht ersetzen: LPI ohne Kern kommt in der Praxis nicht vor.

    Rückgabe: (Zellstärke 0…100, elektrische Aktivität 0…100).
    """
    kern = max(0.0, min(1.0, max(nied / 10.0, (aufwind - 1.5) / 16.0)))
    blitz = max(0.0, min(1.0, lpi / 25.0))
    gew = max(0.0, min(1.0, 0.65 * kern + 0.35 * blitz + 0.35 * kern * blitz))
    return 100 * gew, 100 * blitz


def tpi_of(cape, shear, cin, lcl, konv=1.0):
    """Identisch zur Frontend-Formel in index.template.html — bei Änderungen
    müssen beide Seiten angefasst werden."""
    cin_mag = abs(cin)
    cape_t = min(1.45, math.sqrt(max(cape, 0) / 1500))
    shear_t = max(0.0, min(1.25, (shear - 8) / 17))
    cin_t = max(0.15, min(1.0, 1 - (cin_mag - 50) / 200))
    lcl_t = max(0.25, min(1.1, 1.2 - lcl / 2000))
    konv_t = max(0.0, min(1.0, konv))
    return min(100.0, 100 * cape_t * shear_t * cin_t * lcl_t * konv_t)


def uv(spd_kmh, dir_deg):
    s = spd_kmh / 3.6
    r = math.radians(dir_deg)
    return -s * math.sin(r), -s * math.cos(r)


# ── Abruf ────────────────────────────────────────────────────────────────────
def hole(url, versuche=6):
    for n in range(versuche):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and n < versuche - 1:
                # Verdoppelnd statt linear: 429 kommt bei Open-Meteo nicht nur vom
                # Minutenlimit, sondern auch vom Stundenlimit — dagegen sind 20 bis
                # 80 Sekunden chancenlos. So warten wir bis zu gut acht Minuten.
                warte = 30 * 2 ** n
                print(f"    HTTP {e.code} — warte {warte}s")
                time.sleep(warte)
                continue
            raise
        except Exception:
            if n < versuche - 1:
                time.sleep(10)
                continue
            raise


def gitter_abrufen(lats, lons, variablen, modell=None, weich=False):
    """Holt `variablen` für alle Punkte, in Teilstücken von CHUNK.

    weich=True: Fehler brechen den Lauf nicht ab, sondern liefern None-Platzhalter
    in gleicher Anzahl. So kostet ein Ausfall des Gates nur das Gate, nicht den
    ganzen Durchgang.
    """
    punkte = []
    for a in range(0, len(lats), CHUNK):
        b = min(len(lats), a + CHUNK)
        url = ("https://api.open-meteo.com/v1/forecast"
               "?latitude=" + ",".join(f"{x:.3f}" for x in lats[a:b])
               + "&longitude=" + ",".join(f"{x:.3f}" for x in lons[a:b])
               + "&hourly=" + variablen
               + ("&models=" + modell if modell else "")
               + f"&forecast_hours={STUNDEN_ABRUF}&timezone=UTC")
        print(f"  Teil {a//CHUNK + 1}: Punkte {a}–{b}" + (f" [{modell}]" if modell else ""))
        try:
            antwort = hole(url)
        except Exception as e:
            if not weich:
                raise
            print(f"    Ausfall ({e}) — {b - a} Platzhalter")
            punkte.extend([None] * (b - a))
            time.sleep(3)
            continue
        punkte.extend(antwort if isinstance(antwort, list) else [antwort])
        time.sleep(3)
    return punkte


def saum_maske(maske, rows, cols, km, gitter_km):
    """Weitet die Deutschland-Maske um RAND_KM auf.

    Nur Punkte in Deutschland abzufragen wäre zu knapp: die bilineare
    Interpolation im Frontend zieht an der Grenze Nachbarpunkte heran, und ohne
    Saum wären das Nullen — die Küsten und Grenzen bekämen einen künstlichen
    Abfall. Zwei Zellen Saum bei 15 km reichen dafür.
    """
    r = max(1, int(math.ceil(km / gitter_km)))
    breit = [False] * (rows * cols)
    for j in range(rows):
        for i in range(cols):
            if not maske[j * cols + i]:
                continue
            for dj in range(-r, r + 1):
                for di in range(-r, r + 1):
                    nj, ni = j + dj, i + di
                    if 0 <= nj < rows and 0 <= ni < cols:
                        breit[nj * cols + ni] = True
    return breit


# ── Aufzeichnung ─────────────────────────────────────────────────────────────
def db_oeffnen():
    con = sqlite3.connect(DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS lagen (
            id          INTEGER PRIMARY KEY,
            lauf        TEXT NOT NULL,     -- Modelllauf (ISO)
            gilt_fuer   TEXT NOT NULL,     -- Vorhersagezeitpunkt (ISO, UTC)
            vorlauf_h   INTEGER NOT NULL,  -- Stunden zwischen Lauf und Zeitpunkt
            lat         REAL NOT NULL,
            lon         REAL NOT NULL,
            tpi         REAL NOT NULL,
            cape        REAL, shear REAL, cin REAL, lcl REAL, hoehenwind REAL,
            konv        REAL,             -- Konvektions-Gate 0…1 (NULL = nicht erhoben)
            erfasst_am  TEXT NOT NULL,
            UNIQUE(lauf, gilt_fuer, lat, lon)
        )""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_gilt ON lagen(gilt_fuer)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_tpi  ON lagen(tpi)")
    # Nachrüstung für Datenbanken aus der Zeit vor dem Konvektions-Gate. Alte
    # Zeilen behalten NULL — das unterscheidet „nicht erhoben" von „Gate offen".
    spalten = {r[1] for r in con.execute("PRAGMA table_info(lagen)")}
    if "konv" not in spalten:
        con.execute("ALTER TABLE lagen ADD COLUMN konv REAL")
        print("  DB: Spalte konv ergänzt")
    con.commit()
    return con


def lagen_schreiben(con, lauf, t0, felder, lats, lons, maske, stunden):
    jetzt = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for h in range(stunden):
        gilt = (t0.timestamp() + h * 3600)
        gilt_iso = datetime.fromtimestamp(gilt, timezone.utc).isoformat(timespec="seconds")
        for c, drin in enumerate(maske):
            if not drin:
                continue
            tpi = felder["tpi"][h][c]
            if tpi < SCHWELLE:
                continue
            try:
                con.execute(
                    "INSERT OR IGNORE INTO lagen (lauf,gilt_fuer,vorlauf_h,lat,lon,tpi,"
                    "cape,shear,cin,lcl,hoehenwind,konv,erfasst_am) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (lauf, gilt_iso, h, round(lats[c], 3), round(lons[c], 3), round(tpi, 1),
                     round(felder["cape"][h][c], 1), round(felder["shear"][h][c], 2),
                     round(felder["cin"][h][c], 1), round(felder["lcl"][h][c], 0),
                     round(math.hypot(felder["u"][h][c], felder["v"][h][c]) * 3.6, 1),
                     round(felder["konv"][h][c], 3), jetzt))
            except sqlite3.Error as e:
                print("    DB-Fehler:", e)
    con.commit()


# ── Hauptlauf ────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--km", type=float, default=15.0, help="Gitterweite in km")
    args = ap.parse_args()

    dlat = args.km / 111.0
    dlon = args.km / (111.0 * KX)
    rows = round((GB["lat1"] - GB["lat0"]) / dlat) + 1
    cols = round((GB["lon1"] - GB["lon0"]) / dlon) + 1
    nc = rows * cols
    print(f"Gitter {cols}×{rows} = {nc} Punkte bei {args.km:g} km")

    dlat = (GB["lat1"] - GB["lat0"]) / (rows - 1)
    dlon = (GB["lon1"] - GB["lon0"]) / (cols - 1)

    lats, lons = [], []
    for j in range(rows):
        for i in range(cols):
            lats.append(GB["lat1"] - j * dlat)
            lons.append(GB["lon0"] + i * dlon)

    ringe = umriss_laden()
    maske = [in_deutschland(lo, la, ringe) for lo, la in zip(lons, lats)]
    print(f"  davon in Deutschland: {sum(maske)}")

    # Nur Deutschland plus Saum abfragen. Der Rest des Rechtecks — halb Frankreich,
    # Tschechien, die Ostsee — wird nie gezeichnet und nie aufgezeichnet, kostet
    # aber jedes Mal Anfragegewicht. Seit das Konvektions-Gate eine zweite Anfrage
    # je Teilstück braucht, reicht das Ratelimit sonst nicht mehr.
    abfrage = saum_maske(maske, rows, cols, RAND_KM, args.km)
    idx = [c for c in range(nc) if abfrage[c]]
    q_lats = [lats[c] for c in idx]
    q_lons = [lons[c] for c in idx]
    print(f"  abgefragt: {len(idx)} von {nc} Punkten "
          f"(Deutschland + {RAND_KM:g} km Saum, spart {1 - len(idx)/nc:.0%})")

    def auffuellen(teil, name):
        """Teilergebnis wieder auf die volle Gitterlänge bringen."""
        if len(teil) != len(idx):
            raise SystemExit(f"{name}: {len(teil)} statt {len(idx)} Punkten")
        voll = [None] * nc
        for k, c in enumerate(idx):
            voll[c] = teil[k]
        return voll

    roh = auffuellen(gitter_abrufen(q_lats, q_lons, VARIABLEN), "Basis")
    gate = auffuellen(
        gitter_abrufen(q_lats, q_lons, KONV_VARIABLEN, modell="icon_d2", weich=True),
        "Gate")

    # roh enthält jetzt None für die nicht abgefragten Punkte außerhalb des Saums.
    zeiten = next((r["hourly"]["time"] for r in roh if r), None)
    if zeiten is None:
        raise SystemExit("keine einzige Antwort erhalten")

    # Zeitachsen abgleichen statt blind denselben Index nehmen. Passt sie nicht,
    # läuft der Durchgang ohne Gate weiter — ein offenes Gate ist ehrlicher als
    # ein um Stunden versetztes.
    g_versatz = 0
    g_zeiten = next((g["hourly"]["time"] for g in gate if g), None)
    if g_zeiten is None:
        print("  Gate: ICON-D2 lieferte nichts — Gate bleibt offen")
        gate = [None] * nc
    elif zeiten[0] in g_zeiten:
        g_versatz = g_zeiten.index(zeiten[0])
    else:
        print("  Gate: Zeitachse passt nicht — Gate bleibt offen")
        gate = [None] * nc
    jetzt = datetime.now(timezone.utc).timestamp()
    start = 0
    for k, t in enumerate(zeiten):
        if datetime.fromisoformat(t).replace(tzinfo=timezone.utc).timestamp() >= jetzt - 3600:
            start = k
            break
    start = min(start, max(0, len(zeiten) - STUNDEN))
    n = min(STUNDEN, len(zeiten) - start)
    t0 = datetime.fromisoformat(zeiten[start]).replace(tzinfo=timezone.utc)
    lauf = datetime.fromisoformat(zeiten[0]).replace(tzinfo=timezone.utc)

    felder = {k: [[KEINE_DATEN if k in LUECKENFELDER else 0.0] * nc for _ in range(n)]
              for k in ("cape", "cin", "shear", "lcl", "u", "v", "konv", "tpi",
                        "gew", "blitz")}

    ohne_gate = 0
    for h in range(n):
        k = start + h
        for c in range(nc):
            if roh[c] is None:      # außerhalb des Saums — bleibt auf null
                continue
            st = roh[c]["hourly"]
            konv = 1.0
            if gate[c] is not None:
                gs = gate[c]["hourly"]
                gk = k + g_versatz
                lpi = gs["lightning_potential"][gk] if gk < len(gs["lightning_potential"]) else None
                auf = gs["updraft"][gk] if gk < len(gs["updraft"]) else None
                nie = gs["precipitation"][gk] if gk < len(gs["precipitation"]) else None
                # Alle drei None = jenseits des ICON-D2-Horizonts (+48 h ab Lauf).
                # Dann Gate offen lassen: keine Konvektionsvorhersage ist kein
                # Beleg für keine Konvektion.
                if lpi is None and auf is None and nie is None:
                    ohne_gate += 1
                else:
                    konv = konv_faktor(lpi or 0.0, auf or 0.0, nie or 0.0)
                    # Nur hier, wo ICON-D2 wirklich geantwortet hat, wird die
                    # Zellstärke gesetzt. Sonst bleibt KEINE_DATEN stehen —
                    # sonst hieße Stunde 47 „Gewitter über ganz Deutschland",
                    # weil das Gate dort offensteht.
                    g, b = zell_staerke(lpi or 0.0, auf or 0.0, nie or 0.0)
                    felder["gew"][h][c] = g
                    felder["blitz"][h][c] = b
            cape = st["cape"][k] or 0.0
            cin = -abs(st["convective_inhibition"][k] or 0.0)   # API liefert Beträge
            u10, v10 = uv(st["wind_speed_10m"][k] or 0.0, st["wind_direction_10m"][k] or 0.0)
            u50, v50 = uv(st["wind_speed_500hPa"][k] or 0.0, st["wind_direction_500hPa"][k] or 0.0)
            shear = math.hypot(u50 - u10, v50 - v10)
            t2 = st["temperature_2m"][k]
            td = st["dew_point_2m"][k]
            lcl = max(50.0, 125 * ((t2 if t2 is not None else 15) - (td if td is not None else 10)))
            felder["cape"][h][c] = cape
            felder["cin"][h][c] = cin
            felder["shear"][h][c] = shear
            felder["lcl"][h][c] = lcl
            felder["u"][h][c] = u50
            felder["v"][h][c] = v50
            felder["konv"][h][c] = konv
            felder["tpi"][h][c] = tpi_of(cape, shear, cin, lcl, konv)

    if ohne_gate:
        anteil = ohne_gate / (n * max(1, len(idx)))
        print(f"  Gate: {anteil:.1%} der Punktstunden ohne ICON-D2 "
              f"(Horizont +48 h ab Lauf) — dort bleibt das Gate offen, "
              f"die Gewitterebene bleibt dort leer statt voll")

    # Kurzbilanz der Gewitterebene — ohne die merkt man erst im Browser, dass
    # ein Lauf gar keine Zellen enthält.
    zellwerte = [felder["gew"][h][c] for h in range(n) for c in range(nc)
                 if felder["gew"][h][c] > 0]
    if zellwerte:
        print(f"  Gewitterebene: {len(zellwerte)} Punktstunden mit Zelle, "
              f"Höchstwert {max(zellwerte):.0f}, "
              f"davon kräftig (≥40): {sum(1 for v in zellwerte if v >= 40)}")
    else:
        print("  Gewitterebene: keine einzige Zelle im Vorhersagezeitraum")

    # JSON fürs Frontend
    ausgabe = {
        "grid": {"lat0": GB["lat0"], "lat1": GB["lat1"], "lon0": GB["lon0"],
                 "lon1": GB["lon1"], "rows": rows, "cols": cols},
        "t0": t0.isoformat().replace("+00:00", "Z"),
        "run": lauf.strftime("%d.%m., %H:%M UTC"),
        "hours": n,
        "scale": SKALA,
        "fields": {},
    }
    for f, skala in SKALA.items():
        flach = []
        for h in range(n):
            for c in range(nc):
                flach.append(max(-32768, min(32767, int(round(felder[f][h][c] * skala)))))
        ausgabe["fields"][f] = base64.b64encode(
            struct.pack(f"<{len(flach)}h", *flach)).decode("ascii")

    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    ZIEL.write_text("window.GITTER=" + json.dumps(ausgabe, separators=(",", ":")) + ";", "utf-8")
    print(f"  → {ZIEL} ({ZIEL.stat().st_size/1024/1024:.2f} MB)")

    veraltet = ZIEL.parent / "gitter.json"
    if veraltet.exists():
        veraltet.unlink()

    # Aufzeichnung
    con = db_oeffnen()
    vorher = con.execute("SELECT COUNT(*) FROM lagen").fetchone()[0]
    lagen_schreiben(con, lauf.isoformat(), t0, felder, lats, lons, maske, n)
    nachher = con.execute("SELECT COUNT(*) FROM lagen").fetchone()[0]
    spitze = con.execute("SELECT MAX(tpi) FROM lagen").fetchone()[0]
    con.close()
    print(f"  Aufzeichnung: {nachher - vorher} neue Lagen ab TPI {SCHWELLE} "
          f"(gesamt {nachher}, Höchstwert {spitze})")


if __name__ == "__main__":
    main()
