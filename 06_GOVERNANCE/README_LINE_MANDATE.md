# LINE MANDATE REGISTRATION – IMPLEMENTATION GUIDE

**Change Proposal:** G0-2025-11-23-LINE-MANDATE
**Status:** G0 Submitted → Awaiting G1 (STIG Technical Validation)
**Date:** 2025-11-23
**Authority:** CODE (executing on behalf of LARS)
**Compliance:** ADR-004, ADR-007, ADR-008, ADR-012

---

## EXECUTIVE SUMMARY

This implementation registers **LINE** (Live Infrastructure & Node Engineering) as an operational agent with expanded LLM and API provider support, establishing a comprehensive **Economic Safety Layer** (ADR-012) to prevent cost overruns, rate limit violations, and runaway reasoning loops.

### What Was Built

1. **ADR Governance Infrastructure** (ADR-004)
   - G0-G4 change gate tracking
   - Immutable audit trail with hash chains
   - Version management for all ADRs

2. **Economic Safety Layer** (ADR-012)
   - Rate limits (calls/min, daily caps)
   - Cost limits (per-call, per-task, per-day)
   - Execution limits (LLM steps, latency, tokens)
   - Violation tracking and enforcement

3. **Provider Routing Policies** (ADR-007)
   - Tier-based LLM access (TIER1/TIER2/TIER3)
   - Agent-specific provider assignments
   - Data sharing controls

4. **Ed25519 Key Management** (ADR-008)
   - Key lifecycle tracking (PENDING → ACTIVE → DEPRECATED → ARCHIVED)
   - Multi-tier archival (Hot/Warm/Cold)
   - 7-year retention compliance

5. **Agent Contracts** (ADR-001)
   - Executive role definitions (7 agents)
   - Inter-agent communication rules
   - Mandate scope and authority boundaries

---

## QUICK START

### Prerequisites
- PostgreSQL 17.6+ running on port 54322
- Supabase local instance configured
- Migration 001 (Vision-IoS Foundation) executed
- Migration 017 (Orchestrator Registration) executed

### Installation Steps

#### 1. Execute Migration 018
```bash
cd /home/user/vision-IoS/04_DATABASE/MIGRATIONS/
psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -f 018_line_mandate_governance_economic_safety.sql
```

#### 2. Verify Installation
```sql
-- Check all tables created
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema IN ('fhq_meta', 'fhq_governance', 'vega')
  AND table_name IN (
    'adr_registry', 'adr_audit_log', 'adr_version_history',
    'agent_keys', 'key_archival_log',
    'executive_roles', 'agent_contracts', 'model_provider_policy',
    'llm_rate_limits', 'llm_cost_limits', 'llm_execution_limits',
    'llm_usage_log', 'llm_violation_events'
  )
ORDER BY table_schema, table_name;

-- Expected: 13 tables
```

#### 3. Verify G0 Submission Logged
```sql
SELECT
    change_proposal_id,
    event_type,
    gate_stage,
    initiated_by,
    decision,
    timestamp
FROM fhq_meta.adr_audit_log
WHERE change_proposal_id = 'G0-2025-11-23-LINE-MANDATE';

-- Expected: 1 row (G0 SUBMISSION by CODE)
```

#### 4. Verify LIVE_MODE=False
```sql
SELECT
    'llm_rate_limits' AS table_name,
    COUNT(*) FILTER (WHERE live_mode = TRUE) AS live_mode_true_count
FROM vega.llm_rate_limits
UNION ALL
SELECT 'llm_cost_limits', COUNT(*) FILTER (WHERE live_mode = TRUE)
FROM vega.llm_cost_limits
UNION ALL
SELECT 'llm_execution_limits', COUNT(*) FILTER (WHERE live_mode = TRUE)
FROM vega.llm_execution_limits;

-- Expected: All counts = 0 (CRITICAL SAFETY REQUIREMENT)
```

---

