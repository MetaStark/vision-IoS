#!/usr/bin/env python3
"""
VISION-IOS INITIALIZATION SCRIPT
Clean start on ADR-001–013 foundation

This script creates the complete directory structure and initial files
for Vision-IoS, ensuring 100% compatibility with the foundation.

Principles:
- Same database, new schemas (vision_*)
- Foundation schemas (fhq_*) are READ-ONLY
- Application layer, not kernel layer
- Runs under existing agent identities (LARS/STIG/LINE/FINN)
- First 3 functions only: baseline, noise profile, meta-sync

Usage:
    python init_vision_ios.py [path-to-vision-ios-repo]

Example:
    python init_vision_ios.py C:/vision-IoS
"""

import sys
from pathlib import Path
from datetime import datetime

def create_directory_structure(base_path: Path):
    """Create the complete Vision-IoS directory structure"""

    directories = [
        "00_CONSTITUTION",
        "01_ARCHITECTURE",
        "02_ADR",
        "03_FUNCTIONS/alpha_signal",
        "03_FUNCTIONS/noise_filter",
        "03_FUNCTIONS/meta_analysis",
        "04_DATABASE/SCHEMAS",
        "04_DATABASE/MIGRATIONS",
        "04_DATABASE/MIRROR",
        "05_GOVERNANCE/VEGA",
        "05_GOVERNANCE/STIG",
        "05_GOVERNANCE/LARS",
        "05_GOVERNANCE/LINE",
        "05_GOVERNANCE/FINN",
        "06_AUDIT/SIGNATURES",
        "06_AUDIT/HASHES",
        "06_AUDIT/LINEAGE",
    ]

    print("📁 Creating directory structure...")
    for dir_path in directories:
        full_path = base_path / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print(f"   ✅ {dir_path}")

    print()

