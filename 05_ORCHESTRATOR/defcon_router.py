#!/usr/bin/env python3
"""
IoS-014 DEFCON ROUTER & MODE ROUTER
Authority: CEO DIRECTIVE — IoS-014 BUILD & AUTONOMOUS AGENT ACTIVATION
Purpose: DEFCON-aware scheduling and execution mode enforcement

Per ADR-016:
| Level  | Behavior |
|--------|----------|
| GREEN  | Full schedule, research + execution + options, within economic safety limits |
| YELLOW | Reduce frequency for non-critical tasks, preserve ingest + perception + execution |
| ORANGE | Freeze new research and backtests, keep ingest + perception + monitoring |
| RED    | Stop all trade execution, run only safety checks and perception |
| BLACK  | Complete halt, CEO-only manual override |

Execution Modes:
| Mode       | Description |
|------------|-------------|
| LOCAL_DEV  | Minimal scheduling, reduced universe, no expensive vendor calls |
| PAPER_PROD | Full cycles, real vendors, all execution to paper |
| LIVE_PROD  | Same cycles, execution to real brokers when approved |
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import psycopg2
from psycopg2.extras import RealDictCursor


class DEFCONLevel(Enum):
    """DEFCON levels per ADR-016"""
    GREEN = "GREEN"    # Normal operations
    YELLOW = "YELLOW"  # Elevated caution
    ORANGE = "ORANGE"  # High alert
    RED = "RED"        # Critical - no execution
    BLACK = "BLACK"    # System halt


class ExecutionMode(Enum):
    """Execution modes per IoS-014 spec"""
    LOCAL_DEV = "LOCAL_DEV"      # Development mode
    PAPER_PROD = "PAPER_PROD"    # Paper trading
    LIVE_PROD = "LIVE_PROD"      # Live trading


class TaskCriticality(Enum):
    """Task criticality levels for DEFCON filtering"""
    CRITICAL = "CRITICAL"      # Must run even at RED (perception, safety)
    HIGH = "HIGH"              # Runs at ORANGE+ (ingest, monitoring)
    MEDIUM = "MEDIUM"          # Runs at YELLOW+ (execution, allocation)
    LOW = "LOW"                # Runs only at GREEN (research, backtests)


@dataclass
class DEFCONState:
    """Current DEFCON state"""
    level: DEFCONLevel
    triggered_at: datetime
    triggered_by: str
    reason: str
    auto_expire: Optional[datetime]


@dataclass
class ExecutionModeState:
    """Current execution mode state"""
    mode: ExecutionMode
    set_at: datetime
    set_by: str
    reason: str


@dataclass
class TaskSchedulingDecision:
    """Decision on whether to schedule a task"""
    task_name: str
    should_run: bool
    reason: str
    frequency_multiplier: float  # 1.0 = normal, 0.5 = half frequency, etc.
    vendor_restrictions: List[str]  # Vendors to avoid


class DEFCONRouter:
    """
    IoS-014 DEFCON Router

    Reads current DEFCON level and determines task eligibility.
    Implements ADR-016 circuit breaker behavior.
    """

    # Task criticality by category
    TASK_CRITICALITY = {
        # CRITICAL - Run at all levels except BLACK
        'ios003_regime_freshness_sentinel': TaskCriticality.CRITICAL,
        'ios003_daily_regime_update': TaskCriticality.CRITICAL,
        'defcon_health_check': TaskCriticality.CRITICAL,
        'system_heartbeat': TaskCriticality.CRITICAL,

        # HIGH - Run at ORANGE and above
        'daily_ingest_worker': TaskCriticality.HIGH,
        'lake_tier_ingest': TaskCriticality.HIGH,
        'calc_indicators_v1': TaskCriticality.HIGH,
        'ios006_g2_macro_ingest': TaskCriticality.HIGH,

        # MEDIUM - Run at YELLOW and above
        'ios012_g3_system_loop': TaskCriticality.MEDIUM,
        'ios008_g1_validation': TaskCriticality.MEDIUM,
        'ios004_regime_allocation': TaskCriticality.MEDIUM,
        'ios013_hcp_g3_runner': TaskCriticality.MEDIUM,

        # LOW - Run only at GREEN
        'finn_night_research_executor': TaskCriticality.LOW,
        'ios008_g2_historical_replay': TaskCriticality.LOW,
        'ios005_g3_synthesis': TaskCriticality.LOW,
        'wave002_stress_validator': TaskCriticality.LOW,
    }

    # DEFCON to allowed criticality mapping
    DEFCON_ALLOWED_CRITICALITY = {
        DEFCONLevel.GREEN: [TaskCriticality.CRITICAL, TaskCriticality.HIGH, TaskCriticality.MEDIUM, TaskCriticality.LOW],
        DEFCONLevel.YELLOW: [TaskCriticality.CRITICAL, TaskCriticality.HIGH, TaskCriticality.MEDIUM],
        DEFCONLevel.ORANGE: [TaskCriticality.CRITICAL, TaskCriticality.HIGH],
        DEFCONLevel.RED: [TaskCriticality.CRITICAL],
        DEFCONLevel.BLACK: [],  # Nothing runs at BLACK
    }

    # Frequency multipliers per DEFCON level
    DEFCON_FREQUENCY_MULTIPLIER = {
        DEFCONLevel.GREEN: 1.0,
        DEFCONLevel.YELLOW: 0.75,  # 75% frequency
        DEFCONLevel.ORANGE: 0.5,   # 50% frequency
        DEFCONLevel.RED: 0.25,     # 25% frequency
        DEFCONLevel.BLACK: 0.0,    # No execution
    }

    def __init__(self, connection_string: str, logger: Optional[logging.Logger] = None):
        self.connection_string = connection_string
        self.logger = logger or logging.getLogger("defcon_router")
        self._conn = None
        self._cached_state: Optional[DEFCONState] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 30  # Refresh every 30 seconds

    def connect(self):
        """Establish database connection"""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.connection_string)
        return self._conn

    def close(self):
        """Close database connection"""
        if self._conn and not self._conn.closed:
            self._conn.close()

    def get_current_defcon(self) -> DEFCONState:
        """Get current DEFCON level from database"""
        now = datetime.now(timezone.utc)

        # Check cache
        if (self._cached_state and self._cache_timestamp and
            (now - self._cache_timestamp).total_seconds() < self._cache_ttl_seconds):
            return self._cached_state

        conn = self.connect()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Try to read from defcon_state table
            cur.execute("""
                SELECT
                    defcon_level,
                    triggered_at,
                    triggered_by,
                    trigger_reason,
                    auto_expire_at
                FROM fhq_governance.defcon_state
                WHERE is_current = TRUE
                ORDER BY triggered_at DESC
                LIMIT 1
            """)
            row = cur.fetchone()

            if row:
                state = DEFCONState(
                    level=DEFCONLevel(row['defcon_level']),
                    triggered_at=row['triggered_at'],
                    triggered_by=row['triggered_by'],
                    reason=row['trigger_reason'] or 'No reason provided',
                    auto_expire=row['auto_expire_at']
                )
            else:
                # Default to GREEN if no state found
                state = DEFCONState(
                    level=DEFCONLevel.GREEN,
                    triggered_at=now,
                    triggered_by='SYSTEM',
                    reason='Default GREEN state',
                    auto_expire=None
                )

            self._cached_state = state
            self._cache_timestamp = now
            return state

    def should_task_run(self, task_name: str, defcon_state: Optional[DEFCONState] = None) -> TaskSchedulingDecision:
        """
        Determine if a task should run given current DEFCON level.

        Args:
            task_name: Name of the task
            defcon_state: Optional pre-fetched DEFCON state

        Returns:
            TaskSchedulingDecision with run decision and restrictions
        """
        if defcon_state is None:
            defcon_state = self.get_current_defcon()

        # Get task criticality (default to MEDIUM if unknown)
        criticality = self.TASK_CRITICALITY.get(task_name, TaskCriticality.MEDIUM)

        # Get allowed criticalities for current DEFCON
        allowed = self.DEFCON_ALLOWED_CRITICALITY.get(defcon_state.level, [])

        # Determine if task should run
        should_run = criticality in allowed
        frequency_multiplier = self.DEFCON_FREQUENCY_MULTIPLIER.get(defcon_state.level, 1.0)

        # Determine vendor restrictions based on DEFCON
        vendor_restrictions = []
        if defcon_state.level in [DEFCONLevel.ORANGE, DEFCONLevel.RED]:
            # At ORANGE/RED, restrict expensive vendors
            vendor_restrictions = ['ALPHAVANTAGE', 'FMP', 'OPENAI', 'ANTHROPIC']
        elif defcon_state.level == DEFCONLevel.YELLOW:
            # At YELLOW, restrict only SNIPER tier
            vendor_restrictions = ['ALPHAVANTAGE', 'FMP']

        # Build reason
        if not should_run:
            reason = f"DEFCON {defcon_state.level.value}: Task criticality {criticality.value} not allowed"
        else:
            reason = f"DEFCON {defcon_state.level.value}: Task allowed (criticality={criticality.value}, freq={frequency_multiplier}x)"

        return TaskSchedulingDecision(
            task_name=task_name,
            should_run=should_run,
            reason=reason,
            frequency_multiplier=frequency_multiplier,
            vendor_restrictions=vendor_restrictions
        )

    def filter_tasks_for_defcon(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter a list of tasks based on current DEFCON level.

        Args:
            tasks: List of task dictionaries with 'task_name' key

        Returns:
            Filtered list of tasks that should run
        """
        defcon_state = self.get_current_defcon()
        filtered = []

        for task in tasks:
            decision = self.should_task_run(task['task_name'], defcon_state)
            if decision.should_run:
                task['defcon_decision'] = decision
                filtered.append(task)
            else:
                self.logger.info(f"DEFCON filter: Skipping {task['task_name']} - {decision.reason}")

        self.logger.info(f"DEFCON {defcon_state.level.value}: {len(filtered)}/{len(tasks)} tasks allowed")
        return filtered

    def log_defcon_transition(self, new_level: DEFCONLevel, reason: str, triggered_by: str = "IOS014"):
        """Log a DEFCON level transition"""
        conn = self.connect()
        with conn.cursor() as cur:
            # Mark current state as not current
            cur.execute("""
                UPDATE fhq_governance.defcon_state
                SET is_current = FALSE
                WHERE is_current = TRUE
            """)

            # Insert new state
            cur.execute("""
                INSERT INTO fhq_governance.defcon_state (
                    defcon_level, triggered_at, triggered_by, trigger_reason, is_current
                ) VALUES (%s, %s, %s, %s, TRUE)
            """, (new_level.value, datetime.now(timezone.utc), triggered_by, reason))

            conn.commit()

            # Clear cache
            self._cached_state = None

            self.logger.warning(f"DEFCON TRANSITION: -> {new_level.value} ({reason})")


