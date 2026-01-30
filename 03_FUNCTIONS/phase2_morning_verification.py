#!/usr/bin/env python3
"""
PHASE 2 MORNING VERIFICATION
==============================
CEO-DIR-2026-BLINDNESS-REMEDIATION: Automated morning health check.

Checks 4 critical verification points and sends results to CEO via Telegram:
1. Indicator freshness (momentum + volatility signal_date = today or yesterday)
2. Outcome daemon activity (overnight evaluations + pending count)
3. Zombie daemon detection (ACTIVE lifecycle, stale > 2x expected interval)
4. Experiment pipeline summary (triggers + outcomes per experiment)

Usage:
    python phase2_morning_verification.py          # Check + send Telegram
    python phase2_morning_verification.py --check   # Check only, no Telegram
    python phase2_morning_verification.py --test    # Send test message

Author: STIG (CTO)
Date: 2026-01-29
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime, timezone, timedelta

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[MORNING_VERIFY] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/phase2_morning_verification.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('morning_verification')

# Database
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8019173608:AAH37ApVjUaNXM_EotUS735bj4qqbUTi1Ik')
TELEGRAM_CHAT_ID = os.getenv('CEO_TELEGRAM_CHAT_ID', os.getenv('TELEGRAM_CHAT_ID', '6194473125'))

# Thresholds
ZOMBIE_THRESHOLD_HOURS = 2.0
INDICATOR_MAX_LAG_DAYS = 1  # Allow 1 day lag (today or yesterday)


def send_telegram(message: str) -> bool:
    """Send message to CEO via Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured")
        return False
    try:
        import requests
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                'chat_id': TELEGRAM_CHAT_ID,
                'text': message,
                'parse_mode': 'HTML'
            },
            timeout=10
        )
        if resp.ok:
            logger.info("Telegram message sent")
            return True
        else:
            logger.error(f"Telegram failed: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Telegram exception: {e}")
        return False


def check_indicator_freshness(conn) -> dict:
    """CHECK 1: Indicator calculation layer freshness."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                'momentum' as source,
                MAX(signal_date) as max_date,
                COUNT(DISTINCT listing_id) as assets
            FROM fhq_indicators.momentum
            UNION ALL
            SELECT
                'volatility' as source,
                MAX(signal_date) as max_date,
                COUNT(DISTINCT listing_id) as assets
            FROM fhq_indicators.volatility
            UNION ALL
            SELECT
                'price_series' as source,
                MAX(date) as max_date,
                COUNT(DISTINCT listing_id) as assets
            FROM fhq_data.price_series
        """)
        rows = cur.fetchall()

    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)

    results = {}
    all_fresh = True
    for row in rows:
        source = row['source']
        max_date = row['max_date']
        assets = row['assets']
        if max_date is None:
            fresh = False
        elif hasattr(max_date, 'date'):
            fresh = max_date.date() >= yesterday
        else:
            fresh = max_date >= yesterday
        if not fresh:
            all_fresh = False
        results[source] = {
            'max_date': str(max_date) if max_date else 'NULL',
            'assets': assets,
            'fresh': fresh
        }

    return {
        'pass': all_fresh,
        'sources': results
    }


