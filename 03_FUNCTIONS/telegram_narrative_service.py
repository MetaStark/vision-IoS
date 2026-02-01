"""
Telegram Narrative Service - Story, Not Log Dump
CEO-DIR-2026-01-22: "Tonight's Map" format for signal delivery

Transforms Decision Packs into human-readable stories for Telegram.
- Act 1: Context (regime, volatility, what changed)
- Act 2: Decision (entry, size, TP/SL)
- Act 3: Evidence (confidence, calibration, causal edges)

Author: STIG (CTO)
Contract: EC-003_2026_PRODUCTION
"""

import os
import logging
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime, timezone

# Import existing notifier
from telegram_notifier import FjordHQNotifier, AlertPriority

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class NarrativeStory:
    """Three-act story structure for Telegram."""
    headline: str              # Single-line summary
    act1_context: str          # Market context and setup
    act2_decision: str         # What we're doing and why
    act3_evidence: str         # Supporting evidence and risk
    evidence_id: str           # Pack ID for audit trail
    emoji_mood: str            # Overall mood indicator


# =============================================================================
# NARRATIVE GENERATOR
# =============================================================================

class TelegramNarrativeService:
    """
    Transform Decision Pack + Golden Needle into human story.

    CEO Spec: "Tonight's map" format with Act 1 (Context),
    Act 2 (Decision), Act 3 (Evidence)
    """

    def __init__(self, notifier: FjordHQNotifier = None):
        self.notifier = notifier or FjordHQNotifier()

    def generate_story(self, decision_pack) -> NarrativeStory:
        """Generate three-act narrative from decision pack."""
        # Act 1: Context (from regime + events)
        act1 = self._generate_context(decision_pack)

        # Act 2: Decision (from direction + sizing + TP/SL)
        act2 = self._generate_decision(decision_pack)

        # Act 3: Evidence (from cognitive stack)
        act3 = self._generate_evidence(decision_pack)

        # Headline
        direction_emoji = "📈" if decision_pack.direction == "LONG" else "📉"
        asset_short = decision_pack.asset.split('/')[0] if '/' in decision_pack.asset else decision_pack.asset
        headline = f"{direction_emoji} {asset_short}: {decision_pack.hypothesis_title or 'Signal Detected'}"

        # Mood based on confidence and regime
        emoji_mood = self._determine_mood(decision_pack)

        # Evidence ID
        evidence_id = str(decision_pack.pack_id)[:8] if decision_pack.pack_id else "N/A"

        return NarrativeStory(
            headline=headline,
            act1_context=act1,
            act2_decision=act2,
            act3_evidence=act3,
            evidence_id=evidence_id,
            emoji_mood=emoji_mood
        )

    def _generate_context(self, dp) -> str:
        """Act 1: Market context and setup."""
        regime_descriptions = {
            'BULL': 'Bullish momentum building',
            'STRONG_BULL': 'Strong bullish trend in place',
            'BEAR': 'Bearish pressure dominant',
            'STRONG_BEAR': 'Strong bearish trend confirmed',
            'STRESS': 'Market under stress, caution advised',
            'BROKEN': 'Unusual market conditions',
            'NEUTRAL': 'Range-bound, watching for breakout'
        }

        regime_desc = regime_descriptions.get(dp.snapshot_regime, 'Market in transition')
        volatility_desc = "elevated" if dp.snapshot_volatility_atr > 3.0 else "moderate" if dp.snapshot_volatility_atr > 2.0 else "low"

        narrative = dp.narrative_context or dp.executive_summary or "Conditions align for opportunity."

        # Truncate if too long
        if len(narrative) > 150:
            narrative = narrative[:147] + "..."

        return f"""*Tonight's Context:*
Regime: {dp.snapshot_regime} - {regime_desc}
Volatility: {volatility_desc} ({dp.snapshot_volatility_atr:.1f}% ATR)
{narrative}"""

    def _generate_decision(self, dp) -> str:
        """Act 2: What we're doing and why."""
        direction_word = "Going long" if dp.direction == "LONG" else "Going short"
        asset_display = dp.asset.replace('/', '-')

        # Calculate position as % of portfolio
        position_pct_str = f"{dp.max_position_pct:.1%}" if dp.max_position_pct else "calculated"

        # Risk-reward
        if dp.ewre:
            rr = dp.ewre.risk_reward_ratio
            sl_pct = dp.ewre.stop_loss_pct
            tp_pct = dp.ewre.take_profit_pct
        else:
            rr = 1.5
            sl_pct = 0.03
            tp_pct = 0.05

        return f"""*The Decision:*
{direction_word} on {asset_display} @ ${dp.entry_limit_price:,.2f}
Size: ${dp.position_usd:,.0f} ({position_pct_str} of portfolio)

*Exit Discipline:*
Take Profit: ${dp.take_profit_price:,.2f} (+{tp_pct:.1%})
Stop Loss: ${dp.stop_loss_price:,.2f} (-{sl_pct:.1%})
Risk/Reward: {rr:.1f}:1"""

    def _generate_evidence(self, dp) -> str:
        """Act 3: Supporting evidence and risk."""
        # Confidence bar visualization
        conf = dp.damped_confidence or 0.5
        filled = int(conf * 10)
        empty = 10 - filled
        confidence_bar = "█" * filled + "░" * empty

        # Historical accuracy
        hist_acc = dp.historical_accuracy or 0.40
        hist_desc = "above average" if hist_acc > 0.50 else "average" if hist_acc > 0.35 else "developing"

        # Cognitive checks
        sitc_status = "✅" if dp.sitc_reasoning_complete else "⚠️"
        ikea_status = "✅" if dp.ikea_passed else "❌"
        inforage_str = f"{dp.inforage_roi:.1f}x" if dp.inforage_roi else "N/A"

        # Inversion flag
        inversion_note = "\n🔄 *Inversion active* - contrarian signal" if dp.inversion_flag else ""

        return f"""*Evidence Stack:*
Confidence: [{confidence_bar}] {conf:.0%}
Calibration: {hist_acc:.0%} historical ({hist_desc})
Causal alignment: {dp.causal_alignment_score:.0%}

*Cognitive Checks:*
SitC Reasoning: {sitc_status}
IKEA Boundary: {ikea_status}
InForage ROI: {inforage_str}{inversion_note}"""

    def _determine_mood(self, dp) -> str:
        """Determine emoji mood based on confidence and regime."""
        conf = dp.damped_confidence or 0.5
        regime = dp.snapshot_regime or 'NEUTRAL'

        if conf > 0.6 and regime in ('BULL', 'STRONG_BULL'):
            return "🟢"  # Green: high confidence, favorable regime
        elif regime in ('STRESS', 'BROKEN'):
            return "🟡"  # Yellow: caution
        elif conf > 0.5:
            return "🔵"  # Blue: moderate
        else:
            return "⚪"  # White: exploratory

    def format_tonights_map(self, decision_packs: List) -> str:
        """
        Format complete "Tonight's Map" message for multiple packs.
        """
        if not decision_packs:
            return self._format_quiet_night()

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        header = f"""🗺️ *TONIGHT'S MAP*
_Where the system sees risk, and where it sees edge_
_{timestamp}_
"""
        body = ""
        for i, dp in enumerate(decision_packs[:3], 1):  # Max 3 per message
            story = self.generate_story(dp)
            body += f"""
{story.emoji_mood} *#{i} {story.headline}*

{story.act1_context}

{story.act2_decision}

{story.act3_evidence}

📋 Evidence: `{story.evidence_id}`
{'─' * 35}
"""
        # Footer
        abort_time = decision_packs[0].abort_if_not_filled_by if decision_packs else None
        if abort_time:
            abort_str = abort_time.strftime("%H:%M UTC")
            footer = f"\n⏰ *If not filled by {abort_str}, we walk.*"
        else:
            footer = ""

        return header + body + footer

    def _format_quiet_night(self) -> str:
        """Format message when no signals qualify."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return f"""🌙 *QUIET NIGHT*
