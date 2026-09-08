"""
FjordHQ Telegram Notifier
CEO-DIR-2026-FINN-019: Real-time alerts for critical trading events

Top 5 Notifications:
1. Position Exit (TP/SL) - URGENT
2. Exposure Gate Clear (<25%) - URGENT
3. Trade Executed - HIGH
4. Neural Bridge Block - HIGH
5. Daemon Error/Crash - CRITICAL
"""

import os
import json
import logging
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8019173608:AAH37ApVjUaNXM_EotUS735bj4qqbUTi1Ik')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '6194473125')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


class AlertPriority(Enum):
    """Alert priority levels with emoji indicators."""
    CRITICAL = ("CRITICAL", "🔴")
    URGENT = ("URGENT", "🚨")
    HIGH = ("HIGH", "🟠")
    MEDIUM = ("MEDIUM", "🟡")
    INFO = ("INFO", "🔵")


class FjordHQNotifier:
    """
    Telegram notifier for FjordHQ Market System.

    Sends real-time alerts for critical trading events.
    """

    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        self.enabled = bool(self.bot_token and self.chat_id)

        if not self.enabled:
            logger.warning("Telegram notifier disabled - missing credentials")

    def _send(self, message: str, parse_mode: str = "Markdown") -> bool:
        """Send message to Telegram."""
        if not self.enabled:
            logger.warning(f"Telegram disabled, would send: {message[:100]}...")
            return False

        try:
            response = requests.post(
                self.api_url,
                json={
                    'chat_id': self.chat_id,
                    'text': message,
                    'parse_mode': parse_mode
                },
                timeout=10
            )

            if response.ok:
                logger.info(f"Telegram alert sent successfully")
                return True
            else:
                logger.error(f"Telegram send failed: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Telegram send exception: {e}")
            return False

    def _format_header(self, title: str, priority: AlertPriority) -> str:
        """Format alert header."""
        emoji = priority.value[1]
        priority_name = priority.value[0]
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return f"{emoji} *{title}*\n_{priority_name} | {timestamp}_\n"

    # =========================================================================
    # TOP 5 NOTIFICATION METHODS
    # =========================================================================

    def position_exit(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        pnl_pct: float,
        pnl_usd: float,
        exit_reason: str,
        new_exposure_pct: float
    ) -> bool:
        """
        #1: Position Exit (TP/SL hit)
        Priority: URGENT
        """
        win_loss = "WIN" if pnl_pct > 0 else "LOSS"
        emoji_result = "✅" if pnl_pct > 0 else "❌"

        message = self._format_header("POSITION EXIT", AlertPriority.URGENT)
        message += f"""
{emoji_result} *{win_loss}* | {symbol} {direction}

📊 *Trade Result:*
• Entry: ${entry_price:,.2f}
• Exit: ${exit_price:,.2f}
• P&L: {pnl_pct:+.2f}% (${pnl_usd:+,.2f})
• Reason: {exit_reason}

📈 *Portfolio:*
• New Exposure: {new_exposure_pct:.1f}%
• Gate Status: {"✅ CLEAR" if new_exposure_pct < 25 else "🚫 BLOCKED"}

{"🔓 *Neural Bridge can now activate!*" if new_exposure_pct < 25 else ""}
"""
        return self._send(message)

    def exposure_gate_clear(
        self,
        old_exposure_pct: float,
        new_exposure_pct: float,
        trigger_event: str
    ) -> bool:
        """
        #2: Exposure Gate Clear (<25%)
        Priority: URGENT
        """
        message = self._format_header("EXPOSURE GATE CLEAR", AlertPriority.URGENT)
        message += f"""
🔓 *Single Position Limit Now Clear*

📊 *Exposure Change:*
• Before: {old_exposure_pct:.1f}%
• After: {new_exposure_pct:.1f}%
• Limit: 25%

🎯 *Trigger:* {trigger_event}

✅ *Neural Bridge Status:*
• execute_trade() now reachable
• IntentDraft creation enabled
• IKEA/InForage gates active

_Awaiting first live cycle..._
"""
        return self._send(message)

    def trade_executed(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        position_usd: float,
        needle_title: str,
        eqs_score: float,
        regime: str,
        decision_plan_id: str = None
    ) -> bool:
        """
        #3: Trade Executed
        Priority: HIGH
        """
        message = self._format_header("TRADE EXECUTED", AlertPriority.HIGH)
        message += f"""
💰 *New Position Opened*

📊 *Trade Details:*
• Asset: {symbol}
• Direction: {direction}
• Entry: ${entry_price:,.2f}
• Size: ${position_usd:,.2f}

🎯 *Signal:*
• Needle: {needle_title[:50]}...
• EQS: {eqs_score:.2f}
• Regime: {regime}

{"🔗 DecisionPlan: `" + decision_plan_id[:8] + "...`" if decision_plan_id else "⚠️ Pre-Neural Bridge trade"}
"""
        return self._send(message)

    def neural_bridge_block(
        self,
        symbol: str,
        direction: str,
        blocked_by: str,
        block_reason: str,
        needle_title: str,
        eqs_score: float
    ) -> bool:
        """
        #4: Neural Bridge Block (IKEA/InForage rejection)
        Priority: HIGH
        """
        message = self._format_header("NEURAL BRIDGE BLOCK", AlertPriority.HIGH)
        message += f"""
🛡️ *Trade Blocked by Governance*

📊 *Attempted Trade:*
• Asset: {symbol}
• Direction: {direction}
• EQS: {eqs_score:.2f}

❌ *Block Details:*
• Gate: {blocked_by}
• Reason: {block_reason}

🎯 *Signal:* {needle_title[:50]}...

_Governance working as designed._
"""
        return self._send(message)

    def daemon_error(
        self,
        error_type: str,
        error_message: str,
        component: str,
        is_fatal: bool = False
    ) -> bool:
        """
        #5: Daemon Error/Crash
        Priority: CRITICAL
        """
        priority = AlertPriority.CRITICAL if is_fatal else AlertPriority.HIGH
        status = "CRASHED" if is_fatal else "ERROR"

        message = self._format_header(f"DAEMON {status}", priority)
        message += f"""
{"💀" if is_fatal else "⚠️"} *System {"Down" if is_fatal else "Issue"}*

🔧 *Error Details:*
• Component: {component}
• Type: {error_type}
• Fatal: {"YES" if is_fatal else "No"}

📝 *Message:*
`{error_message[:200]}`

{"🚨 *IMMEDIATE ATTENTION REQUIRED*" if is_fatal else ""}
"""
        return self._send(message)

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def system_status(self, status_dict: Dict[str, Any]) -> bool:
        """Send system status update."""
        message = self._format_header("SYSTEM STATUS", AlertPriority.INFO)

        for key, value in status_dict.items():
            message += f"• {key}: {value}\n"

        return self._send(message)

    def test(self) -> bool:
        """Send test message."""
        message = self._format_header("TEST ALERT", AlertPriority.INFO)
        message += """
✅ *Telegram Notifier Working*

This is a test message from FjordHQ Market System.

_STIG - System for Technical Implementation & Governance_
"""
        return self._send(message)


# Global instance for easy import
notifier = FjordHQNotifier()


# Convenience functions
def send_position_exit(**kwargs) -> bool:
    return notifier.position_exit(**kwargs)

def send_exposure_clear(**kwargs) -> bool:
    return notifier.exposure_gate_clear(**kwargs)

def send_trade_executed(**kwargs) -> bool:
    return notifier.trade_executed(**kwargs)

def send_neural_bridge_block(**kwargs) -> bool:
    return notifier.neural_bridge_block(**kwargs)

def send_daemon_error(**kwargs) -> bool:
    return notifier.daemon_error(**kwargs)

def send_test() -> bool:
    return notifier.test()


if __name__ == "__main__":
    # Test the notifier
    print("Testing FjordHQ Telegram Notifier...")

    n = FjordHQNotifier()

    # Send test
    result = n.test()
    print(f"Test message sent: {result}")

    # Example: Position exit
    # n.position_exit(
    #     symbol="BTC-USD",
    #     direction="LONG",
    #     entry_price=87890,
    #     exit_price=90520,
    #     pnl_pct=2.99,
    #     pnl_usd=2243.50,
    #     exit_reason="TAKE_PROFIT",
    #     new_exposure_pct=0.0
    # )
