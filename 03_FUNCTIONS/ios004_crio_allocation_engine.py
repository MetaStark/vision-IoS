#!/usr/bin/env python3
"""
IoS-004 CRIO-AWARE REGIME ALLOCATION ENGINE
=============================================
Authority: CEO Directive - SOVEREIGN MACRO INTELLIGENCE LOOP
Reference: ADR-017 (MIT Quad Protocol), ADR-012 (Economic Safety)
Owner: LARS (strategy), STIG (infrastructure)

PURPOSE:
    Transform HMM regime states into risk-adjusted allocations using
    LIDS-verified CRIO insights.

CRIO INTEGRATION (CEO Directive ORDER B):
    - fragility_score: Risk scalar for position sizing
    - dominant_driver: Asset rotation bias

RISK SCALAR LOGIC:
    IF fragility_score > 0.70: reduce position size by >= 50%
    ELIF fragility_score < 0.40: allow full sizing (up to 10% NAV)
    ELSE: apply neutral weighting (no adjustment)

DOMINANT DRIVER ROTATION:
    - LIQUIDITY: favor BTC-USD, ETH-USD
    - CREDIT: reduce risk assets, favor cash
    - VOLATILITY: reduce all exposure
    - SENTIMENT: maintain neutral weights
    - UNKNOWN: default allocation

Generated: 2025-12-08
"""

from __future__ import annotations

import os
import sys
import json
import hashlib
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, date, timezone
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
import logging

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(override=True)


# =================================================================
# LOGGING
# =================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - IoS004.ALLOCATION - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ios004_crio_allocation_engine")


# =================================================================
# CONFIGURATION
# =================================================================

class AllocationConfig:
    """IoS-004 Allocation Configuration per CEO Directive"""

    # Database
    PGHOST = os.getenv("PGHOST", "127.0.0.1")
    PGPORT = int(os.getenv("PGPORT", "54322"))
    PGDATABASE = os.getenv("PGDATABASE", "postgres")
    PGUSER = os.getenv("PGUSER", "postgres")
    PGPASSWORD = os.getenv("PGPASSWORD", "postgres")

    # CEO Directive Risk Scalar Thresholds
    HIGH_FRAGILITY_THRESHOLD = 0.70  # Reduce by >= 50%
    LOW_FRAGILITY_THRESHOLD = 0.40   # Full sizing allowed

    # Risk Scalar Values
    HIGH_FRAGILITY_SCALAR = 0.50     # 50% reduction
    NEUTRAL_FRAGILITY_SCALAR = 1.00  # No change
    LOW_FRAGILITY_SCALAR = 1.00      # Full sizing

    # ADR-012 Position Limits
    MAX_SINGLE_POSITION_NAV = 0.10   # 10% NAV per position
    MAX_TOTAL_EXPOSURE = 0.75        # 75% max total exposure
    MIN_CASH_WEIGHT = 0.25           # 25% minimum cash

    # Canonical Assets
    CANONICAL_ASSETS = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'EURUSD']

    # Driver-based asset preferences
    DRIVER_PREFERENCES = {
        'LIQUIDITY': {'BTC-USD': 1.2, 'ETH-USD': 1.15, 'SOL-USD': 1.0, 'EURUSD': 0.8},
        'CREDIT': {'BTC-USD': 0.6, 'ETH-USD': 0.6, 'SOL-USD': 0.5, 'EURUSD': 0.9},
        'VOLATILITY': {'BTC-USD': 0.5, 'ETH-USD': 0.5, 'SOL-USD': 0.4, 'EURUSD': 0.7},
        'SENTIMENT': {'BTC-USD': 1.0, 'ETH-USD': 1.0, 'SOL-USD': 1.0, 'EURUSD': 1.0},
        'UNKNOWN': {'BTC-USD': 1.0, 'ETH-USD': 1.0, 'SOL-USD': 1.0, 'EURUSD': 1.0},
    }

    # Engine version
    ENGINE_VERSION = 'IoS-004_CRIO_v1.0'

    @classmethod
    def get_connection_string(cls) -> str:
        return f"postgresql://{cls.PGUSER}:{cls.PGPASSWORD}@{cls.PGHOST}:{cls.PGPORT}/{cls.PGDATABASE}"


