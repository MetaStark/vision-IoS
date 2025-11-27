# Vision-IoS Dashboard 2026

**The only authorized human interface to FjordHQ** (ADR-005)

## Overview

This Next.js dashboard implements ADR-005: Human Interaction & Application Layer Charter. It provides the CEO with a governed interface to view, question, and influence FjordHQ - under VEGA-enforced governance and Orchestrator control.

## Features

### Data & Insight Panels (Category A - Observational)
- **Overview** - System health, key metrics, and status at a glance
- **Market Data** - Price charts, indicators, and data freshness (IoS-001)
- **FINN Intelligence** - CDS metrics, daily briefings, events (IoS-003)
- **Signals** - Trading signals and alerts from FINN/LARS agents
- **System Health** - Gates, governance, ADRs, economic safety

### Trust Banner
Real-time system health display showing:
- Gate status (G0-G4)
- Data freshness
- CDS risk level
- Economic safety status

### Data Lineage
Every component displays its data sources via lineage indicators, ensuring full transparency.

## Technology Stack

- **Framework**: Next.js 14 (App Router)
- **Database**: SQLite via Drizzle ORM
- **Styling**: Tailwind CSS
- **Charts**: Custom SVG + Recharts (planned)
- **State**: Server Components + SWR for client updates

## Quick Start

```bash
# Install dependencies
npm install

# Initialize and seed the database
npm run db:seed

# Start development server
npm run dev

# Open http://localhost:3000
```

## Database

The dashboard uses a local SQLite database (`db/vision-ios.db`) that mirrors the FHQ schemas:

- `adr_registry` - ADR-001 through ADR-013
- `gate_status` - G0-G4 change gates
- `data_freshness` - Asset freshness tracking
- `cds_metrics` - Cognitive Dissonance Scores
- `economic_safety` - Budget and cost controls
- `governance_state` - Current system phase
- `ios_module_registry` - Application layer modules

### Seeding

```bash
npm run db:seed
```

This populates the database with:
- All ADRs (including ADR-005)
- Agent keys (LARS, STIG, LINE, FINN, VEGA)
- Sample tickers and price data
- Gate statuses
- Economic safety metrics
- IoS module registry

## ADR-005 Compliance

This dashboard implements the following ADR-005 requirements:

1. **Single Human Operator**: CEO-only access indicator in navigation
2. **Hybrid Interaction Model**: Data panels + governance controls
3. **Action Categories**:
   - Category A: Observational (all current views)
   - Category B: Operational (future - ingestion, reconciliation)
   - Category C: Governance (future - config changes via gates)
4. **Data Lineage**: Every card shows source tables/views
5. **VEGA Integration**: Trust banner shows governance status

## Project Structure

```
dashboard-2026/
├── app/                    # Next.js App Router pages
│   ├── page.tsx           # Overview page
│   ├── market-data/       # IoS-001 Market Pulse
│   ├── finn-intelligence/ # IoS-003 FINN Intelligence
│   ├── signals/           # Trading signals
│   └── system-health/     # Gates, ADRs, governance
├── components/
│   ├── ui/                # Base UI components
│   ├── TrustBanner.tsx    # System health banner
│   └── Navigation.tsx     # Main navigation
├── db/
│   ├── schema.ts          # Drizzle schema definitions
│   ├── index.ts           # Database connection
│   └── seed.ts            # Database seeding script
└── lib/
    ├── data.ts            # Data fetching functions
    └── utils.ts           # Utility functions
```

## Development

```bash
# Type checking
npm run type-check

# Linting
npm run lint

# Build for production
npm run build

# Database studio (GUI)
npm run db:studio
```

## Governance

All dashboard operations are:
- Identity-bound to CEO
- Logged for lineage (ADR-002)
- Subject to VEGA governance (ADR-006)
- Compliant with economic safety (ADR-012)

## IoS Modules

The dashboard exposes these Application Layer modules:

| Module | Name | Status |
|--------|------|--------|
| IoS-001 | Market Pulse | Active |
| IoS-002 | Alpha Drift Monitor | Active |
| IoS-003 | FINN Intelligence v3 | Active |
| IoS-006 | Research Workspace | Planned |

## License

Proprietary - FjordHQ / MetaStark

---

**Author**: Claude Agent
**ADR Reference**: ADR-005 Human Interaction & Application Layer Charter
**Last Updated**: 2025-11-27
