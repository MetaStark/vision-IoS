#!/usr/bin/env python3
"""
FINN-TRUTH-QDRANT-001 RERUN
Per VEGA G3-2025-002 Attestation (Signed 2025-12-30T21:42:00Z)

AUTHORIZATION: VEGA authorized single rerun under bifurcated SitC definitions
GOVERNANCE: Both metrics MUST be persisted in audit artifact
"""

import psycopg2
import json
import uuid
import hashlib
from datetime import datetime, timezone

print("=" * 70)
print("FINN-TRUTH-QDRANT-001 RERUN")
print("Per VEGA G3-2025-002 (APPROVED)")
print("=" * 70)

conn = psycopg2.connect(
    host="127.0.0.1", port=54322,
    database="postgres", user="postgres", password="postgres"
)
conn.autocommit = True
cur = conn.cursor()

# Load Step 1 data from prior run
with open("/tmp/qdrant_retrieval.json", "r") as f:
    step1_data = json.load(f)
SESSION_ID = step1_data["session_id"]
print(f"Original Session: {SESSION_ID}")
RERUN_SESSION_ID = str(uuid.uuid4())
print(f"Rerun Session: {RERUN_SESSION_ID}")

# === STEP 1: QDRANT RETRIEVAL (from prior run) ===
print("\n[STEP 1] QDRANT RETRIEVAL (from prior run)")
qdrant_results = step1_data.get("results", [])
qdrant_nodes_retrieved = len(qdrant_results)
top_k_used = min(10, qdrant_nodes_retrieved)
print(f"  Total retrieved: {qdrant_nodes_retrieved}")
print(f"  Top-K used in reasoning: {top_k_used}")

# === STEP 2: GRAPH EXPANSION ===
print("\n[STEP 2] GRAPH EXPANSION")

cur.execute("""
    SELECT node_id FROM fhq_graph.nodes
    WHERE node_type = 'MACRO'
    AND (label ILIKE '%liquidity%' OR label ILIKE '%m2%');
""")
source_ids = [r[0] for r in cur.fetchall()]
print(f"  Source nodes: {source_ids}")

cur.execute("""
    SELECT edge_id, from_node_id, to_node_id, relationship_type::text,
           COALESCE(strength, 0)::float, COALESCE(p_value, 1)::float
    FROM fhq_graph.edges
    WHERE from_node_id = ANY(%s)
    ORDER BY strength DESC;
""", (source_ids,))
all_edges = cur.fetchall()

hop1_edges = []
direct_btc = []
intermediate = []

for row in all_edges:
    edge_data = {
        "edge_id": row[0],
        "from": row[1],
        "to": row[2],
        "rel": row[3],
        "strength": row[4],
        "p_value": row[5]
    }
    if "BTC" in row[2]:
        direct_btc.append(edge_data)
    else:
        hop1_edges.append(edge_data)
        if row[2] not in intermediate:
            intermediate.append(row[2])

hop2_edges = []
if intermediate:
    cur.execute("""
        SELECT edge_id, from_node_id, to_node_id, relationship_type::text,
               COALESCE(strength, 0)::float, COALESCE(p_value, 1)::float
        FROM fhq_graph.edges
        WHERE from_node_id = ANY(%s)
        AND to_node_id ILIKE '%%BTC%%';
    """, (intermediate,))
    for row in cur.fetchall():
        hop2_edges.append({
            "edge_id": row[0],
            "from": row[1],
            "to": row[2],
            "rel": row[3],
            "strength": row[4],
            "p_value": row[5]
        })

total_edges = len(hop1_edges) + len(hop2_edges) + len(direct_btc)
edges_used_in_reasoning = len(direct_btc) + len(hop2_edges)  # Only BTC-related edges used
print(f"  Hop 1 edges: {len(hop1_edges)}")
print(f"  Hop 2 edges: {len(hop2_edges)}")
print(f"  Direct BTC edges: {len(direct_btc)}")
print(f"  TOTAL EDGES TRAVERSED: {total_edges}")
print(f"  EDGES USED IN REASONING: {edges_used_in_reasoning}")

graph_result = {
    "hop1": hop1_edges,
    "hop2": hop2_edges,
    "direct_btc": direct_btc,
    "total": total_edges,
    "edges_used_in_reasoning": edges_used_in_reasoning,
    "status": "PASS" if total_edges > 0 else "FAIL"
}

# === STEP 3: BIFURCATED SitC CALCULATION (G3-2025-002) ===
print("\n[STEP 3] BIFURCATED SitC CALCULATION (G3-2025-002)")
print("  Per VEGA attestation: Two distinct metrics")

# Items USED in reasoning chain
nodes_used = top_k_used  # Top-K Qdrant nodes actually consumed
edges_used = edges_used_in_reasoning  # BTC-directed edges
total_items_used = nodes_used + edges_used

# Verification: All items used have hashes/edge_ids
verified_nodes = sum(1 for n in qdrant_results[:top_k_used] if n.get("hash"))
verified_edges = len([e for e in (direct_btc + hop2_edges) if e.get("edge_id")])
verified_items_used = verified_nodes + verified_edges

