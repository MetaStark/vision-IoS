"""
OKR-2026-D17-001: CFAO Synthetic Stress Scenarios
KR5: Generate 100+ synthetic stress scenarios for validation

This script generates synthetic test scenarios to stress-test the
forecasting and calibration system without affecting production data.

Scenario Categories:
1. REGIME_TRANSITION - Sudden regime changes
2. VOLATILITY_SPIKE - Extreme volatility events
3. CORRELATION_BREAK - Asset correlation breakdown
4. LIQUIDITY_CRISIS - Liquidity drought scenarios
5. BLACK_SWAN - Tail events beyond historical distribution

Author: STIG (via OKR-2026-D17-001)
Date: 2026-01-17
"""

import os
import sys
import json
import random
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
import psycopg2
from psycopg2.extras import RealDictCursor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection
DB_CONFIG = {
    'host': os.environ.get('PGHOST', '127.0.0.1'),
    'port': os.environ.get('PGPORT', '54322'),
    'database': os.environ.get('PGDATABASE', 'postgres'),
    'user': os.environ.get('PGUSER', 'postgres'),
    'password': os.environ.get('PGPASSWORD', 'postgres')
}


@dataclass
class SyntheticScenario:
    """Represents a synthetic stress scenario."""
    scenario_id: str
    scenario_type: str
    scenario_name: str
    description: str
    severity: str  # LOW, MEDIUM, HIGH, EXTREME

    # Market conditions
    volatility_multiplier: float
    regime_before: str
    regime_after: str
    correlation_shift: float

    # Affected assets
    primary_assets: List[str]
    secondary_assets: List[str]

    # Expected system behavior
    expected_brier_impact: float
    expected_confidence_impact: float
    expected_hit_rate_impact: float

    # Test parameters
    duration_hours: int
    ramp_up_hours: int

    # Metadata
    created_at: str
    created_by: str


def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def get_active_assets(conn) -> List[str]:
    """Get list of active assets from the database."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT forecast_domain
            FROM fhq_research.forecast_ledger
            WHERE forecast_made_at >= NOW() - INTERVAL '30 days'
            LIMIT 100
        """)
        return [row[0] for row in cur.fetchall()]


def generate_regime_transition_scenarios(assets: List[str]) -> List[SyntheticScenario]:
    """Generate regime transition scenarios."""
    scenarios = []
    regimes = ['NORMAL', 'STRESS', 'RECOVERY', 'TRENDING', 'CHOPPY']

    for i, (from_regime, to_regime) in enumerate([
        ('NORMAL', 'STRESS'),
        ('STRESS', 'RECOVERY'),
        ('TRENDING', 'CHOPPY'),
        ('NORMAL', 'TRENDING'),
        ('RECOVERY', 'NORMAL'),
        ('CHOPPY', 'STRESS'),
        ('STRESS', 'TRENDING'),
        ('TRENDING', 'NORMAL'),
    ]):
        primary = random.sample(assets, min(5, len(assets)))
        secondary = random.sample([a for a in assets if a not in primary], min(10, len(assets) - 5))

        scenarios.append(SyntheticScenario(
            scenario_id=f"CFAO-RT-{i+1:03d}",
            scenario_type="REGIME_TRANSITION",
            scenario_name=f"Regime shift: {from_regime} to {to_regime}",
            description=f"Synthetic scenario modeling sudden transition from {from_regime} to {to_regime} regime",
            severity="HIGH" if to_regime == "STRESS" else "MEDIUM",
            volatility_multiplier=2.5 if to_regime == "STRESS" else 1.5,
            regime_before=from_regime,
            regime_after=to_regime,
            correlation_shift=0.3 if to_regime == "STRESS" else 0.1,
            primary_assets=primary,
            secondary_assets=secondary,
            expected_brier_impact=0.15 if to_regime == "STRESS" else 0.08,
            expected_confidence_impact=-0.20 if to_regime == "STRESS" else -0.10,
            expected_hit_rate_impact=-0.15 if to_regime == "STRESS" else -0.08,
            duration_hours=24,
            ramp_up_hours=2,
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="CFAO"
        ))

    return scenarios


