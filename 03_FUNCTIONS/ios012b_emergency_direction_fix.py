#!/usr/bin/env python3
"""
IoS-012-B EMERGENCY DIRECTION FIX
=================================
Directive: CEO-DIR-2026-106 P0
Date: 2026-01-19
Author: STIG

KRITISK FIX: Korrigerer invertert retning fra DOWN til UP for STRESS-signaler.

Problemet:
- Koden tolket forecast_probability > 0.5 som "UP prediction"
- Men for STRESS regime, predikerer FINN NEDSIDE (DOWN)
- Høy konfidens STRESS = sterk DOWN-prediksjon
- Invertert burde være UP (LONG), ikke DOWN (SHORT)

Denne scripten:
1. Korrigerer source_direction og inverted_direction i inversion_overlay_shadow
2. Korrigerer direction i ios012b_paper_positions
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


def main():
    print("=" * 60)
    print("IoS-012-B EMERGENCY DIRECTION FIX")
    print("CEO-DIR-2026-106 P0")
    print("=" * 60)

    conn = psycopg2.connect(**DB_CONFIG)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Count affected records
            cur.execute("""
                SELECT COUNT(*) as count
                FROM fhq_alpha.inversion_overlay_shadow
                WHERE source_regime = 'STRESS' AND source_direction = 'UP'
            """)
            overlay_count = cur.fetchone()['count']
            print(f"\nAffected overlay records: {overlay_count}")

            cur.execute("""
                SELECT COUNT(*) as count
                FROM fhq_alpha.ios012b_paper_positions
                WHERE direction = 'DOWN' AND status = 'OPEN'
            """)
            position_count = cur.fetchone()['count']
            print(f"Affected paper positions: {position_count}")

            if overlay_count == 0 and position_count == 0:
                print("\nNo records to fix. Exiting.")
                return

            # 2. Fix inversion_overlay_shadow
            print("\n[STEP 1] Fixing inversion_overlay_shadow...")
            cur.execute("""
                UPDATE fhq_alpha.inversion_overlay_shadow
                SET source_direction = 'DOWN',
                    inverted_direction = 'UP'
                WHERE source_regime = 'STRESS'
                  AND source_direction = 'UP'
                RETURNING overlay_id, ticker
            """)
            fixed_overlays = cur.fetchall()
            print(f"  Fixed {len(fixed_overlays)} overlay records")

            # 3. Fix paper positions
            print("\n[STEP 2] Fixing ios012b_paper_positions...")
            cur.execute("""
                UPDATE fhq_alpha.ios012b_paper_positions
                SET direction = 'UP'
                WHERE direction = 'DOWN'
                  AND status = 'OPEN'
                RETURNING position_id, ticker
            """)
            fixed_positions = cur.fetchall()
            print(f"  Fixed {len(fixed_positions)} paper positions")

            # 4. Log the fix
            print("\n[STEP 3] Logging governance action...")
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_id, action_type, action_target, action_target_type,
                    initiated_by, initiated_at, decision, decision_rationale
                ) VALUES (
                    gen_random_uuid(),
                    'P0_DIRECTION_LOGIC_FIX',
                    'IoS-012-B',
                    'SYNTHETIC_INVERSION_MODULE',
                    'STIG',
                    NOW(),
                    'EMERGENCY_FIX_APPLIED',
                    'CEO-DIR-2026-106 P0: Fixed inverted direction logic. STRESS regime predicts DOWN, inverted should be UP (BUY). Fixed ' || %s || ' overlay records and ' || %s || ' paper positions.'
                )
            """, (len(fixed_overlays), len(fixed_positions)))

            conn.commit()

            print("\n" + "=" * 60)
            print("FIX APPLIED SUCCESSFULLY")
            print("=" * 60)
            print(f"\nOverlay records corrected: {len(fixed_overlays)}")
            print(f"Paper positions corrected: {len(fixed_positions)}")
            print("\nNOTE: Alpaca paper positions are still SHORT.")
            print("You must manually close/reverse them in Alpaca dashboard.")

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
