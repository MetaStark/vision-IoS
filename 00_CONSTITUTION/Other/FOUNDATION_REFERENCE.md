# FOUNDATION REFERENCE
## Link to fhq-market-system (Grunnmuren)

**Foundation Repository:** https://github.com/MetaStark/fhq-market-system
**Foundation Branch:** claude/setup-db-mirroring-01LUuKugCnjjoWAPxAYwxt8s
**Baseline Commit:** c5fb701 - CANONICAL BASE SYNC – ADR001–ADR013 MIRROR ESTABLISHED

---

## Foundation Contents

The foundation contains:
- `/SCHEMAS/` - 4 schema files (fhq_data, fhq_meta, fhq_monitoring, fhq_research)
- `/MIGRATIONS/000_BASELINE.sql` - Initial database state
- `/LINE/` - Ingestion contracts
- `/STIG/` - DDL rules
- ADR-001 through ADR-013 (the constitution)

---

## How Vision-IoS Uses the Foundation

1. **Database:** Same database, new schemas (vision_*)
2. **Agents:** Uses existing identities (LARS/STIG/LINE/FINN)
3. **Governance:** Flows through fhq_governance
4. **Audit:** Logs to fhq_meta.adr_audit_log
5. **Keys:** Uses fhq_meta.agent_keys (ADR-008)

See `FOUNDATION_COMPATIBILITY.md` for full compliance matrix.
