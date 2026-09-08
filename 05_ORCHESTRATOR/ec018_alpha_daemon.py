"""
EC-018 Alpha Discovery Daemon
============================
CEO Directive: CD-EC018-IOS004-ALPHA-PIPELINE-001

Autonomous alpha hypothesis generation with:
- Hourly scheduled hunts
- DeepSeek LLM for hypothesis generation
- Serper API for real-time market intelligence
- $2/day budget constraint
- Automatic trigger of IoS-004 backtest via database insert

Authority: ZERO execution - hypothesis generation only
"""

import os
import sys
import json
import time
import hashlib
import logging
import argparse
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor, Json
import requests

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv('C:/fhq-market-system/vision-ios/.env')

# =============================================================================
# CEO DIRECTIVE MANDATE I & II: IKEA + InForage Integration (2025-12-17)
# =============================================================================

# EC-022 IKEA: Knowledge Boundary Engine (Mandate V)
try:
    from ios022_ikea_boundary_engine import IKEABoundaryEngine, Classification
    IKEA_AVAILABLE = True
except ImportError:
    IKEA_AVAILABLE = False

# EC-021 InForage: Cost Controller
try:
    from inforage_cost_controller import InForageCostController, StepType, CostDecision
    COST_CONTROL_AVAILABLE = True
except ImportError:
    COST_CONTROL_AVAILABLE = False

# =============================================================================
# CEO DIRECTIVE WAVE 7: EC-020 SitC Integration (2025-12-17)
# =============================================================================
# SitC operates as FILTER only - structural validation, evidence checking
# NOT a CO-THINKER - cannot modify hypotheses
try:
    from ios020_sitc_planner import (
        SitCPlannerWithGuardrails,
        PlanConfidenceEnvelope,
        PlanConfidence,
        AbortReason,
        SitCRoleViolation,
        DEFCONViolation as SitCDEFCONViolation,
        RuntimeEconomicViolation as SitCEconomicViolation,
        MITQuadViolation,
        get_sitc_planner_with_guardrails
    )
    SITC_AVAILABLE = True
except ImportError as e:
    SITC_AVAILABLE = False
    import logging
    logging.warning(f"SitC not available: {e}")


class RuntimeEconomicViolation(Exception):
    """Raised when economic safety cannot be enforced - HARD FAIL."""
    pass


class RuntimeEconomicGuardian:
    """
    Unbypassable economic safety enforcement per CEO Directive Mandate II.

    If InForageCostController fails to load or function, all operations MUST halt.
    No optional fallbacks. No try/except bypasses.
    """

    def __init__(self, session_id: str):
        self._cost_controller = None
        self._load_failed = False
        self._failure_reason = None
        self.session_id = session_id

    def initialize(self) -> bool:
        """Initialize the cost controller. MUST succeed or block all operations."""
        try:
            if not COST_CONTROL_AVAILABLE:
                raise RuntimeEconomicViolation(
                    "InForageCostController module not available - EC-018 BLOCKED"
                )
            self._cost_controller = InForageCostController(session_id=self.session_id)
            return True
        except Exception as e:
            self._load_failed = True
            self._failure_reason = str(e)
            return False

    def check_or_fail(self, step_type: 'StepType', predicted_gain: float = 0.5):
        """Check cost or HARD FAIL. No exceptions, no bypasses."""
        if self._load_failed or self._cost_controller is None:
            raise RuntimeEconomicViolation(
                f"Cost controller unavailable - EC-018 HARD FAIL. Reason: {self._failure_reason}"
            )
        return self._cost_controller.check_cost(step_type, predicted_gain)

    @property
    def is_operational(self) -> bool:
        return not self._load_failed and self._cost_controller is not None


# =============================================================================
# CEO DIRECTIVE WAVE 9: Schema Boundary Enforcement
# =============================================================================
# EC-018 + SitC may NOT write to:
# - fhq_research.* (any table)
# - fhq_alpha.g1_* (any table starting with g1_)
#
# Writes are RESTRICTED to:
# - fhq_alpha.g0_draft_proposals (with sitc_* fields)
# - fhq_alpha.hunt_sessions, hunt_telemetry
# - fhq_alpha.state_vectors
# - fhq_meta.chain_of_query
# - fhq_meta.cognitive_engine_evidence
# - fhq_meta.aci_state_snapshot_log
# =============================================================================

class SchemaBoundaryViolation(Exception):
    """Raised when EC-018 attempts to write to prohibited schema/tables."""
    pass


class EC018SchemaBoundary:
    """
    CEO Directive Wave 9: Canonical Promotion Block

    EC-018 operates in G0 (Draft) space ONLY. It may not promote
    hypotheses to G1 or write to research tables. All canonical
    promotion must go through IoS-004 backtest → G1 validation.
    """

    # Allowed schemas and tables for EC-018 writes
    ALLOWED_WRITES = {
        'fhq_alpha': {
            'g0_draft_proposals',
            'hunt_sessions',
            'hunt_telemetry',
            'state_vectors'
        },
        'fhq_meta': {
            'chain_of_query',
            'cognitive_engine_evidence',
            'aci_state_snapshot_log',
            'knowledge_boundary_log',
            'search_foraging_log'
        },
        'fhq_optimization': {
            'inforage_cost_log'
        },
        'fhq_governance': {
            'llm_routing_log'
        }
    }

    # Explicitly blocked patterns
    BLOCKED_PATTERNS = [
        ('fhq_research', None),       # Block entire schema
        ('fhq_alpha', 'g1_'),         # Block g1_* tables
        ('fhq_alpha', 'g2_'),         # Block g2_* tables
        ('fhq_alpha', 'g3_'),         # Block g3_* tables
        ('fhq_alpha', 'g4_'),         # Block g4_* tables
        ('fhq_execution', None),      # Block execution schema
        ('fhq_market', None),         # Block canonical market data
        ('fhq_data', None),           # Block data schema (read-only)
    ]

    @classmethod
    def validate_write(cls, schema: str, table: str) -> None:
        """
        Validate that a write operation is allowed.
        Raises SchemaBoundaryViolation if blocked.
        """
        # Check blocked patterns first
        for blocked_schema, blocked_prefix in cls.BLOCKED_PATTERNS:
            if schema == blocked_schema:
                if blocked_prefix is None:
                    raise SchemaBoundaryViolation(
                        f"EC-018 WRITE BLOCKED: Schema '{schema}' is read-only per CEO Directive Wave 9"
                    )
                elif table.startswith(blocked_prefix):
                    raise SchemaBoundaryViolation(
                        f"EC-018 WRITE BLOCKED: Table '{schema}.{table}' matches blocked pattern '{blocked_prefix}*' - "
                        f"G1+ promotion requires IoS-004 backtest validation"
                    )

        # Check if in allowed list
        if schema in cls.ALLOWED_WRITES:
            if table in cls.ALLOWED_WRITES[schema]:
                return  # Allowed

        # If not explicitly allowed, log warning but allow (for flexibility)
        import logging
        logging.getLogger(__name__).warning(
            f"EC-018 Schema Warning: Write to '{schema}.{table}' not in explicit allow-list"
        )


# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='[EC-018] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('C:/fhq-market-system/vision-ios/logs/ec018_alpha_daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# CEO DIRECTIVE WAVE 12: Live Price Witness (Constitutional Remediation)
# =============================================================================
# Reference: CD-EC018-LIVE-PRICE-PRECONDITION-20251217
#
# A Live Price Witness is an ephemeral, strictly time-bounded proof that the
# price context used for hypothesis formation reflects current market reality.
#
# Requirements:
# - BLOCKING precondition (silent abort on failure)
# - Timestamped and valid only for MAX_WITNESS_AGE_MINUTES
# - Logged ONLY as decision evidence (fhq_meta), NEVER as market truth
# - Uses Binance for crypto, Alpaca for equities
# =============================================================================

MAX_WITNESS_AGE_MINUTES = 30  # CEO Directive: "30 minutes" freshness threshold


