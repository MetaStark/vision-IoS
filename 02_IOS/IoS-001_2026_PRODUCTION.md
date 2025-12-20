# IoS-001_2026_PRODUCTION
## Canonical Asset & Context Registry

**Intelligence Operating System Module (IoS Series)**
**MBB C-Suite Charter – Application Layer Foundation**

---

| Field | Value |
|-------|-------|
| Canonical Version | 2026.PROD.3 |
| Status | ACTIVE (G4_CONSTITUTIONAL) |
| Phase | APPLICATION LAYER – FOUNDATIONAL |
| Entity | IoS-001 |
| Owner Role | CDMO (Chief Data & Model Officer) |
| Strategic Authority | LARS (CSO) |
| Governance Authority | VEGA |
| Dependencies | ADR-001, ADR-006, ADR-012, ADR-013, ADR-016 |
| Successor Modules | IoS-002, IoS-003, IoS-004, IoS-005 |
| Effective Date | 2025-12-11 (VEGA Attested) |
| Location | fhq_meta.ios_registry + /02_IOS/IoS-001_2026_PRODUCTION.md |
| Correction | 2025-12-11: Added §3.4 Canonical Indicator Registry, §4.5 Indicator Governance, updated §2.1 Scalability, §4.1 Onboarding Criteria |

---

## 1. Purpose

This contract establishes **IoS-001 – Canonical Asset & Context Registry**, the sovereign foundation of the FjordHQ Intelligence Operating System.

IoS-001 defines the **Canonical Universe** of financial instruments, exchanges, regions, calendars, liquidity classes, and modelling contexts.

It ensures that every data point, indicator, forecast, regime, or trade is tagged with the correct:

- Asset Identity
- Exchange Identity
- Geographic Context
- Sector & Model Taxonomy
- Training Context
- Execution Constraints

**Without IoS-001, no other IoS module can function.**

This module replaces ad-hoc symbols with formal ontology.
It is the **Constitution of the Application Layer**.

---

## 2. Mandate

IoS-001 must:

### 2.1 Establish Canonical Asset Identity (Scalability Requirements)

Define one and only one authoritative representation for each tradable instrument:

- Canonical ID
- Ticker
- MIC (Market Identifier Code)
- Region
- Currency
- Asset Class
- Lot Size
- Tick Size
- Trading Hours
- Market Calendar

**Scalability Target: 500+ Assets**

The Canonical Universe must support a minimum of 500 active assets distributed across:

| Asset Class | Target Count | Exchange(s) |
|-------------|--------------|-------------|
| Crypto | 50+ | XCRY |
| FX | 20+ | XFOR |
| US Equities | 120+ | XNYS, XNAS, ARCX |
| Oslo Børs | 50+ | XOSL |
| EU Equities | 100+ | XETR, XPAR, XLON |

**Incremental Onboarding:** New assets may be added in batches via governance-approved migrations, subject to §4.1 onboarding criteria.

This eliminates ambiguity and ensures deterministic asset referencing across:

- FINN (Research)
- LARS (Strategy)
- CSEO (Blueprints)
- LINE (Execution)
- CFAO (Validation)
- VEGA (Governance)

### 2.2 Establish Contextual Modelling Framework

Formalize the mapping between assets and their modelling contexts:

- Regime Models
- Volatility Models
- Perception Models
- Signal Pipelines
- Sector Classification
- Feature Definitions
- Context Windows

This enables FINN and LARS to interpret data correctly, regardless of vendor feed or timestamp distortions.

### 2.3 Enforce Single Source of Truth (ADR-013)

IoS-001 is the exclusive registry where:

- assets are defined
- modeling contexts are assigned
- exchange metadata is stored
- training contexts are linked
- sector taxonomies are encoded

All downstream systems must query IoS-001 rather than ingesting raw metadata from external providers.

### 2.4 Governance Integration

IoS-001 is subject to governance by:

- CDMO (Owner & Curator)
- LARS (Strategic Universe Definition)
- STIG (Schema Enforcement & Runtime Guarantees)
- VEGA (TRiSM & Constitutional Guardrails)

No asset or context becomes active without:

1. Airlock Validation (CDMO)
2. Schema Conformance (STIG)
3. Context Verification (FINN/LARS)
4. Canonical Attestation (VEGA)

---

## 3. Architecture & Data Model