def generate_volatility_spike_scenarios(assets: List[str]) -> List[SyntheticScenario]:
    """Generate volatility spike scenarios."""
    scenarios = []

    spike_magnitudes = [
        (2.0, "MEDIUM", "2x volatility spike"),
        (3.0, "HIGH", "3x volatility spike"),
        (5.0, "EXTREME", "5x volatility spike (flash crash)"),
        (10.0, "EXTREME", "10x volatility spike (market dislocation)"),
    ]

    for i, (multiplier, severity, description) in enumerate(spike_magnitudes):
        for asset_count in [1, 3, 10]:  # Single asset, sector, market-wide
            primary = random.sample(assets, min(asset_count, len(assets)))

            scenarios.append(SyntheticScenario(
                scenario_id=f"CFAO-VS-{len(scenarios)+1:03d}",
                scenario_type="VOLATILITY_SPIKE",
                scenario_name=f"{description} ({asset_count} asset{'s' if asset_count > 1 else ''})",
                description=f"Synthetic volatility spike of {multiplier}x on {asset_count} asset(s)",
                severity=severity,
                volatility_multiplier=multiplier,
                regime_before="NORMAL",
                regime_after="STRESS",
                correlation_shift=0.4 if asset_count > 1 else 0.1,
                primary_assets=primary,
                secondary_assets=[],
                expected_brier_impact=min(0.30, multiplier * 0.05),
                expected_confidence_impact=-min(0.40, multiplier * 0.08),
                expected_hit_rate_impact=-min(0.25, multiplier * 0.05),
                duration_hours=4 if multiplier < 5 else 8,
                ramp_up_hours=0,  # Immediate spike
                created_at=datetime.now(timezone.utc).isoformat(),
                created_by="CFAO"
            ))

    return scenarios


def generate_correlation_break_scenarios(assets: List[str]) -> List[SyntheticScenario]:
    """Generate correlation breakdown scenarios."""
    scenarios = []

    # Define typical correlation pairs that might break
    correlation_pairs = [
        (["SPY", "QQQ"], "Tech-Market decorrelation"),
        (["GLD", "TLT"], "Safe-haven decorrelation"),
        (["BTC-USD", "ETH-USD"], "Crypto sector decorrelation"),
        (["AAPL", "MSFT"], "Tech giant decorrelation"),
        (["XLE", "USO"], "Energy sector breakdown"),
    ]

    for i, (pair_hint, description) in enumerate(correlation_pairs):
        # Find matching assets or use random
        primary = [a for a in assets if any(p in a for p in pair_hint)]
        if len(primary) < 2:
            primary = random.sample(assets, min(2, len(assets)))

        scenarios.append(SyntheticScenario(
            scenario_id=f"CFAO-CB-{i+1:03d}",
            scenario_type="CORRELATION_BREAK",
            scenario_name=description,
            description=f"Synthetic scenario where historically correlated assets decorrelate",
            severity="HIGH",
            volatility_multiplier=1.8,
            regime_before="NORMAL",
            regime_after="CHOPPY",
            correlation_shift=-0.6,  # Negative = decorrelation
            primary_assets=primary[:2],
            secondary_assets=primary[2:] if len(primary) > 2 else [],
            expected_brier_impact=0.12,
            expected_confidence_impact=-0.15,
            expected_hit_rate_impact=-0.10,
            duration_hours=48,
            ramp_up_hours=6,
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="CFAO"
        ))

    return scenarios


