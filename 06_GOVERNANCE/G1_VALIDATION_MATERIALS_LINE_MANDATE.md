# G1 VALIDATION MATERIALS – LINE MANDATE REGISTRATION
## Change Proposal: G0-2025-11-23-LINE-MANDATE

**Gate:** G1 – Technical Validation
**Owner:** STIG (System for Technical Implementation & Governance)
**Date:** 2025-11-23
**Initiated By:** CODE (on behalf of LARS)
**Compliance:** ADR-004 (Change Gates), ADR-007 (Provider Routing), ADR-008 (Ed25519 Keys), ADR-012 (Economic Safety)

---

## 1. EXECUTIVE SUMMARY

### Change Type
**MODIFICATION** – API/LLM Provider Expansion (per ADR-004 taxonomy)

### Scope
- Register LINE's operational mandate with expanded provider support
- Implement Economic Safety Layer (ADR-012) for all agents
- Establish governance infrastructure for G0-G4 change gates (ADR-004)
- Configure Ed25519 key management framework (ADR-008)
- Define provider routing policies (ADR-007) for 5 agents

### Impact
- **Agents Affected:** LINE, STIG, FINN, LARS, VEGA
- **New Providers:** DeepSeek, OpenAI, Serper, Scholar, Coindesk, Marketaux, FRED
- **Tables Created:** 13 governance and economic safety tables
- **LIVE_MODE:** FALSE (requires VEGA attestation QG-F6 before enabling)

---

## 2. SCHEMA CHANGES

### 2.1 New Database Schemas
```sql
CREATE SCHEMA vega;  -- Economic Safety Layer (ADR-012)
```

### 2.2 Meta Schema (fhq_meta) – ADR Governance
| Table | Purpose | Key Columns | Compliance |
|-------|---------|-------------|------------|
| `adr_registry` | Central catalog of all ADRs | adr_id, adr_status, current_version, sha256_hash | ADR-004 |
| `adr_audit_log` | Immutable audit trail (G0-G4 gates) | change_proposal_id, event_type, gate_stage, sha256_hash, hash_chain_id | ADR-004 |
| `adr_version_history` | Version lineage per ADR | adr_id, version, sha256_hash, approved_by | ADR-004 |
| `agent_keys` | Ed25519 key lifecycle | agent_id, key_type, key_state, public_key_hex, retention_period_days | ADR-008 |
| `key_archival_log` | Key rotation audit trail | key_id, archival_event, from_state, to_state, hash_chain_id | ADR-008 |

### 2.3 Governance Schema (fhq_governance) – Agent Contracts
| Table | Purpose | Key Columns | Compliance |
|-------|---------|-------------|------------|
| `executive_roles` | Agent definitions | role_id, role_name, authority_level, domain, veto_power | ADR-001 §3 |
| `agent_contracts` | Inter-agent communication rules | agent_id, contract_type, contract_status, mandate_scope, authority_boundaries | ADR-001 §12.3 |
| `model_provider_policy` | LLM provider routing (tier-based) | agent_id, sensitivity_tier, primary_provider, data_sharing_allowed | ADR-007 §4.5 |

### 2.4 VEGA Schema (vega) – Economic Safety Layer
| Table | Purpose | Key Columns | Compliance |
|-------|---------|-------------|------------|
| `llm_rate_limits` | Rate limit governance | agent_id, provider, limit_type, limit_value, live_mode | ADR-012 §3.1 |
| `llm_cost_limits` | Cost ceiling enforcement | agent_id, provider, limit_type, limit_value_usd, live_mode | ADR-012 §3.2 |
| `llm_execution_limits` | Execution time/step limits | agent_id, provider, limit_type, limit_value, abort_on_overrun, live_mode | ADR-012 §3.3 |
| `llm_usage_log` | Detailed LLM call tracking | agent_id, provider, model_name, input_tokens, output_tokens, estimated_cost_usd, timestamp | ADR-012 §4 |
| `llm_violation_events` | Violation tracking and enforcement | agent_id, violation_type, limit_type, enforcement_action, vega_recommendation | ADR-012 §5 |

---

## 3. PROVIDER ROUTING POLICIES (ADR-007)

### 3.1 Tier Model Implementation

#### TIER 1 – High Sensitivity (No Data Sharing)
| Agent | Provider | Model | Max Calls/Day | Cost/Call (USD) |
|-------|----------|-------|---------------|-----------------|
| **LARS** | Anthropic | claude-3-haiku-20240307 | 100 | $0.08 |
| **VEGA** | Anthropic | claude-3-haiku-20240307 | 50 | $0.08 |

