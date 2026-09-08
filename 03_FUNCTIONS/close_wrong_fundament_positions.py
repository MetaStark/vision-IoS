#!/usr/bin/env python3
"""
WRONG FUNDAMENT POSITION CLOSURE
================================
Directive: CEO-DIR-2026-DBV-003
Classification: GOVERNANCE-CRITICAL / P0 ACTION
Date: 2026-01-20

Closes LONG positions that violate inversion logic:
- ADBE, GIS, INTU, NOW are in inversion_universe with 0% hit rate on UP
- Correct direction per inversion: DOWN (SHORT)
- Current positions: LONG (WRONG)

Authority: CEO, STIG
"""

import os
import sys
import json
import uuid
import hashlib
from datetime import datetime, timezone
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor, Json

# Load environment from parent directory
import pathlib
env_path = pathlib.Path(__file__).parent.parent.parent / '.env'
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

# Use paper trading credentials (per alpaca_paper_config)
ALPACA_API_KEY = os.getenv('ALPACA_PAPER_API_KEY', os.getenv('ALPACA_API_KEY', ''))
ALPACA_SECRET_KEY = os.getenv('ALPACA_PAPER_SECRET_KEY', os.getenv('ALPACA_SECRET_KEY', ''))

# Positions to close with reason
WRONG_FUNDAMENT_POSITIONS = [
    {
        "ticker": "ADBE",
        "qty": 7,
        "current_direction": "LONG",
        "correct_direction": "SHORT",
        "reason": "Inversion universe asset with 0% hit rate on UP. Original Brier 0.993, Inverted Brier 0.00001. LONG violates inversion logic.",
        "learning_id": "LEARN-20260120-005"
    },
    {
        "ticker": "GIS",
        "qty": 46,
        "current_direction": "LONG",
        "correct_direction": "SHORT",
        "reason": "Inversion universe asset with 0% hit rate on UP. Original Brier 0.998, Inverted Brier 0.00001. LONG violates inversion logic.",
        "learning_id": "LEARN-20260120-006"
    },
    {
        "ticker": "INTU",
        "qty": 3,
        "current_direction": "LONG",
        "correct_direction": "SHORT",
        "reason": "Inversion universe asset with 0% hit rate on UP. Original Brier 0.993, Inverted Brier 0.00001. LONG violates inversion logic.",
        "learning_id": "LEARN-20260120-007"
    },
    {
        "ticker": "NOW",
        "qty": 15,
        "current_direction": "LONG",
        "correct_direction": "SHORT",
        "reason": "Inversion universe asset with 0% hit rate on UP. Original Brier 0.998, Inverted Brier 0.00001. LONG violates inversion logic.",
        "learning_id": "LEARN-20260120-008"
    }
]


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def get_alpaca_client():
    """
    Initialize Alpaca TradingClient.

    Per Alpaca docs (https://alpaca.markets/sdks/python/trading.html):
    - Set paper=True for paper trading
    - Keys must match paper account credentials
    """
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        raise ValueError(
            "Alpaca credentials not configured. "
            "Set ALPACA_PAPER_API_KEY and ALPACA_PAPER_SECRET_KEY in environment or .env file"
        )

    return TradingClient(
        api_key=ALPACA_API_KEY,
        secret_key=ALPACA_SECRET_KEY,
        paper=True  # Paper trading only - per docs.alpaca.markets
    )


def verify_position_at_broker(client, ticker: str) -> dict:
    """Verify position exists at Alpaca before closing."""
    try:
        position = client.get_open_position(ticker)
        return {
            "exists": True,
            "qty": float(position.qty),
            "side": position.side.value,
            "avg_entry_price": float(position.avg_entry_price),
            "current_price": float(position.current_price),
            "unrealized_pnl": float(position.unrealized_pnl),
            "market_value": float(position.market_value)
        }
    except Exception as e:
        return {"exists": False, "error": str(e)}


