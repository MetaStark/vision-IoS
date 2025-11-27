# Dashboard 2026 - Implementation Plan

## Executive Summary

**Total Timeline**: 8-10 weeks in 4 phases
**Current Status**: Phase 1 Sprint 1.1 COMPLETE ✅
**Next Step**: Sprint 1.2 - Complete Home page with real data

---

## Phase Breakdown

### PHASE 1: Foundation & Core Modules (Week 1-3) 🔄

#### ✅ Sprint 1.1: Infrastructure (Week 1) - **COMPLETE**
- [x] Migrere fra Next.js prototype til produksjonsstruktur
- [x] Sette opp Supabase TypeScript types generator
- [x] Implementere globalt layout med Trust Banner
- [x] Design system (Tailwind config, farger, spacing, typography)
- [x] Komponent-bibliotek: Card, StatusBadge, MetricCard, DataLineage
- [x] Database connection pooling og error handling
- [x] SQL migrations for missing views/tables

**Deliverables**: ✅ Working skeleton app, SQL migrations, component library

---

#### 🔄 Sprint 1.2: Home / Overview (Week 1-2) - **IN PROGRESS**
- [ ] Real Trust Banner data (fetch gate status, alerts, freshness from DB)
- [ ] Data freshness for multiple assets (BTC, ETH, GSPC)
- [ ] Enhanced metrics grid with real-time calculations
- [ ] Loading states (skeleton loaders)
- [ ] Error boundaries and fallback UI
- [ ] Client-side data fetching with SWR (for real-time updates)

**Deliverables**: Fully functional Home page with real data, loading states, error handling

**Implementation Tasks**:

1. **Trust Banner Real Data** (`components/TrustBanner.tsx`)
   ```typescript
   // Fetch from:
   // - fhq_validation.v_gate_a_summary (gate status)
   // - fhq_monitoring.v_drift_alert_history (alert count)
   // - fhq_meta.v_active_adrs (ADR compliance)
   // - fhq_finn.v_btc_data_freshness (data freshness)
   ```

2. **Multi-Asset Freshness** (`app/page.tsx`)
   ```typescript
   // Add freshness checks for ETH, GSPC
   // Display in separate cards or grid
   ```

3. **Loading States** (`components/ui/Skeleton.tsx`)
   ```typescript
   // Create Skeleton component
   // Add to all data-fetching sections
   ```

4. **Error Boundaries** (`components/ErrorBoundary.tsx`)
   ```typescript
   // React Error Boundary wrapper
   // Fallback UI for failed data fetches
   ```

---

#### 🚧 Sprint 1.3: Market Data Module (Week 2-3) - **NEXT**
- [ ] Asset selector component (BTC, ETH, GSPC, others from `fhq_meta.tickers`)
- [ ] Multi-resolution support (1h/1d) - reuse Streamlit logic from `/dashboard`
- [ ] Time range switcher (presets: 1M, 3M, 6M, 1Y, MAX for daily; 24h, 3D, 7D, 14D, 30D for hourly)
- [ ] Price chart component (Recharts - candlestick/line)
- [ ] Indicator overlay system (RSI, MACD, EMA from `v_btc_indicators_pivoted`)
- [ ] Data freshness badge per asset (`v_btc_data_freshness`)
- [ ] Summary stats panel (period high/low, volatility, volume)
- [ ] Tooltip/info system for data lineage

**Deliverables**: Fully functional Market Data module with charts, indicators, multi-resolution

**Implementation Tasks**:

1. **Asset Selector** (`components/modules/MarketData/AssetSelector.tsx`)
   ```typescript
   // Fetch from fhq_meta.tickers
   // Dropdown with search
   // Show asset name, ticker, exchange
   ```

2. **Chart Component** (`components/charts/PriceChart.tsx`)
   ```typescript
   // Recharts candlestick chart
   // Support both 1h and 1d resolution
   // Dynamic x-axis formatting
   ```

