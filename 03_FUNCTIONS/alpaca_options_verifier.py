#!/usr/bin/env python3
"""
ALPACA OPTIONS LEVEL 3 VERIFICATION
====================================
Directive: CEO-DIR-2026-120 P1.3
Classification: G4_EXECUTION_ENABLEMENT
Date: 2026-01-22

Verifies Alpaca Options Level 3 status and PUT contract availability
for the FjordHQ trading universe.

Components:
1. Account options_trading_level verification
2. PUT contract availability check for universe symbols
3. Strike granularity and expiration documentation
4. Evidence file generation

Authority: CEO, STIG, VEGA
Employment Contract: EC-003
"""

import os
import sys
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[OPTIONS-VERIFIER] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Alpaca SDK
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetOptionContractsRequest
    from alpaca.trading.enums import AssetClass, ContractType
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    logger.warning("Alpaca SDK not installed. Run: pip install alpaca-py")

# Database config
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Alpaca credentials
ALPACA_API_KEY = os.getenv('ALPACA_API_KEY', '')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET', os.getenv('ALPACA_SECRET_KEY', ''))

# FjordHQ Universe (27 symbols per plan)
UNIVERSE_SYMBOLS = [
    # US Equities - Large Cap Tech
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA',
    # US Equities - Diversified
    'JPM', 'V', 'JNJ', 'UNH', 'PG', 'XOM', 'HD',
    # ETFs
    'SPY', 'QQQ', 'IWM', 'GLD', 'TLT', 'XLF', 'XLE',
    # Volatility
    'VXX', 'UVXY',
    # Additional
    'AMD', 'COIN', 'PLTR', 'SOFI'
]


@dataclass
class OptionsVerificationResult:
    """Result of options verification for a single symbol."""
    symbol: str
    has_put_contracts: bool
    put_contract_count: int
    expiration_dates: List[str]
    strike_prices: List[float]
    strike_granularity: str  # e.g., "$1", "$2.50", "$5"
    nearest_expiry: Optional[str]
    farthest_expiry: Optional[str]
    min_strike: Optional[float]
    max_strike: Optional[float]
    verification_timestamp: str
    error: Optional[str] = None


@dataclass
class Level3VerificationReport:
    """Complete Options Level 3 verification report."""
    account_id: str
    options_trading_level: int
    options_approved_level: str  # Human readable
    options_buying_power: float
    total_symbols_checked: int
    symbols_with_puts: int
    symbols_without_puts: int
    symbol_results: Dict[str, Dict]
    verification_timestamp: str
    verification_hash: str
    evidence_path: str


