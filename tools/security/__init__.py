"""
FjordHQ Security Tools
======================

Authority: ADR-008 (Cryptographic Key Management)
Reference: EXEC-DIR-004-KEYS (Phase D Identity Sovereignty)

This package provides cryptographic identity management for the FjordHQ
Intelligence Operating System, including:

- generate_fleet_keys_hardened.py: Key ceremony script (SOP-008)
- vega_core.py: VEGA attestation and verification tooling

Zero Trust Rule: No agent operates without a verified Ed25519 identity
keypair anchored in fhq_meta.agent_keys and attested by VEGA.
"""

__version__ = "1.0.0"
__author__ = "CODE"
__authority__ = "ADR-008"
