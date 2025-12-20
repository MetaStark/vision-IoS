#!/usr/bin/env python3
"""
FHQ ORCHESTRATOR DAEMON - THE BRAIN BRIDGE
============================================
CEO Directive: ARO-20251209/LINK_THE_BRAIN
Authority: STIG (CTO)
Date: 2025-12-09

The Missing Link: Market Events → DeepSeek Speciale → Alpha Graph

This daemon:
1. Polls for significant market events
2. Constructs context for LLM reasoning
3. Calls DeepSeek-Speciale for causal analysis
4. Parses insights into graph edges (The Harvest)

"Data flows through the system. NOW wisdom accumulates."
"""

import os
import sys
import re
import json
import time
import uuid
import hashlib
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment (override system env vars)
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

# Logging
LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'orchestrator_daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("FHQ_BRAIN")

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

# DeepSeek Speciale Configuration
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = os.getenv('FHQ_LLM_URL', 'https://api.deepseek.com/v1')
DEEPSEEK_MODEL = 'deepseek-reasoner'  # CEO MANDATE: Speciale only, no fallback

# Serper (Google Search) Configuration - CEO DIRECTIVE: ARO-20251209/CURIOSITY_V2
SERPER_API_KEY = os.getenv('SERPER_API_KEY')
SERPER_API_URL = 'https://google.serper.dev/search'

# Thresholds - CEO DIRECTIVE: ZERO THRESHOLD FOR 24H BURN-IN
SIGNIFICANCE_THRESHOLD_PCT = 0.00  # BURN-IN: Every tick is a lesson
DEBOUNCE_SECONDS = 5  # Minimal debounce during burn-in
MAX_TOKENS = 2000  # Increased for search context
TEMPERATURE = 0.3  # Low temp for factual reasoning

# Rate limits - BURN-IN MODE: Increased for batch processing
MAX_CALLS_PER_HOUR = 500  # CEO DIRECTIVE: Force-feed the brain
COST_PER_CALL_ESTIMATE = 0.02  # $0.02 per call estimate

# Curiosity Engine - CEO DIRECTIVE: ARO-20251209/CURIOSITY_V2
IDLE_THRESHOLD_SECONDS = 300  # Trigger curiosity after 5 min idle
SEARCH_PATTERN = r'SEARCH:\s*(.+?)(?:\n|$)'  # Pattern to extract search queries


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class MarketEvent:
    """A significant market event."""
    event_id: str
    asset: str
    timestamp: datetime
    price: float
    prev_price: float
    delta_pct: float
    volume: Optional[float] = None
    regime: Optional[str] = None


@dataclass
class CausalEdge:
    """A causal relationship extracted from LLM insight."""
    source_node: str
    target_node: str
    edge_type: str  # LEADS, CORRELATES, INVERSE, AMPLIFIES, INHIBITS
    confidence: float
    reasoning: str
    evidence_hash: str


# =============================================================================
# DATABASE
# =============================================================================

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def get_recent_price_changes(lookback_minutes: int = 5) -> List[MarketEvent]:
    """Get significant price changes in recent window."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        WITH recent AS (
            SELECT
                canonical_id,
                timestamp,
                close,
                LAG(close) OVER (PARTITION BY canonical_id ORDER BY timestamp) as prev_close
            FROM fhq_market.prices
            WHERE timestamp > NOW() - INTERVAL '%s minutes'
        ),
        changes AS (
            SELECT
                canonical_id,
                timestamp,
                close,
                prev_close,
                CASE WHEN prev_close > 0
                     THEN ((close - prev_close) / prev_close) * 100
                     ELSE 0
                END as delta_pct
            FROM recent
            WHERE prev_close IS NOT NULL
        )
        SELECT * FROM changes
        WHERE ABS(delta_pct) >= %s
        ORDER BY ABS(delta_pct) DESC
        LIMIT 10
    """, (lookback_minutes, SIGNIFICANCE_THRESHOLD_PCT))

    events = []
    for row in cur.fetchall():
        events.append(MarketEvent(
            event_id=str(uuid.uuid4()),
            asset=row['canonical_id'],
            timestamp=row['timestamp'],
            price=float(row['close']),
            prev_price=float(row['prev_close']),
            delta_pct=float(row['delta_pct'])
        ))

    cur.close()
    conn.close()
    return events


