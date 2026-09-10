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

## 5. Forhold til eksisterende logg-tabeller (jordet av a0, § 23.7)

a0s verifisering fant **35 beslektede tabeller**. To er nære nok til at `autonomy_ledger` må
avgrenses mot dem, ellers blir den et tredje styringssystem, akkurat det D19 advarer mot:

- **`fhq_governance.audit_log`** (19 kolonner, hash-kjede, `event_hash`, `signature`,
  `governance_gate`, `adr_reference`, 60 rader). Dette er den **governance-signerte** hendelses-
  loggen: kun `postgres` skriver den, så agenter *kan ikke*. Den er Tier 2 per natur.
- **`fhq_governance.autonomy_clock_history` / `_state` / `_halt_triggers`**: autonomi-klokkens
  tidslinje og stopp-utløsere, også governance-eid.

**Avgrensning:** `autonomy_ledger` er ikke en erstatning for `audit_log`. Den er
komplementær: `audit_log` fanger *konstitusjonelle, signerte* hendelser (Tier 2, menneske/
postgres); `autonomy_ledger` fanger *operasjonelle agent-handlinger* (Tier 0/1) i `fhq_control`,
**der agenten faktisk har INSERT** (a0 bekreftet 7/7 tabeller). En Tier 2-handling skriver en
`PENDING_G4`-rad i `autonomy_ledger` *og* ender, når mennesket godkjenner, som en signert rad i
`audit_log`. De to loggene møtes på `correlation_id`. Det er slik de to styringssystemene blir
til ett revidert spor, ikke tre.

## 6. Jordede fakta (a0, § 23.7)

- **UUID:** `gen_random_uuid()` er innebygd i `pg_catalog` (PG13+) *og* via pgcrypto 1.3, i aktiv
  bruk som default i 10+ tabeller. `DEFAULT gen_random_uuid()` er trygt uten ekstra avhengighet.
- **Skrive-rolle:** lease-rollen har `USAGE` på `fhq_control` og `INSERT+SELECT` på alle 7
  tabeller der, ingen `DELETE`. `autonomy_ledger` samme skjema = agenten kan skrive den. Men
  lease-rollen kan **ikke lese** `fhq_learning`/`fhq_governance`-ledgerne (D20) — det påvirker
  dom-til-score-broen, ikke loggen.

## 7. Migrasjon (klar, kjøres først etter G4)

Leveres som `04_DATABASE/MIGRATIONS/178_autonomy_ledger.sql` når G4 er gitt. Ikke opprettet nå.
Bør vurdere å arve `audit_log`s `event_hash`/`signature`-mønster for Tier 1/2-rader, så en
autonom handling kan kjede-signeres på samme måte som en governance-hendelse.