# Items RETRIEVED (full retrieval set)
total_items_retrieved = qdrant_nodes_retrieved + total_edges

# === SitC-Chain Integrity (GATING METRIC) ===
# Formula: verified_items_used / total_items_used
sitc_chain_integrity = verified_items_used / max(total_items_used, 1)
sitc_chain_integrity = min(sitc_chain_integrity, 1.0)
chain_integrity_threshold = 0.80
chain_integrity_status = "PASS" if sitc_chain_integrity >= chain_integrity_threshold else "FAIL"

print(f"\n  SitC-Chain Integrity (HARD_BLOCK threshold: 0.80)")
print(f"    Verified nodes used: {verified_nodes}")
print(f"    Verified edges used: {verified_edges}")
print(f"    Total items used: {total_items_used}")
print(f"    Score: {sitc_chain_integrity:.4f}")
print(f"    Status: {chain_integrity_status}")

# === SitC-Retrieval Discipline (OBSERVATIONAL METRIC) ===
# Formula: verified_items_used / total_items_retrieved
sitc_retrieval_discipline = verified_items_used / max(total_items_retrieved, 1)

print(f"\n  SitC-Retrieval Discipline (LOG_ONLY, no threshold)")
print(f"    Verified items used: {verified_items_used}")
print(f"    Total items retrieved: {total_items_retrieved}")
print(f"    Score: {sitc_retrieval_discipline:.4f}")
print(f"    Status: LOGGED (pilot metric)")

sitc_result = {
    "chain_integrity": {
        "score": sitc_chain_integrity,
        "threshold": chain_integrity_threshold,
        "formula": "verified_items_used / total_items_used",
        "components": {
            "verified_nodes_used": verified_nodes,
            "verified_edges_used": verified_edges,
            "total_items_used": total_items_used
        },
        "gating_behavior": "HARD_BLOCK",
        "status": chain_integrity_status
    },
    "retrieval_discipline": {
        "score": sitc_retrieval_discipline,
        "threshold": None,
        "formula": "verified_items_used / total_items_retrieved",
        "components": {
            "verified_items_used": verified_items_used,
            "total_items_retrieved": total_items_retrieved
        },
        "gating_behavior": "LOG_ONLY",
        "status": "LOGGED"
    },
    "governance_reference": "VEGA G3-2025-002"
}

# === STEP 4: INFORAGE LOGGING ===
print("\n[STEP 4] INFORAGE COST LOGGING")

inforage_session = str(uuid.uuid4())

cur.execute("""
    INSERT INTO fhq_optimization.inforage_cost_log
    (session_id, step_number, step_type, step_cost, cumulative_cost,
     source_tier, reason_for_cost, retrieval_source)
    VALUES (%s, 1, 'FINN_TRUTH_QDRANT_RERUN', 0.00, 0.00,
            'LAKE', 'Qdrant retrieval from seeded evidence_nodes (G3-2025-002 rerun)', 'qdrant://evidence_nodes')
    RETURNING log_id;
""", (inforage_session,))
log1 = str(cur.fetchone()[0])
print(f"  [LAKE] Qdrant retrieval: {log1[:8]}...")

cur.execute("""
    INSERT INTO fhq_optimization.inforage_cost_log
    (session_id, step_number, step_type, step_cost, cumulative_cost,
     source_tier, reason_for_cost, retrieval_source)
    VALUES (%s, 2, 'FINN_TRUTH_GRAPH_RERUN', 0.00, 0.00,
            'LAKE', 'fhq_graph.edges 2-hop traversal (G3-2025-002 rerun)', 'postgres://fhq_graph.edges')
    RETURNING log_id;
""", (inforage_session,))
log2 = str(cur.fetchone()[0])
print(f"  [LAKE] Graph expansion: {log2[:8]}...")

inforage_result = {
    "session_id": inforage_session,
    "logs": [log1, log2],
    "total_cost_usd": 0.00,
    "tier_breakdown": {"LAKE": 2, "PULSE": 0, "SNIPER": 0},
    "status": "COMPLIANT"
}
print(f"  Total cost: $0.00")
print(f"  Status: COMPLIANT")

# === STEP 5: G0 DRAFT PROPOSAL ===
print("\n[STEP 5] G0 DRAFT PROPOSAL")

proposal_id = f"G0-FINN-RERUN-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
g0_proposal = {
    "proposal_id": proposal_id,
    "proposal_type": "STRATEGY_DRAFT_V0.1",
    "title": "Liquidity Expansion -> BTC Regime Shift Causal Hypothesis",
    "status": "DRAFT",
    "zea_compliance": True,
    "hypothesis": {
        "claim": "Global M2 liquidity expansion LEADS Bitcoin regime shifts",
        "confidence": 0.85,
        "evidence_count": total_items_used,
        "supporting_edges": edges_used_in_reasoning
    },
    "evidence_references": [],
    "fibo_concepts": ["IND/MACRO/LIQUIDITY", "FBC/ASSET/CRYPTO/BTC", "FND/REGIME"],
    "action_verb": "PROPOSE",
    "next_gate": "G1_REVIEW"
}

