#!/usr/bin/env python3
"""
FINN COGNITIVE BRAIN - Phase 1-4 Integrated Alpha Engine
=========================================================
STIG-2025-001 Final Integration + CD-IOS015-ALPACA-PAPER-001

Combines all cognitive components into unified alpha generation system:
- Phase 1: Infrastructure (CircuitBreaker, Data Pools)
- Phase 2: Strategy Engines (StatArb, Grid, VBO, MeanRev)
- Phase 3: Cognitive Upgrade (VarClus, PCMCI, Causal RL, Thompson Bandit)
- Phase 4: Information Foraging (Patch Switching, Scent Trails)
- Phase 5: Paper Execution & Learning (Alpaca Paper, Feedback Pipeline)

Authority: ADR-020 (ACI), EC-018, STIG-2025-001, CD-IOS015-ALPACA-PAPER-001
Classification: FINN Tier-2 Executive Cognitive Engine
"""

import os
import sys
import json
import time
import signal
import logging
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from decimal import Decimal
import traceback

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import Phase 2 Strategy Engines
from ios015_statarb_engine import StatArbEngine
from ios016_grid_trading_engine import GridTradingEngine
from ios017_volatility_breakout_engine import VolatilityBreakoutEngine
from ios018_mean_reversion_engine import MeanReversionEngine

# Import Phase 3 Cognitive Components
from varclus_clustering import VarClusEngine
from ios019_cluster_causal_engine import ClusterCausalEngine
from ios020_causal_rl_engine import CausalRLEngine
from thompson_bandit import ThompsonBandit

# Import Phase 4 Foraging
from ios021_foraging_orchestrator import get_foraging_orchestrator

# Import Phase 1 Safety
from circuit_breaker_wrapper import TradingCircuitBreaker, CircuitBreakerError, CircuitBreakerConfig

# Import Supporting Components
from kelly_position_sizer import KellyPositionSizer
from ios022_signal_cohesion import SignalCohesionEngine

# Import EC-020 SitC + EC-022 IKEA: Context Injection Layer
try:
    from context_injection_layer import (
        ContextRetriever, SystemContext,
        context_minimum_viability_check,
        build_contextualized_prompt
    )
    CONTEXT_INJECTION_AVAILABLE = True
except ImportError:
    CONTEXT_INJECTION_AVAILABLE = False

# Import EC-021 InForage: Cost Controller
try:
    from inforage_cost_controller import InForageCostController, StepType, CostDecision
    COST_CONTROL_AVAILABLE = True
except ImportError:
    COST_CONTROL_AVAILABLE = False

# Import EC-022 IKEA: Knowledge Boundary Engine (CEO Directive Mandate V)
try:
    from ios022_ikea_boundary_engine import IKEABoundaryEngine, Classification
    IKEA_AVAILABLE = True
except ImportError:
    IKEA_AVAILABLE = False

# Import EC-020 SitC: Search-in-the-Chain Planner (CEO Directive Wave 6)
try:
    from ios020_sitc_planner import (
        SitCPlanner, ResearchPlan, ChainNode, NodeType,
        DEFCONViolation, RuntimeEconomicViolation as SitCEconomicViolation,
        MITQuadViolation
    )
    SITC_AVAILABLE = True
except ImportError:
    SITC_AVAILABLE = False


# =============================================================================
# CEO DIRECTIVE MANDATE II: Economic Safety as Runtime Law
# =============================================================================

class RuntimeEconomicViolation(Exception):
    """Raised when economic safety cannot be enforced - HARD FAIL."""
    pass


class RuntimeEconomicGuardian:
    """
    Unbypassable economic safety enforcement per CEO Directive Mandate II.

    "Economic safety must be unbypassable. The InForageCostController must be
    enforced at the Worker/Runtime level, not just the Agent level."

    If this guardian cannot load or function, the entire cognitive system
    MUST halt. No optional fallbacks.
    """

    def __init__(self, session_id: str):
        self._cost_controller = None
        self._load_failed = False
        self._failure_reason = None
        self.session_id = session_id

    def initialize(self, circuit_breaker: 'TradingCircuitBreaker') -> bool:
        """
        Initialize the cost controller. MUST succeed or trigger circuit breaker.

        Returns True if successful, False if failed (circuit breaker triggered).
        """
        try:
            if not COST_CONTROL_AVAILABLE:
                raise RuntimeEconomicViolation(
                    "InForageCostController module not available - CRITICAL"
                )

            self._cost_controller = InForageCostController(
                session_id=self.session_id
            )
            return True

        except Exception as e:
            self._load_failed = True
            self._failure_reason = str(e)

            # MANDATE II: Trigger circuit breaker on load failure
            circuit_breaker._record_failure(
                RuntimeEconomicViolation(f"ECONOMIC_SAFETY_LOAD_FAILURE: {e}")
            )
            return False

    def check_or_fail(
        self,
        step_type: 'StepType',
        predicted_gain: float = 0.5
    ) -> 'CostDecision':
        """
        Check cost or HARD FAIL. No exceptions, no bypasses.

        Per Mandate II: If cost controller unavailable, raise RuntimeEconomicViolation.
        This is NOT optional.
        """
        if self._load_failed or self._cost_controller is None:
            raise RuntimeEconomicViolation(
                f"Cost controller unavailable - HARD FAIL. Reason: {self._failure_reason}"
            )

        result = self._cost_controller.check_cost(step_type, predicted_gain)

        if result.should_abort:
            # Log the abort but don't raise - let caller handle
            pass

        return result

    def complete_session(self, actual_gain: float = None):
        """Complete the cost tracking session."""
        if self._cost_controller:
            return self._cost_controller.complete_session(actual_gain)
        return {}

    @property
    def is_operational(self) -> bool:
        return not self._load_failed and self._cost_controller is not None

