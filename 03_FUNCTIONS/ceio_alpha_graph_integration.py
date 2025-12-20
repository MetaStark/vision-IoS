"""
CEIO Alpha Graph Integration Layer

Connects the CEIO Engine to IoS-007 Alpha Graph infrastructure.
Provides:
- Subgraph extraction (2-hop expansion from query entities)
- Edge weight retrieval from vision_signals.alpha_graph_edges
- Node freshness tracking
- Database persistence of entropy snapshots and reward traces

Reference: ADR-020 (ACI Protocol), IoS-007 (Alpha Graph)
Authority: VISION-IOS CSO Directive 2025-12-08
Executor: STIG (CTO)
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple, Set, Any
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

from ceio_entropy_engine import (
    CEIOConfig,
    EdgeData,
    EntropySnapshot,
    RewardTrace,
    BehaviorClass,
    RegimeSignal,
    RegimeAction,
    calculate_structural_causal_entropy,
    classify_entropy_regime,
    calculate_graph_coverage,
    calculate_ceio_reward,
    compute_entropy_snapshot,
    compute_reward_trace
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CEIO_ALPHA_GRAPH")


# ============================================================================
# DATABASE CONNECTION
# ============================================================================

def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('PGHOST', '127.0.0.1'),
        port=os.getenv('PGPORT', '54322'),
        dbname=os.getenv('PGDATABASE', 'postgres'),
        user=os.getenv('PGUSER', 'postgres'),
        password=os.getenv('PGPASSWORD', 'postgres')
    )


@contextmanager
def db_cursor():
    """Context manager for database operations."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================================
# HYPERPARAMETER LOADING
# ============================================================================

def load_active_config() -> CEIOConfig:
    """
    Load active CEIO configuration from database.

    Returns:
        CEIOConfig with current hyperparameters
    """
    with db_cursor() as cur:
        cur.execute("""
            SELECT
                r_kb_positive, r_kb_negative, api_max,
                alpha, beta, t_min, t_max,
                gamma, h_sc_threshold,
                r_signal_profit, r_signal_direction,
                r_signal_neutral, r_signal_loss
            FROM fhq_optimization.ceio_hyperparameters
            WHERE is_active = true
            LIMIT 1
        """)

        row = cur.fetchone()
        if not row:
            logger.warning("No active CEIO config found, using defaults")
            return CEIOConfig()

        return CEIOConfig(
            r_kb_positive=float(row['r_kb_positive']),
            r_kb_negative=float(row['r_kb_negative']),
            api_max=int(row['api_max']),
            alpha=float(row['alpha']),
            beta=float(row['beta']),
            t_min=int(row['t_min']),
            t_max=int(row['t_max']),
            gamma=float(row['gamma']),
            h_sc_threshold=float(row['h_sc_threshold']),
            r_signal_profit=float(row['r_signal_profit']),
            r_signal_direction=float(row['r_signal_direction']),
            r_signal_neutral=float(row['r_signal_neutral']),
            r_signal_loss=float(row['r_signal_loss'])
        )


# ============================================================================
# ALPHA GRAPH SUBGRAPH EXTRACTION
# ============================================================================

