#!/usr/bin/env python3
"""
IoS-005 G3 Significance Engine
Constitutional Significance Testing for Macro Features

Authority: LARS (Strategy)
Executor: STIG (Technical)
Auditor: VEGA (Governance)

ADR Compliance: ADR-011, ADR-012, ADR-013, ADR-014

Test Battery per Feature:
- Permutation Test (1000 iterations)
- Bootstrap Test (1000 iterations)
- Lead-Lag Grid [0, 1, 3, 7, 14 days]

Golden Feature Definition:
p_perm < 0.05 AND p_boot < 0.05 at at least one lag
"""

import os
import sys
import json
import hashlib
import warnings
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd
from scipy import stats
import psycopg2
from psycopg2.extras import RealDictCursor

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

# Configuration
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Test Parameters
N_PERMUTATIONS = 1000
N_BOOTSTRAP = 1000
LAG_GRID = [0, 1, 3, 7, 14]
SIGNIFICANCE_THRESHOLD = 0.05

# Cluster Definitions
CLUSTER_CONFIG = {
    'LIQUIDITY': {
        'hypothesis': 'Liquidity drives crypto beta',
        'features': [
            'US_M2_YOY', 'FED_TOTAL_ASSETS', 'US_TGA_BALANCE',
            'FED_RRP_BALANCE', 'US_NET_LIQUIDITY', 'GLOBAL_M2_USD'
        ]
    },
    'CREDIT': {
        'hypothesis': 'Credit stress precedes liquidity withdrawal',
        'features': [
            'US_HY_SPREAD', 'US_IG_SPREAD', 'US_YIELD_CURVE_10Y2Y',
            'TED_SPREAD', 'US_FED_FUNDS_RATE', 'MOVE_INDEX'
        ]
    },
    'FACTOR': {
        'hypothesis': 'Real Rates and macro-gravity shape trend regimes',
        'features': [
            'US_10Y_REAL_RATE', 'GOLD_SPX_RATIO', 'COPPER_GOLD_RATIO'
        ]
    }
}


@dataclass
class SignificanceResult:
    """Result of significance testing for a single feature at a single lag"""
    feature_id: str
    lag_days: int
    n_observations: int
    correlation: float
    p_permutation: float
    p_bootstrap: float
    ci_lower: float
    ci_upper: float
    is_significant: bool
    direction: str  # POSITIVE, NEGATIVE, or NEUTRAL


@dataclass
class FeatureAuditResult:
    """Complete audit result for a single feature across all lags"""
    feature_id: str
    cluster: str
    hypothesis: str
    expected_direction: str
    data_start: str
    data_end: str
    n_observations: int
    lag_results: List[SignificanceResult]
    best_lag: int
    best_p_perm: float
    best_p_boot: float
    is_golden: bool
    status: str  # GOLDEN, SIGNIFICANT, NOT_SIGNIFICANT, NO_DATA, ERROR
    error_message: Optional[str] = None


def get_db_connection():
    """Create database connection"""
    return psycopg2.connect(**DB_CONFIG)


def fetch_btc_returns(conn) -> pd.DataFrame:
    """Fetch BTC daily returns as target variable"""
    query = """
    SELECT
        timestamp::date as date,
        close,
        (close / LAG(close) OVER (ORDER BY timestamp) - 1) as daily_return
    FROM fhq_market.prices
    WHERE canonical_id = 'BTC-USD'
    ORDER BY timestamp
    """
    df = pd.read_sql(query, conn)
    df['date'] = pd.to_datetime(df['date'])
    df = df.dropna(subset=['daily_return'])
    return df.set_index('date')


def fetch_feature_data(conn, feature_id: str) -> pd.DataFrame:
    """Fetch canonical series data for a feature"""
    query = """
    SELECT
        timestamp::date as date,
        value_raw,
        value_transformed,
        transformation_method
    FROM fhq_macro.canonical_series
    WHERE feature_id = %s
    ORDER BY timestamp
    """
    df = pd.read_sql(query, conn, params=(feature_id,))
    if df.empty:
        return df
    df['date'] = pd.to_datetime(df['date'])
    # Use transformed value if available, otherwise raw
    df['value'] = df['value_transformed'].fillna(df['value_raw'])
    return df.set_index('date')