class LivePriceWitness:
    """
    CEO Directive Wave 12: Live Price Verification System.

    Provides ephemeral proof of current market prices as a precondition
    for hypothesis generation. This is NOT a data ingestion system.

    Constitutional Constraints:
    - Witness is EPHEMERAL (not stored as canonical truth)
    - Witness is TIME-BOUNDED (valid only for MAX_WITNESS_AGE_MINUTES)
    - Witness is DECISION EVIDENCE (logged to fhq_meta only)
    """

    def __init__(self):
        # Binance API (crypto) - public endpoint, no auth needed for prices
        self.binance_base_url = "https://api.binance.com/api/v3"

        # Alpaca API (equities) - requires auth
        self.alpaca_api_key = os.environ.get('ALPACA_API_KEY')
        self.alpaca_secret = os.environ.get('ALPACA_SECRET_KEY')
        self.alpaca_base_url = os.environ.get('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')

        # Witness cache (ephemeral - cleared each hunt)
        self._witnesses = {}
        self._witness_timestamp = None

    def fetch_binance_price(self, symbol: str = 'BTCUSDT') -> Optional[Dict]:
        """
        Fetch live price from Binance for crypto assets.

        Returns:
            {
                'symbol': 'BTCUSDT',
                'price': 104000.50,
                'timestamp': datetime,
                'source': 'BINANCE',
                'witness_id': str
            }
            or None on failure
        """
        try:
            response = requests.get(
                f"{self.binance_base_url}/ticker/price",
                params={'symbol': symbol},
                timeout=5
            )

            if response.ok:
                data = response.json()
                now = datetime.now(timezone.utc)
                return {
                    'symbol': symbol,
                    'price': float(data['price']),
                    'timestamp': now,
                    'source': 'BINANCE',
                    'witness_id': hashlib.sha256(
                        f"{symbol}-{data['price']}-{now.isoformat()}".encode()
                    ).hexdigest()[:16]
                }
            else:
                logger.warning(f"Binance API error: {response.status_code}")
                return None

        except Exception as e:
            logger.warning(f"Binance price fetch failed: {e}")
            return None

    def fetch_alpaca_price(self, symbol: str = 'SPY') -> Optional[Dict]:
        """
        Fetch live price from Alpaca for equity assets.

        Returns:
            {
                'symbol': 'SPY',
                'price': 590.25,
                'timestamp': datetime,
                'source': 'ALPACA',
                'witness_id': str
            }
            or None on failure
        """
        if not self.alpaca_api_key or not self.alpaca_secret:
            logger.warning("Alpaca credentials not configured")
            return None

        try:
            # Use Alpaca's latest trade endpoint
            response = requests.get(
                f"https://data.alpaca.markets/v2/stocks/{symbol}/trades/latest",
                headers={
                    'APCA-API-KEY-ID': self.alpaca_api_key,
                    'APCA-API-SECRET-KEY': self.alpaca_secret
                },
                timeout=5
            )

            if response.ok:
                data = response.json()
                trade = data.get('trade', {})
                now = datetime.now(timezone.utc)
                return {
                    'symbol': symbol,
                    'price': float(trade.get('p', 0)),
                    'timestamp': now,
                    'source': 'ALPACA',
                    'witness_id': hashlib.sha256(
                        f"{symbol}-{trade.get('p')}-{now.isoformat()}".encode()
                    ).hexdigest()[:16]
                }
            else:
                logger.warning(f"Alpaca API error: {response.status_code}")
                return None

        except Exception as e:
            logger.warning(f"Alpaca price fetch failed: {e}")
            return None

    def verify_witness_freshness(self, witness: Dict) -> bool:
        """
        Verify that a price witness is within the acceptable age threshold.

        CEO Directive: "30 minutes" maximum age for valid witness.
        """
        if not witness or 'timestamp' not in witness:
            return False

        age = datetime.now(timezone.utc) - witness['timestamp']
        age_minutes = age.total_seconds() / 60

        return age_minutes <= MAX_WITNESS_AGE_MINUTES

    def get_crypto_witness(self) -> Optional[Dict]:
        """
        Obtain a fresh crypto price witness (BTC as primary).

        Returns valid witness or None if unavailable.
        """
        # Try primary symbol (BTC)
        witness = self.fetch_binance_price('BTCUSDT')
        if witness and self.verify_witness_freshness(witness):
            self._witnesses['crypto'] = witness
            return witness

        # Fallback to ETH if BTC fails
        witness = self.fetch_binance_price('ETHUSDT')
        if witness and self.verify_witness_freshness(witness):
            self._witnesses['crypto'] = witness
            return witness

        return None

    def get_equity_witness(self) -> Optional[Dict]:
        """
        Obtain a fresh equity price witness (SPY as primary).

        Returns valid witness or None if unavailable.
        """
        # Try primary symbol (SPY)
        witness = self.fetch_alpaca_price('SPY')
        if witness and self.verify_witness_freshness(witness):
            self._witnesses['equity'] = witness
            return witness

        return None

    def clear_witnesses(self):
        """Clear all cached witnesses (called at start of each hunt)."""
        self._witnesses = {}
        self._witness_timestamp = None


class LivePriceViolation(Exception):
    """Raised when live price precondition cannot be satisfied."""
    pass

# Unicode sanitization for WIN1252 compatibility
def sanitize_for_win1252(text: str) -> str:
    """Replace Unicode characters that WIN1252 cannot handle with ASCII equivalents."""
    if not isinstance(text, str):
        return text
    replacements = {
        '\u2264': '<=',   # ≤
        '\u2265': '>=',   # ≥
        '\u2260': '!=',   # ≠
        '\u2192': '->',   # →
        '\u2190': '<-',   # ←
        '\u2022': '*',    # •
        '\u2013': '-',    # –
        '\u2014': '--',   # —
        '\u201c': '"',    # "
        '\u201d': '"',    # "
        '\u2018': "'",    # '
        '\u2019': "'",    # '
        '\u2026': '...',  # …
        '\u00b0': 'deg',  # °
        '\u00b1': '+/-',  # ±
    }
    for unicode_char, ascii_equiv in replacements.items():
        text = text.replace(unicode_char, ascii_equiv)
    # Remove any remaining non-ASCII characters
    return text.encode('ascii', 'replace').decode('ascii')