IoS-001 spans four canonical tables.

### 3.1 fhq_meta.exchanges

Holds exchange-level metadata.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| mic | TEXT (PK) | Market Identifier Code |
| operating_mic | TEXT | Operating MIC |
| exchange_name | TEXT | Full exchange name |
| country_code | TEXT | ISO country code |
| timezone | TEXT | IANA timezone |
| region | TEXT | Geographic region |
| open_time | TIME | Market open time |
| close_time | TIME | Market close time |
| calendar_id | TEXT | Trading calendar reference |
| yahoo_suffix | TEXT | Yahoo Finance ticker suffix |
| trading_hours | JSONB | Detailed trading hours (pre, regular, post, auction) |
| settlement_convention | TEXT | Settlement convention (T+0, T+2, etc.) |
| is_active | BOOLEAN | Exchange active status |
| vega_signature_id | UUID | VEGA attestation reference |

**Registered Exchanges:**

| MIC | Exchange | Country | Region |
|-----|----------|---------|--------|
| XCRY | Cryptocurrency (24/7) | - | GLOBAL |
| XFOR | Foreign Exchange (24/5) | - | GLOBAL |
| XNYS | New York Stock Exchange | US | NORTH_AMERICA |
| XNAS | NASDAQ Stock Market | US | NORTH_AMERICA |
| ARCX | NYSE Arca | US | NORTH_AMERICA |
| XOSL | Oslo Børs (Euronext Oslo) | NO | EUROPE |
| XETR | Deutsche Börse XETRA | DE | EUROPE |
| XPAR | Euronext Paris | FR | EUROPE |
| XLON | London Stock Exchange | GB | EUROPE |

**Purpose:** Ensure deterministic mapping of trading hours, liquidity regime, and session boundaries.

### 3.2 fhq_meta.assets

Defines every asset in the Canonical Universe.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| canonical_id | TEXT (PK) | Unique canonical identifier |
| ticker | TEXT | Trading symbol |
| exchange_mic | TEXT (FK) | Exchange MIC reference |
| asset_class | TEXT | Asset classification |
| currency | TEXT | Quote currency |
| lot_size | NUMERIC | Minimum trade size |
| tick_size | NUMERIC | Minimum price increment |
| sector | TEXT | Sector classification |
| risk_profile | TEXT | Risk categorization (LOW, MEDIUM, HIGH, VERY_HIGH) |
| active_flag | BOOLEAN | Active status |
| min_daily_volume_usd | NUMERIC | §4.1 Liquidity threshold |
| required_history_days | INTEGER | Minimum history days required |
| gap_policy | TEXT | Data gap handling (INTERPOLATE, FORWARD_FILL, SKIP_IF_GAP, FX_ADJUST) |
| liquidity_tier | TEXT | Liquidity classification (TIER_1, TIER_2, TIER_3) |
| onboarding_date | DATE | Date asset was onboarded |
| data_quality_status | ENUM | Quality status (see §4.1) |
| valid_row_count | INTEGER | Number of valid data rows |
| quarantine_threshold | INTEGER | Rows needed to exit quarantine |
| full_history_threshold | INTEGER | Rows for full history status |
| price_source_field | TEXT | Price field for signals (adj_close or close) |
| vega_signature_id | UUID | VEGA attestation reference |

**Dual Price Ontology (GIPS Alignment):**

| Price Field | Purpose | Used By |
|-------------|---------|---------|
| adj_close | Signal Truth (Total Return) | IoS-002, IoS-003, IoS-005 |
| close | Execution Truth | IoS-004, P&L |

For equities, `adj_close` captures corporate actions (splits, dividends). For crypto/FX, `adj_close = close`.

**Purpose:** One asset, one identity, one truth.

### 3.3 fhq_meta.model_context_registry

Maps functional modeling contexts to assets.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| context_id | UUID (PK) | Unique context identifier |
| canonical_id | TEXT (FK) | Asset reference |
| regime_model | TEXT | Regime model reference (e.g., HMM_REGIME_V1) |
| forecast_model | TEXT | Forecast model reference (e.g., ARIMA_GARCH_V1) |
| perception_model | TEXT | Perception model reference |
| feature_set | JSONB | Indicator families and lookback configuration |
| embedding_profile | JSONB | Embedding configuration |
| model_priority | INTEGER | Processing priority (1 = highest) |
| is_active | BOOLEAN | Context active status |
| vega_signature_id | UUID | VEGA attestation reference |

