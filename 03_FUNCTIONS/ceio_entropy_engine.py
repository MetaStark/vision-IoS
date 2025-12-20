"""
CEIO (Causal-Entropy Information Optimization) Engine

Implements the reward function for FHQ's autonomous research agent.
Synthesizes:
- IKEA Protocol (Knowledge Boundary Awareness) - Huang et al., ICLR 2026
- InForage Logic (Information Scent Optimization) - Qian & Liu, NeurIPS 2025
- Structural Causal Entropy (H_sc) - FHQ Definition

Master Equation:
    R_CEIO = β^max(0,T-2) · (r_signal + α·C_FHQ + γ·r_kb)

Reference: ADR-020 (ACI Protocol), IoS-007 (Alpha Graph)
Authority: VISION-IOS CSO Directive 2025-12-08
Executor: STIG (CTO)
"""

import math
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CEIO_ENGINE")


# ============================================================================
# ENUMS & CONSTANTS
# ============================================================================

class BehaviorClass(Enum):
    """IKEA Behavior Classification per ICLR 2026 paper."""
    PERFECT_EFFICIENCY = 1  # Correct signal + Internal knowledge
    FAILURE = 2             # Incorrect signal
    NECESSARY_SEARCH = 3    # Correct signal + Successful external search
    EXCESSIVE_SEARCH = 4    # Correct signal + Too many API calls


class RegimeSignal(Enum):
    """Structural Entropy Regime Classification."""
    CLEAR_TREND = "CLEAR_TREND"  # H_sc low - strong causal structure
    CHOPPY = "CHOPPY"            # H_sc medium - mixed signals
    CHAOS = "CHAOS"              # H_sc high - no clear causality


class RegimeAction(Enum):
    """Action recommendation based on entropy regime."""
    PROCEED = "PROCEED"    # Clear signal, continue
    CAUTION = "CAUTION"    # Mixed signal, reduce confidence
    ABORT = "ABORT"        # Chaos regime, go to cash


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class CEIOConfig:
    """CEIO Hyperparameters (mirrors fhq_optimization.ceio_hyperparameters)."""
    # IKEA Parameters
    r_kb_positive: float = 0.50
    r_kb_negative: float = 0.05
    api_max: int = 5

    # InForage Parameters
    alpha: float = 0.30    # Graph coverage weight (paper: 0.20)
    beta: float = 0.90     # Efficiency decay (paper: 0.95)
    t_min: int = 2         # Minimum steps
    t_max: int = 4         # Maximum steps

    # Structural Causal Entropy
    gamma: float = 1.00    # Internal knowledge weight
    h_sc_threshold: float = 0.80  # Chaos threshold

    # Signal Rewards
    r_signal_profit: float = 1.00
    r_signal_direction: float = 0.50
    r_signal_neutral: float = 0.00
    r_signal_loss: float = -1.00


@dataclass
class EdgeData:
    """Represents an edge in the Alpha Graph subgraph."""
    source: str
    target: str
    edge_type: str         # 'LEADS', 'CORRELATES', 'INVERSE', etc.
    probability: float     # P(e) - confidence in edge
    weight: float          # w_causal(e) - ontology weight

    @property
    def causal_weight(self) -> float:
        """Map edge type to causal weight."""
        weights = {
            'LEADS': 1.0,
            'CAUSES': 1.0,
            'CORRELATES': 0.5,
            'INVERSE': 0.7,
            'LAGS': 0.6,
            'UNKNOWN': 0.1
        }
        return weights.get(self.edge_type, 0.5)


@dataclass
class EntropySnapshot:
    """Result of structural entropy calculation."""
    snapshot_id: str
    session_id: str
    h_sc: float
    focus_nodes_count: int
    active_edges_count: int
    regime_signal: RegimeSignal
    regime_action: RegimeAction
    components: Dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RewardTrace:
    """Complete CEIO reward calculation trace for audit."""
    trace_id: str
    session_id: str
    agent_id: str

    # Inputs
    input_query: str
    retrieval_count: int
    steps_taken: int

    # Calculated Metrics
    structural_entropy: float
    graph_coverage: float
    outcome_signal: float

    # Reward Components
    r_outcome: float
    r_scent: float
    r_internal: float
    efficiency_factor: float
    r_total: float

    # Classification
    behavior_class: BehaviorClass

    # Metadata
    config: CEIOConfig
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# CORE CALCULATION FUNCTIONS
# ============================================================================

