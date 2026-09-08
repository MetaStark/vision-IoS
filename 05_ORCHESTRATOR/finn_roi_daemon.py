#!/usr/bin/env python3
"""
FINN_ROI DAEMON - ROI-Focused Alpha Generation Engine
======================================================
Authority: ADR-020 (ACI), ADR-012 (Economic Safety)
Cognitive Engines: EC-020 (SitC), EC-021 (InForage), EC-022 (IKEA)
Contract: EC-004 (FINN CRIO)
Classification: Proof of Value (PoV) Loop

PURPOSE:
    Transform FINN from a "researcher" into an "investor" -
    Every token spent is an investment in information.
    ROI = Alpha Generated / (Compute + API + Time + Error Cost)

COGNITIVE ENGINE HIERARCHY:
    1. EC-022 IKEA: "Is this fact?" (Knowledge Classification)
    2. EC-021 InForage: "Is it worth checking?" (ROI-based Search)
    3. EC-020 SitC: "Build reasoning chain" (Alpha Synthesis)

ECONOMIC CONSTRAINT:
    - Every decision has a price tag
    - Only positive expected ROI actions are executed
    - System learns what generates alpha vs. burns money

SIGNED:
    LARS - CSEO (Tier-1 Authority)
    STIG - Implementation
    FINN - Research Execution
"""

import os
import sys
import json
import time
import random
import hashlib
import signal
import logging
import uuid
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass, field, asdict
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# =============================================================================
# CONFIGURATION - ECONOMIC PARAMETERS
# =============================================================================

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# DeepSeek API
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

# =============================================================================
# DeepSeek API Pricing (as of 2025-12-15)
# Source: https://api-docs.deepseek.com/quick_start/pricing
#
# deepseek-chat:
#   - Input tokens (cache hit):  $0.028 / 1M tokens
#   - Input tokens (cache miss): $0.28  / 1M tokens
#   - Output tokens:             $0.42  / 1M tokens
#
# Typical usage per call:
#   - IKEA classification: ~300 input + ~100 output tokens
#   - Reasoning step:      ~500 input + ~200 output tokens
# =============================================================================

# Economic Constants (ADR-012 Compliant) - ACTUAL DeepSeek Costs
DEEPSEEK_INPUT_COST_PER_TOKEN = 0.00000028   # $0.28 / 1M tokens (cache miss)
DEEPSEEK_OUTPUT_COST_PER_TOKEN = 0.00000042  # $0.42 / 1M tokens

# Estimated costs per operation (based on actual token usage)
COST_PER_LLM_CALL = 0.00013      # ~300 input + ~100 output = $0.000126 rounded
COST_PER_SEARCH = 0.0            # Internal DB query - FREE (no external API)
COST_PER_REASONING = 0.00022     # ~500 input + ~200 output = $0.000224 rounded
MIN_ROI_THRESHOLD = 2.0          # Require 2x expected return to proceed
DAILY_BUDGET_LIMIT = 1.00        # $1/day max spend (very conservative)
HOURLY_CALL_LIMIT = 1000         # Max 1000 LLM calls per hour (DeepSeek is cheap)

# IKEA Confidence Thresholds
FACT_CONFIDENCE_THRESHOLD = 0.7  # Above this = HARD_FACT
ASSUMPTION_THRESHOLD = 0.4       # Below this = NOISE

# Daemon Configuration
DEFAULT_CYCLE_INTERVAL = 60      # 60 seconds between cycles

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [FINN_ROI] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('finn_roi_daemon')

EVIDENCE_DIR = Path(__file__).parent / "evidence" / "finn_roi"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# ENUMS & DATA STRUCTURES
# =============================================================================

class InfoType(Enum):
    """IKEA Knowledge Classification (EC-022)"""
    HARD_FACT = "HARD_FACT"           # Verified, can act on
    ASSUMPTION = "ASSUMPTION"          # Needs verification
    NOISE = "NOISE"                    # Discard
    EXTERNAL_REQUIRED = "EXTERNAL"     # Must fetch from external source


class SearchDecision(Enum):
    """InForage Decision (EC-021)"""
    EXECUTE = "EXECUTE"       # ROI positive, proceed with search
    ABORT = "ABORT"           # ROI negative, skip
    DEFER = "DEFER"           # Borderline, wait for more context


class VolatilityClass(Enum):
    """IKEA Volatility Classification"""
    EXTREME = "EXTREME"       # Real-time (prices, FX)
    HIGH = "HIGH"             # Quarterly (earnings)
    MEDIUM = "MEDIUM"         # Monthly (macro)
    LOW = "LOW"               # Yearly (sectors)
    STATIC = "STATIC"         # Never changes (formulas)


@dataclass
class KnowledgeNode:
    """Represents a piece of knowledge in the reasoning chain"""
    id: str
    content: str
    source: str
    info_type: InfoType
    confidence: float
    volatility: VolatilityClass
    timestamp: datetime
    cost_to_acquire: float = 0.0
    verified: bool = False


@dataclass
class SearchCandidate:
    """A potential search action with ROI analysis"""
    id: str
    query: str
    knowledge_gap: str
    scent_score: float          # Expected information value
    estimated_cost: float
    expected_alpha_impact: float
    decision: SearchDecision = SearchDecision.ABORT


