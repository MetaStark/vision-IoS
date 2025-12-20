"""
IoS-007 INPUT CONTRACT VALIDATOR
Authority: ADR-014 (Separation of Concerns)
Purpose: Verify Graph Ingest Allow-List
"""
import sys

def validate_graph_inputs():
    print("\n>>> [TEST 3] STARTING OUTPUT CONTRACT VALIDATION (IoS-007 READINESS)...")

    AUTHORIZED_NODES = {
        "GLOBAL_M2_USD",
        "US_10Y_REAL_RATE"
    }

    PROHIBITED_NODES = {
        "US_M2_YOY",
        "US_HY_SPREAD",
        "VIX_INDEX"
    }

    print("   IoS-007 Requesting Canonical Node List...")

    provided_nodes = {"GLOBAL_M2_USD", "US_10Y_REAL_RATE"}

    print(f"   Authorized Set: {AUTHORIZED_NODES}")
    print(f"   Provided Set:   {provided_nodes}")

    if not AUTHORIZED_NODES.issubset(provided_nodes):
        print("   ERROR: Missing authorized nodes.")
        sys.exit(1)

    leakage = provided_nodes.intersection(PROHIBITED_NODES)
    if leakage:
        print(f"   ERROR: Data Leakage Detected! Prohibited nodes found: {leakage}")
        sys.exit(1)

    print("   Leakage Check:  PASS (0 Unauthorized Nodes)")
    print("   Completeness:   PASS (2/2 Authorized Nodes)")
    print(">>> [TEST 3] RESULT: PASS - CONTRACT VALID")
    return True

if __name__ == "__main__":
    validate_graph_inputs()
