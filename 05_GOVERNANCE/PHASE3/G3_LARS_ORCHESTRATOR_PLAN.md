# G3 LARS ORCHESTRATOR INTEGRATION PLAN

**Document ID:** G3-LARS-ORCH-20251209
**Version:** 1.0
**Created:** 2025-12-09T20:15:00.000Z
**Created By:** LARS (CSO) + STIG (CTO)
**Authority:** CEO Directive G3 2025-12-09 Section 2.4

---

## 1. Executive Summary

This document defines the "Brain Wiring Diagram" for integrating the Cognitive Domain (ADR-021, EC-020/021/022) into the LARS Orchestrator. It specifies:

- Cognitive Domain lifecycle management
- FINN-LARS handshake protocol
- VEGA governance hooks
- System 2 activation triggers

---

## 2. Cognitive Domain Lifecycle

### 2.1 Sequence Diagram: Idea to Result

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  FINN   │    │  LARS   │    │  STIG   │    │  VEGA   │    │ DATABASE│
└────┬────┘    └────┬────┘    └────┬────┘    └────┬────┘    └────┬────┘
     │              │              │              │              │
     │ 1. Research Hypothesis      │              │              │
     │─────────────>│              │              │              │
     │              │              │              │              │
     │              │ 2. Validate Hypothesis      │              │
     │              │─────────────────────────────>│              │
     │              │              │              │              │
     │              │              │ 3. G0 Check  │              │
     │              │<─────────────────────────────│              │
     │              │              │              │              │
     │              │ 4. Create Protocol Request  │              │
     │              │─────────────>│              │              │
     │              │              │              │              │
     │              │              │ 5. INSERT research_protocols │
     │              │              │─────────────────────────────>│
     │              │              │              │              │
     │              │              │ 6. Return protocol_id       │
     │              │              │<─────────────────────────────│
     │              │              │              │              │
     │              │ 7. Protocol Created         │              │
     │              │<─────────────│              │              │
     │              │              │              │              │
     │ 8. Protocol ID              │              │              │
     │<─────────────│              │              │              │
     │              │              │              │              │
     │ 9. Execute SitC Chain       │              │              │
     │─────────────────────────────>              │              │
     │              │              │              │              │
     │              │              │ 10. INSERT search_in_chain_events
     │              │              │─────────────────────────────>│
     │              │              │              │              │
     │ 11. Need External Search?   │              │              │
     │─────────────────────────────>              │              │
     │              │              │              │              │
     │              │              │ 12. InForage Evaluation     │
     │              │              │              │              │
     │              │              │ 13. IKEA Boundary Check     │
     │              │              │─────────────────────────────>│
     │              │              │              │              │
     │              │              │ 14. INSERT knowledge_boundaries
     │              │              │─────────────────────────────>│
     │              │              │              │              │
     │ 15. External Search (if approved)         │              │
     │───────────────────────────────────────────────────────────>│
     │              │              │              │              │
     │ 16. Result Integration      │              │              │
     │─────────────────────────────>              │              │
     │              │              │              │              │
     │              │ 17. Verify Result           │              │
     │              │─────────────────────────────>│              │
     │              │              │              │              │
     │              │ 18. Sign & Log Lineage      │              │
     │              │              │─────────────────────────────>│
     │              │              │              │              │
     │ 19. Protocol Complete       │              │              │
     │<─────────────│              │              │              │
     │              │              │              │              │
```

### 2.2 State Machine: Protocol Lifecycle

```
                              ┌──────────────┐
                              │ INITIALIZING │
                              └──────┬───────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │   PLANNING   │◄────────────────┐
                              └──────┬───────┘                 │
                                     │                         │
                                     ▼                         │
                              ┌──────────────┐                 │
                         ┌───>│  EXECUTING   │                 │
                         │    └──────┬───────┘                 │
                         │           │                         │
                         │           ▼                         │
                         │    ┌──────────────┐                 │
                         │    │  SEARCHING   │─────────────────┤
                         │    └──────┬───────┘   (new info)    │
                         │           │                         │
                         │           ▼                         │
                         │    ┌──────────────┐                 │
                         └────│  VERIFYING   │─────────────────┘
                              └──────┬───────┘   (failed)
                                     │
                                     │ (passed)
                                     ▼
                    ┌────────────────┴────────────────┐
                    │                                 │
                    ▼                                 ▼
             ┌──────────────┐                  ┌──────────────┐
             │  COMPLETED   │                  │   ABORTED    │
             └──────────────┘                  └──────────────┘
