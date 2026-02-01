"""
MBB CORPORATE STANDARDS COMPLIANCE CHECKER
==========================================
ADR-023: MBB Corporate Standards Integration

Validates reports and evidence artifacts against McKinsey, BCG, Bain
corporate communication standards:

1. Pyramid Principle (answer first, then support)
2. MECE Framework (mutually exclusive, collectively exhaustive)
3. Evidence-Based Decision Making (every claim has evidence)
4. "So What?" Test (every data point has impact statement)
5. 80/20 Rule (focus on high-impact factors)

Authority: STIG (CTO)
Reference: ADR-023
"""

import json
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class ComplianceResult:
    """MBB compliance check result"""
    check_name: str
    passed: bool
    score: float  # 0.0 to 1.0
    issues: List[str]
    recommendations: List[str]


class MBBComplianceChecker:
    """
    Validate reports against MBB corporate standards

    Usage:
        checker = MBBComplianceChecker()
        result = checker.validate_report(report_dict)
        print(f"Compliance Score: {result['compliance_score']:.1%}")
    """

    def __init__(self, min_passing_score: float = 0.90):
        self.min_passing_score = min_passing_score

    def validate_report(self, report: Dict) -> Dict:
        """
        Run all MBB compliance checks

        Returns:
            {
                "compliance_score": float (0.0 to 1.0),
                "passing": bool,
                "checks": {
                    "pyramid_structure": ComplianceResult,
                    "mece_compliance": ComplianceResult,
                    ...
                },
                "recommendations": List[str],
                "timestamp": str
            }
        """
        checks = {
            "pyramid_structure": self.check_pyramid(report),
            "mece_compliance": self.check_mece(report),
            "evidence_chain": self.check_evidence(report),
            "so_what_coverage": self.check_so_what(report),
            "pareto_focus": self.check_80_20(report)
        }

        # Calculate overall score
        scores = [check.score for check in checks.values()]
        compliance_score = sum(scores) / len(scores) if scores else 0.0

        # Aggregate recommendations
        all_recommendations = []
        for check in checks.values():
            all_recommendations.extend(check.recommendations)

        return {
            "compliance_score": compliance_score,
            "passing": compliance_score >= self.min_passing_score,
            "checks": {name: {
                "passed": check.passed,
                "score": check.score,
                "issues": check.issues,
                "recommendations": check.recommendations
            } for name, check in checks.items()},
            "recommendations": all_recommendations,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def check_pyramid(self, report: Dict) -> ComplianceResult:
        """
        Check Pyramid Principle compliance

        Requirements:
        1. Executive summary exists
        2. Executive summary comes first
        3. Executive summary contains: key_decision, rationale, impact, risk
        """
        issues = []
        recommendations = []

        # Check 1: Executive summary exists
        if "executive_summary" not in report:
            issues.append("Missing executive_summary section")
            recommendations.append("Add executive_summary at top of report")
            return ComplianceResult(
                check_name="pyramid_structure",
                passed=False,
                score=0.0,
                issues=issues,
                recommendations=recommendations
            )

        # Check 2: Executive summary comes first
        first_key = list(report.keys())[0]
        if first_key != "executive_summary":
            issues.append(f"Executive summary not first (found: {first_key})")
            recommendations.append("Move executive_summary to top of report structure")

        # Check 3: Required fields
        exec_summary = report["executive_summary"]
        required_fields = ["key_decision", "rationale", "impact", "risk"]
        missing_fields = [f for f in required_fields if f not in exec_summary]

        if missing_fields:
            issues.append(f"Executive summary missing fields: {', '.join(missing_fields)}")
            recommendations.append(f"Add missing fields to executive_summary: {', '.join(missing_fields)}")

        # Score: 0.25 per requirement (4 requirements)
        score = 1.0
        if "executive_summary" not in report:
            score -= 0.25
        if first_key != "executive_summary":
            score -= 0.25
        if missing_fields:
            score -= 0.25 * (len(missing_fields) / len(required_fields))

        return ComplianceResult(
            check_name="pyramid_structure",
            passed=score >= 0.90,
            score=max(0.0, score),
            issues=issues,
            recommendations=recommendations
        )

    def check_mece(self, report: Dict) -> ComplianceResult:
        """
        Check MECE (Mutually Exclusive, Collectively Exhaustive) compliance

        Requirements:
        1. Categories are mutually exclusive (no item in multiple categories)
        2. Categories are collectively exhaustive (all items categorized)
        3. Categories have clear boundaries
        """
        issues = []
        recommendations = []

        # Extract categorized data
        categories = self._extract_categories(report)

        if not categories:
            issues.append("No categorized data found")
            recommendations.append("Structure analysis into MECE categories")
            return ComplianceResult(
                check_name="mece_compliance",
                passed=False,
                score=0.0,
                issues=issues,
                recommendations=recommendations
            )

        # Check mutual exclusivity
        all_items = []
        for category_name, items in categories.items():
            all_items.extend(items)

        duplicates = len(all_items) - len(set(all_items))
        if duplicates > 0:
            issues.append(f"{duplicates} items appear in multiple categories (not mutually exclusive)")
            recommendations.append("Ensure each item belongs to exactly one category")

        # Check for residual category (Type X, Other, Unknown)
        has_residual = any(
            key.lower() in ['type_x', 'other', 'unknown', 'uncategorized']
            for key in categories.keys()
        )

        if not has_residual:
            recommendations.append("Add residual category (e.g., Type X, Other) for edge cases to ensure collective exhaustiveness")

        # Score
        score = 1.0
        if duplicates > 0:
            score -= 0.5  # Major violation
        if not has_residual:
            score -= 0.2  # Minor violation

        return ComplianceResult(
            check_name="mece_compliance",
            passed=score >= 0.90,
            score=max(0.0, score),
            issues=issues,
            recommendations=recommendations
        )

    def check_evidence(self, report: Dict) -> ComplianceResult:
        """
        Check Evidence-Based Decision Making compliance

        Requirements:
        1. Every claim has evidence_id or evidence_reference
        2. Evidence includes raw_query, query_result_hash, timestamp
        3. Evidence chain is verifiable
        """
        issues = []
        recommendations = []

        # Extract claims
        claims = self._extract_claims(report)

        if not claims:
            # No claims found - likely just structured data
            return ComplianceResult(
                check_name="evidence_chain",
                passed=True,
                score=1.0,
                issues=[],
                recommendations=[]
            )

        # Check each claim has evidence
        claims_without_evidence = [
            claim for claim in claims
            if not self._has_evidence_reference(claim)
        ]

        if claims_without_evidence:
            issues.append(f"{len(claims_without_evidence)}/{len(claims)} claims lack evidence references")
            recommendations.append("Add evidence_id or evidence_reference to all claims")

        # Check evidence artifacts
        if "evidence_artifacts" in report or "supporting_evidence" in report:
            evidence = report.get("evidence_artifacts") or report.get("supporting_evidence")

            if isinstance(evidence, list):
                for i, artifact in enumerate(evidence):
                    if not isinstance(artifact, dict):
                        continue

                    # Check required fields
                    required = ["raw_query", "query_result_hash", "timestamp"]
                    missing = [f for f in required if f not in artifact]

                    if missing:
                        issues.append(f"Evidence artifact {i} missing: {', '.join(missing)}")

        # Score
        evidence_coverage = 1.0 - (len(claims_without_evidence) / len(claims)) if claims else 1.0

        return ComplianceResult(
            check_name="evidence_chain",
            passed=evidence_coverage >= 0.90,
            score=evidence_coverage,
            issues=issues,
            recommendations=recommendations
        )

    def check_so_what(self, report: Dict) -> ComplianceResult:
        """
        Check "So What?" Test compliance

        Requirements:
        1. Data points have impact statements
        2. Findings explain business implications
        3. Avoid "data dumps" without context
        """
        issues = []
        recommendations = []

        # Extract data points
        data_points = self._extract_data_points(report)

        if not data_points:
            # No data points found
            return ComplianceResult(
                check_name="so_what_coverage",
                passed=True,
                score=1.0,
                issues=[],
                recommendations=[]
            )

        # Check each data point has impact statement
        data_points_with_impact = sum(
            1 for dp in data_points
            if self._has_impact_statement(dp)
        )

        coverage = data_points_with_impact / len(data_points) if data_points else 1.0

        if coverage < 0.90:
            issues.append(f"Only {coverage:.1%} of data points have impact statements")
            recommendations.append("Add 'So What?' impact statements to all data points")

        # Check for common violations
        violations = self._detect_so_what_violations(report)
        if violations:
            issues.extend(violations)

        return ComplianceResult(
            check_name="so_what_coverage",
            passed=coverage >= 0.90,
            score=coverage,
            issues=issues,
            recommendations=recommendations
        )

    def check_80_20(self, report: Dict) -> ComplianceResult:
        """
        Check 80/20 Rule (Pareto Principle) compliance

        Requirements:
        1. Recommendations focus on high-impact factors (top 20%)
        2. Analysis identifies impact/effort for each factor
        3. Low-impact factors explicitly deprioritized
        """
        issues = []
        recommendations = []

        # Extract factors with impact quantification
        factors = self._extract_factors_with_impact(report)

        if not factors:
            # No factors found - cannot assess 80/20
            return ComplianceResult(
                check_name="pareto_focus",
                passed=True,
                score=1.0,
                issues=[],
                recommendations=["Add impact quantification to enable 80/20 analysis"]
            )

        # Sort by impact (extract numeric value from strings like "$200K+/year")
        def extract_impact_value(factor):
            impact = factor.get('impact') or factor.get('expected_impact') or factor.get('expected_value', '')
            if isinstance(impact, (int, float)):
                return float(impact)
            if isinstance(impact, str):
                # Extract numeric value from strings like "$200K+/year", "+2-3% alpha"
                import re
                numbers = re.findall(r'[\d,]+\.?\d*', impact.replace(',', ''))
                if numbers:
                    return float(numbers[0])
            return 0.0

        sorted_factors = sorted(factors, key=extract_impact_value, reverse=True)
        top_20_percent_count = max(1, int(len(sorted_factors) * 0.2))
        top_20_percent = sorted_factors[:top_20_percent_count]

        # Extract recommendations
        report_recommendations = self._extract_recommendations(report)

        if not report_recommendations:
            issues.append("No recommendations found")
            recommendations.append("Add recommendations section with prioritized actions")
            return ComplianceResult(
                check_name="pareto_focus",
                passed=False,
                score=0.0,
                issues=issues,
                recommendations=recommendations
            )

        # Check if recommendations target high-impact factors
        high_impact_targeted = sum(
            1 for rec in report_recommendations
            if self._targets_high_impact_factor(rec, top_20_percent)
        )

        focus_score = high_impact_targeted / len(report_recommendations) if report_recommendations else 0.0

        if focus_score < 0.80:
            issues.append(f"Only {focus_score:.1%} of recommendations target high-impact factors (top 20%)")
            recommendations.append("Focus recommendations on top 20% of impact factors (Pareto Principle)")

        return ComplianceResult(
            check_name="pareto_focus",
            passed=focus_score >= 0.80,
            score=focus_score,
            issues=issues,
            recommendations=recommendations
        )

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _extract_categories(self, report: Dict) -> Dict[str, List]:
        """Extract categorized data from report"""
        categories = {}

        # Look for common category patterns
        for key, value in report.items():
            # Pattern 1: "type_a", "type_b", "type_c" structure
            if re.match(r'type_[a-z]', key.lower()):
                categories[key] = value if isinstance(value, list) else [value]

            # Pattern 2: Nested dict with "count" or "items"
            if isinstance(value, dict):
                if "count" in value or "items" in value:
                    categories[key] = value.get("items", [])

        return categories

    def _extract_claims(self, report: Dict) -> List[Dict]:
        """Extract claims from report"""
        claims = []

        # Look for sections with claims
        sections_to_check = [
            "key_findings",
            "findings",
            "analysis",
            "recommendations"
        ]

        for section in sections_to_check:
            if section in report:
                content = report[section]

                if isinstance(content, list):
                    claims.extend([c for c in content if isinstance(c, dict)])
                elif isinstance(content, dict):
                    claims.extend([content])

        return claims

    def _has_evidence_reference(self, claim: Dict) -> bool:
        """Check if claim has evidence reference"""
        evidence_keys = ["evidence_id", "evidence_reference", "evidence", "source"]
        return any(key in claim for key in evidence_keys)

    def _extract_data_points(self, report: Dict) -> List[Dict]:
        """Extract data points from report"""
        data_points = []

        def extract_recursive(obj):
            if isinstance(obj, dict):
                # Check if this dict represents a data point
                if any(k in obj for k in ["value", "metric", "count", "percentage"]):
                    data_points.append(obj)

                # Recurse
                for value in obj.values():
                    extract_recursive(value)

            elif isinstance(obj, list):
                for item in obj:
                    extract_recursive(item)

        extract_recursive(report)
        return data_points

    def _has_impact_statement(self, data_point: Dict) -> bool:
        """Check if data point has impact statement"""
        impact_keys = [
            "impact", "so_what", "interpretation",
            "rationale", "significance", "implication"
        ]
        return any(key in data_point for key in impact_keys)

    def _detect_so_what_violations(self, report: Dict) -> List[str]:
        """Detect common 'So What?' violations"""
        violations = []

        # Convert to string for pattern matching
        report_str = json.dumps(report, default=str).lower()

        # Pattern 1: Data without interpretation
        if re.search(r'"value":\s*[\d.]+', report_str):
            if "interpretation" not in report_str and "so_what" not in report_str:
                violations.append("Found numeric values without interpretation or 'So What?' statements")

        return violations

    def _extract_factors_with_impact(self, report: Dict) -> List[Dict]:
        """Extract factors with impact quantification"""
        factors = []

        def extract_recursive(obj, path=""):
            if isinstance(obj, dict):
                # Check if this dict represents a factor with impact
                if "impact" in obj or "expected_impact" in obj:
                    factors.append(obj)

                # Recurse
                for key, value in obj.items():
                    extract_recursive(value, f"{path}.{key}" if path else key)

            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    extract_recursive(item, f"{path}[{i}]")

        extract_recursive(report)
        return factors

    def _extract_recommendations(self, report: Dict) -> List[Dict]:
        """Extract recommendations from report"""
        recommendations = []

        # Look for recommendations section
        sections_to_check = [
            "recommendations",
            "corrective_action_plan",
            "action_items",
            "next_actions"
        ]

        for section in sections_to_check:
            if section in report:
                content = report[section]

                if isinstance(content, list):
                    recommendations.extend([r for r in content if isinstance(r, dict)])
                elif isinstance(content, dict):
                    # Could be dict of recommendations
                    for value in content.values():
                        if isinstance(value, list):
                            recommendations.extend([r for r in value if isinstance(r, dict)])

        return recommendations

    def _targets_high_impact_factor(self, recommendation: Dict, high_impact_factors: List[Dict]) -> bool:
        """Check if recommendation targets a high-impact factor"""
        # Simple heuristic: check if recommendation mentions high-impact factor
        rec_str = json.dumps(recommendation, default=str).lower()

        for factor in high_impact_factors:
            factor_str = json.dumps(factor, default=str).lower()

            # Check for overlap in key terms
            rec_terms = set(re.findall(r'\w+', rec_str))
            factor_terms = set(re.findall(r'\w+', factor_str))

            overlap = len(rec_terms & factor_terms)

            if overlap >= 3:  # At least 3 shared terms
                return True

        return False


def main():
    """Test MBB compliance checker"""

    # Test report (good example)
    good_report = {
        "executive_summary": {
            "key_decision": "Deploy adaptive confirms_required by Day 28",
            "rationale": "100% of regret is Type A (hysteresis lag)",
            "impact": "6-9% regret reduction",
            "risk": "LOW (shadow mode validation)"
        },
        "key_findings": [
            {
                "finding": "Type A dominance",
                "value": 31,
                "impact": "Surgical fix available",
                "evidence_id": "REGRET-ATTR-001"
            }
        ],
        "recommendations": [
            {
                "action": "Deploy adaptive confirms_required",
                "expected_impact": 0.07,
                "target_date": "2026-01-28"
            }
        ]
    }

    # Test report (bad example)
    bad_report = {
        "data": {
            "regret_count": 31,
            "regret_rate": 0.161
        },
        "analysis": "We analyzed the data and found some issues."
    }

    checker = MBBComplianceChecker()

    print("=" * 70)
    print("GOOD REPORT TEST")
    print("=" * 70)
    result_good = checker.validate_report(good_report)
    print(json.dumps(result_good, indent=2))

    print("\n" + "=" * 70)
    print("BAD REPORT TEST")
    print("=" * 70)
    result_bad = checker.validate_report(bad_report)
    print(json.dumps(result_bad, indent=2))


if __name__ == "__main__":
    main()