## ARCHITECTURE OVERVIEW

### Schema Organization

```
fhq_meta (Metadata & Audit)
├── adr_registry              # ADR catalog
├── adr_audit_log             # G0-G4 change gates (hash-chained)
├── adr_version_history       # ADR version lineage
├── agent_keys                # Ed25519 key lifecycle
└── key_archival_log          # Key rotation audit

fhq_governance (Governance & Contracts)
├── executive_roles           # Agent definitions (7 roles)
├── agent_contracts           # Inter-agent mandates
└── model_provider_policy     # LLM routing policies (tier-based)

vega (Economic Safety Layer)
├── llm_rate_limits           # Call frequency limits
├── llm_cost_limits           # Budget ceilings
├── llm_execution_limits      # Reasoning step limits
├── llm_usage_log             # Detailed call tracking
└── llm_violation_events      # Enforcement actions
```

### Provider Tier Model (ADR-007)

```
┌─────────────────────────────────────────────────────────────┐
│ TIER 1 – High Sensitivity (No Data Sharing)                │
├─────────────────────────────────────────────────────────────┤
│ LARS  → Anthropic Claude Haiku ($0.08/call, 100/day)       │
│ VEGA  → Anthropic Claude Haiku ($0.08/call, 50/day)        │
│                                                             │
│ Use: Strategic decisions, governance, compliance audits    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ TIER 2 – Medium Sensitivity (No Data Sharing)              │
├─────────────────────────────────────────────────────────────┤
│ FINN  → OpenAI GPT-4 Turbo ($0.04/call, 150/day)          │
│         Fallback: Anthropic Claude Haiku                   │
│                                                             │
│ Use: Research analysis, signal generation, market intel    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ TIER 3 – Low Sensitivity (Data Sharing Allowed)            │
├─────────────────────────────────────────────────────────────┤
│ STIG  → DeepSeek Chat ($0.005/call, 200/day)              │
│         Fallback: OpenAI GPT-4 Turbo                       │
│ LINE  → DeepSeek Chat ($0.005/call, 300/day)              │
│         Fallback: OpenAI GPT-4 Turbo                       │
│                                                             │
│ Use: Technical validation, infrastructure ops, SRE         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ API Providers (Data/Search)                                 │
├─────────────────────────────────────────────────────────────┤
│ Serper     → 5/min     (Web search, news)                  │
│ Scholar    → 3/min     (Academic papers)                   │
│ Coindesk   → 10/min    (Crypto prices)                     │
│ Marketaux  → 5/min, 100/day (Financial news, sentiment)    │
│ FRED       → 10/min, 120/day (Economic data, Fed stats)    │
└─────────────────────────────────────────────────────────────┘
```

---

## ECONOMIC SAFETY LAYER (ADR-012)

### Three Pillars of Protection

#### 1. Rate Governance (Prevent API Abuse)
```sql
-- Per-Agent Limits
LARS/VEGA (Anthropic): 3 calls/min, 5 calls/execution
FINN (OpenAI):         5 calls/min, 10 calls/execution
STIG/LINE (DeepSeek):  10 calls/min, 15 calls/execution

-- Global Daily Limits
Anthropic: 100 calls/day
OpenAI:    150 calls/day
DeepSeek:  500 calls/day
Marketaux: 100 calls/day
FRED:      120 calls/day
```

**Violation Action:** SWITCH_TO_STUB (use fallback/mock data)

#### 2. Cost Governance (Prevent Budget Overrun)
```sql
-- Daily Budget Ceilings
Per-Agent:
  LARS/FINN: $1.00/day
  VEGA/STIG/LINE: $0.50/day

Global System:
  Anthropic: $5.00/day
  OpenAI:    $3.00/day
  DeepSeek:  $2.00/day
  Total:     $10.00/day MAX
```

**Violation Action:** NOTIFY_VEGA → SUSPEND_AGENT (if critical)