**Use Cases:** Strategic analysis, governance decisions, compliance audits, veto decisions

#### TIER 2 – Medium Sensitivity (No Data Sharing)
| Agent | Provider | Model | Max Calls/Day | Cost/Call (USD) |
|-------|----------|-------|---------------|-----------------|
| **FINN** | OpenAI (primary) | gpt-4-turbo | 150 | $0.04 |
|       | Anthropic (fallback) | claude-3-haiku-20240307 | - | $0.08 |

**Use Cases:** Research analysis, signal generation, market intelligence

#### TIER 3 – Low Sensitivity (Data Sharing Allowed)
| Agent | Provider | Model | Max Calls/Day | Cost/Call (USD) |
|-------|----------|-------|---------------|-----------------|
| **STIG** | DeepSeek (primary) | deepseek-chat | 200 | $0.005 |
|       | OpenAI (fallback) | gpt-4-turbo | - | $0.04 |
| **LINE** | DeepSeek (primary) | deepseek-chat | 300 | $0.005 |
|       | OpenAI (fallback) | gpt-4-turbo | - | $0.04 |

**Use Cases:** Technical validation, infrastructure monitoring, SRE operations, incident response

### 3.2 Additional API Providers
| Provider | Type | Rate Limit (calls/min) | Daily Limit | Use Case |
|----------|------|------------------------|-------------|----------|
| **Serper** | Search API | 5 | - | Web search, news, market data |
| **Scholar** | Academic API | 3 | - | Research papers, citations |
| **Coindesk** | Crypto API | 10 | - | Cryptocurrency prices, market data |
| **Marketaux** | Financial News API | 5 | 100/day | Real-time financial news, market sentiment, equities/crypto/forex news |
| **FRED** | Economic Data API | 10 | 120/day | Federal Reserve economic data, macroeconomic indicators, GDP, unemployment, inflation |

---

## 4. ECONOMIC SAFETY LAYER (ADR-012)

### 4.1 Rate Governance (Prevent Runaway Calls)
```sql
-- Per-Agent Limits
LARS/VEGA (Anthropic): 3 calls/min, 5 calls/pipeline
FINN (OpenAI):         5 calls/min, 10 calls/pipeline
STIG/LINE (DeepSeek):  10 calls/min, 15 calls/pipeline

-- Global Daily Limits
Anthropic: 100 calls/day
OpenAI:    150 calls/day
DeepSeek:  500 calls/day
```

### 4.2 Cost Governance (Prevent Budget Overrun)
```sql
-- Per-Call Ceilings
LARS/VEGA (Anthropic): $0.08/call
FINN (OpenAI):         $0.04/call
STIG/LINE (DeepSeek):  $0.005/call

-- Per-Task Ceilings
LARS/FINN:             $0.50/task
STIG/LINE:             $0.10/task

-- Per-Agent Daily Ceilings
LARS/FINN:             $1.00/day
VEGA/STIG/LINE:        $0.50/day

-- Global Daily Ceiling
Total System:          $5.00/day (Anthropic) + $3.00/day (OpenAI) + $2.00/day (DeepSeek) = $10.00/day MAX
```

### 4.3 Execution Governance (Prevent Runaway Reasoning)
```sql
-- LLM Steps per Task
LARS/VEGA:   3 steps max (ABORT on overrun)
FINN/STIG/LINE: 5 steps max (ABORT on overrun)

-- Total Latency
LARS:        3000ms (WARN if exceeded)
FINN/STIG/LINE: 5000ms (WARN if exceeded)

-- Token Generation Limits
LARS/VEGA (Haiku):   4096 tokens max output
FINN (OpenAI):       4096 tokens max output
STIG/LINE (DeepSeek): 8192 tokens max output
```

### 4.4 Violation Actions
| Violation Type | Enforcement Action | VEGA Response | LARS Escalation |
|----------------|-------------------|---------------|-----------------|
| Rate limit exceeded | SWITCH_TO_STUB | WARN | If pattern repeats |
| Cost limit exceeded | SWITCH_TO_STUB | WARN/SUSPEND | If critical breach |
| Execution limit exceeded | ABORT_TASK | WARN | If affects SLA |
| Unauthorized provider | BLOCK | BLOCK | Immediate |
| Data sharing violation | BLOCK | BLOCK | Immediate |