def check_indicator_pulse_health(conn) -> dict:
    """CHECK 6: Indicator PULSE audit trail — staleness sentinel.

    CEO-DIR-20260130-OPS-INDICATOR-PULSE-001 D4:
    - Checks indicator_pulse_audit for recent successful runs
    - Triggers governance incident on 48h breach
    - DEFCON-aligned: staleness blocks downstream
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Last successful run
        cur.execute("""
            SELECT run_date, start_time, end_time, exit_code, duration_seconds
            FROM fhq_monitoring.indicator_pulse_audit
            WHERE exit_code = 0
            ORDER BY start_time DESC
            LIMIT 1
        """)
        last_run = cur.fetchone()

        # Last run regardless of exit code
        cur.execute("""
            SELECT run_date, exit_code, start_time
            FROM fhq_monitoring.indicator_pulse_audit
            ORDER BY start_time DESC
            LIMIT 1
        """)
        latest_any = cur.fetchone()

        # Check Task Scheduler state (by checking last 3 runs)
        cur.execute("""
            SELECT exit_code, COUNT(*) as cnt
            FROM (
                SELECT exit_code
                FROM fhq_monitoring.indicator_pulse_audit
                ORDER BY start_time DESC
                LIMIT 3
            ) recent
            GROUP BY exit_code
        """)
        recent_codes = {r['exit_code']: r['cnt'] for r in cur.fetchall()}

    if not last_run:
        return {
            'pass': False,
            'status': 'NO_AUDIT_DATA',
            'last_success': None,
            'hours_since_success': None,
            'consecutive_failures': 0,
            'detail': 'Ingen vellykket PULSE-kjøring funnet i audit trail'
        }

    hours_since = 0
    if last_run['end_time']:
        delta = datetime.now(timezone.utc) - last_run['end_time']
        hours_since = round(delta.total_seconds() / 3600, 1)

    # Consecutive failures (recent runs with non-zero exit)
    consecutive_failures = recent_codes.get(1, 0) + recent_codes.get(2, 0) + recent_codes.get(3, 0)

    # Staleness threshold: 36h = missed one daily run + buffer
    stale = hours_since > 36
    failing = consecutive_failures >= 3

    return {
        'pass': not stale and not failing,
        'status': 'STALE' if stale else ('FAILING' if failing else 'HEALTHY'),
        'last_success': str(last_run['end_time']) if last_run['end_time'] else None,
        'hours_since_success': hours_since,
        'last_exit_code': latest_any['exit_code'] if latest_any else None,
        'consecutive_failures': consecutive_failures,
        'detail': (
            f"Siste vellykket: {hours_since}t siden"
            if not stale else
            f"FORELDET: {hours_since}t siden siste vellykkede kjøring (grense: 36t)"
        )
    }


def check_outcome_daemon(conn) -> dict:
    """CHECK 2: Outcome daemon overnight activity."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Recent outcomes (last 24h)
        cur.execute("""
            SELECT COUNT(*) as recent_outcomes
            FROM fhq_learning.outcome_ledger
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """)
        recent = cur.fetchone()['recent_outcomes']

        # Pending outcomes (triggers past deadline, no outcome yet)
        cur.execute("""
            SELECT COUNT(*) as pending
            FROM fhq_learning.trigger_events te
            JOIN fhq_learning.experiment_registry er ON te.experiment_id = er.experiment_id
            JOIN fhq_learning.hypothesis_canon hc ON er.hypothesis_id = hc.canon_id
            LEFT JOIN fhq_learning.outcome_ledger ol ON te.trigger_event_id = ol.trigger_event_id
            WHERE ol.outcome_id IS NULL
            AND te.event_timestamp + make_interval(hours => hc.expected_timeframe_hours::int) < NOW()
        """)
        pending = cur.fetchone()['pending']

        # Daemon health
        cur.execute("""
            SELECT status, last_heartbeat,
                   EXTRACT(EPOCH FROM (NOW() - last_heartbeat))/3600 as age_hours
            FROM fhq_monitoring.daemon_health
            WHERE daemon_name = 'mechanism_alpha_outcome'
        """)
        daemon = cur.fetchone()

    daemon_status = daemon['status'] if daemon else 'NOT_FOUND'
    daemon_age = round(daemon['age_hours'], 1) if daemon else None

    return {
        'pass': daemon_status in ('HEALTHY', 'RUNNING') and pending == 0,
        'recent_outcomes_24h': recent,
        'pending_evaluable': pending,
        'daemon_status': daemon_status,
        'daemon_age_hours': daemon_age
    }


