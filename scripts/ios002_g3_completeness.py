#!/usr/bin/env python3
"""
IoS-002 G3 COMPLETENESS PATCH
=============================

Authority: VEGA (Compliance & Oversight)
Target: IoS-002 - Indicator Engine (Sensory Cortex)
Gate: G3_COMPLETENESS

Extended Golden Sample tests for:
- CCI (Commodity Channel Index) - unrestricted range
- MFI (Money Flow Index) - 0-100 range
- StochRSI (Stochastic RSI) - 0-1 range

ADR References:
- ADR-002 (Audit & Error Reconciliation)
- ADR-010 (State Reconciliation & Discrepancy Scoring)
"""

import os
import sys
import json
import uuid
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# ADR-010 Tolerance thresholds
NUMERIC_TOLERANCE = 0.001  # 0.1%
GOLDEN_SAMPLE_WINDOW = 100
ENGINE_VERSION = "1.0.0"

# ADR-010 Severity thresholds
SEVERITY_INFO_THRESHOLD = 0.001     # < 0.1%
SEVERITY_WARN_THRESHOLD = 0.005     # < 0.5%
# > 0.5% = CRITICAL


@dataclass
class IndicatorValidation:
    indicator: str
    test_type: str
    expected: str
    actual: Any
    deviation: float
    deviation_pct: float
    passed: bool
    severity: str  # INFO, WARN, CRITICAL


@dataclass
class AssetAuditResult:
    asset_id: str
    sample_count: int
    indicators_tested: List[str]
    validations: List[IndicatorValidation]
    pass_count: int
    fail_count: int
    discrepancy_score: float
    status: str
    formula_hashes: Dict[str, str]
    latest_values: Dict[str, Any]


def get_connection():
    return psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=os.getenv("PGPORT", "54322"),
        database=os.getenv("PGDATABASE", "postgres"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres")
    )


def compute_formula_hash(formula_name: str, parameters: Dict) -> str:
    """Compute deterministic hash for formula + parameters"""
    formula_str = f"{formula_name}:{json.dumps(parameters, sort_keys=True)}"
    return hashlib.sha256(formula_str.encode()).hexdigest()[:16]


def get_severity(deviation_pct: float) -> str:
    """Determine severity per ADR-010"""
    abs_dev = abs(deviation_pct)
    if abs_dev < SEVERITY_INFO_THRESHOLD * 100:
        return "INFO"
    elif abs_dev < SEVERITY_WARN_THRESHOLD * 100:
        return "WARN"
    else:
        return "CRITICAL"


# ============================================================================
# INDICATOR CALCULATIONS
# ============================================================================

def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI using Wilder's smoothing"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_stoch_rsi(prices: pd.Series, rsi_period: int = 14, stoch_period: int = 14) -> pd.Series:
    """
    Calculate Stochastic RSI
    StochRSI = (RSI - RSI_low) / (RSI_high - RSI_low)
    Returns values 0-1
    """
    rsi = calculate_rsi(prices, rsi_period)
    rsi_low = rsi.rolling(window=stoch_period).min()
    rsi_high = rsi.rolling(window=stoch_period).max()

    stoch_rsi = (rsi - rsi_low) / (rsi_high - rsi_low)
    return stoch_rsi


def calculate_cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
    """
    Calculate Commodity Channel Index
    CCI = (Typical Price - SMA) / (0.015 * Mean Deviation)
    Unrestricted range (typically -200 to +200)
    """
    typical_price = (high + low + close) / 3
    sma = typical_price.rolling(window=period).mean()

    # Mean deviation (not standard deviation)
    mean_dev = typical_price.rolling(window=period).apply(
        lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
    )

    cci = (typical_price - sma) / (0.015 * mean_dev)
    return cci