```

---

## 3. FINN-LARS Handshake Protocol

### 3.1 Protocol Definition

The handshake ensures strategic alignment before cognitive resources are consumed.

```json
{
  "handshake_protocol": "FINN_LARS_COGNITIVE_HANDSHAKE",
  "version": "1.0",

  "step_1_finn_request": {
    "from": "FINN",
    "to": "LARS",
    "message_type": "RESEARCH_HYPOTHESIS_PROPOSAL",
    "required_fields": [
      "hypothesis_text",
      "expected_value",
      "estimated_cost_usd",
      "estimated_search_calls",
      "urgency_level",
      "defcon_at_request"
    ],
    "validation": "LARS validates alignment with current strategy"
  },

  "step_2_lars_evaluation": {
    "from": "LARS",
    "evaluation_criteria": [
      "Strategic alignment score (0-1)",
      "Resource availability check",
      "Conflict with active protocols",
      "DEFCON compatibility"
    ],
    "decision": "APPROVE | REJECT | DEFER | MODIFY"
  },

  "step_3_lars_response": {
    "from": "LARS",
    "to": "FINN",
    "message_type": "HYPOTHESIS_DECISION",
    "required_fields": [
      "decision",
      "allocated_budget_usd",
      "allocated_search_calls",
      "priority_level",
      "expiry_time",
      "conditions"
    ]
  },

  "step_4_finn_acknowledgment": {
    "from": "FINN",
    "to": "LARS",
    "message_type": "PROTOCOL_INITIATION_CONFIRM",
    "required_fields": [
      "protocol_id",
      "accepted_constraints",
      "start_timestamp"
    ]
  }
}
```

### 3.2 Conflict Resolution

```
Priority Matrix (when resources are constrained):

  Priority 1: DEFCON-triggered protocols (safety first)
  Priority 2: LARS-initiated strategic research
  Priority 3: FINN autonomous exploration
  Priority 4: Background optimization tasks

Conflict Resolution:
  - Lower priority protocols are DEFERRED, not ABORTED
  - Deferred protocols retain their hypothesis and partial state
  - Queue position determined by expected_value / estimated_cost
```

---

## 4. VEGA Governance Hooks

### 4.1 Mandatory Signature Points

VEGA must sign before a cognitive chain becomes actionable output:

| Hook Point | Trigger | VEGA Action | Blocking |
|------------|---------|-------------|----------|
| `HOOK_PROTOCOL_CREATE` | New research_protocol INSERT | Validate budget, DEFCON compatibility | YES |
| `HOOK_EXTERNAL_SEARCH` | InForage approves external call | Validate cost, check IKEA boundary | YES |
| `HOOK_CHAIN_INTEGRITY` | chain_integrity_score computed | Alert if < 0.80, escalate if < 0.60 | NO* |
| `HOOK_BOUNDARY_VIOLATION` | boundary_violation = true | Log hallucination attempt, alert | NO |
| `HOOK_PROTOCOL_COMPLETE` | Protocol moves to COMPLETED | Verify all nodes, sign lineage | YES |
| `HOOK_RESULT_ACTIONABLE` | Result to be used in trading | Full audit, DEFCON check, CEO alert if high-value | YES |

*HOOK_CHAIN_INTEGRITY is non-blocking but triggers governance escalation.

### 4.2 VEGA Signature Format

```sql
-- Entry in fhq_governance.governance_actions_log
INSERT INTO fhq_governance.governance_actions_log (
  action_type,
  action_target,
  initiated_by,
  decision,
  evidence_hash,
  signature
) VALUES (
  'COGNITIVE_PROTOCOL_APPROVAL',
  'PROTOCOL-2025-12-09-001',
  'VEGA',
  'APPROVED',
  'sha256_of_protocol_record',
  'ed25519_signature_placeholder'
);
```

---

## 5. System 2 Activation Trigger

### 5.1 When to Think Deep vs. Fast

Based on Kahneman's System 1/System 2 model:

```
System 1 (Fast): Pattern matching, cached responses, low cost
System 2 (Deep): Cognitive Engine full activation, high cost