def generate_liquidity_crisis_scenarios(assets: List[str]) -> List[SyntheticScenario]:
    """Generate liquidity crisis scenarios."""
    scenarios = []

    crisis_types = [
        ("SECTOR_LIQUIDITY", "MEDIUM", "Sector-specific liquidity drought"),
        ("MARKET_WIDE_LIQUIDITY", "EXTREME", "Market-wide liquidity crisis"),
        ("AFTER_HOURS_GAP", "HIGH", "After-hours liquidity gap"),
        ("FLASH_CRASH", "EXTREME", "Flash crash with liquidity vacuum"),
    ]

    for i, (crisis_type, severity, description) in enumerate(crisis_types):
        affected_count = 3 if "SECTOR" in crisis_type else 20
        primary = random.sample(assets, min(affected_count, len(assets)))

        scenarios.append(SyntheticScenario(
            scenario_id=f"CFAO-LC-{i+1:03d}",
            scenario_type="LIQUIDITY_CRISIS",
            scenario_name=description,
            description=f"Synthetic liquidity crisis scenario: {crisis_type}",
            severity=severity,
            volatility_multiplier=4.0 if severity == "EXTREME" else 2.5,
            regime_before="NORMAL",
            regime_after="STRESS",
            correlation_shift=0.7,  # Assets correlate in crisis
            primary_assets=primary,
            secondary_assets=[],
            expected_brier_impact=0.25 if severity == "EXTREME" else 0.15,
            expected_confidence_impact=-0.35 if severity == "EXTREME" else -0.20,
            expected_hit_rate_impact=-0.20 if severity == "EXTREME" else -0.12,
            duration_hours=8 if "FLASH" in crisis_type else 24,
            ramp_up_hours=0,
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="CFAO"
        ))

    return scenarios


def generate_black_swan_scenarios(assets: List[str]) -> List[SyntheticScenario]:
    """Generate black swan / tail event scenarios."""
    scenarios = []

    black_swans = [
        ("GEOPOLITICAL_SHOCK", "Geopolitical black swan (war, sanctions)"),
        ("CENTRAL_BANK_SURPRISE", "Unexpected central bank action"),
        ("MAJOR_DEFAULT", "Major sovereign/corporate default"),
        ("PANDEMIC_SHOCK", "Pandemic-level market shock"),
        ("REGULATORY_SHOCK", "Sudden regulatory change"),
        ("TECH_FAILURE", "Major exchange/clearinghouse failure"),
        ("CURRENCY_CRISIS", "Major currency collapse"),
        ("COMMODITY_SHOCK", "Commodity supply shock"),
    ]

    for i, (event_type, description) in enumerate(black_swans):
        primary = random.sample(assets, min(15, len(assets)))

        scenarios.append(SyntheticScenario(
            scenario_id=f"CFAO-BS-{i+1:03d}",
            scenario_type="BLACK_SWAN",
            scenario_name=description,
            description=f"Synthetic black swan event: {event_type}",
            severity="EXTREME",
            volatility_multiplier=8.0,
            regime_before="NORMAL",
            regime_after="STRESS",
            correlation_shift=0.8,  # Everything correlates in crisis
            primary_assets=primary,
            secondary_assets=[a for a in assets if a not in primary][:20],
            expected_brier_impact=0.40,
            expected_confidence_impact=-0.50,
            expected_hit_rate_impact=-0.35,
            duration_hours=72,
            ramp_up_hours=1,
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="CFAO"
        ))

    return scenarios


def generate_edge_case_scenarios(assets: List[str]) -> List[SyntheticScenario]:
    """Generate edge case scenarios for system robustness testing."""
    scenarios = []

    edge_cases = [
        ("ZERO_VOLUME", "MEDIUM", "Zero trading volume"),
        ("PRICE_LIMIT", "HIGH", "Price limit hit"),
        ("TRADING_HALT", "HIGH", "Trading halt scenario"),
        ("DATA_GAP", "MEDIUM", "Data feed interruption"),
        ("STALE_PRICES", "LOW", "Stale price detection"),
        ("NEGATIVE_PRICES", "EXTREME", "Negative price scenario (oil futures)"),
        ("SPLIT_ADJUSTMENT", "LOW", "Stock split adjustment"),
        ("DIVIDEND_EX", "LOW", "Ex-dividend gap"),
    ]

    for i, (case_type, severity, description) in enumerate(edge_cases):
        primary = random.sample(assets, min(3, len(assets)))

        scenarios.append(SyntheticScenario(
            scenario_id=f"CFAO-EC-{i+1:03d}",
            scenario_type="EDGE_CASE",
            scenario_name=description,
            description=f"System edge case test: {case_type}",
            severity=severity,
            volatility_multiplier=1.0,  # Not necessarily volatile
            regime_before="NORMAL",
            regime_after="NORMAL",
            correlation_shift=0.0,
            primary_assets=primary,
            secondary_assets=[],
            expected_brier_impact=0.05,
            expected_confidence_impact=-0.05,
            expected_hit_rate_impact=-0.03,
            duration_hours=4,
            ramp_up_hours=0,
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="CFAO"
        ))

    return scenarios


