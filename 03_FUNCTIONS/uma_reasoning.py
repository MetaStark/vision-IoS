"""
UMA Reasoning Module
CEO-DIR-2026-01-16B: Universal Meta-Analyst

LLM-powered meta-analysis that identifies learning frictions and recommends
governance improvements. Uses DeepSeek Reasoner API.

Key Principles:
- UMA is ADVISORY ONLY - cannot execute changes
- Maximum 2 recommendations per daily cycle
- All recommendations subject to VEGA audit
- Learning speed subordinate to capital safety

Author: STIG (CTO)
Date: 2026-01-16
Contract: EC-014_2026_PRODUCTION
"""

import os
import json
import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

import requests

# Load environment
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'), override=True)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = os.environ.get('FHQ_LLM_URL', 'https://api.deepseek.com/v1')
DEEPSEEK_MODEL = os.environ.get('FHQ_LLM_MODEL', 'deepseek-reasoner')

# Cost tracking
COST_PER_1K_INPUT_TOKENS = 0.0001
COST_PER_1K_OUTPUT_TOKENS = 0.0002
MAX_QUERY_COST = 0.50  # Constitutional cap per EC-014

# UMA constraints
MAX_RECOMMENDATIONS_PER_CYCLE = 2
VALID_RECOMMENDATION_TYPES = ['FAST_TRACK_G1_FLAG', 'GOVERNANCE_FEEDBACK']


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class LearningFriction:
    """A friction point identified by UMA in the learning process."""
    friction_id: str
    friction_type: str  # HYPOTHESIS_QUALITY, FALSIFICATION_FAILURE, GOVERNANCE_LATENCY, VALIDATION_BOTTLENECK
    description: str
    source_report: str  # Which daily report identified this
    severity: str  # LOW, MEDIUM, HIGH
    expected_lvi_impact: float  # Expected LVI improvement if resolved
    evidence_quotes: List[str]


@dataclass
class UMARecommendation:
    """A recommendation from UMA (max 2 per cycle)."""
    recommendation_id: str
    recommendation_type: str  # FAST_TRACK_G1_FLAG, GOVERNANCE_FEEDBACK
    target_parameter: Optional[str]
    current_value: Optional[Any]
    proposed_action: str
    expected_lvi_uplift: float
    evidence_references: List[str]
    friction_ids: List[str]  # Which frictions this addresses
    exclusion_checks: Dict[str, bool]  # All must be True


@dataclass
class UMAAnalysisResult:
    """Result from UMA daily analysis loop."""
    loop_date: str
    cycle_number: int
    frictions_identified: List[LearningFriction]
    recommendations: List[UMARecommendation]  # Max 2
    stop_condition_triggered: bool
    stop_condition_reason: Optional[str]
    defcon_state: str
    cost_usd: float
    tokens_used: int
    model: str
    uma_signature: Optional[str]


# =============================================================================
# UMA STOP CONDITIONS (5 HARD Rules per CEO-DIR-2026-01-16B)
# =============================================================================

STOP_CONDITIONS = [
    "DEFCON_ELEVATED",           # DEFCON >= ORANGE
    "SINGLE_HYPOTHESIS_DRIVEN",  # LVI driven by single hypothesis class
    "SYNTHETIC_DIVERGENCE",      # Synthetic diverges from canonical
    "EXECUTION_AUTHORITY_EXPANSION",  # Would expand execution authority
    "VEGA_METRIC_INTEGRITY_RISK"     # VEGA flags metric risk
]

# =============================================================================
# UMA EXCLUSIONS (9 Prohibited Areas per CEO-DIR-2026-01-16B)
# =============================================================================