#### 3. Execution Governance (Prevent Runaway Reasoning)
```sql
-- LLM Step Limits (prevent infinite loops)
LARS/VEGA:   3 steps MAX (ABORT if exceeded)
FINN/STIG/LINE: 5 steps MAX (ABORT if exceeded)

-- Latency Limits (prevent hangs)
LARS:        3000ms (WARN)
FINN/STIG/LINE: 5000ms (WARN)

-- Token Generation Limits
LARS/VEGA (Haiku):   4096 tokens MAX output
FINN (GPT-4):        4096 tokens MAX output
STIG/LINE (DeepSeek): 8192 tokens MAX output
```

**Violation Action:** ABORT_TASK → NOTIFY_VEGA

### LIVE_MODE Safety Constraint

**CRITICAL REQUIREMENT:**
```sql
live_mode = FALSE  -- ALL rows in vega.llm_* tables
```

**Cannot be set to TRUE until:**
1. ✅ VEGA completes QG-F6 attestation
2. ✅ LARS approves based on VEGA recommendation
3. ✅ CEO signs off on production readiness

**Enforcement:**
- Database CHECK constraints prevent `live_mode = TRUE` insertion
- Migration 018 sets all rows to `FALSE` by default
- G3 gate (VEGA) must verify before G4 (CEO approval)

---

## G0-G4 CHANGE GATES (ADR-004)

### Current Status: G0 → G1

```
✅ G0 – SUBMISSION (CODE)
   ├─ Change Proposal: G0-2025-11-23-LINE-MANDATE
   ├─ Event Type: MODIFICATION (API/LLM Provider Expansion)
   ├─ Initiated By: CODE
   ├─ Evidence: Migration 018 SQL file
   ├─ Hash Chain: HC-CODE-ADR004-G0-20251123
   └─ Decision: SUBMITTED → G1

⏳ G1 – TECHNICAL VALIDATION (STIG)
   ├─ Owner: STIG (System for Technical Implementation & Governance)
   ├─ Validates: Schema correctness, constraints, indexes
   ├─ Materials: /06_GOVERNANCE/G1_VALIDATION_MATERIALS_LINE_MANDATE.md
   └─ Decision: PASS/FAIL → G2

⏳ G2 – GOVERNANCE VALIDATION (LARS)
   ├─ Owner: LARS (Logic, Analytics & Research Strategy)
   ├─ Validates: Authority boundaries, mandate scope, compliance
   └─ Decision: PASS/FAIL/MODIFY → G3

⏳ G3 – AUDIT VERIFICATION (VEGA)
   ├─ Owner: VEGA (Verification & Governance Authority)
   ├─ Validates: ADR compliance, economic safety enforced
   ├─ Checks: LIVE_MODE=False, hash chains, signatures
   └─ Decision: VERIFY/BLOCK/WARN → G4

⏳ G4 – CANONICALIZATION (CEO)
   ├─ Owner: CEO (Ørjan Skjold)
   ├─ Validates: All gates passed, no blockers
   └─ Decision: APPROVED → Execute migration in production
```

### Next Steps

1. **STIG (G1):** Execute validation queries in G1_VALIDATION_MATERIALS_LINE_MANDATE.md
2. **LARS (G2):** Review provider policies and economic limits
3. **VEGA (G3):** Audit compliance and verify LIVE_MODE=False
4. **CEO (G4):** Final approval and production deployment

---

## DATABASE SCHEMA REFERENCE

### fhq_meta.adr_audit_log
**Purpose:** Immutable audit trail for all ADR changes (G0-G4 gates)

**Key Fields:**
- `change_proposal_id` – Unique identifier (e.g., 'G0-2025-11-23-LINE-MANDATE')
- `event_type` – SUBMISSION, G1_TECHNICAL_VALIDATION, G2_GOVERNANCE_VALIDATION, G3_AUDIT_VERIFICATION, G4_CANONICALIZATION
- `gate_stage` – G0, G1, G2, G3, G4
- `sha256_hash` – Hash chain: `hash(previous_hash || event_data)`
- `hash_chain_id` – Format: `HC-{AGENT}-ADR004-{GATE}-{DATE}`

