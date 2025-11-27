#!/usr/bin/env python3
"""Quick test to verify ANTHROPIC_API_KEY is loaded correctly"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
load_dotenv(Path(__file__).parent / ".env")

# Get the key
key = os.getenv('ANTHROPIC_API_KEY')

if key:
    print(f"✔ Key loaded: {key[:20]}... (length: {len(key)})")
    print(f"  Format check: {'✔ Valid' if key.startswith('sk-ant-') else '❌ Invalid format'}")

    # Try to use it
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=key)
        msg = client.messages.create(
            model='claude-3-haiku-20240307',  # Cheapest model - saves money!
            max_tokens=10,
            messages=[{'role': 'user', 'content': 'Hi'}]
        )
        print(f"✔ API test successful!")
        print(f"  Model: claude-3-haiku-20240307 (cost-optimized)")
        print(f"  Response: {msg.content[0].text}")
    except Exception as e:
        print(f"❌ API test failed: {e}")
else:
    print("❌ ANTHROPIC_API_KEY not found in .env")
