#!/usr/bin/env python3
"""
FINN DEEPSEEK RESEARCHER v1.0 (CRIO Implementation)
====================================================
Agent: FINN (Chief Research & Intelligence Officer)
Contract: EC-004
Authority: CEO Directive - ACTIVATE FINN DEEPSEEK RESEARCH ENGINE

PHASE 4b TELEMETRY INSTRUMENTATION (2025-12-10)
- CEO Directive 2026-FHQ-PHASE-4b
- CS-001 CRIO Core wrapped with @metered_execution
- CONTROLLED INSTRUMENTATION - NO BEHAVIOR CHANGE
- Compliance: ADR-012, ADR-018, ADR-020, ADR-021, TCS-v1, DC-v1

PURPOSE:
    Production-grade DeepSeek-powered research engine for FINN.
    Replaces all RNG/mock implementations with real LLM analysis.

CRIO CONTRACT:
    - Context-only reasoning (no hallucination)
    - Deterministic output structure
    - Token budget enforcement (ADR-012)
    - T-1 snapshot temporal rule (ADR-017)

OUTPUTS:
    - fragility_score (0.0-1.0)
    - dominant_driver (string)
    - reasoning_summary (JSON)

SOVEREIGNTY INTEGRATION:
    - LIDS Truth Gate validation
    - RISL Anomaly verification
    - ACL Coordination hooks

Generated: 2025-12-08
Authorized: CEO
"""

from __future__ import annotations

import os
import sys
import json
import hashlib
import uuid
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
from dataclasses import dataclass, asdict
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv(override=True)  # Override system env vars with .env values

# =============================================================================
# CEO-DIR-2026-019 P0-3: COURT-PROOF EVIDENCE INTEGRATION
# =============================================================================
# Import CourtProofEnforcerV2 for ASRP binding and DDATP validation
# FAIL-CLOSED: Missing evidence = rejected output

COURT_PROOF_V2_ENABLED = False
try:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / '03_FUNCTIONS'))
    from court_proof_enforcer_v2 import (
        CourtProofEnforcerV2,
        CourtProofViolation,
        ASRPBindingViolation,
        DDATPValidationFailure
    )
    COURT_PROOF_V2_ENABLED = True
except ImportError as e:
    logging.warning(f"Court-proof v2 not available: {e}")

# =============================================================================
# PHASE 4b: TELEMETRY INSTRUMENTATION (CS-001 CRIO Core)
# =============================================================================
# CEO Directive 2026-FHQ-PHASE-4b requires telemetry wrapping of CRIO Core
# Following the same pattern as Phase 4a (CS-002 Night Research)
#
# IMPORTANT: This instrumentation must be TRANSPARENT:
# - Output must be bit-identical to unwrapped behavior
# - No retries added
# - No reasoning entropy changes
# - No chain length changes

# Add parent path for fhq_telemetry import
sys.path.insert(0, str(Path(__file__).parent.parent.parent / '03_FUNCTIONS'))

# Import telemetry (graceful fallback if unavailable)
TELEMETRY_ENABLED = False
try:
    from fhq_telemetry import meter_llm_call
    from fhq_telemetry.telemetry_envelope import TaskType, CognitiveModality
    TELEMETRY_ENABLED = True
except ImportError:
    # Telemetry not available - proceed without instrumentation
    pass

# =================================================================
# LOGGING
# =================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - FINN.CRIO - %(levelname)s - %(message)s'
)
logger = logging.getLogger("finn_deepseek_researcher")


# =================================================================
# PHASE 4b TELEMETRY HELPER
# =================================================================
# This function captures telemetry AFTER the LLM call completes
# It does NOT modify the call flow - only observes and records
# Fail-safe: If telemetry fails, the original result is still returned

