#!/bin/bash
# Einmaliger Nachholer: wartet auf den Reset von Open-Meteos Tageskontingent
# (00:00 UTC) und rechnet dann das 15-km-Gitter neu.
#
# Hintergrund: am 06.08.2026 hat ein Testlauf mit --km 60 die Produktionsfassung
# von prototyp/daten/gitter.js überschrieben, und der Neuaufbau lief ins
# Kontingentende. Sobald einmal ein regulärer Lauf durch ist, kann diese Datei
# weg — der Workflow in .github/workflows/gitter.yml macht das dann alle 3 h.
set -u
HIER="$(cd "$(dirname "$0")" && pwd)"
LOG="$HIER/nachholen.log"

ziel=$(date -u -d "tomorrow 00:05" +%s)
jetzt=$(date -u +%s)
warte=$(( ziel - jetzt ))
[ "$warte" -lt 0 ] && warte=0

echo "$(date -u +%FT%TZ) warte ${warte}s auf Kontingent-Reset" >> "$LOG"
sleep "$warte"

for versuch in 1 2 3; do
    echo "$(date -u +%FT%TZ) Versuch $versuch" >> "$LOG"
    if python3 -u "$HIER/rechne_gitter.py" >> "$LOG" 2>&1; then
        echo "$(date -u +%FT%TZ) erfolgreich" >> "$LOG"
        exit 0
    fi
    echo "$(date -u +%FT%TZ) fehlgeschlagen, warte 30 min" >> "$LOG"
    sleep 1800
done
echo "$(date -u +%FT%TZ) aufgegeben" >> "$LOG"
exit 1