**Example Query:**
```sql
SELECT
    audit_id,
    change_proposal_id,
    event_type,
    gate_stage,
    initiated_by,
    decision,
    timestamp
FROM fhq_meta.adr_audit_log
WHERE change_proposal_id = 'G0-2025-11-23-LINE-MANDATE'
ORDER BY timestamp;
```

### fhq_governance.model_provider_policy
**Purpose:** LLM provider routing policies per agent tier (ADR-007 §4.5)

**Key Fields:**
- `agent_id` – LARS, STIG, LINE, FINN, VEGA
- `sensitivity_tier` – TIER1_HIGH, TIER2_MEDIUM, TIER3_LOW
- `primary_provider` – ANTHROPIC, OPENAI, DEEPSEEK
- `data_sharing_allowed` – Boolean (FALSE for TIER1/TIER2, TRUE for TIER3)

**Example Query:**
```sql
SELECT
    agent_id,
    sensitivity_tier,
    primary_provider,
    model_name,
    cost_envelope_per_call_usd,
    data_sharing_allowed
FROM fhq_governance.model_provider_policy
ORDER BY sensitivity_tier, agent_id;
```

### vega.llm_rate_limits
**Purpose:** Rate limit governance for LLM and API calls (ADR-012 §3.1)

**Key Fields:**
- `agent_id` – Agent being limited (NULL for global limits)
- `provider` – ANTHROPIC, OPENAI, DEEPSEEK, SERPER, MARKETAUX, FRED, etc.
- `limit_type` – CALLS_PER_MINUTE_PER_AGENT, GLOBAL_DAILY_LIMIT, etc.
- `limit_value` – Integer threshold
- `live_mode` – **MUST BE FALSE** until VEGA attestation

**Example Query:**
```sql
SELECT
    agent_id,
    provider,
    limit_type,
    limit_value,
    enforcement_mode,
    live_mode
FROM vega.llm_rate_limits
WHERE agent_id = 'LINE';
```

### vega.llm_cost_limits
**Purpose:** Cost ceiling enforcement (ADR-012 §3.2)

**Key Fields:**
- `limit_type` – MAX_COST_PER_CALL_USD, MAX_COST_PER_TASK_USD, MAX_COST_PER_AGENT_PER_DAY_USD, MAX_DAILY_COST_GLOBAL_USD
- `limit_value_usd` – Decimal threshold
- `violation_action` – SWITCH_TO_STUB, SUSPEND_AGENT, NOTIFY_VEGA, ESCALATE_TO_LARS

**Example Query:**
```sql
SELECT
    agent_id,
    provider,
    limit_type,
    limit_value_usd,
    violation_action,
    live_mode
FROM vega.llm_cost_limits
WHERE agent_id IN ('LARS', 'STIG', 'LINE', 'FINN', 'VEGA')
ORDER BY limit_value_usd DESC;
```

### vega.llm_usage_log
**Purpose:** Detailed tracking of all LLM and API calls (ADR-012 §4)

**Key Fields:**
- `agent_id`, `provider`, `model_name`
- `input_tokens`, `output_tokens`, `total_tokens`
- `estimated_cost_usd`, `actual_cost_usd`
- `latency_ms`, `llm_steps_used`
- `success`, `error_message`

**Example Usage Query:**
```sql
SELECT
    DATE(timestamp) AS call_date,
    agent_id,
    provider,
    COUNT(*) AS total_calls,
    SUM(total_tokens) AS total_tokens,
    SUM(estimated_cost_usd) AS total_cost_usd
FROM vega.llm_usage_log
WHERE timestamp >= NOW() - INTERVAL '7 days'
GROUP BY DATE(timestamp), agent_id, provider
ORDER BY call_date DESC, total_cost_usd DESC;
```

