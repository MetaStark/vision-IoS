#!/usr/bin/env python3
"""
Shadow Paper Trade Monitor
CD-026 Autonomous Trade Tracking

Checks open trades against current prices.
Logs results when stop/target hit or 72h expires.
Runs autonomously. No human input required.
"""

import os
import json
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

TRADES_FILE = Path(__file__).parent.parent / "05_GOVERNANCE/PHASE3/SHADOW_PAPER_TRADES.json"

def get_current_price(symbol: str) -> float:
    """Fetch current price from CoinGecko (free, no API key)."""
    coin_map = {
        "BTC-PERP": "bitcoin",
        "ETH-PERP": "ethereum",
        "SOL-PERP": "solana"
    }
    coin_id = coin_map.get(symbol, "bitcoin")

    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        return data[coin_id]["usd"]
    except Exception as e:
        print(f"[ERROR] Failed to fetch price for {symbol}: {e}")
        return None

def check_trade(trade: dict, current_price: float) -> dict:
    """Check if trade hit stop, target, or expired."""

    opened_at = datetime.fromisoformat(trade["opened_at"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    hours_open = (now - opened_at).total_seconds() / 3600

    direction = trade["direction"]
    entry = trade["entry_price"]
    stop = trade["stop_price"]
    target = trade["target_price"]

    result = None
    exit_price = None

    if direction == "SHORT":
        if current_price <= target:
            result = "WIN"
            exit_price = target
        elif current_price >= stop:
            result = "LOSS"
            exit_price = stop
        elif hours_open >= 72:
            result = "EXPIRED"
            exit_price = current_price
    else:  # LONG
        if current_price >= target:
            result = "WIN"
            exit_price = target
        elif current_price <= stop:
            result = "LOSS"
            exit_price = stop
        elif hours_open >= 72:
            result = "EXPIRED"
            exit_price = current_price

    if result:
        if direction == "SHORT":
            pnl_pct = ((entry - exit_price) / entry) * 100
        else:
            pnl_pct = ((exit_price - entry) / entry) * 100

        return {
            "closed": True,
            "result": result,
            "exit_price": exit_price,
            "pnl_pct": round(pnl_pct, 2),
            "closed_at": now.isoformat()
        }

    return {"closed": False, "hours_open": round(hours_open, 1), "current_price": current_price}

def run_monitor():
    """Main monitoring loop."""

    if not TRADES_FILE.exists():
        print("[MONITOR] No trades file found.")
        return

    with open(TRADES_FILE, "r") as f:
        data = json.load(f)

    updated = False

    for trade in data["trades"]:
        if trade["status"] != "OPEN":
            continue

        current_price = get_current_price(trade["instrument"])
        if current_price is None:
            continue

        check = check_trade(trade, current_price)

        if check["closed"]:
            trade["status"] = "CLOSED"
            trade["result"] = check["result"]
            trade["exit_price"] = check["exit_price"]
            trade["pnl_pct"] = check["pnl_pct"]
            trade["closed_at"] = check["closed_at"]
            updated = True

            print(f"[CLOSED] {trade['trade_id']} {trade['instrument']} {trade['direction']}")
            print(f"         Result: {check['result']} | PnL: {check['pnl_pct']:+.2f}%")
        else:
            print(f"[OPEN] {trade['trade_id']} {trade['instrument']} @ {check['current_price']:,.0f} ({check['hours_open']}h)")

    if updated:
        # Update summary
        closed = [t for t in data["trades"] if t["status"] == "CLOSED"]
        wins = len([t for t in closed if t["result"] == "WIN"])
        losses = len([t for t in closed if t["result"] in ["LOSS", "EXPIRED"]])

        data["summary"]["closed_trades"] = len(closed)
        data["summary"]["open_trades"] = len(data["trades"]) - len(closed)
        data["summary"]["wins"] = wins
        data["summary"]["losses"] = losses
        data["summary"]["win_rate"] = round(wins / len(closed), 2) if closed else None
        data["summary"]["total_pnl_pct"] = round(sum(t["pnl_pct"] for t in closed), 2)

        with open(TRADES_FILE, "w") as f:
            json.dump(data, f, indent=2)

        print(f"\n[SUMMARY] Win rate: {data['summary']['win_rate']} | Total PnL: {data['summary']['total_pnl_pct']:+.2f}%")

if __name__ == "__main__":
    print(f"[MONITOR] Shadow Paper Trade Check - {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)
    run_monitor()
