# HMM REGIME RAPPORT - FjordHQ Vision-IoS

**Dato:** 2025-12-14
**Kilde:** fhq_perception schema
**IoS-003 Status:** G1_TECHNICAL_VALIDATION_PASS
**Generert av:** STIG (EC-003)

---

## 1. OVERSIKT

### Datasett-statistikk

| Tabell | Records | Aktiva | Periode |
|--------|---------|--------|---------|
| regime_daily | 126,362 | 466 | 2016-08-29 → 2025-12-13 |
| sovereign_regime_state_v4 | 117,497 | 466 | 2024-12-25 → 2025-12-11 |
| hmm_features_daily | 10,136 | 4 | 2016-08-29 → 2025-12-13 |
| hmm_model_params_v4 | 11 | - | - |
| hmm_v4_config | 3 | - | - |

### Tabeller i fhq_perception (15 totalt)
`anomaly_log`, `bocd_changepoint_log`, `g0_constraints_verification`, `hmm_features_daily`, `hmm_features_v4`, `hmm_model_params_v4`, `hmm_v4_config`, `intent_reports`, `regime_daily`, `regime_v2_to_v4_mapping`, `shock_reports`, `snapshots`, `sovereign_regime_state`, `sovereign_regime_state_v4`, `state_vectors`

---

## 2. HMM V4 KONFIGURASJON

### Asset Class Settings

| Asset Class | States | Emission | IOHMM | Learning Rate | Hazard | Hysteresis | State Labels |
|-------------|--------|----------|-------|---------------|--------|------------|--------------|
| CRYPTO | 4 | student_t | Yes | 0.0200 | 0.0200 | 3 days | BULL, NEUTRAL, BEAR, STRESS |
| FX | 3 | student_t | Yes | 0.0100 | 0.0100 | 5 days | BULL, NEUTRAL, BEAR |
| EQUITIES | 4 | student_t | Yes | 0.0100 | 0.0100 | 5 days | BULL, NEUTRAL, BEAR, STRESS |

### Feature Input

**Technical Features (alle asset classes):**
- `return_z`, `volatility_z`, `drawdown_z`, `macd_diff_z`, `bb_width_z`, `rsi_14_z`, `roc_20_z`

**Macro Covariates:**
- FX/EQUITIES: `yield_spread_z`, `vix_z`, `inflation_z`, `liquidity_z`
- CRYPTO: `vix_z`, `liquidity_z`

**Crypto-spesifikke features:**
- `onchain_hash_z`, `onchain_tx_z`

**IOHMM Transition Covariates (alle modeller):**
- `yield_spread_z`, `vix_z`, `liquidity_z`

---

## 3. MODELL-PARAMETERE

### Trente Modeller (trained_on_rows > 1000)

| Asset Class | States | Trained Rows | Learning Rate | Hazard Rate | Engine |
|-------------|--------|--------------|---------------|-------------|--------|
| EQUITIES | 4 | 95,410 | 0.0010 | 0.0100 | v4.0.0 |
| CRYPTO | 4 | 15,874 | 0.0010 | 0.0100 | v4.0.0 |
| FX | 3 | 6,213 | 0.0010 | 0.0100 | v4.0.0 |
| EQUITIES | 4 | 1,200 | 0.0030 | 0.0100 | v4.0.0 |
| CRYPTO | 4 | 1,044 | 0.0071 | 0.0100 | v4.0.0 |

### Emission Parameters (CRYPTO hovedmodell, 4 states)

**Emission Mu (mean per state x 7 features):**
- State 0 (BULL): [0.37, -0.36, -0.16, 1.03, 0.16, 1.55, 1.57]
- State 1 (NEUTRAL): [0.06, -0.34, -0.40, 0.14, -0.59, 0.12, 0.16]
- State 2 (BEAR): [-0.20, -0.51, -0.76, -0.51, -0.23, -0.87, -0.45]
- State 3 (STRESS): [-0.16, 1.40, -0.91, -0.53, 1.22, -0.79, -0.82]

**Emission Nu (degrees of freedom):** [5.0, 5.0, 5.0, 5.0] (student-t heavy tails)

---

## 4. REGIME-DISTRIBUSJON

### Historisk Fordeling (regime_daily)

| Regime | Count | Andel |
|--------|-------|-------|
| NEUTRAL | 51,371 | 40.72% |
| BEAR | 30,776 | 24.38% |
| BULL | 28,809 | 22.82% |
| STRESS | 13,899 | 11.02% |
| STRONG_BULL | 643 | 0.51% |
| STRONG_BEAR | 421 | 0.33% |
| BROKEN | 170 | 0.13% |
| VOLATILE_NON_DIRECTIONAL | 111 | 0.09% |

### Naavaerende Status (2025-12-11)

**CRYPTO (44 aktiva):**
- NEUTRAL: 54.5%
- BEAR: 36.4%
- BULL: 4.5%
- STRESS: 4.5%

**EQUITIES (389 aktiva):**
- BULL: 41.4%
- NEUTRAL: 33.7%
- BEAR: 18.8%
- STRESS: 6.2%

