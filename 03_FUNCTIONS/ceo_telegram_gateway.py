"""
CEO Telegram Gateway - CEO Glass Window Interface
CEO-DIR-2026-01-03: Cognitive Digital Intuition Platform

Authority: ADR-019 (Human Interaction Charter)
Mode: READ-ONLY (Dumb Glass Principle)
Security: Chat ID whitelist + rate limiting + court-proof logging

This module extends the existing telegram_notifier.py with bidirectional
command handling for CEO observability queries.
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from uuid import uuid4
from dataclasses import dataclass, field
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from dotenv import load_dotenv

# Load .env from project root (before reading env vars)
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
load_dotenv(_env_path)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CEO_GATEWAY")

# =============================================================================
# CONFIGURATION
# =============================================================================

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CEO_CHAT_ID = os.getenv('CEO_TELEGRAM_CHAT_ID', '6194473125')

# Database connection
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Rate limits (per ADR-012)
DEFAULT_RATE_LIMIT_PER_MINUTE = 10
DEFAULT_RATE_LIMIT_PER_HOUR = 100


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class AuthResult:
    """Result of authentication check."""
    authenticated: bool
    chat_id: str
    display_name: Optional[str] = None
    role: Optional[str] = None
    rejection_reason: Optional[str] = None


@dataclass
class RateLimitResult:
    """Result of rate limit check."""
    allowed: bool
    remaining_minute: int = 0
    remaining_hour: int = 0
    retry_after_seconds: Optional[int] = None
    rejection_reason: Optional[str] = None


@dataclass
class CommandResult:
    """Result of command execution."""
    success: bool
    content: str
    evidence_id: Optional[str] = None
    query_result_hash: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# CEO TELEGRAM GATEWAY
# =============================================================================

class CEOTelegramGateway:
    """
    Bidirectional Telegram gateway for CEO observability.

    Implements:
    - Authentication via chat ID whitelist
    - Rate limiting per ADR-012
    - Command routing to read-only views
    - Court-proof evidence attachment
    - MBB-style response formatting
    """

    VALID_COMMANDS = [
        # Phase A: Current State Commands
        '/status', '/agents', '/agent', '/regime', '/needles',
        '/balance', '/aci', '/ledger', '/help',
        # Phase B: Temporal Context Commands (CEO-DIR-2026-01-03-PHASE-B)
        '/when_defcon', '/when_regime', '/when_confidence',
        '/when_blocked', '/history_needles'
    ]

    def __init__(self, db_connection=None):
        """Initialize gateway with database connection."""
        self.conn = db_connection or self._get_connection()
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.telegram_api_url = f"https://api.telegram.org/bot{self.bot_token}"

    def _get_connection(self):
        """Get database connection."""
        return psycopg2.connect(**DB_CONFIG)

    # =========================================================================
    # AUTHENTICATION
    # =========================================================================

    def authenticate(self, chat_id: str) -> AuthResult:
        """
        Authenticate chat ID against whitelist.

        Args:
            chat_id: Telegram chat ID

        Returns:
            AuthResult with authentication status
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT display_name, role, access_level, is_active
                    FROM fhq_governance.ceo_access_whitelist
                    WHERE telegram_chat_id = %s
                """, (str(chat_id),))
                result = cur.fetchone()

            if result is None:
                return AuthResult(
                    authenticated=False,
                    chat_id=str(chat_id),
                    rejection_reason='CHAT_ID_NOT_WHITELISTED'
                )

            if not result['is_active']:
                return AuthResult(
                    authenticated=False,
                    chat_id=str(chat_id),
                    rejection_reason='ACCOUNT_DEACTIVATED'
                )

            return AuthResult(
                authenticated=True,
                chat_id=str(chat_id),
                display_name=result['display_name'],
                role=result['role']
            )

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return AuthResult(
                authenticated=False,
                chat_id=str(chat_id),
                rejection_reason=f'AUTH_ERROR: {str(e)}'
            )

    # =========================================================================
    # RATE LIMITING
    # =========================================================================

    def check_rate_limit(self, chat_id: str) -> RateLimitResult:
        """
        Check and update rate limits for chat ID.

        Args:
            chat_id: Telegram chat ID

        Returns:
            RateLimitResult with rate limit status
        """
        try:
            now = datetime.now(timezone.utc)

            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get current state
                cur.execute("""
                    SELECT * FROM fhq_governance.ceo_rate_limit_state
                    WHERE chat_id = %s
                    FOR UPDATE
                """, (str(chat_id),))
                state = cur.fetchone()

                if state is None:
                    # First request - initialize
                    cur.execute("""
                        INSERT INTO fhq_governance.ceo_rate_limit_state
                        (chat_id, requests_this_minute, requests_this_hour,
                         minute_window_start, hour_window_start, last_request_at,
                         total_requests_lifetime)
                        VALUES (%s, 1, 1, %s, %s, %s, 1)
                    """, (str(chat_id), now, now, now))
                    self.conn.commit()
                    return RateLimitResult(
                        allowed=True,
                        remaining_minute=DEFAULT_RATE_LIMIT_PER_MINUTE - 1,
                        remaining_hour=DEFAULT_RATE_LIMIT_PER_HOUR - 1
                    )

                # Calculate window resets
                minute_reqs = state['requests_this_minute']
                hour_reqs = state['requests_this_hour']
                minute_start = state['minute_window_start']
                hour_start = state['hour_window_start']

                # Reset minute window if needed
                if minute_start is None or (now - minute_start) > timedelta(minutes=1):
                    minute_reqs = 0
                    minute_start = now

                # Reset hour window if needed
                if hour_start is None or (now - hour_start) > timedelta(hours=1):
                    hour_reqs = 0
                    hour_start = now

                # Check limits
                if minute_reqs >= DEFAULT_RATE_LIMIT_PER_MINUTE:
                    retry_after = 60 - int((now - minute_start).total_seconds())
                    cur.execute("""
                        UPDATE fhq_governance.ceo_rate_limit_state
                        SET total_rejections_lifetime = total_rejections_lifetime + 1
                        WHERE chat_id = %s
                    """, (str(chat_id),))
                    self.conn.commit()
                    return RateLimitResult(
                        allowed=False,
                        remaining_minute=0,
                        remaining_hour=DEFAULT_RATE_LIMIT_PER_HOUR - hour_reqs,
                        retry_after_seconds=max(retry_after, 1),
                        rejection_reason='MINUTE_LIMIT_EXCEEDED'
                    )

                if hour_reqs >= DEFAULT_RATE_LIMIT_PER_HOUR:
                    retry_after = 3600 - int((now - hour_start).total_seconds())
                    cur.execute("""
                        UPDATE fhq_governance.ceo_rate_limit_state
                        SET total_rejections_lifetime = total_rejections_lifetime + 1
                        WHERE chat_id = %s
                    """, (str(chat_id),))
                    self.conn.commit()
                    return RateLimitResult(
                        allowed=False,
                        remaining_minute=DEFAULT_RATE_LIMIT_PER_MINUTE - minute_reqs,
                        remaining_hour=0,
                        retry_after_seconds=max(retry_after, 1),
                        rejection_reason='HOUR_LIMIT_EXCEEDED'
                    )

                # Update counters
                cur.execute("""
                    UPDATE fhq_governance.ceo_rate_limit_state
                    SET requests_this_minute = %s,
                        requests_this_hour = %s,
                        minute_window_start = %s,
                        hour_window_start = %s,
                        last_request_at = %s,
                        total_requests_lifetime = total_requests_lifetime + 1
                    WHERE chat_id = %s
                """, (minute_reqs + 1, hour_reqs + 1, minute_start, hour_start, now, str(chat_id)))
                self.conn.commit()

                return RateLimitResult(
                    allowed=True,
                    remaining_minute=DEFAULT_RATE_LIMIT_PER_MINUTE - minute_reqs - 1,
                    remaining_hour=DEFAULT_RATE_LIMIT_PER_HOUR - hour_reqs - 1
                )

        except Exception as e:
            logger.error(f"Rate limit error: {e}")
            # Fail open on errors to avoid blocking CEO
            return RateLimitResult(allowed=True, remaining_minute=10, remaining_hour=100)

    # =========================================================================
    # COMMAND PARSING
    # =========================================================================

    def parse_command(self, text: str) -> Tuple[Optional[str], List[str]]:
        """
        Parse command and arguments from message text.

        Args:
            text: Message text

        Returns:
            Tuple of (command, args)
        """
        if not text or not text.startswith('/'):
            return None, []

        parts = text.strip().split()
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        return command, args

    # =========================================================================
    # COMMAND EXECUTION
    # =========================================================================

    def execute_command(self, command: str, args: List[str], chat_id: str) -> CommandResult:
        """
        Execute a CEO command and return formatted result.

        Args:
            command: The command (e.g., '/status')
            args: Command arguments
            chat_id: Requesting chat ID

        Returns:
            CommandResult with response content
        """
        try:
            # Get command registry entry
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT command_name, view_source, is_enabled
                    FROM fhq_governance.ceo_command_registry
                    WHERE command_name = %s
                """, (command,))
                cmd_entry = cur.fetchone()

            if cmd_entry is None:
                return CommandResult(
                    success=False,
                    content=f"Unknown command: {command}\nUse /help for available commands.",
                    error='UNKNOWN_COMMAND'
                )

            if not cmd_entry['is_enabled']:
                return CommandResult(
                    success=False,
                    content=f"Command {command} is currently disabled.",
                    error='COMMAND_DISABLED'
                )

            # Route to handler
            handler = self._get_handler(command)
            return handler(args, cmd_entry['view_source'])

        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return CommandResult(
                success=False,
                content=f"Error executing command: {str(e)}",
                error=str(e)
            )

    def _get_handler(self, command: str):
        """Get the handler function for a command."""
        handlers = {
            # Phase A: Current State Commands
            '/status': self._handle_status,
            '/agents': self._handle_agents,
            '/agent': self._handle_agent,
            '/regime': self._handle_regime,
            '/needles': self._handle_needles,
            '/balance': self._handle_balance,
            '/aci': self._handle_aci,
            '/ledger': self._handle_ledger,
            '/help': self._handle_help,
            # Phase B: Temporal Context Commands (CEO-DIR-2026-01-03-PHASE-B)
            '/when_defcon': self._handle_when_defcon,
            '/when_regime': self._handle_when_regime,
            '/when_confidence': self._handle_when_confidence,
            '/when_blocked': self._handle_when_blocked,
            '/history_needles': self._handle_history_needles,
        }
        return handlers.get(command, self._handle_unknown)

    # =========================================================================
    # COMMAND HANDLERS
    # =========================================================================

    def _handle_status(self, args: List[str], view_source: str) -> CommandResult:
        """Handle /status command."""
        query = """
            SELECT
                COALESCE(
                    (SELECT current_level FROM fhq_monitoring.defcon_status
                     ORDER BY activated_at DESC LIMIT 1),
                    'GREEN'
                ) AS defcon_level,
                COALESCE(
                    (SELECT regime_label FROM fhq_finn.v_btc_regime_current LIMIT 1),
                    'UNKNOWN'
                ) AS current_regime,
                COALESCE(
                    (SELECT regime_confidence FROM fhq_finn.v_btc_regime_current LIMIT 1),
                    0.0
                )::NUMERIC(5,2) AS regime_confidence,
                COALESCE(
                    (SELECT COUNT(*) FROM fhq_canonical.golden_needles WHERE is_current = TRUE),
                    0
                ) AS active_needles
        """

        result, query_hash = self._execute_query(query)

        if not result:
            return CommandResult(
                success=True,
                content=self._format_status_empty(),
                query_result_hash=query_hash
            )

        row = result[0]
        content = self._format_status(row)
        evidence_id = self._log_evidence(query, result, content)

        return CommandResult(
            success=True,
            content=content,
            evidence_id=evidence_id,
            query_result_hash=query_hash
        )

    def _handle_agents(self, args: List[str], view_source: str) -> CommandResult:
        """Handle /agents command."""
        query = """
            SELECT agent_id, total_actions, approved_count, last_action
            FROM fhq_governance.mv_aol_agent_metrics
            ORDER BY agent_id
            LIMIT 10
        """

        result, query_hash = self._execute_query(query)
        content = self._format_agents(result)
        evidence_id = self._log_evidence(query, result, content)

        return CommandResult(
            success=True,
            content=content,
            evidence_id=evidence_id,
            query_result_hash=query_hash
        )

    def _handle_agent(self, args: List[str], view_source: str) -> CommandResult:
        """Handle /agent [ID] command."""
        if not args:
            return CommandResult(
                success=False,
                content="Usage: /agent [AGENT_ID]\nExample: /agent FINN",
                error='MISSING_ARGUMENT'
            )

        agent_id = args[0].upper()
        query = f"""
            SELECT *
            FROM fhq_governance.mv_aol_agent_metrics
            WHERE agent_id = '{agent_id}'
        """

        result, query_hash = self._execute_query(query)

        if not result:
            content = f"Agent '{agent_id}' not found."
        else:
            content = self._format_agent_detail(result[0])

        evidence_id = self._log_evidence(query, result, content)

        return CommandResult(
            success=True,
            content=content,
            evidence_id=evidence_id,
            query_result_hash=query_hash
        )

    def _handle_regime(self, args: List[str], view_source: str) -> CommandResult:
        """Handle /regime command."""
        query = """
            SELECT listing_id, regime_date, regime_label, regime_confidence,
                   regime_prob_0, regime_prob_1, regime_prob_2
            FROM fhq_finn.v_btc_regime_current
            LIMIT 1
        """

        result, query_hash = self._execute_query(query)
        content = self._format_regime(result)
        evidence_id = self._log_evidence(query, result, content)

        return CommandResult(
            success=True,
            content=content,
            evidence_id=evidence_id,
            query_result_hash=query_hash
        )

    def _handle_needles(self, args: List[str], view_source: str) -> CommandResult:
        """Handle /needles command."""
        limit = int(args[0]) if args and args[0].isdigit() else 5
        limit = min(limit, 10)  # Max 10

        query = f"""
            SELECT needle_id, target_asset, hypothesis_category, eqs_score,
                   hypothesis_title, created_at
            FROM fhq_canonical.golden_needles
            WHERE is_current = TRUE
            ORDER BY created_at DESC
            LIMIT {limit}
        """

        result, query_hash = self._execute_query(query)
        content = self._format_needles(result)
        evidence_id = self._log_evidence(query, result, content)

        return CommandResult(
            success=True,
            content=content,
            evidence_id=evidence_id,
            query_result_hash=query_hash
        )

    def _handle_balance(self, args: List[str], view_source: str) -> CommandResult:
        """Handle /balance command."""
        query = """
            SELECT provider_name, usage_date, requests_made, daily_limit, usage_percent
            FROM fhq_governance.api_budget_log
            WHERE provider_name = 'deepseek'
            ORDER BY usage_date DESC
            LIMIT 1
        """

        result, query_hash = self._execute_query(query)
        content = self._format_balance(result)
        evidence_id = self._log_evidence(query, result, content)

        return CommandResult(
            success=True,
            content=content,
            evidence_id=evidence_id,
            query_result_hash=query_hash
        )

    def _handle_aci(self, args: List[str], view_source: str) -> CommandResult:
        """Handle /aci command."""
        # Query ACI triangle shadow metrics
        query = """
            SELECT
                'SitC' AS controller,
                COALESCE(AVG(chain_integrity_score) * 100, 100.0) AS avg_score
            FROM fhq_cognition.search_in_chain_events
            WHERE created_at > NOW() - INTERVAL '24 hours'
            UNION ALL
            SELECT
                'InForage' AS controller,
                COALESCE(100 - (SELECT usage_percent FROM fhq_governance.api_budget_log
                               WHERE provider_name = 'deepseek'
                               ORDER BY usage_date DESC LIMIT 1), 100.0) AS avg_score
            UNION ALL
            SELECT
                'IKEA' AS controller,
                100.0 AS avg_score
        """

        result, query_hash = self._execute_query(query)
        content = self._format_aci(result)
        evidence_id = self._log_evidence(query, result, content)

        return CommandResult(
            success=True,
            content=content,
            evidence_id=evidence_id,
            query_result_hash=query_hash
        )

    def _handle_ledger(self, args: List[str], view_source: str) -> CommandResult:
        """Handle /ledger command."""
        limit = int(args[0]) if args and args[0].isdigit() else 5
        limit = min(limit, 10)

        query = f"""
            SELECT action_type, action_target, decision, initiated_by, initiated_at
            FROM fhq_governance.governance_actions_log
            ORDER BY initiated_at DESC
            LIMIT {limit}
        """

        result, query_hash = self._execute_query(query)
        content = self._format_ledger(result)
        evidence_id = self._log_evidence(query, result, content)

        return CommandResult(
            success=True,
            content=content,
            evidence_id=evidence_id,
            query_result_hash=query_hash
        )

    def _handle_help(self, args: List[str], view_source: str) -> CommandResult:
        """Handle /help command."""
        content = """CEO GLASS WINDOW - Command Reference

PHASE A: CURRENT STATE
  /status   - DEFCON, regime, needles summary
  /regime   - Current BTC regime classification
  /agents   - All agent metrics overview
  /agent ID - Single agent detail
  /needles [N] - Active golden needles
  /aci      - ACI triangle shadow metrics
  /ledger [N] - Recent governance actions
  /balance  - LLM provider budget status

PHASE B: TEMPORAL CONTEXT
  /when_defcon      - Last DEFCON transitions
  /when_regime      - Recent regime transitions
  /when_confidence [X] - High confidence moments
  /when_blocked     - Recent governance blocks
  /history_needles [N] - Needle counts by day

HELP:
  /help     - This command reference

MODE: READ-ONLY | ADR-019 Compliant
PHASE B: Historical reflection ONLY (no advice)
All queries are logged with court-proof evidence."""

        return CommandResult(success=True, content=content)

    def _handle_unknown(self, args: List[str], view_source: str) -> CommandResult:
        """Handle unknown command."""
        return CommandResult(
            success=False,
            content="Unknown command. Use /help for available commands.",
            error='UNKNOWN_COMMAND'
        )

    # =========================================================================
    # PHASE B: TEMPORAL CONTEXT HANDLERS (CEO-DIR-2026-01-03-PHASE-B)
    # =========================================================================
    # COGNITIVE INTUITION CONTRACT: Historical reflection ONLY.
    # No trends, no advice, no forward-looking summaries.
    # Every response must end with silence (no recommendations).

    def _handle_when_defcon(self, args: List[str], view_source: str) -> CommandResult:
        """
        Handle /when_defcon command.
        Shows: What did the system look like the last time DEFCON changed?
        """
        query = """
            SELECT
                from_level,
                to_level,
                reason,
                authorized_by,
                transition_timestamp,
                (SELECT COUNT(*) FROM fhq_canonical.golden_needles gn
                 WHERE gn.created_at <= dt.transition_timestamp
                   AND gn.is_current = TRUE) AS needles_at_transition
            FROM fhq_governance.defcon_transitions dt
            ORDER BY transition_timestamp DESC
            LIMIT 5
        """

        result, query_hash = self._execute_query(query)
        content = self._format_when_defcon(result)
        evidence_id = self._log_evidence(query, result, content)

        return CommandResult(
            success=True,
            content=content,
            evidence_id=evidence_id,
            query_result_hash=query_hash
        )

    def _handle_when_regime(self, args: List[str], view_source: str) -> CommandResult:
        """
        Handle /when_regime command.
        Shows: What was the system state during prior regime transitions?
        """
        query = """
            WITH regime_changes AS (
                SELECT
                    gn.created_at AS observation_time,
                    gn.regime_sovereign AS regime_at_time,
                    gn.regime_confidence,
                    gn.defcon_level,
                    LAG(gn.regime_sovereign) OVER (ORDER BY gn.created_at) AS prev_regime
                FROM fhq_canonical.golden_needles gn
                WHERE gn.regime_sovereign IS NOT NULL
            )
            SELECT
                observation_time,
                prev_regime,
                regime_at_time AS new_regime,
                regime_confidence,
                defcon_level
            FROM regime_changes
            WHERE prev_regime IS NOT NULL
              AND prev_regime != regime_at_time
            ORDER BY observation_time DESC
            LIMIT 10
        """

        result, query_hash = self._execute_query(query)
        content = self._format_when_regime(result)
        evidence_id = self._log_evidence(query, result, content)

        return CommandResult(
            success=True,
            content=content,
            evidence_id=evidence_id,
            query_result_hash=query_hash
        )

    def _handle_when_confidence(self, args: List[str], view_source: str) -> CommandResult:
        """
        Handle /when_confidence [threshold] command.
        Shows: State when regime confidence exceeded threshold.
        """
        threshold = float(args[0]) if args and args[0].replace('.', '').isdigit() else 0.90
        threshold = min(max(threshold, 0.5), 0.99)  # Clamp to reasonable range

        query = f"""
            SELECT
                created_at AS observation_time,
                regime_sovereign AS regime,
                regime_confidence,
                defcon_level,
                target_asset,
                hypothesis_category,
                eqs_score
            FROM fhq_canonical.golden_needles
            WHERE regime_confidence >= {threshold}
            ORDER BY created_at DESC
            LIMIT 10
        """

        result, query_hash = self._execute_query(query)
        content = self._format_when_confidence(result, threshold)
        evidence_id = self._log_evidence(query, result, content)

        return CommandResult(
            success=True,
            content=content,
            evidence_id=evidence_id,
            query_result_hash=query_hash
        )

    def _handle_when_blocked(self, args: List[str], view_source: str) -> CommandResult:
        """
        Handle /when_blocked command.
        Shows: Context around recent governance blocks.
        """
        query = """
            SELECT
                action_type,
                action_target,
                decision_rationale,
                initiated_at,
                initiated_by,
                (SELECT COUNT(*)
                 FROM fhq_governance.governance_actions_log gal2
                 WHERE gal2.decision = 'BLOCKED'
                   AND gal2.initiated_at BETWEEN gal.initiated_at - INTERVAL '1 hour'
                                              AND gal.initiated_at) AS blocks_in_prior_hour
            FROM fhq_governance.governance_actions_log gal
            WHERE gal.decision = 'BLOCKED'
            ORDER BY gal.initiated_at DESC
            LIMIT 10
        """

        result, query_hash = self._execute_query(query)
        content = self._format_when_blocked(result)
        evidence_id = self._log_evidence(query, result, content)

        return CommandResult(
            success=True,
            content=content,
            evidence_id=evidence_id,
            query_result_hash=query_hash
        )

    def _handle_history_needles(self, args: List[str], view_source: str) -> CommandResult:
        """
        Handle /history_needles [days] command.
        Shows: Historical needle counts by day.
        """
        days = int(args[0]) if args and args[0].isdigit() else 7
        days = min(days, 30)  # Max 30 days

        query = f"""
            SELECT
                DATE(created_at) AS date,
                COUNT(*) AS total_needles,
                COUNT(*) FILTER (WHERE is_current = TRUE) AS current_needles,
                COUNT(*) FILTER (WHERE hypothesis_category LIKE '%MEAN_REVERSION%') AS mean_reversion,
                COUNT(*) FILTER (WHERE hypothesis_category LIKE '%CATALYST%') AS catalyst,
                MODE() WITHIN GROUP (ORDER BY regime_sovereign) AS dominant_regime,
                AVG(regime_confidence)::NUMERIC(5,4) AS avg_confidence
            FROM fhq_canonical.golden_needles
            WHERE created_at >= NOW() - INTERVAL '{days} days'
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at) DESC
        """

        result, query_hash = self._execute_query(query)
        content = self._format_history_needles(result, days)
        evidence_id = self._log_evidence(query, result, content)

        return CommandResult(
            success=True,
            content=content,
            evidence_id=evidence_id,
            query_result_hash=query_hash
        )

    # =========================================================================
    # FORMATTING
    # =========================================================================

    def _format_status(self, row: Dict) -> str:
        """Format /status response."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        defcon = row.get('defcon_level', 'UNKNOWN')
        regime = row.get('current_regime', 'UNKNOWN')
        confidence = float(row.get('regime_confidence', 0))
        needles = row.get('active_needles', 0)

        defcon_emoji = {'GREEN': 'GREEN', 'YELLOW': 'YELLOW', 'ORANGE': 'ORANGE', 'RED': 'RED', 'BLACK': 'BLACK'}.get(defcon, 'UNKNOWN')

        return f"""SYSTEM STATUS | {timestamp}

