#!/usr/bin/env python3
"""
FHQ DOMAIN CONTROLLER
======================
CEO Directive: ARO-20251209/AUTONOMY_ENFORCEMENT_V2
Reference: ADR-016 (DEFCON Protocol)

Architectural Decoupling of Failure Domains:
- Domain A (Ingestion): fhq-streamer. Priority 0. MUST NEVER STOP.
- Domain B (Reasoning): fhq-brain. Priority 1. Can pause/restart.

DEFCON Levels:
- GREEN: All systems nominal
- YELLOW: Domain B degraded (LLM suspended)
- ORANGE: Domain A degraded (ingestion issues)
- RED: Domain A failure (CRITICAL)
"""

import os
import sys
import time
import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment
load_dotenv(Path(__file__).parent.parent / '.env')

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("FHQ_DOMAIN_CONTROLLER")


class DefconLevel(Enum):
    """DEFCON levels per ADR-016."""
    GREEN = "GREEN"    # All systems nominal
    YELLOW = "YELLOW"  # Domain B degraded
    ORANGE = "ORANGE"  # Domain A degraded
    RED = "RED"        # Domain A failure - CRITICAL


class DomainStatus(Enum):
    """Domain operational status."""
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    SUSPENDED = "SUSPENDED"
    FAILED = "FAILED"


@dataclass
class DomainHealth:
    """Health status for a domain."""
    domain: str
    status: DomainStatus
    last_heartbeat: Optional[datetime]
    heartbeat_age_seconds: float
    process_running: bool
    error_message: Optional[str] = None


@dataclass
class SystemState:
    """Overall system state."""
    defcon: DefconLevel
    domain_a_ingestion: DomainHealth
    domain_b_reasoning: DomainHealth
    timestamp: datetime
    llm_provider: str
    llm_model: str
    data_freshness_seconds: float


def get_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv('PGHOST', '127.0.0.1'),
        port=int(os.getenv('PGPORT', 54322)),
        database=os.getenv('PGDATABASE', 'postgres'),
        user=os.getenv('PGUSER', 'postgres'),
        password=os.getenv('PGPASSWORD', 'postgres')
    )


