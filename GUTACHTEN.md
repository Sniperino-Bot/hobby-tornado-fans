# Fachgutachten zum TPI

Erstellt am 06.08.2026 von einem beauftragten Gutachter-Agenten mit Schwerpunkt
europäische Tornadoforschung. Er hat den Quellcode gelesen, eigene Messungen
gegen die ICON-Druckflächen gerechnet und die Literaturwerte belegt.

Kennzeichnung im Original: *gesichert* = belegt · *plausibel* = fachlich
begründet · *Vermutung* = Einschätzung · ⚠ = aus einer Abbildung abgelesen,
keine publizierte Ziffer.

---

## Kernbefund

> **Der TPI ist kein Tornadoindex, sondern strukturell ein reskaliertes
> WMAXSHEAR** — also ein Index für organisierte schwere Konvektion.

`capeTerm × shearTerm ∝ √CAPE · Scherung` ist bis auf die Normierung genau
WMAXSHEAR. Taszarek et al. (2017, MWR 145, 1511–1528) halten WMAXSHEAR für den
besten Trenner zwischen schwerer und nicht-schwerer Konvektion — aber für die
**Tornado**-Intensität gewinnen andere Größen: 0–3-km-Scherung und vor allem
0–1-km-SRH.

Genau diese Größen fehlen im Index vollständig, obwohl sie aus derselben API
berechenbar wären.

---

## 1. Geprüfte Näherungen

### Scherung (500 hPa minus 10 m)

Gemessen an 1728 ICON-Profilen gegen die echte 0–6-km-Bulk-Scherung:

| Größe | Wert |
|---|---|
| Korrelation | **0,979** |
| Bias | **−0,84 m/s (−5 bis −8 %)** |
| Fehler Median / p90 | 0,69 / 2,25 m/s |
| 500-hPa-Fläche über Grund | Median 5564 m (5049–5784 m) |

Die Näherung ist vertretbar, unterschätzt aber systematisch — 500 hPa liegt
unterhalb von 6 km. An der Schwelle verpasst sie 16–30 % der echten
Grenzüberschreitungen, erzeugt dafür fast keine falschen.

### LCL

Die 125-m-je-Kelvin-Regel ist korrekt belegt (Lawrence 2005, BAMS 86(2), Gl. 22;
±2 % bei RH 50–100 %). Gegenrechnung gegen Bolton (1980): Bias +6 m. **Die
Formel stimmt.**

**Der Fehler liegt beim Luftpaket:** Die App rechnet ein Surface-Based-LCL aus
2-m-Werten, die gesamte Literatur arbeitet mit Mixed-Layer-LCL.

| | Median |
|---|---|
| SB-LCL (unsere Formel) | 969 m |
| ML-LCL (unterste 100 hPa) | 1311 m |
| **Differenz** | **+286 m** |

Craven, Jewell & Brooks (2002): mittlerer Absolutfehler SBLCL 270 m gegen
MLLCL 46 m. Wir legen ML-Schwellen an einen SB-Wert an, der ~290 m tiefer
liegt — der LCL-Term ist dadurch systematisch zu wohlwollend.

---

## 2. Konstruktionsfehler in der Formel

1. **`min(100, …)` kappt die halbe Skala.** Produktmaximum wäre 199. Eine
   ordentliche Superzellenlage (roh 103) und eine Jahrhundertlage (roh 163)
   bekommen **denselben Wert 100**. Oberhalb TPI 100 keine Auflösung.
2. **Der CIN-Term schließt den Deckel nie.** Boden 0,15 heißt: CIN −300 J/kg
   ergibt noch TPI 10. Thompson et al. (2012) setzen hart 0,0 unter −200 und
   1,0 über −50. Direkter Fehlalarmerzeuger.
3. **`shearTerm` startet bei 8 m/s** — der deutsche Median liegt bei 13,1 m/s.
   Die Hälfte aller Gitterpunkte hat immer schon Scherungsbeitrag.
4. **`lclTerm` Boden 0,25** — auch eine knochentrockene Grenzschicht trägt bei.
5. **CAPE-Normierung 1500 J/kg ist ein US-Wert.** Europäische F2+-Mediane:
   ⚠ 255 (Taszarek 2017, ML) bis ⚠ 515 J/kg (Púčik, MU). Faktor 3–6 zu hoch.

Der multiplikative Ansatz selbst ist **richtig** (Zutatenprinzip), aber kein
Term darf einen Boden > 0 haben, wenn er eine notwendige Bedingung abbildet.

---

## 3. Datenherkunft — nicht das, was wir dachten

| Variable | tatsächliche Quelle |
|---|---|
| `cape` | ICON `CAPE_ML` = **Mixed-Layer-CAPE** (gut!) |
| `convective_inhibition` | ICON `CIN_ML`, nur D2/EU, **positiv notiert** |
| `lifted_index` | **GFS 0,25°**, nicht ICON |
| `boundary_layer_height` | **ECMWF IFS 9 km**, nicht ICON |

- **`cape` ist ML-CAPE, unser LCL ist SB** → zwei verschiedene Luftpakete in
  einer Formel.
