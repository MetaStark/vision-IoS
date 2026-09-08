# Learning Throughput Verification

**Query Timestamp:** 2026-01-24 22:45 CET
**Executor:** STIG (EC-003)

---

## GENERATOR: FINN-E (Error Repair)

| Metric | Value |
|--------|-------|
| Hypotheses (24h) | 2 |
| Hypotheses (72h) | 3 |
| Hypotheses (total) | 3 |
| Last hypothesis | 2026-01-23 22:57:27 CET |
| Hours since last | **23.8** |
| Experiments (24h) | 2 |
| Experiments (72h) | 2 |
| Last experiment | 2026-01-23 22:58:52 CET |

**Generation cadence:** UNKNOWN - No daemon schedule found

---

## GENERATOR: FINN-T (World-Model)

| Metric | Value |
|--------|-------|
| Hypotheses (24h) | 0 |
| Hypotheses (72h) | 0 |
| Hypotheses (total) | 0 |
| Last hypothesis | **NEVER** |
| Hours since last | N/A |
| Experiments (24h) | 0 |
| Experiments (72h) | 0 |

**Generation cadence:** NOT RUNNING

---

## GENERATOR: GN-S (Shadow)

| Metric | Value |
|--------|-------|
| Hypotheses (24h) | 0 |
| Hypotheses (72h) | 0 |
| Hypotheses (total) | 0 |
| Last hypothesis | **NEVER** |
| Hours since last | N/A |
| Experiments (24h) | 0 |
| Experiments (72h) | 0 |

**Generation cadence:** NOT RUNNING

---

## RAW HYPOTHESIS DATA

```
generator_id | hypothesis_code | created_at              | status    | origin_type
-------------|-----------------|-------------------------|-----------|-------------
FINN-E       | HYP-2026-0003   | 2026-01-23 22:57:27 CET | WEAKENED  | ERROR_DRIVEN
FINN-E       | HYP-2026-0002   | 2026-01-23 22:55:13 CET | FALSIFIED | ERROR_DRIVEN
FINN-E       | HYP-2026-0001   | 2026-01-23 22:39:32 CET | WEAKENED  | ERROR_DRIVEN
```

---

## PERSISTENCE (Authoritative Tables)

| Table | Purpose | Rows |
|-------|---------|------|
| `fhq_learning.hypothesis_canon` | Hypothesis storage with generator_id | 3 |
| `fhq_learning.experiment_registry` | Experiment storage | 2 |
| `fhq_learning.generator_registry` | Generator definitions | 3 |
| `fhq_learning.v_research_trinity_status` | **CEO authoritative view** | 3 |
| `fhq_learning.v_learning_throughput_status` | Throughput monitoring | 1 |

---

## CONCLUSION

| Generator | Status | Last Activity |
|-----------|--------|---------------|
| FINN-E | STALE | 23.8h ago |
| FINN-T | **NOT RUNNING** | Never |
| GN-S | **NOT RUNNING** | Never |

**No daemon or scheduled process is actively generating hypotheses.**

Infrastructure is deployed. Generators are registered. But no generation process is executing.
