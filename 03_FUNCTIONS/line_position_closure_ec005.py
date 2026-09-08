#!/usr/bin/env python3
"""
LINE POSITION CLOSURE (EC-005)
==============================
Directive: CEO-DIR-2026-DBV-003
Classification: GOVERNANCE-CRITICAL / P0 ACTION
Date: 2026-01-20

LINE (EC-005) is the ONLY authorized execution agent per IoS-012.
This script executes position closures through proper governance chain.

Authority: LINE (EC-005) per IoS-012
"""

import os
import sys
import json
import hashlib
from datetime import datetime, timezone
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor, Json

# Load environment
import pathlib
env_path = pathlib.Path('C:/fhq-market-system/vision-ios/.env')
load_dotenv(env_path)

# Alpaca SDK
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    print("ERROR: Alpaca SDK not installed. Run: pip install alpaca-py")
    sys.exit(1)

# Configuration
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Use paper trading credentials
ALPACA_API_KEY = os.getenv('ALPACA_API_KEY', os.getenv('ALPACA_PAPER_API_KEY', ''))
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET', os.getenv('ALPACA_SECRET_KEY', os.getenv('ALPACA_PAPER_SECRET_KEY', '')))


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def get_alpaca_client():
    """Initialize Alpaca TradingClient for paper trading."""
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        raise ValueError(
            "Alpaca credentials not configured. "
            "Set ALPACA_API_KEY and ALPACA_SECRET in .env file"
        )

    return TradingClient(
        api_key=ALPACA_API_KEY,
        secret_key=ALPACA_SECRET_KEY,
        paper=True
    )


def get_current_positions(client):
    """Get all open positions from Alpaca (TRUTH)."""
    positions = client.get_all_positions()
    return [
        {
            "symbol": p.symbol,
            "qty": float(p.qty),
            "side": p.side.value if hasattr(p.side, 'value') else str(p.side),
            "avg_entry_price": float(p.avg_entry_price),
            "current_price": float(p.current_price),
            "unrealized_pnl": float(p.unrealized_pl),
            "market_value": float(p.market_value)
        }
        for p in positions
    ]


def get_open_orders(client):
    """Get all open orders from Alpaca."""
    orders = client.get_orders()
    return [
        {
            "order_id": str(o.id),
            "symbol": o.symbol,
            "side": o.side.value if hasattr(o.side, 'value') else str(o.side),
            "qty": str(o.qty),
            "type": o.type.value if hasattr(o.type, 'value') else str(o.type),
            "status": o.status.value if hasattr(o.status, 'value') else str(o.status),
            "submitted_at": o.submitted_at.isoformat() if o.submitted_at else None
        }
        for o in orders
    ]


def close_position(client, symbol):
    """Close a position via LINE (EC-005) authority."""
    try:
        order = client.close_position(symbol)
        return {
            "success": True,
            "order_id": str(order.id),
            "symbol": order.symbol,
            "qty": str(order.qty),
            "side": order.side.value if hasattr(order.side, 'value') else str(order.side),
            "status": order.status.value if hasattr(order.status, 'value') else str(order.status),
            "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None
        }
    except Exception as e:
        return {"success": False, "symbol": symbol, "error": str(e)}


def cancel_order(client, order_id):
    """Cancel an open order via LINE (EC-005) authority."""
    try:
        client.cancel_order_by_id(order_id)
        return {"success": True, "order_id": order_id, "action": "cancelled"}
    except Exception as e:
        return {"success": False, "order_id": order_id, "error": str(e)}


def log_execution_to_database(conn, execution_record):
    """Log LINE execution to database for audit trail."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_meta.cognitive_engine_evidence (
                evidence_type,
                directive_ref,
                agent_id,
                payload
            ) VALUES (
                'LINE_EC005_POSITION_CLOSURE',
                'CEO-DIR-2026-DBV-003',
                'EC-005_LINE',
                %s
            )
        """, (Json(execution_record),))
    conn.commit()


