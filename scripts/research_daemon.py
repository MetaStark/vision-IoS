#!/usr/bin/env python3
"""
FHQ RESEARCH DAEMON - Parallel Research Processing
===================================================
CEO Directive: DAY 1 - ACTIVATE PARALLEL RESEARCH
Authority: STIG (CTO)
Date: 2025-12-09

PHASE 4c TELEMETRY INSTRUMENTATION (2025-12-10)
- CEO Directive 2026-FHQ-PHASE-4c
- CS-003 Research Daemon wrapped with @metered_execution
- CONTROLLED INSTRUMENTATION - NO BEHAVIOR CHANGE
- Compliance: ADR-012, ADR-018, ADR-020, ADR-021, TCS-v1, DC-v1

Problem: Curiosity Trigger (idle > 300s) too strict - crypto never sleeps.
Solution: Dedicated research daemon, decoupled from price action.

Schedule: Deep Search Cycle every 15 minutes
Target: ~200 Serper credits/day (~14 credits/hour)
"""

import os
import sys
import json
import time
import uuid
import re
import logging
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

# =============================================================================
# PHASE 4c: TELEMETRY INSTRUMENTATION (CS-003 Research Daemon)
# =============================================================================
# CEO Directive 2026-FHQ-PHASE-4c requires telemetry wrapping of Research Daemon
# Following the same pattern as Phase 4a (CS-002) and Phase 4b (CS-001)
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
_telemetry_logger = logging.getLogger("research_daemon.telemetry")
try:
    from fhq_telemetry import meter_llm_call
    from fhq_telemetry.telemetry_envelope import TaskType, CognitiveModality
    TELEMETRY_ENABLED = True
except ImportError:
    # Telemetry not available - proceed without instrumentation
    pass


