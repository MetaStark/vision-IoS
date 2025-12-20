#!/usr/bin/env python3
"""
CRIO NIGHT WATCH - Deep Dive Mode
==================================
CEO Directive: THE NIGHT WATCH (PERSISTENCE & AUTONOMY)
Authority: STIG (CTO)
Date: 2025-12-09

PHASE 4a TELEMETRY INSTRUMENTATION (2025-12-10)
- CEO Directive 2026-FHQ-PHASE-4a
- CS-002 Night Research wrapped with @metered_execution
- CONTROLLED INSTRUMENTATION - NO BEHAVIOR CHANGE
- Compliance: ADR-012, ADR-018, ADR-020, ADR-021, TCS-v1, DC-v1

While the CEO sleeps, the machine hunts.

Target:
- 500 validated edges in Alpha Graph
- 500 saved reasoning traces in reward_traces
- Tokens burned: > 1M

Mode: Level 2 Causal Analysis (Time Lag & Beta)
- For each existing edge, probe deeper:
  - What is the time lag between cause and effect?
  - What is the beta (sensitivity) of the relationship?
  - What conditions amplify or dampen the relationship?
"""

import os
import sys
import json
import time
import uuid
import hashlib
import logging
import requests
import concurrent.futures
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment with override
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

# =============================================================================
# PHASE 4a: TELEMETRY INSTRUMENTATION (CS-002)
# =============================================================================
# CEO Directive 2026-FHQ-PHASE-4a requires telemetry wrapping of night_research
# This is the "safest possible first stitch" - no behavior change, only observability
#
# IMPORTANT: This instrumentation must be TRANSPARENT:
# - Output must be bit-identical to unwrapped behavior
# - No retries added
# - No reasoning entropy changes
# - No chain length changes

# Add parent path for fhq_telemetry import
sys.path.insert(0, str(Path(__file__).parent.parent / '03_FUNCTIONS'))

# Import telemetry (graceful fallback if unavailable)
TELEMETRY_ENABLED = False
try:
    from fhq_telemetry import meter_llm_call
    from fhq_telemetry.telemetry_envelope import TaskType, CognitiveModality
    TELEMETRY_ENABLED = True
except ImportError:
    # Telemetry not available - proceed without instrumentation
    pass

# Logging
LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'night_watch.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("NIGHT_WATCH")

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = 'https://api.deepseek.com/v1'
DEEPSEEK_MODEL = 'deepseek-reasoner'

# Night Watch Targets
TARGET_EDGES = 500
TARGET_TRACES = 500
TARGET_TOKENS = 1_000_000

# Parallel config
MAX_WORKERS = 5  # Conservative for night run
SLEEP_BETWEEN_BATCHES = 2  # Seconds

# =============================================================================
# PHASE 4a TELEMETRY HELPER
# =============================================================================
# This function captures telemetry AFTER the LLM call completes
# It does NOT modify the call flow - only observes and records
# Fail-safe: If telemetry fails, the original result is still returned

def _emit_telemetry(
    task_name: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: int,
    stream_mode: bool = True,
    error: Optional[Exception] = None,
    correlation_id: Optional[str] = None
) -> None:
    """
    Emit telemetry for an LLM call (PHASE 4a CS-002).

    IMPORTANT: This is a PASSIVE observer - it must never:
    - Modify the original response
    - Add retries
    - Block on failure
    - Change any behavior

    Args:
        task_name: Descriptive name for the task
        tokens_in: Input tokens from API response
        tokens_out: Output tokens from API response
        latency_ms: Wall-clock latency in milliseconds
        stream_mode: Whether streaming was used (deepseek-reasoner uses streaming)
        error: Exception if call failed
        correlation_id: Optional correlation ID for linking calls
    """
    if not TELEMETRY_ENABLED:
        return

    try:
        correlation_uuid = None
        if correlation_id:
            try:
                from uuid import UUID
                correlation_uuid = UUID(correlation_id)
            except (ValueError, TypeError):
                pass

        meter_llm_call(
            agent_id='CRIO_NIGHT_WATCH',
            task_name=task_name,
            task_type=TaskType.RESEARCH,
            provider='DEEPSEEK',
            model=DEEPSEEK_MODEL,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            stream_mode=stream_mode,
            error=error,
            correlation_id=correlation_uuid,
            cognitive_modality=CognitiveModality.CAUSAL
        )
        logger.debug(f"Telemetry emitted for {task_name}: {tokens_in}+{tokens_out} tokens")
    except Exception as e:
        # CRITICAL: Never let telemetry failure affect the main flow
        # Log warning but continue
        logger.warning(f"Telemetry emission failed (non-blocking): {e}")


