"""
CEO-DIR-2026-109: EC-015 CPTO - Chief Precision Trading Officer
================================================================

Version: 1.2.0 (CEO Amendments A, B, C + CEO-DIR-2026-110 Mandate B applied)

Transforms IoS-008 signals into executable LIMIT orders with:
1. Regime-Adaptive Entry Price (CEO Addition A + Amendment A: VERIFIED_INVERTED_STRESS)
2. Canonical TP/SL per CEO-DIR-2026-107 (2.0x ATR SL, 1.25R TP)
3. TTL-Sync (CEO Addition B)
4. Liquidity-Aware Sizing (CEO Addition C)
5. Full Audit Lineage (Fix #5)
6. Alpha Attribution - Slippage Saved (CEO Amendment B)
7. Friction Feedback Loop (CEO Amendment C)
8. DEFCON-Aware Behavior
9. LOW_CONFIDENCE_INVERSION_CANDIDATE Signal Class Gating (CEO-DIR-2026-110 B2)
10. Inversion Friction Feedback with FINN Escalation (CEO-DIR-2026-110 R2)
11. 50% Strategic Friction Report to LARS (CEO-DIR-2026-110 R3)

Parent: FINN (Fix #4: Single parent)
Handoff Interface: LINE receives TradePacket for execution
Employment Contract: EC-015

Classification: Tier-2 Sub-Executive Officer
Governing ADRs: ADR-007, ADR-012, ADR-014
Directives: CEO-DIR-2026-107, CEO-DIR-2026-109, CEO-DIR-2026-110
"""

import hashlib
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
from decimal import Decimal
from enum import Enum

import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [CPTO] %(levelname)s: %(message)s'
)
logger = logging.getLogger('CPTO')


# =============================================================================
# DEFCON Levels and Behavior (ADR-016)
# =============================================================================

class DEFCONLevel(Enum):
    """DEFCON levels per ADR-016"""
    GREEN = 1   # Normal operations
    YELLOW = 2  # Elevated awareness
    ORANGE = 3  # Conservative mode
    RED = 4     # Refuse new
    BLACK = 5   # Full shutdown


class CPTOBehavior(Enum):
    """CPTO behavior modes per DEFCON"""
    NORMAL = "NORMAL"           # Standard transformation
    CONSERVATIVE = "CONSERVATIVE"  # Tightened aggression, stricter checks
    REFUSE_NEW = "REFUSE_NEW"   # No new TradePackets


# DEFCON -> Behavior mapping per EC-015 Section 7
DEFCON_BEHAVIOR_MAP = {
    DEFCONLevel.GREEN: CPTOBehavior.NORMAL,
    DEFCONLevel.YELLOW: CPTOBehavior.NORMAL,
    DEFCONLevel.ORANGE: CPTOBehavior.CONSERVATIVE,
    DEFCONLevel.RED: CPTOBehavior.REFUSE_NEW,
    DEFCONLevel.BLACK: CPTOBehavior.REFUSE_NEW,
}


# =============================================================================
# CPTO Parameter Set v1.1.0 (CEO Amendments A, B, C)
# =============================================================================

@dataclass
class CPTOParameterSet:
    """
    Fix #5: All discretionary parameters versioned and logged.
    Version 1.1.0: Includes CEO Amendments A, B, C
    """
    version: str = "1.2.0"

    # Entry price calculation
    max_entry_deviation_pct: float = 0.005  # Max 0.5% from current

    # CEO Addition A + Amendment A: Regime-adaptive aggression map
    # Amendment A adds VERIFIED_INVERTED_STRESS for documented inversions
    regime_aggression_map: Dict[str, float] = field(default_factory=lambda: {
        'STRONG_BULL': 0.002,              # 0.2% from mid (high fill probability)
        'MODERATE_BULL': 0.0025,
        'NEUTRAL': 0.003,                  # 0.3% from EMA
        'MODERATE_BEAR': 0.004,
        'VOLATILE': 0.005,                 # 0.5% margin
        'STRESS': 0.007,                   # 0.7% maximum safety (canonical STRESS)
        'VERIFIED_INVERTED_STRESS': 0.002  # CEO Amendment A: High aggression for verified inversions
    })

    # CEO Addition C: Liquidity threshold
    liquidity_threshold_pct: float = 0.05  # 5% of order book depth

    # CEO Addition B: TTL buffer
    ttl_buffer_seconds: int = 30  # Cancel if < 30s remaining

    # CEO-DIR-2026-107: Canonical exit parameters
    atr_multiplier_stop_loss: float = 2.0   # 2.0x ATR for SL
    r_multiplier_take_profit: float = 1.25  # 1.25R for TP

    # CEO Amendment C: Friction escalation thresholds
    friction_escalation_threshold_pct: float = 0.30  # 30% refusal triggers LARS alert
    friction_escalation_window_hours: int = 24       # Rolling window

    # CEO-DIR-2026-110 R3: Inversion candidate friction escalation
    inversion_friction_threshold_pct: float = 0.50  # 50% refusal triggers Strategic Friction Report
    inversion_escalation_target: str = "LARS"       # CEO R3: LARS receives Strategic Friction Report
    inversion_refusal_escalation_target: str = "FINN"  # CEO R2: FINN receives individual refusals

    # CEO Amendment B: Shadow fill logging
    shadow_fill_log_enabled: bool = True

    # CEO-DIR-2026-110 B2: Valid signal classes
    valid_signal_classes: List[str] = field(default_factory=lambda: [
        'STANDARD',
        'LOW_CONFIDENCE_INVERSION_CANDIDATE',
        'HIGH_CONFIDENCE_VERIFIED',
        'EXPERIMENTAL'
    ])

    def get_hash(self) -> str:
        """Generate hash of parameter set for audit lineage"""
        params_dict = {
            'version': self.version,
            'max_entry_deviation_pct': self.max_entry_deviation_pct,
            'regime_aggression_map': self.regime_aggression_map,
            'liquidity_threshold_pct': self.liquidity_threshold_pct,
            'ttl_buffer_seconds': self.ttl_buffer_seconds,
            'atr_multiplier_stop_loss': self.atr_multiplier_stop_loss,
            'r_multiplier_take_profit': self.r_multiplier_take_profit,
            'friction_escalation_threshold_pct': self.friction_escalation_threshold_pct,
            'friction_escalation_window_hours': self.friction_escalation_window_hours,
            'shadow_fill_log_enabled': self.shadow_fill_log_enabled
        }
        return hashlib.sha256(
            json.dumps(params_dict, sort_keys=True).encode()
        ).hexdigest()


# =============================================================================
# TradePacket: CPTO output for LINE handoff (v1.1.0)
# =============================================================================

