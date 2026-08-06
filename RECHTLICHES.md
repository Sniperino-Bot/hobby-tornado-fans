# Rechtsprüfung — Hobby Tornado Fans

Stand: 06.08.2026

**Vorweg, damit es klar ist:** Ich bin kein Anwalt, und das hier ist keine
Rechtsberatung. Es ist eine sorgfältige Bestandsaufnahme dessen, was bei einer
deutschen Hobbyseite dieser Art typischerweise zählt, mit den Stellen, die ich
im Code und in den Datenquellen tatsächlich nachgesehen habe. Vor dem
Öffentlichgehen sollte ein Fachkundiger draufschauen — besonders auf Impressum
und Datenschutzerklärung.

---

## 1. Was technisch geprüft wurde

Ich habe die gebaute Seite auf ausgehende Verbindungen und Speicherzugriffe
durchsucht. Befund:

| Prüfung | Ergebnis |
|---|---|
| Nachgeladene fremde Ressourcen (Skripte, Schriften, Bilder) | **keine** |
| Cookies, `localStorage`, `sessionStorage` | **keine** |
| Tracking, Statistik, Analysewerkzeuge | **keine** |
| Externe Schriftarten (z. B. Google Fonts) | **keine** — nur Systemschriften |
| Ausgehende Verbindungen zur Laufzeit | **eine**, `api.open-meteo.com`, und nur im Rückfallbetrieb |
| Links nach außen | 4 Stück (dwd.de, open-meteo.com, geonames.org, Wikipedia) — reine Verweise, kein Nachladen |

Das ist eine ungewöhnlich saubere Ausgangslage. Der wichtigste Punkt: Im
Normalbetrieb kommen die Wetterdaten vorberechnet vom eigenen Server, es fließt
also **gar nichts** an Dritte.

## 2. Einwilligungsbanner (Cookie-Banner)

**Nicht erforderlich.** § 25 TDDDG verlangt eine Einwilligung nur für das
Speichern von Informationen im Endgerät oder den Zugriff darauf. Die Seite tut
beides nicht. Ein Banner wäre hier sogar irreführend.

## 3. Impressum (§ 5 DDG)

Das TMG ist im Mai 2024 vom **Digitale-Dienste-Gesetz (DDG)** abgelöst worden;
die Impressumspflicht steht jetzt in § 5 DDG. Sie trifft „geschäftsmäßige, in
der Regel gegen Entgelt angebotene" Dienste.

Rein private Seiten für Familie und Freunde sind ausgenommen. **Deine Seite ist
das nicht** — sie richtet sich an eine unbestimmte Öffentlichkeit von
Sturmjägern. Solche Angebote werden regelmäßig als über das rein Private
hinausgehend eingestuft. Dazu kommt: Sobald Werbung eingeblendet oder sonst
Geld verdient wird, ist die Geschäftsmäßigkeit eindeutig gegeben.

**Empfehlung:** Impressum setzen. Es kostet nichts und beseitigt das
Abmahnrisiko. Ein ausgefülltes Gerüst steht in der Seite (`#impressum`),
Platzhalter sind orange markiert. Erforderlich: Name, ladungsfähige Anschrift
(kein Postfach), E-Mail-Adresse.

## 4. Datenschutzerklärung (Art. 13 DSGVO)

**Erforderlich**, sobald die Seite erreichbar ist — allein weil der Hoster
IP-Adressen protokolliert. Ein Entwurf steht in der Seite (`#datenschutz`).
Zwei Stellen musst du selbst füllen:

- **Hoster eintragen.** Bei GitHub Pages: GitHub Inc., USA — Drittlandtransfer,
  gestützt auf das EU-US Data Privacy Framework.
- **Verantwortlicher**: Name und Anschrift wie im Impressum.

Der Rückfall-Abruf bei Open-Meteo (Schweiz) ist beschrieben. Die Schweiz hat
einen Angemessenheitsbeschluss, das ist unproblematisch.