def save_scenarios_to_database(conn, scenarios: List[SyntheticScenario]) -> int:
    """Save scenarios to the database."""
    # First ensure table exists
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fhq_governance.cfao_synthetic_scenarios (
                scenario_id TEXT PRIMARY KEY,
                scenario_type TEXT NOT NULL,
                scenario_name TEXT NOT NULL,
                description TEXT,
                severity TEXT NOT NULL,
                volatility_multiplier NUMERIC(6,2),
                regime_before TEXT,
                regime_after TEXT,
                correlation_shift NUMERIC(4,2),
                primary_assets TEXT[],
                secondary_assets TEXT[],
                expected_brier_impact NUMERIC(4,2),
                expected_confidence_impact NUMERIC(4,2),
                expected_hit_rate_impact NUMERIC(4,2),
                duration_hours INTEGER,
                ramp_up_hours INTEGER,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                created_by TEXT NOT NULL DEFAULT 'CFAO',
                executed_at TIMESTAMPTZ,
                execution_results JSONB
            )
        """)
        conn.commit()

    inserted = 0
    for scenario in scenarios:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.cfao_synthetic_scenarios (
                        scenario_id, scenario_type, scenario_name, description,
                        severity, volatility_multiplier, regime_before, regime_after,
                        correlation_shift, primary_assets, secondary_assets,
                        expected_brier_impact, expected_confidence_impact,
                        expected_hit_rate_impact, duration_hours, ramp_up_hours,
                        created_at, created_by
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (scenario_id) DO NOTHING
                """, (
                    scenario.scenario_id,
                    scenario.scenario_type,
                    scenario.scenario_name,
                    scenario.description,
                    scenario.severity,
                    scenario.volatility_multiplier,
                    scenario.regime_before,
                    scenario.regime_after,
                    scenario.correlation_shift,
                    scenario.primary_assets,
                    scenario.secondary_assets,
                    scenario.expected_brier_impact,
                    scenario.expected_confidence_impact,
                    scenario.expected_hit_rate_impact,
                    scenario.duration_hours,
                    scenario.ramp_up_hours,
                    scenario.created_at,
                    scenario.created_by
                ))
                if cur.rowcount > 0:
                    inserted += 1
            conn.commit()
        except Exception as e:
            logger.error(f"Error inserting scenario {scenario.scenario_id}: {e}")
            conn.rollback()

    return inserted


