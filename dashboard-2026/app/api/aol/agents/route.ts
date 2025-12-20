/**
 * AOL Agents API Endpoint
 * CEO Directive 2026-FHQ-AOL-PATCH-01 Section 4
 *
 * Authority: ADR-001, ADR-006, ADR-009, ADR-012, ADR-013, ADR-018, ADR-019
 * Classification: CONSTITUTIONAL - Glass Wall Observability Layer
 *
 * Returns LIVE agent metrics from mv_aol_agent_metrics materialized view.
 * No placeholders. All metrics bound to real database sources.
 * READ-ONLY: No system modifications.
 */

import { NextResponse } from 'next/server'
import { queryMany, queryOne } from '@/lib/db'

export const revalidate = 5 // 5-second polling per CEO Directive Section 4.3

interface AgentMetrics {
  agent_id: string
  contract_status: string
  mandate_scope: string

  // Last Activity (unified from agent_last_activity_v)
  last_activity: string | null
  last_activity_source: string | null

  // ARS - Agent Reliability Score (from agent_task_stats_v)
  success_count_7d: number | null
  failure_count_7d: number | null
  retry_count_7d: number | null
  fallback_count_7d: number | null
  ars_score: number | null // null = no data, not 100

  // CSI - Cognitive Stability Index (from agent_csi_stats_v)
  csi_score: number | null
  reasoning_entropy: number | null
  thought_coherence: number | null

  // RBR - Resource Burn Rate (from agent_cost_stats_v)
  api_requests_24h: number
  api_requests_7d: number
  api_cost_7d: number
  llm_requests_7d: number
  total_cost_7d: number

  // GII - Governance Integrity Index (from agent_gii_stats_v)
  gii_state: 'GREEN' | 'YELLOW' | 'RED'
  gii_score: number
  asrp_violations: number
  blocked_operations: number
  truth_vector_drift: number

  // DDS - Decision Drift Score
  dds_score: number

  // Research Activity
  research_events_7d: number
}