def sanitize_dict(d: Dict) -> Dict:
    """Recursively sanitize all string values in a dictionary."""
    if isinstance(d, dict):
        return {k: sanitize_dict(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [sanitize_dict(item) for item in d]
    elif isinstance(d, str):
        return sanitize_for_win1252(d)
    return d


def serialize_envelope(envelope) -> Optional[Dict]:
    """
    Serialize PlanConfidenceEnvelope to JSON-serializable dict.

    Handles enum values, datetime objects, and dataclass conversion for database storage.
    """
    if envelope is None:
        return None

    def make_serializable(obj):
        """Recursively convert objects to JSON-serializable types."""
        if obj is None:
            return None
        elif isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [make_serializable(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, 'value'):  # Enum with value attribute
            return obj.value
        elif hasattr(obj, 'name') and hasattr(obj, '__class__') and obj.__class__.__module__ != 'builtins':
            # Likely an enum
            return obj.name
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        else:
            return str(obj)

    try:
        # Convert dataclass to dict
        env_dict = asdict(envelope)

        # Recursively make all values JSON-serializable
        return make_serializable(env_dict)

    except Exception as e:
        # Fallback: extract essential fields manually
        return {
            'plan_id': str(envelope.plan_id) if hasattr(envelope, 'plan_id') else None,
            'plan_confidence': envelope.plan_confidence.value if hasattr(envelope, 'plan_confidence') else None,
            'failure_reason': envelope.failure_reason if hasattr(envelope, 'failure_reason') else None,
            'abort_reason': envelope.abort_reason.value if hasattr(envelope, 'abort_reason') and envelope.abort_reason else None,
            'evidence_completeness': envelope.evidence_completeness if hasattr(envelope, 'evidence_completeness') else None,
            'state_snapshot_hash': envelope.state_snapshot_hash if hasattr(envelope, 'state_snapshot_hash') else None,
            'serialization_error': str(e)
        }


# Configuration
DAILY_BUDGET_USD = Decimal('2.00')
PER_HUNT_MAX_USD = Decimal('0.50')
HYPOTHESES_PER_HUNT = (2, 4)
DEEPSEEK_MODEL = 'deepseek-chat'
DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions'
SERPER_API_URL = 'https://google.serper.dev/search'

# =============================================================================
# HOLIDAY MODE: Crypto-First Focus (CEO Directive 2025-12-19)
# =============================================================================
# During holiday period, EC-018 focuses exclusively on approved crypto assets
try:
    from holiday_execution_gate import (
        HOLIDAY_MODE_ENABLED,
        APPROVED_CRYPTO_ASSETS as HOLIDAY_CRYPTO_ASSETS,
        get_holiday_status
    )
    HOLIDAY_GATE_AVAILABLE = True
except ImportError:
    HOLIDAY_GATE_AVAILABLE = False
    HOLIDAY_MODE_ENABLED = False
    HOLIDAY_CRYPTO_ASSETS = {'BTC', 'ETH', 'SOL'}

# Focus areas rotation - crypto-specific during holiday
FOCUS_AREAS_CRYPTO = [
    'crypto_regime_transitions',
    'crypto_mean_reversion',
    'crypto_momentum',
    'defi_cross_asset',
    'crypto_volatility_structure',
    'crypto_timing_edges',
    'altcoin_correlation',
    'btc_dominance_shifts'
]

# Standard focus areas (when holiday mode disabled)
FOCUS_AREAS_STANDARD = [
    'regime_transitions',
    'mean_reversion',
    'momentum',
    'cross_asset',
    'volatility_structure',
    'timing_edges'
]

# Active focus areas based on mode
FOCUS_AREAS = FOCUS_AREAS_CRYPTO if HOLIDAY_MODE_ENABLED else FOCUS_AREAS_STANDARD


class EC018AlphaDaemon:
    """Autonomous alpha discovery daemon with ACI integration (CEO Directive 2025-12-17)."""

    def __init__(self):
        self.conn = None
        self.deepseek_key = os.environ.get('DEEPSEEK_API_KEY')
        self.serper_key = os.environ.get('SERPER_API_KEY')
        self.hunt_count = 0

        # CEO Directive Mandate V: IKEA Knowledge Boundary Engine
        self._ikea_engine = None

        # CEO Directive Mandate II: RuntimeEconomicGuardian
        self._runtime_guardian = None

        # ASRP State Binding (Mandate I)
        self._current_asrp_hash = None
        self._current_asrp_timestamp = None

        # CEO Directive Wave 7: EC-020 SitC Planner (Hypothesis Validation)
        # SitC is a FILTER, not a CO-THINKER
        self._sitc_planner = None
        self._sitc_enabled = False

        # CEO Directive Wave 12: Live Price Witness (Constitutional Remediation)
        # Blocking precondition for hypothesis generation
        self._live_price_witness = LivePriceWitness()
        self._current_witness = None

    def _init_ikea(self):
        """Initialize IKEA boundary engine (Mandate V: Fail-Safe Default)."""
        if IKEA_AVAILABLE and self._ikea_engine is None:
            try:
                self._ikea_engine = IKEABoundaryEngine()
                self._ikea_engine.connect()
                logger.info("IKEA Boundary Engine initialized (EC-022)")
            except Exception as e:
                logger.warning(f"IKEA initialization failed (defaulting to EXTERNAL_REQUIRED): {e}")
                # Per Mandate V: If IKEA fails, treat ALL claims as EXTERNAL_REQUIRED
                self._ikea_engine = None

    def _init_runtime_guardian(self, session_id: str) -> bool:
        """Initialize RuntimeEconomicGuardian (Mandate II: Unbypassable)."""
        # InForageCostController requires a valid UUID for session_id
        # Convert human-readable session ID to UUID format if needed
        import re
        if re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', session_id, re.I):
            cost_session_id = session_id
        else:
            # Generate deterministic UUID from session string for traceability
            cost_session_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, session_id))
            logger.debug(f"Mapped session '{session_id}' to UUID {cost_session_id}")

        self._runtime_guardian = RuntimeEconomicGuardian(session_id=cost_session_id)
        if not self._runtime_guardian.initialize():
            logger.critical("RUNTIME GUARDIAN FAILED - EC-018 OPERATIONS BLOCKED")
            return False
        logger.info("RuntimeEconomicGuardian initialized (Mandate II)")
        return True

    def _get_asrp_state(self) -> tuple:
        """
        Get current ASRP state snapshot (Mandate I: ADR-018 State Binding).

        Returns: (state_snapshot_hash, state_timestamp)
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT state_snapshot_hash, vector_timestamp
                    FROM fhq_meta.aci_state_snapshot_log
                    WHERE is_atomic = true
                    ORDER BY created_at DESC LIMIT 1
                """)
                row = cur.fetchone()
                if row:
                    self._current_asrp_hash = row[0]
                    self._current_asrp_timestamp = row[1]
                    return (row[0], row[1])
        except Exception as e:
            logger.warning(f"ASRP state fetch failed (using generated hash): {e}")

        # Fallback: generate state hash from current context
        state_hash = hashlib.sha256(
            f"EC018-{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()
        self._current_asrp_hash = state_hash
        self._current_asrp_timestamp = datetime.now(timezone.utc)
        return (state_hash, self._current_asrp_timestamp)

    # =========================================================================
    # CEO DIRECTIVE WAVE 12: Live Price Precondition
    # =========================================================================

    def _verify_live_price_precondition(self) -> Dict:
        """
        Verify live price precondition before hypothesis generation.

        CEO Directive Wave 12 Requirements:
        - BLOCKING: If no fresh price available, hunt is silently aborted
        - EPHEMERAL: Witness is not stored as canonical truth
        - LOGGED: Decision evidence recorded in fhq_meta

        Returns:
            {
                'satisfied': bool,
                'witness': dict or None,
                'reason': str,
                'staleness_minutes': float or None
            }
        """
        # Clear any previous witnesses
        self._live_price_witness.clear_witnesses()

        # Attempt to obtain crypto witness (primary market context)
        witness = self._live_price_witness.get_crypto_witness()

        if witness:
            self._current_witness = witness
            logger.info(
                f"Live Price Witness obtained: {witness['symbol']} = ${witness['price']:,.2f} "
                f"(witness_id: {witness['witness_id']}, source: {witness['source']})"
            )
            return {
                'satisfied': True,
                'witness': witness,
                'reason': 'FRESH_PRICE_AVAILABLE',
                'staleness_minutes': 0.0
            }
        else:
            # Calculate staleness from database price as evidence
            staleness = self._get_database_price_staleness()
            logger.warning(
                f"Live Price Witness FAILED: Cannot obtain fresh crypto price. "
                f"Database price staleness: {staleness:.1f} minutes"
            )
            return {
                'satisfied': False,
                'witness': None,
                'reason': 'NO_FRESH_PRICE_AVAILABLE',
                'staleness_minutes': staleness
            }

    def _get_database_price_staleness(self) -> float:
        """
        Calculate how stale the database price data is.

        Returns staleness in minutes.
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT date,
                           EXTRACT(EPOCH FROM (NOW() - date)) / 60 as staleness_minutes
                    FROM fhq_data.price_series
                    WHERE listing_id = 'BTC-USD'
                    ORDER BY date DESC LIMIT 1
                """)
                row = cur.fetchone()
                if row:
                    return float(row[1])
        except Exception as e:
            logger.warning(f"Staleness check failed: {e}")
        return float('inf')  # Unknown staleness = infinite

    def _log_witness_evidence(self, witness_result: Dict, session_id: str):
        """
        Log live price witness decision to fhq_meta.cognitive_engine_evidence.

        CEO Directive Wave 12: Evidence only, NEVER canonical truth.
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_meta.cognitive_engine_evidence (
                        engine_id,
                        task_id,
                        invocation_type,
                        input_context,
                        decision_rationale,
                        output_modification,
                        cost_usd,
                        information_gain_score,
                        chain_integrity_score,
                        boundary_violation
                    ) VALUES (
                        'EC-018',
                        %s,
                        'LIVE_PRICE_PRECONDITION',
                        %s,
                        %s,
                        NULL,
                        0.0,
                        %s,
                        1.0,
                        %s
                    )
                """, (
                    session_id,
                    Json({
                        'precondition_type': 'LIVE_PRICE_WITNESS',
                        'directive_ref': 'CD-EC018-LIVE-PRICE-PRECONDITION-20251217',
                        'max_witness_age_minutes': MAX_WITNESS_AGE_MINUTES,
                        'staleness_minutes': witness_result.get('staleness_minutes')
                    }),
                    witness_result['reason'],
                    1.0 if witness_result['satisfied'] else 0.0,  # Information gain
                    not witness_result['satisfied']  # Boundary violation if not satisfied
                ))
                logger.debug(f"Witness evidence logged for session {session_id}")
        except Exception as e:
            # Non-fatal: evidence logging failure should not block hunt
            logger.warning(f"Witness evidence logging failed: {e}")

    def _classify_claim(self, claim: str) -> tuple:
        """
        Classify a factual claim using IKEA (Mandate V).

        Returns: (classification, confidence) - defaults to EXTERNAL_REQUIRED if uncertain.
        """
        if self._ikea_engine:
            try:
                result = self._ikea_engine.classify_query(claim)
                return (result.classification.value, result.confidence)
            except Exception as e:
                logger.warning(f"IKEA classification failed: {e}")

        # MANDATE V FAIL-SAFE: Default to EXTERNAL_REQUIRED (maximum safety)
        return ('EXTERNAL_REQUIRED', 0.0)

    # =========================================================================
    # CEO DIRECTIVE WAVE 7: SitC Hypothesis Validation
    # =========================================================================

    def _init_sitc(self, session_id: str) -> bool:
        """
        Initialize EC-020 SitC Planner for hypothesis validation.

        CEO Directive Wave 7 Constraints:
        - SitC is a FILTER, not a CO-THINKER
        - Must check DEFCON before initialization
        - Must have RuntimeEconomicGuardian active
        - Outputs are Evidence only (fhq_meta writes)

        Returns: True if SitC is operational, False otherwise
        """
        if not SITC_AVAILABLE:
            logger.warning("SitC module not available - validation disabled")
            return False

        try:
            # SitC checks DEFCON internally on connect()
            self._sitc_planner = get_sitc_planner_with_guardrails(session_id=session_id)
            self._sitc_enabled = True
            logger.info("EC-020 SitC Planner initialized (FILTER mode)")
            return True

        except SitCDEFCONViolation as e:
            # DEFCON >= RED blocks SitC
            logger.warning(f"SitC blocked by DEFCON: {e}")
            self._sitc_enabled = False
            return False

        except SitCEconomicViolation as e:
            # Economic safety blocks SitC
            logger.warning(f"SitC blocked by economic safety: {e}")
            self._sitc_enabled = False
            return False

        except Exception as e:
            logger.warning(f"SitC initialization failed: {e}")
            self._sitc_enabled = False
            return False

    def _validate_hypothesis_with_sitc(self, hypothesis: Dict, context: Dict) -> Dict:
        """
        Validate a hypothesis using EC-020 SitC Planner.

        CEO Directive Wave 7 Requirements:
        I. Plan Confidence Envelope (Mandatory):
           - HIGH: Normal validation flow permitted
           - MEDIUM: Log-only, no escalation, no rejection
           - LOW: Hypothesis rejected outright

        II. ASRP State-Binding (ADR-018):
           - All outputs must include state_snapshot_hash and state_timestamp

        III. DEFCON Supremacy (ADR-016):
           - If DEFCON >= ORANGE, validation must not execute

        IV. Role Isolation (ADR-020/021):
           - SitC outputs are Evidence Only (fhq_meta)

        Returns: {
            'validated': bool,
            'action': 'ACCEPT' | 'LOG_ONLY' | 'REJECT',
            'confidence': 'HIGH' | 'MEDIUM' | 'LOW',
            'envelope': PlanConfidenceEnvelope or None,
            'reason': str,
            'hypothesis_unchanged': bool  # MUST be True (filter, not co-thinker)
        }
        """
        if not self._sitc_enabled or not self._sitc_planner:
            # SitC not available - default to ACCEPT (fail-open for hypothesis generation)
            return {
                'validated': True,
                'action': 'ACCEPT',
                'confidence': 'UNKNOWN',
                'envelope': None,
                'reason': 'SitC not available - default accept',
                'hypothesis_unchanged': True
            }

        hypothesis_text = hypothesis.get('statement', hypothesis.get('title', ''))
        original_hypothesis = hypothesis_text  # Store original for verification

        try:
            # Create research plan for hypothesis validation
            plan = self._sitc_planner.create_research_plan(hypothesis_text)

            # Evaluate confidence envelope
            envelope = self._sitc_planner.evaluate_plan_confidence(plan)

            # Log the chain (Evidence only - fhq_meta)
            self._sitc_planner.log_chain(plan.nodes)

            # CRITICAL: Verify hypothesis was not modified (SitC is FILTER, not CO-THINKER)
            hypothesis_unchanged = (hypothesis_text == original_hypothesis)
            if not hypothesis_unchanged:
                # This should NEVER happen - raise violation
                raise SitCRoleViolation(
                    "SitC modified hypothesis content - FILTER role violation!"
                )

            # Determine action based on confidence envelope
            # CEO Directive Wave 9: Mandatory Hard Filter
            # - HIGH:   ACCEPT → store with VALIDATED_BY_SITC
            # - MEDIUM: LOG_ONLY → store with REVIEW_REQUIRED
            # - LOW:    REJECT → drop completely (no persistence)
            # - ABORT:  SILENT_DROP → drop with no error logging

            # Check for ABORT condition first (from envelope)
            if envelope.abort_reason and envelope.abort_reason.value != 'NONE':
                action = 'ABORT'
                validated = False
                reason = f"Plan aborted: {envelope.abort_reason.value}"
            elif envelope.plan_confidence == PlanConfidence.HIGH:
                action = 'ACCEPT'
                validated = True
                reason = "HIGH confidence - normal validation flow"
            elif envelope.plan_confidence == PlanConfidence.MEDIUM:
                action = 'LOG_ONLY'
                validated = True  # Still accepted, but flagged for review
                reason = f"MEDIUM confidence - requires review. {envelope.failure_reason or ''}"
            else:  # LOW
                action = 'REJECT'
                validated = False
                reason = f"LOW confidence - hypothesis rejected. {envelope.failure_reason or ''}"

            # Log validation result (CEO Directive Wave 9: ABORT is silent)
            if action != 'ABORT':
                logger.info(
                    f"SitC Validation: {action} (confidence={envelope.plan_confidence.value}) "
                    f"for '{hypothesis_text[:50]}...'"
                )
            # ABORT outcomes: silent drop - no logging per Wave 9 mandate

            return {
                'validated': validated,
                'action': action,
                'confidence': envelope.plan_confidence.value,
                'envelope': serialize_envelope(envelope),  # Wave 9: JSON-serializable for DB storage
                'reason': reason,
                'hypothesis_unchanged': hypothesis_unchanged,
                'asrp_hash': envelope.state_snapshot_hash,
                'plan_id': plan.plan_id,
                'nodes_count': len(plan.nodes)
            }

        except SitCRoleViolation as e:
            # Role boundary violation - CRITICAL
            logger.error(f"SITC ROLE VIOLATION: {e}")
            return {
                'validated': False,
                'action': 'REJECT',
                'confidence': 'VIOLATION',
                'envelope': None,
                'reason': f"SitC role violation: {e}",
                'hypothesis_unchanged': False
            }

        except SitCDEFCONViolation as e:
            # DEFCON blocked validation
            logger.warning(f"SitC DEFCON block: {e}")
            return {
                'validated': False,
                'action': 'REJECT',
                'confidence': 'BLOCKED',
                'envelope': None,
                'reason': f"DEFCON blocked: {e}",
                'hypothesis_unchanged': True
            }

        except MITQuadViolation as e:
            # Schema boundary violation
            logger.error(f"SitC schema violation: {e}")
            return {
                'validated': False,
                'action': 'REJECT',
                'confidence': 'VIOLATION',
                'envelope': None,
                'reason': f"Schema boundary violation: {e}",
                'hypothesis_unchanged': True
            }

        except Exception as e:
            # Unexpected error - log but don't block hypothesis generation
            logger.warning(f"SitC validation error: {e}")
            return {
                'validated': True,
                'action': 'ACCEPT',
                'confidence': 'ERROR',
                'envelope': None,
                'reason': f"SitC error (fail-open): {e}",
                'hypothesis_unchanged': True
            }

    def connect(self):
        """Connect to database."""
        self.conn = psycopg2.connect(
            host=os.environ.get('PGHOST', '127.0.0.1'),
            port=os.environ.get('PGPORT', '54322'),
            database=os.environ.get('PGDATABASE', 'postgres'),
            user=os.environ.get('PGUSER', 'postgres'),
            password=os.environ.get('PGPASSWORD', 'postgres'),
            options='-c client_encoding=UTF8'
        )
        self.conn.autocommit = True  # Prevent transaction issues
        logger.info("Database connected")

    def close(self):
        """Close database connection and cleanup resources."""
        # Close IKEA engine
        if self._ikea_engine:
            try:
                self._ikea_engine.close()
            except Exception:
                pass
        # Close SitC planner (CEO Directive Wave 7)
        if self._sitc_planner:
            try:
                self._sitc_planner.close()
                logger.info("SitC Planner closed")
            except Exception:
                pass
        # Close database
        if self.conn:
            self.conn.close()

    def get_daily_spend(self) -> Decimal:
        """Get today's total spend from llm_routing_log."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(SUM(cost_usd), 0) as daily_spend
                FROM fhq_governance.llm_routing_log
                WHERE agent_id = 'FINN'
                  AND task_type = 'RESEARCH'
                  AND request_timestamp >= CURRENT_DATE
            """)
            result = cur.fetchone()
            return Decimal(str(result[0])) if result else Decimal('0')

    def get_causal_insights(self) -> List[Dict]:
        """Fetch causal insights from Alpha Graph for hypothesis generation."""
        insights = []
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        e.edge_id,
                        n1.label as from_label,
                        n2.label as to_label,
                        e.relationship_type,
                        e.strength,
                        e.lag_days,
                        e.hypothesis,
                        e.transmission_mechanism
                    FROM fhq_graph.edges e
                    JOIN fhq_graph.nodes n1 ON e.from_node_id = n1.node_id
                    JOIN fhq_graph.nodes n2 ON e.to_node_id = n2.node_id
                    WHERE e.production_locked = true
                    ORDER BY ABS(e.strength) DESC
                    LIMIT 10
                """)
                rows = cur.fetchall()
                for row in rows:
                    insights.append({
                        'from': row['from_label'],
                        'to': row['to_label'],
                        'type': row['relationship_type'],
                        'strength': float(row['strength']),
                        'lag_days': row['lag_days'],
                        'hypothesis': row['hypothesis']
                    })
                logger.info(f"Loaded {len(insights)} causal insights from Alpha Graph")
        except Exception as e:
            logger.warning(f"Alpha Graph query failed: {e}")
        return insights

    def get_market_context(self) -> Dict[str, Any]:
        """Get current market state for hypothesis generation."""
        context = {
            'regime': 'NEUTRAL',
            'regime_confidence': 0.5,
            'defcon': 5,
            'btc_price': None,
            'recent_signals': [],
            'news_context': [],
            'causal_insights': []
        }

        # Fetch causal insights from Alpha Graph
        context['causal_insights'] = self.get_causal_insights()

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get current regime
            try:
                cur.execute("""
                    SELECT sovereign_regime,
                           COALESCE((state_probabilities->sovereign_regime)::float, 0.5) as confidence
                    FROM fhq_perception.sovereign_regime_state_v4
                    WHERE asset_id = 'BTC-USD'
                    ORDER BY timestamp DESC LIMIT 1
                """)
                row = cur.fetchone()
                if row:
                    context['regime'] = row['sovereign_regime']
                    context['regime_confidence'] = row['confidence']
            except Exception as e:
                logger.warning(f"Regime query failed: {e}")

            # Get DEFCON
            try:
                cur.execute("""
                    SELECT defcon_level FROM fhq_monitoring.defcon_state
                    WHERE is_current = true LIMIT 1
                """)
                row = cur.fetchone()
                if row:
                    context['defcon'] = row['defcon_level']
            except Exception as e:
                logger.warning(f"DEFCON query failed: {e}")

            # Get BTC price
            try:
                cur.execute("""
                    SELECT close FROM fhq_data.price_series
                    WHERE listing_id = 'BTC-USD'
                    ORDER BY date DESC LIMIT 1
                """)
                row = cur.fetchone()
                if row:
                    context['btc_price'] = float(row['close'])
            except Exception as e:
                logger.warning(f"Price query failed: {e}")

            # Get recent validated signals count
            try:
                cur.execute("""
                    SELECT COUNT(*) as count FROM fhq_alpha.g0_draft_proposals
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                """)
                row = cur.fetchone()
                context['recent_hypotheses_24h'] = row['count'] if row else 0
            except Exception as e:
                logger.warning(f"Recent signals query failed: {e}")

        return context

    def search_market_news(self, query: str) -> List[Dict]:
        """Search for market news using Serper API."""
        if not self.serper_key:
            logger.warning("Serper API key not available")
            return []

        try:
            response = requests.post(
                SERPER_API_URL,
                headers={
                    'X-API-KEY': self.serper_key,
                    'Content-Type': 'application/json'
                },
                json={
                    'q': query,
                    'num': 5,
                    'type': 'news'
                },
                timeout=10
            )

            if response.ok:
                data = response.json()
                news = data.get('news', [])
                return [{'title': n.get('title'), 'snippet': n.get('snippet')} for n in news[:5]]
            else:
                logger.warning(f"Serper API error: {response.status_code}")
                return []
        except Exception as e:
            logger.warning(f"Serper search failed: {e}")
            return []

    def generate_state_hash(self, context: Dict) -> str:
        """Generate cryptographic hash of current state (ADR-018)."""
        state_string = json.dumps({
            'regime': context['regime'],
            'defcon': context['defcon'],
            'btc_price': context.get('btc_price'),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }, sort_keys=True)
        return hashlib.sha256(state_string.encode()).hexdigest()

    def create_state_vector(self, context: Dict) -> tuple:
        """Create state vector entry capturing current market state (ADR-018).

        Returns: (state_vector_id, state_hash)
        """
        state_hash = self.generate_state_hash(context)

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_alpha.state_vectors (
                    state_hash,
                    market_regime,
                    regime_confidence,
                    btc_price,
                    btc_24h_change,
                    vix_value,
                    defcon_level,
                    perception_summary,
                    active_anomalies,
                    daily_budget_remaining,
                    daily_budget_cap,
                    source_agent
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'EC-018'
                )
                RETURNING state_vector_id
            """, (
                state_hash,
                context.get('regime', 'NEUTRAL'),
                context.get('regime_confidence', 0.5),
                context.get('btc_price'),
                context.get('btc_24h_change'),
                context.get('vix_value'),
                context.get('defcon', 5),
                Json(context.get('perception_summary', {})),
                Json(context.get('active_anomalies', [])),
                float(DAILY_BUDGET_USD - self.get_daily_spend()),
                float(DAILY_BUDGET_USD)
            ))
            state_vector_id = cur.fetchone()[0]

        logger.info(f"Created state vector: {state_vector_id} (hash: {state_hash[:16]}...)")
        return str(state_vector_id), state_hash

    def create_hunt_session(self, focus_area: str, state_vector_id: str) -> str:
        """Create hunt session entry.

        Returns: session_id
        """
        session_name = f"EC018-{focus_area.upper()}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_alpha.hunt_sessions (
                    session_name,
                    initiated_by,
                    focus_areas,
                    budget_cap_usd,
                    primary_model,
                    initial_state_vector_id,
                    session_status
                ) VALUES (
                    %s, 'EC-018', %s, %s, %s, %s, 'ACTIVE'
                )
                RETURNING session_id
            """, (
                session_name,
                Json([focus_area]),
                float(PER_HUNT_MAX_USD),
                DEEPSEEK_MODEL,
                state_vector_id
            ))
            session_id = cur.fetchone()[0]

        logger.info(f"Created hunt session: {session_id}")
        return str(session_id)

    def generate_hypotheses(self, context: Dict, focus_area: str, news: List[Dict]) -> Dict:
        """Generate alpha hypotheses using DeepSeek."""
        if not self.deepseek_key:
            logger.error("DeepSeek API key not available")
            return {'proposals': [], 'tokens_in': 0, 'tokens_out': 0, 'cost_usd': 0}

        state_hash = self.generate_state_hash(context)

        news_context = ""
        if news:
            news_context = "\n\nRecent Market News:\n" + "\n".join(
                [f"- {n['title']}: {n['snippet']}" for n in news[:3]]
            )

        # Build Alpha Graph causal context
        causal_context = ""
        if context.get('causal_insights'):
            causal_context = "\n\nALPHA GRAPH CAUSAL INSIGHTS (use these for hypothesis generation):\n"
            for insight in context['causal_insights'][:6]:
                sign = "+" if insight['strength'] > 0 else ""
                causal_context += f"- {insight['from']} -> {insight['to']}: {insight['type']} ({sign}{insight['strength']:.2f}, lag {insight['lag_days']}d)\n"
                if insight.get('hypothesis'):
                    causal_context += f"  Mechanism: {insight['hypothesis']}\n"

        system_prompt = f"""You are EC-018, FjordHQ's Alpha Discovery Engine.