### 4.5 LIVE_MODE Safety Constraint
```sql
-- CRITICAL REQUIREMENT
live_mode = FALSE  -- ALL economic safety tables

-- Cannot be set to TRUE until:
-- 1. VEGA completes QG-F6 attestation
-- 2. LARS approves based on VEGA recommendation
-- 3. CEO signs off on production readiness
```

---

## 5. ED25519 KEY MANAGEMENT (ADR-008)

### 5.1 Key Lifecycle States
```
PENDING (0h retention)
  ↓ activation
ACTIVE (90 days retention)
  ↓ rotation
DEPRECATED (24h grace period)
  ↓ archival
ARCHIVED (7 years retention)
```

### 5.2 Multi-Tier Archival Strategy
| Tier | Storage | Retention | Access Time | Use Case |
|------|---------|-----------|-------------|----------|
| **Tier 1 (Hot)** | Vault | 24 hours | Immediate | Rollback during rotation |
| **Tier 2 (Warm)** | Encrypted filesystem | 90 days | Minutes | Audits, reconciliation |
| **Tier 3 (Cold)** | Air-gapped backup | 7 years | Hours/days | Compliance, legal |

### 5.3 Agent Key Requirements
| Agent | Key Type | State | Storage (Phase 1 POC) | Rotation Frequency |
|-------|----------|-------|-----------------------|-------------------|
| LARS | ED25519_SIGNING | ACTIVE | .env (Fernet encrypted) | 90 days |
| STIG | ED25519_SIGNING | ACTIVE | .env (Fernet encrypted) | 90 days |
| LINE | ED25519_SIGNING | ACTIVE | .env (Fernet encrypted) | 90 days |
| FINN | ED25519_SIGNING | ACTIVE | .env (Fernet encrypted) | 90 days |
| VEGA | ED25519_SIGNING | ACTIVE | .env (Fernet encrypted) | 90 days |

**Note:** Phase 1 uses `.env` + Fernet. Phase 2 migrates to HashiCorp Vault. Phase 3 adds HSM via PKCS#11.

---

## 6. G0-G4 CHANGE GATES (ADR-004)

### 6.1 Gate Flow for LINE Mandate
```
G0 (SUBMISSION)
  ├─ Initiated by: CODE
  ├─ Change Type: MODIFICATION (API/LLM Provider Expansion)
  ├─ Evidence: Migration 018 SQL file
  ├─ Hash Chain: HC-CODE-ADR004-G0-20251123
  └─ Decision: SUBMITTED → G1

G1 (TECHNICAL VALIDATION) ← YOU ARE HERE
  ├─ Owner: STIG
  ├─ Validates: Schema correctness, constraints, indexes, data integrity
  ├─ Checks: Migration can execute without errors, rollback plan exists
  └─ Decision: PASS/FAIL → G2

G2 (GOVERNANCE VALIDATION)
  ├─ Owner: LARS (+ Governance Committee)
  ├─ Validates: Authority boundaries, mandate scope, compliance alignment
  ├─ Checks: Provider policies align with ADR-007, economic limits reasonable
  └─ Decision: PASS/FAIL/MODIFY → G3

G3 (AUDIT VERIFICATION)
  ├─ Owner: VEGA (or STIG if VEGA unavailable)
  ├─ Validates: Compliance with all ADRs, economic safety enforced
  ├─ Checks: LIVE_MODE=False, hash chains valid, signatures present
  └─ Decision: VERIFY/BLOCK/WARN → G4

G4 (CANONICALIZATION)
  ├─ Owner: CEO
  ├─ Validates: Final approval for production deployment
  ├─ Checks: All gates passed, no outstanding BLOCK/WARN items
  └─ Decision: APPROVED → Execute migration
```

### 6.2 G1 Validation Checklist (STIG)
- [ ] **Schema Correctness**
  - [ ] All 13 tables create successfully
  - [ ] No SQL syntax errors
  - [ ] Foreign key constraints valid
  - [ ] Check constraints enforced

- [ ] **Data Integrity**
  - [ ] Unique constraints prevent duplicates
  - [ ] Indexes improve query performance
  - [ ] Default values sensible
  - [ ] JSONB columns use valid JSON

- [ ] **Migration Safety**
  - [ ] Transaction wrapped (BEGIN/COMMIT)
  - [ ] Verification queries execute
  - [ ] Rollback plan documented
  - [ ] No destructive operations (DROP/TRUNCATE)

- [ ] **Compliance**
  - [ ] All ADR references valid (ADR-004, ADR-007, ADR-008, ADR-012)
  - [ ] Table comments reference correct ADR sections
  - [ ] LIVE_MODE=False enforced on all economic safety tables

