/**
 * IoS-013 Signal Overview API
 * CEO-DIR-2026-024 + CEO-DIR-2026-025: Database-Verified Dashboard Integrity
 *
 * Data sources:
 * - fhq_signal_context.weighted_signal_plan (primary signals + factor breakdown)
 * - fhq_research.forecast_skill_metrics (Brier scores)
 * - fhq_ops.v_brier_summary (aggregated Brier)
 * - fhq_governance.v_system_lvi (LVI values)
 * - fhq_governance.brier_decomposition (Murphy decomposition)
 */

import { NextResponse } from 'next/server'
import { Pool } from 'pg'

const pool = new Pool({
  host: '127.0.0.1',
  port: 54322,
  user: 'postgres',
  password: 'postgres',
  database: 'postgres',
})

interface FactorBreakdown {
  base_confidence: number
  regime_factor: number
  skill_factor: number
  causal_factor: number
  macro_bonus: number
  event_penalty: number
  composite_multiplier: number
  technical_signals: string[]
}

interface SignalRow {
  asset_id: string
  calibration_status: string
  direction: string
  confidence_score: number
  regime_context: string
  factors: FactorBreakdown
  created_at: string
}

interface BrierData {
  avg_brier_forecast_skill_metrics: number | null
  avg_brier_v_brier_summary: number | null
  skill_factor_used: number
  skill_formula: string
  forecast_count: number
  discrepancy_exists: boolean
  discrepancy_delta: number | null
  last_computed: string | null
}

interface MurphyDecomposition {
  avg_reliability: number | null
  avg_resolution: number | null
  avg_uncertainty: number | null
  sample_count: number
  computed_at: string | null
}

interface LVIStatus {
  is_active: boolean
  system_avg_lvi: number | null
  regime_avg_lvi: number | null
  total_assets_with_lvi: number
  last_computed: string | null
  missing_reason: string | null
}

interface SystemStatus {
  status: 'ACTIVE' | 'STALE' | 'DEGRADED'
  total_assets: number
  calibrated_assets: number
  last_updated: string
}

interface SignalOverview {
  system_status: SystemStatus
  signals: SignalRow[]
  brier: BrierData
  murphy: MurphyDecomposition
  lvi: LVIStatus
  db_reconciliation: {
    query_timestamp: string
    source_table: string
    row_count_match: boolean
  }
}

