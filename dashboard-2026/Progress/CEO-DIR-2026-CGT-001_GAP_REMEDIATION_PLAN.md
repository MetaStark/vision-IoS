# CEO-DIR-2026-CALENDAR-GOVERNED-TESTING-001 Gap Remediation Plan

**Date:** 2026-01-24
**Author:** STIG (EC-003)
**Status:** AWAITING CEO APPROVAL

---

## Executive Summary

The FjordHQ Calendar Dashboard displays **~4% of available data**. This plan addresses all gaps identified in the directive compliance review.

**Root Cause:** v_dashboard_calendar view does NOT include `fhq_calendar.calendar_events` table.

---

## GAP ANALYSIS

### Critical Gaps (Must Fix)

| Gap | Current | Required | Impact |
|-----|---------|----------|--------|
| Economic Events (IoS-016) | 0 displayed | 45 in DB | CEO cannot see market calendar |
| Canonical Test Fields | 10 of 40 | All Section 3 fields | No "why" context |
| v_dashboard_calendar view | Missing UNION | Include calendar_events | 96% data invisible |

### Section-by-Section Compliance Review

| Section | Title | Status | Gap Description |
|---------|-------|--------|-----------------|
| 1 | Canonical Storage & Machine Readability | COMPLIANT | Runbooks in correct location |
| 2 | FjordHQ Calendar Dashboard Authority | **PARTIAL** | Missing economic events from IoS-016 |
| 3 | Canonical Test Event Schema | **PARTIAL** | UI doesn't show business_intent, baseline_definition, target_metrics, success/failure criteria |
| 4 | Dynamic Sample Size Governance | COMPLIANT | Implemented correctly |
| 4.3 | Calendar-Driven CEO Interaction | **PARTIAL** | Decision options queried but not rendered in UI |
| 5 | Mandatory RUNBOOK Content | COMPLIANT | All required fields present |
| 5.5 | LVG Status (Correction) | COMPLIANT | Fully implemented |
| 6 | Automatic RUNBOOK Propagation | COMPLIANT | Lifecycle log exists |
| 6.3 | Shadow Tier Mirroring (Correction) | COMPLIANT | View and display working |
| 7 | Success Path - Auto SOP | READY | Schema exists, awaiting test completion |
| 8 | EC-022 Observation Window | **PARTIAL** | Rich details (expected_improvement, improvement_metrics) not shown |
| 9 | Fail-Closed Behavior | COMPLIANT | check_calendar_sync() implemented |
| 10 | Acceptance Criteria | **INCOMPLETE** | 4% data visible, target is 100% |
| 11 | Shadow Veto Integration (Correction) | READY | Divergence audit log implemented |

---

## DETAILED GAP ANALYSIS

### Gap 1: Economic Events (IoS-016) NOT Displayed

**Database State:**
- `fhq_calendar.calendar_events`: 45 events exist
- `fhq_calendar.event_type_registry`: 23 event types defined
- Event types include: US_FOMC, US_NFP, US_CPI, US_GDP, ECB_RATE, BTC_HALVING, DIVIDEND_EX

**View State:**
```sql
-- v_dashboard_calendar UNION includes:
✓ canonical_test_events
✓ ceo_calendar_alerts
✓ observation_window
✓ divergence_audit_log
✗ calendar_events  <-- MISSING
```

**UI State:**
- No EconomicEventsPanel component exists
- Calendar grid cannot display events it doesn't receive
- API route does not query calendar_events

### Gap 2: Section 3 Fields NOT Displayed

**Database has these fields (canonical_test_events):**
```
business_intent          TEXT NOT NULL  -- "Why are we doing this"
beneficiary_system       TEXT NOT NULL  -- "Which agent benefits"
baseline_definition      JSONB NOT NULL -- "What normal means"
target_metrics           JSONB NOT NULL -- "Expected values"
expected_trajectory      JSONB          -- "Day-by-day expected path"
hypothesis_code          TEXT           -- "Linked hypothesis"
success_criteria         JSONB NOT NULL -- "What success looks like"
failure_criteria         JSONB NOT NULL -- "What failure looks like"
escalation_rules         JSONB NOT NULL -- "When to escalate"
mid_test_checkpoint      DATE           -- "Review date"
```