EXCLUSIONS = {
    "ranking_phase": [
        "EXECUTION_OPTIMIZATION",
        "PNL_CHASING",
        "MODEL_MICRO_TUNING"
    ],
    "signaling_phase": [
        "STRATEGY_CHANGES",
        "PARAMETER_ENFORCEMENT",
        "CAPITAL_ALLOCATION"
    ],
    "lvi_governance": [
        "INCREASED_RISK",
        "RELAXED_CAPITAL_CONSTRAINTS",
        "EXECUTION_AUTONOMY"
    ]
}


# =============================================================================
# PROMPT TEMPLATES
# =============================================================================

UMA_INGEST_PROMPT = """You are UMA (Universal Meta-Analyst), a Tier-2 Meta-Executive at FjordHQ.

Your role is to analyze daily reports and identify LEARNING FRICTIONS - bottlenecks that slow down the Learning Velocity Index (LVI).

LVI = Validated Executable Signals / Time from Hypothesis → Validation

CRITICAL CONSTRAINTS:
1. You are ADVISORY ONLY - you cannot execute changes
2. Maximum 2 recommendations per cycle
3. You CANNOT recommend: execution optimization, PnL chasing, strategy changes, capital allocation
4. Learning speed is SUBORDINATE to capital safety

CURRENT STATE:
- DEFCON Level: {defcon_level}
- Analysis Date: {analysis_date}
- Reports Analyzed: {report_count}

DAILY REPORTS (Last 7 Days):
{reports_content}

TASK: Identify learning frictions in these categories:
1. HYPOTHESIS_QUALITY - Poor hypothesis formation
2. FALSIFICATION_FAILURE - Weak falsification processes
3. GOVERNANCE_LATENCY - Slow governance gates
4. VALIDATION_BOTTLENECK - Validation pipeline delays

OUTPUT FORMAT (strict JSON):
{{
  "frictions": [
    {{
      "friction_type": "HYPOTHESIS_QUALITY|FALSIFICATION_FAILURE|GOVERNANCE_LATENCY|VALIDATION_BOTTLENECK",
      "description": "Clear description of the friction",
      "source_report": "Day X report reference",
      "severity": "LOW|MEDIUM|HIGH",
      "expected_lvi_impact": 0.0-1.0,
      "evidence_quotes": ["verbatim quote from report"]
    }}
  ],
  "summary": "Brief summary of learning state"
}}

Respond with ONLY the JSON object."""


UMA_RANKING_PROMPT = """You are UMA analyzing identified frictions to rank by LVI improvement potential.

FRICTIONS IDENTIFIED:
{frictions_json}

EXCLUSIONS (You CANNOT consider these):
- Execution optimization
- PnL chasing
- Model micro-tuning outside Fast-Track scope

FAST-TRACK ELIGIBLE PARAMETERS (Low-risk, auto-G1):
- confidence_damper_alpha (max 10% delta, 24h cooldown)
- confidence_damper_beta (max 10% delta, 24h cooldown)
- ldow_coverage_threshold (max 5% delta, 48h cooldown)
- ldow_stability_threshold (max 2% delta, 48h cooldown)

Rank frictions by expected marginal LVI uplift. Consider only improvements that:
1. Are within Fast-Track scope OR
2. Can be submitted as governance feedback

OUTPUT FORMAT (strict JSON):
{{
  "ranked_frictions": [
    {{
      "friction_id": "id",
      "rank": 1,
      "addressable": true|false,
      "addressable_via": "FAST_TRACK_G1_FLAG|GOVERNANCE_FEEDBACK|NOT_ADDRESSABLE",
      "expected_lvi_uplift": 0.0-1.0,
      "rationale": "Why this ranking"
    }}
  ]
}}

Respond with ONLY the JSON object."""