class ModeRouter:
    """
    IoS-014 Execution Mode Router

    Controls execution mode (LOCAL_DEV, PAPER_PROD, LIVE_PROD).
    CEO mandate: Start in PAPER_PROD until 14-day validation passes.
    """

    # Mode restrictions
    MODE_RESTRICTIONS = {
        ExecutionMode.LOCAL_DEV: {
            'max_universe_size': 10,
            'allowed_vendors': ['YFINANCE', 'FRED'],  # Free vendors only
            'execution_enabled': False,
            'expensive_llm_enabled': False,
        },
        ExecutionMode.PAPER_PROD: {
            'max_universe_size': 100,
            'allowed_vendors': None,  # All vendors per quota
            'execution_enabled': True,  # Paper execution
            'expensive_llm_enabled': True,
        },
        ExecutionMode.LIVE_PROD: {
            'max_universe_size': None,  # No limit
            'allowed_vendors': None,
            'execution_enabled': True,  # Real execution
            'expensive_llm_enabled': True,
        }
    }

    def __init__(self, connection_string: str, logger: Optional[logging.Logger] = None):
        self.connection_string = connection_string
        self.logger = logger or logging.getLogger("mode_router")
        self._conn = None
        self._cached_mode: Optional[ExecutionModeState] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 60  # Refresh every minute

    def connect(self):
        """Establish database connection"""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.connection_string)
        return self._conn

    def close(self):
        """Close database connection"""
        if self._conn and not self._conn.closed:
            self._conn.close()

    def get_current_mode(self) -> ExecutionModeState:
        """Get current execution mode from database"""
        now = datetime.now(timezone.utc)

        # Check cache
        if (self._cached_mode and self._cache_timestamp and
            (now - self._cache_timestamp).total_seconds() < self._cache_ttl_seconds):
            return self._cached_mode

        conn = self.connect()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Try to read from execution_mode table
            cur.execute("""
                SELECT
                    mode_name,
                    set_at,
                    set_by,
                    reason
                FROM fhq_governance.execution_mode
                WHERE is_current = TRUE
                ORDER BY set_at DESC
                LIMIT 1
            """)
            row = cur.fetchone()

            if row:
                mode = ExecutionModeState(
                    mode=ExecutionMode(row['mode_name']),
                    set_at=row['set_at'],
                    set_by=row['set_by'],
                    reason=row['reason'] or 'No reason provided'
                )
            else:
                # Default to PAPER_PROD per CEO directive
                mode = ExecutionModeState(
                    mode=ExecutionMode.PAPER_PROD,
                    set_at=now,
                    set_by='CEO_DIRECTIVE',
                    reason='Default PAPER_PROD per CEO directive IoS-014'
                )

            self._cached_mode = mode
            self._cache_timestamp = now
            return mode

    def get_mode_restrictions(self, mode_state: Optional[ExecutionModeState] = None) -> Dict[str, Any]:
        """Get restrictions for current execution mode"""
        if mode_state is None:
            mode_state = self.get_current_mode()

        return self.MODE_RESTRICTIONS.get(mode_state.mode, self.MODE_RESTRICTIONS[ExecutionMode.PAPER_PROD])

    def is_execution_allowed(self, is_paper: bool = True) -> Tuple[bool, str]:
        """
        Check if execution is allowed in current mode.

        Args:
            is_paper: True for paper execution, False for live

        Returns:
            Tuple of (allowed, reason)
        """
        mode_state = self.get_current_mode()
        restrictions = self.get_mode_restrictions(mode_state)

        if not restrictions['execution_enabled']:
            return False, f"Execution disabled in {mode_state.mode.value} mode"

        if not is_paper and mode_state.mode != ExecutionMode.LIVE_PROD:
            return False, f"Live execution requires LIVE_PROD mode (current: {mode_state.mode.value})"

        return True, f"Execution allowed in {mode_state.mode.value} mode"

    def is_vendor_allowed(self, vendor_name: str, mode_state: Optional[ExecutionModeState] = None) -> Tuple[bool, str]:
        """Check if a vendor is allowed in current mode"""
        if mode_state is None:
            mode_state = self.get_current_mode()

        restrictions = self.get_mode_restrictions(mode_state)
        allowed_vendors = restrictions.get('allowed_vendors')

        if allowed_vendors is None:
            return True, f"All vendors allowed in {mode_state.mode.value}"

        if vendor_name in allowed_vendors:
            return True, f"Vendor {vendor_name} allowed in {mode_state.mode.value}"

        return False, f"Vendor {vendor_name} not allowed in {mode_state.mode.value} (allowed: {allowed_vendors})"

    def get_universe_limit(self, mode_state: Optional[ExecutionModeState] = None) -> Optional[int]:
        """Get maximum universe size for current mode"""
        if mode_state is None:
            mode_state = self.get_current_mode()

        restrictions = self.get_mode_restrictions(mode_state)
        return restrictions.get('max_universe_size')


