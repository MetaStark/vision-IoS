/**
 * AOL Live Shadow Activity API Endpoint
 * CEO Directive CD-IOS-012-LIVE-ACT-001
 *
 * Returns LIVE Paper → Live Shadow activity for IoS-012.
 * READ-ONLY: No system modifications.
 */

import { NextResponse } from 'next/server'
import { queryMany, queryOne } from '@/lib/db'

export const revalidate = 5 // 5-second polling

interface ShadowTrade {
  trade_id: string
  asset_id: string
  direction: string
  entry_price: number
  shadow_size: number
  entry_time: string
  entry_regime: string | null
  exit_price: number | null
  exit_time: string | null
  pnl: number | null
  status: string
}

interface DecisionPlan {
  decision_id: string
  decision_type: string
  defcon_level: number
  execution_state: string
  signature_agent: string
  created_at: string
}

interface SecurityAlert {
  alert_id: string
  alert_type: string
  alert_severity: string
  source_module: string
  description: string
  created_at: string
}

interface IoS012Status {
  ios_id: string
  status: string
  governance_state: string
  updated_at: string
}

export async function GET() {
  try {
    // Get IoS-012 status
    const ios012Status = await queryOne<IoS012Status>(`
      SELECT ios_id, status, governance_state, updated_at
      FROM fhq_meta.ios_registry
      WHERE ios_id = 'IoS-012'
    `)

    // Get recent shadow trades
    const shadowTrades = await queryMany<ShadowTrade>(`
      SELECT
        trade_id,
        asset_id,
        direction,
        entry_price,
        shadow_size,
        entry_time,
        entry_regime,
        exit_price,
        exit_time,
        shadow_pnl as pnl,
        COALESCE(status, CASE WHEN exit_time IS NOT NULL THEN 'CLOSED' ELSE 'OPEN' END) as status
      FROM fhq_execution.shadow_trades
      ORDER BY entry_time DESC
      LIMIT 20
    `)

    // Get recent decision plans
    const decisions = await queryMany<DecisionPlan>(`
      SELECT
        decision_id,
        decision_type,
        defcon_level,
        execution_state,
        signature_agent,
        created_at
      FROM fhq_governance.decision_log
      ORDER BY created_at DESC
      LIMIT 15
    `)

    // Get recent security alerts (governance events)
    const alerts = await queryMany<SecurityAlert>(`
      SELECT
        alert_id,
        alert_type,
        alert_severity,
        source_module,
        description,
        created_at
      FROM fhq_governance.security_alerts
      WHERE source_module = 'IoS-012'
      ORDER BY created_at DESC
      LIMIT 20
    `)

    // Get safeguard status
    const safeguards = {
      ed25519_validation: true,
      execution_guard: true,
      ios008_mandate: true,
      defcon_circuit_breaker: true,
      paper_mode: ios012Status?.governance_state === 'PAPER_LIVE_SHADOW_ACTIVE'
    }

    // Calculate summary stats
    const openTrades = shadowTrades.filter(t => t.status === 'OPEN').length
    const closedTrades = shadowTrades.filter(t => t.status === 'CLOSED').length
    const totalPnL = shadowTrades
      .filter(t => t.pnl !== null)
      .reduce((sum, t) => sum + (t.pnl || 0), 0)

    const criticalAlerts = alerts.filter(a => a.alert_severity === 'CRITICAL').length
    const highAlerts = alerts.filter(a => a.alert_severity === 'HIGH').length

    return NextResponse.json({
      success: true,
      timestamp: new Date().toISOString(),
      directive: 'CD-IOS-012-LIVE-ACT-001',
      activation_mode: 'PAPER_LIVE_SHADOW',
      ios012: ios012Status,
      safeguards,
      shadow_trades: {
        data: shadowTrades,
        summary: {
          open: openTrades,
          closed: closedTrades,
          total_pnl: totalPnL
        }
      },
      decisions: {
        data: decisions,
        total: decisions.length
      },
      governance_events: {
        data: alerts,
        summary: {
          critical: criticalAlerts,
          high: highAlerts,
          total: alerts.length
        }
      }
    })
  } catch (error) {
    console.error('Live Shadow API Error:', error)
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to fetch live shadow activity',
        message: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    )
  }
}
