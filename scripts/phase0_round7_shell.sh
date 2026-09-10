#!/bin/sh
# ============================================================================
# FASE 0 — RUNDE 7, SKALLDEL  (kjoeres INNE i a0-containeren via docker exec)
# ============================================================================
# Kun lesing. Avgjoer H-ENV (plan 17.2): hva setter <prosjekt>/.env for FHQ_DB_*?
# Ingen verdier for passord skrives ut — kun sha256, saa den kan sammenlignes med a942b37c.
#   docker exec 32477e7f9473 sh /host/runtime/phase0_round7_shell.sh > phase0_round7_shell.txt 2>&1
# ============================================================================
P=/a0/usr/projects/agent-zero_runtime_loop
E="$P/.env"

echo "=== P1. finnes .env, og naar ble den sist endret? ==="
if [ -f "$E" ]; then
  echo "EXISTS: yes"
  ls -l --time-style=+%Y-%m-%dT%H:%M:%S "$E" 2>/dev/null || ls -l "$E"
  echo "lines: $(wc -l < "$E")"
else
  echo "EXISTS: no  ($E)"
fi

echo
echo "=== P2. noekkelnavn i .env (kun navn, ingen verdier) ==="
[ -f "$E" ] && grep -v '^\s*#' "$E" | grep '=' | sed 's/=.*//' | sort

echo
echo "=== P3. FHQ_DB_HOST / PORT / USER / NAME slik .env setter dem (ikke hemmelige) ==="
[ -f "$E" ] && grep -E '^\s*FHQ_DB_(HOST|PORT|USER|NAME)=' "$E"

echo
echo "=== P4. sha256 av FHQ_DB_PASSWORD-verdien i .env (sammenlign med a942b37c...) ==="
if [ -f "$E" ] && grep -q '^\s*FHQ_DB_PASSWORD=' "$E"; then
  v=$(grep '^\s*FHQ_DB_PASSWORD=' "$E" | head -1 | sed 's/^[^=]*=//' | sed "s/^['\"]//; s/['\"]$//")
  printf '%s' "$v" | sha256sum | cut -c1-64
  echo "len: $(printf '%s' "$v" | wc -c)"
else
  echo "FHQ_DB_PASSWORD: not set in .env  -> skriptene bruker fallback"
fi

echo
echo "=== P5. hvordan autentiserer a0s eget psql? (pgpass / PGPASSFILE / PGSERVICE — kun eksistens) ==="
echo "HOME=$HOME"
[ -f "$HOME/.pgpass" ] && echo ".pgpass: exists ($(wc -l < "$HOME/.pgpass") lines)" || echo ".pgpass: none"
echo "PGPASSFILE: ${PGPASSFILE:-unset}  PGSERVICE: ${PGSERVICE:-unset}  PGHOST: ${PGHOST:-unset}"

echo
echo "=== P6. naar ble containeren startet, og ble noe restartet rundt 19:50 Oslo (17:50Z)? ==="
echo "container uptime:"; uptime 2>/dev/null
echo "now: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo
echo "=== FERDIG. Returner hele outputen uendret. ==="