@dataclass
class TradePacket:
    """
    CPTO output: Precision-enhanced trade specification for LINE handoff.
    Version 1.1.0: Includes CEO Amendment B fields for alpha attribution.
    """
    # Core trade parameters
    ticker: str
    direction: str  # 'UP' or 'DOWN' (BUY or SELL)
    confidence: float
    limit_price: float
    canonical_stop_loss: float
    canonical_take_profit: float

    # ATR-based calculations
    atr_at_entry: float
    r_value: float  # Risk per share

    # CEO Addition B: TTL
    ttl_valid_until: datetime

    # Fix #5: Full audit lineage (MANDATORY)
    regime_at_calculation: str
    regime_snapshot_hash: str
    parameter_set_version: str
    parameter_content_hash: str
    input_features_hash: str  # Hash of all TA inputs
    outputs_hash: str         # Hash of (entry, SL, TP, R-value)
    calculation_logic_hash: str

    # EC-015 contract binding
    ec_contract_number: str = "EC-015"

    # Source tracking
    source_signal_id: Optional[str] = None
    source_ios: str = "IoS-008"
    signal_timestamp: Optional[datetime] = None
    computed_timestamp: Optional[datetime] = None

    # CEO Amendment B: Alpha Attribution - Slippage Saved
    mid_market_at_signal: Optional[float] = None
    estimated_slippage_saved_bps: Optional[float] = None

    # Execution status
    liquidity_check_passed: bool = True
    ttl_check_passed: bool = True
    refusal_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            'ticker': self.ticker,
            'direction': self.direction,
            'confidence': self.confidence,
            'limit_price': float(self.limit_price),
            'canonical_stop_loss': float(self.canonical_stop_loss),
            'canonical_take_profit': float(self.canonical_take_profit),
            'atr_at_entry': float(self.atr_at_entry),
            'r_value': float(self.r_value),
            'ttl_valid_until': self.ttl_valid_until.isoformat(),
            'regime_at_calculation': self.regime_at_calculation,
            'regime_snapshot_hash': self.regime_snapshot_hash,
            'parameter_set_version': self.parameter_set_version,
            'parameter_content_hash': self.parameter_content_hash,
            'input_features_hash': self.input_features_hash,
            'outputs_hash': self.outputs_hash,
            'calculation_logic_hash': self.calculation_logic_hash,
            'ec_contract_number': self.ec_contract_number,
            'source_signal_id': self.source_signal_id,
            'source_ios': self.source_ios,
            'signal_timestamp': self.signal_timestamp.isoformat() if self.signal_timestamp else None,
            'computed_timestamp': self.computed_timestamp.isoformat() if self.computed_timestamp else None,
            'mid_market_at_signal': float(self.mid_market_at_signal) if self.mid_market_at_signal else None,
            'estimated_slippage_saved_bps': float(self.estimated_slippage_saved_bps) if self.estimated_slippage_saved_bps else None,
            'liquidity_check_passed': self.liquidity_check_passed,
            'ttl_check_passed': self.ttl_check_passed,
            'refusal_reason': self.refusal_reason
        }


# =============================================================================
# CEO Amendment C: Friction Monitor
# =============================================================================

class FrictionMonitor:
    """
    CEO Amendment C: Friction Feedback Loop

    Tracks CPTO refusals/blocks and triggers LARS escalation when:
    - More than 30% of upstream signals are refused within rolling 24h window

    High friction indicates strategy-market mismatch, not CPTO malfunction.
    """

    def __init__(self, conn, params: CPTOParameterSet):
        self.conn = conn
        self.threshold_pct = params.friction_escalation_threshold_pct
        self.window_hours = params.friction_escalation_window_hours

    def record_outcome(
        self,
        ticker: str,
        signal_id: str,
        accepted: bool,
        refusal_reason: Optional[str] = None,
        signal_class: str = "STANDARD"
    ) -> None:
        """Record signal processing outcome for friction tracking"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_alpha.cpto_friction_log (
                        signal_id, ticker, outcome, refusal_reason, recorded_at
                    ) VALUES (%s, %s, %s, %s, NOW())
                """, (
                    signal_id,
                    ticker,
                    'ACCEPTED' if accepted else 'REFUSED',
                    refusal_reason
                ))
                self.conn.commit()

                # CEO-DIR-2026-110: Track inversion candidates separately
                if signal_class == "LOW_CONFIDENCE_INVERSION_CANDIDATE":
                    logger.info(
                        f"Inversion candidate {signal_id} recorded: "
                        f"{'ACCEPTED' if accepted else 'REFUSED'}"
                    )
        except Exception as e:
            logger.error(f"Failed to record friction outcome: {e}")
            self.conn.rollback()

    def compute_friction_rate(self) -> Tuple[float, int, int]:
        """
        Compute current friction rate over rolling window.
        Returns: (friction_pct, refused_count, total_count)
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT fhq_alpha.compute_cpto_friction()
                """)
                result = cur.fetchone()
                if result and result[0]:
                    # Function returns friction percentage
                    friction_pct = float(result[0])

                    # Get counts for reporting
                    cur.execute("""
                        SELECT
                            COUNT(*) FILTER (WHERE outcome = 'REFUSED') as refused,
                            COUNT(*) as total
                        FROM fhq_alpha.cpto_friction_log
                        WHERE recorded_at > NOW() - INTERVAL '%s hours'
                    """, (self.window_hours,))
                    counts = cur.fetchone()
                    return friction_pct, counts[0] or 0, counts[1] or 0
        except Exception as e:
            logger.warning(f"Could not compute friction rate: {e}")

        return 0.0, 0, 0

    def check_and_escalate(self) -> bool:
        """
        Check friction rate and trigger LARS escalation if threshold exceeded.
        Returns True if escalation was triggered.
        """
        friction_pct, refused, total = self.compute_friction_rate()

        if total < 5:
            # Not enough samples for meaningful friction measurement
            return False

        if friction_pct >= self.threshold_pct:
            logger.warning(
                f"FRICTION_ALERT: {friction_pct*100:.1f}% refusal rate "
                f"({refused}/{total}) exceeds {self.threshold_pct*100:.0f}% threshold"
            )
            self._trigger_lars_escalation(friction_pct, refused, total)
            return True

        return False

    def _trigger_lars_escalation(
        self,
        friction_pct: float,
        refused: int,
        total: int
    ) -> None:
        """Trigger LARS escalation for strategic review"""
        try:
            with self.conn.cursor() as cur:
                # Call database escalation function
                cur.execute("""
                    SELECT fhq_alpha.trigger_friction_escalation()
                """)

                # Also log to governance actions
                cur.execute("""
                    INSERT INTO fhq_governance.governance_actions_log (
                        action_type, action_target, action_target_type,
                        initiated_by, decision, decision_rationale,
                        vega_reviewed, created_at
                    ) VALUES (
                        'FRICTION_ESCALATION',
                        'EC-015',
                        'CPTO_FRICTION',
                        'CPTO',
                        'ESCALATED_TO_LARS',
                        %s,
                        false,
                        NOW()
                    )
                """, (
                    f"Friction rate {friction_pct*100:.1f}%% ({refused}/{total}) "
                    f"exceeds {self.threshold_pct*100:.0f}%% threshold. "
                    f"CEO Amendment C: Indicates strategy-market mismatch.",
                ))
                self.conn.commit()

                logger.info("LARS escalation triggered per CEO Amendment C")
        except Exception as e:
            logger.error(f"Failed to trigger LARS escalation: {e}")
            self.conn.rollback()


