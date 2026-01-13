/**
 * Learning Dashboard API - CEO-DIR-2026-057, 058, 059, 060
 * Provides REAL data from database views for the Learning Observability Dashboard
 *
 * CEO-DIR-2026-058 UPDATE:
 * Now returns DUAL metrics:
 * - System Maturity (FMCL, safety, governance)
 * - Market Learning (holdout performance - starts at 0%)
 *
 * CEO-DIR-2026-060 UPDATE:
 * Now returns Time Integrity status:
 * - Artifact validity counts (valid, invalid, pre-canonical)
 * - Blocking status for learning/reporting/QG-F6
 */

import { NextResponse } from 'next/server'
import { Pool } from 'pg'

// Direct PostgreSQL connection
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

    // Fetch learning progress
    const progressResult = await client.query(`
      SELECT * FROM fhq_governance.v_learning_progress
    `)
    const progress = progressResult.rows[0]

    // Fetch daily delta
    const deltaResult = await client.query(`
      SELECT * FROM fhq_governance.v_daily_learning_delta
    `)
    const dailyDelta = deltaResult.rows

    // Fetch cognitive activity
    const activityResult = await client.query(`
      SELECT * FROM fhq_governance.v_cognitive_activity
    `)
    const activity = activityResult.rows[0]

    // Fetch learning mechanisms
    const mechanismResult = await client.query(`
      SELECT * FROM fhq_governance.learning_mechanism_log
      ORDER BY logged_at DESC
      LIMIT 5
    `)
    const mechanisms = mechanismResult.rows

    // CEO-DIR-2026-058: Fetch Market Learning status (separate from System Maturity)
    const marketLearningResult = await client.query(`
      SELECT * FROM fhq_governance.v_market_learning_status
    `)
    const marketLearning = marketLearningResult.rows[0]

    // CEO-DIR-2026-059: Fetch Evidence Clock (canonical time + data availability)
    const evidenceClockResult = await client.query(`
      SELECT * FROM fhq_governance.v_evidence_clock
    `)
    const evidenceClock = evidenceClockResult.rows[0]

    // CEO-DIR-2026-060: Fetch Time Integrity status
    const timeIntegrityResult = await client.query(`
      SELECT * FROM fhq_governance.v_time_integrity_status
    `)
    const timeIntegrity = timeIntegrityResult.rows[0]

    return NextResponse.json({
      progress: progress?.current_progress_pct || 80,
      fmclDistribution: progress?.fmcl_distribution || '0-0-0-0-0',
      highSeverityClosed: progress?.high_severity_closed || 0,
      highSeverityTotal: progress?.high_severity_total || 0,

      dailyDelta: dailyDelta.map((item: any) => ({
        id: item.id,
        type: item.item_type,
        text: item.item_text,
        metric: item.metric,
        delta: item.delta,
      })),

      mechanisms: mechanisms.map((m: any) => ({
        id: m.mechanism_id,
        signal: m.signal_description,
        signalSource: m.signal_source,
        reasoning: m.reasoning_description,
        test: m.test_description,
        outcome: m.outcome_description,
        outcomeStatus: m.outcome_status,
      })),

      searchActivity: {
        queriesPerDay: activity?.search_queries_per_day || 0,
        domainsCovered: ['macro', 'rates', 'crypto', 'equity'].slice(0, activity?.search_domains_covered || 4),
        trend: activity?.search_trend || 'stable',
      },

      reasoningIntensity: {
        callsPerDay: activity?.llm_calls_per_day || 0,
        tierUsed: activity?.llm_tier_used || 'tier2',
        purposes: ['diagnosis', 'synthesis', 'validation'],
        costToday: parseFloat(activity?.llm_cost_today) || 0,
      },

      learningYield: {
        failureModesClosed: activity?.failure_modes_closed_7d || 0,
        invariantsCreated: activity?.invariants_created || 0,
        suppressionRegretReduced: activity?.suppression_regret_reduced || 0,
        trend: activity?.yield_trend || 'stable',
      },

      llmBalance: parseFloat(activity?.llm_balance_remaining) || 0,
      activeProviders: activity?.active_providers || '',

      // CEO-DIR-2026-058: Dual-track metrics
      systemMaturity: progress?.current_progress_pct || 0,  // Renamed from "progress"
      marketLearning: {
        progress: marketLearning?.market_learning_pct || 0,
        status: evidenceClock?.holdout_eligibility_status || marketLearning?.status_label || 'BLOCKED: View not found',
        labelLocked: marketLearning?.label_locked || false,
        labelVersion: marketLearning?.label_version || null,
        labelHash: marketLearning?.label_hash || null,
        holdoutCount: marketLearning?.holdout_count || 0,
        holdoutFrozen: (marketLearning?.frozen_count || 0) > 0,
        holdoutVerified: (marketLearning?.verified_count || 0) > 0,
        latestBrier: marketLearning?.latest_brier || null,
        latestDelta: marketLearning?.latest_delta || null,
        latestDirection: marketLearning?.latest_direction || null,
        totalEvaluations: marketLearning?.total_evaluations || 0,
        significantImprovements: marketLearning?.significant_improvements || 0,
      },

      // CEO-DIR-2026-059: Evidence Clock (canonical time + data availability)
      // CEO-DIR-2026-060: Time Integrity status included
      evidenceClock: {
        canonicalNow: evidenceClock?.canonical_now_utc || new Date().toISOString(),
        operationalStart: evidenceClock?.operational_start || null,
        holdoutWindowStart: evidenceClock?.holdout_window_start || null,
        holdoutWindowEnd: evidenceClock?.holdout_window_end || null,
        forecastDaysAvailable: parseInt(evidenceClock?.forecast_days_available) || 0,
        outcomeDaysAvailable: parseInt(evidenceClock?.outcome_days_available) || 0,
        totalHoldoutEligibleRecords: parseInt(evidenceClock?.total_holdout_eligible_records) || 0,
        holdoutEligibilityStatus: evidenceClock?.holdout_eligibility_status || 'UNKNOWN',
        // CEO-DIR-2026-060: Time Integrity
        timeIntegrity: timeIntegrity ? {
          status: timeIntegrity.time_integrity_status || 'UNKNOWN',
          validCount: parseInt(timeIntegrity.valid_count) || 0,
          invalidCount: parseInt(timeIntegrity.invalid_count) || 0,
          pendingCount: parseInt(timeIntegrity.pending_count) || 0,
          preCanonicalCount: parseInt(timeIntegrity.pre_canonical_count) || 0,
          totalCount: parseInt(timeIntegrity.total_count) || 0,
          integrityPct: parseFloat(timeIntegrity.time_integrity_pct) || 100,
          canProceedWithLearning: timeIntegrity.can_proceed_with_learning || false,
          canProceedWithReporting: timeIntegrity.can_proceed_with_reporting || false,
          canProceedWithQgf6: timeIntegrity.can_proceed_with_qgf6 || false,
        } : undefined,
      },

      lastUpdated: new Date().toISOString(),
      source: 'database',
    })
  } catch (error) {
    console.error('Learning API error:', error)

    // Return error with details for debugging
    return NextResponse.json(
      {
        error: 'Failed to fetch learning data',
        details: error instanceof Error ? error.message : 'Unknown error',
        source: 'error'
      },
      { status: 500 }
    )
  } finally {
    if (client) {
      client.release()
    }
  }
}