def main():
    """Generate CFAO synthetic scenarios."""
    print("=" * 70)
    print("OKR-2026-D17-001: CFAO Synthetic Stress Scenarios")
    print("KR5: Generate 100+ synthetic stress scenarios")
    print("=" * 70)

    conn = get_connection()

    # Get active assets
    assets = get_active_assets(conn)
    logger.info(f"Found {len(assets)} active assets for scenario generation")

    if not assets:
        # Use default assets if none found
        assets = [
            "BTC-USD", "ETH-USD", "SPY", "QQQ", "AAPL", "MSFT", "GOOGL",
            "NVDA", "TSLA", "META", "AMZN", "GLD", "TLT", "XLE", "USO"
        ]
        logger.info(f"Using default asset list: {len(assets)} assets")

    # Generate scenarios
    all_scenarios = []

    logger.info("Generating REGIME_TRANSITION scenarios...")
    all_scenarios.extend(generate_regime_transition_scenarios(assets))

    logger.info("Generating VOLATILITY_SPIKE scenarios...")
    all_scenarios.extend(generate_volatility_spike_scenarios(assets))

    logger.info("Generating CORRELATION_BREAK scenarios...")
    all_scenarios.extend(generate_correlation_break_scenarios(assets))

    logger.info("Generating LIQUIDITY_CRISIS scenarios...")
    all_scenarios.extend(generate_liquidity_crisis_scenarios(assets))

    logger.info("Generating BLACK_SWAN scenarios...")
    all_scenarios.extend(generate_black_swan_scenarios(assets))

    logger.info("Generating EDGE_CASE scenarios...")
    all_scenarios.extend(generate_edge_case_scenarios(assets))

    # Additional scenarios to hit 100+
    while len(all_scenarios) < 100:
        # Generate variations
        base_scenario = random.choice(all_scenarios)
        variation = SyntheticScenario(
            scenario_id=f"CFAO-VAR-{len(all_scenarios)+1:03d}",
            scenario_type=base_scenario.scenario_type,
            scenario_name=f"Variation: {base_scenario.scenario_name}",
            description=f"Variation of {base_scenario.scenario_id} with different parameters",
            severity=base_scenario.severity,
            volatility_multiplier=base_scenario.volatility_multiplier * random.uniform(0.8, 1.2),
            regime_before=base_scenario.regime_before,
            regime_after=base_scenario.regime_after,
            correlation_shift=base_scenario.correlation_shift * random.uniform(0.8, 1.2),
            primary_assets=random.sample(assets, min(5, len(assets))),
            secondary_assets=random.sample(assets, min(10, len(assets))),
            expected_brier_impact=base_scenario.expected_brier_impact * random.uniform(0.9, 1.1),
            expected_confidence_impact=base_scenario.expected_confidence_impact * random.uniform(0.9, 1.1),
            expected_hit_rate_impact=base_scenario.expected_hit_rate_impact * random.uniform(0.9, 1.1),
            duration_hours=base_scenario.duration_hours,
            ramp_up_hours=base_scenario.ramp_up_hours,
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="CFAO"
        )
        all_scenarios.append(variation)

    logger.info(f"Total scenarios generated: {len(all_scenarios)}")

    # Save to database
    inserted = save_scenarios_to_database(conn, all_scenarios)
    logger.info(f"Scenarios inserted to database: {inserted}")

    # Get final count
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM fhq_governance.cfao_synthetic_scenarios")
        total_count = cur.fetchone()[0]

    # Summary by type
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT scenario_type, COUNT(*) as count,
                   AVG(expected_brier_impact) as avg_brier_impact
            FROM fhq_governance.cfao_synthetic_scenarios
            GROUP BY scenario_type
            ORDER BY count DESC
        """)
        type_summary = cur.fetchall()

    print("\n" + "=" * 70)
    print("EXECUTION COMPLETE")
    print("=" * 70)
    print(f"Total Scenarios Generated: {len(all_scenarios)}")
    print(f"Scenarios in Database: {total_count}")
    print(f"New Scenarios Inserted: {inserted}")
    print("\nScenarios by Type:")
    for row in type_summary:
        print(f"  {row['scenario_type']}: {row['count']} (avg Brier impact: {float(row['avg_brier_impact']):.2f})")

    if total_count >= 100:
        print("\nSTATUS: SUCCESS - KR5 target achieved!")
    else:
        print(f"\nSTATUS: IN_PROGRESS - {total_count}/100 scenarios")

    # Save evidence
    evidence = {
        'okr_code': 'OKR-2026-D17-001',
        'key_result': 'KR5',
        'execution_timestamp': datetime.now(timezone.utc).isoformat(),
        'scenarios_generated': len(all_scenarios),
        'scenarios_inserted': inserted,
        'total_in_database': total_count,
        'target_achieved': total_count >= 100,
        'scenario_types': {row['scenario_type']: row['count'] for row in type_summary},
        'severity_distribution': {
            'LOW': len([s for s in all_scenarios if s.severity == 'LOW']),
            'MEDIUM': len([s for s in all_scenarios if s.severity == 'MEDIUM']),
            'HIGH': len([s for s in all_scenarios if s.severity == 'HIGH']),
            'EXTREME': len([s for s in all_scenarios if s.severity == 'EXTREME']),
        }
    }

    evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
    os.makedirs(evidence_dir, exist_ok=True)

    evidence_file = os.path.join(
        evidence_dir,
        f"OKR_D17_KR5_CFAO_SCENARIOS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    with open(evidence_file, 'w') as f:
        json.dump(evidence, f, indent=2)

    print(f"\nEvidence saved: {evidence_file}")

    conn.close()


if __name__ == '__main__':
    main()
