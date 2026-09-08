#!/usr/bin/env python3
"""
HOLIDAY EXECUTION GATE
======================
CEO Directive: Holiday Market Operations - Crypto-First Execution & System Calibration
Effective: 2025-12-19
Duration: Until Traditional Markets Resume Normal Liquidity

Core Principle: "We pause execution, not cognition."

This module implements asset-class execution gating:
- EQUITIES & FX: Execution SUSPENDED (signal lifecycle continues to EPHEMERAL_PRIMED)
- CRYPTO: Execution ACTIVE (Paper Mode) for BTC, ETH, SOL only

All perception, regime detection, signal discovery, and contextual logic remain fully active.
Only execution permission is selectively gated.
"""

import os
import logging
from typing import Tuple, Optional
from datetime import datetime, timezone

logger = logging.getLogger('HOLIDAY_GATE')

# =============================================================================
# HOLIDAY EXECUTION POLICY (CEO DIRECTIVE 2025-12-19)
# =============================================================================

HOLIDAY_MODE_ENABLED = False  # CEO 2026-01-05: Normal operations resumed

# Approved crypto assets during holiday period
# CEO Directive Update: All Alpaca-supported crypto approved
APPROVED_CRYPTO_ASSETS = {
    'AAVE', 'AVAX', 'BAT', 'BCH', 'BTC', 'CRV', 'DOGE', 'DOT', 'ETH',
    'GRT', 'LINK', 'LTC', 'PEPE', 'SHIB', 'SKY', 'SOL', 'SUSHI',
    'TRUMP', 'UNI', 'USDC', 'USDG', 'USDT', 'XRP', 'XTZ', 'YFI'
}

# Crypto symbol variations (all map to base assets)
# Dynamically build map for all approved assets
CRYPTO_SYMBOL_MAP = {}
for base in APPROVED_CRYPTO_ASSETS:
    # Add all common variations
    CRYPTO_SYMBOL_MAP[base] = base
    CRYPTO_SYMBOL_MAP[f'{base}-USD'] = base
    CRYPTO_SYMBOL_MAP[f'{base}USD'] = base
    CRYPTO_SYMBOL_MAP[f'{base}USDT'] = base
    CRYPTO_SYMBOL_MAP[f'{base}/USD'] = base
    CRYPTO_SYMBOL_MAP[f'{base}/USDC'] = base
    CRYPTO_SYMBOL_MAP[f'{base}/USDT'] = base
    CRYPTO_SYMBOL_MAP[f'{base}/BTC'] = base

# Also add lowercase variants
_lower_map = {k.lower(): v for k, v in CRYPTO_SYMBOL_MAP.items()}
CRYPTO_SYMBOL_MAP.update(_lower_map)

# Crypto-adjacent equities (proxies) - these ARE approved for crypto exposure
CRYPTO_PROXY_EQUITIES = {'MSTR', 'COIN', 'MARA', 'RIOT'}

# Asset classification
EQUITY_INDICATORS = {
    'NVDA', 'AAPL', 'MSFT', 'GOOGL', 'TSLA', 'AMD', 'META', 'AMZN',
    'JPM', 'GS', 'MS', 'BAC', 'XOM', 'CVX', 'COP', 'UNH', 'JNJ', 'PFE',
}

ETF_INDICATORS = {'SPY', 'QQQ', 'IWM', 'DIA', 'XLF', 'XLE', 'XLK'}

FX_INDICATORS = {
    'EUR-USD', 'EURUSD', 'GBP-USD', 'GBPUSD', 'USD-JPY', 'USDJPY',
    'EUR/USD', 'GBP/USD', 'USD/JPY',
}