DEFCON: {defcon_emoji} {defcon}
Regime: {regime} (conf: {confidence:.2f})

Active Needles: {needles}

--
ADR-019: READ-ONLY | Court-Proof"""

    def _format_status_empty(self) -> str:
        """Format empty status response."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return f"""SYSTEM STATUS | {timestamp}

DEFCON: GREEN (default)
Regime: UNKNOWN

No active data available.

--
ADR-019: READ-ONLY"""

    def _format_agents(self, result: List[Dict]) -> str:
        """Format /agents response."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        if not result:
            return f"AGENTS | {timestamp}\n\nNo agent metrics available."

        lines = [f"AGENTS | {timestamp}\n"]
        for row in result:
            agent_id = row.get('agent_id', 'UNKNOWN')
            total = row.get('total_actions', 0)
            approved = row.get('approved_count', 0)
            last = str(row.get('last_action', '--'))[:16]

            lines.append(f"  {agent_id}: Actions={total}, Approved={approved}")
            lines.append(f"    Last: {last}")

        lines.append("\n--\nADR-019: READ-ONLY")
        return '\n'.join(lines)

    def _format_agent_detail(self, row: Dict) -> str:
        """Format /agent detail response."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        agent_id = row.get('agent_id', 'UNKNOWN')

        return f"""AGENT: {agent_id} | {timestamp}