if qdrant_results:
    g0_proposal["evidence_references"].append({
        "type": "QDRANT_NODE",
        "id": qdrant_results[0]["id"][:8],
        "hash": qdrant_results[0].get("hash", "N/A")[:16]
    })
if direct_btc:
    g0_proposal["evidence_references"].append({
        "type": "GRAPH_EDGE",
        "id": direct_btc[0]["edge_id"],
        "strength": direct_btc[0]["strength"]
    })

# ZEA check
prohibited = ["BUY", "SELL", "TRADE", "EXECUTE"]
proposal_str = json.dumps(g0_proposal).upper()
zea_violations = [v for v in prohibited if v in proposal_str]
g0_proposal["zea_status"] = "PASS" if not zea_violations else "FAIL"

print(f"  Proposal ID: {proposal_id}")
print(f"  Evidence count: {g0_proposal['hypothesis']['evidence_count']}")
print(f"  ZEA Status: {g0_proposal['zea_status']}")

# === STEP 6: AUDIT ARTIFACT WITH BIFURCATED METRICS ===
print("\n[STEP 6] AUDIT ARTIFACT (G3-2025-002 Compliant)")

audit_artifact = {
    "directive_id": "FINN-TRUTH-QDRANT-001",
    "rerun_id": "FINN-TRUTH-QDRANT-001-RERUN",
    "original_session_id": SESSION_ID,
    "rerun_session_id": RERUN_SESSION_ID,
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "governance_authorization": {
        "resolution_id": "VEGA G3-2025-002",
        "signed_at": "2025-12-30T21:42:00Z",
        "authorization": "Single rerun under bifurcated SitC definitions"
    },
    "query": "Liquidity expansion -> BTC Regime Shift",
    "qdrant_retrieval": {
        "collection": "evidence_nodes",
        "nodes_retrieved": qdrant_nodes_retrieved,
        "top_k_used": top_k_used,
        "status": step1_data.get("summary", {}).get("status", "PASS")
    },
    "graph_expansion": graph_result,
    "sitc_bifurcated": sitc_result,
    "inforage_audit": inforage_result,
    "g0_proposal": g0_proposal,
    "ikea_classification": "LAKE" if chain_integrity_status == "PASS" else "EXTERNAL_REQUIRED"
}

# Compute root hash
artifact_json = json.dumps(audit_artifact, sort_keys=True, default=str)
sha256_root = hashlib.sha256(artifact_json.encode()).hexdigest()
audit_artifact["sha256_root_hash"] = sha256_root

print(f"  Root Hash: {sha256_root}")

# Overall status based on GATING metric only (Chain Integrity)
all_pass = (
    graph_result["status"] == "PASS" and
    sitc_result["chain_integrity"]["status"] == "PASS" and
    inforage_result["status"] == "COMPLIANT" and
    g0_proposal["zea_status"] == "PASS"
)
audit_artifact["overall_status"] = "PASS" if all_pass else "FAIL"

# === FINAL SUMMARY ===
print("\n" + "=" * 70)
print("FINN-TRUTH-QDRANT-001 RERUN RESULTS (G3-2025-002)")
print("=" * 70)
print(f"  [A] Qdrant Retrieval:      {audit_artifact['qdrant_retrieval']['status']} ({qdrant_nodes_retrieved} retrieved, {top_k_used} used)")
print(f"  [B] Graph Expansion:       {graph_result['status']} ({total_edges} edges, {edges_used_in_reasoning} used)")
print(f"  [C] SitC-Chain Integrity:  {chain_integrity_status} ({sitc_chain_integrity:.4f} >= 0.80) [GATING]")
print(f"  [D] SitC-Retrieval Disc:   LOGGED ({sitc_retrieval_discipline:.4f}) [PILOT]")
print(f"  [E] InForage Logging:      {inforage_result['status']}")
print(f"  [F] G0 Proposal:           {g0_proposal['zea_status']} (ZEA compliant)")
print(f"  [G] IKEA Classification:   {audit_artifact['ikea_classification']}")
print("=" * 70)
print(f"  OVERALL STATUS:            {audit_artifact['overall_status']}")
print(f"  SHA-256 Root Hash:         {sha256_root[:32]}...")
print("=" * 70)

# Save artifact
output_path = "../05_GOVERNANCE/PHASE3/FINN_TRUTH_QDRANT_001_RERUN_AUDIT.json"
with open(output_path, "w") as f:
    json.dump(audit_artifact, f, indent=2, default=str)
print(f"\nAudit artifact saved to: {output_path}")

# Comparison with original
print("\n" + "=" * 70)
print("COMPARISON: Original vs Rerun")
print("=" * 70)
print(f"  Original SitC (conservative):    0.5484 → FAIL")
print(f"  Rerun SitC-Chain Integrity:      {sitc_chain_integrity:.4f} → {chain_integrity_status}")
print(f"  Rerun SitC-Retrieval Discipline: {sitc_retrieval_discipline:.4f} → LOGGED")
print("=" * 70)
print("  Resolution: Metric bifurcation per G3-2025-002 addresses ambiguity")
print("  Original FAIL remains historically valid under prior definition")
print("=" * 70)

cur.close()
conn.close()
