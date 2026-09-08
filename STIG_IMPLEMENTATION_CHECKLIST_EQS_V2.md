# STIG IMPLEMENTATION CHECKLIST
## EQS v2 Critical Conditions - Production Readiness

**Authority:** VEGA G3 Audit (VEGA-G3-AUDIT-EQS-V2-20251226)
**Assignee:** STIG (System for Technical Implementation & Governance)
**Deadline:** 1 week from CEO approval
**Status:** ⏳ PENDING

---

## CRITICAL CONDITION C1: Hard Stop Implementation

### 1.1 Add Exception Class

**File:** `03_FUNCTIONS/eqs_v2_calculator.py`
**Location:** After line 13 (after imports, before class definition)

```python
class RegimeDiversityError(Exception):
    """
    Raised when regime diversity insufficient for EQS v2 scoring.

    This error indicates that the regime classifier is producing
    collapsed output (>85% single regime), which reduces EQS v2
    discrimination power by 50-65%. EQS v2 refuses to score
    under these conditions to force upstream fix.

    Fallback: Use EQS v1 until regime diversity restored.
    """
    def __init__(self, message, diversity_data=None):
        super().__init__(message)
        self.diversity_data = diversity_data or {}
```

**Acceptance Criteria:**
- [ ] Exception class defined
- [ ] Docstring explains purpose
- [ ] Can store diversity_data for diagnostics

---

### 1.2 Add Governance Constant

**File:** `03_FUNCTIONS/eqs_v2_calculator.py`
**Location:** After line 65 (in class definition, before __init__)

```python
class EQSv2Calculator:
    # ... existing constants ...

    # Governance constants (ADR-014 Sub-Executive Governance)
    MIN_REGIME_DIVERSITY = 0.15  # 15% non-dominant regime required
    # Rationale: Below 15%, regime_alignment factor becomes non-discriminatory,
    # reducing EQS v2 discrimination power by 50-65% (VEGA G3 Audit validated)
```

**Acceptance Criteria:**
- [ ] Constant defined as class attribute
- [ ] Value = 0.15 (15%)
- [ ] Comment explains rationale

---

### 1.3 Add Diversity Check Method

**File:** `03_FUNCTIONS/eqs_v2_calculator.py`
**Location:** After __init__ method (around line 75)

```python
def check_regime_diversity(self) -> Dict:
    """
    Check current regime diversity status against governance threshold.

    Queries fhq_canonical.v_regime_diversity_status to determine if
    sufficient regime variance exists for EQS v2 regime-aware features.

    Returns:
        Dictionary with:
        - sufficient (bool): True if diversity meets MIN_REGIME_DIVERSITY
        - non_dominant_pct (float): Percentage of signals in non-dominant regime
        - status (str): Diversity status ('FUNCTIONAL', 'DEGRADED', 'BLOCKED')
        - dominant_regime (str): Name of dominant regime (e.g., 'NEUTRAL')
        - dominant_regime_pct (float): Percentage in dominant regime

    Raises:
        ValueError: If regime diversity view returns no data
    """
    query = "SELECT * FROM fhq_canonical.v_regime_diversity_status;"
    result = pd.read_sql_query(query, self.conn)

    if len(result) == 0:
        raise ValueError("No regime diversity data available - check v_regime_diversity_status view")

    # Calculate non-dominant percentage
    max_regime_pct = result['pct_of_total'].max() / 100.0
    non_dominant_pct = 1.0 - max_regime_pct

    return {
        'sufficient': non_dominant_pct >= self.MIN_REGIME_DIVERSITY,
        'non_dominant_pct': non_dominant_pct,
        'status': result['diversity_status'].iloc[0],
        'dominant_regime': result['regime'].iloc[0],
        'dominant_regime_pct': max_regime_pct,
    }
```

**Acceptance Criteria:**
- [ ] Method defined in EQSv2Calculator class
- [ ] Queries v_regime_diversity_status view
- [ ] Returns dictionary with all required fields
- [ ] Handles empty result set gracefully

---

### 1.4 Add Blocking Check to calculate_eqs_v2()

