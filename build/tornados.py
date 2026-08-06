#!/usr/bin/env python3
"""
Erzeugt quellen/tornados_de.csv — bestätigte Tornados in Deutschland.

Quelle: Wikipedia, „Liste von Tornados in Europa", Abschnitt Deutschland.
Lizenz CC BY-SA 4.0 — deshalb liegt die Quellenangabe sichtbar auf der Seite.

Bewusst NICHT verwendet:
  * tornadoliste.de — urheberrechtlich geschützt, Speicherung in Datenbanken
    ausdrücklich untersagt, Nutzung nur privat und nicht-kommerziell.
  * ESWD — eigene Lizenzbedingungen, keine freie Weiterverwendung.

Die Wikipedia-Liste ist ausdrücklich eine **Auswahl** signifikanter Fälle
(F2–F5), keine Vollzählung. In Deutschland treten im Mittel rund 45 Tornados
pro Jahr auf, die allermeisten schwach. Das muss auf der Seite so dastehen.

Geokodierung über den GeoNames-Dump: Ortsname exakt, bei Mehrdeutigkeit
gewinnt der Ort im genannten Bundesland, sonst der einwohnerstärkste.
Nicht auflösbare Orte werden ausgelassen und aufgelistet — lieber ein Fall
weniger als ein Punkt an der falschen Stelle.
"""

import csv
import re
import unicodedata
import zipfile
from pathlib import Path

HIER = Path(__file__).parent
QUELLEN = HIER / "quellen"
WIKITEXT = QUELLEN / "wikipedia_tornados_europa.wikitext"
ZIEL = QUELLEN / "tornados_de.csv"

MONATE = {"januar": 1, "februar": 2, "märz": 3, "april": 4, "mai": 5, "juni": 6,
          "juli": 7, "august": 8, "september": 9, "oktober": 10,
          "november": 11, "dezember": 12}

LAENDER = ["Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen",
           "Hamburg", "Hessen", "Mecklenburg-Vorpommern", "Niedersachsen",
           "Nordrhein-Westfalen", "Rheinland-Pfalz", "Saarland", "Sachsen-Anhalt",
           "Sachsen", "Schleswig-Holstein", "Thüringen"]

# GeoNames-Verwaltungscodes → Bundesland
ADM1 = {"01": "Baden-Württemberg", "02": "Bayern", "03": "Bremen", "04": "Hamburg",
        "05": "Hessen", "06": "Niedersachsen", "07": "Nordrhein-Westfalen",
        "08": "Rheinland-Pfalz", "09": "Saarland", "10": "Schleswig-Holstein",
        "11": "Brandenburg", "12": "Mecklenburg-Vorpommern", "13": "Sachsen",
        "14": "Sachsen-Anhalt", "15": "Thüringen", "16": "Berlin"}


# Handgeprüfte Korrekturen. Die automatische Ortserkennung greift bei
# uneinheitlich formulierten Beschreibungen daneben; jede Zeile hier wurde
# gegen den Wikipedia-Text einzeln nachgeschlagen.
# (Datum, Textmerkmal, Anzeigename, Ziel, Bundesland)
# Ziel ist entweder ein Ortsname für die Suche im Verzeichnis oder ein festes
# Koordinatenpaar. Fest überall dort, wo das Verzeichnis danebengreift: GeoNames
# führt München unter „Munich", und bei gleichnamigen Orten gewinnt sonst der
# einwohnerstärkste — dann landet der Landkreis Waldshut bei Freiburg.
KORREKTUREN = [
    ("1894-07-14", "östlich von München", "östlich von München", (48.1374, 11.5755), "Bayern"),
    ("1927-06-01", "Auen-Holthaus", "Auen-Holthaus (Lkr. Cloppenburg)", "Cloppenburg", "Niedersachsen"),
    ("2007-01-18", "Lutherstadt-Wittenberg", "Lutherstadt Wittenberg", "Wittenberg", "Sachsen-Anhalt"),
    ("2007-01-18", "Lauchhammer", "Lauchhammer", "Lauchhammer", "Brandenburg"),
    ("2013-08-19", "Abtsgmünd-Pommertsweiler", "Abtsgmünd-Pommertsweiler", "Abtsgmünd", "Baden-Württemberg"),
    ("2015-05-13", "Landkreis Waldshut", "Landkreis Waldshut", (47.6231, 8.2154), "Baden-Württemberg"),
    ("2015-05-13", "Stettenhofen", "Affing-Stettenhofen", "Affing", "Bayern"),
    ("2016-06-13", "Bad Waldsees", "Bad Waldsee-Reute", "Bad Waldsee", "Baden-Württemberg"),
    ("2017-06-22", "Töppel", "Töppel (bei Zerbst)", (51.9667, 12.0833), "Sachsen-Anhalt"),
    ("2021-08-16", "Großheide", "Großheide", (53.5975, 7.3708), "Niedersachsen"),
]