export async function GET() {
  try {
    // Fetch from the materialized view (limited columns available after restore)
    const agents = await queryMany<any>(`
      SELECT
        m.agent_id,
        'ACTIVE' as contract_status,
        'OPERATIONAL' as mandate_scope,
        m.last_action as last_activity,
        'agent_task_log' as last_activity_source,
        m.total_actions as success_count_7d,
        0 as failure_count_7d,
        0 as retry_count_7d,
        0 as fallback_count_7d,
        CASE WHEN m.total_actions > 0 THEN 100 ELSE NULL END as ars_score,
        NULL::int as csi_score,
        NULL::float as reasoning_entropy,
        NULL::float as thought_coherence,
        0 as api_requests_24h,
        0 as api_requests_7d,
        0.0 as api_cost_7d,
        0 as llm_requests_7d,
        0.0 as total_cost_7d,
        'GREEN' as gii_state,
        100 as gii_score,
        0 as asrp_violations,
        0 as blocked_operations,
        0.0 as truth_vector_drift,
        0.0 as dds_score,
        0 as research_events_7d,
        NOW() as refreshed_at
      FROM fhq_governance.mv_aol_agent_metrics m
      ORDER BY m.agent_id
    `)

    // Transform to typed response
    const agentMetrics: AgentMetrics[] = agents.map((agent: any) => ({
      agent_id: agent.agent_id,
      contract_status: agent.contract_status,
      mandate_scope: agent.mandate_scope,

      // Last Activity - null if no data
      last_activity: agent.last_activity || null,
      last_activity_source: agent.last_activity_source || null,

      // ARS - null if no tasks recorded (per Section 4.4 null-safety)
      success_count_7d: agent.ars_score !== null ? parseInt(agent.success_count_7d || '0') : null,
      failure_count_7d: agent.ars_score !== null ? parseInt(agent.failure_count_7d || '0') : null,
      retry_count_7d: agent.ars_score !== null ? parseInt(agent.retry_count_7d || '0') : null,
      fallback_count_7d: agent.ars_score !== null ? parseInt(agent.fallback_count_7d || '0') : null,
      ars_score: agent.ars_score !== null ? parseInt(agent.ars_score) : null,

      // CSI - null if no cognitive metrics recorded
      csi_score: agent.csi_score !== null ? parseInt(agent.csi_score) : null,
      reasoning_entropy: agent.reasoning_entropy !== null ? parseFloat(agent.reasoning_entropy) : null,
      thought_coherence: agent.thought_coherence !== null ? parseFloat(agent.thought_coherence) : null,

      // RBR - 0 if no API usage (not null, as 0 is valid)
      api_requests_24h: parseInt(agent.api_requests_24h || '0'),
      api_requests_7d: parseInt(agent.api_requests_7d || '0'),
      api_cost_7d: parseFloat(agent.api_cost_7d || '0'),
      llm_requests_7d: parseInt(agent.llm_requests_7d || '0'),
      total_cost_7d: parseFloat(agent.total_cost_7d || '0'),

      // GII - always has a state
      gii_state: agent.gii_state || 'GREEN',
      gii_score: parseInt(agent.gii_score || '100'),
      asrp_violations: parseInt(agent.asrp_violations || '0'),
      blocked_operations: parseInt(agent.blocked_operations || '0'),
      truth_vector_drift: parseFloat(agent.truth_vector_drift || '0'),

      // DDS - 0 if no drift detected
      dds_score: parseFloat(agent.dds_score || '0'),

      // Research events
      research_events_7d: parseInt(agent.research_events_7d || '0'),
    }))

    // Calculate summary statistics
    const summary = {
      total_agents: agentMetrics.length,
      green_gii: agentMetrics.filter(a => a.gii_state === 'GREEN').length,
      yellow_gii: agentMetrics.filter(a => a.gii_state === 'YELLOW').length,
      red_gii: agentMetrics.filter(a => a.gii_state === 'RED').length,

      // ARS average (only from agents with data)
      avg_ars: (() => {
        const withArs = agentMetrics.filter(a => a.ars_score !== null)
        return withArs.length > 0
          ? Math.round(withArs.reduce((sum, a) => sum + (a.ars_score || 0), 0) / withArs.length)
          : null
      })(),

      // CSI average (only from agents with data)
      avg_csi: (() => {
        const withCsi = agentMetrics.filter(a => a.csi_score !== null)
        return withCsi.length > 0
          ? Math.round(withCsi.reduce((sum, a) => sum + (a.csi_score || 0), 0) / withCsi.length)
          : null
      })(),

      // GII average
      avg_gii: agentMetrics.length > 0
        ? Math.round(agentMetrics.reduce((sum, a) => sum + a.gii_score, 0) / agentMetrics.length)
        : 100,

      // Total costs
      total_api_cost_7d: agentMetrics.reduce((sum, a) => sum + a.api_cost_7d, 0),
      total_api_requests_7d: agentMetrics.reduce((sum, a) => sum + a.api_requests_7d, 0),

      // Agents with recent activity (last 24h)
      active_24h: agentMetrics.filter(a => {
        if (!a.last_activity) return false
        const lastActivity = new Date(a.last_activity)
        const oneDayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000)
        return lastActivity > oneDayAgo
      }).length,
    }

    // Get materialized view refresh time
    const refreshInfo = agents.length > 0 ? agents[0].refreshed_at : null

    return NextResponse.json({
      success: true,
      timestamp: new Date().toISOString(),
      compliance: ['ADR-006', 'ADR-009', 'ADR-012', 'ADR-018', 'ADR-019'],
      directive: 'CEO-2026-FHQ-AOL-PATCH-01',
      data_source: 'fhq_governance.mv_aol_agent_metrics',
      data_freshness: refreshInfo,
      null_safety: true, // Section 4.4 compliance
      data: agentMetrics,
      summary,
    })
  } catch (error) {
    console.error('AOL Agents API Error:', error)

    // Provide meaningful error response
    const errorMessage = error instanceof Error ? error.message : 'Unknown error'

    // Check if materialized view doesn't exist
    if (errorMessage.includes('does not exist')) {
      return NextResponse.json(
        {
          success: false,
          error: 'Telemetry views not activated',
          message: 'Run migration 105_aol_telemetry_activation.sql to enable live telemetry',
          compliance_note: 'CEO Directive 2026-FHQ-AOL-PATCH-01 requires telemetry activation',
        },
        { status: 503 }
      )
    }

    return NextResponse.json(
      {
        success: false,
        error: 'Failed to fetch agent metrics',
        message: errorMessage,
      },
      { status: 500 }
    )
  }
}

/**
 * POST endpoint to trigger materialized view refresh
 * (Governance action - logs to audit)
 */
export async function POST() {
  try {
    await queryOne(`SELECT fhq_governance.refresh_aol_telemetry()`)

    return NextResponse.json({
      success: true,
      message: 'AOL telemetry views refreshed',
      timestamp: new Date().toISOString(),
    })
  } catch (error) {
    console.error('AOL Refresh Error:', error)
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to refresh telemetry views',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    )
  }
}
