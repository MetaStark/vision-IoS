"""
FINN+ Ed25519 Cryptographic Signature Module
Phase 3: Week 2 — ADR-008 Compliance

Authority: LARS Phase 3 Directive (HC-LARS-PHASE3-CONTINUE-20251124)
Canonical ADR Chain: ADR-001 → ADR-015

Purpose: Cryptographic signing of FINN+ regime predictions using Ed25519
Compliance: ADR-008 (Ed25519 signatures, 100% verification rate)

Security Requirements:
- Ed25519 signature on every prediction
- Signature covers full prediction payload (regime, confidence, probabilities, features)
- Public key stored with prediction for verification
- Signature verification mandatory before database persistence
"""

import json
import hashlib
from typing import Dict, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    from cryptography.hazmat.primitives import serialization
    from cryptography.exceptions import InvalidSignature
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("WARNING: cryptography library not available. Ed25519 signing disabled.")


@dataclass
class SignedPrediction:
    """
    Signed regime prediction with Ed25519 signature.

    ADR-008 Compliance:
    - signature_hex: Ed25519 signature (128 hex chars / 64 bytes)
    - public_key_hex: Ed25519 public key (64 hex chars / 32 bytes)
    - signature_verified: Verification status
    """
    # Prediction data
    regime_label: str
    regime_state: int
    confidence: float
    prob_bear: float
    prob_neutral: float
    prob_bull: float
    timestamp: str

    # Feature inputs
    return_z: float = None
    volatility_z: float = None
    drawdown_z: float = None
    macd_diff_z: float = None
    bb_width_z: float = None
    rsi_14_z: float = None
    roc_20_z: float = None

    # Validation metadata
    is_valid: bool = True
    validation_reason: str = "Valid"
    raw_regime: int = None
    candidate_count: int = 0
    persistence_days: int = None

    # ADR-008: Cryptographic signature
    signature_hex: str = None
    public_key_hex: str = None
    signature_verified: bool = False

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return asdict(self)