# Fälle, die die Automatik auslässt, weil der Ort nicht als eigener Begriff
# im Text steht. Ebenfalls einzeln nachgeschlagen.
NACHTRAEGE = [
    ("1764-06-29", "F5", "Woldegk", "Woldegk", "Mecklenburg-Vorpommern"),
    ("2006-03-27", "F2", "Hamburg", "Hamburg", "Hamburg"),
    ("2010-05-24", "F3", "Großenhain", "Großenhain", "Sachsen"),
]


def normieren(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.replace("ß", "ss").strip()


def orte_laden():
    """Alle Siedlungen aus dem GeoNames-Dump, auch die ganz kleinen."""
    orte = {}
    with zipfile.ZipFile(QUELLEN / "geonames_DE.zip") as z:
        for zeile in z.read("DE.txt").decode("utf-8").split("\n"):
            f = zeile.split("\t")
            if len(f) < 15 or f[6] != "P":
                continue
            try:
                pop = int(f[14])
            except ValueError:
                pop = 0
            land = ADM1.get(f[10], "")
            orte.setdefault(normieren(f[1]), []).append(
                {"name": f[1], "lat": float(f[4]), "lon": float(f[5]),
                 "pop": pop, "land": land})
    return orte


def datum_lesen(roh):
    roh = re.sub(r"\[\[|\]\]", "", roh)
    roh = roh.split("/")[0].split(" bis ")[0].strip()
    m = re.search(r"(\d{1,2})\.\s*([A-Za-zÄÖÜäöüß]+)\s*(\d{4})", roh)
    if m and m.group(2).lower() in MONATE:
        return f"{int(m.group(3)):04d}-{MONATE[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    m = re.search(r"(\d{4})", roh)
    return f"{m.group(1)}-01-01" if m else None


VORSILBEN = re.compile(
    r"^(tornado|windhose|wirbelsturm|orkan|unwetter|zyklon|superzelle)\s+"
    r"(über|von|vom|bei|im|in|um|am)\s+", re.I)
ZUSAETZE = re.compile(r"^(kreis|landkreis|bezirk|stadt|lutherstadt|bad)\s+", re.I)
UNBRAUCHBAR = {normieren(l) for l in LAENDER} | {
    normieren(w) for w in ("Deutschland", "Norddeutschland", "Süddeutschland",
                           "Ostdeutschland", "Westdeutschland", "Fujita-Skala",
                           "Tornado", "Superzelle", "Mecklenburg", "Oldenburg",
                           "Bergisches Land", "Vogtland", "Erzgebirge")}


def ortskandidaten(beschreibung):
    """Alle plausiblen Ortsbezeichnungen in Reihenfolge ihrer Verlässlichkeit.

    Die Beschreibungen sind uneinheitlich: mal steht der Ort als Link vorn
    ([[Woldegk]]), mal verbirgt er sich im Artikeltitel ([[Tornado über
    Pforzheim]]), mal nur im Fließtext. Deshalb sammeln, säubern, der Reihe
    nach gegen das Ortsverzeichnis prüfen.
    """
    roh = []
    for m in re.finditer(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", beschreibung):
        roh.append(m.group(2) or m.group(1))
        if m.group(2):
            roh.append(m.group(1))
    ohne_links = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", r"\1 ", beschreibung)
    ohne_links = re.sub(r"<ref.*?</ref>|<ref[^>]*/>", " ", ohne_links, flags=re.S)
    roh += re.findall(r"\b([A-ZÄÖÜ][\wÄÖÜäöüß]{2,}(?:[- ][A-ZÄÖÜ][\wÄÖÜäöüß]{2,})?)", ohne_links)

    kandidaten = []
    for k in roh:
        k = k.strip()
        k = VORSILBEN.sub("", k)
        k = ZUSAETZE.sub("", k)
        k = re.sub(r"\s*\(.*?\)\s*", "", k).strip(" ,.;:")
        if len(k) < 3 or normieren(k) in UNBRAUCHBAR:
            continue
        if k not in kandidaten:
            kandidaten.append(k)
    return kandidaten


def land_lesen(beschreibung):
    for land in LAENDER:
        if land in beschreibung:
            return land
    return ""


def main():
    text = WIKITEXT.read_text("utf-8")
    # Länder stehen auf Überschriftenebene 3 — die Grenze muss beliebig viele
    # Gleichheitszeichen zulassen, sonst läuft der Abschnitt bis Artikelende.
    m = re.search(r"^={2,}\s*Deutschland\s*={2,}\s*$(.*?)(?=^={2,}\s*[A-ZÄÖÜ])",
                  text, re.S | re.M)
    if not m:
        raise SystemExit("Abschnitt Deutschland nicht gefunden")

    orte = orte_laden()
    treffer, fehlend = [], []

    for block in m.group(1).split("|-"):
        zeilen = [z.strip() for z in block.strip().split("\n") if z.strip().startswith("|")]
        if len(zeilen) < 4:
            continue
        felder = [re.sub(r"^\|\s*(align=right\s*\|)?\s*", "", z) for z in zeilen]
        datum = datum_lesen(felder[0])
        staerke = re.sub(r"<ref.*?</ref>|<ref[^>]*/>", "", felder[1]).strip()
        beschreibung = felder[3]
        if not datum:
            continue

        land = land_lesen(beschreibung)
        kandidaten, ortsname, gefunden = [], None, False
        for kandidat in ortskandidaten(beschreibung):
            for variante in (kandidat, *kandidat.split("-"), *kandidat.split(" ")):
                if len(variante) < 3:
                    continue
                treffer_liste = orte.get(normieren(variante), [])
                # Bei bekanntem Bundesland nur dort suchen — sonst landet
                # „Salzburg" (Rheinland-Pfalz) irgendwo im Nichts.
                if land:
                    im_land = [t for t in treffer_liste if t["land"] == land]
                    if im_land:
                        kandidaten, ortsname, gefunden = im_land, variante, True
                        break
                elif treffer_liste:
                    kandidaten, ortsname, gefunden = treffer_liste, variante, True
                    break
            if gefunden:
                break
        if not gefunden:
            fehlend.append((datum, (ortskandidaten(beschreibung) or ["?"])[0]))
            continue

        passend = kandidaten
        bester = max(passend, key=lambda k: k["pop"])

        treffer.append({
            "datum": datum,
            "ort": bester["name"],
            "bundesland": bester["land"],
            "lat": round(bester["lat"], 4),
            "lon": round(bester["lon"], 4),
            "staerke": staerke if re.match(r"^[FT]\d", staerke) else "",
            "_text": " ".join(beschreibung.split()),
        })

    def finde(ziel, land):
        if isinstance(ziel, tuple):
            return {"lat": ziel[0], "lon": ziel[1]}
        liste = [o for o in orte.get(normieren(ziel), []) if o["land"] == land]
        if not liste:
            raise SystemExit(f"Korrektur unbrauchbar: {ziel} in {land} nicht gefunden")
        return max(liste, key=lambda o: o["pop"])

    korrigiert = 0
    for datum, merkmal, anzeige, suchort, land in KORREKTUREN:
        for t in treffer:
            if t["datum"] == datum and merkmal in t["_text"]:
                o = finde(suchort, land)
                t.update(ort=anzeige, bundesland=land,
                         lat=round(o["lat"], 4), lon=round(o["lon"], 4))
                korrigiert += 1
                break
        else:
            print(f"  ! Korrektur ohne Fundstelle: {datum} {merkmal}")

    for datum, staerke, anzeige, suchort, land in NACHTRAEGE:
        if any(t["datum"] == datum and t["ort"] == anzeige for t in treffer):
            continue
        o = finde(suchort, land)
        treffer.append({"datum": datum, "ort": anzeige, "bundesland": land,
                        "lat": round(o["lat"], 4), "lon": round(o["lon"], 4),
                        "staerke": staerke, "_text": "nachgetragen"})

    for t in treffer:
        del t["_text"]
    treffer.sort(key=lambda t: t["datum"])
    print(f"  {korrigiert} Einträge handkorrigiert, {len(NACHTRAEGE)} nachgetragen")
    with ZIEL.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(treffer[0].keys()))
        w.writeheader()
        w.writerows(treffer)

    print(f"  {len(treffer)} Tornados geokodiert → {ZIEL.name}")
    if fehlend:
        print(f"  {len(fehlend)} nicht auflösbar, deshalb ausgelassen:")
        for d, o in fehlend:
            print(f"    {d}  {o}")


if __name__ == "__main__":
    main()
