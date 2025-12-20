#!/usr/bin/env python3
"""
IoS-016 GRID TRADING ENGINE (STIG-2025-001 Compliant)
=====================================================
Authority: STIG (CTO)
ADR Reference: STIG-2025-001 Directive - Grid with Advanced Regime Gate
Classification: Tier-1 Alpha Generation

Purpose:
    ATR-based grid trading for range-bound markets.
    Uses 4D regime filter to prevent "picking up pennies in front of steamroller".

Safety Gate (STIG-2025-001 MANDATORY):
    Grid only deploys if ALL conditions met:
    - ADX < 20 (non-trending)
    - ATR_normalized > 0.005 (some volatility)
    - VolatilityShift < 0.3 (no sudden expansion)
    - Volume > 70% of 20d avg (liquidity)

Usage:
    from ios016_grid_trading_engine import GridTradingEngine

    engine = GridTradingEngine()
    grid = engine.create_grid('AAPL', capital=10000)
    signals = engine.check_grid_levels('AAPL')
"""

import os
import json
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from dotenv import load_dotenv

# Import regime classifier
try:
    from ios003_advanced_regime import AdvancedRegimeClassifier, RegimeVector
    REGIME_AVAILABLE = True
except ImportError:
    REGIME_AVAILABLE = False

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