ARS: {row.get('ars_score', '--')}
CSI: {row.get('csi_score', '--')}
GII: {row.get('gii_state', '--')}
DDS: {row.get('dds_score', '--')}

Last Activity: {str(row.get('last_activity', '--'))[:19]}

--
ADR-019: READ-ONLY"""

    def _format_regime(self, result: List[Dict]) -> str:
        """Format /regime response."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        if not result:
            return f"REGIME | {timestamp}\n\nNo regime data available."

        row = result[0]
        regime = row.get('regime_label', 'UNKNOWN')
        confidence = float(row.get('regime_confidence', 0))
        prob_0 = float(row.get('regime_prob_0', 0))
        prob_1 = float(row.get('regime_prob_1', 0))
        prob_2 = float(row.get('regime_prob_2', 0))

        return f"""BTC REGIME | {timestamp}

Current: {regime}
Confidence: {confidence:.2%}

Probabilities:
  State 0: {prob_0:.2%}
  State 1: {prob_1:.2%}
  State 2: {prob_2:.2%}

--
ADR-019: READ-ONLY"""

    def _format_needles(self, result: List[Dict]) -> str:
        """Format /needles response."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        if not result:
            return f"GOLDEN NEEDLES | {timestamp}\n\nNo active needles."

        lines = [f"GOLDEN NEEDLES ({len(result)}) | {timestamp}\n"]
        for row in result:
            asset = row.get('target_asset', '--')
            category = row.get('hypothesis_category', '--')
            eqs = float(row.get('eqs_score', 0) or 0)
            title = (row.get('hypothesis_title', '--') or '--')[:30]

            lines.append(f"  {asset}: {category} (EQS: {eqs:.2f})")
            lines.append(f"    {title}...")

        lines.append("\n--\nADR-019: READ-ONLY")
        return '\n'.join(lines)

    def _format_balance(self, result: List[Dict]) -> str:
        """Format /balance response."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        if not result:
            return f"LLM BALANCE | {timestamp}\n\nNo budget data available."

        row = result[0]
        used = row.get('requests_made', 0)
        limit = row.get('daily_limit', 0)
        pct = float(row.get('usage_percent', 0))

        return f"""LLM BALANCE | {timestamp}

Provider: DeepSeek
Used: {used} / {limit} ({pct:.1f}%)
Remaining: {limit - used}

--
ADR-019: READ-ONLY"""

    def _format_aci(self, result: List[Dict]) -> str:
        """Format /aci response."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        lines = [f"ACI TRIANGLE | {timestamp}\n"]

        for row in result:
            controller = row.get('controller', '--')
            score = float(row.get('avg_score', 0))
            emoji = 'GREEN' if score >= 80 else ('YELLOW' if score >= 50 else 'RED')
            lines.append(f"  {controller}: {score:.1f}% {emoji}")

        lines.append("\n--\nADR-019: READ-ONLY")
        return '\n'.join(lines)

    def _format_ledger(self, result: List[Dict]) -> str:
        """Format /ledger response."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        if not result:
            return f"GOVERNANCE LEDGER | {timestamp}\n\nNo recent actions."

        lines = [f"GOVERNANCE LEDGER | {timestamp}\n"]
        for row in result:
            action = row.get('action_type', '--')
            target = row.get('action_target', '--')
            decision = row.get('decision', '--')
            initiated = str(row.get('initiated_at', '--'))[:16]

            lines.append(f"  [{initiated}] {action}: {target} = {decision}")

        lines.append("\n--\nADR-019: READ-ONLY")
        return '\n'.join(lines)

    # =========================================================================
    # PHASE B: TEMPORAL FORMATTING (CEO-DIR-2026-01-03-PHASE-B)
    # =========================================================================
    # COGNITIVE INTUITION CONTRACT: End with silence (no recommendations).

    def _format_when_defcon(self, result: List[Dict]) -> str:
        """
        Format /when_defcon response.
        Shows historical DEFCON transitions. No interpretation.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        if not result:
            return f"""DEFCON HISTORY | {timestamp}

