/**
 * CCO Status API Route
 * ====================
 * WAVE 17A + 17D - Central Context Orchestrator Live Status
 *
 * WAVE 17D SINGLE-WRITER LAW:
 * - This API is READ-ONLY
 * - All values come directly from g5_cco_state
 * - No calculations, no inference, no overrides
 * - CCO_DAEMON is the sole writer to g5_cco_state
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
    // Fetch CCO state - READ-ONLY from g5_cco_state
    const ccoStateResult = await pool.query(`
      SELECT
        cco_status,
        global_permit,
        context_vector,
        context_hash,
        input_hash,
        source_tables,
        valid_until,
        permit_reason,
        permit_attribution,
        context_timestamp,
        updated_at,
        defcon_level,
        defcon_blocks_execution,
        current_regime,
        current_regime_confidence,
        current_vol_percentile,
        current_vol_state,
        current_liquidity_state,
        current_market_hours,
        EXTRACT(EPOCH FROM (NOW() - context_timestamp)) as context_age_seconds
      FROM fhq_canonical.g5_cco_state
      WHERE is_active = TRUE
      LIMIT 1
    `)

    // Fetch signal summary
    const signalSummaryResult = await pool.query(`
      SELECT
        current_state,
        COUNT(*) as count
      FROM fhq_canonical.g5_signal_state
      GROUP BY current_state
    `)

    // Fetch recent state transitions
    const transitionsResult = await pool.query(`
      SELECT
        needle_id,
        from_state,
        to_state,
        transition_trigger,
        context_snapshot,
        cco_status,
        transition_valid,
        transitioned_at
      FROM fhq_canonical.g5_state_transitions
      ORDER BY transitioned_at DESC
      LIMIT 10
    `)

    // Fetch exit criteria status
    const exitCriteriaResult = await pool.query(`
      SELECT
        total_paper_trades,
        paper_sharpe,
        paper_max_drawdown,
        paper_win_rate,
        paper_duration_days,
        passes_min_trades,
        passes_sharpe,
        passes_drawdown,
        passes_win_rate,
        passes_duration,
        all_criteria_passed,
        g5_eligible_since,
        vega_attestation,
        vega_attestation_at,
        ceo_two_man_rule,
        live_activation_authorized,
        last_updated
      FROM fhq_canonical.g5_exit_criteria_status
      WHERE is_active = TRUE
      LIMIT 1
    `)

    // Fetch Golden Needles summary with tier distribution
    const needlesSummaryResult = await pool.query(`
      SELECT
        COUNT(*) as total_needles,
        COUNT(*) FILTER (WHERE is_current = true) as current_needles,
        AVG(eqs_score::numeric) as avg_eqs,
        AVG(confluence_factor_count) as avg_factors,
        MIN(created_at) as oldest_needle,
        MAX(created_at) as newest_needle,
        COUNT(*) FILTER (WHERE is_current = true AND eqs_score >= 0.80) as gold_count,
        COUNT(*) FILTER (WHERE is_current = true AND eqs_score >= 0.65 AND eqs_score < 0.80) as silver_count,
        COUNT(*) FILTER (WHERE is_current = true AND eqs_score >= 0.50 AND eqs_score < 0.65) as bronze_count,
        COUNT(*) FILTER (WHERE is_current = true AND eqs_score < 0.50) as below_count
      FROM fhq_canonical.golden_needles
    `)

    // Fetch Golden Needles by category
    const needlesByCategoryResult = await pool.query(`
      SELECT
        hypothesis_category,
        COUNT(*) as count,
        AVG(eqs_score::numeric) as avg_eqs
      FROM fhq_canonical.golden_needles
      WHERE is_current = true
      GROUP BY hypothesis_category
      ORDER BY count DESC
      LIMIT 10
    `)

    // Fetch recent Golden Needles
    const recentNeedlesResult = await pool.query(`
      SELECT
        needle_id,
        hypothesis_title,
        hypothesis_category,
        eqs_score,
        confluence_factor_count,
        sitc_confidence_level,
        regime_technical,
        regime_sovereign,
        price_witness_symbol,
        price_witness_value,
        defcon_level,
        expected_timeframe_days,
        created_at
      FROM fhq_canonical.golden_needles
      WHERE is_current = true
      ORDER BY created_at DESC
      LIMIT 10
    `)

    // Fetch Paper Trades summary
    const tradesSummaryResult = await pool.query(`
      SELECT
        COUNT(*) as total_trades,
        COUNT(*) FILTER (WHERE exit_timestamp IS NOT NULL) as closed_trades,
        COUNT(*) FILTER (WHERE exit_timestamp IS NULL) as open_trades,
        COUNT(*) FILTER (WHERE trade_outcome = 'WIN') as wins,
        COUNT(*) FILTER (WHERE trade_outcome = 'LOSS') as losses,
        SUM(pnl_absolute) as total_pnl,
        AVG(pnl_percent) FILTER (WHERE exit_timestamp IS NOT NULL) as avg_pnl_pct,
        AVG(holding_periods) FILTER (WHERE exit_timestamp IS NOT NULL) as avg_holding_periods
      FROM fhq_canonical.g5_paper_trades
    `)

    // Fetch recent Paper Trades with Golden Needle details
    const recentTradesResult = await pool.query(`
      SELECT
        pt.trade_id,
        pt.needle_id,
        pt.symbol,
        pt.direction,
        pt.entry_price,
        pt.exit_price,
        pt.position_size,
        pt.entry_regime,
        pt.entry_context,
        pt.exit_trigger,
        pt.pnl_absolute,
        pt.pnl_percent,
        pt.holding_periods,
        pt.trade_outcome,
        pt.entry_timestamp,
        pt.exit_timestamp,
        gn.hypothesis_title,
        gn.hypothesis_category,
        gn.eqs_score,
        gn.confluence_factor_count,
        gn.sitc_confidence_level,
        gn.expected_timeframe_days
      FROM fhq_canonical.g5_paper_trades pt
      LEFT JOIN fhq_canonical.golden_needles gn ON pt.needle_id = gn.needle_id
      ORDER BY pt.entry_timestamp DESC
      LIMIT 10
    `)

    // Fetch daemon health from health log
    const healthResult = await pool.query(`
      SELECT
        cco_status,
        context_age_seconds,
        triggered_degraded,
        triggered_unavailable,
        triggered_defcon,
        defcon_level_set,
        recovered_to_operational,
        signals_blocked_count,
        signals_allowed_count,
        check_timestamp
      FROM fhq_canonical.g5_cco_health_log
      ORDER BY check_timestamp DESC
      LIMIT 1
    `)

    const ccoState = ccoStateResult.rows[0] || null
    const signalSummary = signalSummaryResult.rows.reduce((acc: any, row: any) => {
      acc[row.current_state] = parseInt(row.count)
      return acc
    }, {})
    const transitions = transitionsResult.rows
    const exitCriteria = exitCriteriaResult.rows[0] || null
    const daemonHealth = healthResult.rows[0] || null
    const needlesSummary = needlesSummaryResult.rows[0] || null
    const needlesByCategory = needlesByCategoryResult.rows
    const recentNeedles = recentNeedlesResult.rows
    const tradesSummary = tradesSummaryResult.rows[0] || null
    const recentTrades = recentTradesResult.rows

    // Parse context vector for display
    let contextDetails = null
    if (ccoState?.context_vector) {
      try {
        contextDetails = typeof ccoState.context_vector === 'string'
          ? JSON.parse(ccoState.context_vector)
          : ccoState.context_vector
      } catch {
        contextDetails = ccoState.context_vector
      }
    }

    // WAVE 17D: Return exactly what is in g5_cco_state - no overrides
    return NextResponse.json({
      ccoState: ccoState ? {
        status: ccoState.cco_status,
        globalPermit: ccoState.global_permit,
        contextHash: ccoState.context_hash,
        inputHash: ccoState.input_hash,
        sourceTables: ccoState.source_tables,
        validUntil: ccoState.valid_until,
        permitReason: ccoState.permit_reason,
        permitAttribution: ccoState.permit_attribution,
        contextTimestamp: ccoState.context_timestamp,
        updatedAt: ccoState.updated_at,
        contextAgeSeconds: parseFloat(ccoState.context_age_seconds || '0'),
        defconLevel: ccoState.defcon_level,
        defconBlocksExecution: ccoState.defcon_blocks_execution,
        currentRegime: ccoState.current_regime,
        currentRegimeConfidence: parseFloat(ccoState.current_regime_confidence || '0'),
        currentVolPercentile: parseFloat(ccoState.current_vol_percentile || '0'),
        currentVolState: ccoState.current_vol_state,
        currentLiquidityState: ccoState.current_liquidity_state,
        currentMarketHours: ccoState.current_market_hours,
        contextDetails
      } : null,
      signalSummary: {
        DORMANT: signalSummary.DORMANT || 0,
        ARMED: signalSummary.ARMED || 0,
        EXECUTED: signalSummary.EXECUTED || 0,
        EXPIRED: signalSummary.EXPIRED || 0,
        total: Object.values(signalSummary).reduce((a: number, b: any) => a + parseInt(b), 0)
      },
      transitions,
      exitCriteria: exitCriteria ? {
        totalPaperTrades: exitCriteria.total_paper_trades,
        paperSharpe: parseFloat(exitCriteria.paper_sharpe || '0'),
        paperMaxDrawdown: parseFloat(exitCriteria.paper_max_drawdown || '0'),
        paperWinRate: parseFloat(exitCriteria.paper_win_rate || '0'),
        paperDurationDays: exitCriteria.paper_duration_days,
        passesMinTrades: exitCriteria.passes_min_trades,
        passesSharpe: exitCriteria.passes_sharpe,
        passesDrawdown: exitCriteria.passes_drawdown,
        passesWinRate: exitCriteria.passes_win_rate,
        passesDuration: exitCriteria.passes_duration,
        allCriteriaPassed: exitCriteria.all_criteria_passed,
        g5EligibleSince: exitCriteria.g5_eligible_since,
        vegaAttestation: exitCriteria.vega_attestation,
        vegaAttestationAt: exitCriteria.vega_attestation_at,
        ceoTwoManRule: exitCriteria.ceo_two_man_rule,
        liveActivationAuthorized: exitCriteria.live_activation_authorized,
        lastUpdated: exitCriteria.last_updated
      } : null,
      daemonHealth: daemonHealth ? {
        status: daemonHealth.cco_status,
        contextAgeSeconds: parseFloat(daemonHealth.context_age_seconds || '0'),
        triggeredDegraded: daemonHealth.triggered_degraded,
        triggeredUnavailable: daemonHealth.triggered_unavailable,
        triggeredDefcon: daemonHealth.triggered_defcon,
        defconLevelSet: daemonHealth.defcon_level_set,
        recoveredToOperational: daemonHealth.recovered_to_operational,
        signalsBlockedCount: daemonHealth.signals_blocked_count,
        signalsAllowedCount: daemonHealth.signals_allowed_count,
        checkTimestamp: daemonHealth.check_timestamp
      } : null,
      goldenNeedles: {
        summary: needlesSummary ? {
          totalNeedles: parseInt(needlesSummary.total_needles || '0'),
          currentNeedles: parseInt(needlesSummary.current_needles || '0'),
          avgEqs: parseFloat(needlesSummary.avg_eqs || '0'),
          avgFactors: parseFloat(needlesSummary.avg_factors || '0'),
          oldestNeedle: needlesSummary.oldest_needle,
          newestNeedle: needlesSummary.newest_needle,
          tierCounts: {
            gold: parseInt(needlesSummary.gold_count || '0'),
            silver: parseInt(needlesSummary.silver_count || '0'),
            bronze: parseInt(needlesSummary.bronze_count || '0'),
            below: parseInt(needlesSummary.below_count || '0')
          }
        } : null,
        byCategory: needlesByCategory.map((c: any) => ({
          category: c.hypothesis_category,
          count: parseInt(c.count),
          avgEqs: parseFloat(c.avg_eqs || '0')
        })),
        recent: recentNeedles.map((n: any) => {
          const eqs = parseFloat(n.eqs_score || '0')
          const tier = eqs >= 0.80 ? 'GOLD' : eqs >= 0.65 ? 'SILVER' : eqs >= 0.50 ? 'BRONZE' : 'BELOW'
          return {
            needleId: n.needle_id,
            title: n.hypothesis_title,
            category: n.hypothesis_category,
            eqsScore: eqs,
            tier,
            confluenceFactors: n.confluence_factor_count,
            sitcConfidence: n.sitc_confidence_level,
            regimeTechnical: n.regime_technical,
            regimeSovereign: n.regime_sovereign,
            priceWitnessSymbol: n.price_witness_symbol,
            priceWitnessValue: parseFloat(n.price_witness_value || '0'),
            defconLevel: n.defcon_level,
            expectedTimeframeDays: n.expected_timeframe_days,
            createdAt: n.created_at
          }
        })
      },
      paperTrades: {
        summary: tradesSummary ? {
          totalTrades: parseInt(tradesSummary.total_trades || '0'),
          closedTrades: parseInt(tradesSummary.closed_trades || '0'),
          openTrades: parseInt(tradesSummary.open_trades || '0'),
          wins: parseInt(tradesSummary.wins || '0'),
          losses: parseInt(tradesSummary.losses || '0'),
          totalPnl: parseFloat(tradesSummary.total_pnl || '0'),
          avgPnlPct: parseFloat(tradesSummary.avg_pnl_pct || '0'),
          avgHoldingPeriods: parseFloat(tradesSummary.avg_holding_periods || '0'),
          winRate: parseInt(tradesSummary.closed_trades || '0') > 0
            ? (parseInt(tradesSummary.wins || '0') / parseInt(tradesSummary.closed_trades || '1') * 100)
            : 0
        } : null,
        recent: recentTrades.map((t: any) => {
          // Parse entry context for target/stop loss
          let entryContext = null
          if (t.entry_context) {
            try {
              entryContext = typeof t.entry_context === 'string'
                ? JSON.parse(t.entry_context)
                : t.entry_context
            } catch { entryContext = t.entry_context }
          }

          // Calculate target and stop loss based on entry price and strategy
          const entryPrice = parseFloat(t.entry_price || '0')
          const direction = t.direction
          // Default: 5% target, 3% stop loss (can be overridden by entry_context)
          const targetPct = entryContext?.target_pct || 0.05
          const stopLossPct = entryContext?.stop_loss_pct || 0.03

          const targetPrice = direction === 'LONG'
            ? entryPrice * (1 + targetPct)
            : entryPrice * (1 - targetPct)
          const stopLossPrice = direction === 'LONG'
            ? entryPrice * (1 - stopLossPct)
            : entryPrice * (1 + stopLossPct)

          return {
            tradeId: t.trade_id,
            needleId: t.needle_id,
            symbol: t.symbol,
            direction: t.direction,
            entryPrice: entryPrice,
            exitPrice: t.exit_price ? parseFloat(t.exit_price) : null,
            positionSize: parseFloat(t.position_size || '0'),
            entryRegime: t.entry_regime,
            entryContext: entryContext,
            exitTrigger: t.exit_trigger,
            pnlAbsolute: t.pnl_absolute ? parseFloat(t.pnl_absolute) : null,
            pnlPercent: t.pnl_percent ? parseFloat(t.pnl_percent) : null,
            holdingPeriods: t.holding_periods,
            tradeOutcome: t.trade_outcome,
            entryTimestamp: t.entry_timestamp,
            exitTimestamp: t.exit_timestamp,
            // Golden Needle details
            needleTitle: t.hypothesis_title,
            needleCategory: t.hypothesis_category,
            needleEqs: t.eqs_score ? parseFloat(t.eqs_score) : null,
            needleConfluence: t.confluence_factor_count,
            needleSitcConfidence: t.sitc_confidence_level,
            expectedTimeframeDays: t.expected_timeframe_days,
            // Calculated targets
            targetPrice: Math.round(targetPrice * 100) / 100,
            stopLossPrice: Math.round(stopLossPrice * 100) / 100,
            targetPct: targetPct * 100,
            stopLossPct: stopLossPct * 100
          }
        })
      },
      timestamp: new Date().toISOString()
    })
  } catch (error) {
    console.error('CCO Status API error:', error)
    return NextResponse.json(
      { error: String(error), timestamp: new Date().toISOString() },
      { status: 500 }
    )
  }
}
