#!/usr/bin/env python3
"""
MARKET STREAMER V2 — WEBSOCKET PUSH SERVICE
============================================
CEO DIRECTIVE: Input Stream Verification (EAR-CHECK)

This service MUST run as a continuous process OUTSIDE the Orchestrator loop.
It subscribes to Alpaca WebSocket and PUSHES price events to the Event Queue.

Authority: CEO Directive EC-005 Phase 2
Executor: STIG (CTO)
Date: 2025-12-09

DEPLOYMENT:
    nohup python market_streamer_v2.py > /var/log/fhq/market_streamer.log 2>&1 &

    OR (Windows):
    pythonw market_streamer_v2.py

    OR (systemd):
    systemctl start fhq-market-streamer
"""

import os
import sys
import json
import uuid
import time
import signal
import logging
import threading
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional, List
from queue import Queue, Empty

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment
load_dotenv(override=True)

# Configure logging
log_path = os.getenv('FHQ_LOG_PATH', 'C:/fhq-market-system/vision-ios/logs')
os.makedirs(log_path, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - MARKET_STREAMER - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{log_path}/market_streamer.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("MARKET_STREAMER")


# =============================================================================
# CONFIGURATION
# =============================================================================

class StreamerConfig:
    """Streamer configuration."""
    # Alpaca WebSocket endpoints
    ALPACA_CRYPTO_WS = "wss://stream.data.alpaca.markets/v1beta3/crypto/us"
    ALPACA_STOCK_WS = "wss://stream.data.alpaca.markets/v2/iex"

    # Symbols to subscribe
    CRYPTO_SYMBOLS = ['BTC/USD', 'ETH/USD', 'SOL/USD']
    STOCK_SYMBOLS = ['SPY', 'QQQ', 'NVDA', 'AAPL', 'MSFT']

    # Database batch insert settings
    BATCH_SIZE = 50
    FLUSH_INTERVAL_SECONDS = 5

    # Heartbeat interval
    HEARTBEAT_INTERVAL = 30

    # Reconnect settings
    MAX_RECONNECT_ATTEMPTS = 10
    RECONNECT_DELAY_SECONDS = 5


# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv('PGHOST', '127.0.0.1'),
        port=os.getenv('PGPORT', '54322'),
        dbname=os.getenv('PGDATABASE', 'postgres'),
        user=os.getenv('PGUSER', 'postgres'),
        password=os.getenv('PGPASSWORD', 'postgres')
    )


# =============================================================================
# EVENT QUEUE WRITER
# =============================================================================

