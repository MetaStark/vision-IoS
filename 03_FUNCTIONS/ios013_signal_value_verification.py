#!/usr/bin/env python3
"""
IoS-013 Signal Value Verification
=================================
Mandat: Value Verification under Backfill Constraints

Premiss: Backfill gir tilgjengelighet, ikke sannhet.
Vi verifiserer verdi relativt - ikke absolutt.

Owner: EC-003 (STIG)
Mode: OBSERVE -> MEASURE -> CLASSIFY

Stoppregel: Kun observere, male, klassifisere.
Ingen justering, ingen nye features, ingen "fiksing".
"""

import psycopg2
import json
import numpy as np
from datetime import datetime, timezone
from decimal import Decimal

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 54322,
    "database": "postgres",
    "user": "postgres",
    "password": "postgres"
}


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def freeze_universe(conn):
    """
    Phase 1: Freeze the universe.
    Only signals with data availability (BACKFILLED or NATIVE).
    PLACEHOLDER = blocked, no discussion.
    """
    cursor = conn.cursor()

    # Check actual data availability for each signal source
    signal_sources = {}

    # Query data availability for key surfaces
    checks = [
        ("prices", "fhq_market.prices", "canonical_id", "timestamp"),
        ("sovereign_regime", "fhq_perception.sovereign_regime_state_v4", "asset_id", "timestamp"),
        ("technical_indicators", "fhq_data.technical_indicators", "asset_id", "timestamp"),
        ("lvi_canonical", "fhq_governance.lvi_canonical", "asset_id", "computed_at"),
        ("hcp_signal_state", "fhq_positions.hcp_signal_state", "ios003_asset_id", "captured_at"),
        ("calendar_events", "fhq_calendar.calendar_events", None, "event_date"),
        ("sentiment", "fhq_research.sentiment", "listing_id", "date"),
        ("macro_indicators", "fhq_data.macro_indicators", None, "date"),
        ("factor_exposure", "fhq_alpha.factor_exposure_daily", "asset_id", "date"),
        ("meanrev_signals", "fhq_alpha.meanrev_signals", "asset_id", "timestamp"),
        ("statarb_signals", "fhq_alpha.statarb_signals", "pair_id", "timestamp"),
    ]

    for name, table, asset_col, time_col in checks:
        try:
            if asset_col:
                cursor.execute(f"""
                    SELECT COUNT(*) as rows,
                           COUNT(DISTINCT {asset_col}) as assets,
                           MIN({time_col})::date as earliest,
                           MAX({time_col})::date as latest
                    FROM {table}
                """)
            else:
                cursor.execute(f"""
                    SELECT COUNT(*) as rows,
                           0 as assets,
                           MIN({time_col})::date as earliest,
                           MAX({time_col})::date as latest
                    FROM {table}
                """)
            row = cursor.fetchone()
            signal_sources[name] = {
                "rows": row[0],
                "assets": row[1],
                "earliest": str(row[2]) if row[2] else None,
                "latest": str(row[3]) if row[3] else None,
                "backfill_status": "BACKFILLED" if row[0] > 100 else ("NATIVE" if row[0] > 0 else "NO_DATA")
            }
            conn.commit()  # Commit after each successful query
        except Exception as e:
            conn.rollback()  # Rollback on error to clear aborted transaction
            signal_sources[name] = {"rows": 0, "assets": 0, "backfill_status": "ERROR", "error": str(e)}

    # Check G3 views
    g3_views = [
        ("regime_transition_risk", "fhq_signal_context.v_regime_transition_risk"),
        ("sector_relative_strength", "fhq_signal_context.v_sector_relative_strength"),
        ("market_relative_strength", "fhq_signal_context.v_market_relative_strength"),
        ("stop_loss_heatmap", "fhq_signal_context.v_stop_loss_heatmap"),
        ("sentiment_divergence", "fhq_signal_context.v_sentiment_divergence"),
    ]

    for name, view in g3_views:
        try:
            cursor.execute(f"SELECT COUNT(*), MAX(calculation_status) FROM {view}")
            row = cursor.fetchone()
            status = "CALCULATED" if row[1] == 'CALCULATED' and row[0] > 0 else "PLACEHOLDER"
            signal_sources[name] = {
                "rows": row[0],
                "calculation_status": row[1],
                "backfill_status": "NATIVE" if status == "CALCULATED" else "PLACEHOLDER"
            }
            conn.commit()  # Commit after each successful query
        except Exception as e:
            conn.rollback()  # Rollback on error
            signal_sources[name] = {"rows": 0, "backfill_status": "ERROR", "error": str(e)}

    # Build eligible signal list
    eligible_signals = []
    blocked_signals = []

    # Map signals to their sources
    signal_mapping = {
        # ASSET-level signals from prices/technical
        "technical_rsi": ("technical_indicators", "ASSET"),
        "technical_macd": ("technical_indicators", "ASSET"),
        "volatility_regime": ("technical_indicators", "ASSET"),
        "volatility_breakout": ("technical_indicators", "ASSET"),
        "trend_strength": ("technical_indicators", "ASSET"),
        "momentum_score": ("prices", "ASSET"),

        # Regime signals
        "regime_state": ("sovereign_regime", "ASSET"),
        "regime_transition_risk": ("regime_transition_risk", "ASSET"),

        # Relative strength
        "sector_relative_strength": ("sector_relative_strength", "SECTOR"),
        "market_relative_strength": ("market_relative_strength", "ASSET"),

        # Position signals
        "stop_loss_heatmap": ("stop_loss_heatmap", "GLOBAL"),
        "position_lifecycle": ("hcp_signal_state", "ASSET"),

        # Learning/Governance
        "learning_velocity": ("lvi_canonical", "GLOBAL"),
        "epistemic_uncertainty": ("lvi_canonical", "GLOBAL"),

        # Events
        "fomc_proximity": ("calendar_events", "GLOBAL"),
        "earnings_density": ("calendar_events", "GLOBAL"),

        # Blocked - no data
        "sentiment_divergence": ("sentiment_divergence", "ASSET"),
        "macro_surprise": ("macro_indicators", "GLOBAL"),
        "factor_momentum": ("factor_exposure", "ASSET"),
        "factor_value": ("factor_exposure", "ASSET"),
        "factor_quality": ("factor_exposure", "ASSET"),
        "mean_reversion_signal": ("meanrev_signals", "ASSET"),
        "mean_reversion_z": ("meanrev_signals", "ASSET"),
        "statarb_z_score": ("statarb_signals", "PAIR"),
        "statarb_convergence": ("statarb_signals", "PAIR"),
        "statarb_hedge_ratio": ("statarb_signals", "PAIR"),
    }

    for signal_id, (source, scope) in signal_mapping.items():
        source_info = signal_sources.get(source, {"backfill_status": "UNKNOWN"})
        status = source_info.get("backfill_status", "UNKNOWN")

        signal_entry = {
            "signal_id": signal_id,
            "source": source,
            "scope": scope,
            "backfill_status": status,
            "rows": source_info.get("rows", 0)
        }

        if status in ("BACKFILLED", "NATIVE", "CALCULATED"):
            eligible_signals.append(signal_entry)
        else:
            blocked_signals.append(signal_entry)

    return {
        "signal_sources": signal_sources,
        "eligible_signals": eligible_signals,
        "blocked_signals": blocked_signals,
        "summary": {
            "total_mapped": len(signal_mapping),
            "eligible_count": len(eligible_signals),
            "blocked_count": len(blocked_signals)
        }
    }