# =============================================================================
# DATABASE
# =============================================================================

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def get_top_edges(limit: int = 20) -> List[Dict]:
    """Get top edges by evidence count for deep analysis."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT edge_id, source_node, target_node, edge_type,
               confidence, evidence_count, created_at
        FROM vision_signals.alpha_graph_edges
        WHERE is_active = true
        ORDER BY evidence_count DESC, confidence DESC
        LIMIT %s
    """, (limit,))

    edges = [dict(row) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return edges


def get_all_assets() -> List[Dict]:
    """Get all unique assets with prices."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        WITH latest_prices AS (
            SELECT DISTINCT ON (canonical_id)
                canonical_id,
                close as price,
                timestamp
            FROM fhq_market.prices
            WHERE timestamp > NOW() - INTERVAL '7 days'
            ORDER BY canonical_id, timestamp DESC
        )
        SELECT * FROM latest_prices
    """)

    assets = [dict(row) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return assets


def get_current_regime() -> Tuple[str, float, str]:
    """Get current market regime."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT regime_classification, crio_fragility_score, crio_dominant_driver
        FROM fhq_perception.regime_daily
        WHERE asset_id = 'BTC-USD'
        ORDER BY timestamp DESC LIMIT 1
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row if row else ('BULL', 0.45, 'LIQUIDITY')


def get_current_stats() -> Dict:
    """Get current edge and trace counts."""
    conn = get_connection()
    cur = conn.cursor()

    # Edge count
    cur.execute("SELECT COUNT(*) FROM vision_signals.alpha_graph_edges WHERE is_active = true")
    edge_count = cur.fetchone()[0]

    # Trace count
    cur.execute("SELECT COUNT(*) FROM fhq_optimization.reward_traces WHERE reasoning_trace IS NOT NULL")
    trace_count = cur.fetchone()[0]

    # Total tokens
    cur.execute("SELECT COALESCE(SUM(total_tokens), 0) FROM fhq_optimization.reward_traces")
    total_tokens = cur.fetchone()[0]

    cur.close()
    conn.close()

    return {
        'edges': edge_count,
        'traces': trace_count,
        'tokens': total_tokens
    }


def store_reasoning_trace(
    input_query: str,
    reasoning_trace: str,
    reasoning_tokens: int,
    total_tokens: int,
    session_id: str
) -> Optional[str]:
    """Store reasoning trace in database."""
    conn = get_connection()
    cur = conn.cursor()

    trace_id = str(uuid.uuid4())

    try:
        cur.execute("""
            INSERT INTO fhq_optimization.reward_traces
            (trace_id, agent_id, session_id, timestamp_utc, input_query,
             reasoning_trace, reasoning_tokens, total_tokens, model_used, created_at)
            VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, %s, NOW())
        """, (
            trace_id,
            'CRIO_NIGHT_WATCH',
            session_id,
            input_query[:1000],
            reasoning_trace,
            reasoning_tokens,
            total_tokens,
            DEEPSEEK_MODEL
        ))
        conn.commit()
        return trace_id
    except Exception as e:
        logger.error(f"Failed to store trace: {e}")
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()


def insert_edge(source: str, target: str, edge_type: str, confidence: float) -> bool:
    """Insert or update edge in Alpha Graph."""
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO vision_signals.alpha_graph_edges
            (edge_id, source_node, target_node, edge_type, confidence,
             causal_weight, is_active, evidence_count, last_validated, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, true, 1, NOW(), NOW())
            ON CONFLICT (source_node, target_node) DO UPDATE SET
                confidence = GREATEST(vision_signals.alpha_graph_edges.confidence, EXCLUDED.confidence),
                evidence_count = vision_signals.alpha_graph_edges.evidence_count + 1,
                last_validated = NOW()
        """, (
            str(uuid.uuid4()),
            source.upper().replace(' ', '_'),
            target.upper().replace(' ', '_'),
            edge_type.upper(),
            confidence,
            confidence
        ))
        conn.commit()
        return True
    except Exception as e:
        logger.debug(f"Edge insert error: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


# =============================================================================
# SNIPER LOGIC - CEO DIRECTIVE: ARO-20251209/NIGHTFIRE
# =============================================================================

# Track last trace for trade linkage
_last_trace_id = None


def set_last_trace_id(trace_id: str):
    """Set the last trace ID for shadow trade linkage."""
    global _last_trace_id
    _last_trace_id = trace_id


def get_current_price(asset_id: str) -> Optional[float]:
    """Get current price for an asset."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT close FROM fhq_market.prices
            WHERE canonical_id = %s
            ORDER BY timestamp DESC LIMIT 1
        """, (asset_id,))
        row = cur.fetchone()
        return float(row[0]) if row else None
    except:
        return None
    finally:
        cur.close()
        conn.close()