**File:** `03_FUNCTIONS/eqs_v2_calculator.py`
**Location:** Start of calculate_eqs_v2() method (line 176)

**BEFORE:**
```python
def calculate_eqs_v2(self, df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate EQS v2 for all signals using rank-based approach.
    ...
    """
    # Step 1: Calculate base score (scaled down to leave room for premiums)
    df['base_score'] = (df['confluence_factor_count'] / 7.0) * self.BASE_WEIGHT
```

**AFTER:**
```python
def calculate_eqs_v2(self, df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate EQS v2 for all signals using rank-based approach.

    Args:
        df: DataFrame from fetch_dormant_signals()

    Returns:
        DataFrame with additional columns (eqs_v2, eqs_v2_tier, etc.)

    Raises:
        RegimeDiversityError: If regime diversity below MIN_REGIME_DIVERSITY threshold
    """
    # GOVERNANCE CHECKPOINT: Check regime diversity BEFORE scoring
    # This is a BLOCKING check per VEGA G3 Audit condition C1
    diversity = self.check_regime_diversity()

    if not diversity['sufficient']:
        error_msg = (
            f"EQS v2 BLOCKED: Regime diversity {diversity['non_dominant_pct']:.2%} "
            f"< required {self.MIN_REGIME_DIVERSITY:.0%}. "
            f"\n\nCurrent Distribution:"
            f"\n  - {diversity['dominant_regime']}: {diversity['dominant_regime_pct']:.1%}"
            f"\n  - Others: {diversity['non_dominant_pct']:.1%}"
            f"\n\nStatus: {diversity['status']}"
            f"\n\nImpact: factor_regime_alignment non-discriminatory, "
            f"category strength context-blind, temporal regime features unavailable."
            f"\n\nAction Required:"
            f"\n  1. Investigate regime classifier (CEIO/CDMO)"
            f"\n  2. Verify macro input data quality (VIX, yields, etc.)"
            f"\n  3. Check classifier thresholds/logic"
            f"\n\nFallback: Use EQS v1 (absolute scoring) until regime diversity restored."
        )
        raise RegimeDiversityError(error_msg, diversity_data=diversity)

    # Proceed with normal calculation
    # Step 1: Calculate base score (scaled down to leave room for premiums)
    df['base_score'] = (df['confluence_factor_count'] / 7.0) * self.BASE_WEIGHT
    # ... rest of existing code ...
```

**Acceptance Criteria:**
- [ ] Diversity check is FIRST operation in method
- [ ] Exception raised if insufficient diversity
- [ ] Error message is clear and actionable
- [ ] Includes current diversity metrics
- [ ] Suggests fallback to EQS v1

---

### 1.5 Unit Test: Hard Stop Triggers

**File:** `03_FUNCTIONS/test_eqs_v2_hard_stop.py` (NEW FILE)

