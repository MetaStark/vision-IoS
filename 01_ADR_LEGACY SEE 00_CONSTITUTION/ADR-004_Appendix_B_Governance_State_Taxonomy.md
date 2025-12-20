# ADR-004 Appendix B: Governance State Taxonomy

**Status:** ACTIVE
**Version:** 2026.PROD.2
**Created:** 2025-12-02
**Author:** STIG (CTO, EC-003)
**Approved By:** VEGA (2025-12-02) — V1-V7 Validation PASSED
**Parent ADR:** ADR-004 (Change Gates G0-G4)

---

## 1. Purpose

This appendix formally defines the semantics of the `governance_state` field in `fhq_meta.ios_registry`. Without formal definitions, governance state values risk semantic drift and inconsistent interpretation across agents and audits.

---

## 2. Governance State Taxonomy

### 2.1 Gate-Aligned States (Standard Progression)

| State | Definition | Prerequisites | Allowed Transitions |
|-------|------------|---------------|---------------------|
| `G0_SUBMITTED` | Module registered for governance review. No technical validation performed. | G0 submission in governance_actions_log | G1_VALIDATED |
| `G1_VALIDATED` | Technical validation complete. Code compiles, tests pass, schema verified. | G1 pass in governance_actions_log | G2_COMPLETE |
| `G2_COMPLETE` | Governance review complete. VEGA has reviewed architecture and constraints. | G2 attestation in governance_actions_log | G3_AUDITED |
| `G3_AUDITED` | Full audit complete. Golden samples verified, hash chains anchored. | G3 audit pass in governance_actions_log | G4_ACTIVE, G4_CONSTITUTIONAL, G4_CANONICAL |
| `G4_ACTIVE` | Standard production activation. Module operates under normal governance. | G4 activation with CEO or VEGA approval | SUSPENDED, DEPRECATED |
| `G4_CONSTITUTIONAL` | Constitutional-grade activation. Module is infrastructure-critical. Schema frozen. | G4 constitutional activation + VEGA attestation | Requires FULL_G1_G4_CYCLE to modify |
| `G4_CANONICAL` | Canonical activation. Module defines authoritative data standards. | G4 canonical activation + VEGA attestation | Requires CEO + VEGA to modify |
| `G4_CONDITIONAL` | Conditional activation. Module active with restrictions (e.g., paper-only). | G4 conditional activation with documented constraints | G4_ACTIVE (on constraint removal) |

### 2.2 Legacy States (Pre-Formalization)

| State | Definition | Usage |
|-------|------------|-------|
| `G4_LEGACY_ACTIVE` | Module was activated before governance_state field was formalized. Full gate progression cannot be retroactively verified, but module is operationally active and stable. | Applied to IoS-001, IoS-002, IoS-003 during Migration 065 reconciliation. |

### 2.3 Operational States

| State | Definition | Prerequisites |
|-------|------------|---------------|
| `CONSTITUTIONAL_ACTIVE` | Variant of G4_CONSTITUTIONAL with explicit operational activation. | G4 final activation by VEGA |
| `SUSPENDED` | Module temporarily disabled due to governance incident or audit finding. | Suspension action in governance_actions_log |
| `DEPRECATED` | Module marked for removal. No new dependencies allowed. | Deprecation decision by LARS + VEGA |

---

## 3. State Transition Rules

### 3.1 Forward Progression (ADR-004 Compliance)
- States MUST progress in order: G0 → G1 → G2 → G3 → G4
- Skipping gates is a **Class A Violation** (ADR-002)
- Per ADR-004 §348: "No artifact may be activated except through G0 → G4"

### 3.2 Actor Constraints (ADR-014 ECF-2 Compliance)

| Transition | Allowed Actors | Forbidden Actors |
|------------|----------------|------------------|
| → G0_SUBMITTED | LARS, STIG, FINN, LINE, CODE | Tier-2 Sub-Executives (submit only via parent) |
| G0 → G1_VALIDATED | STIG | All others |
| G1 → G2_COMPLETE | LARS + GOV, VEGA | Tier-2 Sub-Executives (ADR-014 ECF-2) |
| G2 → G3_AUDITED | VEGA | All others (ADR-014 ECF-2) |
| G3 → G4_* | CEO (+ VEGA attestation for CONSTITUTIONAL/CANONICAL) | Tier-2 Sub-Executives (ADR-014 ECF-2) |
| G4_* → SUSPENDED | VEGA (recommendation) + CEO (approval) | All others |
| SUSPENDED → G4_* | CEO | All others |