No DEFCON transitions recorded.

--
ADR-019: READ-ONLY | Historical Reflection"""

        lines = [f"DEFCON TRANSITIONS | {timestamp}\n"]
        lines.append("What was:\n")

        for row in result:
            from_lvl = row.get('from_level', '--')
            to_lvl = row.get('to_level', '--')
            reason = (row.get('reason', '--') or '--')[:60]
            trans_time = str(row.get('transition_timestamp', '--'))[:16]
            needles = row.get('needles_at_transition', 0)

            lines.append(f"  [{trans_time}]")
            lines.append(f"    {from_lvl} -> {to_lvl}")
            lines.append(f"    Needles: {needles}")
            lines.append(f"    Reason: {reason}...")
            lines.append("")

        lines.append("--")
        lines.append("ADR-019: READ-ONLY | Historical Reflection")
        return '\n'.join(lines)

    def _format_when_regime(self, result: List[Dict]) -> str:
        """
        Format /when_regime response.
        Shows historical regime transitions. No interpretation.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        if not result:
            return f"""REGIME TRANSITIONS | {timestamp}

No regime transitions recorded.

--
ADR-019: READ-ONLY | Historical Reflection"""

        lines = [f"REGIME TRANSITIONS | {timestamp}\n"]
        lines.append("What was:\n")

        for row in result:
            obs_time = str(row.get('observation_time', '--'))[:16]
            prev = row.get('prev_regime', '--')
            new = row.get('new_regime', '--')
            conf = float(row.get('regime_confidence', 0) or 0)
            defcon = row.get('defcon_level', '--')

            lines.append(f"  [{obs_time}]")
            lines.append(f"    {prev} -> {new} (conf: {conf:.2%})")
            lines.append(f"    DEFCON: {defcon}")
            lines.append("")

        lines.append("--")
        lines.append("ADR-019: READ-ONLY | Historical Reflection")
        return '\n'.join(lines)

    def _format_when_confidence(self, result: List[Dict], threshold: float) -> str:
        """
        Format /when_confidence response.
        Shows moments when confidence exceeded threshold. No interpretation.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        if not result:
            return f"""HIGH CONFIDENCE MOMENTS | {timestamp}

