#!/usr/bin/env python3
"""
OPTIONS GREEKS CALCULATOR
=========================
Directive:  CEO-DIR-2026-OPS-AUTONOMY-001
Spec:       IoS-012-C (Options Execution Architecture)
Gate:       G1 (Technical Validation)
Author:     STIG (EC-003)
Date:       2026-02-01

Pure math module. No execution, no database writes, no side effects.
Deterministic and reproducible for all inputs.

Models:
  - Black-Scholes (European-style)
  - Cox-Ross-Rubinstein Binomial (American-style, early exercise)

Greeks: delta, gamma, vega, theta, rho
IV: Newton-Raphson from market prices
IV Rank / IV Percentile from historical data
"""

import math
import hashlib
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, List

logger = logging.getLogger('OPTIONS_GREEKS')

# =============================================================================
# CONSTANTS
# =============================================================================

TRADING_DAYS_PER_YEAR = 252
CALENDAR_DAYS_PER_YEAR = 365.0
IV_NEWTON_MAX_ITER = 100
IV_NEWTON_TOLERANCE = 1e-8
BINOMIAL_DEFAULT_STEPS = 100


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass(frozen=True)
class GreeksResult:
    """Immutable Greeks calculation result."""
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    price: float
    model: str          # 'BLACK_SCHOLES' or 'BINOMIAL_CRR'
    option_type: str    # 'CALL' or 'PUT'
    underlying_price: float
    strike: float
    time_to_expiry: float
    volatility: float
    risk_free_rate: float
    calculated_at: str
    content_hash: str


@dataclass(frozen=True)
class IVResult:
    """Implied volatility calculation result."""
    implied_volatility: float
    converged: bool
    iterations: int
    market_price: float
    model_price: float
    error: float
    content_hash: str


@dataclass(frozen=True)
class IVRankResult:
    """IV Rank and Percentile calculation."""
    iv_rank: float              # (current - 52w_low) / (52w_high - 52w_low)
    iv_percentile: float        # % of days where IV was lower
    current_iv: float
    high_52w: float
    low_52w: float
    observations: int
    content_hash: str


# =============================================================================
# STANDARD NORMAL DISTRIBUTION
# =============================================================================

def _norm_cdf(x: float) -> float:
    """Cumulative distribution function for standard normal."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    """Probability density function for standard normal."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


# =============================================================================
# BLACK-SCHOLES (EUROPEAN)
# =============================================================================