```python
#!/usr/bin/env python3
"""
Unit tests for EQS v2 Hard Stop (Regime Diversity Blocking)

Tests VEGA G3 Audit Condition C1 compliance.
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch
from eqs_v2_calculator import EQSv2Calculator, RegimeDiversityError


class TestHardStop:
    """Test suite for regime diversity Hard Stop."""

    def test_hard_stop_triggers_on_collapsed_regime(self):
        """Test that EQS v2 blocks when regime diversity < 15%."""
        # Mock database connection
        mock_conn = Mock()

        # Mock diversity query result (100% NEUTRAL = collapsed)
        mock_diversity_result = pd.DataFrame({
            'regime': ['NEUTRAL'],
            'signal_count': [1172],
            'pct_of_total': [100.0],
            'diversity_status': ['COLLAPSED']
        })

        calc = EQSv2Calculator(mock_conn)

        # Patch pandas read_sql to return collapsed regime
        with patch('pandas.read_sql_query', return_value=mock_diversity_result):
            # Attempt to calculate EQS v2
            test_signals = pd.DataFrame({
                'needle_id': ['test1', 'test2'],
                'confluence_factor_count': [7, 6],
                'sitc_nodes_completed': [7, 6],
                'sitc_nodes_total': [7, 7],
                'hypothesis_category': ['TIMING', 'MEAN_REVERSION'],
                'created_at': pd.to_datetime(['2025-12-26 10:00', '2025-12-26 09:00'], utc=True),
                'factor_price_technical': [True, True],
                'factor_volume_confirmation': [True, True],
                'factor_regime_alignment': [True, True],
                'factor_temporal_coherence': [True, False],
                'factor_catalyst_present': [True, True],
                'factor_specific_testable': [True, True],
                'factor_testable_criteria': [True, True],
            })

            # Should raise RegimeDiversityError
            with pytest.raises(RegimeDiversityError) as exc_info:
                calc.calculate_eqs_v2(test_signals)

            # Validate error message
            error_msg = str(exc_info.value)
            assert "BLOCKED" in error_msg
            assert "15%" in error_msg or "0.15" in error_msg
            assert "NEUTRAL" in error_msg
            assert "100" in error_msg or "99.9" in error_msg

    def test_hard_stop_allows_functional_diversity(self):
        """Test that EQS v2 proceeds when regime diversity >= 15%."""
        mock_conn = Mock()

        # Mock diversity query result (70% NEUTRAL, 20% BULL, 10% BEAR = functional)
        mock_diversity_result = pd.DataFrame({
            'regime': ['NEUTRAL'],  # Only returns dominant
            'signal_count': [820],
            'pct_of_total': [70.0],
            'diversity_status': ['FUNCTIONAL']
        })

        calc = EQSv2Calculator(mock_conn)

        with patch('pandas.read_sql_query', return_value=mock_diversity_result):
            # Create minimal test data
            test_signals = pd.DataFrame({
                'needle_id': ['test1'],
                'confluence_factor_count': [7],
                'sitc_nodes_completed': [7],
                'sitc_nodes_total': [7],
                'hypothesis_category': ['TIMING'],
                'created_at': pd.to_datetime(['2025-12-26 10:00'], utc=True),
                'factor_price_technical': [True],
                'factor_volume_confirmation': [True],
                'factor_regime_alignment': [True],
                'factor_temporal_coherence': [True],
                'factor_catalyst_present': [True],
                'factor_specific_testable': [True],
                'factor_testable_criteria': [True],
            })

            # Should NOT raise exception
            try:
                result = calc.calculate_eqs_v2(test_signals)
                assert 'eqs_v2' in result.columns
            except RegimeDiversityError:
                pytest.fail("Hard Stop should not trigger when diversity >= 15%")

    def test_diversity_check_returns_correct_metrics(self):
        """Test that check_regime_diversity() calculates metrics correctly."""
        mock_conn = Mock()

        mock_diversity_result = pd.DataFrame({
            'regime': ['NEUTRAL'],
            'signal_count': [940],
            'pct_of_total': [80.0],
            'diversity_status': ['FUNCTIONAL']
        })

        calc = EQSv2Calculator(mock_conn)

        with patch('pandas.read_sql_query', return_value=mock_diversity_result):
            diversity = calc.check_regime_diversity()

            assert diversity['dominant_regime'] == 'NEUTRAL'
            assert diversity['dominant_regime_pct'] == 0.80
            assert diversity['non_dominant_pct'] == 0.20
            assert diversity['sufficient'] is True  # 20% > 15%
            assert diversity['status'] == 'FUNCTIONAL'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

**Acceptance Criteria:**
- [ ] Test file created
- [ ] Test 1: Hard Stop triggers on collapsed regime (100% single)
- [ ] Test 2: Hard Stop allows functional diversity (>15%)
- [ ] Test 3: check_regime_diversity() calculates correctly
- [ ] All tests pass

**Run Tests:**
```bash
cd C:\fhq-market-system\vision-ios\03_FUNCTIONS
pytest test_eqs_v2_hard_stop.py -v
```

---

## CRITICAL CONDITION C2: Calculation Logging

### 2.1 Database Migration

**File:** `04_DATABASE/MIGRATIONS/161_eqs_v2_calculation_logging.sql` (NEW FILE)

```sql
-- Migration 161: EQS v2 Calculation Logging (VEGA G3 Audit Condition C2)
-- Purpose: Court-proof evidence trail for all EQS v2 calculations
-- Authority: CEO Directive 2025-12-20 (No Summary Without Raw Query Evidence)
-- Audit: VEGA-G3-AUDIT-EQS-V2-20251226

