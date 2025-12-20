#!/usr/bin/env python3
"""
CONTEXT INJECTION LAYER (CIL)
==============================
CEO DIRECTIVE: CI-20251209
Authority: ADR-020 Section 3.2 (InForage) + 3.3 (IKEA)

Purpose: Ensure NO DeepSeek call is made without structured context.

A brain without context hallucinates.
A brain with context perceives.
We do not hallucinate in FjordHQ.
"""

import os
import json
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict


# =============================================================================
# EXCEPTIONS
# =============================================================================

class ContextViabilityError(Exception):
    """Raised when context fails minimum viability check"""
    pass


class GovernanceDiscrepancyError(Exception):
    """Raised when governance constraints are violated"""
    pass


# =============================================================================
# CONTEXT DATA STRUCTURES
# =============================================================================

@dataclass
class MarketClock:
    """2.1 Market Clock - LINE responsibility"""
    current_datetime: str
    time_since_last_event_seconds: Optional[float] = None
    market_session: Optional[str] = None  # PRE_MARKET, REGULAR, AFTER_HOURS, CLOSED


@dataclass
class MarketState:
    """2.2 Market State - IoS-001/003/009"""
    btc_price: Optional[float] = None
    eth_price: Optional[float] = None
    usd_nok: Optional[float] = None
    current_regime: Optional[str] = None  # RISK-ON, RISK-OFF, TRANSITIONAL
    perception_summary: Optional[Dict[str, Any]] = None


@dataclass
class MemoryContext:
    """2.3 Memory Context - fhq_memory"""
    last_episodic_memory: Optional[str] = None
    permanent_causal_truths: Optional[List[str]] = None
    semantic_hits: Optional[List[Dict[str, Any]]] = None


@dataclass
class EventContext:
    """2.4 Events - fhq_governance.system_events"""
    recent_events: Optional[List[Dict[str, Any]]] = None  # Max 3


@dataclass
class SystemContext:
    """Complete system context for LLM injection"""
    market_clock: MarketClock
    market_state: MarketState
    memory_context: MemoryContext
    event_context: EventContext
    context_hash: Optional[str] = None
    context_fields_present: Optional[List[str]] = None
    retrieved_at: Optional[str] = None

    def to_prompt_block(self) -> str:
        """Format context as structured prompt block"""
        lines = [
            "=" * 60,
            "SYSTEM CONTEXT (CI-20251209 Mandatory Injection)",
            "=" * 60,
            "",
            "## MARKET CLOCK",
            f"  Current DateTime: {self.market_clock.current_datetime}",
            f"  Time Since Last Event: {self.market_clock.time_since_last_event_seconds or 'N/A'} seconds",
            f"  Market Session: {self.market_clock.market_session or 'UNKNOWN'}",
            "",
            "## MARKET STATE",
            f"  BTC Price: ${self.market_state.btc_price:,.2f}" if self.market_state.btc_price else "  BTC Price: N/A",
            f"  ETH Price: ${self.market_state.eth_price:,.2f}" if self.market_state.eth_price else "  ETH Price: N/A",
            f"  USD/NOK: {self.market_state.usd_nok:.4f}" if self.market_state.usd_nok else "  USD/NOK: N/A",
            f"  Current Regime: {self.market_state.current_regime or 'UNKNOWN'}",
        ]

        if self.market_state.perception_summary:
            lines.append("  Perception Summary:")
            for k, v in self.market_state.perception_summary.items():
                lines.append(f"    - {k}: {v}")

        lines.extend([
            "",
            "## MEMORY CONTEXT",
        ])

        if self.memory_context.last_episodic_memory:
            lines.append(f"  Last Episode: {self.memory_context.last_episodic_memory[:200]}...")

        if self.memory_context.permanent_causal_truths:
            lines.append("  Permanent Causal Truths:")
            for truth in self.memory_context.permanent_causal_truths[:3]:
                lines.append(f"    - {truth}")

        if self.memory_context.semantic_hits:
            lines.append("  Semantic Hits:")
            for hit in self.memory_context.semantic_hits[:3]:
                lines.append(f"    - {hit.get('summary', 'N/A')} (relevance: {hit.get('relevance', 'N/A')})")

        lines.extend([
            "",
            "## RECENT EVENTS (Max 3)",
        ])

        if self.event_context.recent_events:
            for evt in self.event_context.recent_events[:3]:
                lines.append(f"  - [{evt.get('event_type', 'N/A')}] {evt.get('event_title', 'N/A')} @ {evt.get('created_at', 'N/A')}")
        else:
            lines.append("  No recent events")

        lines.extend([
            "",
            "## CONTEXT METADATA",
            f"  Context Hash: {self.context_hash or 'N/A'}",
            f"  Retrieved At: {self.retrieved_at or 'N/A'}",
            f"  Fields Present: {', '.join(self.context_fields_present or [])}",
            "",
            "=" * 60,
            ""
        ])

        return "\n".join(lines)


