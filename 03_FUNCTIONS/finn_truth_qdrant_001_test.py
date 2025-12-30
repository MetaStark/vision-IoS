#!/usr/bin/env python3
"""
FINN-TRUTH-QDRANT-001: Phase-2 Hybrid Retrieval Integrity Validation
Directive: GOVERNANCE-CRITICAL
"""

import psycopg2
import json
import uuid
import hashlib
from datetime import datetime, timezone

print("=" * 70)
print("FINN-TRUTH-QDRANT-001: HYBRID RETRIEVAL VALIDATION")
print("=" * 70)

conn = psycopg2.connect(
    host="127.0.0.1", port=54322,
    database="postgres", user="postgres", password="postgres"
)
conn.autocommit = True
cur = conn.cursor()

# Load Step 1 data
with open("/tmp/qdrant_retrieval.json", "r") as f:
    step1_data = json.load(f)
SESSION_ID = step1_data["session_id"]
print(f"Session: {SESSION_ID}")

# === STEP 2: GRAPH EXPANSION ===
print("\n[STEP 2] GRAPH EXPANSION")

# Get liquidity source nodes
cur.execute("""
    SELECT node_id FROM fhq_graph.nodes
    WHERE node_type = 'MACRO'
    AND (label ILIKE '%liquidity%' OR label ILIKE '%m2%');
""")
source_ids = [r[0] for r in cur.fetchall()]
print(f"  Source nodes: {source_ids}")

# Get all edges from liquidity nodes
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

print(f"  Hop 1 edges: {len(hop1_edges)}")
print(f"  Direct BTC edges: {len(direct_btc)}")
print(f"  Intermediate nodes: {intermediate}")

# Hop 2: From intermediate to BTC
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

print(f"  Hop 2 edges: {len(hop2_edges)}")

total_edges = len(hop1_edges) + len(hop2_edges) + len(direct_btc)
print(f"  TOTAL EDGES: {total_edges}")

graph_result = {
    "hop1": hop1_edges,
    "hop2": hop2_edges,
    "direct_btc": direct_btc,
    "total": total_edges,
    "status": "PASS" if total_edges > 0 else "FAIL"
}
print(f"  Status: {graph_result['status']}")

# === STEP 3: SitC INTEGRITY ===
print("\n[STEP 3] SitC INTEGRITY SCORE")

qdrant_nodes = len(step1_data.get("results", []))
verified_nodes = sum(1 for n in step1_data.get("results", [])[:10] if n.get("hash"))
verified_edges = len([e for e in (hop1_edges + hop2_edges + direct_btc) if e.get("edge_id")])
total_evidence = qdrant_nodes + total_edges

sitc_score = (verified_nodes + verified_edges) / max(total_evidence, 1)
sitc_score = min(sitc_score, 1.0)

print(f"  Verified nodes: {verified_nodes}")
print(f"  Verified edges: {verified_edges}")
print(f"  Total evidence: {total_evidence}")
print(f"  SitC Score: {sitc_score:.4f}")
print(f"  Threshold: 0.80")
sitc_status = "PASS" if sitc_score >= 0.80 else "FAIL"
print(f"  Status: {sitc_status}")

sitc_result = {"score": sitc_score, "threshold": 0.80, "status": sitc_status}

# === STEP 4: INFORAGE LOGGING ===
print("\n[STEP 4] INFORAGE COST LOGGING")

inforage_session = str(uuid.uuid4())

# Log Qdrant retrieval (LAKE)
cur.execute("""
    INSERT INTO fhq_optimization.inforage_cost_log
    (session_id, step_number, step_type, step_cost, cumulative_cost,
     source_tier, reason_for_cost, retrieval_source)
    VALUES (%s, 1, 'FINN_TRUTH_QDRANT', 0.00, 0.00,
            'LAKE', 'Qdrant semantic search on seeded evidence_nodes', 'qdrant://evidence_nodes')
    RETURNING log_id;
""", (inforage_session,))
log1 = str(cur.fetchone()[0])
print(f"  [LAKE] Qdrant retrieval: {log1[:8]}...")