CREATE SCHEMA IF NOT EXISTS vision_verification;

CREATE TABLE IF NOT EXISTS vision_verification.eqs_v2_calculation_log (
    -- Primary key
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Signal reference
    needle_id UUID NOT NULL REFERENCES fhq_canonical.golden_needles(needle_id) ON DELETE CASCADE,

    -- Timestamp
    calculation_timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Input values (for reproducibility)
    confluence_factor_count INTEGER NOT NULL,
    sitc_nodes_completed INTEGER NOT NULL,
    sitc_nodes_total INTEGER NOT NULL,
    hypothesis_category TEXT NOT NULL,
    age_hours NUMERIC(8,2) NOT NULL,

    -- Intermediate calculations (for auditability)
    base_score NUMERIC(5,4) NOT NULL,
    sitc_completeness NUMERIC(5,4) NOT NULL,
    sitc_percentile NUMERIC(5,4) NOT NULL,
    factor_quality_score NUMERIC(5,4) NOT NULL,
    factor_percentile NUMERIC(5,4) NOT NULL,
    category_strength NUMERIC(5,4) NOT NULL,
    category_percentile NUMERIC(5,4) NOT NULL,
    recency_percentile NUMERIC(5,4) NOT NULL,

    -- Final output
    eqs_v2_final NUMERIC(5,4) NOT NULL,
    eqs_v2_tier TEXT NOT NULL,

    -- Audit trail
    calculation_hash TEXT NOT NULL, -- SHA-256 of all inputs (tamper detection)
    cohort_size INTEGER NOT NULL, -- Number of signals in percentile cohort
    regime_diversity_status TEXT NOT NULL, -- FUNCTIONAL, DEGRADED, BLOCKED

    -- Constraints
    CONSTRAINT valid_eqs_range CHECK (eqs_v2_final BETWEEN 0.0 AND 1.0),
    CONSTRAINT valid_tier CHECK (eqs_v2_tier IN ('S', 'A', 'B', 'C')),
    CONSTRAINT valid_percentiles CHECK (
        sitc_percentile BETWEEN 0.0 AND 1.0 AND
        factor_percentile BETWEEN 0.0 AND 1.0 AND
        category_percentile BETWEEN 0.0 AND 1.0 AND
        recency_percentile BETWEEN 0.0 AND 1.0
    )
);

-- Indexes for performance
CREATE INDEX idx_eqs_v2_log_needle ON vision_verification.eqs_v2_calculation_log(needle_id);
CREATE INDEX idx_eqs_v2_log_timestamp ON vision_verification.eqs_v2_calculation_log(calculation_timestamp DESC);
CREATE INDEX idx_eqs_v2_log_tier ON vision_verification.eqs_v2_calculation_log(eqs_v2_tier);
CREATE INDEX idx_eqs_v2_log_hash ON vision_verification.eqs_v2_calculation_log(calculation_hash);

-- Comments
COMMENT ON TABLE vision_verification.eqs_v2_calculation_log IS
'Court-proof evidence log for all EQS v2 calculations per CEO Directive 2025-12-20. '
'Preserves full audit trail: inputs, intermediate calculations, final scores. '
'Enables verification via re-calculation and hash comparison.';

COMMENT ON COLUMN vision_verification.eqs_v2_calculation_log.calculation_hash IS
'SHA-256 hash of input values (needle_id + confluence_factor_count + sitc + category). '
'Used for tamper detection and calculation verification.';

COMMENT ON COLUMN vision_verification.eqs_v2_calculation_log.cohort_size IS
'Number of signals in the percentile ranking cohort. '
'Required for reproducing percentile calculations.';

