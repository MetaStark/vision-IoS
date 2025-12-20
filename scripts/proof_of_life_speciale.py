#!/usr/bin/env python3
"""
CEO DIRECTIVE: PROOF OF LIFE / FIRST THOUGHTS
Execute SPECIALE model call and capture Chain of Thought
"""

import os
import sys
import json
import httpx
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "03_FUNCTIONS"))

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

def execute_speciale_reasoning(api_key: str) -> dict:
    """
    Execute SPECIALE reasoning call.
    Returns raw Chain of Thought + structured response.
    """

    # PROOF OF LIFE prompt
    system_prompt = """You are a causal inference engine for financial markets within FjordHQ's autonomous trading system.
Your task is to analyze macro liquidity conditions and their correlation with crypto market regimes.

REGIME CONTEXT: Current global market conditions as of December 2025.

Use rigorous statistical reasoning. Cite evidence for causal relationships.
Structure your analysis as a chain of reasoning steps."""

    user_prompt = """CEO DIRECTIVE: PROOF OF LIFE / FIRST THOUGHTS

INSTRUCTION: Assess current global liquidity & crypto regime correlation

Analyze:
1. Current Federal Reserve policy stance and liquidity conditions
2. Global central bank coordination (ECB, BOJ, PBOC)
3. Correlation between M2 money supply changes and BTC/ETH price action
4. Current regime classification: RISK-ON, RISK-OFF, or TRANSITIONAL
5. Key causal edges in the liquidity → crypto price transmission mechanism

Provide your chain of reasoning step by step, then conclude with a structured assessment."""

    print("\n" + "="*60)
    print("EXECUTING SPECIALE REASONING CALL")
    print("="*60)
    print(f"Model: deepseek-reasoner (V3.2-Speciale)")
    print(f"Base URL: {SPECIALE_BASE_URL}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("="*60 + "\n")

    # Make API call
    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            f"{SPECIALE_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-reasoner",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
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
                "status_code": response.status_code
            }

        result = response.json()

        # Extract response details
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = result.get("usage", {})
        model = result.get("model", "unknown")

        # Check for reasoning_content (Thinking Mode)
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
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


def format_json_from_reasoning(raw_reasoning: str, api_key: str) -> dict:
    """
    Stage 2: Use standard deepseek-chat to format reasoning into JSON.
    This demonstrates the Parser Wrapper pattern.
    """

    print("\n" + "="*60)
    print("STAGE 2: PARSER WRAPPER (deepseek-chat)")
    print("="*60)

    format_prompt = f"""Convert the following reasoning output into valid JSON.

REASONING OUTPUT:
{raw_reasoning[:3000]}  # Truncate for efficiency

REQUIRED JSON SCHEMA:
{{
    "regime_assessment": "string (RISK-ON | RISK-OFF | TRANSITIONAL)",
    "liquidity_score": "float (0-1, where 1 = maximum liquidity)",
    "crypto_correlation": "float (-1 to 1)",
    "key_causal_edges": [
        {{
            "source": "string",
            "target": "string",
            "strength": "float (0-1)"
        }}
    ],
    "confidence_score": "float (0-1)",
    "summary": "string (one sentence)"
}}

Return ONLY valid JSON matching the schema. No explanations."""

    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            "https://api.deepseek.com/chat/completions",  # Standard endpoint
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": format_prompt}],
                "max_tokens": 1024,
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            }
        )

        if response.status_code != 200:
            print(f"[ERROR] Parser wrapper failed: {response.text}")
            return None

        result = response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "{}")

        try:
            parsed = json.loads(content)
            print("[OK] Parser Wrapper: JSON extracted successfully")
            return parsed
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON parse failed: {e}")
            return None


def main():
    """Main execution"""

    print("\n" + "="*60)
    print("CEO DIRECTIVE: PROOF OF LIFE / FIRST THOUGHTS")
    print("="*60)
    print(f"Execution Time: {datetime.now(timezone.utc).isoformat()}")
    print("="*60)

    # Check API key
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("[ERROR] DEEPSEEK_API_KEY not set")
        print("\nTo set the API key, run:")
        print('  $env:DEEPSEEK_API_KEY = "your-api-key"')
        return

    print(f"[OK] API Key: {api_key[:10]}...{api_key[-4:]}")

    # Check expiry
    try:
        check_speciale_expiry()
    except Exception as e:
        print(f"[CRITICAL] {e}")
        return

    # Execute SPECIALE reasoning
    result = execute_speciale_reasoning(api_key)

    if not result["success"]:
        print("\n[FAILED] SPECIALE call unsuccessful")
        return

    # Display raw Chain of Thought
    print("\n" + "="*60)
    print("RAW CHAIN OF THOUGHT (FIRST THOUGHTS)")
    print("="*60)

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

    # Stage 2: Parser Wrapper
    structured = format_json_from_reasoning(result["content"], api_key)

    if structured:
        print("\n" + "="*60)
        print("STRUCTURED OUTPUT (Parser Wrapper Result)")
        print("="*60)
        print(json.dumps(structured, indent=2))

    # Final report
    print("\n" + "="*60)
    print("PROOF OF LIFE VERIFICATION")
    print("="*60)
    print(f"  API Call Success: {'YES' if result['success'] else 'NO'}")
    print(f"  Model Used: {result['model']}")
    print(f"  Thinking Mode (CoT): {'YES' if result['thinking_mode'] else 'NO (inline)'}")
    print(f"  Parser Wrapper: {'SUCCESS' if structured else 'FAILED'}")
    print(f"  Token Usage: {result['usage']}")
    print("="*60)

    # Save evidence
    evidence = {
        "evidence_type": "PROOF_OF_LIFE",
        "evidence_id": f"POL-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
        "timestamp": result["timestamp"],
        "speciale_result": {
            "success": result["success"],
            "model": result["model"],
            "thinking_mode": result["thinking_mode"],
            "token_usage": result["usage"],
            "reasoning_sample": (result["reasoning_content"] or result["content"])[:500]
        },
        "parser_wrapper_result": structured,
        "verification": {
            "api_call_success": result["success"],
            "thinking_mode_active": result["thinking_mode"],
            "parser_wrapper_success": structured is not None
        }
    }

    evidence_path = Path(__file__).parent.parent / "05_GOVERNANCE" / "PHASE3" / f"PROOF_OF_LIFE_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    with open(evidence_path, "w") as f:
        json.dump(evidence, f, indent=2)
    print(f"\n[EVIDENCE] Saved to: {evidence_path}")


if __name__ == "__main__":
    main()