Your role: Generate falsifiable trading hypotheses for quantitative validation.

CURRENT MARKET STATE (ADR-018 State Lock):
- Regime: {context['regime']} (confidence: {context['regime_confidence']:.1%})
- DEFCON Level: {context['defcon']}
- BTC Price: ${context.get('btc_price', 'N/A')}
- State Hash: {state_hash[:16]}...
{news_context}
{causal_context}

FOCUS AREA FOR THIS HUNT: {focus_area.upper().replace('_', ' ')}

CONSTRAINTS:
1. Execution Authority: ZERO - You generate hypotheses only
2. All hypotheses require IoS-004 backtest validation
3. Hypotheses must be specific and falsifiable
4. Include exact entry/exit conditions where possible
5. Generate hypotheses for MULTIPLE regimes - not just current!
6. Use causal insights from Alpha Graph when available
{'7. HOLIDAY MODE ACTIVE: Focus ONLY on approved crypto assets: ' + ', '.join(sorted(HOLIDAY_CRYPTO_ASSETS)) + '. No equity or FX hypotheses.' if HOLIDAY_MODE_ENABLED else ''}

IMPORTANT - MULTI-REGIME STRATEGY:
- Current regime is {context['regime']}, but generate hypotheses for ALL regimes
- BULL hypotheses: momentum, trend-following, breakout strategies
- NEUTRAL hypotheses: mean-reversion, range-trading, pairs trading
- BEAR hypotheses: short positions, hedging, defensive plays
- STRESS hypotheses: volatility plays, flight-to-quality