**Purpose:** Every model knows its domain. No model can run out-of-context.

### 3.4 fhq_meta.canonical_indicator_registry

Defines all canonical technical indicators used by IoS-002.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| indicator_id | UUID (PK) | Unique indicator identifier |
| indicator_name | TEXT (UNIQUE) | Indicator name (e.g., RSI_14, MACD_12_26_9) |
| category | TEXT | Category (MOMENTUM, TREND, VOLATILITY, ICHIMOKU, VOLUME) |
| calculation_method | TEXT | Formula description |
| source_standard | TEXT | Academic/industry reference (e.g., "Wilder 1978") |
| ios_module | TEXT | Owning IoS module (always 'IoS-002') |
| default_parameters | JSONB | Default calculation parameters |
| formula_hash | TEXT | SHA-256 hash of formula for integrity |
| indicator_version | TEXT | Version number |
| price_input_field | TEXT | Price field to use (adj_close per Dual Price Ontology) |
| is_active | BOOLEAN | Indicator active status |
| vega_signature_id | UUID | VEGA attestation reference |

**Registered Indicator Categories:**

| Category | Count | Examples |
|----------|-------|----------|
| MOMENTUM | 6 | RSI_14, STOCH_RSI_14, CCI_20, MFI_14, WILLIAMS_R_14, ROC_20 |
| TREND | 8 | MACD_12_26_9, EMA_9, EMA_20, EMA_50, SMA_50, SMA_200, ADX_14, PSAR |
| VOLATILITY | 5 | BB_20_2, ATR_14, KELTNER_20_2, DONCHIAN_20, STDDEV_20 |
| ICHIMOKU | 3 | ICHIMOKU, ICHIMOKU_TENKAN_9, ICHIMOKU_KIJUN_26 |
| VOLUME | 5 | OBV, VWAP, VOLUME_SMA_20, AD_LINE, CMF_20 |

**Purpose:** Standardize indicator definitions across all IoS modules. Ensure reproducibility via formula_hash and academic source citations.

---

## 4. Responsibilities of the Owner (CDMO)

CDMO must:

### 4.1 Curate the Canonical Universe (Onboarding Criteria)

Approve, reject, or modify assets based on:

- liquidity threshold
- governance status
- sector taxonomy
- risk class
- modeling requirements

**Data Quality Status ENUM:**

| Status | Description | IoS-003 Access |
|--------|-------------|----------------|
| QUARANTINED | < threshold rows, awaiting Iron Curtain validation | BLOCKED |
| SHORT_HISTORY | Between threshold and full history | FLAGGED |
| FULL_HISTORY | > full history threshold (5 years) | FULL ACCESS |
| DELISTED_RETAINED | Inactive but preserved for backtest integrity | BACKTEST ONLY |

**Iron Curtain Rule:**

No asset enters IoS-003 (Regime Engine) until minimum history is achieved:

| Asset Class | Quarantine Threshold | Full History Threshold |
|-------------|---------------------|------------------------|
| Equities | 252 rows (1 year) | 1,260 rows (5 years) |
| FX | 252 rows (1 year) | 1,260 rows (5 years) |
| Crypto | 365 rows (1 year, 24/7) | 1,825 rows (5 years) |

**Liquidity Thresholds (min_daily_volume_usd):**

| Asset Class | TIER_1 | TIER_2 | TIER_3 |
|-------------|--------|--------|--------|
| Crypto | > $100M | $10M-$100M | $1M-$10M |
| FX Major | > $100B | $10B-$100B | $1B-$10B |
| US Equities | > $100M | $10M-$100M | $1M-$10M |
| Oslo Børs | > 100M NOK | 10M-100M NOK | 1M-10M NOK |
| EU Equities | > €100M | €10M-€100M | €1M-€10M |

**Gap Policy:**

| Policy | Description | Asset Classes |
|--------|-------------|---------------|
| INTERPOLATE | Linear interpolation for missing values | Crypto |
| FORWARD_FILL | Carry forward last valid value | FX, Equities |
| SKIP_IF_GAP | Skip day if gap > 3 consecutive days | US Equities |
| FX_ADJUST | Forward-fill with FX adjustment | Oslo Børs |

