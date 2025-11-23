ADR-003_2026_PRODUCTION
FjordHQ Institutional Standards & Compliance Framework

Canonical Version: 2026.PROD.2
Status: Active
Phase: CANONICAL
Owner: LARS (CSO)
Constitutional Authority: ADR-001_2026_PRODUCTION
Effective Date: 2026-01-01

1. Purpose

This Architecture Decision Record establishes FjordHQ’s Institutional Standards & Compliance Framework. It binds:

internal constitutional requirements (ADR-001 → ADR-002)

institutional governance (LARS, STIG, GOV/VEGA)

external regulatory-grade standards (ISO/IEC 42001, DORA, GIPS 2020, SMCR analogues)

…into a single, enforceable architecture.

ADR-003 defines the institutional operating system for FjordHQ:
how decisions are governed, how models are controlled, how failures escalate, how regulatory-grade integrity is preserved, and how accountability is assigned.

This is a mandatory requirement for the activation of GOV (VEGA).

2. Scope

ADR-003 governs all institutional processes that sit above technical execution (STIG) and below constitutional audit (ADR-002).

2.1 Domains Covered

Governance roles & senior manager functions (SMF model)

AI governance and AI-specific risk controls

Change approvals

Escalation thresholds

External regulatory alignment

Bias, drift, adversarial risk

Transparency & Explainability (XAI)

Oversight of ALL:

signals

models

datasets

strategy logic

execution logic

performance reporting

2.2 Systems Governed

fhq_meta.* (registry, audit log, version history)

fhq_research.* (models, signals, attribution)

fhq_execution.* (orders, P&L, slippage, reconciliation)

fhq_monitoring.* (incident logs, adversarial anomalies)

3. Constitutional Alignment (ADR-001 → ADR-002 → ADR-003)

ADR-003 derives its authority from ADR-001 and is enforced by ADR-002.

It adds institutional rules that guarantee:

3.1 No governance vacuum

Every canonical artifact must have:

Named Owner (SMF)

Approver (CEO)

Certifier (GOV/VEGA after activation)

3.2 No orphaned decisions

If an SMF becomes inactive → responsibility automatically transfers to CEO until reassignment.

3.3 No unbounded changes

ADR-004 (Change Gates) is subordinate to ADR-003.
ADR-003 defines who may pass the gates;
ADR-004 defines how gates operate.

4. Roles & Institutional Responsibilities
4.1 CEO

final constitutional authority

assigns SMF roles

triggers constitutional review

approves all canonical ADRs

4.2 LARS (CSO)

owns institutional structure & governance logic

cannot certify models

cannot override audit

defines compliance frameworks and policy interpretation

4.3 STIG (CTO)

executes approved changes

performs canonicalization

performs checks (hash, lineage, integrity)

maintains registries

cannot approve or certify anything

4.4 GOV (VEGA) – Audit & Governance AI

Activated after ADR-001 → ADR-005 canonical.

VEGA responsibilities:

daily integrity control

weekly reconciliation

adversarial detection escalation

bias/drift monitoring

certification of models & ADRs

generation of audit evidence

VEGA is the enforcement engine for ADR-003.

4.5 Senior Manager Functions (SMFs)

Mapping inspired by SMCR/MAIFA:

SMF	Role	Responsibility
SMF-1	Data Integrity Officer	lineage, quality, provenance
SMF-2	AI Governance Officer	bias, drift, XAI, MDLC
SMF-3	Model Risk Officer	adversarial robustness, testing
SMF-4	Operational Resilience Officer	DORA, TLPT, availability
SMF-5	Performance Integrity Officer	GIPS, attribution, composites
SMF-0	CEO	final accountability

All SMFs must sign their area’s canonical certification after VEGA activation.

5. Mandatory Standards

ADR-003 mandates adoption of four regulatory-grade standards.

5.1 ISO/IEC 42001 – Artificial Intelligence Management System (AIMS)

This is mandatory.

What must be implemented:

documented MDLC

formalised fairness metrics

required XAI coverage levels

pre-deployment bias & security testing

continuous monitoring for drift

adversarial robustness requirements

traceable model versioning

Required governance outputs:

Model Fact Sheet (canonical)

Explainability Report

Bias & Drift Log

Adversarial Risk Assessment

5.2 DORA – Digital Operational Resilience Act

ADR-003 mandates:

full DORA compliance

ICT risk management

vendor risk contracts

operational resilience architecture

TLPT every 3 years

mandatory incident reporting

Mapping rule:
Any Class A event from ADR-002 that impacts integrity, availability, or confidentiality must trigger a DORA Major Incident Assessment within 30 minutes.

5.3 GIPS 2020 – Performance Standards

Mandatory rules:

NO synthetic composites

NO combining composites

NO reporting of simulated performance as real

All composite outputs must map to canonical trade logs

TWR, dispersion metrics, asset totals must be archived canonically

5.4 SMCR / MAIFA Accountability Principles

every critical function has a named SMF

responsibilities map stored canonically

no “collective responsibility” allowed

6. Automation Requirements

ADR-003 makes audit/compliance automation mandatory, not optional.

6.1 Required automations

daily integrity checks

weekly reconciliation

bias/drift monitors

adversarial detectors

change-control gate logs

lineage verification

DORA-incident triage

6.2 Automation Evidence

Evidence of automation must be included in:

monthly canonical snapshot

annual constitutional review

7. Escalation Framework

ADR-003 formalizes the following escalation logic:

7.1 Class B → Class A Pre-Failure Escalation

If ≥5 Class B failures occur in 7 days, ADR-003 mandates:

→ automatic trigger of Canonical Reconciliation Protocol (ADR-002 Steps 1–5)
→ SMF review
→ CEO notification

7.2 Adversarial Events = Intentional Class A

Any confirmed adversarial model manipulation constitutes a Class A critical event requiring:

immediate CRP

DORA major incident review

adversarial forensic record

7.3 Governance Drift

If an SMF assignment becomes invalid:

system enters Pre-Failure State

CEO takes temporary control

reassignment required within 48 hours

8. Model Development Lifecycle (MDLC)

ADR-003 mandates a canonical, audit-ready MDLC pipeline.

Stages:

Design

Data Qualification

Bias & Security Testing

Adversarial Robustness Validation

Explainability Certification

Shadow Deployment (Paper Trading)

Canonical Certification (VEGA)

Production Deployment

Continuous Monitoring

No model may reach canonical status without:

valid XAI report

adversarial robustness certificate

fairness metrics

drift baseline

lineage logs

9. Registry & Evidence Requirements

VEGA enforces the following evidence structure:

SHA-256 hashes on all artifacts

versioned lineage

SMF sign-off

CEO approval

automated monitoring logs

DORA-incident triage logs

GIPS-compliant performance archives

10. External Alignment Matrix
Regulation	Mandatory Action	ADR-002 Interaction
DORA	Major incident reporting, TLPT, ICT controls	Class A triggers triage
ISO 42001	AI governance, bias, drift, security	MDLC validation
GIPS	Strict composite rules	Performance lineage
SMCR	Individual responsibility	SMF mapping
11. Dependencies

ADR-003 depends on:

ADR-001 (Constitution)

ADR-002 (Audit Charter)

ADR-004 (Change Gates)

It must be in place before:

ADR-005

VEGA activation

12. Signatures

Approved by: CEO
Owned by: LARS (CSO)
To be certified after activation: GOV (VEGA)

Canonical Authority: ADR-001_2026_PRODUCTION

END OF ADR-003_2026_PRODUCTION (2026.PROD.2)