def create_shadow_trade(
    asset_id: str,
    direction: str,
    entry_price: float,
    confidence: float,
    hypothesis_id: str = None
) -> Optional[str]:
    """Create a shadow trade via the database function."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT fhq_execution.create_event_shadow_trade(
                p_trigger_event_id => %s,
                p_source_agent     => 'CRIO_NIGHT_WATCH',
                p_asset_id         => %s,
                p_direction        => %s,
                p_entry_price      => %s,
                p_entry_confidence => %s,
                p_hypothesis_id    => %s
            )
        """, (
            str(uuid.uuid4()),
            asset_id,
            direction,
            entry_price,
            confidence,
            hypothesis_id
        ))
        trade_id = cur.fetchone()[0]
        conn.commit()
        logger.info(f"SHADOW TRADE: {trade_id} | {direction} {asset_id} @ {entry_price} | conf={confidence}")
        return str(trade_id)
    except Exception as e:
        logger.error(f"Shadow trade error: {e}")
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()


def sniper_check_and_fire(source: str, target: str, edge_type: str, confidence: float, trace_id: str = None) -> bool:
    """
    SNIPER: Check if edge qualifies for trade and fire if so.
    CEO Criteria: conf >= 0.90, IMMEDIATE impact type
    """
    if confidence < 0.90:
        return False

    immediate_types = {'LEADS', 'AMPLIFIES', 'CORRELATES'}
    inverse_types = {'INVERSE', 'INHIBITS'}
    tradeable = {'BTC-USD', 'ETH-USD', 'SOL-USD', 'SPY', 'QQQ', 'AAPL', 'MSFT', 'NVDA'}

    edge_type_upper = edge_type.upper()
    if edge_type_upper not in immediate_types and edge_type_upper not in inverse_types:
        return False

    # Find tradeable asset
    source_upper = source.upper().replace(' ', '_')
    target_upper = target.upper().replace(' ', '_')

    asset_id = None
    direction = None

    if target_upper in tradeable:
        asset_id = target_upper
        direction = 'LONG' if edge_type_upper in immediate_types else 'SHORT'
    elif source_upper in tradeable:
        asset_id = source_upper
        direction = 'LONG' if edge_type_upper in immediate_types else 'SHORT'
    else:
        return False

    # Get price and fire
    price = get_current_price(asset_id)
    if not price:
        return False

    logger.info(f"SNIPER QUALIFIED: {source}->{target} conf={confidence} => {direction} {asset_id}")
    return create_shadow_trade(asset_id, direction, price, confidence, trace_id or _last_trace_id) is not None