**UI displays only:**
```typescript
interface ActiveTest {
  name: string           ✓
  code: string           ✓
  owner: string          ✓
  status: string         ✓
  daysElapsed: number    ✓
  daysRemaining: number  ✓
  currentSamples: number ✓
  targetSamples: number  ✓
  sampleStatus: string   ✓
  category: string       ✓
  // MISSING: businessIntent, beneficiarySystem, baselineDefinition, etc.
}
```

**CEO Experience:**
- Sees "EC-022 Reward Logic Observation Window"
- Does NOT see "Why: Validate context integration provides predictive lift"
- Does NOT see "Beneficiary: EC-022 Reward Architect"
- Does NOT see success criteria

### Gap 3: CEO Decision Options NOT Rendered

**Database has:**
```sql
ceo_calendar_alerts.decision_options = '[
  {"option": "increase_sample_size", "description": "..."},
  {"option": "extend_duration", "description": "..."},
  ...
]'
```

**UI shows:**
- Alert title ✓
- Alert summary ✓
- "3 decision options available" ✓
- **Actual options NOT rendered** ✗

---

## IMPLEMENTATION PLAN

### Phase 1: Database View Fix (Migration 341)

**File:** `04_DATABASE/MIGRATIONS/341_calendar_economic_events_union.sql`

**Purpose:** Add economic events to v_dashboard_calendar view

**SQL to add:**
```sql
-- Add to v_dashboard_calendar UNION
UNION ALL

-- Economic Events (IoS-016)
SELECT
    event_id as event_id,
    event_name as event_name,
    'ECONOMIC_EVENT' as event_category,
    event_timestamp::date as event_date,
    NULL as end_date,
    status as event_status,
    'IoS-016' as owning_agent,
    jsonb_build_object(
        'event_type', event_type,
        'consensus_estimate', consensus_estimate,
        'previous_value', previous_value,
        'actual_value', actual_value,
        'surprise_score', surprise_score,
        'importance', importance
    ) as event_details,
    CASE importance
        WHEN 'HIGH' THEN '#dc2626'    -- Red
        WHEN 'MEDIUM' THEN '#f59e0b'  -- Amber
        ELSE '#6b7280'                -- Gray
    END as color_code,
    created_at
FROM fhq_calendar.calendar_events
WHERE event_timestamp >= CURRENT_DATE - INTERVAL '7 days'
  AND event_timestamp <= CURRENT_DATE + INTERVAL '30 days'
```

### Phase 2: API Route Enhancement

**File:** `dashboard-2026/app/api/calendar/route.ts`

**Changes:**

1. **Expand activeTests mapping** (line ~152-162):
```typescript
activeTests: activeTestsResult.rows.map((t: any) => ({
  // Existing fields
  name: t.test_name,
  code: t.test_code,
  owner: t.owning_agent,
  status: t.status,
  daysElapsed: t.days_elapsed,
  daysRemaining: t.days_remaining,
  currentSamples: t.current_sample_size,
  targetSamples: t.target_sample_size,
  sampleStatus: t.sample_trajectory_status,
  category: t.calendar_category,
  // NEW Section 3 fields
  businessIntent: t.business_intent,
  beneficiarySystem: t.beneficiary_system,
  baselineDefinition: t.baseline_definition,
  targetMetrics: t.target_metrics,
  expectedTrajectory: t.expected_trajectory,
  hypothesisCode: t.hypothesis_code,
  successCriteria: t.success_criteria,
  failureCriteria: t.failure_criteria,
  escalationRules: t.escalation_rules,
  midTestCheckpoint: t.mid_test_checkpoint,
})),
```

2. **Add dedicated economic events query:**
```typescript
// Economic events from IoS-016
const economicResult = await client.query(`
  SELECT
    event_id,
    event_name,
    event_type,
    event_timestamp,
    consensus_estimate,
    previous_value,
    actual_value,
    surprise_score,
    importance,
    status,
    provider
  FROM fhq_calendar.calendar_events
  WHERE event_timestamp >= CURRENT_DATE - INTERVAL '7 days'
    AND event_timestamp <= CURRENT_DATE + INTERVAL '30 days'
  ORDER BY event_timestamp ASC
