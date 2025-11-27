# Dashboard 2026 - Quick Start Guide

**Status:** PHASE 6 COMPLETE ✅
**Ready for:** Local development & testing

---

## Prerequisites

- Node.js >= 18.0.0
- npm >= 9.0.0
- PostgreSQL database running on port 54322
- ACE Phases 0-5 operational (database populated with signals)

---

## Installation

```bash
# Navigate to dashboard directory
cd dashboard-2026

# Install dependencies
npm install
```

---

## Environment Configuration

Create `.env.local` file in `dashboard-2026/` directory:

```bash
# PostgreSQL connection (default: local development)
PGHOST=127.0.0.1
PGPORT=54322
PGDATABASE=postgres
PGUSER=postgres
PGPASSWORD=postgres

# Optional: Node environment
NODE_ENV=development
```

---

## Development Server

```bash
# Start Next.js development server
npm run dev

# Server will start at:
# http://localhost:3000
```

**Access Dashboard:**
```
http://localhost:3000/dashboard
```

---

## Testing API Routes

### Test all FINN API endpoints:

```bash
# 1. Meta Signal (3-layer narrative)
curl http://localhost:3000/api/finn/meta-signal?listing_id=LST_BTC_XCRYPTO | jq

# 2. Family Signals (4 families + consensus)
curl http://localhost:3000/api/finn/families?listing_id=LST_BTC_XCRYPTO | jq

# 3. Indicators Matrix (18 indicators)
curl http://localhost:3000/api/finn/indicators?listing_id=LST_BTC_XCRYPTO | jq

# 4. Indicator Explainer (FINN 5-step micro-dialog)
curl http://localhost:3000/api/finn/indicator/RSI_14?listing_id=LST_BTC_XCRYPTO | jq

# 5. Alpha Drift Status (institutional surveillance)
curl http://localhost:3000/api/finn/drift-status?listing_id=LST_BTC_XCRYPTO | jq
```

**Expected Response:** All endpoints should return JSON data without errors.

**Common Issues:**
- **500 Error:** Database connection failed → Check PostgreSQL is running on port 54322
- **404 Error:** No data found → Run ACE pipeline to populate database
- **Connection timeout:** Check `.env.local` credentials

---

## Testing Dashboard Components

### Zone 1: Hero Panel (3-second understanding)

**What to verify:**
- [ ] Meta allocation displays (e.g., "+35%", "-25%", "0%")
- [ ] Direction badge shows (LONG/SHORT/NEUTRAL)
- [ ] Regime badge displays (BULL/NEUTRAL/BEAR)
- [ ] FINN's verdict shows 3-layer narrative:
  - Layer 1: Macro stance ("BTC is in a neutral phase...")
  - Layer 2: Strategy architecture ("Strategies are conflicted...")
  - Layer 3: Recommendation ("Staying neutral until...")
- [ ] Drift status shows (NORMAL/WARNING/CRITICAL)
- [ ] Integrity status shows (✓ VERIFIED or ⚠ STALE)

**How to test:**
1. Open `http://localhost:3000/dashboard`
2. Check Hero Panel (top section)
3. Verify all elements render
4. Check browser console for errors

---

### Zone 2: Signal Grid (30-second comprehension)

**What to verify:**
- [ ] All 4 family cards render:
  - TREND_FOLLOWING (blue)
  - MEAN_REVERSION (green)
  - VOLATILITY (yellow)
  - BREAKOUT (purple)
- [ ] Each card shows:
  - Signal direction (LONG/SHORT/NEUTRAL)
  - Allocation % (e.g., "+40%")
  - Confidence bar (0-100%)
  - Conviction bar (0-100%)
  - Primary driver (strategy name)
- [ ] Consensus bar shows:
  - Alignment status ("All four families align" or "conflicted")
  - Count breakdown (2 LONG, 1 SHORT, 1 NEUTRAL)

**How to test:**
1. Scroll to Signal Grid (middle section)
2. Verify 4 cards in grid layout
3. Hover over cards (should scale slightly)
4. Check consensus interpretation

---

### Zone 3: Indicator Matrix (3-minute verification)

**What to verify:**
- [ ] All 18 indicators render in 6x3 grid
- [ ] Category filter works:
  - Click "All" → shows 18 indicators
  - Click "MOMENTUM" → shows RSI, MACD, Stochastic
  - Click "TREND" → shows EMAs, SMAs
  - Click "VOLATILITY" → shows Bollinger Bands, ATR
  - Click "VOLUME" → shows OBV
- [ ] Each indicator card shows:
  - Name (e.g., "RSI (14)")
  - Current value (e.g., "22.41")
  - Trend icon (↗ UP, ↘ DOWN, → FLAT)
  - Trend % change (e.g., "-8.3%")
  - Status badge (OVERSOLD/OVERBOUGHT if relevant)