def check_zombie_daemons(conn) -> dict:
    """CHECK 3: Zombie daemon detection — truthful health model.

    CEO-DIR-20260130-OPS-INDICATOR-PULSE-001 D3:
    - Only checks daemons with lifecycle_status = 'ACTIVE'
    - Uses expected_interval_minutes * 2 as staleness threshold (not flat 2h)
    - Excludes RETIRED, DEPRECATED, SUSPENDED_BY_DESIGN
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT daemon_name, status, last_heartbeat,
                   EXTRACT(EPOCH FROM (NOW() - last_heartbeat))/3600 as age_hours,
                   COALESCE(expected_interval_minutes, 30) as expected_minutes
            FROM fhq_monitoring.daemon_health
            WHERE lifecycle_status = 'ACTIVE'
            AND status IN ('HEALTHY', 'RUNNING')
            AND EXTRACT(EPOCH FROM (NOW() - last_heartbeat))/60
                > COALESCE(expected_interval_minutes, 30) * 2
            ORDER BY last_heartbeat ASC
        """)
        zombies = cur.fetchall()

        # Total daemon count (only ACTIVE lifecycle)
        cur.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN status IN ('HEALTHY', 'RUNNING') THEN 1 ELSE 0 END) as alive,
                   SUM(CASE WHEN status IN ('STOPPED', 'FAILED', 'DEGRADED') THEN 1 ELSE 0 END) as dead
            FROM fhq_monitoring.daemon_health
            WHERE lifecycle_status = 'ACTIVE'
        """)
        counts = cur.fetchone()

    zombie_list = [
        {
            'name': z['daemon_name'],
            'age_hours': round(z['age_hours'], 1),
            'expected_minutes': z['expected_minutes']
        }
        for z in zombies
    ]

    return {
        'pass': len(zombie_list) == 0,
        'zombies': zombie_list,
        'total_daemons': counts['total'],
        'alive': counts['alive'],
        'dead': counts['dead']
    }


def check_experiment_pipeline(conn) -> dict:
    """CHECK 4: Experiment pipeline summary with goal progress."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Enriched experiment query: triggers, outcomes, wins, hypothesis goals
        cur.execute("""
            SELECT
                er.experiment_code,
                er.status,
                er.metadata->>'candidate_promotion' as promoted,
                er.parameters->>'min_sample_size' as min_sample,
                er.parameters->>'falsified_if' as falsification_rule,
                hc.causal_mechanism,
                hc.expected_timeframe_hours,
                hc.regime_validity,
                hc.current_confidence,
                (SELECT COUNT(*) FROM fhq_learning.trigger_events te
                 WHERE te.experiment_id = er.experiment_id) as triggers,
                (SELECT COUNT(*) FROM fhq_learning.outcome_ledger ol
                 WHERE ol.experiment_id = er.experiment_id) as outcomes,
                (SELECT SUM(CASE WHEN ol2.result_bool THEN 1 ELSE 0 END)
                 FROM fhq_learning.outcome_ledger ol2
                 WHERE ol2.experiment_id = er.experiment_id) as wins
            FROM fhq_learning.experiment_registry er
            JOIN fhq_learning.hypothesis_canon hc ON er.hypothesis_id = hc.canon_id
            WHERE er.experiment_code LIKE 'EXP_ALPHA_SAT_%%'
            ORDER BY er.experiment_code
        """)
        experiments = cur.fetchall()

        # Current regime distribution
        cur.execute("""
            SELECT sovereign_regime, COUNT(*) as cnt
            FROM fhq_perception.sovereign_regime_state_v4
            GROUP BY sovereign_regime
        """)
        regime_counts = {r['sovereign_regime']: r['cnt'] for r in cur.fetchall()}

        # Gate status
        cur.execute("""
            SELECT status FROM fhq_meta.gate_status
            WHERE gate_id = 'PHASE2_HYPOTHESIS_SWARM_V1.1'
        """)
        gate = cur.fetchone()

        # DEFCON
        cur.execute("""
            SELECT defcon_level FROM fhq_governance.defcon_state
            WHERE is_current = true
        """)
        defcon = cur.fetchone()

    total_triggers = sum(e['triggers'] for e in experiments)
    total_outcomes = sum(e['outcomes'] for e in experiments)
    total_wins = sum((e['wins'] or 0) for e in experiments)
    all_running = all(e['status'] == 'RUNNING' for e in experiments)

    exp_list = []
    for e in experiments:
        min_sample = int(e['min_sample'] or 30)
        outcomes = e['outcomes']
        wins = e['wins'] or 0
        win_rate = round(100 * wins / outcomes, 1) if outcomes > 0 else None
        progress_pct = round(100 * outcomes / min_sample, 0) if min_sample > 0 else 0

        exp_list.append({
            'code': e['experiment_code'],
            'status': e['status'],
            'promoted': e['promoted'] == 'true',
            'triggers': e['triggers'],
            'outcomes': outcomes,
            'wins': wins,
            'win_rate': win_rate,
            'min_sample': min_sample,
            'progress_pct': progress_pct,
            'falsification_rule': e['falsification_rule'],
            'causal_mechanism': e['causal_mechanism'],
            'timeframe_hours': float(e['expected_timeframe_hours'] or 0),
            'regime_validity': e['regime_validity'] or [],
            'confidence': float(e['current_confidence'] or 0),
        })

    return {
        'pass': all_running and total_triggers > 0,
        'experiments': exp_list,
        'total_triggers': total_triggers,
        'total_outcomes': total_outcomes,
        'total_wins': total_wins,
        'regime_counts': regime_counts,
        'gate': gate['status'] if gate else 'NOT_FOUND',
        'defcon': defcon['defcon_level'] if defcon else 'NOT_FOUND'
    }