- [ ] **Performance**
  - [ ] Indexes on high-query columns (agent_id, timestamp, provider)
  - [ ] No N+1 query patterns in sample queries
  - [ ] JSONB columns indexed where necessary (GIN indexes)

---

## 7. TECHNICAL VALIDATION QUERIES

### 7.1 Verify All Tables Created
```sql
SELECT
    table_schema,
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns
     WHERE table_schema = t.table_schema
       AND table_name = t.table_name) AS column_count
FROM information_schema.tables t
WHERE table_schema IN ('fhq_meta', 'fhq_governance', 'vega')
  AND table_name IN (
    'adr_registry', 'adr_audit_log', 'adr_version_history',
    'agent_keys', 'key_archival_log',
    'executive_roles', 'agent_contracts', 'model_provider_policy',
    'llm_rate_limits', 'llm_cost_limits', 'llm_execution_limits',
    'llm_usage_log', 'llm_violation_events'
  )
ORDER BY table_schema, table_name;
```

### 7.2 Verify G0 Submission Logged
```sql
SELECT
    audit_id,
    change_proposal_id,
    event_type,
    gate_stage,
    initiated_by,
    decision,
    resolution_notes,
    hash_chain_id,
    timestamp
FROM fhq_meta.adr_audit_log
WHERE change_proposal_id = 'G0-2025-11-23-LINE-MANDATE'
  AND event_type = 'SUBMISSION'
  AND gate_stage = 'G0';
```

### 7.3 Verify LIVE_MODE=False
```sql
SELECT
    'llm_rate_limits' AS table_name,
    COUNT(*) AS total_rows,
    COUNT(*) FILTER (WHERE live_mode = TRUE) AS live_mode_true,
    COUNT(*) FILTER (WHERE live_mode = FALSE) AS live_mode_false
FROM vega.llm_rate_limits
UNION ALL
SELECT
    'llm_cost_limits',
    COUNT(*),
    COUNT(*) FILTER (WHERE live_mode = TRUE),
    COUNT(*) FILTER (WHERE live_mode = FALSE)
FROM vega.llm_cost_limits
UNION ALL
SELECT
    'llm_execution_limits',
    COUNT(*),
    COUNT(*) FILTER (WHERE live_mode = TRUE),
    COUNT(*) FILTER (WHERE live_mode = FALSE)
FROM vega.llm_execution_limits;

-- Expected: live_mode_true = 0 for ALL tables
```

### 7.4 Verify Agent Roles Registered
```sql
SELECT
    role_id,
    role_name,
    authority_level,
    domain,
    veto_power,
    active
FROM fhq_governance.executive_roles
ORDER BY
    CASE
        WHEN veto_power THEN 0
        ELSE 1
    END,
    authority_level DESC NULLS LAST;

-- Expected: 7 roles (LARS, STIG, LINE, FINN, VEGA, CODE, CEO)
```

### 7.5 Verify Provider Policies
```sql
SELECT
    agent_id,
    sensitivity_tier,
    primary_provider,
    fallback_providers,
    model_name,
    data_sharing_allowed,
    cost_envelope_per_call_usd,
    max_calls_per_day
FROM fhq_governance.model_provider_policy
ORDER BY
    CASE sensitivity_tier
        WHEN 'TIER1_HIGH' THEN 1
        WHEN 'TIER2_MEDIUM' THEN 2
        WHEN 'TIER3_LOW' THEN 3
    END,
    agent_id;

-- Expected: 5 policies (LARS, VEGA, FINN, STIG, LINE)
```

### 7.6 Verify Rate Limits
```sql
SELECT
    agent_id,
    provider,
    limit_type,
    limit_value,
    enforcement_mode,
    violation_action,
    live_mode
FROM vega.llm_rate_limits
WHERE agent_id IS NOT NULL
ORDER BY agent_id, provider, limit_type;
```

### 7.7 Verify Cost Limits
```sql
SELECT
    agent_id,
    provider,
    limit_type,
    limit_value_usd,
    enforcement_mode,
    violation_action,
    live_mode
FROM vega.llm_cost_limits
WHERE agent_id IS NOT NULL
ORDER BY agent_id, provider, limit_type;
```

### 7.8 Verify Execution Limits
```sql
SELECT
    agent_id,
    provider,
    limit_type,
    limit_value,
    enforcement_mode,
    abort_on_overrun,
    live_mode
FROM vega.llm_execution_limits
WHERE agent_id IS NOT NULL
ORDER BY agent_id, provider, limit_type;
```