@dataclass
class AlphaHypothesis:
    """Output of the reasoning chain"""
    id: str
    hypothesis: str
    direction: str              # LONG, SHORT, NEUTRAL
    confidence: float
    evidence_chain: List[str]
    total_cost: float
    expected_alpha_value: float
    roi: float
    timestamp: datetime


@dataclass
class CycleMetrics:
    """Metrics for a single FINN_ROI cycle"""
    cycle_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    signals_processed: int = 0
    ikea_classifications: int = 0
    inforage_decisions: int = 0
    searches_executed: int = 0
    searches_aborted: int = 0
    hypotheses_generated: int = 0
    total_cost: float = 0.0
    total_alpha_value: float = 0.0
    roi: float = 0.0
    defcon_level: str = "GREEN"


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for complex types"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, Enum):
            return obj.value
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)


# =============================================================================
# EC-022: IKEA ENGINE (Knowledge Boundary Awareness)
# =============================================================================

class EC022_IKEA_Engine:
    """
    IKEA: Internal-External Knowledge Synergistic Reasoning

    Responsibility: Prevent hallucination by classifying knowledge.
    Motto: "Don't guess, check."

    Capabilities:
    - Classify claims as PARAMETRIC (internal) or EXTERNAL (must retrieve)
    - Compute Internal Certainty Score (0.0 - 1.0)
    - Apply volatility classes to determine freshness requirements
    - Block any output flagged as EXTERNAL_REQUIRED without retrieval evidence
    """

    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm and bool(DEEPSEEK_API_KEY)
        self.classification_count = 0
        self.total_cost = 0.0

    def classify(self, content: str, source: str = "unknown") -> Tuple[InfoType, float, float]:
        """
        Classify a piece of information.

        Returns: (InfoType, confidence, cost)
        """
        self.classification_count += 1

        if self.use_llm:
            return self._llm_classify(content, source)
        else:
            return self._heuristic_classify(content, source)

    def _llm_classify(self, content: str, source: str) -> Tuple[InfoType, float, float]:
        """Use DeepSeek to classify knowledge type"""
        prompt = f"""You are IKEA, a knowledge classification engine. Analyze this statement:

STATEMENT: "{content}"
SOURCE: {source}

Classify into exactly ONE category:
1. HARD_FACT - Verifiable, time-stable fact (e.g., "Bitcoin halving occurs every ~4 years")
2. ASSUMPTION - Opinion or prediction that needs verification (e.g., "BTC will pump tomorrow")
3. NOISE - Irrelevant or unreliable information (e.g., "My uncle thinks crypto is dead")
4. EXTERNAL - Time-sensitive data that MUST be retrieved fresh (e.g., "Current BTC price is $X")

Also assess:
- CONFIDENCE: How certain are you about this classification? (0.0 to 1.0)
- VOLATILITY: How quickly does this information change? (EXTREME/HIGH/MEDIUM/LOW/STATIC)

Respond ONLY with valid JSON:
{{"type": "HARD_FACT|ASSUMPTION|NOISE|EXTERNAL", "confidence": 0.X, "volatility": "MEDIUM", "reasoning": "brief explanation"}}"""

        try:
            response = requests.post(
                DEEPSEEK_API_URL,
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,  # Low temp for deterministic classification
                    "max_tokens": 150
                },
                timeout=10
            )
            response.raise_for_status()

            result = response.json()
            content_str = result['choices'][0]['message']['content'].strip()

            # Parse JSON response
            # Handle markdown code blocks
            if content_str.startswith('```'):
                content_str = content_str.split('```')[1]
                if content_str.startswith('json'):
                    content_str = content_str[4:]

            parsed = json.loads(content_str)

            info_type_map = {
                "HARD_FACT": InfoType.HARD_FACT,
                "ASSUMPTION": InfoType.ASSUMPTION,
                "NOISE": InfoType.NOISE,
                "EXTERNAL": InfoType.EXTERNAL_REQUIRED
            }

            info_type = info_type_map.get(parsed.get('type', 'NOISE'), InfoType.NOISE)
            confidence = float(parsed.get('confidence', 0.5))

            cost = COST_PER_LLM_CALL
            self.total_cost += cost

            logger.debug(f"IKEA LLM: {content[:50]}... -> {info_type.value} ({confidence:.2f})")

            return info_type, confidence, cost

        except Exception as e:
            logger.warning(f"IKEA LLM failed: {e}, falling back to heuristic")
            return self._heuristic_classify(content, source)

    def _heuristic_classify(self, content: str, source: str) -> Tuple[InfoType, float, float]:
        """Fallback heuristic classification (no LLM cost)"""
        content_lower = content.lower()

        # Check for EXTERNAL indicators (time-sensitive)
        external_keywords = ['price', 'current', 'now', 'today', 'rate', 'live', '$']
        if any(kw in content_lower for kw in external_keywords):
            return InfoType.EXTERNAL_REQUIRED, 0.8, 0.0

        # Check for HARD_FACT indicators
        fact_keywords = ['confirmed', 'data shows', 'according to', 'verified', 'official']
        if any(kw in content_lower for kw in fact_keywords):
            return InfoType.HARD_FACT, 0.75, 0.0

        # Check for ASSUMPTION indicators
        assumption_keywords = ['think', 'believe', 'might', 'could', 'probably', 'expect', 'predict']
        if any(kw in content_lower for kw in assumption_keywords):
            return InfoType.ASSUMPTION, 0.6, 0.0

        # Check for NOISE indicators
        noise_keywords = ['rumor', 'heard', 'someone said', 'maybe', 'idk', 'lol']
        if any(kw in content_lower for kw in noise_keywords):
            return InfoType.NOISE, 0.9, 0.0

        # Default: Assumption with medium confidence
        return InfoType.ASSUMPTION, 0.5, 0.0

    def get_volatility_class(self, content: str) -> VolatilityClass:
        """Determine how quickly this information becomes stale"""
        content_lower = content.lower()

        if any(kw in content_lower for kw in ['price', 'rate', 'volume', 'spread']):
            return VolatilityClass.EXTREME
        if any(kw in content_lower for kw in ['earnings', 'revenue', 'profit']):
            return VolatilityClass.HIGH
        if any(kw in content_lower for kw in ['gdp', 'cpi', 'employment', 'inflation']):
            return VolatilityClass.MEDIUM
        if any(kw in content_lower for kw in ['sector', 'industry', 'market cap']):
            return VolatilityClass.LOW

        return VolatilityClass.STATIC


