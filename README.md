# VISION-IOS
## Eliminate Noise. Generate Signal. Verify Everything.

**Built on:** ADR-001–013 Foundation (fhq-market-system)
**Mission:** Convert unstructured noise into auditable alpha signals
**Governance:** VEGA, STIG, LARS, LINE, FINN
**Principle:** Trust is cryptographic proof

---

## Architecture

```
Vision-IoS (Application Layer)
    ↓ builds on
fhq-market-system (Foundation Layer - ADR-001–013)
```

- **Same database**, new schemas (vision_*)
- **Foundation schemas are READ-ONLY**
- **Runs under existing agent identities**
- **100% auditable, cryptographically signed**

---

## Directory Structure

```
00_CONSTITUTION/     # Links to foundation, ADR compliance
01_ARCHITECTURE/     # System design (VEGA, STIG, LARS, LINE, FINN)
02_ADR/              # Decision records (ADR-014+)
03_FUNCTIONS/        # 30-50 functions (starting with 3)
04_DATABASE/         # Schemas, migrations, mirroring tools
05_GOVERNANCE/       # Governance framework integration
06_AUDIT/            # Trust layer (signatures, hashes, lineage)
```

---

## First 3 Functions

1. **Signal Inference Baseline** - Understand state (non-actionable)
2. **Noise Floor Estimator** - Build noise vs signal reference
3. **Meta-State Sync** - Sync Vision-IoS to fhq_meta

---

## Getting Started

```bash
# Initialize database schemas
psql -f 04_DATABASE/MIGRATIONS/001_vision_foundation.sql

# Verify foundation compatibility
python verify_foundation_compliance.py

# Run first function
python 03_FUNCTIONS/alpha_signal/baseline_generator.py
```

---

## Governance

All Vision-IoS operations:
- ✅ Run under existing agent identities (LARS/STIG/LINE/FINN)
- ✅ Signed via Ed25519 (ADR-008)
- ✅ Logged to fhq_meta.adr_audit_log (ADR-002)
- ✅ Subject to VEGA governance (ADR-006)
- ✅ Follow Change Gates G0-G4 (ADR-004)

---

## Compliance

See `00_CONSTITUTION/FOUNDATION_COMPATIBILITY.md` for full compliance matrix.

**Key Rules:**
- ❌ Cannot write to fhq_* schemas
- ❌ Cannot create new agents
- ❌ Cannot bypass audit logging
- ✅ Can create vision_* schemas
- ✅ Can read from fhq_* schemas
- ✅ Can generate signals (non-executable)

---

**Motto:** Move fast and verify things.
**Status:** Building on proven foundation.