### 7.9 Verify Foreign Key Constraints
```sql
SELECT
    tc.constraint_name,
    tc.table_schema,
    tc.table_name,
    kcu.column_name,
    ccu.table_schema AS foreign_table_schema,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema IN ('fhq_meta', 'fhq_governance', 'vega')
ORDER BY tc.table_schema, tc.table_name, tc.constraint_name;
```

### 7.10 Verify Indexes
```sql
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname IN ('fhq_meta', 'fhq_governance', 'vega')
ORDER BY schemaname, tablename, indexname;
```

---

## 8. ROLLBACK PLAN

### 8.1 Rollback SQL
```sql
BEGIN;

-- Drop VEGA schema (cascades to all tables)
DROP SCHEMA IF EXISTS vega CASCADE;

-- Drop governance tables
DROP TABLE IF EXISTS fhq_governance.model_provider_policy CASCADE;
DROP TABLE IF EXISTS fhq_governance.agent_contracts CASCADE;
DROP TABLE IF EXISTS fhq_governance.executive_roles CASCADE;

-- Drop meta tables
DROP TABLE IF EXISTS fhq_meta.key_archival_log CASCADE;
DROP TABLE IF EXISTS fhq_meta.agent_keys CASCADE;
DROP TABLE IF EXISTS fhq_meta.adr_version_history CASCADE;
DROP TABLE IF EXISTS fhq_meta.adr_audit_log CASCADE;
DROP TABLE IF EXISTS fhq_meta.adr_registry CASCADE;

COMMIT;
```

### 8.2 Rollback Verification
```sql
-- Verify all tables dropped
SELECT
    table_schema,
    table_name
FROM information_schema.tables
WHERE table_schema IN ('fhq_meta', 'fhq_governance', 'vega')
  AND table_name IN (
    'adr_registry', 'adr_audit_log', 'adr_version_history',
    'agent_keys', 'key_archival_log',
    'executive_roles', 'agent_contracts', 'model_provider_policy',
    'llm_rate_limits', 'llm_cost_limits', 'llm_execution_limits',
    'llm_usage_log', 'llm_violation_events'
  );

-- Expected: 0 rows
```

---

## 9. ESTIMATED IMPACT ANALYSIS

### 9.1 Database Size Impact
| Component | Estimated Size | Rationale |
|-----------|---------------|-----------|
| Schema definitions | ~50 KB | 13 tables with indexes |
| Initial data (policies, roles, limits) | ~100 KB | ~100 rows initial configuration |
| Audit log (1 year) | ~10 MB | Assuming 10,000 audit events/year |
| LLM usage log (1 year) | ~50 MB | Assuming 100,000 LLM calls/year |
| Key archival log (7 years) | ~5 MB | Key rotations every 90 days |
| **Total (Year 1)** | **~65 MB** | Low impact |

### 9.2 Query Performance Impact
- **Indexes:** All high-query columns indexed (agent_id, timestamp, provider, event_type)
- **Expected Query Time:** <100ms for typical queries (single-agent lookups, date ranges)
- **Write Performance:** Minimal impact (inserts only, no updates on audit tables)
- **Concurrent Access:** No lock contention expected (append-only audit logs)

### 9.3 Application Integration Impact
- **Current Orchestrator:** No changes required (uses existing `fhq_governance.task_registry`)
- **Future LLM Integrations:** Must implement economic safety checks before production
- **Agent Key Management:** Phase 1 POC (.env) already implemented per status report
- **Monitoring:** VEGA will need dashboard for `llm_usage_log` and `llm_violation_events`

---

## 10. STIG DECISION MATRIX

### 10.1 PASS Criteria
✅ All 13 tables created without errors
✅ All verification queries return expected results
✅ LIVE_MODE=False enforced on all economic safety tables
✅ Foreign key constraints valid
✅ Indexes improve query performance
✅ Transaction safety (BEGIN/COMMIT)
✅ Rollback plan tested and verified
✅ No SQL injection vulnerabilities
✅ ADR compliance verified (ADR-004, ADR-007, ADR-008, ADR-012)

**Decision:** PASS → G2 (LARS Governance Validation)

### 10.2 FAIL Criteria
❌ Migration fails to execute
❌ Foreign key constraint violations
❌ LIVE_MODE=True found on any row
❌ Verification queries fail
❌ SQL syntax errors
❌ Missing indexes on critical columns
❌ No rollback plan

