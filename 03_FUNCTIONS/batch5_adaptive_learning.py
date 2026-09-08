#!/usr/bin/env python3
"""
BATCH 5 - ADAPTIVE LEARNING ACTIVATION
CEO-DIR-2026-FINN-011: Runs 401-500
Target: 0.55 Retrieval Discipline
"""

import sys
sys.path.insert(0, '.')
from batch4_causal_attribution import *

BATCH_ID = 'BATCH5'
START_RUN = 401
END_RUN = 500
DIRECTIVE_REF = 'CEO-DIR-2026-FINN-011'
CHECKPOINTS = [425, 450, 475, 500]
DISCIPLINE_TARGET = 0.55
DISCIPLINE_STOP_LOSS_450 = 0.50

conn = get_db_conn()

print('=' * 70)
print('BATCH 5 - ADAPTIVE LEARNING ACTIVATION')
print('CEO-DIR-2026-FINN-011: Runs 401-500')
print(f'Target Discipline: {DISCIPLINE_TARGET}')
print('=' * 70)

results = {
    'valid': 0,
    'error': 0,
    'total_cost': 0.0,
    'cumulative_discipline': 0.0,
    'attributions': []
}

def evaluate_checkpoint_b5(conn, checkpoint, results, batch_id):
    """Evaluate batch progress at checkpoint"""
    avg_discipline = results['cumulative_discipline'] / results['valid'] if results['valid'] > 0 else 0

    result = {
        'checkpoint': checkpoint,
        'avg_discipline': avg_discipline,
        'valid_runs': results['valid'],
        'action': 'CONTINUE'
    }

    # Stop-loss at checkpoint 450: discipline must be >= 0.50
    if checkpoint == 450 and avg_discipline < DISCIPLINE_STOP_LOSS_450:
        result['action'] = 'PAUSE_AND_REVIEW'
        result['reason'] = f'Discipline {avg_discipline:.4f} < {DISCIPLINE_STOP_LOSS_450} at run 450'

        # Log stop-loss
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO fhq_research.learning_stop_loss_log
            (batch_id, checkpoint_run, avg_discipline, threshold, action, directive_ref)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (batch_id, checkpoint, avg_discipline, DISCIPLINE_STOP_LOSS_450,
              result['action'], DIRECTIVE_REF))
        conn.commit()
        cur.close()

    return result

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

    # Checkpoint evaluation
    if run_num in CHECKPOINTS:
        print(f'\n{"="*60}')
        print(f'[CHECKPOINT] Run {run_num}')
        print(f'{"="*60}')

        checkpoint_result = evaluate_checkpoint_b5(conn, run_num, results, BATCH_ID)
        avg_disc = checkpoint_result['avg_discipline']

        print(f'  Avg Discipline (401-{run_num}): {avg_disc:.4f}')
        print(f'  Target: {DISCIPLINE_TARGET}')
        print(f'  Valid Runs: {results["valid"]}')
        print(f'  Delta to Target: {avg_disc - DISCIPLINE_TARGET:+.4f}')

        if checkpoint_result['action'] in ('PAUSE_AND_REVIEW', 'CEO_ESCALATION'):
            print(f'\n[STOP-LOSS TRIGGERED] {checkpoint_result["reason"]}')
            print('Batch paused per CEO-DIR-2026-FINN-011 hard_stops')
            break

# Final summary
print('\n' + '=' * 70)
print('BATCH 5 SUMMARY (401-500)')
print('=' * 70)

total_runs = results['valid'] + results['error']
avg_discipline = results['cumulative_discipline'] / results['valid'] if results['valid'] > 0 else 0

if results['attributions']:
    avg_mc = sum(a.get('marginal_contribution', 0) for a in results['attributions']) / len(results['attributions'])
    avg_yield = sum(a.get('real_yield', 0) for a in results['attributions']) / len(results['attributions'])
    runs_above_target = sum(1 for a in results['attributions']
                           if a.get('marginal_contribution', 0) * 0.6 + a.get('real_yield', 0) * 0.4 >= DISCIPLINE_TARGET)
else:
    avg_mc = 0
    avg_yield = 0
    runs_above_target = 0

print(f'  Total Runs: {total_runs}')
print(f'  Valid: {results["valid"]}')
print(f'  Errors: {results["error"]}')
print(f'  Avg Marginal Contribution: {avg_mc:.4f}')
print(f'  Avg Real Yield: {avg_yield:.4f}')
print(f'  Avg Discipline: {avg_discipline:.4f}')
print(f'  Target Discipline: {DISCIPLINE_TARGET}')
print(f'  Delta to Target: {avg_discipline - DISCIPLINE_TARGET:+.4f}')
print(f'  Runs >= {DISCIPLINE_TARGET}: {runs_above_target} ({100*runs_above_target/results["valid"] if results["valid"] > 0 else 0:.1f}%)')
print(f'  Total Cost: ${results["total_cost"]:.6f}')

# Outcome determination
if avg_discipline >= DISCIPLINE_TARGET:
    print(f'\n[SUCCESS] Batch 5 target achieved: {avg_discipline:.4f} >= {DISCIPLINE_TARGET}')
    print('Graduation: adaptive intelligence -> compounding intelligence')
    print('Batch 6 Target: 0.60')
else:
    print(f'\n[BELOW TARGET] Batch 5: {avg_discipline:.4f} < {DISCIPLINE_TARGET}')
    print('Review path-level variance and consider pruning low-discipline paths')

print('=' * 70)

conn.close()
print('\n[COMPLETE] Batch 5 execution finished')