class AlpacaOptionsVerifier:
    """
    Verifies Alpaca Options Level 3 status and PUT contract availability.

    CEO-DIR-2026-120 P1.3: Confirms options readiness for hedging operations.
    """

    def __init__(self):
        self.conn = None
        self.trading_client = None
        self._verification_results: Dict[str, OptionsVerificationResult] = {}

    def connect(self):
        """Connect to database and Alpaca."""
        # Database
        self.conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Connected to database")

        # Alpaca Trading Client
        if ALPACA_AVAILABLE and ALPACA_API_KEY:
            self.trading_client = TradingClient(
                api_key=ALPACA_API_KEY,
                secret_key=ALPACA_SECRET_KEY,
                paper=True
            )
            logger.info("Connected to Alpaca Paper Trading")
        else:
            raise RuntimeError("Alpaca SDK or credentials not available")

    def close(self):
        """Close connections."""
        if self.conn:
            self.conn.close()

    def verify_account_options_level(self) -> Tuple[int, str, float]:
        """
        Verify account options trading level.

        Returns: (options_level, level_description, options_buying_power)
        """
        account = self.trading_client.get_account()

        # Check options trading level
        # Level 0: No options
        # Level 1: Covered calls, cash-secured puts
        # Level 2: Long calls/puts
        # Level 3: Spreads, straddles, strangles
        # Level 4: Naked calls (margin)

        options_level = getattr(account, 'options_trading_level', None)
        options_buying_power = float(getattr(account, 'options_buying_power', 0) or 0)

        level_descriptions = {
            0: "NO_OPTIONS",
            1: "COVERED_ONLY",
            2: "LONG_OPTIONS",
            3: "SPREADS_ENABLED",
            4: "NAKED_CALLS"
        }

        level_int = int(options_level) if options_level is not None else 0
        level_desc = level_descriptions.get(level_int, f"UNKNOWN_{options_level}")

        logger.info(
            f"Account options level: {level_int} ({level_desc}), "
            f"buying power: ${options_buying_power:,.2f}"
        )

        return level_int, level_desc, options_buying_power

    def verify_put_availability(self, symbol: str) -> OptionsVerificationResult:
        """
        Verify PUT contract availability for a symbol.

        Checks:
        - PUT contracts exist
        - Available expirations
        - Strike price granularity
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        try:
            # Get option contracts for this symbol
            request = GetOptionContractsRequest(
                underlying_symbols=[symbol],
                type=ContractType.PUT,
                expiration_date_gte=datetime.now().date(),
                expiration_date_lte=(datetime.now() + timedelta(days=90)).date()
            )

            contracts = self.trading_client.get_option_contracts(request)

            if not contracts or len(contracts.option_contracts) == 0:
                logger.warning(f"No PUT contracts found for {symbol}")
                return OptionsVerificationResult(
                    symbol=symbol,
                    has_put_contracts=False,
                    put_contract_count=0,
                    expiration_dates=[],
                    strike_prices=[],
                    strike_granularity="N/A",
                    nearest_expiry=None,
                    farthest_expiry=None,
                    min_strike=None,
                    max_strike=None,
                    verification_timestamp=timestamp,
                    error="No PUT contracts available"
                )

            # Extract contract details
            expirations = set()
            strikes = set()

            for contract in contracts.option_contracts:
                expirations.add(str(contract.expiration_date))
                strikes.add(float(contract.strike_price))

            sorted_expirations = sorted(list(expirations))
            sorted_strikes = sorted(list(strikes))

            # Calculate strike granularity
            granularity = self._calculate_strike_granularity(sorted_strikes)

            result = OptionsVerificationResult(
                symbol=symbol,
                has_put_contracts=True,
                put_contract_count=len(contracts.option_contracts),
                expiration_dates=sorted_expirations,
                strike_prices=sorted_strikes,
                strike_granularity=granularity,
                nearest_expiry=sorted_expirations[0] if sorted_expirations else None,
                farthest_expiry=sorted_expirations[-1] if sorted_expirations else None,
                min_strike=sorted_strikes[0] if sorted_strikes else None,
                max_strike=sorted_strikes[-1] if sorted_strikes else None,
                verification_timestamp=timestamp
            )

            logger.info(
                f"PUT verification for {symbol}: {len(contracts.option_contracts)} contracts, "
                f"{len(sorted_expirations)} expirations, "
                f"strikes ${sorted_strikes[0]:.2f}-${sorted_strikes[-1]:.2f}"
            )

            return result

        except Exception as e:
            logger.error(f"Error verifying PUTs for {symbol}: {e}")
            return OptionsVerificationResult(
                symbol=symbol,
                has_put_contracts=False,
                put_contract_count=0,
                expiration_dates=[],
                strike_prices=[],
                strike_granularity="N/A",
                nearest_expiry=None,
                farthest_expiry=None,
                min_strike=None,
                max_strike=None,
                verification_timestamp=timestamp,
                error=str(e)
            )

    def _calculate_strike_granularity(self, strikes: List[float]) -> str:
        """Calculate typical strike price granularity."""
        if len(strikes) < 2:
            return "N/A"

        diffs = [strikes[i+1] - strikes[i] for i in range(len(strikes)-1)]
        common_diff = min(diffs) if diffs else 0

        if common_diff <= 0.5:
            return "$0.50"
        elif common_diff <= 1.0:
            return "$1.00"
        elif common_diff <= 2.5:
            return "$2.50"
        elif common_diff <= 5.0:
            return "$5.00"
        else:
            return f"${common_diff:.2f}"

    def run_full_verification(
        self,
        symbols: Optional[List[str]] = None
    ) -> Level3VerificationReport:
        """
        Run complete Options Level 3 verification.

        Returns comprehensive report with evidence for VEGA attestation.
        """
        symbols = symbols or UNIVERSE_SYMBOLS
        timestamp = datetime.now(timezone.utc).isoformat()

        logger.info(f"Starting Options Level 3 verification for {len(symbols)} symbols")

        # Step 1: Verify account level
        options_level, level_desc, buying_power = self.verify_account_options_level()
        account = self.trading_client.get_account()

        # Step 2: Verify PUT availability for each symbol
        symbol_results = {}
        symbols_with_puts = 0

        for symbol in symbols:
            result = self.verify_put_availability(symbol)
            symbol_results[symbol] = asdict(result)
            self._verification_results[symbol] = result

            if result.has_put_contracts:
                symbols_with_puts += 1

        # Step 3: Generate verification hash
        verification_data = {
            'timestamp': timestamp,
            'account_id': str(account.id),
            'options_level': options_level,
            'symbols_checked': len(symbols),
            'symbols_with_puts': symbols_with_puts
        }
        verification_hash = hashlib.sha256(
            json.dumps(verification_data, sort_keys=True).encode()
        ).hexdigest()

        # Step 4: Create evidence file path
        evidence_path = f"03_FUNCTIONS/evidence/CEO_DIR_2026_120_OPTIONS_LEVEL3_VERIFICATION.json"

        # Build report
        report = Level3VerificationReport(
            account_id=str(account.id),
            options_trading_level=options_level,
            options_approved_level=level_desc,
            options_buying_power=buying_power,
            total_symbols_checked=len(symbols),
            symbols_with_puts=symbols_with_puts,
            symbols_without_puts=len(symbols) - symbols_with_puts,
            symbol_results=symbol_results,
            verification_timestamp=timestamp,
            verification_hash=verification_hash,
            evidence_path=evidence_path
        )

        # Step 5: Log to database
        self._log_verification_to_database(report)

        logger.info(
            f"Verification complete: Level {options_level} ({level_desc}), "
            f"{symbols_with_puts}/{len(symbols)} symbols have PUT contracts"
        )

        return report

    def _log_verification_to_database(self, report: Level3VerificationReport):
        """Log verification results to database."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.options_verification_log (
                        account_id,
                        options_trading_level,
                        options_approved_level,
                        options_buying_power,
                        total_symbols_checked,
                        symbols_with_puts,
                        symbols_without_puts,
                        verification_hash,
                        evidence_path,
                        created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    report.account_id,
                    report.options_trading_level,
                    report.options_approved_level,
                    report.options_buying_power,
                    report.total_symbols_checked,
                    report.symbols_with_puts,
                    report.symbols_without_puts,
                    report.verification_hash,
                    report.evidence_path
                ))
                self.conn.commit()
                logger.info("Verification logged to database")
        except Exception as e:
            logger.warning(f"Failed to log verification to database: {e}")
            try:
                self.conn.rollback()
            except:
                pass

    def generate_evidence_file(self, report: Level3VerificationReport) -> str:
        """Generate VEGA-attestable evidence file."""
        evidence = {
            "directive": "CEO-DIR-2026-120",
            "phase": "P1.3",
            "title": "Alpaca Options Level 3 Verification",
            "classification": "G4_EXECUTION_ENABLEMENT",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": "EC-003 (STIG)",
            "account": {
                "account_id": report.account_id,
                "options_trading_level": report.options_trading_level,
                "options_approved_level": report.options_approved_level,
                "options_buying_power": report.options_buying_power
            },
            "verification_summary": {
                "total_symbols": report.total_symbols_checked,
                "symbols_with_puts": report.symbols_with_puts,
                "symbols_without_puts": report.symbols_without_puts,
                "put_coverage_pct": round(
                    report.symbols_with_puts / report.total_symbols_checked * 100, 2
                ) if report.total_symbols_checked > 0 else 0
            },
            "level_3_confirmed": report.options_trading_level >= 3,
            "hedging_ready": (
                report.options_trading_level >= 3 and
                report.symbols_with_puts >= report.total_symbols_checked * 0.9
            ),
            "symbol_details": report.symbol_results,
            "verification_hash": report.verification_hash,
            "vega_attestation_required": True,
            "attestation_status": "PENDING"
        }

        evidence_path = os.path.join(
            os.path.dirname(__file__),
            "evidence",
            "CEO_DIR_2026_120_OPTIONS_LEVEL3_VERIFICATION.json"
        )

        with open(evidence_path, 'w') as f:
            json.dump(evidence, f, indent=2, default=str)

        logger.info(f"Evidence file generated: {evidence_path}")
        return evidence_path