def calculate_structural_causal_entropy(
    active_edges: List[EdgeData],
    normalize: bool = True
) -> Tuple[float, Dict[str, float]]:
    """
    Calculate Structural Causal Entropy (H_sc) per FHQ definition.

    H_sc(G) = -Σ P(e) · log₂(P(e)) · w_causal(e)

    This measures the entropy of the causal topology:
    - High H_sc → Chaos/Noise (uniform causality)
    - Low H_sc → Clear Signal (peaked distribution)

    Args:
        active_edges: List of edges in the reasoning subgraph
        normalize: Whether to normalize probabilities to form valid distribution

    Returns:
        Tuple of (H_sc value, per-edge contribution dict)
    """
    if not active_edges:
        return 0.0, {}

    # Calculate total probability for normalization
    total_prob = sum(e.probability for e in active_edges)
    if total_prob == 0:
        return 0.0, {}

    entropy = 0.0
    components = {}

    for edge in active_edges:
        # Normalize probability P(e)
        if normalize:
            p_e = edge.probability / total_prob
        else:
            p_e = edge.probability

        # Get causal weight
        w_c = edge.causal_weight

        if p_e > 0:
            # H_sc formula: -Σ P(e) · log₂(P(e)) · w_c
            term = -p_e * math.log2(p_e) * w_c
            entropy += term

            edge_key = f"{edge.source}->{edge.target}"
            components[edge_key] = term

    return entropy, components


def classify_entropy_regime(
    h_sc: float,
    config: CEIOConfig
) -> Tuple[RegimeSignal, RegimeAction]:
    """
    Classify entropy regime and determine action.

    Args:
        h_sc: Structural Causal Entropy value
        config: CEIO hyperparameters

    Returns:
        Tuple of (RegimeSignal, RegimeAction)
    """
    # Thresholds (can be tuned)
    chaos_threshold = config.h_sc_threshold  # 0.80 default
    choppy_threshold = chaos_threshold * 0.5  # 0.40 default

    if h_sc >= chaos_threshold:
        return RegimeSignal.CHAOS, RegimeAction.ABORT
    elif h_sc >= choppy_threshold:
        return RegimeSignal.CHOPPY, RegimeAction.CAUTION
    else:
        return RegimeSignal.CLEAR_TREND, RegimeAction.PROCEED


def calculate_graph_coverage(
    focus_nodes: List[str],
    node_freshness: Dict[str, datetime],
    freshness_threshold_hours: int = 24
) -> float:
    """
    Calculate Graph Coverage (C_FHQ) with 2-hop focus.

    C_FHQ = |{n ∈ N_focus : freshness(n) < threshold}| / |N_focus|

    CRITICAL: Denominator is N_focus (query-relevant subgraph), NOT entire graph.
    This fixes the coverage gaming vulnerability.

    Args:
        focus_nodes: List of node IDs in the 2-hop subgraph
        node_freshness: Dict mapping node_id -> last_update_timestamp
        freshness_threshold_hours: How recent data must be (default 24h)

    Returns:
        Coverage ratio (0.0 - 1.0)
    """
    if not focus_nodes:
        return 0.0

    threshold = datetime.now(timezone.utc) - timedelta(hours=freshness_threshold_hours)

    fresh_count = 0
    for node_id in focus_nodes:
        if node_id in node_freshness:
            if node_freshness[node_id] > threshold:
                fresh_count += 1

    return fresh_count / len(focus_nodes)


def calculate_knowledge_boundary_reward(
    api_calls: int,
    signal_score: float,
    config: CEIOConfig
) -> float:
    """
    Calculate IKEA Knowledge Boundary Reward (r_kb).

    r_kb = r_kb+ · (1 - API_calls/API_max) · 𝟙[r_signal > 0]

    SAFETY: Only rewards efficiency if outcome is POSITIVE.
    This prevents the "lazy loser" failure mode.

    Args:
        api_calls: Number of external API calls made
        signal_score: Outcome signal score (r_signal)
        config: CEIO hyperparameters

    Returns:
        Knowledge boundary reward value
    """
    # Only reward efficiency if signal is positive
    if signal_score <= 0:
        return 0.0

    # Linear penalty for API calls up to max
    usage_ratio = min(api_calls / config.api_max, 1.0)

    return config.r_kb_positive * (1.0 - usage_ratio)


def calculate_efficiency_decay(
    steps_taken: int,
    config: CEIOConfig
) -> float:
    """
    Calculate efficiency decay factor (β^max(0, T-2)).

    We allow T=2 steps (1 search + 1 answer) without penalty.
    Any step beyond 2 incurs the beta penalty.

    Args:
        steps_taken: Number of reasoning steps (T)
        config: CEIO hyperparameters

    Returns:
        Efficiency factor (0.0 - 1.0)
    """
    decay_exponent = max(0, steps_taken - config.t_min)
    return config.beta ** decay_exponent