class EventQueueWriter:
    """Writes price events to the database event queue."""

    def __init__(self):
        self.buffer: List[Dict] = []
        self.last_flush = time.time()
        self.lock = threading.Lock()
        self.total_events_written = 0

    def add_price_event(
        self,
        symbol: str,
        price: float,
        volume: float = 0,
        bid: float = None,
        ask: float = None,
        event_type: str = 'PRICE_UPDATE'
    ):
        """Add a price event to the buffer."""
        # Normalize symbol (BTC/USD -> BTC-USD)
        canonical_id = symbol.replace('/', '-')

        event = {
            'canonical_id': canonical_id,
            'price': price,
            'volume': volume,
            'bid': bid,
            'ask': ask,
            'event_type': event_type,
            'timestamp': datetime.now(timezone.utc)
        }

        with self.lock:
            self.buffer.append(event)

        # Check if we should flush
        if len(self.buffer) >= StreamerConfig.BATCH_SIZE:
            self.flush()
        elif time.time() - self.last_flush >= StreamerConfig.FLUSH_INTERVAL_SECONDS:
            self.flush()

    def flush(self):
        """Flush buffer to database."""
        import hashlib

        with self.lock:
            if not self.buffer:
                return

            events_to_write = self.buffer.copy()
            self.buffer.clear()
            self.last_flush = time.time()

        try:
            conn = get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get or create batch_id for this flush
                batch_id = str(uuid.uuid4())

                for event in events_to_write:
                    # Get asset_id from existing prices or generate deterministic UUID
                    cur.execute("""
                        SELECT DISTINCT asset_id FROM fhq_market.prices
                        WHERE canonical_id = %s
                        LIMIT 1
                    """, (event['canonical_id'],))
                    asset_row = cur.fetchone()

                    if asset_row:
                        asset_id = asset_row['asset_id']
                    else:
                        # Generate deterministic UUID from canonical_id
                        asset_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"fhq.market.{event['canonical_id']}"))

                    # Create data hash
                    data_str = f"{event['canonical_id']}|{event['timestamp']}|{event['price']}"
                    data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:32]

                    # Insert price into fhq_market.prices
                    cur.execute("""
                        INSERT INTO fhq_market.prices (
                            asset_id, canonical_id, timestamp, open, high, low, close,
                            volume, source, data_hash, batch_id
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (canonical_id, timestamp) DO UPDATE
                        SET close = EXCLUDED.close,
                            high = GREATEST(fhq_market.prices.high, EXCLUDED.high),
                            low = LEAST(fhq_market.prices.low, EXCLUDED.low),
                            volume = fhq_market.prices.volume + EXCLUDED.volume
                    """, (
                        asset_id,
                        event['canonical_id'],
                        event['timestamp'],
                        event['price'],  # open
                        event['price'],  # high
                        event['price'],  # low
                        event['price'],  # close
                        event['volume'],
                        'alpaca_websocket',
                        data_hash,
                        batch_id
                    ))

                    # Create system event for significant price moves
                    cur.execute("""
                        INSERT INTO fhq_governance.system_events (
                            event_type,
                            event_category,
                            event_severity,
                            source_agent,
                            source_component,
                            event_title,
                            event_description,
                            event_data
                        ) VALUES (
                            %s,
                            'PERCEPTION',
                            'INFO',
                            'LINE',
                            'market_streamer_v2',
                            %s,
                            %s,
                            %s
                        )
                    """, (
                        event['event_type'],
                        f"{event['canonical_id']} Price Update",
                        f"Price: {event['price']} at {event['timestamp']}",
                        json.dumps({
                            'canonical_id': event['canonical_id'],
                            'price': float(event['price']),
                            'volume': float(event['volume']),
                            'source': 'WEBSOCKET_PUSH',
                            'bid': event['bid'],
                            'ask': event['ask']
                        })
                    ))

                conn.commit()

            self.total_events_written += len(events_to_write)
            logger.info(f"Flushed {len(events_to_write)} events (total: {self.total_events_written})")

        except Exception as e:
            logger.error(f"Failed to flush events: {e}")
        finally:
            if conn:
                conn.close()

    def emit_heartbeat(self):
        """Emit a heartbeat event to prove the streamer is alive."""
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.system_events (
                        event_type,
                        event_category,
                        event_severity,
                        source_agent,
                        source_component,
                        event_title,
                        event_description,
                        event_data
                    ) VALUES (
                        'STREAMER_HEARTBEAT',
                        'HEARTBEAT',
                        'INFO',
                        'LINE',
                        'market_streamer_v2',
                        'WebSocket Streamer Alive',
                        'Continuous market data feed active',
                        %s
                    )
                """, (json.dumps({
                    'uptime_seconds': time.time() - self.start_time if hasattr(self, 'start_time') else 0,
                    'events_written': self.total_events_written,
                    'buffer_size': len(self.buffer),
                    'source': 'WEBSOCKET_PUSH'
                }),))
                conn.commit()
            logger.info(f"Heartbeat emitted. Total events: {self.total_events_written}")
        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")
        finally:
            if conn:
                conn.close()


# =============================================================================
# ALPACA WEBSOCKET CLIENT
# =============================================================================

class AlpacaStreamer:
    """Alpaca WebSocket streamer for crypto and stocks."""

    def __init__(self, writer: EventQueueWriter):
        self.writer = writer
        self.writer.start_time = time.time()
        self.running = False
        self.ws_crypto = None
        self.ws_stock = None
        self.reconnect_attempts = 0

    def _get_auth_message(self) -> str:
        """Get authentication message for Alpaca."""
        return json.dumps({
            "action": "auth",
            "key": os.getenv('ALPACA_API_KEY'),
            "secret": os.getenv('ALPACA_SECRET')
        })

    def _get_crypto_subscribe_message(self) -> str:
        """Get crypto subscription message."""
        return json.dumps({
            "action": "subscribe",
            "trades": StreamerConfig.CRYPTO_SYMBOLS,
            "quotes": StreamerConfig.CRYPTO_SYMBOLS,
            "bars": StreamerConfig.CRYPTO_SYMBOLS
        })

    def _get_stock_subscribe_message(self) -> str:
        """Get stock subscription message."""
        return json.dumps({
            "action": "subscribe",
            "trades": StreamerConfig.STOCK_SYMBOLS,
            "quotes": StreamerConfig.STOCK_SYMBOLS,
            "bars": StreamerConfig.STOCK_SYMBOLS
        })

    def _handle_crypto_message(self, message: Dict):
        """Handle incoming crypto WebSocket message."""
        try:
            for item in message:
                msg_type = item.get('T')

                if msg_type == 't':  # Trade
                    self.writer.add_price_event(
                        symbol=item.get('S'),
                        price=float(item.get('p', 0)),
                        volume=float(item.get('s', 0)),
                        event_type='CRYPTO_TRADE'
                    )
                elif msg_type == 'q':  # Quote
                    self.writer.add_price_event(
                        symbol=item.get('S'),
                        price=(float(item.get('bp', 0)) + float(item.get('ap', 0))) / 2,
                        bid=float(item.get('bp', 0)),
                        ask=float(item.get('ap', 0)),
                        event_type='CRYPTO_QUOTE'
                    )
                elif msg_type == 'b':  # Bar
                    self.writer.add_price_event(
                        symbol=item.get('S'),
                        price=float(item.get('c', 0)),  # close
                        volume=float(item.get('v', 0)),
                        event_type='CRYPTO_BAR'
                    )
        except Exception as e:
            logger.error(f"Error handling crypto message: {e}")

    def _handle_stock_message(self, message: Dict):
        """Handle incoming stock WebSocket message."""
        try:
            for item in message:
                msg_type = item.get('T')

                if msg_type == 't':  # Trade
                    self.writer.add_price_event(
                        symbol=item.get('S'),
                        price=float(item.get('p', 0)),
                        volume=float(item.get('s', 0)),
                        event_type='STOCK_TRADE'
                    )
                elif msg_type == 'q':  # Quote
                    self.writer.add_price_event(
                        symbol=item.get('S'),
                        price=(float(item.get('bp', 0)) + float(item.get('ap', 0))) / 2,
                        bid=float(item.get('bp', 0)),
                        ask=float(item.get('ap', 0)),
                        event_type='STOCK_QUOTE'
                    )
                elif msg_type == 'b':  # Bar
                    self.writer.add_price_event(
                        symbol=item.get('S'),
                        price=float(item.get('c', 0)),
                        volume=float(item.get('v', 0)),
                        event_type='STOCK_BAR'
                    )
        except Exception as e:
            logger.error(f"Error handling stock message: {e}")

    def run_crypto_stream(self):
        """Run crypto WebSocket stream."""
        try:
            import websocket

            def on_open(ws):
                logger.info(f"[CRYPTO] Connected to {StreamerConfig.ALPACA_CRYPTO_WS}")
                ws.send(self._get_auth_message())

            def on_message(ws, message):
                data = json.loads(message)

                # Handle authentication response
                if isinstance(data, list) and len(data) > 0:
                    if data[0].get('T') == 'success':
                        msg = data[0].get('msg', '')
                        if msg == 'authenticated':
                            logger.info("[CRYPTO] Authenticated! Subscribing...")
                            ws.send(self._get_crypto_subscribe_message())
                        elif msg == 'subscribed':
                            logger.info(f"[CRYPTO] Subscribed to {StreamerConfig.CRYPTO_SYMBOLS}")
                    else:
                        self._handle_crypto_message(data)

            def on_error(ws, error):
                logger.error(f"[CRYPTO] WebSocket error: {error}")

            def on_close(ws, close_status_code, close_msg):
                logger.warning(f"[CRYPTO] WebSocket closed: {close_status_code} {close_msg}")

            self.ws_crypto = websocket.WebSocketApp(
                StreamerConfig.ALPACA_CRYPTO_WS,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )

            self.ws_crypto.run_forever()

        except Exception as e:
            logger.error(f"[CRYPTO] Stream error: {e}")

    def run_stock_stream(self):
        """Run stock WebSocket stream."""
        try:
            import websocket

            def on_open(ws):
                logger.info(f"[STOCK] Connected to {StreamerConfig.ALPACA_STOCK_WS}")
                ws.send(self._get_auth_message())

            def on_message(ws, message):
                data = json.loads(message)

                if isinstance(data, list) and len(data) > 0:
                    if data[0].get('T') == 'success':
                        msg = data[0].get('msg', '')
                        if msg == 'authenticated':
                            logger.info("[STOCK] Authenticated! Subscribing...")
                            ws.send(self._get_stock_subscribe_message())
                        elif msg == 'subscribed':
                            logger.info(f"[STOCK] Subscribed to {StreamerConfig.STOCK_SYMBOLS}")
                    else:
                        self._handle_stock_message(data)

            def on_error(ws, error):
                logger.error(f"[STOCK] WebSocket error: {error}")

            def on_close(ws, close_status_code, close_msg):
                logger.warning(f"[STOCK] WebSocket closed: {close_status_code} {close_msg}")

            self.ws_stock = websocket.WebSocketApp(
                StreamerConfig.ALPACA_STOCK_WS,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )

            self.ws_stock.run_forever()

        except Exception as e:
            logger.error(f"[STOCK] Stream error: {e}")

    def run_heartbeat(self):
        """Run heartbeat thread."""
        while self.running:
            time.sleep(StreamerConfig.HEARTBEAT_INTERVAL)
            self.writer.emit_heartbeat()

    def start(self):
        """Start all streams."""
        self.running = True

        logger.info("=" * 60)
        logger.info("MARKET STREAMER V2 — STARTING")
        logger.info("=" * 60)
        logger.info(f"Crypto symbols: {StreamerConfig.CRYPTO_SYMBOLS}")
        logger.info(f"Stock symbols: {StreamerConfig.STOCK_SYMBOLS}")
        logger.info("=" * 60)

        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=self.run_heartbeat, daemon=True)
        heartbeat_thread.start()

        # Start crypto stream in separate thread
        crypto_thread = threading.Thread(target=self.run_crypto_stream, daemon=True)
        crypto_thread.start()

        # Run stock stream in main thread (or vice versa)
        self.run_stock_stream()

    def stop(self):
        """Stop all streams."""
        self.running = False
        if self.ws_crypto:
            self.ws_crypto.close()
        if self.ws_stock:
            self.ws_stock.close()
        self.writer.flush()  # Flush remaining events
        logger.info("Streamer stopped.")


# =============================================================================
# FALLBACK: REST API POLLING (if WebSocket unavailable)
# =============================================================================

class RESTPoller:
    """Fallback REST API polling if WebSocket fails."""

    def __init__(self, writer: EventQueueWriter):
        self.writer = writer
        self.writer.start_time = time.time()
        self.running = False

    def poll_alpaca(self):
        """Poll Alpaca REST API for latest prices."""
        try:
            import requests

            api_key = os.getenv('ALPACA_API_KEY')
            api_secret = os.getenv('ALPACA_SECRET')

            if not api_key or not api_secret:
                logger.error("Alpaca API keys not configured!")
                return

            headers = {
                'APCA-API-KEY-ID': api_key,
                'APCA-API-SECRET-KEY': api_secret
            }

            # Get crypto prices
            for symbol in StreamerConfig.CRYPTO_SYMBOLS:
                try:
                    symbol_api = symbol.replace('/', '')  # BTC/USD -> BTCUSD
                    url = f"https://data.alpaca.markets/v1beta3/crypto/us/latest/trades?symbols={symbol_api}"
                    resp = requests.get(url, headers=headers, timeout=10)

                    if resp.status_code == 200:
                        data = resp.json()
                        if 'trades' in data and symbol_api in data['trades']:
                            trade = data['trades'][symbol_api]
                            self.writer.add_price_event(
                                symbol=symbol,
                                price=float(trade.get('p', 0)),
                                volume=float(trade.get('s', 0)),
                                event_type='CRYPTO_TRADE_REST'
                            )
                            logger.debug(f"Polled {symbol}: {trade.get('p')}")
                except Exception as e:
                    logger.error(f"Failed to poll {symbol}: {e}")

            # Get stock prices (during market hours)
            try:
                symbols_str = ','.join(StreamerConfig.STOCK_SYMBOLS)
                url = f"https://data.alpaca.markets/v2/stocks/trades/latest?symbols={symbols_str}"
                resp = requests.get(url, headers=headers, timeout=10)

                if resp.status_code == 200:
                    data = resp.json()
                    if 'trades' in data:
                        for symbol, trade in data['trades'].items():
                            self.writer.add_price_event(
                                symbol=symbol,
                                price=float(trade.get('p', 0)),
                                volume=float(trade.get('s', 0)),
                                event_type='STOCK_TRADE_REST'
                            )
                            logger.debug(f"Polled {symbol}: {trade.get('p')}")
            except Exception as e:
                logger.error(f"Failed to poll stocks: {e}")

        except ImportError:
            logger.error("requests library not available for REST polling")

    def start(self, poll_interval: int = 10):
        """Start REST polling."""
        self.running = True
        logger.info("=" * 60)
        logger.info("MARKET STREAMER V2 — REST POLLING MODE")
        logger.info(f"Poll interval: {poll_interval} seconds")
        logger.info("=" * 60)

        while self.running:
            self.poll_alpaca()
            self.writer.emit_heartbeat()
            time.sleep(poll_interval)

    def stop(self):
        """Stop polling."""
        self.running = False
        self.writer.flush()


# =============================================================================
# MAIN
# =============================================================================

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='FHQ Market Streamer V2')
    parser.add_argument('--mode', choices=['websocket', 'rest', 'auto'], default='auto',
                       help='Stream mode: websocket, rest, or auto')
    parser.add_argument('--poll-interval', type=int, default=10,
                       help='REST polling interval in seconds')
    parser.add_argument('--test', action='store_true',
                       help='Run quick test and exit')

    args = parser.parse_args()

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create event writer
    writer = EventQueueWriter()

    if args.test:
        # Quick test mode
        logger.info("Running test mode...")
        poller = RESTPoller(writer)
        poller.poll_alpaca()
        writer.flush()
        logger.info("Test complete. Check database for events.")
        return

    # Determine mode
    mode = args.mode
    if mode == 'auto':
        try:
            import websocket
            mode = 'websocket'
            logger.info("WebSocket library available, using WebSocket mode")
        except ImportError:
            mode = 'rest'
            logger.info("WebSocket library not available, falling back to REST")

    if mode == 'websocket':
        streamer = AlpacaStreamer(writer)
        try:
            streamer.start()
        except KeyboardInterrupt:
            streamer.stop()
    else:
        poller = RESTPoller(writer)
        try:
            poller.start(poll_interval=args.poll_interval)
        except KeyboardInterrupt:
            poller.stop()


if __name__ == "__main__":
    main()