**Decision:** FAIL → Return to G0 for fixes

### 10.3 MODIFY Criteria
⚠️ Schema correct but optimization needed (e.g., additional indexes)
⚠️ Minor compliance issues (e.g., missing table comments)
⚠️ Performance concerns (e.g., missing composite indexes)
⚠️ Documentation incomplete

**Decision:** MODIFY → Fix issues → Re-submit to G1

---

## 11. NEXT STEPS (POST-G1)

### 11.1 If PASS → G2 (LARS Governance Validation)
1. **LARS reviews:**
   - Authority boundaries in `agent_contracts`
   - Mandate scope for LINE
   - Provider policies align with strategic objectives
   - Economic limits are reasonable and enforceable

2. **LARS validates:**
   - LINE's authority level (8) appropriate for SRE operations
   - TIER3 classification (DeepSeek/OpenAI) acceptable for infrastructure monitoring
   - Cost ceilings align with budget constraints
   - Escalation rules to VEGA/LARS properly defined

3. **LARS decision:** PASS/FAIL/MODIFY → G3

### 11.2 If PASS → G3 (VEGA Audit Verification)
1. **VEGA audits:**
   - All ADR compliance requirements met
   - Hash chains valid and unbroken
   - LIVE_MODE=False enforced
   - Economic safety violations will trigger VEGA alerts
   - Ed25519 signatures present on all governance events

2. **VEGA validates:**
   - No compliance gaps
   - Economic safety layer fully implemented
   - Violation actions escalate to VEGA correctly
   - QG-F6 attestation checklist prepared

3. **VEGA decision:** VERIFY/BLOCK/WARN → G4

### 11.3 If PASS → G4 (CEO Canonicalization)
1. **CEO reviews:**
   - All gates passed (G1, G2, G3)
   - No outstanding BLOCK or WARN items
   - Production deployment plan ready
   - Monitoring and alerting configured

2. **CEO signs off:**
   - Execute migration 018 in production
   - Register LINE mandate in `agent_contracts`
   - Enable VEGA monitoring of economic safety layer
   - Schedule VEGA QG-F6 attestation

3. **CEO decision:** APPROVED → Production Deployment

---

## 12. APPENDICES

### Appendix A: ADR References
- **ADR-001:** System Charter 2026 (§3 Executive Roles, §12.3 Agent Contracts)
- **ADR-004:** Change Gates Architecture (G0-G4 process)
- **ADR-007:** Orchestrator Architecture (§4.5 Provider Routing Policies)
- **ADR-008:** Ed25519 Key Management and Rotation
- **ADR-012:** Economic Safety Architecture (Rate/Cost/Execution Limits)

### Appendix B: File Locations
- **Migration File:** `/home/user/vision-IoS/04_DATABASE/MIGRATIONS/018_line_mandate_governance_economic_safety.sql`
- **This Document:** `/home/user/vision-IoS/06_GOVERNANCE/G1_VALIDATION_MATERIALS_LINE_MANDATE.md`
- **ADR Files:** `/home/user/vision-IoS/02_ADR/ADR-{001,004,007,008,012}_*.md`
- **Orchestrator:** `/home/user/vision-IoS/05_ORCHESTRATOR/orchestrator_v1.py`

### Appendix C: Contact Information
| Role | Agent | Responsibility | Escalation |
|------|-------|---------------|------------|
| **G1 Owner** | STIG | Technical validation of schema changes | LARS (if blocked) |
| **G2 Owner** | LARS | Governance validation of mandate scope | CEO (if conflict) |
| **G3 Owner** | VEGA | Audit verification of compliance | CEO (if veto needed) |
| **G4 Owner** | CEO | Final approval and canonicalization | N/A (human authority) |

---

## 13. STIG APPROVAL SECTION

**STIG Decision:** [ ] PASS  [ ] FAIL  [ ] MODIFY

**Technical Validation Notes:**
```
[STIG to complete after executing validation queries]

Schema Creation: ✅/❌
Verification Queries: ✅/❌
LIVE_MODE Check: ✅/❌
Foreign Keys: ✅/❌
Indexes: ✅/❌
Rollback Test: ✅/❌
ADR Compliance: ✅/❌

Issues Found:
[List any issues or recommendations]

Recommendations:
[List any optimizations or improvements]

```

**STIG Signature:** _______________________________
**Date:** _______________________________
**Hash Chain ID:** HC-STIG-ADR004-G1-20251123
**Next Gate:** G2 (LARS Governance Validation)

---

**End of G1 Validation Materials**
