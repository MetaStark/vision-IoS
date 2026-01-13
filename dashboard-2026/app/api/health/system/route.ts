/**
 * System Health API Endpoint
 * GET /api/health/system
 *
 * Returns comprehensive system health data:
 * - Agent heartbeats/liveness
 * - Gap closure status (CEO-DIR-2026-042 through 045)
 * - DEFCON state
 * - Monitoring baseline
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
    const client = await pool.connect()
    try {
      // 1. Agent Heartbeats
      const heartbeatsResult = await client.query(`
        SELECT
          agent_id,
          component,
          current_task,
          health_score,
          health_source,
          liveness_basis,
          events_processed,
          last_heartbeat,
          EXTRACT(EPOCH FROM (NOW() - last_heartbeat))::int as age_seconds
        FROM fhq_governance.agent_heartbeats
        ORDER BY agent_id
      `)

      // 2. DEFCON State
      const defconResult = await client.query(`
        SELECT
          defcon_level,
          reason,
          set_by,
          created_at,
          EXTRACT(EPOCH FROM (NOW() - created_at))/86400 as days_since_set
        FROM fhq_monitoring.defcon_state
        WHERE is_current = true
        LIMIT 1
      `)

      // 3. Monitoring Baseline
      const monitoringResult = await client.query(`
        SELECT
          'execution_log' as table_name, COUNT(*) as row_count FROM fhq_monitoring.execution_log
        UNION ALL
        SELECT 'alert_config', COUNT(*) FROM fhq_monitoring.alert_config
        UNION ALL
        SELECT 'daemon_health', COUNT(*) FROM fhq_monitoring.daemon_health
        UNION ALL
        SELECT 'circuit_breaker_events', COUNT(*) FROM fhq_monitoring.circuit_breaker_events
        ORDER BY table_name
      `)

      // 4. Learning Loop Health
      const learningResult = await client.query(`
        SELECT
          COUNT(*) as outcome_ledger_count,
          (SELECT COUNT(*) FROM fhq_canonical.canonical_outcomes) as canonical_outcomes_count
        FROM fhq_research.outcome_ledger
      `)

      // 5. Forecast Production (last 24h)
      const forecastResult = await client.query(`
        SELECT
          COUNT(*) as total_24h,
          COUNT(*) FILTER (WHERE forecast_made_at > NOW() - INTERVAL '1 hour') as last_hour
        FROM fhq_research.forecast_ledger
        WHERE forecast_made_at > NOW() - INTERVAL '24 hours'
      `)

      // 6. Price Freshness
      const priceResult = await client.query(`
        SELECT
          market_type,
          MAX(event_time_utc) as latest,
          EXTRACT(EPOCH FROM (NOW() - MAX(event_time_utc)))/60 as minutes_stale
        FROM fhq_core.market_prices_live
        GROUP BY market_type
        ORDER BY minutes_stale ASC
      `)

      // Compute gap statuses
      const heartbeats = heartbeatsResult.rows
      const allHeartbeatsFresh = heartbeats.every(h => h.age_seconds < 300) // 5 min threshold
      const allAgentsHealthy = heartbeats.every(h => parseFloat(h.health_score) >= 0.5)
      const monitoring = monitoringResult.rows
      const monitoringPopulated = monitoring.every(m => parseInt(m.row_count) > 0)
      const defcon = defconResult.rows[0]
      const learning = learningResult.rows[0]
      const forecasts = forecastResult.rows[0]

      const gaps = [
        {
          id: 'GAP-001',
          name: 'Heartbeat Enforcement',
          status: allHeartbeatsFresh ? 'CLOSED' : 'DEGRADED',
          detail: `${heartbeats.length} agents, max age: ${Math.max(...heartbeats.map(h => h.age_seconds))}s`
        },
        {
          id: 'GAP-002',
          name: 'Monitoring Baseline',
          status: monitoringPopulated ? 'CLOSED' : 'OPEN',
          detail: `${monitoring.reduce((sum, m) => sum + parseInt(m.row_count), 0)} total rows`
        },
        {
          id: 'GAP-003',
          name: 'DEFCON State',
          status: defcon ? 'EVALUATED' : 'OPEN',
          detail: defcon ? `Level ${defcon.defcon_level} (${defcon.reason})` : 'No state'
        },
        {
          id: 'GAP-004',
          name: 'Agent Liveness',
          status: allAgentsHealthy ? 'CLOSED' : 'DEGRADED',
          detail: `${heartbeats.filter(h => parseFloat(h.health_score) >= 0.5).length}/${heartbeats.length} healthy`
        },
        {
          id: 'GAP-005',
          name: 'Outcome Semantics',
          status: parseInt(learning.outcome_ledger_count) > 1000 ? 'ATTESTED' : 'NEEDS_REVIEW',
          detail: `${learning.outcome_ledger_count} outcomes in ledger`
        }
      ]

      return NextResponse.json({
        timestamp: new Date().toISOString(),
        summary: {
          totalAgents: heartbeats.length,
          healthyAgents: heartbeats.filter(h => parseFloat(h.health_score) >= 0.5).length,
          defconLevel: defcon?.defcon_level || 5,
          gapsClosed: gaps.filter(g => ['CLOSED', 'EVALUATED', 'ATTESTED'].includes(g.status)).length,
          totalGaps: gaps.length
        },
        agents: heartbeats.map(h => ({
          id: h.agent_id,
          component: h.component,
          status: h.current_task?.replace('Status: ', '') || 'UNKNOWN',
          healthScore: parseFloat(h.health_score),
          healthSource: h.health_source,
          livenessBasis: h.liveness_basis,
          lastHeartbeat: h.last_heartbeat,
          ageSeconds: h.age_seconds,
          fresh: h.age_seconds < 300
        })),
        defcon: defcon ? {
          level: defcon.defcon_level,
          reason: defcon.reason,
          setBy: defcon.set_by,
          setAt: defcon.created_at,
          daysSinceSet: Math.round(parseFloat(defcon.days_since_set) * 10) / 10
        } : null,
        monitoring: monitoring.reduce((acc, m) => {
          acc[m.table_name] = parseInt(m.row_count)
          return acc
        }, {} as Record<string, number>),
        learning: {
          outcomeLedgerCount: parseInt(learning.outcome_ledger_count),
          canonicalOutcomesCount: parseInt(learning.canonical_outcomes_count)
        },
        forecasts: {
          total24h: parseInt(forecasts.total_24h),
          lastHour: parseInt(forecasts.last_hour),
          hourlyRate: Math.round(parseInt(forecasts.total_24h) / 24 * 10) / 10
        },
        priceFreshness: priceResult.rows.map(p => ({
          marketType: p.market_type,
          latest: p.latest,
          minutesStale: Math.round(parseFloat(p.minutes_stale) * 100) / 100
        })),
        gaps
      })
    } finally {
      client.release()
    }
  } catch (error) {
    console.error('System health fetch error:', error)
    return NextResponse.json({
      error: 'Failed to fetch system health',
      timestamp: new Date().toISOString()
    }, { status: 500 })
  }
}
