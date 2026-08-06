# Arbeitsplan — nächste Schritte

Aus dem Fachgutachten vom 06.08.2026 (`GUTACHTEN.md`). Fünf Maßnahmen, nach
Wirkung sortiert. Jede ist für sich abschließbar; die Reihenfolge ist eine
Empfehlung, keine Abhängigkeitskette — außer wo unten anders vermerkt.

**Status:** Maßnahme 2 erledigt (06.08.2026). Offen: 1, 3, 4, 5.
Zuletzt bearbeitet: 06.08.2026 — Konvektions-Gate.

> ⚠️ **Offener Punkt vom 06.08. abends:** `prototyp/daten/gitter.js` ist gerade
> das grobe **60-km-Testgitter**, nicht die 15-km-Fassung. Ein Testlauf hat die
> Datei überschrieben, und der Neuaufbau lief in Open-Meteos **Tageskontingent**
> (429 auch bei einer einzelnen Minimalanfrage). `pipeline/nachholen.sh` wartet
> auf den Reset um 00:00 UTC und rechnet dann neu; Fortschritt in
> `pipeline/nachholen.log`. Falls das nicht geklappt hat: einmal
> `python3 pipeline/rechne_gitter.py` von Hand. Danach kann `nachholen.sh` weg.

---

## 1. Rückwirkende Verifikation aufsetzen

**Warum zuerst:** Ohne Gegenprobe ist jede Formeländerung Blindflug. Und die
Annahme, man müsse dafür Jahre Daten sammeln, war falsch — das Archiv gibt es
schon.

**Schritte**
1. `historical-forecast-api.open-meteo.com` anzapfen (nicht die ERA5-Archiv-API,
   die hat **kein** CAPE und keine Druckflächen).
   - CAPE verfügbar ab ~Dez 2022, Druckflächen ab ~Okt 2023.
   - **Falle:** CIN stammt vor Ende Juni 2026 aus GFS und ist **negativ**
     notiert. Unser `-abs(...)` fängt das ab, aber die Auswertung muss den
     Modellbruch kennen.
   - **Falle:** 2022 fehlten Druckflächen westlich von ~8 °E (NRW, RLP,
     Saarland, Ostfriesland). Abdeckung fallweise prüfen.
2. ESWD-Meldungen für Deutschland **ab 2023** nach `pipeline/bestaetigt.csv`
   (rein private Auswertung — Lizenz siehe `RECHTLICHES.md` §6). Rund 150 Fälle.
   Die 48 historischen Fälle aus der Wikipedia-Liste sind dafür **unbrauchbar**:
   keine Uhrzeiten, 40 davon vor dem Archiv, Selektion auf F2+.
3. `pipeline/abgleich.py` reparieren: FAR/CSI mischen derzeit Fälle mit
   Rasterzell-Tagen. Beide Seiten auf dieselbe Einheit bringen —
   Vorschlag (Tag × 0,5°-Zelle).
4. `pipeline/rechne_gitter.py` erweitern: zusätzlich das **Tagesmaximum für alle
   ~185 Zellen** schreiben, nicht nur TPI ≥ 25. Sonst fehlen korrekte
   Nullvorhersagen und es ist nie eine Kontingenztafel möglich.
   (~4.400 Zeilen/Tag, wenige MB im Jahr.)
5. Kopfmetrik umstellen auf **P(Tornado | TPI-Klasse) + ROC/AUC + Heidke**.
   CSI streichen oder als „strukturell < 0,05" beschriften — bei der Basisrate
   ist FAR ≥ 0,95 selbst bei perfekter Trefferquote.

**Dateien:** `pipeline/abgleich.py`, `pipeline/rechne_gitter.py`,
`pipeline/bestaetigt.csv`, neu z. B. `pipeline/archiv_holen.py`
**Aufwand:** ein Wochenende · **Nutzen:** höchster

---

## 2. Konvektions-Gate aus ICON-D2 — ERLEDIGT 06.08.2026

**Warum:** Der TPI bewertet nur die Umgebung. Ob ICON dort überhaupt ein
Gewitter produziert, geht nicht ein — hoher Index über konvektionsfreier
Luftmasse ist reiner Fehlalarm.

**Umgesetzt**
1. `lightning_potential`, `updraft`, `precipitation` per **eigener Anfrage** mit
   `&models=icon_d2` — in `ladeLive()` je Teilstück eine zweite Anfrage, in
   `rechne_gitter.py` ein zweiter Durchgang von `gitter_abrufen()`.
2. `konvFaktor()` / `konv_faktor()`:
   `clamp(max(LPI/5, (updraft−2)/6, niederschlag/1.0), 0, 1)`, als sechster
   Faktor in `tpiOf()` / `tpi_of()`.
3. `findZellen()` prüft zusätzlich `cellAt('konv',idx) > 0`.
4. `konv` als eigenes Feld in `gitter.js` (Int16, Skala 1000) und als Spalte in
   `ereignisse.db` (mit `ALTER TABLE`-Nachrüstung für Altbestand).
