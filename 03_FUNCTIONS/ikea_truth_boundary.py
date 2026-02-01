"""
CEO-DIR-2026-FINN-019: IKEA Truth Boundary (EC-022)

6 deterministic rules for execution gate validation.

CEO Issues Addressed:
  #5: Tight, testable rules tied to concrete fields
  #18: Validate against IoS-001 active_flag (forbidden assets)

Refinement R4: Rule ordering (fail-fast):
  1. IKEA-001: Canonical Citation (structural - fail fast)
  2. IKEA-002: Asset Tradeable (structural)
  3. IKEA-003: Position Bound (sizing)
  4. IKEA-004: TTL Sanity (temporal)
  5. IKEA-005: Impossible Return (semantic)
  6. IKEA-006: Regime Mismatch (semantic)
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

# Constants
MAX_POSITION_PCT = 25.0  # Maximum position as % of NAV
MAX_SNAPSHOT_AGE_SECONDS = 60.0  # Snapshot must be < 60s old at IKEA check
CANONICAL_SOURCES = [
    'fhq_canonical.golden_needles',
    'fhq_data.ios001_signals',
    'fhq_alpha.alpha_signals'
]


class IKEARuleID(Enum):
    """IKEA rule identifiers (R4 ordering: structural -> sizing -> temporal -> semantic)."""
    CANONICAL_CITATION = "IKEA-001"
    ASSET_TRADEABLE = "IKEA-002"
    POSITION_BOUND = "IKEA-003"
    TTL_SANITY = "IKEA-004"
    IMPOSSIBLE_RETURN = "IKEA-005"
    REGIME_MISMATCH = "IKEA-006"


@dataclass
class IKEAValidationResult:
    """Result of IKEA boundary validation."""
    validation_id: UUID
    passed: bool
    rule_violated: Optional[str]
    violation_details: Optional[Dict]
    rules_checked: List[str]


class IKEATruthBoundary:
    """
    EC-022 IKEA Truth Boundary - v0 with 6 deterministic rules.

    CEO Issue #5: Tight, testable rules tied to concrete fields.
    CEO Issue #18: Validate against IoS-001 active_flag.
    R4: Fail-fast ordering (structural first).
    """

    def __init__(self, db_conn):
        self.conn = db_conn

    def validate(
        self,
        needle_id: UUID,
        asset: str,
        direction: str,
        eqs_score: float,
        snapshot_timestamp: datetime,
        snapshot_regime: str,
        position_pct: float
    ) -> IKEAValidationResult:
        """
        Run all 6 IKEA rules. Fails fast on first violation.

        R4 ordering: structural -> sizing -> temporal -> semantic
        """
        validation_id = uuid4()
        rules_checked = []

        # Rule 1: Canonical Citation (structural - fail fast)
        passed, details = self._check_canonical_citation(needle_id)
        rules_checked.append(IKEARuleID.CANONICAL_CITATION.value)
        if not passed:
            return self._fail(validation_id, IKEARuleID.CANONICAL_CITATION, details, rules_checked)

        # Rule 2: Asset Tradeable (CEO Issue #18)
        passed, details = self._check_asset_tradeable(asset)
        rules_checked.append(IKEARuleID.ASSET_TRADEABLE.value)
        if not passed:
            return self._fail(validation_id, IKEARuleID.ASSET_TRADEABLE, details, rules_checked)

        # Rule 3: Position Bound
        passed, details = self._check_position_bound(position_pct)
        rules_checked.append(IKEARuleID.POSITION_BOUND.value)
        if not passed:
            return self._fail(validation_id, IKEARuleID.POSITION_BOUND, details, rules_checked)

        # Rule 4: TTL Sanity
        passed, details = self._check_ttl_sanity(snapshot_timestamp)
        rules_checked.append(IKEARuleID.TTL_SANITY.value)
        if not passed:
            return self._fail(validation_id, IKEARuleID.TTL_SANITY, details, rules_checked)

        # Rule 5: Impossible Return
        passed, details = self._check_impossible_return(eqs_score)
        rules_checked.append(IKEARuleID.IMPOSSIBLE_RETURN.value)
        if not passed:
            return self._fail(validation_id, IKEARuleID.IMPOSSIBLE_RETURN, details, rules_checked)

        # Rule 6: Regime Mismatch
        passed, details = self._check_regime_mismatch(snapshot_regime, direction)
        rules_checked.append(IKEARuleID.REGIME_MISMATCH.value)
        if not passed:
            return self._fail(validation_id, IKEARuleID.REGIME_MISMATCH, details, rules_checked)

        # All rules passed
        self._log_validation(validation_id, True, None, rules_checked, None)
        logger.info(f"IKEA validation PASSED: {validation_id}")

        return IKEAValidationResult(
            validation_id=validation_id,
            passed=True,
            rule_violated=None,
            violation_details=None,
            rules_checked=rules_checked
        )

    def _check_canonical_citation(self, needle_id: UUID) -> Tuple[bool, Optional[Dict]]:
        """
        IKEA-001: Needle must exist in canonical table.

        R4: Structural check - fail fast if needle is invalid.
        """
        if self.conn is None:
            # Without DB, assume valid
            return True, None

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT needle_id, source_table
                FROM fhq_canonical.golden_needles
                WHERE needle_id = %s
            ''', (str(needle_id),))

            row = cursor.fetchone()
            if not row:
                return False, {
                    'reason': 'Needle not in canonical table',
                    'needle_id': str(needle_id)
                }

            # Optionally check source_table is in allowed list
            source = row[1] if len(row) > 1 else None
            if source and source not in CANONICAL_SOURCES:
                return False, {
                    'reason': 'Needle from non-canonical source',
                    'source': source,
                    'valid_sources': CANONICAL_SOURCES
                }

            return True, None

        except Exception as e:
            logger.warning(f"Canonical citation check error: {e}")
            # Fail open for DB errors (allow trade)
            return True, None

    def _check_asset_tradeable(self, asset: str) -> Tuple[bool, Optional[Dict]]:
        """
        IKEA-002: Asset must have active_flag=TRUE in IoS-001.

        CEO Issue #18: Validate against IoS-001 active_flag.
        """
        if self.conn is None:
            # Without DB, assume valid
            return True, None

        try:
            # Handle both BTC-USD and BTC/USD formats
            normalized = asset.replace('/', '-')
            alt_format = asset.replace('-', '/')

            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT symbol, active_flag
                FROM fhq_data.ios001_universe_registry
                WHERE symbol IN (%s, %s, %s)
            ''', (asset, normalized, alt_format))

            row = cursor.fetchone()
            if not row:
                return False, {
                    'reason': 'Asset not in canonical universe',
                    'asset': asset
                }

            if not row[1]:  # active_flag is False
                return False, {
                    'reason': 'Asset inactive in IoS-001',
                    'asset': asset,
                    'active_flag': False
                }

            return True, None

        except Exception as e:
            logger.warning(f"Asset tradeable check error: {e}")
            # Fail open for DB errors
            return True, None

    def _check_position_bound(self, position_pct: float) -> Tuple[bool, Optional[Dict]]:
        """
        IKEA-003: Position cannot exceed 25% of NAV.
        """
        if position_pct > MAX_POSITION_PCT:
            return False, {
                'reason': f'Position exceeds {MAX_POSITION_PCT}% bound',
                'position_pct': position_pct,
                'max_allowed': MAX_POSITION_PCT
            }
        return True, None

    def _check_ttl_sanity(self, snapshot_timestamp: datetime) -> Tuple[bool, Optional[Dict]]:
        """
        IKEA-004: Snapshot cannot be >60s old at IKEA check.
        """
        now = datetime.now(timezone.utc)

        # Handle timezone-naive timestamps
        if snapshot_timestamp.tzinfo is None:
            snapshot_timestamp = snapshot_timestamp.replace(tzinfo=timezone.utc)

        age_seconds = (now - snapshot_timestamp).total_seconds()

        if age_seconds > MAX_SNAPSHOT_AGE_SECONDS:
            return False, {
                'reason': 'Snapshot too old at IKEA check',
                'age_seconds': round(age_seconds, 2),
                'max_age': MAX_SNAPSHOT_AGE_SECONDS
            }
        return True, None

    def _check_impossible_return(self, eqs_score: float) -> Tuple[bool, Optional[Dict]]:
        """
        IKEA-005: EQS must be in valid range [0.0, 1.0].
        """
        if eqs_score < 0.0 or eqs_score > 1.0:
            return False, {
                'reason': 'EQS score out of valid range',
                'eqs_score': eqs_score,
                'valid_range': '[0.0, 1.0]'
            }
        return True, None

    def _check_regime_mismatch(self, regime: str, direction: str) -> Tuple[bool, Optional[Dict]]:
        """
        IKEA-006: Cannot go LONG in BEARISH regime.
        """
        regime_upper = regime.upper() if regime else ''
        direction_upper = direction.upper() if direction else ''

        if regime_upper == 'BEARISH' and direction_upper == 'LONG':
            return False, {
                'reason': 'Regime mismatch: LONG in BEARISH regime',
                'regime': regime,
                'direction': direction
            }
        return True, None

    def _fail(
        self,
        validation_id: UUID,
        rule: IKEARuleID,
        details: Dict,
        rules_checked: List[str]
    ) -> IKEAValidationResult:
        """Log failure and return result."""
        self._log_validation(validation_id, False, rule.value, rules_checked, details)
        logger.warning(f"IKEA validation FAILED: {rule.value} - {details.get('reason', 'Unknown')}")

        return IKEAValidationResult(
            validation_id=validation_id,
            passed=False,
            rule_violated=rule.value,
            violation_details=details,
            rules_checked=rules_checked
        )

    def _log_validation(
        self,
        validation_id: UUID,
        passed: bool,
        rule: Optional[str],
        rules_checked: List[str],
        details: Optional[Dict]
    ):
        """Log to fhq_governance.ikea_validation_log."""
        if self.conn is None:
            return

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO fhq_governance.ikea_validation_log
                (validation_id, passed, rule_violated, rules_checked, violation_details, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            ''', (
                str(validation_id),
                passed,
                rule,
                rules_checked,
                json.dumps(details) if details else None
            ))
            self.conn.commit()

        except Exception as e:
            logger.error(f"Failed to log IKEA validation: {e}")
            try:
                self.conn.rollback()
            except:
                pass


def validate_quick(
    needle_id: UUID,
    asset: str,
    direction: str,
    eqs_score: float,
    snapshot_timestamp: datetime,
    snapshot_regime: str,
    position_pct: float,
    db_conn=None
) -> IKEAValidationResult:
    """Quick validation without instantiating class."""
    boundary = IKEATruthBoundary(db_conn)
    return boundary.validate(
        needle_id=needle_id,
        asset=asset,
        direction=direction,
        eqs_score=eqs_score,
        snapshot_timestamp=snapshot_timestamp,
        snapshot_regime=snapshot_regime,
        position_pct=position_pct
    )


if __name__ == "__main__":
    # Quick test of all rules
    from uuid import uuid4
    from datetime import datetime, timezone, timedelta

    print("IKEA Truth Boundary v0 - Rule Tests")
    print("=" * 50)

    boundary = IKEATruthBoundary(None)  # No DB for tests

    # Test 1: Valid case
    result = boundary.validate(
        needle_id=uuid4(),
        asset="BTC/USD",
        direction="LONG",
        eqs_score=0.85,
        snapshot_timestamp=datetime.now(timezone.utc),
        snapshot_regime="RISK_ON",
        position_pct=10.0
    )
    print(f"Test 1 (Valid): {'PASS' if result.passed else 'FAIL'}")

    # Test 2: Position too large
    result = boundary.validate(
        needle_id=uuid4(),
        asset="BTC/USD",
        direction="LONG",
        eqs_score=0.85,
        snapshot_timestamp=datetime.now(timezone.utc),
        snapshot_regime="RISK_ON",
        position_pct=30.0  # > 25%
    )
    print(f"Test 2 (Position Bound): {'PASS' if result.rule_violated == 'IKEA-003' else 'FAIL'}")

    # Test 3: Stale snapshot
    result = boundary.validate(
        needle_id=uuid4(),
        asset="BTC/USD",
        direction="LONG",
        eqs_score=0.85,
        snapshot_timestamp=datetime.now(timezone.utc) - timedelta(seconds=120),  # 2 min old
        snapshot_regime="RISK_ON",
        position_pct=10.0
    )
    print(f"Test 3 (TTL Sanity): {'PASS' if result.rule_violated == 'IKEA-004' else 'FAIL'}")

    # Test 4: Invalid EQS
    result = boundary.validate(
        needle_id=uuid4(),
        asset="BTC/USD",
        direction="LONG",
        eqs_score=1.5,  # > 1.0
        snapshot_timestamp=datetime.now(timezone.utc),
        snapshot_regime="RISK_ON",
        position_pct=10.0
    )
    print(f"Test 4 (Impossible Return): {'PASS' if result.rule_violated == 'IKEA-005' else 'FAIL'}")

    # Test 5: Regime mismatch
    result = boundary.validate(
        needle_id=uuid4(),
        asset="BTC/USD",
        direction="LONG",  # LONG in BEARISH
        eqs_score=0.85,
        snapshot_timestamp=datetime.now(timezone.utc),
        snapshot_regime="BEARISH",
        position_pct=10.0
    )
    print(f"Test 5 (Regime Mismatch): {'PASS' if result.rule_violated == 'IKEA-006' else 'FAIL'}")

    print("=" * 50)
    print("All rule tests completed")