---

## AGENT ROLES & AUTHORITY

### Executive Roles (ADR-001 §3)

| Agent | Full Name | Authority Level | Domain | VETO Power |
|-------|-----------|----------------|--------|------------|
| **LARS** | Logic, Analytics & Research Strategy | 9 | Strategy, Design, Coordination | ❌ |
| **STIG** | System for Technical Implementation & Governance | 8 | Technical, Implementation, Database | ❌ |
| **LINE** | Live Infrastructure & Node Engineering | 8 | Operations, Infrastructure, SRE | ❌ |
| **FINN** | Financial Investments Neural Network | 8 | Research, Analysis, Markets | ❌ |
| **VEGA** | Verification & Governance Authority | 10 | Compliance, Audit, Governance | ✅ |
| **CODE** | Engineering Execution Unit | - | Execution (no autonomy) | ❌ |
| **CEO** | Chief Executive Officer (Human) | - | Constitutional Authority | ✅ |

### Agent Capabilities

#### LARS (CSO – Chief Strategy Officer)
- Cross-domain coordination
- Strategic evaluation and planning
- System design and architecture
- Escalation resolution (when agents disagree)

#### STIG (CTO – Chief Technical Officer)
- Database schema management and migrations
- Technical constraint validation
- Deployment execution and rollback
- G1 gate owner (technical validation)

#### LINE (CIO – Chief Infrastructure Officer)
- Runtime operations and monitoring
- SRE incident handling
- Pipeline uptime management
- Infrastructure cost optimization

#### FINN (CRO – Chief Research Officer)
- Market research and analysis
- Signal generation and backtesting
- Feature engineering
- RAG (Retrieval-Augmented Generation)

#### VEGA (CCO – Chief Compliance Officer)
- Continuous compliance audits
- Economic safety enforcement
- **VETO POWER** on non-compliant changes
- G3 gate owner (audit verification)
- QG-F6 attestation authority

#### CODE (Execution Unit)
- No autonomous decision-making
- Executes tasks per LARS/STIG/LINE directives
- Pipeline integration scripts
- Git operations and deployments

#### CEO (Human Authority)
- Constitution approval
- Role appointments
- Exception handling
- G4 gate owner (canonicalization)
- Final VETO authority

---

## MONITORING & ALERTS

### Key Metrics to Monitor

#### 1. Economic Safety Violations
```sql
SELECT
    violation_type,
    agent_id,
    provider,
    COUNT(*) AS violation_count,
    MAX(timestamp) AS last_violation
FROM vega.llm_violation_events
WHERE timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY violation_type, agent_id, provider
ORDER BY violation_count DESC;
```

#### 2. Daily Cost Tracking
```sql
SELECT
    DATE(timestamp) AS usage_date,
    agent_id,
    provider,
    SUM(estimated_cost_usd) AS daily_cost_usd,
    COUNT(*) AS call_count
FROM vega.llm_usage_log
WHERE timestamp >= NOW() - INTERVAL '7 days'
GROUP BY DATE(timestamp), agent_id, provider
ORDER BY usage_date DESC, daily_cost_usd DESC;
```

#### 3. Rate Limit Compliance
```sql
WITH hourly_calls AS (
    SELECT
        DATE_TRUNC('hour', timestamp) AS hour,
        agent_id,
        provider,
        COUNT(*) AS calls_per_hour
    FROM vega.llm_usage_log
    WHERE timestamp >= NOW() - INTERVAL '24 hours'
    GROUP BY DATE_TRUNC('hour', timestamp), agent_id, provider
)
SELECT
    h.hour,
    h.agent_id,
    h.provider,
    h.calls_per_hour,
    l.limit_value AS configured_limit,
    CASE
        WHEN h.calls_per_hour > l.limit_value THEN '⚠️ EXCEEDED'
        ELSE '✅ OK'
    END AS compliance_status
FROM hourly_calls h
LEFT JOIN vega.llm_rate_limits l
    ON h.agent_id = l.agent_id
    AND h.provider = l.provider
    AND l.limit_type = 'CALLS_PER_MINUTE_PER_AGENT'
ORDER BY h.hour DESC, compliance_status DESC;
```