def create_foundation_compatibility(base_path: Path):
    """Create FOUNDATION_COMPATIBILITY.md"""

    content = f"""# FOUNDATION COMPATIBILITY MATRIX
## Vision-IoS <-> ADR-001–013 Compliance

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
**Foundation Repo:** github.com/MetaStark/fhq-market-system
**Foundation Branch:** claude/setup-db-mirroring-01LUuKugCnjjoWAPxAYwxt8s
**Foundation Commit:** c5fb701 - CANONICAL BASE SYNC

---

## 🏛️ CONSTITUTION REFERENCE

Vision-IoS is built **on top of** the ADR-001–013 foundation.
The foundation is **immutable and sovereign**.
Vision-IoS operates at the **application layer**, not the kernel layer.

```
┌─────────────────────────────────────┐
│ VISION-IOS (Application Layer)     │ ← We are here
│ • Builds on foundation              │
│ • Cannot override ADR-001–013       │
│ • Extends, never replaces           │
└─────────────────────────────────────┘
                ↓ builds on
┌─────────────────────────────────────┐
│ FHQ-MARKET-SYSTEM (Foundation)      │ ← Immutable
│ • ADR-001–013 (constitution)        │
│ • fhq_* schemas (canonical)         │
│ • VEGA/STIG/LARS/LINE/FINN agents   │
└─────────────────────────────────────┘
```

---

## ✅ ADR COMPLIANCE MATRIX

### Foundation ADRs (MUST COMPLY)

| ADR | Title | Vision-IoS Dependency | Compliance Level |
|-----|-------|----------------------|------------------|
| ADR-001 | System Charter | Uses same database, respects domain ownership | **CRITICAL** |
| ADR-002 | Audit Charter | All changes logged to fhq_meta.adr_audit_log | **CRITICAL** |
| ADR-003 | Institutional Standards | Follows schema naming (vision_*), not fhq_* | **REQUIRED** |
| ADR-004 | Change Gates | All DB changes go through G1-G4 gates | **REQUIRED** |
| ADR-005 | Mission & Vision | Aligned: "eliminate noise, generate signal" | INFORMATIONAL |
| ADR-006 | VEGA Charter | Autonomous functions report to VEGA | **CRITICAL** |
| ADR-007 | Orchestrator Architecture | Functions run under LARS/STIG/LINE/FINN | **CRITICAL** |
| ADR-008 | Crypto Keys | All operations signed via Ed25519 | **CRITICAL** |
| ADR-009 | Suspension Workflow | Vision functions can be suspended via VEGA | **REQUIRED** |
| ADR-010 | Reconciliation | Vision state syncs to fhq_meta reconciliation | **REQUIRED** |
| ADR-011 | Fortress | Vision operations produce hash chains | **REQUIRED** |
| ADR-012 | Economic Safety | NO autonomous execution until QG-F6 passes | **BLOCKER** |
| ADR-013 | Kernel Specification | Vision-IoS is application layer, not kernel | **CRITICAL** |

---

## 🚫 PROHIBITED ACTIONS

Vision-IoS **CANNOT** do the following (violations trigger VEGA Class A):

1. ❌ Create new `fhq_*` schemas (only `vision_*` allowed)
2. ❌ Write to foundation schemas (fhq_data, fhq_meta, fhq_monitoring, fhq_research)
3. ❌ Create new agent identities (must use existing LARS/STIG/LINE/FINN)
4. ❌ Generate new Ed25519 keys (must use ADR-008 key management)
5. ❌ Execute autonomous trades before ADR-012 QG-F6 passes
6. ❌ Bypass Change Gates (ADR-004 G0-G4)
7. ❌ Override ADR-001–013 decisions
8. ❌ Use separate database (must use same DB)
9. ❌ Skip audit logging (ADR-002)
10. ❌ Operate outside VEGA governance (ADR-006)

---

## ✅ PERMITTED ACTIONS

Vision-IoS **CAN** do the following:

1. ✅ Create new `vision_*` schemas
2. ✅ Read from foundation schemas (fhq_*)
3. ✅ Write to `vision_*` schemas
4. ✅ Run functions under existing agent identities
5. ✅ Generate signals (non-executable)
6. ✅ Perform meta-analysis
7. ✅ Filter noise
8. ✅ Create hash chains for verification
9. ✅ Log all operations to fhq_meta.adr_audit_log
10. ✅ Request VEGA approval for new capabilities

---

## 📐 DATABASE STRATEGY

### Same Database, New Schemas

```sql
-- FOUNDATION SCHEMAS (READ-ONLY for Vision-IoS)
fhq_data         -- Price data, market data
fhq_meta         -- ADR registry, audit logs
fhq_monitoring   -- System events, health
fhq_research     -- Research results

-- VISION SCHEMAS (READ-WRITE for Vision-IoS)
vision_core         -- Core execution engine
vision_signals      -- Alpha signal storage
vision_autonomy     -- Self-governance state
vision_verification -- Cryptographic proofs
```

### Access Control

```sql
-- Vision-IoS has SELECT on foundation schemas
GRANT SELECT ON SCHEMA fhq_data TO vision_app;
GRANT SELECT ON SCHEMA fhq_meta TO vision_app;
GRANT SELECT ON SCHEMA fhq_monitoring TO vision_app;
GRANT SELECT ON SCHEMA fhq_research TO vision_app;

-- Vision-IoS has ALL on vision schemas
GRANT ALL ON SCHEMA vision_core TO vision_app;
GRANT ALL ON SCHEMA vision_signals TO vision_app;
GRANT ALL ON SCHEMA vision_autonomy TO vision_app;
GRANT ALL ON SCHEMA vision_verification TO vision_app;
```

---

## 🎯 FIRST 3 FUNCTIONS (ADR-Compliant)

### 1. Signal Inference Baseline
- **Schema:** `vision_signals.generate_baseline`
- **Purpose:** System understands state (non-actionable)
- **ADR Compliance:** ADR-010 (reconciliation), FINN discovery
- **Risk Level:** LOW (read-only analysis)

### 2. Noise Floor Estimator
- **Schema:** `vision_core.noise_profile`
- **Purpose:** Build reference level for noise vs signal
- **ADR Compliance:** Required to avoid false VEGA escalations
- **Risk Level:** LOW (profiling only)

### 3. Meta-State Sync
- **Schema:** `vision_autonomy.meta_sync`
- **Purpose:** Sync Vision-IoS state to fhq_meta
- **ADR Compliance:** ADR-002 (audit), ADR-010 (reconciliation)
- **Risk Level:** LOW (state sync only)

---

## 🔐 GOVERNANCE INTEGRATION

Vision-IoS functions run **under existing agent identities**:

- **LARS** - Orchestration commands
- **STIG** - Execution validation
- **LINE** - Data ingestion
- **FINN** - Discovery and analysis

Vision-IoS does **NOT** create new agents.
All governance flows through `fhq_governance` (ADR-007).
All actions signed via `fhq_meta.agent_keys` (ADR-008).

---

## 📊 COMPLIANCE VERIFICATION

To verify Vision-IoS remains compliant:

```bash
# Check schemas (should only have vision_*)
psql -c "\\dn" | grep vision

# Verify no writes to foundation schemas
psql -c "SELECT * FROM fhq_meta.adr_audit_log WHERE schema_name LIKE 'fhq_%' AND created_by = 'vision_app';"

# Confirm all operations are signed
psql -c "SELECT * FROM vision_verification.operation_signatures ORDER BY created_at DESC LIMIT 10;"
```

---

## 🚨 ESCALATION POLICY

If Vision-IoS violates ADR-001–013:

1. **Class A Violation** (writes to fhq_*, new agents, skips audit)
   - Immediate suspension via ADR-009
   - VEGA emergency review
   - System rollback required

2. **Class B Violation** (misses audit log, wrong schema naming)
   - VEGA warning
   - 24h correction window
   - Escalates to Class A if not fixed

3. **Class C Violation** (documentation gaps, minor deviations)
   - Logged to fhq_meta.adr_audit_log
   - Correction in next sprint

---

## 📚 REFERENCES

- **Foundation Repo:** https://github.com/MetaStark/fhq-market-system
- **Baseline Commit:** c5fb701
- **ADR Registry:** See fhq_meta.adr_registry
- **Governance:** See fhq_governance schema

---

**Status:** ACTIVE
**Last Updated:** {datetime.now().strftime('%Y-%m-%d')}
**Maintained By:** LARS (orchestrator)
"""

    file_path = base_path / "00_CONSTITUTION" / "FOUNDATION_COMPATIBILITY.md"
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ Created: FOUNDATION_COMPATIBILITY.md")
    print()

