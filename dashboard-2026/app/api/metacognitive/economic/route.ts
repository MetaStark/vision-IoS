/**
 * Metacognitive Observability - Economic Perspective API
 *
 * Authority: CEO Directive Metacognitive Observability & Audit-Hardening
 * Classification: CONSTITUTIONAL - Glass Wall Observability
 *
 * Provides:
 * - Information Gain Ratio (IGR)
 * - EVPI Proxy (Expected Value of Perfect Information)
 * - Scent-to-Gain efficiency
 * - Calibration status (Brier scores when available)
 */

import { NextResponse } from 'next/server'
import { queryOne, queryMany } from '@/lib/db'

export const revalidate = 10 // 10-second polling

interface EconomicSummary {
  avg_information_gain_ratio: number
  total_query_cost_30d: number
  avg_evidence_coverage: number
  evpi_proxy_value: number
  regret_count_12w: number
  wisdom_count_12w: number
  avg_brier_score: number
  calibrated_forecasts: number
  calibration_status: string
  computed_at: string
}

interface EVPIData {
  week: string
  suppression_category: string
  suppression_count: number
  evpi_proxy: number
  avg_regret_magnitude: number
  regret_count: number
  wisdom_count: number
  opportunity_cost_indicator: string
}

interface IGRData {
  date: string
  querying_agent: string
  total_queries: number
  total_cost: number
  avg_evidence_coverage: number
  information_gain_ratio: number
}

export async function GET() {
  try {
    // Get economic summary
    const summary = await queryOne<EconomicSummary>(`
      SELECT * FROM fhq_governance.v_metacognitive_economic_summary
    `)

    // Get EVPI trend data
    const evpiTrend = await queryMany<EVPIData>(`
      SELECT
        week::text,
        suppression_category,
        suppression_count::int,
        evpi_proxy::float,
        avg_regret_magnitude::float,
        regret_count::int,
        wisdom_count::int,
        opportunity_cost_indicator
      FROM fhq_governance.mv_evpi_proxy
      ORDER BY week DESC
      LIMIT 12
    `)

    // Get IGR trend data
    const igrTrend = await queryMany<IGRData>(`
      SELECT
        date::text,
        querying_agent,
        total_queries::int,
        total_cost::float,
        avg_evidence_coverage::float,
        information_gain_ratio::float
      FROM fhq_governance.v_information_gain_ratio
      WHERE date >= NOW() - INTERVAL '30 days'
      ORDER BY date DESC
    `)

    // Compute deferred gain summary (regret vs wisdom ratio)
    const deferredGainRatio = summary
      ? (summary.wisdom_count_12w / Math.max(1, summary.regret_count_12w + summary.wisdom_count_12w)) * 100
      : 0

    return NextResponse.json({
      perspective: 'ECONOMIC',
      summary: summary || {
        avg_information_gain_ratio: 0,
        total_query_cost_30d: 0,
        avg_evidence_coverage: 0,
        evpi_proxy_value: 0,
        regret_count_12w: 0,
        wisdom_count_12w: 0,
        avg_brier_score: 0,
        calibrated_forecasts: 0,
        calibration_status: 'NO_DATA',
        computed_at: new Date().toISOString()
      },
      evpi_trend: evpiTrend,
      igr_trend: igrTrend,
      derived_metrics: {
        deferred_gain_ratio_pct: parseFloat(deferredGainRatio.toFixed(2)),
        // Wisdom = good suppression decisions, Regret = bad ones
        suppression_wisdom_indicator: deferredGainRatio > 70 ? 'HIGH' : deferredGainRatio > 50 ? 'MEDIUM' : 'LOW'
      },
      _meta: {
        source_views: [
          'fhq_governance.v_metacognitive_economic_summary',
          'fhq_governance.mv_evpi_proxy',
          'fhq_governance.v_information_gain_ratio'
        ],
        authority: 'CEO Directive Metacognitive Observability',
        note: summary?.calibration_status === 'AWAITING_FINN_DATA'
          ? 'Brier score calibration awaiting FINN population of brier_score_ledger'
          : undefined,
        fetched_at: new Date().toISOString()
      }
    })
  } catch (error) {
    console.error('[METACOGNITIVE/ECONOMIC] Error:', error)
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'Unknown error',
        perspective: 'ECONOMIC'
      },
      { status: 500 }
    )
  }
}