`)

// Add to response
economicEvents: economicResult.rows.map((e: any) => ({
  id: e.event_id,
  name: e.event_name,
  type: e.event_type,
  timestamp: e.event_timestamp,
  consensus: e.consensus_estimate,
  previous: e.previous_value,
  actual: e.actual_value,
  surprise: e.surprise_score,
  importance: e.importance,
  status: e.status,
  provider: e.provider,
})),
```

### Phase 3: UI Components

#### 3a. Enhanced ActiveTestsPanel

**File:** `dashboard-2026/components/calendar/ActiveTestsPanel.tsx`

**Changes:**
1. Expand interface with Section 3 fields
2. Add collapsible "Business Context" section:

```tsx
{/* Business Context (Section 3 Required) */}
<div className="mt-4 pt-4 border-t border-gray-700/50">
  <button
    onClick={() => setExpanded(!expanded)}
    className="flex items-center gap-2 text-sm text-gray-400"
  >
    <ChevronDown className={cn("h-4 w-4", expanded && "rotate-180")} />
    Business Context
  </button>

  {expanded && (
    <div className="mt-3 space-y-3 text-sm">
      <div>
        <p className="text-gray-500 text-xs">Why are we doing this?</p>
        <p className="text-white">{test.businessIntent}</p>
      </div>
      <div>
        <p className="text-gray-500 text-xs">Who benefits if successful?</p>
        <p className="text-white">{test.beneficiarySystem}</p>
      </div>
      <div>
        <p className="text-gray-500 text-xs">Success Criteria</p>
        <pre className="text-xs text-gray-400 bg-gray-800/50 rounded p-2">
          {JSON.stringify(test.successCriteria, null, 2)}
        </pre>
      </div>
    </div>
  )}
</div>
```

#### 3b. New EconomicEventsPanel Component

**File:** `dashboard-2026/components/calendar/EconomicEventsPanel.tsx`

**Purpose:** Display IoS-016 economic calendar events

**Features:**
- Compact list of upcoming events
- Date/time display in human format
- Event type with icon (FOMC=bank, NFP=briefcase, CPI=chart)
- Consensus vs Previous value display
- Color-coded importance (HIGH=red, MEDIUM=amber, LOW=gray)
- Surprise score when actual available

**Component Structure:**
```tsx
export function EconomicEventsPanel({ events }: { events: EconomicEvent[] }) {
  // Group by date
  const groupedEvents = groupByDate(events)

  return (
    <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-6">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="h-5 w-5 text-amber-400" />
        <h3 className="text-lg font-semibold text-white">Economic Calendar</h3>
        <span className="ml-auto text-xs text-gray-500">IoS-016</span>
      </div>

      {Object.entries(groupedEvents).map(([date, dayEvents]) => (
        <div key={date} className="mb-4">
          <p className="text-xs text-gray-500 mb-2">{formatDate(date)}</p>
          {dayEvents.map(event => (
            <EconomicEventRow key={event.id} event={event} />
          ))}
        </div>
      ))}
    </div>
  )
}
```

#### 3c. Enhanced Observation Window Display

**File:** `dashboard-2026/app/calendar/page.tsx` (inline)

**Add to observation window cards:**
```tsx
{window.expectedImprovement && (
  <div className="mt-3 pt-3 border-t border-gray-700/50">
    <p className="text-xs text-gray-500">Expected Improvement</p>
    <p className="text-sm text-white mt-1">{window.expectedImprovement}</p>
  </div>
)}
```

### Phase 4: Calendar Page Integration

**File:** `dashboard-2026/app/calendar/page.tsx`

**Changes:**

1. Add Economic Events section:
```tsx
{/* Economic Calendar (IoS-016) */}
<div>
  <div className="mb-3 flex items-center gap-2">
    <div className="h-1 w-1 rounded-full bg-amber-500" />
    <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
      Economic Calendar (Section 2 - IoS-016)
    </h2>
  </div>
  <EconomicEventsPanel events={data?.economicEvents || []} />
</div>
```