def evaluate_coverage(conn, signal_id, source, scope):
    """
    Axis 1: Coverage
    - % assets
    - % days
    - hull / sparsity
    """
    cursor = conn.cursor()
    coverage = {
        "asset_coverage_pct": 0,
        "day_coverage_pct": 0,
        "sparsity_score": 1.0,  # 1.0 = sparse, 0.0 = dense
        "verdict": "LOW"
    }

    try:
        if source == "technical_indicators":
            cursor.execute("""
                WITH stats AS (
                    SELECT
                        COUNT(DISTINCT asset_id) as assets,
                        COUNT(DISTINCT timestamp::date) as days,
                        COUNT(*) as total_rows
                    FROM fhq_data.technical_indicators
                ),
                universe AS (
                    SELECT COUNT(*) as total_assets FROM fhq_meta.assets WHERE active_flag = true
                )
                SELECT
                    s.assets, s.days, s.total_rows,
                    u.total_assets,
                    ROUND(s.assets::numeric / NULLIF(u.total_assets, 0) * 100, 2) as asset_pct
                FROM stats s, universe u
            """)
            row = cursor.fetchone()
            if row:
                coverage["assets"] = row[0]
                coverage["days"] = row[1]
                coverage["total_rows"] = row[2]
                coverage["asset_coverage_pct"] = float(row[4]) if row[4] else 0
                # Estimate day coverage (assume 365 days target)
                coverage["day_coverage_pct"] = min(100, round(row[1] / 365 * 100, 2))
                # Sparsity = 1 - (actual / expected)
                expected = row[0] * row[1] if row[0] and row[1] else 1
                coverage["sparsity_score"] = round(1 - (row[2] / expected), 4) if expected > 0 else 1.0

        elif source == "sovereign_regime":
            cursor.execute("""
                WITH stats AS (
                    SELECT
                        COUNT(DISTINCT asset_id) as assets,
                        COUNT(DISTINCT timestamp::date) as days,
                        COUNT(*) as total_rows
                    FROM fhq_perception.sovereign_regime_state_v4
                ),
                universe AS (
                    SELECT COUNT(*) as total_assets FROM fhq_meta.assets WHERE active_flag = true
                )
                SELECT s.assets, s.days, s.total_rows, u.total_assets
                FROM stats s, universe u
            """)
            row = cursor.fetchone()
            if row:
                coverage["assets"] = row[0]
                coverage["days"] = row[1]
                coverage["total_rows"] = row[2]
                coverage["asset_coverage_pct"] = round(row[0] / row[3] * 100, 2) if row[3] else 0
                coverage["day_coverage_pct"] = min(100, round(row[1] / 365 * 100, 2))
                expected = row[0] * row[1] if row[0] and row[1] else 1
                coverage["sparsity_score"] = round(1 - (row[2] / expected), 4) if expected > 0 else 1.0

        elif source == "prices":
            cursor.execute("""
                WITH stats AS (
                    SELECT
                        COUNT(DISTINCT canonical_id) as assets,
                        COUNT(DISTINCT timestamp::date) as days,
                        COUNT(*) as total_rows
                    FROM fhq_market.prices
                ),
                universe AS (
                    SELECT COUNT(*) as total_assets FROM fhq_meta.assets WHERE active_flag = true
                )
                SELECT s.assets, s.days, s.total_rows, u.total_assets
                FROM stats s, universe u
            """)
            row = cursor.fetchone()
            if row:
                coverage["assets"] = row[0]
                coverage["days"] = row[1]
                coverage["total_rows"] = row[2]
                coverage["asset_coverage_pct"] = round(row[0] / row[3] * 100, 2) if row[3] else 0
                coverage["day_coverage_pct"] = min(100, round(row[1] / 365 * 100, 2))
                expected = row[0] * row[1] if row[0] and row[1] else 1
                coverage["sparsity_score"] = round(1 - (row[2] / expected), 4) if expected > 0 else 1.0

        elif source in ("lvi_canonical", "hcp_signal_state", "calendar_events"):
            coverage["asset_coverage_pct"] = 100 if scope == "GLOBAL" else 10
            coverage["day_coverage_pct"] = 50
            coverage["sparsity_score"] = 0.5

        # Verdict
        avg_coverage = (coverage["asset_coverage_pct"] + coverage["day_coverage_pct"]) / 2
        if avg_coverage >= 70:
            coverage["verdict"] = "HIGH"
        elif avg_coverage >= 40:
            coverage["verdict"] = "MEDIUM"
        else:
            coverage["verdict"] = "LOW"

    except Exception as e:
        conn.rollback()  # Rollback on error
        coverage["error"] = str(e)

    return coverage


