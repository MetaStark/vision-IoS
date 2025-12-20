#!/usr/bin/env python3
"""
CIRCUIT BREAKER WRAPPER (STIG-2025-001 Compliant)
=================================================
Authority: STIG (CTO)
ADR Reference: ADR-016 DEFCON Protocol, STIG-2025-001 Directive
Classification: Tier-1 Infrastructure Critical

Implements pybreaker-style circuit breaker with FjordHQ DEFCON integration.
State Machine: CLOSED -> OPEN -> HALF-OPEN -> CLOSED

Usage:
    from circuit_breaker_wrapper import trading_breaker, TradingCircuitBreaker

    @trading_breaker
    def execute_order(signal):
        # Order logic
        pass
"""

import os
import time
import json
import functools
import threading
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
from typing import Callable, Any, Optional, List, Dict
from enum import Enum
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


class CircuitState(Enum):
    """Circuit breaker states per STIG-2025-001"""
    CLOSED = "CLOSED"       # Normal operation
    OPEN = "OPEN"           # Kill switch active - all calls rejected
    HALF_OPEN = "HALF_OPEN" # Probe mode - testing recovery


class DEFCONLevel(Enum):
    """DEFCON levels per ADR-016"""
    GREEN = 5   # Full operation
    BLUE = 4    # Reduce new positions 25%
    YELLOW = 3  # Shadow mode only
    ORANGE = 2  # Close 50% positions
    RED = 1     # Emergency close all


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    fail_max: int = 5                    # Failures before OPEN
    reset_timeout: int = 300             # Seconds before HALF-OPEN
    success_threshold: int = 3           # Successes needed to close
    excluded_exceptions: tuple = field(default_factory=lambda: (ValueError,))
    name: str = "trading_breaker"

    # DEFCON integration
    defcon_enabled: bool = True
    defcon_yellow_threshold: float = -500.0   # Daily loss -> YELLOW
    defcon_orange_threshold: float = -1000.0  # Drawdown -> ORANGE


class CircuitBreakerError(Exception):
    """Raised when circuit is OPEN"""
    pass


class TradingCircuitBreaker:
    """
    Trading-specific circuit breaker with DEFCON integration.

    Implements STIG-2025-001 mandatory circuit breaker pattern:
    - CLOSED: Normal trading, all calls pass
    - OPEN: Kill switch, all trading calls rejected
    - HALF-OPEN: Probe mode, limited calls allowed

    DEFCON Integration:
    - Syncs with fhq_monitoring.defcon_status
    - Auto-opens on DEFCON YELLOW or worse
    - Logs all state transitions to database
    """

    def __init__(self, config: CircuitBreakerConfig = None):
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._lock = threading.RLock()

        # Statistics
        self._stats = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'rejected_calls': 0,
            'state_transitions': []
        }

    @property
    def state(self) -> CircuitState:
        """Current circuit state with timeout check"""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to(CircuitState.HALF_OPEN)
            return self._state

    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        """Check if reset_timeout has passed"""
        if self._last_failure_time is None:
            return True
        elapsed = (datetime.now(timezone.utc) - self._last_failure_time).total_seconds()
        return elapsed >= self.config.reset_timeout

    def _transition_to(self, new_state: CircuitState, reason: str = None):
        """Record state transition"""
        old_state = self._state
        self._state = new_state

        transition = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'from_state': old_state.value,
            'to_state': new_state.value,
            'reason': reason or 'automatic',
            'failure_count': self._failure_count,
            'success_count': self._success_count
        }
        self._stats['state_transitions'].append(transition)

        # Log to database
        self._log_transition(transition)

        # Reset counters on state change
        if new_state == CircuitState.HALF_OPEN:
            self._success_count = 0
        elif new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0

    def _log_transition(self, transition: Dict):
        """Log state transition to database"""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_monitoring.circuit_breaker_events
                    (breaker_name, from_state, to_state, reason, metadata, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    ON CONFLICT DO NOTHING
                """, (
                    self.config.name,
                    transition['from_state'],
                    transition['to_state'],
                    transition['reason'],
                    json.dumps(transition)
                ))
                conn.commit()
            conn.close()
        except Exception as e:
            # Don't fail on logging errors
            print(f"[CIRCUIT_BREAKER] Log error: {e}")

    def _check_defcon(self) -> DEFCONLevel:
        """Check current DEFCON level from database"""
        if not self.config.defcon_enabled:
            return DEFCONLevel.GREEN

        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT current_level, trigger_reason
                    FROM fhq_monitoring.defcon_status
                    ORDER BY activated_at DESC
                    LIMIT 1
                """)
                result = cur.fetchone()
            conn.close()

            if result:
                level_map = {
                    'GREEN': DEFCONLevel.GREEN,
                    'BLUE': DEFCONLevel.BLUE,
                    'YELLOW': DEFCONLevel.YELLOW,
                    'ORANGE': DEFCONLevel.ORANGE,
                    'RED': DEFCONLevel.RED
                }
                return level_map.get(result['current_level'], DEFCONLevel.GREEN)
            return DEFCONLevel.GREEN
        except Exception:
            return DEFCONLevel.GREEN

    def _record_success(self):
        """Record successful call"""
        with self._lock:
            self._stats['successful_calls'] += 1

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED, "recovery_success")

    def _record_failure(self, exception: Exception):
        """Record failed call"""
        with self._lock:
            self._stats['failed_calls'] += 1
            self._failure_count += 1
            self._last_failure_time = datetime.now(timezone.utc)

            if self._state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN, f"probe_failed: {type(exception).__name__}")
            elif self._failure_count >= self.config.fail_max:
                self._transition_to(CircuitState.OPEN, f"threshold_exceeded: {self._failure_count} failures")

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker"""
        with self._lock:
            self._stats['total_calls'] += 1

        # Check DEFCON level
        defcon = self._check_defcon()
        if defcon.value <= DEFCONLevel.YELLOW.value:
            with self._lock:
                if self._state != CircuitState.OPEN:
                    self._transition_to(CircuitState.OPEN, f"defcon_{defcon.name}")

        # Check circuit state
        current_state = self.state

        if current_state == CircuitState.OPEN:
            self._stats['rejected_calls'] += 1
            raise CircuitBreakerError(
                f"Circuit breaker '{self.config.name}' is OPEN. "
                f"Failures: {self._failure_count}, Last failure: {self._last_failure_time}"
            )

        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except self.config.excluded_exceptions:
            # Don't count excluded exceptions as failures
            raise
        except Exception as e:
            self._record_failure(e)
            raise

    def __call__(self, func: Callable) -> Callable:
        """Decorator interface"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return wrapper

    def force_open(self, reason: str = "manual"):
        """Manually open the circuit"""
        with self._lock:
            self._transition_to(CircuitState.OPEN, f"forced: {reason}")

    def force_close(self, reason: str = "manual"):
        """Manually close the circuit (use with caution)"""
        with self._lock:
            self._failure_count = 0
            self._success_count = 0
            self._transition_to(CircuitState.CLOSED, f"forced: {reason}")

    def get_stats(self) -> Dict:
        """Get circuit breaker statistics"""
        with self._lock:
            return {
                'name': self.config.name,
                'state': self._state.value,
                'failure_count': self._failure_count,
                'success_count': self._success_count,
                'config': {
                    'fail_max': self.config.fail_max,
                    'reset_timeout': self.config.reset_timeout,
                    'success_threshold': self.config.success_threshold
                },
                **self._stats
            }


