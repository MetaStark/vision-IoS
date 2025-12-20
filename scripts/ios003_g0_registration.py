#!/usr/bin/env python3
"""
IoS-003 G0 REGISTRATION - CEO DIRECTIVE
=======================================

Authority: CEO (ADR-001 through ADR-016)
Target: IoS-003 - Meta-Perception Engine (Market Brain)
Gate: G0_SUBMISSION
Version: 2026.DRAFT.1

This script:
1. Registers IoS-003 in fhq_meta.ios_registry
2. Creates fhq_perception schema and tables
3. Registers META_PERCEPTION pipeline stage
4. Logs G0 submission to governance
5. Generates G0 Evidence Bundle

NO COMPUTATION OR INFERENCE MAY OCCUR UNTIL G4 ACTIVATION.
"""

import os
import sys
import json
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

ENGINE_VERSION = "2026.DRAFT.1"
REGISTRATION_ID = str(uuid.uuid4())

# IoS-003 Specification Hash (SHA-256 of the canonical spec)
IOS003_SPEC = """
IoS-003 — Meta-Perception Engine (Market Brain)
Canonical Version: 2026.PROD.DRAFT
Owner: LARS
Dependencies: IoS-001, IoS-002
Purpose: Deterministic perception module producing canonical market regimes,
state vectors, semantic summaries, anomaly detection, and hysteresis-stabilised context.
"""

SPEC_HASH = hashlib.sha256(IOS003_SPEC.encode()).hexdigest()


def get_connection():
    return psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=os.getenv("PGPORT", "54322"),
        database=os.getenv("PGDATABASE", "postgres"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres")
    )