No observations with confidence >= {threshold:.0%}.

--
ADR-019: READ-ONLY | Historical Reflection"""

        lines = [f"CONFIDENCE >= {threshold:.0%} | {timestamp}\n"]
        lines.append("What was:\n")

        for row in result:
            obs_time = str(row.get('observation_time', '--'))[:16]
            regime = row.get('regime', '--')
            conf = float(row.get('regime_confidence', 0) or 0)
            asset = row.get('target_asset', '--')
            category = row.get('hypothesis_category', '--')
            eqs = float(row.get('eqs_score', 0) or 0)

            lines.append(f"  [{obs_time}]")
            lines.append(f"    Regime: {regime} ({conf:.2%})")
            lines.append(f"    {asset}: {category} (EQS: {eqs:.2f})")
            lines.append("")

        lines.append("--")
        lines.append("ADR-019: READ-ONLY | Historical Reflection")
        return '\n'.join(lines)

    def _format_when_blocked(self, result: List[Dict]) -> str:
        """
        Format /when_blocked response.
        Shows governance blocks with context. No interpretation.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        if not result:
            return f"""GOVERNANCE BLOCKS | {timestamp}

No governance blocks recorded.

--
ADR-019: READ-ONLY | Historical Reflection"""

        lines = [f"GOVERNANCE BLOCKS | {timestamp}\n"]
        lines.append("What was:\n")

        for row in result:
            action = row.get('action_type', '--')
            target = row.get('action_target', '--')
            rationale = (row.get('decision_rationale', '--') or '--')[:50]
            init_time = str(row.get('initiated_at', '--'))[:16]
            blocks_prior = row.get('blocks_in_prior_hour', 0)

            lines.append(f"  [{init_time}]")
            lines.append(f"    {action}: {target}")
            lines.append(f"    Reason: {rationale}...")
            lines.append(f"    Blocks in prior hour: {blocks_prior}")
            lines.append("")

        lines.append("--")
        lines.append("ADR-019: READ-ONLY | Historical Reflection")
        return '\n'.join(lines)

    def _format_history_needles(self, result: List[Dict], days: int) -> str:
        """
        Format /history_needles response.
        Shows daily needle counts. No trends, no interpretation.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        if not result:
            return f"""NEEDLE HISTORY ({days}d) | {timestamp}