3. **Indicator Overlay** (`components/charts/IndicatorOverlay.tsx`)
   ```typescript
   // Checkboxes for RSI, MACD, EMA
   // Fetch from v_btc_indicators_pivoted
   // Render as additional traces on chart
   ```

4. **Data Freshness Badge** (`components/ui/FreshnessBadge.tsx`)
   ```typescript
   // Reuse StatusBadge
   // Fetch freshness per asset
   // Show in card header
   ```

---

### PHASE 2: Intelligence & Signals (Week 4-5) 🚧

#### Sprint 2.1: Signal Feed Module (Week 4)
- [ ] Unified signal stream component
- [ ] Signal card UI (timestamp, asset, type, severity, metrics)
- [ ] Advanced filter panel (asset, type, severity, recency, source)
- [ ] "Top 3 Signals Right Now" section (based on `relevance_scores`)
- [ ] Drill-into links to Market Data and FINN context
- [ ] Real-time updates with SWR (1-min refresh)

**Data Sources**:
- `fhq_finn.signal_events`
- `fhq_events.trading_signals`, `anomalies`, `whale_movements`, `sentiment_signals`
- `fhq_finn.v_event_summary_24h`, `v_high_relevance_events`, `v_high_cognitive_dissonance`

---

#### Sprint 2.2: FINN Intelligence Module (Week 5)
- [ ] "Today's Briefing" panel (`v_latest_briefing`, `daily_briefings`)
- [ ] "Regime & Market State" panel (`v_btc_regime_current`, `v_btc_regime_history`)
- [ ] "Derivatives & Fragility" panel (`v_latest_derivative_metrics`)
- [ ] "FINN Quality & Confidence" panel (`v_finn_quality_scorecard`, quality tier gauge)
- [ ] Contract validation warnings display

---

### PHASE 3: Governance & Compliance (Week 6-7) 🚧

#### Sprint 3.1: System Health Module (Week 6)
**Sub-panes:**
1. Data Quality & Freshness
2. Model & Regime Monitoring
3. Vendor & Ingestion Health

#### Sprint 3.2: ADR Governance & Audit (Week 7)
**Sub-panes:**
4. ADR Governance & Events
5. Gate Audit Integration

**Trust Banner Finalization**:
- Real-time gate status
- Active alerts count
- ADR compliance badge

---

### PHASE 4: Augmentation & Polish (Week 8-10) 🚧

#### Sprint 4.1: Research & Backtesting Module (Week 8)
- [ ] Backtest results viewer
- [ ] Strategy performance charts
- [ ] Feature performance table
- [ ] Lessons learned viewer
- [ ] Interactive backtest runner (via MCP Docker exec)

#### Sprint 4.2: Knowledge Graph & RAG (Week 9) - OPTIONAL
- [ ] Knowledge Graph visualization (D3.js force-directed graph)
- [ ] Research Library (searchable `bitcoin_research`, `market_narratives`)
- [ ] RAG query interface (via MCP FINN server)
- [ ] FINN Chat Interface (`finn_chat_history`)

#### Sprint 4.3: UX Polish & Testing (Week 10)
- [ ] Skeleton loaders for all data fetches
- [ ] Error boundaries and fallback UI
- [ ] Responsive design (laptop primary, tablet graceful)
- [ ] Theme switcher (light/dark mode optional)
- [ ] Keyboard shortcuts for power users
- [ ] Performance optimization (bundle size, lazy loading)
- [ ] Comprehensive E2E testing (Playwright)
- [ ] User acceptance testing (Executive/Quant/Operator personas)
- [ ] Documentation (user guide + developer docs)

---

## TODO Tracking

### Immediate Next Steps (Sprint 1.2)

**Priority 1 - Trust Banner Real Data**:
```bash
# File: components/TrustBanner.tsx
# Task: Replace mock data with real DB queries
# Estimated: 2 hours
```

**Priority 2 - Multi-Asset Freshness**:
```bash
# File: app/page.tsx
# Task: Add ETH, GSPC freshness checks
# Estimated: 1 hour
```

