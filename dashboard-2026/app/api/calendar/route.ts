/**
 * Calendar Dashboard API - CEO-DIR-2026-CALENDAR-GOVERNED-TESTING-001
 *
 * Calendar-as-Law Doctrine: If something matters, it exists as a canonical calendar event.
 * CEO must understand system state in <30 seconds.
 */

import { NextResponse } from 'next/server'
import { Pool } from 'pg'

const pool = new Pool({
  host: process.env.PGHOST || '127.0.0.1',
  port: parseInt(process.env.PGPORT || '54322'),
  database: process.env.PGDATABASE || 'postgres',
  user: process.env.PGUSER || 'postgres',
  password: process.env.PGPASSWORD || 'postgres',
})

export async function GET() {
  let client
  try {
    client = await pool.connect()

    // Fetch dashboard calendar events
    const calendarResult = await client.query(`
      SELECT
        event_id,
        event_name,
        event_category,
        event_date,
        end_date,
        event_status,
        owning_agent,
        event_details,
        color_code,
        year,
        month,
        day,
        day_name
      FROM fhq_calendar.v_dashboard_calendar
      WHERE event_date >= CURRENT_DATE - INTERVAL '30 days'
        AND event_date <= CURRENT_DATE + INTERVAL '60 days'
      ORDER BY event_date ASC, created_at DESC
    `)

    // Fetch LVG status for daily reports
    const lvgResult = await client.query(`
      SELECT * FROM fhq_calendar.v_lvg_daily_status
    `)

    // CEO-DIR-2026-DAY25: Fetch cumulative hypothesis totals
    const cumulativeResult = await client.query(`
      SELECT
        COUNT(*) as total_hypotheses,
        COUNT(*) FILTER (WHERE status = 'FALSIFIED') as total_falsified,
        COUNT(*) FILTER (WHERE status NOT IN ('FALSIFIED', 'DRAFT')) as total_active,
        CASE
          WHEN COUNT(*) FILTER (WHERE status != 'DRAFT') = 0 THEN 0
          ELSE ROUND(COUNT(*) FILTER (WHERE status = 'FALSIFIED')::numeric /
               NULLIF(COUNT(*) FILTER (WHERE status != 'DRAFT'), 0) * 100, 1)
        END as death_rate_pct,
        MAX(created_at) as last_hypothesis_time
      FROM fhq_learning.hypothesis_canon
    `)
    const cumulative = cumulativeResult.rows[0] || {}

    // Fetch shadow tier status
    const shadowTierResult = await client.query(`
      SELECT * FROM fhq_calendar.v_shadow_tier_calendar_status
    `)

    // Fetch fail-closed governance checks
    const governanceResult = await client.query(`
      SELECT * FROM fhq_calendar.check_calendar_sync()
    `)

    // Fetch canonical tests with ALL CEO-required fields (Migration 342)
    const canonicalTestsResult = await client.query(`
      SELECT
        test_id,
        test_code,
        COALESCE(display_name, test_name) as test_name,
        owning_agent,
        status,
        -- Timestamps (immutable once ACTIVE)
        start_ts,
        end_ts,
        -- Progress (computed from storage)
        days_elapsed,
        days_remaining,
        required_days,
        ROUND((COALESCE(days_elapsed, 0)::NUMERIC / NULLIF(required_days, 0)) * 100, 1) as progress_pct,
        -- Section 3 required fields
        business_intent,
        beneficiary_system,
        baseline_definition,
        target_metrics,
        hypothesis_code,
        success_criteria,
        failure_criteria,
        -- Governance (CEO Modification 5)
        monitoring_agent_ec,
        escalation_state,
        ceo_action_required,
        recommended_actions,
        mid_test_checkpoint,
        verdict,
        -- Calendar
        calendar_category
      FROM fhq_calendar.canonical_test_events
      WHERE status IN ('ACTIVE', 'SCHEDULED', 'COMPLETED')
      ORDER BY
        CASE WHEN ceo_action_required THEN 0 ELSE 1 END,
        start_ts ASC
    `)

    // Fetch economic events from IoS-016 (Section 2)
    const economicEventsResult = await client.query(`
      SELECT
        ce.event_id,
        etr.event_name,
        ce.event_type_code,
        ce.event_timestamp,
        ce.consensus_estimate,
        ce.previous_value,
        ce.actual_value,
        ce.surprise_score,
        etr.impact_rank,
        etr.event_category as economic_category,
        CASE
          WHEN ce.actual_value IS NOT NULL THEN 'RELEASED'
          WHEN ce.event_timestamp < NOW() THEN 'PENDING'
          ELSE 'SCHEDULED'
        END as status
      FROM fhq_calendar.calendar_events ce
      JOIN fhq_calendar.event_type_registry etr
        ON ce.event_type_code = etr.event_type_code
      WHERE ce.event_timestamp >= CURRENT_DATE - INTERVAL '7 days'
        AND ce.event_timestamp <= CURRENT_DATE + INTERVAL '60 days'
        AND ce.is_canonical = TRUE
      ORDER BY ce.event_timestamp ASC
    `)

    // Fetch pending CEO alerts
    const alertsResult = await client.query(`
      SELECT
        alert_id,
        alert_type,
        alert_title,
        alert_summary,
        decision_options,
        priority,
        status,
        calendar_date,
        created_at
      FROM fhq_calendar.ceo_calendar_alerts
      WHERE status = 'PENDING'
      ORDER BY
        CASE priority
          WHEN 'CRITICAL' THEN 1
          WHEN 'HIGH' THEN 2
          WHEN 'NORMAL' THEN 3
          ELSE 4
        END,
        created_at ASC
    `)

    // Fetch observation windows with rich details (Section 8)
    const observationResult = await client.query(`
      SELECT
        window_name,
        window_type,
        start_date,
        end_date,
        required_market_days,
        current_market_days,
        status,
        criteria_met,
        volume_scaling_active,
        metric_drift_alerts,
        expected_improvement,
        improvement_metrics,
        starting_consensus_state
      FROM fhq_learning.observation_window
      WHERE status = 'ACTIVE'
    `)

    // CEO-DIR-2026-DAY25: Learning Visibility Metrics (time-series for graphs)
    const learningMetricsResult = await client.query(`
      SELECT
        metric_date,
        hypotheses_total,
        hypotheses_falsified,
        death_rate_pct,
        from_errors,
        avg_causal_depth,
        gen_finn_e,
        gen_finn_t,
        gen_gn_s,
        gen_other
      FROM fhq_learning.v_daily_learning_metrics
      ORDER BY metric_date ASC
      LIMIT 30
    `)

    // CEO-DIR-2026-DAY25: Learning Status Summary
    const learningSummaryResult = await client.query(`
      SELECT * FROM fhq_learning.v_learning_status_summary
    `)

    // CEO-DIR-2026-DAY25: Generator Performance
    const generatorPerfResult = await client.query(`
      SELECT * FROM fhq_learning.v_generator_performance
    `)

    // Get current date info
    const dateResult = await client.query(`
      SELECT
        CURRENT_DATE as today,
        EXTRACT(YEAR FROM CURRENT_DATE) as year,
        EXTRACT(MONTH FROM CURRENT_DATE) as month,
        TO_CHAR(CURRENT_DATE, 'Month') as month_name
    `)

    const lvg = lvgResult.rows[0] || {}
    const shadowTier = shadowTierResult.rows[0] || {}
    const dateInfo = dateResult.rows[0] || {}

    return NextResponse.json({
      // Calendar events
      events: calendarResult.rows.map((e: any) => ({
        id: e.event_id,
        name: e.event_name,
        category: e.event_category,
        date: e.event_date,
        endDate: e.end_date,
        status: e.event_status,
        owner: e.owning_agent,
        details: e.event_details,
        color: e.color_code,
        year: parseInt(e.year),
        month: parseInt(e.month),
        day: parseInt(e.day),
        dayName: e.day_name?.trim(),
      })),

      // Canonical tests with CEO-required fields (Migration 342)
      canonicalTests: canonicalTestsResult.rows.map((t: any) => ({
        id: t.test_id,
        code: t.test_code,
        name: t.test_name,
        owner: t.owning_agent,
        status: t.status,
        category: t.calendar_category,
        // Timestamps (immutable)
        startDate: t.start_ts,
        endDate: t.end_ts,
        // Progress (computed from storage - CEO Mod 3)
        daysElapsed: parseInt(t.days_elapsed) || 0,
        daysRemaining: parseInt(t.days_remaining) || 0,
        requiredDays: parseInt(t.required_days) || 30,
        progressPct: parseFloat(t.progress_pct) || 0,
        // Purpose & Logic
        businessIntent: t.business_intent,
        beneficiarySystem: t.beneficiary_system,
        hypothesisCode: t.hypothesis_code,
        // Measurement
        baselineDefinition: t.baseline_definition,
        targetMetrics: t.target_metrics,
        successCriteria: t.success_criteria,
        failureCriteria: t.failure_criteria,
        // Governance (CEO Mod 5)
        monitoringAgent: t.monitoring_agent_ec,
        escalationState: t.escalation_state,
        ceoActionRequired: t.ceo_action_required || false,
        recommendedActions: t.recommended_actions || [],
        midTestCheckpoint: t.mid_test_checkpoint,
        verdict: t.verdict,
      })),

      // Legacy activeTests mapping (for backwards compatibility)
      activeTests: canonicalTestsResult.rows
        .filter((t: any) => t.status === 'ACTIVE' || t.status === 'SCHEDULED')
        .map((t: any) => ({
          name: t.test_name,
          code: t.test_code,
          owner: t.owning_agent,
          status: t.status,
          daysElapsed: parseInt(t.days_elapsed) || 0,
          daysRemaining: parseInt(t.days_remaining) || 0,
          currentSamples: 0,
          targetSamples: 0,
          sampleStatus: 'ON_TRACK',
          category: t.calendar_category,
          businessIntent: t.business_intent,
          beneficiarySystem: t.beneficiary_system,
          baselineDefinition: t.baseline_definition,
          targetMetrics: t.target_metrics,
          hypothesisCode: t.hypothesis_code,
          successCriteria: t.success_criteria,
          failureCriteria: t.failure_criteria,
          escalationRules: t.recommended_actions,
          midTestCheckpoint: t.mid_test_checkpoint,
          outcome: t.verdict,
          startDate: t.start_ts,
          endDate: t.end_ts,
        })),

      // Economic events from IoS-016 (Section 2)
      economicEvents: economicEventsResult.rows.map((e: any) => ({
        id: e.event_id,
        name: e.event_name,
        typeCode: e.event_type_code,
        timestamp: e.event_timestamp,
        consensus: e.consensus_estimate,
        previous: e.previous_value,
        actual: e.actual_value,
        surprise: e.surprise_score,
        impactRank: e.impact_rank,
        category: e.economic_category,
        status: e.status,
      })),

      // CEO Alerts
      alerts: alertsResult.rows.map((a: any) => ({
        id: a.alert_id,
        type: a.alert_type,
        title: a.alert_title,
        summary: a.alert_summary,
        options: a.decision_options,
        priority: a.priority,
        status: a.status,
        date: a.calendar_date,
        createdAt: a.created_at,
      })),

      // Observation windows with rich details (Section 8)
      observationWindows: observationResult.rows.map((w: any) => ({
        name: w.window_name,
        type: w.window_type,
        startDate: w.start_date,
        endDate: w.end_date,
        requiredDays: w.required_market_days,
        currentDays: w.current_market_days,
        status: w.status,
        criteriaMet: w.criteria_met,
        volumeScaling: w.volume_scaling_active,
        driftAlerts: w.metric_drift_alerts,
        // Rich details (Section 8 required)
        expectedImprovement: w.expected_improvement,
        improvementMetrics: w.improvement_metrics,
        startingConsensusState: w.starting_consensus_state,
      })),

      // LVG Status (Section 5.5) + Cumulative Totals (CEO-DIR-2026-DAY25)
      lvgStatus: {
        hypothesesBornToday: lvg.hypotheses_born_today || 0,
        hypothesesKilledToday: lvg.hypotheses_killed_today || 0,
        entropyScore: lvg.entropy_score,
        thrashingIndex: lvg.thrashing_index,
        governorAction: lvg.governor_action || 'NORMAL',
        velocityBrakeActive: lvg.velocity_brake_active || false,
        // Cumulative totals (CEO-DIR-2026-DAY25)
        totalHypotheses: parseInt(cumulative.total_hypotheses) || 0,
        totalFalsified: parseInt(cumulative.total_falsified) || 0,
        totalActive: parseInt(cumulative.total_active) || 0,
        deathRatePct: parseFloat(cumulative.death_rate_pct) || 0,
        lastHypothesisTime: cumulative.last_hypothesis_time || null,
      },

      // Shadow Tier Status (Section 6.3)
      shadowTier: {
        totalSamples: shadowTier.total_samples || 0,
        survivedCount: shadowTier.survived_count || 0,
        survivalRate: shadowTier.shadow_survival_rate || 0,
        calibrationStatus: shadowTier.calibration_status || 'NORMAL',
      },

      // Governance checks (Section 9)
      governanceChecks: governanceResult.rows.map((g: any) => ({
        name: g.check_name,
        status: g.check_status,
        discrepancy: g.discrepancy,
      })),

      // CEO-DIR-2026-DAY25: Learning Visibility (time-series for graphs)
      learningMetrics: learningMetricsResult.rows.map((m: any) => ({
        date: m.metric_date,
        hypothesesTotal: parseInt(m.hypotheses_total) || 0,
        hypothesesFalsified: parseInt(m.hypotheses_falsified) || 0,
        deathRatePct: parseFloat(m.death_rate_pct) || 0,
        fromErrors: parseInt(m.from_errors) || 0,
        avgCausalDepth: parseFloat(m.avg_causal_depth) || 0,
        genFinnE: parseInt(m.gen_finn_e) || 0,
        genFinnT: parseInt(m.gen_finn_t) || 0,
        genGnS: parseInt(m.gen_gn_s) || 0,
        genOther: parseInt(m.gen_other) || 0,
      })),

      // CEO-DIR-2026-DAY25: Learning Summary with status sentence
      learningSummary: (() => {
        const s = learningSummaryResult.rows[0] || {}
        const deathRate = parseFloat(s.death_rate_pct) || 0
        let statusSentence = ''
        if (deathRate >= 60 && deathRate <= 90) {
          statusSentence = 'ON TRACK: Death rate within target band (60-90%).'
        } else if (deathRate > 90) {
          statusSentence = 'BEHIND: Death rate too high - hypotheses dying too fast, need more robust generation.'
        } else {
          statusSentence = 'BEHIND: Death rate too low - Tier-1 not brutal enough, tighten falsification criteria.'
        }
        return {
          totalHypotheses: parseInt(s.total_hypotheses) || 0,
          totalFalsified: parseInt(s.total_falsified) || 0,
          totalActive: parseInt(s.total_active) || 0,
          deathRatePct: deathRate,
          deathRateStatus: s.death_rate_status || 'UNKNOWN',
          avgCausalDepth: parseFloat(s.avg_causal_depth) || 0,
          finnECount: parseInt(s.finn_e_count) || 0,
          finnTCount: parseInt(s.finn_t_count) || 0,
          gnSCount: parseInt(s.gn_s_count) || 0,
          lastHypothesisTime: s.last_hypothesis_time,
          todayCount: parseInt(s.today_count) || 0,
          statusSentence,
        }
      })(),

      // CEO-DIR-2026-DAY25: Generator Performance
      generatorPerformance: generatorPerfResult.rows.map((g: any) => ({
        name: g.generator_name,
        totalGenerated: parseInt(g.total_generated) || 0,
        falsified: parseInt(g.falsified) || 0,
        surviving: parseInt(g.surviving) || 0,
        deathRatePct: parseFloat(g.death_rate_pct) || 0,
        avgDepth: parseFloat(g.avg_depth) || 0,
      })),

      // Current date
      currentDate: {
        today: dateInfo.today,
        year: parseInt(dateInfo.year),
        month: parseInt(dateInfo.month),
        monthName: dateInfo.month_name?.trim(),
      },

      // Metadata
      lastUpdated: new Date().toISOString(),
      source: 'database',
    })
  } catch (error) {
    console.error('Calendar API error:', error)
    return NextResponse.json(
      {
        error: 'Failed to fetch calendar data',
        details: error instanceof Error ? error.message : 'Unknown error',
        source: 'error',
      },
      { status: 500 }
    )
  } finally {
    if (client) client.release()
  }
}