- **`best_match` blendet an Modellnähten über** → künstliche Sprünge auf der
  Zeitachse. Empfehlung: `&models=icon_d2` explizit setzen (deckt 48 h ab).
- **CIN-Vorzeichen ist historisch nicht stabil** (vor Juni 2026 aus GFS,
  negativ). Unser `-abs(...)` fängt beides korrekt ab — **so lassen**.

---

## 4. Was fehlt (alles aus Open-Meteo berechenbar)

| Größe | Weg | Wert |
|---|---|---|
| 0–1-km-Scherung | 925/950 hPa + `geopotential_height` | hoch |
| **0–3-km-Scherung** | 700 hPa, interpoliert | **sehr hoch** — bester EU-Intensitätstrenner |
| **SRH 0–1 km** | Windprofil + Bunkers-Zugvektor | **sehr hoch** |
| Storm Motion (Bunkers) | Formel s. u. | Voraussetzung für SRH, verbessert Zugpfeile |
| Mischungsverhältnis | `dew_point_2m` + `surface_pressure` | mittel–hoch |
| Lapse Rates | `temperature_*hPa` + Höhen | mittel |
| **Konvektionsauslösung** | **`lightning_potential`, `updraft`** — exklusiv ICON-D2 | **höchster Fehlalarm-Hebel** |

Nicht möglich: Effective Inflow Layer, MU-/SB-CAPE getrennt.

**Für das Archiv wichtig:** ERA5 über Open-Meteo hat **kein** CAPE/CIN und keine
Druckflächen. Die `historical-forecast-api` dagegen hat alles — CAPE ab
~Dez 2022, Druckflächen ab ~Okt 2023, CIN erst ab Ende Juni 2026. 2022 gab es
räumliche Lücken westlich von ~8 °E.

---

## 5. Vorgeschlagene neue Formel

```
f_cape = min(1.5, MLCAPE / 400)
f_dls  = 0 falls DLS < 10 ; sonst min(1.5, DLS / 20)
f_srh  = min(1.5, SRH1 / 90)
f_lcl  = clamp((1600 − MLLCL) / 900, 0, 1)
f_cin  = clamp((200 − MLCIN) / 150, 0, 1)
f_konv = clamp(max(LPI/5, (updraft−2)/6, niederschlag), 0, 1)

X   = f_cape · f_dls · f_srh · f_lcl · f_cin · f_konv
TPI = 100 · X / (X + 1)      # streng monoton, nach oben offen
```

Ohne Storm Motion: `f_srh` durch `f_mls = 0 falls MLS < 7; sonst min(1.5, MLS/14)`.

**Bunkers et al. (2000), Wea. Forecasting 15, Gl. 1:**
```
V_mean  = 0–6-km-Mittelwind (nicht druckgewichtet)
V_shear = V(5,5–6 km) − V(0–0,5 km)
V_RM    = V_mean + 7,5 m/s · (V_shear × k̂)/|V_shear|
```

**Empfehlung: zwei Zahlen statt einer** — „Unwetterpotenzial" (WMAXSHEAR,
laut Taszarek 2020 in EU wie US anwendbar) neben „Tornado-Zusatz"
(SRH · LCL · MLS).

---

## 6. Korrigierte Schwellwerte

| Parameter | jetzt | Vorschlag |
|---|---|---|
| CAPE (ML) | ab 100 / opt. 800–2500 | ab 100 / **opt. 300–1500** |
| Scherung 0–6 km | ab 15 / opt. 20–32 | F2+: ab 15 / 20–30; **zusätzlich „irgendein Tornado": ab 10 / 14–22** |
| **NEU** Scherung 0–1 km | — | ab 6 / opt. 9–15 m/s |
| **NEU** SRH 0–1 km | — | ab 50 / opt. 90–200 m²/s² |
| CIN | zu ab −75 | **voll bis −50, null ab −200** |
| LCL | unter 1200 / 400–900 | **ML-LCL: unter 1400 / 500–1000** (oder SB-Werte um 280 m senken) |

**Unser Codekommentar ist zur Hälfte falsch.** „Europäische Tornados bei
niedrigem CAPE" stimmt. „hoher Scherung" ist widerlegt: Europa hat **auch
weniger** Scherung (0–1-km-BWD ⚠ ~9,5 gegen ~15,2 m/s in den USA). Die echte
europäische Signatur ist höheres 0–3-km-CAPE, steilere untere Lapse Rates und
schwächeres CIN.

Zur Einordnung, warum Umkalibrieren nicht optional ist: Der europäische
Median-STP bei F2–F3 liegt bei ⚠ ~0,10 gegen ~0,43 in den USA — bei einer
operationellen Schwelle von 1.

**Wichtig:** 89,9 % der deutschen Tornados sind F0/F1 (Beyer et al. 2025).
Unsere Schwellen sind auf die seltensten 10 % geeicht.

---

## 7. Verifikation — ein echter Fehler und eine strukturelle Grenze

**Rechenfehler in `abgleich.py`:** `treffer` zählt Fälle, `fehl` zählt
0,5°-Zelltage. Zwei verschiedene Grundgesamtheiten in einer Kontingenztafel →
FAR und CSI sind **keine wohldefinierten Größen**.