# =============================================================================
# LEVEL 2 CAUSAL ANALYSIS
# =============================================================================

def level2_deep_dive(edge: Dict, regime: str, driver: str, session_id: str) -> Dict:
    """
    Level 2 Causal Analysis: Time Lag & Beta

    For an existing edge, probe deeper:
    - What is the time lag between cause and effect?
    - What is the beta (sensitivity)?
    - What conditions amplify or dampen the relationship?
    """

    prompt = f"""You are CRIO, a causal reasoning engine performing LEVEL 2 DEEP ANALYSIS.

EXISTING EDGE TO ANALYZE:
- Source: {edge['source_node']}
- Target: {edge['target_node']}
- Relation: {edge['edge_type']}
- Current Confidence: {edge['confidence']}
- Evidence Count: {edge['evidence_count']}

MARKET CONTEXT:
- Regime: {regime}
- Dominant Driver: {driver}
- Timestamp: {datetime.now(timezone.utc).isoformat()}

LEVEL 2 ANALYSIS TASKS:
1. TIME LAG: What is the typical delay between {edge['source_node']} movement and {edge['target_node']} response?
   - Immediate (< 1 hour)?
   - Intraday (1-24 hours)?
   - Multi-day (1-5 days)?
   - Regime-dependent?

2. BETA (SENSITIVITY): How sensitive is {edge['target_node']} to changes in {edge['source_node']}?
   - Low beta (< 0.5): Dampened response
   - Medium beta (0.5-1.5): Proportional response
   - High beta (> 1.5): Amplified response

3. CONDITIONAL FACTORS: What conditions strengthen or weaken this relationship?
   - In which regimes is the relationship strongest?
   - What other factors can override this relationship?

4. DERIVATIVE EDGES: Based on this analysis, what NEW edges should exist?
   - Related factors that feed into this relationship
   - Second-order effects we should track

Respond in JSON format:
{{
  "time_lag": {{
    "estimate": "IMMEDIATE|INTRADAY|MULTIDAY|REGIME_DEPENDENT",
    "hours_typical": 0-120,
    "confidence": 0.0-1.0,
    "reasoning": "explanation"
  }},
  "beta": {{
    "estimate": 0.0-3.0,
    "category": "LOW|MEDIUM|HIGH",
    "confidence": 0.0-1.0,
    "reasoning": "explanation"
  }},
  "conditions": [
    {{
      "factor": "FACTOR_NAME",
      "effect": "AMPLIFIES|DAMPENS|INVERTS",
      "reasoning": "explanation"
    }}
  ],
  "derivative_edges": [
    {{
      "source": "FACTOR",
      "target": "FACTOR",
      "relation": "LEADS|CORRELATES|INVERSE|AMPLIFIES|INHIBITS",
      "confidence": 0.85-1.0,
      "reasoning": "explanation (50+ words)"
    }}
  ],
  "insight": "Key insight from this deep analysis"
}}
"""

    # PHASE 4a: Capture start time for latency measurement
    _call_start_ms = int(time.time() * 1000)

    try:
        response = requests.post(
            f"{DEEPSEEK_API_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": "You are CRIO, a precise causal reasoning engine."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 2000,
                "temperature": 0.3
            },
            timeout=120
        )

        # PHASE 4a: Capture latency immediately after response
        _call_latency_ms = int(time.time() * 1000) - _call_start_ms

        if response.status_code == 200:
            data = response.json()
            content = data['choices'][0]['message']['content']
            reasoning = data['choices'][0]['message'].get('reasoning_content', '')

            usage = data.get('usage', {})
            total_tokens = usage.get('total_tokens', 0)
            reasoning_tokens = usage.get('completion_tokens_details', {}).get('reasoning_tokens', 0)
            prompt_tokens = usage.get('prompt_tokens', 0)
            completion_tokens = usage.get('completion_tokens', 0)

            # PHASE 4a TELEMETRY: Emit after extracting data, before any other processing
            _emit_telemetry(
                task_name='LEVEL2_DEEP_DIVE',
                tokens_in=prompt_tokens,
                tokens_out=completion_tokens,
                latency_ms=_call_latency_ms,
                stream_mode=True,  # deepseek-reasoner uses streaming
                correlation_id=session_id
            )

            # Store the reasoning trace and capture trace_id
            trace_id = None
            if reasoning:
                trace_id = store_reasoning_trace(
                    input_query=prompt,
                    reasoning_trace=reasoning,
                    reasoning_tokens=reasoning_tokens,
                    total_tokens=total_tokens,
                    session_id=session_id
                )
                if trace_id:
                    set_last_trace_id(trace_id)

            return {
                'success': True,
                'content': content,
                'reasoning_tokens': reasoning_tokens,
                'total_tokens': total_tokens,
                'edge': edge,
                'trace_id': trace_id
            }
        else:
            # PHASE 4a TELEMETRY: Emit error telemetry
            _emit_telemetry(
                task_name='LEVEL2_DEEP_DIVE',
                tokens_in=0,
                tokens_out=0,
                latency_ms=_call_latency_ms,
                error=Exception(f"API error {response.status_code}: {response.text[:200]}")
            )
            logger.error(f"API error: {response.status_code}")
            return {'success': False, 'error': response.text}

    except Exception as e:
        # PHASE 4a TELEMETRY: Emit exception telemetry
        _call_latency_ms = int(time.time() * 1000) - _call_start_ms
        _emit_telemetry(
            task_name='LEVEL2_DEEP_DIVE',
            tokens_in=0,
            tokens_out=0,
            latency_ms=_call_latency_ms,
            error=e
        )
        logger.error(f"Deep dive failed: {e}")
        return {'success': False, 'error': str(e)}