# =============================================================================
# CPTO Precision Engine v1.1.0
# =============================================================================

class CPTOPrecisionEngine:
    """
    EC-015: Chief Precision Trading Officer (v1.1.0)

    Transforms IoS-008 signals into precision limit orders with regime-adaptive
    entry pricing, canonical exits, and full audit lineage.

    Version 1.1.0 includes:
    - CEO Amendment A: VERIFIED_INVERTED_STRESS regime handling
    - CEO Amendment B: Alpha attribution (slippage saved measurement)
    - CEO Amendment C: Friction feedback loop with LARS escalation
    - DEFCON-aware behavior

    Parent: FINN (Fix #4: Single parent)
    Handoff Interface: LINE receives TradePacket for execution
    Employment Contract: EC-015
    """

    # Calculation logic hash for audit (update when logic changes)
    CALCULATION_LOGIC_VERSION = "1.1.0"

    def __init__(self, db_conn=None):
        """Initialize CPTO engine with database connection"""
        self.params = self._load_active_parameters()
        self.conn = db_conn or self._get_db_connection()
        self._calculation_logic_hash = self._compute_logic_hash()
        self.friction_monitor = FrictionMonitor(self.conn, self.params)
        self._defcon_level = self._get_current_defcon()
        logger.info(
            f"CPTO v{self.CALCULATION_LOGIC_VERSION} initialized with params v{self.params.version}, "
            f"DEFCON={self._defcon_level.name}"
        )

    def _load_active_parameters(self) -> CPTOParameterSet:
        """Load active parameter version from database, fall back to defaults"""
        # Default v1.1.0 parameters
        params = CPTOParameterSet()

        try:
            conn = self._get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        version_number,
                        max_entry_deviation_pct,
                        regime_aggression,
                        liquidity_threshold_pct,
                        ttl_buffer_seconds,
                        atr_multiplier_sl,
                        r_multiplier_tp,
                        extended_params
                    FROM fhq_alpha.cpto_parameter_versions
                    WHERE is_active = true
                    AND superseded_at IS NULL
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                row = cur.fetchone()

                if row:
                    params.version = row['version_number']
                    params.max_entry_deviation_pct = float(row['max_entry_deviation_pct'])
                    params.regime_aggression_map = row['regime_aggression']
                    params.liquidity_threshold_pct = float(row['liquidity_threshold_pct'])
                    params.ttl_buffer_seconds = int(row['ttl_buffer_seconds'])
                    params.atr_multiplier_stop_loss = float(row['atr_multiplier_sl'])
                    params.r_multiplier_take_profit = float(row['r_multiplier_tp'])

                    # Load extended params (CEO amendments)
                    if row['extended_params']:
                        ext = row['extended_params']
                        params.friction_escalation_threshold_pct = float(
                            ext.get('friction_escalation_threshold_pct', 0.30)
                        )
                        params.friction_escalation_window_hours = int(
                            ext.get('friction_escalation_window_hours', 24)
                        )
                        params.shadow_fill_log_enabled = ext.get('shadow_fill_log_enabled', True)

                    logger.info(f"Loaded params v{params.version} from database")
            conn.close()
        except Exception as e:
            logger.warning(f"Could not load params from DB, using defaults: {e}")

        return params

    def _get_db_connection(self):
        """Get database connection from environment"""
        return psycopg2.connect(
            host=os.getenv('PGHOST', '127.0.0.1'),
            port=os.getenv('PGPORT', '54322'),
            database=os.getenv('PGDATABASE', 'postgres'),
            user=os.getenv('PGUSER', 'postgres'),
            password=os.getenv('PGPASSWORD', 'postgres')
        )

    def _compute_logic_hash(self) -> str:
        """Compute hash of calculation logic for audit"""
        logic_signature = f"""
        CPTO_LOGIC_v{self.CALCULATION_LOGIC_VERSION}:
        1. entry_price = regime_adaptive_calculation(regime, direction, price, TA)
        2. stop_loss = entry_price -/+ (ATR * 2.0) per direction
        3. take_profit = entry_price +/- (R * 1.25) per direction
        4. R = abs(entry_price - stop_loss)
        5. slippage_saved_bps = (mid - entry) / mid * 10000 [BUY] or (entry - mid) / mid * 10000 [SELL]
        6. VERIFIED_INVERTED_STRESS uses high aggression (0.002) per CEO Amendment A
        7. Friction monitoring with 30%/24h LARS escalation per CEO Amendment C
        """
        return hashlib.sha256(logic_signature.encode()).hexdigest()[:16]

    def _get_current_defcon(self) -> DEFCONLevel:
        """Get current DEFCON level from database"""
        try:
            conn = self._get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT current_level
                    FROM fhq_governance.defcon_status
                    ORDER BY changed_at DESC
                    LIMIT 1
                """)
                row = cur.fetchone()
                conn.close()

                if row:
                    level_name = row[0].upper()
                    return DEFCONLevel[level_name]
        except Exception as e:
            logger.warning(f"Could not get DEFCON level: {e}")

        return DEFCONLevel.GREEN  # Default to GREEN

    def get_behavior_mode(self) -> CPTOBehavior:
        """Get current CPTO behavior mode based on DEFCON"""
        self._defcon_level = self._get_current_defcon()
        return DEFCON_BEHAVIOR_MAP.get(self._defcon_level, CPTOBehavior.NORMAL)

    # =========================================================================
    # Core Transformation: Signal -> TradePacket
    # =========================================================================

    def transform_signal(
        self,
        ticker: str,
        direction: str,
        confidence: float,
        current_price: float,
        signal_valid_until: datetime,
        signal_id: Optional[str] = None,
        signal_timestamp: Optional[datetime] = None,
        signal_class: str = "STANDARD",
        inversion_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[TradePacket]:
        """
        Main entry point: Transform IoS-008 signal to precision TradePacket.

        Returns TradePacket if all checks pass, None if blocked.
        Implements DEFCON-aware behavior per EC-015 Section 7.

        CEO-DIR-2026-110 B2: Supports signal_class parameter for inversion candidates.
        """
        now = datetime.now(timezone.utc)
        signal_ts = signal_timestamp or now

        logger.info(f"CPTO transforming signal: {ticker} {direction} @ {current_price} (class={signal_class})")

        # CEO-DIR-2026-110 B2: Validate signal class
        if signal_class not in self.params.valid_signal_classes:
            logger.warning(f"INVALID_SIGNAL_CLASS: {signal_class} not in valid classes")
            self._record_refusal(ticker, signal_id, "INVALID_SIGNAL_CLASS")
            return None

        # DEFCON check first (EC-015 Section 7)
        behavior = self.get_behavior_mode()
        if behavior == CPTOBehavior.REFUSE_NEW:
            logger.warning(
                f"DEFCON_BLOCK: CPTO in REFUSE_NEW mode (DEFCON={self._defcon_level.name})"
            )
            self._record_refusal(ticker, signal_id, "DEFCON_REFUSE_NEW", signal_class=signal_class)
            return None

        # CEO Addition B: TTL check
        if not self._check_ttl(signal_valid_until):
            logger.warning(f"TTL_BLOCK: Signal for {ticker} has insufficient TTL")
            self._record_refusal(ticker, signal_id, "TTL_INSUFFICIENT", signal_class=signal_class)
            return None

        # CEO-DIR-2026-110 B2: Inversion candidate gating
        if signal_class == "LOW_CONFIDENCE_INVERSION_CANDIDATE":
            inversion_verified = self._verify_inversion_candidate(
                ticker, signal_id, inversion_metadata
            )
            if not inversion_verified:
                logger.warning(
                    f"INVERSION_GATE_BLOCK: {ticker} signal lacks verified_inverted evidence"
                )
                self._record_inversion_refusal(
                    ticker, signal_id, "INVERSION_UNVERIFIED", inversion_metadata
                )
                return None
            logger.info(f"INVERSION_GATE_PASS: {ticker} verified_inverted=true")

        # Get regime state (CEO Addition A + Amendment A)
        regime, regime_hash = self._get_regime_state(ticker)
        logger.info(f"Regime for {ticker}: {regime}")

        # CONSERVATIVE mode adjustments (DEFCON ORANGE)
        conservative_mode = (behavior == CPTOBehavior.CONSERVATIVE)

        # Calculate precision entry
        entry_price, input_hash, indicators = self._calculate_precision_entry(
            ticker, direction, current_price, regime, conservative_mode
        )

        # CEO Amendment B: Store mid-market price for slippage calculation
        mid_market = current_price

        # Get ATR for canonical exits
        atr = self._get_canonical_atr(ticker)
        if atr is None or atr <= 0:
            logger.error(f"ATR_ERROR: Cannot get valid ATR for {ticker}")
            self._record_refusal(ticker, signal_id, "ATR_UNAVAILABLE")
            return None

        # Calculate canonical exits (CEO-DIR-2026-107)
        stop_loss, take_profit, r_value = self._calculate_canonical_exits(
            entry_price, direction, atr
        )

        # Compute outputs hash (Fix #5)
        outputs_hash = self._compute_outputs_hash(entry_price, stop_loss, take_profit, r_value)

        # CEO Addition C: Liquidity check
        # In conservative mode, use stricter threshold
        liquidity_threshold = self.params.liquidity_threshold_pct
        if conservative_mode:
            liquidity_threshold *= 0.5  # Halve threshold in conservative mode

        liquidity_passed = True  # Placeholder - needs real order book data

        # CEO Amendment B: Calculate estimated slippage saved
        slippage_saved_bps = self._calculate_slippage_saved(
            direction, entry_price, mid_market
        )

        # Build TradePacket
        computed_at = datetime.now(timezone.utc)
        packet = TradePacket(
            ticker=ticker,
            direction=direction,
            confidence=confidence,
            limit_price=entry_price,
            canonical_stop_loss=stop_loss,
            canonical_take_profit=take_profit,
            atr_at_entry=atr,
            r_value=r_value,
            ttl_valid_until=signal_valid_until,
            regime_at_calculation=regime,
            regime_snapshot_hash=regime_hash,
            parameter_set_version=self.params.version,
            parameter_content_hash=self.params.get_hash()[:16],
            input_features_hash=input_hash,
            outputs_hash=outputs_hash,
            calculation_logic_hash=self._calculation_logic_hash,
            ec_contract_number="EC-015",
            source_signal_id=signal_id,
            signal_timestamp=signal_ts,
            computed_timestamp=computed_at,
            mid_market_at_signal=mid_market,
            estimated_slippage_saved_bps=slippage_saved_bps,
            liquidity_check_passed=liquidity_passed,
            ttl_check_passed=True,
            refusal_reason=None
        )

        # Log to database for audit
        self._log_precision_calculation(packet, indicators)

        # CEO Amendment C: Record successful outcome for friction tracking
        self.friction_monitor.record_outcome(ticker, signal_id or "N/A", accepted=True)

        # Check if friction threshold exceeded
        self.friction_monitor.check_and_escalate()

        logger.info(
            f"CPTO TradePacket: {ticker} {direction} "
            f"Entry={entry_price:.2f} SL={stop_loss:.2f} TP={take_profit:.2f} "
            f"SlippageSaved={slippage_saved_bps:.2f}bps"
        )

        return packet

    def _record_refusal(
        self,
        ticker: str,
        signal_id: Optional[str],
        reason: str,
        signal_class: str = "STANDARD"
    ) -> None:
        """Record a signal refusal for friction tracking (CEO Amendment C)"""
        self.friction_monitor.record_outcome(
            ticker=ticker,
            signal_id=signal_id or "UNKNOWN",
            accepted=False,
            refusal_reason=reason,
            signal_class=signal_class
        )
        # Check if this refusal pushed us over the threshold
        self.friction_monitor.check_and_escalate()

    # =========================================================================
    # CEO-DIR-2026-110 B2: Inversion Candidate Gating
    # =========================================================================

    def _verify_inversion_candidate(
        self,
        ticker: str,
        signal_id: Optional[str],
        inversion_metadata: Optional[Dict[str, Any]]
    ) -> bool:
        """
        CEO-DIR-2026-110 B2: Verify inversion candidate has required evidence.

        Returns True if verified_inverted=true, False otherwise.
        Inversion candidates without verification are REFUSED.
        """
        if inversion_metadata is None:
            logger.warning(f"Inversion candidate {signal_id} has no metadata")
            return False

        # Check verified_inverted flag
        verified = inversion_metadata.get('verified_inverted', False)
        if not verified:
            logger.warning(
                f"Inversion candidate {signal_id} has verified_inverted=false"
            )
            return False

        # Check minimum evidence requirements
        required_fields = [
            'inversion_verification_source',
            'historical_inversion_evidence'
        ]
        for field in required_fields:
            if field not in inversion_metadata or inversion_metadata[field] is None:
                logger.warning(
                    f"Inversion candidate {signal_id} missing required field: {field}"
                )
                return False

        return True

    def _record_inversion_refusal(
        self,
        ticker: str,
        signal_id: Optional[str],
        reason: str,
        inversion_metadata: Optional[Dict[str, Any]]
    ) -> None:
        """
        CEO-DIR-2026-110 R2: Record inversion candidate refusal with FINN escalation.

        Unlike standard refusals that escalate to LARS, inversion refusals
        escalate to FINN for strategy-level feedback.
        """
        # Record to standard friction log
        self._record_refusal(
            ticker, signal_id, reason,
            signal_class="LOW_CONFIDENCE_INVERSION_CANDIDATE"
        )

        # Record to inversion-specific evidence table
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_alpha.inversion_candidate_evidence (
                        signal_id,
                        regime_at_signal,
                        confidence_at_signal,
                        verified_inverted,
                        inversion_verification_source,
                        historical_inversion_evidence,
                        cpto_decision,
                        cpto_refusal_reason,
                        cpto_processed_at,
                        logged_to_friction,
                        friction_escalation_target
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, NOW(), true, %s
                    )
                """, (
                    signal_id,
                    inversion_metadata.get('regime', 'UNKNOWN') if inversion_metadata else 'UNKNOWN',
                    inversion_metadata.get('confidence', 0) if inversion_metadata else 0,
                    inversion_metadata.get('verified_inverted', False) if inversion_metadata else False,
                    inversion_metadata.get('inversion_verification_source') if inversion_metadata else None,
                    json.dumps(inversion_metadata.get('historical_inversion_evidence')) if inversion_metadata and inversion_metadata.get('historical_inversion_evidence') else None,
                    'REFUSED',
                    reason,
                    self.params.inversion_refusal_escalation_target  # FINN
                ))
                self.conn.commit()
                logger.info(
                    f"Inversion refusal logged with escalation_target={self.params.inversion_refusal_escalation_target}"
                )
        except Exception as e:
            logger.error(f"Failed to log inversion refusal: {e}")
            self.conn.rollback()

        # Check inversion-specific friction threshold (CEO R3: 50%)
        self._check_inversion_friction_escalation()

    def _check_inversion_friction_escalation(self) -> None:
        """
        CEO-DIR-2026-110 R3: Check if inversion candidate friction exceeds 50%.

        If >50% of inversion candidate signals refused in rolling 24h window,
        trigger Strategic Friction Report to LARS.
        """
        try:
            with self.conn.cursor() as cur:
                # Compute inversion candidate friction rate
                cur.execute("""
                    WITH inversion_window AS (
                        SELECT
                            COUNT(*) FILTER (WHERE cpto_decision = 'REFUSED') as refused,
                            COUNT(*) as total
                        FROM fhq_alpha.inversion_candidate_evidence
                        WHERE cpto_processed_at > NOW() - INTERVAL '24 hours'
                    )
                    SELECT
                        refused,
                        total,
                        CASE WHEN total > 0 THEN refused::numeric / total ELSE 0 END as refusal_rate
                    FROM inversion_window
                """)
                result = cur.fetchone()

                if result and result[2]:
                    refused, total, refusal_rate = result
                    threshold = self.params.inversion_friction_threshold_pct

                    if total >= 3 and refusal_rate >= threshold:  # Minimum 3 signals for meaningful rate
                        logger.warning(
                            f"INVERSION_FRICTION_ALERT: {refusal_rate*100:.1f}% refused "
                            f"({refused}/{total}) exceeds {threshold*100:.0f}% threshold"
                        )

                        # Log to inversion friction table
                        cur.execute("""
                            INSERT INTO fhq_alpha.cpto_inversion_friction_log (
                                window_start,
                                window_end,
                                window_hours,
                                inversion_candidates_received,
                                inversion_candidates_accepted,
                                inversion_candidates_refused,
                                inversion_refusal_rate,
                                refused_unverified,
                                threshold_pct,
                                threshold_exceeded,
                                strategic_friction_report_triggered,
                                escalation_sent_to,
                                escalation_timestamp
                            ) VALUES (
                                NOW() - INTERVAL '24 hours',
                                NOW(),
                                24,
                                %s,
                                %s,
                                %s,
                                %s,
                                %s,
                                %s,
                                true,
                                true,
                                %s,
                                NOW()
                            )
                        """, (
                            total,
                            total - refused,
                            refused,
                            float(refusal_rate),
                            refused,  # Assuming all are unverified refusals
                            threshold,
                            self.params.inversion_escalation_target  # LARS
                        ))

                        # Log governance action for Strategic Friction Report
                        cur.execute("""
                            INSERT INTO fhq_governance.governance_actions_log (
                                action_type,
                                action_target,
                                action_target_type,
                                initiated_by,
                                initiated_at,
                                decision,
                                decision_rationale,
                                vega_reviewed
                            ) VALUES (
                                'STRATEGIC_FRICTION_REPORT',
                                'CEO-DIR-2026-110',
                                'INVERSION_CANDIDATE_ESCALATION',
                                'CPTO',
                                NOW(),
                                'ESCALATED_TO_LARS',
                                %s,
                                false
                            )
                        """, (
                            f"Inversion candidate refusal rate {refusal_rate*100:.1f}% "
                            f"({refused}/{total}) exceeds 50% threshold. "
                            f"Strategic Friction Report sent to LARS per CEO-DIR-2026-110 R3.",
                        ))

                        self.conn.commit()
                        logger.info(
                            f"Strategic Friction Report sent to {self.params.inversion_escalation_target}"
                        )

        except Exception as e:
            logger.error(f"Failed to check inversion friction escalation: {e}")
            self.conn.rollback()

    # =========================================================================
    # CEO Amendment B: Slippage Saved Calculation
    # =========================================================================

    def _calculate_slippage_saved(
        self,
        direction: str,
        limit_price: float,
        mid_market: float
    ) -> float:
        """
        CEO Amendment B: Calculate estimated slippage saved in basis points.

        Counterfactual cost avoidance - the difference between market execution
        and precision limit execution.

        Formula:
          BUY: (mid_market - limit_price) / mid_market * 10000
          SELL: (limit_price - mid_market) / mid_market * 10000

        Positive value = alpha contribution (limit price better than market).
        """
        if mid_market <= 0:
            return 0.0

        if direction == 'UP':  # BUY
            # For BUY, limit below mid = savings
            slippage_saved = (mid_market - limit_price) / mid_market * 10000
        else:  # DOWN / SELL
            # For SELL, limit above mid = savings
            slippage_saved = (limit_price - mid_market) / mid_market * 10000

        return round(slippage_saved, 2)

    # =========================================================================
    # CEO Addition A + Amendment A: Regime-Adaptive Entry
    # =========================================================================

    def _calculate_precision_entry(
        self,
        ticker: str,
        direction: str,
        current_price: float,
        regime: str,
        conservative_mode: bool = False
    ) -> Tuple[float, str, Dict[str, float]]:
        """
        Regime-Adaptive entry calculation (CEO Addition A + Amendment A).

        Amendment A: VERIFIED_INVERTED_STRESS uses high aggression (0.002)
        because documented inversions justify prioritizing fill probability.

        Returns (entry_price, input_features_hash, indicators)
        """
        indicators = self._get_latest_indicators(ticker)

        # Get regime-specific aggression factor
        # Amendment A: VERIFIED_INVERTED_STRESS explicitly handled
        aggression = self.params.regime_aggression_map.get(
            regime,
            self.params.max_entry_deviation_pct  # Default fallback
        )

        # Conservative mode: increase aggression for more safety margin
        if conservative_mode:
            aggression = min(aggression * 1.5, self.params.max_entry_deviation_pct)

        # Calculate entry based on direction and regime
        if direction == 'UP':
            if regime in ('STRONG_BULL', 'MODERATE_BULL', 'VERIFIED_INVERTED_STRESS'):
                # High aggression: closer to current price for high fill probability
                # Amendment A: VERIFIED_INVERTED_STRESS treated like STRONG_BULL
                entry = current_price * (1 - aggression)
            elif regime in ('VOLATILE', 'STRESS'):
                # Low aggression: maximum margin of safety
                bb_lower = indicators.get('bb_lower', current_price * 0.98)
                entry = min(bb_lower, current_price * (1 - aggression))
            else:
                # Medium: EMA(21) level
                ema_21 = indicators.get('ema_21', current_price)
                entry = min(ema_21, current_price * (1 - aggression))
        else:
            # DOWN (short) direction - inverse logic
            if regime in ('STRONG_BULL', 'MODERATE_BULL'):
                # In bull regime, shorts need more margin
                entry = current_price * (1 + aggression * 1.5)
            elif regime in ('VERIFIED_INVERTED_STRESS',):
                # Amendment A: Inverted STRESS for shorts = bullish behavior expected
                entry = current_price * (1 + aggression)
            elif regime in ('VOLATILE', 'STRESS'):
                bb_upper = indicators.get('bb_upper', current_price * 1.02)
                entry = max(bb_upper, current_price * (1 + aggression))
            else:
                ema_21 = indicators.get('ema_21', current_price)
                entry = max(ema_21, current_price * (1 + aggression))

        # Ensure entry doesn't deviate too much from current
        max_deviation = current_price * self.params.max_entry_deviation_pct
        if direction == 'UP':
            entry = max(entry, current_price - max_deviation)
        else:
            entry = min(entry, current_price + max_deviation)

        # Fix #5: Create input features hash
        input_features = {
            'ticker': ticker,
            'current_price': current_price,
            'regime': regime,
            'direction': direction,
            'bb_lower': indicators.get('bb_lower'),
            'bb_upper': indicators.get('bb_upper'),
            'ema_21': indicators.get('ema_21'),
            'aggression': aggression,
            'conservative_mode': conservative_mode,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        features_hash = hashlib.sha256(
            json.dumps(input_features, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

        return round(entry, 2), features_hash, indicators

    # =========================================================================
    # CEO-DIR-2026-107: Canonical Exits
    # =========================================================================

    def _calculate_canonical_exits(
        self,
        entry_price: float,
        direction: str,
        atr: float
    ) -> Tuple[float, float, float]:
        """
        Calculate canonical TP/SL per CEO-DIR-2026-107.
        Returns (stop_loss, take_profit, r_value)
        """
        # R = ATR * multiplier (the risk per share)
        r_value = atr * self.params.atr_multiplier_stop_loss

        if direction == 'UP':
            stop_loss = entry_price - r_value
            take_profit = entry_price + (r_value * self.params.r_multiplier_take_profit)
        else:
            stop_loss = entry_price + r_value
            take_profit = entry_price - (r_value * self.params.r_multiplier_take_profit)

        return round(stop_loss, 2), round(take_profit, 2), round(r_value, 4)

    def _compute_outputs_hash(
        self,
        entry: float,
        stop_loss: float,
        take_profit: float,
        r_value: float
    ) -> str:
        """Compute hash of outputs for audit lineage"""
        outputs = {
            'entry': entry,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'r_value': r_value
        }
        return hashlib.sha256(
            json.dumps(outputs, sort_keys=True).encode()
        ).hexdigest()[:16]

    # =========================================================================
    # CEO Addition B: TTL Check
    # =========================================================================

    def _check_ttl(self, signal_valid_until: datetime) -> bool:
        """CEO Addition B: TTL sync check"""
        now = datetime.now(timezone.utc)

        # Handle naive datetime
        if signal_valid_until.tzinfo is None:
            signal_valid_until = signal_valid_until.replace(tzinfo=timezone.utc)

        remaining = (signal_valid_until - now).total_seconds()

        if remaining < self.params.ttl_buffer_seconds:
            logger.warning(
                f"TTL_BLOCK: Only {remaining:.0f}s remaining, "
                f"< {self.params.ttl_buffer_seconds}s buffer"
            )
            return False
        return True

    # =========================================================================
    # CEO Addition C: Liquidity Check
    # =========================================================================

    def check_liquidity(
        self,
        ticker: str,
        limit_price: float,
        position_size_usd: float
    ) -> bool:
        """
        CEO Addition C: Liquidity-aware sizing gate.
        Blocks if position > 5% of order book depth.
        """
        depth = self._get_order_book_depth(ticker, limit_price)
        if depth is None:
            logger.warning(f"No order book data for {ticker}, proceeding")
            return True  # Proceed if no data (log warning)

        threshold = depth * self.params.liquidity_threshold_pct
        if position_size_usd > threshold:
            logger.warning(
                f"LIQUIDITY_BLOCK: {ticker} size ${position_size_usd:.2f} > "
                f"5%% of depth ${threshold:.2f}"
            )
            return False  # Block per ADR-012
        return True

    # =========================================================================
    # Database Queries
    # =========================================================================

    def _get_regime_state(self, ticker: str) -> Tuple[str, str]:
        """
        Get current regime state and snapshot hash.
        Amendment A: Supports VERIFIED_INVERTED_STRESS from upstream metadata.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Query IoS-003 regime state with potential inversion flag
            cur.execute("""
                SELECT
                    regime_label,
                    regime_confidence,
                    calculated_at,
                    COALESCE(metadata->>'verified_inverted', 'false') as verified_inverted,
                    md5(regime_label || ':' || regime_confidence::text || ':' || calculated_at::text) as snapshot_hash
                FROM fhq_research.regime_classifications
                WHERE ticker = %s
                ORDER BY calculated_at DESC
                LIMIT 1
            """, (ticker,))
            row = cur.fetchone()

            if row:
                regime = row['regime_label']

                # Amendment A: Check for verified inversion
                if regime == 'STRESS' and row['verified_inverted'] == 'true':
                    regime = 'VERIFIED_INVERTED_STRESS'

                return regime, row['snapshot_hash']

            # Fallback to global regime if ticker-specific not found
            cur.execute("""
                SELECT
                    current_regime,
                    md5(current_regime || ':' || updated_at::text) as snapshot_hash
                FROM fhq_research.global_regime_state
                ORDER BY updated_at DESC
                LIMIT 1
            """)
            row = cur.fetchone()

            if row:
                return row['current_regime'], row['snapshot_hash']

            # Default fallback
            return 'NEUTRAL', hashlib.md5(b'NEUTRAL:default').hexdigest()[:8]

    def _get_latest_indicators(self, ticker: str) -> Dict[str, float]:
        """Get latest TA indicators for ticker"""
        indicators = {}
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    indicator_name,
                    indicator_value
                FROM fhq_research.indicator_values
                WHERE ticker = %s
                AND indicator_name IN ('ema_21', 'bb_lower', 'bb_upper', 'bb_mid', 'rsi_14')
                AND calculated_at > NOW() - INTERVAL '24 hours'
                ORDER BY calculated_at DESC
            """, (ticker,))

            for row in cur.fetchall():
                indicators[row['indicator_name']] = float(row['indicator_value'])

        return indicators

    def _get_canonical_atr(self, ticker: str, period: int = 14) -> Optional[float]:
        """
        Get canonical ATR(14) for ticker with on-the-fly fallback.

        CEO-DIR-2026-120 P1.1: Enhanced ATR retrieval with multi-source fallback:
        1. Try fhq_alpha function
        2. Try fhq_research.indicator_values
        3. Try fhq_indicators.volatility
        4. Calculate on-the-fly from price data
        """
        with self.conn.cursor() as cur:
            # Source 1: Try dedicated function first
            try:
                cur.execute("SELECT fhq_alpha.get_canonical_atr(%s)", (ticker,))
                result = cur.fetchone()
                if result and result[0]:
                    logger.info(f"ATR for {ticker} from fhq_alpha function: {result[0]}")
                    return float(result[0])
            except Exception:
                pass

            # Source 2: Fallback to indicator_values
            try:
                cur.execute("""
                    SELECT indicator_value
                    FROM fhq_research.indicator_values
                    WHERE ticker = %s
                    AND indicator_name = 'atr_14'
                    ORDER BY calculated_at DESC
                    LIMIT 1
                """, (ticker,))
                row = cur.fetchone()
                if row and row[0]:
                    logger.info(f"ATR for {ticker} from indicator_values: {row[0]}")
                    return float(row[0])
            except Exception:
                pass

            # Source 3: Try fhq_indicators.volatility table
            try:
                cur.execute("""
                    SELECT atr_14
                    FROM fhq_indicators.volatility
                    WHERE listing_id = %s
                    ORDER BY signal_date DESC
                    LIMIT 1
                """, (ticker,))
                row = cur.fetchone()
                if row and row[0]:
                    logger.info(f"ATR for {ticker} from volatility table: {row[0]}")
                    return float(row[0])
            except Exception:
                pass

        # Source 4: Calculate on-the-fly from price data
        logger.info(f"Computing ATR on-the-fly for {ticker} (no cached data)")
        return self._calculate_atr_from_price_data(ticker, period)

    def _calculate_atr_from_price_data(self, ticker: str, period: int = 14) -> Optional[float]:
        """
        Calculate ATR on-the-fly from fhq_data.price_series.

        CEO-DIR-2026-120 P1.1: Fallback ATR calculation when database lacks pre-computed values.
        Uses True Range methodology: max(H-L, |H-C_prev|, |L-C_prev|)
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get enough price data for ATR calculation
                cur.execute("""
                    SELECT date, high, low, close
                    FROM fhq_data.price_series
                    WHERE listing_id = %s
                    ORDER BY date DESC
                    LIMIT %s
                """, (ticker, period + 5))

                rows = cur.fetchall()

                if len(rows) < period + 1:
                    logger.warning(f"Insufficient price data for ATR: {ticker} ({len(rows)} rows)")
                    return None

                # Reverse to chronological order
                rows = list(reversed(rows))

                # Calculate True Range for each bar
                true_ranges = []
                for i in range(1, len(rows)):
                    high = float(rows[i]['high'])
                    low = float(rows[i]['low'])
                    prev_close = float(rows[i-1]['close'])

                    # True Range = max(H-L, |H-C_prev|, |L-C_prev|)
                    tr = max(
                        high - low,
                        abs(high - prev_close),
                        abs(low - prev_close)
                    )
                    true_ranges.append(tr)

                if len(true_ranges) < period:
                    logger.warning(f"Not enough True Range values for ATR: {ticker}")
                    return None

                # ATR = SMA of True Range
                atr = sum(true_ranges[-period:]) / period

                logger.info(f"ATR({period}) for {ticker} calculated on-the-fly: {atr:.4f}")

                # Cache to volatility table for future use
                try:
                    cur.execute("""
                        INSERT INTO fhq_indicators.volatility (
                            listing_id, signal_date, atr_14, created_at
                        ) VALUES (%s, CURRENT_DATE, %s, NOW())
                        ON CONFLICT (listing_id, signal_date)
                        DO UPDATE SET atr_14 = EXCLUDED.atr_14, created_at = NOW()
                    """, (ticker, round(atr, 4)))
                    self.conn.commit()
                except Exception as cache_err:
                    logger.warning(f"Failed to cache ATR: {cache_err}")
                    self.conn.rollback()

                return round(atr, 4)

        except Exception as e:
            logger.error(f"Failed to calculate ATR from price data for {ticker}: {e}")
            return None

    def _get_order_book_depth(
        self,
        ticker: str,
        price_level: float
    ) -> Optional[float]:
        """
        Get order book depth / liquidity proxy at price level.

        CEO-DIR-2026-120 P1.2: Replace placeholder with Alpaca quotes API.
        Uses NBBO spread as liquidity proxy when depth unavailable.

        Returns USD value of estimated liquidity or None if unavailable.
        """
        try:
            import os
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockLatestQuoteRequest

            api_key = os.getenv('ALPACA_API_KEY', '')
            secret_key = os.getenv('ALPACA_SECRET', os.getenv('ALPACA_SECRET_KEY', ''))

            if not api_key or not secret_key:
                logger.warning(f"No Alpaca credentials for order book check: {ticker}")
                return None

            data_client = StockHistoricalDataClient(api_key, secret_key)
            request = StockLatestQuoteRequest(symbol_or_symbols=[ticker])

            quotes = data_client.get_stock_latest_quote(request)

            if ticker not in quotes:
                logger.warning(f"No quote data for {ticker}")
                return None

            quote = quotes[ticker]

            # Extract NBBO data
            bid_price = float(quote.bid_price) if quote.bid_price else 0
            ask_price = float(quote.ask_price) if quote.ask_price else 0
            bid_size = int(quote.bid_size) if quote.bid_size else 0
            ask_size = int(quote.ask_size) if quote.ask_size else 0

            if bid_price <= 0 or ask_price <= 0:
                logger.warning(f"Invalid NBBO for {ticker}: bid={bid_price}, ask={ask_price}")
                return None

            # Calculate spread as liquidity indicator
            spread_pct = (ask_price - bid_price) / bid_price if bid_price > 0 else 1.0

            # Estimate depth from NBBO sizes (conservative estimate)
            # Actual depth would require Level 2 data
            mid_price = (bid_price + ask_price) / 2
            estimated_depth_bid = bid_size * bid_price
            estimated_depth_ask = ask_size * ask_price
            estimated_total_depth = estimated_depth_bid + estimated_depth_ask

            logger.info(
                f"Liquidity proxy for {ticker}: spread={spread_pct:.4f}%, "
                f"bid_depth=${estimated_depth_bid:,.0f}, ask_depth=${estimated_depth_ask:,.0f}"
            )

            # Log to database for analysis
            self._log_liquidity_check(ticker, price_level, spread_pct, estimated_total_depth)

            return estimated_total_depth

        except ImportError:
            logger.warning("Alpaca SDK not available for liquidity check")
            return None
        except Exception as e:
            logger.error(f"Failed to get order book depth for {ticker}: {e}")
            return None

    def _log_liquidity_check(
        self,
        ticker: str,
        price_level: float,
        spread_pct: float,
        estimated_depth: float
    ) -> None:
        """Log liquidity check for analysis and monitoring."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_alpha.cpto_liquidity_log (
                        ticker, price_level, spread_pct, estimated_depth_usd, checked_at
                    ) VALUES (%s, %s, %s, %s, NOW())
                """, (ticker, price_level, spread_pct, estimated_depth))
                self.conn.commit()
        except Exception as e:
            logger.warning(f"Failed to log liquidity check: {e}")
            try:
                self.conn.rollback()
            except:
                pass

    def _log_precision_calculation(
        self,
        packet: TradePacket,
        indicators: Dict[str, float]
    ) -> None:
        """Log precision calculation to database for audit (Fix #5 + Amendment B)"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_alpha.cpto_precision_log (
                        ticker, direction, signal_timestamp,
                        signal_confidence, signal_ttl_valid_until, current_market_price,
                        regime_at_calculation, regime_snapshot_hash,
                        calculated_entry_price, entry_aggression,
                        ema_21, bb_lower, bb_upper,
                        liquidity_check_passed,
                        atr_14, canonical_stop_loss, canonical_take_profit, r_value,
                        parameter_set_version, input_features_hash, calculation_logic_hash,
                        ec_contract_number, source_signal_id,
                        mid_market_at_signal, estimated_slippage_saved_bps,
                        created_at
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s,
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        NOW()
                    )
                """, (
                    packet.ticker,
                    packet.direction,
                    packet.signal_timestamp,
                    packet.confidence,
                    packet.ttl_valid_until,
                    packet.mid_market_at_signal,
                    packet.regime_at_calculation,
                    packet.regime_snapshot_hash,
                    packet.limit_price,
                    self.params.regime_aggression_map.get(
                        packet.regime_at_calculation, 0.005
                    ),
                    indicators.get('ema_21'),
                    indicators.get('bb_lower'),
                    indicators.get('bb_upper'),
                    packet.liquidity_check_passed,
                    packet.atr_at_entry,
                    packet.canonical_stop_loss,
                    packet.canonical_take_profit,
                    packet.r_value,
                    packet.parameter_set_version,
                    packet.input_features_hash,
                    packet.calculation_logic_hash,
                    packet.ec_contract_number,
                    packet.source_signal_id,
                    packet.mid_market_at_signal,
                    packet.estimated_slippage_saved_bps
                ))
                self.conn.commit()
                logger.info(f"Logged precision calculation for {packet.ticker}")
        except Exception as e:
            logger.error(f"Failed to log precision calculation: {e}")
            self.conn.rollback()

    # =========================================================================
    # LINE Handoff Interface
    # =========================================================================

    def submit_to_line(self, packet: TradePacket) -> str:
        """
        Submit TradePacket to LINE for execution via handoff interface.
        Returns handoff_id for tracking.
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_alpha.cpto_line_handoff (
                        ticker, direction, limit_price,
                        canonical_stop_loss, canonical_take_profit,
                        ttl_valid_until, source_signal_id,
                        parameter_version, regime_at_handoff,
                        cpto_precision_hash, handoff_status
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, 'PENDING_LINE'
                    )
                    RETURNING handoff_id
                """, (
                    packet.ticker,
                    packet.direction,
                    packet.limit_price,
                    packet.canonical_stop_loss,
                    packet.canonical_take_profit,
                    packet.ttl_valid_until,
                    packet.source_signal_id,
                    packet.parameter_set_version,
                    packet.regime_at_calculation,
                    packet.outputs_hash
                ))
                handoff_id = cur.fetchone()[0]
                self.conn.commit()

                logger.info(f"TradePacket submitted to LINE: handoff_id={handoff_id}")
                return str(handoff_id)
        except Exception as e:
            logger.error(f"Failed to submit to LINE: {e}")
            self.conn.rollback()
            raise


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """CLI entry point for testing CPTO"""
    import argparse

    parser = argparse.ArgumentParser(
        description='CPTO Precision Engine v1.1.0 (CEO Amendments A, B, C)'
    )
    parser.add_argument('--ticker', required=True, help='Ticker symbol')
    parser.add_argument('--direction', choices=['UP', 'DOWN'], required=True)
    parser.add_argument('--price', type=float, required=True, help='Current price')
    parser.add_argument('--confidence', type=float, default=0.7)
    parser.add_argument('--ttl-hours', type=float, default=24)
    parser.add_argument('--submit', action='store_true', help='Submit to LINE handoff')

    args = parser.parse_args()

    engine = CPTOPrecisionEngine()

    valid_until = datetime.now(timezone.utc) + timedelta(hours=args.ttl_hours)

    packet = engine.transform_signal(
        ticker=args.ticker,
        direction=args.direction,
        confidence=args.confidence,
        current_price=args.price,
        signal_valid_until=valid_until
    )

    if packet:
        print(json.dumps(packet.to_dict(), indent=2, default=str))

        if args.submit:
            handoff_id = engine.submit_to_line(packet)
            print(f"\nSubmitted to LINE: handoff_id={handoff_id}")
    else:
        print("Signal blocked by CPTO checks")
        sys.exit(1)


if __name__ == '__main__':
    main()