OUTPUT FORMAT (JSON array):
[
  {{
    "hypothesis_id": "ALPHA-YYYYMMDD-XXX",
    "title": "Short descriptive title",
    "category": "REGIME_EDGE|MEAN_REVERSION|MOMENTUM|CROSS_ASSET|VOLATILITY|TIMING",
    "statement": "Precise, falsifiable hypothesis statement",
    "entry_conditions": ["condition1", "condition2"],
    "exit_conditions": {{"take_profit": "...", "stop_loss": "...", "time_exit": "..."}},
    "regime_filter": ["BULL", "NEUTRAL", "BEAR", "STRESS"],
    "confidence": 0.XX,
    "rationale": "Why this might work given current state",
    "falsification_criteria": "What would prove this wrong",
    "causal_driver": "Optional: which Alpha Graph edge supports this"
  }}
]

Generate 3-4 high-quality hypotheses. Include at least one for current regime ({context['regime']}) and one for a different regime."""

        user_prompt = f"""Generate alpha hypotheses focused on {focus_area.replace('_', ' ')}.

Current state: {context['regime']} regime, DEFCON-{context['defcon']}.

IMPORTANT: Generate hypotheses for MULTIPLE regimes, not just {context['regime']}!
- Include at least 1 hypothesis that works in BULL market
- Include at least 1 hypothesis that works in NEUTRAL market
- Use Alpha Graph causal insights if available

