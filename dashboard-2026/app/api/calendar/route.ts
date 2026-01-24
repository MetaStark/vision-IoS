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

    // Fetch shadow tier status
    const shadowTierResult = await client.query(`
      SELECT * FROM fhq_calendar.v_shadow_tier_calendar_status
    `)

    // Fetch fail-closed governance checks
    const governanceResult = await client.query(`
      SELECT * FROM fhq_calendar.check_calendar_sync()
    `)

    // Fetch active tests summary
    const activeTestsResult = await client.query(`
      SELECT
        test_name,
        test_code,
        owning_agent,
        status,
        days_elapsed,
        days_remaining,
        current_sample_size,
        target_sample_size,
        sample_trajectory_status,
        calendar_category
      FROM fhq_calendar.canonical_test_events
      WHERE status IN ('ACTIVE', 'SCHEDULED')
      ORDER BY start_date ASC
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

    // Fetch observation windows
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
        metric_drift_alerts
      FROM fhq_learning.observation_window
      WHERE status = 'ACTIVE'
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
        year: e.year,
        month: e.month,
        day: e.day,
        dayName: e.day_name,
      })),

      // Active tests
      activeTests: activeTestsResult.rows.map((t: any) => ({
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

      // Observation windows
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
      })),

      // LVG Status (Section 5.5)
      lvgStatus: {
        hypothesesBornToday: lvg.hypotheses_born_today || 0,
        hypothesesKilledToday: lvg.hypotheses_killed_today || 0,
        entropyScore: lvg.entropy_score,
        thrashingIndex: lvg.thrashing_index,
        governorAction: lvg.governor_action || 'NORMAL',
        velocityBrakeActive: lvg.velocity_brake_active || false,
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