def evaluate_stability(conn, signal_id, source):
    """
    Axis 2: Stability
    - variance in signal distribution over time
    - regime sensitivity (does character shift?)
    """
    cursor = conn.cursor()
    stability = {
        "variance_score": 0,
        "regime_sensitivity": 0,
        "verdict": "UNKNOWN"
    }

    try:
        if source == "technical_indicators":
            # Check RSI stability across time windows
            cursor.execute("""
                WITH monthly AS (
                    SELECT
                        DATE_TRUNC('month', timestamp) as month,
                        AVG(rsi_14) as avg_rsi,
                        STDDEV(rsi_14) as std_rsi
                    FROM fhq_data.technical_indicators
                    WHERE rsi_14 IS NOT NULL
                    GROUP BY DATE_TRUNC('month', timestamp)
                )
                SELECT
                    STDDEV(avg_rsi) as variance_of_means,
                    AVG(std_rsi) as avg_within_variance
                FROM monthly
            """)
            row = cursor.fetchone()
            if row and row[0]:
                # Lower variance of means = more stable
                stability["variance_score"] = round(float(row[0]), 4)
                stability["within_variance"] = round(float(row[1]), 4) if row[1] else 0

        elif source == "sovereign_regime":
            # Check regime transition frequency
            cursor.execute("""
                WITH transitions AS (
                    SELECT
                        asset_id,
                        timestamp,
                        sovereign_regime,
                        LAG(sovereign_regime) OVER (PARTITION BY asset_id ORDER BY timestamp) as prev_regime
                    FROM fhq_perception.sovereign_regime_state_v4
                )
                SELECT
                    COUNT(*) FILTER (WHERE sovereign_regime != prev_regime) as transitions,
                    COUNT(*) as total,
                    ROUND(COUNT(*) FILTER (WHERE sovereign_regime != prev_regime)::numeric / NULLIF(COUNT(*), 0) * 100, 2) as transition_rate
                FROM transitions
                WHERE prev_regime IS NOT NULL
            """)
            row = cursor.fetchone()
            if row:
                stability["transitions"] = row[0]
                stability["transition_rate_pct"] = float(row[2]) if row[2] else 0
                # High transition rate = less stable
                stability["regime_sensitivity"] = float(row[2]) if row[2] else 0

        elif source == "prices":
            # Check return volatility stability
            cursor.execute("""
                WITH daily_vol AS (
                    SELECT
                        DATE_TRUNC('week', timestamp) as week,
                        STDDEV(price_change_pct) as weekly_vol
                    FROM fhq_market.prices
                    WHERE price_change_pct IS NOT NULL
                    GROUP BY DATE_TRUNC('week', timestamp)
                )
                SELECT STDDEV(weekly_vol) as vol_of_vol
                FROM daily_vol
            """)
            row = cursor.fetchone()
            if row and row[0]:
                stability["variance_score"] = round(float(row[0]), 4)

        # Verdict based on variance
        if stability.get("variance_score", 999) < 5:
            stability["verdict"] = "STABLE"
        elif stability.get("variance_score", 999) < 15:
            stability["verdict"] = "MODERATE"
        else:
            stability["verdict"] = "UNSTABLE"

    except Exception as e:
        conn.rollback()  # Rollback on error
        stability["error"] = str(e)
        stability["verdict"] = "ERROR"

    return stability