def main():
    """CLI entry point for options verification."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Alpaca Options Level 3 Verifier (CEO-DIR-2026-120 P1.3)'
    )
    parser.add_argument('--verify', action='store_true', help='Run full verification')
    parser.add_argument('--symbol', help='Verify single symbol')
    parser.add_argument('--generate-evidence', action='store_true', help='Generate evidence file')

    args = parser.parse_args()

    verifier = AlpacaOptionsVerifier()
    verifier.connect()

    try:
        if args.symbol:
            result = verifier.verify_put_availability(args.symbol)
            print(json.dumps(asdict(result), indent=2, default=str))
        elif args.verify:
            report = verifier.run_full_verification()

            print(f"\n{'='*60}")
            print("ALPACA OPTIONS LEVEL 3 VERIFICATION REPORT")
            print(f"{'='*60}")
            print(f"Account ID: {report.account_id}")
            print(f"Options Level: {report.options_trading_level} ({report.options_approved_level})")
            print(f"Options Buying Power: ${report.options_buying_power:,.2f}")
            print(f"\nSymbols Checked: {report.total_symbols_checked}")
            print(f"With PUT Contracts: {report.symbols_with_puts}")
            print(f"Without PUT Contracts: {report.symbols_without_puts}")
            print(f"\nVerification Hash: {report.verification_hash[:16]}...")

            if args.generate_evidence:
                evidence_path = verifier.generate_evidence_file(report)
                print(f"\nEvidence File: {evidence_path}")
        else:
            # Default: show account level
            level, desc, bp = verifier.verify_account_options_level()
            print(f"Options Level: {level} ({desc})")
            print(f"Buying Power: ${bp:,.2f}")
    finally:
        verifier.close()


if __name__ == '__main__':
    main()