COMMENT ON COLUMN vision_verification.eqs_v2_calculation_log.regime_diversity_status IS
'Regime diversity status at time of calculation. '
'Values: OPTIMAL, FUNCTIONAL, DEGRADED, BLOCKED. '
'If DEGRADED, EQS v2 operates at reduced capacity.';

-- Grant permissions
GRANT SELECT ON vision_verification.eqs_v2_calculation_log TO PUBLIC;
GRANT INSERT ON vision_verification.eqs_v2_calculation_log TO postgres;

-- Verification query
DO $$
BEGIN
    RAISE NOTICE 'Migration 161 complete: eqs_v2_calculation_log table created';
END $$;
```

**Acceptance Criteria:**
- [ ] Migration file created
- [ ] Table schema includes all required fields
- [ ] Constraints enforce data integrity
- [ ] Indexes created for performance
- [ ] Comments document purpose and fields

**Run Migration:**
```bash
psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -f 04_DATABASE/MIGRATIONS/161_eqs_v2_calculation_logging.sql
```

---

### 2.2 Add Logging Method to Calculator

**File:** `03_FUNCTIONS/eqs_v2_calculator.py`
**Location:** After save_to_database() method (around line 328)

```python
def log_calculations(self, df: pd.DataFrame, regime_diversity_status: str):
    """
    Log all EQS v2 calculations to database for court-proof audit trail.

    Implements CEO Directive 2025-12-20: No Summary Without Raw Query Evidence.
    All intermediate calculations and final scores are persisted for verification.

    Args:
        df: DataFrame with all calculation columns (from calculate_eqs_v2)
        regime_diversity_status: Current regime diversity status (e.g., 'FUNCTIONAL')

    Raises:
        Exception: If logging fails (calculation still succeeds but audit trail incomplete)
    """
    import hashlib

    cursor = self.conn.cursor()

    try:
        for _, row in df.iterrows():
            # Calculate input hash for tamper detection
            input_str = (
                f"{row['needle_id']}"
                f"{row['confluence_factor_count']}"
                f"{row['sitc_nodes_completed']}"
                f"{row['sitc_nodes_total']}"
                f"{row['hypothesis_category']}"
            )
            calc_hash = hashlib.sha256(input_str.encode()).hexdigest()

            cursor.execute("""
                INSERT INTO vision_verification.eqs_v2_calculation_log (
                    needle_id,
                    confluence_factor_count,
                    sitc_nodes_completed,
                    sitc_nodes_total,
                    hypothesis_category,
                    age_hours,
                    base_score,
                    sitc_completeness,
                    sitc_percentile,
                    factor_quality_score,
                    factor_percentile,
                    category_strength,
                    category_percentile,
                    recency_percentile,
                    eqs_v2_final,
                    eqs_v2_tier,
                    calculation_hash,
                    cohort_size,
                    regime_diversity_status
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                );
            """, (
                row['needle_id'],
                int(row['confluence_factor_count']),
                int(row['sitc_nodes_completed']),
                int(row['sitc_nodes_total']),
                row['hypothesis_category'],
                float(row['age_hours']),
                float(row['base_score']),
                float(row['sitc_completeness']),
                float(row['sitc_pct']),
                float(row['factor_quality_score']),
                float(row['factor_pct']),
                float(row['category_strength']),
                float(row['category_pct']),
                float(row['recency_pct']),
                float(row['eqs_v2']),
                str(row['eqs_v2_tier']),
                calc_hash,
                len(df),  # cohort_size
                regime_diversity_status
            ))

        self.conn.commit()
        print(f"✓ Logged {len(df)} EQS v2 calculations to audit trail")

    except Exception as e:
        self.conn.rollback()
        print(f"⚠ WARNING: Calculation logging failed: {e}")
        print("  Calculations succeeded but audit trail incomplete")
        raise  # Re-raise to alert operator

    finally:
        cursor.close()