- [ ] FINN tooltip appears on hover:
  - Shows "FINN is analyzing..." while loading
  - Displays 5-step micro-dialog
  - Shows regime context box
  - Shows integrity status (✓ Verified)

**How to test:**
1. Scroll to Indicator Matrix (bottom section)
2. Test category filter (click each button)
3. Hover over any indicator card
4. Verify FINN tooltip appears with complete data
5. Check tooltip disappears when mouse leaves

---

## Production Build

```bash
# Type check (ensure no TypeScript errors)
npm run type-check

# Build for production
npm run build

# Start production server
npm run start
```

**Production URL:**
```
http://localhost:3000/dashboard
```

---

## Common Issues & Solutions

### Issue: "Database connection error"

**Cause:** PostgreSQL not running or wrong port

**Solution:**
```bash
# Check if PostgreSQL is running
psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -c "SELECT 1"

# If fails, verify port in .env.local matches your PostgreSQL instance
```

---

### Issue: "No data available" / 404 errors

**Cause:** ACE database tables empty (no signals computed)

**Solution:**
```bash
# Run ACE daily pipeline to populate database
cd ..
python python/orchestration/daily_ace_pipeline.py 2025-11-17 manual

# Verify data exists
psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -c "
  SELECT signal_date, allocation_pct
  FROM fhq_ace.meta_allocations
  ORDER BY signal_date DESC
  LIMIT 5;
"
```

---

### Issue: "FINN tooltip shows 'Error loading FINN analysis'"

**Cause:** API route `/api/finn/indicator/[id]` failing

**Solution:**
```bash
# Test API route directly
curl http://localhost:3000/api/finn/indicator/RSI_14?listing_id=LST_BTC_XCRYPTO

# Check browser console for error details
# Common cause: Indicator not in fhq_indicators tables
```

---

### Issue: "Components render but show stale data"

**Cause:** Caching or old data in database

**Solution:**
```bash
# Force refresh in browser (disable cache)
# Chrome/Edge: Ctrl+Shift+R (Windows) / Cmd+Shift+R (Mac)
# Firefox: Ctrl+F5 (Windows) / Cmd+Shift+R (Mac)

# Or click "Refresh" button in dashboard top-right
```

---

## Performance Benchmarks

**Expected Load Times:**

| Component | Target | Acceptable | Needs Optimization |
|-----------|--------|------------|-------------------|
| Hero Panel | <500ms | <1s | >1s |
| Signal Grid | <500ms | <1s | >1s |
| Indicator Matrix | <1s | <2s | >2s |
| FINN Tooltip | <200ms | <500ms | >500ms |
| **Total Page Load** | **<2s** | **<3s** | **>3s** |

**How to measure:**
1. Open browser DevTools (F12)
2. Go to Network tab
3. Reload page (Ctrl+R)
4. Check "Load" time at bottom of Network tab

---

## Next Steps

### Immediate Testing

1. **Visual QA:**
   - [ ] Check all colors match semantic system (green/red/blue/yellow)
   - [ ] Verify fonts are readable (no tiny text)
   - [ ] Test hover effects (1px glow, 150ms animation)
   - [ ] Verify responsive layout (test at 1920px, 1440px, 1280px widths)

2. **Functional QA:**
   - [ ] Asset selector works (BTC-USD functional, ETH/SOL disabled)
   - [ ] Refresh button reloads all zones
   - [ ] Category filter in Indicator Matrix works
   - [ ] FINN tooltips load without errors

3. **Data QA:**
   - [ ] FINN narratives follow 3-layer framework
   - [ ] Tooltips use 5-step micro-dialog pattern
   - [ ] All numbers match database values
   - [ ] Integrity status reflects actual data freshness

### Phase 7 Preparation

- [ ] Write automated tests (Playwright E2E)
- [ ] Performance profiling (identify slow API routes)
- [ ] Multi-asset expansion (enable ETH, SOL)
- [ ] Mobile responsive testing
- [ ] Browser compatibility (Chrome, Firefox, Safari, Edge)

---

## Documentation Links

- **UX Specification:** `docs/Dashboard_UX_Specification_2026.md`
- **FINN Voice Guidelines:** `docs/FINN_Voice_Guidelines.md`
- **Executive Narrative:** `docs/Dashboard_Executive_Narrative.md`
- **Implementation Summary:** `docs/Phase6_Dashboard_Implementation_Summary.md`
- **ACE Architecture:** `docs/Phase5_Daily_Automation_Guide.md`

---

## Support

**Issue Tracking:** Create GitHub issue with:
- Browser + version
- Error message (console logs)
- Steps to reproduce
- Screenshot if visual issue

**Contact:**
- Technical: STIG (Technical Officer)
- Architecture: LARS (Architecture Lead)

---

**Last Updated:** 2025-11-18
**Status:** READY FOR TESTING ✅