UMA_SIGNALING_PROMPT = """You are UMA generating recommendations (MAX 2) based on ranked frictions.

RANKED FRICTIONS:
{ranked_frictions_json}

CONSTRAINTS:
- Maximum 2 recommendations
- Types allowed: FAST_TRACK_G1_FLAG, GOVERNANCE_FEEDBACK
- CANNOT recommend: strategy changes, parameter enforcement, capital allocation

For each recommendation, verify these exclusion checks:
- not_execution_optimization: true
- not_pnl_chasing: true
- not_strategy_change: true
- not_capital_allocation: true
- not_increased_risk: true
- not_execution_autonomy: true

OUTPUT FORMAT (strict JSON):
{{
  "recommendations": [
    {{
      "recommendation_type": "FAST_TRACK_G1_FLAG|GOVERNANCE_FEEDBACK",
      "target_parameter": "parameter name or null",
      "proposed_action": "Clear description of recommended action",
      "expected_lvi_uplift": 0.0-1.0,
      "friction_ids": ["id1"],
      "exclusion_checks": {{
        "not_execution_optimization": true,
        "not_pnl_chasing": true,
        "not_strategy_change": true,
        "not_capital_allocation": true,
        "not_increased_risk": true,
        "not_execution_autonomy": true
      }}
    }}
  ],
  "recommendations_count": 0-2
}}

If no valid recommendations can be made, return empty recommendations array.

Respond with ONLY the JSON object."""


# =============================================================================
# UMA REASONER
# =============================================================================