def _bs_d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes d1 parameter."""
    return (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))


def _bs_d2(d1: float, sigma: float, T: float) -> float:
    """Black-Scholes d2 parameter."""
    return d1 - sigma * math.sqrt(T)


def black_scholes_price(
    S: float, K: float, T: float, r: float, sigma: float,
    option_type: str = 'CALL'
) -> float:
    """
    Black-Scholes European option price.

    Args:
        S: Underlying price
        K: Strike price
        T: Time to expiry in years
        r: Risk-free rate (annualized, decimal)
        sigma: Volatility (annualized, decimal)
        option_type: 'CALL' or 'PUT'

    Returns:
        Option price
    """
    if T <= 0:
        if option_type == 'CALL':
            return max(S - K, 0.0)
        return max(K - S, 0.0)

    d1 = _bs_d1(S, K, T, r, sigma)
    d2 = _bs_d2(d1, sigma, T)

    if option_type == 'CALL':
        return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    else:
        return K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def black_scholes_greeks(
    S: float, K: float, T: float, r: float, sigma: float,
    option_type: str = 'CALL'
) -> GreeksResult:
    """
    Full Black-Scholes Greeks calculation.

    Args:
        S: Underlying price
        K: Strike price
        T: Time to expiry in years
        r: Risk-free rate (annualized, decimal)
        sigma: Volatility (annualized, decimal)
        option_type: 'CALL' or 'PUT'

    Returns:
        GreeksResult with all Greeks + price
    """
    if T <= 0:
        price = max(S - K, 0.0) if option_type == 'CALL' else max(K - S, 0.0)
        itm = (S > K) if option_type == 'CALL' else (K > S)
        return GreeksResult(
            delta=1.0 if (option_type == 'CALL' and itm) else (-1.0 if (option_type == 'PUT' and itm) else 0.0),
            gamma=0.0, vega=0.0, theta=0.0, rho=0.0,
            price=price, model='BLACK_SCHOLES', option_type=option_type,
            underlying_price=S, strike=K, time_to_expiry=T,
            volatility=sigma, risk_free_rate=r,
            calculated_at=datetime.now(timezone.utc).isoformat(),
            content_hash=_hash_greeks_input(S, K, T, r, sigma, option_type)
        )

    d1 = _bs_d1(S, K, T, r, sigma)
    d2 = _bs_d2(d1, sigma, T)
    sqrt_T = math.sqrt(T)
    pdf_d1 = _norm_pdf(d1)
    discount = math.exp(-r * T)

    price = black_scholes_price(S, K, T, r, sigma, option_type)

    # Greeks
    gamma = pdf_d1 / (S * sigma * sqrt_T)
    vega = S * pdf_d1 * sqrt_T / 100.0  # per 1% IV change

    if option_type == 'CALL':
        delta = _norm_cdf(d1)
        theta = (-(S * pdf_d1 * sigma) / (2.0 * sqrt_T)
                 - r * K * discount * _norm_cdf(d2)) / CALENDAR_DAYS_PER_YEAR
        rho = K * T * discount * _norm_cdf(d2) / 100.0
    else:
        delta = _norm_cdf(d1) - 1.0
        theta = (-(S * pdf_d1 * sigma) / (2.0 * sqrt_T)
                 + r * K * discount * _norm_cdf(-d2)) / CALENDAR_DAYS_PER_YEAR
        rho = -K * T * discount * _norm_cdf(-d2) / 100.0

    return GreeksResult(
        delta=round(delta, 6),
        gamma=round(gamma, 6),
        vega=round(vega, 6),
        theta=round(theta, 6),
        rho=round(rho, 6),
        price=round(price, 4),
        model='BLACK_SCHOLES',
        option_type=option_type,
        underlying_price=S,
        strike=K,
        time_to_expiry=T,
        volatility=sigma,
        risk_free_rate=r,
        calculated_at=datetime.now(timezone.utc).isoformat(),
        content_hash=_hash_greeks_input(S, K, T, r, sigma, option_type)
    )


# =============================================================================
# BINOMIAL (COX-ROSS-RUBINSTEIN) — AMERICAN STYLE
# =============================================================================

def binomial_price(
    S: float, K: float, T: float, r: float, sigma: float,
    option_type: str = 'CALL', steps: int = BINOMIAL_DEFAULT_STEPS
) -> float:
    """
    Cox-Ross-Rubinstein binomial model for American-style options.

    Args:
        S: Underlying price
        K: Strike price
        T: Time to expiry in years
        r: Risk-free rate
        sigma: Volatility
        option_type: 'CALL' or 'PUT'
        steps: Number of binomial tree steps

    Returns:
        American option price
    """
    if T <= 0:
        if option_type == 'CALL':
            return max(S - K, 0.0)
        return max(K - S, 0.0)

    dt = T / steps
    u = math.exp(sigma * math.sqrt(dt))
    d = 1.0 / u
    p = (math.exp(r * dt) - d) / (u - d)
    disc = math.exp(-r * dt)

    # Terminal values
    prices = [S * (u ** (steps - j)) * (d ** j) for j in range(steps + 1)]

    if option_type == 'CALL':
        values = [max(px - K, 0.0) for px in prices]
    else:
        values = [max(K - px, 0.0) for px in prices]

    # Backward induction with early exercise
    for i in range(steps - 1, -1, -1):
        for j in range(i + 1):
            hold = disc * (p * values[j] + (1.0 - p) * values[j + 1])
            spot = S * (u ** (i - j)) * (d ** j)
            if option_type == 'CALL':
                exercise = max(spot - K, 0.0)
            else:
                exercise = max(K - spot, 0.0)
            values[j] = max(hold, exercise)

    return values[0]


def binomial_greeks(
    S: float, K: float, T: float, r: float, sigma: float,
    option_type: str = 'CALL', steps: int = BINOMIAL_DEFAULT_STEPS
) -> GreeksResult:
    """
    American-style Greeks via finite difference on binomial model.

    Greeks computed by bumping inputs and measuring price changes.
    """
    price = binomial_price(S, K, T, r, sigma, option_type, steps)

    # Delta: dV/dS via central difference
    dS = S * 0.01
    price_up = binomial_price(S + dS, K, T, r, sigma, option_type, steps)
    price_dn = binomial_price(S - dS, K, T, r, sigma, option_type, steps)
    delta = (price_up - price_dn) / (2.0 * dS)

    # Gamma: d²V/dS²
    gamma = (price_up - 2.0 * price + price_dn) / (dS * dS)

    # Vega: dV/dσ per 1% change
    dsig = 0.01
    price_vol_up = binomial_price(S, K, T, r, sigma + dsig, option_type, steps)
    price_vol_dn = binomial_price(S, K, T, r, sigma - dsig, option_type, steps)
    vega = (price_vol_up - price_vol_dn) / (2.0 * 100.0)  # per 1%

    # Theta: dV/dt per day
    if T > 1.0 / CALENDAR_DAYS_PER_YEAR:
        dt = 1.0 / CALENDAR_DAYS_PER_YEAR
        price_t_dn = binomial_price(S, K, T - dt, r, sigma, option_type, steps)
        theta = (price_t_dn - price) / 1.0  # already per day
    else:
        theta = -price  # at expiry, theta is full remaining value

    # Rho: dV/dr per 1% change
    dr = 0.01
    price_r_up = binomial_price(S, K, T, r + dr, sigma, option_type, steps)
    price_r_dn = binomial_price(S, K, T, r - dr, sigma, option_type, steps)
    rho = (price_r_up - price_r_dn) / (2.0 * 100.0)  # per 1%

    return GreeksResult(
        delta=round(delta, 6),
        gamma=round(gamma, 6),
        vega=round(vega, 6),
        theta=round(theta, 6),
        rho=round(rho, 6),
        price=round(price, 4),
        model='BINOMIAL_CRR',
        option_type=option_type,
        underlying_price=S,
        strike=K,
        time_to_expiry=T,
        volatility=sigma,
        risk_free_rate=r,
        calculated_at=datetime.now(timezone.utc).isoformat(),
        content_hash=_hash_greeks_input(S, K, T, r, sigma, option_type)
    )


# =============================================================================
# IMPLIED VOLATILITY (NEWTON-RAPHSON)
# =============================================================================

def implied_volatility(
    market_price: float, S: float, K: float, T: float, r: float,
    option_type: str = 'CALL'
) -> IVResult:
    """
    Calculate implied volatility via Newton-Raphson iteration.

    Uses Black-Scholes vega as the derivative for iteration.

    Args:
        market_price: Observed market price of the option
        S: Underlying price
        K: Strike price
        T: Time to expiry in years
        r: Risk-free rate
        option_type: 'CALL' or 'PUT'

    Returns:
        IVResult with implied volatility and convergence info
    """
    if T <= 0 or market_price <= 0:
        return IVResult(
            implied_volatility=0.0, converged=False, iterations=0,
            market_price=market_price, model_price=0.0, error=float('inf'),
            content_hash=_hash_iv_input(market_price, S, K, T, r, option_type)
        )

    # Initial guess via Brenner-Subrahmanyam approximation
    sigma = math.sqrt(2.0 * math.pi / T) * market_price / S

    # Bound the initial guess
    sigma = max(0.01, min(sigma, 5.0))

    for i in range(IV_NEWTON_MAX_ITER):
        model_price = black_scholes_price(S, K, T, r, sigma, option_type)
        error = model_price - market_price

        if abs(error) < IV_NEWTON_TOLERANCE:
            return IVResult(
                implied_volatility=round(sigma, 8),
                converged=True,
                iterations=i + 1,
                market_price=market_price,
                model_price=round(model_price, 6),
                error=round(error, 10),
                content_hash=_hash_iv_input(market_price, S, K, T, r, option_type)
            )

        # Vega for Newton step (unscaled)
        d1 = _bs_d1(S, K, T, r, sigma)
        vega_raw = S * _norm_pdf(d1) * math.sqrt(T)

        if vega_raw < 1e-12:
            break

        sigma = sigma - error / vega_raw
        sigma = max(0.001, min(sigma, 10.0))  # Keep in reasonable bounds

    model_price = black_scholes_price(S, K, T, r, sigma, option_type)
    return IVResult(
        implied_volatility=round(sigma, 8),
        converged=False,
        iterations=IV_NEWTON_MAX_ITER,
        market_price=market_price,
        model_price=round(model_price, 6),
        error=round(model_price - market_price, 10),
        content_hash=_hash_iv_input(market_price, S, K, T, r, option_type)
    )


# =============================================================================
# IV RANK & IV PERCENTILE
# =============================================================================

def iv_rank_percentile(
    current_iv: float,
    historical_ivs: List[float]
) -> IVRankResult:
    """
    Calculate IV Rank and IV Percentile from historical IV data.

    IV Rank = (current_IV - 52w_low_IV) / (52w_high_IV - 52w_low_IV)
    IV Percentile = % of days in history where IV was lower

    Args:
        current_iv: Current implied volatility
        historical_ivs: List of historical IV values (ideally 252 trading days)

    Returns:
        IVRankResult with rank, percentile, and metadata
    """
    if not historical_ivs:
        return IVRankResult(
            iv_rank=0.0, iv_percentile=0.0,
            current_iv=current_iv, high_52w=current_iv, low_52w=current_iv,
            observations=0,
            content_hash=hashlib.sha256(f"ivr:{current_iv}:0".encode()).hexdigest()
        )

    high_52w = max(historical_ivs)
    low_52w = min(historical_ivs)
    iv_range = high_52w - low_52w

    if iv_range < 1e-10:
        iv_rank = 0.5
    else:
        iv_rank = (current_iv - low_52w) / iv_range
        iv_rank = max(0.0, min(1.0, iv_rank))

    days_lower = sum(1 for iv in historical_ivs if iv < current_iv)
    iv_percentile = days_lower / len(historical_ivs)

    payload = f"ivr:{current_iv}:{high_52w}:{low_52w}:{len(historical_ivs)}"
    content_hash = hashlib.sha256(payload.encode()).hexdigest()

    return IVRankResult(
        iv_rank=round(iv_rank, 4),
        iv_percentile=round(iv_percentile, 4),
        current_iv=round(current_iv, 6),
        high_52w=round(high_52w, 6),
        low_52w=round(low_52w, 6),
        observations=len(historical_ivs),
        content_hash=content_hash
    )


# =============================================================================
# STRATEGY-LEVEL GREEKS (MULTI-LEG)
# =============================================================================

def strategy_greeks(legs: list, S: float, r: float = 0.05) -> dict:
    """
    Calculate aggregate Greeks for a multi-leg options strategy.

    Args:
        legs: List of dicts with keys:
            - strike (float)
            - expiry_years (float): time to expiry in years
            - volatility (float)
            - option_type (str): 'CALL' or 'PUT'
            - quantity (int): positive for long, negative for short
        S: Current underlying price
        r: Risk-free rate

    Returns:
        Dict with aggregate Greeks and per-leg detail
    """
    total = {'delta': 0.0, 'gamma': 0.0, 'vega': 0.0, 'theta': 0.0, 'rho': 0.0, 'price': 0.0}
    leg_details = []

    for leg in legs:
        greeks = black_scholes_greeks(
            S=S, K=leg['strike'], T=leg['expiry_years'],
            r=r, sigma=leg['volatility'], option_type=leg['option_type']
        )
        qty = leg['quantity']
        total['delta'] += greeks.delta * qty
        total['gamma'] += greeks.gamma * qty
        total['vega'] += greeks.vega * qty
        total['theta'] += greeks.theta * qty
        total['rho'] += greeks.rho * qty
        total['price'] += greeks.price * qty
        leg_details.append({
            'strike': leg['strike'],
            'option_type': leg['option_type'],
            'quantity': qty,
            'greeks': asdict(greeks)
        })

    for k in total:
        total[k] = round(total[k], 6)

    return {
        'aggregate': total,
        'legs': leg_details,
        'underlying_price': S,
        'risk_free_rate': r
    }


# =============================================================================
# MAX LOSS / MAX PROFIT CALCULATORS
# =============================================================================

def vertical_spread_risk(
    long_strike: float, short_strike: float,
    net_premium: float, option_type: str = 'PUT'
) -> dict:
    """Calculate max loss/profit for a vertical spread."""
    width = abs(long_strike - short_strike)
    if option_type == 'PUT':
        # Bull put spread: sell higher strike put, buy lower strike put
        max_profit = net_premium
        max_loss = width - net_premium
    else:
        # Bear call spread: sell lower strike call, buy higher strike call
        max_profit = net_premium
        max_loss = width - net_premium
    return {
        'max_profit': round(max_profit, 4),
        'max_loss': round(max_loss, 4),
        'width': round(width, 4),
        'net_premium': round(net_premium, 4),
        'breakeven': round(short_strike - net_premium if option_type == 'PUT'
                          else short_strike + net_premium, 4)
    }


def iron_condor_risk(
    put_long_strike: float, put_short_strike: float,
    call_short_strike: float, call_long_strike: float,
    net_premium: float
) -> dict:
    """Calculate max loss/profit for an iron condor."""
    put_width = abs(put_short_strike - put_long_strike)
    call_width = abs(call_long_strike - call_short_strike)
    max_width = max(put_width, call_width)
    max_loss = max_width - net_premium
    return {
        'max_profit': round(net_premium, 4),
        'max_loss': round(max_loss, 4),
        'put_width': round(put_width, 4),
        'call_width': round(call_width, 4),
        'net_premium': round(net_premium, 4),
        'lower_breakeven': round(put_short_strike - net_premium, 4),
        'upper_breakeven': round(call_short_strike + net_premium, 4)
    }


# =============================================================================
# HASH UTILITIES (ADR-013)
# =============================================================================

def _hash_greeks_input(S, K, T, r, sigma, option_type) -> str:
    """Deterministic hash for Greeks calculation inputs."""
    payload = f"greeks:{S}:{K}:{T}:{r}:{sigma}:{option_type}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _hash_iv_input(market_price, S, K, T, r, option_type) -> str:
    """Deterministic hash for IV calculation inputs."""
    payload = f"iv:{market_price}:{S}:{K}:{T}:{r}:{option_type}"
    return hashlib.sha256(payload.encode()).hexdigest()


def hash_greeks_result(result: GreeksResult) -> str:
    """SHA256 hash of a full GreeksResult for ADR-013 chain signing."""
    payload = json.dumps(asdict(result), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


# =============================================================================
# SELF-TEST
# =============================================================================

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("OPTIONS GREEKS CALCULATOR — Self-Test")
    print("IoS-012-C / CEO-DIR-2026-OPS-AUTONOMY-001")
    print("=" * 60)

    # Test 1: Black-Scholes AAPL $150 call, 30 DTE, 25% IV
    S, K, T, r, sigma = 150.0, 150.0, 30.0 / 365.0, 0.05, 0.25
    greeks = black_scholes_greeks(S, K, T, r, sigma, 'CALL')
    print(f"\n1. BS CALL: S={S}, K={K}, T=30d, IV=25%")
    print(f"   Price:  {greeks.price}")
    print(f"   Delta:  {greeks.delta}")
    print(f"   Gamma:  {greeks.gamma}")
    print(f"   Vega:   {greeks.vega}")
    print(f"   Theta:  {greeks.theta}")
    print(f"   Rho:    {greeks.rho}")
    print(f"   Hash:   {greeks.content_hash[:16]}...")

    # Expected: delta ~0.53-0.55 for ATM 30-day call
    assert 0.48 < greeks.delta < 0.60, f"Delta {greeks.delta} outside expected range"
    print("   PASS: Delta within expected range (0.48-0.60)")

    # Test 2: Put-call parity
    put = black_scholes_greeks(S, K, T, r, sigma, 'PUT')
    parity_lhs = greeks.price - put.price
    parity_rhs = S - K * math.exp(-r * T)
    parity_err = abs(parity_lhs - parity_rhs)
    print(f"\n2. Put-Call Parity: |C - P - (S - Ke^-rT)| = {parity_err:.8f}")
    assert parity_err < 0.01, f"Put-call parity violated: {parity_err}"
    print("   PASS: Parity holds (<0.01)")

    # Test 3: Binomial (American put)
    am_price = binomial_price(S, K, T, r, sigma, 'PUT', 200)
    eu_price = black_scholes_price(S, K, T, r, sigma, 'PUT')
    print(f"\n3. American vs European PUT:")
    print(f"   American (CRR-200): {am_price:.4f}")
    print(f"   European (BS):      {eu_price:.4f}")
    print(f"   Early exercise premium: {am_price - eu_price:.4f}")
    assert am_price >= eu_price - 0.01, "American put should be >= European put"
    print("   PASS: American >= European")

    # Test 4: Implied volatility recovery
    target_price = black_scholes_price(S, K, T, r, 0.30, 'CALL')
    iv_result = implied_volatility(target_price, S, K, T, r, 'CALL')
    print(f"\n4. IV Recovery (target sigma=0.30):")
    print(f"   Recovered IV: {iv_result.implied_volatility:.6f}")
    print(f"   Converged:    {iv_result.converged}")
    print(f"   Iterations:   {iv_result.iterations}")
    assert iv_result.converged, "IV Newton-Raphson should converge"
    assert abs(iv_result.implied_volatility - 0.30) < 0.001, "IV recovery error too large"
    print("   PASS: IV recovered within 0.001")

    # Test 5: IV Rank
    hist_ivs = [0.20, 0.22, 0.25, 0.30, 0.35, 0.28, 0.18, 0.40, 0.15, 0.32]
    ivr = iv_rank_percentile(0.25, hist_ivs)
    print(f"\n5. IV Rank/Percentile (current=0.25, 10 obs):")
    print(f"   IV Rank:       {ivr.iv_rank}")
    print(f"   IV Percentile: {ivr.iv_percentile}")
    print(f"   52w High:      {ivr.high_52w}")
    print(f"   52w Low:       {ivr.low_52w}")
    assert 0.0 <= ivr.iv_rank <= 1.0, "IV Rank out of bounds"
    print("   PASS: IV Rank in [0, 1]")

    # Test 6: Strategy Greeks (bull put spread)
    spread_legs = [
        {'strike': 145.0, 'expiry_years': T, 'volatility': 0.25, 'option_type': 'PUT', 'quantity': 1},
        {'strike': 150.0, 'expiry_years': T, 'volatility': 0.25, 'option_type': 'PUT', 'quantity': -1},
    ]
    strat = strategy_greeks(spread_legs, S, r)
    print(f"\n6. Bull Put Spread (145/150):")
    print(f"   Net Delta: {strat['aggregate']['delta']}")
    print(f"   Net Theta: {strat['aggregate']['theta']}")
    print(f"   Net Price: {strat['aggregate']['price']}")
    print("   PASS: Strategy Greeks computed")

    # Test 7: Vertical spread risk
    vsr = vertical_spread_risk(145.0, 150.0, 1.50, 'PUT')
    print(f"\n7. Vertical Spread Risk (145/150 bull put, $1.50 credit):")
    print(f"   Max Profit: {vsr['max_profit']}")
    print(f"   Max Loss:   {vsr['max_loss']}")
    print(f"   Breakeven:  {vsr['breakeven']}")
    assert vsr['max_profit'] == 1.50
    assert vsr['max_loss'] == 3.50  # 5.0 width - 1.50 credit
    print("   PASS: Risk/reward correct")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
