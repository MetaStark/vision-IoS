#!/usr/bin/env python3
"""
CEO-DIR-2026-083: Populate ROI Direction Ledger (EQUITY)

Captures existing STRESS@99%+ EQUITY signals from shadow inversion table
into the canonical roi_direction_ledger_equity table.

Authority: CEO
Executed by: STIG (EC-003)
"""

import os
import sys
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).parent))

import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=os.getenv("PGPORT", "54322"),
        database=os.getenv("PGDATABASE", "postgres"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres")
    )


def get_stress_signals_with_prices(conn):
    """Get all STRESS@99%+ EQUITY signals with price data."""
    query = """
    SELECT
        s.inversion_id,
        s.asset_id as ticker,
        s.forecast_timestamp as signal_timestamp,
        s.original_confidence as confidence,
        s.inverted_brier,
        s.original_score_id as forecast_id,
        p.close as price_t0,
        p1.close as price_t0_plus_1d,
        p3.close as price_t0_plus_3d,
        p5.close as price_t0_plus_5d
    FROM fhq_alpha.stress_inversion_shadow s
    JOIN fhq_market.prices p ON s.asset_id = p.canonical_id
        AND DATE(s.forecast_timestamp) = DATE(p.timestamp)
    LEFT JOIN fhq_market.prices p1 ON s.asset_id = p1.canonical_id
        AND DATE(s.forecast_timestamp + INTERVAL '1 day') = DATE(p1.timestamp)
    LEFT JOIN fhq_market.prices p3 ON s.asset_id = p3.canonical_id
        AND DATE(s.forecast_timestamp + INTERVAL '3 days') = DATE(p3.timestamp)
    LEFT JOIN fhq_market.prices p5 ON s.asset_id = p5.canonical_id
        AND DATE(s.forecast_timestamp + INTERVAL '5 days') = DATE(p5.timestamp)
    WHERE s.original_regime = 'STRESS'
    AND s.original_confidence >= 0.99
    AND s.asset_class = 'EQUITY_US'
    ORDER BY s.forecast_timestamp DESC
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query)
        return cur.fetchall()


def populate_roi_ledger(conn, signals):
    """Insert signals into roi_direction_ledger_equity."""
    print("\n" + "="*60)
    print("POPULATING ROI DIRECTION LEDGER (EQUITY)")
    print("="*60)

    inserted = 0
    skipped = 0
    errors = 0

    for signal in signals:
        ticker = signal['ticker']
        signal_ts = signal['signal_timestamp']
        confidence = float(signal['confidence'])
        price_t0 = float(signal['price_t0'])
        inverted_brier = float(signal['inverted_brier'])
        forecast_id = signal['forecast_id']

        # Check if already exists
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1 FROM fhq_research.roi_direction_ledger_equity
                WHERE ticker = %s AND signal_timestamp = %s
            """, (ticker, signal_ts))

            if cur.fetchone():
                skipped += 1
                continue

        try:
            with conn.cursor() as cur:
                # Use the append function
                cur.execute("""
                    SELECT fhq_research.append_roi_direction_event_equity(
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    ticker,
                    signal_ts,
                    confidence,
                    price_t0,
                    inverted_brier,
                    forecast_id,
                    False,  # anomaly_flag
                    'ARMED'  # kill_switch_state
                ))

                event_id = cur.fetchone()[0]

                # Now update with outcome prices if available
                price_1d = signal.get('price_t0_plus_1d')
                price_3d = signal.get('price_t0_plus_3d')
                price_5d = signal.get('price_t0_plus_5d')

                if price_1d or price_3d or price_5d:
                    cur.execute("""
                        SELECT fhq_research.capture_roi_direction_outcome_equity(
                            %s, %s, %s, %s
                        )
                    """, (
                        event_id,
                        float(price_1d) if price_1d else None,
                        float(price_3d) if price_3d else None,
                        float(price_5d) if price_5d else None
                    ))

                conn.commit()
                inserted += 1
                print(f"  [+] {ticker} @ {signal_ts.strftime('%Y-%m-%d')}: conf={confidence:.4f}, brier={inverted_brier:.6f}")

        except Exception as e:
            conn.rollback()
            errors += 1
            print(f"  [!] ERROR {ticker}: {e}")

    print(f"\n  Summary:")
    print(f"    Inserted: {inserted}")
    print(f"    Skipped (duplicates): {skipped}")
    print(f"    Errors: {errors}")

    return inserted, skipped, errors


def verify_ledger(conn):
    """Verify ledger contents."""
    print("\n" + "="*60)
    print("LEDGER VERIFICATION")
    print("="*60)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Count totals
        cur.execute("""
            SELECT
                COUNT(*) as total_events,
                COUNT(price_t0_plus_1d) as with_1d_outcome,
                COUNT(price_t0_plus_3d) as with_3d_outcome,
                COUNT(price_t0_plus_5d) as with_5d_outcome,
                AVG(inverted_brier_at_event) as avg_inverted_brier,
                AVG(CASE WHEN correct_direction_1d THEN 1.0 ELSE 0.0 END) as hit_rate_1d
            FROM fhq_research.roi_direction_ledger_equity
        """)
        stats = cur.fetchone()

        print(f"  Total Events: {stats['total_events']}")
        print(f"  With 1D Outcome: {stats['with_1d_outcome']}")
        print(f"  With 3D Outcome: {stats['with_3d_outcome']}")
        print(f"  With 5D Outcome: {stats['with_5d_outcome']}")
        print(f"  Avg Inverted Brier: {float(stats['avg_inverted_brier']):.6f}" if stats['avg_inverted_brier'] else "  Avg Inverted Brier: N/A")
        print(f"  Hit Rate 1D: {float(stats['hit_rate_1d'])*100:.1f}%" if stats['hit_rate_1d'] else "  Hit Rate 1D: N/A")

        # Show by ticker
        cur.execute("""
            SELECT
                ticker,
                COUNT(*) as events,
                AVG(inverted_brier_at_event) as avg_brier
            FROM fhq_research.roi_direction_ledger_equity
            GROUP BY ticker
            ORDER BY events DESC
        """)
        tickers = cur.fetchall()

        print("\n  By Ticker:")
        for t in tickers:
            print(f"    {t['ticker']}: {t['events']} events, avg brier={float(t['avg_brier']):.6f}")

        return stats


def generate_evidence(inserted, skipped, errors, stats):
    """Generate evidence file."""
    evidence = {
        "directive_id": "CEO-DIR-2026-083",
        "action": "POPULATE_ROI_DIRECTION_LEDGER_EQUITY",
        "executed_by": "STIG (EC-003)",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "status": "COMPLETED",

        "population_results": {
            "signals_inserted": inserted,
            "signals_skipped": skipped,
            "errors": errors,
            "source_table": "fhq_alpha.stress_inversion_shadow",
            "target_table": "fhq_research.roi_direction_ledger_equity"
        },

        "ledger_stats": {
            "total_events": int(stats['total_events']) if stats['total_events'] else 0,
            "with_1d_outcome": int(stats['with_1d_outcome']) if stats['with_1d_outcome'] else 0,
            "with_3d_outcome": int(stats['with_3d_outcome']) if stats['with_3d_outcome'] else 0,
            "with_5d_outcome": int(stats['with_5d_outcome']) if stats['with_5d_outcome'] else 0,
            "avg_inverted_brier": float(stats['avg_inverted_brier']) if stats['avg_inverted_brier'] else None,
            "hit_rate_1d": float(stats['hit_rate_1d']) if stats['hit_rate_1d'] else None
        },

        "constraints_verified": {
            "asset_class": "EQUITY",
            "confidence_threshold": ">= 0.99",
            "inversion_direction": "CONTRARIAN_DOWN"
        },

        "okr_impact": {
            "okr_code": "OKR-2026-D18-001",
            "kr1_target": 5,
            "kr1_current": int(stats['total_events']) if stats['total_events'] else 0,
            "kr1_status": "ACHIEVED" if (stats['total_events'] and int(stats['total_events']) >= 5) else "IN_PROGRESS"
        }
    }

    evidence_path = Path(__file__).parent / "evidence" / "CEO_DIR_2026_083_ROI_LEDGER_POPULATED.json"
    evidence_path.parent.mkdir(exist_ok=True)

    with open(evidence_path, "w") as f:
        json.dump(evidence, f, indent=2)

    print(f"\n  Evidence: {evidence_path.name}")
    return evidence_path


def main():
    """Execute ROI ledger population."""
    print("="*60)
    print("CEO-DIR-2026-083: POPULATE ROI DIRECTION LEDGER")
    print("="*60)
    print(f"Executed: {datetime.now(timezone.utc).isoformat()}")
    print("Authority: CEO")
    print("Executed by: STIG (EC-003)")

    conn = get_db_connection()

    try:
        # Get signals
        print("\nFetching STRESS@99%+ EQUITY signals...")
        signals = get_stress_signals_with_prices(conn)
        print(f"  Found {len(signals)} signals")

        # Populate ledger
        inserted, skipped, errors = populate_roi_ledger(conn, signals)

        # Verify
        stats = verify_ledger(conn)

        # Generate evidence
        generate_evidence(inserted, skipped, errors, stats)

        print("\n" + "="*60)
        print("ROI LEDGER POPULATION: COMPLETE")
        print("="*60)
        print("\nCanonical Economic Truth is now measurable.")
        print("Alpha speaks first. Instruments listen.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