```

**Acceptance Criteria:**
- [ ] Method defined in EQSv2Calculator class
- [ ] Calculates SHA-256 hash of inputs
- [ ] Inserts all required fields
- [ ] Handles errors gracefully (rollback)
- [ ] Reports success/failure to console

---

### 2.3 Integrate Logging into save_to_database()

**File:** `03_FUNCTIONS/eqs_v2_calculator.py`
**Location:** Modify save_to_database() method (line 292)

**BEFORE:**
```python
def save_to_database(self, df: pd.DataFrame, dry_run: bool = True):
    # ... existing code ...
    else:
        cursor = self.conn.cursor()
        # ... update code ...
        self.conn.commit()
        cursor.close()
        print(f"Updated {len(df)} signals with EQS v2 scores")
```

**AFTER:**
```python
def save_to_database(self, df: pd.DataFrame, dry_run: bool = True):
    # ... existing code ...
    else:
        cursor = self.conn.cursor()

        # Add column if not exists
        cursor.execute("""
            ALTER TABLE fhq_canonical.golden_needles
            ADD COLUMN IF NOT EXISTS eqs_score_v2 NUMERIC(5,4);
        """)

        # Batch update
        for _, row in df.iterrows():
            cursor.execute("""
                UPDATE fhq_canonical.golden_needles
                SET eqs_score_v2 = %s
                WHERE needle_id = %s;
            """, (float(row['eqs_v2']), row['needle_id']))

        self.conn.commit()
        cursor.close()
        print(f"✓ Updated {len(df)} signals with EQS v2 scores")

        # COURT-PROOF LOGGING (VEGA G3 Audit Condition C2)
        diversity = self.check_regime_diversity()
        self.log_calculations(df, diversity['status'])
```

**Acceptance Criteria:**
- [ ] log_calculations() called after database update
- [ ] Regime diversity status passed to logging
- [ ] Errors in logging do not prevent score update

---

### 2.4 Unit Test: Calculation Logging

**File:** `03_FUNCTIONS/test_eqs_v2_logging.py` (NEW FILE)

```python
#!/usr/bin/env python3
"""
Unit tests for EQS v2 Calculation Logging

Tests VEGA G3 Audit Condition C2 compliance.
"""

import pytest
import pandas as pd
from unittest.mock import Mock, MagicMock
from eqs_v2_calculator import EQSv2Calculator