_{timestamp}_

No qualified signals tonight.
All gates satisfied, system healthy.
Waiting for high-conviction opportunities.

_Patience is alpha._
"""

    def send_tonights_map(self, decision_packs: List) -> bool:
        """
        Send "Tonight's Map" summary to Telegram.

        Args:
            decision_packs: List of DecisionPack objects

        Returns:
            True if sent successfully
        """
        message = self.format_tonights_map(decision_packs)
        return self.notifier._send(message, parse_mode="Markdown")

    def send_single_signal(self, decision_pack) -> bool:
        """
        Send single signal notification.
        """
        story = self.generate_story(decision_pack)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        message = f"""{story.emoji_mood} *NEW SIGNAL*
_{timestamp}_

{story.headline}

{story.act1_context}

{story.act2_decision}

{story.act3_evidence}

📋 Evidence: `{story.evidence_id}`
"""
        return self.notifier._send(message, parse_mode="Markdown")

    def send_execution_update(self, decision_pack, alpaca_order_id: str, status: str) -> bool:
        """
        Send execution status update.
        """
        direction_emoji = "📈" if decision_pack.direction == "LONG" else "📉"
        status_emoji = "✅" if status in ('filled', 'EXECUTED') else "⏳" if status in ('new', 'accepted', 'PENDING') else "❌"

        message = f"""{status_emoji} *ORDER UPDATE*