def get_current_regime() -> Tuple[str, float, str]:
    """Get current market regime from perception."""
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

    if row:
        return row[0], float(row[1] or 0.5), row[2] or 'NEUTRAL'
    return 'NEUTRAL', 0.5, 'NEUTRAL'


def get_api_call_count_last_hour() -> int:
    """Get number of API calls in last hour (rate limiting)."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*) FROM fhq_governance.system_events
        WHERE event_type = 'DEEPSEEK_API_CALL'
        AND created_at > NOW() - INTERVAL '1 hour'
    """)
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count


def log_api_call(prompt: str, response: str, tokens_used: int, cost: float):
    """Log API call for audit and rate limiting."""
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO fhq_governance.system_events
            (event_type, event_category, severity, event_data, created_at)
            VALUES ('DEEPSEEK_API_CALL', 'LLM', 'INFO', %s, NOW())
        """, (json.dumps({
            'prompt_preview': prompt[:200],
            'response_preview': response[:500] if response else None,
            'tokens_used': tokens_used,
            'cost_usd': cost
        }),))
        conn.commit()
    except Exception as e:
        logger.warning(f"Failed to log API call: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


def insert_edge(edge: CausalEdge) -> bool:
    """Insert a causal edge into Alpha Graph."""
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
            RETURNING edge_id
        """, (
            str(uuid.uuid4()),
            edge.source_node,
            edge.target_node,
            edge.edge_type,
            edge.confidence,
            edge.confidence  # causal_weight = confidence for now
        ))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to insert edge: {e}")
        conn.rollback()
        cur.close()
        conn.close()
        return False


# =============================================================================
# SIGNIFICANCE FILTER (Debounce)
# =============================================================================

_last_analysis = {}  # asset -> timestamp

def is_significant(event: MarketEvent) -> bool:
    """
    Check if event is significant enough to analyze.
    Implements debouncing to prevent API spam.
    """
    global _last_analysis

    # Check magnitude
    if abs(event.delta_pct) < SIGNIFICANCE_THRESHOLD_PCT:
        return False

    # Check debounce
    last = _last_analysis.get(event.asset)
    if last:
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        if elapsed < DEBOUNCE_SECONDS:
            logger.debug(f"Debounce: {event.asset} analyzed {elapsed:.0f}s ago")
            return False

    _last_analysis[event.asset] = datetime.now(timezone.utc)
    return True


# =============================================================================
# CONTEXT BUILDER
# =============================================================================

def build_context_block(event: MarketEvent) -> str:
    """
    Build rich context for LLM reasoning.
    Includes: regime, related assets, recent patterns.
    """
    regime, fragility, driver = get_current_regime()

    # Get related assets from existing graph
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT source_node, target_node, edge_type, confidence
        FROM vision_signals.alpha_graph_edges
        WHERE source_node = %s OR target_node = %s
        ORDER BY confidence DESC
        LIMIT 5
    """, (event.asset, event.asset))
    related = cur.fetchall()
    cur.close()
    conn.close()

    related_str = ""
    if related:
        related_str = "Known relationships:\n"
        for r in related:
            related_str += f"  - {r[0]} {r[2]} {r[1]} (conf: {r[3]})\n"

    context = f"""
MARKET CONTEXT (as of {event.timestamp.isoformat()}):
- Asset: {event.asset}
- Price Move: {event.delta_pct:+.2f}% (${event.prev_price:.2f} → ${event.price:.2f})
- Current Regime: {regime}
- Fragility Score: {fragility:.2f}
- Dominant Driver: {driver}

{related_str}

