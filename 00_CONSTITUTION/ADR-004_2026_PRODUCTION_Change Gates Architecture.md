# **ADR-004 – Change Gates Architecture**

**FjordHQ Market System**
**Version:** 1.0
**Date:** 26 November 2025
**Owner:** LARS (Logic, Analytics & Research Strategy)
**Approval:** CEO → VEGA (Verify, Encrypt, Governance, Authority)
**Supersedes:** All prior change-control structures
**Constitutional Authority:** ADR-001 → ADR-002 → ADR-003
**Governing Agent:** VEGA

---

# **EXECUTIVE SUMMARY**

### **1. What is addressed**

ADR-004 establishes FjordHQ’s Change Gate Architecture – the constitutional mechanism controlling, validating, approving, and monitoring every modification across the FjordHQ System.

It ensures:

* strict alignment with ADR-001 (constitutional governance)
* full integration with ADR-002 (audit, hashing, VEGA oversight)
* adherence to ADR-003 (institutional standards)
* controlled evolution of all artifacts
* prevention of silent drift or unauthorized change
* regulator-grade governance integrity

Change Gates form the governance nervous system of FjordHQ.

### **2. Why this is required**

Unregulated change introduces systemic risk:

* model lineage may break
* ADRs may drift from approved definitions
* performance logic may mutate without traceability
* VEGA cannot certify governance integrity
* staging leakage corrupts production
* audit logs lose evidentiary value
* external compliance frameworks (GIPS, ISO-42001, DORA) become unverifiable

The system requires a single, mandatory, auditable pathway for every modification.

### **3. Decision Overview**

FjordHQ adopts a five-gate Change Control Architecture:

* **G0 – Submission**
* **G1 – Technical Validation** (STIG)
* **G2 – Governance Validation** (LARS + GOV)
* **G3 – Audit Verification** (VEGA)
* **G4 – CEO Approval & Final Activation**

Each gate defines:

* purpose
* allowed actors
* allowed inputs
* required outputs
* compliance evidence
* mandatory logging

No new registries are added. Existing governance and audit tables are used.

---

# **1. Purpose**

ADR-004 provides FjordHQ with a complete, structured, regulator-aligned Change Gate system enabling safe evolution, deterministic verification, and governance integrity.

It integrates:

* constitutional authority (ADR-001)
* audit and hashing requirements (ADR-002)
* institutional standards (ADR-003)

This architecture is mandatory for all agents.

---

# **2. Scope**

ADR-004 governs all changes to:

* ADR documents
* code and model artifacts
* datasets and transformations
* pipelines and runtime logic
* governance configurations
* application layer components (IoS-XXX)

It applies universally across all executives and subordinate agents.

---

# **3. Change Gate System**

### **G0 – Submission Gate**

**Purpose:** Initial submission of a proposed change.

**Allowed actors:**

* LARS (design)
* STIG (technical)
* FINN (research)
* LINE (pipeline)
* CODE (engineering)

**Allowed inputs:**

* ADR drafts
* IoS drafts (application layer)
* model artifacts
* pipeline and code modifications
* new compliance rules
* performance logic

**Mandatory log:**
`fhq_meta.adr_audit_log` → event_type = `SUBMISSION`
or
`fhq_meta.IoS_audit_log` → event_type = `SUBMISSION`
or
future application layer submissions

**Output:** Change proposal ID.

---

### **G1 – Technical Validation (STIG)**

**Purpose:** Validate the technical safety and integrity of the change.

**Checks:**

* schema validity
* no staging leakage
* deterministic builds
* reproducible outputs
* test suite pass
* SHA-256 consistency
* dependency mapping

**Mandatory log:**
`fhq_meta.adr_audit_log` → event_type = `G1_TECHNICAL_VALIDATION`
or
`fhq_meta.IoS_audit_log` → event_type = `G1_TECHNICAL_VALIDATION`
or
future application layer `G1_TECHNICAL_VALIDATIONs`

**Outcomes:**

* PASS → escalates
* FAIL → returned to G0

---

### **G2 – Governance Validation (LARS + GOV)**