def process_deep_dive_result(result: Dict) -> int:
    """Process Level 2 analysis result and extract derivative edges."""
    if not result.get('success'):
        return 0

    content = result.get('content', '')
    edges_added = 0

    try:
        # Parse JSON
        json_str = content
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0]

        data = json.loads(json_str.strip())

        # Extract derivative edges
        derivative_edges = data.get('derivative_edges', [])
        for e in derivative_edges:
            conf = float(e.get('confidence', 0))
            if conf >= 0.85:
                if insert_edge(e['source'], e['target'], e['relation'], conf):
                    edges_added += 1
                    logger.info(f"  NEW EDGE: {e['source']} --{e['relation']}--> {e['target']}")
                    # CEO DIRECTIVE NIGHTFIRE: Check for shadow trade
                    if conf >= 0.90:
                        sniper_check_and_fire(e['source'], e['target'], e['relation'], conf)

        # Log insight
        insight = data.get('insight', '')
        if insight:
            logger.info(f"  INSIGHT: {insight[:100]}...")

    except Exception as e:
        logger.debug(f"Parse error: {e}")

    return edges_added


def broad_sweep(asset: str, price: float, regime: str, driver: str, session_id: str) -> Dict:
    """Broad sweep causal analysis for an asset."""

    prompt = f"""You are CRIO, a causal reasoning engine for financial markets.

BROAD SWEEP ANALYSIS for: {asset}
Current Price: ${price:,.2f}
Market Regime: {regime}
Dominant Driver: {driver}
Timestamp: {datetime.now(timezone.utc).isoformat()}

TASK: Identify ALL significant causal relationships involving {asset}.

Consider:
1. MACRO FACTORS: Fed policy, inflation, GDP, employment, dollar strength
2. SECTOR FACTORS: Industry trends, competitor dynamics, supply chain
3. TECHNICAL FACTORS: Momentum, support/resistance, volume patterns
4. CROSS-ASSET: Correlations with other assets, flight-to-safety dynamics
5. SENTIMENT: News flow, social media, institutional positioning

Generate 5-8 high-confidence edges. Be comprehensive.

Respond in JSON format:
{{
  "edges": [
    {{
      "source": "FACTOR_OR_ASSET",
      "target": "FACTOR_OR_ASSET",
      "relation": "LEADS|CORRELATES|INVERSE|AMPLIFIES|INHIBITS",
      "confidence": 0.85-1.0,
      "reasoning": "Brief causal explanation (50+ words)"
    }}
  ],
  "key_insight": "Most important causal relationship for {asset}"
}}
"""

    # PHASE 4a: Capture start time for latency measurement
    _call_start_ms = int(time.time() * 1000)

    try:
        response = requests.post(
            f"{DEEPSEEK_API_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": "You are CRIO, a precise causal reasoning engine."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 2000,
                "temperature": 0.3
            },
            timeout=120
        )

        # PHASE 4a: Capture latency immediately after response
        _call_latency_ms = int(time.time() * 1000) - _call_start_ms

        if response.status_code == 200:
            data = response.json()
            content = data['choices'][0]['message']['content']
            reasoning = data['choices'][0]['message'].get('reasoning_content', '')

            usage = data.get('usage', {})
            total_tokens = usage.get('total_tokens', 0)
            reasoning_tokens = usage.get('completion_tokens_details', {}).get('reasoning_tokens', 0)
            prompt_tokens = usage.get('prompt_tokens', 0)
            completion_tokens = usage.get('completion_tokens', 0)

            # PHASE 4a TELEMETRY: Emit after extracting data, before any other processing
            _emit_telemetry(
                task_name='BROAD_SWEEP',
                tokens_in=prompt_tokens,
                tokens_out=completion_tokens,
                latency_ms=_call_latency_ms,
                stream_mode=True,  # deepseek-reasoner uses streaming
                correlation_id=session_id
            )

            # Store the reasoning trace and capture trace_id
            trace_id = None
            if reasoning:
                trace_id = store_reasoning_trace(
                    input_query=prompt,
                    reasoning_trace=reasoning,
                    reasoning_tokens=reasoning_tokens,
                    total_tokens=total_tokens,
                    session_id=session_id
                )
                if trace_id:
                    set_last_trace_id(trace_id)

            return {
                'success': True,
                'content': content,
                'reasoning_tokens': reasoning_tokens,
                'total_tokens': total_tokens,
                'asset': asset,
                'trace_id': trace_id
            }
        else:
            # PHASE 4a TELEMETRY: Emit error telemetry
            _emit_telemetry(
                task_name='BROAD_SWEEP',
                tokens_in=0,
                tokens_out=0,
                latency_ms=_call_latency_ms,
                error=Exception(f"API error {response.status_code}")
            )
            logger.error(f"API error: {response.status_code}")
            return {'success': False}

    except Exception as e:
        # PHASE 4a TELEMETRY: Emit exception telemetry
        _call_latency_ms = int(time.time() * 1000) - _call_start_ms
        _emit_telemetry(
            task_name='BROAD_SWEEP',
            tokens_in=0,
            tokens_out=0,
            latency_ms=_call_latency_ms,
            error=e
        )
        logger.error(f"Broad sweep failed: {e}")
        return {'success': False}


