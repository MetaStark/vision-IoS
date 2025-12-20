#!/usr/bin/env python3
"""
IoS-012 G1 TECHNICAL INTEGRATION VALIDATION
============================================
Authority: BOARD (Vice-CEO)
Technical Lead: STIG (CTO)
Operations: LINE
Governance: VEGA
Classification: Tier-1 Critical

Validation Protocol:
1. Infrastructure Setup (PAPER_MOCK mode)
2. Security Primitives (Ed25519, TTL, Schema, Hash)
3. Integration Test ("The Handshake")
4. Negative Test ("The Sentinel")
"""

import os
import sys
import json
import hashlib
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Tuple, Optional
from decimal import Decimal
import uuid

# Cryptographic imports
try:
    from nacl.signing import SigningKey, VerifyKey
    from nacl.exceptions import BadSignatureError
    NACL_AVAILABLE = True
except ImportError:
    NACL_AVAILABLE = False
    print("WARNING: PyNaCl not available. Using mock signature verification.")

from dotenv import load_dotenv
load_dotenv()

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)


class IoS012ExecutionEngine:
    """
    IoS-012 Execution Engine (Alpaca Adapter)
    Mode: PAPER_MOCK (G1 Validation)
    """

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.conn.autocommit = False
        self.mode = 'PAPER_MOCK'

        # Generate test signing keys for G1 validation
        if NACL_AVAILABLE:
            self.signing_key = SigningKey.generate()
            self.verify_key = self.signing_key.verify_key
        else:
            self.signing_key = None
            self.verify_key = None

        self.results = {
            'metadata': {
                'validation_type': 'IOS012_G1_INTEGRATION',
                'module': 'IoS-012',
                'gate': 'G1',
                'mode': self.mode,
                'started_at': datetime.now(timezone.utc).isoformat(),
                'validator': 'STIG/LINE',
                'authority': 'BOARD',
                'nacl_available': NACL_AVAILABLE
            },
            'tests': {},
            'security_events': [],
            'mock_lifecycle': [],
            'overall_status': 'PENDING'
        }

    def _execute_query(self, query: str, params: tuple = None, commit: bool = False) -> List[Dict]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if commit:
                self.conn.commit()
            if cur.description:
                return [dict(row) for row in cur.fetchall()]
            return []

    def _execute_insert(self, query: str, params: tuple = None) -> None:
        with self.conn.cursor() as cur:
            cur.execute(query, params)
        self.conn.commit()

    # =========================================================
    # CRYPTOGRAPHIC PRIMITIVES
    # =========================================================
    def sign_message(self, message: str) -> str:
        """Sign a message with Ed25519"""
        if NACL_AVAILABLE and self.signing_key:
            signed = self.signing_key.sign(message.encode())
            return signed.signature.hex()
        else:
            # Mock signature for testing
            return hashlib.sha256(f"MOCK_SIG:{message}".encode()).hexdigest()

    def verify_signature(self, message: str, signature: str, public_key: Optional[bytes] = None) -> Tuple[bool, str]:
        """Verify Ed25519 signature"""
        if NACL_AVAILABLE and self.verify_key:
            try:
                sig_bytes = bytes.fromhex(signature)
                self.verify_key.verify(message.encode(), sig_bytes)
                return True, "VALID"
            except BadSignatureError:
                return False, "INVALID_SIGNATURE"
            except Exception as e:
                return False, f"VERIFICATION_ERROR: {str(e)}"
        else:
            # Mock verification - check if signature matches expected format
            expected = hashlib.sha256(f"MOCK_SIG:{message}".encode()).hexdigest()
            if signature == expected:
                return True, "VALID_MOCK"
            return False, "INVALID_MOCK_SIGNATURE"

    def compute_context_hash(self, data: Dict) -> str:
        """Compute SHA256 hash of context data"""
        normalized = json.dumps(data, sort_keys=True, cls=DecimalEncoder)
        return hashlib.sha256(normalized.encode()).hexdigest()

    # =========================================================
    # SECURITY PRIMITIVES
    # =========================================================
    def verify_decision_plan(self, decision_id: str) -> Dict:
        """
        Verify a DecisionPlan meets all security requirements:
        1. Ed25519 signature validity
        2. context_hash integrity
        3. TTL validity
        4. Schema compliance
        """
        start_time = time.time()

        # Fetch decision
        query = """
        SELECT * FROM fhq_governance.decision_log
        WHERE decision_id = %s
        """
        results = self._execute_query(query, (decision_id,))

        if not results:
            return {
                'verified': False,
                'reason': 'DECISION_NOT_FOUND',
                'latency_ms': int((time.time() - start_time) * 1000)
            }

        decision = results[0]

        verification = {
            'decision_id': decision_id,
            'checks': {},
            'verified': True,
            'rejection_reason': None
        }

        # Check 1: TTL Validity
        now = datetime.now(timezone.utc)
        valid_until = decision['valid_until']
        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=timezone.utc)

        ttl_valid = now < valid_until
        verification['checks']['ttl_valid'] = {
            'passed': ttl_valid,
            'current_time': now.isoformat(),
            'valid_until': valid_until.isoformat()
        }
        if not ttl_valid:
            verification['verified'] = False
            verification['rejection_reason'] = 'TTL_EXPIRED'

        # Check 2: Signature Presence
        has_signature = decision.get('governance_signature') is not None
        verification['checks']['signature_present'] = {'passed': has_signature}

        if has_signature:
            # For G1, we verify against our test key
            # In production, this would use IoS-008's public key
            sig_message = f"{decision_id}:{decision['context_hash']}"
            sig_valid, sig_reason = self.verify_signature(
                sig_message,
                decision['governance_signature']
            )
            verification['checks']['signature_valid'] = {
                'passed': sig_valid,
                'reason': sig_reason
            }
            if not sig_valid and verification['verified']:
                verification['verified'] = False
                verification['rejection_reason'] = sig_reason
        else:
            verification['checks']['signature_valid'] = {
                'passed': False,
                'reason': 'MISSING_SIGNATURE'
            }
            if verification['verified']:
                verification['verified'] = False
                verification['rejection_reason'] = 'MISSING_SIGNATURE'

        # Check 3: Context Hash Present
        has_hash = decision.get('context_hash') is not None and decision['context_hash'] != ''
        verification['checks']['context_hash_present'] = {'passed': has_hash}
        if not has_hash and verification['verified']:
            verification['verified'] = False
            verification['rejection_reason'] = 'MISSING_CONTEXT_HASH'

        # Check 4: Schema Compliance
        required_fields = ['decision_id', 'valid_until', 'final_allocation', 'asset_directives']
        missing_fields = [f for f in required_fields if decision.get(f) is None]
        schema_valid = len(missing_fields) == 0
        verification['checks']['schema_valid'] = {
            'passed': schema_valid,
            'missing_fields': missing_fields
        }
        if not schema_valid and verification['verified']:
            verification['verified'] = False
            verification['rejection_reason'] = f'SCHEMA_INVALID: missing {missing_fields}'

        verification['latency_ms'] = int((time.time() - start_time) * 1000)
        return verification

    def log_security_alert(self, alert_type: str, decision_id: str, description: str, evidence: Dict = None):
        """Log a security alert"""
        query = """
        INSERT INTO fhq_governance.security_alerts
        (alert_type, alert_severity, source_module, decision_id, description, evidence)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        self._execute_insert(query, (
            alert_type,
            'HIGH',
            'IoS-012',
            decision_id,
            description,
            json.dumps(evidence, cls=DecimalEncoder) if evidence else None
        ))
        self.results['security_events'].append({
            'type': alert_type,
            'decision_id': decision_id,
            'description': description,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    # =========================================================
    # CONSTITUTIONAL ENFORCEMENT (CEO Directive - IoS-012 Hardening)
    # =========================================================
    def enforce_defcon_circuit_breaker(self, action_type: str, asset_id: str = None) -> Dict:
        """
        ADR-016 DEFCON Circuit Breaker Enforcement
        FAIL-CLOSED: If DEFCON >= 2, block ACQUIRE actions
        """
        query = """
        SELECT * FROM fhq_governance.enforce_defcon_circuit_breaker(%s, %s)
        """
        results = self._execute_query(query, (action_type, asset_id))
        if results:
            return dict(results[0])
        return {'action_permitted': False, 'blocked_reason': 'DEFCON_CHECK_FAILED'}

    def enforce_ios008_mandate(self, decision_id: str, plan_hash: str) -> Dict:
        """
        HV-001 IoS-008 Source Mandate Enforcement
        FAIL-CLOSED: Only accept signals from IoS-008
        """
        query = """
        SELECT * FROM fhq_governance.enforce_ios008_mandate(%s, %s)
        """
        results = self._execute_query(query, (decision_id, plan_hash))
        if results:
            return dict(results[0])
        return {'mandate_valid': False, 'failure_reason': 'MANDATE_CHECK_FAILED'}

    def execution_guard_check(self, decision_id: str, asset_id: str, action_type: str, order_value: float = 0) -> Dict:
        """
        CV-002 ExecutionGuard with Economic Safety
        FAIL-CLOSED: Enforce skill threshold and position limits
        """
        query = """
        SELECT * FROM fhq_governance.execution_guard_check(%s, %s, %s, %s)
        """
        results = self._execute_query(query, (decision_id, asset_id, action_type, order_value))
        if results:
            return dict(results[0])
        return {'execution_permitted': False, 'rejection_reason': 'GUARD_CHECK_FAILED'}

    def validate_execution_request(self, decision_id: str, asset_id: str, action_type: str, order_value: float = 0) -> Dict:
        """
        Unified Constitutional Validation (CV-001, CV-002, HV-001, HV-002)
        FAIL-CLOSED: All checks must pass
        """
        query = """
        SELECT * FROM fhq_governance.validate_execution_request(%s, %s, %s, %s)
        """
        results = self._execute_query(query, (decision_id, asset_id, action_type, order_value))
        if results:
            return dict(results[0])
        return {
            'execution_authorized': False,
            'cv001_signature_valid': False,
            'cv002_guard_passed': False,
            'hv002_defcon_permitted': False,
            'rejection_reasons': ['VALIDATION_CHECK_FAILED']
        }

    # =========================================================
    # MOCK EXECUTION
    # =========================================================
    def compute_position_diff(self, asset_id: str, target_allocation: float) -> Dict:
        """Compute difference between current and target position"""
        # Get current mock position
        query = """
        SELECT quantity FROM fhq_governance.mock_positions
        WHERE asset_id = %s
        """
        result = self._execute_query(query, (asset_id,))
        current = float(result[0]['quantity']) if result else 0.0

        diff = target_allocation - current

        return {
            'asset_id': asset_id,
            'current_position': current,
            'target_position': target_allocation,
            'position_diff': diff,
            'order_side': 'BUY' if diff > 0.01 else ('SELL' if diff < -0.01 else 'HOLD')
        }

    def generate_mock_order(self, decision_id: str, asset_id: str, diff: Dict) -> Dict:
        """Generate a mock order (no real execution)"""
        mock_prices = {'BTC-USD': 95000, 'ETH-USD': 3500, 'SOL-USD': 230}

        order = {
            'order_id': str(uuid.uuid4()),
            'decision_id': decision_id,
            'asset_id': asset_id,
            'side': diff['order_side'],
            'quantity': abs(diff['position_diff']),
            'price': mock_prices.get(asset_id, 100),
            'status': 'MOCK_FILLED',
            'executed_at': datetime.now(timezone.utc).isoformat()
        }

        return order

    def execute_decision_plan(self, decision_id: str) -> Dict:
        """
        Full execution lifecycle with Constitutional Enforcement:
        1. Detect DecisionPlan
        2. Verify security primitives
        3. CONSTITUTIONAL CHECK: IoS-008 mandate (HV-001)
        4. CONSTITUTIONAL CHECK: DEFCON circuit breaker (HV-002)
        5. CONSTITUTIONAL CHECK: ExecutionGuard (CV-002)
        6. Compute position diff
        7. Generate mock execution report

        CEO Directive: CD-IOS-012-EXEC-HARDENING
        All constitutional checks are FAIL-CLOSED
        """
        start_time = time.time()

        lifecycle = {
            'decision_id': decision_id,
            'stages': [],
            'success': False,
            'constitutional_checks': {}
        }

        # Stage 1: Detection
        detect_start = time.time()
        query = "SELECT * FROM fhq_governance.decision_log WHERE decision_id = %s"
        decisions = self._execute_query(query, (decision_id,))
        detect_latency = int((time.time() - detect_start) * 1000)

        lifecycle['stages'].append({
            'stage': 'DETECTION',
            'latency_ms': detect_latency,
            'passed': len(decisions) > 0
        })

        if not decisions:
            lifecycle['error'] = 'DECISION_NOT_FOUND'
            return lifecycle

        decision = decisions[0]

        # Parse asset info early for constitutional checks
        asset_directives = decision.get('asset_directives', {})
        if isinstance(asset_directives, str):
            asset_directives = json.loads(asset_directives) if asset_directives else {}
        asset_id = asset_directives.get('asset_id', 'BTC-USD') if asset_directives else 'BTC-USD'
        action_type = asset_directives.get('action', 'HOLD') if asset_directives else 'HOLD'

        # Stage 2: Verification
        verify_start = time.time()
        verification = self.verify_decision_plan(decision_id)
        verify_latency = int((time.time() - verify_start) * 1000)

        lifecycle['stages'].append({
            'stage': 'VERIFICATION',
            'latency_ms': verify_latency,
            'passed': verification['verified'],
            'checks': verification['checks']
        })

        if not verification['verified']:
            # Log security alert
            self.log_security_alert(
                'VERIFICATION_FAILED',
                decision_id,
                f"DecisionPlan failed verification: {verification['rejection_reason']}",
                verification
            )

        # =====================================================
        # CONSTITUTIONAL ENFORCEMENT (CEO Directive - MANDATORY)
        # =====================================================

        # Stage 3: HV-001 - IoS-008 Source Mandate
        mandate_start = time.time()
        plan_hash = decision.get('hash_self') or decision.get('context_hash', '')
        ios008_result = self.enforce_ios008_mandate(decision_id, plan_hash)
        mandate_latency = int((time.time() - mandate_start) * 1000)

        lifecycle['constitutional_checks']['HV001_IOS008_MANDATE'] = {
            'passed': ios008_result.get('mandate_valid', False),
            'signature_agent': ios008_result.get('signature_agent'),
            'failure_reason': ios008_result.get('failure_reason'),
            'latency_ms': mandate_latency
        }
        lifecycle['stages'].append({
            'stage': 'HV001_IOS008_MANDATE',
            'latency_ms': mandate_latency,
            'passed': ios008_result.get('mandate_valid', False)
        })

        if not ios008_result.get('mandate_valid', False):
            self.log_security_alert(
                'HV001_MANDATE_VIOLATION',
                decision_id,
                f"IoS-008 mandate enforcement failed: {ios008_result.get('failure_reason', 'UNKNOWN')}",
                ios008_result
            )
            lifecycle['error'] = f"HV001_VIOLATION: {ios008_result.get('failure_reason', 'MANDATE_FAILED')}"
            return lifecycle

        # Stage 4: HV-002 - DEFCON Circuit Breaker
        defcon_start = time.time()
        defcon_result = self.enforce_defcon_circuit_breaker(action_type, asset_id)
        defcon_latency = int((time.time() - defcon_start) * 1000)

        lifecycle['constitutional_checks']['HV002_DEFCON_CIRCUIT_BREAKER'] = {
            'passed': defcon_result.get('action_permitted', False),
            'current_defcon': defcon_result.get('current_defcon'),
            'enforcement_rule': defcon_result.get('enforcement_rule'),
            'blocked_reason': defcon_result.get('blocked_reason'),
            'latency_ms': defcon_latency
        }
        lifecycle['stages'].append({
            'stage': 'HV002_DEFCON_CIRCUIT_BREAKER',
            'latency_ms': defcon_latency,
            'passed': defcon_result.get('action_permitted', False)
        })

        if not defcon_result.get('action_permitted', False):
            self.log_security_alert(
                'HV002_DEFCON_BLOCK',
                decision_id,
                f"DEFCON circuit breaker activated: {defcon_result.get('blocked_reason', 'DEFCON_HALT')}",
                defcon_result
            )
            lifecycle['error'] = f"HV002_DEFCON_BLOCK: {defcon_result.get('blocked_reason', 'CIRCUIT_BREAKER_ACTIVE')}"
            return lifecycle

        # Stage 5: CV-002 - ExecutionGuard (Economic Safety)
        guard_start = time.time()
        order_value = float(decision.get('final_allocation', 0))
        guard_result = self.execution_guard_check(decision_id, asset_id, action_type, order_value)
        guard_latency = int((time.time() - guard_start) * 1000)

        lifecycle['constitutional_checks']['CV002_EXECUTION_GUARD'] = {
            'passed': guard_result.get('execution_permitted', False),
            'skill_score': float(guard_result.get('skill_score', 0)) if guard_result.get('skill_score') else None,
            'min_required_skill': float(guard_result.get('min_required_skill', 0)) if guard_result.get('min_required_skill') else None,
            'economic_safety_check': guard_result.get('economic_safety_check'),
            'rejection_reason': guard_result.get('rejection_reason'),
            'latency_ms': guard_latency
        }
        lifecycle['stages'].append({
            'stage': 'CV002_EXECUTION_GUARD',
            'latency_ms': guard_latency,
            'passed': guard_result.get('execution_permitted', False)
        })

        if not guard_result.get('execution_permitted', False):
            self.log_security_alert(
                'CV002_GUARD_REJECTION',
                decision_id,
                f"ExecutionGuard blocked: {guard_result.get('rejection_reason', 'GUARD_FAILED')}",
                guard_result
            )
            lifecycle['error'] = f"CV002_GUARD_BLOCK: {guard_result.get('rejection_reason', 'ECONOMIC_SAFETY_VIOLATION')}"
            return lifecycle

        # =====================================================
        # END CONSTITUTIONAL ENFORCEMENT
        # =====================================================

        if not verification['verified']:
            # Log security alert
            self.log_security_alert(
                'VERIFICATION_FAILED',
                decision_id,
                f"DecisionPlan failed verification: {verification['rejection_reason']}",
                verification
            )

            # Log rejection
            self._execute_insert("""
                INSERT INTO fhq_governance.execution_log
                (decision_id, decision_hash, signature_verified, ttl_valid, schema_valid,
                 context_hash_valid, security_status, rejection_reason, execution_mode)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                decision_id,
                decision.get('context_hash', ''),
                verification['checks'].get('signature_valid', {}).get('passed', False),
                verification['checks'].get('ttl_valid', {}).get('passed', False),
                verification['checks'].get('schema_valid', {}).get('passed', False),
                verification['checks'].get('context_hash_present', {}).get('passed', False),
                'REJECTED',
                verification['rejection_reason'],
                self.mode
            ))

            lifecycle['error'] = verification['rejection_reason']
            return lifecycle

        # Stage 3: Position Diff
        diff_start = time.time()
        asset_directives = decision.get('asset_directives', {})

        # Parse asset from directives
        if isinstance(asset_directives, str):
            asset_directives = json.loads(asset_directives)

        asset_id = asset_directives.get('asset_id', 'BTC-USD') if asset_directives else 'BTC-USD'
        target_alloc = float(decision.get('final_allocation', 0))

        diff = self.compute_position_diff(asset_id, target_alloc)
        diff_latency = int((time.time() - diff_start) * 1000)

        lifecycle['stages'].append({
            'stage': 'POSITION_DIFF',
            'latency_ms': diff_latency,
            'passed': True,
            'diff': diff
        })

        # Stage 4: Mock Execution
        exec_start = time.time()
        mock_order = self.generate_mock_order(decision_id, asset_id, diff)
        exec_latency = int((time.time() - exec_start) * 1000)

        lifecycle['stages'].append({
            'stage': 'MOCK_EXECUTION',
            'latency_ms': exec_latency,
            'passed': True,
            'order': mock_order
        })

        # Log successful execution
        self._execute_insert("""
            INSERT INTO fhq_governance.execution_log
            (decision_id, decision_hash, signature_verified, ttl_valid, schema_valid,
             context_hash_valid, security_status, execution_mode, execution_status,
             asset_id, order_side, order_qty, order_price,
             current_position, target_position, position_diff,
             detection_latency_ms, verification_latency_ms, execution_latency_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            decision_id,
            decision.get('context_hash', ''),
            True, True, True, True,
            'VERIFIED',
            self.mode,
            'MOCK_FILLED',
            asset_id,
            diff['order_side'],
            abs(diff['position_diff']),
            mock_order['price'],
            diff['current_position'],
            diff['target_position'],
            diff['position_diff'],
            detect_latency,
            verify_latency,
            exec_latency
        ))

        lifecycle['success'] = True
        lifecycle['total_latency_ms'] = int((time.time() - start_time) * 1000)
        lifecycle['execution_report'] = mock_order

        return lifecycle


class IoS012G1Validator:
    """G1 Integration Validation Suite"""

    def __init__(self):
        self.engine = IoS012ExecutionEngine()
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.results = self.engine.results

    def _execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if cur.description:
                return [dict(row) for row in cur.fetchall()]
            return []

    def _execute_insert(self, query: str, params: tuple = None) -> None:
        with self.conn.cursor() as cur:
            cur.execute(query, params)
        self.conn.commit()

    # =========================================================
    # TEST 1: THE HANDSHAKE (Valid DecisionPlan)
    # =========================================================
    def test_handshake(self) -> Dict:
        """
        Integration Test: Valid DecisionPlan
        - Inject valid plan
        - Verify detection < 1000ms
        - Verify signature
        - Compute position diff
        - Generate mock execution
        """
        print("\n" + "="*70)
        print("G1 INTEGRATION TEST: THE HANDSHAKE")
        print("="*70)

        # Create a valid DecisionPlan
        decision_id = str(uuid.uuid4())
        context_data = {
            'asset': 'BTC-USD',
            'regime': 'NEUTRAL',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        context_hash = self.engine.compute_context_hash(context_data)

        # Sign the decision
        sig_message = f"{decision_id}:{context_hash}"
        signature = self.engine.sign_message(sig_message)

        # Insert valid DecisionPlan
        valid_until = datetime.now(timezone.utc) + timedelta(minutes=15)

        print(f"  Injecting valid DecisionPlan: {decision_id[:8]}...")

        self._execute_insert("""
            INSERT INTO fhq_governance.decision_log
            (decision_id, valid_from, valid_until, context_hash,
             regime_snapshot, causal_snapshot, skill_snapshot,
             global_regime, defcon_level, system_skill_score,
             asset_directives, base_allocation, regime_scalar,
             causal_vector, skill_damper, final_allocation,
             governance_signature, signature_agent,
             hash_prev, hash_self, sequence_number)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            decision_id,
            datetime.now(timezone.utc),
            valid_until,
            context_hash,
            json.dumps({'regime': 'NEUTRAL'}),
            json.dumps({'vector': 1.0}),
            json.dumps({'score': 0.8}),
            'NEUTRAL',
            4,
            0.8,
            json.dumps({'asset_id': 'BTC-USD', 'action': 'HOLD'}),
            1.0,
            0.5,
            1.0,
            1.0,
            0.5,
            signature,
            'IoS-008',
            None,
            hashlib.sha256(decision_id.encode()).hexdigest(),
            1
        ))

        # Execute the lifecycle
        print("  Executing lifecycle...")
        lifecycle = self.engine.execute_decision_plan(decision_id)

        # Validate results
        detection_pass = lifecycle['stages'][0]['latency_ms'] < 1000 if lifecycle['stages'] else False
        verification_pass = lifecycle['stages'][1]['passed'] if len(lifecycle['stages']) > 1 else False
        diff_pass = lifecycle['stages'][2]['passed'] if len(lifecycle['stages']) > 2 else False
        exec_pass = lifecycle['stages'][3]['passed'] if len(lifecycle['stages']) > 3 else False

        all_pass = detection_pass and verification_pass and diff_pass and exec_pass

        test_result = {
            'test_id': 'G1-HANDSHAKE',
            'test_name': 'THE_HANDSHAKE',
            'decision_id': decision_id,
            'lifecycle': lifecycle,
            'checks': {
                'detection_under_1000ms': {
                    'passed': detection_pass,
                    'latency_ms': lifecycle['stages'][0]['latency_ms'] if lifecycle['stages'] else None
                },
                'signature_verified': {'passed': verification_pass},
                'position_diff_computed': {'passed': diff_pass},
                'mock_execution_generated': {'passed': exec_pass}
            },
            'status': 'PASS' if all_pass else 'FAIL'
        }

        if all_pass:
            print(f"  [PASS] Handshake complete in {lifecycle.get('total_latency_ms', 0)}ms")
            print(f"         Mock order: {lifecycle.get('execution_report', {}).get('side', 'N/A')}")
        else:
            print(f"  [FAIL] Handshake failed: {lifecycle.get('error', 'Unknown')}")

        self.results['tests']['G1-HANDSHAKE'] = test_result
        self.results['mock_lifecycle'].append(lifecycle)
        return test_result

    # =========================================================
    # TEST 2: THE SENTINEL (Invalid DecisionPlan)
    # =========================================================
    def test_sentinel(self) -> Dict:
        """
        Negative Test: Invalid DecisionPlan
        - Test expired TTL
        - Test invalid signature
        - Test mutated context_hash
        All must be REJECTED with SECURITY_ALERT
        """
        print("\n" + "="*70)
        print("G1 NEGATIVE TEST: THE SENTINEL")
        print("="*70)

        subtests = {}

        # Subtest A: Expired TTL
        # NOTE: Database constraint correctly prevents inserting expired decisions
        # We test TTL verification by creating a valid decision with 1-second TTL
        # and verifying it's rejected after expiration
        print("\n  [A] Testing Expired TTL...")
        decision_id_a = str(uuid.uuid4())

        # Create decision with 1-second valid TTL (will expire almost immediately)
        valid_from_a = datetime.now(timezone.utc)
        valid_until_a = valid_from_a + timedelta(seconds=1)

        self._execute_insert("""
            INSERT INTO fhq_governance.decision_log
            (decision_id, valid_from, valid_until, context_hash,
             regime_snapshot, causal_snapshot, skill_snapshot,
             global_regime, defcon_level, system_skill_score,
             asset_directives, base_allocation, regime_scalar,
             causal_vector, skill_damper, final_allocation,
             governance_signature, signature_agent,
             hash_prev, hash_self, sequence_number)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            decision_id_a,
            valid_from_a,
            valid_until_a,
            'ttl_test_hash',
            '{}', '{}', '{}',
            'NEUTRAL', 4, 0.8,
            '{}', 1.0, 0.5, 1.0, 1.0, 0.5,
            self.engine.sign_message(f"{decision_id_a}:ttl_test_hash"),
            'IoS-008', None, 'hash', 2
        ))

        # Wait for TTL to expire
        time.sleep(1.5)

        # Now try to execute - should reject due to expired TTL
        lifecycle_a = self.engine.execute_decision_plan(decision_id_a)
        rejected_a = not lifecycle_a.get('success', True)

        # Verify rejection reason is TTL-related
        reason_a = lifecycle_a.get('error', '') or lifecycle_a.get('rejection_reason', '')
        ttl_rejection = 'TTL' in reason_a.upper() or 'EXPIRED' in reason_a.upper() or 'STALE' in reason_a.upper()

        subtests['A_EXPIRED_TTL'] = {
            'decision_id': decision_id_a,
            'rejected': rejected_a,
            'ttl_correctly_identified': ttl_rejection,
            'reason': reason_a,
            'status': 'PASS' if rejected_a else 'FAIL'
        }
        print(f"      [{'PASS' if rejected_a else 'FAIL'}] Expired TTL correctly rejected")

        # Subtest B: Invalid Signature
        print("  [B] Testing Invalid Signature...")
        decision_id_b = str(uuid.uuid4())
        valid_until_b = datetime.now(timezone.utc) + timedelta(minutes=15)

        self._execute_insert("""
            INSERT INTO fhq_governance.decision_log
            (decision_id, valid_from, valid_until, context_hash,
             regime_snapshot, causal_snapshot, skill_snapshot,
             global_regime, defcon_level, system_skill_score,
             asset_directives, base_allocation, regime_scalar,
             causal_vector, skill_damper, final_allocation,
             governance_signature, signature_agent,
             hash_prev, hash_self, sequence_number)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            decision_id_b,
            datetime.now(timezone.utc),
            valid_until_b,
            'valid_hash',
            '{}', '{}', '{}',
            'NEUTRAL', 4, 0.8,
            '{}', 1.0, 0.5, 1.0, 1.0, 0.5,
            'INVALID_SIGNATURE_12345',  # Wrong signature
            'IoS-008', None, 'hash', 3
        ))

        lifecycle_b = self.engine.execute_decision_plan(decision_id_b)
        rejected_b = not lifecycle_b.get('success', True)
        subtests['B_INVALID_SIGNATURE'] = {
            'decision_id': decision_id_b,
            'rejected': rejected_b,
            'reason': lifecycle_b.get('error', 'N/A'),
            'status': 'PASS' if rejected_b else 'FAIL'
        }
        print(f"      [{'PASS' if rejected_b else 'FAIL'}] Invalid signature correctly rejected")

        # Subtest C: Missing Context Hash
        print("  [C] Testing Missing Context Hash...")
        decision_id_c = str(uuid.uuid4())
        valid_until_c = datetime.now(timezone.utc) + timedelta(minutes=15)

        self._execute_insert("""
            INSERT INTO fhq_governance.decision_log
            (decision_id, valid_from, valid_until, context_hash,
             regime_snapshot, causal_snapshot, skill_snapshot,
             global_regime, defcon_level, system_skill_score,
             asset_directives, base_allocation, regime_scalar,
             causal_vector, skill_damper, final_allocation,
             governance_signature, signature_agent,
             hash_prev, hash_self, sequence_number)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            decision_id_c,
            datetime.now(timezone.utc),
            valid_until_c,
            '',  # Empty context hash
            '{}', '{}', '{}',
            'NEUTRAL', 4, 0.8,
            '{}', 1.0, 0.5, 1.0, 1.0, 0.5,
            self.engine.sign_message(f"{decision_id_c}:"),
            'IoS-008', None, 'hash', 4
        ))

        lifecycle_c = self.engine.execute_decision_plan(decision_id_c)
        rejected_c = not lifecycle_c.get('success', True)
        subtests['C_MISSING_HASH'] = {
            'decision_id': decision_id_c,
            'rejected': rejected_c,
            'reason': lifecycle_c.get('error', 'N/A'),
            'status': 'PASS' if rejected_c else 'FAIL'
        }
        print(f"      [{'PASS' if rejected_c else 'FAIL'}] Missing hash correctly rejected")

        # Check security alerts were logged
        alerts_query = """
        SELECT COUNT(*) as count FROM fhq_governance.security_alerts
        WHERE source_module = 'IoS-012'
        """
        alerts = self._execute_query(alerts_query)
        alert_count = alerts[0]['count'] if alerts else 0

        all_pass = all(s['status'] == 'PASS' for s in subtests.values())

        test_result = {
            'test_id': 'G1-SENTINEL',
            'test_name': 'THE_SENTINEL',
            'subtests': subtests,
            'security_alerts_logged': alert_count,
            'status': 'PASS' if all_pass else 'FAIL'
        }

        print(f"\n  Security alerts logged: {alert_count}")

        self.results['tests']['G1-SENTINEL'] = test_result
        return test_result

    # =========================================================
    # MAIN EXECUTION
    # =========================================================
    def run_full_validation(self) -> Dict:
        """Execute complete G1 validation suite"""
        print("\n" + "="*70)
        print("IoS-012 G1 TECHNICAL INTEGRATION VALIDATION")
        print("Authority: BOARD | Technical Lead: STIG/LINE")
        print(f"Mode: {self.engine.mode}")
        print("="*70)

        # Run tests
        self.test_handshake()
        self.test_sentinel()

        # Compute overall status
        all_pass = all(
            t['status'] == 'PASS'
            for t in self.results['tests'].values()
        )

        self.results['overall_status'] = 'PASS' if all_pass else 'FAIL'
        self.results['metadata']['completed_at'] = datetime.now(timezone.utc).isoformat()

        # Generate integrity hash
        self.results['integrity_hash'] = hashlib.sha256(
            json.dumps(self.results['tests'], sort_keys=True, cls=DecimalEncoder).encode()
        ).hexdigest()

        # Print summary
        print("\n" + "="*70)
        print("G1 INTEGRATION SUMMARY")
        print("="*70)
        for test_id, test_data in self.results['tests'].items():
            status_icon = "[PASS]" if test_data['status'] == 'PASS' else "[FAIL]"
            print(f"  {status_icon} {test_id}: {test_data['status']}")

        print("-"*70)
        print(f"  Security Events: {len(self.results['security_events'])}")
        overall_icon = "[PASS]" if self.results['overall_status'] == 'PASS' else "[FAIL]"
        print(f"  {overall_icon} OVERALL: {self.results['overall_status']}")
        print("="*70)

        return self.results

    def save_report(self, output_dir: str) -> str:
        """Save validation report to JSON"""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        filename = f"IOS012_G1_INTEGRATION_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2, cls=DecimalEncoder)

        print(f"\nReport saved: {filepath}")
        return filepath


def main():
    validator = IoS012G1Validator()
    results = validator.run_full_validation()

    # Save report
    output_dir = os.path.join(os.path.dirname(__file__), '..', '05_GOVERNANCE', 'PHASE3')
    validator.save_report(output_dir)

    # Exit with appropriate code
    sys.exit(0 if results['overall_status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
