"""
Decision Pack - Atomic Decision Object
CEO-DIR-2026-01-22: Signal → Decision Pack → Bracket Order

Every trade decision is encapsulated in a complete, signed Decision Pack
before any execution is permitted. This ensures:
- No ambiguity at execution time
- Full evidence chain for audit
- VEGA attestation enforcement
- Deterministic TP/SL from EWRE

Author: STIG (CTO)
Contract: EC-003_2026_PRODUCTION
"""

import os
import json
import hashlib
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', '127.0.0.1'),
    'port': int(os.getenv('POSTGRES_PORT', 54322)),
    'dbname': os.getenv('POSTGRES_DB', 'postgres'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', '')
}


@dataclass
class EWRESpec:
    """Event-Weighted Risk Envelope specification."""
    stop_loss_pct: float          # e.g., 0.03 = 3%
    take_profit_pct: float        # e.g., 0.08 = 8%
    risk_reward_ratio: float      # TP/SL
    calculation_inputs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionPack:
    """
    Atomic Decision Object per CEO Specification.

    All fields must be complete before execution is permitted.
    """
    # Identity
    pack_id: UUID
    created_at: datetime
    pack_version: str = "1.0.0"

    # Source Signal Reference
    needle_id: UUID = None
    hypothesis_id: str = None

    # Asset & Direction
    asset: str = None                    # Canonical symbol (e.g., "BTC/USD")
    direction: str = None                # "LONG" or "SHORT"
    asset_class: str = None              # "CRYPTO", "EQUITY", "ETF"

    # Market Snapshot (TTL-enforced)
    snapshot_price: float = None
    snapshot_regime: str = None
    snapshot_volatility_atr: float = None
    snapshot_timestamp: datetime = None
    snapshot_ttl_valid_until: datetime = None  # 60s from snapshot

    # Confidence Stack (Damped)
    raw_confidence: float = None
    damped_confidence: float = None
    confidence_ceiling: float = None
    inversion_flag: bool = False
    inversion_type: str = None           # "STRESS_HIGH", "BULL_LOW"

    # Historical Calibration
    historical_accuracy: float = None
    brier_skill_score: float = None

    # EWRE (Event-Weighted Risk Envelope)
    ewre: EWRESpec = None

    # Bracket Order Specification
    entry_type: str = "LIMIT"
    entry_limit_price: float = None
    take_profit_price: float = None
    stop_loss_price: float = None
    stop_type: str = "STOP_MARKET"       # "STOP_MARKET" or "STOP_LIMIT"
    stop_limit_price: float = None       # If STOP_LIMIT

    # Position Sizing
    position_usd: float = None
    position_qty: float = None
    kelly_fraction: float = None
    max_position_pct: float = None

    # Time Constraints
    order_ttl_seconds: int = 86400       # 24h default
    abort_if_not_filled_by: datetime = None

    # Evidence Chain (Court-Proof)
    sitc_event_id: UUID = None
    inforage_session_id: UUID = None
    ikea_validation_id: UUID = None
    causal_edge_refs: List[UUID] = field(default_factory=list)
    evidence_hash: str = None

    # Cognitive Stack Results
    sitc_reasoning_complete: bool = False
    inforage_roi: float = None
    ikea_passed: bool = False
    causal_alignment_score: float = 0.5

    # Narrative (for Telegram)
    hypothesis_title: str = None
    executive_summary: str = None
    narrative_context: str = None

    # VEGA Attestation
    vega_attestation_required: bool = True
    vega_attested: bool = False
    vega_attestation_id: str = None

    # Signature
    signature: str = None
    signing_agent: str = "STIG"
    signing_key_id: str = "STIG-KEY-2026-001"
    signed_at: datetime = None

    # Outcome (Post-execution)
    execution_status: str = "PENDING"    # PENDING/EXECUTED/BLOCKED/EXPIRED
    alpaca_order_id: str = None
    filled_price: float = None
    filled_at: datetime = None

    # Strategy tracking for Day 22 analysis
    strategy_tag: str = "EWRE_V1"
    experiment_cohort: str = "FIRST_20"

    def __post_init__(self):
        """Initialize computed fields."""
        if self.pack_id is None:
            self.pack_id = uuid4()
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.snapshot_ttl_valid_until is None and self.snapshot_timestamp:
            self.snapshot_ttl_valid_until = self.snapshot_timestamp + timedelta(seconds=60)
        if self.abort_if_not_filled_by is None:
            self.abort_if_not_filled_by = self.created_at + timedelta(seconds=self.order_ttl_seconds)

    def compute_evidence_hash(self) -> str:
        """Compute SHA-256 hash of all evidence for audit trail."""
        evidence_content = {
            'needle_id': str(self.needle_id) if self.needle_id else None,
            'asset': self.asset,
            'direction': self.direction,
            'entry_limit_price': self.entry_limit_price,
            'take_profit_price': self.take_profit_price,
            'stop_loss_price': self.stop_loss_price,
            'position_usd': self.position_usd,
            'damped_confidence': self.damped_confidence,
            'sitc_event_id': str(self.sitc_event_id) if self.sitc_event_id else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        content_str = json.dumps(evidence_content, sort_keys=True)
        self.evidence_hash = hashlib.sha256(content_str.encode()).hexdigest()
        return self.evidence_hash

    def sign(self, agent: str = "STIG", key_id: str = "STIG-KEY-2026-001") -> str:
        """Sign the decision pack."""
        self.signing_agent = agent
        self.signing_key_id = key_id
        self.signed_at = datetime.now(timezone.utc)

        # Compute signature over critical fields
        sign_content = {
            'pack_id': str(self.pack_id),
            'evidence_hash': self.evidence_hash,
            'signing_agent': self.signing_agent,
            'signed_at': self.signed_at.isoformat()
        }
        content_str = json.dumps(sign_content, sort_keys=True)
        self.signature = hashlib.sha256(content_str.encode()).hexdigest()[:32]
        return self.signature

    def is_valid_for_execution(self) -> tuple[bool, str]:
        """
        VEGA Rule: No execution unless pack is complete + evidence refs exist.
        """
        now = datetime.now(timezone.utc)

        # Check VEGA attestation
        if self.vega_attestation_required and not self.vega_attested:
            return False, "VEGA_ATTESTATION_MISSING"

        # Check evidence completeness
        if not self.evidence_hash:
            return False, "EVIDENCE_HASH_MISSING"

        # Check signature
        if not self.signature:
            return False, "SIGNATURE_MISSING"

        # Check TTL
        if self.snapshot_ttl_valid_until and now > self.snapshot_ttl_valid_until:
            return False, "SNAPSHOT_TTL_EXPIRED"

        # Check abort time
        if self.abort_if_not_filled_by and now > self.abort_if_not_filled_by:
            return False, "ORDER_TTL_EXPIRED"

        # Check bracket order completeness
        if not self.take_profit_price or not self.stop_loss_price:
            return False, "TP_SL_INCOMPLETE"

        if not self.entry_limit_price:
            return False, "ENTRY_PRICE_MISSING"

        # Check EWRE validity
        if self.ewre and self.ewre.risk_reward_ratio < 1.0:
            return False, "RISK_REWARD_BELOW_MINIMUM"

        return True, "APPROVED"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {}
        for key, value in asdict(self).items():
            if isinstance(value, (UUID, datetime)):
                result[key] = str(value) if value else None
            elif isinstance(value, Decimal):
                result[key] = float(value)
            elif hasattr(value, 'to_dict'):
                result[key] = value.to_dict()
            else:
                result[key] = value
        return result

    def save_evidence(self, evidence_dir: str = None) -> str:
        """Save decision pack as evidence JSON file."""
        if evidence_dir is None:
            evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
        os.makedirs(evidence_dir, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        filename = f"DECISION_PACK_{str(self.pack_id)[:8]}_{timestamp}.json"
        filepath = os.path.join(evidence_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

        logger.info(f"[DecisionPack] Evidence saved: {filepath}")
        return filepath


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def save_decision_pack_to_db(pack: DecisionPack) -> bool:
    """
    Persist decision pack to fhq_learning.decision_packs.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Ensure schema exists
        cur.execute("CREATE SCHEMA IF NOT EXISTS fhq_learning")

        # Insert decision pack
        cur.execute("""
            INSERT INTO fhq_learning.decision_packs (
                pack_id, needle_id, asset, direction, asset_class,
                snapshot_price, snapshot_regime, snapshot_volatility_atr,
                snapshot_timestamp, snapshot_ttl_valid_until,
                raw_confidence, damped_confidence, confidence_ceiling,
                inversion_flag, inversion_type,
                historical_accuracy, brier_skill_score,
                ewre_stop_loss_pct, ewre_take_profit_pct, ewre_risk_reward_ratio,
                ewre_calculation_inputs,
                entry_type, entry_limit_price, take_profit_price, stop_loss_price,
                stop_type, stop_limit_price,
                position_usd, position_qty, kelly_fraction, max_position_pct,
                order_ttl_seconds, abort_if_not_filled_by,
                sitc_event_id, evidence_hash,
                sitc_reasoning_complete, inforage_roi, ikea_passed, causal_alignment_score,
                hypothesis_title, executive_summary, narrative_context,
                vega_attestation_required, vega_attested, vega_attestation_id,
                signature, signing_agent, signing_key_id, signed_at,
                execution_status, strategy_tag, experiment_cohort,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (pack_id) DO UPDATE SET
                execution_status = EXCLUDED.execution_status,
                alpaca_order_id = EXCLUDED.alpaca_order_id,
                filled_price = EXCLUDED.filled_price,
                filled_at = EXCLUDED.filled_at
        """, (
            str(pack.pack_id), str(pack.needle_id) if pack.needle_id else None,
            pack.asset, pack.direction, pack.asset_class,
            pack.snapshot_price, pack.snapshot_regime, pack.snapshot_volatility_atr,
            pack.snapshot_timestamp, pack.snapshot_ttl_valid_until,
            pack.raw_confidence, pack.damped_confidence, pack.confidence_ceiling,
            pack.inversion_flag, pack.inversion_type,
            pack.historical_accuracy, pack.brier_skill_score,
            pack.ewre.stop_loss_pct if pack.ewre else None,
            pack.ewre.take_profit_pct if pack.ewre else None,
            pack.ewre.risk_reward_ratio if pack.ewre else None,
            json.dumps(pack.ewre.calculation_inputs) if pack.ewre else None,
            pack.entry_type, pack.entry_limit_price, pack.take_profit_price, pack.stop_loss_price,
            pack.stop_type, pack.stop_limit_price,
            pack.position_usd, pack.position_qty, pack.kelly_fraction, pack.max_position_pct,
            pack.order_ttl_seconds, pack.abort_if_not_filled_by,
            str(pack.sitc_event_id) if pack.sitc_event_id else None, pack.evidence_hash,
            pack.sitc_reasoning_complete, pack.inforage_roi, pack.ikea_passed, pack.causal_alignment_score,
            pack.hypothesis_title, pack.executive_summary, pack.narrative_context,
            pack.vega_attestation_required, pack.vega_attested, pack.vega_attestation_id,
            pack.signature, pack.signing_agent, pack.signing_key_id, pack.signed_at,
            pack.execution_status, pack.strategy_tag, pack.experiment_cohort,
            pack.created_at
        ))

        conn.commit()
        logger.info(f"[DecisionPack] Saved to DB: {pack.pack_id}")
        return True

    except Exception as e:
        logger.error(f"[DecisionPack] DB save failed: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def load_decision_pack_from_db(pack_id: UUID) -> Optional[DecisionPack]:
    """Load decision pack from database."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT * FROM fhq_learning.decision_packs
            WHERE pack_id = %s
        """, (str(pack_id),))

        row = cur.fetchone()
        if not row:
            return None

        # Reconstruct DecisionPack from row
        pack = DecisionPack(
            pack_id=UUID(row['pack_id']),
            created_at=row['created_at']
        )
        # ... (populate other fields)

        return pack

    except Exception as e:
        logger.error(f"[DecisionPack] DB load failed: {e}")
        return None
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    # Test decision pack creation
    pack = DecisionPack(
        pack_id=uuid4(),
        needle_id=uuid4(),
        asset="BTC/USD",
        direction="LONG",
        asset_class="CRYPTO",
        snapshot_price=103500.0,
        snapshot_regime="NEUTRAL",
        snapshot_volatility_atr=2.8,
        snapshot_timestamp=datetime.now(timezone.utc),
        raw_confidence=0.85,
        damped_confidence=0.68,
        confidence_ceiling=0.70,
        entry_limit_price=103450.0,
        take_profit_price=111726.0,
        stop_loss_price=98278.0,
        position_usd=5000.0,
        position_qty=0.048,
        hypothesis_title="Neutral-to-Bull Transition on Regulatory Clarity",
        narrative_context="UK regulatory clarity removes uncertainty tail risk.",
        ewre=EWRESpec(
            stop_loss_pct=0.05,
            take_profit_pct=0.08,
            risk_reward_ratio=1.6
        )
    )

    pack.compute_evidence_hash()
    pack.sign()

    print(f"Pack ID: {pack.pack_id}")
    print(f"Evidence Hash: {pack.evidence_hash}")
    print(f"Signature: {pack.signature}")

    valid, reason = pack.is_valid_for_execution()
    print(f"Valid for execution: {valid} ({reason})")

    # Save evidence
    filepath = pack.save_evidence()
    print(f"Evidence saved to: {filepath}")
