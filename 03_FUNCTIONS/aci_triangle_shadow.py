#!/usr/bin/env python3
"""
ACI CONSTRAINT TRIANGLE - SHADOW EVALUATOR
===========================================
CEO Directive: CEO-ACI-TRIANGLE-2025-12-21
Mode: SHADOW / AUDIT-ONLY (Non-Blocking)
Scope: CRYPTO ASSETS ONLY

This module implements shadow evaluation for:
- EC-020 SitC: Reasoning chain integrity
- EC-021 InForage: API budget discipline / marginal ROI
- EC-022 IKEA: Hallucination & stale-data firewall

EXPLICIT RULE: Evaluate, log, score, report - DO NOT reject, throttle, or block.

Author: STIG (CTO)
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [ACI] %(levelname)s: %(message)s'
)
logger = logging.getLogger('ACI_TRIANGLE')

# Database config
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Crypto asset identifiers
CRYPTO_ASSETS = {
    'BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'ADA', 'AVAX', 'DOT', 'MATIC', 'LINK',
    'BTC-USD', 'ETH-USD', 'SOL-USD', 'BTCUSDT', 'ETHUSDT', 'SOLUSDT',
    'BTC/USD', 'ETH/USD', 'SOL/USD'
}

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SitCEvaluation:
    """EC-020 SitC reasoning chain evaluation."""
    needle_id: str
    has_broken_chain: bool
    failure_type: Optional[str]  # MISSING_PREMISE, CIRCULAR_LOGIC, NON_DETERMINISTIC
    sitc_score: float  # 0.0 - 1.0
    chain_depth: int
    verified_nodes: int
    total_nodes: int
    details: Dict


@dataclass
class IKEAEvaluation:
    """EC-022 IKEA hallucination/stale data evaluation."""
    needle_id: str
    has_fabrication_flag: bool
    has_stale_data_flag: bool
    has_unverifiable_claim: bool
    ikea_score: float  # 0.0 - 1.0
    flagged_elements: List[str]
    data_freshness_hours: Optional[float]
    details: Dict


@dataclass
class InForageEvaluation:
    """EC-021 InForage API cost/ROI evaluation."""
    needle_id: str
    api_cost_usd: float
    marginal_cost_vs_eqs: float  # cost / eqs_score
    production_velocity: float  # needles per hour
    budget_pressure: float  # 0.0 - 1.0 (1.0 = max pressure)
    api_calls_count: int
    details: Dict


# =============================================================================
# EC-020 SitC SHADOW EVALUATOR
# =============================================================================

class SitCShadowEvaluator:
    """
    EC-020 SitC - Reasoning Chain Integrity Evaluator

    Evaluates:
    - % needles with broken reasoning chains
    - Failure taxonomy (missing premise, circular logic, non-deterministic)
    - SitC score distribution

    Does NOT block or reject.
    """

    def __init__(self, conn):
        self.conn = conn

    def evaluate_needle(self, needle: Dict) -> SitCEvaluation:
        """Evaluate a single needle for reasoning chain integrity."""
        needle_id = str(needle.get('needle_id', ''))

        # Extract reasoning chain indicators
        sitc_confidence = needle.get('sitc_confidence_level', 'UNKNOWN')
        sitc_nodes_completed = needle.get('sitc_nodes_completed', 0) or 0
        sitc_nodes_total = needle.get('sitc_nodes_total', 0) or 0
        chain_hash = needle.get('chain_of_query_hash')
        hypothesis = needle.get('hypothesis_statement', '') or ''

        # Evaluate chain integrity
        failure_type = None
        has_broken_chain = False

        # Check 1: Missing premise (no chain hash or incomplete nodes)
        if not chain_hash or sitc_nodes_completed == 0:
            failure_type = 'MISSING_PREMISE'
            has_broken_chain = True

        # Check 2: Incomplete chain (nodes below 80% threshold)
        # Allow 6/7 as valid since not all hypotheses have all 7 confluence factors
        elif sitc_nodes_total > 0 and (sitc_nodes_completed / sitc_nodes_total) < 0.80:
            failure_type = 'INCOMPLETE_CHAIN'
            has_broken_chain = True

        # Check 3: Circular logic detection (simple heuristic)
        elif self._detect_circular_logic(hypothesis):
            failure_type = 'CIRCULAR_LOGIC'
            has_broken_chain = True

        # Check 4: Non-deterministic inference (confidence too low)
        elif sitc_confidence not in ('HIGH', 'ACCEPT'):
            failure_type = 'NON_DETERMINISTIC'
            has_broken_chain = True

        # Calculate SitC score
        if sitc_nodes_total > 0:
            chain_completion = sitc_nodes_completed / sitc_nodes_total
        else:
            chain_completion = 0.0

        confidence_score = 1.0 if sitc_confidence == 'HIGH' else 0.7 if sitc_confidence == 'MEDIUM' else 0.3
        sitc_score = (chain_completion * 0.6 + confidence_score * 0.4)

        return SitCEvaluation(
            needle_id=needle_id,
            has_broken_chain=has_broken_chain,
            failure_type=failure_type,
            sitc_score=round(sitc_score, 4),
            chain_depth=sitc_nodes_total,
            verified_nodes=sitc_nodes_completed,
            total_nodes=sitc_nodes_total,
            details={
                'sitc_confidence': sitc_confidence,
                'chain_hash_present': chain_hash is not None,
                'hypothesis_length': len(hypothesis)
            }
        )

    def _detect_circular_logic(self, hypothesis: str) -> bool:
        """Simple heuristic for circular logic detection."""
        if not hypothesis:
            return False

        # Check for self-referential patterns
        circular_patterns = [
            'because it will',
            'therefore it is because',
            'which causes itself',
            'self-fulfilling'
        ]

        hypothesis_lower = hypothesis.lower()
        return any(pattern in hypothesis_lower for pattern in circular_patterns)


# =============================================================================
# EC-022 IKEA SHADOW EVALUATOR
# =============================================================================

class IKEAShadowEvaluator:
    """
    EC-022 IKEA - Hallucination & Stale Data Firewall

    Evaluates:
    - % needles flagged for fabricated references
    - % needles flagged for stale data
    - % needles with unverifiable claims

    Does NOT block or reject.
    """

    def __init__(self, conn):
        self.conn = conn
        self.knowledge_cutoff = datetime(2025, 1, 1, tzinfo=timezone.utc)

    def evaluate_needle(self, needle: Dict) -> IKEAEvaluation:
        """Evaluate a single needle for hallucination/stale data."""
        needle_id = str(needle.get('needle_id', ''))

        # Extract data freshness indicators
        price_witness_timestamp = needle.get('price_witness_timestamp')
        regime_snapshot_timestamp = needle.get('regime_snapshot_timestamp')
        asrp_timestamp = needle.get('asrp_timestamp')
        created_at = needle.get('created_at')

        # Extract verification indicators
        canonical_hash = needle.get('canonical_hash')
        evidence_pack_path = needle.get('evidence_pack_path')
        vega_attestation_id = needle.get('vega_attestation_id')

        flagged_elements = []

        # Check 1: Fabricated references (no evidence backing)
        has_fabrication_flag = False
        if not canonical_hash:
            has_fabrication_flag = True
            flagged_elements.append('MISSING_CANONICAL_HASH')
        if not evidence_pack_path:
            has_fabrication_flag = True
            flagged_elements.append('MISSING_EVIDENCE_PACK')

        # Check 2: Stale data (price witness older than 24h AT TIME OF CREATION)
        # For historical needles, compare against created_at, not NOW()
        has_stale_data_flag = False
        data_freshness_hours = None

        # Parse created_at for comparison
        needle_created_at = None
        if created_at:
            if isinstance(created_at, str):
                try:
                    needle_created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                except:
                    needle_created_at = None
            else:
                needle_created_at = created_at
            if needle_created_at and needle_created_at.tzinfo is None:
                needle_created_at = needle_created_at.replace(tzinfo=timezone.utc)

        if price_witness_timestamp:
            if isinstance(price_witness_timestamp, str):
                try:
                    pw_ts = datetime.fromisoformat(price_witness_timestamp.replace('Z', '+00:00'))
                except:
                    pw_ts = None
            else:
                pw_ts = price_witness_timestamp
            if pw_ts and pw_ts.tzinfo is None:
                pw_ts = pw_ts.replace(tzinfo=timezone.utc)

            if pw_ts and needle_created_at:
                # Compare age AT TIME OF CREATION
                age = needle_created_at - pw_ts
                data_freshness_hours = age.total_seconds() / 3600
                # Stale = price data was >24h old when needle was created
                if data_freshness_hours > 24:
                    has_stale_data_flag = True
                    flagged_elements.append(f'STALE_PRICE_WITNESS_{data_freshness_hours:.1f}h')
            elif pw_ts:
                # Fallback to NOW() if no created_at
                now = datetime.now(timezone.utc)
                age = now - pw_ts
                data_freshness_hours = age.total_seconds() / 3600
                if data_freshness_hours > 24:
                    has_stale_data_flag = True
                    flagged_elements.append(f'STALE_PRICE_WITNESS_{data_freshness_hours:.1f}h')
        else:
            has_stale_data_flag = True
            flagged_elements.append('MISSING_PRICE_WITNESS')

        # Check 3: Unverifiable claims (no VEGA attestation)
        has_unverifiable_claim = False
        if not vega_attestation_id:
            has_unverifiable_claim = True
            flagged_elements.append('NO_VEGA_ATTESTATION')

        # Calculate IKEA score (higher = better, fewer issues)
        deductions = 0
        if has_fabrication_flag:
            deductions += 0.4
        if has_stale_data_flag:
            deductions += 0.3
        if has_unverifiable_claim:
            deductions += 0.3

        ikea_score = max(0.0, 1.0 - deductions)

        return IKEAEvaluation(
            needle_id=needle_id,
            has_fabrication_flag=has_fabrication_flag,
            has_stale_data_flag=has_stale_data_flag,
            has_unverifiable_claim=has_unverifiable_claim,
            ikea_score=round(ikea_score, 4),
            flagged_elements=flagged_elements,
            data_freshness_hours=round(data_freshness_hours, 2) if data_freshness_hours else None,
            details={
                'has_canonical_hash': canonical_hash is not None,
                'has_evidence_pack': evidence_pack_path is not None,
                'has_vega_attestation': vega_attestation_id is not None
            }
        )


# =============================================================================
# EC-021 InForage SHADOW EVALUATOR
# =============================================================================

class InForageShadowEvaluator:
    """
    EC-021 InForage - API Budget Discipline / Marginal ROI

    Evaluates:
    - API cost per needle
    - Marginal cost vs EQS
    - Production velocity vs budget pressure

    Does NOT throttle or block.
    """

    def __init__(self, conn):
        self.conn = conn
        self.daily_budget = 50.0  # $50/day budget
        # Fetch real balance from DeepSeek API tracker
        self._real_balance = self._fetch_real_balance()
        self._daily_consumption = self._fetch_daily_consumption()

    def _fetch_real_balance(self) -> dict:
        """Fetch latest real balance from llm_provider_balance table."""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT total_balance, topped_up_balance, fetched_at
                    FROM fhq_governance.llm_provider_balance
                    WHERE provider = 'deepseek'
                    ORDER BY fetched_at DESC
                    LIMIT 1
                """)
                result = cur.fetchone()
                if result:
                    return {
                        'balance': float(result['total_balance']),
                        'topped_up': float(result['topped_up_balance']),
                        'fetched_at': result['fetched_at']
                    }
        except Exception:
            pass
        return {'balance': 0, 'topped_up': 0, 'fetched_at': None}

    def _fetch_daily_consumption(self) -> float:
        """Calculate daily consumption from balance history."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    WITH bounds AS (
                        SELECT 
                            MAX(total_balance) FILTER (WHERE fetched_at >= NOW() - INTERVAL '24 hours') as day_start,
                            MIN(total_balance) FILTER (WHERE fetched_at >= NOW() - INTERVAL '24 hours') as day_end
                        FROM fhq_governance.llm_provider_balance
                        WHERE provider = 'deepseek'
                    )
                    SELECT COALESCE(day_start - day_end, 0) as consumed
                    FROM bounds
                """)
                result = cur.fetchone()
                return float(result[0]) if result and result[0] else 0.0
        except Exception:
            return 0.0

    def evaluate_needle(self, needle: Dict) -> InForageEvaluation:
        """Evaluate a single needle for API cost/ROI using REAL DeepSeek balance."""
        needle_id = str(needle.get('needle_id', ''))

        # Extract EQS and metadata
        eqs_score = float(needle.get('eqs_score', 0) or 0)
        
        # Use real daily consumption divided by needle count for cost per needle
        total_needles = self._get_total_needles_today()
        if total_needles > 0 and self._daily_consumption > 0:
            api_cost_usd = self._daily_consumption / total_needles
        else:
            api_cost_usd = 0.0  # No consumption data yet

        # Marginal cost vs EQS (cost efficiency)
        if eqs_score > 0 and api_cost_usd > 0:
            marginal_cost_vs_eqs = api_cost_usd / eqs_score
        else:
            marginal_cost_vs_eqs = 0.0

        # Calculate budget pressure from real balance
        current_balance = self._real_balance.get('balance', 0)
        budget_pressure = max(0, min(1.0, 1.0 - (current_balance / self.daily_budget)))

        return InForageEvaluation(
            needle_id=needle_id,
            api_cost_usd=round(api_cost_usd, 6),
            marginal_cost_vs_eqs=round(marginal_cost_vs_eqs, 6),
            production_velocity=0,  # Not used with real data
            budget_pressure=round(budget_pressure, 4),
            api_calls_count=0,  # We track cost, not calls
            details={
                'real_balance': current_balance,
                'daily_consumption': self._daily_consumption,
                'eqs_score': eqs_score,
                'source': 'DEEPSEEK_API_BALANCE'
            }
        )

    def _get_total_needles_today(self) -> int:
        """Get count of needles created today."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FROM fhq_canonical.golden_needles
                    WHERE created_at >= CURRENT_DATE AND is_current = TRUE
                """)
                return cur.fetchone()[0] or 0
        except Exception:
            return 0

    def _get_production_velocity(self) -> float:
        """Get current needle production velocity (needles/hour)."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) as count
                FROM fhq_canonical.golden_needles
                WHERE created_at > NOW() - INTERVAL '1 hour'
                AND is_current = TRUE
            """)
            result = cur.fetchone()
            return float(result[0]) if result else 0.0


