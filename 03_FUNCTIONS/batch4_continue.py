#!/usr/bin/env python3
"""
BATCH 4 CONTINUATION - CEO STOP-LOSS OVERRIDE
Runs 351-400
"""

import sys
sys.path.insert(0, '.')
from batch4_causal_attribution import *

BATCH_ID = 'BATCH4'
START_RUN = 351
END_RUN = 400

conn = get_db_conn()

print('=' * 70)
print('BATCH 4 CONTINUATION - CEO STOP-LOSS OVERRIDE')
print('CEO-DIR-2026-FINN-010: Runs 351-400')
print('=' * 70)

results = {
    'valid': 0,
    'error': 0,
    'total_cost': 0.0,
    'cumulative_discipline': 0.0,
    'attributions': []
}

for run_num in range(START_RUN, END_RUN + 1):
    hyp_idx = (run_num - 1) % len(HYPOTHESES)
    hypothesis = HYPOTHESES[hyp_idx]

    print(f'\n{"="*60}')
    print(f'RUN {run_num}: {hypothesis[0]}')
    print(f'{"="*60}')

    run_result = execute_run(conn, run_num, hypothesis, BATCH_ID)

    if run_result['status'] == 'VALID':
        results['valid'] += 1
        results['total_cost'] += run_result['cost']
        results['cumulative_discipline'] += run_result['retrieval_discipline']
        results['attributions'].append(run_result.get('attribution', {}))
    else:
        results['error'] += 1

    print(f'\n[RESULT] Run {run_num}: {run_result["status"]}')
    print(f'  Duration: {run_result["duration"]:.2f}s | Cost: ${run_result["cost"]:.6f}')

    # Checkpoint at 375 and 400
    if run_num in [375, 400]:
        print(f'\n{"="*60}')
        print(f'[CHECKPOINT] Run {run_num} (OVERRIDE MODE)')
        print(f'{"="*60}')
        avg_disc = results['cumulative_discipline'] / results['valid'] if results['valid'] > 0 else 0
        print(f'  Continuation Avg Discipline: {avg_disc:.4f}')
        print(f'  Valid Runs: {results["valid"]}')

# Final summary
print('\n' + '=' * 70)
print('BATCH 4 CONTINUATION SUMMARY (351-400)')
print('=' * 70)
total_runs = results['valid'] + results['error']
avg_discipline = results['cumulative_discipline'] / results['valid'] if results['valid'] > 0 else 0

if results['attributions']:
    avg_mc = sum(a.get('marginal_contribution', 0) for a in results['attributions']) / len(results['attributions'])
    avg_yield = sum(a.get('real_yield', 0) for a in results['attributions']) / len(results['attributions'])
else:
    avg_mc = 0
    avg_yield = 0

print(f'  Runs 351-400: {total_runs}')
print(f'  Valid: {results["valid"]}')
print(f'  Errors: {results["error"]}')
print(f'  Avg Discipline (351-400): {avg_discipline:.4f}')
print(f'  Avg MC (351-400): {avg_mc:.4f}')
print(f'  Avg Yield (351-400): {avg_yield:.4f}')
print(f'  Total Cost: ${results["total_cost"]:.6f}')
print('=' * 70)

conn.close()
print('\n[SUCCESS] Batch 4 continuation complete (CEO Override)')
