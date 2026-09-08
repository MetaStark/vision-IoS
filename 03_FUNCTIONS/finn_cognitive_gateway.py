"""
FINN Cognitive Gateway
CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001

Single deterministic entrypoint from orchestrator to cognitive engine.
Returns SignalEnvelope or NoSignal - never raises exceptions to caller.

Mode Switch (Circuit-Breaker Class):
- OFF: Gateway not invoked, returns NoSignal immediately
- SHADOW: Full pipeline runs, evidence stored, but returns NoSignal (observation mode)
- LIVE: Full pipeline runs, returns real signals

Default: COGNITIVE_ENGINE_MODE=OFF (explicit activation required)
Activation path: OFF -> SHADOW (48h observation) -> LIVE (CEO approval)

Author: STIG (CTO)
Date: 2026-01-04
"""

import os
import sys
import uuid
import json
import logging
import psycopg2
from datetime import datetime, timezone
from typing import Union, Optional, Dict, List, Any

# Load environment
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'), override=True)

# Setup path
sys.path.insert(0, os.path.dirname(__file__))

# Imports
from schemas.signal_envelope import (
    SignalEnvelope,
    NoSignal,
    Claim,
    GroundingResult,
    SignalAction,
    ClaimType,
    DEFCONLevel,
    validate_envelope_for_execution
)
from schemas.cognitive_engines import EvidenceBundle

from data_liveness_checker import check_data_liveness, should_abort_cognitive_cycle
from cognitive_health_monitor import calculate_evidence_coverage_ratio
from finn_reasoning import FINNReasoner, convert_to_gateway_claims

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Mode switch: OFF / SHADOW / LIVE
COGNITIVE_ENGINE_MODE = os.environ.get('COGNITIVE_ENGINE_MODE', 'OFF')

# Cost cap (constitutional - $0.50 per query)
QUERY_COST_CAP_USD = 0.50

# Database connection
DB_HOST = os.environ.get('PGHOST', 'localhost')
DB_PORT = os.environ.get('PGPORT', '54322')
DB_NAME = os.environ.get('PGDATABASE', 'postgres')
DB_USER = os.environ.get('PGUSER', 'postgres')
DB_PASS = os.environ.get('PGPASSWORD', 'postgres')


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=int(DB_PORT),
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )


# =============================================================================
# TYPE ALIAS
# =============================================================================

CognitiveResult = Union[SignalEnvelope, NoSignal]


# =============================================================================
# AUDIT LOGGING (CEO-DIR-2026-SITC-DATA-BLACKOUT-FIX-001 P0)
# =============================================================================

