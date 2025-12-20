/**
 * CCO Pipeline Status API Route
 * ==============================
 * WAVE 17C + 17C.1 - Autonomous Promotion Pipeline Status
 *
 * Returns:
 * - Pipeline state (SHADOW/RAMP_10/RAMP_50/ACTIVE/PAUSED/HALTED)
 * - Rate limiting status
 * - Shadow mode status
 * - Drift metrics
 * - SLA compliance
 * - Recent pipeline events
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
  try {
    // Pipeline status view
    const statusResult = await pool.query(`
      SELECT * FROM fhq_canonical.v_pipeline_status
    `)

    // Shadow decisions summary
    const shadowResult = await pool.query(`
      SELECT
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE would_pass_gate_a = TRUE) as would_pass,
        COUNT(*) FILTER (WHERE would_pass_gate_a = FALSE) as would_reject,
        COUNT(*) FILTER (WHERE reviewed = TRUE) as reviewed,
        AVG(total_ms) as avg_ms,
        MAX(total_ms) as max_ms
      FROM fhq_canonical.g5_shadow_decisions
    `)

    // Recent shadow decisions
    const recentShadowResult = await pool.query(`
      SELECT
        shadow_id,
        needle_id,
        would_pass_gate_a,
        would_be_signal_state,
        gate_a_result,
        evidence_gen_ms,
        gate_a_eval_ms,
        total_ms,
        reviewed,
        created_at
      FROM fhq_canonical.g5_shadow_decisions
      ORDER BY created_at DESC
      LIMIT 10
    `)

    // Drift metrics (latest)
    const driftResult = await pool.query(`
      SELECT
        rolling_7day_avg_eqs,
        rolling_7day_needle_count,
        rolling_7day_signal_count,
        rolling_7day_conversion_rate,
        eqs_threshold,
        conversion_threshold,
        eqs_below_threshold,
        conversion_below_threshold,
        any_drift_detected,
        computed_at
      FROM fhq_canonical.g5_drift_metrics
      ORDER BY computed_at DESC
      LIMIT 1
    `)

    // SLA metrics summary (last 24h)
    const slaResult = await pool.query(`
      SELECT
        COUNT(*) as total_promotions,
        COUNT(*) FILTER (WHERE evidence_gen_sla_breach = TRUE) as evidence_breaches,
        COUNT(*) FILTER (WHERE gate_a_sla_breach = TRUE) as gate_a_breaches,
        COUNT(*) FILTER (WHERE total_sla_breach = TRUE) as total_breaches,
        AVG(evidence_gen_ms) as avg_evidence_ms,
        AVG(gate_a_ms) as avg_gate_a_ms,
        AVG(total_ms) as avg_total_ms,
        MAX(total_ms) as max_total_ms
      FROM fhq_canonical.g5_sla_metrics
      WHERE created_at > NOW() - INTERVAL '24 hours'
    `)

    // Pass rate history (last 10)
    const passRateResult = await pool.query(`
      SELECT
        total_evaluated,
        total_passed,
        pass_rate,
        previous_pass_rate,
        pass_rate_delta,
        anomaly_detected,
        created_at
      FROM fhq_canonical.g5_pass_rate_history
      ORDER BY created_at DESC
      LIMIT 10
    `)

    // Recent pipeline events
    const eventsResult = await pool.query(`
      SELECT
        event_id,
        event_type,
        needle_id,
        event_data,
        severity,
        defcon_escalation,
        created_at
      FROM fhq_canonical.g5_pipeline_events
      ORDER BY created_at DESC
      LIMIT 20
    `)

    // Rate limit status
    const rateResult = await pool.query(`
      SELECT
        hour_bucket,
        promotions_count,
        promotions_allowed,
        promotions_blocked,
        rate_limit_triggered
      FROM fhq_canonical.g5_promotion_rate_log
      WHERE hour_bucket >= date_trunc('hour', NOW() - INTERVAL '6 hours')
      ORDER BY hour_bucket DESC
    `)

    const status = statusResult.rows[0] || {}
    const shadow = shadowResult.rows[0] || {}
    const drift = driftResult.rows[0] || null
    const sla = slaResult.rows[0] || {}

    return NextResponse.json({
      pipeline: {
        state: status.pipeline_state || 'UNKNOWN',
        shadowModeEnabled: status.shadow_mode_enabled,
        shadowModeUntil: status.shadow_mode_until,
        shadowReviewCount: status.shadow_review_count || 0,
        shadowReviewRequired: status.shadow_review_required || 50,
        rampUpPercentage: status.ramp_up_percentage || 10,
        rampUpStage: status.ramp_up_stage || 1,
        maxPromotionsPerHour: status.max_promotions_per_hour || 50,
        rateLimitEnabled: status.rate_limit_enabled,
        currentHourPromotions: status.current_hour_promotions || 0,
        pausedAt: status.paused_at,
        pausedReason: status.paused_reason,
        configUpdatedAt: status.config_updated_at
      },
      shadow: {
        total: parseInt(shadow.total || '0'),
        wouldPass: parseInt(shadow.would_pass || '0'),
        wouldReject: parseInt(shadow.would_reject || '0'),
        reviewed: parseInt(shadow.reviewed || '0'),
        avgMs: parseFloat(shadow.avg_ms || '0'),
        maxMs: parseInt(shadow.max_ms || '0'),
        passRate: parseInt(shadow.total || '0') > 0
          ? (parseInt(shadow.would_pass || '0') / parseInt(shadow.total || '1') * 100)
          : 0
      },
      recentShadow: recentShadowResult.rows.map((r: any) => ({
        shadowId: r.shadow_id,
        needleId: r.needle_id,
        wouldPass: r.would_pass_gate_a,
        wouldBeState: r.would_be_signal_state,
        result: r.gate_a_result,
        evidenceMs: r.evidence_gen_ms,
        gateAMs: r.gate_a_eval_ms,
        totalMs: r.total_ms,
        reviewed: r.reviewed,
        createdAt: r.created_at
      })),
      drift: drift ? {
        avgEqs: parseFloat(drift.rolling_7day_avg_eqs || '0'),
        needleCount: parseInt(drift.rolling_7day_needle_count || '0'),
        signalCount: parseInt(drift.rolling_7day_signal_count || '0'),
        conversionRate: parseFloat(drift.rolling_7day_conversion_rate || '0'),
        eqsThreshold: parseFloat(drift.eqs_threshold || '0.85'),
        conversionThreshold: parseFloat(drift.conversion_threshold || '0.05'),
        eqsBreach: drift.eqs_below_threshold,
        conversionBreach: drift.conversion_below_threshold,
        driftDetected: drift.any_drift_detected,
        computedAt: drift.computed_at
      } : null,
      sla: {
        totalPromotions: parseInt(sla.total_promotions || '0'),
        evidenceBreaches: parseInt(sla.evidence_breaches || '0'),
        gateABreaches: parseInt(sla.gate_a_breaches || '0'),
        totalBreaches: parseInt(sla.total_breaches || '0'),
        avgEvidenceMs: parseFloat(sla.avg_evidence_ms || '0'),
        avgGateAMs: parseFloat(sla.avg_gate_a_ms || '0'),
        avgTotalMs: parseFloat(sla.avg_total_ms || '0'),
        maxTotalMs: parseInt(sla.max_total_ms || '0'),
        complianceRate: parseInt(sla.total_promotions || '0') > 0
          ? ((parseInt(sla.total_promotions || '0') - parseInt(sla.total_breaches || '0')) /
             parseInt(sla.total_promotions || '1') * 100)
          : 100
      },
      passRateHistory: passRateResult.rows.map((r: any) => ({
        evaluated: r.total_evaluated,
        passed: r.total_passed,
        rate: parseFloat(r.pass_rate || '0'),
        previousRate: parseFloat(r.previous_pass_rate || '0'),
        delta: parseFloat(r.pass_rate_delta || '0'),
        anomaly: r.anomaly_detected,
        createdAt: r.created_at
      })),
      recentEvents: eventsResult.rows.map((r: any) => ({
        eventId: r.event_id,
        type: r.event_type,
        needleId: r.needle_id,
        data: r.event_data,
        severity: r.severity,
        defconEscalation: r.defcon_escalation,
        createdAt: r.created_at
      })),
      rateLimit: rateResult.rows.map((r: any) => ({
        hour: r.hour_bucket,
        count: r.promotions_count,
        allowed: r.promotions_allowed,
        blocked: r.promotions_blocked,
        triggered: r.rate_limit_triggered
      })),
      timestamp: new Date().toISOString()
    })
  } catch (error) {
    console.error('Pipeline Status API error:', error)
    return NextResponse.json(
      { error: String(error), timestamp: new Date().toISOString() },
      { status: 500 }
    )
  }
}
