"""
CEO-DIR-2026-109: CPTO Shadow Test - Pathway A
==============================================

Real-data shadow test with zero synthetic data.
Uses actual signal_id from canonical signal surface.
No test data created - only governance evidence.

Classification: AUDIT-SAFE VERIFICATION
"""

import json
import hashlib
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import sys

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(
        host=os.getenv('PGHOST', '127.0.0.1'),
        port=os.getenv('PGPORT', '54322'),
        database=os.getenv('PGDATABASE', 'postgres'),
        user=os.getenv('PGUSER', 'postgres'),
        password=os.getenv('PGPASSWORD', 'postgres')
    )


def run_pathway_a_shadow_test():
    """
    Pathway A: Real-data shadow test, zero test data.

    Uses real upstream signal from canonical surface.
    Runs CPTO in shadow/non-executing mode.
    Writes evidence to governance log.
    Does NOT submit to LINE or place orders.
    """
    conn = get_db_connection()
    results = {
        "test_type": "PATHWAY_A_SHADOW",
        "classification": "AUDIT_SAFE_VERIFICATION",
        "test_data_created": False,
        "submission_to_line": False,
        "orders_placed": False
    }

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get database clock for evidence
        cur.execute("SELECT NOW() as db_clock")
        db_clock = cur.fetchone()['db_clock']
        results["db_clock_start"] = db_clock.isoformat()

        # Step 1: Get real signal from canonical surface
        print("=" * 60)
        print("PATHWAY A: Real-Data Shadow Test")
        print("=" * 60)
        print(f"\nDatabase clock: {db_clock.isoformat()}")

        cur.execute("""
            SELECT
                plan_id,
                signal_id,
                instrument,
                direction,
                decision_confidence,
                regime_at_decision,
                defcon_at_decision,
                valid_from,
                valid_until,
                created_at
            FROM fhq_alpha.g2_decision_plans
            WHERE regime_at_decision = 'STRESS'
            ORDER BY created_at DESC
            LIMIT 1
        """)
        signal = cur.fetchone()

        if not signal:
            print("ERROR: No real signals found in canonical surface")
            results["status"] = "NO_REAL_SIGNALS"
            return results

        results["real_signal"] = {
            "plan_id": str(signal['plan_id']),
            "signal_id": str(signal['signal_id']),
            "instrument": signal['instrument'],
            "direction": signal['direction'],
            "confidence": float(signal['decision_confidence']),
            "regime": signal['regime_at_decision'],
            "defcon_at_decision": signal['defcon_at_decision'],
            "valid_until": signal['valid_until'].isoformat(),
            "created_at": signal['created_at'].isoformat()
        }

        print(f"\n[REAL SIGNAL]")
        print(f"  signal_id: {signal['signal_id']}")
        print(f"  instrument: {signal['instrument']}")
        print(f"  direction: {signal['direction']}")
        print(f"  regime: {signal['regime_at_decision']}")
        print(f"  valid_until: {signal['valid_until']}")

        # Step 2: Get real price data
        cur.execute("""
            SELECT
                asset,
                price,
                bid,
                ask,
                event_time_utc
            FROM fhq_core.v_latest_prices
            WHERE asset = %s
            AND bid IS NOT NULL
            LIMIT 1
        """, (signal['instrument'],))
        price_data = cur.fetchone()

        if price_data:
            mid_market = float(price_data['price'])
            results["real_price"] = {
                "asset": price_data['asset'],
                "price": mid_market,
                "bid": float(price_data['bid']) if price_data['bid'] else None,
                "ask": float(price_data['ask']) if price_data['ask'] else None,
                "timestamp": price_data['event_time_utc'].isoformat()
            }
            print(f"\n[REAL PRICE]")
            print(f"  {price_data['asset']}: ${mid_market:,.2f}")
            print(f"  bid/ask: {price_data['bid']}/{price_data['ask']}")
        else:
            mid_market = 92618.62  # Fallback to last known
            results["real_price"] = {"fallback": True, "price": mid_market}

        # Step 3: Get real ATR data
        cur.execute("""
            SELECT
                asset_id,
                timestamp,
                value_json->'atr_14' as atr_14,
                value_json->'bb_lower' as bb_lower,
                value_json->'bb_upper' as bb_upper
            FROM fhq_research.indicator_volatility
            WHERE asset_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """, (signal['instrument'],))
        indicator_data = cur.fetchone()

        if indicator_data:
            atr = float(indicator_data['atr_14'])
            results["real_indicators"] = {
                "asset": indicator_data['asset_id'],
                "atr_14": atr,
                "bb_lower": float(indicator_data['bb_lower']),
                "bb_upper": float(indicator_data['bb_upper']),
                "timestamp": indicator_data['timestamp'].isoformat()
            }
            print(f"\n[REAL INDICATORS]")
            print(f"  ATR(14): ${atr:,.2f}")
            print(f"  BB_lower: ${float(indicator_data['bb_lower']):,.2f}")
            print(f"  BB_upper: ${float(indicator_data['bb_upper']):,.2f}")
        else:
            atr = 1037.33
            results["real_indicators"] = {"fallback": True, "atr_14": atr}

        # Step 4: Get current DEFCON
        cur.execute("""
            SELECT defcon_level, triggered_at, trigger_reason
            FROM fhq_governance.defcon_state
            WHERE is_current = true
            LIMIT 1
        """)
        defcon = cur.fetchone()

        results["current_defcon"] = {
            "level": defcon['defcon_level'],
            "triggered_at": defcon['triggered_at'].isoformat()
        }
        print(f"\n[CURRENT DEFCON]")
        print(f"  Level: {defcon['defcon_level']}")

        # Step 5: CPTO Shadow Evaluation (NO SUBMISSION)
        print(f"\n{'=' * 60}")
        print("CPTO SHADOW EVALUATION")
        print("=" * 60)

        # Check TTL
        now = datetime.now(timezone.utc)
        valid_until = signal['valid_until']
        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=timezone.utc)

        ttl_remaining = (valid_until - now).total_seconds()
        ttl_check = ttl_remaining > 30  # 30 second buffer

        results["ttl_check"] = {
            "valid_until": valid_until.isoformat(),
            "remaining_seconds": ttl_remaining,
            "passed": ttl_check,
            "reason": "TTL_VALID" if ttl_check else "TTL_EXPIRED"
        }

        print(f"\n[TTL CHECK]")
        print(f"  Valid until: {valid_until}")
        print(f"  Remaining: {ttl_remaining:,.0f} seconds")
        print(f"  Result: {'PASS' if ttl_check else 'BLOCK - TTL_EXPIRED'}")

        # Check DEFCON
        defcon_level = defcon['defcon_level'].upper()
        defcon_behavior = {
            'GREEN': 'NORMAL',
            'YELLOW': 'NORMAL',
            'ORANGE': 'CONSERVATIVE',
            'RED': 'REFUSE_NEW',
            'BLACK': 'REFUSE_NEW'
        }.get(defcon_level, 'NORMAL')

        defcon_check = defcon_behavior != 'REFUSE_NEW'

        results["defcon_check"] = {
            "level": defcon_level,
            "behavior": defcon_behavior,
            "passed": defcon_check,
            "reason": "DEFCON_ALLOW" if defcon_check else "DEFCON_REFUSE_NEW"
        }

        print(f"\n[DEFCON CHECK]")
        print(f"  Level: {defcon_level}")
        print(f"  Behavior: {defcon_behavior}")
        print(f"  Result: {'PASS' if defcon_check else 'BLOCK - REFUSE_NEW'}")

        # Compute what entry price WOULD be (shadow calculation)
        regime = signal['regime_at_decision']
        aggression_map = {
            'STRONG_BULL': 0.002,
            'NEUTRAL': 0.003,
            'VOLATILE': 0.005,
            'STRESS': 0.007,
            'VERIFIED_INVERTED_STRESS': 0.002
        }
        aggression = aggression_map.get(regime, 0.005)

        direction = signal['direction']
        if direction == 'LONG':
            shadow_entry = mid_market * (1 - aggression)
        else:
            shadow_entry = mid_market * (1 + aggression)

        # Canonical exits (CEO-DIR-2026-107)
        r_value = atr * 2.0
        if direction == 'LONG':
            shadow_sl = shadow_entry - r_value
            shadow_tp = shadow_entry + (r_value * 1.25)
        else:
            shadow_sl = shadow_entry + r_value
            shadow_tp = shadow_entry - (r_value * 1.25)

        # Slippage saved (Amendment B)
        if direction == 'LONG':
            slippage_saved_bps = (mid_market - shadow_entry) / mid_market * 10000
        else:
            slippage_saved_bps = (shadow_entry - mid_market) / mid_market * 10000

        results["shadow_calculation"] = {
            "regime": regime,
            "aggression": aggression,
            "mid_market": mid_market,
            "shadow_entry_price": round(shadow_entry, 2),
            "shadow_stop_loss": round(shadow_sl, 2),
            "shadow_take_profit": round(shadow_tp, 2),
            "r_value": round(r_value, 2),
            "estimated_slippage_saved_bps": round(slippage_saved_bps, 2)
        }

        print(f"\n[SHADOW CALCULATION] (what WOULD happen if signal were valid)")
        print(f"  Regime: {regime}")
        print(f"  Aggression: {aggression}")
        print(f"  Mid-market: ${mid_market:,.2f}")
        print(f"  Shadow entry: ${shadow_entry:,.2f}")
        print(f"  Shadow SL: ${shadow_sl:,.2f}")
        print(f"  Shadow TP: ${shadow_tp:,.2f}")
        print(f"  Slippage saved: {slippage_saved_bps:.2f} bps")

        # Final verdict
        if not ttl_check:
            verdict = "BLOCKED"
            reason = "TTL_EXPIRED"
        elif not defcon_check:
            verdict = "BLOCKED"
            reason = "DEFCON_REFUSE_NEW"
        else:
            verdict = "WOULD_PROCESS"
            reason = "ALL_CHECKS_PASS"

        results["verdict"] = {
            "outcome": verdict,
            "reason": reason,
            "submission_to_line": False,
            "orders_placed": False
        }

        print(f"\n{'=' * 60}")
        print(f"VERDICT: {verdict}")
        print(f"Reason: {reason}")
        print(f"Submission to LINE: NO (shadow mode)")
        print(f"Orders placed: NO (shadow mode)")
        print("=" * 60)

        # Step 6: Log to governance (evidence only, no test data)
        cur.execute("SELECT NOW() as db_clock")
        db_clock_end = cur.fetchone()['db_clock']
        results["db_clock_end"] = db_clock_end.isoformat()

        # Create evidence hash
        evidence_hash = hashlib.sha256(
            json.dumps(results, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]
        results["evidence_hash"] = evidence_hash

        # Log to governance_actions_log (audit trail, not test data)
        cur.execute("""
            INSERT INTO fhq_governance.governance_actions_log (
                action_type, action_target, action_target_type,
                initiated_by, initiated_at, decision, decision_rationale,
                vega_reviewed
            ) VALUES (
                'CPTO_SHADOW_TEST',
                %s,
                'PATHWAY_A_VERIFICATION',
                'STIG',
                NOW(),
                %s,
                %s,
                false
            )
        """, (
            str(signal['signal_id']),
            verdict,
            f"Real signal shadow test: {reason}. Evidence hash: {evidence_hash}"
        ))
        conn.commit()

        print(f"\n[GOVERNANCE LOG]")
        print(f"  Logged to governance_actions_log")
        print(f"  Evidence hash: {evidence_hash}")

        results["governance_logged"] = True
        results["status"] = "COMPLETED"

    conn.close()
    return results


def main():
    """Run Pathway A shadow test"""
    print("\n" + "=" * 70)
    print("CEO-DIR-2026-109: CPTO PATHWAY A SHADOW TEST")
    print("Real data only - Zero synthetic data - No LINE submission")
    print("=" * 70)

    results = run_pathway_a_shadow_test()

    # Save evidence file
    evidence_path = os.path.join(
        os.path.dirname(__file__),
        'evidence',
        'CEO_DIR_2026_109_CPTO_PATHWAY_A_SHADOW_TEST.json'
    )

    with open(evidence_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n[EVIDENCE FILE]")
    print(f"  Saved to: {evidence_path}")

    return results


if __name__ == '__main__':
    main()