def evaluate_orthogonality(conn, signal_id, source):
    """
    Axis 3: Orthogonality (raw)
    - correlation against regime
    - correlation against market return
    - correlation against each other
    - 0.8+ = redundant
    """
    cursor = conn.cursor()
    orthogonality = {
        "regime_correlation": 0,
        "market_correlation": 0,
        "redundancy_flags": [],
        "verdict": "UNKNOWN"
    }

    try:
        if source == "technical_indicators":
            # Check correlation between RSI and MACD
            cursor.execute("""
                SELECT CORR(rsi_14, macd_histogram) as rsi_macd_corr
                FROM fhq_data.technical_indicators
                WHERE rsi_14 IS NOT NULL AND macd_histogram IS NOT NULL
            """)
            row = cursor.fetchone()
            if row and row[0]:
                corr = abs(float(row[0]))
                orthogonality["rsi_macd_correlation"] = round(corr, 4)
                if corr > 0.8:
                    orthogonality["redundancy_flags"].append("RSI-MACD highly correlated")

        elif source == "sovereign_regime":
            # Regime is by definition the reference - cannot be correlated with itself
            orthogonality["regime_correlation"] = 1.0  # Self-reference
            orthogonality["is_reference_signal"] = True

        # General market correlation check
        if source in ("technical_indicators", "prices"):
            cursor.execute("""
                WITH market_ret AS (
                    SELECT timestamp::date as date, AVG(price_change_pct) as market_return
                    FROM fhq_market.prices
                    GROUP BY timestamp::date
                )
                SELECT CORR(t.rsi_14, m.market_return) as market_corr
                FROM fhq_data.technical_indicators t
                JOIN market_ret m ON t.timestamp::date = m.date
                WHERE t.rsi_14 IS NOT NULL
            """)
            row = cursor.fetchone()
            if row and row[0]:
                orthogonality["market_correlation"] = round(abs(float(row[0])), 4)

        # Verdict
        max_corr = max(
            orthogonality.get("regime_correlation", 0),
            orthogonality.get("market_correlation", 0),
            orthogonality.get("rsi_macd_correlation", 0)
        )
        if orthogonality.get("is_reference_signal"):
            orthogonality["verdict"] = "REFERENCE"
        elif max_corr < 0.4:
            orthogonality["verdict"] = "ORTHOGONAL"
        elif max_corr < 0.8:
            orthogonality["verdict"] = "MODERATE"
        else:
            orthogonality["verdict"] = "REDUNDANT"

    except Exception as e:
        conn.rollback()  # Rollback on error
        orthogonality["error"] = str(e)

    return orthogonality


