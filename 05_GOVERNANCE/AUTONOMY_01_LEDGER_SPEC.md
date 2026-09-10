# AUTONOMI — DOKUMENT 1 av 3: REGISTER-SPEC (`autonomy_ledger`)

**Forfatter:** STIG · **Status:** UTKAST til gjennomlesing · **Krever:** G4 for å opprette
tabellen (den ligger i `fhq_control`) · **Dato:** 2026-09-10

Dette er sannhetskilden for autonom styring. Hver handling en autonom agent gjør skriver
nøyaktig én rad her, **før** handlingen for intensjon og **etter** for resultat (samme
`action_id`, to statuser). Uten en rad her skjedde ikke handlingen. Det er dette registeret som
lukker D19 (to styringssystemer uten felles logg) og som dashboardet i dokument 2 leser.

---

## 1. Skjema

```sql
-- KREVER G4. Opprettes av supabase_admin. Ligger bevisst i fhq_control (drift), ikke
-- fhq_governance, fordi agenter skal kunne skrive den selv under Tier 0/1; radene ER loggen,
-- ikke konstitusjon.
CREATE TABLE IF NOT EXISTS fhq_control.autonomy_ledger (
  action_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at       timestamptz NOT NULL DEFAULT now(),
  agent            text    NOT NULL,          -- 'STIG-HOST', 'a0-runtime', 'FINN', ...
  session_ref      text,                       -- agentens økt-/kjøre-id
  tier             smallint NOT NULL CHECK (tier IN (0,1,2)),
  phase            text    NOT NULL CHECK (phase IN ('INTENT','RESULT')),
  action_kind      text    NOT NULL,          -- 'GRANT','RESTART_JOB','ENV_FIX','DB_WRITE',...
  target           text    NOT NULL,          -- objektet, f.eks. 'fhq_runtime.run_locks'
  reason           text    NOT NULL,          -- hvorfor, i klartekst
  basis_ref        text,                       -- hjemmel: run_registry-rad, ADR, CEO-DIR, ruling
  hash_before      text,                       -- sha256 av relevant tilstand før (kan være NULL)
  hash_after       text,                       -- sha256 etter (fylles i RESULT-raden)
  outcome          text    CHECK (outcome IN ('OK','FAILED','VETOED','PENDING_G4')),
  reversible       boolean NOT NULL DEFAULT true,
  revert_command   text,                       -- eksakt kommando som omgjør handlingen
  veto_deadline    timestamptz,                -- for Tier 1: frist for etterhånds-veto
  correlation_id   text                        -- knytter INTENT- og RESULT-rad + relaterte
);

CREATE INDEX IF NOT EXISTS idx_autonomy_ledger_created ON fhq_control.autonomy_ledger (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_autonomy_ledger_tier    ON fhq_control.autonomy_ledger (tier, outcome);
CREATE INDEX IF NOT EXISTS idx_autonomy_ledger_pending ON fhq_control.autonomy_ledger (outcome) WHERE outcome = 'PENDING_G4';
```

## 2. Protokoll (hvordan en agent bruker den)

1. **Før handling:** skriv en `INTENT`-rad med `tier`, `action_kind`, `target`, `reason`,
   `basis_ref`, `hash_before`, `reversible`, `revert_command`, og et friskt `correlation_id`.
2. **Tier-sjekk:** les tier-policyen (dokument 3). Er handlingen Tier 2, sett `outcome =
   'PENDING_G4'` og **stopp** — et menneske må godkjenne. Tier 0/1: fortsett.
3. **Utfør handlingen.**
4. **Etter handling:** skriv en `RESULT`-rad med samme `correlation_id`, `hash_after`,
   `outcome` (`OK`/`FAILED`), og for Tier 1 en `veto_deadline` (f.eks. now() + 24t).
5. **Ved feil:** `outcome='FAILED'`, full feiltekst i `reason`. Ingen stille feil (ADR-013).

## 3. Court-proof-egenskaper

- **Hver handling har hjemmel.** `basis_ref` peker på det som autoriserte den: en
  `run_registry.writes_to`-erklæring, en ADR, en CEO-DIR, en LARS-ruling. Handlinger uten
  hjemmel er per definisjon Tier 2.
- **Hver handling er reversibel eller merket irreversibel.** `revert_command` er den eksakte
  strengen som omgjør den. Tier 0/1 krever `reversible = true`.
- **Ingenting er skjult.** a0-runtime og STIG-host skriver til samme tabell. Det er slutten på
  «to styringssystemer».

## 4. Hva CEO/VEGA må avgjøre (G4)

1. Godkjenne opprettelsen av tabellen i `fhq_control`.
2. Bekrefte at loggen selv er Tier 0 å skrive til (ellers kan ingen agent logge autonomt).
3. Sette standard `veto_deadline`-vindu for Tier 1 (forslag: 24 timer).

## 5. Migrasjon (klar, kjøres først etter G4)

Leveres som `04_DATABASE/MIGRATIONS/178_autonomy_ledger.sql` når G4 er gitt. Ikke opprettet nå.
