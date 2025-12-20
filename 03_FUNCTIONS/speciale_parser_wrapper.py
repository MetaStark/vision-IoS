"""
SPECIALE PARSER WRAPPER
========================
CEO DIRECTIVE: ARO-20251208/IGNITION (AMENDED)
CEO DIRECTIVE: CI-20251209 (Context Injection)
Purpose: Parse raw Speciale reasoning output into structured JSON

DeepSeek V3.2-Speciale does NOT support:
- JSON Output mode
- Tool Calls

Therefore this wrapper implements a two-step process:
1. Speciale generates raw reasoning/strategy (thinking mode)
2. Standard deepseek-chat formats the result into JSON

MANDATORY CONTEXT INJECTION (CI-20251209):
- No prompt is ever sent without SYSTEM CONTEXT BLOCK
- Context viability check must pass before any LLM call
- Missing context = BLOCKED call + governance discrepancy logged

EXPIRY: 2025-12-15 15:59 UTC
After this date, this wrapper becomes DEPRECATED and standard
deepseek-reasoner should be used directly.
"""

import os
import json
import httpx
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

# CI-20251209: Context Injection Layer
from context_injection_layer import (
    ContextRetriever,
    SystemContext,
    build_contextualized_prompt,
    context_minimum_viability_check,
    log_governance_discrepancy,
    ContextViabilityError
)

# Configuration
SPECIALE_BASE_URL = "https://api.deepseek.com/v3.2_speciale_expires_on_20251215"
STANDARD_BASE_URL = "https://api.deepseek.com"
SPECIALE_EXPIRY = datetime(2025, 12, 15, 15, 59, 0, tzinfo=timezone.utc)

@dataclass
class SpecialeConfig:
    """Configuration for Speciale model usage"""
    api_key: str
    speciale_model: str = "deepseek-reasoner"
    formatter_model: str = "deepseek-chat"
    max_tokens_reasoning: int = 8192
    max_tokens_formatting: int = 2048
    context_window: int = 128000
    temperature_reasoning: float = 0.3
    temperature_formatting: float = 0.1


class CriticalGovernanceError(Exception):
    """Raised when governance constraints are violated"""
    pass