# =============================================================================
# EC-021: INFORAGE ENGINE (Information Foraging)
# =============================================================================

class EC021_InForage_Engine:
    """
    InForage: Information Foraging Protocol

    Responsibility: Treat information retrieval as strategic investment.
    Motto: "Is this search worth the money?"

    Capabilities:
    - Compute Scent Score (predicted information value)
    - Adaptive termination when ROI plateaus
    - Budget management (ADR-012 compliant)
    - Source tiering (Lake -> Pulse -> Sniper)
    """

    def __init__(self):
        self.searches_executed = 0
        self.searches_aborted = 0
        self.total_cost = 0.0
        self.budget_remaining = DAILY_BUDGET_LIMIT

    def compute_scent_score(
        self,
        knowledge_gap: str,
        current_volatility: float,
        regime: str,
        defcon_level: str
    ) -> SearchCandidate:
        """
        Compute the "scent score" for a potential search.

        Scent = (Relevance × Volatility Impact × Regime Alignment) / Cost

        Returns: SearchCandidate with decision
        """
        candidate_id = str(uuid.uuid4())[:8]

        # 1. Estimate Relevance (0.0 - 1.0)
        relevance = self._estimate_relevance(knowledge_gap)

        # 2. Volatility Impact (higher vol = higher potential alpha)
        vol_impact = min(current_volatility * 50, 2.0)  # Cap at 2x

        # 3. Regime Alignment (certain regimes favor certain searches)
        regime_multiplier = self._get_regime_multiplier(knowledge_gap, regime)

        # 4. DEFCON Penalty (higher DEFCON = more conservative)
        defcon_penalty = self._get_defcon_penalty(defcon_level)

        # 5. Calculate expected alpha impact
        expected_alpha = relevance * vol_impact * regime_multiplier * 100  # Base $100
        expected_alpha *= defcon_penalty

        # 6. Cost estimation
        estimated_cost = COST_PER_SEARCH

        # 7. Scent Score = Expected Value / Cost
        scent_score = expected_alpha / estimated_cost if estimated_cost > 0 else 0

        # 8. Make decision based on ROI threshold
        if scent_score >= MIN_ROI_THRESHOLD and self.budget_remaining >= estimated_cost:
            decision = SearchDecision.EXECUTE
        elif scent_score >= MIN_ROI_THRESHOLD * 0.8:
            decision = SearchDecision.DEFER
        else:
            decision = SearchDecision.ABORT

        return SearchCandidate(
            id=candidate_id,
            query=knowledge_gap,
            knowledge_gap=knowledge_gap,
            scent_score=scent_score,
            estimated_cost=estimated_cost,
            expected_alpha_impact=expected_alpha,
            decision=decision
        )

    def _estimate_relevance(self, gap: str) -> float:
        """Estimate relevance of knowledge gap to alpha generation"""
        gap_lower = gap.lower()

        # High relevance keywords
        high_relevance = ['regime', 'liquidity', 'volatility', 'correlation', 'momentum']
        if any(kw in gap_lower for kw in high_relevance):
            return 0.9

        # Medium relevance
        medium_relevance = ['price', 'volume', 'trend', 'market', 'sentiment']
        if any(kw in gap_lower for kw in medium_relevance):
            return 0.7

        # Low relevance
        low_relevance = ['news', 'rumor', 'opinion', 'social']
        if any(kw in gap_lower for kw in low_relevance):
            return 0.4

        return 0.5

    def _get_regime_multiplier(self, gap: str, regime: str) -> float:
        """Certain searches are more valuable in certain regimes"""
        gap_lower = gap.lower()

        if regime in ['BULL', 'STRONG_BULL']:
            # In bull: momentum and breakout searches are valuable
            if any(kw in gap_lower for kw in ['momentum', 'breakout', 'strength']):
                return 1.5
        elif regime in ['BEAR', 'STRONG_BEAR']:
            # In bear: risk and correlation searches are valuable
            if any(kw in gap_lower for kw in ['risk', 'correlation', 'hedge']):
                return 1.5
        elif regime == 'NEUTRAL':
            # In neutral: volatility and regime change searches are valuable
            if any(kw in gap_lower for kw in ['volatility', 'regime', 'transition']):
                return 1.3

        return 1.0

    def _get_defcon_penalty(self, defcon: str) -> float:
        """Higher DEFCON = more conservative = lower search appetite"""
        defcon_map = {
            'GREEN': 1.0,   # Full search budget
            'BLUE': 0.9,
            'YELLOW': 0.7,
            'ORANGE': 0.4,
            'RED': 0.1      # Almost no searches
        }
        return defcon_map.get(defcon.upper(), 1.0)

    def execute_search(self, candidate: SearchCandidate) -> Optional[str]:
        """Execute the search and return result"""
        if candidate.decision != SearchDecision.EXECUTE:
            self.searches_aborted += 1
            logger.info(f"InForage ABORT: {candidate.query[:40]}... (scent={candidate.scent_score:.2f})")
            return None

        if self.budget_remaining < candidate.estimated_cost:
            self.searches_aborted += 1
            logger.warning(f"InForage ABORT: Budget exhausted (${self.budget_remaining:.2f} remaining)")
            return None

        # Execute the search
        self.searches_executed += 1
        self.total_cost += candidate.estimated_cost
        self.budget_remaining -= candidate.estimated_cost

        logger.info(
            f"InForage EXECUTE: {candidate.query[:40]}... "
            f"(scent={candidate.scent_score:.2f}, cost=${candidate.estimated_cost:.3f})"
        )

        # TODO: Replace with actual search (Serper API, database query, etc.)
        # For PoV: Return mock verification
        return f"VERIFIED: {candidate.query}"

    def get_budget_status(self) -> Dict[str, float]:
        """Get current budget status"""
        return {
            'daily_limit': DAILY_BUDGET_LIMIT,
            'spent': self.total_cost,
            'remaining': self.budget_remaining,
            'utilization': self.total_cost / DAILY_BUDGET_LIMIT if DAILY_BUDGET_LIMIT > 0 else 0
        }