{direction_emoji} {decision_pack.asset} {decision_pack.direction}
Entry: ${decision_pack.entry_limit_price:,.2f}
Status: {status.upper()}
Order ID: `{alpaca_order_id[:12]}...`

TP: ${decision_pack.take_profit_price:,.2f}
SL: ${decision_pack.stop_loss_price:,.2f}
"""
        return self.notifier._send(message, parse_mode="Markdown")

    def send_batch_summary(self, total_packs: int, submitted: int, failed: int) -> bool:
        """
        Send batch execution summary.
        """
        success_rate = (submitted / total_packs * 100) if total_packs > 0 else 0
        status_emoji = "✅" if failed == 0 else "⚠️" if failed < submitted else "❌"

        message = f"""{status_emoji} *BATCH EXECUTION SUMMARY*
_EWRE V1 - First 20 Orders_

Total Decision Packs: {total_packs}
Submitted to Market: {submitted}
Failed: {failed}
Success Rate: {success_rate:.0f}%

Strategy Tag: EWRE_V1
Experiment Cohort: FIRST_20

_Monitoring for TP/SL triggers..._
"""
        return self.notifier._send(message, parse_mode="Markdown")


# =============================================================================
# TESTING
# =============================================================================

if __name__ == '__main__':
    from decision_pack import DecisionPack, EWRESpec
    from uuid import uuid4
    from datetime import timedelta

    print("=" * 60)
    print("Telegram Narrative Service Test")
    print("=" * 60)

    # Create test decision pack
    now = datetime.now(timezone.utc)
    test_pack = DecisionPack(
        pack_id=uuid4(),
        needle_id=uuid4(),
        asset="BTC/USD",
        direction="LONG",
        asset_class="CRYPTO",
        snapshot_price=103500.0,
        snapshot_regime="NEUTRAL",
        snapshot_volatility_atr=2.8,
        snapshot_timestamp=now,
        snapshot_ttl_valid_until=now + timedelta(seconds=60),
        raw_confidence=0.85,
        damped_confidence=0.68,
        confidence_ceiling=0.70,
        inversion_flag=False,
        historical_accuracy=0.47,
        entry_limit_price=103450.0,
        take_profit_price=111726.0,
        stop_loss_price=98278.0,
        position_usd=5000.0,
        position_qty=0.048,
        max_position_pct=0.025,
        hypothesis_title="Neutral-to-Bull Transition on Regulatory Clarity",
        executive_summary="UK regulatory clarity removes uncertainty tail risk.",
        narrative_context="Sequential volume increase shows accumulation. The 3-day MA hold demonstrates underlying strength before breakout.",
        sitc_reasoning_complete=True,
        ikea_passed=True,
        inforage_roi=1.5,
        causal_alignment_score=0.72,
        abort_if_not_filled_by=now + timedelta(hours=24),
        ewre=EWRESpec(
            stop_loss_pct=0.05,
            take_profit_pct=0.08,
            risk_reward_ratio=1.6
        )
    )

    # Test narrative generation
    service = TelegramNarrativeService()

    print("\n--- Single Signal Format ---\n")
    story = service.generate_story(test_pack)
    print(f"Headline: {story.headline}")
    print(f"Mood: {story.emoji_mood}")
    print(f"\n{story.act1_context}")
    print(f"\n{story.act2_decision}")
    print(f"\n{story.act3_evidence}")

    print("\n--- Tonight's Map Format ---\n")
    map_message = service.format_tonights_map([test_pack])
    print(map_message)

    print("\n--- Quiet Night Format ---\n")
    quiet_message = service._format_quiet_night()
    print(quiet_message)

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)