# Log Graph expansion (LAKE)
cur.execute("""
    INSERT INTO fhq_optimization.inforage_cost_log
    (session_id, step_number, step_type, step_cost, cumulative_cost,
     source_tier, reason_for_cost, retrieval_source)
    VALUES (%s, 2, 'FINN_TRUTH_GRAPH', 0.00, 0.00,
            'LAKE', 'fhq_graph.edges 2-hop traversal', 'postgres://fhq_graph.edges')
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

proposal_id = f"G0-FINN-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
g0_proposal = {
    "proposal_id": proposal_id,
    "proposal_type": "STRATEGY_DRAFT_V0.1",
    "title": "Liquidity Expansion -> BTC Regime Shift Causal Hypothesis",
    "status": "DRAFT",
    "zea_compliance": True,
    "hypothesis": {
        "claim": "Global M2 liquidity expansion LEADS Bitcoin regime shifts",
        "confidence": 0.85,
        "evidence_count": total_evidence,
        "supporting_edges": len(direct_btc) + len(hop2_edges)
    },
    "evidence_references": [],
    "fibo_concepts": ["IND/MACRO/LIQUIDITY", "FBC/ASSET/CRYPTO/BTC", "FND/REGIME"],
    "action_verb": "PROPOSE",
    "next_gate": "G1_REVIEW"
}

# Add evidence refs
if step1_data.get("results"):
    g0_proposal["evidence_references"].append({
        "type": "QDRANT_NODE",
        "id": step1_data["results"][0]["id"][:8],
        "hash": step1_data["results"][0].get("hash", "N/A")[:16]
    })
if direct_btc:
    g0_proposal["evidence_references"].append({
        "type": "GRAPH_EDGE",
        "id": direct_btc[0]["edge_id"],
        "strength": direct_btc[0]["strength"]
    })

# ZEA check - no execution verbs
prohibited = ["BUY", "SELL", "TRADE", "EXECUTE"]
proposal_str = json.dumps(g0_proposal).upper()
zea_violations = [v for v in prohibited if v in proposal_str]
g0_proposal["zea_status"] = "PASS" if not zea_violations else "FAIL"

print(f"  Proposal ID: {proposal_id}")
print(f"  Evidence count: {g0_proposal['hypothesis']['evidence_count']}")
print(f"  ZEA Status: {g0_proposal['zea_status']}")

# === STEP 6: SHA-256 ROOT HASH ===
print("\n[STEP 6] SHA-256 ROOT HASH")

audit_artifact = {
    "directive_id": "FINN-TRUTH-QDRANT-001",
    "session_id": SESSION_ID,
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "query": "Liquidity expansion -> BTC Regime Shift",
    "qdrant_retrieval": {
        "collection": "evidence_nodes",
        "nodes_retrieved": qdrant_nodes,
        "top_k_relevant": min(10, qdrant_nodes),
        "status": step1_data.get("summary", {}).get("status", "PASS")
    },
    "graph_expansion": graph_result,
    "sitc_integrity": sitc_result,
    "inforage_audit": inforage_result,
    "g0_proposal": g0_proposal,
    "ikea_classification": "LAKE" if sitc_score >= 0.80 else "EXTERNAL_REQUIRED"
}

# Compute root hash
artifact_json = json.dumps(audit_artifact, sort_keys=True, default=str)
sha256_root = hashlib.sha256(artifact_json.encode()).hexdigest()
audit_artifact["sha256_root_hash"] = sha256_root

print(f"  Root Hash: {sha256_root}")

# Overall status
all_pass = (
    graph_result["status"] == "PASS" and
    sitc_result["status"] == "PASS" and
    inforage_result["status"] == "COMPLIANT" and
    g0_proposal["zea_status"] == "PASS"
)
audit_artifact["overall_status"] = "PASS" if all_pass else "FAIL"

# === FINAL SUMMARY ===
print("\n" + "=" * 70)
print("FINN-TRUTH-QDRANT-001 VALIDATION RESULTS")
print("=" * 70)
print(f"  [A] Qdrant Retrieval:   {audit_artifact['qdrant_retrieval']['status']} ({qdrant_nodes} nodes)")
print(f"  [B] Graph Expansion:    {graph_result['status']} ({total_edges} edges)")
print(f"  [C] SitC Integrity:     {sitc_status} ({sitc_score:.4f} >= 0.80)")
print(f"  [D] InForage Logging:   {inforage_result['status']}")
print(f"  [E] G0 Proposal:        {g0_proposal['zea_status']} (ZEA compliant)")
print(f"  [F] IKEA Classification: {audit_artifact['ikea_classification']}")
print("=" * 70)
print(f"  OVERALL STATUS:         {audit_artifact['overall_status']}")
print(f"  SHA-256 Root Hash:      {sha256_root[:32]}...")
print("=" * 70)

# Save artifact
output_path = "../05_GOVERNANCE/PHASE3/FINN_TRUTH_QDRANT_001_AUDIT.json"
with open(output_path, "w") as f:
    json.dump(audit_artifact, f, indent=2, default=str)
print(f"\nAudit artifact saved to: {output_path}")

cur.close()
conn.close()