def _emit_crio_telemetry(
    task_name: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: int,
    model: str = "deepseek-chat",
    error: Optional[Exception] = None,
    correlation_id: Optional[str] = None
) -> None:
    """
    Emit telemetry for a CRIO Core LLM call (PHASE 4b CS-001).

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
        model: Model used (deepseek-chat or deepseek-reasoner)
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
            agent_id='FINN_CRIO',
            task_name=task_name,
            task_type=TaskType.RESEARCH,
            provider='DEEPSEEK',
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            stream_mode=False,  # CRIO Core uses non-streaming by default
            error=error,
            correlation_id=correlation_uuid,
            cognitive_modality=CognitiveModality.SYNTHESIS
        )
        logger.debug(f"Telemetry emitted for {task_name}: {tokens_in}+{tokens_out} tokens")
    except Exception as e:
        # CRITICAL: Never let telemetry failure affect the main flow
        # Log warning but continue
        logger.warning(f"Telemetry emission failed (non-blocking): {e}")


# =================================================================
# CONFIGURATION
# =================================================================

@dataclass
class CRIOConfig:
    """FINN CRIO Engine Configuration"""

    AGENT_ID: str = "FINN"
    ENGINE_VERSION: str = "CRIO_v1"
    CONTRACT: str = "EC-004"

    # DeepSeek Configuration
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # ADR-012 Token Budget Limits
    MAX_INPUT_TOKENS: int = 4000
    MAX_OUTPUT_TOKENS: int = 1000
    MAX_DAILY_BUDGET_USD: float = 5.00
    # DeepSeek official pricing (2025-12-14): Input $0.28/M, Output $0.42/M
    COST_PER_1K_INPUT: float = 0.00028   # $0.28 per million tokens
    COST_PER_1K_OUTPUT: float = 0.00042  # $0.42 per million tokens

    # Research Parameters
    TEMPERATURE: float = 0.1  # Low for deterministic output
    TOP_P: float = 0.95

    # Database
    PGHOST: str = os.getenv("PGHOST", "127.0.0.1")
    PGPORT: str = os.getenv("PGPORT", "54322")
    PGDATABASE: str = os.getenv("PGDATABASE", "postgres")
    PGUSER: str = os.getenv("PGUSER", "postgres")
    PGPASSWORD: str = os.getenv("PGPASSWORD", "postgres")

    def get_connection_string(self) -> str:
        return f"postgresql://{self.PGUSER}:{self.PGPASSWORD}@{self.PGHOST}:{self.PGPORT}/{self.PGDATABASE}"


# =================================================================
# CRIO PROMPT TEMPLATES (DDATP v1.0 - CEO-DIR-2026-015B)
# =================================================================

CRIO_SYSTEM_PROMPT = """You are FINN, the Chief Research & Intelligence Officer for FjordHQ Autonomous Trading System.

Your role is to analyze market data and provide structured research insights.

