/**
 * AOL Integrity Ledger API Endpoint
 * CEO Directive 2026-FHQ-AOL-PATCH-01 Section 4.3
 *
 * Authority: ADR-001, ADR-006, ADR-009, ADR-018
 * Classification: CONSTITUTIONAL - Glass Wall Observability Layer
 *
 * Returns real-time agent task events from agent_task_log.
 * READ-ONLY: No system modifications.
 */

import { NextResponse } from 'next/server'
import { queryMany } from '@/lib/db'

export const revalidate = 5 // 5-second polling

interface LedgerEntry {
  task_id: string
  agent_id: string
  task_name: string
  task_type: string
  status: string
  started_at: string
  completed_at: string | null
  latency_ms: number | null
  cost_usd: number | null
  provider: string | null
  signature_hash: string | null
  quad_hash: string | null
  governance_flag: 'OK' | 'ALERT' | 'INFO'
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const limit = Math.min(parseInt(searchParams.get('limit') || '50'), 100)
  const agent_id = searchParams.get('agent_id')

  try {
    // Build query with optional agent filter
    const whereClause = agent_id ? 'WHERE agent_id = $1' : ''
    const params = agent_id ? [agent_id] : []

    const entries = await queryMany<any>(`
      SELECT
        task_id,
        agent_id,
        task_name,
        task_type,
        status,
        started_at,
        completed_at,
        latency_ms,
        cost_usd,
        provider,
        signature_hash,
        quad_hash,
        fallback_used,
        retry_count,
        error_message
      FROM fhq_governance.agent_task_log
      ${whereClause}
      ORDER BY started_at DESC
      LIMIT ${limit}
    `, params)

    // Transform to ledger entries with governance flags
    const ledger: LedgerEntry[] = entries.map((entry: any) => {
      // Determine governance flag based on status and context
      let governanceFlag: 'OK' | 'ALERT' | 'INFO' = 'INFO'

      if (entry.status === 'SUCCESS') {
        governanceFlag = 'OK'
      } else if (entry.status === 'FAILED' || entry.status === 'ERROR') {
        governanceFlag = 'ALERT'
      } else if (entry.retry_count > 0 || entry.fallback_used) {
        governanceFlag = 'ALERT' // Retries or fallbacks indicate issues
      }

      return {
        task_id: entry.task_id,
        agent_id: entry.agent_id,
        task_name: entry.task_name,
        task_type: entry.task_type,
        status: entry.status,
        started_at: entry.started_at,
        completed_at: entry.completed_at,
        latency_ms: entry.latency_ms,
        cost_usd: entry.cost_usd ? parseFloat(entry.cost_usd) : null,
        provider: entry.provider,
        signature_hash: entry.signature_hash,
        quad_hash: entry.quad_hash,
        governance_flag: governanceFlag,
      }
    })

    // Calculate summary
    const summary = {
      total_entries: ledger.length,
      ok_count: ledger.filter(e => e.governance_flag === 'OK').length,
      alert_count: ledger.filter(e => e.governance_flag === 'ALERT').length,
      info_count: ledger.filter(e => e.governance_flag === 'INFO').length,
      unique_agents: [...new Set(ledger.map(e => e.agent_id))].length,
    }

    return NextResponse.json({
      success: true,
      timestamp: new Date().toISOString(),
      compliance: ['ADR-006', 'ADR-018'],
      directive: 'CEO-2026-FHQ-AOL-PATCH-01',
      data_source: 'fhq_governance.agent_task_log',
      data: ledger,
      summary,
    })
  } catch (error) {
    console.error('AOL Ledger API Error:', error)

    const errorMessage = error instanceof Error ? error.message : 'Unknown error'

    // Check if table doesn't exist
    if (errorMessage.includes('does not exist')) {
      return NextResponse.json(
        {
          success: false,
          error: 'Telemetry not activated',
          message: 'Run migration 105_aol_telemetry_activation.sql to enable integrity ledger',
        },
        { status: 503 }
      )
    }

    return NextResponse.json(
      {
        success: false,
        error: 'Failed to fetch integrity ledger',
        message: errorMessage,
      },
      { status: 500 }
    )
  }
}
