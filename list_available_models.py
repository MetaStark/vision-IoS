#!/usr/bin/env python3
"""
List available Claude models for your API key
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
ENV_FILE = Path(__file__).parent / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

api_key = os.getenv('ANTHROPIC_API_KEY')

if not api_key:
    print("❌ ANTHROPIC_API_KEY not set")
    exit(1)

print(f"Testing models with API key: {api_key[:20]}...")
print()

from anthropic import Anthropic

client = Anthropic(api_key=api_key)

# List of models to test
models_to_test = [
    'claude-3-5-sonnet-20241022',      # Sonnet 3.5 (Oct 2024)
    'claude-3-5-sonnet-latest',        # Latest Sonnet 3.5
    'claude-3-5-sonnet-20240620',      # Sonnet 3.5 (June 2024)
    'claude-3-opus-20240229',          # Opus 3.0
    'claude-3-sonnet-20240229',        # Sonnet 3.0
    'claude-3-haiku-20240307',         # Haiku 3.0
]

print("Testing model availability:")
print("=" * 70)

available_models = []

for model in models_to_test:
    try:
        # Try a minimal API call
        msg = client.messages.create(
            model=model,
            max_tokens=5,
            messages=[{'role': 'user', 'content': 'Hi'}]
        )
        print(f"✔ {model}")
        available_models.append(model)
    except Exception as e:
        if 'not_found_error' in str(e):
            print(f"❌ {model} - NOT AVAILABLE")
        elif 'rate_limit' in str(e):
            print(f"⚠️  {model} - RATE LIMITED (but exists)")
            available_models.append(model)
        else:
            print(f"⚠️  {model} - {str(e)[:60]}")

print()
print("=" * 70)

if available_models:
    print(f"✅ Available models ({len(available_models)}):")
    for model in available_models:
        print(f"   - {model}")
    print()
    print(f"💡 Recommended: {available_models[0]}")
else:
    print("❌ No models available. Check your API key permissions.")