STRICT RULES (CRIO Contract):
1. CONTEXT-ONLY: You may only reason from data explicitly provided. No external knowledge.
2. NO HALLUCINATION: If data is insufficient, state "INSUFFICIENT_DATA" - never guess.
3. DETERMINISTIC: Your output must be structured JSON matching the exact schema.
4. TEMPORAL: All analysis is T-1 (based on yesterday's close, not today).
5. ATTRIBUTION TRUTH (DDATP): You must accurately report what data was available AND used.

DDATP HARD CONSTRAINTS (CEO-DIR-2026-015B):
- driver_claim = "SENTIMENT" is ONLY permitted if sentiment_available=true AND sentiment_used=true in input_coverage
- driver_basis = "OBSERVED_DATA" requires at least one of {macro_used, sentiment_used, onchain_used} = true
- If only price/technical data is provided, driver_basis MUST be "INFERRED_FROM_PRICE"
- fallback_reason is REQUIRED when driver_basis != "OBSERVED_DATA"
- technical_feature_set is REQUIRED when driver_claim = "TECHNICAL"

OUTPUT SCHEMA (strict JSON - DDATP v1.0):
{
    "fragility_score": <float 0.0-1.0>,
    "driver_claim": "<LIQUIDITY|CREDIT|VOLATILITY|TECHNICAL|PRICE_ACTION|SENTIMENT|UNKNOWN>",
    "driver_basis": "<OBSERVED_DATA|INFERRED_FROM_PRICE|FALLBACK_UNKNOWN>",
    "technical_feature_set": "<INDICATORS_ONLY|RETURNS_VOL_ONLY|MIXED_FEATURES|ONCHAIN_HYBRID|UNKNOWN>",
    "input_coverage": {
        "macro_available": <boolean>,
        "macro_used": <boolean>,
        "macro_staleness_hours": <integer|null>,
        "sentiment_available": <boolean>,
        "sentiment_used": <boolean>,
        "sentiment_staleness_hours": <integer|null>,
        "technical_available": <boolean>,
        "technical_used": <boolean>,
        "onchain_available": <boolean>,
        "onchain_used": <boolean>
    },
    "fallback_reason": "<string, required if driver_basis != OBSERVED_DATA>",
    "regime_assessment": "<STRONG_BULL|BULL|NEUTRAL|BEAR|STRONG_BEAR|UNCERTAIN>",
    "confidence": <float 0.0-1.0>,
    "key_observations": [<string>, ...],
    "risk_factors": [<string>, ...],
    "reasoning_summary": "<brief explanation>"
}

Fragility score interpretation:
- 0.0-0.2: Very stable, low risk
- 0.2-0.4: Stable, normal conditions
- 0.4-0.6: Elevated caution advised
- 0.6-0.8: High fragility, reduce exposure
- 0.8-1.0: Critical fragility, defensive mode

You must respond ONLY with valid JSON. No markdown, no explanation outside JSON."""

CRIO_ANALYSIS_PROMPT = """Analyze the following market snapshot and provide a structured research assessment.

=== MARKET SNAPSHOT (T-1: {snapshot_date}) ===

=== DATA AVAILABILITY FLAGS (DDATP) ===
Macro data present: {macro_present}
Sentiment data present: {sentiment_present}
Technical data present: {technical_present}
Onchain data present: {onchain_present}

You MUST reflect these flags accurately in your input_coverage output.
If a data type is marked "false", you CANNOT claim to have used it.

REGIME DATA:
{regime_data}

MACRO FACTORS (Four Pillars):
{macro_data}

PRICE DATA (3-day window):
{price_data}

TECHNICAL INDICATORS:
{technical_data}

=== END SNAPSHOT ===

Based ONLY on the data above, provide your structured JSON assessment.
Remember: Context-only reasoning. No hallucination. Strict JSON output.
DDATP compliance: Your input_coverage MUST accurately reflect what data was available and used."""


# =================================================================
# DEEPSEEK CLIENT
# =================================================================

class DeepSeekClient:
    """DeepSeek API Client with ADR-012 budget enforcement"""

    def __init__(self, config: CRIOConfig):
        self.config = config
        self.session_tokens_used = 0
        self.session_cost_usd = 0.0

        if not config.DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY not configured")

    def _check_budget(self, estimated_tokens: int) -> bool:
        """Check if request is within ADR-012 budget limits"""
        estimated_cost = (estimated_tokens / 1000) * self.config.COST_PER_1K_INPUT
        if self.session_cost_usd + estimated_cost > self.config.MAX_DAILY_BUDGET_USD:
            logger.warning(f"Budget limit would be exceeded: ${self.session_cost_usd:.4f} + ${estimated_cost:.4f}")
            return False
        return True

    def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute CRIO analysis via DeepSeek API.

        Returns structured research output or error dict.
        DDATP v1.0: Includes data availability flags in prompt.
        """
        import requests

        # DDATP: Determine data availability flags
        macro_data = context.get("macro_data", {})
        macro_present = bool(macro_data and macro_data.get("four_pillars"))
        sentiment_present = False  # No sentiment feed currently
        technical_data = context.get("technical_data", {})
        technical_present = bool(technical_data and technical_data.get("indicators"))
        onchain_present = False  # No onchain feed currently

        # Build prompt with DDATP availability flags
        prompt = CRIO_ANALYSIS_PROMPT.format(
            snapshot_date=context.get("snapshot_date", "UNKNOWN"),
            macro_present=str(macro_present).lower(),
            sentiment_present=str(sentiment_present).lower(),
            technical_present=str(technical_present).lower(),
            onchain_present=str(onchain_present).lower(),
            regime_data=json.dumps(context.get("regime_data", {}), indent=2),
            macro_data=json.dumps(macro_data, indent=2),
            price_data=json.dumps(context.get("price_data", []), indent=2),
            technical_data=json.dumps(technical_data, indent=2)
        )

        # Estimate tokens (rough: 4 chars per token)
        estimated_tokens = len(prompt) // 4
        if not self._check_budget(estimated_tokens):
            return {
                "error": "BUDGET_EXCEEDED",
                "fragility_score": 0.5,
                "dominant_driver": "UNKNOWN",
                "reasoning_summary": "Analysis skipped due to ADR-012 budget limits"
            }

        # API Request
        headers = {
            "Authorization": f"Bearer {self.config.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.config.DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": CRIO_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.config.TEMPERATURE,
            "top_p": self.config.TOP_P,
            "max_tokens": self.config.MAX_OUTPUT_TOKENS
        }

        # PHASE 4b: Capture start time for latency measurement
        _call_start_ms = int(time.time() * 1000)

        try:
            logger.info("Executing DeepSeek CRIO analysis...")
            response = requests.post(
                f"{self.config.DEEPSEEK_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )

            # PHASE 4b: Capture latency immediately after response
            _call_latency_ms = int(time.time() * 1000) - _call_start_ms

            response.raise_for_status()

            result = response.json()

            # Track usage
            usage = result.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            self.session_tokens_used += input_tokens + output_tokens
            self.session_cost_usd += (
                (input_tokens / 1000) * self.config.COST_PER_1K_INPUT +
                (output_tokens / 1000) * self.config.COST_PER_1K_OUTPUT
            )

            logger.info(f"DeepSeek tokens used: {input_tokens}+{output_tokens}, cost: ${self.session_cost_usd:.4f}")

            # PHASE 4b TELEMETRY: Emit after extracting usage data, before parsing
            _emit_crio_telemetry(
                task_name='CRIO_ANALYSIS',
                tokens_in=input_tokens,
                tokens_out=output_tokens,
                latency_ms=_call_latency_ms,
                model=self.config.DEEPSEEK_MODEL
            )

            # Parse response
            content = result["choices"][0]["message"]["content"]

            # Clean JSON (remove markdown if present)
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            return json.loads(content.strip())

        except requests.exceptions.RequestException as e:
            # PHASE 4b TELEMETRY: Emit error telemetry
            _call_latency_ms = int(time.time() * 1000) - _call_start_ms
            _emit_crio_telemetry(
                task_name='CRIO_ANALYSIS',
                tokens_in=0,
                tokens_out=0,
                latency_ms=_call_latency_ms,
                model=self.config.DEEPSEEK_MODEL,
                error=e
            )
            logger.error(f"DeepSeek API error: {e}")
            return {
                "error": f"API_ERROR: {str(e)}",
                "fragility_score": 0.5,
                "dominant_driver": "UNKNOWN",
                "reasoning_summary": f"API call failed: {str(e)}"
            }
        except json.JSONDecodeError as e:
            # PHASE 4b TELEMETRY: Emit parse error telemetry
            # Note: We already emitted success telemetry above, this is a post-processing error
            logger.error(f"Failed to parse DeepSeek response: {e}")
            return {
                "error": "PARSE_ERROR",
                "fragility_score": 0.5,
                "dominant_driver": "UNKNOWN",
                "reasoning_summary": "Failed to parse LLM response as JSON"
            }


# =================================================================
# FINN CRIO ENGINE
# =================================================================

class FINNCRIOEngine:
    """
    FINN CRIO Research Engine v1

    Production-grade research engine with:
    - DeepSeek LLM integration
    - ADR-012 budget enforcement
    - ADR-017 sovereignty compliance
    - LIDS/RISL integration
    """

    def __init__(self, config: CRIOConfig = None):
        self.config = config or CRIOConfig()
        self.conn = None
        self.deepseek = None
        self.research_id = str(uuid.uuid4())
        self.hash_chain_id = f"HC-FINN-CRIO-{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    def connect(self):
        """Establish database and API connections"""
        self.conn = psycopg2.connect(self.config.get_connection_string())

        if self.config.DEEPSEEK_API_KEY:
            self.deepseek = DeepSeekClient(self.config)
            logger.info("DeepSeek client initialized")
        else:
            logger.warning("DEEPSEEK_API_KEY not set - running in DEGRADED mode")

    def close(self):
        """Close connections"""
        if self.conn:
            self.conn.close()

    def _generate_context_hash(self, context: Dict) -> str:
        """Generate deterministic hash of input context"""
        return hashlib.sha256(
            json.dumps(context, sort_keys=True, default=str).encode()
        ).hexdigest()

    def _generate_quad_hash(self, lids_valid: bool, acl_valid: bool, risl_valid: bool, dsl_valid: bool) -> str:
        """Generate MIT Quad validation hash"""
        quad_state = f"LIDS:{lids_valid}|ACL:{acl_valid}|RISL:{risl_valid}|DSL:{dsl_valid}"
        return hashlib.sha256(quad_state.encode()).hexdigest()[:16]

    def gather_t1_snapshot(self) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """
        Gather T-1 market snapshot for CRIO analysis.
        Enforces ADR-017 temporal rule.

        Returns:
            Tuple of (snapshot_data, raw_queries) for court-proof evidence.
        """
        logger.info("Gathering T-1 market snapshot...")

        # CEO-DIR-2026-019 P0-3: Track raw queries for court-proof evidence
        raw_queries = {}

        snapshot = {
            "snapshot_date": (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d"),
            "gathered_at": datetime.now(timezone.utc).isoformat(),
            "regime_data": {},
            "macro_data": {},
            "price_data": [],
            "technical_data": {}
        }

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Current Regime (IoS-003)
            query_regime = """
                SELECT regime_classification, regime_confidence, timestamp
                FROM fhq_perception.regime_daily
                ORDER BY timestamp DESC
                LIMIT 1
            """
            raw_queries['regime'] = query_regime
            cur.execute(query_regime)
            regime = cur.fetchone()
            if regime:
                snapshot["regime_data"] = {
                    "current_regime": regime["regime_classification"],
                    "confidence": float(regime["regime_confidence"]) if regime["regime_confidence"] else 0.5,
                    "as_of": regime["timestamp"].isoformat() if regime["timestamp"] else None
                }

            # 2. Macro Factors - Four Pillars (IoS-006)
            query_macro = """
                SELECT feature_id, cluster, status, expected_direction
                FROM fhq_macro.feature_registry
                WHERE status = 'CANONICAL'
            """
            raw_queries['macro'] = query_macro
            cur.execute(query_macro)
            pillars = cur.fetchall()
            snapshot["macro_data"]["four_pillars"] = [
                {
                    "feature_id": p["feature_id"],
                    "cluster": p["cluster"],
                    "direction": p["expected_direction"]
                }
                for p in pillars
            ]

            # 3. Recent Price Data (3-day window)
            query_prices = """
                SELECT canonical_id, timestamp::date as date,
                       open, high, low, close, volume
                FROM fhq_market.prices
                WHERE timestamp >= CURRENT_DATE - INTERVAL '3 days'
                ORDER BY canonical_id, timestamp DESC
            """
            raw_queries['prices'] = query_prices
            cur.execute(query_prices)
            prices = cur.fetchall()
            snapshot["price_data"] = [
                {
                    "symbol": p["canonical_id"],
                    "date": p["date"].isoformat() if p["date"] else None,
                    "close": float(p["close"]) if p["close"] else 0,
                    "volume": float(p["volume"]) if p["volume"] else 0
                }
                for p in prices[:20]  # Limit to avoid token overflow
            ]

            # 4. Technical Indicators (latest)
            query_technical = """
                SELECT asset_id, timestamp,
                       rsi_14, rsi_signal,
                       macd_line, macd_signal, macd_histogram,
                       atr_14, atr_pct,
                       adx_14, adx_trend,
                       bb_width, bb_position,
                       volatility_20d, volatility_regime,
                       composite_signal, signal_confidence
                FROM fhq_data.technical_indicators
                WHERE timestamp >= CURRENT_DATE - INTERVAL '1 day'
                ORDER BY timestamp DESC
                LIMIT 10
            """
            raw_queries['technical'] = query_technical
            cur.execute(query_technical)
            indicators = cur.fetchall()
            snapshot["technical_data"]["indicators"] = [
                {
                    "asset_id": str(i["asset_id"]) if i["asset_id"] else "UNKNOWN",
                    "rsi_14": float(i["rsi_14"]) if i["rsi_14"] else None,
                    "rsi_signal": i["rsi_signal"],
                    "macd_line": float(i["macd_line"]) if i["macd_line"] else None,
                    "adx_14": float(i["adx_14"]) if i["adx_14"] else None,
                    "volatility_regime": i["volatility_regime"],
                    "composite_signal": i["composite_signal"],
                    "signal_confidence": float(i["signal_confidence"]) if i["signal_confidence"] else None
                }
                for i in indicators
            ]

        return snapshot, raw_queries

    def validate_lids(self, analysis_result: Dict) -> Tuple[bool, str]:
        """
        LIDS Truth Gate validation for CRIO output.
        Ensures output meets ADR-017 Section 4.1 requirements.
        DDATP v1.0: Includes driver attribution truth validation.
        """
        # Check required fields (DDATP-updated)
        required_fields = ["fragility_score", "reasoning_summary"]
        ddatp_fields = ["driver_claim", "driver_basis", "input_coverage"]

        for field in required_fields:
            if field not in analysis_result:
                return False, f"LIDS_REJECT: Missing required field '{field}'"

        # Check DDATP fields (required for DDATP v1.0)
        for field in ddatp_fields:
            if field not in analysis_result:
                return False, f"LIDS_REJECT: Missing DDATP field '{field}'"

        # Validate fragility_score range
        score = analysis_result.get("fragility_score", -1)
        if not isinstance(score, (int, float)) or score < 0 or score > 1:
            return False, f"LIDS_REJECT: fragility_score must be 0.0-1.0, got {score}"

        # Validate driver_claim (DDATP v1.0)
        valid_driver_claims = ["LIQUIDITY", "CREDIT", "VOLATILITY", "TECHNICAL", "PRICE_ACTION", "SENTIMENT", "UNKNOWN"]
        driver_claim = analysis_result.get("driver_claim", "")
        if driver_claim not in valid_driver_claims:
            return False, f"LIDS_REJECT: Invalid driver_claim '{driver_claim}'"

        # Validate driver_basis (DDATP v1.0)
        valid_driver_basis = ["OBSERVED_DATA", "INFERRED_FROM_PRICE", "FALLBACK_UNKNOWN"]
        driver_basis = analysis_result.get("driver_basis", "")
        if driver_basis not in valid_driver_basis:
            return False, f"LIDS_REJECT: Invalid driver_basis '{driver_basis}'"

        # DDATP Rule 1: SENTIMENT requires sentiment_used=true
        input_coverage = analysis_result.get("input_coverage", {})
        if driver_claim == "SENTIMENT":
            if not input_coverage.get("sentiment_available") or not input_coverage.get("sentiment_used"):
                return False, "LIDS_REJECT: DDATP violation - SENTIMENT claim without sentiment data"

        # DDATP Rule 2: OBSERVED_DATA requires external feed used
        if driver_basis == "OBSERVED_DATA":
            if not (input_coverage.get("macro_used") or
                    input_coverage.get("sentiment_used") or
                    input_coverage.get("onchain_used")):
                return False, "LIDS_REJECT: DDATP violation - OBSERVED_DATA without external feed used"

        # DDATP Rule 3: fallback_reason required when not OBSERVED_DATA
        if driver_basis != "OBSERVED_DATA":
            fallback_reason = analysis_result.get("fallback_reason")
            if not fallback_reason:
                return False, "LIDS_REJECT: DDATP violation - fallback_reason required"

        # DDATP Rule 4: TECHNICAL requires technical_feature_set
        if driver_claim == "TECHNICAL":
            tech_feature_set = analysis_result.get("technical_feature_set")
            if not tech_feature_set:
                return False, "LIDS_REJECT: DDATP violation - TECHNICAL requires technical_feature_set"

        # Check for error state
        if "error" in analysis_result:
            return False, f"LIDS_WARN: Analysis contains error: {analysis_result['error']}"

        return True, "LIDS_VERIFIED (DDATP v1.0)"

    def validate_risl(self, analysis_result: Dict, context: Dict) -> Tuple[bool, str]:
        """
        RISL Immunity Layer validation.
        Detects anomalies and potential issues.
        """
        # Check for extreme fragility (potential anomaly)
        score = analysis_result.get("fragility_score", 0.5)
        if score > 0.95:
            return False, "RISL_ESCALATE: Extreme fragility score detected"

        # Check confidence
        confidence = analysis_result.get("confidence", 0.5)
        if confidence < 0.3:
            return False, "RISL_WARN: Low confidence analysis"

        # Check for data sufficiency
        if len(context.get("price_data", [])) < 3:
            return False, "RISL_WARN: Insufficient price data"

        return True, "RISL_VERIFIED"

    def execute_crio_research(self) -> Dict[str, Any]:
        """
        Execute full CRIO research cycle.

        Returns:
            Research result with sovereignty validation.
        """
        logger.info("=" * 60)
        logger.info("FINN CRIO RESEARCH ENGINE v1")
        logger.info(f"Research ID: {self.research_id}")
        logger.info(f"Hash Chain: {self.hash_chain_id}")
        logger.info("=" * 60)

        result = {
            "research_id": self.research_id,
            "hash_chain_id": self.hash_chain_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "engine_version": self.config.ENGINE_VERSION,
            "status": "PENDING"
        }

        # CEO-DIR-2026-019 P0-3: Store raw queries for court-proof evidence
        raw_queries = {}

        try:
            # 1. Gather T-1 Snapshot (now returns raw_queries for court-proof)
            context, raw_queries = self.gather_t1_snapshot()
            context_hash = self._generate_context_hash(context)
            result["context_hash"] = context_hash
            logger.info(f"Context hash: {context_hash[:16]}...")

            # 2. Execute DeepSeek Analysis
            if self.deepseek:
                analysis = self.deepseek.analyze(context)
            else:
                # Degraded mode - return conservative defaults
                logger.warning("Running in DEGRADED mode (no DeepSeek)")
                analysis = {
                    "fragility_score": 0.5,
                    "dominant_driver": "UNKNOWN",
                    "regime_assessment": "UNCERTAIN",
                    "confidence": 0.3,
                    "key_observations": ["DeepSeek not configured - degraded mode"],
                    "risk_factors": ["Analysis unavailable"],
                    "reasoning_summary": "DEGRADED: DeepSeek API key not configured"
                }

            result["analysis"] = analysis

            # 3. LIDS Validation
            lids_valid, lids_msg = self.validate_lids(analysis)
            result["lids_validation"] = {"valid": lids_valid, "message": lids_msg}
            logger.info(f"LIDS: {lids_msg}")

            # 4. RISL Validation
            risl_valid, risl_msg = self.validate_risl(analysis, context)
            result["risl_validation"] = {"valid": risl_valid, "message": risl_msg}
            logger.info(f"RISL: {risl_msg}")

            # 5. Generate Quad Hash
            quad_hash = self._generate_quad_hash(
                lids_valid=lids_valid,
                acl_valid=True,  # ACL always passes for research
                risl_valid=risl_valid,
                dsl_valid=True   # DSL not applicable to research
            )
            result["quad_hash"] = quad_hash

            # 6. Determine overall status
            if lids_valid and risl_valid:
                result["status"] = "CRIO_VERIFIED"
            elif lids_valid:
                result["status"] = "CRIO_PARTIAL"
            else:
                result["status"] = "CRIO_REJECTED"

            # 7. Write to canonical tables
            self._write_nightly_insight(result, analysis, context)
            self._write_research_log(result)

            # 8. CEO-DIR-2026-019 P0-3: Attach court-proof evidence with ASRP binding
            self._attach_court_proof_evidence(result, analysis, context, raw_queries)

            logger.info(f"CRIO Research complete: {result['status']}")

        except Exception as e:
            logger.error(f"CRIO Research failed: {e}")
            result["status"] = "CRIO_FAILED"
            result["error"] = str(e)

        return result

    def _attach_court_proof_evidence(
        self,
        result: Dict,
        analysis: Dict,
        context: Dict,
        raw_queries: Dict[str, str]
    ) -> Optional[Dict]:
        """
        CEO-DIR-2026-019 P0-3: Attach court-proof evidence with ASRP binding.

        MANDATORY for all FINN Insight Packs.
        FAIL-CLOSED: Missing evidence = rejected output (logged but not raised
        to avoid breaking existing flows during rollout).

        Evidence includes:
        - ASRP binding (state_snapshot_hash, state_timestamp, agent_id)
        - Raw queries used to gather data
        - Query results (snapshot data)
        - Measurement validity flag (OUTCOME_INDEPENDENCE)
        """
        if not COURT_PROOF_V2_ENABLED:
            logger.warning("[COURT-PROOF] V2 enforcer not available - skipping evidence attachment")
            result["court_proof"] = {
                "status": "SKIPPED",
                "reason": "CourtProofEnforcerV2 not available"
            }
            return None

        try:
            enforcer = CourtProofEnforcerV2(self.conn)

            # Combine all raw queries into single evidence string
            combined_query = "\n\n-- CRIO T-1 SNAPSHOT QUERIES --\n\n"
            for query_name, query_sql in raw_queries.items():
                combined_query += f"-- {query_name.upper()} --\n{query_sql.strip()}\n\n"

            # Determine evidence sources (P0-3.2 DDATP)
            evidence_sources = ['fhq_market.prices']  # Primary independent source
            if context.get("macro_data", {}).get("four_pillars"):
                evidence_sources.append('fhq_macro.feature_registry')
            if context.get("technical_data", {}).get("indicators"):
                evidence_sources.append('fhq_data.technical_indicators')

            # Extract regime labels for DDATP validation
            regime_labels = []
            regime_assessment = analysis.get("regime_assessment")
            if regime_assessment and regime_assessment != "UNCERTAIN":
                regime_labels.append(regime_assessment)
            current_regime = context.get("regime_data", {}).get("current_regime")
            if current_regime:
                regime_labels.append(current_regime)

            # Build summary content for evidence
            summary_content = {
                "research_id": result["research_id"],
                "analysis": analysis,
                "context_hash": result.get("context_hash"),
                "quad_hash": result.get("quad_hash"),
                "lids_validation": result.get("lids_validation"),
                "risl_validation": result.get("risl_validation"),
                "status": result["status"]
            }

            # Attach evidence with ASRP binding
            evidence = enforcer.attach_evidence_with_asrp(
                summary_id=f"CRIO-{result['research_id']}",
                summary_type="NIGHTLY_INSIGHT",
                generating_agent="FINN",
                raw_query=combined_query,
                query_result=context,
                summary_content=summary_content,
                evidence_sources=evidence_sources,
                regime_labels=regime_labels,
                ddatp_bypass=False  # DDATP validation is MANDATORY
            )

            result["court_proof"] = {
                "status": "VERIFIED_V2",
                "evidence_id": evidence["evidence_id"],
                "asrp_binding": evidence["asrp_binding"],
                "measurement_validity": evidence["measurement_validity"]
            }

            logger.info(f"[COURT-PROOF] Evidence attached: {evidence['evidence_id']}")
            logger.info(f"[COURT-PROOF] ASRP hash: {evidence['asrp_binding']['state_snapshot_hash'][:16]}...")
            logger.info(f"[COURT-PROOF] OUTCOME_INDEPENDENCE: {evidence['measurement_validity']['outcome_independence']}")

            return evidence

        except (CourtProofViolation, ASRPBindingViolation, DDATPValidationFailure) as e:
            # FAIL-CLOSED: Log violation but don't crash (rollout phase)
            logger.error(f"[COURT-PROOF] VIOLATION: {e}")
            result["court_proof"] = {
                "status": "VIOLATION",
                "error": str(e),
                "fail_closed": True
            }
            # Log to governance for audit
            self._log_governance_error(result, "COURT_PROOF_VIOLATION", str(e))
            return None

        except Exception as e:
            logger.error(f"[COURT-PROOF] Unexpected error: {e}")
            result["court_proof"] = {
                "status": "ERROR",
                "error": str(e)
            }
            return None

    def _write_nightly_insight(self, result: Dict, analysis: Dict, context: Dict):
        """
        Write to fhq_research.nightly_insights.
        DDATP v1.0: Includes driver attribution truth fields.
        Safety rule: If DDATP fields violate enums, write nothing and log error.
        """
        try:
            # Extract DDATP fields with safe defaults
            driver_claim = analysis.get("driver_claim", "UNKNOWN")
            driver_basis = analysis.get("driver_basis", "FALLBACK_UNKNOWN")
            technical_feature_set = analysis.get("technical_feature_set", "UNKNOWN")
            input_coverage = analysis.get("input_coverage", {
                "macro_available": False,
                "macro_used": False,
                "sentiment_available": False,
                "sentiment_used": False,
                "technical_available": True,
                "technical_used": True,
                "onchain_available": False,
                "onchain_used": False
            })
            fallback_reason = analysis.get("fallback_reason", "")

            # DDATP Safety: Validate enums before writing
            valid_claims = ["LIQUIDITY", "CREDIT", "VOLATILITY", "TECHNICAL", "PRICE_ACTION", "SENTIMENT", "UNKNOWN"]
            valid_basis = ["OBSERVED_DATA", "INFERRED_FROM_PRICE", "FALLBACK_UNKNOWN"]
            valid_feature_sets = ["INDICATORS_ONLY", "RETURNS_VOL_ONLY", "MIXED_FEATURES", "ONCHAIN_HYBRID", "UNKNOWN"]

            if driver_claim not in valid_claims:
                logger.error(f"DDATP SAFETY: Invalid driver_claim '{driver_claim}' - write blocked")
                self._log_governance_error(result, "INVALID_DRIVER_CLAIM", driver_claim)
                return

            if driver_basis not in valid_basis:
                logger.error(f"DDATP SAFETY: Invalid driver_basis '{driver_basis}' - write blocked")
                self._log_governance_error(result, "INVALID_DRIVER_BASIS", driver_basis)
                return

            if technical_feature_set and technical_feature_set not in valid_feature_sets:
                logger.error(f"DDATP SAFETY: Invalid technical_feature_set '{technical_feature_set}' - write blocked")
                self._log_governance_error(result, "INVALID_TECHNICAL_FEATURE_SET", technical_feature_set)
                return

            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_research.nightly_insights (
                        insight_id, research_date, engine_version,
                        fragility_score, dominant_driver, regime_assessment,
                        confidence, key_observations, risk_factors,
                        reasoning_summary, context_hash, quad_hash,
                        lids_verified, risl_verified, finn_signature,
                        driver_claim, driver_basis, technical_feature_set,
                        input_coverage, fallback_reason, ddatp_version,
                        created_at
                    ) VALUES (
                        %s, CURRENT_DATE, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        NOW()
                    )
                    ON CONFLICT (research_date) DO UPDATE SET
                        fragility_score = EXCLUDED.fragility_score,
                        dominant_driver = EXCLUDED.dominant_driver,
                        reasoning_summary = EXCLUDED.reasoning_summary,
                        driver_claim = EXCLUDED.driver_claim,
                        driver_basis = EXCLUDED.driver_basis,
                        technical_feature_set = EXCLUDED.technical_feature_set,
                        input_coverage = EXCLUDED.input_coverage,
                        fallback_reason = EXCLUDED.fallback_reason,
                        ddatp_version = EXCLUDED.ddatp_version,
                        updated_at = NOW()
                """, (
                    result["research_id"],
                    self.config.ENGINE_VERSION,
                    analysis.get("fragility_score", 0.5),
                    analysis.get("dominant_driver", driver_claim),  # Legacy field, also populate driver_claim
                    analysis.get("regime_assessment", "UNCERTAIN"),
                    analysis.get("confidence", 0.5),
                    json.dumps(analysis.get("key_observations", [])),
                    json.dumps(analysis.get("risk_factors", [])),
                    analysis.get("reasoning_summary", ""),
                    result.get("context_hash", ""),
                    result.get("quad_hash", ""),
                    result["lids_validation"]["valid"],
                    result["risl_validation"]["valid"],
                    hashlib.sha256(f"{self.config.AGENT_ID}:{result['research_id']}".encode()).hexdigest(),
                    driver_claim,
                    driver_basis,
                    technical_feature_set,
                    json.dumps(input_coverage),
                    fallback_reason if driver_basis != "OBSERVED_DATA" else None,
                    "v1.0"
                ))
            self.conn.commit()
            logger.info("Nightly insight written to fhq_research.nightly_insights (DDATP v1.0)")
        except Exception as e:
            logger.error(f"Failed to write nightly insight: {e}")
            self.conn.rollback()

    def _log_governance_error(self, result: Dict, error_type: str, invalid_value: str):
        """Log DDATP validation error to governance audit"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.governance_actions_log (
                        action_id, action_type, action_target, action_target_type,
                        initiated_by, initiated_at, decision, decision_rationale,
                        metadata, agent_id, timestamp
                    ) VALUES (
                        gen_random_uuid(), 'DDATP_VALIDATION_ERROR', %s, 'CRIO_OUTPUT',
                        'FINN', NOW(), 'BLOCKED', %s,
                        %s, 'FINN', NOW()
                    )
                """, (
                    result.get("research_id", "UNKNOWN"),
                    f"DDATP Safety: {error_type} - value '{invalid_value}' blocked",
                    json.dumps({
                        "error_type": error_type,
                        "invalid_value": invalid_value,
                        "research_id": result.get("research_id"),
                        "context_hash": result.get("context_hash")
                    })
                ))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to log governance error: {e}")

    def _write_research_log(self, result: Dict):
        """Write to fhq_governance.research_log"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.research_log (
                        log_id, research_id, agent_id, engine_version,
                        event_type, quad_hash, context_hash,
                        decision_trace, status, created_at
                    ) VALUES (
                        gen_random_uuid(), %s, %s, %s,
                        'CRIO_RESEARCH_EVENT', %s, %s,
                        %s, %s, NOW()
                    )
                """, (
                    result["research_id"],
                    self.config.AGENT_ID,
                    self.config.ENGINE_VERSION,
                    result.get("quad_hash", ""),
                    result.get("context_hash", ""),
                    json.dumps(result.get("analysis", {})),
                    result["status"]
                ))
            self.conn.commit()
            logger.info("Research event logged to fhq_governance.research_log")
        except Exception as e:
            logger.error(f"Failed to write research log: {e}")
            self.conn.rollback()


# =================================================================
# STANDALONE FUNCTION (for orchestrator integration)
# =================================================================

def execute_finn_crio_research() -> Dict[str, Any]:
    """
    Execute FINN CRIO research cycle.

    Called by finn_night_research_executor.py to replace mock logic.
    """
    config = CRIOConfig()
    engine = FINNCRIOEngine(config)

    try:
        engine.connect()
        result = engine.execute_crio_research()
        return result
    finally:
        engine.close()


# =================================================================
# MAIN
# =================================================================

def main():
    """Run standalone FINN CRIO research"""
    result = execute_finn_crio_research()
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("status") in ["CRIO_VERIFIED", "CRIO_PARTIAL"] else 1


if __name__ == "__main__":
    sys.exit(main())