**Priority 3 - Loading States**:
```bash
# File: components/ui/Skeleton.tsx (new)
# Task: Create skeleton loader component
# Estimated: 1 hour
```

**Priority 4 - Error Boundaries**:
```bash
# File: components/ErrorBoundary.tsx (new)
# Task: React Error Boundary with fallback UI
# Estimated: 1 hour
```

---

## Missing Components Checklist (From Technical Design)

### ✅ COMPLETE
- [x] `fhq_meta.dashboard_config` table
- [x] `fhq_finn.v_high_relevance_events` view
- [x] `fhq_validation.v_gate_audit_integration` view
- [x] Next.js project structure
- [x] Component library (Card, StatusBadge, MetricCard)
- [x] Global layout + Trust Banner skeleton
- [x] Home page skeleton

### 🚧 IN PROGRESS
- [ ] Trust Banner with real data
- [ ] Home page with loading states

### 📋 TODO (Phase 1)
- [ ] Market Data module (Sprint 1.3)
- [ ] Recharts integration
- [ ] Multi-resolution chart support

### 📋 TODO (Phase 2+)
- [ ] Signal Feed module
- [ ] FINN Intelligence module
- [ ] System Health module
- [ ] Research module
- [ ] Knowledge Graph (optional)

---

## Development Workflow

### 1. Local Development
```bash
cd dashboard-2026
npm install
npm run dev
# Open http://localhost:3000
```

### 2. Database Migrations
```bash
# Run from project root
psql postgresql://postgres:postgres@localhost:54322/postgres -f sql/create_missing_dashboard_components.sql
```

### 3. TypeScript Types Generation (when Supabase is fully set up)
```bash
cd dashboard-2026
npm run db:types
```

### 4. Testing
```bash
# Type checking
npm run type-check

# Linting
npm run lint

# Build test
npm run build
```

---

## Notes & Decisions

### Confirmed Decisions (from User Clarifications)

✅ **A3**: Drop `v_active_execution_plans` from Phase 1 (add as future feature)
✅ **B1**: Real-time data via polling first (mark WebSocket as TODO)
✅ **B2**: Start with BTC-USD only, 10 assets later (TODO)
✅ **B3**: Single user, no auth (Phase 1)
✅ **C1**: Recharts + D3.js for charts
✅ **C2**: Phase 1 hardcoded thresholds (logged), Phase 2 dynamic config
✅ **C3**: 3-level hierarchy (0-3s: answer, 3-10s: components, 10s+: lineage)
✅ **D1**: Versioned Supabase migrations
✅ **D2**: JSON schema data contracts, batch validation
✅ **D3**: Write actions only logged, via MCP

### Risk Mitigation

- **CDS function**: Exists but not populated with data → Phase 2 integration
- **Multi-asset**: BTC-only Phase 1 → 10 assets Phase 2
- **Real-time**: Polling Phase 1 → WebSocket Phase 2
- **RBAC**: Single-user Phase 1 → Supabase Auth Phase 2

---

## Success Criteria

### Sprint 1.2 (Next)
- [ ] Home page loads in <2s with real data
- [ ] Trust Banner shows accurate system health
- [ ] Loading states prevent "flash of empty content"
- [ ] Error boundaries prevent full-page crashes
- [ ] All data lineage tooltips work

### Sprint 1.3 (Market Data)
- [ ] BTC chart renders in <500ms
- [ ] Switching resolution (1h/1d) works smoothly
- [ ] Indicator overlays render correctly
- [ ] Data freshness badge updates in real-time

### Phase 1 Complete
- [ ] Home + Market Data modules fully functional
- [ ] Trust Banner with real-time health data
- [ ] All components have data lineage
- [ ] No console errors
- [ ] TypeScript builds without errors

---

**Last Updated**: 2025-11-15
**Author**: Claude Agent
**Review Status**: Ready for Sprint 1.2