## 5. Abgrenzung zu amtlichen Warnungen — der wichtigste Punkt

Amtliche Warnungen vor Wettergefahren sind nach **§ 4 DWD-Gesetz** Aufgabe des
Deutschen Wetterdienstes. Private dürfen eigene Einschätzungen veröffentlichen,
aber sie dürfen nicht den Eindruck einer amtlichen Warnung erwecken.

Umgesetzt ist das an vier Stellen:

1. Der Name **„Hobby Tornado Fans"** macht die Nicht-Amtlichkeit sofort klar.
2. Die Leiste unter der Karte: „Für Sturmjäger und Wetterfans · **keine amtliche
   Warnung** · offizielle Warnlage: dwd.de".
3. Der orange Kasten im Fuß mit dem Verweis auf dwd.de und NINA.
4. Kein Behörden-Look, keine Ampelfarben im DWD-Stil, kein Wort „Warnung" in
   der Bedienoberfläche — es heißt durchgehend „Potenzial".

**Was du unbedingt lassen solltest:** amtliche DWD-Warnungen einbinden und wie
eigene darstellen, Begriffe wie „Warnstufe" oder „Unwetterwarnung" verwenden,
oder Push-Benachrichtigungen verschicken, die wie Warnungen aussehen.

## 6. Datenquellen und Lizenzen

| Quelle | Lizenz | Auflage | Erfüllt |
|---|---|---|---|
| Open-Meteo (Wetterdaten) | CC BY 4.0 | Namensnennung + Lizenzhinweis | ✅ im Fuß |
| Open-Meteo (die API selbst) | kostenlos **nur nicht-kommerziell** | keine Werbung, kein Verkauf | ⚠️ siehe unten |
| DWD ICON (Modell dahinter) | CC BY 4.0 / GeoNutzV | Quellenangabe | ✅ im Fuß |
| deutschlandGeoJSON / BKG | DL-DE/BY-2.0 | Namensnennung | ✅ im Fuß |
| GeoNames (Ortschaften) | CC BY 4.0 | Namensnennung | ✅ im Fuß |
| Wikipedia (Tornado-Liste) | CC BY-SA 4.0 | Namensnennung + Weitergabe unter gleicher Lizenz | ✅ im Fuß und im Haftungsteil |

⚠️ **Der eine echte Stolperstein:** Die kostenlose Open-Meteo-Schnittstelle ist
auf nicht-kommerzielle Nutzung beschränkt. Solange die Seite werbefrei bleibt
und nichts verkauft, passt das. **Sobald du Werbung schaltest oder Geld
nimmst, brauchst du einen kostenpflichtigen Open-Meteo-Tarif** — und dann greift
zugleich die Impressumspflicht ohne jeden Zweifel.

### Der Ausweg: DWD Open Data (geprüft 06.08.2026)

Beschlossen ist, mit Maßnahme 3 aus `PLAN.md` auf **ICON-D2-GRIB direkt vom DWD
Open-Data-Server** (`opendata.dwd.de/weather/nwp/icon-d2/grib/`) umzuziehen.
Damit fällt der Stolperstein oben weg:

- **Entgeltfrei, ohne Registrierung, ohne Ratelimit** — Grundlage ist die
  Novelle des DWD-Gesetzes von 2017.
- **Kommerzielle Nutzung ausdrücklich erlaubt.** Die Geodaten stehen unter
  **CC BY 4.0** bzw. GeoNutzV. Werbung und Verkauf sind damit möglich, ohne
  einen Tarif zu kaufen.
- **Pflicht ist ein Quellenvermerk**, und zwar auch bei Auszügen und bei
  Formatwechseln (§ 7 DWD-Gesetz, § 3 GeoNutzV). Weil wir die Daten
  **verändern** — der TPI ist ein eigener Index daraus —, muss der Vermerk das
  kenntlich machen. Formulierung: **„Datenbasis: Deutscher Wetterdienst, eigene
  Elemente ergänzt"**. Gehört dann in den Quellenblock der Seite.
  Maßgeblich ist der Wortlaut unter
  <https://www.dwd.de/DE/service/rechtliche_hinweise/rechtliche_hinweise.html> —
  vor dem Umzug dort gegenlesen.

