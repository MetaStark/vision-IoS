#!/usr/bin/env python3
"""
NEWS SENTIMENT SCHEDULER DAEMON
===============================
Directive: CEO-DIR-2026-META-ANALYSIS Phase 3
Classification: G2_DATA_PIPELINE
Date: 2026-01-23

Automated sentiment analysis for tracked symbols using Serper API + DeepSeek-R1.
Provides the 6th signal source for IoS-013 (Perspective System).

Schedule: Every 4 hours (cron: 0 */4 * * *)
Data Flow: Serper News Search -> LLM Sentiment Analysis -> fhq_research.sentiment_timeseries

Authority: CEO, STIG (Technical)
Employment Contract: EC-003
"""

import os
import sys
import json
import hashlib
import logging
import argparse
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import re

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment
load_dotenv('C:/fhq-market-system/vision-ios/.env')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('NewsSentimentDaemon')

# Database config
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Daemon configuration
DAEMON_NAME = 'NEWS_SENTIMENT_DAEMON'
CHECK_INTERVAL_SECONDS = 4 * 60 * 60  # 4 hours
SYMBOLS_PER_BATCH = 10  # Process 10 symbols per cycle
MAX_NEWS_AGE_HOURS = 24  # Only consider news from last 24 hours


class NewsSentimentDaemon:
    """
    Daemon for automated news sentiment analysis.

    Uses Serper API to fetch recent news for tracked symbols,
    analyzes sentiment using DeepSeek-R1 or heuristic fallback,
    and stores results in fhq_research.sentiment_timeseries.
    """

    def __init__(self):
        self.conn = None
        self.serper_wrapper = None
        self._run_id = None

    def connect(self):
        """Connect to database."""
        self.conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Database connection established")

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def _get_serper_wrapper(self):
        """Lazy load Serper wrapper."""
        if self.serper_wrapper is None:
            from serper_mbb_wrapper import SerperMBBWrapper
            self.serper_wrapper = SerperMBBWrapper()
        return self.serper_wrapper

    def register_heartbeat(self):
        """Register daemon heartbeat."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_ops.daemon_heartbeats (daemon_name, last_heartbeat, health_score, metadata)
                    VALUES (%s, NOW(), 1.0, %s)
                    ON CONFLICT (daemon_name) DO UPDATE SET
                        last_heartbeat = NOW(),
                        health_score = 1.0,
                        metadata = EXCLUDED.metadata
                """, (DAEMON_NAME, json.dumps({
                    'version': '1.0.0',
                    'directive': 'CEO-DIR-2026-META-ANALYSIS',
                    'phase': 'Phase 3'
                })))
                self.conn.commit()
        except Exception as e:
            logger.warning(f"Failed to register heartbeat: {e}")

    def get_tracked_symbols(self) -> List[Dict]:
        """
        Get symbols to analyze from various sources.

        Sources:
        1. Active positions (fhq_capital.positions)
        2. Watchlist symbols (fhq_research.watchlist)
        3. Golden Needle symbols (fhq_canonical.golden_needles)

        Returns:
            List of dicts with symbol, asset_class
        """
        symbols = []

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get active position symbols
            cur.execute("""
                SELECT DISTINCT symbol,
                       CASE WHEN symbol ~ '^[A-Z]{3}(USD|EUR|GBP)$' THEN 'FOREX'
                            WHEN symbol IN ('BTC', 'ETH', 'SOL', 'ADA', 'DOT', 'AVAX', 'LINK', 'MATIC') THEN 'CRYPTO'
                            WHEN symbol IN ('GLD', 'SLV', 'USO', 'UNG') THEN 'COMMODITY'
                            ELSE 'EQUITY' END as asset_class
                FROM fhq_capital.positions
                WHERE status = 'OPEN'
                ORDER BY symbol
            """)
            for row in cur.fetchall():
                symbols.append({'symbol': row['symbol'], 'asset_class': row['asset_class']})

            # Get golden needle symbols
            cur.execute("""
                SELECT DISTINCT symbol,
                       COALESCE(asset_class, 'EQUITY') as asset_class
                FROM fhq_canonical.golden_needles
                WHERE status = 'ACTIVE'
                  AND symbol NOT IN (SELECT DISTINCT symbol FROM fhq_capital.positions WHERE status = 'OPEN')
                ORDER BY symbol
            """)
            for row in cur.fetchall():
                symbols.append({'symbol': row['symbol'], 'asset_class': row['asset_class']})

        logger.info(f"Found {len(symbols)} symbols to analyze")
        return symbols

    def needs_refresh(self, symbol: str) -> bool:
        """
        Check if symbol needs sentiment refresh.

        Returns True if no recent sentiment data (< 4 hours old)
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT MAX(analyzed_at)
                FROM fhq_research.sentiment_timeseries
                WHERE symbol = %s
            """, (symbol,))
            last_analysis = cur.fetchone()[0]

            if last_analysis is None:
                return True

            # Check if older than 4 hours
            age_seconds = (datetime.now(timezone.utc) - last_analysis.replace(tzinfo=timezone.utc)).total_seconds()
            return age_seconds > CHECK_INTERVAL_SECONDS

    def fetch_news_for_symbol(self, symbol: str, asset_class: str) -> List[Dict]:
        """
        Fetch recent news for a symbol using Serper API.

        Args:
            symbol: Stock/crypto symbol
            asset_class: EQUITY, CRYPTO, FOREX, COMMODITY

        Returns:
            List of news items with title, snippet, url, source
        """
        serper = self._get_serper_wrapper()

        # Construct search query based on asset class
        if asset_class == 'CRYPTO':
            query = f"{symbol} cryptocurrency price news today"
        elif asset_class == 'FOREX':
            base = symbol[:3]
            quote = symbol[3:]
            query = f"{base}/{quote} forex exchange rate news today"
        elif asset_class == 'COMMODITY':
            commodity_names = {
                'GLD': 'gold',
                'SLV': 'silver',
                'USO': 'oil crude',
                'UNG': 'natural gas'
            }
            name = commodity_names.get(symbol, symbol)
            query = f"{name} commodity price news today"
        else:
            # Equity - search company stock news
            query = f"{symbol} stock news today"

        try:
            result = serper.search_mbb(query, num_results=10, use_llm_synthesis=False)
            evidence = result.get('supporting_evidence', [])

            logger.info(f"Fetched {len(evidence)} news items for {symbol}")
            return evidence

        except Exception as e:
            logger.error(f"Failed to fetch news for {symbol}: {e}")
            return []

    def analyze_sentiment(self, symbol: str, news_items: List[Dict]) -> Dict:
        """
        Analyze sentiment from news items.

        Uses DeepSeek-R1 for LLM analysis if available,
        falls back to keyword-based heuristic.

        Args:
            symbol: Asset symbol
            news_items: List of news items from Serper

        Returns:
            Dict with sentiment_score, sentiment_label, confidence, etc.
        """
        if not news_items:
            return {
                'sentiment_score': 0.0,
                'sentiment_label': 'NEUTRAL',
                'sentiment_confidence': 0.0,
                'source_count': 0,
                'bullish_count': 0,
                'bearish_count': 0,
                'neutral_count': 0,
                'headline_sample': None,
                'keywords': [],
                'primary_source': 'NONE'
            }

        # Try LLM sentiment analysis first
        try:
            return self._analyze_sentiment_llm(symbol, news_items)
        except Exception as e:
            logger.warning(f"LLM sentiment failed for {symbol}: {e}, using heuristic")
            return self._analyze_sentiment_heuristic(symbol, news_items)

    def _analyze_sentiment_llm(self, symbol: str, news_items: List[Dict]) -> Dict:
        """
        Use DeepSeek-R1 for sentiment analysis.

        Prompt: Analyze headlines and return sentiment score [-1, 1]
        """
        import openai

        deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
        if not deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY not available")

        # Prepare news context
        news_context = "\n".join([
            f"- [{item.get('credibility', 'LOW')}] {item.get('title', '')}"
            for item in news_items[:10]
        ])

        prompt = f"""Analyze the sentiment of these news headlines for {symbol}:

{news_context}

Return ONLY a JSON object (no markdown, no explanation):
{{
    "sentiment_score": <float from -1.0 (very bearish) to 1.0 (very bullish)>,
    "sentiment_label": <"VERY_BEARISH" | "BEARISH" | "NEUTRAL" | "BULLISH" | "VERY_BULLISH">,
    "confidence": <float from 0.0 to 1.0>,
    "bullish_count": <int>,
    "bearish_count": <int>,
    "neutral_count": <int>,
    "key_theme": <string summarizing dominant theme>
}}

Scoring Guide:
- VERY_BEARISH: score < -0.6 (severe negative news, crashes, scandals)
- BEARISH: score -0.6 to -0.2 (negative outlook, downgrades, concerns)
- NEUTRAL: score -0.2 to 0.2 (mixed or factual reporting)
- BULLISH: score 0.2 to 0.6 (positive outlook, upgrades, growth)
- VERY_BULLISH: score > 0.6 (exceptional news, breakthroughs, beats)
"""

        client = openai.OpenAI(
            api_key=deepseek_api_key,
            base_url="https://api.deepseek.com/v1"
        )

        start_time = time.time()

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a financial sentiment analyst. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=300
        )

        duration_ms = int((time.time() - start_time) * 1000)

        content = response.choices[0].message.content.strip()

        # Extract JSON if wrapped in code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        result = json.loads(content)

        return {
            'sentiment_score': float(result.get('sentiment_score', 0)),
            'sentiment_label': result.get('sentiment_label', 'NEUTRAL'),
            'sentiment_confidence': float(result.get('confidence', 0.5)),
            'source_count': len(news_items),
            'bullish_count': int(result.get('bullish_count', 0)),
            'bearish_count': int(result.get('bearish_count', 0)),
            'neutral_count': int(result.get('neutral_count', 0)),
            'headline_sample': news_items[0].get('title') if news_items else None,
            'keywords': [result.get('key_theme', '')] if result.get('key_theme') else [],
            'primary_source': 'SERPER',
            'model_used': 'DEEPSEEK_CHAT',
            'analysis_duration_ms': duration_ms
        }

    def _analyze_sentiment_heuristic(self, symbol: str, news_items: List[Dict]) -> Dict:
        """
        Keyword-based sentiment analysis fallback.

        No LLM cost, but less accurate.
        """
        # Sentiment keywords
        bullish_words = {
            'surge', 'soar', 'jump', 'rally', 'gain', 'rise', 'up', 'high', 'record',
            'beat', 'exceed', 'outperform', 'upgrade', 'buy', 'bullish', 'growth',
            'positive', 'strong', 'boost', 'advance', 'climb', 'breakthrough'
        }

        bearish_words = {
            'fall', 'drop', 'plunge', 'crash', 'decline', 'down', 'low', 'miss',
            'cut', 'downgrade', 'sell', 'bearish', 'weak', 'concern', 'risk',
            'negative', 'loss', 'slump', 'tumble', 'warning', 'trouble'
        }

        bullish_count = 0
        bearish_count = 0
        neutral_count = 0

        for item in news_items:
            text = (item.get('title', '') + ' ' + item.get('snippet', '')).lower()

            bullish_hits = sum(1 for word in bullish_words if word in text)
            bearish_hits = sum(1 for word in bearish_words if word in text)

            if bullish_hits > bearish_hits:
                bullish_count += 1
            elif bearish_hits > bullish_hits:
                bearish_count += 1
            else:
                neutral_count += 1

        total = len(news_items)
        if total == 0:
            sentiment_score = 0.0
        else:
            sentiment_score = (bullish_count - bearish_count) / total

        # Determine label
        if sentiment_score > 0.6:
            sentiment_label = 'VERY_BULLISH'
        elif sentiment_score > 0.2:
            sentiment_label = 'BULLISH'
        elif sentiment_score < -0.6:
            sentiment_label = 'VERY_BEARISH'
        elif sentiment_score < -0.2:
            sentiment_label = 'BEARISH'
        else:
            sentiment_label = 'NEUTRAL'

        # Confidence based on sample size
        confidence = min(0.3 + (total * 0.07), 0.8)

        return {
            'sentiment_score': round(sentiment_score, 4),
            'sentiment_label': sentiment_label,
            'sentiment_confidence': round(confidence, 4),
            'source_count': total,
            'bullish_count': bullish_count,
            'bearish_count': bearish_count,
            'neutral_count': neutral_count,
            'headline_sample': news_items[0].get('title') if news_items else None,
            'keywords': [],
            'primary_source': 'SERPER',
            'model_used': 'HEURISTIC',
            'analysis_duration_ms': 0
        }

    def store_sentiment(self, symbol: str, asset_class: str, sentiment: Dict, news_items: List[Dict]) -> str:
        """
        Store sentiment analysis results in database.

        Args:
            symbol: Asset symbol
            asset_class: EQUITY, CRYPTO, etc.
            sentiment: Sentiment analysis result dict
            news_items: Raw news items for source tracking

        Returns:
            sentiment_id (UUID) of inserted record
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_research.sentiment_timeseries (
                    symbol, asset_class, sentiment_score, sentiment_label,
                    sentiment_confidence, source_count, bullish_count, bearish_count,
                    neutral_count, primary_source, sources, headline_sample, keywords,
                    analyzed_at, model_used, analysis_duration_ms, created_by
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    NOW(), %s, %s, %s
                )
                RETURNING sentiment_id
            """, (
                symbol,
                asset_class,
                sentiment['sentiment_score'],
                sentiment['sentiment_label'],
                sentiment['sentiment_confidence'],
                sentiment['source_count'],
                sentiment['bullish_count'],
                sentiment['bearish_count'],
                sentiment['neutral_count'],
                sentiment['primary_source'],
                json.dumps([{'title': n.get('title'), 'url': n.get('url'), 'credibility': n.get('credibility')} for n in news_items[:5]]),
                sentiment['headline_sample'],
                json.dumps(sentiment['keywords']),
                sentiment.get('model_used', 'HEURISTIC'),
                sentiment.get('analysis_duration_ms', 0),
                DAEMON_NAME
            ))

            sentiment_id = cur.fetchone()[0]
            self.conn.commit()

            logger.info(f"Stored sentiment for {symbol}: {sentiment['sentiment_label']} ({sentiment['sentiment_score']:.3f})")
            return str(sentiment_id)

    def process_batch(self, symbols: List[Dict], max_symbols: int = None) -> Dict:
        """
        Process a batch of symbols for sentiment analysis.

        Args:
            symbols: List of symbol dicts
            max_symbols: Max symbols to process (default: all)

        Returns:
            Dict with processing results
        """
        if max_symbols:
            symbols = symbols[:max_symbols]

        results = {
            'processed': 0,
            'skipped': 0,
            'failed': 0,
            'symbols': []
        }

        for sym_info in symbols:
            symbol = sym_info['symbol']
            asset_class = sym_info['asset_class']

            try:
                # Check if needs refresh
                if not self.needs_refresh(symbol):
                    results['skipped'] += 1
                    continue

                # Fetch news
                news_items = self.fetch_news_for_symbol(symbol, asset_class)

                # Analyze sentiment
                sentiment = self.analyze_sentiment(symbol, news_items)

                # Store results
                sentiment_id = self.store_sentiment(symbol, asset_class, sentiment, news_items)

                results['processed'] += 1
                results['symbols'].append({
                    'symbol': symbol,
                    'sentiment_id': sentiment_id,
                    'label': sentiment['sentiment_label'],
                    'score': sentiment['sentiment_score']
                })

                # Rate limiting - 1 second between API calls
                time.sleep(1)

            except Exception as e:
                logger.error(f"Failed to process {symbol}: {e}")
                results['failed'] += 1

        return results

    def run_once(self, max_symbols: int = None):
        """
        Execute a single sentiment analysis cycle.

        Args:
            max_symbols: Max symbols to process (default: all)
        """
        self.connect()

        try:
            self.register_heartbeat()

            # Get symbols to analyze
            symbols = self.get_tracked_symbols()

            if not symbols:
                logger.info("No symbols to analyze")
                return

            # Process batch
            results = self.process_batch(symbols, max_symbols)

            logger.info(f"Batch complete: {results['processed']} processed, {results['skipped']} skipped, {results['failed']} failed")

            # Generate evidence
            self._generate_evidence(results)

        finally:
            self.close()

    def run_daemon(self):
        """
        Run as continuous daemon with 4-hour intervals.
        """
        logger.info("=" * 60)
        logger.info("News Sentiment Scheduler Daemon Starting")
        logger.info(f"Check interval: {CHECK_INTERVAL_SECONDS} seconds")
        logger.info("=" * 60)

        while True:
            try:
                self.run_once(max_symbols=SYMBOLS_PER_BATCH)

            except Exception as e:
                logger.error(f"Daemon cycle failed: {e}")

            logger.info(f"Sleeping for {CHECK_INTERVAL_SECONDS} seconds...")
            time.sleep(CHECK_INTERVAL_SECONDS)

    def _generate_evidence(self, results: Dict):
        """Generate evidence file for the run."""
        evidence = {
            'directive': 'CEO-DIR-2026-META-ANALYSIS',
            'phase': 'Phase 3',
            'title': 'News Sentiment Analysis Cycle',
            'daemon': DAEMON_NAME,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'results': {
                'processed': results['processed'],
                'skipped': results['skipped'],
                'failed': results['failed'],
                'symbols_analyzed': [s['symbol'] for s in results.get('symbols', [])]
            }
        }

        evidence_hash = hashlib.sha256(
            json.dumps(evidence, sort_keys=True).encode()
        ).hexdigest()[:16]

        filename = f"evidence/SENTIMENT_ANALYSIS_{evidence_hash}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(os.path.dirname(__file__), filename)

        try:
            with open(filepath, 'w') as f:
                json.dump(evidence, f, indent=2)
            logger.info(f"Evidence file: {filepath}")
        except Exception as e:
            logger.warning(f"Failed to write evidence file: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='News Sentiment Scheduler Daemon (CEO-DIR-2026-META-ANALYSIS Phase 3)'
    )
    parser.add_argument('--run', action='store_true', help='Run single sentiment cycle')
    parser.add_argument('--daemon', action='store_true', help='Run as continuous daemon')
    parser.add_argument('--max-symbols', type=int, default=None, help='Max symbols to process')
    parser.add_argument('--symbol', type=str, help='Analyze specific symbol')
    parser.add_argument('--status', action='store_true', help='Show daemon status')

    args = parser.parse_args()

    daemon = NewsSentimentDaemon()

    if args.status:
        daemon.connect()

        with daemon.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check daemon heartbeat
            cur.execute("""
                SELECT daemon_name, last_heartbeat, health_score
                FROM fhq_ops.daemon_heartbeats
                WHERE daemon_name = %s
            """, (DAEMON_NAME,))
            heartbeat = cur.fetchone()

            # Check sentiment data
            cur.execute("""
                SELECT COUNT(*),
                       COUNT(DISTINCT symbol),
                       MAX(analyzed_at),
                       AVG(sentiment_score) as avg_sentiment
                FROM fhq_research.sentiment_timeseries
                WHERE analyzed_at >= NOW() - INTERVAL '24 hours'
            """)
            stats = cur.fetchone()

        daemon.close()

        print(f"\n{'='*60}")
        print("NEWS SENTIMENT DAEMON STATUS")
        print(f"{'='*60}")

        if heartbeat:
            print(f"Daemon:       {heartbeat['daemon_name']}")
            print(f"Last Beat:    {heartbeat['last_heartbeat']}")
            print(f"Health:       {heartbeat['health_score']}")
        else:
            print("Daemon:       NOT REGISTERED")

        print(f"\nLast 24h Stats:")
        print(f"  Analyses:   {stats['count'] or 0}")
        print(f"  Symbols:    {stats['count_1'] or 0}")
        print(f"  Last Run:   {stats['max'] or 'Never'}")
        print(f"  Avg Score:  {float(stats['avg_sentiment'] or 0):.3f}")
        print(f"{'='*60}\n")

    elif args.symbol:
        daemon.connect()

        try:
            news_items = daemon.fetch_news_for_symbol(args.symbol, 'EQUITY')
            sentiment = daemon.analyze_sentiment(args.symbol, news_items)

            print(f"\n{'='*60}")
            print(f"SENTIMENT ANALYSIS: {args.symbol}")
            print(f"{'='*60}")
            print(f"Score:      {sentiment['sentiment_score']:.4f}")
            print(f"Label:      {sentiment['sentiment_label']}")
            print(f"Confidence: {sentiment['sentiment_confidence']:.4f}")
            print(f"Sources:    {sentiment['source_count']}")
            print(f"Bullish:    {sentiment['bullish_count']}")
            print(f"Bearish:    {sentiment['bearish_count']}")
            print(f"Neutral:    {sentiment['neutral_count']}")
            print(f"Model:      {sentiment.get('model_used', 'N/A')}")
            if sentiment['headline_sample']:
                print(f"Headline:   {sentiment['headline_sample'][:80]}...")
            print(f"{'='*60}\n")

        finally:
            daemon.close()

    elif args.daemon:
        daemon.run_daemon()

    elif args.run:
        daemon.run_once(max_symbols=args.max_symbols)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