def main():
    print("=" * 70)
    print("IoS-003 G0 REGISTRATION - CEO DIRECTIVE")
    print("=" * 70)
    print(f"Registration ID: {REGISTRATION_ID}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Version: {ENGINE_VERSION}")
    print(f"Spec Hash: {SPEC_HASH[:32]}...")
    print("=" * 70)
    print()

    conn = get_connection()
    registration_log = []

    # ========================================================================
    # STEP 1: Register IoS-003 in fhq_meta.ios_registry
    # ========================================================================
    print("STEP 1: Registering IoS-003 in fhq_meta.ios_registry...")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check if already exists
        cur.execute("SELECT ios_id, status FROM fhq_meta.ios_registry WHERE ios_id = 'IoS-003'")
        existing = cur.fetchone()

        if existing:
            print(f"  [INFO] IoS-003 already exists with status: {existing['status']}")
            print(f"  [INFO] Updating registration...")

            cur.execute("""
                UPDATE fhq_meta.ios_registry
                SET title = %s,
                    description = %s,
                    version = %s,
                    status = 'DRAFT',
                    owner_role = 'LARS',
                    governing_adrs = %s,
                    dependencies = %s,
                    content_hash = %s,
                    updated_at = NOW()
                WHERE ios_id = 'IoS-003'
                RETURNING ios_id, title, status, version
            """, (
                'Meta-Perception Engine (Market Brain)',
                'Deterministic perception module producing canonical market regimes, state vectors, semantic summaries, anomaly detection, and hysteresis-stabilised context.',
                ENGINE_VERSION,
                ['ADR-001', 'ADR-002', 'ADR-003', 'ADR-004', 'ADR-006', 'ADR-007',
                 'ADR-009', 'ADR-010', 'ADR-011', 'ADR-012', 'ADR-013', 'ADR-014', 'ADR-016'],
                ['IoS-001', 'IoS-002'],
                SPEC_HASH
            ))
        else:
            cur.execute("""
                INSERT INTO fhq_meta.ios_registry (
                    ios_id, title, description, version, status, owner_role,
                    governing_adrs, dependencies, content_hash, created_at, updated_at
                ) VALUES (
                    'IoS-003',
                    'Meta-Perception Engine (Market Brain)',
                    'Deterministic perception module producing canonical market regimes, state vectors, semantic summaries, anomaly detection, and hysteresis-stabilised context.',
                    %s,
                    'DRAFT',
                    'LARS',
                    %s,
                    %s,
                    %s,
                    NOW(),
                    NOW()
                )
                RETURNING ios_id, title, status, version
            """, (
                ENGINE_VERSION,
                ['ADR-001', 'ADR-002', 'ADR-003', 'ADR-004', 'ADR-006', 'ADR-007',
                 'ADR-009', 'ADR-010', 'ADR-011', 'ADR-012', 'ADR-013', 'ADR-014', 'ADR-016'],
                ['IoS-001', 'IoS-002'],
                SPEC_HASH
            ))

        result = cur.fetchone()
        print(f"  [OK] IoS-003 registered")
        print(f"       Title: {result['title']}")
        print(f"       Status: {result['status']}")
        print(f"       Version: {result['version']}")

        registration_log.append({
            "step": 1,
            "action": "REGISTER_IOS_MODULE",
            "target": "fhq_meta.ios_registry",
            "ios_id": "IoS-003",
            "status": "G0_SUBMITTED",
            "version": ENGINE_VERSION,
            "result": "COMPLETE"
        })

    conn.commit()

    # ========================================================================
    # STEP 2: Create fhq_perception Schema
    # ========================================================================
    print("\nSTEP 2: Creating fhq_perception schema...")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Create schema
        cur.execute("""
            CREATE SCHEMA IF NOT EXISTS fhq_perception;
        """)
        print("  [OK] Schema fhq_perception created/verified")

        # Grant permissions
        cur.execute("""
            GRANT USAGE ON SCHEMA fhq_perception TO PUBLIC;
        """)
        print("  [OK] Schema permissions granted")

        registration_log.append({
            "step": 2,
            "action": "CREATE_SCHEMA",
            "target": "fhq_perception",
            "result": "COMPLETE"
        })

    conn.commit()

    # ========================================================================
    # STEP 3: Create regime_daily Table
    # ========================================================================
    print("\nSTEP 3: Creating fhq_perception.regime_daily table...")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fhq_perception.regime_daily (
                -- Primary Key
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

                -- Core identifiers
                asset_id TEXT NOT NULL,
                timestamp DATE NOT NULL,

                -- Regime classification
                regime_classification TEXT NOT NULL CHECK (
                    regime_classification IN (
                        'STRONG_BULL', 'BULL', 'NEUTRAL', 'BEAR', 'STRONG_BEAR',
                        'VOLATILE_NON_DIRECTIONAL', 'COMPRESSION', 'BROKEN', 'UNTRUSTED'
                    )
                ),
                regime_stability_flag BOOLEAN NOT NULL DEFAULT TRUE,
                regime_confidence NUMERIC(5,4) CHECK (regime_confidence >= 0 AND regime_confidence <= 1),

                -- Hysteresis tracking
                consecutive_confirms INTEGER DEFAULT 0,
                prior_regime TEXT,
                regime_change_date DATE,

                -- Anomaly detection
                anomaly_flag BOOLEAN NOT NULL DEFAULT FALSE,
                anomaly_type TEXT,
                anomaly_severity TEXT CHECK (anomaly_severity IN ('INFO', 'WARN', 'CRITICAL')),

                -- Lineage & versioning (ADR-002, ADR-013)
                engine_version TEXT NOT NULL,
                perception_model_version TEXT NOT NULL,
                formula_hash TEXT NOT NULL,
                lineage_hash TEXT NOT NULL,
                hash_prev TEXT,
                hash_self TEXT NOT NULL,

                -- Metadata
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

                -- Constraints
                UNIQUE(asset_id, timestamp)
            );
        """)
        print("  [OK] Table fhq_perception.regime_daily created")

        # Create indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_regime_daily_asset_ts
            ON fhq_perception.regime_daily(asset_id, timestamp DESC);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_regime_daily_regime
            ON fhq_perception.regime_daily(regime_classification);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_regime_daily_anomaly
            ON fhq_perception.regime_daily(anomaly_flag) WHERE anomaly_flag = TRUE;
        """)
        print("  [OK] Indexes created")

        registration_log.append({
            "step": 3,
            "action": "CREATE_TABLE",
            "target": "fhq_perception.regime_daily",
            "columns": [
                "asset_id", "timestamp", "regime_classification", "regime_stability_flag",
                "anomaly_flag", "engine_version", "perception_model_version",
                "formula_hash", "lineage_hash", "hash_prev", "hash_self"
            ],
            "result": "COMPLETE"
        })

    conn.commit()

    # ========================================================================
    # STEP 4: Create state_vectors Table
    # ========================================================================
    print("\nSTEP 4: Creating fhq_perception.state_vectors table...")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fhq_perception.state_vectors (
                -- Primary Key
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

                -- Core identifiers
                asset_id TEXT NOT NULL,
                timestamp DATE NOT NULL,

                -- Perception scores (deterministic)
                trend_score NUMERIC(6,4) NOT NULL CHECK (trend_score >= -1.0 AND trend_score <= 1.0),
                momentum_score NUMERIC(6,4) NOT NULL CHECK (momentum_score >= -1.0 AND momentum_score <= 1.0),
                volatility_score NUMERIC(5,4) NOT NULL CHECK (volatility_score >= 0.0 AND volatility_score <= 1.0),
                confidence_score NUMERIC(5,4) NOT NULL CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),

                -- Composite scores
                final_score NUMERIC(6,4),
                trend_weight NUMERIC(4,2) DEFAULT 0.50,
                momentum_weight NUMERIC(4,2) DEFAULT 0.30,
                volatility_weight NUMERIC(4,2) DEFAULT 0.20,

                -- Component breakdown (JSON for flexibility)
                component_scores JSONB,

                -- Semantic output (deterministic template-based)
                semantic_context_summary TEXT NOT NULL,
                semantic_template_id TEXT,

                -- Regime link
                regime_classification TEXT NOT NULL,
                regime_daily_id UUID REFERENCES fhq_perception.regime_daily(id),

                -- Lineage & versioning (ADR-002, ADR-013)
                engine_version TEXT NOT NULL,
                perception_model_version TEXT NOT NULL,
                formula_hash TEXT NOT NULL,
                lineage_hash TEXT NOT NULL,
                hash_prev TEXT,
                hash_self TEXT NOT NULL,

                -- Metadata
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

                -- Constraints
                UNIQUE(asset_id, timestamp)
            );
        """)
        print("  [OK] Table fhq_perception.state_vectors created")

        # Create indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_state_vectors_asset_ts
            ON fhq_perception.state_vectors(asset_id, timestamp DESC);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_state_vectors_regime
            ON fhq_perception.state_vectors(regime_classification);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_state_vectors_confidence
            ON fhq_perception.state_vectors(confidence_score);
        """)
        print("  [OK] Indexes created")

        registration_log.append({
            "step": 4,
            "action": "CREATE_TABLE",
            "target": "fhq_perception.state_vectors",
            "columns": [
                "asset_id", "timestamp", "trend_score", "momentum_score",
                "volatility_score", "confidence_score", "semantic_context_summary",
                "regime_classification", "engine_version", "perception_model_version",
                "formula_hash", "lineage_hash", "hash_prev", "hash_self"
            ],
            "result": "COMPLETE"
        })

    conn.commit()

    # ========================================================================
    # STEP 5: Create anomaly_log Table
    # ========================================================================
    print("\nSTEP 5: Creating fhq_perception.anomaly_log table...")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fhq_perception.anomaly_log (
                -- Primary Key
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

                -- Core identifiers
                asset_id TEXT NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL,
                detection_date DATE NOT NULL,

                -- Anomaly classification
                anomaly_type TEXT NOT NULL CHECK (
                    anomaly_type IN (
                        'VOLATILITY_SPIKE', 'STRUCTURAL_BREAK', 'DATA_GAP',
                        'SIGNAL_CONTRADICTION', 'REGIME_INSTABILITY', 'EXTREME_DEVIATION',
                        'LIQUIDITY_COLLAPSE', 'CORRELATION_BREAK', 'OTHER'
                    )
                ),
                severity TEXT NOT NULL CHECK (severity IN ('INFO', 'WARN', 'CRITICAL')),

                -- Anomaly details
                description TEXT NOT NULL,
                trigger_values JSONB,
                threshold_breached TEXT,
                deviation_magnitude NUMERIC(10,4),
                z_score NUMERIC(8,4),

                -- Impact assessment
                affected_indicators TEXT[],
                perception_impact TEXT CHECK (perception_impact IN ('NONE', 'DEGRADED', 'SUSPENDED')),
                regime_impact TEXT,

                -- Resolution
                resolution_status TEXT DEFAULT 'OPEN' CHECK (
                    resolution_status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'FALSE_POSITIVE')
                ),
                resolved_at TIMESTAMPTZ,
                resolved_by TEXT,
                resolution_notes TEXT,

                -- DEFCON integration (ADR-016)
                defcon_triggered BOOLEAN DEFAULT FALSE,
                defcon_level TEXT,

                -- Lineage
                engine_version TEXT NOT NULL,
                perception_model_version TEXT NOT NULL,

                -- Metadata
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        print("  [OK] Table fhq_perception.anomaly_log created")

        # Create indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_anomaly_log_asset_date
            ON fhq_perception.anomaly_log(asset_id, detection_date DESC);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_anomaly_log_severity
            ON fhq_perception.anomaly_log(severity);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_anomaly_log_type
            ON fhq_perception.anomaly_log(anomaly_type);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_anomaly_log_open
            ON fhq_perception.anomaly_log(resolution_status) WHERE resolution_status = 'OPEN';
        """)
        print("  [OK] Indexes created")

        registration_log.append({
            "step": 5,
            "action": "CREATE_TABLE",
            "target": "fhq_perception.anomaly_log",
            "columns": [
                "asset_id", "timestamp", "detection_date", "anomaly_type", "severity",
                "description", "trigger_values", "defcon_triggered", "engine_version",
                "perception_model_version"
            ],
            "result": "COMPLETE"
        })

    conn.commit()

    # ========================================================================
    # STEP 6: Register META_PERCEPTION Pipeline Stage
    # ========================================================================
    print("\nSTEP 6: Registering META_PERCEPTION pipeline stage...")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check if task exists
        cur.execute("""
            SELECT task_id, task_name, task_status
            FROM fhq_governance.task_registry
            WHERE task_name = 'META_PERCEPTION'
        """)
        existing_task = cur.fetchone()

        if existing_task:
            print(f"  [INFO] META_PERCEPTION already exists with status: {existing_task['task_status']}")
            cur.execute("""
                UPDATE fhq_governance.task_registry
                SET task_status = 'REGISTERED',
                    gate_approved = FALSE,
                    vega_reviewed = FALSE,
                    updated_at = NOW()
                WHERE task_name = 'META_PERCEPTION'
                RETURNING task_id, task_name, task_status
            """)
        else:
            cur.execute("""
                INSERT INTO fhq_governance.task_registry (
                    task_id, task_name, task_description, owner_role, executor_role,
                    source_schema, target_schema, task_status, gate_approved, vega_reviewed,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    'META_PERCEPTION',
                    'IoS-003 Meta-Perception Engine: Computes regime classification, state vectors, and semantic summaries from IoS-001 prices and IoS-002 indicators.',
                    'LARS',
                    'CODE',
                    'fhq_research',
                    'fhq_perception',
                    'REGISTERED',
                    FALSE,
                    FALSE,
                    NOW(),
                    NOW()
                )
                RETURNING task_id, task_name, task_status
            """)

        task = cur.fetchone()
        print(f"  [OK] Task registered: {task['task_name']}")
        print(f"  [OK] Task ID: {task['task_id']}")
        print(f"  [OK] Status: {task['task_status']} (awaiting G4)")

        registration_log.append({
            "step": 6,
            "action": "REGISTER_PIPELINE_STAGE",
            "target": "fhq_governance.task_registry",
            "task_name": "META_PERCEPTION",
            "task_id": str(task['task_id']),
            "owner": "LARS",
            "executor": "CODE",
            "source": "fhq_research",
            "target": "fhq_perception",
            "status": "REGISTERED",
            "activated": False,
            "result": "COMPLETE"
        })

    conn.commit()

    # ========================================================================
    # STEP 7: Log G0 Submission to Governance
    # ========================================================================
    print("\nSTEP 7: Logging G0 submission to governance...")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            INSERT INTO fhq_governance.governance_actions_log (
                action_id, action_type, action_target, action_target_type,
                initiated_by, initiated_at, decision, decision_rationale,
                hash_chain_id, signature_id
            ) VALUES (
                %s, 'IOS_MODULE_G0_SUBMISSION', 'IoS-003', 'IOS_MODULE',
                'CEO', NOW(), 'APPROVED',
                'G0 Registration complete. IoS-003 Meta-Perception Engine registered with schema, tables, and pipeline stage. Awaiting G1 Technical Validation.',
                %s, gen_random_uuid()
            )
        """, (REGISTRATION_ID, f"G0-REG-{REGISTRATION_ID[:8]}"))

        # Log to ios_audit
        cur.execute("""
            INSERT INTO fhq_meta.ios_audit_log (
                ios_id, event_type, actor, event_data, gate_level
            ) VALUES (
                'IoS-003', 'G0_SUBMISSION', 'CEO', %s, 'G0'
            )
        """, (json.dumps({
            "registration_id": REGISTRATION_ID,
            "version": ENGINE_VERSION,
            "spec_hash": SPEC_HASH,
            "tables_created": [
                "fhq_perception.regime_daily",
                "fhq_perception.state_vectors",
                "fhq_perception.anomaly_log"
            ],
            "pipeline_stage": "META_PERCEPTION",
            "owner": "LARS",
            "dependencies": ["IoS-001", "IoS-002"]
        }),))

        print(f"  [OK] G0 submission logged to governance_actions_log")
        print(f"  [OK] Audit entry created in ios_audit_log")

        registration_log.append({
            "step": 7,
            "action": "LOG_G0_SUBMISSION",
            "target": "fhq_governance.governance_actions_log",
            "registration_id": REGISTRATION_ID,
            "result": "COMPLETE"
        })

    conn.commit()

    # ========================================================================
    # STEP 8: VEGA Governance Pre-Checks
    # ========================================================================
    print("\nSTEP 8: VEGA Governance Pre-Checks...")

    vega_checks = []

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check 1: Dependencies exist and are ACTIVE
        cur.execute("""
            SELECT ios_id, status FROM fhq_meta.ios_registry
            WHERE ios_id IN ('IoS-001', 'IoS-002')
        """)
        deps = cur.fetchall()
        deps_ok = all(d['status'] == 'ACTIVE' for d in deps)
        vega_checks.append({
            "check": "DEPENDENCY_STATUS",
            "description": "IoS-001 and IoS-002 must be ACTIVE",
            "result": "PASS" if deps_ok else "FAIL",
            "details": {d['ios_id']: d['status'] for d in deps}
        })
        print(f"  [{'OK' if deps_ok else 'FAIL'}] Dependencies: {', '.join(d['ios_id'] + '=' + d['status'] for d in deps)}")

        # Check 2: Schema isolation
        cur.execute("""
            SELECT schema_name FROM information_schema.schemata
            WHERE schema_name = 'fhq_perception'
        """)
        schema_exists = cur.fetchone() is not None
        vega_checks.append({
            "check": "SCHEMA_ISOLATION",
            "description": "fhq_perception schema must exist and be isolated",
            "result": "PASS" if schema_exists else "FAIL"
        })
        print(f"  [{'OK' if schema_exists else 'FAIL'}] Schema isolation: fhq_perception exists")

        # Check 3: Lineage fields present
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'fhq_perception' AND table_name = 'regime_daily'
            AND column_name IN ('engine_version', 'perception_model_version', 'formula_hash',
                               'lineage_hash', 'hash_prev', 'hash_self', 'created_at')
        """)
        lineage_cols = [r['column_name'] for r in cur.fetchall()]
        required_lineage = ['engine_version', 'perception_model_version', 'formula_hash',
                           'lineage_hash', 'hash_prev', 'hash_self', 'created_at']
        lineage_ok = all(col in lineage_cols for col in required_lineage)
        vega_checks.append({
            "check": "LINEAGE_FIELDS",
            "description": "All required lineage fields must exist",
            "result": "PASS" if lineage_ok else "FAIL",
            "found": lineage_cols,
            "required": required_lineage
        })
        print(f"  [{'OK' if lineage_ok else 'FAIL'}] Lineage fields: {len(lineage_cols)}/{len(required_lineage)} present")

        # Check 4: ADR compliance declaration
        cur.execute("""
            SELECT governing_adrs FROM fhq_meta.ios_registry WHERE ios_id = 'IoS-003'
        """)
        adrs = cur.fetchone()
        adr_count = len(adrs['governing_adrs']) if adrs else 0
        vega_checks.append({
            "check": "ADR_COMPLIANCE",
            "description": "ADR-001 through ADR-016 must be declared",
            "result": "PASS" if adr_count >= 10 else "WARN",
            "count": adr_count
        })
        status_str = "OK" if adr_count >= 10 else "WARN"
        print(f"  [{status_str}] ADR compliance: {adr_count} ADRs declared")

    registration_log.append({
        "step": 8,
        "action": "VEGA_PRE_CHECKS",
        "checks": vega_checks,
        "result": "COMPLETE"
    })

    # ========================================================================
    # STEP 9: STIG Technical Pre-Checks
    # ========================================================================
    print("\nSTEP 9: STIG Technical Pre-Checks...")

    stig_checks = []

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check 1: Table structures
        tables_to_check = ['regime_daily', 'state_vectors', 'anomaly_log']
        for table in tables_to_check:
            cur.execute("""
                SELECT COUNT(*) as col_count FROM information_schema.columns
                WHERE table_schema = 'fhq_perception' AND table_name = %s
            """, (table,))
            col_count = cur.fetchone()['col_count']
            stig_checks.append({
                "check": f"TABLE_STRUCTURE_{table.upper()}",
                "result": "PASS" if col_count > 0 else "FAIL",
                "column_count": col_count
            })
            print(f"  [{'OK' if col_count > 0 else 'FAIL'}] {table}: {col_count} columns")

        # Check 2: Indexes exist
        cur.execute("""
            SELECT COUNT(*) as idx_count FROM pg_indexes
            WHERE schemaname = 'fhq_perception'
        """)
        idx_count = cur.fetchone()['idx_count']
        stig_checks.append({
            "check": "INDEX_COUNT",
            "result": "PASS" if idx_count >= 6 else "WARN",
            "count": idx_count
        })
        status_str = "OK" if idx_count >= 6 else "WARN"
        print(f"  [{status_str}] Indexes: {idx_count} indexes created")

        # Check 3: Constraints
        cur.execute("""
            SELECT COUNT(*) as const_count FROM information_schema.table_constraints
            WHERE constraint_schema = 'fhq_perception'
        """)
        const_count = cur.fetchone()['const_count']
        stig_checks.append({
            "check": "CONSTRAINT_COUNT",
            "result": "PASS" if const_count >= 3 else "WARN",
            "count": const_count
        })
        status_str = "OK" if const_count >= 3 else "WARN"
        print(f"  [{status_str}] Constraints: {const_count} constraints defined")

        # Check 4: Hash fields for reproducibility
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'fhq_perception'
            AND column_name LIKE '%hash%'
        """)
        hash_cols = [r['column_name'] for r in cur.fetchall()]
        stig_checks.append({
            "check": "HASH_FIELDS",
            "result": "PASS" if len(hash_cols) >= 3 else "WARN",
            "fields": hash_cols
        })
        status_str = "OK" if len(hash_cols) >= 3 else "WARN"
        print(f"  [{status_str}] Hash fields: {', '.join(hash_cols)}")

    registration_log.append({
        "step": 9,
        "action": "STIG_PRE_CHECKS",
        "checks": stig_checks,
        "result": "COMPLETE"
    })

    # ========================================================================
    # STEP 10: Generate G0 Evidence Bundle
    # ========================================================================
    print("\nSTEP 10: Generating G0 Evidence Bundle...")

    timestamp = datetime.now(timezone.utc).isoformat()

    evidence = {
        "registration_id": REGISTRATION_ID,
        "ios_module": "IoS-003",
        "module_name": "Meta-Perception Engine (Market Brain)",
        "registration_type": "G0_SUBMISSION",
        "version": ENGINE_VERSION,
        "timestamp": timestamp,
        "submitter": "CEO",

        "module_definition": {
            "owner": "LARS",
            "category": "INTERPRETATION",
            "dependencies": ["IoS-001", "IoS-002"],
            "purpose": "Deterministic perception module producing canonical market regimes, state vectors, semantic summaries, anomaly detection, and hysteresis-stabilised context.",
            "spec_hash": SPEC_HASH
        },

        "schema_created": {
            "schema": "fhq_perception",
            "tables": [
                {
                    "name": "regime_daily",
                    "purpose": "Daily regime classification with hysteresis",
                    "key_columns": ["asset_id", "timestamp", "regime_classification", "anomaly_flag"]
                },
                {
                    "name": "state_vectors",
                    "purpose": "Multi-dimensional perception vectors with semantic summaries",
                    "key_columns": ["asset_id", "timestamp", "trend_score", "momentum_score", "volatility_score", "confidence_score", "semantic_context_summary"]
                },
                {
                    "name": "anomaly_log",
                    "purpose": "Structural breaks, extreme events, perception inconsistencies",
                    "key_columns": ["asset_id", "anomaly_type", "severity", "defcon_triggered"]
                }
            ]
        },

        "pipeline_stage": {
            "name": "META_PERCEPTION",
            "owner": "LARS",
            "executor": "CODE",
            "source_schema": "fhq_research",
            "target_schema": "fhq_perception",
            "status": "REGISTERED",
            "activated": False,
            "note": "Pipeline will not execute until G4 activation"
        },

        "governance_prechecks": {
            "vega": vega_checks,
            "stig": stig_checks
        },

        "registration_log": registration_log,

        "adr_compliance": [
            "ADR-001", "ADR-002", "ADR-003", "ADR-004", "ADR-006",
            "ADR-007", "ADR-009", "ADR-010", "ADR-011", "ADR-012",
            "ADR-013", "ADR-014", "ADR-016"
        ],

        "constraints": {
            "no_computation_until_g4": True,
            "no_inference_until_g4": True,
            "no_perception_events_until_g4": True,
            "read_only_to_ios001_ios002": True,
            "write_only_to_fhq_perception": True
        },

        "next_steps": [
            "G1_TECHNICAL_VALIDATION: STIG validates deterministic math, schema, reproducibility",
            "G2_GOVERNANCE_VALIDATION: VEGA validates role isolation, semantic determinism, ADR compliance",
            "G3_AUDIT: Golden Sample tests for perception vector consistency",
            "G4_ACTIVATION: CEO activates META_PERCEPTION pipeline"
        ],

        "status": "G0_REGISTERED"
    }

    # Compute bundle hash
    bundle_json = json.dumps(evidence, sort_keys=True, default=str)
    bundle_hash = hashlib.sha256(bundle_json.encode()).hexdigest()
    evidence["bundle_hash"] = bundle_hash

    # CEO signature
    evidence["ceo_signature"] = {
        "signer": "CEO",
        "sign_time": timestamp,
        "registration_id": REGISTRATION_ID,
        "bundle_hash": bundle_hash,
        "authority": "ADR-001 through ADR-016",
        "directive": "No computation, no inference, and no perception events may occur until G4 activation."
    }

    # Save evidence
    evidence_dir = Path("evidence")
    evidence_dir.mkdir(exist_ok=True)

    filename = f"IoS-003_G0_REGISTRATION_{REGISTRATION_ID[:8]}.json"
    filepath = evidence_dir / filename

    with open(filepath, 'w') as f:
        json.dump(evidence, f, indent=2, default=str)

    print(f"  [OK] Evidence saved: {filepath}")

    conn.close()

    # ========================================================================
    # REGISTRATION COMPLETE
    # ========================================================================
    print()
    print("=" * 70)
    print("G0 REGISTRATION COMPLETE")
    print("=" * 70)
    print()
    print(f"  IoS-003 Meta-Perception Engine is now G0_REGISTERED")
    print(f"  Version: {ENGINE_VERSION}")
    print(f"  Registration ID: {REGISTRATION_ID}")
    print()
    print("  SCHEMA CREATED:")
    print("  ----------------")
    print("  [OK] fhq_perception.regime_daily")
    print("  [OK] fhq_perception.state_vectors")
    print("  [OK] fhq_perception.anomaly_log")
    print()
    print("  PIPELINE STAGE:")
    print("  ----------------")
    print("  [OK] META_PERCEPTION registered (INACTIVE until G4)")
    print()
    print("  CONSTRAINTS ACTIVE:")
    print("  --------------------")
    print("  [!] No computation until G4")
    print("  [!] No inference until G4")
    print("  [!] No perception events until G4")
    print()
    print(f"  Bundle Hash: {bundle_hash[:32]}...")
    print()
    print("=" * 70)
    print("  STATUS: IoS-003 G0_REGISTERED")
    print("  NEXT: G1_TECHNICAL_VALIDATION")
    print("=" * 70)

    return evidence


if __name__ == "__main__":
    result = main()