def _emit_research_telemetry(
    task_name: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: int,
    stream_mode: bool = True,
    error: Optional[Exception] = None,
    correlation_id: Optional[str] = None
) -> None:
    """
    Emit telemetry for a Research Daemon LLM call (PHASE 4c CS-003).

    IMPORTANT: This is a PASSIVE observer - it must never:
    - Modify the original response
    - Add retries
    - Block on failure
    - Change any behavior
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
            agent_id='RESEARCH_DAEMON',
            task_name=task_name,
            task_type=TaskType.RESEARCH,
            provider='DEEPSEEK',
            model='deepseek-reasoner',
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            stream_mode=stream_mode,
            error=error,
            correlation_id=correlation_uuid,
            cognitive_modality=CognitiveModality.SYNTHESIS
        )
        _telemetry_logger.debug(f"Telemetry emitted for {task_name}: {tokens_in}+{tokens_out} tokens")
    except Exception as e:
        # CRITICAL: Never let telemetry failure affect the main flow
        _telemetry_logger.warning(f"Telemetry emission failed (non-blocking): {e}")

# Alpaca for order management
import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import APIError

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

# Serper (Google Search)
SERPER_API_KEY = os.getenv('SERPER_API_KEY')
SERPER_API_URL = 'https://google.serper.dev/search'

# DeepSeek for synthesis
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = 'https://api.deepseek.com/v1'
DEEPSEEK_MODEL = 'deepseek-reasoner'

# Alpaca Paper
ALPACA_API = tradeapi.REST(
    key_id=os.getenv('ALPACA_API_KEY'),
    secret_key=os.getenv('ALPACA_SECRET'),
    base_url='https://paper-api.alpaca.markets',
    api_version='v2'
)

# Research config
CYCLE_INTERVAL_SECONDS = 15 * 60  # 15 minutes
SEARCHES_PER_CYCLE = 3  # ~12 searches/hour = ~200/day
CANCEL_CONFIDENCE_THRESHOLD = 0.70  # Cancel if contradiction confidence > 70%

# =============================================================================
# DATABASE
# =============================================================================

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def log_research_event(event_type: str, data: dict):
    """Log research activity to governance."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO fhq_governance.system_events
            (event_type, event_category, source_agent, event_title, event_data, event_severity)
            VALUES (%s, 'RESEARCH', 'CRIO', %s, %s, 'INFO')
        """, (event_type, event_type, json.dumps(data, default=str)))
        conn.commit()
    except Exception as e:
        print(f"  [WARN] Log error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


def store_research_trace(query: str, results: str, synthesis: str, tokens: int, session_id: str) -> str:
    """Store research trace in reward_traces."""
    conn = get_connection()
    cur = conn.cursor()
    trace_id = str(uuid.uuid4())
    try:
        cur.execute("""
            INSERT INTO fhq_optimization.reward_traces
            (trace_id, agent_id, session_id, timestamp_utc, input_query,
             reasoning_trace, reasoning_tokens, total_tokens, model_used, created_at)
            VALUES (%s, 'CRIO_RESEARCHER', %s, NOW(), %s, %s, %s, %s, 'serper+deepseek', NOW())
        """, (trace_id, session_id, query[:1000], synthesis, tokens, tokens))
        conn.commit()
        return trace_id
    except Exception as e:
        print(f"  [WARN] Trace store error: {e}")
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()


def get_serper_usage_today() -> int:
    """Get Serper credits used today."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT COUNT(*) FROM fhq_governance.system_events
            WHERE event_type = 'SERPER_SEARCH'
            AND created_at > CURRENT_DATE
        """)
        return cur.fetchone()[0]
    except:
        return 0
    finally:
        cur.close()
        conn.close()


# =============================================================================
# SERPER SEARCH
# =============================================================================

def serper_search(query: str, num_results: int = 5) -> List[Dict]:
    """Execute Google search via Serper API."""
    if not SERPER_API_KEY:
        print("  [ERROR] SERPER_API_KEY not configured")
        return []

    try:
        response = requests.post(
            SERPER_API_URL,
            headers={
                "X-API-KEY": SERPER_API_KEY,
                "Content-Type": "application/json"
            },
            json={"q": query, "num": num_results},
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            results = []

            # Organic results
            for item in data.get('organic', [])[:num_results]:
                results.append({
                    'title': item.get('title', ''),
                    'snippet': item.get('snippet', ''),
                    'link': item.get('link', ''),
                    'source': 'organic'
                })

            # News results
            for item in data.get('news', [])[:2]:
                results.append({
                    'title': item.get('title', ''),
                    'snippet': item.get('snippet', ''),
                    'link': item.get('link', ''),
                    'date': item.get('date', ''),
                    'source': 'news'
                })

            # Log usage
            log_research_event('SERPER_SEARCH', {'query': query, 'results_count': len(results)})

            return results
        else:
            print(f"  [ERROR] Serper API: {response.status_code}")
            return []

    except Exception as e:
        print(f"  [ERROR] Serper search failed: {e}")
        return []


def format_search_results(results: List[Dict]) -> str:
    """Format search results for LLM context."""
    if not results:
        return "No search results found."

    formatted = []
    for i, r in enumerate(results, 1):
        source_tag = f"[{r.get('source', 'web').upper()}]"
        date_tag = f" ({r.get('date')})" if r.get('date') else ""
        formatted.append(f"{i}. {source_tag}{date_tag} {r['title']}\n   {r['snippet']}\n   Source: {r['link']}")

    return "\n\n".join(formatted)


# =============================================================================
# DEEPSEEK SYNTHESIS
# =============================================================================

def synthesize_research(query: str, search_results: str, context: str = "") -> Dict:
    """Use DeepSeek to synthesize search results into actionable insight."""

    prompt = f"""You are CRIO, a causal reasoning engine performing RESEARCH VALIDATION.

RESEARCH QUERY: {query}

CONTEXT: {context}

GOOGLE SEARCH RESULTS:
{search_results}

TASK: Analyze these search results and provide:
1. KEY FINDINGS: What do the sources say? (bullet points)
2. SENTIMENT: Is the overall sentiment BULLISH, BEARISH, or NEUTRAL for the asset?
3. CONFIDENCE: How confident are you in this assessment? (0.0-1.0)
4. CONTRADICTION: Do these results CONTRADICT or SUPPORT our bullish thesis?
5. RECOMMENDATION: Should we HOLD the position, or CANCEL the pending order?