2. Update event detail modal to show Section 3 context
3. Add CEO decision options rendering in alert modal

---

## FILES TO MODIFY

| # | File | Action | Lines Changed |
|---|------|--------|---------------|
| 1 | `04_DATABASE/MIGRATIONS/341_calendar_economic_events_union.sql` | CREATE | ~50 |
| 2 | `dashboard-2026/app/api/calendar/route.ts` | EDIT | ~60 |
| 3 | `dashboard-2026/components/calendar/ActiveTestsPanel.tsx` | EDIT | ~100 |
| 4 | `dashboard-2026/components/calendar/EconomicEventsPanel.tsx` | CREATE | ~150 |
| 5 | `dashboard-2026/components/calendar/index.ts` | EDIT | ~2 |
| 6 | `dashboard-2026/app/calendar/page.tsx` | EDIT | ~80 |
| 7 | `12_DAILY_REPORTS/DAY24_RUNBOOK_20260124.md` | EDIT | ~30 |

**Total:** ~470 lines of code

---

## VERIFICATION PLAN

### Database Verification
```sql
-- Should return 47+ events after migration (45 economic + 2 existing)
SELECT COUNT(*) FROM fhq_calendar.v_dashboard_calendar;

-- Should include ECONOMIC_EVENT category
SELECT DISTINCT event_category FROM fhq_calendar.v_dashboard_calendar;
-- Expected: ACTIVE_TEST, OBSERVATION_WINDOW, ECONOMIC_EVENT, (CEO_ACTION_REQUIRED), (DIVERGENCE_POINT)

-- Verify economic events have correct color codes
SELECT event_category, color_code, COUNT(*)
FROM fhq_calendar.v_dashboard_calendar
GROUP BY event_category, color_code;
```

### API Verification
```bash
curl http://localhost:3000/api/calendar | jq '.economicEvents | length'
# Expected: 45+

curl http://localhost:3000/api/calendar | jq '.activeTests[0].businessIntent'
# Expected: Non-null string
```

### UI Verification
1. Start dev server: `cd dashboard-2026 && npm run dev`
2. Navigate to `http://localhost:3000/calendar`
3. Verify checklist:
   - [ ] Economic events visible in calendar grid (color-coded by importance)
   - [ ] Economic Events panel shows upcoming events with date/time
   - [ ] Active tests show "Business Context" expandable section
   - [ ] Business Intent text visible when expanded
   - [ ] Success/Failure criteria visible when expanded
   - [ ] Observation windows show expected_improvement
   - [ ] CEO can understand system state in <30 seconds

---

## ACCEPTANCE CRITERIA (Section 10 - Binary)

| # | Criteria | Test Method | Expected Result |
|---|----------|-------------|-----------------|
| 1 | Calendar fully represents system reality | Count events in view | 47+ events visible |
| 2 | Tests explain themselves without CEO archaeology | Check business_intent display | Visible in UI |
| 3 | CEO only interrupted when judgment required | Review alert workflow | Decision options rendered |
| 4 | Every test has purpose, owner, metric, end state | Check Section 3 fields | All visible |
| 5 | Economic calendar integrated | Check IoS-016 events | 45 events with date/time |

---

## RISK ASSESSMENT

| Risk | Mitigation |
|------|------------|
| Migration fails | Test on local DB first |
| Performance impact from 45+ events | Add date range filter (already in plan) |
| UI clutter | Use collapsible sections, grouping |

---

## CEO DECISION REQUIRED

**Before implementation, please confirm:**

1. Color scheme for economic events by importance:
   - HIGH: Red (#dc2626)
   - MEDIUM: Amber (#f59e0b)
   - LOW: Gray (#6b7280)

2. Date range for economic events:
   - Current plan: -7 days to +30 days
   - Alternative: +30 days only (future focused)

3. Business Context display:
   - Current plan: Collapsible section (default collapsed)
   - Alternative: Always visible

---

**Plan prepared by:** STIG (EC-003)
**Date:** 2026-01-24
**Awaiting:** CEO Approval