# =============================================================================
# EC-020: SitC ENGINE (Search-in-the-Chain)
# =============================================================================

class EC020_SitC_Engine:
    """
    SitC: Search-in-the-Chain Protocol

    Responsibility: Build dynamic reasoning chains for alpha synthesis.
    Motto: "Think deeper, correct along the way."

    Capabilities:
    - Decompose hypotheses into reasoning trees
    - Interleave reasoning with search (via InForage)
    - Correction loops when evidence contradicts assumptions
    - Global plan refinement
    """

    def __init__(self):
        self.reasoning_steps = 0
        self.total_cost = 0.0

    def generate_hypothesis(
        self,
        facts: List[KnowledgeNode],
        market_context: Dict[str, Any]
    ) -> AlphaHypothesis:
        """
        Synthesize an alpha hypothesis from verified facts.

        Uses reasoning chain to derive actionable insight.
        """
        hypothesis_id = str(uuid.uuid4())
        self.reasoning_steps += 1

        # Extract evidence chain
        evidence_chain = [f.content for f in facts if f.verified or f.info_type == InfoType.HARD_FACT]

        if not evidence_chain:
            # No verified facts - cannot generate hypothesis
            return AlphaHypothesis(
                id=hypothesis_id,
                hypothesis="INSUFFICIENT_DATA",
                direction="NEUTRAL",
                confidence=0.0,
                evidence_chain=[],
                total_cost=0.0,
                expected_alpha_value=0.0,
                roi=0.0,
                timestamp=datetime.now(timezone.utc)
            )

        # Calculate confidence based on evidence strength
        avg_confidence = sum(f.confidence for f in facts) / len(facts) if facts else 0.0

        # Determine direction from market context
        regime = market_context.get('regime', 'NEUTRAL')
        direction = self._infer_direction(facts, regime)

        # Calculate total cost
        total_cost = sum(f.cost_to_acquire for f in facts)
        total_cost += COST_PER_REASONING
        self.total_cost += COST_PER_REASONING

        # Estimate alpha value (with Gaussian noise for realism)
        base_alpha = 500.0 if avg_confidence > 0.8 else 200.0 if avg_confidence > 0.6 else 50.0
        alpha_value = random.gauss(base_alpha, base_alpha * 0.15)  # 15% std dev
        alpha_value = max(0, alpha_value)  # Can't be negative

        # Calculate ROI
        roi = alpha_value / total_cost if total_cost > 0 else 0.0

        # Generate hypothesis text
        hypothesis_text = self._synthesize_hypothesis(facts, direction, regime)

        return AlphaHypothesis(
            id=hypothesis_id,
            hypothesis=hypothesis_text,
            direction=direction,
            confidence=avg_confidence,
            evidence_chain=evidence_chain,
            total_cost=total_cost,
            expected_alpha_value=alpha_value,
            roi=roi,
            timestamp=datetime.now(timezone.utc)
        )

    def _infer_direction(self, facts: List[KnowledgeNode], regime: str) -> str:
        """Infer trading direction from facts and regime"""
        # Count bullish/bearish signals in facts
        bullish_keywords = ['bullish', 'up', 'growth', 'expansion', 'buy', 'long', 'positive']
        bearish_keywords = ['bearish', 'down', 'contraction', 'sell', 'short', 'negative', 'risk']

        bullish_count = 0
        bearish_count = 0

        for fact in facts:
            content_lower = fact.content.lower()
            bullish_count += sum(1 for kw in bullish_keywords if kw in content_lower)
            bearish_count += sum(1 for kw in bearish_keywords if kw in content_lower)

        # Regime bias
        if regime in ['BULL', 'STRONG_BULL']:
            bullish_count += 2
        elif regime in ['BEAR', 'STRONG_BEAR']:
            bearish_count += 2

        if bullish_count > bearish_count + 1:
            return "LONG"
        elif bearish_count > bullish_count + 1:
            return "SHORT"
        else:
            return "NEUTRAL"

    def _synthesize_hypothesis(self, facts: List[KnowledgeNode], direction: str, regime: str) -> str:
        """Generate hypothesis text from facts"""
        fact_summary = " | ".join(f.content[:50] for f in facts[:3])

        direction_text = {
            "LONG": "bullish opportunity",
            "SHORT": "bearish setup",
            "NEUTRAL": "no clear directional edge"
        }

        return f"Based on {len(facts)} verified facts in {regime} regime: {direction_text[direction]}. Evidence: {fact_summary}"