def fetch_feature_metadata(conn, feature_id: str) -> Dict:
    """Fetch feature metadata from registry"""
    query = """
    SELECT feature_id, cluster, hypothesis, expected_direction,
           stationarity_method, is_stationary
    FROM fhq_macro.feature_registry
    WHERE feature_id = %s
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (feature_id,))
        row = cur.fetchone()
        return dict(row) if row else {}


def align_data(feature_df: pd.DataFrame, btc_df: pd.DataFrame, lag: int) -> Tuple[np.ndarray, np.ndarray]:
    """Align feature and BTC data with specified lag"""
    # Shift feature data by lag (positive lag means feature leads BTC)
    feature_shifted = feature_df['value'].shift(lag)

    # Merge on date
    merged = pd.merge(
        feature_shifted.reset_index(),
        btc_df[['daily_return']].reset_index(),
        on='date',
        how='inner'
    ).dropna()

    if len(merged) < 30:  # Minimum observations
        return np.array([]), np.array([])

    return merged['value'].values, merged['daily_return'].values


def permutation_test(x: np.ndarray, y: np.ndarray, n_permutations: int = 1000) -> Tuple[float, float]:
    """
    Permutation test for correlation significance.
    Returns: (observed_correlation, p_value)
    """
    if len(x) < 10:
        return 0.0, 1.0

    observed_corr = np.corrcoef(x, y)[0, 1]

    # Handle NaN correlation
    if np.isnan(observed_corr):
        return 0.0, 1.0

    # Permutation distribution
    perm_corrs = np.zeros(n_permutations)
    for i in range(n_permutations):
        y_perm = np.random.permutation(y)
        perm_corrs[i] = np.corrcoef(x, y_perm)[0, 1]

    # Two-tailed p-value
    p_value = np.mean(np.abs(perm_corrs) >= np.abs(observed_corr))

    return observed_corr, p_value


def bootstrap_test(x: np.ndarray, y: np.ndarray, n_bootstrap: int = 1000) -> Tuple[float, float, float, float]:
    """
    Bootstrap test for correlation confidence interval.
    Returns: (observed_correlation, p_value, ci_lower, ci_upper)
    """
    if len(x) < 10:
        return 0.0, 1.0, 0.0, 0.0

    observed_corr = np.corrcoef(x, y)[0, 1]

    if np.isnan(observed_corr):
        return 0.0, 1.0, 0.0, 0.0

    n = len(x)
    boot_corrs = np.zeros(n_bootstrap)

    for i in range(n_bootstrap):
        indices = np.random.randint(0, n, size=n)
        x_boot = x[indices]
        y_boot = y[indices]
        boot_corrs[i] = np.corrcoef(x_boot, y_boot)[0, 1]

    # Remove NaN values
    boot_corrs = boot_corrs[~np.isnan(boot_corrs)]

    if len(boot_corrs) == 0:
        return observed_corr, 1.0, 0.0, 0.0

    # Confidence interval (2.5th and 97.5th percentiles)
    ci_lower = np.percentile(boot_corrs, 2.5)
    ci_upper = np.percentile(boot_corrs, 97.5)

    # P-value: proportion of bootstrap samples with opposite sign or zero crossing
    if observed_corr > 0:
        p_value = np.mean(boot_corrs <= 0) * 2  # Two-tailed
    else:
        p_value = np.mean(boot_corrs >= 0) * 2

    p_value = min(p_value, 1.0)

    return observed_corr, p_value, ci_lower, ci_upper


def test_feature_at_lag(
    feature_df: pd.DataFrame,
    btc_df: pd.DataFrame,
    feature_id: str,
    lag: int
) -> SignificanceResult:
    """Test a single feature at a single lag"""
    x, y = align_data(feature_df, btc_df, lag)

    if len(x) < 30:
        return SignificanceResult(
            feature_id=feature_id,
            lag_days=lag,
            n_observations=len(x),
            correlation=0.0,
            p_permutation=1.0,
            p_bootstrap=1.0,
            ci_lower=0.0,
            ci_upper=0.0,
            is_significant=False,
            direction='INSUFFICIENT_DATA'
        )

    # Run permutation test
    corr_perm, p_perm = permutation_test(x, y, N_PERMUTATIONS)

    # Run bootstrap test
    corr_boot, p_boot, ci_lower, ci_upper = bootstrap_test(x, y, N_BOOTSTRAP)

    # Use permutation correlation (should be same as bootstrap)
    correlation = corr_perm

    # Determine significance
    is_significant = (p_perm < SIGNIFICANCE_THRESHOLD) and (p_boot < SIGNIFICANCE_THRESHOLD)

    # Determine direction
    if abs(correlation) < 0.01:
        direction = 'NEUTRAL'
    elif correlation > 0:
        direction = 'POSITIVE'
    else:
        direction = 'NEGATIVE'

    return SignificanceResult(
        feature_id=feature_id,
        lag_days=lag,
        n_observations=len(x),
        correlation=round(correlation, 6),
        p_permutation=round(p_perm, 6),
        p_bootstrap=round(p_boot, 6),
        ci_lower=round(ci_lower, 6),
        ci_upper=round(ci_upper, 6),
        is_significant=is_significant,
        direction=direction
    )


def audit_feature(
    conn,
    feature_id: str,
    btc_df: pd.DataFrame,
    cluster: str,
    hypothesis: str
) -> FeatureAuditResult:
    """Run complete audit on a single feature"""
    print(f"  Testing {feature_id}...", end=" ", flush=True)

    try:
        # Fetch feature metadata
        metadata = fetch_feature_metadata(conn, feature_id)
        expected_direction = metadata.get('expected_direction', 'UNKNOWN')

        # Fetch feature data
        feature_df = fetch_feature_data(conn, feature_id)

        if feature_df.empty:
            print("NO DATA")
            return FeatureAuditResult(
                feature_id=feature_id,
                cluster=cluster,
                hypothesis=hypothesis,
                expected_direction=expected_direction,
                data_start='N/A',
                data_end='N/A',
                n_observations=0,
                lag_results=[],
                best_lag=0,
                best_p_perm=1.0,
                best_p_boot=1.0,
                is_golden=False,
                status='NO_DATA',
                error_message='No data in canonical_series'
            )

        # Test at each lag
        lag_results = []
        for lag in LAG_GRID:
            result = test_feature_at_lag(feature_df, btc_df, feature_id, lag)
            lag_results.append(result)

        # Find best lag (lowest combined p-value)
        valid_results = [r for r in lag_results if r.n_observations >= 30]

        if not valid_results:
            print("INSUFFICIENT DATA")
            return FeatureAuditResult(
                feature_id=feature_id,
                cluster=cluster,
                hypothesis=hypothesis,
                expected_direction=expected_direction,
                data_start=str(feature_df.index.min().date()),
                data_end=str(feature_df.index.max().date()),
                n_observations=len(feature_df),
                lag_results=lag_results,
                best_lag=0,
                best_p_perm=1.0,
                best_p_boot=1.0,
                is_golden=False,
                status='INSUFFICIENT_DATA',
                error_message='Not enough overlapping observations with BTC'
            )

        # Find best lag by minimum combined p-value
        best_result = min(valid_results, key=lambda r: r.p_permutation + r.p_bootstrap)

        # Check if any lag is significant (Golden Feature criteria)
        is_golden = any(r.is_significant for r in valid_results)

        # Determine status
        if is_golden:
            status = 'GOLDEN'
        elif any(r.p_permutation < SIGNIFICANCE_THRESHOLD or r.p_bootstrap < SIGNIFICANCE_THRESHOLD
                 for r in valid_results):
            status = 'SIGNIFICANT'
        else:
            status = 'NOT_SIGNIFICANT'

        print(f"{status} (best lag={best_result.lag_days}, p_perm={best_result.p_permutation:.4f})")

        return FeatureAuditResult(
            feature_id=feature_id,
            cluster=cluster,
            hypothesis=hypothesis,
            expected_direction=expected_direction,
            data_start=str(feature_df.index.min().date()),
            data_end=str(feature_df.index.max().date()),
            n_observations=len(feature_df),
            lag_results=lag_results,
            best_lag=best_result.lag_days,
            best_p_perm=best_result.p_permutation,
            best_p_boot=best_result.p_bootstrap,
            is_golden=is_golden,
            status=status
        )

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return FeatureAuditResult(
            feature_id=feature_id,
            cluster=cluster,
            hypothesis=hypothesis,
            expected_direction='UNKNOWN',
            data_start='N/A',
            data_end='N/A',
            n_observations=0,
            lag_results=[],
            best_lag=0,
            best_p_perm=1.0,
            best_p_boot=1.0,
            is_golden=False,
            status='ERROR',
            error_message=str(e)
        )


def audit_cluster(
    conn,
    cluster_name: str,
    btc_df: pd.DataFrame
) -> Dict[str, Any]:
    """Run complete audit on a cluster"""
    config = CLUSTER_CONFIG[cluster_name]
    hypothesis = config['hypothesis']
    features = config['features']

    print(f"\n{'='*60}")
    print(f"CLUSTER: {cluster_name}")
    print(f"Hypothesis: {hypothesis}")
    print(f"Features: {len(features)}")
    print('='*60)

    results = []
    for feature_id in features:
        result = audit_feature(conn, feature_id, btc_df, cluster_name, hypothesis)
        results.append(result)

    # Summary statistics
    golden_count = sum(1 for r in results if r.is_golden)
    significant_count = sum(1 for r in results if r.status in ['GOLDEN', 'SIGNIFICANT'])
    no_data_count = sum(1 for r in results if r.status == 'NO_DATA')
    error_count = sum(1 for r in results if r.status == 'ERROR')

    print(f"\n--- {cluster_name} Summary ---")
    print(f"Golden Features: {golden_count}/{len(features)}")
    print(f"Significant: {significant_count}/{len(features)}")
    print(f"No Data: {no_data_count}/{len(features)}")
    print(f"Errors: {error_count}/{len(features)}")

    return {
        'cluster': cluster_name,
        'hypothesis': hypothesis,
        'feature_count': len(features),
        'golden_count': golden_count,
        'significant_count': significant_count,
        'no_data_count': no_data_count,
        'error_count': error_count,
        'results': [asdict(r) for r in results],
        'golden_features': [r.feature_id for r in results if r.is_golden]
    }


def generate_evidence(
    cluster_name: str,
    cluster_result: Dict[str, Any],
    sequence_number: int
) -> Dict[str, Any]:
    """Generate evidence artifact for a cluster audit"""
    timestamp = datetime.now(timezone.utc)
    date_str = timestamp.strftime('%Y%m%d')

    evidence = {
        'metadata': {
            'document_type': f'IOS005_G3_{cluster_name}_SIGNIFICANCE',
            'module': 'IoS-005',
            'phase': 'G3',
            'sequence': sequence_number,
            'generated_at': timestamp.isoformat(),
            'generated_by': 'STIG',
            'authority': 'LARS (Strategic)',
            'auditor': 'IoS-005 (Constitutional)',
            'oversight': 'VEGA (Tier-1 Governance)',
            'adr_compliance': ['ADR-011', 'ADR-012', 'ADR-013', 'ADR-014'],
            'hash_chain_id': 'HC-IOS-006-2026'
        },
        'test_configuration': {
            'n_permutations': N_PERMUTATIONS,
            'n_bootstrap': N_BOOTSTRAP,
            'lag_grid': LAG_GRID,
            'significance_threshold': SIGNIFICANCE_THRESHOLD,
            'golden_criteria': 'p_perm < 0.05 AND p_boot < 0.05 at least one lag'
        },
        'cluster_audit': {
            'cluster': cluster_name,
            'hypothesis': cluster_result['hypothesis'],
            'features_tested': cluster_result['feature_count'],
            'golden_features': cluster_result['golden_count'],
            'significant_features': cluster_result['significant_count'],
            'no_data_features': cluster_result['no_data_count'],
            'error_features': cluster_result['error_count']
        },
        'golden_feature_list': cluster_result['golden_features'],
        'feature_results': cluster_result['results'],
        'exit_criteria': {
            'all_features_tested': cluster_result['error_count'] == 0,
            'hypothesis_validated': cluster_result['golden_count'] > 0,
            'evidence_complete': True
        },
        'vega_attestation': {
            'required': True,
            'attested': False,
            'attestor': None,
            'timestamp': None,
            'notes': 'Awaiting VEGA attestation before proceeding to next cluster'
        }
    }

    # Compute integrity hash
    evidence_str = json.dumps(evidence, sort_keys=True, default=str)
    evidence['integrity_hash'] = hashlib.sha256(evidence_str.encode()).hexdigest()

    return evidence


def save_evidence(evidence: Dict[str, Any], cluster_name: str) -> str:
    """Save evidence to file"""
    date_str = datetime.now(timezone.utc).strftime('%Y%m%d')
    sequence = evidence['metadata']['sequence']
    filename = f"G3_{sequence}_{cluster_name}_SIGNIFICANCE_{date_str}.json"
    filepath = os.path.join('evidence', filename)

    os.makedirs('evidence', exist_ok=True)

    with open(filepath, 'w') as f:
        json.dump(evidence, f, indent=2, default=str)

    return filepath


def run_cluster_audit(cluster_name: str) -> Tuple[str, Dict[str, Any]]:
    """
    Run complete G3 audit for a single cluster.
    Returns: (evidence_filepath, evidence_dict)
    """
    sequence_map = {'LIQUIDITY': 1, 'CREDIT': 2, 'FACTOR': 3}
    sequence = sequence_map.get(cluster_name, 0)

    print(f"\n{'#'*60}")
    print(f"IoS-005 G3 SIGNIFICANCE ENGINE")
    print(f"Cluster: {cluster_name}")
    print(f"Sequence: {sequence}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print('#'*60)

    conn = get_db_connection()

    try:
        # Fetch BTC returns (target variable)
        print("\nFetching BTC returns (target variable)...")
        btc_df = fetch_btc_returns(conn)
        print(f"BTC data: {len(btc_df)} observations ({btc_df.index.min().date()} to {btc_df.index.max().date()})")

        # Run cluster audit
        cluster_result = audit_cluster(conn, cluster_name, btc_df)

        # Generate evidence
        print("\nGenerating evidence artifact...")
        evidence = generate_evidence(cluster_name, cluster_result, sequence)

        # Save evidence
        filepath = save_evidence(evidence, cluster_name)
        print(f"Evidence saved: {filepath}")
        print(f"Integrity hash: {evidence['integrity_hash']}")

        return filepath, evidence

    finally:
        conn.close()


def main():
    """Main entry point"""
    # If no cluster specified, run ALL clusters sequentially
    if len(sys.argv) < 2:
        print("No cluster specified - running ALL clusters sequentially")
        all_results = []
        for cluster_name in CLUSTER_CONFIG.keys():
            try:
                filepath, evidence = run_cluster_audit(cluster_name)
                all_results.append({
                    'cluster': cluster_name,
                    'filepath': filepath,
                    'golden_count': len(evidence['golden_feature_list']),
                    'hash': evidence['integrity_hash']
                })
            except Exception as e:
                print(f"ERROR running {cluster_name}: {e}")
                all_results.append({
                    'cluster': cluster_name,
                    'error': str(e)
                })

        print(f"\n{'='*60}")
        print("G3 AUDIT COMPLETE - ALL CLUSTERS")
        for result in all_results:
            if 'error' in result:
                print(f"  {result['cluster']}: ERROR - {result['error']}")
            else:
                print(f"  {result['cluster']}: {result['golden_count']} golden features")
        print('='*60)
        return

    cluster_name = sys.argv[1].upper()

    if cluster_name not in CLUSTER_CONFIG:
        print(f"Error: Unknown cluster '{cluster_name}'")
        print(f"Valid clusters: {', '.join(CLUSTER_CONFIG.keys())}")
        sys.exit(1)

    filepath, evidence = run_cluster_audit(cluster_name)

    print(f"\n{'='*60}")
    print("G3 AUDIT COMPLETE")
    print(f"Cluster: {cluster_name}")
    print(f"Golden Features: {len(evidence['golden_feature_list'])}")
    print(f"Evidence: {filepath}")
    print(f"Hash: {evidence['integrity_hash']}")
    print("\nAwaiting VEGA attestation...")
    print('='*60)


if __name__ == '__main__':
    main()