Was der Umzug **nicht** löst:

- **Kein Archiv.** Der Server hält nur die letzten acht Läufe, also rund 24
  Stunden. Die rückwirkende Verifikation (Maßnahme 1) braucht weiterhin
  Open-Meteos `historical-forecast-api`, und damit dort weiterhin die
  Nicht-Kommerziell-Klausel — allerdings nur für die private Auswertung im
  Hinterzimmer, nicht für die veröffentlichte Seite.
- **§ 4 DWDG bleibt.** Amtliche Warnungen sind Sache des DWD. An der
  Sprachregelung „Potenzial" statt „Warnung" ändert der Umzug nichts.
- Solange Open-Meteo im Live-Rückfallpfad der Seite steckt, gilt dessen Klausel
  weiter. Bei einem kommerziellen Betrieb muss dieser Pfad mit umgezogen oder
  abgeschaltet werden.

### Bewusst nicht verwendet

- **tornadoliste.de** (Thomas Sävert): Im Impressum ausdrücklich geregelt —
  Vervielfältigung, Verarbeitung und **Speicherung in Datenbanken** sind
  untersagt, Nutzung nur privat und nicht-kommerziell. Eine Übernahme in diese
  Seite wäre eine Urheberrechts- und Datenbankrechtsverletzung
  (§§ 87a ff. UrhG). **Nicht anfassen.**
- **ESWD** (European Severe Weather Database): eigene Lizenzbedingungen, keine
  freie Weiterverwendung. Für die private Auswertung in `bestaetigt.csv`
  vertretbar, für eine Veröffentlichung nicht ohne Klärung.

Deshalb kommt die Tornado-Liste aus der Wikipedia. Sie ist dafür ausdrücklich
nur eine **Auswahl** (im Wesentlichen F2–F5), keine Vollzählung — Deutschland
hat im Mittel rund 45 Tornados im Jahr, die meisten schwach. Das steht so in der
Legende und im Haftungsteil, damit niemand die 48 Punkte für die ganze
Wirklichkeit hält.

## 7. Barrierefreiheit (BFSG)

Das Barrierefreiheitsstärkungsgesetz gilt seit dem 28.06.2025, richtet sich aber
an Produkte und Dienstleistungen **für Verbraucher im geschäftlichen Verkehr**
(insbesondere Onlinehandel). Eine kostenlose, private Informationsseite ohne
Verkauf und ohne Vertragsschluss fällt nicht darunter. Auch die Pflichten für
öffentliche Stellen (BITV 2.0) greifen nicht.

Unabhängig davon: Die Karte ist als Canvas-Grafik für Screenreader unzugänglich.
Rechtlich derzeit kein Problem, praktisch eine Einschränkung. Falls dir das
wichtig ist, wäre eine textliche Tabelle der Werte je Region die naheliegende
Ergänzung.

## 8. Was noch offen ist

1. **Impressum und Datenschutzerklärung ausfüllen** — die Platzhalter sind
   orange markiert und nicht zu übersehen.
2. **Hoster eintragen**, sobald entschieden.
3. **Werbefrei bleiben**, solange Open-Meteo kostenlos genutzt wird — oder den
   Umzug auf DWD Open Data vorziehen (§ 6, „Der Ausweg"). Dann ist Werbung und
   Verkauf zulässig, es kommt aber der Quellenvermerk „Datenbasis: Deutscher
   Wetterdienst, eigene Elemente ergänzt" als Pflicht dazu.
4. Falls eine eigene Domain dazukommt: Impressum muss von jeder Seite aus in
   zwei Klicks erreichbar sein — über den Fuß ist das erfüllt.
5. Vor dem Öffentlichgehen einmal juristisch gegenlesen lassen.