class Ed25519Signer:
    """
    Ed25519 signature manager for FINN+ predictions.

    Implements ADR-008 requirements:
    - Generate Ed25519 key pairs
    - Sign prediction payloads
    - Verify signatures
    - 100% verification rate enforcement
    """

    def __init__(self, private_key: Ed25519PrivateKey = None):
        """
        Initialize signer with optional private key.

        Args:
            private_key: Ed25519PrivateKey (if None, generates new key pair)
        """
        if not CRYPTO_AVAILABLE:
            raise ImportError(
                "cryptography library required for Ed25519 signing. "
                "Install with: pip install cryptography"
            )

        if private_key is None:
            # Generate new key pair
            self.private_key = Ed25519PrivateKey.generate()
        else:
            self.private_key = private_key

        self.public_key = self.private_key.public_key()

    def get_public_key_hex(self) -> str:
        """
        Get public key as hex string.

        Returns:
            64-character hex string (32 bytes)
        """
        public_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        return public_bytes.hex()

    def get_private_key_hex(self) -> str:
        """
        Get private key as hex string (for persistence/backup).

        WARNING: Handle private keys securely! Never commit to git.

        Returns:
            64-character hex string (32 bytes)
        """
        private_bytes = self.private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        return private_bytes.hex()

    @classmethod
    def from_hex(cls, private_key_hex: str) -> 'Ed25519Signer':
        """
        Load signer from hex-encoded private key.

        Args:
            private_key_hex: 64-character hex string (32 bytes)

        Returns:
            Ed25519Signer instance
        """
        private_bytes = bytes.fromhex(private_key_hex)
        private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
        return cls(private_key)

    def _prepare_signing_payload(self, prediction_dict: Dict) -> bytes:
        """
        Prepare canonical JSON payload for signing.

        ADR-008 Requirement: Deterministic serialization
        - Sort keys alphabetically
        - No whitespace
        - UTF-8 encoding

        Args:
            prediction_dict: Prediction data (without signature fields)

        Returns:
            UTF-8 encoded JSON bytes
        """
        # Remove signature fields if present
        payload = {k: v for k, v in prediction_dict.items()
                  if k not in ['signature_hex', 'public_key_hex', 'signature_verified']}

        # Canonical JSON: sorted keys, no whitespace
        canonical_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))

        return canonical_json.encode('utf-8')

    def sign_prediction(self, prediction_dict: Dict) -> Tuple[str, str]:
        """
        Sign prediction payload with Ed25519 private key.

        Args:
            prediction_dict: Prediction data (without signature)

        Returns:
            (signature_hex, public_key_hex) tuple
        """
        # Prepare canonical payload
        payload_bytes = self._prepare_signing_payload(prediction_dict)

        # Sign with Ed25519
        signature_bytes = self.private_key.sign(payload_bytes)

        # Convert to hex
        signature_hex = signature_bytes.hex()
        public_key_hex = self.get_public_key_hex()

        return signature_hex, public_key_hex

    @staticmethod
    def verify_signature(prediction_dict: Dict,
                        signature_hex: str,
                        public_key_hex: str) -> bool:
        """
        Verify Ed25519 signature on prediction payload.

        ADR-008 Requirement: 100% verification rate before database persistence

        Args:
            prediction_dict: Prediction data (without signature fields)
            signature_hex: 128-character hex string (64 bytes)
            public_key_hex: 64-character hex string (32 bytes)

        Returns:
            True if signature valid, False otherwise
        """
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography library required for signature verification")

        try:
            # Reconstruct public key
            public_key_bytes = bytes.fromhex(public_key_hex)
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)

            # Reconstruct signature
            signature_bytes = bytes.fromhex(signature_hex)

            # Prepare canonical payload (same as signing)
            signer_temp = Ed25519Signer()  # Temporary instance for payload prep
            payload_bytes = signer_temp._prepare_signing_payload(prediction_dict)

            # Verify signature
            public_key.verify(signature_bytes, payload_bytes)

            return True  # Verification successful

        except InvalidSignature:
            return False  # Verification failed

        except Exception as e:
            print(f"Signature verification error: {e}")
            return False


def sign_regime_prediction(prediction_data: Dict,
                          signer: Ed25519Signer) -> SignedPrediction:
    """
    Sign a regime prediction with Ed25519 signature.

    High-level convenience function for FINN+ integration.

    Args:
        prediction_data: Prediction dict (from RegimeClassification.to_dict())
        signer: Ed25519Signer instance

    Returns:
        SignedPrediction with verified signature
    """
    # Sign the prediction
    signature_hex, public_key_hex = signer.sign_prediction(prediction_data)

    # Add signature fields
    signed_data = prediction_data.copy()
    signed_data['signature_hex'] = signature_hex
    signed_data['public_key_hex'] = public_key_hex

    # Verify signature (ADR-008: 100% verification rate)
    verified = Ed25519Signer.verify_signature(
        prediction_data,
        signature_hex,
        public_key_hex
    )

    signed_data['signature_verified'] = verified

    if not verified:
        raise RuntimeError(
            "ADR-008 VIOLATION: Signature verification failed immediately after signing. "
            "This should never happen and indicates a critical cryptographic error."
        )

    # Convert to SignedPrediction object
    return SignedPrediction(**signed_data)


# ============================================================================
# Example Usage and Testing
# ============================================================================

