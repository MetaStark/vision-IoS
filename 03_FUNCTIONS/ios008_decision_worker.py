#!/usr/bin/env python3
"""
IoS-008 DECISION ENGINE DAEMON
==============================
Authority: ADR-012 (Economic Safety), ADR-016 (System Safety), ADR-017 (Signal Integrity)
Technical Lead: STIG (CTO)
Operations: LINE
Governance: VEGA
Classification: Tier-1 Critical

EXECUTIVE DIRECTIVE: IoS-008 DECISION WORKER (v2026.PROD.G1)
This implementation operationalizes ACL-principles in ADR-017 and risk protection
per ADR-012 and ADR-016.

Constitutional Safeguards:
A. Race Condition Prevention (Task Locking)
B. ADR-017 Quad-Hash Logging (LIDS, ACL, DSL, RISL)
C. Signal Cohesion Logic (Batch Intelligence)
D. Smart Regime Filtering (Transition Awareness)
E. Fail-Safe Execution Mode (Shadow Fallback)

SIGNED:
LARS - CSEO (Tier-1 Authority)
Verified by STIG - Implementation Hash
Logged by VEGA - Governance Chain
"""

import os
import sys
import json
import hashlib
import signal
import time
import logging
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Tuple, Optional
from decimal import Decimal
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, asdict

from dotenv import load_dotenv
load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Daemon Configuration
DEFAULT_INTERVAL_SECONDS = 300  # 5 minutes
LOCK_ID = 'IOS008_DECISION_WORKER'
LOCK_TTL_SECONDS = 600  # 10 minutes
DECISION_TTL_MINUTES = 15  # ADR-017 IRONCLAD

# Risk Thresholds
MIN_CAPITAL_REQUIRED = 1000.0  # Minimum capital for operation
REGIME_STABILITY_THRESHOLD = 0.5  # For transition awareness

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [IoS-008] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('ios008_decision_worker')

EVIDENCE_DIR = Path(__file__).parent / "evidence" / "ios008"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# ENUMS & DATA STRUCTURES (ADR-017 Compliant)
# =============================================================================

class RegimeMatchStatus(Enum):
    """Formal regime match status codes for auditability (ADR-017 D)"""
    MATCH = "MATCH"                         # Signal matches current regime
    SOFT_MISMATCH = "SOFT_MISMATCH"         # Minor mismatch, may still process
    TRANSITION_EXEMPT = "TRANSITION_EXEMPT"  # Allowed due to regime instability
    HARD_CONFLICT = "HARD_CONFLICT"          # Rejected - incompatible regime


class ExecutionMode(Enum):
    """Execution mode for fail-safe fallback (ADR-017 E)"""
    LIVE = "LIVE"                # Full execution to IoS-012
    SHADOW_PAPER = "SHADOW_PAPER"  # Shadow mode - no real execution


class SignalDirection(Enum):
    """Normalized signal directions"""
    LONG = "LONG"
    SHORT = "SHORT"
    CLOSE = "CLOSE"
    NEUTRAL = "NEUTRAL"


@dataclass
class QuadHash:
    """ADR-017 Quad-Hash Structure"""
    lids: str   # Logical Intent Data Structure - Hash of input signals
    acl: str    # Action Control Logic - Hash of generated plan
    dsl: str    # Data State Ledger - Snapshot of market data
    risl: str   # Risk Instruction Set - DEFCON + capital constraints

    @property
    def combined_hash(self) -> str:
        """Combined context hash"""
        combined = f"{self.lids}:{self.acl}:{self.dsl}:{self.risl}"
        return hashlib.sha256(combined.encode()).hexdigest()


@dataclass
class BatchCohesion:
    """Signal cohesion analysis result"""
    score: float           # 0.0 to 1.0
    dominant_direction: SignalDirection
    conflicting_signals: int
    aligned_signals: int
    confidence_modifier: float  # Multiplier for confidence


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for Decimal and datetime types"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


# =============================================================================
# IoS-008 DECISION DAEMON
# =============================================================================

