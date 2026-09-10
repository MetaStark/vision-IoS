# AUTONOMI — DOKUMENT 2 av 3: STIG-PÅ-VERTEN (headless, planlagt)

**Forfatter:** STIG · **Status:** UTKAST til gjennomlesing · **Krever:** CEO starter den; ingen
G4 for selve oppsettet, men agentens skrive-fullmakt gjelder bare Tier 0/1 til policyen
(dokument 3) er på plass · **Dato:** 2026-09-10

Dette fjerner mellommann-rollen. Agenten kjører **der databasen er**, på verten, uten en chat å
relé-e. Den våkner på et intervall, leser tilstand, handler innenfor fullmakten, logger til
`autonomy_ledger`, og eskalerer bare Tier 2 til CEO.

---

## 1. Hva den er

Claude Code kjørt headless på Windows-verten, planlagt via Windows Task Scheduler (samme sted
`RUNA-CADENCE-EXECUTOR` og fabrikk-ticken allerede lever). Den har `psql`, `docker` og
`D:\Runtime` rett foran seg og trenger ingen nettvei inn til databasen.

## 2. Oppsett (CEO kjører én gang)

```powershell
# 1. Installer Claude Code CLI på verten (én gang). Se docs; deretter:
cd C:\fhq-market-system\vision-ios

# 2. Fast, ren arbeidskopi for agenten (unngår de 30 divergerende filene, § 20.8):
git worktree add D:\stig-host claude/explain-learning-loop-Sa9z7

# 3. Legg agentens fullmakt og systemprompt (fra denne mappen) i worktreen:
#    05_GOVERNANCE/AUTONOMY_02_HOST_AGENT_SETUP.md  (denne fila, seksjon 4 er systemprompten)
#    05_GOVERNANCE/AUTONOMY_03_TIER_POLICY.md       (leses av agenten hver tick)

# 4. Planlagt kjøring hvert 15. minutt, forskjøvet fra fabrikk-ticken (som går 4-59/15):
schtasks /Create /SC MINUTE /MO 15 /TN "STIG-HOST" /RU SYSTEM ^
  /TR "powershell -NoProfile -ExecutionPolicy Bypass -File D:\stig-host\run_stig_host.ps1"
```

## 3. `run_stig_host.ps1` (wrapper, STIG leverer i neste ledd)

Wrapperen: setter `PGPASSWORD` fra Machine-scope (nå riktig, § 18.8), setter
`default_transaction_read_only=on` for lesefasen, kaller Claude Code headless med systemprompten
under, fanger exit-kode og skriver en `autonomy_ledger`-rad selv hvis agenten krasjer (ingen
stille feil).

## 4. Systemprompt for STIG-HOST (utkast)

> Du er STIG-HOST, driftsgrenen av STIG, som kjører på FjordHQ-verten der databasen lever.
> Du opererer under CLAUDE.md og fullmakts-policyen i `05_GOVERNANCE/AUTONOMY_03_TIER_POLICY.md`,
> som du leser først hver kjøring.
>
> **Hver kjøring:**
> 1. Les tilstand (kun lesing): `run_attempts` siste 30 min, `run_failures` siste 30 min,
>    `autonomy_ledger` PENDING/veto-vindu, fabrikkens `factory_cycles` heartbeat.
> 2. Finn avvik: døde jobber, rettighetsnekt, sultet fabrikk, brutt kjede.
> 3. For hvert avvik, klassifiser tier mot policyen.
>    - **Tier 0:** utfør. Skriv INTENT- og RESULT-rad til `autonomy_ledger`.
>    - **Tier 1:** utfør, skriv radene med `veto_deadline = now()+24t`, varsle CEO i sammendraget.
>    - **Tier 2:** IKKE utfør. Skriv en `PENDING_G4`-rad og ta den med i sammendraget til CEO.
> 4. Skriv et kort sammendrag til `D:\stig-host\digest\STIG_HOST_{yyyyMMddHHmm}.md`: hva jeg
>    gjorde (Tier 0/1), hva som venter på deg (Tier 2), og systemets helse i tre tall.
>
> **Forbud (arves fra CLAUDE.md):** ingen skriving til `fhq_governance`/`fhq_meta`/`fhq_research`
> uten G4 (alltid Tier 2). Ingen DDL uten G4. Ingen sletting av data. Ingen antagelser — verifiser
> mot `information_schema` før du konkluderer med at noe mangler. Ingen stille feil.
>
> **Grensen din:** du reparerer drift, du eier ikke retning. Fabrikk-tilførsel, læringsmodell og
> alt strategisk er LARS'. Du foreslår, du bygger ikke uten ordre.

## 5. Hvorfor dette er trygt

- Agenten skriver bare det tier-policyen tillater; alt annet blir en `PENDING_G4`-rad, ikke en
  handling.
- Hver handling er i `autonomy_ledger` med `revert_command`. CEO kan omgjøre alt Tier 1 innen
  vinduet.
- Worktreen (`D:\stig-host`) er isolert fra vertens divergerende arbeidskopi (§ 20.8), så
  agenten jobber mot en ren, kjent tilstand.
- Read-only-fasen først betyr at agenten aldri handler på en tilstand den ikke har lest.

## 6. Hva CEO må gjøre

1. Installere Claude Code CLI på verten.
2. Kjøre de fire kommandoene i seksjon 2.
3. Lese det første `digest`-sammendraget og bekrefte at Tier 0/1-handlingene ser riktige ut,
   før intervallet får løpe fritt.

STIG leverer `run_stig_host.ps1` og en låst fullmakts-fil i neste ledd, etter at policyen
(dokument 3) er godkjent av VEGA.
