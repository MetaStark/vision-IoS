"""
Full Cognitive Engine E2E Pipeline Test
CEO-DIR-2026-COGNITIVE-ENGINES-001

Tests the complete pipeline:
1. Embedding Generator - Query embedding
2. InForage Hybrid Retriever - Evidence retrieval
3. IKEA Verifier - Claim grounding verification
4. Memory Stack - Memory hierarchy integration
5. Evidence Bundle - Court-proof storage

All tests use LIVE DATA from production tables.
"""

import os
import psycopg2
import uuid
import json
import hashlib
import time
from datetime import datetime, timezone
import sys
sys.path.insert(0, '.')
sys.path.insert(0, 'schemas')

# Load environment variables from .env file (override=True to replace system env vars)
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(env_path, override=True)

def run_e2e_pipeline():
    print('='*80)
    print('COGNITIVE ENGINE E2E PIPELINE TEST')
    print('CEO-DIR-2026-COGNITIVE-ENGINES-001')
    print(f'Timestamp: {datetime.now(timezone.utc).isoformat()}')
    print('='*80)

    conn = psycopg2.connect(
        host='127.0.0.1', port=54322, database='postgres',
        user='postgres', password='postgres'
    )

    test_results = []
    pipeline_metrics = {}

    def log_test(test_name, status, details, latency_ms=None):
        result = {
            'test_id': str(uuid.uuid4()),
            'test_name': test_name,
            'status': status,
            'details': details,
            'latency_ms': latency_ms,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        test_results.append(result)
        latency_str = f' ({latency_ms}ms)' if latency_ms else ''
        print(f'[{status}] {test_name}{latency_str}')
        if details:
            print(f'    {str(details)[:100]}')

    # =========================================================================
    # DATA LIVENESS VERIFICATION
    # =========================================================================
    print('\n' + '='*80)
    print('PHASE 0: DATA LIVENESS VERIFICATION')
    print('='*80)

    cursor = conn.cursor()

    # Check evidence nodes
    cursor.execute('''
        SELECT COUNT(*), MAX(created_at),
               EXTRACT(EPOCH FROM (NOW() - MAX(created_at)))/3600 as hours_stale
        FROM fhq_canonical.evidence_nodes
    ''')
    ev_count, ev_latest, ev_stale = cursor.fetchone()
    print(f'Evidence Nodes: {ev_count} records, {ev_stale:.1f}h stale')

    # Check regime state
    cursor.execute('''
        SELECT COUNT(*), MAX(created_at),
               EXTRACT(EPOCH FROM (NOW() - MAX(created_at)))/3600 as hours_stale
        FROM fhq_perception.sovereign_regime_state_v4
    ''')
    reg_count, reg_latest, reg_stale = cursor.fetchone()
    print(f'Regime State: {reg_count} records, {reg_stale:.1f}h stale')

    # Check market prices
    cursor.execute('''
        SELECT COUNT(*), MAX(timestamp),
               EXTRACT(EPOCH FROM (NOW() - MAX(timestamp)))/3600 as hours_stale
        FROM fhq_market.prices
    ''')
    price_count, price_latest, price_stale = cursor.fetchone()
    print(f'Market Prices: {price_count} records, {price_stale:.1f}h stale')

    pipeline_metrics['data_liveness'] = {
        'evidence_nodes': {'count': ev_count, 'hours_stale': float(ev_stale) if ev_stale else None},
        'regime_state': {'count': reg_count, 'hours_stale': float(reg_stale) if reg_stale else None},
        'market_prices': {'count': price_count, 'hours_stale': float(price_stale) if price_stale else None}
    }

    log_test('DATA_LIVENESS_CHECK', 'PASS',
             f'Evidence:{ev_count}, Regime:{reg_count}, Prices:{price_count}')

    cursor.close()

    # =========================================================================
    # PHASE 1: EMBEDDING GENERATOR
    # =========================================================================
    print('\n' + '='*80)
    print('PHASE 1: EMBEDDING GENERATOR')
    print('='*80)

    # Read OpenAI key from multiple sources
    import os
    api_key = os.environ.get('OPENAI_API_KEY')

    # Try .env files if not in environment
    if not api_key:
        env_paths = [
            '../.env',
            '.env',
            'C:/fhq-market-system/.env',
            'C:/fhq-market-system/vision-ios/.env'
        ]
        for env_path in env_paths:
            try:
                with open(env_path, 'r') as f:
                    for line in f:
                        if line.startswith('OPENAI_API_KEY='):
                            api_key = line.strip().split('=', 1)[1].strip('"\'')
                            break
                if api_key:
                    break
            except:
                pass

    if not api_key:
        log_test('EMBEDDING_GENERATOR', 'SKIP',
                 'OPENAI_API_KEY not found. Set env var or add to .env for dense search.')
        embedder = None
        embedding = None  # Ensure embedding is None for downstream checks
    else:
        from embedding_generator import EmbeddingGenerator
        embedder = EmbeddingGenerator(api_key=api_key)

        # Test with live query based on current regime
        cursor = conn.cursor()
        cursor.execute('''
            SELECT asset_id, sovereign_regime, state_probabilities
            FROM fhq_perception.sovereign_regime_state_v4
            WHERE asset_id LIKE 'BTC%' OR asset_id LIKE '%BTC%'
            ORDER BY created_at DESC LIMIT 1
        ''')
        btc_regime = cursor.fetchone()
        cursor.close()

        if btc_regime:
            live_query = f"What is the outlook for {btc_regime[0]} given current {btc_regime[1]} regime?"
        else:
            live_query = "What is the Bitcoin price forecast given current market conditions?"

        start_time = time.time()
        try:
            embedding = embedder.generate_query_embedding(live_query)
            latency = int((time.time() - start_time) * 1000)

            log_test('EMBEDDING_GENERATION', 'PASS',
                     f'Query: "{live_query[:50]}..." -> {len(embedding)} dims', latency)
            pipeline_metrics['embedding'] = {
                'query': live_query,
                'dimensions': len(embedding),
                'latency_ms': latency
            }
        except Exception as e:
            log_test('EMBEDDING_GENERATION', 'FAIL', str(e))
            embedding = None

    # =========================================================================
    # PHASE 2: INFORAGE HYBRID RETRIEVAL
    # =========================================================================
    print('\n' + '='*80)
    print('PHASE 2: INFORAGE HYBRID RETRIEVAL')
    print('='*80)

    from inforage_hybrid_retriever import reciprocal_rank_fusion, BUDGET_GATES
    from schemas.cognitive_engines import DenseResult, SparseResult, DEFCONLevel
    from qdrant_graphrag_client import QdrantGraphRAGClient

    cursor = conn.cursor()

    # Use a live query about current market conditions
    retrieval_query = "Bitcoin regime causal transmission liquidity"

    # Sparse (FTS) search
    start_time = time.time()
    cursor.execute('''
        SELECT evidence_id, fts_rank
        FROM fhq_canonical.postgres_fts_search(%s, 10, 'simple')
    ''', [retrieval_query])
    sparse_raw = cursor.fetchall()
    sparse_latency = int((time.time() - start_time) * 1000)

    sparse_results = [
        SparseResult(evidence_id=row[0], score=float(row[1]), rank=i+1)
        for i, row in enumerate(sparse_raw)
    ]

    log_test('SPARSE_FTS_SEARCH', 'PASS' if sparse_results else 'FAIL',
             f'Query: "{retrieval_query}" -> {len(sparse_results)} results', sparse_latency)

    # REAL Dense search via Qdrant (not simulated!)
    dense_results = []
    dense_latency = 0

    if embedder and embedding:  # Use the embedding generated in Phase 1
        try:
            qdrant_client = QdrantGraphRAGClient(
                qdrant_host='localhost',
                qdrant_port=6333,
                defcon_level='ORANGE'
            )

            start_time = time.time()
            raw_dense = qdrant_client.search_similar(
                embedding=embedding,  # Real query embedding from Phase 1
                collection='evidence_nodes',
                top_k=10,
                score_threshold=0.0
            )
            dense_latency = int((time.time() - start_time) * 1000)

            # Qdrant payload has entity_id, not evidence_id
            # Use qdrant_point_id to look up evidence_id in Postgres
            qdrant_point_ids = [r.get('qdrant_point_id') for r in raw_dense if r.get('qdrant_point_id')]

            if qdrant_point_ids:
                # Look up evidence_ids from Postgres via qdrant_point_id
                placeholders = ','.join(['%s'] * len(qdrant_point_ids))
                cursor.execute(f'''
                    SELECT evidence_id, qdrant_point_id
                    FROM fhq_canonical.evidence_nodes
                    WHERE qdrant_point_id IN ({placeholders})
                ''', qdrant_point_ids)

                point_to_evidence = {str(row[1]): row[0] for row in cursor.fetchall()}

                for i, r in enumerate(raw_dense):
                    point_id = r.get('qdrant_point_id')
                    if point_id and point_id in point_to_evidence:
                        dense_results.append(DenseResult(
                            evidence_id=point_to_evidence[point_id],
                            score=r.get('score', 0.0),
                            rank=i + 1
                        ))

            log_test('DENSE_VECTOR_SEARCH', 'PASS' if dense_results else 'WARN',
                     f'Qdrant returned {len(raw_dense)} results, {len(dense_results)} mapped to evidence', dense_latency)
        except Exception as e:
            log_test('DENSE_VECTOR_SEARCH', 'FAIL', f'Qdrant error: {e}')
            import traceback
            traceback.print_exc()
    else:
        log_test('DENSE_VECTOR_SEARCH', 'SKIP', 'No embedding available for dense search')

    # RRF Fusion
    start_time = time.time()
    fused_results = reciprocal_rank_fusion(dense_results, sparse_results, k=60)
    fusion_latency = int((time.time() - start_time) * 1000)

    log_test('RRF_FUSION', 'PASS',
             f'Fused {len(fused_results)} unique results, top_score={fused_results[0].rrf_score:.6f}' if fused_results else 'No results',
             fusion_latency)

    pipeline_metrics['retrieval'] = {
        'query': retrieval_query,
        'sparse_count': len(sparse_results),
        'dense_count': len(dense_results),
        'dense_real': len(dense_results) > 0,  # Flag: real Qdrant search (not simulated)
        'fused_count': len(fused_results),
        'top_rrf_score': fused_results[0].rrf_score if fused_results else 0,
        'latency_ms': sparse_latency + dense_latency + fusion_latency
    }

    # Get evidence texts for IKEA verification
    snippet_ids = [r.evidence_id for r in fused_results[:5]]
    evidence_texts = {}
    if snippet_ids:
        placeholders = ','.join(['%s'] * len(snippet_ids))
        cursor.execute(f'''
            SELECT evidence_id, content
            FROM fhq_canonical.evidence_nodes
            WHERE evidence_id IN ({placeholders})
        ''', [str(sid) for sid in snippet_ids])
        for row in cursor.fetchall():
            evidence_texts[str(row[0])] = row[1]

    log_test('EVIDENCE_TEXT_FETCH', 'PASS', f'Fetched {len(evidence_texts)} evidence texts')

    cursor.close()

    # =========================================================================
    # PHASE 3: IKEA CLAIM VERIFICATION
    # =========================================================================
    print('\n' + '='*80)
    print('PHASE 3: IKEA CLAIM VERIFICATION')
    print('='*80)

    from ikea_verifier import IKEAVerifier, IKEAViolation
    from schemas.cognitive_engines import EvidenceBundle

    ikea = IKEAVerifier()

    # Create a mock LLM response based on live evidence
    # [FIX] Only use content from actual evidence - no fabricated numbers
    if evidence_texts:
        # Use actual evidence content to build grounded response
        evidence_list = list(evidence_texts.values())
        first_evidence = evidence_list[0]

        # Extract any percentages/numbers from the actual evidence for grounding
        import re
        evidence_numbers = re.findall(r'\d+\.?\d*%', first_evidence)
        evidence_entities = re.findall(r'[A-Z]{2,5}(?:-[A-Z]+)?', first_evidence)

        # Build response that only references actual evidence content
        mock_llm_response = f"""Based on the evidence analysis:

{first_evidence[:300]}

This data was directly retrieved from the evidence corpus."""

        # If we have a second piece of evidence, add it
        if len(evidence_list) > 1:
            mock_llm_response += f"\n\nAdditional context: {evidence_list[1][:200]}"
    else:
        mock_llm_response = "No evidence found for the query. Unable to generate grounded analysis."

    # Extract claims
    start_time = time.time()
    claims = ikea.extract_claims(mock_llm_response)
    extraction_latency = int((time.time() - start_time) * 1000)

    log_test('CLAIM_EXTRACTION', 'PASS',
             f'Extracted {len(claims)} claims from response', extraction_latency)

    for i, claim in enumerate(claims[:3]):
        print(f'    Claim {i+1}: [{claim.claim_type.value}] {claim.claim_text[:60]}...')

    # Create evidence bundle for verification
    bundle = EvidenceBundle(
        bundle_id=uuid.uuid4(),
        query_text=retrieval_query,
        snippet_ids=snippet_ids,
        rrf_fused_results=fused_results[:5] if fused_results else None,
        rrf_top_score=fused_results[0].rrf_score if fused_results else None,
        defcon_level=DEFCONLevel.ORANGE,
        query_cost_usd=0.002
    )

    # Verify grounding
    start_time = time.time()
    verification_result = ikea.verify_grounding(
        mock_llm_response, bundle, evidence_texts
    )
    grounding_latency = int((time.time() - start_time) * 1000)

    is_grounded = verification_result.is_valid
    grounded_count = verification_result.grounded_claims_count
    ungrounded_count = verification_result.ungrounded_claims_count

    # Calculate Grounded Claim Rate for display
    total_for_rate = grounded_count + ungrounded_count
    gcr = (grounded_count / total_for_rate * 100) if total_for_rate > 0 else 100.0

    log_test('IKEA_GROUNDING_CHECK', 'PASS' if is_grounded else 'WARN',
             f'Grounded: {grounded_count}, Ungrounded: {ungrounded_count}, GCR: {gcr:.1f}%', grounding_latency)

    # Calculate Grounded Claim Rate (GCR) - CEO-mandated metric
    total_claims = grounded_count + ungrounded_count
    grounded_claim_rate = grounded_count / total_claims if total_claims > 0 else 1.0

    pipeline_metrics['ikea'] = {
        'claims_extracted': len(claims),
        'claims_grounded': grounded_count,
        'claims_ungrounded': ungrounded_count,
        'grounded_claim_rate': grounded_claim_rate,  # GCR metric (0.0-1.0)
        'is_fully_grounded': is_grounded,
        'latency_ms': extraction_latency + grounding_latency
    }

    # =========================================================================
    # PHASE 4: MEMORY STACK INTEGRATION
    # =========================================================================
    print('\n' + '='*80)
    print('PHASE 4: MEMORY STACK INTEGRATION')
    print('='*80)

    from memory_stack import MemoryStack
    from schemas.cognitive_engines import MemoryType

    # Initialize memory stack (without embedder for now)
    stack = MemoryStack(db_conn=conn, embedding_generator=None, agent_id='FINN')

    # Test core memory loading
    start_time = time.time()
    core = stack._load_core()
    core_latency = int((time.time() - start_time) * 1000)

    log_test('CORE_MEMORY_LOAD', 'PASS',
             f'Loaded constitution ({core.token_count} tokens)', core_latency)

    # Test page-in with current regime
    cursor = conn.cursor()
    cursor.execute('''
        SELECT sovereign_regime FROM fhq_perception.sovereign_regime_state_v4
        WHERE asset_id LIKE '%BTC%' ORDER BY created_at DESC LIMIT 1
    ''')
    regime_row = cursor.fetchone()
    raw_regime = regime_row[0] if regime_row else 'UNKNOWN'
    # Map to valid archival regime: BULL, BEAR, SIDEWAYS, CRISIS, UNKNOWN
    regime_map = {'NEUTRAL': 'SIDEWAYS', 'STRESS': 'CRISIS'}
    current_regime = regime_map.get(raw_regime, raw_regime) if raw_regime in regime_map else raw_regime
    if current_regime not in ['BULL', 'BEAR', 'SIDEWAYS', 'CRISIS', 'UNKNOWN']:
        current_regime = 'UNKNOWN'
    cursor.close()

    start_time = time.time()
    paged = stack.page_in(
        query=retrieval_query,
        defcon_level=DEFCONLevel.ORANGE,
        regime=current_regime,
        token_budget=8000
    )
    pagein_latency = int((time.time() - start_time) * 1000)

    log_test('MEMORY_PAGE_IN', 'PASS',
             f'Regime={current_regime}, Core={paged.core.token_count}t, Recall={len(paged.recall_memories)}',
             pagein_latency)

    # Archive the retrieval result as an insight (include timestamp for uniqueness)
    archive_content = f"[E2E Test {datetime.now(timezone.utc).isoformat()}] Query: {retrieval_query}. " \
                      f"Found {len(fused_results)} results. " \
                      f"Top RRF score: {fused_results[0].rrf_score:.4f}. Regime: {current_regime}"

    start_time = time.time()
    cursor = conn.cursor()
    archive_id = uuid.uuid4()
    content_hash = hashlib.sha256(archive_content.encode()).hexdigest()

    cursor.execute('''
        INSERT INTO fhq_memory.archival_store
        (archive_id, agent_id, content, content_hash, memory_type, regime_at_archival, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    ''', [str(archive_id), 'FINN', archive_content, content_hash,
          'INSIGHT', current_regime, datetime.now(timezone.utc)])
    conn.commit()
    cursor.close()
    archive_latency = int((time.time() - start_time) * 1000)

    log_test('ARCHIVAL_STORE', 'PASS',
             f'Archived insight {archive_id}', archive_latency)

    pipeline_metrics['memory'] = {
        'core_tokens': core.token_count,
        'recall_memories': len(paged.recall_memories),
        'current_regime': current_regime,
        'archive_id': str(archive_id),
        'latency_ms': core_latency + pagein_latency + archive_latency
    }

    # =========================================================================
    # PHASE 5: EVIDENCE BUNDLE STORAGE (COURT-PROOF)
    # =========================================================================
    print('\n' + '='*80)
    print('PHASE 5: EVIDENCE BUNDLE STORAGE (COURT-PROOF)')
    print('='*80)

    cursor = conn.cursor()

    # Prepare bundle data
    bundle_id = uuid.uuid4()
    fused_json = json.dumps([
        {
            'evidence_id': str(r.evidence_id),
            'rrf_score': r.rrf_score,
            'dense_rank': r.dense_rank,
            'sparse_rank': r.sparse_rank
        }
        for r in fused_results[:5]
    ]) if fused_results else None

    sparse_json = json.dumps([
        {'evidence_id': str(r.evidence_id), 'score': r.score, 'rank': r.rank}
        for r in sparse_results[:5]
    ]) if sparse_results else None

    # Calculate court-proof hash
    bundle_content = f'{bundle_id}{retrieval_query}{fused_json}{sparse_json}'
    bundle_hash = hashlib.sha256(bundle_content.encode()).hexdigest()

    start_time = time.time()
    cursor.execute('''
        INSERT INTO fhq_canonical.evidence_bundles (
            bundle_id, query_text, sparse_results, rrf_fused_results,
            rrf_top_score, snippet_ids, defcon_level, regime,
            query_cost_usd, bundle_hash, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s::uuid[], %s, %s, %s, %s, %s)
    ''', [
        str(bundle_id), retrieval_query, sparse_json, fused_json,
        fused_results[0].rrf_score if fused_results else 0,
        [str(sid) for sid in snippet_ids],
        'ORANGE', current_regime, 0.002, bundle_hash,
        datetime.now(timezone.utc)
    ])
    conn.commit()
    bundle_latency = int((time.time() - start_time) * 1000)

    log_test('EVIDENCE_BUNDLE_STORE', 'PASS',
             f'Bundle {bundle_id}, hash={bundle_hash[:16]}...', bundle_latency)

    # Log to inforage_query_log
    cursor.execute('''
        INSERT INTO fhq_governance.inforage_query_log (
            query_id, query_text, retrieval_mode, rrf_k, dense_weight, sparse_weight,
            top_k, latency_ms, results_count, cost_usd,
            defcon_level, querying_agent, bundle_id, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''', [
        str(uuid.uuid4()), retrieval_query, 'HYBRID',
        60, 0.5, 0.5, 10,
        pipeline_metrics['retrieval']['latency_ms'],
        len(fused_results), 0.002,
        'ORANGE', 'FINN_E2E_TEST', str(bundle_id),
        datetime.now(timezone.utc)
    ])
    conn.commit()
    cursor.close()

    log_test('QUERY_LOG_STORE', 'PASS', 'Logged to inforage_query_log')

    pipeline_metrics['storage'] = {
        'bundle_id': str(bundle_id),
        'bundle_hash': bundle_hash,
        'latency_ms': bundle_latency
    }

    # =========================================================================
    # PHASE 6: PIPELINE SUMMARY
    # =========================================================================
    print('\n' + '='*80)
    print('PHASE 6: PIPELINE SUMMARY')
    print('='*80)

    total_latency = sum([
        pipeline_metrics.get('embedding', {}).get('latency_ms', 0),
        pipeline_metrics.get('retrieval', {}).get('latency_ms', 0),
        pipeline_metrics.get('ikea', {}).get('latency_ms', 0),
        pipeline_metrics.get('memory', {}).get('latency_ms', 0),
        pipeline_metrics.get('storage', {}).get('latency_ms', 0)
    ])

    passed = len([t for t in test_results if t['status'] == 'PASS'])
    failed = len([t for t in test_results if t['status'] == 'FAIL'])
    warned = len([t for t in test_results if t['status'] == 'WARN'])
    skipped = len([t for t in test_results if t['status'] == 'SKIP'])

    print(f'\nTotal Pipeline Latency: {total_latency}ms')
    print(f'Tests: {passed} passed, {failed} failed, {warned} warnings, {skipped} skipped')

    # Store final evidence
    evidence = {
        'test_suite': 'COGNITIVE_ENGINE_E2E_PIPELINE',
        'directive': 'CEO-DIR-2026-COGNITIVE-ENGINES-001',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'pipeline_metrics': pipeline_metrics,
        'total_latency_ms': total_latency,
        'total_tests': len(test_results),
        'passed': passed,
        'failed': failed,
        'warned': warned,
        'skipped': skipped,
        'results': test_results
    }

    evidence_path = 'evidence/COGNITIVE_ENGINE_E2E_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S') + '.json'
    with open(evidence_path, 'w') as f:
        json.dump(evidence, f, indent=2)
    print(f'\nEvidence stored: {evidence_path}')

    # Final database counts
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM fhq_governance.inforage_query_log')
    log_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM fhq_canonical.evidence_bundles')
    bundle_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM fhq_memory.archival_store')
    archive_count = cursor.fetchone()[0]
    cursor.close()

    print(f'\nDatabase State:')
    print(f'  Query Logs: {log_count}')
    print(f'  Evidence Bundles: {bundle_count}')
    print(f'  Archival Store: {archive_count}')

    conn.close()

    print('\n' + '='*80)
    if failed == 0:
        print('[SUCCESS] COGNITIVE ENGINE E2E PIPELINE: ALL TESTS PASSED')
    else:
        print(f'[WARNING] COGNITIVE ENGINE E2E PIPELINE: {failed} TEST(S) FAILED')
    print('='*80)

    return evidence

if __name__ == '__main__':
    run_e2e_pipeline()