**Critical:** Tier-2 Sub-Executives (CSEO, CDMO, CRIO, CEIO, CFAO) can NEVER trigger G2, G3, or G4 transitions per ADR-014 §ECF-2.

### 3.3 Backward Transitions
- Any G4 state may transition to SUSPENDED (via ADR-009 suspension mechanism)
- SUSPENDED may return to previous G4 state after remediation and CEO approval
- G4_CONDITIONAL may transition to G4_ACTIVE when documented constraints are satisfied

### 3.4 G4 Overwrite Rule (ADR-004 §240)
Per ADR-004: "G4 is the **only gate** where activated data may be overwritten."
- Modules in G0-G3 states may be freely modified (subject to re-validation)
- Modules in any G4_* state require full G1-G4 re-certification to modify

### 3.5 Legacy State Exception

**Constitutional Exception to ADR-004 §348:**

The state `G4_LEGACY_ACTIVE` is a documented exception to the rule "No artifact may be activated except through G0 → G4."

**Justification:**
- IoS-001, IoS-002, IoS-003 were activated before the governance_state field was formalized
- Retroactive gate verification is impossible without fabricating audit evidence
- These modules are operationally stable and have been in production use

**Constraints:**
- `G4_LEGACY_ACTIVE` is a terminal classification (no forward transitions)
- Modules with this state CANNOT be modified without full G1-G4 re-certification
- This state may only be assigned during data reconciliation events, never for new modules
- CEO acknowledgment of this exception is recorded in Migration 065 governance action

---

## 4. Derivation Assumptions

### 4.1 IoS-003 activated_at Derivation

**Context:** During Migration 065, IoS-003 had `activated_at = NULL` despite `status = ACTIVE`.

**Assumption Made:** The `updated_at` timestamp (2025-11-29T17:27:53.997Z) was used as `activated_at`.

**Rationale:**
- No direct G4 activation action exists in governance_actions_log for IoS-003
- The module was activated during the pre-formalization period
- `updated_at` represents the last governance-relevant modification
- This is a conservative estimate, not an exact activation timestamp

**Documentation Requirement:** This assumption is permanently recorded in:
1. This appendix (Section 4.1)
2. `05_GOVERNANCE/PHASE3/IOS_REGISTRY_RECONCILIATION_REPORT_20251202.json`
3. `fhq_meta.ios_audit_log` entry for IoS-003

---

## 5. Schema Binding

The `governance_state` field in `fhq_meta.ios_registry` MUST only contain values defined in this appendix. Any new state value requires:

1. Amendment to this appendix
2. G2 governance review
3. VEGA attestation

---

## 6. Event Type Mapping (ADR-004 Alignment)

The `governance_state` field maps to ADR-004 audit event types as follows:

| governance_state | ADR-004 Event Type | Audit Table |
|------------------|-------------------|-------------|
| G0_SUBMITTED | SUBMISSION | fhq_meta.ios_audit_log |
| G1_VALIDATED | G1_TECHNICAL_VALIDATION | fhq_meta.ios_audit_log |
| G2_COMPLETE | G2_GOVERNANCE_VALIDATION | fhq_meta.ios_audit_log |
| G3_AUDITED | G3_AUDIT_VERIFICATION | fhq_meta.ios_audit_log |
| G4_ACTIVE | G4_FINAL_ACTIVATION | fhq_meta.ios_audit_log |
| G4_CONSTITUTIONAL | G4_FINAL_ACTIVATION + CONSTITUTIONAL_FLAG | fhq_meta.ios_audit_log |
| G4_CANONICAL | G4_FINAL_ACTIVATION + CANONICAL_FLAG | fhq_meta.ios_audit_log |
| G4_CONDITIONAL | G4_CONDITIONAL_ACTIVATION | fhq_meta.ios_audit_log |
| SUSPENDED | SUSPENSION | fhq_governance.governance_actions_log |