export async function GET() {
  const queryTimestamp = new Date().toISOString()

  try {
    const client = await pool.connect()

    try {
      // Get latest computation date
      const dateResult = await client.query(`
        SELECT MAX(computation_date) as max_date
        FROM fhq_signal_context.weighted_signal_plan
      `)
      const maxDate = dateResult.rows[0]?.max_date

      if (!maxDate) {
        return NextResponse.json({
          system_status: {
            status: 'DEGRADED',
            total_assets: 0,
            calibrated_assets: 0,
            last_updated: queryTimestamp,
          },
          signals: [],
          brier: { avg_brier_forecast_skill_metrics: null, avg_brier_v_brier_summary: null, skill_factor_used: 0, skill_formula: 'N/A', forecast_count: 0, discrepancy_exists: false, discrepancy_delta: null, last_computed: null },
          murphy: { avg_reliability: null, avg_resolution: null, avg_uncertainty: null, sample_count: 0, computed_at: null },
          lvi: { is_active: false, system_avg_lvi: null, regime_avg_lvi: null, total_assets_with_lvi: 0, last_computed: null, missing_reason: 'No signal data' },
          db_reconciliation: { query_timestamp: queryTimestamp, source_table: 'fhq_signal_context.weighted_signal_plan', row_count_match: false }
        })
      }

      // Get system status
      const statusResult = await client.query(`
        SELECT
          COUNT(DISTINCT asset_id) as total_assets,
          COUNT(DISTINCT CASE WHEN calibration_status = 'CALIBRATED' THEN asset_id END) as calibrated_assets,
          MAX(created_at) as last_updated
        FROM fhq_signal_context.weighted_signal_plan
        WHERE computation_date = $1
      `, [maxDate])

      const statusRow = statusResult.rows[0]
      const lastUpdated = new Date(statusRow.last_updated)
      const hoursSinceUpdate = (Date.now() - lastUpdated.getTime()) / (1000 * 60 * 60)

      let systemStatus: 'ACTIVE' | 'STALE' | 'DEGRADED'
      if (hoursSinceUpdate < 24) {
        systemStatus = 'ACTIVE'
      } else if (hoursSinceUpdate < 72) {
        systemStatus = 'STALE'
      } else {
        systemStatus = 'DEGRADED'
      }

      // Get all signals with factor breakdown from JSONB
      const signalsResult = await client.query(`
        SELECT
          asset_id,
          calibration_status::text,
          direction::text,
          confidence_score::numeric,
          regime_context,
          raw_signals,
          weighted_signals,
          created_at::text
        FROM fhq_signal_context.weighted_signal_plan
        WHERE computation_date = $1
        ORDER BY confidence_score DESC NULLS LAST, asset_id ASC
      `, [maxDate])

      // Parse signals with factor breakdown
      const signals: SignalRow[] = signalsResult.rows.map(row => {
        let factors: FactorBreakdown = {
          base_confidence: 0,
          regime_factor: 0,
          skill_factor: 0,
          causal_factor: 0,
          macro_bonus: 0,
          event_penalty: 0,
          composite_multiplier: 0,
          technical_signals: []
        }

        // Extract factors from weighted_signals JSONB
        const ws = row.weighted_signals
        if (Array.isArray(ws) && ws.length > 0 && ws[0].factors) {
          const f = ws[0].factors
          factors = {
            base_confidence: ws[0].raw_strength || 0,
            regime_factor: f.regime_factor || 0,
            skill_factor: f.skill_factor || 0,
            causal_factor: f.causal_factor || 0,
            macro_bonus: f.macro_bonus || 0,
            event_penalty: f.event_penalty || 0,
            composite_multiplier: f.composite_multiplier || 0,
            technical_signals: f.sources?.ios002_technical || []
          }
        } else if (ws && ws.factors) {
          // Old format (BTC-USD style)
          const f = ws.factors
          factors = {
            base_confidence: ws.weighted_confidence || 0,
            regime_factor: f.regime_alignment || 0,
            skill_factor: f.forecast_skill || 0,
            causal_factor: f.causal_linkage || 0,
            macro_bonus: 0,
            event_penalty: f.event_proximity_penalty || 0,
            composite_multiplier: 0,
            technical_signals: []
          }
        }

        return {
          asset_id: row.asset_id,
          calibration_status: row.calibration_status,
          direction: row.direction,
          confidence_score: parseFloat(row.confidence_score),
          regime_context: row.regime_context,
          factors,
          created_at: row.created_at,
        }
      })

      // Get Brier data from both sources
      const brierFSM = await client.query(`
        SELECT
          brier_score_mean::numeric as brier,
          forecast_count,
          computed_at::text
        FROM fhq_research.forecast_skill_metrics
        WHERE metric_scope = 'GLOBAL' AND scope_value = 'ALL_ASSETS'
        ORDER BY computed_at DESC
        LIMIT 1
      `)

      const brierSummary = await client.query(`
        SELECT
          avg_brier_score::numeric as brier,
          skill_factor::numeric,
          sample_count::integer,
          last_computed::text
        FROM fhq_ops.v_brier_summary
        LIMIT 1
      `)

      const brierFSMValue = brierFSM.rows[0]?.brier ? parseFloat(brierFSM.rows[0].brier) : null
      const brierSummaryValue = brierSummary.rows[0]?.brier ? parseFloat(brierSummary.rows[0].brier) : null
      const skillFactorUsed = brierSummary.rows[0]?.skill_factor ? parseFloat(brierSummary.rows[0].skill_factor) : 0

      const brier: BrierData = {
        avg_brier_forecast_skill_metrics: brierFSMValue,
        avg_brier_v_brier_summary: brierSummaryValue,
        skill_factor_used: skillFactorUsed,
        skill_formula: 'max(0.1, 1.0 - (brier * 1.8))',
        forecast_count: brierFSM.rows[0]?.forecast_count || 0,
        discrepancy_exists: brierFSMValue !== null && brierSummaryValue !== null && Math.abs(brierFSMValue - brierSummaryValue) > 0.001,
        discrepancy_delta: brierFSMValue !== null && brierSummaryValue !== null ? Math.abs(brierFSMValue - brierSummaryValue) : null,
        last_computed: brierSummary.rows[0]?.last_computed || brierFSM.rows[0]?.computed_at || null
      }

      // Get Murphy decomposition
      const murphyResult = await client.query(`
        SELECT
          AVG(reliability::numeric) as avg_reliability,
          AVG(resolution::numeric) as avg_resolution,
          AVG(uncertainty::numeric) as avg_uncertainty,
          COUNT(*) as sample_count,
          MAX(computed_at)::text as computed_at
        FROM fhq_governance.brier_decomposition
        WHERE computed_at > NOW() - INTERVAL '30 days'
      `)

      const murphy: MurphyDecomposition = {
        avg_reliability: murphyResult.rows[0]?.avg_reliability ? parseFloat(murphyResult.rows[0].avg_reliability) : null,
        avg_resolution: murphyResult.rows[0]?.avg_resolution ? parseFloat(murphyResult.rows[0].avg_resolution) : null,
        avg_uncertainty: murphyResult.rows[0]?.avg_uncertainty ? parseFloat(murphyResult.rows[0].avg_uncertainty) : null,
        sample_count: parseInt(murphyResult.rows[0]?.sample_count) || 0,
        computed_at: murphyResult.rows[0]?.computed_at || null
      }

      // Get LVI status
      const lviResult = await client.query(`
        SELECT
          COUNT(DISTINCT asset_id) as total_assets,
          AVG(lvi_value::numeric) as system_avg_lvi,
          AVG(regime_avg_lvi::numeric) as regime_avg_lvi,
          MAX(computed_at)::text as last_computed
        FROM fhq_governance.v_system_lvi
      `)

      const lviRow = lviResult.rows[0]
      const lvi: LVIStatus = {
        is_active: lviRow && parseInt(lviRow.total_assets) > 0,
        system_avg_lvi: lviRow?.system_avg_lvi ? parseFloat(lviRow.system_avg_lvi) : null,
        regime_avg_lvi: lviRow?.regime_avg_lvi ? parseFloat(lviRow.regime_avg_lvi) : null,
        total_assets_with_lvi: parseInt(lviRow?.total_assets) || 0,
        last_computed: lviRow?.last_computed || null,
        missing_reason: (!lviRow || parseInt(lviRow.total_assets) === 0) ? 'No LVI computations found' : null
      }

      const response: SignalOverview = {
        system_status: {
          status: systemStatus,
          total_assets: parseInt(statusRow.total_assets),
          calibrated_assets: parseInt(statusRow.calibrated_assets),
          last_updated: statusRow.last_updated,
        },
        signals,
        brier,
        murphy,
        lvi,
        db_reconciliation: {
          query_timestamp: queryTimestamp,
          source_table: 'fhq_signal_context.weighted_signal_plan',
          row_count_match: signals.length === parseInt(statusRow.total_assets)
        }
      }

      return NextResponse.json(response)
    } finally {
      client.release()
    }
  } catch (error) {
    console.error('IoS-013 API Error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch IoS-013 signals', details: String(error) },
      { status: 500 }
    )
  }
}
