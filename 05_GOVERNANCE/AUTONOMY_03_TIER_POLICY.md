# AUTONOMI — DOKUMENT 3 av 3: FULLMAKTS-POLICY (tiers)

**Forfatter:** STIG · **Status:** UTKAST til VEGA · **Eier:** VEGA (governance); LARS for
retnings-grensene · **Dato:** 2026-09-10

Dette er regelen som bytter «spør mennesket hver gang» med «mennesket satte grensen én gang».
STIG-HOST leser denne fila hver kjøring og klassifiserer hver påtenkt handling i en tier.
**VEGA eier innholdet.** STIG leverer strukturen og et forslag; VEGA endrer, strammer eller
avviser.

---

## 1. Prinsippet

Tier bestemmes av to akser: **reversibilitet** og **skjema**. En handling er så høy tier som den
høyeste aksen tilsier.

| | `fhq_runtime`/`fhq_truth`/`fhq_features` (drift) | `fhq_control` (fabrikk/logg) | `fhq_governance`/`fhq_meta`/`fhq_research` |
|---|---|---|---|
| **Reversibel** | Tier 0 | Tier 1 | **Tier 2** |
| **Irreversibel** | Tier 1 | Tier 2 | **Tier 2** |

Skriving til styringsskjema er **alltid Tier 2**, uansett reversibilitet. Det er CLAUDE.md-regelen,
uendret.

## 2. Tier 0 — autonomt, logg i etterkant

Systemet handler selv og skriver `autonomy_ledger`. Ingen varsling nødvendig.

**Tillatt:**
- `GRANT`/`REVOKE` på drift-objekter (`fhq_runtime`, `fhq_truth`, `fhq_features`, `fhq_regime`,
  `fhq_decide`, `fhq_hypothesis`, `fhq_perception`) **når `run_registry` erklærer relasjonen** i
  `reads_from`/`writes_to`. Dette dekker alle de ti GRANT-passene fra § 20 unntatt ett.
- Restart av en registrert, `ENABLED` jobb som har feilet med en kjent, forbigående feil.
- Fjerne en åpenbar teknisk defekt med presedens (f.eks. logg-kapping, § 20.2) i en drift-fil.

**Grense:** hjemmel må finnes i `run_registry` eller en ADR. Uten hjemmel → Tier 2.

## 3. Tier 1 — handl, logg, veto-vindu

Systemet handler, skriver `autonomy_ledger` med `veto_deadline = now()+24t`, og tar handlingen
med i CEO-sammendraget. CEO kan omgjøre innen vinduet via `revert_command`.

**Tillatt:**
- Credential-/`.env`-fiks på drift-siden (som § 16.7/§ 18) når verdien verifiseres mot
  containerens sannhet.
- Brannmur-/nettverksregel på verten (som § 20.3).
- `GRANT` på et **nytt** drift-skjema som ennå ikke er sett, når en registrert jobb feiler på det.
- `str_replace`-nivå kodefiks i en drift-fil med backup og `py_compile`-verifisering.

**Grense:** må være reversibel og ha `revert_command`. Bred flate (mange filer/rader) → hev til
Tier 2 selv om hver enkelt er liten.

## 4. Tier 2 — hard stopp, G4

Systemet handler **ikke**. Det skriver en `PENDING_G4`-rad og eskalerer til CEO/VEGA/LARS med
navn på beslutningen.

**Alltid Tier 2:**
- Enhver skriving (`GRANT INSERT/UPDATE/DELETE`, `INSERT`, `UPDATE`, DDL) i `fhq_governance`,
  `fhq_meta`, `fhq_research`. `baseline_controls_v5` (§ 20.11) var dette.
- Endring av CLAUDE.md, en ADR, en EC, eller tier-policyen selv.
- Å drepe eller pause et helt system/en hel jobb-klasse.
- Å reversere en LARS-ruling (f.eks. `llm_probe_on_empty_queue`, § 22.7, spak B).
- Fabrikk-tilførsel / hypotese-frysing (§ 22.7, spak A) — retning, LARS eier den.
- Å plassere dom-til-score-broen (§ 22.5) i drift — se seksjon 5.
- Alt irreversibelt, uansett skjema.

## 5. To grenser bare LARS/VEGA kan sette (åpne spørsmål i denne policyen)

1. **Er lærings-ledgerne (`brier_score_ledger`, `lvi_canonical`, `outcome_ledger`) Tier 2?** De
   ligger i `fhq_governance`/`fhq_learning`, så etter regelen er de Tier 2. Men da kan
   dom-til-score-broen (§ 22.5) aldri kjøre autonomt, og læringsløkka forblir manuell. **VEGAs
   valg:** enten (a) hold dem Tier 2 og aksepter at scoring krever menneske, eller (b) erklær
   *append-only scoring-skriving* til disse tre tabellene som Tier 1 under en egen regel, slik at
   broen kan kjøre og logge, men aldri endre eller slette en score. Anbefaling: (b), fordi en
   score som bare kan legges til, aldri endres, er selv en falsifiserings-disiplin.
2. **Hvor stor kvote får fabrikk-tilførselen?** Hvis LARS åpner spak A (frysing) under en kvote,
   blir frysing opp til N hypoteser per døgn Tier 1. LARS setter N. Uten en kvote forblir det
   Tier 2 per handling.

## 6. Hva VEGA må gjøre

1. Godkjenne, endre eller avvise tabellen i seksjon 1 og listene i 2–4.
2. Svare på de to grensene i seksjon 5.
3. Bekrefte at policyen selv er Tier 2 å endre (så en agent aldri kan utvide sin egen fullmakt).

Når VEGA har svart, låser STIG policyen som en versjonert fil agenten leser, og leverer
`run_stig_host.ps1` (dokument 2) som håndhever den.