if __name__ == "__main__":
    """
    Demonstrate Ed25519 signing for FINN+ regime predictions.
    """

    print("=" * 80)
    print("FINN+ ED25519 SIGNATURE MODULE — ADR-008 COMPLIANCE TEST")
    print("=" * 80)

    if not CRYPTO_AVAILABLE:
        print("\n❌ FAILED: cryptography library not available")
        print("   Install with: pip install cryptography")
        exit(1)

    # [1] Generate key pair
    print("\n[1] Generating Ed25519 key pair...")
    signer = Ed25519Signer()

    print(f"    Public key:  {signer.get_public_key_hex()}")
    print(f"    Private key: {signer.get_private_key_hex()[:16]}... (truncated)")

    # [2] Create sample prediction
    print("\n[2] Creating sample regime prediction...")
    prediction = {
        'regime_label': 'BULL',
        'regime_state': 2,
        'confidence': 0.70,
        'prob_bear': 0.10,
        'prob_neutral': 0.20,
        'prob_bull': 0.70,
        'timestamp': datetime.utcnow().isoformat(),
        'return_z': 1.25,
        'volatility_z': -0.45,
        'drawdown_z': 0.15,
        'is_valid': True,
        'validation_reason': 'Valid'
    }

    print(f"    Regime: {prediction['regime_label']}")
    print(f"    Confidence: {prediction['confidence']:.2%}")

    # [3] Sign prediction
    print("\n[3] Signing prediction with Ed25519...")
    signature_hex, public_key_hex = signer.sign_prediction(prediction)

    print(f"    Signature: {signature_hex[:32]}... (128 hex chars total)")
    print(f"    Public key: {public_key_hex}")

    # [4] Verify signature
    print("\n[4] Verifying Ed25519 signature...")
    is_valid = Ed25519Signer.verify_signature(prediction, signature_hex, public_key_hex)

    print(f"    Verification: {'✅ PASS' if is_valid else '❌ FAIL'}")

    # [5] Test tampering detection
    print("\n[5] Testing tampering detection...")
    tampered_prediction = prediction.copy()
    tampered_prediction['regime_label'] = 'BEAR'  # Tamper with prediction

    is_valid_tampered = Ed25519Signer.verify_signature(
        tampered_prediction,
        signature_hex,
        public_key_hex
    )

    print(f"    Tampered prediction verification: {'❌ PASS (detected)' if not is_valid_tampered else '✅ FAIL (not detected)'}")

    # [6] Test high-level convenience function
    print("\n[6] Testing high-level sign_regime_prediction()...")
    signed_pred = sign_regime_prediction(prediction, signer)

    print(f"    Signed prediction type: {type(signed_pred).__name__}")
    print(f"    Signature verified: {'✅ PASS' if signed_pred.signature_verified else '❌ FAIL'}")
    print(f"    Regime: {signed_pred.regime_label}")

    # [7] Test key persistence and reload
    print("\n[7] Testing key persistence and reload...")
    private_key_hex = signer.get_private_key_hex()

    # Reload signer from hex key
    signer_reloaded = Ed25519Signer.from_hex(private_key_hex)

    # Sign again with reloaded key
    signature_hex_2, public_key_hex_2 = signer_reloaded.sign_prediction(prediction)

    # Verify with original public key
    is_valid_reloaded = Ed25519Signer.verify_signature(
        prediction,
        signature_hex_2,
        public_key_hex
    )

    print(f"    Key reload successful: {'✅ PASS' if is_valid_reloaded else '❌ FAIL'}")
    print(f"    Public keys match: {'✅ PASS' if public_key_hex == public_key_hex_2 else '❌ FAIL'}")

    # Final summary
    print("\n" + "=" * 80)
    print("ADR-008 COMPLIANCE TEST COMPLETE")
    print("=" * 80)

    all_tests_pass = is_valid and not is_valid_tampered and signed_pred.signature_verified and is_valid_reloaded

    if all_tests_pass:
        print("✅ ALL TESTS PASSED")
        print("\nEd25519 Signature Module:")
        print("  - Key generation: FUNCTIONAL")
        print("  - Signing: FUNCTIONAL")
        print("  - Verification: FUNCTIONAL")
        print("  - Tampering detection: FUNCTIONAL")
        print("  - Key persistence: FUNCTIONAL")
        print("\nStatus: Ready for FINN+ integration")
    else:
        print("❌ SOME TESTS FAILED")
        print("   Review output above for details")

    print("=" * 80)
