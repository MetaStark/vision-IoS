#!/usr/bin/env python3
"""
INDEPENDENT REGIME OUTCOME GENERATOR
=====================================
CEO-DIR-2026-020 D1: Eliminate Outcome Contamination

This is the ONLY admissible regime outcome generator for FjordHQ.

METHODOLOGY (Documented, Reproducible, Court-Proof):
----------------------------------------------------
1. Source: fhq_market.prices ONLY (no prediction sources)
2. Lookback: 20 trading days
3. Metrics:
   - return_20d: (close_t / close_t-20) - 1
   - volatility_20d: std(daily_returns) over 20 days
   - volatility_ratio: current vol / 60-day avg vol

4. Regime Classification:
   - STRONG_BULL: return > 2*vol AND return > 5%
   - BULL: return > 0.5*vol AND return > 0
   - NEUTRAL: |return| < 0.5*vol
   - BEAR: return < -0.5*vol AND return < 0
   - STRONG_BEAR: return < -2*vol AND return < -5%
   - VOLATILE_NON_DIRECTIONAL: vol_ratio > 2.0 AND |return| < vol

EVIDENCE CHAIN:
--------------
Every outcome written to fhq_research.outcome_ledger includes:
- evidence_source: 'fhq_market.prices' (REQUIRED)
- evidence_data: Full calculation inputs (prices, returns, volatility)
- content_hash: SHA-256 of deterministic output

Author: STIG (CTO)
Date: 2026-01-08
Classification: CEO-DIR-2026-020 COMPLIANT
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv
import numpy as np

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - INDEPENDENT_REGIME - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ios003_independent_regime_outcome")

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_CONFIG = {
    "host": os.getenv("PGHOST", "127.0.0.1"),
    "port": os.getenv("PGPORT", "54322"),
    "database": os.getenv("PGDATABASE", "postgres"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "postgres")
}

# Regime classification parameters (DOCUMENTED)
LOOKBACK_DAYS = 20
VOLATILITY_AVG_DAYS = 60
STRONG_MOVE_THRESHOLD = 0.05  # 5% for strong bull/bear
VOLATILITY_RATIO_HIGH = 2.0    # 2x avg volatility = high vol regime

# Canonical regime labels (CEO-DIR-2026-020 compliant)
CANONICAL_REGIMES = [
    'STRONG_BULL',
    'BULL',
    'NEUTRAL',
    'BEAR',
    'STRONG_BEAR',
    'VOLATILE_NON_DIRECTIONAL',
    'COMPRESSION',
    'BROKEN',
    'UNTRUSTED'
]


# =============================================================================
# INDEPENDENT REGIME CALCULATOR
# =============================================================================

class IndependentRegimeCalculator:
    """
    CEO-DIR-2026-020 D1: Independent regime outcome generator.

    This class derives regime outcomes ONLY from fhq_market.prices.
    No prediction sources. No circular validation. Court-proof evidence.
    """

    def __init__(self):
        self.conn = None
        self.run_id = f"REGIME-IND-{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    def connect(self):
        """Establish database connection."""
        if not self.conn or self.conn.closed:
            self.conn = psycopg2.connect(**DB_CONFIG)
        return self.conn

    def close(self):
        """Close database connection."""
        if self.conn and not self.conn.closed:
            self.conn.close()

    def _compute_hash(self, data: Dict) -> str:
        """Compute SHA-256 hash of data for court-proof evidence."""
        data_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()

    def get_price_data(self, canonical_id: str, as_of_date: datetime) -> Optional[Dict]:
        """
        Fetch price data from fhq_market.prices for regime calculation.

        Returns 60 days of price data ending at as_of_date.
        """
        conn = self.connect()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    canonical_id,
                    timestamp::date as price_date,
                    close,
                    open,
                    high,
                    low,
                    volume
                FROM fhq_market.prices
                WHERE canonical_id = %s
                  AND timestamp <= %s
                  AND timestamp > %s - INTERVAL '%s days'
                ORDER BY timestamp DESC
            """, (canonical_id, as_of_date, as_of_date, VOLATILITY_AVG_DAYS + 5))

            rows = cur.fetchall()

            if len(rows) < LOOKBACK_DAYS:
                logger.warning(f"Insufficient data for {canonical_id}: {len(rows)} < {LOOKBACK_DAYS}")
                return None

            return {
                'canonical_id': canonical_id,
                'as_of_date': as_of_date.isoformat(),
                'prices': [dict(r) for r in rows],
                'data_points': len(rows)
            }

    def calculate_regime(self, price_data: Dict) -> Dict:
        """
        Calculate regime from price data using documented methodology.

        METHODOLOGY:
        1. 20-day return: (close_t / close_t-20) - 1
        2. 20-day volatility: std(daily_returns)
        3. Volatility ratio: current_vol / 60-day_avg_vol
        4. Regime classification based on return/volatility bands
        """
        prices = price_data['prices']

        if len(prices) < LOOKBACK_DAYS:
            return {
                'regime': 'UNTRUSTED',
                'reason': f'Insufficient data: {len(prices)} < {LOOKBACK_DAYS}',
                'confidence': 0.0
            }

        # Extract close prices (sorted newest to oldest)
        closes = [float(p['close']) for p in prices]

        # Calculate daily returns
        daily_returns = []
        for i in range(len(closes) - 1):
            if closes[i+1] > 0:
                ret = (closes[i] / closes[i+1]) - 1
                daily_returns.append(ret)

        if len(daily_returns) < LOOKBACK_DAYS - 1:
            return {
                'regime': 'UNTRUSTED',
                'reason': f'Insufficient returns: {len(daily_returns)}',
                'confidence': 0.0
            }

        # 20-day return
        if closes[LOOKBACK_DAYS - 1] > 0:
            return_20d = (closes[0] / closes[LOOKBACK_DAYS - 1]) - 1
        else:
            return_20d = 0.0

        # 20-day volatility (annualized)
        vol_20d = float(np.std(daily_returns[:LOOKBACK_DAYS])) * np.sqrt(252)

        # 60-day average volatility (if available)
        if len(daily_returns) >= VOLATILITY_AVG_DAYS:
            vol_60d_avg = float(np.std(daily_returns[:VOLATILITY_AVG_DAYS])) * np.sqrt(252)
        else:
            vol_60d_avg = vol_20d

        # Volatility ratio
        vol_ratio = vol_20d / vol_60d_avg if vol_60d_avg > 0 else 1.0

        # REGIME CLASSIFICATION (Documented Rules)
        regime = 'NEUTRAL'
        confidence = 0.7
        reason = ''

        # High volatility regime check first
        if vol_ratio > VOLATILITY_RATIO_HIGH and abs(return_20d) < vol_20d:
            regime = 'VOLATILE_NON_DIRECTIONAL'
            confidence = 0.75
            reason = f'High vol ratio ({vol_ratio:.2f}) with low directional move'

        # Strong bull
        elif return_20d > 2 * vol_20d and return_20d > STRONG_MOVE_THRESHOLD:
            regime = 'STRONG_BULL'
            confidence = 0.85
            reason = f'Return {return_20d:.2%} > 2*vol ({2*vol_20d:.2%}) and > {STRONG_MOVE_THRESHOLD:.0%}'

        # Bull
        elif return_20d > 0.5 * vol_20d and return_20d > 0:
            regime = 'BULL'
            confidence = 0.75
            reason = f'Return {return_20d:.2%} > 0.5*vol ({0.5*vol_20d:.2%})'

        # Strong bear
        elif return_20d < -2 * vol_20d and return_20d < -STRONG_MOVE_THRESHOLD:
            regime = 'STRONG_BEAR'
            confidence = 0.85
            reason = f'Return {return_20d:.2%} < -2*vol ({-2*vol_20d:.2%}) and < -{STRONG_MOVE_THRESHOLD:.0%}'

        # Bear
        elif return_20d < -0.5 * vol_20d and return_20d < 0:
            regime = 'BEAR'
            confidence = 0.75
            reason = f'Return {return_20d:.2%} < -0.5*vol ({-0.5*vol_20d:.2%})'

        # Neutral (default)
        else:
            regime = 'NEUTRAL'
            confidence = 0.70
            reason = f'Return {return_20d:.2%} within +/- 0.5*vol ({0.5*vol_20d:.2%})'

        return {
            'regime': regime,
            'confidence': confidence,
            'reason': reason,
            'metrics': {
                'return_20d': round(return_20d, 6),
                'volatility_20d': round(vol_20d, 6),
                'volatility_60d_avg': round(vol_60d_avg, 6),
                'volatility_ratio': round(vol_ratio, 4),
                'data_points': len(closes),
                'lookback_days': LOOKBACK_DAYS
            }
        }

    def write_outcome(self, canonical_id: str, as_of_date: datetime,
                      regime_result: Dict, price_data: Dict) -> Optional[str]:
        """
        Write regime outcome to fhq_research.outcome_ledger.

        Evidence source is ALWAYS 'fhq_market.prices'.
        Evidence data includes full calculation audit trail.
        """
        conn = self.connect()

        # Build evidence data (court-proof)
        evidence_data = {
            'methodology': 'CEO-DIR-2026-020_INDEPENDENT_REGIME_V1',
            'source_table': 'fhq_market.prices',
            'canonical_id': canonical_id,
            'as_of_date': as_of_date.isoformat(),
            'lookback_days': LOOKBACK_DAYS,
            'calculation': regime_result,
            'raw_query': f"""
SELECT canonical_id, timestamp::date, close, open, high, low, volume
FROM fhq_market.prices
WHERE canonical_id = '{canonical_id}'
  AND timestamp <= '{as_of_date.isoformat()}'
  AND timestamp > '{as_of_date.isoformat()}'::timestamp - INTERVAL '{VOLATILITY_AVG_DAYS} days'
ORDER BY timestamp DESC
""",
            'data_point_count': price_data['data_points'],
            'run_id': self.run_id,
            'generated_at': datetime.now(timezone.utc).isoformat()
        }

        # Compute content hash
        content_hash = self._compute_hash({
            'canonical_id': canonical_id,
            'as_of_date': as_of_date.isoformat(),
            'regime': regime_result['regime'],
            'metrics': regime_result.get('metrics', {})
        })

        outcome_id = None

        with conn.cursor() as cur:
            try:
                cur.execute("""
                    INSERT INTO fhq_research.outcome_ledger (
                        outcome_id,
                        outcome_type,
                        outcome_domain,
                        outcome_value,
                        outcome_timestamp,
                        evidence_source,
                        evidence_data,
                        content_hash,
                        hash_chain_id,
                        created_by,
                        created_at
                    ) VALUES (
                        gen_random_uuid(),
                        'REGIME',
                        %s,
                        %s,
                        %s,
                        'fhq_market.prices',
                        %s,
                        %s,
                        %s,
                        'IOS003_INDEPENDENT_REGIME',
                        NOW()
                    )
                    RETURNING outcome_id
                """, (
                    canonical_id,
                    regime_result['regime'],
                    as_of_date,
                    Json(evidence_data),
                    content_hash,
                    f"CHAIN-{self.run_id}-{canonical_id}"
                ))

                result = cur.fetchone()
                if result:
                    outcome_id = str(result[0])

                conn.commit()
                logger.info(f"Written independent REGIME outcome: {canonical_id} = {regime_result['regime']} (ID: {outcome_id})")

            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to write outcome for {canonical_id}: {e}")
                raise

        return outcome_id

    def generate_regime_outcomes(self, as_of_date: Optional[datetime] = None) -> Dict:
        """
        Generate independent regime outcomes for all tracked assets.

        Returns summary of outcomes generated.
        """
        if as_of_date is None:
            as_of_date = datetime.now(timezone.utc)

        logger.info("=" * 60)
        logger.info("INDEPENDENT REGIME OUTCOME GENERATOR")
        logger.info(f"Run ID: {self.run_id}")
        logger.info(f"As-of Date: {as_of_date.isoformat()}")
        logger.info(f"Methodology: CEO-DIR-2026-020 D1 COMPLIANT")
        logger.info("=" * 60)

        # Get list of assets with recent price data
        conn = self.connect()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT canonical_id
                FROM fhq_market.prices
                WHERE timestamp > NOW() - INTERVAL '7 days'
                ORDER BY canonical_id
            """)
            assets = [r['canonical_id'] for r in cur.fetchall()]

        logger.info(f"Found {len(assets)} assets with recent price data")

        results = {
            'run_id': self.run_id,
            'as_of_date': as_of_date.isoformat(),
            'assets_processed': 0,
            'outcomes_written': 0,
            'outcomes_skipped': 0,
            'regime_distribution': {},
            'outcomes': []
        }

        for canonical_id in assets:
            results['assets_processed'] += 1

            try:
                # Get price data
                price_data = self.get_price_data(canonical_id, as_of_date)

                if price_data is None:
                    results['outcomes_skipped'] += 1
                    continue

                # Calculate regime
                regime_result = self.calculate_regime(price_data)

                # Write outcome
                outcome_id = self.write_outcome(canonical_id, as_of_date, regime_result, price_data)

                if outcome_id:
                    results['outcomes_written'] += 1

                    # Track distribution
                    regime = regime_result['regime']
                    results['regime_distribution'][regime] = results['regime_distribution'].get(regime, 0) + 1

                    results['outcomes'].append({
                        'canonical_id': canonical_id,
                        'regime': regime,
                        'confidence': regime_result['confidence'],
                        'outcome_id': outcome_id
                    })
                else:
                    results['outcomes_skipped'] += 1

            except Exception as e:
                logger.error(f"Error processing {canonical_id}: {e}")
                results['outcomes_skipped'] += 1

        logger.info("=" * 60)
        logger.info(f"Generation Complete")
        logger.info(f"Assets processed: {results['assets_processed']}")
        logger.info(f"Outcomes written: {results['outcomes_written']}")
        logger.info(f"Outcomes skipped: {results['outcomes_skipped']}")
        logger.info(f"Regime distribution: {results['regime_distribution']}")
        logger.info("=" * 60)

        return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run independent regime outcome generation."""
    calculator = IndependentRegimeCalculator()

    try:
        calculator.connect()
        results = calculator.generate_regime_outcomes()

        # Output results as JSON
        print(json.dumps(results, indent=2, default=str))

        return 0 if results['outcomes_written'] > 0 else 1

    except Exception as e:
        logger.error(f"Generation failed: {e}")
        return 2

    finally:
        calculator.close()


if __name__ == "__main__":
    exit(main())