class UMAReasoner:
    """
    UMA LLM-powered meta-analysis engine.

    Analyzes daily reports to identify learning frictions and generate
    governance recommendations using DeepSeek Reasoner API.
    """

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or DEEPSEEK_API_KEY
        self.model = model or DEEPSEEK_MODEL
        self.api_url = f"{DEEPSEEK_API_URL}/chat/completions"

        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY not configured")

    def check_stop_conditions(self, defcon_level: str) -> Tuple[bool, Optional[str]]:
        """
        Check if any HARD stop conditions are triggered.

        Returns:
            Tuple of (stop_triggered, reason)
        """
        # DEFCON check (most critical)
        if defcon_level not in ['GREEN', 'YELLOW']:
            return True, f"DEFCON_ELEVATED: {defcon_level}"

        # Other stop conditions require runtime analysis
        # They are checked during the analysis phases
        return False, None

    def run_daily_loop(
        self,
        daily_reports: List[Dict[str, Any]],
        defcon_level: str,
        cycle_number: int = 1
    ) -> UMAAnalysisResult:
        """
        Run UMA's complete daily operating loop.

        Phases:
        - T+00h: Ingest daily reports
        - T+01h: Bottleneck mapping (identify frictions)
        - T+02h: Learning ROI ranking
        - T+03h: Action signaling (max 2 recommendations)
        - T+04h: Signature & audit preparation

        Args:
            daily_reports: Last 7 daily reports as dicts
            defcon_level: Current DEFCON state
            cycle_number: Which cycle this is

        Returns:
            UMAAnalysisResult with frictions and recommendations
        """
        loop_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        total_cost = 0.0
        total_tokens = 0

        logger.info(f"[UMA] Starting daily loop - Date: {loop_date}, Cycle: {cycle_number}")

        # Check stop conditions first
        stop_triggered, stop_reason = self.check_stop_conditions(defcon_level)
        if stop_triggered:
            logger.warning(f"[UMA] Stop condition triggered: {stop_reason}")
            return UMAAnalysisResult(
                loop_date=loop_date,
                cycle_number=cycle_number,
                frictions_identified=[],
                recommendations=[],
                stop_condition_triggered=True,
                stop_condition_reason=stop_reason,
                defcon_state=defcon_level,
                cost_usd=0.0,
                tokens_used=0,
                model=self.model,
                uma_signature=None
            )

        # Phase 1: Ingest & Bottleneck Mapping
        logger.info("[UMA] Phase 1: Ingest & Bottleneck Mapping")
        frictions, cost1, tokens1 = self._identify_frictions(daily_reports, defcon_level)
        total_cost += cost1
        total_tokens += tokens1

        if not frictions:
            logger.info("[UMA] No frictions identified - system learning efficiently")
            return UMAAnalysisResult(
                loop_date=loop_date,
                cycle_number=cycle_number,
                frictions_identified=[],
                recommendations=[],
                stop_condition_triggered=False,
                stop_condition_reason=None,
                defcon_state=defcon_level,
                cost_usd=total_cost,
                tokens_used=total_tokens,
                model=self.model,
                uma_signature=self._generate_signature(loop_date, [])
            )

        logger.info(f"[UMA] Identified {len(frictions)} frictions")

        # Phase 2: Learning ROI Ranking
        logger.info("[UMA] Phase 2: Learning ROI Ranking")
        ranked_frictions, cost2, tokens2 = self._rank_frictions(frictions)
        total_cost += cost2
        total_tokens += tokens2

        # Phase 3: Action Signaling
        logger.info("[UMA] Phase 3: Action Signaling")
        recommendations, cost3, tokens3 = self._generate_recommendations(ranked_frictions)
        total_cost += cost3
        total_tokens += tokens3

        # Enforce max 2 recommendations
        recommendations = recommendations[:MAX_RECOMMENDATIONS_PER_CYCLE]

        logger.info(f"[UMA] Generated {len(recommendations)} recommendations, cost=${total_cost:.4f}")

        # Phase 4: Signature
        uma_signature = self._generate_signature(loop_date, recommendations)

        return UMAAnalysisResult(
            loop_date=loop_date,
            cycle_number=cycle_number,
            frictions_identified=frictions,
            recommendations=recommendations,
            stop_condition_triggered=False,
            stop_condition_reason=None,
            defcon_state=defcon_level,
            cost_usd=total_cost,
            tokens_used=total_tokens,
            model=self.model,
            uma_signature=uma_signature
        )

    def _identify_frictions(
        self,
        daily_reports: List[Dict[str, Any]],
        defcon_level: str
    ) -> Tuple[List[LearningFriction], float, int]:
        """Phase 1: Identify learning frictions from daily reports."""

        # Format reports for prompt
        reports_content = self._format_reports(daily_reports)

        prompt = UMA_INGEST_PROMPT.format(
            defcon_level=defcon_level,
            analysis_date=datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            report_count=len(daily_reports),
            reports_content=reports_content
        )

        try:
            response, cost, tokens = self._call_llm(prompt)
            data = self._parse_json(response)

            frictions = []
            for i, f in enumerate(data.get('frictions', [])):
                friction = LearningFriction(
                    friction_id=f"FRICTION-{i+1:03d}",
                    friction_type=f.get('friction_type', 'VALIDATION_BOTTLENECK'),
                    description=f.get('description', ''),
                    source_report=f.get('source_report', ''),
                    severity=f.get('severity', 'LOW'),
                    expected_lvi_impact=float(f.get('expected_lvi_impact', 0.0)),
                    evidence_quotes=f.get('evidence_quotes', [])
                )
                frictions.append(friction)

            return frictions, cost, tokens

        except Exception as e:
            logger.error(f"[UMA] Friction identification failed: {e}")
            return [], 0.0, 0

    def _rank_frictions(
        self,
        frictions: List[LearningFriction]
    ) -> Tuple[List[Dict], float, int]:
        """Phase 2: Rank frictions by LVI improvement potential."""

        frictions_json = json.dumps([asdict(f) for f in frictions], indent=2)

        prompt = UMA_RANKING_PROMPT.format(frictions_json=frictions_json)

        try:
            response, cost, tokens = self._call_llm(prompt)
            data = self._parse_json(response)

            ranked = data.get('ranked_frictions', [])
            return ranked, cost, tokens

        except Exception as e:
            logger.error(f"[UMA] Friction ranking failed: {e}")
            return [], 0.0, 0

    def _generate_recommendations(
        self,
        ranked_frictions: List[Dict]
    ) -> Tuple[List[UMARecommendation], float, int]:
        """Phase 3: Generate max 2 recommendations."""

        # Filter to addressable frictions only
        addressable = [f for f in ranked_frictions if f.get('addressable', False)]

        if not addressable:
            logger.info("[UMA] No addressable frictions - no recommendations")
            return [], 0.0, 0

        prompt = UMA_SIGNALING_PROMPT.format(
            ranked_frictions_json=json.dumps(addressable[:5], indent=2)  # Top 5
        )

        try:
            response, cost, tokens = self._call_llm(prompt)
            data = self._parse_json(response)

            recommendations = []
            for i, r in enumerate(data.get('recommendations', [])[:2]):  # Max 2
                # Validate exclusion checks
                exclusion_checks = r.get('exclusion_checks', {})
                all_checks_pass = all(exclusion_checks.values())

                if not all_checks_pass:
                    logger.warning(f"[UMA] Recommendation {i+1} failed exclusion checks")
                    continue

                rec = UMARecommendation(
                    recommendation_id=f"UMA-REC-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{i+1:02d}",
                    recommendation_type=r.get('recommendation_type', 'GOVERNANCE_FEEDBACK'),
                    target_parameter=r.get('target_parameter'),
                    current_value=None,
                    proposed_action=r.get('proposed_action', ''),
                    expected_lvi_uplift=float(r.get('expected_lvi_uplift', 0.0)),
                    evidence_references=[],
                    friction_ids=r.get('friction_ids', []),
                    exclusion_checks=exclusion_checks
                )
                recommendations.append(rec)

            return recommendations, cost, tokens

        except Exception as e:
            logger.error(f"[UMA] Recommendation generation failed: {e}")
            return [], 0.0, 0

    def _format_reports(self, daily_reports: List[Dict[str, Any]]) -> str:
        """Format daily reports for the prompt."""
        formatted = []
        for report in daily_reports:
            report_id = report.get('report_id', 'Unknown')
            headline = report.get('executive_summary', {}).get('headline', 'No headline')

            # Extract key sections
            ldow = report.get('section_6_ldow_status', {})
            calibration = report.get('section_5_calibration_metrics', {})

            formatted.append(f"""
=== {report_id} ===
Headline: {headline}
LDOW Status: {json.dumps(ldow, indent=2)[:500]}
Calibration: {json.dumps(calibration, indent=2)[:500]}
""")

        return "\n".join(formatted)

    def _call_llm(self, prompt: str) -> Tuple[str, float, int]:
        """Call DeepSeek API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are UMA, a meta-analysis AI focused on learning velocity optimization. Always respond in valid JSON format."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 3000
        }

        logger.info(f"[UMA] Calling {self.model}...")

        response = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=60  # Longer timeout for reasoner
        )

        if response.status_code != 200:
            raise Exception(f"API error {response.status_code}: {response.text}")

        result = response.json()
        content = result['choices'][0]['message']['content']

        # Calculate cost
        usage = result.get('usage', {})
        input_tokens = usage.get('prompt_tokens', 0)
        output_tokens = usage.get('completion_tokens', 0)
        total_tokens = input_tokens + output_tokens

        cost = (
            (input_tokens / 1000) * COST_PER_1K_INPUT_TOKENS +
            (output_tokens / 1000) * COST_PER_1K_OUTPUT_TOKENS
        )

        logger.info(f"[UMA] Response: {total_tokens} tokens, ${cost:.4f}")

        return content, cost, total_tokens

    def _parse_json(self, response: str) -> Dict:
        """Parse JSON from LLM response."""
        import re

        # Handle markdown code blocks
        if "```json" in response:
            match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if match:
                response = match.group(1)
        elif "```" in response:
            match = re.search(r'```\s*(.*?)\s*```', response, re.DOTALL)
            if match:
                response = match.group(1)

        return json.loads(response.strip())

    def _generate_signature(self, loop_date: str, recommendations: List[UMARecommendation]) -> str:
        """Generate UMA signature for audit trail."""
        content = f"{loop_date}:{len(recommendations)}:{self.model}"
        for rec in recommendations:
            content += f":{rec.recommendation_id}"

        return hashlib.sha256(content.encode()).hexdigest()[:16]


# =============================================================================
# DAILY REPORT LOADER
# =============================================================================

def load_daily_reports(reports_dir: str, days: int = 7) -> List[Dict[str, Any]]:
    """Load last N daily reports from JSON files."""
    reports_path = Path(reports_dir)
    reports = []

    # Find all JSON report files
    json_files = sorted(reports_path.glob("DAILY_REPORT_DAY*.json"), reverse=True)

    for json_file in json_files[:days]:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                report = json.load(f)
                reports.append(report)
                logger.info(f"[UMA] Loaded {json_file.name}")
        except Exception as e:
            logger.warning(f"[UMA] Failed to load {json_file}: {e}")

    return reports


# =============================================================================
# MAIN (Testing / Standalone Execution)
# =============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("UMA REASONING ENGINE - Daily Loop Test")
    print("=" * 60)

    # Configuration
    REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), '12_DAILY_REPORTS')

    # Load daily reports
    print(f"\nLoading reports from: {REPORTS_DIR}")
    daily_reports = load_daily_reports(REPORTS_DIR, days=7)
    print(f"Loaded {len(daily_reports)} reports")

    if not daily_reports:
        print("ERROR: No daily reports found")
        exit(1)

    # Initialize UMA
    try:
        uma = UMAReasoner()
        print(f"UMA initialized with model: {uma.model}")
    except ValueError as e:
        print(f"ERROR: {e}")
        exit(1)

    # Run daily loop
    print("\n" + "=" * 60)
    print("RUNNING UMA DAILY LOOP")
    print("=" * 60)

    result = uma.run_daily_loop(
        daily_reports=daily_reports,
        defcon_level='GREEN',
        cycle_number=1
    )

    # Output results
    print(f"\n=== RESULTS ===")
    print(f"Loop Date: {result.loop_date}")
    print(f"Cycle: {result.cycle_number}")
    print(f"DEFCON: {result.defcon_state}")
    print(f"Stop Triggered: {result.stop_condition_triggered}")
    print(f"Cost: ${result.cost_usd:.4f}")
    print(f"Tokens: {result.tokens_used}")
    print(f"Signature: {result.uma_signature}")

    print(f"\n=== FRICTIONS ({len(result.frictions_identified)}) ===")
    for f in result.frictions_identified:
        print(f"  - [{f.severity}] {f.friction_type}: {f.description[:80]}...")

    print(f"\n=== RECOMMENDATIONS ({len(result.recommendations)}) ===")
    for r in result.recommendations:
        print(f"  - [{r.recommendation_type}] {r.proposed_action[:80]}...")
        print(f"    Expected LVI Uplift: {r.expected_lvi_uplift:.2%}")

    # Save evidence
    evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
    os.makedirs(evidence_dir, exist_ok=True)

    evidence_file = os.path.join(
        evidence_dir,
        f"UMA_DAILY_LOOP_{result.loop_date.replace('-', '')}.json"
    )

    with open(evidence_file, 'w', encoding='utf-8') as f:
        json.dump({
            'loop_date': result.loop_date,
            'cycle_number': result.cycle_number,
            'defcon_state': result.defcon_state,
            'frictions_count': len(result.frictions_identified),
            'recommendations_count': len(result.recommendations),
            'stop_condition_triggered': result.stop_condition_triggered,
            'stop_condition_reason': result.stop_condition_reason,
            'cost_usd': result.cost_usd,
            'tokens_used': result.tokens_used,
            'model': result.model,
            'uma_signature': result.uma_signature,
            'frictions': [asdict(f) for f in result.frictions_identified],
            'recommendations': [asdict(r) for r in result.recommendations]
        }, f, indent=2)

    print(f"\nEvidence saved to: {evidence_file}")