def classify_asset(symbol: str) -> str:
    """
    Classify an asset into its asset class.

    Returns: 'CRYPTO', 'CRYPTO_PROXY', 'EQUITY', 'ETF', 'FX', or 'UNKNOWN'
    """
    symbol_upper = symbol.upper().strip()

    # Check if it's a crypto symbol
    if symbol_upper in CRYPTO_SYMBOL_MAP:
        return 'CRYPTO'

    # Check if it's a crypto proxy equity
    if symbol_upper in CRYPTO_PROXY_EQUITIES:
        return 'CRYPTO_PROXY'

    # Check if it's an ETF
    if symbol_upper in ETF_INDICATORS:
        return 'ETF'

    # Check if it's FX
    if symbol_upper in FX_INDICATORS:
        return 'FX'

    # Check if it's a known equity
    if symbol_upper in EQUITY_INDICATORS:
        return 'EQUITY'

    # Heuristics for unknown symbols
    if '/' in symbol or '-USD' in symbol_upper or 'USDT' in symbol_upper:
        # Likely crypto or FX
        if any(crypto in symbol_upper for crypto in ['BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'ADA']):
            return 'CRYPTO'
        return 'FX'

    # Default to equity for unknown symbols
    return 'EQUITY'


def is_approved_crypto(symbol: str) -> bool:
    """
    Check if a symbol is an approved crypto asset during holiday period.

    Only BTC, ETH, SOL (and their variations) are approved.
    """
    symbol_upper = symbol.upper().strip()

    # Direct crypto check
    if symbol_upper in CRYPTO_SYMBOL_MAP:
        base_asset = CRYPTO_SYMBOL_MAP[symbol_upper]
        return base_asset in APPROVED_CRYPTO_ASSETS

    return False


def check_holiday_execution_gate(
    symbol: str,
    signal_state: str = 'DORMANT',
    target_state: str = 'ARMED',
    source_signal: Optional[str] = None
) -> Tuple[bool, str, str]:
    """
    Check if execution is permitted under Holiday Market Operations policy.

    Args:
        symbol: The asset symbol to check
        signal_state: Current signal state (DORMANT, PRIMED, EPHEMERAL_PRIMED, etc.)
        target_state: Target state for transition (ARMED, ACTIVE, etc.)
        source_signal: Optional source signal for crypto proxy resolution

    Returns:
        Tuple of (is_permitted, reason, asset_class)

    Holiday Policy:
        - EQUITIES & FX: Signal lifecycle permitted up to EPHEMERAL_PRIMED only
        - CRYPTO (BTC, ETH, SOL): Full pipeline including ARMED/ACTIVE (24/7 markets)
        - CRYPTO_PROXY (MSTR, COIN, etc.): BLOCKED - equity markets have limited holiday hours
    """
    if not HOLIDAY_MODE_ENABLED:
        return True, "Holiday mode disabled - normal operations", "N/A"

    asset_class = classify_asset(symbol)

    # Execution states that are blocked for non-crypto during holiday
    EXECUTION_STATES = {'ARMED', 'ACTIVE', 'EXECUTING', 'EXECUTED'}

    # CRYPTO: Full pipeline permitted
    if asset_class == 'CRYPTO':
        if is_approved_crypto(symbol):
            return True, f"CRYPTO execution permitted: {symbol} is approved holiday asset", asset_class
        else:
            return False, f"CRYPTO blocked: {symbol} not in approved list (BTC, ETH, SOL only)", asset_class

    # CRYPTO_PROXY: BLOCKED during holiday - stock markets have limited hours
    # CEO Directive 2025-12-23: Only trade actual crypto (24/7 markets), not equity proxies
    if asset_class == 'CRYPTO_PROXY':
        if target_state.upper() in EXECUTION_STATES:
            return False, f"CRYPTO_PROXY BLOCKED: {symbol} is equity (limited hours) - use actual crypto during holiday", asset_class
        else:
            # Signal observation permitted
            return True, f"CRYPTO_PROXY signal observation permitted: {symbol}", asset_class

    # EQUITIES, ETFs, FX: Signal lifecycle permitted, execution blocked
    if asset_class in {'EQUITY', 'ETF', 'FX'}:
        if target_state.upper() in EXECUTION_STATES:
            return False, f"{asset_class} execution SUSPENDED: {symbol} cannot transition to {target_state} during holiday", asset_class
        else:
            # Non-execution states are permitted (signal observation continues)
            return True, f"{asset_class} signal lifecycle permitted: {symbol} -> {target_state}", asset_class

    # Unknown assets default to blocked execution
    if target_state.upper() in EXECUTION_STATES:
        return False, f"UNKNOWN asset blocked: {symbol} cannot execute during holiday", "UNKNOWN"

    return True, f"Signal observation permitted for {symbol}", asset_class


def get_holiday_status() -> dict:
    """
    Get current holiday execution gate status.
    """
    return {
        'holiday_mode_enabled': HOLIDAY_MODE_ENABLED,
        'effective_date': '2025-12-19',
        'approved_crypto': list(APPROVED_CRYPTO_ASSETS),
        'crypto_proxies': list(CRYPTO_PROXY_EQUITIES),
        'policy': {
            'equities': 'SUSPENDED (signal lifecycle to EPHEMERAL_PRIMED only)',
            'fx': 'SUSPENDED (signal lifecycle to EPHEMERAL_PRIMED only)',
            'crypto': 'ACTIVE (BTC, ETH, SOL - Paper Mode)',
        },
        'checked_at': datetime.now(timezone.utc).isoformat()
    }


def log_holiday_gate_decision(
    symbol: str,
    permitted: bool,
    reason: str,
    asset_class: str,
    target_state: str = None
):
    """
    Log holiday gate decision for audit trail.
    """
    status = "PERMITTED" if permitted else "BLOCKED"
    logger.info(
        f"[HOLIDAY_GATE] {status}: {symbol} ({asset_class}) "
        f"-> {target_state or 'N/A'} | {reason}"
    )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def can_execute(symbol: str, source_signal: Optional[str] = None) -> bool:
    """
    Quick check if execution is permitted for a symbol.

    Use this as a pre-check before submitting any trade.
    """
    permitted, _, _ = check_holiday_execution_gate(
        symbol=symbol,
        target_state='ACTIVE',
        source_signal=source_signal
    )
    return permitted


def get_executable_asset_for_signal(
    signal_symbol: str,
    proxy_options: list = None
) -> Optional[str]:
    """
    Get an executable asset for a signal during holiday period.

    If the signal is for a non-executable asset (equity), returns None.
    If the signal is for crypto, returns the Alpaca-tradeable version.
    If the signal is for crypto and proxy_options provided, returns first approved proxy.
    """
    asset_class = classify_asset(signal_symbol)

    if asset_class == 'CRYPTO' and is_approved_crypto(signal_symbol):
        # Return Alpaca crypto format
        base = CRYPTO_SYMBOL_MAP.get(signal_symbol.upper(), signal_symbol)
        return f"{base}/USD"

    if asset_class in {'EQUITY', 'ETF', 'FX'}:
        # These are blocked during holiday
        return None

    if proxy_options and is_approved_crypto(signal_symbol):
        # Return first approved proxy
        for proxy in proxy_options:
            if proxy in CRYPTO_PROXY_EQUITIES:
                return proxy

    return None


# =============================================================================
# MAIN (for testing)
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("HOLIDAY EXECUTION GATE - Test Suite")
    print("=" * 60)

    test_cases = [
        ('BTC-USD', 'ACTIVE', None),
        ('ETH-USD', 'ACTIVE', None),
        ('SOL-USD', 'ACTIVE', None),
        ('DOGE-USD', 'ACTIVE', None),  # Not approved
        ('NVDA', 'ACTIVE', None),       # Equity - blocked
        ('NVDA', 'PRIMED', None),       # Equity - signal OK
        ('MSTR', 'ACTIVE', 'BTC-USD'),  # Proxy with crypto source - OK
        ('MSTR', 'ACTIVE', None),       # Proxy without source - blocked
        ('SPY', 'ACTIVE', None),        # ETF - blocked
        ('EUR-USD', 'ACTIVE', None),    # FX - blocked
    ]

    print("\nTest Results:")
    print("-" * 60)

    for symbol, target, source in test_cases:
        permitted, reason, asset_class = check_holiday_execution_gate(
            symbol=symbol,
            target_state=target,
            source_signal=source
        )
        status = "PASS" if permitted else "BLOCK"
        print(f"[{status}] {symbol} -> {target} ({asset_class})")
        print(f"       {reason}")
        print()

    print("=" * 60)
    print("Holiday Status:")
    print(get_holiday_status())