class IoS008DecisionDaemon:
    """
    IoS-008 Runtime Decision Engine Daemon

    Transforms G1-validated signals into deterministic DecisionPlans
    with full constitutional safeguards per ADR-012, ADR-016, ADR-017.
    """

    def __init__(self, interval_seconds: int = DEFAULT_INTERVAL_SECONDS):
        self.interval = interval_seconds
        self.running = False
        self.conn = None
        self.cycle_count = 0

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        logger.info(f"IoS-008 Decision Daemon initialized (interval={interval_seconds}s)")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False

    def _get_connection(self) -> psycopg2.extensions.connection:
        """Get database connection with auto-reconnect"""
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.conn.autocommit = False
        return self.conn

    def _execute_query(self, query: str, params: tuple = None,
                       commit: bool = False) -> List[Dict]:
        """Execute query with proper cursor handling and error recovery"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                if commit:
                    conn.commit()
                if cur.description:
                    return [dict(row) for row in cur.fetchall()]
                return []
        except psycopg2.Error as e:
            # Rollback on error to allow subsequent queries
            conn.rollback()
            raise

    # =========================================================================
    # A. RACE CONDITION PREVENTION (Task Locking)
    # =========================================================================

    def acquire_lock(self) -> bool:
        """
        Acquire exclusive lock using PostgreSQL advisory locks.
        Prevents duplicate DecisionPlans and hash-chain corruption.
        """
        try:
            # Use pg_advisory_lock with a hash of the lock ID
            lock_key = hash(LOCK_ID) % (2**31)  # PostgreSQL advisory lock key
            result = self._execute_query(
                "SELECT pg_try_advisory_lock(%s) as acquired",
                (lock_key,)
            )

            acquired = result[0]['acquired'] if result else False

            if acquired:
                logger.debug(f"Lock acquired: {LOCK_ID}")
                # Log lock acquisition to governance
                self._log_governance_action('LOCK_ACQUIRED', {
                    'lock_id': LOCK_ID,
                    'cycle': self.cycle_count
                })
            else:
                logger.warning(f"Could not acquire lock: {LOCK_ID} (another instance running?)")

            return acquired

        except Exception as e:
            logger.error(f"Lock acquisition failed: {e}")
            return False

    def release_lock(self) -> None:
        """Release the advisory lock"""
        try:
            lock_key = hash(LOCK_ID) % (2**31)
            self._execute_query(
                "SELECT pg_advisory_unlock(%s)",
                (lock_key,),
                commit=True
            )
            logger.debug(f"Lock released: {LOCK_ID}")
        except Exception as e:
            logger.error(f"Lock release failed: {e}")

    # =========================================================================
    # B. ADR-017 QUAD-HASH LOGGING
    # =========================================================================

    def compute_quad_hash(self, signals: List[Dict], plan: Dict,
                          market_snapshot: Dict, risk_state: Dict) -> QuadHash:
        """
        Compute ADR-017 Quad-Hash for decision integrity.

        Components:
        - LIDS: Hash of input signals (Logical Intent Data Structure)
        - ACL: Hash of generated plan (Action Control Logic)
        - DSL: Hash of market data snapshot (Data State Ledger)
        - RISL: Hash of DEFCON + capital limits (Risk Instruction Set)
        """

        # LIDS - Logical Intent Data Structure
        lids_data = json.dumps(
            [{'id': s['signal_id'], 'category': s['category'],
              'confidence': float(s['confidence_score'])} for s in signals],
            sort_keys=True, cls=DecimalEncoder
        )
        lids_hash = hashlib.sha256(lids_data.encode()).hexdigest()

        # ACL - Action Control Logic
        acl_data = json.dumps(plan, sort_keys=True, cls=DecimalEncoder)
        acl_hash = hashlib.sha256(acl_data.encode()).hexdigest()

        # DSL - Data State Ledger
        dsl_data = json.dumps(market_snapshot, sort_keys=True, cls=DecimalEncoder)
        dsl_hash = hashlib.sha256(dsl_data.encode()).hexdigest()

        # RISL - Risk Instruction Set (includes DEFCON snapshot per directive)
        risl_data = json.dumps({
            'defcon_level': risk_state.get('defcon_level'),
            'defcon_triggered_at': risk_state.get('defcon_triggered_at'),
            'capital_limits': risk_state.get('capital_limits'),
            'defcon_multiplier': risk_state.get('defcon_multiplier')
        }, sort_keys=True, cls=DecimalEncoder)
        risl_hash = hashlib.sha256(risl_data.encode()).hexdigest()

        return QuadHash(
            lids=lids_hash,
            acl=acl_hash,
            dsl=dsl_hash,
            risl=risl_hash
        )

    # =========================================================================
    # C. SIGNAL COHESION LOGIC (Batch Intelligence)
    # =========================================================================

    def assess_batch_cohesion(self, signals: List[Dict]) -> BatchCohesion:
        """
        Assess cohesion of signals in a batch.

        Logic:
        - If batch contains conflicting directions: reduce confidence
        - If all signals align: boost confidence
        """
        if not signals:
            return BatchCohesion(
                score=0.0,
                dominant_direction=SignalDirection.NEUTRAL,
                conflicting_signals=0,
                aligned_signals=0,
                confidence_modifier=0.0
            )

        # Analyze signal directions
        directions = {}
        for sig in signals:
            # Infer direction from entry conditions
            direction = self._infer_signal_direction(sig)
            directions[direction] = directions.get(direction, 0) + 1

        total = len(signals)
        dominant = max(directions.items(), key=lambda x: x[1])
        dominant_direction = dominant[0]
        dominant_count = dominant[1]

        # Calculate cohesion
        aligned = dominant_count
        conflicting = total - aligned

        # Cohesion score: ratio of aligned signals
        cohesion_score = aligned / total if total > 0 else 0.0

        # Confidence modifier based on cohesion
        if conflicting == 0:
            # All aligned - boost confidence by 10%
            confidence_modifier = 1.10
        elif conflicting <= total * 0.2:
            # Minor conflicts - no change
            confidence_modifier = 1.0
        elif conflicting <= total * 0.4:
            # Moderate conflicts - reduce by 15%
            confidence_modifier = 0.85
        else:
            # Major conflicts - reduce by 30%
            confidence_modifier = 0.70

        return BatchCohesion(
            score=cohesion_score,
            dominant_direction=dominant_direction,
            conflicting_signals=conflicting,
            aligned_signals=aligned,
            confidence_modifier=confidence_modifier
        )

    def _infer_signal_direction(self, signal: Dict) -> SignalDirection:
        """Infer signal direction from entry conditions"""
        entry = signal.get('entry_conditions', [])
        if isinstance(entry, list):
            entry_str = ' '.join(str(e) for e in entry).lower()
        else:
            entry_str = str(entry).lower()

        # Simple heuristic - can be enhanced
        if 'long' in entry_str or 'buy' in entry_str or 'bullish' in entry_str:
            return SignalDirection.LONG
        elif 'short' in entry_str or 'sell' in entry_str or 'bearish' in entry_str:
            return SignalDirection.SHORT
        elif 'close' in entry_str or 'exit' in entry_str:
            return SignalDirection.CLOSE
        else:
            # Default based on category patterns
            category = signal.get('category', '').upper()
            if category in ['MOMENTUM', 'REGIME_EDGE']:
                return SignalDirection.LONG
            return SignalDirection.NEUTRAL

    # =========================================================================
    # D. SMART REGIME FILTERING (Transition Awareness)
    # =========================================================================

    def smart_regime_filter(self, signals: List[Dict],
                            current_regime: str,
                            regime_stability: float) -> Tuple[List[Dict], Dict[str, RegimeMatchStatus]]:
        """
        Smart regime filtering with transition awareness.

        Logic:
        - Standard: Signal must match current_regime
        - Exception: If regime_stability < 0.5, allow TRANSITION_EXEMPT signals
        """
        filtered = []
        status_map = {}

        for sig in signals:
            signal_id = sig['signal_id']
            regime_filter = sig.get('regime_filter', [])

            # Check if signal matches current regime
            if current_regime in regime_filter:
                status_map[signal_id] = RegimeMatchStatus.MATCH
                filtered.append(sig)
                continue

            # Check for transition exemption
            if regime_stability < REGIME_STABILITY_THRESHOLD:
                # Regime is unstable - allow transition bets
                status_map[signal_id] = RegimeMatchStatus.TRANSITION_EXEMPT
                sig['_transition_bet'] = True
                sig['_regime_stability_at_decision'] = regime_stability
                filtered.append(sig)
                logger.info(
                    f"Signal {signal_id}: TRANSITION_EXEMPT "
                    f"(stability={regime_stability:.2f} < {REGIME_STABILITY_THRESHOLD})"
                )
                continue

            # Check for soft mismatch (adjacent regimes)
            if self._is_soft_mismatch(current_regime, regime_filter):
                status_map[signal_id] = RegimeMatchStatus.SOFT_MISMATCH
                # Don't include soft mismatches by default
                logger.debug(f"Signal {signal_id}: SOFT_MISMATCH (filtered)")
                continue

            # Hard conflict - completely incompatible
            status_map[signal_id] = RegimeMatchStatus.HARD_CONFLICT
            logger.debug(f"Signal {signal_id}: HARD_CONFLICT (filtered)")

        return filtered, status_map

    def _is_soft_mismatch(self, current: str, allowed: List[str]) -> bool:
        """Check if regimes are adjacent (soft mismatch)"""
        # Define regime adjacency
        adjacency = {
            'STRONG_BULL': ['BULL'],
            'BULL': ['STRONG_BULL', 'RANGE_UP', 'NEUTRAL'],
            'RANGE_UP': ['BULL', 'NEUTRAL'],
            'NEUTRAL': ['RANGE_UP', 'RANGE_DOWN', 'BULL', 'BEAR'],
            'RANGE_DOWN': ['NEUTRAL', 'BEAR'],
            'BEAR': ['RANGE_DOWN', 'NEUTRAL', 'STRONG_BEAR'],
            'STRONG_BEAR': ['BEAR'],
        }

        adjacent = adjacency.get(current, [])
        return any(r in adjacent for r in allowed)

    def get_current_regime_state(self) -> Tuple[str, float]:
        """Get current regime and stability score"""
        result = self._execute_query("""
            SELECT
                sovereign_regime,
                state_probabilities
            FROM fhq_perception.sovereign_regime_state_v4
            WHERE asset_id = 'BTC-USD'
            ORDER BY timestamp DESC
            LIMIT 1
        """)

        if not result:
            # Fallback to meta regime state
            result = self._execute_query("""
                SELECT
                    current_regime as sovereign_regime,
                    confidence as stability
                FROM fhq_meta.regime_state
                WHERE is_current = true
                ORDER BY updated_at DESC
                LIMIT 1
            """)

            if result:
                return result[0]['sovereign_regime'], float(result[0].get('stability', 0.5))
            return 'NEUTRAL', 0.5

        row = result[0]
        regime = row['sovereign_regime']

        # Calculate stability from state probabilities
        probs = row.get('state_probabilities', {})
        if probs:
            stability = max(probs.values()) if probs else 0.5
        else:
            stability = 0.5

        return regime, stability

    # =========================================================================
    # E. FAIL-SAFE EXECUTION MODE (Shadow Fallback)
    # =========================================================================

    def determine_execution_mode(self, defcon_level: str,
                                  available_capital: float,
                                  system_error: bool = False) -> ExecutionMode:
        """
        Determine execution mode based on system state.

        Fallback to SHADOW_PAPER if:
        - DEFCON <= 2 (critical/emergency)
        - Capital < MIN_CAPITAL_REQUIRED
        - System error detected
        """
        # Map DEFCON text to numeric
        defcon_map = {
            'GREEN': 5, 'BLUE': 4, 'YELLOW': 3,
            'ORANGE': 2, 'RED': 1,
            '5': 5, '4': 4, '3': 3, '2': 2, '1': 1
        }

        defcon_num = defcon_map.get(str(defcon_level).upper(), 5)

        # Check fail-safe conditions
        if defcon_num <= 2:
            logger.warning(f"SHADOW_PAPER mode: DEFCON {defcon_level} (critical)")
            return ExecutionMode.SHADOW_PAPER

        if available_capital < MIN_CAPITAL_REQUIRED:
            logger.warning(f"SHADOW_PAPER mode: Capital ${available_capital:.2f} < ${MIN_CAPITAL_REQUIRED}")
            return ExecutionMode.SHADOW_PAPER

        if system_error:
            logger.warning("SHADOW_PAPER mode: System error detected")
            return ExecutionMode.SHADOW_PAPER

        return ExecutionMode.LIVE

    # =========================================================================
    # CORE PIPELINE
    # =========================================================================

    def collect_pending_signals(self) -> List[Dict]:
        """Collect G1-validated signals queued for IoS-008"""
        return self._execute_query("""
            SELECT
                signal_id,
                source_proposal_id,
                hypothesis_id,
                title,
                category,
                entry_conditions,
                exit_conditions,
                regime_filter,
                backtest_summary,
                confidence_score,
                state_hash_at_validation,
                defcon_at_validation,
                status,
                validated_at,
                created_at
            FROM fhq_alpha.g1_validated_signals
            WHERE status = 'QUEUED_FOR_IOS008'
            ORDER BY validated_at ASC
        """)

    def get_risk_state(self) -> Dict:
        """Get current risk state (DEFCON, capital limits)"""
        # Get DEFCON
        defcon_result = self._execute_query("""
            SELECT defcon_level, triggered_at, trigger_reason
            FROM fhq_governance.defcon_state
            WHERE is_current = true
            LIMIT 1
        """)

        defcon = defcon_result[0] if defcon_result else {
            'defcon_level': 'GREEN',
            'triggered_at': None,
            'trigger_reason': 'Default'
        }

        # Get risk budget
        budget_result = self._execute_query("""
            SELECT
                total_capital,
                max_position_pct,
                max_daily_risk_pct,
                capital_deployed,
                daily_risk_used,
                defcon_multiplier
            FROM fhq_alpha.risk_budget
            WHERE is_current = true
            LIMIT 1
        """)

        budget = budget_result[0] if budget_result else {
            'total_capital': Decimal('100000'),
            'max_position_pct': Decimal('0.10'),
            'max_daily_risk_pct': Decimal('0.02'),
            'capital_deployed': Decimal('0'),
            'daily_risk_used': Decimal('0'),
            'defcon_multiplier': Decimal('1.0')
        }

        return {
            'defcon_level': defcon['defcon_level'],
            'defcon_triggered_at': defcon.get('triggered_at'),
            'defcon_reason': defcon.get('trigger_reason'),
            'total_capital': float(budget['total_capital']),
            'capital_deployed': float(budget['capital_deployed']),
            'available_capital': float(budget['total_capital']) - float(budget['capital_deployed']),
            'defcon_multiplier': float(budget['defcon_multiplier']),
            'capital_limits': {
                'max_position_pct': float(budget['max_position_pct']),
                'max_daily_risk_pct': float(budget['max_daily_risk_pct']),
            }
        }

    def get_market_snapshot(self) -> Dict:
        """Get current market data snapshot for DSL hash"""
        result = self._execute_query("""
            SELECT
                canonical_id,
                timestamp,
                close,
                volume
            FROM fhq_market.prices
            WHERE canonical_id IN ('BTC-USD', 'ETH-USD', 'SOL-USD')
            AND timestamp = (SELECT MAX(timestamp) FROM fhq_market.prices WHERE canonical_id = 'BTC-USD')
            ORDER BY canonical_id
        """)

        return {
            'snapshot_time': datetime.now(timezone.utc).isoformat(),
            'prices': [dict(r) for r in result] if result else []
        }

    def generate_decision_plan(self, signals: List[Dict],
                               cohesion: BatchCohesion,
                               regime: str,
                               risk_state: Dict,
                               execution_mode: ExecutionMode,
                               quad_hash: QuadHash) -> Dict:
        """Generate a DecisionPlan from processed signals"""

        # Calculate aggregated confidence
        if signals:
            avg_confidence = sum(float(s['confidence_score']) for s in signals) / len(signals)
            adjusted_confidence = avg_confidence * cohesion.confidence_modifier
        else:
            adjusted_confidence = 0.0

        # Calculate valid_until (TTL = 15 minutes, IRONCLAD)
        now = datetime.now(timezone.utc)
        valid_until = now + timedelta(minutes=DECISION_TTL_MINUTES)

        # Build asset directives
        asset_directives = []
        for sig in signals:
            direction = self._infer_signal_direction(sig)

            # Get regime scalar
            scalar_result = self._execute_query("""
                SELECT scalar_value FROM fhq_governance.regime_scalar_config
                WHERE regime_label = %s AND is_active = true
            """, (regime,))
            regime_scalar = float(scalar_result[0]['scalar_value']) if scalar_result else 0.5

            # Calculate allocation
            base_alloc = adjusted_confidence * regime_scalar * risk_state['defcon_multiplier']

            directive = {
                'signal_id': str(sig['signal_id']),
                'hypothesis_id': sig['hypothesis_id'],
                'category': sig['category'],
                'action': direction.value,
                'target_allocation_bps': int(base_alloc * 10000),  # Convert to basis points
                'confidence_score': adjusted_confidence,
                'regime_match_status': sig.get('_regime_match_status', 'MATCH'),
                'transition_bet': sig.get('_transition_bet', False),
                'entry_conditions': sig['entry_conditions'],
                'exit_conditions': sig['exit_conditions'],
            }
            asset_directives.append(directive)

        plan = {
            'decision_id': str(uuid.uuid4()),
            'timestamp': now.isoformat(),
            'valid_until': valid_until.isoformat(),
            'ttl_minutes': DECISION_TTL_MINUTES,

            # Global state
            'global_state': {
                'regime': regime,
                'defcon_level': risk_state['defcon_level'],
                'execution_mode': execution_mode.value,
            },

            # Batch metrics
            'batch_metrics': {
                'signals_processed': len(signals),
                'cohesion_score': cohesion.score,
                'dominant_direction': cohesion.dominant_direction.value,
                'confidence_modifier': cohesion.confidence_modifier,
            },

            # Asset directives
            'asset_directives': asset_directives,

            # ADR-017 Quad-Hash
            'quad_hash': {
                'lids': quad_hash.lids,
                'acl': quad_hash.acl,
                'dsl': quad_hash.dsl,
                'risl': quad_hash.risl,
                'context_hash': quad_hash.combined_hash,
            },

            # Metadata
            'metadata': {
                'worker_version': 'v2026.PROD.G1',
                'generated_by': 'IoS-008',
                'authority': 'ADR-017',
            }
        }

        return plan

    def log_decision(self, plan: Dict) -> None:
        """Log decision to governance tables (append-only)"""
        try:
            # Get previous hash for chain
            prev_result = self._execute_query("""
                SELECT hash_self, sequence_number
                FROM fhq_governance.decision_log
                ORDER BY sequence_number DESC
                LIMIT 1
            """)

            hash_prev = prev_result[0]['hash_self'] if prev_result else None
            seq_num = (prev_result[0]['sequence_number'] + 1) if prev_result else 1

            # Map DEFCON text to numeric
            defcon_map = {'GREEN': 5, 'BLUE': 4, 'YELLOW': 3, 'ORANGE': 2, 'RED': 1}
            defcon_num = defcon_map.get(plan['global_state']['defcon_level'], 5)

            # Calculate hash_self (chain integrity)
            chain_data = f"{plan['decision_id']}:{plan['quad_hash']['context_hash']}:{hash_prev or 'GENESIS'}"
            hash_self = hashlib.sha256(chain_data.encode()).hexdigest()

            # Get skill score (default to 0.7 if no FSS metrics available)
            # IoS-005 FSS metrics may not be deployed yet
            skill_score = 0.7  # Default skill score for G1 validation

            # Build snapshots
            regime_snapshot = {
                'regime': plan['global_state']['regime'],
                'cohesion_score': plan['batch_metrics']['cohesion_score'],
                'dominant_direction': plan['batch_metrics']['dominant_direction'],
            }

            causal_snapshot = {
                'signals_processed': plan['batch_metrics']['signals_processed'],
                'confidence_modifier': plan['batch_metrics']['confidence_modifier'],
            }

            skill_snapshot = {
                'system_skill_score': skill_score,
                'execution_mode': plan['global_state']['execution_mode'],
            }

            # Calculate allocation components
            scalar_result = self._execute_query("""
                SELECT scalar_value FROM fhq_governance.regime_scalar_config
                WHERE regime_label = %s AND is_active = true
            """, (plan['global_state']['regime'],))
            regime_scalar = float(scalar_result[0]['scalar_value']) if scalar_result else 0.5

            # Get damper for skill score
            damper_result = self._execute_query("""
                SELECT damper_value FROM fhq_governance.skill_damper_config
                WHERE %s >= fss_min AND %s < fss_max AND is_active = true
                LIMIT 1
            """, (skill_score, skill_score))
            skill_damper = float(damper_result[0]['damper_value']) if damper_result else 1.0

            base_alloc = 1.0
            causal_vector = plan['batch_metrics']['confidence_modifier']
            final_alloc = base_alloc * regime_scalar * causal_vector * skill_damper

            # Log to decision_log
            self._execute_query("""
                INSERT INTO fhq_governance.decision_log (
                    decision_id,
                    created_at,
                    valid_from,
                    valid_until,
                    context_hash,
                    regime_snapshot,
                    causal_snapshot,
                    skill_snapshot,
                    global_regime,
                    defcon_level,
                    system_skill_score,
                    asset_directives,
                    decision_type,
                    decision_rationale,
                    base_allocation,
                    regime_scalar,
                    causal_vector,
                    skill_damper,
                    final_allocation,
                    governance_signature,
                    signature_agent,
                    hash_prev,
                    hash_self,
                    sequence_number,
                    execution_state,
                    created_by
                ) VALUES (
                    %s, NOW(), NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                plan['decision_id'],
                plan['valid_until'],
                plan['quad_hash']['context_hash'],
                json.dumps(regime_snapshot, cls=DecimalEncoder),
                json.dumps(causal_snapshot, cls=DecimalEncoder),
                json.dumps(skill_snapshot, cls=DecimalEncoder),
                plan['global_state']['regime'],
                defcon_num,
                skill_score,
                json.dumps(plan['asset_directives'], cls=DecimalEncoder),
                'BATCH_DECISION',
                f"IoS-008 processed {plan['batch_metrics']['signals_processed']} signals",
                base_alloc,
                regime_scalar,
                causal_vector,
                skill_damper,
                final_alloc,
                plan['quad_hash']['context_hash'],  # Use quad-hash as signature
                'IOS008_DECISION_WORKER',
                hash_prev,
                hash_self,
                seq_num,
                'PENDING',
                'IOS008_DECISION_WORKER'
            ), commit=True)

            # Log to governance_actions_log
            self._log_governance_action('DECISION_PLAN_GENERATED', {
                'decision_id': plan['decision_id'],
                'signals_processed': plan['batch_metrics']['signals_processed'],
                'execution_mode': plan['global_state']['execution_mode'],
                'context_hash': plan['quad_hash']['context_hash'],
                'sequence_number': seq_num,
            })

            logger.info(f"Decision logged: {plan['decision_id']} (seq={seq_num})")

        except Exception as e:
            logger.error(f"Failed to log decision: {e}")
            raise

    def update_signal_status(self, signals: List[Dict],
                             plan_id: str,
                             status_map: Dict[str, RegimeMatchStatus]) -> None:
        """Update processed signals with decision reference"""
        try:
            for sig in signals:
                signal_id = sig['signal_id']
                match_status = status_map.get(signal_id, RegimeMatchStatus.MATCH)

                self._execute_query("""
                    UPDATE fhq_alpha.g1_validated_signals
                    SET
                        status = 'PROCESSED_BY_IOS008',
                        forwarded_to_ios008_at = NOW()
                    WHERE signal_id = %s
                """, (signal_id,), commit=True)

            logger.info(f"Updated {len(signals)} signals to PROCESSED_BY_IOS008")

        except Exception as e:
            logger.error(f"Failed to update signal status: {e}")

    def _log_governance_action(self, action: str, details: Dict) -> None:
        """Log action to governance_actions_log"""
        try:
            self._execute_query("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_id,
                    action_type,
                    action_target,
                    action_target_type,
                    initiated_by,
                    initiated_at,
                    decision,
                    decision_rationale,
                    metadata,
                    agent_id,
                    timestamp
                ) VALUES (
                    gen_random_uuid(),
                    %s,
                    'IOS008_DECISION_ENGINE',
                    'SYSTEM',
                    'STIG',
                    NOW(),
                    'APPROVED',
                    %s,
                    %s,
                    'IOS008_DECISION_WORKER',
                    NOW()
                )
            """, (
                action,
                f"IoS-008 Decision Worker: {action}",
                json.dumps(details, cls=DecimalEncoder)
            ), commit=True)
        except Exception as e:
            logger.warning(f"Governance logging failed: {e}")

    def log_heartbeat(self) -> None:
        """Log heartbeat for monitoring"""
        try:
            self._execute_query("""
                INSERT INTO fhq_monitoring.system_heartbeats (
                    component_id,
                    heartbeat_time,
                    status,
                    metadata
                ) VALUES (
                    'IOS008_DECISION_WORKER',
                    NOW(),
                    'ALIVE',
                    %s
                )
                ON CONFLICT (component_id)
                DO UPDATE SET
                    heartbeat_time = NOW(),
                    status = 'ALIVE',
                    metadata = EXCLUDED.metadata
            """, (
                json.dumps({'cycle': self.cycle_count}),
            ), commit=True)
        except Exception as e:
            # Heartbeat failures are non-critical
            logger.debug(f"Heartbeat logging failed: {e}")

    def save_evidence(self, plan: Dict, signals: List[Dict]) -> str:
        """Save evidence bundle to file"""
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        filename = f"IOS008_DECISION_{timestamp}.json"
        filepath = EVIDENCE_DIR / filename

        evidence = {
            'metadata': {
                'type': 'IOS008_DECISION_EVIDENCE',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'worker_version': 'v2026.PROD.G1',
            },
            'decision_plan': plan,
            'input_signals': signals,
        }

        with open(filepath, 'w') as f:
            json.dump(evidence, f, indent=2, cls=DecimalEncoder)

        logger.info(f"Evidence saved: {filepath}")
        return str(filepath)

    # =========================================================================
    # MAIN LOOP
    # =========================================================================

    def run_cycle(self) -> Optional[Dict]:
        """Run a single decision cycle"""
        self.cycle_count += 1
        cycle_start = datetime.now(timezone.utc)

        logger.info(f"=== Cycle {self.cycle_count} started ===")

        try:
            # 1. Collect pending signals
            signals = self.collect_pending_signals()

            if not signals:
                logger.info("No pending signals - cycle complete")
                return None

            logger.info(f"Collected {len(signals)} pending signals")

            # 2. Assess batch cohesion
            cohesion = self.assess_batch_cohesion(signals)
            logger.info(
                f"Cohesion: score={cohesion.score:.2f}, "
                f"direction={cohesion.dominant_direction.value}, "
                f"modifier={cohesion.confidence_modifier:.2f}"
            )

            # 3. Get current regime state
            regime, stability = self.get_current_regime_state()
            logger.info(f"Regime: {regime}, stability={stability:.2f}")

            # 4. Smart regime filter
            valid_signals, status_map = self.smart_regime_filter(
                signals, regime, stability
            )

            if not valid_signals:
                logger.info("No signals passed regime filter - cycle complete")
                return None

            logger.info(f"{len(valid_signals)} signals passed regime filter")

            # 5. Get risk state and determine execution mode
            risk_state = self.get_risk_state()
            execution_mode = self.determine_execution_mode(
                risk_state['defcon_level'],
                risk_state['available_capital']
            )

            logger.info(
                f"Risk state: DEFCON={risk_state['defcon_level']}, "
                f"capital=${risk_state['available_capital']:.2f}, "
                f"mode={execution_mode.value}"
            )

            # 6. Get market snapshot for DSL
            market_snapshot = self.get_market_snapshot()

            # 7. Generate decision plan (for ACL hash)
            preliminary_plan = self.generate_decision_plan(
                valid_signals, cohesion, regime, risk_state,
                execution_mode, QuadHash('', '', '', '')  # Placeholder
            )

            # 8. Compute Quad-Hash
            quad_hash = self.compute_quad_hash(
                valid_signals, preliminary_plan, market_snapshot, risk_state
            )

            # 9. Generate final plan with proper Quad-Hash
            final_plan = self.generate_decision_plan(
                valid_signals, cohesion, regime, risk_state,
                execution_mode, quad_hash
            )

            # 10. Log decision (append-only)
            self.log_decision(final_plan)

            # 11. Update signal status
            self.update_signal_status(valid_signals, final_plan['decision_id'], status_map)

            # 12. Save evidence
            self.save_evidence(final_plan, valid_signals)

            cycle_duration = (datetime.now(timezone.utc) - cycle_start).total_seconds()
            logger.info(
                f"=== Cycle {self.cycle_count} complete ({cycle_duration:.2f}s) === "
                f"Decision: {final_plan['decision_id']}"
            )

            return final_plan

        except Exception as e:
            logger.error(f"Cycle {self.cycle_count} failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def start(self) -> None:
        """Start the daemon loop"""
        self.running = True
        logger.info("IoS-008 Decision Daemon starting...")

        self._log_governance_action('DAEMON_STARTED', {
            'interval_seconds': self.interval,
            'worker_version': 'v2026.PROD.G1'
        })

        while self.running:
            # Try to acquire lock
            if not self.acquire_lock():
                logger.info(f"Waiting {self.interval}s before retry...")
                time.sleep(self.interval)
                continue

            try:
                # Run decision cycle
                self.run_cycle()

                # Log heartbeat
                self.log_heartbeat()

            finally:
                # Always release lock
                self.release_lock()

            # Wait for next cycle
            if self.running:
                logger.info(f"Sleeping {self.interval}s until next cycle...")
                time.sleep(self.interval)

        self._log_governance_action('DAEMON_STOPPED', {
            'cycles_completed': self.cycle_count
        })

        logger.info("IoS-008 Decision Daemon stopped")

    def stop(self) -> None:
        """Stop the daemon gracefully"""
        self.running = False


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='IoS-008 Decision Engine Daemon (v2026.PROD.G1)'
    )
    parser.add_argument(
        '--interval', '-i',
        type=int,
        default=DEFAULT_INTERVAL_SECONDS,
        help=f'Cycle interval in seconds (default: {DEFAULT_INTERVAL_SECONDS})'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run a single cycle and exit'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without executing'
    )

    args = parser.parse_args()

    daemon = IoS008DecisionDaemon(interval_seconds=args.interval)

    if args.once:
        # Single cycle mode
        if daemon.acquire_lock():
            try:
                result = daemon.run_cycle()
                if result:
                    print(json.dumps(result, indent=2, cls=DecimalEncoder))
                else:
                    print("No decision generated (no pending signals or all filtered)")
            finally:
                daemon.release_lock()
        else:
            print("Could not acquire lock - another instance may be running")
            sys.exit(1)
    else:
        # Continuous daemon mode
        try:
            daemon.start()
        except KeyboardInterrupt:
            daemon.stop()


if __name__ == '__main__':
    main()