def expand_2hop_neighbors(
    start_entities: List[str],
    max_nodes: int = 100
) -> Tuple[Set[str], List[EdgeData]]:
    """
    Extract 2-hop subgraph from Alpha Graph starting from query entities.

    This implements the N_focus calculation for C_FHQ denominator.
    Critical for preventing coverage gaming.

    Args:
        start_entities: Starting entity IDs (query-relevant)
        max_nodes: Maximum nodes to include (prevents explosion)

    Returns:
        Tuple of (focus_nodes set, active_edges list)
    """
    focus_nodes = set(start_entities)
    active_edges = []

    with db_cursor() as cur:
        # Check if alpha_graph_edges table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'vision_signals'
                AND table_name = 'alpha_graph_edges'
            )
        """)

        if not cur.fetchone()['exists']:
            logger.warning("alpha_graph_edges table not found, returning empty subgraph")
            return focus_nodes, active_edges

        # 1-hop expansion
        cur.execute("""
            SELECT
                source_node,
                target_node,
                edge_type,
                confidence,
                COALESCE(causal_weight, 0.5) as causal_weight
            FROM vision_signals.alpha_graph_edges
            WHERE source_node = ANY(%s) OR target_node = ANY(%s)
            AND is_active = true
            LIMIT %s
        """, (list(start_entities), list(start_entities), max_nodes * 2))

        hop1_edges = cur.fetchall()

        for row in hop1_edges:
            focus_nodes.add(row['source_node'])
            focus_nodes.add(row['target_node'])
            active_edges.append(EdgeData(
                source=row['source_node'],
                target=row['target_node'],
                edge_type=row['edge_type'],
                probability=float(row['confidence']),
                weight=float(row['causal_weight'])
            ))

        if len(focus_nodes) >= max_nodes:
            return focus_nodes, active_edges

        # 2-hop expansion
        hop1_nodes = focus_nodes - set(start_entities)
        if hop1_nodes:
            cur.execute("""
                SELECT
                    source_node,
                    target_node,
                    edge_type,
                    confidence,
                    COALESCE(causal_weight, 0.5) as causal_weight
                FROM vision_signals.alpha_graph_edges
                WHERE (source_node = ANY(%s) OR target_node = ANY(%s))
                AND source_node NOT IN %s
                AND target_node NOT IN %s
                AND is_active = true
                LIMIT %s
            """, (
                list(hop1_nodes),
                list(hop1_nodes),
                tuple(start_entities) if len(start_entities) > 0 else ('__none__',),
                tuple(start_entities) if len(start_entities) > 0 else ('__none__',),
                max_nodes
            ))

            hop2_edges = cur.fetchall()

            for row in hop2_edges:
                if len(focus_nodes) >= max_nodes:
                    break
                focus_nodes.add(row['source_node'])
                focus_nodes.add(row['target_node'])
                active_edges.append(EdgeData(
                    source=row['source_node'],
                    target=row['target_node'],
                    edge_type=row['edge_type'],
                    probability=float(row['confidence']),
                    weight=float(row['causal_weight'])
                ))

    return focus_nodes, active_edges


def get_node_freshness(node_ids: List[str]) -> Dict[str, datetime]:
    """
    Get freshness timestamps for nodes.

    Args:
        node_ids: List of node IDs to check

    Returns:
        Dict mapping node_id -> last_update_timestamp
    """
    if not node_ids:
        return {}

    freshness = {}

    with db_cursor() as cur:
        # Check alpha_graph_nodes table
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'vision_signals'
                AND table_name = 'alpha_graph_nodes'
            )
        """)

        if cur.fetchone()['exists']:
            cur.execute("""
                SELECT node_id, updated_at
                FROM vision_signals.alpha_graph_nodes
                WHERE node_id = ANY(%s)
            """, (node_ids,))

            for row in cur.fetchall():
                freshness[row['node_id']] = row['updated_at']

    # For nodes without records, assume stale (24h ago)
    default_time = datetime.now(timezone.utc)
    for node_id in node_ids:
        if node_id not in freshness:
            freshness[node_id] = default_time

    return freshness


# ============================================================================
# SHADOW LEDGER INTEGRATION (CEO DIRECTIVE 001-CEIO FIX)
# ============================================================================
# Fix Date: 2025-12-08
# Issue: shadow_ledger table was empty - no bridge between CEIO hypotheses and P&L tracking
# Resolution: Added create_shadow_position() and close_shadow_position() functions
# Authority: CEO Directive

