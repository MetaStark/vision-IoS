#!/usr/bin/env python3
"""
Helper script to set ANTHROPIC_API_KEY in .env file
Usage: python set_api_key.py <your-api-key>
"""

import sys
from pathlib import Path

def update_env_key(api_key: str):
    """Update ANTHROPIC_API_KEY in .env file"""
    env_file = Path(__file__).parent / ".env"

    if not env_file.exists():
        print(f"❌ .env file not found at: {env_file}")
        return False

    # Validate key format
    if not api_key.startswith('sk-ant-'):
        print(f"⚠️  Warning: API key doesn't start with 'sk-ant-'")
        print(f"   Key starts with: {api_key[:10]}...")
        response = input("   Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("❌ Aborted")
            return False

    # Read current .env content
    with open(env_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Update the ANTHROPIC_API_KEY line
    updated = False
    for i, line in enumerate(lines):
        if line.strip().startswith('ANTHROPIC_API_KEY='):
            old_value = line.strip().split('=', 1)[1] if '=' in line else ''
            lines[i] = f'ANTHROPIC_API_KEY={api_key}\n'
            updated = True
            print(f"✔ Updated ANTHROPIC_API_KEY")
            print(f"  Old: {old_value[:30]}...")
            print(f"  New: {api_key[:30]}... (length: {len(api_key)})")
            break

    if not updated:
        print(f"❌ ANTHROPIC_API_KEY not found in .env file")
        return False

    # Write back to file
    with open(env_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print(f"✔ .env file updated successfully")

    # Verify it loads correctly
    print(f"\nVerifying...")
    from dotenv import load_dotenv
    import os

    # Clear any cached value
    if 'ANTHROPIC_API_KEY' in os.environ:
        del os.environ['ANTHROPIC_API_KEY']

    load_dotenv(env_file, override=True)
    loaded_key = os.getenv('ANTHROPIC_API_KEY')

    if loaded_key == api_key:
        print(f"✔ Verification successful!")
        print(f"  Loaded: {loaded_key[:30]}... (length: {len(loaded_key)})")
        return True
    else:
        print(f"❌ Verification failed!")
        print(f"  Expected: {api_key[:30]}...")
        print(f"  Got: {loaded_key[:30] if loaded_key else 'None'}...")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python set_api_key.py <your-api-key>")
        print("")
        print("Example:")
        print("  python set_api_key.py sk-ant-api03-XXXXXXXXXXXXXXXXXXXX")
        print("")
        print("Or set it directly by editing vision-IoS/.env:")
        print("  ANTHROPIC_API_KEY=sk-ant-api03-XXXXXXXXXXXXXXXXXXXX")
        sys.exit(1)

    api_key = sys.argv[1].strip()

    if update_env_key(api_key):
        print("\n🚀 Ready to test! Run:")
        print("   python vision-IoS/test_api_key.py")
        sys.exit(0)
    else:
        sys.exit(1)
