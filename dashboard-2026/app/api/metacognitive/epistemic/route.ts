/**
 * Metacognitive Observability - Epistemic Perspective API
 *
 * Authority: CEO Directive Metacognitive Observability & Audit-Hardening
 * Classification: CONSTITUTIONAL - Glass Wall Observability
 *
 * Provides:
 * - Parametric vs External boundary metrics
 * - Boundary confidence tracking
 * - Belief-policy divergence metrics
 * - Suppression ledger insights
 */

import { NextResponse } from 'next/server'
import { queryOne, queryMany } from '@/lib/db'

export const revalidate = 10 // 10-second polling

interface SuppressionSummary {
  suppression_category: string
  count: number
  avg_confidence_delta: number
  regret_rate: number
  wisdom_rate: number
}

interface BeliefPolicyDivergence {
  date: string
  total_beliefs: number
  suppressed_count: number
  divergence_rate: number
}

export async function GET() {
  try {
    // Get suppression breakdown by category
    const suppressionByCategory = await queryMany<SuppressionSummary>(`
      SELECT
        suppression_category,
        COUNT(*)::int as count,
        AVG(ABS(suppressed_confidence - chosen_confidence))::float as avg_confidence_delta,
        ROUND(
          COUNT(*) FILTER (WHERE regret_classification = 'REGRET')::numeric /
          NULLIF(COUNT(*), 0)::numeric,
          4
        )::float as regret_rate,
        ROUND(
          COUNT(*) FILTER (WHERE regret_classification = 'WISDOM')::numeric /
          NULLIF(COUNT(*), 0)::numeric,
          4
        )::float as wisdom_rate
      FROM fhq_governance.epistemic_suppression_ledger
      WHERE suppression_timestamp >= NOW() - INTERVAL '30 days'
      GROUP BY suppression_category
      ORDER BY count DESC
    `)

    // Get belief-policy divergence trend
    const divergenceTrend = await queryMany<BeliefPolicyDivergence>(`
      WITH daily_beliefs AS (
        SELECT
          DATE_TRUNC('day', created_at) as date,
          COUNT(*) as total_beliefs
        FROM fhq_perception.model_belief_state
        WHERE created_at >= NOW() - INTERVAL '14 days'
        GROUP BY DATE_TRUNC('day', created_at)
      ),
      daily_suppressions AS (
        SELECT
          DATE_TRUNC('day', suppression_timestamp) as date,
          COUNT(*) as suppressed_count
        FROM fhq_governance.epistemic_suppression_ledger
        WHERE suppression_timestamp >= NOW() - INTERVAL '14 days'
        GROUP BY DATE_TRUNC('day', suppression_timestamp)
      )
      SELECT
        db.date::text,
        db.total_beliefs::int,
        COALESCE(ds.suppressed_count, 0)::int as suppressed_count,
        ROUND(
          COALESCE(ds.suppressed_count, 0)::numeric /
          NULLIF(db.total_beliefs, 0)::numeric,
          4
        )::float as divergence_rate
      FROM daily_beliefs db
      LEFT JOIN daily_suppressions ds ON db.date = ds.date
      ORDER BY db.date DESC
    `)

    // Get boundary validation status (IKEA)
    const boundaryStatus = await queryOne<{
      total_validations: number
      passed_count: number
      failed_count: number
      pass_rate: number
    }>(`
      SELECT
        COUNT(*)::int as total_validations,
        COUNT(*) FILTER (WHERE passed = TRUE)::int as passed_count,
        COUNT(*) FILTER (WHERE passed = FALSE)::int as failed_count,
        ROUND(
          COUNT(*) FILTER (WHERE passed = TRUE)::numeric /
          NULLIF(COUNT(*), 0)::numeric * 100,
          2
        )::float as pass_rate
      FROM fhq_governance.ikea_validation_log
      WHERE created_at >= NOW() - INTERVAL '30 days'
    `)

    // Calculate Parametric/External ratio from lessons
    const lessonBreakdown = await queryMany<{
      lesson_category: string
      count: number
    }>(`
      SELECT
        lesson_category,
        COUNT(*)::int as count
      FROM fhq_governance.epistemic_lessons
      WHERE created_at >= NOW() - INTERVAL '30 days'
      GROUP BY lesson_category
      ORDER BY count DESC
    `)

    // Compute summary metrics
    const totalSuppressions = suppressionByCategory.reduce((sum, s) => sum + s.count, 0)
    const avgRegretRate = suppressionByCategory.length > 0
      ? suppressionByCategory.reduce((sum, s) => sum + (s.regret_rate || 0) * s.count, 0) / totalSuppressions
      : 0
    const avgWisdomRate = suppressionByCategory.length > 0
      ? suppressionByCategory.reduce((sum, s) => sum + (s.wisdom_rate || 0) * s.count, 0) / totalSuppressions
      : 0

    return NextResponse.json({
      perspective: 'EPISTEMIC',
      summary: {
        total_suppressions_30d: totalSuppressions,
        avg_regret_rate: parseFloat((avgRegretRate * 100).toFixed(2)),
        avg_wisdom_rate: parseFloat((avgWisdomRate * 100).toFixed(2)),
        boundary_pass_rate: boundaryStatus?.pass_rate || 100,
        boundary_violations: boundaryStatus?.failed_count || 0,
        computed_at: new Date().toISOString()
      },
      suppression_by_category: suppressionByCategory,
      divergence_trend: divergenceTrend,
      boundary_status: boundaryStatus || {
        total_validations: 0,
        passed_count: 0,
        failed_count: 0,
        pass_rate: 100
      },
      lesson_breakdown: lessonBreakdown,
      _meta: {
        source_tables: [
          'fhq_governance.epistemic_suppression_ledger',
          'fhq_perception.model_belief_state',
          'fhq_governance.ikea_validation_log',
          'fhq_governance.epistemic_lessons'
        ],
        authority: 'CEO Directive Metacognitive Observability',
        fetched_at: new Date().toISOString()
      }
    })
  } catch (error) {
    console.error('[METACOGNITIVE/EPISTEMIC] Error:', error)
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'Unknown error',
        perspective: 'EPISTEMIC'
      },
      { status: 500 }
    )
  }
}