def main():
    print("=" * 70)
    print("LINE (EC-005) POSITION CLOSURE EXECUTION")
    print("Directive: CEO-DIR-2026-DBV-003")
    print("Authority: LINE (EC-005) per IoS-012")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    # Initialize clients
    print("\n[1] Initializing Alpaca connection...")
    client = get_alpaca_client()
    print(f"    API Key: {ALPACA_API_KEY[:10]}...")
    print(f"    Mode: PAPER TRADING")

    conn = get_db_connection()
    print("    Database: Connected")

    # Get account status
    account = client.get_account()
    print(f"\n[2] Account Status:")
    print(f"    Account: {account.account_number}")
    print(f"    Equity: ${float(account.equity):,.2f}")
    print(f"    Cash: ${float(account.cash):,.2f}")

    # Step 1: Get current positions (TRUTH)
    print("\n[3] Getting open positions from Alpaca (TRUTH)...")
    positions = get_current_positions(client)
    print(f"    Found {len(positions)} open positions")

    total_pnl = 0
    for pos in positions:
        pnl = pos['unrealized_pnl']
        total_pnl += pnl
        print(f"    - {pos['symbol']}: {pos['qty']} shares @ ${pos['avg_entry_price']:.2f} | P&L: ${pnl:.2f}")

    print(f"\n    Total Unrealized P&L: ${total_pnl:.2f}")

    # Step 2: Get open orders
    print("\n[4] Getting open orders from Alpaca...")
    orders = get_open_orders(client)
    print(f"    Found {len(orders)} open orders")
    for order in orders:
        print(f"    - {order['symbol']}: {order['side']} {order['qty']} | Status: {order['status']} | ID: {order['order_id'][:8]}...")

    # Step 3: Cancel all open orders first
    print("\n[5] Cancelling all open orders via LINE (EC-005)...")
    order_cancellations = []
    for order in orders:
        result = cancel_order(client, order['order_id'])
        order_cancellations.append(result)
        if result['success']:
            print(f"    CANCELLED: {order['symbol']} order {order['order_id'][:8]}...")
        else:
            print(f"    FAILED: {order['symbol']} - {result.get('error')}")

    # Step 4: Close all positions
    print("\n[6] Closing all positions via LINE (EC-005)...")
    position_closures = []
    for pos in positions:
        symbol = pos['symbol']
        result = close_position(client, symbol)
        result['pre_close_state'] = pos
        position_closures.append(result)

        if result['success']:
            print(f"    CLOSED: {symbol} - Order {result['order_id'][:8]}... | Status: {result['status']}")
        else:
            print(f"    FAILED: {symbol} - {result.get('error')}")

    # Step 5: Verify closure
    print("\n[7] Verifying closure from Alpaca (TRUTH)...")
    remaining_positions = get_current_positions(client)
    remaining_orders = get_open_orders(client)
    print(f"    Remaining positions: {len(remaining_positions)}")
    print(f"    Remaining orders: {len(remaining_orders)}")

    # Create evidence record
    execution_record = {
        "execution_id": f"LINE_CLOSURE_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "directive": "CEO-DIR-2026-DBV-003",
        "agent": "LINE (EC-005)",
        "authority": "IoS-012",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "pre_execution_state": {
            "positions": positions,
            "orders": orders,
            "total_unrealized_pnl": total_pnl
        },
        "order_cancellations": order_cancellations,
        "position_closures": position_closures,
        "post_execution_state": {
            "remaining_positions": remaining_positions,
            "remaining_orders": remaining_orders
        },
        "verification": {
            "all_positions_closed": len(remaining_positions) == 0,
            "all_orders_cancelled": len(remaining_orders) == 0
        }
    }

    # Log to database
    print("\n[8] Logging execution to database...")
    log_execution_to_database(conn, execution_record)
    print("    Evidence logged: LINE_EC005_POSITION_CLOSURE")

    # Save evidence file
    evidence_path = os.path.join(
        os.path.dirname(__file__),
        "evidence",
        f"LINE_EC005_POSITION_CLOSURE_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    with open(evidence_path, 'w') as f:
        json.dump(execution_record, f, indent=2, default=str)

    print(f"    Evidence file: {evidence_path}")

    # Summary
    print("\n" + "=" * 70)
    print("EXECUTION SUMMARY")
    print("=" * 70)
    print(f"Orders cancelled: {sum(1 for r in order_cancellations if r.get('success'))}/{len(orders)}")
    print(f"Positions closed: {sum(1 for r in position_closures if r.get('success'))}/{len(positions)}")
    print(f"Total realized P&L: ${total_pnl:.2f}")
    print(f"Verification: {'PASS' if len(remaining_positions) == 0 else 'FAIL'}")
    print("=" * 70)

    conn.close()
    return execution_record


if __name__ == "__main__":
    main()