5. Im Panel als sechste Zeile „Konvektion ICON-D2" in Prozent.

**Korrekturen gegenüber dem ursprünglichen Plan**
- Die Reichweite steht falsch im Gutachten: ICON-D2 reicht **nicht bis +64 h**,
  sondern nur **+48 h ab Modelllauf**. Alle drei Variablen kommen danach als
  `null` zurück.
- Deshalb **nicht** die ganze Anfrage auf `icon_d2` umgestellt — das hätte die
  Zeitleiste von 48 auf ~44–47 h gekürzt. Der globale Modellwechsel bleibt in
  Maßnahme 4, wo er ohnehin steht.
- Jenseits des Horizonts gilt `f_konv = 1` (**Gate offen**), nicht 0. Eine
  fehlende Konvektionsvorhersage ist kein Beleg für fehlende Konvektion —
  sonst fielen die letzten Stunden stillschweigend auf null Potenzial.
- Fällt die Gate-Anfrage ganz aus, läuft beides ohne Gate weiter statt gar nicht.

**Wirkung** (Testlauf 60 km, ruhige Lage, 49 h): Rasterzell-Stunden mit TPI ≥ 25
von **13 auf 1**, TPI ≥ 10 von **102 auf 4**, Höchstwert 49,9 → 27,2.
Folge fürs Auge: an konvektionsfreien Tagen ist die Karte künftig weitgehend
leer. Das ist der Zweck, sollte aber beim ersten Blick nicht als Fehler gelten.

**Dateien:** `build/index.template.html`, `pipeline/rechne_gitter.py`

---

## 3. Echte Windprofile statt 500-hPa-Näherung

**Warum:** Die jetzige Näherung (500 hPa minus 10 m) unterschätzt die
0–6-km-Scherung um 5–8 % und verpasst 16–30 % der Grenzüberschreitungen. Vor
allem aber fehlen die Größen, die Tornado von Nicht-Tornado trennen.

**Schritte**
1. Sechs Druckflächen mitziehen (1000, 925, 850, 700, 600, 500 hPa), je
   `wind_speed_*`, `wind_direction_*`, `geopotential_height_*`. **Vorher
   API-Budget klären, siehe unten.**
2. Höhe über Grund: `z_AGL = geopotential_height − elevation`, dann linear
   interpolieren.
3. Berechnen: `DLS` (0–6 km), `MLS` (0–3 km), `LLS` (0–1 km).
4. Storm Motion nach **Bunkers et al. (2000), Wea. Forecasting 15, Gl. 1**:
   ```
   V_mean  = 0–6-km-Mittelwind (nicht druckgewichtet)
   V_shear = V(5,5–6 km) − V(0–0,5 km)
   V_RM    = V_mean + 7,5 m/s · (V_shear × k̂)/|V_shear|
   ```
5. `SRH(0–1 km)` daraus.
6. Zugrichtungspfeile in `drawZellen()` auf den Bunkers-Rechtsmover umstellen
   (bisher 500-hPa-Wind — zu schnell und ohne Rechtsablenkung).

**Dateien:** `pipeline/rechne_gitter.py`, `build/index.template.html`
**Aufwand:** ~½ Tag · **Nutzen:** hoch — Voraussetzung für Maßnahme 4

---

## 4. Formel und Schwellwerte europäisch umeichen

**Warum:** Vier echte Fehler, alle ohne neue Daten behebbar (bis auf `f_srh`,
das Maßnahme 3 braucht — bis dahin die MLS-Variante nehmen).

**Neue Formel**
```
f_cape = min(1.5, MLCAPE / 400)                    # statt /1500 (US-Wert)
f_dls  = 0 falls DLS < 10 ; sonst min(1.5, DLS/20) # statt ab 8 m/s
f_srh  = min(1.5, SRH1 / 90)                       # neu, braucht Maßnahme 3
f_lcl  = clamp((1600 − MLLCL) / 900, 0, 1)         # kein Boden mehr
f_cin  = clamp((200 − MLCIN) / 150, 0, 1)          # kein Boden mehr
f_konv = clamp(max(LPI/5, (updraft−2)/6, nied.), 0, 1)

X   = f_cape · f_dls · f_srh · f_lcl · f_cin · f_konv
TPI = 100 · X / (X + 1)        # statt min(100, ·) — nach oben offen
```
Ohne Storm Motion: `f_srh` ersetzen durch
`f_mls = 0 falls MLS < 7; sonst min(1.5, MLS/14)`.

**Schwellwerte in `PARS`**

