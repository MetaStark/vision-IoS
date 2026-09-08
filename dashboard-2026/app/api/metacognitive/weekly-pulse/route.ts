/**
 * Metacognitive Observability - Weekly Learning Pulse API
 *
 * Authority: CEO Directive Metacognitive Observability & Audit-Hardening
 * Classification: CONSTITUTIONAL - Glass Wall Observability
 *
 * Provides:
 * - Weekly regret/wisdom metrics
 * - Attribution breakdown (TYPE_A, TYPE_B, TYPE_C, TYPE_X)
 * - Learning health indicators
 * - Trailing 12-week trends
 */

import { NextResponse } from 'next/server'
import { queryMany, queryOne } from '@/lib/db'

export const revalidate = 30 // 30-second polling (less frequent for weekly data)

interface WeeklyMetrics {
  iso_year: number
  iso_week: number
  week_label: string
  total_suppressions: number
  regret_count: number
  wisdom_count: number
  unresolved_count: number
  regret_rate: number
  wisdom_rate: number
  type_a_count: number
  type_b_count: number
  type_c_count: number
  type_x_count: number
  avg_regret_magnitude: number
  regret_magnitude_stddev: number
  low_magnitude_count: number
  medium_magnitude_count: number
  high_magnitude_count: number
  extreme_magnitude_count: number
}

export async function GET() {
  try {
    // Get weekly learning metrics (trailing 12 weeks)
    const weeklyMetrics = await queryMany<WeeklyMetrics>(`
      SELECT
        iso_year::int,
        iso_week::int,
        week_label,
        total_suppressions::int,
        regret_count::int,
        wisdom_count::int,
        unresolved_count::int,
        COALESCE(regret_rate, 0)::float as regret_rate,
        COALESCE(wisdom_rate, 0)::float as wisdom_rate,
        COALESCE(type_a_count, 0)::int as type_a_count,
        COALESCE(type_b_count, 0)::int as type_b_count,
        COALESCE(type_c_count, 0)::int as type_c_count,
        COALESCE(type_x_count, 0)::int as type_x_count,
        COALESCE(avg_regret_magnitude, 0)::float as avg_regret_magnitude,
        COALESCE(regret_magnitude_stddev, 0)::float as regret_magnitude_stddev,
        COALESCE(low_magnitude_count, 0)::int as low_magnitude_count,
        COALESCE(medium_magnitude_count, 0)::int as medium_magnitude_count,
        COALESCE(high_magnitude_count, 0)::int as high_magnitude_count,
        COALESCE(extreme_magnitude_count, 0)::int as extreme_magnitude_count
      FROM fhq_governance.weekly_learning_metrics
      ORDER BY iso_year DESC, iso_week DESC
      LIMIT 12
    `)

    // Get current week summary
    const currentWeek = weeklyMetrics.length > 0 ? weeklyMetrics[0] : null

    // Compute attribution breakdown for current week
    const attributionBreakdown = currentWeek ? {
      type_a_hysteresis: {
        count: currentWeek.type_a_count,
        pct: currentWeek.total_suppressions > 0
          ? parseFloat(((currentWeek.type_a_count / currentWeek.total_suppressions) * 100).toFixed(1))
          : 0,
        label: 'Hysteresis Lag'
      },
      type_b_confidence: {
        count: currentWeek.type_b_count,
        pct: currentWeek.total_suppressions > 0
          ? parseFloat(((currentWeek.type_b_count / currentWeek.total_suppressions) * 100).toFixed(1))
          : 0,
        label: 'Confidence Floor'
      },
      type_c_data: {
        count: currentWeek.type_c_count,
        pct: currentWeek.total_suppressions > 0
          ? parseFloat(((currentWeek.type_c_count / currentWeek.total_suppressions) * 100).toFixed(1))
          : 0,
        label: 'Data Blindness'
      },
      type_x_unknown: {
        count: currentWeek.type_x_count,
        pct: currentWeek.total_suppressions > 0
          ? parseFloat(((currentWeek.type_x_count / currentWeek.total_suppressions) * 100).toFixed(1))
          : 0,
        label: 'Unknown'
      }
    } : null

    // Compute learning health indicator
    let learningHealth: 'EXCELLENT' | 'GOOD' | 'WARNING' | 'CRITICAL' | 'NO_DATA' = 'NO_DATA'
    if (currentWeek) {
      const regretRate = currentWeek.regret_rate || 0
      const wisdomRate = currentWeek.wisdom_rate || 0
      const hasExtremeRegrets = currentWeek.extreme_magnitude_count > 0

      if (hasExtremeRegrets || regretRate > 0.3) {
        learningHealth = 'CRITICAL'
      } else if (regretRate > 0.2 || currentWeek.high_magnitude_count > 5) {
        learningHealth = 'WARNING'
      } else if (wisdomRate > 0.6 && regretRate < 0.15) {
        learningHealth = 'EXCELLENT'
      } else {
        learningHealth = 'GOOD'
      }
    }

    // Compute trend (is regret rate improving?)
    let trend: 'IMPROVING' | 'STABLE' | 'DEGRADING' | 'INSUFFICIENT_DATA' = 'INSUFFICIENT_DATA'
    if (weeklyMetrics.length >= 4) {
      const recent = weeklyMetrics.slice(0, 2).reduce((sum, w) => sum + (w.regret_rate || 0), 0) / 2
      const older = weeklyMetrics.slice(2, 4).reduce((sum, w) => sum + (w.regret_rate || 0), 0) / 2

      if (recent < older * 0.8) {
        trend = 'IMPROVING'
      } else if (recent > older * 1.2) {
        trend = 'DEGRADING'
      } else {
        trend = 'STABLE'
      }
    }

    return NextResponse.json({
      current_week: currentWeek ? {
        week_label: currentWeek.week_label,
        total_suppressions: currentWeek.total_suppressions,
        regret_pct: parseFloat(((currentWeek.regret_rate || 0) * 100).toFixed(1)),
        wisdom_pct: parseFloat(((currentWeek.wisdom_rate || 0) * 100).toFixed(1)),
        unresolved_pct: currentWeek.total_suppressions > 0
          ? parseFloat(((currentWeek.unresolved_count / currentWeek.total_suppressions) * 100).toFixed(1))
          : 0
      } : null,
      attribution_breakdown: attributionBreakdown,
      learning_health: learningHealth,
      trend: trend,
      weekly_history: weeklyMetrics.map(w => ({
        week_label: w.week_label,
        regret_rate: parseFloat(((w.regret_rate || 0) * 100).toFixed(1)),
        wisdom_rate: parseFloat(((w.wisdom_rate || 0) * 100).toFixed(1)),
        total: w.total_suppressions
      })),
      magnitude_breakdown: currentWeek ? {
        low: currentWeek.low_magnitude_count,
        medium: currentWeek.medium_magnitude_count,
        high: currentWeek.high_magnitude_count,
        extreme: currentWeek.extreme_magnitude_count
      } : null,
      _meta: {
        source_view: 'fhq_governance.weekly_learning_metrics',
        authority: 'CEO Directive Metacognitive Observability',
        weeks_analyzed: weeklyMetrics.length,
        fetched_at: new Date().toISOString()
      }
    })
  } catch (error) {
    console.error('[METACOGNITIVE/WEEKLY-PULSE] Error:', error)
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'Unknown error',
        current_week: null,
        learning_health: 'ERROR'
      },
      { status: 500 }
    )
  }
}
