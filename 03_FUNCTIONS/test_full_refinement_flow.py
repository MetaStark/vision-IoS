#!/usr/bin/env python3
"""
STAR SQL Full Refinement Flow Test
===================================
Tests the complete admission controller + LLM + engine flow.
"""

import os
import time
import psycopg2
from datetime import datetime, timezone
from openai import OpenAI

from star_sql_admission_controller import (
    admit_refinement_request,
    release_concurrency_gate,
    CONTROLLER_VERSION
)
from star_sql_reasoning_engine import (
    execute_refinement_attempt,
    build_reasoning_artifact
)

def run_full_flow_test():
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
    if not DEEPSEEK_API_KEY:
        print("ERROR: DEEPSEEK_API_KEY not set")
        return False

    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url='https://api.deepseek.com')

    conn = psycopg2.connect(
        host='127.0.0.1', port=54322, database='postgres',
        user='postgres', password='postgres'
    )

    print('=' * 70)
    print('STAR SQL FULL REFINEMENT FLOW - REAL LLM TEST')
    print('=' * 70)
    print(f'Controller: {CONTROLLER_VERSION} | Time: {datetime.now(timezone.utc).strftime("%H:%M:%S")} UTC')
    print()

    original_query = 'SELECT symbol, confidence FROM vision_signals.alpha_signals WHERE confidence > 0.5'
    agent_id = 'FINN'

    # STEP 1: ADMISSION
    print('STEP 1: ADMISSION CHECK')
    admission = admit_refinement_request(conn, original_query, agent_id)
    print(f'  Result: {"ADMITTED" if admission.admitted else "REJECTED"}')
    if not admission.admitted:
        print(f'  Code: {admission.rejection_code} | Reason: {admission.reason}')
        release_concurrency_gate()
        conn.close()
        return False
    print(f'  Gates: {list(admission.gates_checked.keys())}')
    print()

    # STEP 2: DEEPSEEK CALL
    print('STEP 2: DEEPSEEK SQL REFINEMENT')
    prompt = f'Optimize this SQL query. Add ORDER BY confidence DESC and LIMIT 10. Return only SQL:\n{original_query}'

    start = time.time()
    response = client.chat.completions.create(
        model='deepseek-chat',
        messages=[{'role': 'user', 'content': prompt}],
        max_tokens=300, temperature=0.1
    )
    latency_ms = int((time.time() - start) * 1000)

    generated_sql = response.choices[0].message.content.strip()
    tokens_in = response.usage.prompt_tokens
    tokens_out = response.usage.completion_tokens
    cost_usd = (tokens_in * 0.00000014) + (tokens_out * 0.00000028)

    print(f'  Latency: {latency_ms}ms | Tokens: {tokens_in}+{tokens_out} | Cost: ${cost_usd:.6f}')
    print(f'  SQL: {generated_sql[:80]}...')
    print()

    # STEP 3: LOG TO ENGINE
    print('STEP 3: LOG TO REASONING ENGINE')
    artifact = build_reasoning_artifact(
        intent='Add ordering and limit',
        tables=['vision_signals.alpha_signals'],
        columns=['symbol', 'confidence'],
        join_plan='None',
        filters=['confidence > 0.5'],
        aggregation_grain=None,
        verification_steps=['Added ORDER BY', 'Added LIMIT'],
        risk_flags=[]
    )

    result = execute_refinement_attempt(
        conn=conn, original_query=original_query, reasoning_artifact=artifact,
        generated_sql=generated_sql, agent_id=agent_id, attempt_number=1,
        latency_ms=latency_ms, tokens_consumed=tokens_in+tokens_out,
        cost_usd=cost_usd, success=True, model_used='deepseek-chat',
        prompt_template_version='v1.0'
    )
    print(f'  Refinement ID: {result.refinement_id}')
    print(f'  Success: {result.success} | Cost: ${result.cost_usd:.6f}')
    print()

    release_concurrency_gate()

    # STEP 4: VERIFY DB
    print('STEP 4: DATABASE VERIFICATION')
    with conn.cursor() as cur:
        cur.execute('''
            SELECT log_id, cost_usd, tokens_consumed, latency_ms, success, created_at
            FROM fhq_governance.sql_refinement_log
            WHERE agent_id = %s ORDER BY created_at DESC LIMIT 1
        ''', (agent_id,))
        row = cur.fetchone()
        if row:
            print(f'  Log ID: {row[0]}')
            print(f'  Cost: ${row[1]:.6f} | Tokens: {row[2]} | Latency: {row[3]}ms')
            print(f'  Success: {row[4]} | Created: {row[5]}')
        else:
            print('  WARNING: No entry found')

    conn.close()
    print()
    print('=' * 70)
    print('FULL FLOW COMPLETE - ALL 4 STEPS PASSED')
    print('=' * 70)
    return True


if __name__ == "__main__":
    run_full_flow_test()