def classify_behavior(
    signal_correct: bool,
    api_calls: int
) -> BehaviorClass:
    """
    Classify behavior per IKEA protocol hierarchy.

    Hierarchy: Behavior 1 > Behavior 3 > Behavior 4 > Behavior 2

    Args:
        signal_correct: Whether the signal was correct
        api_calls: Number of external API calls made

    Returns:
        BehaviorClass enum value
    """
    if signal_correct and api_calls == 0:
        return BehaviorClass.PERFECT_EFFICIENCY  # Best: correct + internal
    elif not signal_correct:
        return BehaviorClass.FAILURE  # Worst: incorrect
    elif signal_correct and api_calls <= 3:
        return BehaviorClass.NECESSARY_SEARCH  # Good: correct + reasonable search
    else:
        return BehaviorClass.EXCESSIVE_SEARCH  # Meh: correct but wasteful


# ============================================================================
# MASTER EQUATION
# ============================================================================

def calculate_ceio_reward(
    steps_taken: int,
    signal_score: float,
    graph_coverage: float,
    api_calls: int,
    config: Optional[CEIOConfig] = None
) -> Tuple[float, Dict[str, float]]:
    """
    The CEIO Master Equation Implementation.

    R_CEIO = β^max(0,T-2) · (r_signal + α·C_FHQ + γ·r_kb)

    Args:
        steps_taken: Number of reasoning steps (T)
        signal_score: Outcome signal score (r_signal)
        graph_coverage: Graph coverage ratio (C_FHQ)
        api_calls: Number of external API calls (RT)
        config: CEIO hyperparameters (uses default if None)

    Returns:
        Tuple of (total_reward, component_breakdown)
    """
    if config is None:
        config = CEIOConfig()

    # 1. Efficiency Decay
    efficiency_factor = calculate_efficiency_decay(steps_taken, config)

    # 2. Outcome Reward (r_signal)
    r_outcome = signal_score

    # 3. Scent Reward (α · C_FHQ)
    r_scent = config.alpha * graph_coverage

    # 4. Internal Knowledge Reward (γ · r_kb)
    r_kb = calculate_knowledge_boundary_reward(api_calls, signal_score, config)
    r_internal = config.gamma * r_kb

    # 5. Total Aggregation
    r_total = efficiency_factor * (r_outcome + r_scent + r_internal)

    # Component breakdown for audit
    components = {
        'efficiency_factor': efficiency_factor,
        'r_outcome': r_outcome,
        'r_scent': r_scent,
        'r_internal': r_internal,
        'r_total': r_total,
        'steps_taken': steps_taken,
        'api_calls': api_calls,
        'graph_coverage': graph_coverage
    }

    return r_total, components


# ============================================================================
# HIGH-LEVEL API
# ============================================================================

def compute_entropy_snapshot(
    session_id: str,
    query_entities: List[str],
    active_edges: List[EdgeData],
    config: Optional[CEIOConfig] = None
) -> EntropySnapshot:
    """
    Compute a complete entropy snapshot for a reasoning session.

    Args:
        session_id: Unique session identifier
        query_entities: Starting entities for subgraph
        active_edges: Edges in the reasoning subgraph
        config: CEIO hyperparameters

    Returns:
        EntropySnapshot with full analysis
    """
    if config is None:
        config = CEIOConfig()

    # Calculate H_sc
    h_sc, components = calculate_structural_causal_entropy(active_edges)

    # Classify regime
    regime_signal, regime_action = classify_entropy_regime(h_sc, config)

    # Count unique nodes
    nodes = set()
    for edge in active_edges:
        nodes.add(edge.source)
        nodes.add(edge.target)

    return EntropySnapshot(
        snapshot_id=str(uuid.uuid4()),
        session_id=session_id,
        h_sc=h_sc,
        focus_nodes_count=len(nodes),
        active_edges_count=len(active_edges),
        regime_signal=regime_signal,
        regime_action=regime_action,
        components=components
    )