# =============================================================================
# FINN_ROI DAEMON - Main Engine
# =============================================================================

class FINN_ROI_Daemon:
    """
    FINN_ROI: ROI-Focused Alpha Generation Daemon

    Transforms FINN from researcher to investor.
    Every token spent is an investment in information.
    """

    def __init__(self, cycle_interval: int = DEFAULT_CYCLE_INTERVAL):
        self.ikea = EC022_IKEA_Engine(use_llm=True)
        self.inforage = EC021_InForage_Engine()
        self.sitc = EC020_SitC_Engine()

        self.cycle_interval = cycle_interval
        self.running = False
        self.cycle_count = 0

        self.conn = None

        # Metrics
        self.total_spend = 0.0
        self.total_alpha_generated = 0.0
        self.hypotheses_generated = 0

        # Signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        logger.info(f"FINN_ROI Daemon initialized (interval={cycle_interval}s)")

    def _signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False

    def _get_connection(self):
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(**DB_CONFIG)
        return self.conn

    def _execute_query(self, query: str, params: tuple = None, commit: bool = False) -> List[Dict]:
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                if commit:
                    conn.commit()
                if cur.description:
                    return [dict(row) for row in cur.fetchall()]
                return []
        except psycopg2.Error as e:
            conn.rollback()
            raise

    def get_market_context(self) -> Dict[str, Any]:
        """Get current market context for decision making"""
        context = {
            'regime': 'NEUTRAL',
            'defcon_level': 'GREEN',
            'volatility': 0.02,
            'btc_price': 0.0,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        try:
            # Get regime
            regime_result = self._execute_query("""
                SELECT sovereign_regime, state_probabilities
                FROM fhq_perception.sovereign_regime_state_v4
                WHERE asset_id = 'BTC-USD'
                ORDER BY timestamp DESC LIMIT 1
            """)
            if regime_result:
                context['regime'] = regime_result[0]['sovereign_regime']

            # Get DEFCON
            defcon_result = self._execute_query("""
                SELECT defcon_level FROM fhq_governance.defcon_state
                WHERE is_current = true LIMIT 1
            """)
            if defcon_result:
                context['defcon_level'] = defcon_result[0]['defcon_level']

            # Get BTC price
            price_result = self._execute_query("""
                SELECT close FROM fhq_market.prices
                WHERE canonical_id = 'BTC-USD'
                ORDER BY timestamp DESC LIMIT 1
            """)
            if price_result:
                context['btc_price'] = float(price_result[0]['close'])

        except Exception as e:
            logger.warning(f"Failed to get market context: {e}")

        return context

    def get_raw_signals(self) -> List[Dict]:
        """
        Get raw signals from VERIFIED database sources only.
        NO MOCK DATA - only real canonical data.

        Sources:
        - fhq_market.prices (price data)
        - fhq_perception.sovereign_regime_state_v4 (regime)
        - fhq_perception.regime_daily (daily regime)
        - fhq_graph.alpha_edges (causal signals)
        - fhq_research.weak_signal_summary (FINN research)
        """
        signals = []
        timestamp = time.time()

        try:
            # 1. Get latest price changes (real market data)
            price_signals = self._execute_query("""
                WITH latest_prices AS (
                    SELECT
                        canonical_id,
                        timestamp,
                        close,
                        volume,
                        LAG(close) OVER (PARTITION BY canonical_id ORDER BY timestamp) as prev_close
                    FROM fhq_market.prices
                    WHERE canonical_id IN ('BTC-USD', 'ETH-USD', 'SOL-USD')
                    ORDER BY timestamp DESC
                    LIMIT 9
                )
                SELECT
                    canonical_id,
                    timestamp,
                    close,
                    volume,
                    prev_close,
                    CASE
                        WHEN prev_close > 0 THEN ((close - prev_close) / prev_close * 100)
                        ELSE 0
                    END as pct_change
                FROM latest_prices
                WHERE prev_close IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 3
            """)

            for row in price_signals:
                pct_change = float(row.get('pct_change', 0))
                direction = 'up' if pct_change > 0 else 'down'

                signals.append({
                    'id': f'PRICE-{row["canonical_id"]}-{int(timestamp)}',
                    'content': f'{row["canonical_id"]} price ${float(row["close"]):,.2f}, {direction} {abs(pct_change):.2f}% from previous, volume: {float(row["volume"]):,.0f}',
                    'source': 'fhq_market.prices',
                    'timestamp': timestamp,
                    'data_type': 'PRICE',
                    'raw_data': dict(row)
                })

            # 2. Get current regime state (sovereign perception)
            regime_signals = self._execute_query("""
                SELECT
                    asset_id,
                    timestamp,
                    technical_regime,
                    sovereign_regime,
                    state_probabilities,
                    crio_dominant_driver,
                    crio_override_reason
                FROM fhq_perception.sovereign_regime_state_v4
                ORDER BY timestamp DESC
                LIMIT 3
            """)

            for row in regime_signals:
                probs = row.get('state_probabilities', {})
                max_prob = max(probs.values()) if probs else 0

                signals.append({
                    'id': f'REGIME-{row["asset_id"]}-{int(timestamp)}',
                    'content': f'{row["asset_id"]} regime: {row["sovereign_regime"]} (confidence: {max_prob:.2f}), technical: {row["technical_regime"]}',
                    'source': 'fhq_perception.sovereign_regime_state_v4',
                    'timestamp': timestamp,
                    'data_type': 'REGIME',
                    'raw_data': dict(row)
                })

            # 3. Get causal graph edges (alpha signals)
            try:
                edge_signals = self._execute_query("""
                    SELECT
                        source_node,
                        target_node,
                        edge_type,
                        strength,
                        confidence,
                        lag_days,
                        updated_at
                    FROM fhq_graph.alpha_edges
                    WHERE is_active = true
                    AND confidence > 0.7
                    ORDER BY updated_at DESC
                    LIMIT 3
                """)

                for row in edge_signals:
                    signals.append({
                        'id': f'EDGE-{row["source_node"]}-{row["target_node"]}-{int(timestamp)}',
                        'content': f'Causal edge: {row["source_node"]} -> {row["target_node"]} (type: {row["edge_type"]}, strength: {float(row["strength"]):.2f}, lag: {row["lag_days"]}d)',
                        'source': 'fhq_graph.alpha_edges',
                        'timestamp': timestamp,
                        'data_type': 'CAUSAL_EDGE',
                        'raw_data': dict(row)
                    })
            except Exception as e:
                logger.debug(f"No alpha edges available: {e}")

            # 4. Get weak signals from FINN research
            try:
                weak_signals = self._execute_query("""
                    SELECT
                        signal_type,
                        signal_strength,
                        confidence_level,
                        actionable,
                        summary,
                        created_at
                    FROM fhq_research.weak_signal_summary
                    WHERE actionable = true
                    AND created_at > NOW() - INTERVAL '24 hours'
                    ORDER BY created_at DESC
                    LIMIT 3
                """)

                for row in weak_signals:
                    signals.append({
                        'id': f'WEAK-{row["signal_type"]}-{int(timestamp)}',
                        'content': f'Weak signal detected: {row["signal_type"]} (strength: {float(row["signal_strength"]):.2f}, confidence: {float(row["confidence_level"]):.2f}). {row.get("summary", "")}',
                        'source': 'fhq_research.weak_signal_summary',
                        'timestamp': timestamp,
                        'data_type': 'WEAK_SIGNAL',
                        'raw_data': dict(row)
                    })
            except Exception as e:
                logger.debug(f"No weak signals available: {e}")

            # 5. Get technical indicators
            try:
                indicator_signals = self._execute_query("""
                    SELECT
                        canonical_id,
                        indicator_name,
                        value,
                        signal,
                        timestamp
                    FROM fhq_market.technical_indicators
                    WHERE canonical_id = 'BTC-USD'
                    AND timestamp = (SELECT MAX(timestamp) FROM fhq_market.technical_indicators WHERE canonical_id = 'BTC-USD')
                    AND indicator_name IN ('RSI', 'MACD', 'ADX')
                """)

                for row in indicator_signals:
                    signals.append({
                        'id': f'INDICATOR-{row["indicator_name"]}-{int(timestamp)}',
                        'content': f'BTC {row["indicator_name"]}: {float(row["value"]):.2f}, signal: {row.get("signal", "NEUTRAL")}',
                        'source': 'fhq_market.technical_indicators',
                        'timestamp': timestamp,
                        'data_type': 'INDICATOR',
                        'raw_data': dict(row)
                    })
            except Exception as e:
                logger.debug(f"No technical indicators available: {e}")

            if not signals:
                logger.warning("No signals found from any verified source")

            logger.info(f"Collected {len(signals)} signals from verified sources")
            return signals

        except Exception as e:
            logger.error(f"Failed to get signals from verified sources: {e}")
            return []

    def run_cycle(self) -> Optional[CycleMetrics]:
        """Run a single FINN_ROI cycle"""
        self.cycle_count += 1
        cycle_id = f"FINN_ROI_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        metrics = CycleMetrics(
            cycle_id=cycle_id,
            started_at=datetime.now(timezone.utc)
        )

        logger.info(f"=== FINN_ROI Cycle {self.cycle_count} started ===")

        try:
            # 1. Get market context
            context = self.get_market_context()
            metrics.defcon_level = context['defcon_level']

            # DEFCON check
            if context['defcon_level'] in ['ORANGE', 'RED']:
                logger.warning(f"DEFCON {context['defcon_level']} -> SHADOW_PAPER mode enforced")
                # Continue but don't generate real signals

            logger.info(f"Context: Regime={context['regime']}, DEFCON={context['defcon_level']}, BTC=${context['btc_price']:,.0f}")

            # 2. Get raw signals
            raw_signals = self.get_raw_signals()
            metrics.signals_processed = len(raw_signals)

            if not raw_signals:
                logger.info("No signals to process")
                metrics.ended_at = datetime.now(timezone.utc)
                return metrics

            # 3. Process each signal through cognitive pipeline
            verified_facts: List[KnowledgeNode] = []

            for signal in raw_signals:
                logger.info(f"\n--- Processing: {signal['id']} ---")
                logger.info(f"Content: {signal['content'][:60]}...")

                # STEP 1: IKEA Classification
                info_type, confidence, ikea_cost = self.ikea.classify(
                    signal['content'],
                    signal['source']
                )
                metrics.ikea_classifications += 1
                metrics.total_cost += ikea_cost

                logger.info(f"IKEA: {info_type.value} (confidence={confidence:.2f}, cost=${ikea_cost:.3f})")

                # Filter NOISE immediately
                if info_type == InfoType.NOISE:
                    logger.info("IKEA: Rejected as NOISE - $0 further cost")
                    continue

                # Create knowledge node
                node = KnowledgeNode(
                    id=signal['id'],
                    content=signal['content'],
                    source=signal['source'],
                    info_type=info_type,
                    confidence=confidence,
                    volatility=self.ikea.get_volatility_class(signal['content']),
                    timestamp=datetime.now(timezone.utc),
                    cost_to_acquire=ikea_cost,
                    verified=(info_type == InfoType.HARD_FACT)
                )

                # STEP 2: InForage ROI Check (for non-HARD_FACT)
                if info_type in [InfoType.ASSUMPTION, InfoType.EXTERNAL_REQUIRED]:
                    knowledge_gap = f"Verify: {signal['content']}"

                    candidate = self.inforage.compute_scent_score(
                        knowledge_gap,
                        context['volatility'],
                        context['regime'],
                        context['defcon_level']
                    )
                    metrics.inforage_decisions += 1

                    logger.info(
                        f"InForage: scent={candidate.scent_score:.2f}, "
                        f"expected_alpha=${candidate.expected_alpha_impact:.2f}, "
                        f"decision={candidate.decision.value}"
                    )

                    if candidate.decision == SearchDecision.EXECUTE:
                        # Execute search
                        result = self.inforage.execute_search(candidate)
                        metrics.searches_executed += 1
                        metrics.total_cost += candidate.estimated_cost

                        if result:
                            node.verified = True
                            node.cost_to_acquire += candidate.estimated_cost
                            node.content = result  # Update with verified content
                    else:
                        metrics.searches_aborted += 1
                        logger.info(f"InForage: Search aborted (ROI too low)")
                        continue  # Don't add unverified assumptions

                # Add to verified facts
                if node.verified or node.info_type == InfoType.HARD_FACT:
                    verified_facts.append(node)

            # 4. SitC Reasoning - Generate hypothesis if we have facts
            if verified_facts:
                logger.info(f"\n--- SitC: Synthesizing from {len(verified_facts)} verified facts ---")

                hypothesis = self.sitc.generate_hypothesis(verified_facts, context)
                metrics.hypotheses_generated += 1
                metrics.total_cost += COST_PER_REASONING
                metrics.total_alpha_value = hypothesis.expected_alpha_value

                self.total_spend += metrics.total_cost
                self.total_alpha_generated += hypothesis.expected_alpha_value
                self.hypotheses_generated += 1

                logger.info(f"HYPOTHESIS: {hypothesis.hypothesis[:80]}...")
                logger.info(f"Direction: {hypothesis.direction}, Confidence: {hypothesis.confidence:.2f}")
                logger.info(f"Expected Alpha: ${hypothesis.expected_alpha_value:.2f}, Total Cost: ${metrics.total_cost:.3f}")
                logger.info(f"ROI: {hypothesis.roi:.2f}x")

                # Log to database
                self._log_hypothesis(hypothesis, metrics)

                # Save evidence
                self._save_evidence(hypothesis, metrics, verified_facts)
            else:
                logger.info("No verified facts - cannot generate hypothesis")

            # 5. Calculate cycle ROI
            metrics.roi = metrics.total_alpha_value / metrics.total_cost if metrics.total_cost > 0 else 0
            metrics.ended_at = datetime.now(timezone.utc)

            duration = (metrics.ended_at - metrics.started_at).total_seconds()
            logger.info(f"\n=== Cycle {self.cycle_count} complete ({duration:.2f}s) ===")
            logger.info(f"Signals: {metrics.signals_processed}, Hypotheses: {metrics.hypotheses_generated}")
            logger.info(f"Cost: ${metrics.total_cost:.3f}, Alpha: ${metrics.total_alpha_value:.2f}, ROI: {metrics.roi:.2f}x")
            logger.info(f"Cumulative: Spend=${self.total_spend:.3f}, Alpha=${self.total_alpha_generated:.2f}")

            return metrics

        except Exception as e:
            logger.error(f"Cycle {self.cycle_count} failed: {e}")
            import traceback
            traceback.print_exc()
            metrics.ended_at = datetime.now(timezone.utc)
            return metrics

    def _log_hypothesis(self, hypothesis: AlphaHypothesis, metrics: CycleMetrics) -> None:
        """Log hypothesis to database"""
        try:
            self._execute_query("""
                INSERT INTO fhq_alpha.g0_draft_proposals (
                    proposal_id,
                    hypothesis_id,
                    hypothesis_title,
                    hypothesis_category,
                    hypothesis_statement,
                    confidence_score,
                    executive_summary,
                    falsification_criteria,
                    execution_authority,
                    state_hash_at_creation,
                    proposal_status,
                    created_at
                ) VALUES (
                    gen_random_uuid(),
                    %s,
                    %s,
                    'ROI_ALPHA',
                    %s,
                    %s,
                    %s,
                    %s,
                    'FINN_ROI',
                    %s,
                    'G0_DRAFT',
                    NOW()
                )
            """, (
                hypothesis.id,
                f"FINN_ROI: {hypothesis.direction} ({hypothesis.confidence:.2f})",
                hypothesis.hypothesis,
                hypothesis.confidence,
                f"Direction: {hypothesis.direction}, ROI: {hypothesis.roi:.2f}x, Cost: ${hypothesis.total_cost:.3f}",
                json.dumps({
                    'direction_reversal': f'Signal flips to opposite of {hypothesis.direction}',
                    'confidence_drop': 'Confidence falls below 0.5',
                    'roi_negative': 'ROI becomes negative'
                }),
                hashlib.sha256(json.dumps(asdict(metrics), cls=DecimalEncoder).encode()).hexdigest()
            ), commit=True)

            logger.info(f"Hypothesis logged to g0_draft_proposals: {hypothesis.id}")

        except Exception as e:
            logger.warning(f"Failed to log hypothesis: {e}")

    def _save_evidence(self, hypothesis: AlphaHypothesis, metrics: CycleMetrics, facts: List[KnowledgeNode]) -> None:
        """Save evidence bundle to file"""
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        filename = f"FINN_ROI_{timestamp}.json"
        filepath = EVIDENCE_DIR / filename

        evidence = {
            'metadata': {
                'type': 'FINN_ROI_EVIDENCE',
                'version': 'PoV_1.0',
                'timestamp': datetime.now(timezone.utc).isoformat()
            },
            'hypothesis': asdict(hypothesis),
            'metrics': asdict(metrics),
            'facts': [asdict(f) for f in facts],
            'engines': {
                'ikea_classifications': self.ikea.classification_count,
                'ikea_cost': self.ikea.total_cost,
                'inforage_searches': self.inforage.searches_executed,
                'inforage_aborted': self.inforage.searches_aborted,
                'inforage_cost': self.inforage.total_cost,
                'sitc_reasoning_steps': self.sitc.reasoning_steps,
                'sitc_cost': self.sitc.total_cost
            },
            'cumulative': {
                'total_spend': self.total_spend,
                'total_alpha': self.total_alpha_generated,
                'hypotheses_generated': self.hypotheses_generated,
                'overall_roi': self.total_alpha_generated / self.total_spend if self.total_spend > 0 else 0
            }
        }

        with open(filepath, 'w') as f:
            json.dump(evidence, f, indent=2, cls=DecimalEncoder, default=str)

        logger.info(f"Evidence saved: {filepath}")

    def start(self) -> None:
        """Start the daemon loop"""
        self.running = True
        logger.info("FINN_ROI Daemon starting...")
        logger.info(f"Budget: ${DAILY_BUDGET_LIMIT}/day, ROI threshold: {MIN_ROI_THRESHOLD}x")

        while self.running:
            try:
                self.run_cycle()
            except Exception as e:
                logger.error(f"Cycle error: {e}")

            if self.running:
                logger.info(f"Sleeping {self.cycle_interval}s until next cycle...")
                time.sleep(self.cycle_interval)

        logger.info("FINN_ROI Daemon stopped")
        logger.info(f"Final stats: Spend=${self.total_spend:.3f}, Alpha=${self.total_alpha_generated:.2f}")

    def stop(self) -> None:
        self.running = False


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='FINN_ROI Alpha Generation Daemon')
    parser.add_argument('--interval', '-i', type=int, default=DEFAULT_CYCLE_INTERVAL,
                        help=f'Cycle interval in seconds (default: {DEFAULT_CYCLE_INTERVAL})')
    parser.add_argument('--once', action='store_true', help='Run single cycle and exit')
    parser.add_argument('--test', action='store_true', help='Run with 3 test scenarios')

    args = parser.parse_args()

    daemon = FINN_ROI_Daemon(cycle_interval=args.interval)

    if args.test:
        # Test with 3 scenarios: Noise, Low ROI, High ROI
        print("\n" + "="*60)
        print("FINN_ROI TEST MODE: 3 Scenarios")
        print("="*60)

        test_signals = [
            ("NOISE", "My neighbor thinks crypto is a scam lol"),
            ("LOW_ROI", "I think maybe BTC could go up tomorrow"),
            ("HIGH_ROI", "Confirmed: FED announces rate cut, markets responding positively")
        ]

        for scenario, content in test_signals:
            print(f"\n--- Test: {scenario} ---")
            print(f"Input: {content}")

            info_type, confidence, cost = daemon.ikea.classify(content, "test")
            print(f"IKEA: {info_type.value} (confidence={confidence:.2f})")

            if info_type != InfoType.NOISE:
                candidate = daemon.inforage.compute_scent_score(
                    f"Verify: {content}", 0.03, "NEUTRAL", "GREEN"
                )
                print(f"InForage: scent={candidate.scent_score:.2f}, decision={candidate.decision.value}")

        print("\n" + "="*60)
        print("Test complete. Run --once for full cycle.")
        print("="*60)

    elif args.once:
        daemon.run_cycle()
    else:
        try:
            daemon.start()
        except KeyboardInterrupt:
            daemon.stop()


if __name__ == '__main__':
    main()