| Parameter | jetzt | neu |
|---|---|---|
| CAPE (ML) | ab 100 / opt. 800–2500 | ab 100 / **opt. 300–1500** |
| Scherung 0–6 km | ab 15 / opt. 20–32 | F2+: ab 15 / 20–30; zusätzlich „irgendein Tornado": ab 10 / 14–22 |
| Scherung 0–1 km | — | **neu:** ab 6 / opt. 9–15 m/s |
| SRH 0–1 km | — | **neu:** ab 50 / opt. 90–200 m²/s² |
| CIN | zu ab −75 | **voll bis −50, null ab −200** |
| LCL | unter 1200 / 400–900 | **ML-LCL: unter 1400 / 500–1000** |

**Außerdem**
- LCL auf **Mixed-Layer** umstellen (unterste 100 hPa) — oder ersatzweise alle
  SB-Schwellen um ~280 m absenken.
- `&models=icon_d2` explizit setzen statt `best_match` (blendet an Modellnähten
  über → künstliche Sprünge auf der Zeitachse).
- **Codekommentar korrigieren** (`index.template.html`, bei `PARS`): Europa hat
  nicht „hohe Scherung", sondern *weniger* Scherung als die USA. Richtig ist:
  weniger CAPE, weniger Scherung, dafür höheres bodennahes CAPE, steilere untere
  Lapse Rates und schwächeres CIN.
- Im Panel ergänzen: „LCL sagt, **ob** ein Tornado möglich ist, nicht **wie
  stark**" (Púčik et al. 2015).
- `findZellen()`: Schwelle 20 auf 25 anheben (bisher inkonsistent zu `LEVELS`).

**Dateien:** `build/index.template.html`, `pipeline/rechne_gitter.py`
(Formel steht doppelt — **immer beide anfassen**)
**Aufwand:** ~2 h · **Nutzen:** hoch

---

## 5. Zwei Zahlen statt einer

**Warum:** Die Seite kann heute nicht zwischen „organisierte schwere Gewitter"
und „tornadotypisch" unterscheiden, tut aber so.

**Schritte**
1. `Unwetterpotenzial = WMAXSHEAR = sqrt(2 · MLCAPE) · DLS` — laut Taszarek
   et al. (2020) in Europa wie in den USA anwendbar.
2. `Tornado-Zusatz = f_srh · f_lcl (· f_mls)`.
3. Beide getrennt anzeigen; Legende und Erklärtext anpassen.

**Dateien:** `build/index.template.html`
**Aufwand:** ~2 h · **Nutzen:** fachliche Ehrlichkeit

---

## Nebenpunkte (klein, jederzeit mitnehmbar)

- **Entschieden am 06.08.2026: Maßnahme 3 holt die Daten als ICON-D2-GRIB direkt
  vom DWD Open-Data-Server**, nicht über Open-Meteo. Kostenlos, kein Ratelimit,
  und die Nicht-Kommerziell-Klausel von Open-Meteo entfällt — damit ist auch der
  Weg zu Werbung oder Verkauf offen. Preis: GRIB2-Parsing und eigene
  Interpolation statt fertiger JSON-Antworten. Die Frage, ob Open-Meteo pro
  Location oder pro HTTP-Anfrage zählt, erübrigt sich damit.
  Wenn Maßnahme 3 umzieht, sollte das Konvektions-Gate aus Maßnahme 2
  mitwandern — es hängt heute noch an Open-Meteos `&models=icon_d2`.
- ~~`rechne_gitter.py` holt `forecast_days=3`~~ **erledigt 06.08.2026:**
  `forecast_hours=51`.
- ~~Nur Gitterpunkte in Deutschland + ~30 km Rand abfragen~~ **erledigt
  06.08.2026:** `saum_maske()`, 2102 statt 2596 Punkte.
  Beide vorgezogen, weil das Konvektions-Gate eine zweite Anfrage je Teilstück
  braucht und der Lauf danach an Open-Meteos **HTTP 429** scheiterte — auch nach
  fünf Backoff-Versuchen. Zusammen −43 % Anfragegewicht je Durchgang; beide
  Durchgänge liegen damit unter der früheren Last des einen. Backoff außerdem
  von linear 20–80 s auf verdoppelnd 30–960 s bei sechs Versuchen umgestellt,
  weil 429 auch vom Stundenlimit kommt, nicht nur vom Minutenlimit.
- Legende ergänzen: **Wasserhosen fehlen** in der historischen Ebene — 36,6 %
  aller deutschen Meldungen, und die Nordseeküste ist mit 77,2 Tornados je
  10.000 km² die dichteste Region.
- Quelle für „rund 45 pro Jahr" nachtragen: **Beyer, Wapler & Kühne (2025),
  Meteorol. Z. 34(4), DOI 10.1127/metz/1276** — 48,9 ± 20,3 Meldungen/Jahr.

---

## Was bleiben soll

- `-abs(cin)` in beiden Formeln — fängt beide Vorzeichenkonventionen der API ab.
- Die Sprachregelung „Potenzial" statt „Warnung".
- Die historischen Fälle als Kartenebene (nur nicht für die Verifikation).