**Survivorship Integrity:**

Delisted assets must never be deleted. They are marked:
- `active_flag = FALSE`
- `data_quality_status = 'DELISTED_RETAINED'`

This ensures IoS-004 backtests are free from survivorship bias.

**CDMO is the gatekeeper of asset identity.**

### 4.2 Enforce Context Economy

Apply measurable rules:

- Similarity Score threshold: ≥ 0.75
- Tier-specific context budget:
  - T1 (LARS): 128k tokens
  - T2 (FINN): 32k tokens
  - T3 (LINE): 4k tokens
- Priority Weights:
  - Regime Alignment: 40%
  - Causal Centrality: 30%
  - Alpha Impact: 30%

**Context is capital. CDMO allocates it.**

### 4.3 Operate the Airlock Protocol

No data enters canonical tables unless:

- Schema_Valid = TRUE
- Null_Check < 1%
- Time_Continuity = TRUE
- Anomaly_Detection < 3σ
- Cost_Check = TRUE
- Source_Signature = VALID

**Contaminated data dies in quarantine.**

### 4.4 Maintain the Model Vault Lineage

Every model must have:

- Training_Data_Hash
- Code_Hash
- Config_Hash
- Performance_Metrics
- TRiSM_Attestation_ID

**Invalid lineage → automatic REVOKE.**

### 4.5 Indicator Governance Protocol

Technical indicators in `fhq_meta.canonical_indicator_registry` are subject to:

**Registration Workflow:**
1. FINN/LARS propose indicator specification
2. STIG validates formula and parameters
3. CDMO approves for canonical registry
4. VEGA attests with Ed25519 signature

**Requirements for Indicator Registration:**
- `source_standard`: Academic or industry reference (BIS/ISO 8000 compliance)
- `formula_hash`: SHA-256 hash of calculation method
- `price_input_field`: Must align with Dual Price Ontology (adj_close for signals)
- `category`: Must be one of MOMENTUM, TREND, VOLATILITY, ICHIMOKU, VOLUME

**Indicator Modification:**
- Any change to calculation_method requires new formula_hash
- Version increment required for parameter changes
- VEGA re-attestation required for any modification

**Purpose:** Ensure indicator reproducibility and audit trail for GIPS compliance.

---

## 5. Constraints

IoS-001 **cannot**:

- Execute trades
- Generate signals
- Make forecasts
- Define strategies
- Alter ADRs
- Modify agent behavior
- Override VEGA
- Write to non-canonical schemas

**IoS-001 is definition, not inference.**

---

## 6. Activation Conditions

IoS-001 becomes ACTIVE when:

1. CDMO provides the formal specification
2. STIG enforces schema migrations
3. FINN validates context mappings
4. LARS approves the Canonical Universe
5. VEGA attests and signs content_hash
6. Hash-chain is committed

Only then do downstream IoS modules unlock:

- IoS-002 Feature Vectors
- IoS-003 Regime Engine
- IoS-004 Backtest Engine
- IoS-005 Skill Metrics

---

## 7. Cryptographic Identity

All IoS-001 artifacts must include:

- SHA-256 content_hash
- VEGA attestation (Ed25519)
- hash_chain_id
- governance_action_id
- lineage metadata snapshot

**Unsigned = invalid.**
**Unattested = blocked.**

---

## 8. Signatures

| Role | Agent | Status |
|------|-------|--------|
| Owner | CDMO | Ed25519 — Registered |
| Strategic Authority | LARS (CSO) | Ed25519 — Registered |
| Governance Authority | VEGA | Ed25519 — Attested (2025-12-11) |
| CEO | Final Constitutional Approval | APPROVED |

---

## 9. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 2026.PROD.1 | 2025-11-28 | Initial release |
| 2026.PROD.2 | 2025-11-28 | Removed invalid ADR references, purged unapproved seed data |
| 2026.PROD.3 | 2025-12-11 | Added §3.4 Canonical Indicator Registry, §4.5 Indicator Governance, updated §2.1 with 500+ asset scalability, updated §4.1 with Iron Curtain and Dual Price Ontology |

---

*Document Version: 2026.PROD.3*
*Created: 2025-11-28*
*Updated: 2025-12-11 (IOS-001_UPDATE_20251211)*
*Location: /02_IOS/IoS-001_2026_PRODUCTION.md*
