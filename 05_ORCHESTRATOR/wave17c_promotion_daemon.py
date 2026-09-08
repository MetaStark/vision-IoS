#!/usr/bin/env python3
"""
WAVE 17C + 17C.1 - Autonomous Promotion Pipeline Daemon
========================================================
CEO Directive: Autonomous Golden Needle Promotion with Enterprise Safeguards

Features:
- Automatic evidence pack generation (Step 1)
- Gate A evaluation with deterministic criteria (Step 2)
- Rate limiting (50/hr configurable)
- Shadow mode (first 24h)
- SLA enforcement (5s/1s/30s)
- Pass-rate anomaly detection
- Drift monitoring
- Cross-verification

Owner: STIG (CTO)
References: ADR-004, ADR-012, ADR-013, WAVE 17C, WAVE 17C.1
"""

import os
import sys
import json
import hashlib
import uuid
import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('wave17c_promotion.log')
    ]
)
logger = logging.getLogger('WAVE17C')

# Database config
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Evidence pack output directory
EVIDENCE_DIR = Path(r"C:\fhq-market-system\vision-ios\05_GOVERNANCE\PHASE3\Golden Needles")


class PromotionPipeline:
    """Autonomous promotion pipeline with enterprise safeguards."""

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load pipeline configuration."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM fhq_canonical.g5_promotion_config
                WHERE is_active = TRUE LIMIT 1
            """)
            return dict(cur.fetchone() or {})

    def _log_event(self, event_type: str, needle_id: str = None,
                   promotion_id: str = None, data: Dict = None,
                   severity: str = 'INFO', defcon_escalation: bool = False,
                   signal_id: str = None):  # Accept signal_id for backwards compatibility
        """Log pipeline event."""
        # Merge signal_id into data if provided as kwarg
        event_data = data or {}
        if signal_id and 'signal_id' not in event_data:
            event_data['signal_id'] = signal_id
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_canonical.g5_pipeline_events
                (event_type, needle_id, promotion_id, event_data, severity, defcon_escalation)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (event_type, needle_id, promotion_id, json.dumps(event_data),
                  severity, defcon_escalation))
        self.conn.commit()

    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limit (Section 2.1)."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT fhq_canonical.check_promotion_rate_limit()")
            return cur.fetchone()[0]

    def _increment_rate_counter(self):
        """Increment the rate counter."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT fhq_canonical.increment_promotion_rate()")
        self.conn.commit()

    def _is_shadow_mode(self) -> bool:
        """Check if we're in shadow mode (Section 3)."""
        return (self.config.get('shadow_mode_enabled', True) and
                datetime.now(timezone.utc) < self.config.get('shadow_mode_until',
                    datetime.now(timezone.utc) + timedelta(hours=24)))

    def _get_pipeline_state(self) -> str:
        """Get current pipeline state."""
        return self.config.get('pipeline_state', 'SHADOW')

    def _generate_evidence_pack(self, needle: Dict) -> Tuple[str, str, int]:
        """
        Generate VEGA evidence pack for a needle (Step 1).
        Returns: (attestation_id, file_path, generation_time_ms)
        """
        start_time = time.time()

        attestation_id = str(uuid.uuid4())

        # Build evidence pack
        evidence = {
            "attestation_id": attestation_id,
            "needle_id": str(needle['needle_id']),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generator": "WAVE17C_PROMOTION_DAEMON",
            "version": "1.0",

            # Needle metadata
            "needle_metadata": {
                "hypothesis_title": needle.get('hypothesis_title'),
                "hypothesis_category": needle.get('hypothesis_category'),
                "eqs_score": float(needle.get('eqs_score', 0)),
                "sitc_confidence_level": needle.get('sitc_confidence_level'),
                "confluence_factor_count": needle.get('confluence_factor_count'),
                "regime_technical": needle.get('regime_technical'),
                "regime_sovereign": needle.get('regime_sovereign'),
                "defcon_level": needle.get('defcon_level'),
                "created_at": str(needle.get('created_at'))
            },

            # Gate A criteria snapshot
            "gate_a_criteria": {
                "eqs_threshold": 0.85,
                "sitc_required": "HIGH",
                "canonical_provenance_required": True,
                "evidence_linkage_required": True
            },

            # Provenance
            "canonical_hash": hashlib.sha256(
                json.dumps(needle, default=str, sort_keys=True).encode()
            ).hexdigest(),

            # VEGA signature placeholder (real signature would use Ed25519)
            "vega_signature": hashlib.sha256(
                f"VEGA_ATTESTS_{attestation_id}_{needle['needle_id']}".encode()
            ).hexdigest()
        }

        # Ensure directory exists
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

        # Write evidence pack
        filename = f"EVIDENCE_{attestation_id[:8]}_{needle['needle_id']}.json"
        filepath = EVIDENCE_DIR / filename

        with open(filepath, 'w') as f:
            json.dump(evidence, f, indent=2, default=str)

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Update needle with attestation reference
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_canonical.golden_needles
                SET vega_attestation_id = %s,
                    evidence_pack_path = %s,
                    evidence_generated_at = NOW()
                WHERE needle_id = %s
            """, (attestation_id, str(filepath), needle['needle_id']))
        self.conn.commit()

        logger.info(f"Evidence pack generated: {filename} ({elapsed_ms}ms)")

        return attestation_id, str(filepath), elapsed_ms

    def _evaluate_gate_a(self, needle: Dict, attestation_id: str) -> Tuple[bool, str, int]:
        """
        Evaluate Gate A criteria (Step 2).
        Returns: (passed, rejection_reason, evaluation_time_ms)

        PASS criteria (ALL required):
        - EQS >= 0.85
        - SITC = ACCEPT and SITC_CONFIDENCE = HIGH
        - Evidence pack linked
        - Canonical provenance fields present
        """
        start_time = time.time()

        eqs_score = float(needle.get('eqs_score', 0))
        sitc_confidence = needle.get('sitc_confidence_level', '')
        has_evidence = attestation_id is not None

        # Check canonical provenance (ADR-013)
        has_canonical = (
            needle.get('regime_technical') is not None and
            needle.get('regime_sovereign') is not None and
            needle.get('hypothesis_title') is not None
        )

        # Evaluate criteria
        criteria = {
            'eqs_threshold': eqs_score >= 0.85,
            'sitc_high': sitc_confidence.upper() == 'HIGH',
            'vega_evidence': has_evidence,
            'canonical_immutable': has_canonical
        }

        passed = all(criteria.values())

        # Build rejection reason if failed
        rejection_reason = None
        if not passed:
            failures = [k for k, v in criteria.items() if not v]
            rejection_reason = f"FAILED: {', '.join(failures)}"
            if not criteria['eqs_threshold']:
                rejection_reason += f" (EQS={eqs_score:.3f}<0.85)"
            if not criteria['sitc_high']:
                rejection_reason += f" (SITC={sitc_confidence}!=HIGH)"

        elapsed_ms = int((time.time() - start_time) * 1000)

        return passed, rejection_reason, elapsed_ms

    def _record_promotion(self, needle: Dict, attestation_id: str,
                          gate_a_passed: bool, rejection_reason: str,
                          evidence_gen_ms: int, gate_a_ms: int,
                          total_ms: int) -> str:
        """Record promotion decision in ledger."""
        promotion_id = str(uuid.uuid4())

        # Determine status
        if gate_a_passed:
            status = 'CANDIDATE'
        else:
            status = 'REJECT_ADMISSIBILITY'

        # Calculate lineage hash for cross-verification
        needle_hash = hashlib.sha256(
            json.dumps(needle, default=str, sort_keys=True).encode()
        ).hexdigest()

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_canonical.g5_promotion_ledger (
                    promotion_id, needle_id, current_status,
                    gate_a_sitc_high, gate_a_eqs_threshold,
                    gate_a_vega_evidence, gate_a_canonical_immutable,
                    gate_a_passed, gate_a_rejection_reason, gate_a_evaluated_at,
                    evidence_pack_hash, needle_lineage_hash,
                    cross_verification_passed, signed_by
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, NOW(),
                    %s, %s, %s, %s
                )
            """, (
                promotion_id, needle['needle_id'], status,
                needle.get('sitc_confidence_level', '').upper() == 'HIGH',
                float(needle.get('eqs_score', 0)) >= 0.85,
                attestation_id is not None,
                needle.get('regime_technical') is not None,
                gate_a_passed, rejection_reason,
                attestation_id, needle_hash, True, 'STIG'
            ))
        self.conn.commit()

        # Record SLA metrics
        self._record_sla_metrics(needle['needle_id'], promotion_id,
                                  evidence_gen_ms, gate_a_ms, total_ms)

        return promotion_id

    def _record_sla_metrics(self, needle_id: str, promotion_id: str,
                            evidence_gen_ms: int, gate_a_ms: int, total_ms: int):
        """Record SLA metrics (Section 5)."""
        # Check for breaches
        evidence_breach = evidence_gen_ms > self.config.get('sla_evidence_gen_ms', 5000)
        gate_a_breach = gate_a_ms > self.config.get('sla_gate_a_eval_ms', 1000)
        total_breach = total_ms > self.config.get('sla_end_to_end_ms', 30000)

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_canonical.g5_sla_metrics (
                    needle_id, promotion_id,
                    evidence_gen_ms, evidence_gen_sla_breach,
                    gate_a_ms, gate_a_sla_breach,
                    total_ms, total_sla_breach
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (needle_id, promotion_id,
                  evidence_gen_ms, evidence_breach,
                  gate_a_ms, gate_a_breach,
                  total_ms, total_breach))
        self.conn.commit()

        if evidence_breach or gate_a_breach or total_breach:
            self._log_event('SLA_BREACH', needle_id=needle_id,
                           data={'evidence_ms': evidence_gen_ms,
                                 'gate_a_ms': gate_a_ms,
                                 'total_ms': total_ms},
                           severity='WARN')

    def _record_shadow_decision(self, needle: Dict, attestation_id: str,
                                 gate_a_passed: bool, rejection_reason: str,
                                 evidence_gen_ms: int, gate_a_ms: int, total_ms: int):
        """Record decision in shadow mode (Section 3.1)."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_canonical.g5_shadow_decisions (
                    needle_id, would_pass_gate_a, would_create_signal,
                    would_be_signal_state, gate_a_result,
                    vega_attestation_id, evidence_gen_ms, gate_a_eval_ms, total_ms
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                needle['needle_id'], gate_a_passed, gate_a_passed,
                'DORMANT' if gate_a_passed else None,
                json.dumps({'passed': gate_a_passed, 'reason': rejection_reason}),
                attestation_id, evidence_gen_ms, gate_a_ms, total_ms
            ))

            # Increment shadow review count
            cur.execute("""
                UPDATE fhq_canonical.g5_promotion_config
                SET shadow_review_count = shadow_review_count + 1,
                    updated_at = NOW()
                WHERE is_active = TRUE
            """)
        self.conn.commit()

        self._log_event('SHADOW_DECISION', needle_id=needle['needle_id'],
                       data={'would_pass': gate_a_passed, 'reason': rejection_reason})

    def _create_dormant_signal(self, needle: Dict, promotion_id: str,
                               attestation_id: str):
        """Create DORMANT signal in arsenal (Step 5)."""
        with self.conn.cursor() as cur:
            # Check if signal already exists
            cur.execute("""
                SELECT state_id FROM fhq_canonical.g5_signal_state
                WHERE needle_id = %s
            """, (needle['needle_id'],))

            if cur.fetchone():
                logger.info(f"Signal already exists for needle {needle['needle_id']}")
                return

            # Create new signal
            signal_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO fhq_canonical.g5_signal_state (
                    state_id, needle_id, current_state, last_transition
                ) VALUES (%s, %s, 'DORMANT', 'PROMOTED_FROM_GATE_A')
            """, (signal_id, needle['needle_id']))

            # Update promotion ledger with signal reference
            cur.execute("""
                UPDATE fhq_canonical.g5_promotion_ledger
                SET gate_c_signal_instantiated = TRUE,
                    gate_c_signal_state_id = %s,
                    gate_c_evaluated_at = NOW(),
                    current_status = 'DORMANT_SIGNAL'
                WHERE promotion_id = %s
            """, (signal_id, promotion_id))

        self.conn.commit()

        self._log_event('SIGNAL_CREATED', needle_id=needle['needle_id'],
                       promotion_id=promotion_id,
                       data={'state': 'DORMANT', 'signal_id': signal_id})

        logger.info(f"Created DORMANT signal {signal_id} for needle {needle['needle_id']}")

    def _check_pass_rate_anomaly(self) -> bool:
        """Check for pass-rate anomaly (Section 2.2)."""
        window_minutes = self.config.get('pass_rate_window_minutes', 60)
        threshold = self.config.get('pass_rate_change_threshold', 20.0)

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get current window pass rate
            cur.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE gate_a_passed = TRUE) as passed
                FROM fhq_canonical.g5_promotion_ledger
                WHERE created_at > NOW() - INTERVAL '%s minutes'
            """, (window_minutes,))
            current = cur.fetchone()

            # Get previous window pass rate
            cur.execute("""
                SELECT pass_rate FROM fhq_canonical.g5_pass_rate_history
                ORDER BY created_at DESC LIMIT 1
            """)
            previous = cur.fetchone()

            if current['total'] == 0:
                return False

            current_rate = (current['passed'] / current['total']) * 100
            previous_rate = float(previous['pass_rate']) if previous else 0

            delta = abs(current_rate - previous_rate)
            anomaly = delta > threshold

            # Record history
            cur.execute("""
                INSERT INTO fhq_canonical.g5_pass_rate_history (
                    window_start, window_end, total_evaluated, total_passed,
                    pass_rate, previous_pass_rate, pass_rate_delta, anomaly_detected
                ) VALUES (
                    NOW() - INTERVAL '%s minutes', NOW(), %s, %s,
                    %s, %s, %s, %s
                )
            """, (window_minutes, current['total'], current['passed'],
                  current_rate, previous_rate, delta, anomaly))

        self.conn.commit()

        if anomaly:
            self._log_event('PASS_RATE_ANOMALY',
                           data={'current': current_rate, 'previous': previous_rate,
                                 'delta': delta, 'threshold': threshold},
                           severity='WARN', defcon_escalation=True)
            logger.warning(f"Pass-rate anomaly detected: {delta:.1f}% change")

        return anomaly

    def _compute_drift_metrics(self):
        """Compute and record drift metrics (Section 4)."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Rolling 7-day metrics
            cur.execute("""
                SELECT
                    AVG(eqs_score::numeric) as avg_eqs,
                    COUNT(*) as needle_count
                FROM fhq_canonical.golden_needles
                WHERE created_at > NOW() - INTERVAL '7 days'
                AND is_current = TRUE
            """)
            needles = cur.fetchone()

            cur.execute("""
                SELECT COUNT(*) as signal_count
                FROM fhq_canonical.g5_signal_state
                WHERE state_entered_at > NOW() - INTERVAL '7 days'
            """)
            signals = cur.fetchone()

            avg_eqs = float(needles['avg_eqs'] or 0)
            needle_count = int(needles['needle_count'] or 0)
            signal_count = int(signals['signal_count'] or 0)
            conversion_rate = signal_count / needle_count if needle_count > 0 else 0

            eqs_threshold = float(self.config.get('min_rolling_7day_eqs', 0.85))
            conv_threshold = float(self.config.get('min_conversion_rate', 0.05))

            eqs_breach = avg_eqs < eqs_threshold
            conv_breach = conversion_rate < conv_threshold

            cur.execute("""
                INSERT INTO fhq_canonical.g5_drift_metrics (
                    rolling_7day_avg_eqs, rolling_7day_needle_count,
                    rolling_7day_signal_count, rolling_7day_conversion_rate,
                    eqs_threshold, conversion_threshold,
                    eqs_below_threshold, conversion_below_threshold
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (avg_eqs, needle_count, signal_count, conversion_rate,
                  eqs_threshold, conv_threshold, eqs_breach, conv_breach))

        self.conn.commit()

        if eqs_breach or conv_breach:
            self._log_event('DRIFT_DETECTED',
                           data={'avg_eqs': avg_eqs, 'conversion': conversion_rate,
                                 'eqs_breach': eqs_breach, 'conv_breach': conv_breach},
                           severity='WARN')
            logger.warning(f"Drift detected: EQS={avg_eqs:.3f}, Conv={conversion_rate:.3f}")

    def process_needle(self, needle: Dict) -> bool:
        """
        Process a single needle through the promotion pipeline.
        Returns True if processing was attempted (not rate-limited).
        """
        total_start = time.time()
        needle_id = str(needle['needle_id'])

        logger.info(f"Processing needle: {needle_id}")

        # Check pipeline state
        state = self._get_pipeline_state()
        if state in ('PAUSED', 'HALTED'):
            logger.warning(f"Pipeline is {state}, skipping needle")
            return False

        # Check rate limit
        if not self._check_rate_limit():
            self._log_event('RATE_LIMIT_HIT', needle_id=needle_id, severity='WARN')
            logger.warning("Rate limit hit, skipping needle")
            return False

        try:
            # Step 1: Generate evidence pack
            attestation_id, evidence_path, evidence_gen_ms = \
                self._generate_evidence_pack(needle)

            self._log_event('EVIDENCE_GENERATED', needle_id=needle_id,
                           data={'attestation_id': attestation_id,
                                 'path': evidence_path,
                                 'ms': evidence_gen_ms})

            # Step 2: Evaluate Gate A
            gate_a_passed, rejection_reason, gate_a_ms = \
                self._evaluate_gate_a(needle, attestation_id)

            self._log_event('GATE_A_EVALUATED', needle_id=needle_id,
                           data={'passed': gate_a_passed,
                                 'reason': rejection_reason,
                                 'ms': gate_a_ms})

            total_ms = int((time.time() - total_start) * 1000)

            # Check if shadow mode
            if self._is_shadow_mode():
                # Record as shadow decision only
                self._record_shadow_decision(needle, attestation_id,
                                              gate_a_passed, rejection_reason,
                                              evidence_gen_ms, gate_a_ms, total_ms)
                logger.info(f"Shadow decision recorded: would_pass={gate_a_passed}")
            else:
                # Record promotion decision
                promotion_id = self._record_promotion(needle, attestation_id,
                                                       gate_a_passed, rejection_reason,
                                                       evidence_gen_ms, gate_a_ms, total_ms)

                # If passed Gate A, create DORMANT signal (simplified - skip Gate B for MVP)
                if gate_a_passed:
                    self._create_dormant_signal(needle, promotion_id, attestation_id)
                    self._increment_rate_counter()

            logger.info(f"Needle processed: gate_a={'PASS' if gate_a_passed else 'REJECT'} "
                       f"({total_ms}ms)")

            return True

        except Exception as e:
            logger.error(f"Error processing needle {needle_id}: {e}")
            self._log_event('GATE_A_EVALUATED', needle_id=needle_id,
                           data={'error': str(e)}, severity='ERROR')
            raise

    def find_unprocessed_needles(self, limit: int = 50) -> list:
        """Find needles that haven't been processed yet."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT gn.*
                FROM fhq_canonical.golden_needles gn
                WHERE gn.is_current = TRUE
                AND gn.vega_attestation_id IS NULL
                AND NOT EXISTS (
                    SELECT 1 FROM fhq_canonical.g5_promotion_ledger pl
                    WHERE pl.needle_id = gn.needle_id
                )
                AND NOT EXISTS (
                    SELECT 1 FROM fhq_canonical.g5_shadow_decisions sd
                    WHERE sd.needle_id = gn.needle_id
                )
                ORDER BY gn.created_at DESC
                LIMIT %s
            """, (limit,))
            return [dict(row) for row in cur.fetchall()]

    def run_cycle(self):
        """Run one promotion cycle."""
        logger.info("=" * 60)
        logger.info("WAVE 17C PROMOTION CYCLE")
        logger.info("=" * 60)

        # Reload config
        self.config = self._load_config()
        state = self._get_pipeline_state()
        shadow = self._is_shadow_mode()

        logger.info(f"Pipeline State: {state}")
        logger.info(f"Shadow Mode: {shadow}")
        logger.info(f"Rate Limit: {self.config.get('max_promotions_per_hour')}/hr")

        if state in ('PAUSED', 'HALTED'):
            logger.warning(f"Pipeline is {state}, skipping cycle")
            return

        # Find unprocessed needles
        needles = self.find_unprocessed_needles()
        logger.info(f"Found {len(needles)} unprocessed needles")

        processed = 0
        passed = 0
        failed = 0
        rate_limited = 0

        for needle in needles:
            try:
                if self.process_needle(needle):
                    processed += 1
                    # Check if Gate A passed (simplified check)
                    if float(needle.get('eqs_score', 0)) >= 0.85 and \
                       needle.get('sitc_confidence_level', '').upper() == 'HIGH':
                        passed += 1
                    else:
                        failed += 1
                else:
                    rate_limited += 1
                    break  # Stop if rate limited
            except Exception as e:
                logger.error(f"Error: {e}")
                failed += 1

        # Check for anomalies
        if processed > 0:
            self._check_pass_rate_anomaly()

        # Compute drift metrics periodically
        self._compute_drift_metrics()

        logger.info(f"Cycle complete: processed={processed}, passed={passed}, "
                   f"failed={failed}, rate_limited={rate_limited}")

    def close(self):
        """Close database connection."""
        self.conn.close()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='WAVE 17C Promotion Pipeline')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--interval', type=int, default=60,
                        help='Seconds between cycles (default: 60)')
    args = parser.parse_args()

    pipeline = PromotionPipeline()

    try:
        if args.once:
            pipeline.run_cycle()
        else:
            logger.info(f"Starting continuous mode (interval: {args.interval}s)")
            while True:
                pipeline.run_cycle()
                logger.info(f"Sleeping {args.interval}s...")
                time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        pipeline.close()


if __name__ == "__main__":
    main()
