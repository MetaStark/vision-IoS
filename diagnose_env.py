#!/usr/bin/env python3
"""
Comprehensive .env diagnostic script
Identifies why ANTHROPIC_API_KEY is not loading correctly
"""

import os
import sys
from pathlib import Path

print("=" * 70)
print("ENVIRONMENT DIAGNOSTICS")
print("=" * 70)
print()

# 1. Check current working directory
print(f"1. Current working directory: {os.getcwd()}")
print()

# 2. Check script location
script_dir = Path(__file__).parent
print(f"2. Script directory: {script_dir}")
print()

# 3. Check for .env file
env_file = script_dir / ".env"
print(f"3. Looking for .env at: {env_file}")
print(f"   Exists: {env_file.exists()}")
if env_file.exists():
    print(f"   Size: {env_file.stat().st_size} bytes")
    print(f"   Modified: {env_file.stat().st_mtime}")
print()

# 4. Check system environment variable BEFORE loading .env
sys_env_key = os.environ.get('ANTHROPIC_API_KEY')
print(f"4. System environment ANTHROPIC_API_KEY (before .env load):")
if sys_env_key:
    print(f"   ⚠️  FOUND IN SYSTEM ENV: {sys_env_key[:20]}... (length: {len(sys_env_key)})")
    print(f"   ⚠️  This will OVERRIDE .env file!")
else:
    print(f"   Not set in system environment")
print()

# 5. Read .env file content directly (NO dotenv yet)
print("5. Reading .env file content directly:")
if env_file.exists():
    try:
        with open(env_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for i, line in enumerate(lines, 1):
                line_stripped = line.strip()
                if line_stripped.startswith('ANTHROPIC_API_KEY'):
                    print(f"   Line {i}: {line_stripped[:50]}...")
                    # Extract the value
                    if '=' in line_stripped:
                        key_value = line_stripped.split('=', 1)[1]
                        print(f"   Extracted value: {key_value[:30]}... (length: {len(key_value)})")
    except Exception as e:
        print(f"   ❌ Error reading file: {e}")
else:
    print("   ❌ .env file not found")
print()

# 6. Check for .env in parent directories
print("6. Checking for .env files in parent directories:")
current = script_dir.parent
for i in range(3):  # Check up to 3 levels up
    parent_env = current / ".env"
    if parent_env.exists():
        print(f"   ⚠️  Found .env at: {parent_env}")
        # Check if it has ANTHROPIC_API_KEY
        try:
            with open(parent_env, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'ANTHROPIC_API_KEY' in content:
                    print(f"   ⚠️  This file also contains ANTHROPIC_API_KEY!")
        except:
            pass
    current = current.parent
print()

# 7. Now load with python-dotenv
print("7. Loading .env with python-dotenv:")
try:
    from dotenv import load_dotenv

    # Clear any existing value first
    if 'ANTHROPIC_API_KEY' in os.environ:
        print(f"   Clearing existing os.environ value")
        del os.environ['ANTHROPIC_API_KEY']

    result = load_dotenv(env_file, override=True)
    print(f"   load_dotenv returned: {result}")
    print(f"   Target file: {env_file}")

    loaded_key = os.getenv('ANTHROPIC_API_KEY')
    if loaded_key:
        print(f"   ✔ Loaded: {loaded_key[:30]}... (length: {len(loaded_key)})")
    else:
        print(f"   ❌ Not loaded (None)")
except ImportError:
    print("   ❌ python-dotenv not installed")
except Exception as e:
    print(f"   ❌ Error: {e}")
print()

# 8. Check os.environ directly
print("8. Checking os.environ directly after load:")
env_key = os.environ.get('ANTHROPIC_API_KEY')
if env_key:
    print(f"   Value: {env_key[:30]}... (length: {len(env_key)})")
else:
    print(f"   Not found in os.environ")
print()

# 9. List all ANTHROPIC_* variables
print("9. All ANTHROPIC_* environment variables:")
found_any = False
for key, value in os.environ.items():
    if key.startswith('ANTHROPIC'):
        print(f"   {key}: {value[:30]}... (length: {len(value)})")
        found_any = True
if not found_any:
    print("   None found")
print()

print("=" * 70)
print("DIAGNOSIS COMPLETE")
print("=" * 70)