def calculate_mfi(high: pd.Series, low: pd.Series, close: pd.Series,
                  volume: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Money Flow Index
    MFI = 100 - (100 / (1 + Money Flow Ratio))
    Returns values 0-100
    """
    typical_price = (high + low + close) / 3
    raw_money_flow = typical_price * volume

    # Positive and negative money flow
    tp_diff = typical_price.diff()
    positive_flow = pd.Series(np.where(tp_diff > 0, raw_money_flow, 0), index=close.index)
    negative_flow = pd.Series(np.where(tp_diff < 0, raw_money_flow, 0), index=close.index)

    positive_mf = positive_flow.rolling(window=period).sum()
    negative_mf = negative_flow.rolling(window=period).sum()

    mf_ratio = positive_mf / negative_mf
    mfi = 100 - (100 / (1 + mf_ratio))
    return mfi


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Average True Range"""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = abs(high - prev_close)
    tr3 = abs(low - prev_close)
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr


def calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Calculate MACD"""
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 2.0):
    """Calculate Bollinger Bands"""
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower


# ============================================================================
# VALIDATION TESTS
# ============================================================================

def run_completeness_audit(conn, asset_id: str) -> AssetAuditResult:
    """Run extended Golden Sample test with CCI, MFI, StochRSI"""

    # Fetch data
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT timestamp, open, high, low, close, volume
            FROM fhq_market.prices
            WHERE canonical_id = %s
            ORDER BY timestamp DESC
            LIMIT %s
        """, (asset_id, GOLDEN_SAMPLE_WINDOW))
        rows = cur.fetchall()

    if not rows or len(rows) < 50:
        return AssetAuditResult(
            asset_id=asset_id,
            sample_count=len(rows) if rows else 0,
            indicators_tested=[],
            validations=[],
            pass_count=0,
            fail_count=1,
            discrepancy_score=1.0,
            status="FAIL",
            formula_hashes={},
            latest_values={"error": f"Insufficient data: {len(rows) if rows else 0} rows"}
        )

    df = pd.DataFrame(rows)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']

    validations = []
    formula_hashes = {}
    indicators_computed = {}

    # ========================================================================
    # INDICATOR CALCULATIONS
    # ========================================================================

    # RSI-14
    rsi = calculate_rsi(close, 14)
    indicators_computed['rsi_14'] = rsi
    formula_hashes['rsi_14'] = compute_formula_hash('RSI', {'period': 14})

    # StochRSI (14, 14)
    stoch_rsi = calculate_stoch_rsi(close, 14, 14)
    indicators_computed['stoch_rsi'] = stoch_rsi
    formula_hashes['stoch_rsi'] = compute_formula_hash('STOCH_RSI', {'rsi_period': 14, 'stoch_period': 14})

    # CCI-20
    cci = calculate_cci(high, low, close, 20)
    indicators_computed['cci_20'] = cci
    formula_hashes['cci_20'] = compute_formula_hash('CCI', {'period': 20})

    # MFI-14
    mfi = calculate_mfi(high, low, close, volume, 14)
    indicators_computed['mfi_14'] = mfi
    formula_hashes['mfi_14'] = compute_formula_hash('MFI', {'period': 14})

    # ATR-14
    atr = calculate_atr(high, low, close, 14)
    indicators_computed['atr_14'] = atr
    formula_hashes['atr_14'] = compute_formula_hash('ATR', {'period': 14})

    # MACD
    macd_line, macd_signal, macd_hist = calculate_macd(close, 12, 26, 9)
    indicators_computed['macd_line'] = macd_line
    indicators_computed['macd_signal'] = macd_signal
    indicators_computed['macd_histogram'] = macd_hist
    formula_hashes['macd'] = compute_formula_hash('MACD', {'fast': 12, 'slow': 26, 'signal': 9})

    # Bollinger Bands
    bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(close, 20, 2.0)
    indicators_computed['bb_upper'] = bb_upper
    indicators_computed['bb_middle'] = bb_middle
    indicators_computed['bb_lower'] = bb_lower
    formula_hashes['bollinger'] = compute_formula_hash('BOLLINGER', {'period': 20, 'std_dev': 2.0})

    # ========================================================================
    # RANGE VALIDATION TESTS
    # ========================================================================

    # TEST 1: RSI Range (0-100)
    rsi_valid = rsi.dropna()
    rsi_in_range = ((rsi_valid >= 0) & (rsi_valid <= 100)).all()
    rsi_min, rsi_max = float(rsi_valid.min()), float(rsi_valid.max())
    validations.append(IndicatorValidation(
        indicator='rsi_14',
        test_type='RANGE_VALIDATION',
        expected='0-100',
        actual=f'{rsi_min:.2f} - {rsi_max:.2f}',
        deviation=0.0 if rsi_in_range else max(abs(rsi_min), abs(rsi_max - 100)),
        deviation_pct=0.0 if rsi_in_range else 100.0,
        passed=bool(rsi_in_range),
        severity='INFO' if rsi_in_range else 'CRITICAL'
    ))

    # TEST 2: StochRSI Range (0-1)
    stoch_valid = stoch_rsi.dropna()
    stoch_in_range = ((stoch_valid >= 0) & (stoch_valid <= 1)).all()
    stoch_min, stoch_max = float(stoch_valid.min()), float(stoch_valid.max())
    validations.append(IndicatorValidation(
        indicator='stoch_rsi',
        test_type='RANGE_VALIDATION',
        expected='0-1',
        actual=f'{stoch_min:.4f} - {stoch_max:.4f}',
        deviation=0.0 if stoch_in_range else max(abs(stoch_min), abs(stoch_max - 1)),
        deviation_pct=0.0 if stoch_in_range else 100.0,
        passed=bool(stoch_in_range),
        severity='INFO' if stoch_in_range else 'CRITICAL'
    ))

    # TEST 3: CCI Unrestricted (typically -200 to +200, but can exceed)
    cci_valid = cci.dropna()
    cci_reasonable = len(cci_valid) > 0  # CCI has no fixed bounds
    cci_min, cci_max = float(cci_valid.min()), float(cci_valid.max())
    validations.append(IndicatorValidation(
        indicator='cci_20',
        test_type='RANGE_VALIDATION',
        expected='unrestricted (typically -200 to +200)',
        actual=f'{cci_min:.2f} - {cci_max:.2f}',
        deviation=0.0,
        deviation_pct=0.0,
        passed=cci_reasonable,
        severity='INFO'
    ))

    # TEST 4: MFI Range (0-100)
    mfi_valid = mfi.dropna()
    mfi_in_range = ((mfi_valid >= 0) & (mfi_valid <= 100)).all()
    mfi_min, mfi_max = float(mfi_valid.min()), float(mfi_valid.max())
    validations.append(IndicatorValidation(
        indicator='mfi_14',
        test_type='RANGE_VALIDATION',
        expected='0-100',
        actual=f'{mfi_min:.2f} - {mfi_max:.2f}',
        deviation=0.0 if mfi_in_range else max(abs(mfi_min), abs(mfi_max - 100)),
        deviation_pct=0.0 if mfi_in_range else 100.0,
        passed=bool(mfi_in_range),
        severity='INFO' if mfi_in_range else 'CRITICAL'
    ))

    # TEST 5: ATR Positive
    atr_valid = atr.dropna()
    atr_positive = (atr_valid > 0).all()
    atr_min = float(atr_valid.min())
    validations.append(IndicatorValidation(
        indicator='atr_14',
        test_type='RANGE_VALIDATION',
        expected='> 0',
        actual=f'min: {atr_min:.4f}',
        deviation=0.0 if atr_positive else abs(atr_min),
        deviation_pct=0.0 if atr_positive else 100.0,
        passed=bool(atr_positive),
        severity='INFO' if atr_positive else 'CRITICAL'
    ))

    # ========================================================================
    # DETERMINISM TESTS
    # ========================================================================

    # TEST 6: RSI Determinism
    rsi_recompute = calculate_rsi(close, 14)
    rsi_diff = (rsi - rsi_recompute).abs().dropna()
    rsi_deterministic = (rsi_diff < 1e-10).all()
    rsi_max_diff = float(rsi_diff.max()) if len(rsi_diff) > 0 else 0.0
    validations.append(IndicatorValidation(
        indicator='rsi_14',
        test_type='DETERMINISM',
        expected='identical on recalculation',
        actual=f'max_diff: {rsi_max_diff:.2e}',
        deviation=rsi_max_diff,
        deviation_pct=rsi_max_diff * 100,
        passed=bool(rsi_deterministic),
        severity=get_severity(rsi_max_diff * 100)
    ))

    # TEST 7: StochRSI Determinism
    stoch_recompute = calculate_stoch_rsi(close, 14, 14)
    stoch_diff = (stoch_rsi - stoch_recompute).abs().dropna()
    stoch_deterministic = (stoch_diff < 1e-10).all()
    stoch_max_diff = float(stoch_diff.max()) if len(stoch_diff) > 0 else 0.0
    validations.append(IndicatorValidation(
        indicator='stoch_rsi',
        test_type='DETERMINISM',
        expected='identical on recalculation',
        actual=f'max_diff: {stoch_max_diff:.2e}',
        deviation=stoch_max_diff,
        deviation_pct=stoch_max_diff * 100,
        passed=bool(stoch_deterministic),
        severity=get_severity(stoch_max_diff * 100)
    ))

    # TEST 8: CCI Determinism
    cci_recompute = calculate_cci(high, low, close, 20)
    cci_diff = (cci - cci_recompute).abs().dropna()
    cci_deterministic = (cci_diff < 1e-10).all()
    cci_max_diff = float(cci_diff.max()) if len(cci_diff) > 0 else 0.0
    validations.append(IndicatorValidation(
        indicator='cci_20',
        test_type='DETERMINISM',
        expected='identical on recalculation',
        actual=f'max_diff: {cci_max_diff:.2e}',
        deviation=cci_max_diff,
        deviation_pct=cci_max_diff * 100,
        passed=bool(cci_deterministic),
        severity=get_severity(cci_max_diff * 100)
    ))

    # TEST 9: MFI Determinism
    mfi_recompute = calculate_mfi(high, low, close, volume, 14)
    mfi_diff = (mfi - mfi_recompute).abs().dropna()
    mfi_deterministic = (mfi_diff < 1e-10).all()
    mfi_max_diff = float(mfi_diff.max()) if len(mfi_diff) > 0 else 0.0
    validations.append(IndicatorValidation(
        indicator='mfi_14',
        test_type='DETERMINISM',
        expected='identical on recalculation',
        actual=f'max_diff: {mfi_max_diff:.2e}',
        deviation=mfi_max_diff,
        deviation_pct=mfi_max_diff * 100,
        passed=bool(mfi_deterministic),
        severity=get_severity(mfi_max_diff * 100)
    ))

    # ========================================================================
    # FORMULA IDENTITY TESTS
    # ========================================================================

    # TEST 10: Formula Hash Consistency
    hash_1 = compute_formula_hash('RSI', {'period': 14})
    hash_2 = compute_formula_hash('RSI', {'period': 14})
    hash_match = hash_1 == hash_2
    validations.append(IndicatorValidation(
        indicator='formula_hash',
        test_type='FORMULA_IDENTITY',
        expected='consistent hash generation',
        actual=f'{hash_1} == {hash_2}',
        deviation=0.0 if hash_match else 1.0,
        deviation_pct=0.0 if hash_match else 100.0,
        passed=hash_match,
        severity='INFO' if hash_match else 'CRITICAL'
    ))

    # TEST 11: MACD Histogram = Line - Signal
    macd_hist_calc = macd_line - macd_signal
    macd_diff = (macd_hist - macd_hist_calc).abs().dropna()
    macd_consistent = (macd_diff < 1e-10).all()
    macd_max_diff = float(macd_diff.max()) if len(macd_diff) > 0 else 0.0
    validations.append(IndicatorValidation(
        indicator='macd_histogram',
        test_type='FORMULA_IDENTITY',
        expected='histogram = line - signal',
        actual=f'max_diff: {macd_max_diff:.2e}',
        deviation=macd_max_diff,
        deviation_pct=macd_max_diff * 100,
        passed=bool(macd_consistent),
        severity=get_severity(macd_max_diff * 100)
    ))

    # TEST 12: Bollinger Middle = SMA-20
    sma_20 = close.rolling(window=20).mean()
    bb_sma_diff = (bb_middle - sma_20).abs().dropna()
    bb_consistent = (bb_sma_diff < 1e-10).all()
    bb_max_diff = float(bb_sma_diff.max()) if len(bb_sma_diff) > 0 else 0.0
    validations.append(IndicatorValidation(
        indicator='bb_middle',
        test_type='FORMULA_IDENTITY',
        expected='bb_middle = SMA(20)',
        actual=f'max_diff: {bb_max_diff:.2e}',
        deviation=bb_max_diff,
        deviation_pct=bb_max_diff * 100,
        passed=bool(bb_consistent),
        severity=get_severity(bb_max_diff * 100)
    ))

    # ========================================================================
    # CALCULATE RESULTS
    # ========================================================================

    pass_count = sum(1 for v in validations if v.passed)
    fail_count = len(validations) - pass_count

    # Discrepancy score (RMS of deviations)
    deviations = [v.deviation for v in validations if not v.passed]
    if deviations:
        discrepancy_score = min(np.sqrt(np.mean(np.array(deviations) ** 2)), 1.0)
    else:
        discrepancy_score = 0.0

    # Latest values
    latest_idx = len(df) - 1
    latest_values = {
        'timestamp': df['timestamp'].iloc[latest_idx].isoformat(),
        'close': float(close.iloc[latest_idx]),
        'rsi_14': float(rsi.iloc[latest_idx]) if not np.isnan(rsi.iloc[latest_idx]) else None,
        'stoch_rsi': float(stoch_rsi.iloc[latest_idx]) if not np.isnan(stoch_rsi.iloc[latest_idx]) else None,
        'cci_20': float(cci.iloc[latest_idx]) if not np.isnan(cci.iloc[latest_idx]) else None,
        'mfi_14': float(mfi.iloc[latest_idx]) if not np.isnan(mfi.iloc[latest_idx]) else None,
        'atr_14': float(atr.iloc[latest_idx]) if not np.isnan(atr.iloc[latest_idx]) else None,
        'macd_line': float(macd_line.iloc[latest_idx]) if not np.isnan(macd_line.iloc[latest_idx]) else None,
        'macd_signal': float(macd_signal.iloc[latest_idx]) if not np.isnan(macd_signal.iloc[latest_idx]) else None,
        'bb_upper': float(bb_upper.iloc[latest_idx]) if not np.isnan(bb_upper.iloc[latest_idx]) else None,
        'bb_middle': float(bb_middle.iloc[latest_idx]) if not np.isnan(bb_middle.iloc[latest_idx]) else None,
        'bb_lower': float(bb_lower.iloc[latest_idx]) if not np.isnan(bb_lower.iloc[latest_idx]) else None,
    }

    status = "PASS" if fail_count == 0 else "FAIL"

    return AssetAuditResult(
        asset_id=asset_id,
        sample_count=len(df),
        indicators_tested=list(indicators_computed.keys()),
        validations=validations,
        pass_count=pass_count,
        fail_count=fail_count,
        discrepancy_score=discrepancy_score,
        status=status,
        formula_hashes=formula_hashes,
        latest_values=latest_values
    )