def check_domain_a_ingestion() -> DomainHealth:
    """
    Check Domain A (Ingestion) health.
    Priority 0 - MUST NEVER STOP.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Check latest streamer heartbeat
        cur.execute("""
            SELECT MAX(created_at) as last_heartbeat
            FROM fhq_governance.system_events
            WHERE event_type = 'STREAMER_HEARTBEAT'
        """)
        row = cur.fetchone()
        last_heartbeat = row[0] if row and row[0] else None

        # Check latest price timestamp
        cur.execute("SELECT MAX(timestamp) FROM fhq_market.prices")
        row = cur.fetchone()
        latest_price = row[0] if row and row[0] else None

        cur.close()
        conn.close()

        now = datetime.now(timezone.utc)

        if last_heartbeat:
            if last_heartbeat.tzinfo is None:
                last_heartbeat = last_heartbeat.replace(tzinfo=timezone.utc)
            heartbeat_age = (now - last_heartbeat).total_seconds()
        else:
            heartbeat_age = float('inf')

        # Determine status
        if heartbeat_age < 60:
            status = DomainStatus.ACTIVE
        elif heartbeat_age < 300:
            status = DomainStatus.DEGRADED
        else:
            status = DomainStatus.FAILED

        return DomainHealth(
            domain="INGESTION",
            status=status,
            last_heartbeat=last_heartbeat,
            heartbeat_age_seconds=heartbeat_age,
            process_running=heartbeat_age < 120
        )

    except Exception as e:
        return DomainHealth(
            domain="INGESTION",
            status=DomainStatus.FAILED,
            last_heartbeat=None,
            heartbeat_age_seconds=float('inf'),
            process_running=False,
            error_message=str(e)
        )


def check_domain_b_reasoning() -> DomainHealth:
    """
    Check Domain B (Reasoning) health.
    Priority 1 - Can pause/restart.
    """
    # Check LLM configuration
    llm_provider = os.getenv('FHQ_LLM_PROVIDER', 'NOT_SET')
    llm_model = os.getenv('FHQ_LLM_MODEL', 'NOT_SET')
    deepseek_key = os.getenv('DEEPSEEK_API_KEY', '')

    if llm_provider != 'speciale' or not deepseek_key:
        return DomainHealth(
            domain="REASONING",
            status=DomainStatus.SUSPENDED,
            last_heartbeat=None,
            heartbeat_age_seconds=0,
            process_running=False,
            error_message="LLM_SUSPENDED: Config not sealed or API key missing"
        )

    # For now, reasoning is available if config is correct
    return DomainHealth(
        domain="REASONING",
        status=DomainStatus.ACTIVE,
        last_heartbeat=datetime.now(timezone.utc),
        heartbeat_age_seconds=0,
        process_running=True
    )


def determine_defcon(domain_a: DomainHealth, domain_b: DomainHealth) -> DefconLevel:
    """Determine DEFCON level based on domain health."""
    if domain_a.status == DomainStatus.FAILED:
        return DefconLevel.RED
    elif domain_a.status == DomainStatus.DEGRADED:
        return DefconLevel.ORANGE
    elif domain_b.status in (DomainStatus.SUSPENDED, DomainStatus.DEGRADED, DomainStatus.FAILED):
        return DefconLevel.YELLOW
    else:
        return DefconLevel.GREEN


def get_system_state() -> SystemState:
    """Get comprehensive system state."""
    domain_a = check_domain_a_ingestion()
    domain_b = check_domain_b_reasoning()
    defcon = determine_defcon(domain_a, domain_b)

    # Get data freshness
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT MAX(timestamp) FROM fhq_market.prices")
        row = cur.fetchone()
        if row and row[0]:
            latest = row[0]
            if latest.tzinfo is None:
                latest = latest.replace(tzinfo=timezone.utc)
            data_freshness = (datetime.now(timezone.utc) - latest).total_seconds()
        else:
            data_freshness = float('inf')
        cur.close()
        conn.close()
    except:
        data_freshness = float('inf')

    return SystemState(
        defcon=defcon,
        domain_a_ingestion=domain_a,
        domain_b_reasoning=domain_b,
        timestamp=datetime.now(timezone.utc),
        llm_provider=os.getenv('FHQ_LLM_PROVIDER', 'NOT_SET'),
        llm_model=os.getenv('FHQ_LLM_MODEL', 'NOT_SET'),
        data_freshness_seconds=data_freshness
    )


def log_defcon_event(state: SystemState):
    """Log DEFCON status change to database."""
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO fhq_governance.system_events (event_type, event_data, created_at)
            VALUES ('DEFCON_STATUS', %s, NOW())
        """, (json.dumps({
            'defcon': state.defcon.value,
            'domain_a_status': state.domain_a_ingestion.status.value,
            'domain_b_status': state.domain_b_reasoning.status.value,
            'data_freshness_seconds': state.data_freshness_seconds
        }),))

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to log DEFCON event: {e}")


def print_status_report(state: SystemState):
    """Print formatted status report."""
    defcon_colors = {
        DefconLevel.GREEN: "NOMINAL",
        DefconLevel.YELLOW: "DEGRADED",
        DefconLevel.ORANGE: "WARNING",
        DefconLevel.RED: "CRITICAL"
    }

    print("=" * 70)
    print("FHQ DOMAIN CONTROLLER - SYSTEM STATUS")
    print("=" * 70)
    print(f"Timestamp: {state.timestamp.isoformat()}")
    print(f"DEFCON Level: {state.defcon.value} ({defcon_colors[state.defcon]})")
    print("-" * 70)

    print("\nDOMAIN A - INGESTION (Priority 0)")
    print(f"  Status: {state.domain_a_ingestion.status.value}")
    print(f"  Last Heartbeat: {state.domain_a_ingestion.last_heartbeat}")
    print(f"  Heartbeat Age: {state.domain_a_ingestion.heartbeat_age_seconds:.0f}s")
    print(f"  Process Running: {state.domain_a_ingestion.process_running}")
    if state.domain_a_ingestion.error_message:
        print(f"  Error: {state.domain_a_ingestion.error_message}")

    print("\nDOMAIN B - REASONING (Priority 1)")
    print(f"  Status: {state.domain_b_reasoning.status.value}")
    print(f"  LLM Provider: {state.llm_provider}")
    print(f"  LLM Model: {state.llm_model}")
    if state.domain_b_reasoning.error_message:
        print(f"  Note: {state.domain_b_reasoning.error_message}")

    print("\nDATA FRESHNESS")
    print(f"  Latest Price Age: {state.data_freshness_seconds:.0f}s")

    print("=" * 70)


def main():
    """Run domain controller status check."""
    state = get_system_state()
    print_status_report(state)
    log_defcon_event(state)

    # Return appropriate exit code
    if state.defcon == DefconLevel.RED:
        return 2
    elif state.defcon in (DefconLevel.ORANGE, DefconLevel.YELLOW):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