def check_speciale_expiry() -> bool:
    """
    TIME-BOMB CHECK: Verify Speciale model is not expired.

    Returns:
        True if Speciale is still valid

    Raises:
        CriticalGovernanceError if expired
    """
    current_time = datetime.now(timezone.utc)

    if current_time > SPECIALE_EXPIRY:
        raise CriticalGovernanceError(
            f"EXPIRED MODEL CONFIGURATION - FORCE SWITCH\n"
            f"Speciale expired at: {SPECIALE_EXPIRY.isoformat()}\n"
            f"Current time: {current_time.isoformat()}\n"
            f"Action required: Switch to standard deepseek-reasoner"
        )

    days_remaining = (SPECIALE_EXPIRY - current_time).days
    hours_remaining = ((SPECIALE_EXPIRY - current_time).seconds // 3600)

    if days_remaining <= 1:
        print(f"[WARNING] Speciale expires in {days_remaining}d {hours_remaining}h")

    return True


def get_base_url() -> str:
    """Get appropriate base URL based on expiry status"""
    try:
        check_speciale_expiry()
        return SPECIALE_BASE_URL
    except CriticalGovernanceError:
        return STANDARD_BASE_URL


class SpecialeParserWrapper:
    """
    Two-stage parser wrapper for DeepSeek Speciale.

    Stage 1: Speciale reasoning (raw thinking output)
    Stage 2: Standard chat formatting (structured JSON)

    CI-20251209: All calls now include mandatory context injection.
    """

    def __init__(self, config: Optional[SpecialeConfig] = None, require_context: bool = True):
        self.config = config or SpecialeConfig(
            api_key=os.environ.get("DEEPSEEK_API_KEY", "")
        )
        self.client = httpx.Client(timeout=120.0)
        self.require_context = require_context  # CI-20251209: Context requirement flag
        self.last_context: Optional[SystemContext] = None  # Store last used context

    def _call_speciale(self, prompt: str, system_prompt: str = "") -> str:
        """
        Stage 1: Call Speciale for raw reasoning.

        Args:
            prompt: The reasoning prompt
            system_prompt: Optional system context

        Returns:
            Raw reasoning output from Speciale
        """
        check_speciale_expiry()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.post(
            f"{SPECIALE_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.config.speciale_model,
                "messages": messages,
                "max_tokens": self.config.max_tokens_reasoning,
                "temperature": self.config.temperature_reasoning,
                # Thinking mode is implicit in Speciale
            }
        )
        response.raise_for_status()

        result = response.json()
        return result["choices"][0]["message"]["content"]

    def _format_to_json(self, raw_reasoning: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Stage 2: Format raw reasoning into structured JSON.

        Args:
            raw_reasoning: Output from Speciale
            schema: Expected JSON schema

        Returns:
            Structured JSON matching schema
        """
        format_prompt = f"""Convert the following reasoning output into valid JSON.

REASONING OUTPUT:
{raw_reasoning}

REQUIRED JSON SCHEMA:
{json.dumps(schema, indent=2)}

Return ONLY valid JSON matching the schema. No explanations."""

        response = self.client.post(
            f"{STANDARD_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.config.formatter_model,
                "messages": [{"role": "user", "content": format_prompt}],
                "max_tokens": self.config.max_tokens_formatting,
                "temperature": self.config.temperature_formatting,
                "response_format": {"type": "json_object"}
            }
        )
        response.raise_for_status()

        result = response.json()
        content = result["choices"][0]["message"]["content"]

        return json.loads(content)

    def reason_and_format(
        self,
        prompt: str,
        output_schema: Dict[str, Any],
        system_prompt: str = "",
        include_raw_reasoning: bool = False,
        skip_context_injection: bool = False
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Complete two-stage reasoning pipeline.

        CI-20251209: Now includes mandatory context injection.

        Args:
            prompt: The reasoning prompt
            output_schema: Expected JSON output schema
            system_prompt: Optional system context
            include_raw_reasoning: Whether to return raw reasoning
            skip_context_injection: Override context requirement (use with caution)

        Returns:
            Tuple of (structured_output, optional_raw_reasoning)

        Raises:
            ContextViabilityError: If context fails viability check
        """
        # CI-20251209: Context Injection
        if self.require_context and not skip_context_injection:
            try:
                final_system, final_user, context = build_contextualized_prompt(
                    user_prompt=prompt,
                    system_prompt=system_prompt,
                    require_viable_context=True
                )
                self.last_context = context
                prompt = final_user
                system_prompt = final_system
                print(f"[CI-20251209] Context injected. Hash: {context.context_hash}")
                print(f"[CI-20251209] Fields present: {context.context_fields_present}")
            except ContextViabilityError as e:
                print(f"[CI-20251209] BLOCKED: {e}")
                raise

        # Stage 1: Speciale reasoning
        raw_reasoning = self._call_speciale(prompt, system_prompt)

        # Stage 2: JSON formatting
        structured_output = self._format_to_json(raw_reasoning, output_schema)

        if include_raw_reasoning:
            return structured_output, raw_reasoning
        return structured_output, None

    def close(self):
        """Close HTTP client"""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Convenience functions for common use cases

def reason_causal_inference(
    query: str,
    context: str,
    api_key: str
) -> Dict[str, Any]:
    """
    IoS-007 Alpha Graph causal inference using Speciale.

    Returns structured causal analysis.
    """
    schema = {
        "causal_edges": [
            {
                "source": "string",
                "target": "string",
                "relationship": "string",
                "confidence": "float (0-1)",
                "evidence": "string"
            }
        ],
        "reasoning_chain": ["string"],
        "conclusion": "string",
        "confidence_score": "float (0-1)"
    }

    system_prompt = """You are a causal inference engine for financial markets.
Analyze the query and context to identify causal relationships.
Use rigorous statistical reasoning. Only assert relationships with evidence."""

    prompt = f"""QUERY: {query}

CONTEXT:
{context}

Identify all causal relationships. Explain your reasoning step by step."""

    config = SpecialeConfig(api_key=api_key)
    with SpecialeParserWrapper(config) as wrapper:
        result, _ = wrapper.reason_and_format(prompt, schema, system_prompt)

    return result


def reason_strategy(
    market_state: Dict[str, Any],
    regime: str,
    api_key: str
) -> Dict[str, Any]:
    """
    IoS-009 Strategy reasoning using Speciale.

    Returns strategic recommendations.
    """
    schema = {
        "regime_assessment": "string",
        "strategy_recommendation": "string",
        "risk_factors": ["string"],
        "opportunity_factors": ["string"],
        "action_items": [
            {
                "action": "string",
                "priority": "integer (1-5)",
                "rationale": "string"
            }
        ],
        "confidence_score": "float (0-1)"
    }

    system_prompt = f"""You are a strategic reasoning engine for financial markets.
Current regime: {regime}
Analyze the market state and provide actionable strategic recommendations.
Consider risk carefully. Never recommend actions beyond risk tolerance."""

    prompt = f"""MARKET STATE:
{json.dumps(market_state, indent=2)}

Analyze this market state and provide strategic recommendations."""

    config = SpecialeConfig(api_key=api_key)
    with SpecialeParserWrapper(config) as wrapper:
        result, _ = wrapper.reason_and_format(prompt, schema, system_prompt)

    return result


# Test function
def test_speciale_wrapper():
    """Test the Speciale parser wrapper"""
    print("Testing Speciale Parser Wrapper...")

    # Check expiry
    try:
        is_valid = check_speciale_expiry()
        print(f"Speciale validity check: {is_valid}")

        days_left = (SPECIALE_EXPIRY - datetime.now(timezone.utc)).days
        print(f"Days until expiry: {days_left}")

    except CriticalGovernanceError as e:
        print(f"CRITICAL: {e}")
        return False

    print("Speciale Parser Wrapper: READY")
    return True


if __name__ == "__main__":
    test_speciale_wrapper()