Respond in JSON format:
{{
    "key_findings": ["finding 1", "finding 2", ...],
    "sentiment": "BULLISH|BEARISH|NEUTRAL",
    "confidence": 0.0-1.0,
    "contradicts_thesis": true|false,
    "recommendation": "HOLD|CANCEL",
    "reasoning": "Brief explanation of your recommendation"
}}
"""

    # PHASE 4c: Capture start time for latency measurement
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
                    {"role": "system", "content": "You are CRIO, a precise financial research analyst."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1500,
                "temperature": 0.3
            },
            timeout=120
        )

        # PHASE 4c: Capture latency immediately after response
        _call_latency_ms = int(time.time() * 1000) - _call_start_ms

        if response.status_code == 200:
            data = response.json()
            content = data['choices'][0]['message']['content']
            reasoning = data['choices'][0]['message'].get('reasoning_content', '')

            usage = data.get('usage', {})
            total_tokens = usage.get('total_tokens', 0)
            prompt_tokens = usage.get('prompt_tokens', 0)
            completion_tokens = usage.get('completion_tokens', 0)

            # PHASE 4c TELEMETRY: Emit after extracting usage data
            _emit_research_telemetry(
                task_name='SYNTHESIZE_FINDINGS',
                tokens_in=prompt_tokens,
                tokens_out=completion_tokens,
                latency_ms=_call_latency_ms,
                stream_mode=True
            )

            # Parse JSON from response
            try:
                json_str = content
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    json_str = content.split("```")[1].split("```")[0]

                result = json.loads(json_str.strip())
                result['raw_reasoning'] = reasoning
                result['tokens_used'] = total_tokens
                return result
            except:
                return {
                    'key_findings': [content[:500]],
                    'sentiment': 'NEUTRAL',
                    'confidence': 0.5,
                    'contradicts_thesis': False,
                    'recommendation': 'HOLD',
                    'reasoning': 'Could not parse structured response',
                    'tokens_used': total_tokens
                }
        else:
            # PHASE 4c TELEMETRY: Emit error telemetry
            _emit_research_telemetry(
                task_name='SYNTHESIZE_FINDINGS',
                tokens_in=0,
                tokens_out=0,
                latency_ms=_call_latency_ms,
                error=Exception(f"API error {response.status_code}")
            )
            print(f"  [ERROR] DeepSeek API: {response.status_code}")
            return None

    except Exception as e:
        # PHASE 4c TELEMETRY: Emit exception telemetry
        _call_latency_ms = int(time.time() * 1000) - _call_start_ms
        _emit_research_telemetry(
            task_name='SYNTHESIZE_FINDINGS',
            tokens_in=0,
            tokens_out=0,
            latency_ms=_call_latency_ms,
            error=e
        )
        print(f"  [ERROR] DeepSeek synthesis failed: {e}")
        return None


# =============================================================================
# LAST MILE VERIFICATION
# =============================================================================

def get_pending_orders() -> List[Dict]:
    """Get pending equity orders from Alpaca."""
    try:
        orders = ALPACA_API.list_orders(status='open')
        pending = []
        for o in orders:
            # Only equity orders (crypto fills immediately)
            if o.symbol not in ['BTCUSD', 'ETHUSD', 'SOLUSD']:
                pending.append({
                    'order_id': o.id,
                    'symbol': o.symbol,
                    'side': o.side,
                    'qty': o.qty,
                    'status': o.status,
                    'submitted_at': o.submitted_at
                })
        return pending
    except Exception as e:
        print(f"  [ERROR] Get pending orders: {e}")
        return []


def cancel_order(order_id: str, reason: str) -> bool:
    """Cancel an Alpaca order."""
    try:
        ALPACA_API.cancel_order(order_id)
        log_research_event('ORDER_CANCELLED', {
            'order_id': order_id,
            'reason': reason,
            'source': 'LAST_MILE_VERIFICATION'
        })
        return True
    except Exception as e:
        print(f"  [ERROR] Cancel order failed: {e}")
        return False


def verify_pending_order(order: Dict, session_id: str) -> Dict:
    """Last Mile Verification: Research a pending order before market open."""
    symbol = order['symbol']
    side = order['side']

    print(f"\n  [VERIFY] {side.upper()} {symbol}")

    # Build search queries based on the asset
    search_queries = []

    if symbol == 'NVDA':
        search_queries = [
            f"Nvidia stock outlook December 2025 AI demand",
            f"NVDA earnings forecast Q4 2025 analyst rating"
        ]
    elif symbol == 'AAPL':
        search_queries = [
            f"Apple stock forecast December 2025 iPhone sales",
            f"AAPL analyst rating Q4 2025 services revenue"
        ]
    elif symbol == 'MSFT':
        search_queries = [
            f"Microsoft Azure AI growth 2025 outlook",
            f"MSFT stock forecast December 2025 cloud revenue"
        ]
    elif symbol == 'QQQ':
        search_queries = [
            f"Nasdaq 100 outlook December 2025 tech sector",
            f"QQQ ETF forecast 2025 Federal Reserve impact"
        ]
    elif symbol == 'SPY':
        search_queries = [
            f"S&P 500 forecast December 2025 market outlook",
            f"SPY ETF analysis 2025 economic indicators"
        ]
    else:
        search_queries = [f"{symbol} stock forecast December 2025 analyst outlook"]

    # Execute searches
    all_results = []
    for query in search_queries[:2]:  # Max 2 searches per order
        print(f"    SEARCH: {query}")
        results = serper_search(query, num_results=3)
        all_results.extend(results)
        time.sleep(0.5)  # Rate limit

    if not all_results:
        print(f"    [SKIP] No search results")
        return {'action': 'HOLD', 'reason': 'No search results'}

    # Format and synthesize
    formatted = format_search_results(all_results)
    context = f"We have a pending {side.upper()} order for {symbol}. Thesis: Bullish on liquidity-driven rally."

    print(f"    SYNTHESIZING {len(all_results)} results...")
    synthesis = synthesize_research(search_queries[0], formatted, context)

    if not synthesis:
        print(f"    [SKIP] Synthesis failed")
        return {'action': 'HOLD', 'reason': 'Synthesis failed'}

    # Store trace
    store_research_trace(
        query=f"VERIFY:{symbol}",
        results=formatted,
        synthesis=json.dumps(synthesis, default=str),
        tokens=synthesis.get('tokens_used', 0),
        session_id=session_id
    )

    # Decision logic
    action = 'HOLD'
    if synthesis.get('contradicts_thesis') and synthesis.get('confidence', 0) >= CANCEL_CONFIDENCE_THRESHOLD:
        if synthesis.get('recommendation') == 'CANCEL':
            action = 'CANCEL'

    print(f"    SENTIMENT: {synthesis.get('sentiment')}")
    print(f"    CONFIDENCE: {synthesis.get('confidence')}")
    print(f"    CONTRADICTS: {synthesis.get('contradicts_thesis')}")
    print(f"    ACTION: {action}")

    return {
        'action': action,
        'symbol': symbol,
        'sentiment': synthesis.get('sentiment'),
        'confidence': synthesis.get('confidence'),
        'contradicts': synthesis.get('contradicts_thesis'),
        'reasoning': synthesis.get('reasoning'),
        'key_findings': synthesis.get('key_findings', [])
    }


# =============================================================================
# KNOWLEDGE GAP RESEARCH
# =============================================================================

def get_knowledge_gaps() -> List[str]:
    """Find under-researched topics in our knowledge graph."""
    conn = get_connection()
    cur = conn.cursor()

    # Find nodes with few connections
    cur.execute("""
        SELECT source_node, COUNT(*) as edge_count
        FROM vision_signals.alpha_graph_edges
        WHERE is_active = true
        GROUP BY source_node
        HAVING COUNT(*) < 3
        ORDER BY RANDOM()
        LIMIT 5
    """)

    gaps = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()

    return gaps


def research_knowledge_gap(topic: str, session_id: str) -> Dict:
    """Deep research on a knowledge gap."""
    print(f"\n  [GAP RESEARCH] {topic}")

    # Build contextual search query
    query = f"{topic} market impact 2025 causal factors economic analysis"

    print(f"    SEARCH: {query}")
    results = serper_search(query, num_results=5)

    if not results:
        return {'topic': topic, 'status': 'no_results'}

    formatted = format_search_results(results)

    # Synthesize into causal edges
    prompt = f"""You are CRIO, a causal reasoning engine.

