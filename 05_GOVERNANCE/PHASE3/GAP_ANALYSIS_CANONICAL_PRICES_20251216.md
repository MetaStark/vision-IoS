# CANONICAL PRICE DATA GAP ANALYSIS
## Date: 2025-12-16 (CORRECTED v2)
## Executor: STIG (EC-003)
## Classification: INFRASTRUCTURE AUDIT

---

## EXECUTIVE SUMMARY

### Single Source of Truth: `fhq_market.prices`
- **1.16 million rows**
- **470 unique assets**
- **Data range**: 2015-12-02 to 2025-12-13

| Asset Class | Total Canonical | In fhq_market.prices | Missing | Coverage |
|-------------|-----------------|----------------------|---------|----------|
| CRYPTO      | 50              | 50                   | 0       | **100%** |
| EQUITY      | 422             | 395                  | 27      | 93.6%    |
| FX          | 25              | 25                   | 0       | **100%** |
| **TOTAL**   | **497**         | **470**              | **27**  | **94.6%** |

---

## DATA ARCHITECTURE ISSUE (LEGACY)

There is a legacy table `fhq_data.price_series` with 71K rows and 29 assets that is NOT the canonical source.

### Assets ONLY in legacy table (NOT in canonical):
```
AMZN, ASML, BRK.B, BT.A.L, DIA, GOOG, GOOGL, IWM, JNJ, MA, META,
TSLA, UNH, V, VOO, VTI, XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE,
XLU, XLV, XLY
```

Plus crypto in wrong format:
- `LST_BTC_XCRYPTO` (should be `BTC-USD`)
- `LST_ETH_XCRYPTO` (should be `ETH-USD`)

**NOTE**: `fhq_market.prices` already has BTC-USD (8,160 rows) and ETH-USD (3,591 rows) in correct format.

---

## REMEDIATION REQUIRED

### Option 1: Migrate Legacy Data (RECOMMENDED)
Migrate the 27 equities from `fhq_data.price_series` into `fhq_market.prices`:

```sql
INSERT INTO fhq_market.prices (canonical_id, timestamp, open, high, low, close, volume, source)
SELECT
    listing_id as canonical_id,
    date as timestamp,
    open, high, low, close, volume,
    'MIGRATION_FROM_PRICE_SERIES' as source
FROM fhq_data.price_series
WHERE listing_id NOT LIKE 'LST_%'
ON CONFLICT DO NOTHING;
```

### Option 2: Deprecate Legacy Table
After migration, mark `fhq_data.price_series` as deprecated and update all systems to use only `fhq_market.prices`.

---

## IoS-004 CONFIGURATION

**Current Status**: IoS-004 now uses ONLY `fhq_market.prices` as the canonical source.

```python
# CANONICAL SOURCE: fhq_market.prices (1.16M rows, 470 assets)
# This is the SINGLE source of truth for price data.
```

---

## CRYPTO COVERAGE (100%)

All 50 crypto assets have data in `fhq_market.prices`:

| Asset | Rows | First Date | Last Date |
|-------|------|------------|-----------|
| BTC-USD | 8,160 | 2015-12-02 | 2025-12-13 |
| ETH-USD | 3,591 | 2017-11-09 | 2025-12-13 |
| SOL-USD | 2,838 | 2020-04-10 | 2025-12-13 |
| ADA-USD | 2,956 | 2017-11-09 | 2025-12-12 |
| DOGE-USD | 2,956 | 2017-11-09 | 2025-12-12 |
| XRP-USD | 2,956 | 2017-11-09 | 2025-12-12 |
| ... | ... | ... | ... |

**Impact**: ALL crypto proposals can now be backtested.

---

## FX COVERAGE (100%)

All 25 FX pairs have data:
```
AUDJPY=X, AUDUSD=X, CADJPY=X, CHFJPY=X, EURAUD=X, EURCHF=X,
EURGBP=X, EURJPY=X, EURNOK=X, EURSEK=X, EURUSD=X, GBPJPY=X,
GBPUSD=X, NZDUSD=X, USDCAD=X, USDCHF=X, USDHKD=X, USDJPY=X,
USDMXN=X, USDNOK=X, USDSEK=X, USDSGD=X, USDTRY=X, USDZAR=X
```

---

## EQUITY COVERAGE (93.6%)

**395 of 422** equities have data, including:
- Oslo Børs (AKER.OL, AKRBP.OL, etc.)
- European (1COV.DE, ACA.PA, AIR.DE, etc.)
- US (AAPL, MSFT, NVDA, etc.)

**27 MISSING** (in legacy table only):
- AMZN, TSLA, META, GOOG, GOOGL
- JNJ, UNH, MA, V
- Sector ETFs: XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV, XLY
- Index ETFs: DIA, IWM, VOO, VTI

---

## ATTESTATION

**Analysis completed by**: STIG (EC-003)
**Date**: 2025-12-16T17:00:00+01:00
**Canonical Source**: `fhq_market.prices`
**Action Required**: Migrate 27 legacy equities to canonical table