# =================================================================
# CRIO RISK SCALAR ENGINE
# =================================================================

class CRIORiskScalar:
    """
    Computes risk scalar from LIDS-verified CRIO insights.

    CEO Directive Logic:
    - fragility_score > 0.70: reduce by >= 50%
    - fragility_score < 0.40: full sizing
    - else: neutral (no adjustment)
    """

    @staticmethod
    def compute_fragility_scalar(fragility_score: float) -> Tuple[float, str]:
        """
        Compute risk scalar based on fragility_score.

        Returns: (scalar, reason)
        """
        if fragility_score > AllocationConfig.HIGH_FRAGILITY_THRESHOLD:
            return (
                AllocationConfig.HIGH_FRAGILITY_SCALAR,
                f"HIGH_FRAGILITY: {fragility_score:.2f} > {AllocationConfig.HIGH_FRAGILITY_THRESHOLD} -> 50% reduction"
            )
        elif fragility_score < AllocationConfig.LOW_FRAGILITY_THRESHOLD:
            return (
                AllocationConfig.LOW_FRAGILITY_SCALAR,
                f"LOW_FRAGILITY: {fragility_score:.2f} < {AllocationConfig.LOW_FRAGILITY_THRESHOLD} -> full sizing"
            )
        else:
            return (
                AllocationConfig.NEUTRAL_FRAGILITY_SCALAR,
                f"NEUTRAL_FRAGILITY: {AllocationConfig.LOW_FRAGILITY_THRESHOLD} <= {fragility_score:.2f} <= {AllocationConfig.HIGH_FRAGILITY_THRESHOLD} -> no adjustment"
            )

    @staticmethod
    def compute_driver_weight(dominant_driver: str, asset_id: str) -> float:
        """
        Compute asset weight adjustment based on dominant driver.
        """
        preferences = AllocationConfig.DRIVER_PREFERENCES.get(
            dominant_driver,
            AllocationConfig.DRIVER_PREFERENCES['UNKNOWN']
        )
        return preferences.get(asset_id, 1.0)


# =================================================================
# REGIME ALLOCATION MATRIX
# =================================================================

class RegimeAllocationMatrix:
    """
    Base allocation weights by HMM regime state.
    These weights are then adjusted by CRIO risk scalars.
    """

    BASE_WEIGHTS = {
        'STRONG_BULL': 0.25,   # 25% per asset in strong bull
        'BULL': 0.20,          # 20% per asset in bull
        'PARABOLIC': 0.15,     # Reduce in parabolic (risk of reversal)
        'RANGE_UP': 0.15,      # 15% in range up
        'NEUTRAL': 0.10,       # 10% in neutral
        'RANGE_DOWN': 0.05,    # 5% in range down
        'BEAR': 0.00,          # No exposure in bear
        'STRONG_BEAR': 0.00,   # No exposure in strong bear
        'BROKEN': 0.00,        # No exposure in broken
    }

    @classmethod
    def get_base_weight(cls, regime: str) -> float:
        return cls.BASE_WEIGHTS.get(regime, 0.10)


# =================================================================
# CRIO ALLOCATION ENGINE
# =================================================================

