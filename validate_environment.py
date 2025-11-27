#!/usr/bin/env python3
"""
Vision-IoS Environment Validation Script
Validates connectivity to all required services
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env
ENV_FILE = Path(__file__).parent / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
    print(f"✔ .env loaded from: {ENV_FILE}\n")
else:
    print(f"❌ ERROR: .env not found at {ENV_FILE}")
    print(f"   Copy .env.template to .env and fill in your API keys")
    sys.exit(1)


def validate_database():
    """Validate PostgreSQL connection"""
    print("Testing PostgreSQL connection...")
    try:
        import psycopg2

        host = os.getenv("PGHOST", "127.0.0.1")
        port = os.getenv("PGPORT", "54322")
        database = os.getenv("PGDATABASE", "postgres")
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "postgres")

        conn_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        conn = psycopg2.connect(conn_string)
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        cur.close()
        conn.close()

        print(f"✔ DB connection validated")
        print(f"  PostgreSQL version: {version.split(',')[0]}")
        return True
    except Exception as e:
        print(f"❌ DB connection failed: {e}")
        return False


def validate_llm():
    """Validate Anthropic Claude API connection"""
    print("\nTesting Anthropic Claude API...")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "sk-ant-your-key-here":
        print("⚠️  Anthropic API key not configured")
        print("  Set ANTHROPIC_API_KEY in .env file")
        return False

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)

        # Test with a minimal API call
        message = client.messages.create(
            model="claude-3-haiku-20240307",  # Cheapest model - saves money!
            max_tokens=10,
            messages=[{"role": "user", "content": "Hello"}]
        )

        print(f"✔ LLM ready")
        print(f"  Model: claude-3-haiku-20240307 (cost-optimized)")
        print(f"  Response: {message.content[0].text}")
        return True
    except ImportError:
        print("⚠️  Anthropic library not installed")
        print("  Run: pip install anthropic")
        return False
    except Exception as e:
        print(f"❌ LLM connection failed: {e}")
        return False


def validate_binance():
    """Validate Binance API connection"""
    print("\nTesting Binance API...")

    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")

    if not api_key or api_key == "your-binance-api-key-here":
        print("⚠️  Binance API key not configured")
        print("  Set BINANCE_API_KEY and BINANCE_API_SECRET in .env file")
        return False

    try:
        from binance.client import Client

        client = Client(api_key, api_secret, testnet=False)

        # Test with ping endpoint (no auth required)
        ping = client.ping()

        # Test with server time (no auth required)
        server_time = client.get_server_time()

        # Test with account info (requires auth)
        account = client.get_account()

        print(f"✔ Binance ready")
        print(f"  Server time: {server_time['serverTime']}")
        print(f"  Account type: {account.get('accountType', 'N/A')}")
        return True
    except ImportError:
        print("⚠️  Binance library not installed")
        print("  Run: pip install python-binance")
        return False
    except Exception as e:
        print(f"❌ Binance connection failed: {e}")
        return False


def main():
    """Run all validation checks"""
    print("=" * 70)
    print("VISION-IOS ENVIRONMENT VALIDATION")
    print("=" * 70)
    print()

    results = {
        'database': validate_database(),
        'llm': validate_llm(),
        'binance': validate_binance()
    }

    print()
    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    for service, status in results.items():
        status_icon = "✔" if status else "❌"
        print(f"{status_icon} {service.upper()}: {'READY' if status else 'NOT READY'}")

    print()

    if all(results.values()):
        print("✅ Vision-IoS bound to environment root")
        print(f"   Root: {Path(__file__).parent}")
        print()
        print("🚀 All systems operational!")
        return 0
    else:
        print("⚠️  Some systems not ready. Check errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