# =============================================================================
# ACI TRIANGLE COORDINATOR
# =============================================================================

class ACITriangleShadow:
    """
    Coordinates all three EC shadow evaluators.
    Crypto assets only per CEO directive.
    """

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.sitc = SitCShadowEvaluator(self.conn)
        self.ikea = IKEAShadowEvaluator(self.conn)
        self.inforage = InForageShadowEvaluator(self.conn)

        # Ensure shadow tables exist
        self._ensure_tables()

    def _ensure_tables(self):
        """Create shadow evaluation tables if they don't exist."""
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS fhq_canonical.aci_shadow_evaluations (
                    eval_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    needle_id UUID NOT NULL,
                    asset_class TEXT,

                    -- EC-020 SitC
                    sitc_score NUMERIC(5,4),
                    sitc_has_broken_chain BOOLEAN,
                    sitc_failure_type TEXT,
                    sitc_verified_nodes INTEGER,
                    sitc_total_nodes INTEGER,

                    -- EC-022 IKEA
                    ikea_score NUMERIC(5,4),
                    ikea_has_fabrication BOOLEAN,
                    ikea_has_stale_data BOOLEAN,
                    ikea_has_unverifiable BOOLEAN,
                    ikea_flagged_elements JSONB,
                    ikea_data_freshness_hours NUMERIC,

                    -- EC-021 InForage
                    inforage_api_cost_usd NUMERIC(10,6),
                    inforage_marginal_cost NUMERIC(10,6),
                    inforage_budget_pressure NUMERIC(5,4),
                    inforage_api_calls INTEGER,

                    -- Metadata
                    evaluated_at TIMESTAMPTZ DEFAULT NOW(),
                    shadow_mode BOOLEAN DEFAULT TRUE
                );

                CREATE INDEX IF NOT EXISTS idx_aci_shadow_needle
                ON fhq_canonical.aci_shadow_evaluations(needle_id);

                CREATE INDEX IF NOT EXISTS idx_aci_shadow_time
                ON fhq_canonical.aci_shadow_evaluations(evaluated_at);
            """)
        self.conn.commit()
        logger.info("ACI shadow tables ensured")

    def is_crypto_asset(self, needle: Dict) -> bool:
        """Check if needle is for a crypto asset."""
        price_witness = needle.get('price_witness_symbol', '') or ''
        target_asset = needle.get('target_asset', '') or ''
        hypothesis_category = needle.get('hypothesis_category', '') or ''

        # Check various fields for crypto indicators
        check_fields = [price_witness.upper(), target_asset.upper(), hypothesis_category.upper()]

        for field in check_fields:
            if any(crypto in field for crypto in CRYPTO_ASSETS):
                return True
            if 'CRYPTO' in field or 'BITCOIN' in field or 'ETHEREUM' in field:
                return True

        return False

    def evaluate_needle(self, needle: Dict) -> Optional[Dict]:
        """
        Evaluate a single needle through all three ECs.
        Returns None if not a crypto asset.
        Does NOT block - shadow mode only.
        """
        # Scope check: Crypto only
        if not self.is_crypto_asset(needle):
            return None

        needle_id = str(needle.get('needle_id', ''))

        # Run all three evaluators
        sitc_eval = self.sitc.evaluate_needle(needle)
        ikea_eval = self.ikea.evaluate_needle(needle)
        inforage_eval = self.inforage.evaluate_needle(needle)

        # Store shadow evaluation
        self._store_evaluation(needle_id, 'CRYPTO', sitc_eval, ikea_eval, inforage_eval)

        return {
            'needle_id': needle_id,
            'asset_class': 'CRYPTO',
            'sitc': asdict(sitc_eval),
            'ikea': asdict(ikea_eval),
            'inforage': asdict(inforage_eval),
            'shadow_mode': True,
            'blocking': False
        }

    def _store_evaluation(self, needle_id: str, asset_class: str,
                          sitc: SitCEvaluation, ikea: IKEAEvaluation,
                          inforage: InForageEvaluation):
        """Store shadow evaluation in database."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_canonical.aci_shadow_evaluations (
                    needle_id, asset_class,
                    sitc_score, sitc_has_broken_chain, sitc_failure_type,
                    sitc_verified_nodes, sitc_total_nodes,
                    ikea_score, ikea_has_fabrication, ikea_has_stale_data,
                    ikea_has_unverifiable, ikea_flagged_elements, ikea_data_freshness_hours,
                    inforage_api_cost_usd, inforage_marginal_cost,
                    inforage_budget_pressure, inforage_api_calls,
                    shadow_mode
                ) VALUES (
                    %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    TRUE
                )
                ON CONFLICT DO NOTHING
            """, (
                needle_id, asset_class,
                sitc.sitc_score, sitc.has_broken_chain, sitc.failure_type,
                sitc.verified_nodes, sitc.total_nodes,
                ikea.ikea_score, ikea.has_fabrication_flag, ikea.has_stale_data_flag,
                ikea.has_unverifiable_claim, Json(ikea.flagged_elements), ikea.data_freshness_hours,
                inforage.api_cost_usd, inforage.marginal_cost_vs_eqs,
                inforage.budget_pressure, inforage.api_calls_count
            ))
        self.conn.commit()

    def evaluate_recent_needles(self, hours: int = 24, limit: int = 1000) -> Dict:
        """Evaluate recent crypto needles and return summary."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT *
                FROM fhq_canonical.golden_needles
                WHERE is_current = TRUE
                AND created_at > NOW() - INTERVAL '%s hours'
                ORDER BY created_at DESC
                LIMIT %s
            """, (hours, limit))
            needles = cur.fetchall()

        results = {
            'evaluated': 0,
            'crypto_only': 0,
            'skipped_non_crypto': 0,
            'sitc_broken_chains': 0,
            'ikea_flagged': 0,
            'avg_sitc_score': 0,
            'avg_ikea_score': 0,
            'total_api_cost': 0,
            'avg_budget_pressure': 0,
            'failure_taxonomy': {
                'MISSING_PREMISE': 0,
                'INCOMPLETE_CHAIN': 0,
                'CIRCULAR_LOGIC': 0,
                'NON_DETERMINISTIC': 0
            },
            'evaluations': []
        }

        sitc_scores = []
        ikea_scores = []
        budget_pressures = []

        for needle in needles:
            evaluation = self.evaluate_needle(needle)

            if evaluation is None:
                results['skipped_non_crypto'] += 1
                continue

            results['evaluated'] += 1
            results['crypto_only'] += 1
            results['evaluations'].append(evaluation)

            # Aggregate SitC
            sitc = evaluation['sitc']
            sitc_scores.append(sitc['sitc_score'])
            if sitc['has_broken_chain']:
                results['sitc_broken_chains'] += 1
                if sitc['failure_type']:
                    results['failure_taxonomy'][sitc['failure_type']] = \
                        results['failure_taxonomy'].get(sitc['failure_type'], 0) + 1

            # Aggregate IKEA
            ikea = evaluation['ikea']
            ikea_scores.append(ikea['ikea_score'])
            if ikea['has_fabrication_flag'] or ikea['has_stale_data_flag'] or ikea['has_unverifiable_claim']:
                results['ikea_flagged'] += 1

            # Aggregate InForage
            inforage = evaluation['inforage']
            results['total_api_cost'] += inforage['api_cost_usd']
            budget_pressures.append(inforage['budget_pressure'])

        # Calculate averages
        if sitc_scores:
            results['avg_sitc_score'] = round(sum(sitc_scores) / len(sitc_scores), 4)
        if ikea_scores:
            results['avg_ikea_score'] = round(sum(ikea_scores) / len(ikea_scores), 4)
        if budget_pressures:
            results['avg_budget_pressure'] = round(sum(budget_pressures) / len(budget_pressures), 4)

        results['total_api_cost'] = round(results['total_api_cost'], 4)

        return results

    def get_telemetry(self) -> Dict:
        """Get current telemetry for dashboard."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # EC-020 SitC metrics
            cur.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE sitc_has_broken_chain = TRUE) as broken_chains,
                    AVG(sitc_score) as avg_score,
                    sitc_failure_type,
                    COUNT(*) FILTER (WHERE sitc_failure_type IS NOT NULL) as failure_count
                FROM fhq_canonical.aci_shadow_evaluations
                WHERE evaluated_at > NOW() - INTERVAL '24 hours'
                AND asset_class = 'CRYPTO'
                GROUP BY sitc_failure_type
            """)
            sitc_rows = cur.fetchall()

            # EC-022 IKEA metrics
            cur.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE ikea_has_fabrication = TRUE) as fabrication_flags,
                    COUNT(*) FILTER (WHERE ikea_has_stale_data = TRUE) as stale_data_flags,
                    COUNT(*) FILTER (WHERE ikea_has_unverifiable = TRUE) as unverifiable_flags,
                    AVG(ikea_score) as avg_score,
                    AVG(ikea_data_freshness_hours) as avg_freshness
                FROM fhq_canonical.aci_shadow_evaluations
                WHERE evaluated_at > NOW() - INTERVAL '24 hours'
                AND asset_class = 'CRYPTO'
            """)
            ikea_row = cur.fetchone()

            # EC-021 InForage metrics
            cur.execute("""
                SELECT
                    SUM(inforage_api_cost_usd) as total_cost,
                    AVG(inforage_marginal_cost) as avg_marginal_cost,
                    AVG(inforage_budget_pressure) as avg_budget_pressure,
                    SUM(inforage_api_calls) as total_api_calls
                FROM fhq_canonical.aci_shadow_evaluations
                WHERE evaluated_at > NOW() - INTERVAL '24 hours'
                AND asset_class = 'CRYPTO'
            """)
            inforage_row = cur.fetchone()

        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'mode': 'SHADOW',
            'scope': 'CRYPTO_ONLY',
            'blocking': False,
            'ec_020_sitc': {
                'broken_chain_pct': self._safe_pct(sitc_rows),
                'failure_taxonomy': {row['sitc_failure_type']: row['failure_count']
                                     for row in sitc_rows if row['sitc_failure_type']},
                'avg_score': float(sitc_rows[0]['avg_score'] or 0) if sitc_rows else 0
            },
            'ec_022_ikea': {
                'fabrication_pct': self._safe_div(ikea_row['fabrication_flags'], ikea_row['total']) * 100 if ikea_row else 0,
                'stale_data_pct': self._safe_div(ikea_row['stale_data_flags'], ikea_row['total']) * 100 if ikea_row else 0,
                'unverifiable_pct': self._safe_div(ikea_row['unverifiable_flags'], ikea_row['total']) * 100 if ikea_row else 0,
                'avg_score': float(ikea_row['avg_score'] or 0) if ikea_row else 0,
                'avg_freshness_hours': float(ikea_row['avg_freshness'] or 0) if ikea_row else 0
            },
            'ec_021_inforage': {
                'total_cost_usd': float(inforage_row['total_cost'] or 0) if inforage_row else 0,
                'avg_marginal_cost': float(inforage_row['avg_marginal_cost'] or 0) if inforage_row else 0,
                'avg_budget_pressure': float(inforage_row['avg_budget_pressure'] or 0) if inforage_row else 0,
                'total_api_calls': int(inforage_row['total_api_calls'] or 0) if inforage_row else 0
            }
        }

    def _safe_pct(self, rows) -> float:
        if not rows:
            return 0.0
        total = sum(r['total'] or 0 for r in rows)
        broken = sum(r['broken_chains'] or 0 for r in rows)
        return round(broken / total * 100, 2) if total > 0 else 0.0

    def _safe_div(self, a, b) -> float:
        if not b or b == 0:
            return 0.0
        return (a or 0) / b

    def close(self):
        self.conn.close()


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='ACI Triangle Shadow Evaluator')
    parser.add_argument('--evaluate', action='store_true', help='Evaluate recent crypto needles')
    parser.add_argument('--hours', type=int, default=24, help='Hours to look back')
    parser.add_argument('--telemetry', action='store_true', help='Get current telemetry')
    parser.add_argument('--limit', type=int, default=1000, help='Max needles to evaluate (covers all 740+)')
    args = parser.parse_args()

    aci = ACITriangleShadow()

    try:
        if args.evaluate:
            print("=" * 70)
            print("ACI TRIANGLE SHADOW EVALUATION")
            print("Mode: SHADOW / AUDIT-ONLY (Non-Blocking)")
            print("Scope: CRYPTO ASSETS ONLY")
            print("=" * 70)

            results = aci.evaluate_recent_needles(hours=args.hours, limit=args.limit)

            print(f"\nEvaluated: {results['evaluated']} crypto needles")
            print(f"Skipped (non-crypto): {results['skipped_non_crypto']}")

            print(f"\n--- EC-020 SitC (Reasoning Chain) ---")
            print(f"Broken chains: {results['sitc_broken_chains']} ({results['sitc_broken_chains']/max(1,results['evaluated'])*100:.1f}%)")
            print(f"Avg SitC score: {results['avg_sitc_score']}")
            print(f"Failure taxonomy: {results['failure_taxonomy']}")

            print(f"\n--- EC-022 IKEA (Hallucination Firewall) ---")
            print(f"Flagged: {results['ikea_flagged']} ({results['ikea_flagged']/max(1,results['evaluated'])*100:.1f}%)")
            print(f"Avg IKEA score: {results['avg_ikea_score']}")

            print(f"\n--- EC-021 InForage (API Budget) ---")
            print(f"Total API cost: ${results['total_api_cost']:.4f}")
            print(f"Avg budget pressure: {results['avg_budget_pressure']*100:.1f}%")

            print("\n" + "=" * 70)
            print("SHADOW MODE: No needles blocked or rejected")
            print("=" * 70)

        elif args.telemetry:
            telemetry = aci.get_telemetry()
            print(json.dumps(telemetry, indent=2, default=str))

        else:
            parser.print_help()

    finally:
        aci.close()


if __name__ == '__main__':
    main()