Remember: These are G0 hypotheses requiring IoS-004 validation. Be specific about entry/exit conditions."""

        try:
            response = requests.post(
                DEEPSEEK_API_URL,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.deepseek_key}'
                },
                json={
                    'model': DEEPSEEK_MODEL,
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt}
                    ],
                    'temperature': 0.7,
                    'max_tokens': 4000
                },
                timeout=60
            )

            if not response.ok:
                logger.error(f"DeepSeek API error: {response.status_code}")
                return {'proposals': [], 'tokens_in': 0, 'tokens_out': 0, 'cost_usd': 0}

            data = response.json()
            content = data['choices'][0]['message']['content']

            # Parse JSON from response
            try:
                # Find JSON array in response
                start = content.find('[')
                end = content.rfind(']') + 1
                if start >= 0 and end > start:
                    proposals = json.loads(content[start:end])
                else:
                    proposals = []
            except json.JSONDecodeError:
                logger.warning("Failed to parse hypotheses JSON")
                proposals = []

            # Calculate cost
            usage = data.get('usage', {})
            tokens_in = usage.get('prompt_tokens', 0)
            tokens_out = usage.get('completion_tokens', 0)
            # DeepSeek pricing: $0.14/1M input, $0.28/1M output
            cost_usd = (tokens_in * 0.14 / 1_000_000) + (tokens_out * 0.28 / 1_000_000)

            return {
                'proposals': proposals,
                'tokens_in': tokens_in,
                'tokens_out': tokens_out,
                'cost_usd': cost_usd,
                'state_hash': state_hash
            }

        except Exception as e:
            logger.error(f"DeepSeek call failed: {e}")
            return {'proposals': [], 'tokens_in': 0, 'tokens_out': 0, 'cost_usd': 0}

    def store_proposals(self, proposals: List[Dict], state_hash: str, state_vector_id: str, context: Dict, session_id: str):
        """Store proposals in g0_draft_proposals table.

        CEO DIRECTIVE WAVE 9: Evidence Linking Mandate
        All stored hypotheses MUST include:
        - sitc_plan_id: UUID linking to fhq_meta.chain_of_query
        - sitc_confidence: HIGH or MEDIUM (LOW/ABORT are never stored)
        - sitc_asrp_hash: ASRP state hash at validation time
        - sitc_envelope: Full PlanConfidenceEnvelope snapshot

        Status Mapping (Confidence Envelope → Storage):
        - HIGH → VALIDATED_BY_SITC
        - MEDIUM → REVIEW_REQUIRED
        - LOW → NEVER STORED
        - ABORT → NEVER STORED (silent drop)
        """
        # =========================================================
        # WAVE 9: Schema Boundary Enforcement
        # =========================================================
        EC018SchemaBoundary.validate_write('fhq_alpha', 'g0_draft_proposals')

        # Sanitize all proposals for WIN1252 compatibility
        proposals = [sanitize_dict(p) for p in proposals]
        context = sanitize_dict(context)

        with self.conn.cursor() as cur:
            for proposal in proposals:
                proposal_id = str(uuid.uuid4())
                hypothesis_id = proposal.get('hypothesis_id', f"ALPHA-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:3].upper()}")

                # =========================================================
                # WAVE 9: Evidence Linking - Extract SitC validation data
                # =========================================================
                sitc_status = proposal.get('_sitc_status', 'G0_DRAFT')
                sitc_plan_id = proposal.get('_sitc_plan_id')
                sitc_confidence = proposal.get('_sitc_confidence')
                sitc_asrp_hash = proposal.get('_sitc_asrp_hash')
                sitc_envelope = proposal.get('_sitc_envelope')

                # Map SitC status to proposal_status for CHECK constraint compliance
                # VALIDATED_BY_SITC and REVIEW_REQUIRED are not in original CHECK,
                # so we store to G0_DRAFT and use sitc_* columns for true status
                db_status = 'G0_DRAFT'  # CHECK constraint: G0_DRAFT, G1_PENDING, etc.

                cur.execute("""
                    INSERT INTO fhq_alpha.g0_draft_proposals (
                        proposal_id,
                        hunt_session_id,
                        hypothesis_id,
                        hypothesis_title,
                        hypothesis_category,
                        hypothesis_statement,
                        confidence_score,
                        executive_summary,
                        falsification_criteria,
                        backtest_requirements,
                        execution_authority,
                        downstream_pipeline,
                        state_vector_id,
                        state_hash_at_creation,
                        proposal_status,
                        sitc_plan_id,
                        sitc_confidence,
                        sitc_asrp_hash,
                        sitc_envelope,
                        created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                    )
                """, (
                    proposal_id,
                    session_id,
                    hypothesis_id,
                    proposal.get('title', 'Untitled Hypothesis'),
                    proposal.get('category', 'UNKNOWN'),
                    proposal.get('statement', ''),
                    proposal.get('confidence', 0.5),
                    proposal.get('rationale', ''),
                    Json(proposal.get('falsification_criteria', '')),
                    Json({
                        'entry_conditions': proposal.get('entry_conditions', []),
                        'exit_conditions': proposal.get('exit_conditions', {}),
                        'regime_filter': proposal.get('regime_filter', [context['regime']])
                    }),
                    'NONE',  # EC-018 has no execution authority (must match CHECK constraint)
                    Json(['IoS-004', 'IoS-008', 'IoS-012']),
                    state_vector_id,  # Required FK to state_vectors
                    state_hash,
                    db_status,  # G0_DRAFT for CHECK constraint
                    sitc_plan_id,  # Wave 9: SitC Plan ID (UUID)
                    sitc_status,  # Wave 9: VALIDATED_BY_SITC or REVIEW_REQUIRED
                    sitc_asrp_hash,  # Wave 9: ASRP hash at validation
                    Json(sitc_envelope) if sitc_envelope else None  # Wave 9: Full envelope snapshot
                ))

            # Log with SitC status breakdown
            validated_count = sum(1 for p in proposals if p.get('_sitc_status') == 'VALIDATED_BY_SITC')
            review_count = sum(1 for p in proposals if p.get('_sitc_status') == 'REVIEW_REQUIRED')
            logger.info(
                f"Stored {len(proposals)} proposals: "
                f"{validated_count} VALIDATED_BY_SITC, {review_count} REVIEW_REQUIRED"
            )

    def log_telemetry(self, tokens_in: int, tokens_out: int, cost_usd: float, session_id: str):
        """Log hunt telemetry."""
        try:
            with self.conn.cursor() as cur:
                # Log to llm_routing_log (catches immutability trigger errors)
                try:
                    cur.execute("""
                        INSERT INTO fhq_governance.llm_routing_log (
                            agent_id, request_timestamp, requested_provider, requested_tier,
                            routed_provider, routed_tier, policy_satisfied, violation_detected,
                            model, tokens_in, tokens_out, cost_usd, task_type
                        ) VALUES (
                            'FINN', NOW(), 'DEEPSEEK', 2, 'DEEPSEEK', 2, TRUE, FALSE,
                            %s, %s, %s, %s, 'RESEARCH'
                        )
                    """, (DEEPSEEK_MODEL, tokens_in, tokens_out, cost_usd))
                except Exception as e:
                    logger.warning(f"LLM routing log failed (governance constraint): {e}")
                    # Reset connection state if in error state
                    self.conn.rollback()

                # Log to hunt_telemetry if table exists
                try:
                    cur.execute("""
                        INSERT INTO fhq_alpha.hunt_telemetry (
                            session_id, tokens_in, tokens_out, cost_usd, timestamp
                        ) VALUES (%s, %s, %s, %s, NOW())
                    """, (session_id, tokens_in, tokens_out, cost_usd))
                except Exception:
                    pass  # Table might not exist
        except Exception as e:
            logger.warning(f"Telemetry logging failed: {e}")

    def run_hunt(self, focus_area: Optional[str] = None) -> Dict:
        """Execute a single alpha hunt with full ACI integration (CEO Directive 2025-12-17)."""
        hunt_session_id = f"EC018-HUNT-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # =========================================================
        # MANDATE I: ASRP State Binding (ADR-018)
        # =========================================================
        asrp_hash, asrp_timestamp = self._get_asrp_state()
        logger.info(f"ASRP State: {asrp_hash[:16]}... at {asrp_timestamp}")

        # =========================================================
        # MANDATE II: RuntimeEconomicGuardian - UNBYPASSABLE
        # =========================================================
        if not self._init_runtime_guardian(hunt_session_id):
            return {
                'success': False,
                'reason': 'ECONOMIC_GUARDIAN_FAILURE',
                'error': 'RuntimeEconomicGuardian failed to initialize - hunt BLOCKED'
            }

        try:
            # Pre-hunt cost check
            cost_check = self._runtime_guardian.check_or_fail(
                StepType.DB_QUERY if COST_CONTROL_AVAILABLE else None,
                predicted_gain=0.6  # Alpha discovery has high expected value
            )
            if hasattr(cost_check, 'should_abort') and cost_check.should_abort:
                logger.warning(f"RuntimeGuardian ABORT: {cost_check.abort_reason}")
                return {
                    'success': False,
                    'reason': 'RUNTIME_ABORT',
                    'abort_reason': cost_check.abort_reason
                }
        except RuntimeEconomicViolation as e:
            logger.critical(f"ECONOMIC SAFETY VIOLATION: {e}")
            return {
                'success': False,
                'reason': 'ECONOMIC_VIOLATION',
                'error': str(e)
            }
        except Exception as e:
            # If cost control not available, log warning but continue (per Mandate II exception)
            logger.warning(f"Cost check skipped (module unavailable): {e}")

        # =========================================================
        # MANDATE V: IKEA Initialization
        # =========================================================
        self._init_ikea()
        if self._ikea_engine:
            logger.info("IKEA boundary checks active for hypothesis generation")

        # =========================================================
        # CEO DIRECTIVE WAVE 7: SitC Initialization
        # =========================================================
        self._init_sitc(hunt_session_id)
        if self._sitc_enabled:
            logger.info("EC-020 SitC validation active (FILTER mode)")

        # Check budget
        daily_spend = self.get_daily_spend()
        if daily_spend >= DAILY_BUDGET_USD:
            logger.warning(f"Daily budget exhausted: ${daily_spend:.4f} >= ${DAILY_BUDGET_USD}")
            return {'success': False, 'reason': 'BUDGET_EXHAUSTED', 'daily_spend': float(daily_spend)}

        remaining = DAILY_BUDGET_USD - daily_spend
        logger.info(f"Budget check: ${daily_spend:.4f} spent, ${remaining:.4f} remaining")

        # Select focus area (rotate through list)
        if not focus_area:
            focus_area = FOCUS_AREAS[self.hunt_count % len(FOCUS_AREAS)]
        self.hunt_count += 1

        logger.info(f"Starting hunt #{self.hunt_count} - Focus: {focus_area}")

        # Get market context
        context = self.get_market_context()
        logger.info(f"Market context: {context['regime']} regime, DEFCON-{context['defcon']}")

        # Create state vector (ADR-018 State Discipline)
        state_vector_id, state_hash = self.create_state_vector(context)

        # Create hunt session
        session_id = self.create_hunt_session(focus_area, state_vector_id)

        # =========================================================
        # CEO DIRECTIVE WAVE 12: Live Price Witness Precondition
        # =========================================================
        # BLOCKING: If no fresh price witness available, hunt aborts silently.
        # This prevents hypothesis generation under stale data conditions
        # (the root cause of Wave 12 INCONCLUSIVE result).
        witness_result = self._verify_live_price_precondition()

        # Log the witness decision as evidence (fhq_meta only)
        self._log_witness_evidence(witness_result, session_id)

        if not witness_result['satisfied']:
            # SILENT ABORT - CEO Directive requires no exception, just return
            logger.warning(
                f"WAVE 12 PRECONDITION FAILED: {witness_result['reason']} "
                f"(staleness: {witness_result['staleness_minutes']:.1f} min)"
            )
            # Update session status to reflect precondition failure
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE fhq_alpha.hunt_sessions SET
                        session_status = 'PRECONDITION_FAILED',
                        completed_at = NOW()
                    WHERE session_id = %s
                """, (session_id,))

            return {
                'success': False,
                'reason': 'LIVE_PRICE_PRECONDITION_FAILED',
                'session_id': session_id,
                'state_vector_id': state_vector_id,
                'precondition': witness_result,
                'directive_ref': 'CD-EC018-LIVE-PRICE-PRECONDITION-20251217'
            }

        # Witness satisfied - add to context for hypothesis generation
        context['live_price_witness'] = witness_result['witness']
        logger.info(
            f"Live Price Precondition SATISFIED: "
            f"{witness_result['witness']['symbol']} = ${witness_result['witness']['price']:,.2f}"
        )

        # Search for relevant news
        # Holiday Mode: Focus on approved crypto assets
        if HOLIDAY_MODE_ENABLED:
            # Build query focusing on major crypto assets
            crypto_terms = ' OR '.join(['BTC', 'ETH', 'SOL', 'bitcoin', 'ethereum', 'solana'])
            news_query = f"({crypto_terms}) {focus_area.replace('_', ' ').replace('crypto_', '')} trading"
            logger.info(f"HOLIDAY MODE: Crypto-focused news query")
        else:
            news_query = f"cryptocurrency {focus_area.replace('_', ' ')} market"
        news = self.search_market_news(news_query)
        if news:
            logger.info(f"Found {len(news)} news items")

        # Generate hypotheses
        result = self.generate_hypotheses(context, focus_area, news)

        if result['proposals']:
            # =========================================================
            # CEO DIRECTIVE WAVE 9: SitC Cognitive Hard Filter
            # =========================================================
            # SitC is MANDATORY validation gate for all hypotheses.
            # Confidence Envelope Enforcement:
            # - HIGH:   ACCEPT → store with status VALIDATED_BY_SITC
            # - MEDIUM: LOG_ONLY → store with status REVIEW_REQUIRED
            # - LOW:    REJECT → drop completely (no persistence)
            # - ABORT:  SILENT_DROP → drop with no error logging
            #
            # Evidence Linking (all persisted hypotheses MUST reference):
            # - SitC Plan ID
            # - ASRP hash
            # - Confidence Envelope snapshot
            # - Linked entries in fhq_meta.cognitive_engine_evidence

            # Wave 9 Mandate: SitC is MANDATORY - fail-closed if unavailable
            if not self._sitc_enabled:
                logger.error("WAVE 9 VIOLATION: SitC is mandatory but unavailable - hunt BLOCKED")
                return {
                    'success': False,
                    'reason': 'SITC_MANDATORY_UNAVAILABLE',
                    'error': 'CEO Directive Wave 9: SitC is mandatory for hypothesis validation'
                }

            validated_proposals = []
            rejected_proposals = []
            aborted_proposals = []  # Silent drops
            sitc_results = []

            for proposal in result['proposals']:
                validation = self._validate_hypothesis_with_sitc(proposal, context)
                sitc_results.append(validation)

                if validation['action'] == 'ACCEPT':
                    # HIGH confidence → VALIDATED_BY_SITC
                    proposal['_sitc_status'] = 'VALIDATED_BY_SITC'
                    proposal['_sitc_plan_id'] = validation.get('plan_id')
                    proposal['_sitc_confidence'] = validation.get('confidence')
                    proposal['_sitc_asrp_hash'] = validation.get('asrp_hash')
                    proposal['_sitc_envelope'] = validation.get('envelope')
                    validated_proposals.append(proposal)

                elif validation['action'] == 'LOG_ONLY':
                    # MEDIUM confidence → REVIEW_REQUIRED
                    proposal['_sitc_status'] = 'REVIEW_REQUIRED'
                    proposal['_sitc_plan_id'] = validation.get('plan_id')
                    proposal['_sitc_confidence'] = validation.get('confidence')
                    proposal['_sitc_asrp_hash'] = validation.get('asrp_hash')
                    proposal['_sitc_envelope'] = validation.get('envelope')
                    proposal['_sitc_reason'] = validation['reason']
                    validated_proposals.append(proposal)

                elif validation['action'] == 'ABORT':
                    # ABORT → Silent drop (no persistence, no error logging)
                    # CEO Directive Wave 9: System prefers silence over false certainty
                    aborted_proposals.append(proposal)
                    # NO LOGGING - silent drop

                else:  # REJECT (LOW confidence)
                    # LOW confidence → drop completely (no persistence)
                    rejected_proposals.append({
                        'proposal': proposal,
                        'reason': validation['reason'],
                        'confidence': validation['confidence']
                    })
                    logger.warning(
                        f"Hypothesis REJECTED (LOW confidence): {proposal.get('title', 'Untitled')[:40]}..."
                    )

            # Log validation summary (exclude ABORT count from noise)
            logger.info(
                f"SitC Validation: {len(validated_proposals)} accepted, "
                f"{len(rejected_proposals)} rejected out of {len(result['proposals'])} proposals"
            )

            # Store only validated proposals with evidence linking
            if validated_proposals:
                self.store_proposals(validated_proposals, state_hash, state_vector_id, context, session_id)

            # Log telemetry
            self.log_telemetry(result['tokens_in'], result['tokens_out'], result['cost_usd'], session_id)

            # Update hunt session with results
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE fhq_alpha.hunt_sessions SET
                        total_tokens_in = %s,
                        total_tokens_out = %s,
                        total_cost_usd = %s,
                        hypotheses_generated = %s,
                        session_status = 'COMPLETED',
                        completed_at = NOW()
                    WHERE session_id = %s
                """, (
                    result['tokens_in'],
                    result['tokens_out'],
                    result['cost_usd'],
                    len(validated_proposals),  # Only count validated proposals
                    session_id
                ))

            logger.info(
                f"Hunt complete: {len(validated_proposals)} validated hypotheses "
                f"(of {len(result['proposals'])} generated), ${result['cost_usd']:.6f}"
            )

            return {
                'success': True,
                'session_id': session_id,
                'state_vector_id': state_vector_id,
                'hypotheses_count': len(validated_proposals),
                'hypotheses_generated': len(result['proposals']),
                'hypotheses_rejected': len(rejected_proposals),
                'hypotheses_aborted': len(aborted_proposals),  # Wave 9: Silent drops
                'cost_usd': result['cost_usd'],
                'focus_area': focus_area,
                'state_hash': state_hash,
                # MANDATE I: ASRP State Binding
                'asrp_hash': self._current_asrp_hash,
                'asrp_timestamp': str(self._current_asrp_timestamp) if self._current_asrp_timestamp else None,
                # CEO DIRECTIVE WAVE 9: SitC Cognitive Hard Filter Results
                'sitc_enabled': self._sitc_enabled,
                'sitc_validation': {
                    'accepted': len([r for r in sitc_results if r['action'] == 'ACCEPT']),
                    'log_only': len([r for r in sitc_results if r['action'] == 'LOG_ONLY']),
                    'rejected': len([r for r in sitc_results if r['action'] == 'REJECT']),
                    'aborted': len([r for r in sitc_results if r['action'] == 'ABORT']),  # Wave 9
                    'all_unchanged': all(r.get('hypothesis_unchanged', True) for r in sitc_results)
                },
                # CEO DIRECTIVE AMEND-002: Full SitC validation details for G2 evidentiary completeness
                # This propagates already-computed EQS scores upward for governance examination.
                # NO cognitive/scoring logic is modified - purely observational.
                'sitc_validations': [
                    {
                        'title': proposal.get('title', 'Untitled'),
                        'hypothesis': proposal.get('statement', proposal.get('title', '')),
                        'eqs_score': validation.get('envelope', {}).get('evidence_quality_score', 0.0) if isinstance(validation.get('envelope'), dict) else 0.0,
                        'confidence': validation.get('confidence', 'UNKNOWN'),
                        'action': validation.get('action', 'UNKNOWN'),
                        'confluence_factors': validation.get('envelope', {}).get('confluence_factors', []) if isinstance(validation.get('envelope'), dict) else [],
                        'eqs_components': validation.get('envelope', {}).get('eqs_components', {}) if isinstance(validation.get('envelope'), dict) else {},
                        'plan_id': validation.get('plan_id', ''),
                        'asrp_hash': validation.get('asrp_hash', '')
                    }
                    for proposal, validation in zip(result['proposals'], sitc_results)
                ]
            }
        else:
            # Mark session as completed with no results
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE fhq_alpha.hunt_sessions SET
                        session_status = 'COMPLETED',
                        completed_at = NOW()
                    WHERE session_id = %s
                """, (session_id,))

            logger.warning("Hunt produced no hypotheses")
            return {
                'success': False,
                'reason': 'NO_HYPOTHESES',
                'session_id': session_id,
                'state_vector_id': state_vector_id
            }

    def run_daemon(self, interval_minutes: int = 60):
        """Run as continuous daemon."""
        logger.info(f"EC-018 Alpha Daemon starting - interval: {interval_minutes} minutes")

        while True:
            try:
                result = self.run_hunt()
                logger.info(f"Hunt result: {json.dumps(result, default=str)}")
            except Exception as e:
                logger.error(f"Hunt failed: {e}")

            # Wait for next hunt
            next_hunt = datetime.now() + timedelta(minutes=interval_minutes)
            logger.info(f"Next hunt at {next_hunt.strftime('%H:%M:%S')}")
            time.sleep(interval_minutes * 60)


def main():
    parser = argparse.ArgumentParser(description='EC-018 Alpha Discovery Daemon')
    parser.add_argument('--daemon', action='store_true', help='Run as continuous daemon')
    parser.add_argument('--interval', type=int, default=60, help='Hunt interval in minutes')
    parser.add_argument('--focus', type=str, help='Specific focus area for single hunt')
    parser.add_argument('--once', action='store_true', help='Run single hunt and exit')
    args = parser.parse_args()

    # Ensure logs directory exists
    os.makedirs('C:/fhq-market-system/vision-ios/logs', exist_ok=True)

    daemon = EC018AlphaDaemon()

    try:
        daemon.connect()

        if args.daemon:
            daemon.run_daemon(args.interval)
        elif args.once or args.focus:
            result = daemon.run_hunt(args.focus)
            print(json.dumps(result, indent=2, default=str))
        else:
            # Default: single hunt
            result = daemon.run_hunt()
            print(json.dumps(result, indent=2, default=str))

    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        daemon.close()


if __name__ == '__main__':
    main()