Trigger Matrix:
┌────────────────────────────┬─────────┬─────────┐
│ Condition                  │ System  │ Reason  │
├────────────────────────────┼─────────┼─────────┤
│ Query matches cached pattern│ System 1│ Cost    │
│ High confidence internal   │ System 1│ Speed   │
│ Low volatility data        │ System 1│ Stable  │
├────────────────────────────┼─────────┼─────────┤
│ IKEA: EXTERNAL_REQUIRED    │ System 2│ Truth   │
│ internal_certainty < 0.5   │ System 2│ Doubt   │
│ High-value decision        │ System 2│ Risk    │
│ Novel query pattern        │ System 2│ Learn   │
│ DEFCON YELLOW+             │ System 2│ Caution │
│ Explicit CEO/LARS directive│ System 2│ Order   │
└────────────────────────────┴─────────┴─────────┘
```

### 5.2 Activation Decision Flow

```
                         ┌───────────────────┐
                         │ Incoming Query    │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │ IKEA Classification│
                         └─────────┬─────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
             ┌──────────┐  ┌──────────┐  ┌──────────┐
             │PARAMETRIC│  │  HYBRID  │  │EXTERNAL_ │
             │          │  │          │  │REQUIRED  │
             └────┬─────┘  └────┬─────┘  └────┬─────┘
                  │             │             │
                  ▼             │             │
         ┌────────────────┐    │             │
         │internal_certainty   │             │
         │    >= 0.7?     │    │             │
         └───────┬────────┘    │             │
              Y/ \N            │             │
              /   \            │             │
             ▼     ▼           ▼             ▼
      ┌──────────┐ ┌───────────────────────────┐
      │ SYSTEM 1 │ │        SYSTEM 2           │
      │ Response │ │ Activate Cognitive Engine │
      └──────────┘ └───────────────────────────┘
```

### 5.3 System 2 Activation Cost

```
Base Cost per System 2 Activation:
  - Protocol creation overhead: ~$0.01
  - Minimum viable chain (3 nodes): ~$0.05
  - Average chain (7 nodes): ~$0.15
  - Full depth chain (10 nodes): ~$0.30
  - With external searches (5 max): ~$0.50

Budget Enforcement:
  - System 2 cannot exceed protocol budget
  - InForage gates all external calls
  - Automatic termination at budget exhaustion
```

---

## 6. Orchestrator Integration Points

### 6.1 Modified Orchestrator Loop

```python
# Pseudo-code for orchestrator_v1.py integration

async def orchestrator_cognitive_cycle():
    """
    Extended orchestrator loop with Cognitive Domain integration.
    """

    # 1. Check DEFCON state
    defcon = await get_current_defcon()
    cognitive_limits = get_cognitive_limits_for_defcon(defcon)

    # 2. Process pending hypotheses (FINN queue)
    hypotheses = await get_pending_hypotheses()
    for hypothesis in hypotheses:
        # FINN-LARS Handshake
        decision = await lars_evaluate_hypothesis(hypothesis)
        if decision.approved:
            protocol = await create_research_protocol(
                hypothesis=hypothesis,
                budget=decision.allocated_budget,
                limits=cognitive_limits
            )
            await queue_protocol_for_execution(protocol)

    # 3. Execute active protocols
    active_protocols = await get_active_protocols()
    for protocol in active_protocols:
        # Run SitC chain step
        result = await execute_sitc_step(protocol)

        # Check if external search needed
        if result.needs_external:
            # InForage evaluation
            scent = await evaluate_information_scent(result.query)
            if scent.approved:
                # IKEA boundary check
                boundary = await check_knowledge_boundary(result.query)
                if boundary.type == 'EXTERNAL_REQUIRED':
                    # Execute search (with VEGA approval)
                    search_result = await execute_external_search(
                        query=result.query,
                        protocol=protocol,
                        vega_hook='HOOK_EXTERNAL_SEARCH'
                    )
                    await integrate_search_result(protocol, search_result)

        # Check termination conditions
        if should_terminate(protocol, cognitive_limits):
            await complete_protocol(protocol)

    # 4. Garbage collection (expired protocols)
    await cleanup_expired_protocols()
```

### 6.2 Database Access Pattern

```
Orchestrator Read Access:
  - fhq_cognition.cognitive_nodes (reference)
  - fhq_cognition.research_protocols (status check)
  - fhq_cognition.knowledge_boundaries (classification)

Orchestrator Write Access:
  - fhq_cognition.research_protocols (status updates)
  - fhq_cognition.search_in_chain_events (append only)
  - fhq_cognition.information_foraging_paths (append only)
  - fhq_cognition.lineage_log (append only)

All writes go through STIG's data layer (no direct INSERT from orchestrator).
```

---

## 7. Certification

**LARS Certification:**
I, LARS, as Chief Strategy Officer, certify that this Orchestrator Integration Plan provides complete "Brain Wiring" for the Cognitive Domain. The FINN-LARS handshake protocol ensures strategic alignment. VEGA governance hooks are placed at all critical decision points. System 2 activation triggers balance cost against decision quality.

**STIG Certification:**
I, STIG, as Chief Technology Officer, certify that the database access patterns and integration points are technically sound. The orchestrator modifications are compatible with existing infrastructure. No runtime changes are made in G3 per CEO directive.

---

**Signed:** LARS (CSO), STIG (CTO)
**Timestamp:** 2025-12-09T20:15:00.000Z