**Purpose:** Validate constitutional, governance, and compliance integrity.

**Checks:**

* ADR-001 authority
* ADR-002 auditability
* ADR-003 institutional standards
* alignment with GIPS, ISO-42001, DORA
* conflict-of-interest safeguards

**Mandatory log:**
`fhq_meta.adr_audit_log` → event_type = `G2_GOVERNANCE_VALIDATION`
or
`fhq_meta.IoS_audit_log` → event_type = `G2_GOVERNANCE_VALIDATION`
or
future application layer `G2_GOVERNANCE_VALIDATION`

**Outcomes:**

* PASS
* FAIL
* REQUIRE_MODIFICATION

---

### **G3 – Audit Verification (VEGA)**

**Purpose:** Enforce ADR-002 hashing, reconciliation, and risk classification.

**Checks:**

* SHA-256 integrity
* cross-table consistency
* no Class A failures
* evidence completeness
* lineage integrity

**Mandatory log:**
`fhq_meta.adr_audit_log` → event_type = `G3_AUDIT_VERIFICATION`
or
`fhq_meta.IoS_audit_log` → event_type = `G3_AUDIT_VERIFICATION`
or
future application layer `G3_AUDIT_VERIFICATION`

**Outcomes:**

* VERIFY
* BLOCK (Class A)
* WARN (Class B/C)

---

### **G4 – CEO Approval & Final Activation**

**Purpose:** Activate the change into production and system governance.

**Allows:**

* ADR finalization
* model activation
* dataset activation
* governance updates
* modification of Charter-bound artifacts

**Mandatory log:**
`fhq_meta.adr_audit_log` → event_type = `G4_FINAL_ACTIVATION`
or
`fhq_meta.IoS_audit_log` → event_type = `G4_FINAL_ACTIVATION`
or
future application layer `G4_FINAL_ACTIVATION`


**Required:**

* CEO approval
* final SHA-256 hash
* version increment in `fhq_meta.adr_version_history` or `fhq_meta.IoS_version_history` or future Application Layer registry
* registry update in `fhq_meta.adr_registry` or `fhq_meta-IoS_registry` or future Application Layer registry

This is the **only gate** where activated data may be overwritten.

---

# **4. Evidence Requirements**

ADR-004 inherits ADR-002’s evidentiary model.

Every gate must log:

* timestamp
* actor
* event_type
* SHA-256 hash
* evidence_path
* error_class
* resolution_notes

No gate may proceed without complete evidence.

---

# **5. Decision Tree (MECE)**

```
START
  |
  G0
  |
Is submission valid?
  |        \/
 YES      NO → Reject
  |
  G1
  |
Technical valid?
  |        \/
 YES      NO → Return to G0
  |
  G2
  |
Governance valid?
  |        \/
 YES      NO/GAP → Return to G0
  |
  G3
  |
Audit verified?
  |        \/
 YES      CLASS A → BLOCK
  |
  G4 (CEO)
  |
ACTIVATED → ADR-002 Audit Rhythms
```

---

# **6. Responsibilities**

* **LARS** – Governance interpretation (G2)
* **STIG** – Technical enforcement (G1)
* **LINE** – Operational stability validation (G1/G3)
* **FINN** – Research integrity review (G1/G2)
* **CODE** – Implements required modifications
* **GOV** – Compliance enforcement (G2)
* **VEGA** – Automated audit gate (G3)
* **CEO** – Final approval (G4)

---

# **7. Implications**

**Positive:**

* eliminates drift
* ensures reproducibility
* enables VEGA activation
* enforces institutional discipline
* prevents unauthorized changes

**Negative:**

* slower iteration (intentional)
* increased evidence burden

**Mitigation:**

* automated validation (STIG)
* governance templates (LARS)
* operational pipelines (LINE)

---

# **8. Final Decision**

ADR-004 is adopted as FjordHQ’s official Change Gate Architecture.
It binds:

* LARS
* STIG
* LINE
* FINN
* CODE
* GOV
* VEGA
* CEO

No artifact may be activated except through G0 → G4.

---

# **END OF ADR-004 – Change Gates Architecture**