def log_cognitive_attempt(
    conn,
    query: str,
    defcon_level: DEFCONLevel,
    regime: str,
    asset: Optional[str],
    result: CognitiveResult,
    latency_ms: float,
    snippet_count: int = 0,
    cost_usd: float = 0.0,
    bundle_id: Optional[str] = None
) -> bool:
    """
    Log every cognitive cycle attempt to inforage_query_log.

    CEO-DIR-2026-SITC-DATA-BLACKOUT-FIX-001 P0: Mandatory audit logging

    Executes exactly once per governed query attempt, regardless of outcome:
    - SUCCESS: SignalEnvelope generated
    - NO_SIGNAL: Normal termination without signal
    - ABORT: STALE_DATA / DATA_BLACKOUT / EVIDENCE_UNAVAILABLE
    - EXCEPTION: Caught error converted to NoSignal

    Returns: True if logged successfully, False if DB write failed
    """
    if conn is None:
        logger.error("[GATEWAY/LOG] Cannot log: no database connection")
        return False

    cursor = None
    actual_cost = cost_usd
    actual_bundle_id = bundle_id

    try:
        cursor = conn.cursor()

        # Determine result_type
        if isinstance(result, SignalEnvelope):
            result_type = 'SIGNAL'
            actual_cost = result.query_cost_usd or cost_usd
            actual_bundle_id = str(result.bundle_id) if result.bundle_id else bundle_id
        elif isinstance(result, NoSignal):
            reason = result.reason or ''
            if 'STALE_DATA' in reason or 'DATA_BLACKOUT' in reason:
                result_type = 'ABORT_STALE_DATA'
            elif 'EVIDENCE' in reason or 'RETRIEVAL' in reason:
                result_type = 'ABORT_EVIDENCE'
            elif 'EXCEPTION' in reason or 'ERROR' in reason:
                result_type = 'EXCEPTION'
            elif 'SHADOW' in reason:
                result_type = 'SHADOW_SIGNAL'
                if hasattr(result, 'shadow_envelope') and result.shadow_envelope:
                    actual_cost = result.shadow_envelope.query_cost_usd or cost_usd
                    actual_bundle_id = str(result.shadow_envelope.bundle_id) if result.shadow_envelope.bundle_id else bundle_id
            elif 'OFF' in reason:
                result_type = 'MODE_OFF'
            elif 'IKEA' in reason:
                result_type = 'IKEA_VIOLATION'
            elif 'COST' in reason:
                result_type = 'COST_EXCEEDED'
            else:
                result_type = 'NO_SIGNAL'
        else:
            result_type = 'UNKNOWN'

        ecr = min(snippet_count / 3.0, 1.0) if snippet_count else 0.0
        query_id = str(uuid.uuid4())

        cursor.execute("""
            INSERT INTO fhq_governance.inforage_query_log (
                query_id, query_text, retrieval_mode, defcon_level, latency_ms, cost_usd,
                result_type, evidence_coverage_ratio, retrieved_snippet_count,
                bundle_id, querying_agent, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, [
            query_id,
            query[:500] if query else '',
            'HYBRID',  # Retrieval mode: HYBRID (dense + sparse)
            defcon_level.value if hasattr(defcon_level, 'value') else str(defcon_level),
            latency_ms,
            actual_cost,
            result_type,
            ecr,
            snippet_count,
            actual_bundle_id,
            'FINN'  # Querying agent
        ])
        conn.commit()

        logger.info(f"[GATEWAY/LOG] Logged: {result_type} | ECR={ecr:.2f} | cost=${actual_cost:.4f} | latency={latency_ms:.0f}ms")
        return True

    except Exception as e:
        logger.error(f"[GATEWAY/LOG] CRITICAL: Failed to log cognitive attempt: {e}")
        try:
            if cursor:
                cursor.close()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO fhq_monitoring.alert_events (
                    alert_id, alert_type, severity, source_system, message, created_at
                ) VALUES (%s, 'COGNITIVE_LOG_FAILURE', 'HIGH', 'FINN_GATEWAY', %s, NOW())
                ON CONFLICT DO NOTHING
            """, [str(uuid.uuid4()), f"Log write failed: {str(e)[:200]}"])
            conn.commit()
        except:
            pass
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return False
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass


# =============================================================================
# GATEWAY IMPLEMENTATION
# =============================================================================