**Die Datenbank kann nie eine Kontingenztafel liefern:** `rechne_gitter.py`
schreibt nur TPI ≥ 25. Korrekte Nullvorhersagen fehlen physisch. Fix: Tagesmax
für **alle** ~185 Zellen mitschreiben (~4.400 Zeilen/Tag, wenige MB im Jahr).

**Strukturelle Grenze**, gemessen (216 Punkt-Tage): TPI ≥ 25 an 2,8 % der
Punkt-Tage → ~940 gewarnte Zelltage pro Sommerhalbjahr bei 25–45 Ereignissen.

| Ereignis-Zelltage | FAR mindestens | CSI höchstens |
|---|---|---|
| 25 | 0,973 | 0,027 |
| 45 | 0,952 | 0,048 |

**Das gilt bei perfekter Trefferquote.** FAR und CSI messen hier die Seltenheit
von Tornados, nicht die Güte des Index.

**Bessere Maße:** P(Tornado | TPI-Klasse) + ROC/AUC (schwellenfrei), Heidke
Skill Score, Reliability-Diagramm + Brier Skill Score, SEDI/EDI. CSI streichen
oder als „strukturell < 0,05" beschriften.

Radius 50 km / ±3 h ist gut gewählt (strenger als die Literatur), muss aber auf
der Fehlalarmseite **identisch** angewandt werden.

**Die Verifikation kann sofort beginnen:** ICON-Archiv ab 2023 + ESWD ab 2023
≈ 150 Fälle → ein Wochenende statt drei Jahre.

---

## 8. Die 48 historischen Fälle

**Als Kartenebene: behalten.** Die Legende ist bereits ehrlich.

**Für die Verifikation: unbrauchbar** — vier unabhängige Gründe: keine
Uhrzeiten (±3-h-Fenster nicht anwendbar), 40 von 48 vor dem ICON-Archiv,
Selektion auf F2+, Ortsfehler 10–30 km.

Verzerrungen: 34 von 48 sind F2+, obwohl 89,9 % aller deutschen Tornados F0/F1
sind. 60 % der Fälle nach 2000 — das misst Meldedichte, nicht Klima
(Groenemeijer & Kühne 2014: mittleres Jahr schwacher Fälle 1985, starker 1949).

**Zwei Ergänzungen für die Legende:**
- Wasserhosen fehlen — 36,6 % aller deutschen Meldungen, und die Nordseeküste
  ist mit 77,2 Tornados je 10.000 km² die dichteste Region des Landes.
- Bessere Quelle für „rund 45 pro Jahr": **Beyer, Wapler & Kühne (2025),
  Meteorol. Z. 34(4), DOI 10.1127/metz/1276** — 48,9 ± 20,3 Meldungen/Jahr,
  davon 31 über Land und 17,9 Wasserhosen; kein F4/F5 seit 2000.

---

## 9. Die fünf wichtigsten Maßnahmen

| # | Maßnahme | Aufwand | Nutzen |
|---|---|---|---|
| 1 | **Rückwirkende Verifikation** — ICON-Archiv gegen ESWD ab 2023; `abgleich.py` reparieren; Kopfmetrik auf P(Tornado \| Klasse) + AUC + Heidke | 1 Wochenende | **Höchster.** Macht aus der Behauptung eine geprüfte Größe — jetzt statt 2029 |
| 2 | **Konvektions-Gate** aus `lightning_potential`/`updraft` | ~20 Zeilen | Größter Fehlalarm-Hebel bei kleinstem Aufwand |
| 3 | **Echte Windprofile** — DLS, MLS, LLS, SRH, Bunkers | ~½ Tag | Ergänzt genau die Größen, die Tornado von Nicht-Tornado trennen |
| 4 | **Formel europäisch umeichen** (§5, §6) | ~2 h | Behebt Sättigung bei 100, nie schließenden Deckel, zu hohe CAPE-Normierung |
| 5 | **Zwei Zahlen statt einer** | ~2 h | Macht die Seite fachlich ehrlich |

**Zwei Dinge bleiben, wie sie sind:** das `-abs(cin)` und die Sprachregelung
„Potenzial" statt „Warnung".

---

## Offene Nebenpunkte

- **API-Budget klären, bevor Druckflächen dazukommen.** Frei: 600/min,
  10.000/Tag. Ob Open-Meteo pro Location oder pro HTTP-Anfrage zählt, ist
  entscheidend: 2596 Punkte × 8 Läufe wären ~20.800 gegen ~60 Calls/Tag.
  Saubere Lösung auf Sicht: ICON-D2-GRIB direkt vom DWD Open-Data-Server —
  kostenlos, kein Ratelimit, und die Nicht-Kommerziell-Klausel entfällt.
- `rechne_gitter.py` holt 72 h, die Seite zeigt 48 → ~40 % Nutzlast zu viel.
- `findZellen()`: Schwelle 20 gegen `LEVELS` 25 inkonsistent; Zellen sollten an
  das Konvektions-Gate gekoppelt und mit Bunkers-Zugvektor gezeichnet werden.
