#!/bin/sh
# ============================================================================
# FASE 0 — RUNDE 6, SKALLDEL  (kjoeres INNE i a0-containeren)
# ============================================================================
# Kun lesing: grep, env, cat. Ingen tilkoblinger, ingen skriving, ingen endring.
# Formaal: skille de to kandidataarsakene for D10 som SQL ikke kan skille.
#   Kandidat 1 — DB_HOST peker feil inne i containeren
#   Kandidat 2 — PGPASSWORD er tom naar jobbene kjoeres
#   sh phase0_round6_shell.sh > phase0_round6_shell.txt 2>&1
# ============================================================================
S=/a0/usr/projects/agent-zero_runtime_loop/scripts

echo "=== K1. DB_HOST / DB_PORT / PGPASSWORD slik skriptene definerer dem ==="
for f in container_candle_fetcher.py runa_cadence_executor.py step08_evidence_grading_v5.py; do
  echo "--- $f"
  grep -n "DB_HOST\|DB_PORT\|DB_NAME\|DB_USER\|PGPASSWORD\|password" "$S/$f" 2>/dev/null | head -12
done

echo
echo "=== K2. miljoeet slik cron gir det til jobbene ==="
echo "PGPASSWORD sett i dette skallet: $([ -n "$PGPASSWORD" ] && echo JA || echo NEI)"
echo "DB_HOST i dette skallet: '${DB_HOST}'"
echo "--- crontab-linjer som setter miljoe (ingen hemmeligheter skrives ut, kun noekkelnavn)"
crontab -l 2>/dev/null | grep -n "PGPASSWORD\|DB_HOST\|ENV\|export" | sed 's/=.*/=<verdi skjult>/' | head -20

echo
echo "=== K3. hva cadence-executor setter foer den starter en jobb ==="
grep -n "env\|Popen\|subprocess\|PGPASSWORD\|DB_HOST" "$S/runa_cadence_executor.py" 2>/dev/null | head -20

echo
echo "=== K4. hvem skriver run_failures naar jobbene selv ikke kommer inn? ==="
grep -rln "run_failures" "$S" 2>/dev/null | head -10

echo
echo "=== FERDIG. Returner hele outputen uendret. ==="
