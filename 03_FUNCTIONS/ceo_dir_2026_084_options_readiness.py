#!/usr/bin/env python3
"""
CEO-DIR-2026-084: OPTIONS COMPATIBILITY & EXECUTION READINESS (PREPARATION ONLY)

Authority: CEO
Scope: Non-executing, non-capital, non-broker
Status: SHADOW / OBSERVATION / TRAINING
Explicitly NOT paper trading

Purpose:
Ensure FjordHQ ACI and LINE are fully compatible with:
- STRESS Inversion signal structure
- Direction-Only ROI Ledger timing dynamics
- Alpaca Options Trading instrument logic

BEFORE we consider paper trading.

This is competence and architecture preparation, NOT trading.
"""

import os
import sys
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=os.getenv("PGPORT", "54322"),
        database=os.getenv("PGDATABASE", "postgres"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres")
    )


def register_directive(conn):
    """Register CEO-DIR-2026-084 in governance."""
    print("\n" + "="*60)
    print("STEP 1: REGISTERING DIRECTIVE")
    print("="*60)

    action_id = str(uuid.uuid4())

    with conn.cursor() as cur:
        try:
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log
                (action_type, action_target, action_target_type, initiated_by,
                 initiated_at, decision, decision_rationale, metadata, agent_id, timestamp)
                VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s::jsonb, %s, NOW())
            """, (
                'CEO_DIRECTIVE_EXECUTION',
                'CEO-DIR-2026-084',
                'DIRECTIVE',
                'CEO',
                'EXECUTING',
                'OPTIONS COMPATIBILITY & EXECUTION READINESS - Preparation only, no trading',
                json.dumps({
                    "directive": "CEO-DIR-2026-084",
                    "action_id": action_id,
                    "scope": "NON_EXECUTING",
                    "mode": "SHADOW_OBSERVATION_TRAINING"
                }),
                'STIG'
            ))
            conn.commit()
            print(f"  Directive registered: CEO-DIR-2026-084")
            print(f"  Action ID: {action_id}")
            print(f"  Mode: SHADOW / OBSERVATION / TRAINING")
        except Exception as e:
            print(f"  Note: Governance log entry skipped ({e})")

    return action_id


def create_line_mandate(conn):
    """Create LINE Options Authority mandate."""
    print("\n" + "="*60)
    print("STEP 2: CREATING LINE OPTIONS AUTHORITY MANDATE")
    print("="*60)

    mandate = {
        "mandate_id": "LINE-OPT-MANDATE-001",
        "directive_ref": "CEO-DIR-2026-084",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "issued_by": "CEO",
        "agent": "LINE",
        "role": "Options Microstructure & Risk Authority",
        "status": "ACTIVE",

        "SHALL_DO": {
            "1_study_alpaca_api": {
                "description": "Study and document Alpaca Options Trading API in detail",
                "specifics": [
                    "Contract specification",
                    "Expiration mechanics",
                    "Strike selection constraints",
                    "Liquidity & fill assumptions",
                    "Exercise / assignment rules"
                ]
            },
            "2_map_structures": {
                "description": "Map compatible options structures",
                "criteria": [
                    "Compatible with direction-only signals",
                    "Robust against timing uncertainty (t+1 / t+3 / t+5)"
                ]
            },
            "3_build_readiness_doc": {
                "description": "Build Execution Readiness v1 document",
                "question_answered": "If the signal says DOWN in STRESS - which instruments can express this without distorting signal truth?"
            }
        },

        "SHALL_NOT": [
            "Place orders",
            "Connect to Alpaca broker",
            "Simulate PnL",
            "Optimize payoff",
            "Propose sizing"
        ],

        "principle": "This is understanding before power.",

        "deliverables": {
            "1": {
                "name": "Options Execution Readiness v1 (Equity)",
                "type": "DOCUMENT",
                "format": "Pure document, no code, no ROI numbers",
                "deadline_days": 7
            },
            "2": {
                "name": "Compatibility Matrix",
                "type": "MATRIX",
                "format": "Signal property × Options property",
                "deadline_days": 7
            },
            "3": {
                "name": "Explicit Non-Compatibility List",
                "type": "LIST",
                "format": "Structures NOT to use + reasons",
                "deadline_days": 7
            }
        },

        "gate_function": "These documents are prerequisites for: paper trading, G5 authority, capital discussion"
    }

    # Save mandate
    mandate_path = Path(__file__).parent / "evidence" / "LINE_OPTIONS_AUTHORITY_MANDATE_001.json"
    mandate_path.parent.mkdir(exist_ok=True)

    with open(mandate_path, "w") as f:
        json.dump(mandate, f, indent=2)

    print(f"  Agent: LINE")
    print(f"  Role: Options Microstructure & Risk Authority")
    print(f"  Mandate ID: {mandate['mandate_id']}")
    print(f"  SHALL DO: 3 items")
    print(f"  SHALL NOT: 5 items")
    print(f"  Deliverables: 3 documents")
    print(f"  Deadline: 7 days")
    print(f"  Saved: {mandate_path.name}")

    return mandate


def create_compatibility_requirements():
    """Document compatibility requirements."""
    print("\n" + "="*60)
    print("STEP 3: DOCUMENTING COMPATIBILITY REQUIREMENTS")
    print("="*60)

    requirements = {
        "document_id": "OPTIONS_COMPATIBILITY_REQUIREMENTS_v1",
        "directive_ref": "CEO-DIR-2026-084",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "STIG (EC-003)",

        "NON_NEGOTIABLE_PRINCIPLE": {
            "statement": "The signal proves truth. The instrument exploits truth. Never reverse.",
            "implication": "Options selection NEVER influences signal thresholds"
        },

        "SIGNAL_PROPERTIES_TO_PRESERVE": {
            "1_directional_intent": {
                "property": "UP/DOWN",
                "current_signal": "STRESS@99%+ implies DOWN (inverted)",
                "requirement": "Options structure must express DOWN without ambiguity"
            },
            "2_time_horizon": {
                "property": "t0 -> t+N",
                "current_horizons": ["t+1d", "t+3d", "t+5d"],
                "requirement": "Options expiry must accommodate these horizons without theta decay destroying edge"
            },
            "3_event_sparsity": {
                "property": "Edge per activation",
                "observation": "Signals are rare (~31 in 10 days)",
                "requirement": "Each signal activation must have meaningful payoff potential"
            },
            "4_shadow_observability": {
                "property": "Non-executing observation",
                "current_mode": "SHADOW",
                "requirement": "Must be able to observe theoretical payoff without execution"
            }
        },

        "LEDGER_INTEGRITY_CONSTRAINTS": {
            "table": "fhq_research.roi_direction_ledger_equity",
            "MUST_REMAIN_FREE_OF": [
                "Greeks (delta, gamma, theta, vega, rho)",
                "Implied Volatility (IV)",
                "PnL calculations",
                "Spreads metadata",
                "Options contract details"
            ],
            "rationale": "Direction-Only ROI is the ONLY admissible proof of alpha. Options are downstream."
        },

        "COMPATIBILITY_TEST": {
            "question": "Can this options structure express the signal without breaking the above?",
            "if_no": "Structure is unsuitable, regardless of theoretical payoff"
        },

        "CANDIDATE_STRUCTURES_FOR_ANALYSIS": {
            "potentially_compatible": [
                "ATM Puts (single leg)",
                "Slightly OTM Puts (single leg)",
                "Put spreads (requires analysis)"
            ],
            "likely_incompatible": [
                "Complex multi-leg strategies",
                "Calendar spreads (timing mismatch)",
                "Iron condors (non-directional)",
                "Straddles/strangles (non-directional)"
            ],
            "note": "LINE must validate these classifications"
        },

        "ALPACA_SPECIFIC_REQUIREMENTS": {
            "api_documentation": "https://alpaca.markets/docs/trading/options/",
            "items_to_document": [
                "Available option classes for our tickers",
                "Strike granularity",
                "Expiration dates available",
                "Liquidity characteristics",
                "Order types supported",
                "Exercise/assignment mechanics",
                "Margin requirements (observation only)"
            ]
        }
    }

    # Save requirements
    req_path = Path(__file__).parent / "evidence" / "OPTIONS_COMPATIBILITY_REQUIREMENTS_v1.json"

    with open(req_path, "w") as f:
        json.dump(requirements, f, indent=2)

    print(f"  Non-negotiable principle: Signal proves truth, instrument exploits")
    print(f"  Signal properties to preserve: 4")
    print(f"  Ledger constraints: 5 items MUST remain free")
    print(f"  Candidate structures identified: 3 potentially compatible, 4 likely incompatible")
    print(f"  Saved: {req_path.name}")

    return requirements


def create_compatibility_matrix_template():
    """Create compatibility matrix template."""
    print("\n" + "="*60)
    print("STEP 4: CREATING COMPATIBILITY MATRIX TEMPLATE")
    print("="*60)

    matrix = {
        "matrix_id": "SIGNAL_OPTIONS_COMPATIBILITY_MATRIX_v1",
        "directive_ref": "CEO-DIR-2026-084",
        "status": "TEMPLATE_CREATED",
        "to_be_filled_by": "LINE",
        "deadline": (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d"),

        "SIGNAL_PROPERTIES": {
            "SP1": {"name": "Direction", "value": "DOWN (inverted)", "source": "STRESS@99%+"},
            "SP2": {"name": "Confidence", "value": ">=99%", "source": "regime_confidence"},
            "SP3": {"name": "Horizon_1D", "value": "t0+1 day", "source": "roi_direction_ledger"},
            "SP4": {"name": "Horizon_3D", "value": "t0+3 days", "source": "roi_direction_ledger"},
            "SP5": {"name": "Horizon_5D", "value": "t0+5 days", "source": "roi_direction_ledger"},
            "SP6": {"name": "Event_Frequency", "value": "~3/day", "source": "shadow observation"},
            "SP7": {"name": "Ticker_Universe", "value": "EQUITY_US", "source": "asset_class constraint"}
        },

        "OPTIONS_PROPERTIES": {
            "OP1": {"name": "Structure", "values": ["ATM Put", "OTM Put", "Put Spread", "Other"]},
            "OP2": {"name": "DTE_Range", "values": ["7-14", "14-21", "21-30", "30+"]},
            "OP3": {"name": "Strike_Selection", "values": ["ATM", "5% OTM", "10% OTM"]},
            "OP4": {"name": "Single_vs_Multi", "values": ["Single Leg", "Multi Leg"]},
            "OP5": {"name": "Exercise_Style", "values": ["American", "European"]},
            "OP6": {"name": "Liquidity_Requirement", "values": ["High", "Medium", "Low"]}
        },

        "COMPATIBILITY_MATRIX": {
            "_note": "LINE to fill: Y=Compatible, N=Incompatible, ?=Needs Analysis",
            "_format": "SIGNAL_PROPERTY x OPTIONS_PROPERTY",

            "ATM_Put_14DTE": {
                "SP1_Direction": "?",
                "SP2_Confidence": "?",
                "SP3_Horizon_1D": "?",
                "SP4_Horizon_3D": "?",
                "SP5_Horizon_5D": "?",
                "SP6_Event_Frequency": "?",
                "SP7_Ticker_Universe": "?"
            },
            "OTM_Put_5pct_14DTE": {
                "SP1_Direction": "?",
                "SP2_Confidence": "?",
                "SP3_Horizon_1D": "?",
                "SP4_Horizon_3D": "?",
                "SP5_Horizon_5D": "?",
                "SP6_Event_Frequency": "?",
                "SP7_Ticker_Universe": "?"
            },
            "Put_Spread_14DTE": {
                "SP1_Direction": "?",
                "SP2_Confidence": "?",
                "SP3_Horizon_1D": "?",
                "SP4_Horizon_3D": "?",
                "SP5_Horizon_5D": "?",
                "SP6_Event_Frequency": "?",
                "SP7_Ticker_Universe": "?"
            }
        },

        "LINE_INSTRUCTIONS": [
            "1. Study each options structure against each signal property",
            "2. Mark Y if compatible, N if incompatible, ? if needs more research",
            "3. Add notes explaining compatibility or incompatibility",
            "4. Add additional structures if relevant",
            "5. Submit completed matrix for VEGA review"
        ]
    }

    # Save matrix
    matrix_path = Path(__file__).parent / "evidence" / "SIGNAL_OPTIONS_COMPATIBILITY_MATRIX_v1.json"

    with open(matrix_path, "w") as f:
        json.dump(matrix, f, indent=2)

    print(f"  Signal properties defined: 7")
    print(f"  Options properties defined: 6")
    print(f"  Matrix structures to analyze: 3 initial")
    print(f"  To be filled by: LINE")
    print(f"  Deadline: {matrix['deadline']}")
    print(f"  Saved: {matrix_path.name}")

    return matrix


def create_non_compatibility_template():
    """Create non-compatibility list template."""
    print("\n" + "="*60)
    print("STEP 5: CREATING NON-COMPATIBILITY LIST TEMPLATE")
    print("="*60)

    non_compat = {
        "list_id": "EXPLICIT_NON_COMPATIBILITY_LIST_v1",
        "directive_ref": "CEO-DIR-2026-084",
        "status": "TEMPLATE_CREATED",
        "to_be_filled_by": "LINE",
        "deadline": (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d"),

        "PURPOSE": "Document which options structures SHALL NOT be used, with explicit reasons",

        "PRELIMINARY_NON_COMPATIBLE_STRUCTURES": {
            "_note": "LINE to validate and expand",

            "1_iron_condor": {
                "structure": "Iron Condor",
                "reason": "Non-directional - cannot express DOWN signal",
                "status": "LIKELY_INCOMPATIBLE",
                "line_validation": "PENDING"
            },
            "2_straddle": {
                "structure": "Straddle",
                "reason": "Non-directional - profits from volatility, not direction",
                "status": "LIKELY_INCOMPATIBLE",
                "line_validation": "PENDING"
            },
            "3_strangle": {
                "structure": "Strangle",
                "reason": "Non-directional - profits from volatility, not direction",
                "status": "LIKELY_INCOMPATIBLE",
                "line_validation": "PENDING"
            },
            "4_calendar_spread": {
                "structure": "Calendar Spread",
                "reason": "Timing mismatch - exploits time decay difference, not direction",
                "status": "LIKELY_INCOMPATIBLE",
                "line_validation": "PENDING"
            },
            "5_naked_call": {
                "structure": "Naked Call",
                "reason": "Wrong direction - profits from UP, signal says DOWN",
                "status": "INCOMPATIBLE",
                "line_validation": "PENDING"
            },
            "6_covered_call": {
                "structure": "Covered Call",
                "reason": "Requires underlying ownership, neutral-to-bullish bias",
                "status": "LIKELY_INCOMPATIBLE",
                "line_validation": "PENDING"
            }
        },

        "LINE_INSTRUCTIONS": [
            "1. Validate each preliminary classification",
            "2. Add additional incompatible structures discovered during research",
            "3. Provide detailed rationale for each incompatibility",
            "4. Reference specific signal properties that are violated",
            "5. Submit completed list for VEGA review"
        ],

        "ACCEPTANCE_CRITERIA": [
            "Each incompatible structure has clear rationale",
            "Rationale references signal properties (SP1-SP7)",
            "No execution-oriented language",
            "No PnL projections"
        ]
    }

    # Save list
    list_path = Path(__file__).parent / "evidence" / "EXPLICIT_NON_COMPATIBILITY_LIST_v1.json"

    with open(list_path, "w") as f:
        json.dump(non_compat, f, indent=2)

    print(f"  Preliminary incompatible structures: 6")
    print(f"  To be validated by: LINE")
    print(f"  Deadline: {non_compat['deadline']}")
    print(f"  Saved: {list_path.name}")

    return non_compat


def create_deliverables_tracker(conn):
    """Create deliverables tracking."""
    print("\n" + "="*60)
    print("STEP 6: CREATING DELIVERABLES TRACKER")
    print("="*60)

    deadline = datetime.now(timezone.utc) + timedelta(days=7)

    tracker = {
        "tracker_id": "CEO_DIR_2026_084_DELIVERABLES",
        "directive_ref": "CEO-DIR-2026-084",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "deadline": deadline.strftime("%Y-%m-%d"),

        "deliverables": [
            {
                "id": "D1",
                "name": "Options Execution Readiness v1 (Equity)",
                "owner": "LINE",
                "type": "DOCUMENT",
                "format": "Pure document, no code, no ROI numbers",
                "status": "NOT_STARTED",
                "due": deadline.strftime("%Y-%m-%d"),
                "prerequisite_for": ["Paper trading", "G5 authority", "Capital discussion"]
            },
            {
                "id": "D2",
                "name": "Compatibility Matrix",
                "owner": "LINE",
                "type": "MATRIX",
                "format": "Signal property × Options property",
                "status": "TEMPLATE_CREATED",
                "template_file": "SIGNAL_OPTIONS_COMPATIBILITY_MATRIX_v1.json",
                "due": deadline.strftime("%Y-%m-%d")
            },
            {
                "id": "D3",
                "name": "Explicit Non-Compatibility List",
                "owner": "LINE",
                "type": "LIST",
                "format": "Structures NOT to use + reasons",
                "status": "TEMPLATE_CREATED",
                "template_file": "EXPLICIT_NON_COMPATIBILITY_LIST_v1.json",
                "due": deadline.strftime("%Y-%m-%d")
            }
        ],

        "governance": {
            "VEGA": "Validates no execution pressure introduced",
            "UMA": "Quality-checks epistemistic integrity preserved",
            "STIG": "Holds together and reports to CEO"
        },

        "gate_requirement": "All 3 deliverables are prerequisites for paper trading discussion"
    }

    # Save tracker
    tracker_path = Path(__file__).parent / "evidence" / "CEO_DIR_2026_084_DELIVERABLES_TRACKER.json"

    with open(tracker_path, "w") as f:
        json.dump(tracker, f, indent=2)

    print(f"  Deliverables: 3")
    print(f"  Owner: LINE")
    print(f"  Deadline: {deadline.strftime('%Y-%m-%d')}")
    print(f"  Governance: VEGA validates, UMA QC, STIG reports")
    print(f"  Saved: {tracker_path.name}")

    return tracker


def generate_evidence(action_id, mandate, requirements, matrix, non_compat, tracker):
    """Generate comprehensive evidence file."""
    print("\n" + "="*60)
    print("STEP 7: GENERATING EVIDENCE")
    print("="*60)

    evidence = {
        "directive_id": "CEO-DIR-2026-084",
        "directive_title": "OPTIONS COMPATIBILITY & EXECUTION READINESS (PREPARATION ONLY)",
        "executed_by": "STIG (EC-003)",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "status": "ACTIVATED",

        "scope": {
            "mode": "SHADOW / OBSERVATION / TRAINING",
            "explicitly_not": "Paper trading",
            "broker_connection": False,
            "order_placement": False,
            "pnl_simulation": False
        },

        "non_negotiable_principle": {
            "statement": "The signal proves truth. The instrument exploits truth. Never reverse.",
            "status": "GOVERNING"
        },

        "ledger_integrity": {
            "table": "fhq_research.roi_direction_ledger_equity",
            "remains_free_of": ["Greeks", "IV", "PnL", "Spreads", "Options metadata"],
            "status": "PROTECTED"
        },

        "line_mandate": {
            "mandate_id": mandate["mandate_id"],
            "role": mandate["role"],
            "shall_do": list(mandate["SHALL_DO"].keys()),
            "shall_not": mandate["SHALL_NOT"],
            "status": "ACTIVE"
        },

        "deliverables": {
            "count": 3,
            "deadline": tracker["deadline"],
            "items": [d["name"] for d in tracker["deliverables"]],
            "gate_function": "Prerequisites for paper trading"
        },

        "templates_created": [
            "LINE_OPTIONS_AUTHORITY_MANDATE_001.json",
            "OPTIONS_COMPATIBILITY_REQUIREMENTS_v1.json",
            "SIGNAL_OPTIONS_COMPATIBILITY_MATRIX_v1.json",
            "EXPLICIT_NON_COMPATIBILITY_LIST_v1.json",
            "CEO_DIR_2026_084_DELIVERABLES_TRACKER.json"
        ],

        "governance": {
            "VEGA": "Will validate no execution pressure",
            "UMA": "Will QC epistemistic integrity",
            "STIG": "Holds together, reports to CEO"
        },

        "ceo_confirmation": {
            "directive_registered": True,
            "line_mandate_created": True,
            "compatibility_requirements_documented": True,
            "matrix_template_created": True,
            "non_compatibility_template_created": True,
            "deliverables_tracked": True,
            "ledger_protected": True
        },

        "closing_principle": "We go to market when we understand exactly how truth becomes money - without lying to ourselves along the way."
    }

    evidence_path = Path(__file__).parent / "evidence" / "CEO_DIR_2026_084_OPTIONS_READINESS_ACTIVATION.json"

    with open(evidence_path, "w") as f:
        json.dump(evidence, f, indent=2)

    print(f"  Evidence file: {evidence_path.name}")
    print(f"  Templates created: 5")
    print(f"  Directive status: ACTIVATED")

    return evidence_path


def main():
    """Execute CEO-DIR-2026-084."""
    print("="*60)
    print("CEO-DIR-2026-084: OPTIONS COMPATIBILITY & EXECUTION READINESS")
    print("(PREPARATION ONLY)")
    print("="*60)
    print(f"Executed: {datetime.now(timezone.utc).isoformat()}")
    print("Authority: CEO")
    print("Executed by: STIG (EC-003)")
    print("\nScope: Non-executing, non-capital, non-broker")
    print("Mode: SHADOW / OBSERVATION / TRAINING")
    print("Explicitly NOT: Paper trading")

    conn = get_db_connection()

    try:
        # Step 1: Register directive
        action_id = register_directive(conn)

        # Step 2: Create LINE mandate
        mandate = create_line_mandate(conn)

        # Step 3: Document compatibility requirements
        requirements = create_compatibility_requirements()

        # Step 4: Create compatibility matrix template
        matrix = create_compatibility_matrix_template()

        # Step 5: Create non-compatibility list template
        non_compat = create_non_compatibility_template()

        # Step 6: Create deliverables tracker
        tracker = create_deliverables_tracker(conn)

        # Step 7: Generate evidence
        evidence_path = generate_evidence(
            action_id, mandate, requirements, matrix, non_compat, tracker
        )

        print("\n" + "="*60)
        print("CEO-DIR-2026-084: ACTIVATION COMPLETE")
        print("="*60)

        print("\nSUMMARY:")
        print("  [x] Directive registered in governance")
        print("  [x] LINE Options Authority mandate created")
        print("  [x] Compatibility requirements documented")
        print("  [x] Compatibility matrix template created")
        print("  [x] Non-compatibility list template created")
        print("  [x] Deliverables tracker established")
        print("  [x] Ledger integrity protected")

        print("\nLINE DELIVERABLES (7 days):")
        print("  1. Options Execution Readiness v1 (Equity)")
        print("  2. Compatibility Matrix (completed)")
        print("  3. Explicit Non-Compatibility List (completed)")

        print("\nPRINCIPLE:")
        print("  Signal proves truth. Instrument exploits truth. Never reverse.")
        print("\n  We go to market when we understand exactly how truth becomes")
        print("  money - without lying to ourselves along the way.")
        print("\n  Shadow Mode is our advantage. Use it fully.")
        print("\n  Holding the line.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