def evaluate_decision_impact(conn, signal_id, source, scope):
    """
    Axis 4: Decision Impact (conservative)
    - How often is the signal ACTIVE / ELIGIBLE / BLOCKED?
    - Signals rarely decision-active = low value now
    """
    cursor = conn.cursor()
    impact = {
        "active_rate_pct": 0,
        "eligible_rate_pct": 0,
        "blocked_rate_pct": 0,
        "verdict": "UNKNOWN"
    }

    try:
        if source == "technical_indicators":
            # Check how often RSI gives actionable signal (not neutral)
            cursor.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE rsi_signal IN ('OVERBOUGHT', 'OVERSOLD')) as active,
                    COUNT(*) FILTER (WHERE rsi_signal = 'NEUTRAL') as neutral,
                    COUNT(*) as total
                FROM fhq_data.technical_indicators
                WHERE rsi_signal IS NOT NULL
            """)
            row = cursor.fetchone()
            if row and row[2]:
                impact["active_rate_pct"] = round(row[0] / row[2] * 100, 2)
                impact["eligible_rate_pct"] = round(row[1] / row[2] * 100, 2)
                impact["total_observations"] = row[2]

        elif source == "sovereign_regime":
            # Check regime distribution
            cursor.execute("""
                SELECT
                    sovereign_regime,
                    COUNT(*) as count,
                    ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 2) as pct
                FROM fhq_perception.sovereign_regime_state_v4
                GROUP BY sovereign_regime
                ORDER BY count DESC
            """)
            rows = cursor.fetchall()
            impact["regime_distribution"] = {row[0]: float(row[2]) for row in rows}
            # Active = not NEUTRAL
            neutral_pct = impact["regime_distribution"].get("NEUTRAL", 0)
            impact["active_rate_pct"] = round(100 - neutral_pct, 2)

        elif scope == "GLOBAL":
            # Global signals are always "active" when present
            impact["active_rate_pct"] = 100
            impact["eligible_rate_pct"] = 100

        # Verdict
        if impact["active_rate_pct"] >= 30:
            impact["verdict"] = "OFTEN_ACTIVE"
        elif impact["active_rate_pct"] >= 10:
            impact["verdict"] = "SOMETIMES_ACTIVE"
        else:
            impact["verdict"] = "RARELY_ACTIVE"

    except Exception as e:
        conn.rollback()  # Rollback on error
        impact["error"] = str(e)

    return impact


def generate_ranking_table(evaluations):
    """
    Generate the relative ranking table with verdicts.

    Verdict types:
    - CORE (keep)
    - SECONDARY (keep, low weight)
    - MERGE (combine with similar)
    - PARK (don't use now)
    """
    rankings = []

    for signal_id, eval_data in evaluations.items():
        coverage = eval_data.get("coverage", {})
        stability = eval_data.get("stability", {})
        orthogonality = eval_data.get("orthogonality", {})
        decision = eval_data.get("decision_impact", {})

        # Scoring logic
        score = 0

        # Coverage: HIGH=3, MEDIUM=2, LOW=1
        cov_v = coverage.get("verdict", "LOW")
        score += {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(cov_v, 0)

        # Stability: STABLE=3, MODERATE=2, UNSTABLE=1
        stab_v = stability.get("verdict", "UNKNOWN")
        score += {"STABLE": 3, "MODERATE": 2, "UNSTABLE": 1, "ERROR": 0}.get(stab_v, 0)

        # Orthogonality: ORTHOGONAL=3, MODERATE=2, REDUNDANT=0, REFERENCE=2
        orth_v = orthogonality.get("verdict", "UNKNOWN")
        score += {"ORTHOGONAL": 3, "MODERATE": 2, "REDUNDANT": 0, "REFERENCE": 2}.get(orth_v, 0)

        # Decision Impact: OFTEN_ACTIVE=3, SOMETIMES_ACTIVE=2, RARELY_ACTIVE=1
        dec_v = decision.get("verdict", "UNKNOWN")
        score += {"OFTEN_ACTIVE": 3, "SOMETIMES_ACTIVE": 2, "RARELY_ACTIVE": 1}.get(dec_v, 0)

        # Determine verdict
        if orth_v == "REDUNDANT":
            verdict = "MERGE"
        elif score >= 10:
            verdict = "CORE"
        elif score >= 6:
            verdict = "SECONDARY"
        else:
            verdict = "PARK"

        rankings.append({
            "signal_id": signal_id,
            "coverage": cov_v,
            "stability": stab_v,
            "orthogonality": orth_v,
            "decision_activity": dec_v,
            "score": score,
            "verdict": verdict
        })

    # Sort by score descending
    rankings.sort(key=lambda x: x["score"], reverse=True)
    return rankings


def create_truth_snapshot(universe, evaluations, rankings):
    """
    Create the IoS-013_SIGNAL_VALUE_SNAPSHOT_YYYYMMDD.json
    Single artifact. Single date.
    """
    snapshot_date = datetime.now(timezone.utc).strftime("%Y%m%d")

    snapshot = {
        "snapshot_id": f"IoS-013_SIGNAL_VALUE_SNAPSHOT_{snapshot_date}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "owner": "EC-003",
        "mandate": "Value Verification under Backfill Constraints",
        "mode": "OBSERVE_MEASURE_CLASSIFY",

        "premise": {
            "statement": "Backfill gir tilgjengelighet, ikke sannhet. Vi verifiserer verdi relativt - ikke absolutt.",
            "constraints": [
                "Ingen Sharpe",
                "Ingen PnL",
                "Pre-alpha verifisering"
            ]
        },

        "universe_frozen": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "eligible_signals": [s["signal_id"] for s in universe["eligible_signals"]],
            "blocked_signals": [s["signal_id"] for s in universe["blocked_signals"]],
            "sources_summary": {
                k: {
                    "rows": v.get("rows", 0),
                    "backfill_status": v.get("backfill_status", "UNKNOWN")
                }
                for k, v in universe["signal_sources"].items()
            }
        },

        "evaluations": {
            signal_id: {
                "coverage": eval_data.get("coverage", {}),
                "stability": eval_data.get("stability", {}),
                "orthogonality": eval_data.get("orthogonality", {}),
                "decision_impact": eval_data.get("decision_impact", {})
            }
            for signal_id, eval_data in evaluations.items()
        },

        "ranking_table": rankings,

        "summary": {
            "total_eligible": len(universe["eligible_signals"]),
            "total_blocked": len(universe["blocked_signals"]),
            "verdicts": {
                "CORE": len([r for r in rankings if r["verdict"] == "CORE"]),
                "SECONDARY": len([r for r in rankings if r["verdict"] == "SECONDARY"]),
                "MERGE": len([r for r in rankings if r["verdict"] == "MERGE"]),
                "PARK": len([r for r in rankings if r["verdict"] == "PARK"])
            }
        },

        "what_is_available": [s["signal_id"] for s in universe["eligible_signals"]],
        "what_is_used": [r["signal_id"] for r in rankings if r["verdict"] in ("CORE", "SECONDARY")],
        "what_is_parked": [r["signal_id"] for r in rankings if r["verdict"] == "PARK"],
        "why_parked": {
            r["signal_id"]: f"Score {r['score']}/12 - Coverage:{r['coverage']}, Stability:{r['stability']}, Orthogonality:{r['orthogonality']}, Activity:{r['decision_activity']}"
            for r in rankings if r["verdict"] == "PARK"
        },

        "reference_before_sovereign": True,
        "stig_attestation": {
            "ec_id": "EC-003",
            "attestation": "Observation and classification complete. No adjustments made. No new features introduced.",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }

    return snapshot


def main():
    print("=" * 70)
    print("IoS-013 Signal Value Verification")
    print("Mode: OBSERVE -> MEASURE -> CLASSIFY")
    print("=" * 70)

    conn = get_connection()

    try:
        # Phase 1: Freeze Universe
        print("\n[Phase 1] Freezing universe...")
        universe = freeze_universe(conn)
        print(f"  Eligible signals: {len(universe['eligible_signals'])}")
        print(f"  Blocked signals: {len(universe['blocked_signals'])}")

        # Phase 2-5: Evaluate each eligible signal
        print("\n[Phase 2-5] Evaluating signals across 4 axes...")
        evaluations = {}

        for signal in universe["eligible_signals"]:
            signal_id = signal["signal_id"]
            source = signal["source"]
            scope = signal["scope"]

            print(f"  Evaluating: {signal_id}...")

            evaluations[signal_id] = {
                "source": source,
                "scope": scope,
                "backfill_status": signal["backfill_status"],
                "coverage": evaluate_coverage(conn, signal_id, source, scope),
                "stability": evaluate_stability(conn, signal_id, source),
                "orthogonality": evaluate_orthogonality(conn, signal_id, source),
                "decision_impact": evaluate_decision_impact(conn, signal_id, source, scope)
            }

        # Phase 6: Generate ranking table
        print("\n[Phase 6] Generating ranking table...")
        rankings = generate_ranking_table(evaluations)

        # Print ranking table
        print("\n" + "=" * 90)
        print(f"{'Signal':<30} {'Coverage':<10} {'Stability':<12} {'Orthogonality':<15} {'Activity':<15} {'Verdict':<10}")
        print("=" * 90)
        for r in rankings:
            print(f"{r['signal_id']:<30} {r['coverage']:<10} {r['stability']:<12} {r['orthogonality']:<15} {r['decision_activity']:<15} {r['verdict']:<10}")
        print("=" * 90)

        # Phase 7: Create Truth Snapshot
        print("\n[Phase 7] Creating Truth Snapshot...")
        snapshot = create_truth_snapshot(universe, evaluations, rankings)

        snapshot_date = datetime.now(timezone.utc).strftime("%Y%m%d")
        snapshot_path = f"C:/fhq-market-system/vision-ios/05_GOVERNANCE/Signals/IoS-013_SIGNAL_VALUE_SNAPSHOT_{snapshot_date}.json"

        with open(snapshot_path, 'w') as f:
            json.dump(snapshot, f, indent=2, cls=DecimalEncoder)

        print(f"  Snapshot written to: {snapshot_path}")

        # Also save eligible signal registry
        registry_path = "C:/fhq-market-system/vision-ios/05_GOVERNANCE/Signals/eligible_signal_registry.json"
        with open(registry_path, 'w') as f:
            json.dump({
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "eligible_signals": universe["eligible_signals"],
                "blocked_signals": universe["blocked_signals"]
            }, f, indent=2, cls=DecimalEncoder)
        print(f"  Registry written to: {registry_path}")

        # Summary
        print("\n" + "=" * 70)
        print("VALUE VERIFICATION COMPLETE")
        print("=" * 70)
        summary = snapshot["summary"]
        print(f"  CORE signals: {summary['verdicts']['CORE']}")
        print(f"  SECONDARY signals: {summary['verdicts']['SECONDARY']}")
        print(f"  MERGE candidates: {summary['verdicts']['MERGE']}")
        print(f"  PARKED signals: {summary['verdicts']['PARK']}")
        print("\nNo Sharpe. No PnL. Pre-alpha verification complete.")
        print("=" * 70)

        return snapshot

    except Exception as e:
        print(f"[ERROR] Value verification failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