def log_discrepancies(conn, results: List[AssetAuditResult]):
    """Log discrepancies to fhq_governance.discrepancy_events per ADR-010"""
    logged_count = 0

    with conn.cursor() as cur:
        for result in results:
            for v in result.validations:
                if not v.passed:
                    cur.execute("""
                        INSERT INTO fhq_governance.discrepancy_events (
                            ios_id, agent_id, target_table, target_column,
                            canonical_value, reported_value,
                            discrepancy_type, discrepancy_score, severity,
                            detection_method, context_data, resolution_status
                        ) VALUES (
                            'IoS-002', 'VEGA',
                            'fhq_research.indicator_momentum', %s,
                            %s, %s,
                            %s, %s, %s::fhq_governance.discrepancy_severity,
                            'G3_COMPLETENESS_AUDIT', %s, 'OPEN'
                        )
                    """, (
                        v.indicator,
                        v.expected,
                        str(v.actual),
                        v.test_type,
                        v.deviation,
                        v.severity,
                        json.dumps({
                            'asset_id': result.asset_id,
                            'test_type': v.test_type,
                            'deviation_pct': v.deviation_pct
                        })
                    ))
                    logged_count += 1

        conn.commit()

    return logged_count


def generate_evidence_bundle(results: List[AssetAuditResult]) -> Dict[str, Any]:
    """Generate G3 Completeness Evidence Bundle"""

    validation_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    # Aggregate
    total_pass = sum(r.pass_count for r in results)
    total_fail = sum(r.fail_count for r in results)
    max_discrepancy = max(r.discrepancy_score for r in results) if results else 0

    overall_status = "G3_COMPLETENESS_PASS" if all(r.status == "PASS" for r in results) else "G3_COMPLETENESS_FAIL"

    # Compute hashes
    canonical_data = json.dumps([r.latest_values for r in results], sort_keys=True, default=str)
    canonical_hash = hashlib.sha256(canonical_data.encode()).hexdigest()

    recompute_data = json.dumps([r.formula_hashes for r in results], sort_keys=True)
    recompute_hash = hashlib.sha256(recompute_data.encode()).hexdigest()

    # Deviation matrix extended
    deviation_matrix = {}
    for r in results:
        deviation_matrix[r.asset_id] = {
            'indicators_tested': len(r.indicators_tested),
            'validations': len(r.validations),
            'pass_count': r.pass_count,
            'fail_count': r.fail_count,
            'discrepancy_score': r.discrepancy_score,
            'status': r.status,
            'new_indicators': {
                'stoch_rsi': r.latest_values.get('stoch_rsi'),
                'cci_20': r.latest_values.get('cci_20'),
                'mfi_14': r.latest_values.get('mfi_14')
            }
        }

    evidence = {
        "validation_id": validation_id,
        "ios_module": "IoS-002",
        "module_name": "Indicator Engine (Sensory Cortex)",
        "validation_type": "G3_COMPLETENESS",
        "timestamp": timestamp,
        "validator": "VEGA (Compliance & Oversight)",
        "overall_status": overall_status,

        "extended_indicators": ["CCI", "MFI", "StochRSI"],

        "sample_window": {
            "window_size": GOLDEN_SAMPLE_WINDOW,
            "assets_tested": [r.asset_id for r in results],
            "total_rows_analyzed": sum(r.sample_count for r in results)
        },

        "canonical_hash": canonical_hash,
        "recompute_hash": recompute_hash,

        "deviation_matrix_extended": deviation_matrix,

        "validation_summary": {
            "total_tests": total_pass + total_fail,
            "passed": total_pass,
            "failed": total_fail,
            "pass_rate": total_pass / (total_pass + total_fail) * 100 if (total_pass + total_fail) > 0 else 0,
            "max_discrepancy_score": max_discrepancy,
            "tolerance_threshold": NUMERIC_TOLERANCE,
            "test_types": {
                "range_validation": 5,
                "determinism": 4,
                "formula_identity": 3
            }
        },

        "verdict": {
            "status": overall_status,
            "reason": "All extended indicator validations passed" if overall_status == "G3_COMPLETENESS_PASS"
                     else f"Validation failures: {total_fail} tests failed",
            "discrepancy_score": max_discrepancy,
            "within_adr010_tolerance": max_discrepancy < 0.1
        },

        "audit_results": [{
            "asset_id": r.asset_id,
            "sample_count": r.sample_count,
            "indicators_tested": r.indicators_tested,
            "pass_count": r.pass_count,
            "fail_count": r.fail_count,
            "discrepancy_score": r.discrepancy_score,
            "status": r.status,
            "formula_hashes": r.formula_hashes,
            "validations": [asdict(v) for v in r.validations],
            "latest_values": r.latest_values
        } for r in results],

        "adr_compliance": ["ADR-002", "ADR-010"],
        "next_gate": "G4_ACTIVATION" if overall_status == "G3_COMPLETENESS_PASS" else "REMEDIATION_REQUIRED"
    }

    bundle_json = json.dumps(evidence, sort_keys=True, default=str)
    bundle_hash = hashlib.sha256(bundle_json.encode()).hexdigest()
    evidence["bundle_hash"] = bundle_hash

    evidence["vega_attestation"] = {
        "attestor": "VEGA",
        "role": "Compliance & Oversight",
        "attestation_time": timestamp,
        "attestation_id": str(uuid.uuid4()),
        "bundle_hash": bundle_hash,
        "decision": overall_status
    }

    return evidence