def create_shadow_position(
    hypothesis_id: str,
    hypothesis_type: str,  # 'ALPHA_SIGNAL', 'REGIME_CALL', 'CORRELATION'
    asset_id: str,
    direction: str,        # 'LONG', 'SHORT', 'NEUTRAL'
    confidence: float,
    entry_price: float,
    ceio_trace_id: Optional[str] = None,
    entropy_snapshot_id: Optional[str] = None
) -> str:
    """
    Create shadow position in CEIO shadow_ledger.

    This bridges CEIO research hypotheses to P&L tracking.
    Required for CEIO learning loop per CEO DIRECTIVE 001-CEIO.

    Args:
        hypothesis_id: Unique ID for this hypothesis
        hypothesis_type: Type of research hypothesis
        asset_id: Asset being analyzed
        direction: Trade direction implied by hypothesis
        confidence: Confidence level (0-1)
        entry_price: Current price at hypothesis time
        ceio_trace_id: Optional link to reward_traces
        entropy_snapshot_id: Optional link to entropy_snapshots

    Returns:
        ledger_id
    """
    ledger_id = str(uuid.uuid4())

    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_optimization.shadow_ledger (
                ledger_id,
                ceio_trace_id,
                entropy_snapshot_id,
                hypothesis_id,
                hypothesis_type,
                asset_id,
                direction,
                confidence,
                shadow_entry_price,
                shadow_entry_time,
                status,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), 'OPEN', NOW()
            )
        """, (
            ledger_id,
            ceio_trace_id,
            entropy_snapshot_id,
            hypothesis_id,
            hypothesis_type,
            asset_id,
            direction,
            confidence,
            entry_price
        ))

    logger.info(f"Shadow position CREATED: {ledger_id[:8]}... {direction} {asset_id} @ {entry_price}")
    return ledger_id


def close_shadow_position(
    ledger_id: str,
    exit_price: float,
    exit_reason: str = 'MANUAL'
) -> Dict[str, Any]:
    """
    Close shadow position and calculate shadow P&L.

    Args:
        ledger_id: Shadow position to close
        exit_price: Current price at close time
        exit_reason: Reason for closing ('TARGET_HIT', 'STOP_LOSS', 'TIME_EXPIRY',
                     'DEFCON_ESCALATION', 'H_SC_ABORT', 'MANUAL')

    Returns:
        Dict with shadow_pnl and shadow_return_pct
    """
    with db_cursor() as cur:
        # Get entry data
        cur.execute("""
            SELECT direction, shadow_entry_price
            FROM fhq_optimization.shadow_ledger
            WHERE ledger_id = %s AND status = 'OPEN'
        """, (ledger_id,))

        row = cur.fetchone()
        if not row:
            raise ValueError(f"Shadow position {ledger_id} not found or not OPEN")

        entry_price = float(row['shadow_entry_price'])
        direction = row['direction']

        # Calculate shadow P&L
        if direction == 'LONG':
            shadow_pnl = exit_price - entry_price
            shadow_return_pct = (exit_price - entry_price) / entry_price if entry_price > 0 else 0.0
        elif direction == 'SHORT':
            shadow_pnl = entry_price - exit_price
            shadow_return_pct = (entry_price - exit_price) / entry_price if entry_price > 0 else 0.0
        else:  # NEUTRAL
            shadow_pnl = 0.0
            shadow_return_pct = 0.0

        # Update position
        cur.execute("""
            UPDATE fhq_optimization.shadow_ledger
            SET shadow_exit_price = %s,
                shadow_exit_time = NOW(),
                shadow_pnl = %s,
                shadow_return_pct = %s,
                status = 'CLOSED',
                exit_reason = %s,
                updated_at = NOW()
            WHERE ledger_id = %s
        """, (exit_price, shadow_pnl, shadow_return_pct, exit_reason, ledger_id))

    logger.info(f"Shadow position CLOSED: {ledger_id[:8]}... P&L={shadow_pnl:.4f} ({shadow_return_pct:.2%})")

    return {
        'ledger_id': ledger_id,
        'shadow_pnl': shadow_pnl,
        'shadow_return_pct': shadow_return_pct,
        'exit_reason': exit_reason
    }


def get_open_shadow_positions(asset_id: Optional[str] = None) -> List[Dict]:
    """
    Get all open shadow positions, optionally filtered by asset.

    Args:
        asset_id: Optional asset filter

    Returns:
        List of open shadow positions
    """
    with db_cursor() as cur:
        if asset_id:
            cur.execute("""
                SELECT * FROM fhq_optimization.shadow_ledger
                WHERE status = 'OPEN' AND asset_id = %s
                ORDER BY created_at DESC
            """, (asset_id,))
        else:
            cur.execute("""
                SELECT * FROM fhq_optimization.shadow_ledger
                WHERE status = 'OPEN'
                ORDER BY created_at DESC
            """)

        return [dict(row) for row in cur.fetchall()]


def expire_stale_shadow_positions(max_age_hours: int = 24) -> int:
    """
    Expire shadow positions older than max_age_hours.

    Args:
        max_age_hours: Maximum age before expiring

    Returns:
        Number of positions expired
    """
    with db_cursor() as cur:
        cur.execute("""
            UPDATE fhq_optimization.shadow_ledger
            SET status = 'EXPIRED',
                exit_reason = 'TIME_EXPIRY',
                updated_at = NOW()
            WHERE status = 'OPEN'
            AND created_at < NOW() - INTERVAL '%s hours'
            RETURNING ledger_id
        """, (max_age_hours,))

        expired = cur.fetchall()
        count = len(expired)

        if count > 0:
            logger.info(f"Expired {count} stale shadow positions (>{max_age_hours}h old)")

        return count


# ============================================================================
# DATABASE PERSISTENCE
# ============================================================================

def save_entropy_snapshot(snapshot: EntropySnapshot) -> str:
    """
    Save entropy snapshot to database.

    Args:
        snapshot: EntropySnapshot to persist

    Returns:
        snapshot_id
    """
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_optimization.entropy_snapshots (
                snapshot_id,
                session_id,
                agent_id,
                query_entities,
                focus_nodes_count,
                active_edges_count,
                h_sc,
                h_sc_components,
                regime_signal,
                regime_action,
                calculation_timestamp
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            snapshot.snapshot_id,
            snapshot.session_id,
            'CEIO_ENGINE',
            [],  # Will be set by caller
            snapshot.focus_nodes_count,
            snapshot.active_edges_count,
            snapshot.h_sc,
            psycopg2.extras.Json(snapshot.components),
            snapshot.regime_signal.value,
            snapshot.regime_action.value,
            snapshot.timestamp
        ))

    return snapshot.snapshot_id


def save_reward_trace(trace: RewardTrace, entropy_snapshot_id: Optional[str] = None) -> str:
    """
    Save reward trace to database.

    Args:
        trace: RewardTrace to persist
        entropy_snapshot_id: Optional linked entropy snapshot

    Returns:
        trace_id
    """
    with db_cursor() as cur:
        # Get config_id for active config
        cur.execute("""
            SELECT config_id FROM fhq_optimization.ceio_hyperparameters
            WHERE is_active = true LIMIT 1
        """)
        config_row = cur.fetchone()
        config_id = config_row['config_id'] if config_row else None

        cur.execute("""
            INSERT INTO fhq_optimization.reward_traces (
                trace_id,
                agent_id,
                session_id,
                timestamp_utc,
                input_query,
                retrieval_count,
                steps_taken,
                structural_entropy,
                graph_coverage_pct,
                outcome_signal,
                r_outcome,
                r_scent,
                r_internal,
                efficiency_factor,
                r_total,
                config_id,
                alpha_val,
                beta_val,
                gamma_val,
                entropy_snapshot_id,
                behavior_class,
                behavior_label
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s
            )
        """, (
            trace.trace_id,
            trace.agent_id,
            trace.session_id,
            trace.timestamp,
            trace.input_query,
            trace.retrieval_count,
            trace.steps_taken,
            trace.structural_entropy,
            trace.graph_coverage,
            trace.outcome_signal,
            trace.r_outcome,
            trace.r_scent,
            trace.r_internal,
            trace.efficiency_factor,
            trace.r_total,
            config_id,
            trace.config.alpha,
            trace.config.beta,
            trace.config.gamma,
            entropy_snapshot_id,
            trace.behavior_class.value,
            trace.behavior_class.name
        ))

    return trace.trace_id


# ============================================================================
# HIGH-LEVEL API
# ============================================================================

def analyze_query(
    session_id: str,
    agent_id: str,
    query: str,
    query_entities: List[str],
    steps_taken: int,
    api_calls: int,
    signal_score: float,
    signal_correct: bool,
    # Shadow ledger integration (CEO DIRECTIVE 001-CEIO FIX)
    asset_id: Optional[str] = None,
    direction: Optional[str] = None,  # 'LONG', 'SHORT', 'NEUTRAL'
    entry_price: Optional[float] = None,
    create_shadow: bool = True,
    persist: bool = True
) -> Tuple[RewardTrace, EntropySnapshot, Optional[str]]:
    """
    Complete CEIO analysis for a research query.

    This is the main entry point for integrating CEIO with the research agent.

    UPDATED (CEO DIRECTIVE 001-CEIO FIX): Now supports automatic shadow position
    creation for P&L tracking and CEIO learning loop.

    Args:
        session_id: Unique session identifier
        agent_id: Agent performing the research
        query: The research query
        query_entities: Starting entities for subgraph extraction
        steps_taken: Number of reasoning steps
        api_calls: Number of external API calls
        signal_score: Outcome signal score
        signal_correct: Whether signal was correct
        asset_id: Asset for shadow position (optional)
        direction: Trade direction 'LONG', 'SHORT', 'NEUTRAL' (optional)
        entry_price: Current price for shadow entry (optional)
        create_shadow: Whether to create shadow position (default True)
        persist: Whether to save to database

    Returns:
        Tuple of (RewardTrace, EntropySnapshot, shadow_ledger_id or None)
    """
    # Load config
    config = load_active_config()

    # Extract subgraph
    focus_nodes, active_edges = expand_2hop_neighbors(query_entities)

    # Get node freshness
    freshness = get_node_freshness(list(focus_nodes))

    # Calculate metrics
    h_sc, h_sc_components = calculate_structural_causal_entropy(active_edges)
    regime_signal, regime_action = classify_entropy_regime(h_sc, config)
    coverage = calculate_graph_coverage(list(focus_nodes), freshness)

    # Build entropy snapshot
    entropy_snapshot = EntropySnapshot(
        snapshot_id=str(uuid.uuid4()),
        session_id=session_id,
        h_sc=h_sc,
        focus_nodes_count=len(focus_nodes),
        active_edges_count=len(active_edges),
        regime_signal=regime_signal,
        regime_action=regime_action,
        components=h_sc_components
    )

    # Compute reward trace
    reward_trace = compute_reward_trace(
        session_id=session_id,
        agent_id=agent_id,
        input_query=query,
        steps_taken=steps_taken,
        api_calls=api_calls,
        signal_score=signal_score,
        signal_correct=signal_correct,
        graph_coverage=coverage,
        structural_entropy=h_sc,
        config=config
    )

    # Persist if requested
    if persist:
        try:
            save_entropy_snapshot(entropy_snapshot)
            save_reward_trace(reward_trace, entropy_snapshot.snapshot_id)
            logger.info(f"Saved CEIO analysis: trace={reward_trace.trace_id}, entropy={entropy_snapshot.snapshot_id}")
        except Exception as e:
            logger.error(f"Failed to persist CEIO analysis: {e}")

    # CEO DIRECTIVE 001-CEIO FIX: Create shadow position if enabled and parameters provided
    shadow_ledger_id = None
    if create_shadow and direction and asset_id and entry_price is not None:
        # Check if entropy regime allows shadow position (abort on CHAOS)
        if entropy_snapshot.regime_action != RegimeAction.ABORT:
            try:
                shadow_ledger_id = create_shadow_position(
                    hypothesis_id=str(uuid.uuid4()),
                    hypothesis_type='ALPHA_SIGNAL',
                    asset_id=asset_id,
                    direction=direction,
                    confidence=min(1.0, max(0.0, abs(signal_score))),
                    entry_price=entry_price,
                    ceio_trace_id=reward_trace.trace_id if persist else None,
                    entropy_snapshot_id=entropy_snapshot.snapshot_id if persist else None
                )
                logger.info(f"Shadow position created: {shadow_ledger_id[:8]}...")
            except Exception as e:
                logger.error(f"Failed to create shadow position: {e}")
        else:
            logger.warning(f"Shadow position BLOCKED: H_sc regime is CHAOS/ABORT")

    return reward_trace, entropy_snapshot, shadow_ledger_id


def should_abort_research(h_sc: float, config: Optional[CEIOConfig] = None) -> bool:
    """
    Check if research should be aborted due to high entropy (Chaos regime).

    This implements the "Stop-Loss on Research" risk mitigation.

    Args:
        h_sc: Current structural entropy
        config: CEIO hyperparameters

    Returns:
        True if research should abort, False otherwise
    """
    if config is None:
        config = load_active_config()

    _, action = classify_entropy_regime(h_sc, config)
    return action == RegimeAction.ABORT


# ============================================================================
# TESTING / VALIDATION
# ============================================================================

def test_integration():
    """Test the integration layer."""
    logger.info("=== CEIO Alpha Graph Integration Test ===")

    # Test config loading
    config = load_active_config()
    logger.info(f"Loaded config: alpha={config.alpha}, beta={config.beta}")

    # Test subgraph extraction (will return empty if no data)
    focus_nodes, edges = expand_2hop_neighbors(['BTC-USD', 'NVDA'])
    logger.info(f"Subgraph: {len(focus_nodes)} nodes, {len(edges)} edges")

    # Test analysis (mock) - without shadow position
    session_id = str(uuid.uuid4())
    trace, snapshot, shadow_id = analyze_query(
        session_id=session_id,
        agent_id='TEST_AGENT',
        query='Test query: BTC vs NVDA correlation',
        query_entities=['BTC-USD', 'NVDA'],
        steps_taken=3,
        api_calls=1,
        signal_score=1.0,
        signal_correct=True,
        create_shadow=False,  # Don't create shadow for basic test
        persist=False
    )

    logger.info(f"Reward: {trace.r_total:.4f}")
    logger.info(f"Behavior: {trace.behavior_class.name}")
    logger.info(f"Entropy: {snapshot.h_sc:.4f}")
    logger.info(f"Regime: {snapshot.regime_signal.value} -> {snapshot.regime_action.value}")

    # Test abort check
    should_abort = should_abort_research(0.9)
    logger.info(f"Should abort at H_sc=0.9: {should_abort}")

    logger.info("=== Integration Test Complete ===")


def test_shadow_ledger():
    """
    Test shadow ledger integration (CEO DIRECTIVE 001-CEIO FIX).

    Creates a shadow position, then closes it to verify P&L calculation.
    """
    logger.info("=== CEIO Shadow Ledger Test ===")

    # Test 1: Create shadow position via analyze_query
    session_id = str(uuid.uuid4())
    trace, snapshot, shadow_id = analyze_query(
        session_id=session_id,
        agent_id='CEIO_TEST',
        query='Test: BTC bullish signal',
        query_entities=['BTC-USD'],
        steps_taken=2,
        api_calls=0,
        signal_score=0.85,
        signal_correct=True,
        asset_id='BTC-USD',
        direction='LONG',
        entry_price=98000.0,
        create_shadow=True,
        persist=True
    )

    logger.info(f"Shadow position ID: {shadow_id}")

    if shadow_id:
        # Test 2: Close shadow position with profit
        result = close_shadow_position(
            ledger_id=shadow_id,
            exit_price=99500.0,
            exit_reason='TARGET_HIT'
        )

        logger.info(f"Shadow P&L: ${result['shadow_pnl']:.2f}")
        logger.info(f"Shadow Return: {result['shadow_return_pct']:.2%}")

        # Verify in database
        with db_cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) as cnt FROM fhq_optimization.shadow_ledger
                WHERE status = 'CLOSED'
            """)
            count = cur.fetchone()['cnt']
            logger.info(f"Total closed shadow positions: {count}")

    logger.info("=== Shadow Ledger Test Complete ===")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--shadow':
        test_shadow_ledger()
    else:
        test_integration()