# Global trading circuit breaker instance
trading_breaker = TradingCircuitBreaker(CircuitBreakerConfig(
    name="trading_breaker",
    fail_max=5,
    reset_timeout=300,
    success_threshold=3,
    excluded_exceptions=(ValueError, TypeError),
    defcon_enabled=True
))

# Strategy-specific breakers
strategy_breakers = {
    'statarb': TradingCircuitBreaker(CircuitBreakerConfig(
        name="statarb_breaker",
        fail_max=3,
        reset_timeout=600
    )),
    'grid': TradingCircuitBreaker(CircuitBreakerConfig(
        name="grid_breaker",
        fail_max=3,
        reset_timeout=600
    )),
    'meanrev': TradingCircuitBreaker(CircuitBreakerConfig(
        name="meanrev_breaker",
        fail_max=5,
        reset_timeout=300
    )),
    'volatility': TradingCircuitBreaker(CircuitBreakerConfig(
        name="volatility_breaker",
        fail_max=5,
        reset_timeout=300
    ))
}


def get_breaker(strategy: str) -> TradingCircuitBreaker:
    """Get circuit breaker for specific strategy"""
    return strategy_breakers.get(strategy, trading_breaker)


def check_all_breakers() -> Dict[str, Dict]:
    """Get status of all circuit breakers"""
    result = {'global': trading_breaker.get_stats()}
    for name, breaker in strategy_breakers.items():
        result[name] = breaker.get_stats()
    return result


if __name__ == "__main__":
    # Self-test
    print("=" * 60)
    print("CIRCUIT BREAKER WRAPPER - SELF TEST")
    print("=" * 60)

    # Test basic functionality
    @trading_breaker
    def test_success():
        return "SUCCESS"

    @trading_breaker
    def test_failure():
        raise RuntimeError("Simulated failure")

    print(f"\n[1] Initial state: {trading_breaker.state.value}")

    # Test successful calls
    for i in range(3):
        result = test_success()
        print(f"[2] Call {i+1}: {result}")

    print(f"[3] State after success: {trading_breaker.state.value}")
    print(f"[4] Stats: {json.dumps(trading_breaker.get_stats(), indent=2)}")

    # Test failure threshold
    print("\n[5] Testing failure threshold...")
    for i in range(6):
        try:
            test_failure()
        except CircuitBreakerError as e:
            print(f"    Circuit OPEN: {e}")
            break
        except RuntimeError:
            print(f"    Failure {i+1} recorded")

    print(f"[6] Final state: {trading_breaker.state.value}")
    print(f"[7] All breakers: {json.dumps(check_all_breakers(), indent=2, default=str)}")

    print("\n" + "=" * 60)
    print("CIRCUIT BREAKER WRAPPER - TEST COMPLETE")
    print("=" * 60)