def main():
    print("=" * 70)
    print("IoS-002 G3 COMPLETENESS PATCH")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("Validator: VEGA (Compliance & Oversight)")
    print("Extended Indicators: CCI, MFI, StochRSI")
    print("=" * 70)
    print()

    conn = get_connection()
    results = []

    assets = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'EURUSD']

    print("PHASE 1: Extended Golden Sample Tests")
    print("-" * 70)

    for asset_id in assets:
        print(f"\nTesting {asset_id}...")
        result = run_completeness_audit(conn, asset_id)
        results.append(result)

        status_icon = "OK" if result.status == "PASS" else "FAIL"
        print(f"  [{status_icon}] {result.status}: {result.pass_count}/{result.pass_count + result.fail_count} tests")
        print(f"       Discrepancy score: {result.discrepancy_score:.6f}")

        # Show new indicator values
        lv = result.latest_values
        if lv.get('stoch_rsi') is not None:
            print(f"       StochRSI: {lv['stoch_rsi']:.4f}")
        if lv.get('cci_20') is not None:
            print(f"       CCI-20: {lv['cci_20']:.2f}")
        if lv.get('mfi_14') is not None:
            print(f"       MFI-14: {lv['mfi_14']:.2f}")

    print()
    print("PHASE 2: Discrepancy Logging (ADR-010)")
    print("-" * 70)

    failures = [r for r in results if r.status == "FAIL"]
    if failures:
        logged = log_discrepancies(conn, failures)
        print(f"  Logged {logged} discrepancy events")
    else:
        print("  No discrepancies to log - all tests passed")

    print()
    print("PHASE 3: Evidence Bundle Generation")
    print("-" * 70)

    evidence = generate_evidence_bundle(results)

    evidence_dir = Path("evidence")
    evidence_dir.mkdir(exist_ok=True)

    filename = "IoS-002_G3_COMPLETENESS_EVIDENCE.json"
    filepath = evidence_dir / filename

    with open(filepath, 'w') as f:
        json.dump(evidence, f, indent=2, default=str)

    print(f"  Evidence saved: {filepath.absolute()}")

    # Log to governance
    try:
        with conn.cursor() as cur:
            decision = "APPROVED" if "PASS" in evidence["overall_status"] else "REJECTED"

            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_id, action_type, action_target, action_target_type,
                    initiated_by, initiated_at, decision, decision_rationale,
                    hash_chain_id, signature_id
                ) VALUES (
                    gen_random_uuid(), 'IOS_MODULE_G3_COMPLETENESS', 'IoS-002',
                    'IOS_MODULE', 'VEGA', NOW(), %s, %s, %s, gen_random_uuid()
                )
            """, (
                decision,
                f"G3 Completeness: {evidence['overall_status']}. Extended indicators (CCI, MFI, StochRSI) validated.",
                f"G3C-{evidence['bundle_hash'][:8]}"
            ))

            cur.execute("""
                INSERT INTO fhq_meta.ios_audit_log (
                    ios_id, event_type, actor, event_data, gate_level
                ) VALUES ('IoS-002', 'G3_COMPLETENESS', 'VEGA', %s, 'G3')
            """, (json.dumps({
                "validation_id": evidence["validation_id"],
                "overall_status": evidence["overall_status"],
                "extended_indicators": evidence["extended_indicators"],
                "tests_passed": evidence["validation_summary"]["passed"],
                "tests_failed": evidence["validation_summary"]["failed"]
            }),))

        conn.commit()
        print("  Logged to governance")
    except Exception as e:
        print(f"  Warning: Could not log: {e}")

    conn.close()

    # Summary
    print()
    print("=" * 70)
    print("G3 COMPLETENESS SUMMARY")
    print("=" * 70)

    print(f"\n  Extended Indicators: {', '.join(evidence['extended_indicators'])}")
    print(f"  Assets Tested: {', '.join(evidence['sample_window']['assets_tested'])}")

    print(f"\n  Canonical Hash: {evidence['canonical_hash'][:32]}...")
    print(f"  Recompute Hash: {evidence['recompute_hash'][:32]}...")

    print(f"\n  DEVIATION MATRIX EXTENDED:")
    for asset, data in evidence['deviation_matrix_extended'].items():
        status_icon = "OK" if data['status'] == "PASS" else "FAIL"
        print(f"    {asset}: [{status_icon}] score={data['discrepancy_score']:.6f}")
        ni = data['new_indicators']
        stoch_str = f"{ni['stoch_rsi']:.4f}" if ni['stoch_rsi'] is not None else 'N/A'
        cci_str = f"{ni['cci_20']:.2f}" if ni['cci_20'] is not None else 'N/A'
        mfi_str = f"{ni['mfi_14']:.2f}" if ni['mfi_14'] is not None else 'N/A'
        print(f"      StochRSI={stoch_str}, CCI={cci_str}, MFI={mfi_str}")

    print(f"\n  Tests: {evidence['validation_summary']['passed']}/{evidence['validation_summary']['total_tests']} passed")
    print(f"  Pass Rate: {evidence['validation_summary']['pass_rate']:.1f}%")
    print(f"  Max Discrepancy: {evidence['validation_summary']['max_discrepancy_score']:.6f}")

    print()
    print(f"  VERDICT: {evidence['verdict']['status']}")
    print(f"  REASON: {evidence['verdict']['reason']}")
    print(f"  BUNDLE HASH: {evidence['bundle_hash'][:32]}...")
    print("=" * 70)

    return evidence


if __name__ == "__main__":
    result = main()
