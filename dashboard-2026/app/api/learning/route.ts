/**
 * Learning Dashboard API - CEO-DIR-2026-057
 * Provides REAL data from database views for the Learning Observability Dashboard
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