def check_pipeline_health(conn) -> dict:
    """CHECK 5: 9-step pipeline toward capital — shows where the chain breaks."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Step 1: Hypotheses
        cur.execute("SELECT COUNT(*) as cnt FROM fhq_learning.hypothesis_canon WHERE status NOT IN ('FALSIFIED', 'RETIRED')")
        hypotheses = cur.fetchone()['cnt']

        # Step 2: Running experiments
        cur.execute("SELECT COUNT(*) as cnt FROM fhq_learning.experiment_registry WHERE status = 'RUNNING'")
        experiments = cur.fetchone()['cnt']

        # Step 3: Outcomes collected
        cur.execute("SELECT COUNT(*) as cnt FROM fhq_learning.outcome_ledger")
        outcomes = cur.fetchone()['cnt']

        # Step 4: Promotion gate evaluations
        cur.execute("SELECT COUNT(*) as cnt FROM fhq_learning.promotion_gate_audit")
        promotions = cur.fetchone()['cnt']
        cur.execute("SELECT COUNT(*) as cnt FROM fhq_learning.promotion_gate_audit WHERE gate_result = 'PASS'")
        promotions_pass = cur.fetchone()['cnt']

        # Step 5: Shadow tier entries
        cur.execute("SELECT COUNT(*) as cnt FROM fhq_learning.shadow_tier_registry")
        shadow_tier = cur.fetchone()['cnt']

        # Step 6: Capital simulations
        cur.execute("SELECT COUNT(*) as cnt FROM fhq_learning.capital_simulation_ledger")
        simulations = cur.fetchone()['cnt']

        # Step 7: Execution eligibility
        cur.execute("SELECT COUNT(*) as cnt FROM fhq_learning.execution_eligibility_registry")
        eligibility = cur.fetchone()['cnt']

        # Step 8: Paper orders filled
        cur.execute("SELECT COUNT(*) as cnt FROM fhq_execution.paper_orders WHERE status = 'filled'")
        paper_filled = cur.fetchone()['cnt']
        cur.execute("SELECT COUNT(*) as cnt FROM fhq_execution.paper_orders")
        paper_total = cur.fetchone()['cnt']

        # Step 9: Paper trade outcomes (real P&L tracking)
        cur.execute("SELECT COUNT(*) as cnt FROM fhq_execution.paper_trade_outcomes")
        paper_outcomes = cur.fetchone()['cnt']

        # Next milestone: find first step with 0
        cur.execute("""
            SELECT
                COALESCE((SELECT MIN((e.parameters->>'min_sample_size')::int)
                          FROM fhq_learning.experiment_registry e
                          WHERE e.status = 'RUNNING'), 30) as min_sample_needed
        """)
        min_sample = cur.fetchone()['min_sample_needed']

    steps = [
        {'step': 1, 'name': 'Hypotese', 'count': hypotheses, 'detail': f'{hypotheses} aktive'},
        {'step': 2, 'name': 'Eksperiment', 'count': experiments, 'detail': f'{experiments} kjører'},
        {'step': 3, 'name': 'Utfall', 'count': outcomes, 'detail': f'{outcomes} samlet'},
        {'step': 4, 'name': 'Promotering', 'count': promotions, 'detail': f'{promotions} evaluert ({promotions_pass} bestått)'},
        {'step': 5, 'name': 'Skyggehandel', 'count': shadow_tier, 'detail': f'{shadow_tier} registrert'},
        {'step': 6, 'name': 'Simulering', 'count': simulations, 'detail': f'{simulations} aktive'},
        {'step': 7, 'name': 'Eligibilitet', 'count': eligibility, 'detail': f'{eligibility} vurdert'},
        {'step': 8, 'name': 'Papirhandel', 'count': paper_filled, 'detail': f'{paper_filled} fylt av {paper_total}'},
        {'step': 9, 'name': 'Ekte kapital', 'count': 0, 'detail': 'Ikke aktivert (krever G4)'},
    ]

    # Find where the chain breaks
    first_break = None
    for s in steps:
        if s['count'] == 0 and s['step'] <= 8:  # Step 9 is always 0 for now
            first_break = s['step']
            break

    # Next milestone description
    if first_break == 4:
        next_milestone = f'Steg 4 aktiveres ved {min_sample} utfall'
    elif first_break == 5:
        next_milestone = 'Steg 5 aktiveres når promotering gir PASS'
    elif first_break == 6:
        next_milestone = 'Steg 6 aktiveres ved positiv skyggehandel'
    elif first_break == 7:
        next_milestone = 'Steg 7 aktiveres etter simuleringsresultater'
    elif first_break == 8:
        next_milestone = 'Steg 8 aktiveres etter eligibilitetsvurdering'
    elif first_break is None:
        next_milestone = 'Pipeline operativ — venter på G4 for ekte kapital'
    else:
        next_milestone = f'Steg {first_break} er neste flaskehals'

    active_steps = sum(1 for s in steps if s['count'] > 0)

    return {
        'pass': active_steps >= 3,  # At minimum steps 1-3 should be active
        'steps': steps,
        'active_steps': active_steps,
        'total_steps': 9,
        'first_break': first_break,
        'next_milestone': next_milestone
    }


def get_experiment_status_label(exp: dict) -> str:
    """Map experiment status + trigger count to Norwegian status label."""
    status = exp.get('status', '').upper()
    triggers = exp.get('triggers', 0)

    if status == 'PROMOTED' or exp.get('promoted'):
        return 'PRO'
    if status in ('RUNNING', 'MEASURING') and triggers > 0:
        return 'MÅL'
    if status in ('RUNNING',) and triggers == 0:
        return 'OBS'
    return status[:3]


# Short Norwegian descriptions of what each experiment tests
EXPERIMENT_DESCRIPTIONS = {
    'ALPHA_SAT_A': 'Volatilitetsklem',
    'ALPHA_SAT_B': 'Trendfølging i sterk oppgang',
    'ALPHA_SAT_C': 'Tilbakevending til snitt',
    'ALPHA_SAT_D': 'Utbrudd med momentum',
    'ALPHA_SAT_E': 'Kjøp på tilbakefall i opptrend',
    'ALPHA_SAT_F': 'Panikk-bunn-sprett',
}

# Norwegian regime names
REGIME_LABELS = {
    'BULL': 'oppgang',
    'STRONG_BULL': 'sterk oppgang',
    'BEAR': 'nedgang',
    'STRESS': 'stress',
    'NEUTRAL': 'nøytral',
    'WEAK_BULL': 'svak oppgang',
    'WEAK_BEAR': 'svak nedgang',
    'LOW_VOL': 'lav volatilitet',
    'BULL_OR_NEUTRAL': 'oppgang/nøytral',
    'BEAR_OR_STRESS': 'nedgang/stress',
}


def _progress_bar(pct: float, width: int = 10) -> str:
    """Build a text progress bar: [████░░░░░░] 40%"""
    filled = int(round(pct / 100 * width))
    filled = min(filled, width)
    return '█' * filled + '░' * (width - filled)


def _extract_threshold(rule: str) -> float:
    """Extract numeric threshold from falsification rule like 'bounce_rate < 0.45'."""
    if not rule:
        return 0.0
    try:
        parts = rule.split('<')
        if len(parts) == 2:
            return float(parts[1].strip()) * 100
    except (ValueError, IndexError):
        pass
    return 0.0


def _test_letter(code: str) -> str:
    """Extract letter from experiment code: EXP_ALPHA_SAT_F_V1.0 -> F"""
    parts = code.split('_')
    for i, p in enumerate(parts):
        if p == 'SAT' and i + 1 < len(parts):
            return parts[i + 1]
    return code


def _test_key(code: str) -> str:
    """Extract key like ALPHA_SAT_F from experiment code."""
    # EXP_ALPHA_SAT_F_V1.0 -> ALPHA_SAT_F
    parts = code.replace('EXP_', '').split('_V')[0]
    return parts


def build_assessment(results: dict) -> list:
    """Faglig vurdering: fremgang mot mål + neste beste handling."""
    lines = []
    pipe = results['pipeline']
    regime_counts = pipe.get('regime_counts', {})

    # Per-experiment progress report
    for exp in pipe['experiments']:
        letter = _test_letter(exp['code'])
        key = _test_key(exp['code'])
        desc = EXPERIMENT_DESCRIPTIONS.get(key, '')
        min_s = exp['min_sample']
        outcomes = exp['outcomes']
        wins = exp['wins']
        wr = exp['win_rate']
        threshold = _extract_threshold(exp.get('falsification_rule'))
        bar = _progress_bar(exp['progress_pct'])
        regime_names = ', '.join(
            REGIME_LABELS.get(r, r.lower()) for r in exp['regime_validity']
        )

        # Header line with description
        lines.append(f"<b>Test {letter}</b> — {desc}")

        if outcomes > 0:
            # Has data: show progress + win rate vs threshold
            wr_icon = '✓' if (threshold > 0 and wr >= threshold) else '→'
            lines.append(
                f"  {bar} {outcomes}/{min_s} utfall"
            )
            rate_str = f"{wr:.0f}%" if wr is not None else '—'
            if threshold > 0:
                lines.append(f"  {wr_icon} Treffsikkerhet: {rate_str} (mål: ≥{threshold:.0f}%)")
            else:
                lines.append(f"  {wr_icon} Treffsikkerhet: {rate_str}")
            if exp.get('promoted'):
                lines.append(f"  ⭐ Promotert — kandidat for skyggekapital")
        else:
            # No data: explain why
            lines.append(
                f"  {bar} 0/{min_s} utfall"
            )
            lines.append(f"  Venter på regime: {regime_names}")

        lines.append("")

    # Data freshness warning
    if not results['indicators']['pass']:
        lines.append(
            "⚠ Indikatordata er foreldet. "
            "Verifiser FHQ_INDICATOR_PULSE i Task Scheduler."
        )
        lines.append("")

    # Pending outcomes
    pending = results['outcomes']['pending_evaluable']
    if pending > 0:
        lines.append(
            f"⏳ {pending} triggere venter på at tidsfristen utløper "
            f"før vi kan måle utfallet."
        )
        lines.append("")

    return lines


def build_next_best_action(results: dict) -> list:
    """Meta-analysert neste beste handling for å nå omsetning og avkastning."""
    lines = []
    pipe = results['pipeline']
    regime_counts = pipe.get('regime_counts', {})
    total_outcomes = pipe['total_outcomes']
    total_wins = pipe.get('total_wins', 0)
    has_zombies = not results.get('zombies', {}).get('pass', True)

    # Identify the most advanced experiment
    active = [e for e in pipe['experiments'] if e['outcomes'] > 0]
    waiting = [e for e in pipe['experiments'] if e['outcomes'] == 0]

    # 1. What is the single most important thing right now?
    if total_outcomes == 0:
        lines.append(
            "Vi har null utfall. Systemet samler data. "
            "Det viktigste nå er tålmodighet — vi venter på at "
            "markedet gir oss de riktige forholdene."
        )
    elif total_outcomes < 30:
        best = max(active, key=lambda e: e['outcomes'])
        letter = _test_letter(best['code'])
        remaining = best['min_sample'] - best['outcomes']
        lines.append(
            f"Vi er i læringsmodus. Test {letter} leder med "
            f"{best['outcomes']}/{best['min_sample']} utfall. "
            f"{remaining} gjenstår før vi kan konkludere statistisk."
        )
    else:
        overall_wr = round(100 * total_wins / total_outcomes) if total_outcomes > 0 else 0
        lines.append(
            f"Vi har {total_outcomes} utfall totalt med "
            f"{overall_wr}% samlet treffsikkerhet. "
            f"Statistisk terskel er nådd."
        )

    # 2. Regime context — explain *why* some tests don't trigger
    bear_stress = regime_counts.get('BEAR', 0) + regime_counts.get('STRESS', 0)
    bull = regime_counts.get('BULL', 0)
    neutral = regime_counts.get('NEUTRAL', 0)
    total_r = sum(regime_counts.values()) if regime_counts else 1

    if bear_stress > 0 and total_r > 0:
        bear_pct = round(100 * bear_stress / total_r)
        lines.append(
            f"Markedsklima: {bear_pct}% av aktivaene er i nedgang/stress. "
            f"Det betyr at test F (panikk-bunn) får flest triggere nå, "
            f"mens test B og E (som trenger oppgang) må vente."
        )

    # 3. Promoted experiment — closest to revenue
    promoted = [e for e in pipe['experiments'] if e.get('promoted')]
    if promoted:
        p = promoted[0]
        letter = _test_letter(p['code'])
        remaining = p['min_sample'] - p['outcomes']
        wr = p['win_rate']
        threshold = _extract_threshold(p.get('falsification_rule'))
        if wr is not None and threshold > 0 and wr >= threshold:
            lines.append(
                f"Test {letter} er promotert og holder {wr:.0f}% "
                f"(over {threshold:.0f}%-terskelen). "
                f"Når vi når {p['min_sample']} utfall, er neste steg "
                f"skyggekapital — papirhandel med realistiske beløp."
            )
        elif wr is not None:
            lines.append(
                f"Test {letter} er promotert men ligger på {wr:.0f}% "
                f"(trenger ≥{threshold:.0f}%). Vi samler flere utfall "
                f"før vi konkluderer — {remaining} gjenstår."
            )

    # 4. Concrete next action
    actions = []
    if has_zombies:
        zombie_names = [z['name'] for z in results.get('zombies', {}).get('zombies', [])]
        actions.append(
            "Restart zombie-daemons: " + ", ".join(zombie_names)
        )
    if not results['indicators']['pass']:
        actions.append(
            "Indikatordata er foreldet. Verifiser FHQ_INDICATOR_PULSE "
            "i Task Scheduler (06:00 daglig). "
            "Uten ferske data stopper hele pipelinen."
        )
    pulse = results.get('indicator_pulse', {})
    if pulse and not pulse.get('pass', True):
        actions.append(
            f"PULSE-sentinel: {pulse.get('status', 'UNKNOWN')}. "
            f"{pulse.get('detail', '')}"
        )

    if actions:
        lines.append("→ Handling: " + ". ".join(actions) + ".")
    elif total_outcomes < 30:
        lines.append(
            "→ Handling: Ingen manuell inngripen nødvendig. "
            "Systemet samler data automatisk. "
            "Neste milepæl: 30 utfall samlet = statistisk grunnlag."
        )
    else:
        lines.append(
            "→ Handling: Evaluer om promoterte eksperimenter "
            "kvalifiserer for skyggekapital-allokering."
        )

    return lines


# Norwegian source name mapping
SOURCE_NAMES = {
    'momentum': 'momentum',
    'volatility': 'volatilitet',
    'price_series': 'prisdata',
}

# Norwegian DEFCON mapping
DEFCON_LABELS = {
    'GREEN': 'GRØNN',
    'YELLOW': 'GUL',
    'RED': 'RØD',
}


def build_telegram_message(results: dict, conn=None) -> str:
    """Build Norwegian HTML-formatted morning verification report."""
    now_oslo = datetime.now(timezone(timedelta(hours=1)))

    check_keys = ('indicators', 'outcomes', 'zombies', 'pipeline', 'pipeline_health')
    all_pass = all(results[k]['pass'] for k in check_keys if k in results)
    verdict = "ALT OPERATIVT" if all_pass else "KREVER HANDLING"
    verdict_icon = "\u2705" if all_pass else "\u274c"

    date_str = now_oslo.strftime('%d. %b %Y kl. %H:%M').lstrip('0')
    lines = [
        f"<b>FASE 2 MORGENRAPPORT</b>",
        f"<i>{date_str} CET</i>",
        f"",
        f"{verdict_icon} <b>SYSTEMSTATUS: {verdict}</b>",
    ]

    # 1. DATAKVALITET
    ind = results['indicators']
    lines.append(f"\n━━━ <b>1. DATAKVALITET</b> ━━━")
    for src, data in ind['sources'].items():
        sflag = "✓" if data['fresh'] else "✗"
        label = SOURCE_NAMES.get(src, src)
        lines.append(f"{sflag} {label}: {data['max_date']} ({data['assets']} aktiva)")

    # 1b. INDICATOR PULSE
    if 'indicator_pulse' in results:
        pulse = results['indicator_pulse']
        pulse_icon = "\u2713" if pulse['pass'] else "\u2717"
        lines.append(f"{pulse_icon} Indikator-PULSE: {pulse['status']}")
        if pulse.get('hours_since_success') is not None:
            lines.append(f"  Siste vellykkede kjøring: {pulse['hours_since_success']}t siden")

    # 2. UTFALLSMOTOR
    out = results['outcomes']
    lines.append(f"\n━━━ <b>2. UTFALLSMOTOR</b> ━━━")
    daemon_age = out['daemon_age_hours']
    if out['daemon_status'] in ('HEALTHY', 'RUNNING') and daemon_age is not None and float(daemon_age) < ZOMBIE_THRESHOLD_HOURS:
        lines.append(f"Status: FRISK ({daemon_age}t siden sist)")
    else:
        lines.append(f"Status: <code>{out['daemon_status']}</code> ({daemon_age}t siden sist)")
    lines.append(f"Utfall siste 24t: {out['recent_outcomes_24h']}")
    lines.append(f"Ventende evalueringer: {out['pending_evaluable']}")

    # 3. PROSESSOVERVÅKING
    zom = results['zombies']
    lines.append(f"\n━━━ <b>3. PROSESSOVERVÅKING</b> ━━━")
    lines.append(f"Aktive: {zom['alive']}/{zom['total_daemons']} | Stoppet: {zom['dead']}")
    if zom['zombies']:
        for z in zom['zombies']:
            lines.append(f"⚠️ <code>{z['name']}</code> ({z['age_hours']}t foreldet)")
    else:
        lines.append("Ingen zombier oppdaget")

    # 4. EKSPERIMENTSTATUS — compact overview
    pipe = results['pipeline']
    gate_label = "ÅPEN" if pipe['gate'] == 'OPEN' else pipe['gate']
    defcon_raw = str(pipe.get('defcon', 'UNKNOWN')).upper()
    defcon_label = DEFCON_LABELS.get(defcon_raw, defcon_raw)
    lines.append(f"\n━━━ <b>4. EKSPERIMENTSTATUS</b> ━━━")
    lines.append(f"Gate: {gate_label} | DEFCON: {defcon_label}")
    lines.append(f"Totalt: {pipe['total_triggers']} triggere, {pipe['total_outcomes']} utfall")
    lines.append("")
    for exp in pipe['experiments']:
        label = get_experiment_status_label(exp)
        lines.append(f"<code>{exp['code']}</code> [{label}]  T:{exp['triggers']}  O:{exp['outcomes']}")

    # 5. FREMGANG MOT MÅL — per experiment
    assessment = build_assessment(results)
    if assessment:
        lines.append(f"\n━━━ <b>5. FREMGANG MOT MÅL</b> ━━━")
        for ln in assessment:
            lines.append(ln)

    # 6. NESTE BESTE HANDLING
    nba = build_next_best_action(results)
    if nba:
        lines.append(f"━━━ <b>6. NESTE BESTE HANDLING</b> ━━━")
        for ln in nba:
            lines.append(ln)

    # 7. PIPELINE MOT KAPITAL
    if 'pipeline_health' in results:
        ph = results['pipeline_health']
        lines.append(f"\n━━━ <b>7. PIPELINE MOT KAPITAL</b> ━━━")
        for s in ph['steps']:
            icon = "✓" if s['count'] > 0 else "✗"
            lines.append(f"{icon} {s['step']}. {s['name']}  {s['detail']}")
        lines.append(f"\n<i>Neste milepæl: {ph['next_milestone']}</i>")
        lines.append(f"Aktive steg: {ph['active_steps']}/{ph['total_steps']}")

    lines.append(f"\n— <i>STIG, CTO FjordHQ</i>")

    return "\n".join(lines)


def run_verification(send_tg: bool = True) -> dict:
    """Execute all 4 verification checks."""
    logger.info("=" * 50)
    logger.info("PHASE 2 MORNING VERIFICATION")
    logger.info("=" * 50)

    conn = psycopg2.connect(**DB_CONFIG)

    try:
        results = {
            'indicators': check_indicator_freshness(conn),
            'indicator_pulse': check_indicator_pulse_health(conn),
            'outcomes': check_outcome_daemon(conn),
            'zombies': check_zombie_daemons(conn),
            'pipeline': check_experiment_pipeline(conn),
            'pipeline_health': check_pipeline_health(conn),
        }

        # D5 fail-closed: if PULSE is stale, override indicator freshness to FAIL
        if not results['indicator_pulse']['pass']:
            if results['indicators']['pass']:
                results['indicators']['pass'] = False
                results['indicators']['override_reason'] = (
                    'FAIL-CLOSED: indicator_pulse audit trail shows '
                    + results['indicator_pulse'].get('status', 'UNKNOWN')
                    + '. Data freshness cannot be trusted without verified pipeline.'
                )
                logger.warning("FAIL-CLOSED: Indicator freshness overridden by PULSE sentinel")

        all_pass = all(r['pass'] for r in results.values())
        results['overall'] = 'PASS' if all_pass else 'FAIL'
        results['timestamp'] = datetime.now(timezone.utc).isoformat()

        # Log summary
        for name, data in results.items():
            if isinstance(data, dict) and 'pass' in data:
                status = "PASS" if data['pass'] else "FAIL"
                logger.info(f"  [{status}] {name}")

        logger.info(f"Overall: {results['overall']}")

        # Send Telegram
        if send_tg:
            msg = build_telegram_message(results)
            sent = send_telegram(msg)
            results['telegram_sent'] = sent
            if sent:
                logger.info("Telegram report sent to CEO")
            else:
                logger.warning("Telegram send failed")
        else:
            logger.info("Telegram disabled (--check mode)")

        return results

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Phase 2 Morning Verification')
    parser.add_argument('--check', action='store_true', help='Check only, no Telegram')
    parser.add_argument('--test', action='store_true', help='Send test message')
    args = parser.parse_args()

    if args.test:
        result = send_telegram(
            "<b>PHASE 2 MORNING VERIFICATION</b>\n"
            "<i>Test message</i>\n\n"
            "\u2705 Telegram integration working\n\n"
            "<i>STIG - Phase 2 Verification</i>"
        )
        print(f"Test message sent: {result}")
        sys.exit(0 if result else 1)

    results = run_verification(send_tg=not args.check)

    # Write evidence
    evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
    os.makedirs(evidence_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    evidence_path = os.path.join(evidence_dir, f'MORNING_VERIFICATION_{ts}.json')
    with open(evidence_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    logger.info(f"Evidence: {evidence_path}")

    sys.exit(0 if results['overall'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