RESEARCH TOPIC: {topic}

GOOGLE SEARCH RESULTS:
{formatted}

TASK: Extract causal relationships from these search results.
Focus on: What factors CAUSE or INFLUENCE {topic}? What does {topic} AFFECT?

Respond in JSON format:
{{
    "topic_summary": "Brief summary of what you learned",
    "causal_edges": [
        {{
            "source": "FACTOR_A",
            "target": "FACTOR_B",
            "relation": "LEADS|CORRELATES|INVERSE|AMPLIFIES|INHIBITS",
            "confidence": 0.85-1.0,
            "evidence": "Quote or summary from search results"
        }}
    ]
}}
"""

    # PHASE 4c: Capture start time for latency measurement
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
                "max_tokens": 1500,
                "temperature": 0.3
            },
            timeout=120
        )

        # PHASE 4c: Capture latency immediately after response
        _call_latency_ms = int(time.time() * 1000) - _call_start_ms

        if response.status_code == 200:
            data = response.json()
            content = data['choices'][0]['message']['content']
            usage = data.get('usage', {})
            tokens = usage.get('total_tokens', 0)
            prompt_tokens = usage.get('prompt_tokens', 0)
            completion_tokens = usage.get('completion_tokens', 0)

            # PHASE 4c TELEMETRY: Emit after extracting usage data
            _emit_research_telemetry(
                task_name='EXTRACT_CAUSAL_EDGES',
                tokens_in=prompt_tokens,
                tokens_out=completion_tokens,
                latency_ms=_call_latency_ms,
                stream_mode=True
            )

            # Parse and store edges
            try:
                json_str = content
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    json_str = content.split("```")[1].split("```")[0]

                result = json.loads(json_str.strip())

                # Insert edges
                edges_added = 0
                conn = get_connection()
                cur = conn.cursor()

                for edge in result.get('causal_edges', []):
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
                            edge['source'].upper().replace(' ', '_'),
                            edge['target'].upper().replace(' ', '_'),
                            edge['relation'].upper(),
                            float(edge.get('confidence', 0.85)),
                            float(edge.get('confidence', 0.85))
                        ))
                        edges_added += 1
                    except Exception as e:
                        pass

                conn.commit()
                cur.close()
                conn.close()

                # Store trace
                store_research_trace(
                    query=f"GAP:{topic}",
                    results=formatted,
                    synthesis=content,
                    tokens=tokens,
                    session_id=session_id
                )

                print(f"    +{edges_added} edges from research")
                return {'topic': topic, 'edges_added': edges_added, 'tokens': tokens}

            except Exception as e:
                print(f"    [WARN] Parse error: {e}")
                return {'topic': topic, 'status': 'parse_error'}

        else:
            # PHASE 4c TELEMETRY: Emit error telemetry
            _emit_research_telemetry(
                task_name='EXTRACT_CAUSAL_EDGES',
                tokens_in=0,
                tokens_out=0,
                latency_ms=_call_latency_ms,
                error=Exception(f"API error {response.status_code}")
            )
            return {'topic': topic, 'status': f'api_error_{response.status_code}'}

    except Exception as e:
        # PHASE 4c TELEMETRY: Emit exception telemetry
        _call_latency_ms = int(time.time() * 1000) - _call_start_ms
        _emit_research_telemetry(
            task_name='EXTRACT_CAUSAL_EDGES',
            tokens_in=0,
            tokens_out=0,
            latency_ms=_call_latency_ms,
            error=e
        )
        print(f"    [ERROR] Research failed: {e}")
        return {'topic': topic, 'status': 'error'}


# =============================================================================
# MAIN RESEARCH CYCLE
# =============================================================================

def research_cycle(session_id: str) -> Dict:
    """Execute one research cycle."""
    cycle_start = datetime.now(timezone.utc)
    results = {
        'cycle_id': str(uuid.uuid4())[:8],
        'started_at': cycle_start.isoformat(),
        'verifications': [],
        'gap_research': [],
        'serper_credits_used': 0
    }

    print(f"\n{'='*60}")
    print(f"RESEARCH CYCLE {results['cycle_id']}")
    print(f"{'='*60}")

    # 1. LAST MILE VERIFICATION - Check pending orders
    print("\n[PHASE 1] LAST MILE VERIFICATION")
    pending_orders = get_pending_orders()

    if pending_orders:
        print(f"  Found {len(pending_orders)} pending orders")
        for order in pending_orders[:3]:  # Max 3 verifications per cycle
            verification = verify_pending_order(order, session_id)
            results['verifications'].append(verification)
            results['serper_credits_used'] += 2  # ~2 searches per verification

            # Execute cancellation if recommended
            if verification.get('action') == 'CANCEL':
                print(f"  [CANCEL] {order['symbol']} - {verification.get('reasoning')}")
                cancel_order(order['order_id'], verification.get('reasoning', 'Research contradiction'))
    else:
        print("  No pending orders to verify")

    # 2. KNOWLEDGE GAP RESEARCH - Fill gaps in our graph
    print("\n[PHASE 2] KNOWLEDGE GAP RESEARCH")
    gaps = get_knowledge_gaps()

    if gaps:
        print(f"  Found {len(gaps)} knowledge gaps")
        for topic in gaps[:2]:  # Max 2 gap researches per cycle
            gap_result = research_knowledge_gap(topic, session_id)
            results['gap_research'].append(gap_result)
            results['serper_credits_used'] += 1
    else:
        print("  No knowledge gaps identified")

    # 3. Log cycle completion
    results['completed_at'] = datetime.now(timezone.utc).isoformat()
    results['duration_seconds'] = (datetime.now(timezone.utc) - cycle_start).total_seconds()

    log_research_event('RESEARCH_CYCLE_COMPLETE', results)

    print(f"\n[CYCLE COMPLETE]")
    print(f"  Duration: {results['duration_seconds']:.1f}s")
    print(f"  Serper Credits: {results['serper_credits_used']}")
    print(f"  Verifications: {len(results['verifications'])}")
    print(f"  Gap Research: {len(results['gap_research'])}")

    return results


def daemon_loop():
    """Main daemon loop - runs every 15 minutes."""
    print("=" * 60)
    print("FHQ RESEARCH DAEMON - STARTING")
    print("=" * 60)
    print(f"Cycle Interval: {CYCLE_INTERVAL_SECONDS}s ({CYCLE_INTERVAL_SECONDS//60} minutes)")
    print(f"Searches per Cycle: ~{SEARCHES_PER_CYCLE}")
    print(f"Target Daily Credits: ~200")
    print(f"Serper API Key: {'CONFIGURED' if SERPER_API_KEY else 'MISSING'}")
    print(f"DeepSeek API Key: {'CONFIGURED' if DEEPSEEK_API_KEY else 'MISSING'}")

    if not SERPER_API_KEY or not DEEPSEEK_API_KEY:
        print("\n[FATAL] Missing API keys. Exiting.")
        return

    session_id = str(uuid.uuid4())
    cycle_count = 0

    while True:
        try:
            cycle_count += 1
            credits_today = get_serper_usage_today()

            print(f"\n--- Starting Cycle {cycle_count} ---")
            print(f"Serper Credits Today: {credits_today}/200")

            if credits_today >= 200:
                print("[PAUSE] Daily Serper limit reached. Waiting...")
                time.sleep(CYCLE_INTERVAL_SECONDS)
                continue

            # Execute research cycle
            research_cycle(session_id)

            # Wait for next cycle
            print(f"\n[SLEEP] Next cycle in {CYCLE_INTERVAL_SECONDS//60} minutes...")
            time.sleep(CYCLE_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            print("\n[SHUTDOWN] Research Daemon stopped by user")
            break
        except Exception as e:
            print(f"\n[ERROR] Cycle failed: {e}")
            time.sleep(60)  # Wait 1 minute on error


def main():
    """Entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        # Single cycle mode for testing
        session_id = str(uuid.uuid4())
        research_cycle(session_id)
    else:
        # Daemon mode
        daemon_loop()


if __name__ == '__main__':
    main()