def close_position_at_broker(client, ticker: str) -> dict:
    """
    Close position at Alpaca broker.

    Per Alpaca docs (https://alpaca.markets/sdks/python/api_reference/trading/positions.html):
    - TradingClient.close_position(symbol_or_asset_id) liquidates the position
    - Returns the Order object placed to close the position
    - Throws error if position doesn't exist
    """
    try:
        # Close position using SDK method - per Alpaca documentation
        order = client.close_position(ticker)
        return {
            "success": True,
            "order_id": str(order.id),
            "symbol": order.symbol,
            "qty": str(order.qty),
            "side": order.side.value if hasattr(order.side, 'value') else str(order.side),
            "status": order.status.value if hasattr(order.status, 'value') else str(order.status),
            "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
            "filled_avg_price": str(order.filled_avg_price) if order.filled_avg_price else None
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def close_all_positions_at_broker(client) -> dict:
    """
    Close ALL positions at Alpaca broker.

    Per Alpaca docs (https://alpaca.markets/sdks/python/api_reference/trading/positions.html):
    - TradingClient.close_all_positions(cancel_orders=True)
    - Liquidates all positions AND cancels all open orders
    - Returns list of ClosePositionResponse objects
    """
    try:
        responses = client.close_all_positions(cancel_orders=True)
        return {
            "success": True,
            "positions_closed": len(responses) if responses else 0,
            "responses": [
                {
                    "symbol": r.symbol if hasattr(r, 'symbol') else str(r),
                    "status": r.status if hasattr(r, 'status') else "unknown"
                }
                for r in (responses or [])
            ]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def log_closure_to_database(conn, closure_record: dict):
    """Log position closure to database for audit trail."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_meta.cognitive_engine_evidence (
                evidence_type,
                directive_ref,
                agent_id,
                payload
            ) VALUES (
                'POSITION_CLOSURE_WRONG_FUNDAMENT',
                'CEO-DIR-2026-DBV-003',
                'EC-003_STIG',
                %s
            )
        """, (Json(closure_record),))
    conn.commit()


def update_ios012b_position(conn, ticker: str, exit_reason: str):
    """Mark IOS012B position as closed if exists."""
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE fhq_alpha.ios012b_paper_positions
            SET status = 'CLOSED',
                exit_reason = %s,
                exit_timestamp = NOW(),
                updated_at = NOW()
            WHERE ticker = %s AND status = 'OPEN'
            RETURNING position_id, ticker, shares, direction
        """, (exit_reason, ticker))
        result = cur.fetchone()
    conn.commit()
    return result


def main():
    print("=" * 70)
    print("WRONG FUNDAMENT POSITION CLOSURE")
    print("Directive: CEO-DIR-2026-DBV-003")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    # Initialize clients
    client = get_alpaca_client()
    conn = get_db_connection()

    closure_results = []
    total_pnl = 0.0

    for pos in WRONG_FUNDAMENT_POSITIONS:
        ticker = pos["ticker"]
        print(f"\n--- Processing {ticker} ---")

        # Step 1: Verify position exists at broker
        broker_pos = verify_position_at_broker(client, ticker)
        if not broker_pos.get("exists"):
            print(f"  Position NOT found at broker: {broker_pos.get('error', 'Unknown')}")
            closure_results.append({
                "ticker": ticker,
                "status": "NOT_FOUND",
                "error": broker_pos.get("error")
            })
            continue

        print(f"  Found: {broker_pos['qty']} shares @ ${broker_pos['avg_entry_price']:.2f}")
        print(f"  Current: ${broker_pos['current_price']:.2f}, P&L: ${broker_pos['unrealized_pnl']:.2f}")

        # Step 2: Close position at broker
        close_result = close_position_at_broker(client, ticker)
        if not close_result.get("success"):
            print(f"  FAILED to close: {close_result.get('error')}")
            closure_results.append({
                "ticker": ticker,
                "status": "CLOSE_FAILED",
                "error": close_result.get("error"),
                "broker_position": broker_pos
            })
            continue

        print(f"  CLOSED: Order {close_result['order_id']} - {close_result['status']}")
        total_pnl += broker_pos['unrealized_pnl']

        # Step 3: Update IOS012B if tracked
        ios012b_result = update_ios012b_position(conn, ticker, f"WRONG_FUNDAMENT: {pos['reason']}")
        if ios012b_result:
            print(f"  IOS012B position updated: {ios012b_result}")

        # Step 4: Create closure record
        closure_record = {
            "ticker": ticker,
            "status": "CLOSED",
            "reason": pos["reason"],
            "learning_id": pos["learning_id"],
            "current_direction": pos["current_direction"],
            "correct_direction": pos["correct_direction"],
            "broker_position": broker_pos,
            "close_order": close_result,
            "ios012b_updated": ios012b_result is not None,
            "closed_at": datetime.now(timezone.utc).isoformat()
        }

        # Step 5: Log to database
        log_closure_to_database(conn, closure_record)
        print(f"  Evidence logged to database")

        closure_results.append(closure_record)

    # Summary
    print("\n" + "=" * 70)
    print("CLOSURE SUMMARY")
    print("=" * 70)

    closed_count = sum(1 for r in closure_results if r.get("status") == "CLOSED")
    print(f"Positions closed: {closed_count}/{len(WRONG_FUNDAMENT_POSITIONS)}")
    print(f"Total realized P&L: ${total_pnl:.2f}")

    # Create evidence file
    evidence = {
        "evidence_id": f"WRONG_FUNDAMENT_CLOSURE_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "directive": "CEO-DIR-2026-DBV-003",
        "classification": "GOVERNANCE-CRITICAL / P0_ACTION",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "STIG (EC-003_2026_PRODUCTION)",
        "summary": {
            "positions_targeted": len(WRONG_FUNDAMENT_POSITIONS),
            "positions_closed": closed_count,
            "total_realized_pnl": total_pnl,
            "reason": "LONG positions on inversion universe assets with 0% hit rate on UP direction"
        },
        "closure_results": closure_results,
        "learnings": [
            {
                "id": "LEARN-20260120-005",
                "category": "DIRECTION_VIOLATION",
                "description": "ADBE was LONG but inversion logic requires SHORT",
                "action": "Position closed, loss realized as tuition"
            },
            {
                "id": "LEARN-20260120-006",
                "category": "DIRECTION_VIOLATION",
                "description": "GIS was LONG but inversion logic requires SHORT",
                "action": "Position closed, loss realized as tuition"
            },
            {
                "id": "LEARN-20260120-007",
                "category": "DIRECTION_VIOLATION",
                "description": "INTU was LONG but inversion logic requires SHORT",
                "action": "Position closed, loss realized as tuition"
            },
            {
                "id": "LEARN-20260120-008",
                "category": "DIRECTION_VIOLATION",
                "description": "NOW was LONG but inversion logic requires SHORT",
                "action": "Position closed, loss realized as tuition"
            }
        ],
        "hindsight_firewall_value": {
            "status": "VALIDATED",
            "description": "Shadow mode allowed discovery of direction bug with minimal paper losses",
            "paper_loss_total": total_pnl,
            "real_capital_protected": True
        },
        "hash": hashlib.md5(json.dumps(closure_results, default=str).encode()).hexdigest()
    }

    evidence_path = os.path.join(
        os.path.dirname(__file__),
        "evidence",
        f"CEO_DIR_2026_DBV_003_WRONG_FUNDAMENT_CLOSURE_{datetime.now().strftime('%Y%m%d')}.json"
    )

    with open(evidence_path, 'w') as f:
        json.dump(evidence, f, indent=2, default=str)

    print(f"\nEvidence saved: {evidence_path}")

    conn.close()
    return closure_results


if __name__ == "__main__":
    main()