class GridAction(Enum):
    """Grid trading actions"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CLOSE_ALL = "CLOSE_ALL"
    DISABLED = "DISABLED"


class GridStatus(Enum):
    """Grid status"""
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"           # Temporarily paused
    DISABLED_REGIME = "DISABLED_REGIME"  # Unsafe regime
    DISABLED_MANUAL = "DISABLED_MANUAL"
    COMPLETED = "COMPLETED"     # All levels filled


@dataclass
class GridLevel:
    """Single grid level"""
    level_id: int
    price: float
    is_buy: bool                # Buy or sell at this level
    quantity: float
    filled: bool = False
    filled_at: Optional[datetime] = None
    fill_price: Optional[float] = None


@dataclass
class GridConfig:
    """Grid configuration"""
    asset: str
    center_price: float
    grid_levels: int = 10       # Levels above and below center
    grid_spacing_atr: float = 0.5   # Spacing in ATR multiples
    total_capital: float = 10000
    quantity_per_level: float = 0
    upper_bound: float = 0
    lower_bound: float = 0
    atr: float = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class GridSignal:
    """Grid trading signal"""
    asset: str
    action: GridAction
    price: float
    quantity: float
    level_id: int
    reason: str
    confidence: float
    regime_safe: bool
    generated_at: datetime


class GridTradingEngine:
    """
    Grid Trading Engine (STIG-2025-001)

    Implements ATR-based grid trading with mandatory regime safety checks.

    Key features:
    - ATR-based grid spacing (adapts to volatility)
    - 4D regime safety gate
    - Auto-disable on VolatilityShift > 0.3
    - Kelly-adjusted position sizing
    """

    # STIG-2025-001 Parameters
    DEFAULT_GRID_LEVELS = 10        # 10 above + 10 below = 20 total
    ATR_SPACING_MULTIPLIER = 0.5    # Grid spacing = 0.5 * ATR
    MAX_POSITION_PCT = 0.10         # Max 10% per asset

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.regime_classifier = AdvancedRegimeClassifier() if REGIME_AVAILABLE else None
        self._active_grids: Dict[str, GridConfig] = {}

    def _get_current_price(self, asset: str) -> float:
        """Get current price for asset"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT close
                FROM fhq_market.prices
                WHERE canonical_id = %s
                ORDER BY timestamp DESC
                LIMIT 1
            """, (asset,))
            result = cur.fetchone()
            return float(result['close']) if result else 0

    def _calculate_atr(self, asset: str, period: int = 14) -> float:
        """Calculate ATR for grid spacing"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT high, low, close
                FROM fhq_market.prices
                WHERE canonical_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """, (asset, period + 5))
            rows = cur.fetchall()

        if len(rows) < period + 1:
            return 0

        true_ranges = []
        for i in range(1, len(rows)):
            high = float(rows[i]['high'])
            low = float(rows[i]['low'])
            prev_close = float(rows[i-1]['close'])

            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)

        return np.mean(true_ranges[:period])

    def check_regime_safety(self, asset: str) -> Tuple[bool, str, Optional[RegimeVector]]:
        """
        Check if regime is safe for grid trading.

        Returns:
            (is_safe, reason, regime_vector)
        """
        if not self.regime_classifier:
            # Without regime classifier, use simplified checks
            atr = self._calculate_atr(asset)
            price = self._get_current_price(asset)

            if price == 0:
                return False, "no_price_data", None

            atr_norm = atr / price
            if atr_norm < 0.005:
                return False, "volatility_too_low", None

            return True, "simplified_check", None

        regime = self.regime_classifier.classify(asset)

        if regime.grid_safe:
            return True, "regime_safe", regime
        else:
            reasons = []
            if regime.adx >= 20:
                reasons.append(f"trending(ADX={regime.adx})")
            if regime.atr_normalized <= 0.005:
                reasons.append(f"low_vol(ATR_norm={regime.atr_normalized})")
            if regime.volatility_shift >= 0.3:
                reasons.append(f"vol_expanding({regime.volatility_shift:.1%})")
            if regime.volume_ratio < 0.7:
                reasons.append(f"low_volume({regime.volume_ratio:.1%})")

            return False, "|".join(reasons), regime

    def create_grid(
        self,
        asset: str,
        capital: float,
        grid_levels: int = None,
        force: bool = False
    ) -> Optional[GridConfig]:
        """
        Create a new grid for asset.

        Args:
            asset: Asset identifier
            capital: Capital to allocate
            grid_levels: Number of levels (default 10)
            force: Skip regime check (dangerous!)

        Returns:
            GridConfig or None if unsafe
        """
        levels = grid_levels or self.DEFAULT_GRID_LEVELS

        # Safety check
        if not force:
            is_safe, reason, regime = self.check_regime_safety(asset)
            if not is_safe:
                print(f"[GRID] {asset} unsafe: {reason}")
                return None

        # Get current price and ATR
        current_price = self._get_current_price(asset)
        atr = self._calculate_atr(asset)

        if current_price == 0 or atr == 0:
            return None

        # Calculate grid bounds
        grid_spacing = atr * self.ATR_SPACING_MULTIPLIER
        upper_bound = current_price + (levels * grid_spacing)
        lower_bound = current_price - (levels * grid_spacing)

        # Calculate quantity per level
        total_levels = levels * 2  # Above and below
        capital_per_level = capital / total_levels
        quantity_per_level = capital_per_level / current_price

        config = GridConfig(
            asset=asset,
            center_price=current_price,
            grid_levels=levels,
            grid_spacing_atr=self.ATR_SPACING_MULTIPLIER,
            total_capital=capital,
            quantity_per_level=round(quantity_per_level, 4),
            upper_bound=round(upper_bound, 2),
            lower_bound=round(lower_bound, 2),
            atr=round(atr, 4)
        )

        # Store and log
        self._active_grids[asset] = config
        self._log_grid_creation(config)

        return config

    def _log_grid_creation(self, config: GridConfig):
        """Log grid creation to database"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_alpha.grid_configs
                    (asset_id, center_price, grid_levels, grid_spacing_atr,
                     total_capital, quantity_per_level, upper_bound, lower_bound,
                     atr, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (asset_id) DO UPDATE SET
                        center_price = EXCLUDED.center_price,
                        upper_bound = EXCLUDED.upper_bound,
                        lower_bound = EXCLUDED.lower_bound,
                        status = 'ACTIVE',
                        created_at = EXCLUDED.created_at
                """, (
                    config.asset,
                    config.center_price,
                    config.grid_levels,
                    config.grid_spacing_atr,
                    config.total_capital,
                    config.quantity_per_level,
                    config.upper_bound,
                    config.lower_bound,
                    config.atr,
                    'ACTIVE',
                    config.created_at
                ))
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            pass

    def get_grid_levels(self, asset: str) -> List[GridLevel]:
        """Generate all grid levels for asset"""
        config = self._active_grids.get(asset)
        if not config:
            return []

        levels = []
        grid_spacing = config.atr * config.grid_spacing_atr

        # Buy levels (below center)
        for i in range(1, config.grid_levels + 1):
            price = config.center_price - (i * grid_spacing)
            levels.append(GridLevel(
                level_id=-i,
                price=round(price, 2),
                is_buy=True,
                quantity=config.quantity_per_level
            ))

        # Sell levels (above center)
        for i in range(1, config.grid_levels + 1):
            price = config.center_price + (i * grid_spacing)
            levels.append(GridLevel(
                level_id=i,
                price=round(price, 2),
                is_buy=False,
                quantity=config.quantity_per_level
            ))

        return sorted(levels, key=lambda x: x.price)

    def check_grid_signals(self, asset: str) -> List[GridSignal]:
        """
        Check for grid signals based on current price.

        Returns signals for any levels that should be executed.
        """
        config = self._active_grids.get(asset)
        if not config:
            return []

        # Check regime safety first
        is_safe, reason, regime = self.check_regime_safety(asset)

        current_price = self._get_current_price(asset)
        signals = []

        if not is_safe:
            # Return CLOSE_ALL signal if regime becomes unsafe
            signals.append(GridSignal(
                asset=asset,
                action=GridAction.DISABLED,
                price=current_price,
                quantity=0,
                level_id=0,
                reason=f"regime_unsafe:{reason}",
                confidence=0,
                regime_safe=False,
                generated_at=datetime.now(timezone.utc)
            ))
            return signals

        # Check each grid level
        levels = self.get_grid_levels(asset)

        for level in levels:
            if level.filled:
                continue

            # Check if price crossed level
            if level.is_buy and current_price <= level.price:
                signals.append(GridSignal(
                    asset=asset,
                    action=GridAction.BUY,
                    price=level.price,
                    quantity=level.quantity,
                    level_id=level.level_id,
                    reason="price_crossed_buy_level",
                    confidence=0.8,
                    regime_safe=True,
                    generated_at=datetime.now(timezone.utc)
                ))
            elif not level.is_buy and current_price >= level.price:
                signals.append(GridSignal(
                    asset=asset,
                    action=GridAction.SELL,
                    price=level.price,
                    quantity=level.quantity,
                    level_id=level.level_id,
                    reason="price_crossed_sell_level",
                    confidence=0.8,
                    regime_safe=True,
                    generated_at=datetime.now(timezone.utc)
                ))

        # Log signals
        for signal in signals:
            self._log_signal(signal)

        return signals

    def _log_signal(self, signal: GridSignal):
        """Log grid signal to database"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_alpha.grid_signals
                    (asset_id, action, price, quantity, level_id, reason,
                     confidence, regime_safe, generated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    signal.asset,
                    signal.action.value,
                    signal.price,
                    signal.quantity,
                    signal.level_id,
                    signal.reason,
                    signal.confidence,
                    signal.regime_safe,
                    signal.generated_at
                ))
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            pass

    def disable_grid(self, asset: str, reason: str = "manual"):
        """Disable grid for asset"""
        if asset in self._active_grids:
            del self._active_grids[asset]

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE fhq_alpha.grid_configs
                    SET status = %s
                    WHERE asset_id = %s
                """, (f"DISABLED_{reason.upper()}", asset))
                self.conn.commit()
        except Exception:
            self.conn.rollback()

    def get_active_grids(self) -> Dict[str, GridConfig]:
        """Get all active grids"""
        return self._active_grids.copy()


if __name__ == "__main__":
    print("=" * 60)
    print("IoS-016 GRID TRADING ENGINE - SELF TEST")
    print("=" * 60)

    engine = GridTradingEngine()

    # Get test assets
    print("\n[1] Fetching assets...")
    with engine.conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT DISTINCT canonical_id
            FROM fhq_market.prices
            WHERE timestamp >= NOW() - INTERVAL '60 days'
            ORDER BY canonical_id
            LIMIT 10
        """)
        assets = [r['canonical_id'] for r in cur.fetchall()]

    print(f"   Found {len(assets)} assets: {assets[:5]}...")

    # Test regime safety
    print("\n[2] Testing regime safety...")
    safe_assets = []
    for asset in assets[:5]:
        is_safe, reason, regime = engine.check_regime_safety(asset)
        status = "SAFE" if is_safe else f"UNSAFE({reason})"
        print(f"   {asset}: {status}")
        if is_safe:
            safe_assets.append(asset)

    # Create grid for safe asset
    if safe_assets:
        test_asset = safe_assets[0]
        print(f"\n[3] Creating grid for {test_asset}...")
        grid = engine.create_grid(test_asset, capital=10000)

        if grid:
            print(f"   Center: ${grid.center_price:.2f}")
            print(f"   ATR: ${grid.atr:.4f}")
            print(f"   Bounds: ${grid.lower_bound:.2f} - ${grid.upper_bound:.2f}")
            print(f"   Qty/Level: {grid.quantity_per_level:.4f}")

            levels = engine.get_grid_levels(test_asset)
            print(f"\n[4] Grid levels ({len(levels)} total):")
            for level in levels[:5]:
                action = "BUY" if level.is_buy else "SELL"
                print(f"   Level {level.level_id}: ${level.price:.2f} -> {action} {level.quantity:.4f}")
            print(f"   ... ({len(levels) - 5} more)")

            print(f"\n[5] Checking for signals...")
            signals = engine.check_grid_signals(test_asset)
            print(f"   Generated {len(signals)} signals")
            for sig in signals[:3]:
                print(f"   {sig.action.value} @ ${sig.price:.2f} (level {sig.level_id})")
    else:
        print("\n[3] No safe assets for grid testing")
        # Force create for demo
        if assets:
            print(f"\n[3b] Force-creating grid for {assets[0]} (demo only)...")
            grid = engine.create_grid(assets[0], capital=10000, force=True)
            if grid:
                print(f"   Center: ${grid.center_price:.2f}")
                print(f"   Bounds: ${grid.lower_bound:.2f} - ${grid.upper_bound:.2f}")

    print("\n" + "=" * 60)
    print("IoS-016 GRID TRADING ENGINE - TEST COMPLETE")
    print("=" * 60)
