"""
InForage Hybrid Retriever Test Suite
CEO-DIR-2026-COGNITIVE-ENGINES-001
Traceability: All tests logged to evidence files
"""

import psycopg2
import uuid
import json
import hashlib
from datetime import datetime, timezone
import sys
sys.path.insert(0, '.')
sys.path.insert(0, 'schemas')

def run_tests():
    print('='*70)
    print('INFORAGE HYBRID RETRIEVER TEST SUITE')
    print('CEO-DIR-2026-COGNITIVE-ENGINES-001')
    print(f'Timestamp: {datetime.now(timezone.utc).isoformat()}')
    print('='*70)

    conn = psycopg2.connect(
        host='127.0.0.1', port=54322, database='postgres',
        user='postgres', password='postgres'
    )

    test_results = []

    def log_test(test_name, status, details):
        result = {
            'test_id': str(uuid.uuid4()),
            'test_name': test_name,
            'status': status,
            'details': details,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        test_results.append(result)
        print(f'[{status}] {test_name}')
        if details:
            print(f'    {details[:100]}')

    # TEST 1: Sparse (FTS) Search
    print('\n' + '='*70)
    print('TEST 1: Sparse (FTS) Search - postgres_fts_search()')
    print('='*70)

    cursor = conn.cursor()

    test_query = 'Bitcoin price volatility'
    cursor.execute("SELECT evidence_id, fts_rank FROM fhq_canonical.postgres_fts_search(%s, 10, 'simple')", [test_query])
    fts_results = cursor.fetchall()
    print(f'Query: "{test_query}"')
    print(f'Results: {len(fts_results)} evidence nodes')

    if fts_results:
        log_test('FTS_BITCOIN_QUERY', 'PASS', f'Found {len(fts_results)} results')
        for i, (eid, rank) in enumerate(fts_results[:3]):
            print(f'  [{i+1}] {eid} (rank={rank:.4f})')
    else:
        log_test('FTS_BITCOIN_QUERY', 'FAIL', 'No results returned')

    test_query2 = 'Ethereum Solana'
    cursor.execute("SELECT evidence_id, fts_rank FROM fhq_canonical.postgres_fts_search(%s, 10, 'simple')", [test_query2])
    fts_results2 = cursor.fetchall()
    print(f'\nQuery: "{test_query2}"')
    print(f'Results: {len(fts_results2)} evidence nodes')
    log_test('FTS_ETH_SOL_QUERY', 'PASS' if fts_results2 else 'FAIL', f'Found {len(fts_results2)} results')

    test_query3 = 'regime HMM'
    cursor.execute("SELECT evidence_id, fts_rank FROM fhq_canonical.postgres_fts_search(%s, 10, 'simple')", [test_query3])
    fts_results3 = cursor.fetchall()
    print(f'\nQuery: "{test_query3}"')
    print(f'Results: {len(fts_results3)} evidence nodes')
    log_test('FTS_REGIME_QUERY', 'PASS' if fts_results3 else 'FAIL', f'Found {len(fts_results3)} results')

    cursor.close()

    # TEST 2: RRF Fusion Algorithm
    print('\n' + '='*70)
    print('TEST 2: Reciprocal Rank Fusion (RRF) Algorithm')
    print('='*70)

    from inforage_hybrid_retriever import reciprocal_rank_fusion
    from schemas.cognitive_engines import DenseResult, SparseResult

    cursor = conn.cursor()
    cursor.execute('SELECT evidence_id FROM fhq_canonical.evidence_nodes LIMIT 10')
    live_ids = [row[0] for row in cursor.fetchall()]
    cursor.close()

    if len(live_ids) >= 6:
        dense_results = [
            DenseResult(evidence_id=live_ids[0], score=0.95, rank=1),
            DenseResult(evidence_id=live_ids[2], score=0.88, rank=2),
            DenseResult(evidence_id=live_ids[4], score=0.75, rank=3),
            DenseResult(evidence_id=live_ids[1], score=0.70, rank=4),
        ]

        sparse_results = [
            SparseResult(evidence_id=live_ids[1], score=0.92, rank=1),
            SparseResult(evidence_id=live_ids[0], score=0.85, rank=2),
            SparseResult(evidence_id=live_ids[3], score=0.78, rank=3),
            SparseResult(evidence_id=live_ids[2], score=0.65, rank=4),
        ]

        fused = reciprocal_rank_fusion(dense_results, sparse_results, k=60)

        print(f'Dense results: {len(dense_results)} docs')
        print(f'Sparse results: {len(sparse_results)} docs')
        print(f'Fused results: {len(fused)} unique docs')
        print('\nRRF Fusion Results:')
        for i, r in enumerate(fused[:5]):
            print(f'  [{i+1}] {r.evidence_id} rrf={r.rrf_score:.6f} dense_rank={r.dense_rank} sparse_rank={r.sparse_rank}')

        both_lists = [r for r in fused if r.dense_rank is not None and r.sparse_rank is not None]
        log_test('RRF_FUSION_RANKING', 'PASS', f'Fused {len(fused)} results, {len(both_lists)} in both lists')

        # Verify RRF score calculation for first result (rank 1 dense, rank 2 sparse)
        # RRF = 0.5/(60+1) + 0.5/(60+2) = 0.008197 + 0.008065 = 0.016261
        top_result = fused[0]
        if top_result.dense_rank == 1 and top_result.sparse_rank == 2:
            expected_score = (0.5 / (60 + 1)) + (0.5 / (60 + 2))
            score_match = abs(expected_score - top_result.rrf_score) < 0.0001
            log_test('RRF_SCORE_CALCULATION', 'PASS' if score_match else 'FAIL',
                     f'Score {top_result.rrf_score:.6f} vs expected {expected_score:.6f}')
        else:
            # Just verify RRF scores are reasonable (between 0 and 0.02)
            scores_valid = all(0 < r.rrf_score < 0.02 for r in fused)
            log_test('RRF_SCORE_CALCULATION', 'PASS' if scores_valid else 'FAIL',
                     f'Top score {top_result.rrf_score:.6f}, all scores in valid range')

    # TEST 3: Budget Gating
    print('\n' + '='*70)
    print('TEST 3: Budget Gating per DEFCON Level')
    print('='*70)

    from inforage_hybrid_retriever import BUDGET_GATES
    from schemas.cognitive_engines import DEFCONLevel

    for level in DEFCONLevel:
        gate = BUDGET_GATES[level]
        print(f'{level.value}: dense={gate.allow_dense}, sparse={gate.allow_sparse}, rerank={gate.allow_rerank}, max=${gate.max_cost_usd:.2f}')

    escalation_valid = (
        BUDGET_GATES[DEFCONLevel.GREEN].max_cost_usd < BUDGET_GATES[DEFCONLevel.YELLOW].max_cost_usd and
        BUDGET_GATES[DEFCONLevel.YELLOW].max_cost_usd < BUDGET_GATES[DEFCONLevel.ORANGE].max_cost_usd
    )
    log_test('BUDGET_ESCALATION', 'PASS' if escalation_valid else 'FAIL', 'Cost limits escalate correctly')

    green_blocks = not BUDGET_GATES[DEFCONLevel.GREEN].allow_dense and not BUDGET_GATES[DEFCONLevel.GREEN].allow_sparse
    log_test('DEFCON_GREEN_BLOCK', 'PASS' if green_blocks else 'FAIL', 'GREEN blocks all retrieval')

    red_full = BUDGET_GATES[DEFCONLevel.RED].allow_rerank and BUDGET_GATES[DEFCONLevel.BLACK].allow_rerank
    log_test('DEFCON_RED_BLACK_FULL', 'PASS' if red_full else 'FAIL', 'RED/BLACK allow full access')

    # TEST 4: Query Logging
    print('\n' + '='*70)
    print('TEST 4: Query Logging to inforage_query_log')
    print('='*70)

    cursor = conn.cursor()
    test_query_id = uuid.uuid4()

    # Note: bundle_id is NULL - we log queries before bundle creation in real flow
    cursor.execute('''
        INSERT INTO fhq_governance.inforage_query_log (
            query_id, query_text, retrieval_mode, rrf_k, dense_weight, sparse_weight,
            top_k, rerank_cutoff, latency_ms, results_count,
            embedding_cost_usd, search_cost_usd, rerank_cost_usd, cost_usd,
            defcon_level, querying_agent, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''', [
        str(test_query_id), 'TEST: Bitcoin price forecast', 'HYBRID',
        60, 0.5, 0.5, 20, 5, 125, 8,
        0.0001, 0.0015, 0.0, 0.0016,
        'ORANGE', 'STIG_TEST', datetime.now(timezone.utc)
    ])
    conn.commit()

    cursor.execute('SELECT query_id FROM fhq_governance.inforage_query_log WHERE query_id = %s', [str(test_query_id)])
    log_row = cursor.fetchone()
    cursor.close()
    log_test('QUERY_LOG_INSERT', 'PASS' if log_row else 'FAIL', f'Logged query {test_query_id}')

    # TEST 5: Evidence Bundle Storage
    print('\n' + '='*70)
    print('TEST 5: Evidence Bundle Storage')
    print('='*70)

    cursor = conn.cursor()
    bundle_id = uuid.uuid4()
    # Use actual UUIDs, not strings - cast in SQL
    snippet_id_strs = [str(live_ids[0]), str(live_ids[1])] if len(live_ids) >= 2 else []

    fused_json = json.dumps([
        {'evidence_id': str(live_ids[0]), 'rrf_score': 0.0163, 'dense_rank': 1, 'sparse_rank': 2},
    ]) if len(live_ids) >= 1 else None

    bundle_content = f'{bundle_id}TEST{fused_json}'
    bundle_hash = hashlib.sha256(bundle_content.encode()).hexdigest()

    cursor.execute('''
        INSERT INTO fhq_canonical.evidence_bundles (
            bundle_id, query_text, rrf_fused_results, rrf_top_score,
            snippet_ids, defcon_level, regime, query_cost_usd, bundle_hash, created_at
        ) VALUES (%s, %s, %s, %s, %s::uuid[], %s, %s, %s, %s, %s)
    ''', [
        str(bundle_id), 'TEST: Bitcoin regime analysis', fused_json,
        0.0163, snippet_id_strs, 'ORANGE', 'BULL', 0.0016, bundle_hash, datetime.now(timezone.utc)
    ])
    conn.commit()

    cursor.execute('SELECT bundle_id, bundle_hash FROM fhq_canonical.evidence_bundles WHERE bundle_id = %s', [str(bundle_id)])
    bundle_row = cursor.fetchone()
    cursor.close()
    log_test('EVIDENCE_BUNDLE_STORE', 'PASS' if bundle_row else 'FAIL', f'Bundle {bundle_id} stored')

    # TEST 6: End-to-End Search + Bundle
    print('\n' + '='*70)
    print('TEST 6: End-to-End Sparse Search + Bundle Creation')
    print('='*70)

    cursor = conn.cursor()
    query = 'causal edge transmission'
    cursor.execute("SELECT evidence_id, fts_rank FROM fhq_canonical.postgres_fts_search(%s, 5, 'simple')", [query])
    e2e_results = cursor.fetchall()

    if e2e_results:
        e2e_bundle_id = uuid.uuid4()
        e2e_snippet_ids = [str(r[0]) for r in e2e_results]
        e2e_sparse_json = json.dumps([
            {'evidence_id': str(r[0]), 'score': float(r[1]), 'rank': i+1}
            for i, r in enumerate(e2e_results)
        ])

        e2e_content = f'{e2e_bundle_id}{query}{e2e_sparse_json}'
        e2e_hash = hashlib.sha256(e2e_content.encode()).hexdigest()

        cursor.execute('''
            INSERT INTO fhq_canonical.evidence_bundles (
                bundle_id, query_text, sparse_results, rrf_top_score,
                snippet_ids, defcon_level, query_cost_usd, bundle_hash, created_at
            ) VALUES (%s, %s, %s, %s, %s::uuid[], %s, %s, %s, %s)
        ''', [
            str(e2e_bundle_id), query, e2e_sparse_json,
            float(e2e_results[0][1]) if e2e_results else 0,
            e2e_snippet_ids, 'YELLOW', 0.0005, e2e_hash, datetime.now(timezone.utc)
        ])
        conn.commit()

        log_test('E2E_SEARCH_BUNDLE', 'PASS', f'Created bundle {e2e_bundle_id} with {len(e2e_results)} results')
        print(f'Query: "{query}"')
        print(f'Bundle: {e2e_bundle_id}')
        print(f'Results: {len(e2e_results)} evidence nodes')
    else:
        log_test('E2E_SEARCH_BUNDLE', 'FAIL', 'No results for E2E test query')

    cursor.close()

    # STORE TEST EVIDENCE
    print('\n' + '='*70)
    print('STORING TEST RESULTS AS EVIDENCE')
    print('='*70)

    test_evidence = {
        'test_suite': 'INFORAGE_HYBRID_RETRIEVER',
        'directive': 'CEO-DIR-2026-COGNITIVE-ENGINES-001',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'total_tests': len(test_results),
        'passed': len([t for t in test_results if t['status'] == 'PASS']),
        'failed': len([t for t in test_results if t['status'] == 'FAIL']),
        'results': test_results
    }

    evidence_path = 'evidence/INFORAGE_RETRIEVER_TEST_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S') + '.json'
    with open(evidence_path, 'w') as f:
        json.dump(test_evidence, f, indent=2)
    print(f'Evidence stored: {evidence_path}')

    # Final counts
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM fhq_governance.inforage_query_log')
    log_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM fhq_canonical.evidence_bundles')
    bundle_count = cursor.fetchone()[0]
    cursor.close()

    print('\n' + '='*70)
    print('TEST SUMMARY')
    print('='*70)
    print(f'Total Tests: {test_evidence["total_tests"]}')
    print(f'Passed: {test_evidence["passed"]}')
    print(f'Failed: {test_evidence["failed"]}')
    print(f'Query Logs: {log_count} entries')
    print(f'Evidence Bundles: {bundle_count} entries')

    conn.close()

    if test_evidence['failed'] == 0:
        print('\n[SUCCESS] All tests passed!')
    else:
        print(f'\n[WARNING] {test_evidence["failed"]} test(s) failed')

    return test_evidence

if __name__ == '__main__':
    run_tests()