# =============================================================================
# CONTEXT RETRIEVAL
# =============================================================================

class ContextRetriever:
    """Retrieves system context from database"""

    def __init__(self, connection_string: Optional[str] = None):
        self.connection_string = connection_string or self._get_connection_string()
        self.conn = None

    @staticmethod
    def _get_connection_string() -> str:
        host = os.getenv("PGHOST", "127.0.0.1")
        port = os.getenv("PGPORT", "54322")
        database = os.getenv("PGDATABASE", "postgres")
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "postgres")
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    def connect(self):
        if not self.conn or self.conn.closed:
            self.conn = psycopg2.connect(self.connection_string)
        return self.conn

    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()

    def get_market_clock(self) -> MarketClock:
        """Retrieve market clock from LINE"""
        conn = self.connect()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get time since last event
            cur.execute("""
                SELECT
                    EXTRACT(EPOCH FROM (NOW() - MAX(created_at))) as seconds_since_event
                FROM fhq_governance.system_events
            """)
            row = cur.fetchone()
            time_since = row['seconds_since_event'] if row else None

            # Determine market session (simplified)
            hour = datetime.now(timezone.utc).hour
            if 13 <= hour < 20:  # Roughly US market hours in UTC
                session = "REGULAR"
            elif 9 <= hour < 13:
                session = "PRE_MARKET"
            elif 20 <= hour < 24:
                session = "AFTER_HOURS"
            else:
                session = "CLOSED"

        return MarketClock(
            current_datetime=datetime.now(timezone.utc).isoformat(),
            time_since_last_event_seconds=float(time_since) if time_since else None,
            market_session=session
        )

    def get_market_state(self) -> MarketState:
        """Retrieve market state from IoS-001/003/009"""
        conn = self.connect()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get current regime
            cur.execute("""
                SELECT current_regime FROM fhq_meta.regime_state LIMIT 1
            """)
            regime_row = cur.fetchone()
            regime = regime_row['current_regime'] if regime_row else None

            # Get latest prices from canonical price table (fhq_market.prices)
            btc_price = None
            eth_price = None
            usd_nok = None

            try:
                cur.execute("""
                    SELECT canonical_id, close, timestamp
                    FROM fhq_market.prices
                    WHERE canonical_id IN ('BTC-USD', 'ETH-USD', 'USDNOK')
                    AND timestamp = (
                        SELECT MAX(timestamp) FROM fhq_market.prices
                        WHERE canonical_id = fhq_market.prices.canonical_id
                    )
                """)
                for row in cur.fetchall():
                    if row['canonical_id'] == 'BTC-USD':
                        btc_price = float(row['close'])
                    elif row['canonical_id'] == 'ETH-USD':
                        eth_price = float(row['close'])
                    elif row['canonical_id'] == 'USDNOK':
                        usd_nok = float(row['close'])
            except Exception as e:
                print(f"[WARN] Price fetch error: {e}")

            # Get perception summary if available
            perception = None
            try:
                cur.execute("""
                    SELECT perception_type, perception_value, confidence
                    FROM fhq_perception.current_state
                    ORDER BY updated_at DESC
                    LIMIT 3
                """)
                rows = cur.fetchall()
                if rows:
                    perception = {row['perception_type']: row['perception_value'] for row in rows}
            except Exception:
                pass

        return MarketState(
            btc_price=btc_price,
            eth_price=eth_price,
            usd_nok=usd_nok,
            current_regime=regime,
            perception_summary=perception
        )

    def get_memory_context(self, regime_filter: Optional[str] = None) -> MemoryContext:
        """Retrieve memory context from fhq_memory"""
        # Use fresh connection to avoid transaction issues
        conn = psycopg2.connect(self.connection_string)
        last_episode = None
        truths = []
        hits = []

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get last episodic memory
                try:
                    cur.execute("""
                        SELECT episode_title, episode_description, created_at
                        FROM fhq_memory.episodic_memory
                        ORDER BY created_at DESC
                        LIMIT 1
                    """)
                    row = cur.fetchone()
                    if row:
                        last_episode = f"{row['episode_title']}: {row['episode_description']}"
                except Exception as e:
                    print(f"[WARN] Episodic memory fetch error: {e}")

                # Get permanent causal truths
                try:
                    cur.execute("""
                        SELECT content_text, content_summary
                        FROM fhq_memory.embedding_store
                        WHERE is_eternal_truth = TRUE
                        ORDER BY created_at DESC
                        LIMIT 5
                    """)
                    truths = [row['content_summary'] or row['content_text'] for row in cur.fetchall()]
                except Exception as e:
                    print(f"[WARN] Eternal truths fetch error: {e}")
        finally:
            conn.close()

        return MemoryContext(
            last_episodic_memory=last_episode,
            permanent_causal_truths=truths if truths else None,
            semantic_hits=hits if hits else None
        )

    def get_event_context(self) -> EventContext:
        """Retrieve recent events from fhq_governance.system_events"""
        # Use fresh connection to avoid transaction issues
        conn = psycopg2.connect(self.connection_string)
        events = []

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        event_type,
                        event_category,
                        event_title,
                        event_severity,
                        regime,
                        created_at
                    FROM fhq_governance.system_events
                    WHERE event_category IN ('REGIME', 'SIGNAL', 'CEIO', 'ALPHA_GRAPH', 'PERCEPTION')
                    ORDER BY created_at DESC
                    LIMIT 3
                """)
                for row in cur.fetchall():
                    events.append({
                        'event_type': row['event_type'],
                        'event_category': row['event_category'],
                        'event_title': row['event_title'],
                        'event_severity': row['event_severity'],
                        'regime': row['regime'],
                        'created_at': row['created_at'].isoformat() if row['created_at'] else None
                    })
        except Exception as e:
            print(f"[WARN] Event fetch error: {e}")
        finally:
            conn.close()

        return EventContext(recent_events=events if events else None)

    def retrieve_full_context(self) -> SystemContext:
        """Retrieve complete system context"""
        market_clock = self.get_market_clock()
        market_state = self.get_market_state()
        memory_context = self.get_memory_context(regime_filter=market_state.current_regime)
        event_context = self.get_event_context()

        # Calculate fields present
        fields_present = []
        if market_clock.current_datetime:
            fields_present.append("timestamp")
        if market_state.btc_price or market_state.eth_price:
            fields_present.append("price")
        if market_state.current_regime:
            fields_present.append("regime")
        if memory_context.last_episodic_memory or memory_context.permanent_causal_truths:
            fields_present.append("memory_snapshot")
        if event_context.recent_events:
            fields_present.append("events")

        # Create context object
        context = SystemContext(
            market_clock=market_clock,
            market_state=market_state,
            memory_context=memory_context,
            event_context=event_context,
            context_fields_present=fields_present,
            retrieved_at=datetime.now(timezone.utc).isoformat()
        )

        # Calculate context hash
        context_dict = {
            "clock": asdict(market_clock),
            "state": asdict(market_state),
            "memory": asdict(memory_context),
            "events": asdict(event_context)
        }
        context.context_hash = hashlib.sha256(
            json.dumps(context_dict, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

        return context


# =============================================================================
# CONTEXT VIABILITY CHECK (CVC)
# =============================================================================

def context_minimum_viability_check(context: SystemContext) -> Tuple[bool, List[str]]:
    """
    CEO DIRECTIVE CI-20251209 Section 3: Context Viability Check

    Required fields:
    - price (BTC or ETH)
    - regime
    - timestamp
    - memory snapshot
    - at least 1 event

    Returns:
        Tuple of (is_viable, missing_fields)
    """
    missing = []

    # Check timestamp
    if not context.market_clock.current_datetime:
        missing.append("timestamp")

    # Check price (at least one)
    if not context.market_state.btc_price and not context.market_state.eth_price:
        missing.append("price")

    # Check regime
    if not context.market_state.current_regime:
        missing.append("regime")

    # Check memory snapshot
    if not context.memory_context.last_episodic_memory and not context.memory_context.permanent_causal_truths:
        missing.append("memory_snapshot")

    # Check events (at least 1)
    if not context.event_context.recent_events or len(context.event_context.recent_events) == 0:
        missing.append("events")

    is_viable = len(missing) == 0
    return is_viable, missing


def log_governance_discrepancy(
    missing_fields: List[str],
    severity: str = "MEDIUM",
    connection_string: Optional[str] = None
) -> None:
    """Log governance discrepancy for context viability failure"""
    conn_str = connection_string or ContextRetriever._get_connection_string()

    try:
        conn = psycopg2.connect(conn_str)
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_type,
                    agent_id,
                    action_category,
                    decision,
                    metadata,
                    timestamp
                ) VALUES (
                    'CONTEXT_VIABILITY_FAILURE',
                    'STIG',
                    'DISCREPANCY',
                    'BLOCKED',
                    %s,
                    NOW()
                )
            """, (json.dumps({
                "missing_fields": missing_fields,
                "severity": severity,
                "directive": "CI-20251209"
            }),))
            conn.commit()
    except Exception as e:
        print(f"[WARNING] Failed to log governance discrepancy: {e}")
    finally:
        if conn:
            conn.close()