def run_cognitive_cycle(
    query: str,
    defcon_level: DEFCONLevel,
    regime: str,
    asset: Optional[str] = None
) -> CognitiveResult:
    """
    Single entrypoint for all cognitive operations.

    CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001 Section 2.2

    Pipeline:
    - P0: Data Liveness Check (per-domain gates)
    - P1: EmbeddingGenerator.generate_query_embedding()
    - P2: InForageHybridRetriever.retrieve()
    - P3: MemoryStack.page_in()
    - P4: FINN Reasoning (LLM)
    - P5: IKEAVerifier.enforce()
    - P6: Signal Output

    Args:
        query: Query text for cognitive engine
        defcon_level: Current DEFCON level (gates budget)
        regime: Current market regime (e.g., "NEUTRAL", "RISK_ON")
        asset: Optional asset ticker (e.g., "BTC-USD")

    Returns:
        SignalEnvelope (in LIVE mode) or NoSignal (in OFF/SHADOW mode or on failure)

    Never raises exceptions to caller - all failures return NoSignal.
    """
    start_time = datetime.now(timezone.utc)
    snippet_count = 0
    cost_usd = 0.0
    bundle_id = None

    def elapsed_ms():
        return (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

    # === MODE CHECK ===
    if COGNITIVE_ENGINE_MODE == 'OFF':
        logger.info(f"[GATEWAY] Mode=OFF, returning NoSignal immediately")
        result = NoSignal.create(
            reason="COGNITIVE_ENGINE_MODE=OFF",
            defcon_level=defcon_level
        )
        try:
            conn = get_db_connection()
            log_cognitive_attempt(conn, query, defcon_level, regime, asset, result, elapsed_ms())
            conn.close()
        except Exception as e:
            logger.warning(f"[GATEWAY] Failed to log MODE_OFF: {e}")
        return result

    logger.info(f"[GATEWAY] Mode={COGNITIVE_ENGINE_MODE}, starting cognitive cycle")
    logger.info(f"[GATEWAY] Query: {query[:50]}... | DEFCON: {defcon_level} | Regime: {regime}")

    conn = None
    try:
        conn = get_db_connection()

        # === P0: DATA LIVENESS CHECK ===
        should_abort, abort_reason, liveness_report = should_abort_cognitive_cycle(conn)

        if should_abort:
            logger.warning(f"[GATEWAY] P0 ABORT: {abort_reason}")
            result = NoSignal.create(
                reason=f"STALE_DATA: {abort_reason}",
                defcon_level=defcon_level
            )
            log_cognitive_attempt(conn, query, defcon_level, regime, asset, result, elapsed_ms())
            return result

        logger.info(f"[GATEWAY] P0 PASS: All data domains fresh")

        # === P1: EMBEDDING GENERATION ===
        try:
            from embedding_generator import EmbeddingGenerator

            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key or api_key == 'placeholder':
                logger.warning("[GATEWAY] P1 FALLBACK: No valid API key, sparse-only mode")
                query_embedding = []
            else:
                embedder = EmbeddingGenerator(api_key=api_key)
                query_embedding = embedder.generate([query])[0]
                logger.info(f"[GATEWAY] P1 PASS: Generated embedding ({len(query_embedding)} dims)")

        except Exception as e:
            logger.warning(f"[GATEWAY] P1 FALLBACK: Embedding failed ({e}), sparse-only mode")
            query_embedding = []

        # === P2: HYBRID RETRIEVAL ===
        try:
            from inforage_hybrid_retriever import InForageHybridRetriever
            from qdrant_graphrag_client import QdrantGraphRAGClient

            # Initialize Qdrant client
            qdrant_client = QdrantGraphRAGClient(qdrant_host="localhost", qdrant_port=6333)

            # Initialize retriever with all required components
            retriever = InForageHybridRetriever(
                qdrant_client=qdrant_client,
                db_conn=conn,
                embedding_generator=embedder if 'embedder' in dir() else None
            )
            evidence_bundle = retriever.retrieve(
                query_text=query,
                defcon_level=defcon_level.value if hasattr(defcon_level, 'value') else str(defcon_level),
                top_k=5
            )

            snippet_ids = evidence_bundle.snippet_ids
            snippet_count = len(snippet_ids)
            bundle_id = str(evidence_bundle.bundle_id) if evidence_bundle.bundle_id else None
            logger.info(f"[GATEWAY] P2 PASS: Retrieved {snippet_count} snippets")

            # Calculate ECR
            ecr_result = calculate_evidence_coverage_ratio(len(snippet_ids))
            if ecr_result.status == "CRITICAL":
                logger.warning(f"[GATEWAY] P2 WARNING: Low ECR={ecr_result.ecr:.2f}")

        except Exception as e:
            logger.error(f"[GATEWAY] P2 FAIL: Retrieval failed ({e})")
            result = NoSignal.create(
                reason=f"RETRIEVAL_FAILED: {str(e)}",
                defcon_level=defcon_level
            )
            log_cognitive_attempt(conn, query, defcon_level, regime, asset, result, elapsed_ms(), snippet_count, cost_usd, bundle_id)
            return result

        if not snippet_ids:
            logger.warning("[GATEWAY] P2 ABORT: No evidence retrieved")
            result = NoSignal.create(
                reason="NO_EVIDENCE_RETRIEVED",
                defcon_level=defcon_level
            )
            log_cognitive_attempt(conn, query, defcon_level, regime, asset, result, elapsed_ms(), snippet_count, cost_usd, bundle_id)
            return result

        # === P3: MEMORY STACK (Simplified) ===
        # Full implementation would page in Core/Recall/Archival memory
        # For now, we pass regime context directly
        memory_context = {
            'regime': regime,
            'asset': asset,
            'defcon_level': defcon_level.value if hasattr(defcon_level, 'value') else str(defcon_level)
        }
        logger.info(f"[GATEWAY] P3 PASS: Memory context loaded")

        # === P4: FINN REASONING (LLM-Powered) ===
        # Get evidence texts for FINN reasoning
        evidence_texts = {}
        cursor = conn.cursor()
        for snippet_id in snippet_ids[:5]:  # Limit to top 5
            cursor.execute("""
                SELECT content FROM fhq_canonical.evidence_nodes
                WHERE evidence_id = %s
            """, [str(snippet_id)])
            row = cursor.fetchone()
            if row:
                evidence_texts[str(snippet_id)] = row[0]
        cursor.close()

        # Initialize FINN reasoner and generate grounded claims
        draft_claims = []
        reasoning_result = None

        try:
            reasoner = FINNReasoner()
            reasoning_result = reasoner.reason(
                query=query,
                evidence_texts=evidence_texts,
                asset=asset or "UNKNOWN",
                regime=regime,
                defcon_level=defcon_level.value if hasattr(defcon_level, 'value') else str(defcon_level)
            )

            # Convert FINN claims to gateway claims
            draft_claims = convert_to_gateway_claims(reasoning_result, Claim, ClaimType)
            cost_usd = reasoning_result.cost_usd if reasoning_result else 0.0

            logger.info(
                f"[GATEWAY] P4 PASS: FINN generated {len(draft_claims)} claims, "
                f"signal={reasoning_result.signal_action}, cost=${reasoning_result.cost_usd:.4f}"
            )

        except Exception as e:
            logger.error(f"[GATEWAY] P4 FALLBACK: FINN reasoning failed ({e}), using evidence-based claims")
            # Fallback: Create simple claims from evidence
            if evidence_texts:
                for snippet_id, content in list(evidence_texts.items())[:3]:
                    # Extract first meaningful sentence from evidence
                    first_sentence = content.split('.')[0].strip()
                    if len(first_sentence) > 20:
                        draft_claims.append(Claim.create(
                            claim_text=f"{first_sentence}. [Source: snippet {snippet_id[:8]}]",
                            claim_type=ClaimType.ENTITY_PREDICATE,
                            snippet_ids=[snippet_id],
                            grounded=False
                        ))

        logger.info(f"[GATEWAY] P4 COMPLETE: {len(draft_claims)} draft claims ready for IKEA")

        # === P5: IKEA GROUNDING ===
        try:
            from ikea_verifier import IKEAVerifier, IKEAViolation

            verifier = IKEAVerifier(strict_mode=True)

            # Verify each claim against evidence
            verified_claims = []
            ungrounded_claim_ids = []

            for claim in draft_claims:
                is_grounded = False
                grounding_snippets = []

                for snippet_id, snippet_text in evidence_texts.items():
                    if verifier._claim_matches_evidence(claim.claim_text, snippet_text):
                        grounding_snippets.append(snippet_id)
                        is_grounded = True

                if is_grounded:
                    verified_claims.append(Claim.create(
                        claim_text=claim.claim_text,
                        claim_type=claim.claim_type,
                        snippet_ids=grounding_snippets,
                        grounded=True
                    ))
                else:
                    ungrounded_claim_ids.append(claim.claim_id)

            # Calculate grounding result
            total_claims = len(draft_claims)
            grounded_count = len(verified_claims)
            ungrounded_count = total_claims - grounded_count
            gcr = grounded_count / total_claims if total_claims > 0 else 1.0

            grounding_result = GroundingResult(
                total_claims=total_claims,
                grounded_count=grounded_count,
                ungrounded_count=ungrounded_count,
                gcr=gcr,
                ungrounded_claims=ungrounded_claim_ids
            )

            if not grounding_result.is_fully_grounded:
                logger.warning(f"[GATEWAY] P5 FAIL: GCR={gcr:.2%}, {ungrounded_count} ungrounded")
                result = NoSignal.create(
                    reason=f"IKEA_VIOLATION: GCR={gcr:.2%}",
                    defcon_level=defcon_level
                )
                log_cognitive_attempt(conn, query, defcon_level, regime, asset, result, elapsed_ms(), snippet_count, cost_usd, bundle_id)
                return result

            logger.info(f"[GATEWAY] P5 PASS: GCR={gcr:.2%}, all claims grounded")

        except IKEAViolation as e:
            logger.warning(f"[GATEWAY] P5 FAIL: {e}")
            result = NoSignal.create(
                reason=f"IKEA_VIOLATION: {str(e)}",
                defcon_level=defcon_level
            )
            log_cognitive_attempt(conn, query, defcon_level, regime, asset, result, elapsed_ms(), snippet_count, cost_usd, bundle_id)
            return result
        except Exception as e:
            logger.error(f"[GATEWAY] P5 ERROR: {e}")
            result = NoSignal.create(
                reason=f"GROUNDING_ERROR: {str(e)}",
                defcon_level=defcon_level
            )
            log_cognitive_attempt(conn, query, defcon_level, regime, asset, result, elapsed_ms(), snippet_count, cost_usd, bundle_id)
            return result

        # === P6: SIGNAL OUTPUT ===
        # Calculate query cost (includes FINN LLM cost)
        finn_cost = reasoning_result.cost_usd if reasoning_result else 0.0
        embedding_cost = 0.001  # Approximate embedding cost
        query_cost_usd = finn_cost + embedding_cost
        cost_usd = query_cost_usd

        if query_cost_usd > QUERY_COST_CAP_USD:
            logger.warning(f"[GATEWAY] P6 ABORT: Cost cap exceeded (${query_cost_usd})")
            result = NoSignal.create(
                reason=f"COST_CAP_EXCEEDED: ${query_cost_usd}",
                defcon_level=defcon_level
            )
            log_cognitive_attempt(conn, query, defcon_level, regime, asset, result, elapsed_ms(), snippet_count, cost_usd, bundle_id)
            return result

        # Map FINN signal to SignalAction
        signal_action_map = {
            'BUY': SignalAction.BUY,
            'SELL': SignalAction.SELL,
            'HOLD': SignalAction.HOLD,
            'NO_SIGNAL': SignalAction.NO_SIGNAL
        }
        finn_signal = reasoning_result.signal_action if reasoning_result else 'HOLD'
        signal_action = signal_action_map.get(finn_signal, SignalAction.HOLD)

        # Use FINN confidence if available, otherwise GCR
        signal_confidence = reasoning_result.signal_confidence if reasoning_result else gcr

        # CEO-DIR-2026-032: Apply calibration gate enforcement
        # Prevents "Algorithmic Arrogance" - caps confidence at proven accuracy levels
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT adjusted_confidence, was_capped, gate_id, match_type
                FROM fhq_governance.enforce_calibration_gate(%s, %s, %s, %s)
            """, (str(uuid.uuid4()), signal_confidence, 'PRICE_DIRECTION', regime or 'ALL'))
            gate_result = cursor.fetchone()
            cursor.close()

            if gate_result and gate_result[1]:  # was_capped
                original_confidence = signal_confidence
                signal_confidence = float(gate_result[0])
                logger.info(f"[GATEWAY] CALIBRATION_GATE: {original_confidence*100:.1f}% -> {signal_confidence*100:.1f}% (match={gate_result[3]})")
        except Exception as e:
            logger.warning(f"[GATEWAY] Calibration gate check failed: {e}")
            # Fallback: apply conservative ceiling if gate check fails
            signal_confidence = min(signal_confidence, 0.50)

        # Create SignalEnvelope
        envelope = SignalEnvelope.create(
            asset=asset or "UNKNOWN",
            regime=regime,
            defcon_level=defcon_level,
            action=signal_action,
            confidence=signal_confidence,
            bundle_id=evidence_bundle.bundle_id,
            snippet_ids=list(snippet_ids),
            draft_claims=list(draft_claims),
            verified_claims=verified_claims,
            grounding_result=grounding_result,
            signed_by="FINN",
            query_cost_usd=query_cost_usd
        )

        # Store evidence bundle (court-proof)
        try:
            store_evidence_bundle(conn, envelope)
            logger.info(f"[GATEWAY] P6 PASS: Evidence bundle stored ({envelope.bundle_id})")
        except Exception as e:
            logger.warning(f"[GATEWAY] P6 WARNING: Evidence storage failed ({e})")

        # === MODE-DEPENDENT RETURN ===
        if COGNITIVE_ENGINE_MODE == 'SHADOW':
            logger.info(f"[GATEWAY] Mode=SHADOW, returning NoSignal (envelope stored)")
            result = NoSignal.create(
                reason="SHADOW_MODE",
                defcon_level=defcon_level,
                shadow_envelope=envelope
            )
            log_cognitive_attempt(conn, query, defcon_level, regime, asset, result, elapsed_ms(), snippet_count, cost_usd, bundle_id)
            return result

        # LIVE mode - return real signal
        logger.info(f"[GATEWAY] Mode=LIVE, returning SignalEnvelope")
        log_cognitive_attempt(conn, query, defcon_level, regime, asset, envelope, elapsed_ms(), snippet_count, cost_usd, bundle_id)
        return envelope

    except Exception as e:
        logger.error(f"[GATEWAY] UNEXPECTED ERROR: {e}")
        result = NoSignal.create(
            reason=f"GATEWAY_ERROR: {str(e)}",
            defcon_level=defcon_level if 'defcon_level' in dir() else DEFCONLevel.GREEN
        )
        if conn:
            try:
                log_cognitive_attempt(conn, query, defcon_level, regime, asset, result, elapsed_ms(), snippet_count, cost_usd, bundle_id)
            except:
                pass
        return result

    finally:
        if conn:
            conn.close()


def store_evidence_bundle(conn, envelope: SignalEnvelope) -> None:
    """Store evidence bundle to evidence_bundles table (court-proof)."""
    cursor = conn.cursor()
    # Convert all UUIDs to strings for psycopg2 compatibility
    snippet_ids_str = [str(sid) for sid in envelope.snippet_ids] if envelope.snippet_ids else []
    cursor.execute("""
        INSERT INTO fhq_canonical.evidence_bundles (
            bundle_id, query_text, snippet_ids, defcon_level, query_cost_usd, created_at
        ) VALUES (%s, '', %s::uuid[], %s, %s, %s)
        ON CONFLICT (bundle_id) DO NOTHING
    """, [
        str(envelope.bundle_id),  # Convert UUID to string for psycopg2
        snippet_ids_str,  # List of UUID strings
        envelope.defcon_level.value if hasattr(envelope.defcon_level, 'value') else str(envelope.defcon_level),
        envelope.query_cost_usd,
        envelope.timestamp.isoformat() if hasattr(envelope.timestamp, 'isoformat') else str(envelope.timestamp)
    ])
    conn.commit()
    cursor.close()


def update_query_result(
    conn, bundle_id: str, result_type: str, snippet_count: int
) -> None:
    """
    Update existing query log entry with result info.
    Called after cognitive cycle completes (success or failure).
    """
    if not bundle_id:
        return

    cursor = conn.cursor()
    ecr = snippet_count / 3.0 if snippet_count else 0.0  # ECR = snippets / expected minimum (3)

    try:
        cursor.execute("""
            UPDATE fhq_governance.inforage_query_log
            SET result_type = %s,
                evidence_coverage_ratio = %s,
                retrieved_snippet_count = %s
            WHERE bundle_id = %s
        """, [result_type, ecr, snippet_count, bundle_id])
        conn.commit()
    except Exception as e:
        logger.warning(f"Failed to update query result: {e}")
        conn.rollback()
    finally:
        cursor.close()


def log_cognitive_query(
    conn, query: str, defcon_level: DEFCONLevel, regime: str, asset: Optional[str],
    envelope: SignalEnvelope, latency_ms: float, snippet_count: int
) -> None:
    """Log cognitive query to inforage_query_log."""
    cursor = conn.cursor()

    result_type = 'SIGNAL' if isinstance(envelope, SignalEnvelope) else 'NO_SIGNAL'
    ecr = snippet_count / 3.0  # ECR = snippets / expected minimum (3)

    cursor.execute("""
        INSERT INTO fhq_governance.inforage_query_log (
            query_id, query_text, defcon_level, latency_ms, cost_usd,
            result_type, evidence_coverage_ratio, retrieved_snippet_count, bundle_id, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    """, [
        str(uuid.uuid4()),
        query[:500],  # Truncate
        defcon_level.value if hasattr(defcon_level, 'value') else str(defcon_level),
        latency_ms,
        envelope.query_cost_usd,
        result_type,
        ecr,
        snippet_count,
        str(envelope.bundle_id)  # Convert UUID to string for psycopg2
    ])
    conn.commit()
    cursor.close()


# =============================================================================
# MAIN (Testing)
# =============================================================================

def main():
    """Test the cognitive gateway."""
    print("=" * 70)
    print("FINN COGNITIVE GATEWAY TEST")
    print("CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001")
    print(f"Mode: {COGNITIVE_ENGINE_MODE}")
    print("=" * 70)

    # Test with a sample query
    result = run_cognitive_cycle(
        query="What is BTC outlook given current NEUTRAL regime?",
        defcon_level=DEFCONLevel.YELLOW,
        regime="NEUTRAL",
        asset="BTC-USD"
    )

    print(f"\nResult type: {type(result).__name__}")

    if isinstance(result, NoSignal):
        print(f"Reason: {result.reason}")
        if result.shadow_envelope:
            print(f"Shadow envelope bundle_id: {result.shadow_envelope.bundle_id}")
    else:
        print(f"Signal ID: {result.signal_id}")
        print(f"Action: {result.action}")
        print(f"Confidence: {result.confidence}")
        print(f"IKEA Verified: {result.ikea_verified}")
        print(f"Bundle ID: {result.bundle_id}")


if __name__ == '__main__':
    main()
