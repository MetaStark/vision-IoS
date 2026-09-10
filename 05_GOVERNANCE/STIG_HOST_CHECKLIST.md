# HUSKELISTE — slå på autonomi, ett steg av gangen

Du trenger ikke gjøre alt på én gang. Hvert steg står for seg. Ingenting haster; systemet
kjører allerede.

---

## STEG 1 — Helsevakt på din maskin (5 minutter, ingen godkjenning trengs)

Dette fjerner mellommann-rollen for overvåking. En les-bare rapport skriver seg selv hvert 15.
minutt. Den rører aldri databasen, så du trenger verken G4 eller VEGA.

**1a. Hent skriptet til `D:\Runtime`:**
```
cd C:\fhq-market-system\vision-ios
git fetch origin claude/explain-learning-loop-Sa9z7
cmd /c "git show origin/claude/explain-learning-loop-Sa9z7:scripts/stig_host_watch.ps1 > D:\Runtime\stig_host_watch.ps1"
```

**1b. Prøv den én gang:**
```
powershell -ExecutionPolicy Bypass -File D:\Runtime\stig_host_watch.ps1
```
Du får én linje på skjermen og en fil i `D:\Runtime\digest\`. Åpne fila. Ser du helsen? Da virker
det.

**1c. La den kjøre av seg selv hvert 15. minutt (ett administrator-vindu):**
```
schtasks /Create /SC MINUTE /MO 15 /TN "STIG-HOST-WATCH" /RU SYSTEM /TR "powershell -NoProfile -ExecutionPolicy Bypass -File D:\Runtime\stig_host_watch.ps1"
```
Ferdig. Fra nå av ligger det alltid en fersk helserapport i `D:\Runtime\digest\`. Du leser den
når du vil, i stedet for å kopiere kommandoer til meg.

**For å stoppe den senere:** `schtasks /Delete /TN "STIG-HOST-WATCH" /F`

---

## STEG 2 — La VEGA lese nivå-policyen (en beslutning, ikke en kommando)

Åpne `05_GOVERNANCE/AUTONOMY_03_TIER_POLICY.md`. VEGA svarer på to spørsmål i seksjon 5:
skal systemet få skrive resultater til den ene læringsloggen selv, og hvor mye nytt arbeid får
fabrikken lage per døgn. Når VEGA har svart, låser jeg policyen.

---

## STEG 3 — Den skrivende agenten (etter steg 2 + G4 på loggtabellen)

Dette er den fulle versjonen: en agent som ikke bare ser, men også reparerer drift selv, innenfor
VEGAs grenser, og sender deg bare de store beslutningene. Den krever at loggtabellen
(`autonomy_ledger`) er opprettet med G4, og at policyen fra steg 2 er låst. Når begge er på
plass, leverer jeg oppsettet, og du kjører fire kommandoer som i dokument 2.

---

## STEG 4 — Slå læringen på igjen (LARS bestemmer)

Fabrikken tester ideer, men lærer ikke før resultatene kobles tilbake. LARS velger hvordan den
mates (spak A eller B i plan-dokumentet § 22.7). Det er en retningsbeslutning, ikke en fiks.

---

**Rekkefølge:** steg 1 nå, når du vil. Steg 2–4 når de rette personene er klare. Du taper
ingenting på å ta dem én etter én.
