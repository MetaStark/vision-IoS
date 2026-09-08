"""
Test ACI Integration Architecture evidence against MBB compliance
"""

import json
import sys
sys.path.append('03_FUNCTIONS')

from mbb_compliance_checker import MBBComplianceChecker

# Load evidence artifact
with open('03_FUNCTIONS/evidence/ACI_INTEGRATION_ARCHITECTURE_20260108.json', 'r') as f:
    evidence = json.load(f)

# Validate
checker = MBBComplianceChecker()
result = checker.validate_report(evidence)

# Print results
print("=" * 70)
print("MBB COMPLIANCE VALIDATION: ACI INTEGRATION ARCHITECTURE")
print("=" * 70)
print(f"\nOverall Compliance Score: {result['compliance_score']:.2f}")
print(f"Passing (>= 0.90): {'YES [PASS]' if result['passing'] else 'NO [FAIL]'}")

print("\n" + "=" * 70)
print("INDIVIDUAL CHECKS")
print("=" * 70)

for check_name, check_result in result['checks'].items():
    status = "PASS" if check_result['passed'] else "FAIL"
    score = check_result['score']
    print(f"\n{check_name.upper()}: {status} (score: {score:.2f})")

    if check_result['issues']:
        print("  Issues:")
        for issue in check_result['issues']:
            print(f"    - {issue}")

    if check_result['recommendations']:
        print("  Recommendations:")
        for rec in check_result['recommendations']:
            print(f"    - {rec}")

if result['recommendations']:
    print("\n" + "=" * 70)
    print("SUMMARY RECOMMENDATIONS")
    print("=" * 70)
    for rec in result['recommendations']:
        print(f"  - {rec}")

print("\n" + "=" * 70)
print("VALIDATION COMPLETE")
print("=" * 70)