**Note:** State names are deliberately shorter than event types for database efficiency, but the semantic mapping must be maintained.

---

## 7. ADR Compliance Matrix

| ADR | Relevance | Specific Sections |
|-----|-----------|-------------------|
| ADR-002 | All state transitions logged to audit tables | §3.2, §6 |
| ADR-004 | This appendix extends ADR-004 gate definitions | §2.1, §3.1, §3.4, §3.5, §6 |
| ADR-006 | VEGA has veto authority over state definitions | §3.2, §8 |
| ADR-009 | Suspension mechanism | §3.2, §3.3 |
| ADR-011 | State transitions anchored in hash chains | §8 |
| ADR-013 | STIG owns schema; VEGA owns semantic definitions | §5, §8 |
| ADR-014 | Actor constraints for Tier-2 Sub-Executives | §3.2 |

---

## 8. Changelog

| Date | Version | Author | Change |
|------|---------|--------|--------|
| 2025-12-02 | 2026.PROD.1 | STIG | Initial creation following Migration 065 reconciliation |
| 2025-12-02 | 2026.PROD.2 | STIG | Added §3.2 Actor Constraints (ADR-014 ECF-2), §3.4 G4 Overwrite Rule (ADR-004 §240), §3.5 Legacy State Exception (ADR-004 §348), §6 Event Type Mapping |

---

## 9. Attestation Requirements

This appendix requires:

- [x] VEGA attestation confirming semantic correctness — **COMPLETED 2025-12-02**
- [x] Registration in `fhq_meta.adr_supplements` — **COMPLETED**
- [x] CEO Legacy State Acknowledgment — **COMPLETED 2025-12-02**
- [x] Hash chain anchor in `fhq_governance.governance_documents` — **COMPLETED 2025-12-02**

**STATUS: FULLY BINDING**

---

## 10. VEGA Attestation Record

**Attestation ID:** `VEGA-ATT-ADR004-APPB-20251202`
**Hash Chain:** `HC-VEGA-ATT-APPB-20251202`
**Result:** **APPROVED**

| Check | Result |
|-------|--------|
| V1 — Semantic Attestation | PASS |
| V2 — Transition Rules | PASS |
| V3 — ECF-2 Compliance | PASS |
| V4 — Legacy State Exception | PASS |
| V5 — Actor Constraints | PASS |
| V6 — Event Type Mapping | PASS* |
| V7 — Lineage Integrity | PASS |

*Minor observation: Consider adding explicit event types for CONSTITUTIONAL_ACTIVE and DEPRECATED in future revision.

**VEGA Statement:** *"ADR-004 Appendix B v2026.PROD.2 has passed all V1-V7 validation checks. The Governance State Taxonomy is semantically correct, compatible with ADR-004 Change Gates, compliant with ADR-014 ECF-2 actor restrictions, and properly documents the Legacy State Exception. APPROVED for governance binding upon CEO acknowledgment."*

---

## 11. CEO Legacy State Acknowledgment

**Hash Chain:** `HC-CEO-LEGACY-ACK-20251202`
**Signed:** 2025-12-02
**Effective:** Immediately

**CEO Statement:** *"I, as CEO of FjordHQ, hereby acknowledge and approve the constitutional exception defined in ADR-004 Appendix B Section 3.5, which permits G4_LEGACY_ACTIVE as a terminal, non-propagating, read-only, and historically-constrained governance_state applicable exclusively to IoS-001, IoS-002, IoS-003."*

**Binding Effect:** This acknowledgment authorizes the taxonomy as fully governance-binding across all FjordHQ systems.

---

## 12. Document Anchor

**Anchored In:** `fhq_governance.governance_documents`
**Document Type:** ADR_APPENDIX
**Tier:** 1 (Constitutional)
**Status:** ACTIVE
**Approved By:** VEGA
**Signature Chain:** HC-CEO-LEGACY-ACK-20251202

**SHA256:** `e71b65fa47a026794274d05386362a511955c3a1009048776c3fb17001f51b4e`