No needles in the past {days} days.

--
ADR-019: READ-ONLY | Historical Reflection"""

        lines = [f"NEEDLE HISTORY ({days}d) | {timestamp}\n"]
        lines.append("What was:\n")
        lines.append("  Date       | Total | Current | Regime      | Conf")
        lines.append("  " + "-" * 50)

        for row in result:
            date = str(row.get('date', '--'))[:10]
            total = row.get('total_needles', 0)
            current = row.get('current_needles', 0)
            regime = (row.get('dominant_regime', '--') or '--')[:10]
            conf = float(row.get('avg_confidence', 0) or 0)

            lines.append(f"  {date} | {total:5} | {current:7} | {regime:11} | {conf:.2%}")

        lines.append("")
        lines.append("--")
        lines.append("ADR-019: READ-ONLY | Historical Reflection")
        return '\n'.join(lines)

    # =========================================================================
    # QUERY EXECUTION
    # =========================================================================

    def _execute_query(self, query: str) -> Tuple[List[Dict], str]:
        """Execute query and return results with hash."""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                result = cur.fetchall()
            self.conn.commit()  # Commit to clear transaction state

            # Compute hash
            result_str = json.dumps([dict(r) for r in result], default=str, sort_keys=True)
            query_hash = hashlib.sha256(result_str.encode()).hexdigest()

            return result, query_hash

        except Exception as e:
            logger.error(f"Query error: {e}")
            try:
                self.conn.rollback()  # Rollback on error to clear transaction
            except:
                pass
            return [], hashlib.sha256(str(e).encode()).hexdigest()

    # =========================================================================
    # LOGGING
    # =========================================================================

    def _log_evidence(self, query: str, result: List[Dict], content: str) -> str:
        """Log query evidence and return evidence ID."""
        evidence_id = str(uuid4())

        try:
            result_str = json.dumps([dict(r) for r in result], default=str, sort_keys=True)
            query_hash = hashlib.sha256(result_str.encode()).hexdigest()
            response_hash = hashlib.sha256(content.encode()).hexdigest()

            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.ceo_access_log
                    (access_id, chat_id, command, query_executed, query_result_hash,
                     response_sent, response_hash, auth_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    evidence_id,
                    CEO_CHAT_ID,
                    'QUERY',
                    query,
                    query_hash,
                    content[:500],  # Truncate for storage
                    response_hash,
                    'AUTHENTICATED'
                ))
            self.conn.commit()

        except Exception as e:
            logger.error(f"Evidence logging error: {e}")

        return evidence_id

    def log_access(self, chat_id: str, command: str, auth_status: str,
                   rejection_reason: Optional[str] = None) -> None:
        """Log access attempt."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.ceo_access_log
                    (access_id, chat_id, command, auth_status, auth_rejection_reason,
                     access_timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    str(uuid4()),
                    str(chat_id),
                    command,
                    auth_status,
                    rejection_reason,
                    datetime.now(timezone.utc)
                ))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Access logging error: {e}")

    # =========================================================================
    # TELEGRAM API
    # =========================================================================

    def send_message(self, chat_id: str, text: str) -> bool:
        """Send message to Telegram chat."""
        if not self.bot_token:
            logger.error("No bot token configured")
            return False

        try:
            url = f"{self.telegram_api_url}/sendMessage"
            # Plain text mode (no Markdown) to avoid parsing errors
            data = {
                'chat_id': chat_id,
                'text': text
            }
            response = requests.post(url, json=data, timeout=10)
            return response.status_code == 200

        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False

    def get_updates(self, offset: int = 0) -> List[Dict]:
        """Get updates from Telegram."""
        if not self.bot_token:
            return []

        try:
            url = f"{self.telegram_api_url}/getUpdates"
            params = {'offset': offset, 'timeout': 30}
            response = requests.get(url, params=params, timeout=35)

            if response.status_code == 200:
                data = response.json()
                return data.get('result', [])

        except Exception as e:
            logger.error(f"Telegram getUpdates error: {e}")

        return []

    # =========================================================================
    # MESSAGE HANDLING
    # =========================================================================

    def handle_message(self, update: Dict) -> None:
        """Handle incoming Telegram message."""
        message = update.get('message', {})
        chat_id = str(message.get('chat', {}).get('id', ''))
        text = message.get('text', '')

        if not chat_id or not text:
            return

        # Parse command
        command, args = self.parse_command(text)
        if not command:
            return

        # Authenticate
        auth_result = self.authenticate(chat_id)
        if not auth_result.authenticated:
            self.log_access(chat_id, command, 'REJECTED', auth_result.rejection_reason)
            logger.warning(f"Rejected access from {chat_id}: {auth_result.rejection_reason}")
            return

        # Rate limit
        rate_result = self.check_rate_limit(chat_id)
        if not rate_result.allowed:
            self.log_access(chat_id, command, 'RATE_LIMITED', rate_result.rejection_reason)
            self.send_message(
                chat_id,
                f"Rate limit exceeded. Retry in {rate_result.retry_after_seconds}s."
            )
            return

        # Execute command
        result = self.execute_command(command, args, chat_id)

        # Send response
        self.send_message(chat_id, result.content)

        # Log success
        logger.info(f"Executed {command} for {auth_result.display_name}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Test the gateway."""
    gateway = CEOTelegramGateway()

    # Test /status
    result = gateway.execute_command('/status', [], CEO_CHAT_ID)
    print("=== /status ===")
    print(result.content)
    print(f"Evidence ID: {result.evidence_id}")
    print(f"Query Hash: {result.query_result_hash}")
    print()

    # Test /help
    result = gateway.execute_command('/help', [], CEO_CHAT_ID)
    print("=== /help ===")
    print(result.content)


if __name__ == '__main__':
    main()
