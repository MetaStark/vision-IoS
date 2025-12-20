/**
 * CCO Promotion Funnel API Route
 * ===============================
 * WAVE 17B - Golden Needle Promotion Standard
 *
 * Returns:
 * - Funnel metrics (intake, validation, arsenal)
 * - Signal arsenal state counts
 * - Governance ledger (recent promotions)
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
    // Panel A & B: Fetch funnel metrics from v_promotion_funnel
    const funnelResult = await pool.query(`
      SELECT
        total_needles,
        admissible_candidates,
        rejected_admissibility,
        gate_a_pass_rate,
        reject_sitc_not_high,
        reject_eqs_below_085,
        reject_no_vega_evidence,
        reject_no_canonical,
        avg_eqs,
        min_eqs,
        max_eqs
      FROM fhq_canonical.v_promotion_funnel
    `)

    // Panel C: Fetch signal arsenal from v_signal_arsenal
    const arsenalResult = await pool.query(`
      SELECT
        current_state,
        count,
        latest_entry,
        oldest_entry
      FROM fhq_canonical.v_signal_arsenal
      ORDER BY count DESC
    `)

    // Panel D: Fetch recent governance ledger entries
    const ledgerResult = await pool.query(`
      SELECT
        promotion_id,
        needle_id,
        current_status,
        gate_a_passed,
        gate_a_rejection_reason,
        gate_b_passed,
        gate_b_rejection_reason,
        gate_c_signal_instantiated as gate_c_passed,
        gate_c_signal_state_id as signal_id,
        evidence_pack_hash,
        signed_by,
        created_at
      FROM fhq_canonical.g5_promotion_ledger
      ORDER BY created_at DESC
      LIMIT 20
    `)

    // Intake rate (needles per hour in last 24h)
    const intakeRateResult = await pool.query(`
      SELECT
        COUNT(*) as needles_24h,
        COUNT(*) / 24.0 as needles_per_hour
      FROM fhq_canonical.golden_needles
      WHERE created_at > NOW() - INTERVAL '24 hours'
    `)

    // Needles awaiting validation (NEEDLE status, not yet processed)
    const awaitingValidationResult = await pool.query(`
      SELECT COUNT(*) as awaiting
      FROM fhq_canonical.golden_needles gn
      WHERE gn.is_current = true
      AND NOT EXISTS (
        SELECT 1 FROM fhq_canonical.g5_promotion_ledger pl
        WHERE pl.needle_id = gn.needle_id
      )
    `)

    // Get rejection breakdown by reason
    const rejectionBreakdownResult = await pool.query(`
      SELECT
        gate_a_rejection_reason,
        COUNT(*) as count
      FROM fhq_canonical.g5_promotion_ledger
      WHERE gate_a_passed = false
      AND gate_a_rejection_reason IS NOT NULL
      GROUP BY gate_a_rejection_reason
      ORDER BY count DESC
      LIMIT 10
    `)

    const funnel = funnelResult.rows[0] || {
      total_needles: 0,
      admissible_candidates: 0,
      rejected_admissibility: 0,
      gate_a_pass_rate: 0,
      reject_sitc_not_high: 0,
      reject_eqs_below_085: 0,
      reject_no_vega_evidence: 0,
      reject_no_canonical: 0,
      avg_eqs: 0,
      min_eqs: 0,
      max_eqs: 0
    }

    const arsenal = arsenalResult.rows.reduce((acc: any, row: any) => {
      acc[row.current_state] = {
        count: parseInt(row.count),
        latestEntry: row.latest_entry,
        oldestEntry: row.oldest_entry
      }
      return acc
    }, {})

    const intakeRate = intakeRateResult.rows[0] || { needles_24h: 0, needles_per_hour: 0 }
    const awaitingValidation = parseInt(awaitingValidationResult.rows[0]?.awaiting || '0')
    const rejectionBreakdown = rejectionBreakdownResult.rows

    return NextResponse.json({
      // Panel A: Intake
      intake: {
        totalNeedles: parseInt(funnel.total_needles),
        needles24h: parseInt(intakeRate.needles_24h),
        needlesPerHour: parseFloat(intakeRate.needles_per_hour || '0'),
        avgEqs: parseFloat(funnel.avg_eqs || '0'),
        minEqs: parseFloat(funnel.min_eqs || '0'),
        maxEqs: parseFloat(funnel.max_eqs || '0'),
        gateAPassRate: parseFloat(funnel.gate_a_pass_rate || '0')
      },
      // Panel B: Validation Queue
      validationQueue: {
        awaitingValidation,
        admissibleCandidates: parseInt(funnel.admissible_candidates),
        rejectedAdmissibility: parseInt(funnel.rejected_admissibility),
        rejectionReasons: {
          sitcNotHigh: parseInt(funnel.reject_sitc_not_high || '0'),
          eqsBelow085: parseInt(funnel.reject_eqs_below_085 || '0'),
          noVegaEvidence: parseInt(funnel.reject_no_vega_evidence || '0'),
          noCanonical: parseInt(funnel.reject_no_canonical || '0')
        },
        rejectionBreakdown: rejectionBreakdown.map((r: any) => ({
          reason: r.gate_a_rejection_reason,
          count: parseInt(r.count)
        }))
      },
      // Panel C: Signal Arsenal
      signalArsenal: {
        DORMANT: arsenal.DORMANT || { count: 0 },
        PRIMED: arsenal.PRIMED || { count: 0 },
        ARMED: arsenal.ARMED || { count: 0 },
        EXECUTING: arsenal.EXECUTING || { count: 0 },
        POSITION: arsenal.POSITION || { count: 0 },
        COOLING: arsenal.COOLING || { count: 0 },
        EXPIRED: arsenal.EXPIRED || { count: 0 },
        total: Object.values(arsenal).reduce((sum: number, a: any) => sum + (a.count || 0), 0)
      },
      // Panel D: Governance Ledger
      governanceLedger: ledgerResult.rows.map((row: any) => ({
        promotionId: row.promotion_id,
        needleId: row.needle_id,
        currentStatus: row.current_status,
        gateAPassed: row.gate_a_passed,
        gateARejection: row.gate_a_rejection_reason,
        gateBPassed: row.gate_b_passed,
        gateBRejection: row.gate_b_rejection_reason,
        gateCPassed: row.gate_c_passed,
        signalId: row.signal_id,
        evidenceHash: row.evidence_pack_hash,
        signedBy: row.signed_by,
        createdAt: row.created_at
      })),
      timestamp: new Date().toISOString()
    })
  } catch (error) {
    console.error('Promotion Funnel API error:', error)
    return NextResponse.json(
      { error: String(error), timestamp: new Date().toISOString() },
      { status: 500 }
    )
  }
}