class TestCalculationLogging:
    """Test suite for EQS v2 calculation logging."""

    def test_logging_creates_audit_records(self, db_conn):
        """Test that log_calculations() inserts records to database."""
        calc = EQSv2Calculator(db_conn)

        # Create test calculation results
        test_df = pd.DataFrame({
            'needle_id': ['test-uuid-1', 'test-uuid-2'],
            'confluence_factor_count': [7, 6],
            'sitc_nodes_completed': [7, 6],
            'sitc_nodes_total': [7, 7],
            'hypothesis_category': ['TIMING', 'MEAN_REVERSION'],
            'age_hours': [48.5, 72.3],
            'base_score': [0.60, 0.51],
            'sitc_completeness': [1.0, 0.857],
            'sitc_pct': [1.0, 0.5],
            'factor_quality_score': [1.0, 0.94],
            'factor_pct': [1.0, 0.5],
            'category_strength': [0.90, 0.70],
            'category_pct': [0.8, 0.3],
            'recency_pct': [0.7, 0.3],
            'eqs_v2': [0.95, 0.71],
            'eqs_v2_tier': ['S', 'C'],
        })

        # Log calculations
        calc.log_calculations(test_df, regime_diversity_status='FUNCTIONAL')

        # Verify records created
        cursor = db_conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM vision_verification.eqs_v2_calculation_log
            WHERE calculation_timestamp > CURRENT_TIMESTAMP - INTERVAL '1 minute';
        """)
        log_count = cursor.fetchone()[0]

        assert log_count == 2, "Should log 2 calculation records"

        # Verify field values
        cursor.execute("""
            SELECT needle_id, eqs_v2_final, eqs_v2_tier, regime_diversity_status
            FROM vision_verification.eqs_v2_calculation_log
            WHERE needle_id IN ('test-uuid-1', 'test-uuid-2')
            ORDER BY eqs_v2_final DESC;
        """)
        records = cursor.fetchall()

        assert records[0][0] == 'test-uuid-1'
        assert abs(records[0][1] - 0.95) < 0.001
        assert records[0][2] == 'S'
        assert records[0][3] == 'FUNCTIONAL'

    def test_logging_includes_hash(self, db_conn):
        """Test that calculation_hash is generated correctly."""
        calc = EQSv2Calculator(db_conn)

        test_df = pd.DataFrame({
            'needle_id': ['test-uuid-hash'],
            'confluence_factor_count': [7],
            'sitc_nodes_completed': [7],
            'sitc_nodes_total': [7],
            'hypothesis_category': ['TIMING'],
            'age_hours': [48.5],
            'base_score': [0.60],
            'sitc_completeness': [1.0],
            'sitc_pct': [1.0],
            'factor_quality_score': [1.0],
            'factor_pct': [1.0],
            'category_strength': [0.90],
            'category_pct': [0.8],
            'recency_pct': [0.7],
            'eqs_v2': [0.95],
            'eqs_v2_tier': ['S'],
        })

        calc.log_calculations(test_df, 'FUNCTIONAL')

        # Verify hash exists and has correct format
        cursor = db_conn.cursor()
        cursor.execute("""
            SELECT calculation_hash FROM vision_verification.eqs_v2_calculation_log
            WHERE needle_id = 'test-uuid-hash';
        """)
        hash_value = cursor.fetchone()[0]

        assert len(hash_value) == 64, "SHA-256 hash should be 64 hex characters"
        assert all(c in '0123456789abcdef' for c in hash_value), "Hash should be hexadecimal"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

**Acceptance Criteria:**
- [ ] Test file created
- [ ] Test 1: Logging creates audit records
- [ ] Test 2: Logging includes SHA-256 hash
- [ ] All tests pass

**Run Tests:**
```bash
cd C:\fhq-market-system\vision-ios\03_FUNCTIONS
pytest test_eqs_v2_logging.py -v
```

---

## FINAL VALIDATION CHECKLIST

### Before Requesting VEGA Re-Audit

- [ ] **C1.1** Exception class `RegimeDiversityError` added
- [ ] **C1.2** Constant `MIN_REGIME_DIVERSITY = 0.15` added
- [ ] **C1.3** Method `check_regime_diversity()` implemented
- [ ] **C1.4** Blocking check added to `calculate_eqs_v2()`
- [ ] **C1.5** Unit tests pass: `pytest test_eqs_v2_hard_stop.py -v`

- [ ] **C2.1** Migration 161 executed successfully
- [ ] **C2.2** Method `log_calculations()` implemented
- [ ] **C2.3** Logging integrated into `save_to_database()`
- [ ] **C2.4** Unit tests pass: `pytest test_eqs_v2_logging.py -v`

### Integration Test

- [ ] Run full EQS v2 calculation on production data
- [ ] Verify Hard Stop triggers when regime diversity < 15%
- [ ] Verify calculations logged to database
- [ ] Verify no errors in console output
- [ ] Verify audit trail complete and queryable

**Integration Test Command:**
```bash
cd C:\fhq-market-system\vision-ios\03_FUNCTIONS
python eqs_v2_calculator.py
```

Expected behavior:
- If regime diversity < 15%: `RegimeDiversityError` raised with clear message
- If regime diversity >= 15%: Calculations succeed, audit trail logged

---

## SIGN-OFF

**STIG Certification:**

I certify that:
- [ ] All code changes implemented as specified
- [ ] All unit tests passing
- [ ] Integration test successful
- [ ] Database migration executed
- [ ] Audit trail verified
- [ ] No regressions introduced

**Signature:** _________________________
**Date:** _________________________
**Commit Hash:** _________________________

**Ready for VEGA Re-Audit:** YES / NO

---

## NEXT STEPS AFTER SIGN-OFF

1. **STIG** creates Git commit with all changes
2. **STIG** requests VEGA re-audit
3. **VEGA** executes validation tests
4. **VEGA** issues approval or requests corrections
5. **LARS (CEO)** makes final deployment decision

---

**END OF CHECKLIST**
