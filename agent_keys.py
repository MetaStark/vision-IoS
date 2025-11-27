#!/usr/bin/env python3
"""
Vision-IoS Agent Key Manager
Manages agent-specific private keys and LLM keys
"""

import os
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Load .env from vision-IoS directory
ENV_FILE = Path(__file__).parent / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    print(f"⚠️  Warning: .env not found at {ENV_FILE}")


class AgentKeyManager:
    """Manages encrypted agent keys"""

    AGENTS = ['LARS', 'STIG', 'LINE', 'FINN', 'VEGA']

    def __init__(self):
        """Initialize key manager with keystore passphrase"""
        self.passphrase = os.getenv('KEYSTORE_PASSPHRASE')
        if not self.passphrase:
            raise ValueError("KEYSTORE_PASSPHRASE not set in environment")

    def get_agent_private_key(self, agent_id: str) -> Optional[str]:
        """Get encrypted private key for agent"""
        env_var = f"AGENT_{agent_id.upper()}_PRIVATE_KEY"
        return os.getenv(env_var)

    def decrypt_agent_key(self, agent_id: str) -> Optional[str]:
        """Decrypt agent private key using keystore passphrase"""
        encrypted_key = self.get_agent_private_key(agent_id)
        if not encrypted_key:
            return None

        try:
            # Use passphrase to create Fernet key (must be properly derived)
            # Note: This is a simplified example - production should use proper key derivation
            cipher = Fernet(self._derive_key_from_passphrase(self.passphrase))
            decrypted = cipher.decrypt(encrypted_key.encode())
            return decrypted.decode()
        except Exception as e:
            print(f"⚠️  Failed to decrypt key for {agent_id}: {e}")
            return None

    def get_agent_llm_key(self, agent_id: str) -> str:
        """Get LLM API key for agent (falls back to shared key)"""
        # Try agent-specific key first
        agent_key = os.getenv(f"AGENT_{agent_id.upper()}_LLM_KEY")
        if agent_key:
            return agent_key

        # Fall back to shared key
        shared_key = os.getenv("ANTHROPIC_API_KEY")
        if not shared_key:
            raise ValueError(f"No LLM key found for agent {agent_id}")

        return shared_key

    @staticmethod
    def _derive_key_from_passphrase(passphrase: str) -> bytes:
        """
        Derive Fernet key from passphrase
        Note: This is simplified - production should use proper KDF like PBKDF2
        """
        import base64
        import hashlib

        # Hash the passphrase to get 32 bytes
        key_bytes = hashlib.sha256(passphrase.encode()).digest()
        # Fernet requires base64 encoded key
        return base64.urlsafe_b64encode(key_bytes)

    def validate_all_agents(self) -> dict:
        """Validate all agent keys are present"""
        results = {}
        for agent in self.AGENTS:
            private_key = self.get_agent_private_key(agent)
            llm_key = os.getenv(f"AGENT_{agent}_LLM_KEY") or os.getenv("ANTHROPIC_API_KEY")

            results[agent] = {
                'private_key_present': private_key is not None,
                'private_key_encrypted': private_key.startswith('gAAAAAB') if private_key else False,
                'llm_key_present': llm_key is not None,
                'llm_key_type': 'agent-specific' if os.getenv(f"AGENT_{agent}_LLM_KEY") else 'shared'
            }

        return results


def get_llm_client_for_agent(agent_id: str):
    """Get configured LLM client for specific agent"""
    from anthropic import Anthropic

    key_manager = AgentKeyManager()
    api_key = key_manager.get_agent_llm_key(agent_id)

    return Anthropic(api_key=api_key)


if __name__ == "__main__":
    """Test agent key manager"""
    print("Testing Agent Key Manager...")
    print()

    try:
        manager = AgentKeyManager()

        print("Agent Key Status:")
        print("=" * 70)

        results = manager.validate_all_agents()

        for agent, status in results.items():
            print(f"\n{agent}:")
            print(f"  Private Key: {'✔' if status['private_key_present'] else '❌'} "
                  f"({'Encrypted' if status['private_key_encrypted'] else 'Plain text'})")
            print(f"  LLM Key: {'✔' if status['llm_key_present'] else '❌'} "
                  f"({status['llm_key_type']})")

        print()
        print("=" * 70)

        # Test LLM key retrieval
        print("\nTesting LLM key retrieval:")
        for agent in ['LARS', 'FINN', 'STIG']:
            try:
                llm_key = manager.get_agent_llm_key(agent)
                print(f"  {agent}: {'✔' if llm_key else '❌'} (key length: {len(llm_key) if llm_key else 0})")
            except Exception as e:
                print(f"  {agent}: ❌ {e}")

    except Exception as e:
        print(f"❌ Error: {e}")