class CombinedRouter:
    """
    Combined DEFCON + Mode Router for IoS-014

    Provides single interface for all routing decisions.
    """

    def __init__(self, connection_string: str, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger("ios014_router")
        self.defcon_router = DEFCONRouter(connection_string, self.logger)
        self.mode_router = ModeRouter(connection_string, self.logger)

    def close(self):
        """Close all connections"""
        self.defcon_router.close()
        self.mode_router.close()

    def get_system_state(self) -> Dict[str, Any]:
        """Get combined system state"""
        defcon = self.defcon_router.get_current_defcon()
        mode = self.mode_router.get_current_mode()

        return {
            'defcon': {
                'level': defcon.level.value,
                'triggered_at': defcon.triggered_at.isoformat() if defcon.triggered_at else None,
                'triggered_by': defcon.triggered_by,
                'reason': defcon.reason
            },
            'mode': {
                'mode': mode.mode.value,
                'set_at': mode.set_at.isoformat() if mode.set_at else None,
                'set_by': mode.set_by,
                'reason': mode.reason
            },
            'restrictions': self.mode_router.get_mode_restrictions(mode)
        }

    def should_task_run(self, task_name: str, vendor_name: Optional[str] = None) -> Tuple[bool, str]:
        """
        Combined check: Should this task run given DEFCON and Mode?

        Returns:
            Tuple of (should_run, reason)
        """
        # Check DEFCON
        defcon_decision = self.defcon_router.should_task_run(task_name)
        if not defcon_decision.should_run:
            return False, defcon_decision.reason

        # Check vendor in mode if specified
        if vendor_name:
            vendor_allowed, vendor_reason = self.mode_router.is_vendor_allowed(vendor_name)
            if not vendor_allowed:
                return False, vendor_reason

            # Also check DEFCON vendor restrictions
            if vendor_name in defcon_decision.vendor_restrictions:
                return False, f"Vendor {vendor_name} restricted at DEFCON {self.defcon_router.get_current_defcon().level.value}"

        return True, defcon_decision.reason

    def filter_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter tasks based on DEFCON and Mode"""
        return self.defcon_router.filter_tasks_for_defcon(tasks)


# =============================================================================
# Convenience functions
# =============================================================================

_combined_router: Optional[CombinedRouter] = None

def get_router() -> CombinedRouter:
    """Get or create singleton CombinedRouter instance"""
    global _combined_router
    if _combined_router is None:
        host = os.getenv("PGHOST", "127.0.0.1")
        port = os.getenv("PGPORT", "54322")
        database = os.getenv("PGDATABASE", "postgres")
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "postgres")
        conn_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        _combined_router = CombinedRouter(conn_string)
    return _combined_router


def get_system_state() -> Dict[str, Any]:
    """Get current system state (DEFCON + Mode)"""
    return get_router().get_system_state()


if __name__ == "__main__":
    # Test the routers
    logging.basicConfig(level=logging.INFO)

    router = get_router()

    print("\n=== SYSTEM STATE ===")
    state = router.get_system_state()
    print(f"DEFCON: {state['defcon']['level']}")
    print(f"Mode: {state['mode']['mode']}")
    print(f"Restrictions: {state['restrictions']}")

    print("\n=== TASK DECISIONS ===")
    test_tasks = [
        'ios003_daily_regime_update',
        'daily_ingest_worker',
        'ios012_g3_system_loop',
        'finn_night_research_executor'
    ]

    for task in test_tasks:
        should_run, reason = router.should_task_run(task)
        status = "RUN" if should_run else "SKIP"
        print(f"[{status}] {task}: {reason}")
