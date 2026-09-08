/**
 * Metacognitive Observability - Cognitive Perspective API
 *
 * Authority: CEO Directive Metacognitive Observability & Audit-Hardening
 * Classification: CONSTITUTIONAL - Glass Wall Observability
 *
 * Provides:
 * - Chain-of-Query (CoQ) efficiency metrics
 * - Abort rate tracking
 * - CV (Coefficient of Variation) per regime
 * - Latency and cost metrics
 */

import { NextResponse } from 'next/server'
import { queryOne, queryMany } from '@/lib/db'

export const revalidate = 10 // 10-second polling

interface CognitiveSummary {
  coq_efficiency_score: number
  abort_rate_pct: number
  avg_latency_ms: number
  total_query_cost_7d: number
  cv_per_regime: Record<string, number>
  computed_at: string
}

interface DailyCoQMetrics {
  query_date: string
  querying_agent: string
  total_queries: number
  avg_latency_ms: number
  total_cost_usd: number
  aborted_queries: number
  abort_rate: number
  efficiency_score: number
}

export async function GET() {
  try {
    // Get cognitive summary
    const summary = await queryOne<CognitiveSummary>(`
      SELECT * FROM fhq_governance.v_metacognitive_cognitive_summary
    `)

    // Get daily trend data (last 7 days)
    const dailyTrend = await queryMany<DailyCoQMetrics>(`
      SELECT
        query_date::text,
        querying_agent,
        total_queries::int,
        avg_latency_ms::float,
        total_cost_usd::float,
        aborted_queries::int,
        abort_rate::float,
        efficiency_score::float
      FROM fhq_governance.v_chain_of_query_efficiency
      WHERE query_date >= NOW() - INTERVAL '7 days'
      ORDER BY query_date DESC
    `)

    // Get regime variance metrics
    const regimeVariance = await queryMany<{
      dominant_regime: string
      week: string
      belief_count: number
      confidence_cv: number
      entropy_cv: number
      stability_indicator: string
    }>(`
      SELECT
        dominant_regime,
        week::text,
        belief_count::int,
        confidence_cv::float,
        entropy_cv::float,
        stability_indicator
      FROM fhq_governance.v_regime_variance_metrics
      WHERE week >= NOW() - INTERVAL '4 weeks'
      ORDER BY week DESC, dominant_regime
    `)

    return NextResponse.json({
      perspective: 'COGNITIVE',
      summary: summary || {
        coq_efficiency_score: 0,
        abort_rate_pct: 0,
        avg_latency_ms: 0,
        total_query_cost_7d: 0,
        cv_per_regime: {},
        computed_at: new Date().toISOString()
      },
      daily_trend: dailyTrend,
      regime_variance: regimeVariance,
      _meta: {
        source_views: [
          'fhq_governance.v_metacognitive_cognitive_summary',
          'fhq_governance.v_chain_of_query_efficiency',
          'fhq_governance.v_regime_variance_metrics'
        ],
        authority: 'CEO Directive Metacognitive Observability',
        fetched_at: new Date().toISOString()
      }
    })
  } catch (error) {
    console.error('[METACOGNITIVE/COGNITIVE] Error:', error)
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'Unknown error',
        perspective: 'COGNITIVE'
      },
      { status: 500 }
    )
  }
}