def compute_reward_trace(
    session_id: str,
    agent_id: str,
    input_query: str,
    steps_taken: int,
    api_calls: int,
    signal_score: float,
    signal_correct: bool,
    graph_coverage: float,
    structural_entropy: float,
    config: Optional[CEIOConfig] = None
) -> RewardTrace:
    """
    Compute a complete reward trace for audit.

    Args:
        session_id: Unique session identifier
        agent_id: Agent performing the reasoning
        input_query: The research query
        steps_taken: Number of reasoning steps
        api_calls: Number of external API calls
        signal_score: Outcome signal score
        signal_correct: Whether signal was correct
        graph_coverage: Graph coverage ratio
        structural_entropy: H_sc value
        config: CEIO hyperparameters

    Returns:
        RewardTrace with full audit information
    """
    if config is None:
        config = CEIOConfig()

    # Calculate master equation
    r_total, components = calculate_ceio_reward(
        steps_taken=steps_taken,
        signal_score=signal_score,
        graph_coverage=graph_coverage,
        api_calls=api_calls,
        config=config
    )

    # Classify behavior
    behavior = classify_behavior(signal_correct, api_calls)

    return RewardTrace(
        trace_id=str(uuid.uuid4()),
        session_id=session_id,
        agent_id=agent_id,
        input_query=input_query,
        retrieval_count=api_calls,
        steps_taken=steps_taken,
        structural_entropy=structural_entropy,
        graph_coverage=graph_coverage,
        outcome_signal=signal_score,
        r_outcome=components['r_outcome'],
        r_scent=components['r_scent'],
        r_internal=components['r_internal'],
        efficiency_factor=components['efficiency_factor'],
        r_total=r_total,
        behavior_class=behavior,
        config=config
    )


# ============================================================================
# SCENARIO SIMULATIONS (for validation)
# ============================================================================

def simulate_scenario_a_obvious_macro():
    """
    Scenario A: The "Obvious Macro" (Bitcoin vs. Nvidia)
    Query: "Should I buy BTC based on NVDA earnings beat?"

    Path 1 (Pre-CEIO): 3 API calls, 6 steps
    Path 2 (CEIO): 1 API call, 3 steps
    """
    config = CEIOConfig()

    # Path 1: Pre-CEIO behavior
    r1, c1 = calculate_ceio_reward(
        steps_taken=6,
        signal_score=1.0,  # Correct signal
        graph_coverage=0.8,
        api_calls=3,
        config=config
    )

    # Path 2: CEIO-optimized behavior
    r2, c2 = calculate_ceio_reward(
        steps_taken=3,
        signal_score=1.0,  # Correct signal
        graph_coverage=0.8,
        api_calls=1,
        config=config
    )

    logger.info("=== Scenario A: Obvious Macro ===")
    logger.info(f"Pre-CEIO (T=6, API=3): R={r1:.4f}")
    logger.info(f"CEIO-Opt (T=3, API=1): R={r2:.4f}")
    logger.info(f"Improvement: {((r2-r1)/r1)*100:.1f}%")

    return r1, r2


def simulate_scenario_b_black_swan():
    """
    Scenario B: The "Black Swan" (Geopolitical Shock)
    Query: "Impact of unexpected coup on Oil"

    Agent must search heavily - no internal knowledge.
    """
    config = CEIOConfig()

    # Heavy search required
    r, c = calculate_ceio_reward(
        steps_taken=4,
        signal_score=1.0,  # Correct signal after research
        graph_coverage=0.9,  # High coverage achieved
        api_calls=5,  # Max API calls
        config=config
    )

    logger.info("=== Scenario B: Black Swan ===")
    logger.info(f"Heavy Search (T=4, API=5): R={r:.4f}")
    logger.info(f"r_scent saved the reward: {c['r_scent']:.4f}")
    logger.info(f"r_internal (penalized): {c['r_internal']:.4f}")

    return r, c


if __name__ == "__main__":
    # Run validation scenarios
    logger.info("CEIO Engine Validation")
    logger.info("=" * 50)

    # Test scenarios
    simulate_scenario_a_obvious_macro()
    print()
    simulate_scenario_b_black_swan()

    # Test entropy calculation
    print()
    logger.info("=== Entropy Calculation Test ===")

    test_edges = [
        EdgeData("RATES", "TECH", "LEADS", 0.8, 1.0),
        EdgeData("VIX", "SPX", "INVERSE", 0.7, 0.7),
        EdgeData("USD", "GOLD", "INVERSE", 0.6, 0.7),
        EdgeData("OIL", "INFLATION", "CORRELATES", 0.5, 0.5),
    ]

    h_sc, components = calculate_structural_causal_entropy(test_edges)
    regime_signal, regime_action = classify_entropy_regime(h_sc, CEIOConfig())

    logger.info(f"H_sc = {h_sc:.4f}")
    logger.info(f"Regime: {regime_signal.value} -> {regime_action.value}")

    # Perfect efficiency test
    print()
    logger.info("=== Behavior Classification Test ===")
    behaviors = [
        (True, 0),   # Perfect
        (False, 0),  # Failure
        (True, 2),   # Necessary
        (True, 5),   # Excessive
    ]

    for correct, api in behaviors:
        b = classify_behavior(correct, api)
        logger.info(f"Correct={correct}, API={api} -> {b.name}")