def process_broad_sweep(result: Dict) -> int:
    """Process broad sweep and insert edges."""
    if not result.get('success'):
        return 0

    content = result.get('content', '')
    edges_added = 0

    try:
        json_str = content
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0]

        data = json.loads(json_str.strip())

        for e in data.get('edges', []):
            conf = float(e.get('confidence', 0))
            if conf >= 0.85:
                if insert_edge(e['source'], e['target'], e['relation'], conf):
                    edges_added += 1
                    logger.info(f"  NEW EDGE: {e['source']} --{e['relation']}--> {e['target']}")
                    # CEO DIRECTIVE NIGHTFIRE: Check for shadow trade
                    if conf >= 0.90:
                        sniper_check_and_fire(e['source'], e['target'], e['relation'], conf)

    except Exception as e:
        logger.debug(f"Parse error: {e}")

    return edges_added


# =============================================================================
# NIGHT WATCH MAIN LOOP
# =============================================================================

def night_watch():
    """
    The Night Watch: Hunt until targets are met.
    Target: 500 edges, 500 traces, 1M tokens
    """

    print("=" * 70)
    print("CRIO NIGHT WATCH - DEEP DIVE MODE")
    print("=" * 70)
    print(f"Model: {DEEPSEEK_MODEL}")
    print(f"Target Edges: {TARGET_EDGES}")
    print(f"Target Traces: {TARGET_TRACES}")
    print(f"Target Tokens: {TARGET_TOKENS:,}")
    print("=" * 70)

    if not DEEPSEEK_API_KEY:
        print("ERROR: DEEPSEEK_API_KEY not set!")
        return

    session_id = str(uuid.uuid4())
    regime, fragility, driver = get_current_regime()
    print(f"Session: {session_id[:8]}")
    print(f"Regime: {regime}, Driver: {driver}")
    print("-" * 70)

    # Get initial stats
    stats = get_current_stats()
    print(f"Starting: {stats['edges']} edges, {stats['traces']} traces, {stats['tokens']:,} tokens")

    cycle = 0

    while True:
        cycle += 1
        stats = get_current_stats()

        # Check if targets met
        if (stats['edges'] >= TARGET_EDGES and
            stats['traces'] >= TARGET_TRACES and
            stats['tokens'] >= TARGET_TOKENS):
            print("=" * 70)
            print("TARGETS MET! NIGHT WATCH COMPLETE")
            print(f"  Edges: {stats['edges']}")
            print(f"  Traces: {stats['traces']}")
            print(f"  Tokens: {stats['tokens']:,}")
            print("=" * 70)
            break

        print(f"\n--- Cycle {cycle} ---")
        print(f"Progress: {stats['edges']}/{TARGET_EDGES} edges, "
              f"{stats['traces']}/{TARGET_TRACES} traces, "
              f"{stats['tokens']:,}/{TARGET_TOKENS:,} tokens")

        # Phase 1: Deep dive on top edges
        top_edges = get_top_edges(20)
        if top_edges:
            print(f"Phase 1: Deep dive on {len(top_edges)} top edges")

            for edge in top_edges[:5]:  # 5 at a time
                logger.info(f"Analyzing: {edge['source_node']} -> {edge['target_node']}")
                result = level2_deep_dive(edge, regime, driver, session_id)
                edges = process_deep_dive_result(result)
                logger.info(f"  +{edges} derivative edges, {result.get('reasoning_tokens', 0)} thinking tokens")
                time.sleep(1)  # Rate limit respect

        # Phase 2: Broad sweep on all assets
        assets = get_all_assets()
        if assets:
            print(f"Phase 2: Broad sweep on {len(assets)} assets")

            for asset in assets:
                logger.info(f"Sweeping: {asset['canonical_id']}")
                result = broad_sweep(
                    asset['canonical_id'],
                    float(asset['price']),
                    regime, driver, session_id
                )
                edges = process_broad_sweep(result)
                logger.info(f"  +{edges} edges, {result.get('reasoning_tokens', 0)} thinking tokens")
                time.sleep(1)

        # Status update
        stats = get_current_stats()
        print(f"\nCycle {cycle} complete: {stats['edges']} edges, {stats['traces']} traces, {stats['tokens']:,} tokens")

        # Sleep between cycles
        time.sleep(SLEEP_BETWEEN_BATCHES)


def main():
    """Run Night Watch."""
    try:
        night_watch()
    except KeyboardInterrupt:
        print("\nNight Watch interrupted. Final stats:")
        stats = get_current_stats()
        print(f"  Edges: {stats['edges']}")
        print(f"  Traces: {stats['traces']}")
        print(f"  Tokens: {stats['tokens']:,}")
    except Exception as e:
        logger.error(f"Night Watch error: {e}")
        raise


if __name__ == '__main__':
    main()