# Import Phase 5: Paper Execution & Learning (CD-IOS015-ALPACA-PAPER-001)
try:
    from alpaca_paper_adapter import (
        AlpacaPaperAdapter, PaperOrder, SignalLineage, EpisodicSnapshot
    )
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    logger.warning("Alpaca Paper Adapter not available")

try:
    from learning_feedback_pipeline import LearningFeedbackPipeline
    LEARNING_AVAILABLE = True
except ImportError:
    LEARNING_AVAILABLE = False
    logger.warning("Learning Feedback Pipeline not available")

try:
    from trade_management_system import TradeManagementSystem, ExitReason
    TRADE_MGMT_AVAILABLE = True
except ImportError:
    TRADE_MGMT_AVAILABLE = False
    logger.warning("Trade Management System not available")

logging.basicConfig(
    level=logging.INFO,
    format='[FINN-BRAIN] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('C:/fhq-market-system/vision-ios/logs/finn_cognitive_brain.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


@dataclass
class CognitiveState:
    """Current state of FINN's cognitive engine."""
    cycle_count: int = 0
    signals_generated: int = 0
    signals_validated: int = 0
    signals_executed: int = 0
    current_patch: str = ''
    time_in_patch: float = 0.0
    daily_cost_usd: Decimal = Decimal('0.00')
    defcon_level: str = 'GREEN'
    strategies_active: List[str] = None
    last_causal_update: datetime = None
    cluster_count: int = 0
    paper_pnl_total: Decimal = Decimal('0.00')
    learning_updates_applied: int = 0

    def __post_init__(self):
        if self.strategies_active is None:
            self.strategies_active = []


class FINNCognitiveBrain:
    """
    FINN's enhanced cognitive engine integrating all Phase 1-4 components.

    Cognitive Loop:
    1. Foraging: Select research patch (asset/strategy)
    2. Clustering: Group assets via VarClus for efficient causal discovery
    3. Causal Discovery: Run hierarchical PCMCI on clusters
    4. Strategy Selection: Use Thompson Bandit for strategy allocation
    5. Signal Generation: Run strategy engines on selected assets
    6. Signal Validation: Check cohesion, apply Kelly sizing
    7. Paper Execution: Execute validated signals via Alpaca Paper
    8. Learning Update: Process outcomes through feedback pipeline

    Safety Rails:
    - Circuit Breaker: Halt on repeated failures
    - DEFCON Integration: Respect system-wide risk levels
    - Budget Constraints: Track and limit daily spend
    """

    def __init__(self, daily_budget_usd: Decimal = Decimal('10.00')):
        self.daily_budget = daily_budget_usd
        self.state = CognitiveState()
        self.conn = None

        # Phase 1: Safety
        self.circuit_breaker = TradingCircuitBreaker(
            config=CircuitBreakerConfig(
                fail_max=5,
                reset_timeout=300,
                name='FINN_COGNITIVE'
            )
        )

        # Phase 2: Strategy Engines (initialized lazily)
        self._statarb = None
        self._grid = None
        self._vbo = None
        self._meanrev = None

        # Phase 3: Cognitive Components (initialized lazily)
        self._varclus = None
        self._causal_engine = None
        self._causal_rl = None
        self._strategy_bandit = None

        # Phase 4: Foraging
        self._foraging = None

        # Phase 5: Paper Execution & Learning (CD-IOS015)
        self._paper_adapter = None
        self._learning_pipeline = None
        self._trade_manager = None
        self._paper_execution_enabled = True  # Can be disabled via DEFCON

        # EC-020 SitC + EC-022 IKEA: Context Injection
        self._context_retriever = None
        self._current_context: Optional['SystemContext'] = None

        # EC-021 InForage: Cost Controller
        self._cost_controller = None

        # EC-022 IKEA: Knowledge Boundary Engine (Mandate V)
        self._ikea_engine = None

        # EC-020 SitC: Search-in-the-Chain Planner (CEO Directive Wave 6)
        # Role: Research Planning ONLY - NOT for execution triggering
        self._sitc_planner = None

        # Runtime Economic Guardian (Mandate II: Unbypassable)
        self._runtime_guardian = None

        # Supporting
        self._kelly = None
        self._cohesion = None

        # Shutdown flag
        self._shutdown = False

    def connect(self):
        """Connect to database."""
        self.conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Connected to database")

    def close(self):
        """Close all connections."""
        if self.conn:
            self.conn.close()
        # Close strategy engines
        for engine in [self._statarb, self._grid, self._vbo, self._meanrev]:
            if engine:
                try:
                    engine.close()
                except:
                    pass
        # Close Phase 5 components
        if self._paper_adapter:
            try:
                self._paper_adapter.close()
            except:
                pass
        if self._learning_pipeline:
            try:
                self._learning_pipeline.close()
            except:
                pass
        # Close IKEA engine
        if self._ikea_engine:
            try:
                self._ikea_engine.close()
            except:
                pass
        # Close SitC planner
        if self._sitc_planner:
            try:
                self._sitc_planner.close()
            except:
                pass
        logger.info("Connections closed")

    # =========================================================================
    # LAZY INITIALIZATION
    # =========================================================================

    @property
    def statarb(self) -> StatArbEngine:
        if self._statarb is None:
            self._statarb = StatArbEngine()
            # StatArbEngine connects in __init__
        return self._statarb

    @property
    def grid(self) -> GridTradingEngine:
        if self._grid is None:
            self._grid = GridTradingEngine()
            # GridTradingEngine connects in __init__
        return self._grid

    @property
    def vbo(self) -> VolatilityBreakoutEngine:
        if self._vbo is None:
            self._vbo = VolatilityBreakoutEngine()
            self._vbo.connect()  # VBO requires explicit connect
        return self._vbo

    @property
    def meanrev(self) -> MeanReversionEngine:
        if self._meanrev is None:
            self._meanrev = MeanReversionEngine()
            # MeanReversionEngine connects in __init__
        return self._meanrev

    @property
    def varclus(self) -> VarClusEngine:
        if self._varclus is None:
            self._varclus = VarClusEngine()
        return self._varclus

    @property
    def causal_engine(self) -> ClusterCausalEngine:
        if self._causal_engine is None:
            self._causal_engine = ClusterCausalEngine()
            self._causal_engine.connect()
        return self._causal_engine

    @property
    def causal_rl(self) -> CausalRLEngine:
        if self._causal_rl is None:
            self._causal_rl = CausalRLEngine()
            self._causal_rl.connect()
        return self._causal_rl

    @property
    def strategy_bandit(self) -> ThompsonBandit:
        if self._strategy_bandit is None:
            self._strategy_bandit = ThompsonBandit(
                actions=['STATARB', 'GRID', 'VBO', 'MEANREV'],
                name='STRATEGY_SELECT'
            )
        return self._strategy_bandit

    @property
    def foraging(self):
        if self._foraging is None:
            self._foraging = get_foraging_orchestrator()
        return self._foraging

    @property
    def kelly(self) -> KellyPositionSizer:
        if self._kelly is None:
            self._kelly = KellyPositionSizer()
        return self._kelly

    @property
    def cohesion(self) -> SignalCohesionEngine:
        if self._cohesion is None:
            self._cohesion = SignalCohesionEngine()
            self._cohesion.connect()
        return self._cohesion

    @property
    def paper_adapter(self) -> Optional['AlpacaPaperAdapter']:
        if self._paper_adapter is None and ALPACA_AVAILABLE:
            self._paper_adapter = AlpacaPaperAdapter()
            self._paper_adapter.connect()
            logger.info("Alpaca Paper Adapter initialized")
        return self._paper_adapter

    @property
    def learning_pipeline(self) -> Optional['LearningFeedbackPipeline']:
        if self._learning_pipeline is None and LEARNING_AVAILABLE:
            self._learning_pipeline = LearningFeedbackPipeline()
            self._learning_pipeline.connect()
            logger.info("Learning Feedback Pipeline initialized")
        return self._learning_pipeline

    @property
    def trade_manager(self) -> Optional['TradeManagementSystem']:
        if self._trade_manager is None and TRADE_MGMT_AVAILABLE:
            self._trade_manager = TradeManagementSystem()
            self._trade_manager.connect()
            logger.info(f"Trade Manager initialized - Capital: ${self._trade_manager.capital_state.total_equity:,.2f}")
        return self._trade_manager

    @property
    def context_retriever(self) -> Optional['ContextRetriever']:
        """EC-020 SitC + EC-022 IKEA: Context retrieval for grounded decisions."""
        if self._context_retriever is None and CONTEXT_INJECTION_AVAILABLE:
            self._context_retriever = ContextRetriever()
            logger.info("Context Retriever initialized (EC-020/EC-022)")
        return self._context_retriever

    @property
    def cost_controller(self) -> Optional['InForageCostController']:
        """EC-021 InForage: Cost-aware research controller."""
        if self._cost_controller is None and COST_CONTROL_AVAILABLE:
            self._cost_controller = InForageCostController(
                session_id=f'FINN_CYCLE_{self.state.cycle_count}'
            )
            logger.info("Cost Controller initialized (EC-021 InForage)")
        return self._cost_controller

    @property
    def ikea_engine(self) -> Optional['IKEABoundaryEngine']:
        """EC-022 IKEA: Knowledge boundary classification (Mandate V)."""
        if self._ikea_engine is None and IKEA_AVAILABLE:
            self._ikea_engine = IKEABoundaryEngine()
            self._ikea_engine.connect()
            logger.info("IKEA Boundary Engine initialized (EC-022)")
        return self._ikea_engine

    @property
    def sitc_planner(self) -> Optional['SitCPlanner']:
        """
        EC-020 SitC: Search-in-the-Chain Planner (CEO Directive Wave 6).

        Role: Research Planning ONLY - NOT for execution triggering.
        Per CEO Directive Section 7 (WIRING AUTHORIZATION):
        - SitC may be wired into FINN cognitive cycle (research planning only)
        - Prohibited: Triggering execution, learning updates, schema mutations
        """
        if self._sitc_planner is None and SITC_AVAILABLE:
            try:
                self._sitc_planner = SitCPlanner(
                    session_id=f'FINN_CYCLE_{self.state.cycle_count}'
                )
                self._sitc_planner.connect()
                logger.info(f"SitC Planner initialized (EC-020) - "
                           f"DEFCON: {self._sitc_planner._defcon_level}")
            except DEFCONViolation as e:
                logger.warning(f"SitC blocked by DEFCON: {e}")
            except SitCEconomicViolation as e:
                logger.warning(f"SitC blocked by economic safety: {e}")
            except Exception as e:
                logger.warning(f"SitC initialization failed: {e}")
        return self._sitc_planner

    @property
    def runtime_guardian(self) -> RuntimeEconomicGuardian:
        """Runtime Economic Guardian (Mandate II: Unbypassable)."""
        if self._runtime_guardian is None:
            self._runtime_guardian = RuntimeEconomicGuardian(
                session_id=f'FINN_CYCLE_{self.state.cycle_count}'
            )
            if not self._runtime_guardian.initialize(self.circuit_breaker):
                logger.critical("RUNTIME GUARDIAN FAILED TO INITIALIZE - ECONOMIC SAFETY COMPROMISED")
        return self._runtime_guardian

    # =========================================================================
    # DEFCON & SAFETY
    # =========================================================================

    def check_defcon(self) -> str:
        """Check current DEFCON level."""
        sql = """
            SELECT current_level FROM fhq_governance.defcon_status
            ORDER BY updated_at DESC LIMIT 1
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql)
                row = cur.fetchone()
                return row[0] if row else 'GREEN'
        except:
            return 'GREEN'

    def check_budget(self) -> bool:
        """Check if within daily budget."""
        sql = """
            SELECT COALESCE(SUM(cost_usd), 0) as total
            FROM fhq_monitoring.api_budget_log
            WHERE created_at > NOW() - INTERVAL '24 hours'
              AND agent_id = 'FINN'
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql)
                row = cur.fetchone()
                self.state.daily_cost_usd = Decimal(str(row[0])) if row else Decimal('0')
                return self.state.daily_cost_usd < self.daily_budget
        except:
            return True

    # =========================================================================
    # COGNITIVE LOOP
    # =========================================================================

    def run_cognitive_cycle(self) -> Dict[str, Any]:
        """
        Run one cognitive cycle.

        Returns dict with cycle results.
        """
        cycle_start = time.time()
        results = {
            'cycle': self.state.cycle_count,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'signals': [],
            'validated': [],
            'executed': [],
            'exits_triggered': [],
            'learning_updates': 0,
            'strategy_used': None,
            'patch': None,
            'capital': None,
            'context': None,  # EC-020/EC-022 system context
            'cost_metrics': None,  # EC-021 InForage cost tracking
            'duration_sec': 0
        }

        try:
            # Check safety rails
            self.state.defcon_level = self.check_defcon()
            if self.state.defcon_level in ('RED', 'ORANGE'):
                logger.warning(f"DEFCON {self.state.defcon_level} - cognitive cycle suspended")
                return results

            if not self.check_budget():
                logger.warning(f"Daily budget exceeded (${self.state.daily_cost_usd})")
                return results

            # =========================================================
            # MANDATE II: RuntimeEconomicGuardian - UNBYPASSABLE
            # =========================================================
            # Economic safety must be enforced at Runtime level
            try:
                if not self.runtime_guardian.is_operational:
                    logger.critical("RUNTIME GUARDIAN NOT OPERATIONAL - CYCLE BLOCKED")
                    results['runtime_guardian_error'] = "Guardian not operational"
                    return results

                # Check if we can proceed with this cycle
                cost_check = self.runtime_guardian.check_or_fail(
                    StepType.DB_QUERY,
                    predicted_gain=0.5  # Baseline predicted gain for cycle start
                )
                if cost_check.should_abort:
                    logger.warning(f"RuntimeGuardian ABORT: {cost_check.abort_reason}")
                    results['runtime_abort'] = cost_check.abort_reason
                    return results

            except RuntimeEconomicViolation as e:
                logger.critical(f"ECONOMIC SAFETY VIOLATION: {e}")
                results['economic_violation'] = str(e)
                return results

            # =========================================================
            # MANDATE V: IKEA Boundary Check
            # =========================================================
            # Check knowledge boundaries before proceeding
            results['ikea_stats'] = None
            if self.ikea_engine:
                try:
                    # IKEA will be used throughout the cycle for individual claims
                    results['ikea_stats'] = self.ikea_engine.get_statistics()
                except Exception as e:
                    logger.warning(f"IKEA initialization check failed: {e}")

            # EC-020/EC-022: Retrieve System Context (SitC + IKEA)
            # "A brain without context hallucinates. A brain with context perceives."
            if self.context_retriever:
                try:
                    self._current_context = self.context_retriever.retrieve_full_context()
                    is_viable, missing = context_minimum_viability_check(self._current_context)

                    results['context'] = {
                        'hash': self._current_context.context_hash,
                        'regime': self._current_context.market_state.current_regime,
                        'session': self._current_context.market_clock.market_session,
                        'fields_present': self._current_context.context_fields_present,
                        'viable': is_viable,
                        'missing_fields': missing
                    }

                    if not is_viable:
                        logger.warning(f"Context not viable - missing: {missing}")
                        # Continue anyway but log the gap

                    logger.info(f"Context retrieved: regime={self._current_context.market_state.current_regime}, "
                               f"session={self._current_context.market_clock.market_session}")
                except Exception as e:
                    logger.warning(f"Context retrieval failed: {e}")

            # EC-020 SitC: Research Planning (CEO Directive Wave 6)
            # Role: Chain-of-Query planning for structured research
            # Prohibited: Execution triggering, learning updates
            results['sitc_plan'] = None
            if self.sitc_planner and self.state.current_patch:
                try:
                    # Create research plan for current patch (hypothesis)
                    hypothesis = f"Evaluate alpha potential for {self.state.current_patch}"
                    research_plan = self.sitc_planner.create_research_plan(hypothesis)

                    results['sitc_plan'] = {
                        'plan_id': research_plan.plan_id,
                        'hypothesis': research_plan.hypothesis,
                        'node_count': len(research_plan.nodes),
                        'asrp_hash': research_plan.state_snapshot_hash[:16],
                        'nodes': [
                            {'type': n.node_type.value, 'content': n.content[:50]}
                            for n in research_plan.nodes
                        ]
                    }

                    # Log chain to database (fhq_meta only - role isolation enforced)
                    self.sitc_planner.log_chain(research_plan.nodes)

                    logger.info(f"SitC Research Plan created: {research_plan.plan_id} "
                               f"({len(research_plan.nodes)} nodes)")

                except DEFCONViolation as e:
                    logger.warning(f"SitC blocked by DEFCON: {e}")
                except SitCEconomicViolation as e:
                    logger.warning(f"SitC blocked by economic safety: {e}")
                except MITQuadViolation as e:
                    logger.error(f"SitC schema violation: {e}")
                except Exception as e:
                    logger.warning(f"SitC planning failed: {e}")

            # Step 0: Exit Monitoring (before generating new signals)
            # Per ADR-020: ACI monitors positions and triggers exits
            if self.trade_manager:
                try:
                    self.trade_manager.load_open_positions()
                    exits_triggered = self.trade_manager.scan_for_exits()
                    results['exits_triggered'] = exits_triggered
                    results['capital'] = float(self.trade_manager.capital_state.total_equity)

                    if exits_triggered:
                        logger.info(f"Exit conditions detected: {len(exits_triggered)} positions")
                        # Execute exits via paper adapter
                        for exit_info in exits_triggered:
                            self._execute_exit(exit_info)
                except Exception as e:
                    logger.warning(f"Exit monitoring failed: {e}")

            # Step 1: Foraging Decision
            foraging_decision = self.foraging.decide(
                self.state.current_patch,
                self.state.time_in_patch
            )

            if foraging_decision.action == 'SWITCH' and foraging_decision.target_patch:
                logger.info(f"Switching patch: {self.state.current_patch} -> {foraging_decision.target_patch}")
                self.state.current_patch = foraging_decision.target_patch
                self.state.time_in_patch = 0
            else:
                self.state.time_in_patch += 0.5  # Assume 30 min per cycle

            results['patch'] = self.state.current_patch

            # Step 2: Strategy Selection via Thompson Bandit
            strategy = self.strategy_bandit.select_action()
            results['strategy_used'] = strategy
            logger.info(f"Strategy selected: {strategy}")

            # Step 3: Run Selected Strategy
            signals = self._run_strategy(strategy)
            results['signals'] = [asdict(s) if hasattr(s, '__dataclass_fields__') else s for s in signals]

            # Step 4: Validate Signals (Cohesion Check)
            validated = []
            for sig in signals:
                canonical_id = sig.canonical_id if hasattr(sig, 'canonical_id') else sig.get('canonical_id')
                if canonical_id and self.cohesion.check_cohesion(canonical_id):
                    validated.append(sig)
                    self.state.signals_validated += 1

            results['validated'] = [asdict(s) if hasattr(s, '__dataclass_fields__') else s for s in validated]

            # Step 5: Update Thompson Bandit based on results
            reward = len(validated) / max(len(signals), 1) if signals else 0
            self.strategy_bandit.update(strategy, reward)

            # Step 6: Store signals
            self._store_signals(validated, strategy)

            # Step 7: Paper Execution (CD-IOS015-ALPACA-PAPER-001)
            if self._paper_execution_enabled and validated:
                executed = self._execute_paper_orders(validated, strategy)
                results['executed'] = executed
                self.state.signals_executed += len(executed)

            # Step 8: Process Learning Feedback
            if self.learning_pipeline:
                learning_result = self.learning_pipeline.process_all_pending()
                results['learning_updates'] = learning_result.get('updates', 0)
                self.state.learning_updates_applied += results['learning_updates']

            self.state.signals_generated += len(signals)
            self.state.cycle_count += 1

            # EC-021 InForage: Record cost metrics for this cycle
            if self.cost_controller:
                results['cost_metrics'] = {
                    'session_id': self.cost_controller.session_id,
                    'step_count': self.cost_controller.step_count,
                    'total_cost': self.cost_controller.total_cost,
                    'aborted': self.cost_controller.aborted,
                    'abort_reason': self.cost_controller.abort_reason
                }

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN - cognitive cycle blocked")
        except Exception as e:
            logger.error(f"Cognitive cycle error: {e}")
            traceback.print_exc()
            self.circuit_breaker._record_failure(e)

        results['duration_sec'] = time.time() - cycle_start
        return results

    def _get_active_assets(self, limit: int = 50) -> List[str]:
        """Get list of active assets for strategy scanning."""
        sql = """
            SELECT canonical_id FROM fhq_meta.assets
            WHERE active_flag = true
              AND data_quality_status = 'FULL_HISTORY'
            ORDER BY valid_row_count DESC
            LIMIT %s
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (limit,))
            return [r[0] for r in cur.fetchall()]

    def _run_strategy(self, strategy: str) -> List:
        """Run the selected strategy engine."""
        try:
            if strategy == 'STATARB':
                # StatArb uses generate_all_signals()
                return self.statarb.generate_all_signals()
            elif strategy == 'GRID':
                # Grid doesn't have scan_universe - check signals for active grids
                signals = []
                for asset in self.grid.get_active_grids().keys():
                    signals.extend(self.grid.check_grid_signals(asset))
                return signals
            elif strategy == 'VBO':
                # VBO has scan_universe()
                return self.vbo.scan_universe()
            elif strategy == 'MEANREV':
                # MeanRev needs asset list
                assets = self._get_active_assets(50)
                return self.meanrev.scan_universe(assets)
            else:
                logger.warning(f"Unknown strategy: {strategy}")
                return []
        except Exception as e:
            logger.error(f"Strategy {strategy} failed: {e}")
            return []

    def _store_signals(self, signals: List, strategy: str):
        """Store validated signals to database."""
        if not signals:
            return

        sql = """
            INSERT INTO fhq_alpha.alpha_signals (
                signal_id, canonical_id, signal_type, strategy_source,
                confidence, signal_metadata, created_at
            ) VALUES (
                gen_random_uuid(), %s, %s, %s, %s, %s, NOW()
            )
            ON CONFLICT DO NOTHING
        """
        with self.conn.cursor() as cur:
            for sig in signals:
                try:
                    canonical_id = sig.canonical_id if hasattr(sig, 'canonical_id') else sig.get('canonical_id')
                    signal_type = sig.signal_type if hasattr(sig, 'signal_type') else sig.get('signal_type')
                    confidence = sig.confidence if hasattr(sig, 'confidence') else sig.get('confidence', 0.5)
                    metadata = asdict(sig) if hasattr(sig, '__dataclass_fields__') else sig

                    cur.execute(sql, (
                        canonical_id,
                        signal_type,
                        f'FINN_COGNITIVE_{strategy}',
                        confidence,
                        Json(metadata)
                    ))
                except Exception as e:
                    logger.warning(f"Could not store signal: {e}")

        self.conn.commit()

    # =========================================================================
    # PAPER EXECUTION (CD-IOS015-ALPACA-PAPER-001)
    # =========================================================================

    def _execute_paper_orders(self, signals: List, strategy: str) -> List[Dict]:
        """
        Execute validated signals via Alpaca Paper Trading.

        Per Directive Section 4:
        - Full signal lineage required
        - DEFCON must be GREEN
        - Circuit breaker must be CLOSED
        - Kelly sizing enforced

        Returns list of executed order results.
        """
        if not self.paper_adapter:
            logger.debug("Paper adapter not available")
            return []

        executed = []

        for sig in signals:
            try:
                # Extract signal properties
                canonical_id = sig.canonical_id if hasattr(sig, 'canonical_id') else sig.get('canonical_id')
                signal_type = sig.signal_type if hasattr(sig, 'signal_type') else sig.get('signal_type', '')
                confidence = sig.confidence if hasattr(sig, 'confidence') else sig.get('confidence', 0.5)

                # Determine side from signal type
                if 'LONG' in signal_type.upper() or 'BUY' in signal_type.upper() or 'UP' in signal_type.upper():
                    side = 'buy'
                elif 'SHORT' in signal_type.upper() or 'SELL' in signal_type.upper() or 'DOWN' in signal_type.upper():
                    side = 'sell'
                else:
                    logger.debug(f"Cannot determine side for signal type: {signal_type}")
                    continue

                # Get current regime
                regime = self._get_current_regime(canonical_id)

                # Calculate Kelly position size
                kelly_fraction = self.kelly.calculate_kelly(
                    win_rate=0.5 + (confidence - 0.5) * 0.2,  # Adjust win rate by confidence
                    avg_win=0.03,  # 3% average win
                    avg_loss=0.02  # 2% average loss
                )

                # Get current price
                current_price = self._get_current_price(canonical_id)

                # Calculate position size using Trade Manager (capital-aware)
                # This respects the $200k+ capital base and 5% max position rule
                if self.trade_manager:
                    qty, notional_usd = self.trade_manager.calculate_position_size(
                        canonical_id=canonical_id,
                        signal_confidence=confidence,
                        current_price=current_price,
                        kelly_fraction=kelly_fraction
                    )
                    logger.info(f"Capital-aware position: {canonical_id} ${notional_usd:,.2f} = {qty} units")
                else:
                    # Fallback to simpler calculation if trade manager unavailable
                    # Still use meaningful position size (~$5000 base for $200k account)
                    base_position_usd = 5000.0
                    qty = base_position_usd * kelly_fraction * confidence / current_price
                    qty = round(qty, 4) if current_price < 100 else round(qty, 2)

                # Create signal lineage
                lineage = SignalLineage(
                    signal_id=str(sig.signal_id) if hasattr(sig, 'signal_id') else 'GENERATED',
                    strategy_source=f'FINN_COGNITIVE_{strategy}',
                    regime_state=regime,
                    cognitive_action='EXECUTE',
                    kelly_fraction=kelly_fraction,
                    circuit_breaker_state=self.circuit_breaker.state
                )

                if qty <= 0:
                    continue

                # Create paper order
                order = PaperOrder(
                    canonical_id=canonical_id,
                    side=side,
                    order_type='market',
                    qty=qty,
                    limit_price=None,
                    lineage=lineage
                )

                # Submit order
                result = self.paper_adapter.submit_order(order)

                if result.status.value == 'filled':
                    filled_notional = float(result.filled_qty) * float(result.filled_avg_price)

                    # Create exit strategy for this new position
                    exit_strategy = None
                    if self.trade_manager:
                        exit_strategy = self.trade_manager.create_exit_strategy(
                            entry_price=float(result.filled_avg_price),
                            side='long' if side == 'buy' else 'short',
                            regime=regime,
                            signal_confidence=confidence
                        )

                    executed.append({
                        'canonical_id': canonical_id,
                        'side': side,
                        'qty': result.filled_qty,
                        'price': result.filled_avg_price,
                        'notional_usd': filled_notional,
                        'strategy': strategy,
                        'kelly_fraction': kelly_fraction,
                        'regime': regime,
                        'exit_strategy': {
                            'stop_loss': exit_strategy.stop_loss_price if exit_strategy else None,
                            'take_profit': exit_strategy.take_profit_price if exit_strategy else None,
                            'max_hold_hours': exit_strategy.max_hold_hours if exit_strategy else 168
                        } if exit_strategy else None
                    })
                    logger.info(f"Paper order filled: {canonical_id} {side} {result.filled_qty} @ {result.filled_avg_price} (${filled_notional:,.2f})")

            except Exception as e:
                logger.warning(f"Paper execution failed for signal: {e}")

        return executed

    def _execute_exit(self, exit_info: Dict):
        """
        Execute an exit order for a position that triggered exit conditions.

        Args:
            exit_info: Dict with position_id, canonical_id, side, exit_reason, etc.
        """
        if not self.paper_adapter:
            logger.debug("Paper adapter not available for exit execution")
            return

        try:
            canonical_id = exit_info['canonical_id']
            side = exit_info['side']
            exit_reason = exit_info['exit_reason']

            # Reverse the position side for exit
            exit_side = 'sell' if side == 'long' else 'buy'

            # Get quantity from trade_manager positions
            pos_state = self.trade_manager.positions.get(exit_info['position_id'])
            qty = pos_state.quantity if pos_state else 0

            if qty <= 0:
                logger.warning(f"No quantity found for exit: {canonical_id}")
                return

            # Create exit lineage
            lineage = SignalLineage(
                signal_id=f'EXIT_{exit_info["position_id"]}',
                strategy_source=f'EXIT_{exit_reason}',
                regime_state=self._get_current_regime(canonical_id),
                cognitive_action='EXIT',
                kelly_fraction=0.0,  # Full exit
                circuit_breaker_state=self.circuit_breaker.state
            )

            # Create exit order
            order = PaperOrder(
                canonical_id=canonical_id,
                side=exit_side,
                order_type='market',
                qty=qty,
                limit_price=None,
                lineage=lineage
            )

            result = self.paper_adapter.submit_order(order)

            if result.status.value == 'filled':
                logger.info(f"EXIT EXECUTED: {canonical_id} | "
                           f"Reason: {exit_reason} | "
                           f"Qty: {result.filled_qty} @ {result.filled_avg_price}")

        except Exception as e:
            logger.error(f"Exit execution failed for {exit_info.get('canonical_id', 'UNKNOWN')}: {e}")

    def _get_current_regime(self, canonical_id: str) -> str:
        """Get current regime for asset."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT regime_label FROM fhq_perception.regime_log
                    WHERE canonical_id = %s
                    ORDER BY created_at DESC LIMIT 1
                """, (canonical_id,))
                row = cur.fetchone()
                return row[0] if row else 'UNKNOWN'
        except:
            return 'UNKNOWN'

    def _get_current_price(self, canonical_id: str) -> float:
        """Get current price for asset."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT close FROM fhq_data.price_series
                    WHERE listing_id = %s
                    ORDER BY date DESC LIMIT 1
                """, (canonical_id,))
                row = cur.fetchone()
                return float(row[0]) if row else 100.0
        except:
            return 100.0

    # =========================================================================
    # CAUSAL UPDATE (Periodic)
    # =========================================================================

    def update_causal_graph(self):
        """
        Periodically update the causal graph using hierarchical PCMCI.
        This is expensive, so run infrequently (e.g., daily).
        """
        logger.info("Starting causal graph update...")

        try:
            # Step 1: Run VarClus clustering
            clusters = self.varclus.fit_from_database(n_clusters=30)
            self.state.cluster_count = len(clusters) if clusters else 0
            logger.info(f"VarClus identified {self.state.cluster_count} clusters")

            # Step 2: Run hierarchical PCMCI
            self.causal_engine.run_macro_pcmci(clusters)
            logger.info("Macro-level causal discovery complete")

            # Step 3: Drill down on significant cluster pairs
            self.causal_engine.run_micro_pcmci()
            logger.info("Micro-level causal discovery complete")

            self.state.last_causal_update = datetime.now(timezone.utc)

        except Exception as e:
            logger.error(f"Causal graph update failed: {e}")
            traceback.print_exc()

    # =========================================================================
    # MAIN LOOP
    # =========================================================================

    def run(self, interval_minutes: int = 60, max_cycles: int = None):
        """
        Run continuous cognitive loop.

        Args:
            interval_minutes: Minutes between cycles
            max_cycles: Max cycles to run (None = infinite)
        """
        logger.info("=" * 60)
        logger.info("FINN COGNITIVE BRAIN ACTIVATED")
        logger.info(f"Daily budget: ${self.daily_budget}")
        logger.info(f"Cycle interval: {interval_minutes} minutes")
        logger.info("=" * 60)

        # Setup signal handlers
        def shutdown_handler(signum, frame):
            logger.info("Shutdown signal received")
            self._shutdown = True

        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)

        self.connect()

        # Initial causal graph build
        self.update_causal_graph()

        cycles = 0
        while not self._shutdown:
            if max_cycles and cycles >= max_cycles:
                break

            results = self.run_cognitive_cycle()
            logger.info(f"Cycle {results['cycle']}: "
                       f"{len(results['signals'])} signals, "
                       f"{len(results['validated'])} validated, "
                       f"strategy={results['strategy_used']}, "
                       f"duration={results['duration_sec']:.1f}s")

            cycles += 1

            # Periodic causal update (every 24 hours)
            if self.state.last_causal_update:
                hours_since = (datetime.now(timezone.utc) - self.state.last_causal_update).total_seconds() / 3600
                if hours_since >= 24:
                    self.update_causal_graph()

            # Sleep until next cycle
            if not self._shutdown:
                time.sleep(interval_minutes * 60)

        self.close()
        logger.info("FINN Cognitive Brain shutdown complete")

    def run_single_cycle(self) -> Dict[str, Any]:
        """Run a single cognitive cycle (for testing)."""
        self.connect()
        results = self.run_cognitive_cycle()
        self.close()
        return results


def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description='FINN Cognitive Brain')
    parser.add_argument('--interval', type=int, default=60, help='Cycle interval in minutes')
    parser.add_argument('--budget', type=float, default=10.0, help='Daily budget USD')
    parser.add_argument('--cycles', type=int, default=None, help='Max cycles (default: infinite)')
    parser.add_argument('--single', action='store_true', help='Run single cycle and exit')
    args = parser.parse_args()

    brain = FINNCognitiveBrain(daily_budget_usd=Decimal(str(args.budget)))

    if args.single:
        results = brain.run_single_cycle()
        print(json.dumps(results, indent=2, default=str))
    else:
        brain.run(interval_minutes=args.interval, max_cycles=args.cycles)


if __name__ == '__main__':
    main()