TASK: Identify causal relationships that could explain or be affected by this price movement.
Focus on actionable insights that can improve trading decisions.
"""
    return context


# =============================================================================
# SERPER BRIDGE (Google Search) - CEO DIRECTIVE: ARO-20251209/CURIOSITY_V2
# =============================================================================

def serper_search(query: str, num_results: int = 3) -> List[Dict]:
    """
    Call Serper API to search Google.
    CEO: "A researcher without Google is crippled."
    """
    if not SERPER_API_KEY:
        logger.warning("SERPER_API_KEY not set - search disabled")
        return []

    try:
        response = requests.post(
            SERPER_API_URL,
            headers={
                "X-API-KEY": SERPER_API_KEY,
                "Content-Type": "application/json"
            },
            json={
                "q": query,
                "num": num_results
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            results = []

            # Extract organic results
            for item in data.get('organic', [])[:num_results]:
                results.append({
                    'title': item.get('title', ''),
                    'snippet': item.get('snippet', ''),
                    'link': item.get('link', '')
                })

            logger.info(f"SERPER: Found {len(results)} results for '{query[:50]}...'")
            return results
        else:
            logger.error(f"Serper API error: {response.status_code}")
            return []

    except Exception as e:
        logger.error(f"Serper search failed: {e}")
        return []


def format_search_results(results: List[Dict]) -> str:
    """Format search results as context for Speciale."""
    if not results:
        return "No search results found."

    context = "GOOGLE SEARCH RESULTS:\n"
    for i, r in enumerate(results, 1):
        context += f"\n[{i}] {r['title']}\n"
        context += f"    {r['snippet']}\n"
        context += f"    Source: {r['link']}\n"

    return context


def extract_search_queries(text: str) -> List[str]:
    """Extract SEARCH: queries from LLM output."""
    pattern = re.compile(SEARCH_PATTERN, re.IGNORECASE)
    matches = pattern.findall(text)
    return [q.strip() for q in matches if q.strip()]


# =============================================================================
# CURIOSITY ENGINE - CEO DIRECTIVE: ARO-20251209/CURIOSITY_V2
# =============================================================================

_last_event_time = datetime.now(timezone.utc)
_curiosity_session_id = None


def reset_idle_timer():
    """Reset the idle timer when events are processed."""
    global _last_event_time
    _last_event_time = datetime.now(timezone.utc)


def check_idle_trigger() -> bool:
    """Check if system has been idle long enough to trigger curiosity."""
    elapsed = (datetime.now(timezone.utc) - _last_event_time).total_seconds()
    return elapsed >= IDLE_THRESHOLD_SECONDS


def generate_gap_analysis_request() -> Dict:
    """
    Generate a GAP_ANALYSIS_REQUEST event.
    This triggers the "Idle Mind" research mode.
    """
    return {
        'event_type': 'GAP_ANALYSIS_REQUEST',
        'timestamp': datetime.now(timezone.utc),
        'idle_seconds': (datetime.now(timezone.utc) - _last_event_time).total_seconds()
    }


def get_graph_gaps() -> List[Dict]:
    """Identify potential gaps in the Alpha Graph for research."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Find nodes with few connections (potential gaps)
    cur.execute("""
        WITH node_connections AS (
            SELECT source_node as node, COUNT(*) as out_degree
            FROM vision_signals.alpha_graph_edges
            WHERE is_active = true
            GROUP BY source_node
            UNION ALL
            SELECT target_node as node, COUNT(*) as in_degree
            FROM vision_signals.alpha_graph_edges
            WHERE is_active = true
            GROUP BY target_node
        ),
        node_summary AS (
            SELECT node, SUM(out_degree) as total_connections
            FROM node_connections
            GROUP BY node
        )
        SELECT node, total_connections
        FROM node_summary
        WHERE total_connections <= 3
        ORDER BY total_connections ASC
        LIMIT 10
    """)

    gaps = [dict(row) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return gaps


def curiosity_hunt(session_id: str = None) -> int:
    """
    THE IDLE MIND: When quiet, the brain researches.

    Pseudo-Tool Protocol:
    1. Ask Speciale to identify a causal gap
    2. If Speciale outputs SEARCH: <query>, call Serper
    3. Feed results back for synthesis
    4. Update Alpha Graph
    """
    global _curiosity_session_id

    session_id = session_id or str(uuid.uuid4())
    _curiosity_session_id = session_id

    logger.info("=" * 50)
    logger.info("CURIOSITY ENGINE ACTIVATED - Idle Mind Research")
    logger.info("=" * 50)

    # Get current graph gaps
    gaps = get_graph_gaps()
    gap_nodes = [g['node'] for g in gaps[:5]] if gaps else ['GOLD', 'OIL', 'REAL_RATES']

    # Get current regime for context
    regime, fragility, driver = get_current_regime()

    # Step A: The Query - Ask Speciale to identify gaps
    gap_prompt = f"""You are CRIO, a causal reasoning engine in RESEARCH MODE.

CURRENT STATE:
- Market Regime: {regime}
- Dominant Driver: {driver}
- Fragility: {fragility}
- Timestamp: {datetime.now(timezone.utc).isoformat()}

UNDER-CONNECTED NODES IN KNOWLEDGE GRAPH:
{', '.join(gap_nodes)}

TASK: Identify a CAUSAL GAP in our understanding. What relationship should we research?

INSTRUCTIONS:
1. Pick ONE under-connected node or identify a missing macro relationship
2. If you need current data to establish causality, output: SEARCH: <your google query>
3. Your search query should be specific and financial (e.g., "Federal Reserve balance sheet impact on gold prices 2025")

OUTPUT FORMAT:
{{
  "gap_identified": "Description of the causal gap",
  "node_to_research": "NODE_NAME",
  "hypothesis": "Your hypothesis about the causal relationship",
  "search_needed": true/false,
  "search_query": "SEARCH: <query>" or null
}}
"""

    # Call Speciale for gap identification
    result = call_deepseek_speciale(
        prompt="Identify a causal gap and request search if needed.",
        context=gap_prompt,
        session_id=session_id
    )

    if not result:
        logger.warning("Curiosity hunt: No response from Speciale")
        return 0

    content = result.get('content', '') if isinstance(result, dict) else result

    # Step B: The Hook - Check for SEARCH: requests
    search_queries = extract_search_queries(content)

    search_context = ""
    if search_queries:
        logger.info(f"CURIOSITY: Speciale requested search: {search_queries[0]}")

        # Call Serper for the first search query
        search_results = serper_search(search_queries[0], num_results=3)
        search_context = format_search_results(search_results)

        if search_results:
            # Step C: The Synthesis - Feed results back to Speciale
            synthesis_prompt = f"""You are CRIO. You requested external data and received:

{search_context}

ORIGINAL HYPOTHESIS:
{content[:500]}

TASK: Based on the search results, synthesize a causal insight.

Respond in JSON format:
{{
  "edges": [
    {{
      "source": "FACTOR_OR_ASSET",
      "target": "FACTOR_OR_ASSET",
      "relation": "LEADS|CORRELATES|INVERSE|AMPLIFIES|INHIBITS",
      "confidence": 0.85-1.0,
      "reasoning": "Explanation citing the search results (50+ words)"
    }}
  ],
  "synthesis": "What we learned from the search",
  "source_citations": ["url1", "url2"]
}}
"""

            synthesis_result = call_deepseek_speciale(
                prompt="Synthesize search results into causal edges.",
                context=synthesis_prompt,
                session_id=session_id
            )

            if synthesis_result:
                synth_content = synthesis_result.get('content', '') if isinstance(synthesis_result, dict) else synthesis_result
                edges = parse_and_store_edges(synth_content)
                logger.info(f"CURIOSITY HARVEST: {edges} edges from search synthesis")
                return edges

    # If no search needed, try to extract edges from initial response
    edges = parse_and_store_edges(content)
    logger.info(f"CURIOSITY: {edges} edges from gap analysis")
    return edges


# =============================================================================
# DEEPSEEK SPECIALE INTEGRATION
# =============================================================================

def store_reasoning_trace(
    input_query: str,
    reasoning_trace: str,
    reasoning_tokens: int,
    total_tokens: int,
    session_id: str = None
) -> Optional[str]:
    """
    Store the full reasoning trace in reward_traces.
    CEO DIRECTIVE: Save the thoughts - we will need to search them.
    """
    conn = get_connection()
    cur = conn.cursor()

    trace_id = str(uuid.uuid4())
    session_id = session_id or str(uuid.uuid4())

    try:
        cur.execute("""
            INSERT INTO fhq_optimization.reward_traces
            (trace_id, agent_id, session_id, timestamp_utc, input_query,
             reasoning_trace, reasoning_tokens, total_tokens, model_used, created_at)
            VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, %s, NOW())
            RETURNING trace_id
        """, (
            trace_id,
            'CRIO',
            session_id,
            input_query[:1000],  # Truncate query for storage
            reasoning_trace,
            reasoning_tokens,
            total_tokens,
            DEEPSEEK_MODEL
        ))
        conn.commit()
        logger.info(f"THOUGHT SAVED: trace_id={trace_id}, {reasoning_tokens} reasoning tokens")
        return trace_id
    except Exception as e:
        logger.error(f"Failed to store reasoning trace: {e}")
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()


def call_deepseek_speciale(prompt: str, context: str, session_id: str = None) -> Optional[Dict[str, Any]]:
    """
    Call DeepSeek Speciale API for causal reasoning.
    CEO DIRECTIVE: Capture and store the full thinking trace.
    Returns dict with content, reasoning_content, and token counts.
    """
    if not DEEPSEEK_API_KEY:
        logger.error("DEEPSEEK_API_KEY not set - cannot call Speciale")
        return None

    # Rate limit check
    calls_last_hour = get_api_call_count_last_hour()
    if calls_last_hour >= MAX_CALLS_PER_HOUR:
        logger.warning(f"Rate limit reached: {calls_last_hour}/{MAX_CALLS_PER_HOUR} calls/hour")
        return None

    full_prompt = f"""You are CRIO, a causal reasoning engine for financial markets.

{context}

{prompt}

Respond in JSON format with an array of causal edges:
{{
  "edges": [
    {{
      "source": "ASSET_OR_FACTOR",
      "target": "ASSET_OR_FACTOR",
      "relation": "LEADS|CORRELATES|INVERSE|AMPLIFIES|INHIBITS",
      "confidence": 0.0-1.0,
      "reasoning": "Brief explanation (50+ words)"
    }}
  ],
  "market_insight": "One sentence summary of the key insight"
}}

Only include edges with confidence > 0.85. Quality over quantity.
"""

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
                    {"role": "user", "content": full_prompt}
                ],
                "max_tokens": MAX_TOKENS,
                "temperature": TEMPERATURE
            },
            timeout=60
        )

        if response.status_code == 200:
            data = response.json()
            content = data['choices'][0]['message']['content']

            # CEO DIRECTIVE: Extract the reasoning trace (the gold)
            reasoning_content = data['choices'][0]['message'].get('reasoning_content', '')

            # Token accounting
            usage = data.get('usage', {})
            total_tokens = usage.get('total_tokens', 0)
            reasoning_tokens = usage.get('completion_tokens_details', {}).get('reasoning_tokens', 0)
            cost = total_tokens * 0.00001  # Rough estimate

            log_api_call(full_prompt[:500], content, total_tokens, cost)
            logger.info(f"DeepSeek call: {total_tokens} total, {reasoning_tokens} reasoning tokens, ${cost:.4f}")

            # CEO DIRECTIVE: SAVE THE THOUGHTS
            if reasoning_content:
                trace_id = store_reasoning_trace(
                    input_query=full_prompt,
                    reasoning_trace=reasoning_content,
                    reasoning_tokens=reasoning_tokens,
                    total_tokens=total_tokens,
                    session_id=session_id
                )
                # CEO DIRECTIVE NIGHTFIRE: Link trace to potential trades
                if trace_id:
                    set_last_trace_id(trace_id)

            return {
                'content': content,
                'reasoning_content': reasoning_content,
                'reasoning_tokens': reasoning_tokens,
                'total_tokens': total_tokens
            }
        else:
            logger.error(f"DeepSeek API error: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        logger.error(f"DeepSeek API call failed: {e}")
        return None


# =============================================================================
# CRIO EDGE PARSER
# =============================================================================

def parse_and_store_edges(insight: str) -> int:
    """
    Parse LLM insight and store edges in Alpha Graph.
    THIS IS THE HARVEST.
    """
    if not insight:
        return 0

    try:
        # Extract JSON from response (handle markdown code blocks)
        json_str = insight
        if "```json" in insight:
            json_str = insight.split("```json")[1].split("```")[0]
        elif "```" in insight:
            json_str = insight.split("```")[1].split("```")[0]

        data = json.loads(json_str.strip())
        edges = data.get('edges', [])

        stored = 0
        for e in edges:
            # Validate confidence threshold
            confidence = float(e.get('confidence', 0))
            if confidence < 0.85:
                logger.debug(f"Skipping low confidence edge: {confidence}")
                continue

            # Create edge
            edge = CausalEdge(
                source_node=e['source'].upper().replace(' ', '_'),
                target_node=e['target'].upper().replace(' ', '_'),
                edge_type=e['relation'].upper(),
                confidence=confidence,
                reasoning=e.get('reasoning', ''),
                evidence_hash=hashlib.sha256(
                    f"{e['source']}|{e['target']}|{datetime.now().isoformat()}".encode()
                ).hexdigest()[:32]
            )

            if insert_edge(edge):
                stored += 1
                logger.info(f"NEW EDGE: {edge.source_node} --{edge.edge_type}--> {edge.target_node} (conf: {edge.confidence})")

                # CEO DIRECTIVE NIGHTFIRE: Check if edge qualifies for shadow trade
                if edge.confidence >= 0.90:
                    process_edge_for_trading(edge)

        # Log market insight
        market_insight = data.get('market_insight', '')
        if market_insight:
            logger.info(f"MARKET INSIGHT: {market_insight}")

        return stored

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.debug(f"Raw response: {insight[:500]}")
        return 0
    except Exception as e:
        logger.error(f"Edge parsing failed: {e}")
        return 0


# =============================================================================
# SNIPER LOGIC - CEO DIRECTIVE: ARO-20251209/NIGHTFIRE
# =============================================================================

# Track last trace_id for trade linkage
_last_trace_id = None


def set_last_trace_id(trace_id: str):
    """Set the last trace ID for shadow trade linkage."""
    global _last_trace_id
    _last_trace_id = trace_id


def get_last_trace_id() -> Optional[str]:
    """Get the last trace ID for shadow trade linkage."""
    return _last_trace_id


def sniper_filter(edge: CausalEdge, target_asset: str = None) -> Tuple[bool, str, str]:
    """
    THE SNIPER FILTER: Evaluate if an edge should trigger a shadow trade.

    CEO Criteria:
    - confidence >= 0.90
    - impact_horizon == "IMMEDIATE" (inferred from edge_type)

    Returns: (should_trade, direction, asset_id)
    """
    # Confidence threshold
    if edge.confidence < 0.90:
        return (False, None, None)

    # Determine if impact is immediate based on edge type
    immediate_types = {'LEADS', 'AMPLIFIES', 'CORRELATES'}
    inverse_types = {'INVERSE', 'INHIBITS'}

    if edge.edge_type not in immediate_types and edge.edge_type not in inverse_types:
        return (False, None, None)

    # Determine direction and asset
    # If target is a tradeable asset, that's what we trade
    tradeable_assets = {'BTC-USD', 'ETH-USD', 'SOL-USD', 'SPY', 'QQQ', 'AAPL', 'MSFT', 'NVDA'}

    asset_id = None
    direction = None

    if edge.target_node in tradeable_assets:
        asset_id = edge.target_node
        # LEADS/AMPLIFIES/CORRELATES = bullish for target
        # INVERSE/INHIBITS = bearish for target
        if edge.edge_type in immediate_types:
            direction = 'LONG'
        else:
            direction = 'SHORT'
    elif edge.source_node in tradeable_assets:
        asset_id = edge.source_node
        # If source is tradeable, same logic applies
        if edge.edge_type in immediate_types:
            direction = 'LONG'
        else:
            direction = 'SHORT'
    else:
        # Neither node is directly tradeable
        return (False, None, None)

    logger.info(f"SNIPER: Edge qualifies - {edge.source_node}->{edge.target_node} "
                f"conf={edge.confidence}, type={edge.edge_type} => {direction} {asset_id}")

    return (True, direction, asset_id)


def create_shadow_trade(
    trigger_event_id: str,
    asset_id: str,
    direction: str,
    entry_price: float,
    confidence: float,
    hypothesis_id: str = None
) -> Optional[str]:
    """
    FIRE: Create a shadow trade via the database function.

    CEO DIRECTIVE: Every trade must link to reasoning via hypothesis_id.
    """
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT fhq_execution.create_event_shadow_trade(
                p_trigger_event_id => %s,
                p_source_agent     => 'CRIO',
                p_asset_id         => %s,
                p_direction        => %s,
                p_entry_price      => %s,
                p_entry_confidence => %s,
                p_hypothesis_id    => %s
            )
        """, (
            trigger_event_id,
            asset_id,
            direction,
            entry_price,
            confidence,
            hypothesis_id
        ))

        trade_id = cur.fetchone()[0]
        conn.commit()

        logger.info(f"SHADOW TRADE CREATED: {trade_id} | {direction} {asset_id} @ {entry_price} | conf={confidence}")
        logger.info(f"  Linked to trace: {hypothesis_id}")

        return str(trade_id)

    except Exception as e:
        logger.error(f"Failed to create shadow trade: {e}")
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()


def get_current_price(asset_id: str) -> Optional[float]:
    """Get current price for an asset from the streamer."""
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT close FROM fhq_market.prices
            WHERE canonical_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """, (asset_id,))

        row = cur.fetchone()
        return float(row[0]) if row else None

    except Exception as e:
        logger.error(f"Failed to get price for {asset_id}: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def process_edge_for_trading(edge: CausalEdge, trigger_event_id: str = None) -> bool:
    """
    Process a high-confidence edge through the Sniper filter.
    If it qualifies, create a shadow trade.
    """
    should_trade, direction, asset_id = sniper_filter(edge)

    if not should_trade:
        return False

    # Get current price
    price = get_current_price(asset_id)
    if not price:
        logger.warning(f"SNIPER: No price available for {asset_id}")
        return False

    # Generate event ID if not provided
    if not trigger_event_id:
        trigger_event_id = str(uuid.uuid4())

    # Get linked trace ID
    trace_id = get_last_trace_id()

    # FIRE!
    trade_id = create_shadow_trade(
        trigger_event_id=trigger_event_id,
        asset_id=asset_id,
        direction=direction,
        entry_price=price,
        confidence=edge.confidence,
        hypothesis_id=trace_id
    )

    return trade_id is not None


# =============================================================================
# THE BRAIN BRIDGE
# =============================================================================

def handle_market_event(event: MarketEvent, session_id: str = None) -> int:
    """
    The Missing Link.
    Takes a price update → Triggers DeepSeek Speciale → Updates Alpha Graph.
    CEO DIRECTIVE: Now saves full reasoning traces.
    """
    # 1. THRESHOLD CHECK (Debounce)
    if not is_significant(event):
        return 0

    logger.info(f"SIGNIFICANT EVENT: {event.asset} {event.delta_pct:+.2f}%")

    # 2. CONTEXT CONSTRUCTION (The "Prompt")
    context = build_context_block(event)

    # 3. CALL THE BRAIN (DeepSeek Speciale)
    # Returns dict with content + reasoning_content + tokens
    result = call_deepseek_speciale(
        prompt=f"Analyze causal impact of {event.asset} move: {event.delta_pct:+.2f}%",
        context=context,
        session_id=session_id
    )

    if not result:
        logger.warning("No insight generated - brain is silent")
        return 0

    # Extract the JSON content for edge parsing
    content = result.get('content', '') if isinstance(result, dict) else result

    # 4. STORE THE KNOWLEDGE (Graph Update)
    # THIS is the "Harvest"
    edges_stored = parse_and_store_edges(content)

    logger.info(f"HARVEST: {edges_stored} edges, {result.get('reasoning_tokens', 0)} thinking tokens")
    return edges_stored


# =============================================================================
# DAEMON MAIN LOOP
# =============================================================================

def daemon_loop(poll_interval: int = 30):
    """
    Main daemon loop - polls for events and processes them.
    CEO DIRECTIVE ARO-20251209/CURIOSITY_V2: Includes idle-triggered research.
    """
    logger.info("=" * 60)
    logger.info("FHQ ORCHESTRATOR DAEMON STARTING")
    logger.info("CEO Directive: ARO-20251209/LINK_THE_BRAIN + CURIOSITY_V2")
    logger.info(f"DeepSeek Model: {DEEPSEEK_MODEL}")
    logger.info(f"Serper Search: {'ENABLED' if SERPER_API_KEY else 'DISABLED'}")
    logger.info(f"Curiosity Trigger: {IDLE_THRESHOLD_SECONDS}s idle")
    logger.info(f"Significance Threshold: {SIGNIFICANCE_THRESHOLD_PCT}%")
    logger.info(f"Rate Limit: {MAX_CALLS_PER_HOUR} calls/hour")
    logger.info("=" * 60)

    # Validate config
    if not DEEPSEEK_API_KEY:
        logger.error("CRITICAL: DEEPSEEK_API_KEY not set!")
        logger.error("The brain cannot think without API access.")
        return

    total_edges = 0
    curiosity_edges = 0
    cycles = 0
    session_id = str(uuid.uuid4())

    while True:
        try:
            cycles += 1

            # Get significant events
            events = get_recent_price_changes(lookback_minutes=5)

            if events:
                logger.info(f"Cycle {cycles}: Found {len(events)} significant events")
                reset_idle_timer()  # Reset idle timer when events found

                for event in events:
                    edges = handle_market_event(event, session_id=session_id)
                    total_edges += edges
            else:
                logger.debug(f"Cycle {cycles}: No significant events")

                # CEO DIRECTIVE: CURIOSITY_V2 - Idle Mind Research
                if check_idle_trigger():
                    logger.info(f"CURIOSITY TRIGGER: Idle for {IDLE_THRESHOLD_SECONDS}+ seconds")
                    edges = curiosity_hunt(session_id=session_id)
                    curiosity_edges += edges
                    total_edges += edges
                    reset_idle_timer()  # Reset after curiosity hunt

            # Status heartbeat every 10 cycles
            if cycles % 10 == 0:
                logger.info(f"BRAIN HEARTBEAT: {cycles} cycles, {total_edges} edges (curiosity: {curiosity_edges})")

            time.sleep(poll_interval)

        except KeyboardInterrupt:
            logger.info("Daemon stopping...")
            break
        except Exception as e:
            logger.error(f"Daemon error: {e}")
            time.sleep(poll_interval)


def run_once():
    """Run a single analysis cycle (for testing)."""
    logger.info("Running single analysis cycle...")

    events = get_recent_price_changes(lookback_minutes=60)  # Wider window for testing

    if not events:
        logger.info("No significant events found in last hour")
        # Force an event for testing
        regime, fragility, driver = get_current_regime()
        test_event = MarketEvent(
            event_id=str(uuid.uuid4()),
            asset='BTC-USD',
            timestamp=datetime.now(timezone.utc),
            price=100000,
            prev_price=99000,
            delta_pct=1.01,
            regime=regime
        )
        logger.info(f"Using test event: {test_event.asset} {test_event.delta_pct:+.2f}%")
        edges = handle_market_event(test_event)
        return edges

    total = 0
    for event in events[:3]:  # Process top 3
        edges = handle_market_event(event)
        total += edges

    return total


# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description='FHQ Orchestrator Daemon')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--interval', type=int, default=30, help='Poll interval in seconds')
    args = parser.parse_args()

    if args.once:
        edges = run_once()
        print(f"Single cycle complete: {edges} edges harvested")
    else:
        daemon_loop(poll_interval=args.interval)


if __name__ == '__main__':
    main()