# =============================================================================
# CONTEXT-INJECTED PROMPT BUILDER
# =============================================================================

def build_contextualized_prompt(
    user_prompt: str,
    system_prompt: str = "",
    require_viable_context: bool = True
) -> Tuple[str, str, SystemContext]:
    """
    Build a contextualized prompt with mandatory system context injection.

    Args:
        user_prompt: The original user/agent request
        system_prompt: Optional system prompt
        require_viable_context: If True, raises error on viability failure

    Returns:
        Tuple of (final_system_prompt, final_user_prompt, context)

    Raises:
        ContextViabilityError: If context fails viability check and required
    """
    # Retrieve context
    retriever = ContextRetriever()
    try:
        context = retriever.retrieve_full_context()
    finally:
        retriever.close()

    # Viability check
    is_viable, missing = context_minimum_viability_check(context)

    if not is_viable:
        log_governance_discrepancy(missing, severity="MEDIUM")
        if require_viable_context:
            raise ContextViabilityError(
                f"Context failed minimum viability check. Missing: {missing}. "
                f"DeepSeek call BLOCKED per CI-20251209."
            )

    # Build final prompts
    context_block = context.to_prompt_block()

    final_system_prompt = f"""{system_prompt}

IMPORTANT: You MUST use the SYSTEM CONTEXT provided below for all reasoning.
Do NOT reference your training data for current market conditions.
Begin your response with "Given the provided context..." to confirm context awareness.

{context_block}"""

    final_user_prompt = f"""USER REQUEST:
{user_prompt}

INSTRUCTION: Base your analysis ONLY on the SYSTEM CONTEXT provided above.
Reference specific values (prices, regime, events) from the context."""

    return final_system_prompt, final_user_prompt, context


# =============================================================================
# TEST FUNCTION
# =============================================================================

def test_context_injection():
    """Test the context injection layer"""
    print("\n" + "=" * 60)
    print("TESTING CONTEXT INJECTION LAYER (CI-20251209)")
    print("=" * 60)

    retriever = ContextRetriever()
    try:
        context = retriever.retrieve_full_context()
        print(f"\n[OK] Context retrieved")
        print(f"[OK] Context hash: {context.context_hash}")
        print(f"[OK] Fields present: {context.context_fields_present}")

        # Viability check
        is_viable, missing = context_minimum_viability_check(context)
        print(f"\n[{'OK' if is_viable else 'WARN'}] Viability check: {'PASSED' if is_viable else 'FAILED'}")
        if missing:
            print(f"[WARN] Missing fields: {missing}")

        # Print context block
        print("\n" + context.to_prompt_block())

    finally:
        retriever.close()


if __name__ == "__main__":
    test_context_injection()
