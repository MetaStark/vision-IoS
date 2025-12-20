#!/usr/bin/env python3
"""
FORCE BATCH REASONING - CEO DIRECTIVE
======================================
CEO Order: Force-feed the brain with 100 parallel requests.
Target: Edge Count > 100

This script:
1. Gets ALL assets from fhq_market.prices
2. Creates synthetic price events for each
3. Sends parallel requests to DeepSeek-Reasoner
4. Harvests edges into Alpha Graph
"""

import os
import sys
import json
import uuid
import hashlib
import logging
import requests
import concurrent.futures
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment with override
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("FORCE_BATCH")

# Config
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = 'https://api.deepseek.com/v1'
DEEPSEEK_MODEL = 'deepseek-reasoner'  # CEO MANDATE: Speciale only

# Parallel config
MAX_WORKERS = 10  # Parallel threads
MAX_REQUESTS = 100  # Target requests


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def get_all_assets() -> List[Dict]:
    """Get all unique assets with recent price data."""
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
        ORDER BY canonical_id
    """)

    assets = [dict(row) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return assets


def get_current_regime() -> tuple:
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


def call_deepseek_reasoner(asset: str, price: float, regime: str, driver: str) -> Optional[Dict]:
    """Call DeepSeek Reasoner for causal analysis."""

    prompt = f"""You are CRIO, a causal reasoning engine for financial markets.

MARKET CONTEXT:
- Asset: {asset}
- Current Price: ${price:,.2f}
- Market Regime: {regime}
- Dominant Driver: {driver}
- Timestamp: {datetime.now(timezone.utc).isoformat()}

TASK: Identify ALL causal relationships involving {asset}.
Think about:
1. What macro factors LEAD or AMPLIFY this asset?
2. What other assets CORRELATE with this one?
3. What factors could INHIBIT or create INVERSE pressure?

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
  "insight": "Key market insight for {asset}"
}}

Generate 3-5 high-confidence edges. Quality over quantity.
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
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1500,
                "temperature": 0.3
            },
            timeout=60
        )

        if response.status_code == 200:
            data = response.json()
            content = data['choices'][0]['message']['content']
            tokens = data.get('usage', {}).get('total_tokens', 0)

            # Extract reasoning_content if present (R1 model)
            reasoning = data['choices'][0]['message'].get('reasoning_content', '')
            if reasoning:
                logger.debug(f"Reasoning: {reasoning[:200]}...")

            return {
                'content': content,
                'tokens': tokens,
                'asset': asset
            }
        else:
            logger.error(f"API error for {asset}: {response.status_code}")
            return None

    except Exception as e:
        logger.error(f"Request failed for {asset}: {e}")
        return None


def parse_edges(response: Dict) -> List[Dict]:
    """Parse edges from LLM response."""
    if not response or not response.get('content'):
        return []

    content = response['content']

    try:
        # Extract JSON
        json_str = content
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0]

        data = json.loads(json_str.strip())
        edges = data.get('edges', [])

        valid_edges = []
        for e in edges:
            conf = float(e.get('confidence', 0))
            if conf >= 0.85:
                valid_edges.append({
                    'source': e['source'].upper().replace(' ', '_'),
                    'target': e['target'].upper().replace(' ', '_'),
                    'edge_type': e['relation'].upper(),
                    'confidence': conf,
                    'reasoning': e.get('reasoning', '')
                })

        return valid_edges

    except Exception as e:
        logger.debug(f"Parse error: {e}")
        return []


def insert_edges(edges: List[Dict]) -> int:
    """Batch insert edges into Alpha Graph."""
    if not edges:
        return 0

    conn = get_connection()
    cur = conn.cursor()

    inserted = 0
    for edge in edges:
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
                edge['source'],
                edge['target'],
                edge['edge_type'],
                edge['confidence'],
                edge['confidence']
            ))
            inserted += 1
        except Exception as e:
            logger.debug(f"Insert error: {e}")
            conn.rollback()
            continue

    conn.commit()
    cur.close()
    conn.close()
    return inserted


def process_asset(asset_data: Dict, regime: str, driver: str) -> int:
    """Process a single asset - called in parallel."""
    asset = asset_data['canonical_id']
    price = float(asset_data['price'])

    logger.info(f"Processing: {asset} @ ${price:,.2f}")

    response = call_deepseek_reasoner(asset, price, regime, driver)
    if not response:
        return 0

    edges = parse_edges(response)
    if edges:
        inserted = insert_edges(edges)
        logger.info(f"  {asset}: {inserted} edges harvested")
        return inserted

    return 0


def main():
    """Execute batch reasoning."""
    print("=" * 70)
    print("FORCE BATCH REASONING - CEO DIRECTIVE")
    print("Model: deepseek-reasoner (SPECIALE)")
    print(f"Target: {MAX_REQUESTS} requests, 100+ edges")
    print("=" * 70)

    if not DEEPSEEK_API_KEY:
        print("ERROR: DEEPSEEK_API_KEY not set!")
        return

    # Get current regime
    regime, fragility, driver = get_current_regime()
    print(f"Regime: {regime}, Fragility: {fragility}, Driver: {driver}")

    # Get all assets
    assets = get_all_assets()
    print(f"Assets found: {len(assets)}")

    # Expand to reach target requests
    requests_list = []
    while len(requests_list) < MAX_REQUESTS:
        for asset in assets:
            requests_list.append(asset)
            if len(requests_list) >= MAX_REQUESTS:
                break

    print(f"Requests to execute: {len(requests_list)}")
    print("-" * 70)

    # Execute in parallel
    total_edges = 0
    completed = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_asset, asset, regime, driver): asset
            for asset in requests_list
        }

        for future in concurrent.futures.as_completed(futures):
            try:
                edges = future.result()
                total_edges += edges
                completed += 1

                if completed % 10 == 0:
                    print(f"Progress: {completed}/{len(requests_list)} requests, {total_edges} edges")

            except Exception as e:
                logger.error(f"Future error: {e}")

    print("=" * 70)
    print(f"BATCH COMPLETE")
    print(f"  Requests: {completed}")
    print(f"  Edges Harvested: {total_edges}")
    print("=" * 70)

    # Final count
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM vision_signals.alpha_graph_edges")
    final_count = cur.fetchone()[0]
    cur.close()
    conn.close()

    print(f"  Total Edges in Graph: {final_count}")

    return total_edges


if __name__ == '__main__':
    main()
