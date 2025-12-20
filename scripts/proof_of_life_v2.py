#!/usr/bin/env python3
"""
CEO DIRECTIVE: PROOF OF LIFE V2 - WITH CONTEXT INJECTION
=========================================================
CI-20251209: Mandatory Context Injection

Success Criteria:
- DeepSeek cites the provided BTC price
- DeepSeek references the provided regime
- DeepSeek no longer refers to training cut-off
- First Thoughts begins with "Given the provided context..."
"""

import os
import sys
import json
import httpx
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "03_FUNCTIONS"))

from context_injection_layer import (
    ContextRetriever,
    SystemContext,
    build_contextualized_prompt,
    context_minimum_viability_check,
    ContextViabilityError
)

# Configuration
SPECIALE_BASE_URL = "https://api.deepseek.com/v3.2_speciale_expires_on_20251215"
SPECIALE_EXPIRY = datetime(2025, 12, 15, 15, 59, 0, tzinfo=timezone.utc)


def check_speciale_expiry():
    """Verify Speciale is not expired"""
    current = datetime.now(timezone.utc)
    if current > SPECIALE_EXPIRY:
        raise Exception(f"SPECIALE EXPIRED at {SPECIALE_EXPIRY}")
    days_left = (SPECIALE_EXPIRY - current).days
    hours_left = ((SPECIALE_EXPIRY - current).seconds // 3600)
    print(f"[OK] Speciale valid for {days_left}d {hours_left}h")
    return True


def execute_contextualized_reasoning(api_key: str) -> dict:
    """
    Execute SPECIALE reasoning with mandatory context injection.
    """

    # Base prompts (will be enhanced with context)
    base_system_prompt = """You are a causal inference engine for financial markets within FjordHQ's autonomous trading system.

CRITICAL INSTRUCTION:
- You MUST use the SYSTEM CONTEXT provided below for ALL reasoning
- Reference specific prices, regime, and events from the context
- Do NOT use your training data for current market conditions
- Begin your response with "Given the provided context..."
"""

    base_user_prompt = """CEO DIRECTIVE: PROOF OF LIFE / FIRST THOUGHTS (V2 - Context Aware)

INSTRUCTION: Assess current global liquidity & crypto regime correlation

Based ONLY on the provided SYSTEM CONTEXT, analyze:
1. The current price levels and what they indicate
2. The current regime classification and its implications
3. Any recent events that affect the analysis
4. Key causal relationships you can identify from the data

Reference specific values from the SYSTEM CONTEXT in your response."""

    print("\n" + "=" * 60)
    print("CI-20251209: RETRIEVING SYSTEM CONTEXT")
    print("=" * 60)

    # Build contextualized prompt
    try:
        final_system, final_user, context = build_contextualized_prompt(
            user_prompt=base_user_prompt,
            system_prompt=base_system_prompt,
            require_viable_context=False  # Allow partial context for testing
        )
    except Exception as e:
        print(f"[ERROR] Context retrieval failed: {e}")
        return {"success": False, "error": str(e)}

    # Check viability
    is_viable, missing = context_minimum_viability_check(context)
    print(f"\n[CONTEXT] Viability: {'PASS' if is_viable else 'PARTIAL'}")
    print(f"[CONTEXT] Hash: {context.context_hash}")
    print(f"[CONTEXT] Fields: {context.context_fields_present}")
    if missing:
        print(f"[CONTEXT] Missing: {missing}")

    # Show context block
    print("\n" + context.to_prompt_block())

    print("\n" + "=" * 60)
    print("EXECUTING CONTEXTUALIZED SPECIALE CALL")
    print("=" * 60)
    print(f"Model: deepseek-reasoner (V3.2-Speciale)")
    print(f"Base URL: {SPECIALE_BASE_URL}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60 + "\n")

    # Make API call with context-injected prompts
    with httpx.Client(timeout=180.0) as client:
        response = client.post(
            f"{SPECIALE_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-reasoner",
                "messages": [
                    {"role": "system", "content": final_system},
                    {"role": "user", "content": final_user}
                ],
                "max_tokens": 4096,
                "temperature": 0.3
            }
        )

        print(f"[API] Status Code: {response.status_code}")

        if response.status_code != 200:
            print(f"[ERROR] API call failed: {response.text}")
            return {
                "success": False,
                "error": response.text,
                "status_code": response.status_code,
                "context": context
            }

        result = response.json()

        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = result.get("usage", {})
        model = result.get("model", "unknown")
        reasoning_content = result.get("choices", [{}])[0].get("message", {}).get("reasoning_content", None)

        print(f"[API] Model Used: {model}")
        print(f"[API] Tokens - Prompt: {usage.get('prompt_tokens', 'N/A')}, Completion: {usage.get('completion_tokens', 'N/A')}")
        print(f"[API] Thinking Mode: {'YES' if reasoning_content else 'NO (inline reasoning)'}")

        return {
            "success": True,
            "model": model,
            "thinking_mode": reasoning_content is not None,
            "reasoning_content": reasoning_content,
            "content": content,
            "usage": usage,
            "context": context,
            "context_viable": is_viable,
            "context_missing": missing,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


def verify_context_awareness(content: str, context: SystemContext) -> dict:
    """
    Verify that the response demonstrates context awareness.

    Success Criteria:
    - Begins with "Given the provided context..."
    - References provided prices
    - References provided regime
    - Does NOT mention training cut-off
    """
    checks = {
        "begins_with_context": content.lower().startswith("given the provided context"),
        "references_btc_price": False,
        "references_regime": False,
        "no_training_cutoff": "training" not in content.lower() and "cut-off" not in content.lower() and "cutoff" not in content.lower(),
        "no_knowledge_limitation": "knowledge" not in content.lower() or "as of" not in content.lower()
    }

    # Check for price references
    if context.market_state.btc_price:
        btc_str = f"{context.market_state.btc_price:,.0f}"
        checks["references_btc_price"] = btc_str in content or str(int(context.market_state.btc_price)) in content

    # Check for regime references
    if context.market_state.current_regime:
        checks["references_regime"] = context.market_state.current_regime.upper() in content.upper()

    passed = sum(1 for v in checks.values() if v)
    total = len(checks)

    return {
        "checks": checks,
        "passed": passed,
        "total": total,
        "success": passed >= 3  # At least 3 of 5 checks must pass
    }


def main():
    """Main execution"""

    print("\n" + "=" * 60)
    print("CEO DIRECTIVE: PROOF OF LIFE V2 (CI-20251209)")
    print("WITH MANDATORY CONTEXT INJECTION")
    print("=" * 60)
    print(f"Execution Time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    # Check API key
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("[ERROR] DEEPSEEK_API_KEY not set")
        return

    print(f"[OK] API Key: {api_key[:10]}...{api_key[-4:]}")

    # Check expiry
    try:
        check_speciale_expiry()
    except Exception as e:
        print(f"[CRITICAL] {e}")
        return

    # Execute contextualized reasoning
    result = execute_contextualized_reasoning(api_key)

    if not result["success"]:
        print("\n[FAILED] SPECIALE call unsuccessful")
        return

    # Display response
    print("\n" + "=" * 60)
    print("CONTEXTUALIZED RESPONSE")
    print("=" * 60)

    if result["thinking_mode"] and result["reasoning_content"]:
        print("\n[THINKING MODE CONTENT]:")
        print("-" * 40)
        print(result["reasoning_content"][:2000])
        if len(result["reasoning_content"]) > 2000:
            print(f"\n... (truncated, total {len(result['reasoning_content'])} chars)")

    print("\n[FINAL RESPONSE]:")
    print("-" * 40)
    print(result["content"][:3000])
    if len(result["content"]) > 3000:
        print(f"\n... (truncated, total {len(result['content'])} chars)")

    # Verify context awareness
    print("\n" + "=" * 60)
    print("CONTEXT AWARENESS VERIFICATION")
    print("=" * 60)

    verification = verify_context_awareness(result["content"], result["context"])

    for check, passed in verification["checks"].items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {check}")

    print(f"\n  Score: {verification['passed']}/{verification['total']}")
    print(f"  Overall: {'SUCCESS' if verification['success'] else 'NEEDS IMPROVEMENT'}")

    # Final report
    print("\n" + "=" * 60)
    print("PROOF OF LIFE V2 VERIFICATION")
    print("=" * 60)
    print(f"  API Call Success: {'YES' if result['success'] else 'NO'}")
    print(f"  Model Used: {result['model']}")
    print(f"  Thinking Mode (CoT): {'YES' if result['thinking_mode'] else 'NO'}")
    print(f"  Context Injected: YES")
    print(f"  Context Hash: {result['context'].context_hash}")
    print(f"  Context Viable: {'YES' if result['context_viable'] else 'PARTIAL'}")
    print(f"  Context Awareness: {verification['passed']}/{verification['total']} checks")
    print(f"  Token Usage: {result['usage']}")
    print("=" * 60)

    # Save evidence
    evidence = {
        "evidence_type": "PROOF_OF_LIFE_V2",
        "evidence_id": f"POL2-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
        "directive": "CI-20251209",
        "timestamp": result["timestamp"],
        "context_injection": {
            "enabled": True,
            "hash": result["context"].context_hash,
            "fields_present": result["context"].context_fields_present,
            "viable": result["context_viable"],
            "missing": result["context_missing"]
        },
        "speciale_result": {
            "success": result["success"],
            "model": result["model"],
            "thinking_mode": result["thinking_mode"],
            "token_usage": result["usage"]
        },
        "context_awareness_verification": verification,
        "response_sample": result["content"][:1000]
    }

    evidence_path = Path(__file__).parent.parent / "05_GOVERNANCE" / "PHASE3" / f"PROOF_OF_LIFE_V2_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    with open(evidence_path, "w") as f:
        json.dump(evidence, f, indent=2, default=str)
    print(f"\n[EVIDENCE] Saved to: {evidence_path}")


if __name__ == "__main__":
    main()