#### 4. LIVE_MODE Safety Check
```sql
-- CRITICAL: This query MUST return 0 rows until VEGA attestation
SELECT
    'llm_rate_limits' AS table_name,
    agent_id,
    provider,
    limit_type,
    live_mode
FROM vega.llm_rate_limits
WHERE live_mode = TRUE
UNION ALL
SELECT 'llm_cost_limits', agent_id, provider, limit_type, live_mode
FROM vega.llm_cost_limits
WHERE live_mode = TRUE
UNION ALL
SELECT 'llm_execution_limits', agent_id, provider, limit_type::text, live_mode
FROM vega.llm_execution_limits
WHERE live_mode = TRUE;

-- Expected: 0 rows (if ANY rows returned, BLOCK ALL LLM calls immediately)
```

---

## TROUBLESHOOTING

### Issue: Migration 018 Fails to Execute

**Symptoms:**
- SQL syntax errors
- Foreign key constraint violations
- Unique constraint violations

**Resolution:**
1. Check prerequisites:
   ```sql
   -- Verify foundation schemas exist
   SELECT schema_name
   FROM information_schema.schemata
   WHERE schema_name IN ('fhq_meta', 'fhq_governance', 'vision_core');

   -- Expected: 3 rows
   ```

2. Check existing tables:
   ```sql
   SELECT table_schema, table_name
   FROM information_schema.tables
   WHERE table_schema = 'fhq_governance'
     AND table_name IN ('task_registry', 'governance_actions_log');

   -- Expected: 2 rows (created by foundation migration)
   ```

3. If tables already exist, rollback and retry:
   ```bash
   psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -c "
   DROP SCHEMA IF EXISTS vega CASCADE;
   DROP TABLE IF EXISTS fhq_governance.model_provider_policy CASCADE;
   "

   # Then re-run migration 018
   ```

### Issue: LIVE_MODE=True Found in Production

**Symptoms:**
- G3 validation fails
- VEGA blocks deployment

**Resolution:**
1. **IMMEDIATE ACTION:** Suspend all LLM calls
2. Force LIVE_MODE=False:
   ```sql
   BEGIN;

   UPDATE vega.llm_rate_limits SET live_mode = FALSE WHERE live_mode = TRUE;
   UPDATE vega.llm_cost_limits SET live_mode = FALSE WHERE live_mode = TRUE;
   UPDATE vega.llm_execution_limits SET live_mode = FALSE WHERE live_mode = TRUE;

   -- Verify
   SELECT COUNT(*) FROM vega.llm_rate_limits WHERE live_mode = TRUE;
   -- Expected: 0

   COMMIT;
   ```
3. Escalate to VEGA and LARS
4. Investigate root cause (who/when/why was LIVE_MODE set to TRUE)

### Issue: Hash Chain Broken

**Symptoms:**
- G3 audit verification fails
- `sha256_hash` doesn't match computed hash

**Resolution:**
1. Identify break point:
   ```sql
   WITH hash_validation AS (
       SELECT
           audit_id,
           change_proposal_id,
           sha256_hash,
           previous_audit_id,
           LAG(sha256_hash) OVER (ORDER BY timestamp) AS expected_previous_hash
       FROM fhq_meta.adr_audit_log
   )
   SELECT *
   FROM hash_validation
   WHERE previous_audit_id IS NOT NULL
     AND sha256_hash != encode(sha256((expected_previous_hash || change_proposal_id)::bytea), 'hex');
   ```