**FX (24 aktiva):**
- BULL/BEAR/NEUTRAL: 33.3% hver

---

## 5. ASSET-DEKNING

### Topp 10 Aktiva (historisk dybde)

| Asset | Dager | BULL | BEAR | NEUTRAL | STRESS | Fra | Til |
|-------|-------|------|------|---------|--------|-----|-----|
| BTC-USD | 3,394 | 1,075 | 1,173 | 589 | 59 | 2016-08-29 | 2025-12-13 |
| ETH-USD | 2,686 | 850 | 930 | 507 | 46 | 2018-08-07 | 2025-12-13 |
| EURUSD | 2,275 | 800 | 859 | 334 | 0 | 2016-12-28 | 2025-12-12 |
| SOL-USD | 1,803 | 535 | 723 | 294 | 37 | 2021-01-06 | 2025-12-13 |
| ATOM-USD | 352 | 58 | 82 | 155 | 57 | 2024-12-25 | 2025-12-11 |
| ALGO-USD | 352 | 40 | 96 | 183 | 33 | 2024-12-25 | 2025-12-11 |

---

## 6. REGIME V2 til V4 MAPPING

| V2 Regime | V4 Regime | Konfidans |
|-----------|-----------|-----------|
| STRONG_BULL | BULL | 1.00 |
| BULL | BULL | 1.00 |
| NEUTRAL | NEUTRAL | 1.00 |
| BEAR | BEAR | 1.00 |
| STRONG_BEAR | BEAR | 1.00 |
| VOLATILE_NON_DIRECTIONAL | STRESS | 0.90 |
| COMPRESSION | NEUTRAL | 0.80 |
| BROKEN | STRESS | 0.70 |
| UNTRUSTED | NEUTRAL | 0.50 |

---

## 7. FERSKE REGIME-SIGNALER (2025-12-11)

| Asset | Regime | Konfidans | Consec. | HMM Ver |
|-------|--------|-----------|---------|---------|
| ABNB | BULL | 0.998 | 3 | v4.0 |
| ADBE | BULL | 0.995 | 5 | v4.0 |
| ADI | BULL | 0.998 | 12 | v4.0 |
| ACA.PA | BULL | 0.992 | 11 | v4.0 |
| ABBV | BEAR | 0.955 | 1 | v4.0 |
| ABT | BEAR | 0.946 | 7 | v4.0 |
| AEP | BEAR | 0.831 | 9 | v4.0 |
| 1COV.DE | NEUTRAL | 0.927 | 1 | v4.0 |
| AAVE-USD | NEUTRAL | 0.925 | 2 | v4.0 |

---

## 8. FERSKE HMM FEATURES (BTC-USD)

| Dato | Return_z | Vol_z | RSI_z | MACD_z |
|------|----------|-------|-------|--------|
| 2025-12-13 | -1.299 | 0.752 | -0.273 | 1.068 |
| 2025-12-12 | 0.596 | 0.680 | 0.037 | 1.327 |
| 2025-12-11 | -0.386 | 0.684 | -0.168 | 1.314 |

---

## 9. GOVERNANCE STATUS

### IoS-003 Attestasjoner

| Type | Status | Dato | Basis |
|------|--------|------|-------|
| G1_TECHNICAL_VALIDATION | PASS | 2025-12-14 | CD-IOS-003-G1-ACCEL-001 |
| G4_ACTIVATION (Appendix A HMM) | APPROVED | 2025-11-29 | ADR-004 Change Gates |
| IOS_MODULE_G4_ACTIVATION | ACTIVE | 2025-11-29 | CEO authority ADR-001 |

### Relaterte IoS-lag

| IoS | Status | Oppdatert |
|-----|--------|-----------|
| IoS-003 | G1_TECHNICAL_VALIDATION_PASS | 2025-12-14 |
| IoS-005 | G4_CONSTITUTIONAL | 2025-12-08 |
| IoS-007 | G2_HISTORICAL_BUILD_IN_PROGRESS | 2025-12-14 |

---

## 10. BOCD CHANGEPOINT STATUS

**bocd_changepoint_log:** Tom (0 registrerte changepoints)
- Systemet tracker changepoint-sannsynlighet, men ingen har overskredet terskel (0.50)
- Changepoint-deteksjon er aktiv men har ikke utlost noen flagg ennaa

---

## 11. ARKITEKTUR-NOTATER

### Input-Output HMM (IOHMM)
- **Aktivert:** Ja, for alle asset classes
- **Covariater:** yield_spread_z, vix_z, liquidity_z
- **Effekt:** Makrookonomiske faktorer pavirker overgangsmatrisen dynamisk

### Student-t Emisjoner
- **Frihetsgrader:** 5 for alle states
- **Formal:** Handterer heavy-tailed avkastningsfordelinger bedre enn Gaussisk

### Hysteresis
- **CRYPTO:** 3 dager (kortere for hoyere volatilitet)
- **FX/EQUITIES:** 5 dager (standard)
- **Formal:** Unngaar falske regimeskifter fra stoy

---

**RAPPORT SLUTT**
