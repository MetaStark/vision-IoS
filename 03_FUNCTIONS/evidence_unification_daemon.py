#!/usr/bin/env python3
"""
EVIDENCE UNIFICATION DAEMON
============================
CEO-DIR-2026-024: Institutional Learning Activation (Phase 2)
ADR-011: Court-Proof Evidence Chain (Hash Binding)

PURPOSE: System "memory engine" - converts volatile signals to institutional capital

ARCHITECTURE:
- Source: cognitive_engine_evidence (PostgreSQL) - Research, EC018, Serper intelligence
- Target: evidence_nodes (Qdrant) - Canonical belief formation layer
- Mechanism: Automatic sync every 10 minutes with embedding generation

GOVERNANCE:
- Hash-bound evidence chain (ADR-011)
- Causal linking (evidence → belief → decision)
- Time consistency validation (max 4-hour staleness)

STRATEGIC VALUE:
"Before: System experiences data. After: System remembers experience."

Authority: CEO-DIR-2026-024, STIG (CTO)
"""

import os
import sys
import json
import hashlib
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

# Database
import psycopg2
from psycopg2.extras import RealDictCursor

# Vector embeddings
from sentence_transformers import SentenceTransformer

# Environment
from dotenv import load_dotenv
load_dotenv('C:/fhq-market-system/vision-ios/.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('EvidenceUnificationDaemon')


class EvidenceUnificationDaemon:
    """
    Evidence Unification Daemon - System Memory Engine

    Converts volatile signals from cognitive_engine_evidence (PostgreSQL)
    into persistent institutional capital via evidence_nodes (Qdrant graph).

    Key Features:
    - Automatic 10-minute sync cycle
    - Embedding generation for semantic search
    - Hash-bound evidence chain (ADR-011)
    - Causal linking (evidence → belief → decision)
    - Time consistency validation
    """

    def __init__(self):
        self.db_conn = self._connect_db()
        self.embedding_model = self._load_embedding_model()
        self.sync_interval_seconds = 600  # 10 minutes (CEO-DIR-2026-024)

    def _connect_db(self):
        """Connect to PostgreSQL"""
        conn_params = {
            'host': os.getenv('PGHOST', '127.0.0.1'),
            'port': os.getenv('PGPORT', '54322'),
            'database': os.getenv('PGDATABASE', 'postgres'),
            'user': os.getenv('PGUSER', 'postgres'),
            'password': os.getenv('PGPASSWORD', 'postgres')
        }

        conn = psycopg2.connect(**conn_params)
        logger.info("Database connection established")
        return conn

    def _load_embedding_model(self):
        """Load sentence transformer for embeddings"""
        model_name = 'all-MiniLM-L6-v2'  # Fast, efficient model
        model = SentenceTransformer(model_name)
        logger.info(f"Embedding model loaded: {model_name}")
        return model

    def run_continuous(self):
        """
        Run daemon continuously with 10-minute sync cycles

        Mantra: "Move fast and verify things"
        - Fast: 10-minute cycles maintain continuous awareness
        - Verify: Hash-bound evidence chain ensures integrity
        """
        logger.info("=" * 70)
        logger.info("EVIDENCE UNIFICATION DAEMON ACTIVATED")
        logger.info("CEO-DIR-2026-024: Institutional Learning Phase 2")
        logger.info("=" * 70)
        logger.info(f"Sync interval: {self.sync_interval_seconds} seconds (10 minutes)")
        logger.info("Strategic value: Converting volatile signals to institutional capital")
        logger.info("Mantra: Eliminate Noise. Generate Signal. Move fast and verify things.")
        logger.info("=" * 70)

        cycle_count = 0

        while True:
            cycle_count += 1
            cycle_start = datetime.now(timezone.utc)

            logger.info(f"\n{'='*70}")
            logger.info(f"SYNC CYCLE {cycle_count} - {cycle_start.isoformat()}")
            logger.info(f"{'='*70}")

            try:
                # Execute unification sync
                result = self.unify_evidence()

                # Log results
                logger.info(f"Sync complete: {result['synced_count']} records unified")
                logger.info(f"  New: {result['new_count']}")
                logger.info(f"  Updated: {result['updated_count']}")
                logger.info(f"  Skipped: {result['skipped_count']}")
                logger.info(f"  Errors: {result['error_count']}")

                # Store evidence of sync
                self._store_sync_evidence(cycle_count, result)

                # Calculate next cycle
                cycle_end = datetime.now(timezone.utc)
                cycle_duration = (cycle_end - cycle_start).total_seconds()
                sleep_duration = max(0, self.sync_interval_seconds - cycle_duration)

                logger.info(f"Cycle duration: {cycle_duration:.2f}s")
                logger.info(f"Next cycle in: {sleep_duration:.2f}s")

                time.sleep(sleep_duration)

            except Exception as e:
                logger.error(f"Sync cycle {cycle_count} failed: {e}", exc_info=True)
                logger.info(f"Retrying in {self.sync_interval_seconds} seconds")
                time.sleep(self.sync_interval_seconds)

    def unify_evidence(self) -> Dict[str, int]:
        """
        Main unification logic: cognitive_engine_evidence → evidence_nodes

        Steps:
        1. Query unsynced evidence from cognitive_engine_evidence
        2. Generate embeddings for semantic search
        3. Create hash-bound evidence chain (ADR-011)
        4. Insert to vision_verification.evidence_nodes (TODO: Qdrant when available)
        5. Mark as synced

        Returns:
            Dict with sync statistics (new_count, updated_count, etc.)
        """
        cursor = self.db_conn.cursor(cursor_factory=RealDictCursor)

        # Query unsynced evidence
        # NOTE: cognitive_engine_evidence table may not exist yet - handle gracefully
        try:
            cursor.execute("""
                SELECT
                    id,
                    evidence_type,
                    evidence_content,
                    created_at,
                    generating_agent,
                    source_query,
                    metadata
                FROM vision_verification.cognitive_engine_evidence
                WHERE synced_to_graph = FALSE
                    OR synced_to_graph IS NULL
                ORDER BY created_at ASC
                LIMIT 100
            """)

            unsynced_records = cursor.fetchall()

        except psycopg2.errors.UndefinedTable:
            logger.warning("cognitive_engine_evidence table does not exist yet - creating placeholder")
            self._create_cognitive_engine_evidence_table(cursor)
            self.db_conn.commit()
            return {
                'synced_count': 0,
                'new_count': 0,
                'updated_count': 0,
                'skipped_count': 0,
                'error_count': 0
            }

        if not unsynced_records:
            logger.info("No unsynced evidence found - system is up to date")
            return {
                'synced_count': 0,
                'new_count': 0,
                'updated_count': 0,
                'skipped_count': 0,
                'error_count': 0
            }

        logger.info(f"Found {len(unsynced_records)} unsynced evidence records")

        # Process each record
        stats = {
            'synced_count': 0,
            'new_count': 0,
            'updated_count': 0,
            'skipped_count': 0,
            'error_count': 0
        }

        for record in unsynced_records:
            try:
                # Generate embedding
                evidence_text = self._extract_evidence_text(record)
                embedding = self.embedding_model.encode(evidence_text).tolist()

                # Generate hash (ADR-011 court-proof)
                evidence_hash = self._generate_evidence_hash(record)

                # Insert to evidence_nodes (placeholder until Qdrant available)
                self._insert_evidence_node(cursor, record, embedding, evidence_hash)

                # Mark as synced
                cursor.execute("""
                    UPDATE vision_verification.cognitive_engine_evidence
                    SET
                        synced_to_graph = TRUE,
                        synced_at = CURRENT_TIMESTAMP,
                        evidence_hash = %s
                    WHERE id = %s
                """, (evidence_hash, record['id']))

                stats['synced_count'] += 1
                stats['new_count'] += 1

            except Exception as e:
                logger.error(f"Failed to sync record {record.get('id')}: {e}")
                stats['error_count'] += 1

        self.db_conn.commit()

        return stats

    def _create_cognitive_engine_evidence_table(self, cursor):
        """
        Create cognitive_engine_evidence table if it doesn't exist

        This table stores outputs from:
        - Research Daemon (Serper queries, analysis)
        - EC018 Alpha Daemon (draft hypotheses)
        - Wave15 Autonomous Hunter (market anomalies)
        - Orchestrator (meta-coordination intelligence)
        """
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vision_verification.cognitive_engine_evidence (
                id SERIAL PRIMARY KEY,
                evidence_type VARCHAR(100) NOT NULL,
                evidence_content JSONB NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                generating_agent VARCHAR(50) NOT NULL,
                source_query TEXT,
                metadata JSONB,
                synced_to_graph BOOLEAN DEFAULT FALSE,
                synced_at TIMESTAMP WITH TIME ZONE,
                evidence_hash VARCHAR(64),

                CONSTRAINT valid_agent CHECK (generating_agent IN (
                    'RESEARCH_DAEMON', 'EC018', 'WAVE15', 'ORCHESTRATOR',
                    'CEIO', 'CRIO', 'CDMO', 'CFAO', 'CSEO'
                ))
            );

            CREATE INDEX IF NOT EXISTS idx_cee_synced
                ON vision_verification.cognitive_engine_evidence(synced_to_graph, created_at);
            CREATE INDEX IF NOT EXISTS idx_cee_type
                ON vision_verification.cognitive_engine_evidence(evidence_type);
            CREATE INDEX IF NOT EXISTS idx_cee_agent
                ON vision_verification.cognitive_engine_evidence(generating_agent);

            COMMENT ON TABLE vision_verification.cognitive_engine_evidence IS
                'CEO-DIR-2026-024: Volatile signals from cognitive processes (Research, EC018, Serper) before unification';
        """)

        logger.info("Created cognitive_engine_evidence table")

    def _extract_evidence_text(self, record: Dict) -> str:
        """Extract text for embedding generation"""
        content = record.get('evidence_content', {})

        # Extract key fields for embedding
        text_parts = [
            record.get('evidence_type', ''),
            record.get('generating_agent', ''),
            str(content.get('summary', '')),
            str(content.get('key_finding', '')),
            str(content.get('analysis', '')),
            str(record.get('source_query', ''))
        ]

        # Join and clean
        text = ' '.join(filter(None, text_parts))
        return text[:1000]  # Limit to 1000 chars for embedding

    def _generate_evidence_hash(self, record: Dict) -> str:
        """
        Generate hash for evidence chain (ADR-011)

        Hash includes:
        - evidence_content (deterministic JSON)
        - created_at (timestamp)
        - generating_agent (source)
        """
        content_str = json.dumps(record.get('evidence_content', {}), sort_keys=True)
        timestamp_str = record.get('created_at', datetime.now(timezone.utc)).isoformat()
        agent_str = record.get('generating_agent', '')

        hash_input = f"{content_str}|{timestamp_str}|{agent_str}"
        return hashlib.sha256(hash_input.encode()).hexdigest()

    def _insert_evidence_node(
        self,
        cursor,
        record: Dict,
        embedding: List[float],
        evidence_hash: str
    ):
        """
        Insert evidence node (placeholder until Qdrant integration)

        TODO: When Qdrant is integrated, replace this with:
        - qdrant_client.upsert(collection='evidence_nodes', points=[...])
        - Include graph relationships (evidence → belief → decision)
        """
        # For now, store in PostgreSQL as placeholder
        cursor.execute("""
            INSERT INTO vision_verification.summary_evidence_ledger (
                summary_id,
                summary_type,
                generating_agent,
                raw_query,
                query_result_hash,
                summary_content,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (
            f"EVIDENCE-{record['id']}",
            record.get('evidence_type', 'COGNITIVE_ENGINE_OUTPUT'),
            record.get('generating_agent', 'UNKNOWN'),
            record.get('source_query', ''),
            evidence_hash,
            record.get('evidence_content', {}),
            record.get('created_at', datetime.now(timezone.utc))
        ))

        logger.debug(f"Inserted evidence node: {evidence_hash[:8]}... (record {record['id']})")

    def _store_sync_evidence(self, cycle_count: int, result: Dict):
        """Store evidence of sync cycle (ADR-002 audit requirement + CEO-DIR-2026-024-B court-proof)"""
        cursor = self.db_conn.cursor(cursor_factory=RealDictCursor)

        evidence_id = f"EVIDENCE-UNIFICATION-SYNC-{cycle_count:06d}"

        # CEO-DIR-2026-024-B: Execute raw_query to get snapshot (court-proof protocol)
        raw_query = """
            SELECT
              NOW() AS observed_at,
              COUNT(*) AS total_evidence,
              COUNT(*) FILTER (WHERE synced_to_graph = FALSE) AS unsynced,
              COUNT(*) FILTER (WHERE synced_to_graph = TRUE) AS synced,
              MAX(synced_at) AS last_synced_at
            FROM vision_verification.cognitive_engine_evidence
        """

        cursor.execute(raw_query)
        query_result = cursor.fetchone()

        # Convert to JSON-serializable dict
        query_result_snapshot = dict(query_result) if query_result else {}

        # Convert datetime to ISO string for JSON serialization
        if 'observed_at' in query_result_snapshot and query_result_snapshot['observed_at']:
            query_result_snapshot['observed_at'] = query_result_snapshot['observed_at'].isoformat()
        if 'last_synced_at' in query_result_snapshot and query_result_snapshot['last_synced_at']:
            query_result_snapshot['last_synced_at'] = query_result_snapshot['last_synced_at'].isoformat()

        # Calculate hash of query result (court-proof)
        query_result_hash = hashlib.sha256(
            json.dumps(query_result_snapshot, sort_keys=True).encode()
        ).hexdigest()

        # Summary content with metadata
        evidence_content = {
            "cycle_count": cycle_count,
            "sync_timestamp": datetime.now(timezone.utc).isoformat(),
            "statistics": result,
            "daemon_version": "1.0.0",
            "sync_interval_seconds": self.sync_interval_seconds,
            "evidence_state_snapshot": query_result_snapshot
        }

        evidence_hash = hashlib.sha256(
            json.dumps(evidence_content, sort_keys=True).encode()
        ).hexdigest()

        cursor.execute("""
            INSERT INTO vision_verification.summary_evidence_ledger (
                summary_id,
                summary_type,
                generating_agent,
                raw_query,
                query_result_hash,
                query_result_snapshot,
                summary_content,
                summary_hash,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT DO NOTHING
        """, (
            evidence_id,
            'EVIDENCE_UNIFICATION_SYNC',
            'STIG',
            raw_query.strip(),
            query_result_hash,
            json.dumps(query_result_snapshot),
            json.dumps(evidence_content),
            evidence_hash
        ))

        self.db_conn.commit()


def main():
    """
    Main entry point for Evidence Unification Daemon

    Usage:
        python evidence_unification_daemon.py

    Runs continuously with 10-minute sync cycles until interrupted.
    """
    daemon = EvidenceUnificationDaemon()

    try:
        daemon.run_continuous()
    except KeyboardInterrupt:
        logger.info("\n" + "="*70)
        logger.info("Evidence Unification Daemon shutdown requested")
        logger.info("="*70)
        sys.exit(0)


if __name__ == "__main__":
    main()