2. If break found, escalate to VEGA immediately
3. Do NOT proceed to G4 until resolved

---

## COMPLIANCE CHECKLIST

Before proceeding to G1 (STIG Technical Validation):

- [ ] Migration 018 executed successfully
- [ ] All 13 tables created (see Quick Start verification)
- [ ] G0 submission logged in `fhq_meta.adr_audit_log`
- [ ] LIVE_MODE=False on ALL economic safety tables
- [ ] 7 agent roles registered in `fhq_governance.executive_roles`
- [ ] 5 provider policies configured (LARS, VEGA, FINN, STIG, LINE)
- [ ] Rate limits populated for all providers
- [ ] Cost limits populated for all providers
- [ ] Execution limits populated for all providers
- [ ] Hash chain ID format correct: `HC-CODE-ADR004-G0-20251123`

Before proceeding to G4 (CEO Canonicalization):

- [ ] G1 (STIG) decision: PASS
- [ ] G2 (LARS) decision: PASS
- [ ] G3 (VEGA) decision: VERIFY
- [ ] VEGA QG-F6 attestation completed
- [ ] No outstanding BLOCK or WARN items
- [ ] Monitoring dashboards configured
- [ ] Rollback plan tested
- [ ] CEO approval obtained

---

## RELATED DOCUMENTATION

### ADR References
- **ADR-001:** System Charter 2026 (§3 Executive Roles, §12.3 Agent Contracts)
- **ADR-004:** Change Gates Architecture (G0-G4 Process)
- **ADR-007:** Orchestrator Architecture (§4.5 Provider Routing Policies)
- **ADR-008:** Ed25519 Key Management and Rotation Architecture
- **ADR-012:** Economic Safety Architecture (Rate/Cost/Execution Limits)

### File Locations
```
/home/user/vision-IoS/
├── 02_ADR/
│   ├── ADR-001_2026_PRODUCTION.md
│   ├── ADR-004_2026_PRODUCTION.md
│   ├── ADR-007_2026_PRODUCTION_ORCHESTRATOR.md
│   ├── ADR-008_2026_PRODUCTION_Cryptographic Key Management.md
│   └── ADR-012_2026_PRODUCTION_Economic Safety Architecture.md
├── 04_DATABASE/MIGRATIONS/
│   ├── 001_vision_foundation.sql
│   ├── 017_orchestrator_registration.sql
│   └── 018_line_mandate_governance_economic_safety.sql
├── 05_ORCHESTRATOR/
│   └── orchestrator_v1.py
└── 06_GOVERNANCE/
    ├── README_LINE_MANDATE.md (this file)
    └── G1_VALIDATION_MATERIALS_LINE_MANDATE.md
```

### External API Documentation
- **Anthropic Claude:** https://docs.anthropic.com/
- **OpenAI GPT:** https://platform.openai.com/docs
- **DeepSeek:** https://www.deepseek.com/
- **Serper:** https://serper.dev/
- **Google Scholar:** https://scholar.google.com/
- **Coindesk:** https://www.coindesk.com/
- **Marketaux:** https://www.marketaux.com/
- **FRED (Federal Reserve Economic Data):** https://fred.stlouisfed.org/docs/api/

---

## CONTACT & ESCALATION

| Issue Type | Contact | SLA |
|------------|---------|-----|
| **Technical Issues (G1)** | STIG | 4 hours |
| **Governance Questions (G2)** | LARS | 8 hours |
| **Compliance Violations (G3)** | VEGA | Immediate |
| **Production Approval (G4)** | CEO | 24 hours |
| **Security Incidents** | VEGA + CEO | Immediate |
| **Cost Overruns** | VEGA + LARS | 1 hour |

---

**Version:** 1.0.0
**Last Updated:** 2025-11-23
**Maintained By:** CODE (on behalf of LARS)
**Approval Status:** Pending G1 (STIG Technical Validation)

---

*End of LINE Mandate Implementation Guide*