class CRIOAllocationEngine:
    """
    IoS-004 CRIO-Aware Regime Allocation Engine.

    Integrates:
    1. HMM regime states from IoS-003
    2. LIDS-verified CRIO insights (fragility_score, dominant_driver)
    3. CEO Directive risk scalar logic
    """

    def __init__(self):
        self.conn = None
        self.allocation_id = str(uuid.uuid4())
        self.timestamp = datetime.now(timezone.utc)

    def connect(self):
        """Establish database connection"""
        self.conn = psycopg2.connect(AllocationConfig.get_connection_string())
        logger.info("Database connection established")

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def get_active_model_id(self) -> Optional[str]:
        """Get active HMM model ID"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT model_id FROM fhq_research.regime_model_registry
                WHERE is_active = true
                ORDER BY created_at DESC LIMIT 1
            """)
            row = cur.fetchone()
            return str(row[0]) if row else None

    def get_latest_crio_insight(self) -> Optional[Dict]:
        """
        Fetch latest LIDS-verified CRIO insight.

        Only returns insight if lids_verified = TRUE (CEO Directive compliant)
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT insight_id, research_date, fragility_score, dominant_driver,
                       regime_assessment, confidence, quad_hash, lids_verified
                FROM fhq_research.nightly_insights
                WHERE lids_verified = TRUE
                ORDER BY research_date DESC
                LIMIT 1
            """)
            return cur.fetchone()

    def get_regime_data(self, target_date: date) -> List[Dict]:
        """Fetch HMM regime data for allocation date"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT asset_id, regime_classification, regime_confidence,
                       lineage_hash, hash_self
                FROM fhq_perception.regime_daily
                WHERE timestamp = %s
                ORDER BY asset_id
            """, (target_date,))
            return cur.fetchall()

    def compute_allocations(
        self,
        regimes: List[Dict],
        crio_insight: Optional[Dict],
        model_id: str,
        target_date: date
    ) -> Dict[str, Any]:
        """
        Compute risk-adjusted allocations.

        Flow:
        1. Get base weights from regime states
        2. Apply CRIO fragility scalar (CEO Directive)
        3. Apply driver-based asset rotation
        4. Enforce ADR-012 position limits
        5. Generate governance hashes
        """
        result = {
            'allocation_id': self.allocation_id,
            'target_date': str(target_date),
            'model_id': model_id,
            'engine_version': AllocationConfig.ENGINE_VERSION,
            'crio_integrated': crio_insight is not None,
            'allocations': [],
            'risk_scalar': None,
            'dominant_driver': None,
        }

        # Determine risk scalar from CRIO
        if crio_insight:
            fragility_score = float(crio_insight.get('fragility_score', 0.5))
            dominant_driver = crio_insight.get('dominant_driver', 'UNKNOWN')

            risk_scalar, scalar_reason = CRIORiskScalar.compute_fragility_scalar(fragility_score)

            result['crio_insight'] = {
                'insight_id': str(crio_insight['insight_id']),
                'research_date': str(crio_insight['research_date']),
                'fragility_score': fragility_score,
                'dominant_driver': dominant_driver,
                'quad_hash': crio_insight.get('quad_hash'),
            }
            result['risk_scalar'] = {
                'value': risk_scalar,
                'reason': scalar_reason,
                'fragility_score': fragility_score,
            }
            result['dominant_driver'] = dominant_driver

            logger.info(f"CRIO Integration: {scalar_reason}")
            logger.info(f"Dominant Driver: {dominant_driver}")
        else:
            # No CRIO insight - use neutral defaults
            risk_scalar = 1.0
            dominant_driver = 'UNKNOWN'
            result['risk_scalar'] = {
                'value': 1.0,
                'reason': 'NO_CRIO_INSIGHT: using neutral defaults',
                'fragility_score': None,
            }
            logger.warning("No LIDS-verified CRIO insight available - using neutral defaults")

        # Compute allocations for each asset
        total_exposure = Decimal('0')
        allocations = []

        for regime_data in regimes:
            asset_id = regime_data['asset_id']
            regime = regime_data['regime_classification']
            confidence = float(regime_data.get('regime_confidence', 0.5))

            # Step 1: Base weight from regime
            base_weight = RegimeAllocationMatrix.get_base_weight(regime)

            # Step 2: Apply CRIO fragility scalar
            scaled_weight = base_weight * risk_scalar

            # Step 3: Apply driver-based adjustment
            driver_weight = CRIORiskScalar.compute_driver_weight(dominant_driver, asset_id)
            adjusted_weight = scaled_weight * driver_weight

            # Step 4: Enforce ADR-012 position limits
            constrained_weight = min(
                adjusted_weight,
                AllocationConfig.MAX_SINGLE_POSITION_NAV
            )

            # Ensure non-negative
            constrained_weight = max(0, constrained_weight)

            total_exposure += Decimal(str(constrained_weight))

            allocations.append({
                'asset_id': asset_id,
                'regime': regime,
                'confidence': confidence,
                'base_weight': base_weight,
                'risk_scalar_applied': risk_scalar,
                'driver_adjustment': driver_weight,
                'exposure_raw': adjusted_weight,
                'exposure_constrained': constrained_weight,
            })

        # Enforce total exposure limit
        if total_exposure > Decimal(str(AllocationConfig.MAX_TOTAL_EXPOSURE)):
            scale_factor = Decimal(str(AllocationConfig.MAX_TOTAL_EXPOSURE)) / total_exposure
            for alloc in allocations:
                alloc['exposure_constrained'] = float(
                    Decimal(str(alloc['exposure_constrained'])) * scale_factor
                )
            total_exposure = Decimal(str(AllocationConfig.MAX_TOTAL_EXPOSURE))
            logger.info(f"Total exposure capped at {AllocationConfig.MAX_TOTAL_EXPOSURE}")

        # Calculate cash weight
        cash_weight = Decimal('1.0') - total_exposure

        result['allocations'] = allocations
        result['total_exposure'] = float(total_exposure)
        result['cash_weight'] = float(cash_weight)

        return result

    def persist_allocations(
        self,
        allocations_result: Dict,
        model_id: str,
        target_date: date
    ) -> bool:
        """Persist allocations to target_exposure_daily with CRIO lineage"""

        with self.conn.cursor() as cur:
            # First, delete any existing allocations for this target date
            # This avoids conflicts with portfolio invariant trigger
            cur.execute("""
                DELETE FROM fhq_positions.target_exposure_daily
                WHERE timestamp = %s
            """, (target_date,))
            deleted_count = cur.rowcount
            if deleted_count > 0:
                logger.info(f"  Cleared {deleted_count} existing allocations for {target_date}")

            # CRIO reference for lineage
            crio_ref = allocations_result.get('crio_insight', {})
            lineage_data = {
                'allocation_id': self.allocation_id,
                'crio_insight_id': crio_ref.get('insight_id'),
                'crio_quad_hash': crio_ref.get('quad_hash'),
                'risk_scalar': allocations_result['risk_scalar']['value'],
                'dominant_driver': allocations_result.get('dominant_driver'),
            }
            lineage_hash = hashlib.sha256(
                json.dumps(lineage_data, sort_keys=True).encode()
            ).hexdigest()

            # Track RUNNING total exposure for portfolio invariant
            # The trigger validates: cash_weight = 1.0 - SUM(exposure) including current row
            running_total = Decimal('0')

            for i, alloc in enumerate(allocations_result['allocations']):
                asset_id = alloc['asset_id']
                exposure_raw = Decimal(str(alloc['exposure_raw']))
                exposure_constrained = Decimal(str(alloc['exposure_constrained']))
                regime = alloc['regime']
                confidence = Decimal(str(alloc['confidence']))

                # Add current row's exposure to running total
                running_total += exposure_constrained
                # Cash weight is complement of running total (including this row)
                cash_weight = Decimal('1.0') - running_total

                # Generate governance hash
                hash_data = f"{asset_id}|{target_date}|{regime}|{exposure_constrained}|{self.allocation_id}"
                hash_self = hashlib.sha256(hash_data.encode()).hexdigest()

                # Insert allocation record with running cash_weight
                cur.execute("""
                    INSERT INTO fhq_positions.target_exposure_daily
                    (asset_id, timestamp, exposure_raw, exposure_constrained, cash_weight,
                     model_id, regime_label, confidence, lineage_hash, hash_prev, hash_self,
                     created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    asset_id, target_date, float(exposure_raw), float(exposure_constrained),
                    float(cash_weight), model_id, regime, float(confidence),
                    lineage_hash, 'CRIO_' + (crio_ref.get('quad_hash') or 'NONE')[:16],
                    hash_self, self.timestamp
                ))

                logger.info(
                    f"  {asset_id}: {regime} -> {float(exposure_constrained)*100:.1f}% "
                    f"(scalar: {alloc['risk_scalar_applied']:.2f}, driver: {alloc['driver_adjustment']:.2f})"
                )

            # Log audit event
            evidence_hash = hashlib.sha256(
                json.dumps(allocations_result, sort_keys=True, default=str).encode()
            ).hexdigest()

            cur.execute("""
                INSERT INTO fhq_meta.ios_audit_log
                (audit_id, ios_id, event_type, event_timestamp, actor, gate_level,
                 event_data, evidence_hash)
                VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s)
            """, (
                'IoS-004',
                'CRIO_ALLOCATION_COMPUTED',
                self.timestamp,
                'STIG',
                'G1',
                json.dumps({
                    'allocation_id': self.allocation_id,
                    'target_date': str(target_date),
                    'crio_integrated': allocations_result['crio_integrated'],
                    'risk_scalar': allocations_result['risk_scalar'],
                    'dominant_driver': allocations_result.get('dominant_driver'),
                    'total_exposure': allocations_result['total_exposure'],
                    'cash_weight': allocations_result['cash_weight'],
                    'engine_version': AllocationConfig.ENGINE_VERSION,
                }, default=str),
                evidence_hash[:16]
            ))

            self.conn.commit()
            return True

    def run(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Execute CRIO-aware allocation for target date.

        If no target_date, uses latest available regime date.
        """
        logger.info("=" * 60)
        logger.info("IoS-004 CRIO-AWARE REGIME ALLOCATION ENGINE")
        logger.info(f"Allocation ID: {self.allocation_id}")
        logger.info(f"Engine: {AllocationConfig.ENGINE_VERSION}")
        logger.info("=" * 60)

        # Get active model
        model_id = self.get_active_model_id()
        if not model_id:
            logger.error("No active HMM model found")
            return {'success': False, 'error': 'No active HMM model'}

        logger.info(f"Model ID: {model_id[:8]}...")

        # Get latest CRIO insight
        crio_insight = self.get_latest_crio_insight()
        if crio_insight:
            logger.info(f"CRIO Insight: {crio_insight['research_date']}")
            logger.info(f"  fragility_score: {crio_insight['fragility_score']}")
            logger.info(f"  dominant_driver: {crio_insight['dominant_driver']}")
            logger.info(f"  quad_hash: {crio_insight['quad_hash']}")
        else:
            logger.warning("No LIDS-verified CRIO insight available")

        # Determine target date
        if target_date is None:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT MAX(timestamp) FROM fhq_perception.regime_daily
                """)
                row = cur.fetchone()
                target_date = row[0] if row and row[0] else date.today()

        logger.info(f"Target Date: {target_date}")

        # Get regime data
        regimes = self.get_regime_data(target_date)
        if not regimes:
            logger.error(f"No regime data for {target_date}")
            return {'success': False, 'error': f'No regime data for {target_date}'}

        logger.info(f"Found {len(regimes)} assets with regime data")

        # Compute allocations
        allocations_result = self.compute_allocations(
            regimes, crio_insight, model_id, target_date
        )

        # Persist to database
        logger.info("\nPersisting allocations:")
        self.persist_allocations(allocations_result, model_id, target_date)

        logger.info("=" * 60)
        logger.info(f"Total Exposure: {allocations_result['total_exposure']*100:.1f}%")
        logger.info(f"Cash Weight: {allocations_result['cash_weight']*100:.1f}%")
        logger.info("=" * 60)

        allocations_result['success'] = True
        return allocations_result


# =================================================================
# PUBLIC API
# =================================================================

def run_crio_allocation(target_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Public API for running CRIO-aware allocation.

    Called by orchestrator after IoS-003 regime update.
    """
    engine = CRIOAllocationEngine()
    try:
        engine.connect()
        return engine.run(target_date)
    finally:
        engine.close()


def get_latest_allocation() -> Optional[Dict]:
    """Get latest allocation result from database"""
    conn = psycopg2.connect(AllocationConfig.get_connection_string())
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT asset_id, timestamp, exposure_raw, exposure_constrained,
                       cash_weight, regime_label, confidence, lineage_hash
                FROM fhq_positions.target_exposure_daily
                WHERE timestamp = (SELECT MAX(timestamp) FROM fhq_positions.target_exposure_daily)
                ORDER BY asset_id
            """)
            return cur.fetchall()
    finally:
        conn.close()


# =================================================================
# MAIN
# =================================================================

def main():
    """Run CRIO-aware allocation engine."""
    result = run_crio_allocation()
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get('success') else 1


if __name__ == "__main__":
    sys.exit(main())
