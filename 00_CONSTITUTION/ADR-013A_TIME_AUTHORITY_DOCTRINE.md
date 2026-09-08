# ADR-013A: Time Authority Doctrine

**Status:** CONSTITUTIONAL
**Authority:** CEO-DIR-2026-091
**Parent:** ADR-013 (Kernel Specification - Infrastructure Sovereignty)
**Effective:** 2026-01-18
**Classification:** GOVERNANCE-CRITICAL

---

## Doctrine Statement

> **All temporal reasoning must originate from canonical calendar truth (or epoch boundary for crypto). No local clocks, no assumptions.**

---

## 1. Scope

This doctrine applies to:

- All agent operations (LARS, STIG, LINE, FINN, VEGA, CRIO, CEIO, CDMO)
- All automated processes, daemons, and scheduled tasks
- All signal generation, forecast evaluation, and ROI measurement
- All horizon calculations (T+N days)
- All learning attribution and outcome capture

---

## 2. Canonical Time Sources

| Asset Class | Time Source | Boundary |
|-------------|-------------|----------|
| US Equities | `fhq_meta.calendar_days` (US_EQUITY) | Market open/close (09:30-16:00 ET) |
| Crypto | `fhq_meta.crypto_epoch_boundary()` | 00:00:00 UTC |

### 2.1 Equity Time Authority

```sql
-- CORRECT: Query canonical calendar
SELECT fhq_meta.is_market_open('US_EQUITY', target_date);
SELECT * FROM fhq_meta.get_next_trading_days('US_EQUITY', CURRENT_DATE, 5);

-- INCORRECT: Local assumption (PROHIBITED)
-- target_date + INTERVAL '1 day'  -- May land on weekend/holiday
-- CURRENT_TIMESTAMP               -- Local clock, not canonical
```

### 2.2 Crypto Time Authority

```sql
-- CORRECT: Query epoch boundary
SELECT fhq_meta.crypto_epoch_boundary(signal_timestamp);

-- INCORRECT: Local assumption (PROHIBITED)
-- DATE_TRUNC('day', timestamp)    -- May use local timezone
-- signal_timestamp + INTERVAL '1 day'  -- No epoch awareness
```

---

## 3. Prohibited Patterns

The following patterns are **Class B violations** under ADR-013:

| Pattern | Why Prohibited |
|---------|----------------|
| `CURRENT_DATE + N` for equity horizons | May land on weekend/holiday |
| Local clock for timestamp generation | Timezone drift risk |
| Hardcoded day counts for horizon | Ignores market structure |
| Assuming "tomorrow is a trading day" | Must query calendar |
| Using `NOW()` without timezone | Ambiguous temporal reference |

---

## 4. Required Patterns

### 4.1 Horizon Calculation (Equity)

```sql
-- Get T+5 trading day date
SELECT trading_date
FROM fhq_meta.get_next_trading_days('US_EQUITY', signal_date, 5)
WHERE day_number = 5;
```

### 4.2 Epoch Calculation (Crypto)

```sql
-- Get T+5 epoch boundary
SELECT fhq_meta.crypto_epoch_boundary(signal_timestamp + INTERVAL '5 days');
```

### 4.3 Market Context Check

```sql
-- Get risk-aware context
SELECT market_context_flag, risk_note
FROM fhq_meta.ios016_calendar_truth
WHERE market = 'US_EQUITY' AND date = target_date;
```

---

## 5. Enforcement

### 5.1 Pre-Execution Check

All execution-path code must verify:

```python
# REQUIRED: Check calendar before any trade decision
is_trading_day = query("SELECT fhq_meta.is_market_open('US_EQUITY', %s)", date)
if not is_trading_day:
    raise CalendarViolationError("Cannot execute on non-trading day")
```

### 5.2 Audit Trail

All temporal decisions must be logged with:

- Source of time authority (calendar_id or epoch function)
- Provenance (LIBRARY or PROJECTED)
- Timestamp of query

---

## 6. Exceptions

| Scenario | Allowed Exception | Constraint |
|----------|-------------------|------------|
| Internal logging | Local clock (`NOW()`) | For audit timestamps only, not decisions |
| Daemon scheduling | OS scheduler | Must validate against calendar on wake |
| Evidence generation | `NOW()` with timezone | Must include explicit timezone |

---

## 7. Validation Function

```sql
-- Validate that a date is safe for execution
CREATE OR REPLACE FUNCTION fhq_meta.validate_time_authority(
    p_market VARCHAR,
    p_date DATE
) RETURNS TABLE (
    is_valid BOOLEAN,
    reason TEXT,
    provenance VARCHAR
) AS $$
SELECT
    cd.is_open AND cd.provenance = 'LIBRARY',
    CASE
        WHEN NOT cd.is_open THEN 'Market closed on this date'
        WHEN cd.provenance = 'PROJECTED' THEN 'Date is in projected window - no trading authority'
        ELSE 'Valid trading date'
    END,
    cd.provenance
FROM fhq_meta.calendar_days cd
WHERE cd.calendar_id = p_market AND cd.date = p_date;
$$ LANGUAGE sql STABLE;
```

---

## 8. Constitutional Binding

This doctrine is **constitutional** under ADR-013 (Infrastructure Sovereignty):

- STIG is the sole custodian of temporal infrastructure
- No agent may bypass canonical time sources
- Violations are escalated per ADR severity rules
- This doctrine may only be amended by CEO directive

---

## 9. Rationale

Time-as-infrastructure prevents:

- Silent horizon drift
- Weekend/holiday execution attempts
- Timezone confusion
- Non-deterministic outcome capture
- Audit-failing temporal claims

A system that assumes time is a system that will eventually be wrong.

---

## 10. References

- **CEO-DIR-2026-091**: Trading Calendar Continuous Governance + IoS-016 Integration
- **CEO-DIR-2026-086**: Trading Calendar Canonicalization
- **ADR-013**: Kernel Specification (Infrastructure Sovereignty)
- **IoS-016**: Economic Calendar & Temporal Governance

---

**Principle:** No system component may assume time – it must query time.
