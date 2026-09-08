/**
 * Metacognitive Observability - Board-Grade Metrics API
 *
 * Authority: CEO-DIR-2026-036
 * Classification: CONSTITUTIONAL - Board Dashboard
 *
 * Provides:
 * - Calibration Index (1 - avg overconfidence gap)
 * - Restraint Index (Wisdom Rate)
 * - Learning Velocity (delta Brier / week)
 * - Attribution Coverage (1 - X rate)
 * - Regret Exposure (Regret × Magnitude)
 * - Phase Milestones
 * - 12-week trajectory with targets
 */

import { NextResponse } from 'next/server'
import { queryMany, queryOne } from '@/lib/db'

export const revalidate = 30

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
  low_magnitude_count: number
  medium_magnitude_count: number
  high_magnitude_count: number
  extreme_magnitude_count: number
}

interface CalibrationMetrics {
  confidence_band: string
  sample_count: number
  avg_confidence: number
  actual_accuracy: number
  brier_score: number
}

interface PhaseGoal {
  day_number: number
  calendar_date: string
  goal_title: string
  status: string
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
        COALESCE(low_magnitude_count, 0)::int as low_magnitude_count,
        COALESCE(medium_magnitude_count, 0)::int as medium_magnitude_count,
        COALESCE(high_magnitude_count, 0)::int as high_magnitude_count,
        COALESCE(extreme_magnitude_count, 0)::int as extreme_magnitude_count
      FROM fhq_governance.weekly_learning_metrics
      ORDER BY iso_year DESC, iso_week DESC
      LIMIT 12
    `)

    // Get calibration metrics by confidence band
    const calibrationMetrics = await queryMany<CalibrationMetrics>(`
      WITH confidence_bins AS (
        SELECT
          CASE
            WHEN fl.forecast_confidence < 0.5 THEN 'LOW'
            WHEN fl.forecast_confidence < 0.7 THEN 'MED'
            ELSE 'HIGH'
          END as confidence_band,
          fl.forecast_confidence,
          fop.hit_rate_contribution::int as correct,
          fop.brier_score
        FROM fhq_research.forecast_outcome_pairs fop
        JOIN fhq_research.forecast_ledger fl ON fl.forecast_id = fop.forecast_id
        WHERE fop.reconciled_at >= NOW() - INTERVAL '30 days'
      )
      SELECT
        confidence_band,
        COUNT(*)::int as sample_count,
        AVG(forecast_confidence)::float as avg_confidence,
        AVG(correct)::float as actual_accuracy,
        AVG(brier_score)::float as brier_score
      FROM confidence_bins
      GROUP BY confidence_band
      ORDER BY avg_confidence
    `)

    // Get Brier trend for learning velocity
    const brierTrend = await queryMany<{ week_label: string; avg_brier: number }>(`
      SELECT
        TO_CHAR(DATE_TRUNC('week', fop.reconciled_at), 'IYYY-"W"IW') as week_label,
        AVG(fop.brier_score)::float as avg_brier
      FROM fhq_research.forecast_outcome_pairs fop
      WHERE fop.reconciled_at >= NOW() - INTERVAL '8 weeks'
      GROUP BY DATE_TRUNC('week', fop.reconciled_at)
      ORDER BY DATE_TRUNC('week', fop.reconciled_at) DESC
      LIMIT 4
    `)

    // Get phase milestones from daily goal calendar
    const phaseGoals = await queryMany<PhaseGoal>(`
      SELECT
        day_number,
        calendar_date::text,
        goal_title,
        COALESCE(status, 'PENDING') as status
      FROM fhq_governance.daily_goal_calendar
      WHERE calendar_date >= CURRENT_DATE - INTERVAL '3 days'
      AND calendar_date <= CURRENT_DATE + INTERVAL '7 days'
      ORDER BY calendar_date
      LIMIT 10
    `)

    const currentWeek = weeklyMetrics.length > 0 ? weeklyMetrics[0] : null

    // Calculate Calibration Index (1 - avg overconfidence gap)
    let calibrationIndex = 0.5
    if (calibrationMetrics.length > 0) {
      const totalSamples = calibrationMetrics.reduce((sum, m) => sum + m.sample_count, 0)
      const weightedGap = calibrationMetrics.reduce((sum, m) => {
        const gap = Math.abs(m.avg_confidence - m.actual_accuracy)
        return sum + (gap * m.sample_count)
      }, 0)
      calibrationIndex = Math.max(0, 1 - (weightedGap / totalSamples))
    }

    // Calculate Restraint Index (Wisdom Rate)
    const restraintIndex = currentWeek ? (currentWeek.wisdom_rate || 0) : 0

    // Calculate Learning Velocity (delta Brier per week)
    let learningVelocity = 0
    let learningVelocityPct = 0
    if (brierTrend.length >= 2) {
      const recent = brierTrend[0].avg_brier
      const older = brierTrend[brierTrend.length - 1].avg_brier
      learningVelocity = (older - recent) / brierTrend.length
      learningVelocityPct = older > 0 ? ((older - recent) / older) * 100 : 0
    }

    // Calculate Attribution Coverage (1 - X rate)
    let attributionCoverage = 0
    if (currentWeek && currentWeek.total_suppressions > 0) {
      const xRate = currentWeek.type_x_count / currentWeek.total_suppressions
      attributionCoverage = 1 - xRate
    }

    // Calculate Regret Exposure (weighted by magnitude)
    let regretExposure = 0
    if (currentWeek && currentWeek.total_suppressions > 0) {
      const weightedRegret = (
        currentWeek.low_magnitude_count * 0.1 +
        currentWeek.medium_magnitude_count * 0.3 +
        currentWeek.high_magnitude_count * 0.6 +
        currentWeek.extreme_magnitude_count * 1.0
      )
      regretExposure = weightedRegret / currentWeek.total_suppressions
    }

    // Compute trend direction
    let trend: 'IMPROVING' | 'STABLE' | 'DEGRADING' | 'INSUFFICIENT_DATA' = 'INSUFFICIENT_DATA'
    if (weeklyMetrics.length >= 4) {
      const recent = weeklyMetrics.slice(0, 2).reduce((sum, w) => sum + (w.regret_rate || 0), 0) / 2
      const older = weeklyMetrics.slice(2, 4).reduce((sum, w) => sum + (w.regret_rate || 0), 0) / 2
      if (recent < older * 0.8) trend = 'IMPROVING'
      else if (recent > older * 1.2) trend = 'DEGRADING'
      else trend = 'STABLE'
    }

    // Compute overall status
    let overallStatus: 'ON_TRACK' | 'AT_RISK' | 'BLOCKED' | 'UNKNOWN' = 'UNKNOWN'
    if (currentWeek) {
      if (restraintIndex >= 0.6 && calibrationIndex >= 0.7 && currentWeek.regret_rate < 0.25) {
        overallStatus = 'ON_TRACK'
      } else if (currentWeek.regret_rate > 0.35 || currentWeek.extreme_magnitude_count > 0) {
        overallStatus = 'BLOCKED'
      } else {
        overallStatus = 'AT_RISK'
      }
    }

    // Categorize attribution
    const attributionCategories = currentWeek ? {
      by_design: {
        count: currentWeek.type_a_count + currentWeek.type_b_count,
        pct: currentWeek.total_suppressions > 0
          ? ((currentWeek.type_a_count + currentWeek.type_b_count) / currentWeek.total_suppressions) * 100
          : 0,
        label: 'By Design',
        description: 'Expected suppressions from confidence ceiling and hysteresis gates',
        types: ['A - Hysteresis', 'B - Confidence']
      },
      challenging: {
        count: currentWeek.type_c_count,
        pct: currentWeek.total_suppressions > 0
          ? (currentWeek.type_c_count / currentWeek.total_suppressions) * 100
          : 0,
        label: 'Challenging',
        description: 'Known difficulty: data gaps, regime transitions',
        types: ['C - Data Blindness']
      },
      surprising: {
        count: currentWeek.type_x_count,
        pct: currentWeek.total_suppressions > 0
          ? (currentWeek.type_x_count / currentWeek.total_suppressions) * 100
          : 0,
        label: 'Surprising',
        description: 'Unknown attribution - needs investigation',
        types: ['X - Unknown'],
        alert: currentWeek.type_x_count > currentWeek.total_suppressions * 0.3
      }
    } : null

    // Build 12-week trajectory with targets
    const trajectory = weeklyMetrics.map((w, idx) => ({
      week: w.week_label,
      regret: parseFloat(((w.regret_rate || 0) * 100).toFixed(1)),
      wisdom: parseFloat(((w.wisdom_rate || 0) * 100).toFixed(1)),
      suppressions: w.total_suppressions,
      regretTarget: 15, // CEO target: <15%
      wisdomTarget: 80, // CEO target: >80%
      isCurrent: idx === 0
    }))

    // Get current phase info
    const currentDay = phaseGoals.find(g => g.status === 'IN_PROGRESS') || phaseGoals[0]
    const completedDays = phaseGoals.filter(g => g.status === 'COMPLETED').length
    const totalDays = phaseGoals.length

    return NextResponse.json({
      executive_summary: {
        status: overallStatus,
        trend: trend,
        phase: 'M1_BOOTSEQ',
        current_day: currentDay?.day_number || 4,
        headline: overallStatus === 'ON_TRACK'
          ? 'System learning correctly - blocking bad forecasts, minimal regret'
          : overallStatus === 'AT_RISK'
          ? 'Learning in progress - monitoring attribution gaps'
          : 'Blocked - requires attention',
        insight: `Wisdom ${(restraintIndex * 100).toFixed(0)}% | Regret ${((currentWeek?.regret_rate || 0) * 100).toFixed(0)}% | Attribution coverage ${(attributionCoverage * 100).toFixed(0)}%`
      },
      kpis: {
        calibration_index: {
          value: parseFloat(calibrationIndex.toFixed(2)),
          target: 0.85,
          delta: parseFloat((calibrationIndex - 0.85).toFixed(3)),
          status: calibrationIndex >= 0.85 ? 'MET' : calibrationIndex >= 0.7 ? 'ON_TRACK' : 'AT_RISK',
          description: 'Confidence matches accuracy'
        },
        restraint_index: {
          value: parseFloat(restraintIndex.toFixed(2)),
          target: 0.80,
          delta: parseFloat((restraintIndex - 0.80).toFixed(3)),
          status: restraintIndex >= 0.80 ? 'MET' : restraintIndex >= 0.6 ? 'ON_TRACK' : 'AT_RISK',
          description: 'Blocking bad forecasts'
        },
        learning_velocity: {
          value: parseFloat(learningVelocity.toFixed(4)),
          value_pct: parseFloat(learningVelocityPct.toFixed(1)),
          target: 0, // Negative = improving
          status: learningVelocity > 0 ? 'IMPROVING' : learningVelocity < -0.02 ? 'DEGRADING' : 'STABLE',
          description: 'Brier improvement per week'
        },
        attribution_coverage: {
          value: parseFloat(attributionCoverage.toFixed(2)),
          target: 0.90,
          delta: parseFloat((attributionCoverage - 0.90).toFixed(3)),
          status: attributionCoverage >= 0.90 ? 'MET' : attributionCoverage >= 0.7 ? 'ON_TRACK' : 'AT_RISK',
          description: 'Understand why forecasts blocked'
        },
        regret_exposure: {
          value: parseFloat(regretExposure.toFixed(3)),
          target: 0.05,
          status: regretExposure <= 0.05 ? 'MET' : regretExposure <= 0.10 ? 'ON_TRACK' : 'AT_RISK',
          description: 'Impact of missed opportunities'
        }
      },
      trajectory: trajectory.reverse(), // Oldest first for chart
      attribution_categories: attributionCategories,
      calibration_bands: calibrationMetrics.map(m => ({
        band: m.confidence_band,
        samples: m.sample_count,
        confidence: parseFloat((m.avg_confidence * 100).toFixed(1)),
        accuracy: parseFloat((m.actual_accuracy * 100).toFixed(1)),
        brier: parseFloat(m.brier_score.toFixed(4)),
        gap: parseFloat(((m.avg_confidence - m.actual_accuracy) * 100).toFixed(1)),
        status: m.avg_confidence > m.actual_accuracy + 0.1 ? 'OVERCONFIDENT' :
                m.avg_confidence < m.actual_accuracy - 0.05 ? 'UNDERCONFIDENT' : 'CALIBRATED'
      })),
      phase_milestones: phaseGoals.map(g => ({
        day: g.day_number,
        date: g.calendar_date,
        objective: g.goal_title,
        status: g.status,
        isCurrent: g.status === 'IN_PROGRESS'
      })),
      phase_progress: {
        completed: completedDays,
        total: totalDays,
        pct: totalDays > 0 ? Math.round((completedDays / totalDays) * 100) : 0
      },
      current_week: currentWeek ? {
        label: currentWeek.week_label,
        suppressions: currentWeek.total_suppressions,
        regret_pct: parseFloat(((currentWeek.regret_rate || 0) * 100).toFixed(1)),
        wisdom_pct: parseFloat(((currentWeek.wisdom_rate || 0) * 100).toFixed(1)),
        unresolved_pct: currentWeek.total_suppressions > 0
          ? parseFloat(((currentWeek.unresolved_count / currentWeek.total_suppressions) * 100).toFixed(1))
          : 0
      } : null,
      magnitude_distribution: currentWeek ? {
        low: currentWeek.low_magnitude_count,
        medium: currentWeek.medium_magnitude_count,
        high: currentWeek.high_magnitude_count,
        extreme: currentWeek.extreme_magnitude_count
      } : null,
      _meta: {
        source: 'fhq_governance.weekly_learning_metrics + fhq_research.forecast_outcome_pairs',
        authority: 'CEO-DIR-2026-036',
        fetched_at: new Date().toISOString()
      }
    })
  } catch (error) {
    console.error('[METACOGNITIVE/BOARD-METRICS] Error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    )
  }
}
