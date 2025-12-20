 FjordHQ ACI Integration Plan

 C-Level Executive Strategy Document

 Classification: STIG-2025-ACI-INTEGRATION
 Authority: ADR-020 (ACI), ADR-021 (Cognitive Engine Architecture)
 Status: CONDITIONAL APPROVAL (CEO Directive 2025-12-17)

 ---
 CEO DIRECTIVE COMPLIANCE

 Reference: CEO DIRECTIVE: ACI INTEGRATION – CONDITIONAL APPROVAL & REMEDIATION (2025-12-17)

 This plan has been rectified to incorporate all 8 Critical Mandates issued by CEO/FjordHQ Executive Board.

 | Mandate | Description                              | Compliance Section           |
 |---------|------------------------------------------|------------------------------|
 | I       | ASRP State-Binding (ADR-018)             | MANDATE I COMPLIANCE         |
 | II      | Economic Safety as Runtime Law (ADR-012) | MANDATE II COMPLIANCE        |
 | III     | DEFCON Deterministic Gating (ADR-016)    | MANDATE III COMPLIANCE       |
 | IV      | Governance of Learning Loop              | MANDATE IV COMPLIANCE        |
 | V       | IKEA Fail-Safe Default                   | MANDATE V COMPLIANCE         |
 | VI      | Audit-Grade Metrics                      | MANDATE VI COMPLIANCE        |
 | VII     | Evidence of Existence                    | APPENDIX A: SCHEMA INTEGRITY |
 | VIII    | Role Isolation (MIT Quad)                | MANDATE VIII COMPLIANCE      |

 ---
 EXECUTIVE SUMMARY

 FjordHQ has built sophisticated cognitive infrastructure (EC-018, EC-020, EC-021, EC-022) but only EC-018 is fully
 operational. This plan activates the complete ACI stack to enable autonomous alpha generation with
 governance-compliant self-learning.

 Current State:
 | Component           | Status     | Gap                                        |
 |---------------------|------------|--------------------------------------------|
 | EC-018 (Meta-Alpha) | ACTIVE     | None - operational                         |
 | EC-020 (SitC)       | REGISTERED | No implementation file                     |
 | EC-021 (InForage)   | REGISTERED | Imported but not wired into cognitive loop |
 | EC-022 (IKEA)       | REGISTERED | No implementation file                     |
 | Learning Loop       | PARTIAL    | Not connected to cognitive engines         |

 Target State: Full ACI stack operational with self-learning feedback loop.

 ---
 WAVE 1: IKEA IMPLEMENTATION (CRITICAL - SAFETY FIRST)

 Rationale: IKEA is the hallucination firewall. Must be first to prevent bad data decisions.

 1.1 Create 03_FUNCTIONS/ios022_ikea_boundary_engine.py

 # Core functionality required:
 class IKEABoundaryEngine:
     def classify_query(self, query: str) -> Tuple[str, float]:
         """Returns (PARAMETRIC|EXTERNAL_REQUIRED|HYBRID, confidence)"""

     def check_volatility_class(self, data_type: str) -> str:
         """Returns EXTREME|HIGH|MEDIUM|LOW|STATIC"""

     def log_classification(self, query, classification, confidence):
         """Log to fhq_meta.knowledge_boundary_log"""

 Classification Rules (per EC-022 contract):
 - PARAMETRIC: Stable knowledge (formulas, definitions, sector classifications)
 - EXTERNAL_REQUIRED: Time-sensitive data (prices, earnings, macro releases)
 - HYBRID: Stable concept + current data (P/E vs industry average)

 1.2 Wire IKEA into finn_cognitive_brain.py

 File: C:\fhq-market-system\vision-ios\03_FUNCTIONS\finn_cognitive_brain.py

 Integration point: Before every LLM call in run_cognitive_cycle() (around line 433-456)

 # Add IKEA gate before context retrieval
 if self.ikea_engine:
     for claim in self._extract_factual_claims(query):
         classification, confidence = self.ikea_engine.classify_query(claim)
         if classification == 'EXTERNAL_REQUIRED':
             # Must retrieve before proceeding
             self._trigger_retrieval(claim)

 1.3 Wire IKEA into ec018_alpha_daemon.py

 File: C:\fhq-market-system\vision-ios\03_FUNCTIONS\ec018_alpha_daemon.py

 Integration point: Before hypothesis generation to ensure all factual claims have retrieval backing.

 ---
 WAVE 2: INFORAGE FULL INTEGRATION (HIGH PRIORITY)

 Rationale: InForage exists (inforage_cost_controller.py) but is not fully wired.

 2.1 Complete integration in finn_cognitive_brain.py

 Current state (lines 68-73):
 try:
     from inforage_cost_controller import InForageCostController, StepType, CostDecision
     COST_CONTROL_AVAILABLE = True
 except ImportError:
     COST_CONTROL_AVAILABLE = False

 Required changes in run_cognitive_cycle() (around line 475-488):

 # Before each API-consuming step, check InForage
 if self.cost_controller:
     predicted_gain = self._estimate_information_gain(patch=self.state.current_patch)
     result = self.cost_controller.check_cost(StepType.API_CALL, predicted_gain)

     if result.should_abort:
         logger.warning(f"InForage ABORT: {result.abort_reason}")
         # Skip this cycle, preserve budget for higher-value opportunities
         results['inforage_abort'] = result.abort_reason
         return results

 2.2 Add InForage to ec018_alpha_daemon.py

 Add cost checks before:
 - Serper API call (news retrieval)
 - DeepSeek API call (hypothesis generation)

 ---
 WAVE 3: SITC PLANNER (MEDIUM PRIORITY)

 Rationale: SitC requires IKEA and InForage to function. Orchestrates reasoning chains.

 3.1 Create 03_FUNCTIONS/ios020_sitc_planner.py

 class SitCPlanner:
     def create_research_plan(self, hypothesis: str) -> List[ChainNode]:
         """Decompose hypothesis into Chain-of-Query nodes"""

     def verify_node(self, node: ChainNode) -> VerificationResult:
         """Verify node using IKEA + InForage"""

     def revise_plan(self, node: ChainNode, new_evidence: Any) -> List[ChainNode]:
         """Dynamically revise plan based on new evidence"""

     def log_chain(self, nodes: List[ChainNode]):
         """Log to fhq_meta.chain_of_query"""

 Node Types (per EC-020 contract):
 - PLAN_INIT, REASONING, SEARCH, VERIFICATION, PLAN_REVISION, SYNTHESIS, ABORT

 3.2 Wire SitC into cognitive loop

 Wrap research tasks in SitC plans for:
 - EC-018 hypothesis generation
 - FINN cognitive cycle research steps

 ---
 WAVE 4: LEARNING LOOP COMPLETION (HIGH PRIORITY)

 Rationale: Close the feedback loop for self-improvement.

 4.1 Add cognitive engine feedback to learning_feedback_pipeline.py

 File: C:\fhq-market-system\vision-ios\03_FUNCTIONS\learning_feedback_pipeline.py

 Add new methods:
 def _update_ikea_classifier(self, outcome: TradeOutcome):
     """Update IKEA boundary classifier based on trade outcomes"""
     # If hypothesis used hallucinated data and trade failed -> penalty

 def _update_inforage_scent(self, outcome: TradeOutcome):
     """Update InForage Scent Score based on actual ROI"""
     # Compare predicted_gain to actual_gain, adjust scent model

 def _update_sitc_success(self, outcome: TradeOutcome):
     """Update SitC plan success metrics"""
     # Track which plan structures lead to successful trades

 4.2 Log cognitive decisions to evidence table

 All IKEA/InForage/SitC decisions must log to fhq_meta.cognitive_engine_evidence:
 INSERT INTO fhq_meta.cognitive_engine_evidence (
     engine_id, task_id, invocation_type,
     input_context, decision_rationale, output_modification,
     cost_usd, information_gain_score, chain_integrity_score,
     boundary_violation, signature
 )

 ---
 WAVE 5: DAEMON ORCHESTRATION

 5.1 Update scheduled tasks

 Market Hours (09:30-16:00 ET):
 - Every 30 min: FINN Cognitive Cycle with full ACI stack
 - Every 1 hour: EC-018 Alpha Hunt

 Daily:
 - 06:00: IoS-001 price ingestion
 - 07:00: IoS-003 regime update
 - 22:00: Causal graph update (VarClus + PCMCI)

 5.2 Health monitoring

 Add cognitive engine heartbeat checks to existing monitoring.

 ---
 CRITICAL FILES TO MODIFY

 | File                                        | Action                                | Priority |
 |---------------------------------------------|---------------------------------------|----------|
 | 03_FUNCTIONS/ios022_ikea_boundary_engine.py | CREATE                                | CRITICAL |
 | 03_FUNCTIONS/finn_cognitive_brain.py        | MODIFY (wire IKEA, complete InForage) | CRITICAL |
 | 03_FUNCTIONS/ec018_alpha_daemon.py          | MODIFY (add IKEA/InForage gates)      | HIGH     |
 | 03_FUNCTIONS/ios020_sitc_planner.py         | CREATE                                | MEDIUM   |
 | 03_FUNCTIONS/learning_feedback_pipeline.py  | MODIFY (add cognitive feedback)       | HIGH     |
 | 03_FUNCTIONS/context_injection_layer.py     | VERIFY (already integrated)           | LOW      |

 ---
 DATABASE TABLES (VERIFIED EXIST)

 - fhq_meta.chain_of_query - SitC plan nodes
 - fhq_meta.cognitive_engine_evidence - Audit trail
 - fhq_meta.knowledge_boundary_log - IKEA classifications
 - fhq_meta.search_foraging_log - InForage decisions
 - fhq_optimization.inforage_cost_log - Cost tracking

 ---
 SUCCESS METRICS

 | Metric                       | Target      | Source                 |
 |------------------------------|-------------|------------------------|
 | IKEA Classification Accuracy | >85%        | knowledge_boundary_log |
 | InForage Cost Savings        | >40%        | inforage_cost_log      |
 | Hypothesis Validation Rate   | >30% G0->G1 | g0_draft_proposals     |
 | Paper Trading Sharpe         | >0.5        | paper_trade_outcomes   |
 | Learning Updates/Week        | >50         | learning_updates       |

 ---
 DEFCON BEHAVIOR

 | DEFCON | EC-020 (SitC)         | EC-021 (InForage)       | EC-022 (IKEA)      |
 |--------|-----------------------|-------------------------|--------------------|
 | GREEN  | Full dynamic planning | Normal optimization     | Standard check     |
 | YELLOW | Shorter chains        | Aggressive cost-cutting | Bias internal      |
 | ORANGE | CoT validation only   | Emergency budget only   | External mandatory |
 | RED    | ABORT all chains      | HALT all searches       | READ-ONLY          |

 ---
 IMPLEMENTATION SEQUENCE

 1. WAVE 1.1: Create ios022_ikea_boundary_engine.py
 2. WAVE 1.2: Wire IKEA into finn_cognitive_brain.py
 3. WAVE 1.3: Wire IKEA into ec018_alpha_daemon.py
 4. WAVE 2.1: Complete InForage integration in finn_cognitive_brain.py
 5. WAVE 2.2: Add InForage to ec018_alpha_daemon.py
 6. WAVE 4.1: Add cognitive feedback to learning_feedback_pipeline.py
 7. WAVE 3.1: Create ios020_sitc_planner.py
 8. WAVE 3.2: Wire SitC into cognitive loop
 9. WAVE 5: Update daemon orchestration

 ---
 GOVERNANCE COMPLIANCE

 - All changes require G1 technical validation
 - VEGA attestation required for each wave completion
 - Ed25519 signatures on all database operations
 - Audit trail to fhq_meta.adr_audit_log

 Authority Chain: CEO -> LARS (strategy) -> STIG (implementation) -> VEGA (governance)

 ---
 GOVERNANCE ARTIFACTS TO CREATE

 CEO Directives (05_GOVERNANCE/PHASE3/)

 | File                                            | Purpose                         |
 |-------------------------------------------------|---------------------------------|
 | CD_ACI_WAVE1_IKEA_ACTIVATION_20251217.json      | IKEA boundary engine activation |
 | CD_ACI_WAVE2_INFORAGE_COMPLETION_20251217.json  | InForage full integration       |
 | CD_ACI_WAVE3_SITC_ACTIVATION_20251217.json      | SitC planner activation         |
 | CD_ACI_WAVE4_LEARNING_LOOP_20251217.json        | Learning feedback completion    |
 | CD_ACI_WAVE5_DAEMON_ORCHESTRATION_20251217.json | Daemon scheduling update        |

 VEGA Attestation Templates

 Each wave completion requires:
 {
   "attestation_type": "G1_TECHNICAL_VALIDATION",
   "target": "EC-0XX",
   "gate_level": "G1",
   "status": "PENDING",
   "validation_criteria": [...],
   "evidence_required": [...]
 }

 ---
 FULL IMPLEMENTATION SCOPE

 User Decision: Full implementation of all 5 waves with complete governance artifacts.

 Deliverables Checklist (CEO Mandate Compliant)

 Core Implementation:
 - ios022_ikea_boundary_engine.py created (with fail-safe default per Mandate V)
 - ios020_sitc_planner.py created (with ASRP state binding per Mandate I)
 - finn_cognitive_brain.py modified (RuntimeEconomicGuardian per Mandate II)
 - ec018_alpha_daemon.py modified (IKEA + InForage + ASRP binding)
 - learning_feedback_pipeline.py modified (staging-only per Mandate IV)
 - finn_brain_scheduler.py modified (DEFCON hard gates per Mandate III)

 New Infrastructure:
 - RuntimeEconomicGuardian class (Mandate II)
 - defcon_gate_check() function (Mandate III)
 - fhq_governance.learning_proposals table (Mandate IV)
 - Schema boundary enforcement decorator (Mandate VIII)

 Governance Artifacts:
 - 5 CEO Directive JSON files created
 - G1 validation tests for each wave
 - VEGA attestation templates
 - Schema integrity hash recorded

 ---
 MANDATE I COMPLIANCE: ASRP State-Binding (ADR-018)

 Requirement: Every artifact must embed state_snapshot_hash and timestamp from Atomic Shared State.

 Implementation:

 1. IKEA Classifications - Every knowledge_boundary_log entry will include:
 {
     "state_snapshot_hash": <current_asrp_hash>,
     "state_timestamp": <atomic_timestamp>,
     "classification": "PARAMETRIC|EXTERNAL_REQUIRED|HYBRID",
     "query_hash": <sha256_of_query>
 }
 2. InForage Decisions - Every search_foraging_log entry will include:
 {
     "state_snapshot_hash": <current_asrp_hash>,
     "state_timestamp": <atomic_timestamp>,
     "decision": "CONTINUE|ABORT",
     "cost_at_decision": <cumulative_cost>
 }
 3. SitC Plan Nodes - Every chain_of_query node will include:
 {
     "state_snapshot_hash": <hash_at_node_creation>,
     "state_timestamp": <atomic_timestamp>,
     "node_type": "REASONING|SEARCH|VERIFICATION|..."
 }
 4. Helper Function - Create get_current_asrp_state() in all cognitive engines:
 def get_current_asrp_state(conn) -> Tuple[str, datetime]:
     """Retrieve atomic state snapshot hash and timestamp."""
     sql = '''
         SELECT state_snapshot_hash, vector_timestamp
         FROM fhq_meta.aci_state_snapshot_log
         WHERE is_atomic = true
         ORDER BY created_at DESC LIMIT 1
     '''
     return (hash, timestamp)

 ---
 MANDATE II COMPLIANCE: Economic Safety as Runtime Law (ADR-012)

 Requirement: InForageCostController must be unbypassable at Runtime level, not just Agent level.

 Implementation:

 1. Runtime Guardian Class - Create RuntimeEconomicGuardian in finn_cognitive_brain.py:
 class RuntimeEconomicGuardian:
     """Unbypassable economic safety enforcement."""

     def __init__(self):
         self._cost_controller = None
         self._load_failed = False

     def initialize(self) -> bool:
         try:
             from inforage_cost_controller import InForageCostController
             self._cost_controller = InForageCostController()
             return True
         except Exception as e:
             self._load_failed = True
             self._trigger_circuit_breaker(f"ECONOMIC_SAFETY_LOAD_FAILURE: {e}")
             return False

     def check_or_fail(self, step_type, predicted_gain) -> CostCheckResult:
         """Check cost or HARD FAIL. No exceptions."""
         if self._load_failed or self._cost_controller is None:
             raise RuntimeEconomicViolation("Cost controller unavailable - HARD FAIL")
         return self._cost_controller.check_cost(step_type, predicted_gain)
 2. Hard Fail Mode - If cost controller fails to load:
   - Circuit breaker triggers immediately
   - All cognitive cycles BLOCKED
   - DEFCON escalation to ORANGE
 3. No Try/Except Bypass - Replace optional patterns:
 # BEFORE (Bypassable):
 if self.cost_controller:
     result = self.cost_controller.check_cost(...)

 # AFTER (Unbypassable):
 result = self.runtime_guardian.check_or_fail(...)  # Raises on failure

 ---
 MANDATE III COMPLIANCE: DEFCON Deterministic Gating (ADR-016)

 Requirement: Daemon Scheduler must have explicit Hard Gates linked to DEFCON state.

 Implementation:

 1. DaemonOrchestrator DEFCON Gates - Create defcon_gate_check():
 def defcon_gate_check(conn) -> Tuple[bool, str]:
     """Hard gate check BEFORE any cycle starts."""
     sql = "SELECT current_level FROM fhq_governance.defcon_status ORDER BY updated_at DESC LIMIT 1"
     level = execute(sql)

     if level in ('RED', 'BLACK'):
         kill_running_processes()  # Immediate termination
         return (False, f"DEFCON {level}: ALL PROCESSES KILLED")

     if level == 'ORANGE':
         return (False, f"DEFCON ORANGE: NEW CYCLES BLOCKED")

     return (True, f"DEFCON {level}: PROCEED")
 2. Scheduler Integration - In finn_brain_scheduler.py:
 def run_scheduled_cycle():
     # HARD GATE - Checked BEFORE any agent logic
     can_proceed, reason = defcon_gate_check(conn)
     if not can_proceed:
         logger.critical(reason)
         return  # BLOCKED

     # Only if gate passes
     brain.run_cognitive_cycle()
 3. DEFCON Behavior Matrix (Proscriptive, not Descriptive):
 | DEFCON | Research Cycles   | Running Processes | Learning Updates |
 |--------|-------------------|-------------------|------------------|
 | GREEN  | ALLOWED           | ALLOWED           | STAGING ONLY     |
 | YELLOW | ALLOWED (reduced) | ALLOWED           | STAGING ONLY     |
 | ORANGE | BLOCKED           | ALLOWED (no new)  | BLOCKED          |
 | RED    | BLOCKED           | KILLED            | BLOCKED          |
 | BLACK  | BLOCKED           | KILLED            | BLOCKED          |


 ---
 MANDATE IV COMPLIANCE: Governance of Learning Loop (ADR-020/021)

 Requirement: NO automated updates to IKEA classifier. All updates go to staging + G1/VEGA approval.

 Implementation:

 1. Learning Loop Architecture (Corrected):
 Trade Outcome
      ↓
 learning_feedback_pipeline.py
      ↓
 PROPOSAL (fhq_governance.learning_proposals)  ← Staging Area
      ↓
 [G1 VEGA Attestation Required]
      ↓
 PRODUCTION (cognitive engine weights)
 2. New Table - fhq_governance.learning_proposals:
 CREATE TABLE fhq_governance.learning_proposals (
     proposal_id UUID PRIMARY KEY,
     engine_id VARCHAR(10),  -- 'IKEA', 'INFORAGE', 'SITC'
     proposal_type VARCHAR(50),  -- 'BOUNDARY_WEIGHT', 'SCENT_MODEL', 'PLAN_PRIOR'
     current_value JSONB,
     proposed_value JSONB,
     evidence_bundle JSONB,  -- Trade outcomes that justify the change
     status VARCHAR(20) DEFAULT 'PENDING',  -- PENDING, APPROVED, REJECTED
     submitted_at TIMESTAMPTZ DEFAULT NOW(),
     reviewed_by VARCHAR(50),
     reviewed_at TIMESTAMPTZ,
     vega_attestation_id UUID
 );
 3. Prohibited Actions:
   - ❌ self.ikea_classifier.update_weights(outcome)
   - ❌ self.inforage.adjust_scent_model(actual_roi)
   - ✅ self._propose_learning_update(engine, proposal, evidence)
 4. "Facts Without Sources Are Illegal" - This constraint is IMMUTABLE:
   - IKEA boundary engine parameters are Constitutional
   - Any relaxation requires CEO + VEGA approval through G4 gate

 ---
 MANDATE V COMPLIANCE: IKEA Fail-Safe Default

 Requirement: If uncertain or failed, default to EXTERNAL_REQUIRED (maximum safety).

 Implementation:

 1. Fail-Safe Classification in ios022_ikea_boundary_engine.py:
 def classify_query(self, query: str) -> Tuple[str, float]:
     try:
         classification, confidence = self._internal_classify(query)

         # FAIL-SAFE: If confidence < threshold, default to maximum safety
         if confidence < 0.7:
             logger.warning(f"IKEA: Low confidence ({confidence:.2f}), defaulting to EXTERNAL_REQUIRED")
             return ('EXTERNAL_REQUIRED', confidence)

         return (classification, confidence)

     except Exception as e:
         # FAIL-SAFE: Any failure defaults to maximum safety
         logger.error(f"IKEA classification failed: {e}")
         return ('EXTERNAL_REQUIRED', 0.0)
 2. Burden of Proof Inversion:
   - Default state: EXTERNAL_REQUIRED (assume we don't know)
   - To classify as PARAMETRIC: Must prove with high confidence (>0.85)
   - To classify as HYBRID: Must identify which parts are parametric
 3. Extractor Failure Handling:
 def _extract_factual_claims(self, text: str) -> List[str]:
     try:
         claims = self._nlp_extract(text)
         return claims if claims else [text]  # If no claims extracted, treat entire text as claim
     except:
         return [text]  # Fail-safe: entire text needs verification

 ---
 MANDATE VI COMPLIANCE: Audit-Grade Metrics

 Requirement: Ground truth sources defined, vanity metrics removed.

 Implementation:

 1. Ground Truth Sources:
 | Metric                       | Ground Truth Provider      | Measurement Method                      |
 |------------------------------|----------------------------|-----------------------------------------|
 | IKEA Classification Accuracy | VEGA Sampling (10% random) | Human review of 50 classifications/week |
 | InForage Cost Savings        | ADR-012 Budget Log         | actual_cost / baseline_cost             |
 | Hypothesis Validation Rate   | IoS-004 Backtest Results   | g1_validated / g0_submitted             |
 | Paper Trading Performance    | Alpaca Paper API           | Realized P&L from broker                |

 2. Removed Vanity Metrics (cannot be mathematically proven):
   - ~~"Chain Integrity Score >0.9"~~ → No ground truth definition
   - ~~"InForage Scent Accuracy >80%"~~ → No labeled dataset
 3. New Audit-Compliant Metrics:
 | Metric                     | Formula                              | Source Table        |
 |----------------------------|--------------------------------------|---------------------|
 | IKEA False Negative Rate   | (claims_hallucinated / total_claims) | vega.sampling_audit |
 | InForage Budget Efficiency | (value_generated / cost_incurred)    | inforage_cost_log   |
 | SitC Plan Completion Rate  | (plans_completed / plans_started)    | chain_of_query      |


 ---
 MANDATE VIII COMPLIANCE: Role Isolation (MIT Quad)

 Requirement: IKEA/InForage/SitC outputs are Evidence, not Truth. Must reside in fhq_meta.

 Implementation:

 1. Schema Boundary Enforcement:
 | Schema     | Purpose               | IKEA/InForage/SitC Access        |
 |------------|-----------------------|----------------------------------|
 | fhq_data   | Canonical Market Data | ❌ READ-ONLY                     |
 | fhq_market | Canonical Truth       | ❌ NO ACCESS                     |
 | fhq_meta   | Context & Evidence    | ✅ WRITE (logs, classifications) |
 | fhq_alpha  | Alpha Proposals       | ✅ WRITE (via G0 process only)   |

 2. Port-of-Admittance Enforcement:
   - Cognitive outputs (IKEA classifications, InForage decisions) → fhq_meta.*
   - To become Truth → Must pass through G0-G4 gates → fhq_alpha.*
   - Never direct write to fhq_data.* or fhq_market.*
 3. Code Enforcement - All cognitive engine writes must use:
 ALLOWED_SCHEMAS = ['fhq_meta', 'fhq_optimization']

 def validated_insert(self, schema: str, table: str, data: dict):
     if schema not in ALLOWED_SCHEMAS:
         raise MITQuadViolation(f"Cognitive engine cannot write to {schema}")
     # Proceed with insert

 ---
 APPENDIX A: SCHEMA INTEGRITY REPORT (Mandate VII)

 Generated: 2025-12-17
 Verification Method: Direct PostgreSQL query against production database

 | Schema           | Table                     | Row Count | Status          |
 |------------------|---------------------------|-----------|-----------------|
 | fhq_meta         | aci_state_snapshot_log    | 0         | EXISTS (empty)  |
 | fhq_meta         | chain_of_query            | 0         | EXISTS (empty)  |
 | fhq_meta         | cognitive_engine_evidence | 0         | EXISTS (empty)  |
 | fhq_meta         | knowledge_boundary_log    | 0         | EXISTS (empty)  |
 | fhq_meta         | search_foraging_log       | 0         | EXISTS (empty)  |
 | fhq_optimization | inforage_cost_log         | 10        | EXISTS (active) |
 | fhq_alpha        | g0_draft_proposals        | 154       | EXISTS (active) |
 | fhq_alpha        | g1_validated_signals      | 91        | EXISTS (active) |
 | fhq_alpha        | backtest_queue            | 2         | EXISTS (active) |
 | fhq_alpha        | backtest_results          | 144       | EXISTS (active) |
 | fhq_execution    | paper_trade_outcomes      | 0         | EXISTS (empty)  |
 | fhq_execution    | learning_updates          | 0         | EXISTS (empty)  |

 Migration Reference: Migration 102 (cognitive engine registration), Migration 129 (ACI console infrastructure)

 Schema Hash: To be computed at implementation time via pg_dump --schema-only | sha256sum