def create_foundation_reference(base_path: Path):
    """Create FOUNDATION_REFERENCE.md"""

    content = """# FOUNDATION REFERENCE
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
"""

    file_path = base_path / "00_CONSTITUTION" / "FOUNDATION_REFERENCE.md"
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ Created: FOUNDATION_REFERENCE.md")
    print()

def create_readme(base_path: Path):
    """Create main README.md"""

    content = """# VISION-IOS
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
"""

    file_path = base_path / "README.md"
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ Created: README.md")
    print()

def main():
    print("=" * 70)
    print("VISION-IOS INITIALIZATION")
    print("Clean start on ADR-001–013 foundation")
    print("=" * 70)
    print()

    # Get target path
    if len(sys.argv) > 1:
        target_path = Path(sys.argv[1])
    else:
        target_path = Path.cwd()

    print(f"📍 Target directory: {target_path}")
    print()

    # Confirm (skip if --yes flag provided)
    if "--yes" not in sys.argv:
        try:
            response = input("Initialize Vision-IoS in this directory? [y/N]: ")
            if response.lower() != 'y':
                print("Cancelled.")
                return 1
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return 1
    else:
        print("⚡ Auto-confirming with --yes flag")

    print()

    # Create structure
    create_directory_structure(target_path)
    create_foundation_compatibility(target_path)
    create_foundation_reference(target_path)
    create_readme(target_path)

    print("=" * 70)
    print("✅ VISION-IOS INITIALIZED")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. Review 00_CONSTITUTION/FOUNDATION_COMPATIBILITY.md")
    print("2. Create database schemas in 04_DATABASE/SCHEMAS/")
    print("3. Implement first 3 functions in 03_FUNCTIONS/")
    print("4. Set up governance integration in 05_GOVERNANCE/")
    print()
    print("Move fast and verify things. 🚀")

    return 0

if __name__ == "__main__":
    exit(main())
