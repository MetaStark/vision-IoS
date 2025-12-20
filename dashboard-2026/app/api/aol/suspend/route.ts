/**
 * AOL Suspend Agent API Endpoint
 * CEO Directive 2026-FHQ-FCC-AOL-01 Section 3.9
 * ADR-009: Governance Approval Workflow for Agent Suspension
 *
 * Authority: ADR-001, ADR-006, ADR-009
 * Classification: CONSTITUTIONAL - Governance Action
 *
 * This endpoint initiates an agent suspension request that requires
 * CEO signature per ADR-009 governance workflow.
 *
 * IMPORTANT: This action is NOT automatic. It creates a governance
 * request that must be approved through the proper workflow.
 */

import { NextRequest, NextResponse } from 'next/server'
import { queryOne, queryMany } from '@/lib/db'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { agent_id, reason, requestor } = body

    // Validate required fields
    if (!agent_id) {
      return NextResponse.json(
        { success: false, error: 'agent_id is required' },
        { status: 400 }
      )
    }

    if (!reason) {
      return NextResponse.json(
        { success: false, error: 'reason is required for ADR-009 compliance' },
        { status: 400 }
      )
    }

    // Verify agent exists and is active
    // Using fhq_meta.agent_keys which has agent_id and status columns
    const agent = await queryOne<any>(`
      SELECT agent_id, status as contract_status, 'OPERATIONAL' as mandate_scope
      FROM fhq_meta.agent_keys
      WHERE agent_id = $1
      LIMIT 1
    `, [agent_id])

    if (!agent) {
      return NextResponse.json(
        { success: false, error: `Agent ${agent_id} not found` },
        { status: 404 }
      )
    }

    if (agent.contract_status !== 'ACTIVE' && agent.contract_status !== 'active') {
      return NextResponse.json(
        { success: false, error: `Agent ${agent_id} is already ${agent.contract_status}` },
        { status: 400 }
      )
    }

    // Get current governance metrics for the agent
    const metrics = await queryOne<any>(`
      SELECT
        COUNT(*) FILTER (WHERE propagation_blocked = true) as blocked_ops
      FROM fhq_governance.causal_entropy_audit
      WHERE executed_by = $1
        AND executed_at >= NOW() - INTERVAL '7 days'
    `, [agent_id])

    const blockedOps = parseInt(metrics?.blocked_ops || '0')

    // Create a governance suspension request (ADR-009 workflow)
    // This creates a pending request that requires CEO approval
    const suspensionRequest = await queryOne<any>(`
      INSERT INTO fhq_governance.governance_actions_log (
        action_type,
        entity_type,
        entity_id,
        requested_by,
        request_reason,
        status,
        metadata,
        created_at
      ) VALUES (
        'AGENT_SUSPENSION',
        'AGENT',
        $1,
        $2,
        $3,
        'PENDING_CEO_APPROVAL',
        $4::jsonb,
        NOW()
      )
      RETURNING action_id, created_at
    `, [
      agent_id,
      requestor || 'FCC_DASHBOARD',
      reason,
      JSON.stringify({
        directive: 'CEO-2026-FHQ-FCC-AOL-01',
        compliance: ['ADR-009'],
        governance_state: blockedOps > 5 ? 'RED' : blockedOps > 0 ? 'YELLOW' : 'GREEN',
        blocked_operations_7d: blockedOps,
        dashboard_initiated: true,
      })
    ])

    return NextResponse.json({
      success: true,
      message: `Suspension request for ${agent_id} created. Pending CEO approval per ADR-009.`,
      timestamp: new Date().toISOString(),
      compliance: ['ADR-009'],
      directive: 'CEO-2026-FHQ-FCC-AOL-01',
      data: {
        action_id: suspensionRequest.action_id,
        agent_id: agent_id,
        status: 'PENDING_CEO_APPROVAL',
        created_at: suspensionRequest.created_at,
        governance_workflow: 'ADR-009 requires CEO signature for agent suspension',
      },
    })
  } catch (error) {
    console.error('AOL Suspend Agent API Error:', error)

    // Check if it's a missing table error
    const errorMessage = error instanceof Error ? error.message : 'Unknown error'
    if (errorMessage.includes('does not exist')) {
      return NextResponse.json(
        {
          success: false,
          error: 'Governance action logging is not yet available',
          message: 'The governance_actions_log table needs to be created',
          compliance_note: 'ADR-009 suspension workflow requires proper infrastructure',
        },
        { status: 503 }
      )
    }

    return NextResponse.json(
      {
        success: false,
        error: 'Failed to create suspension request',
        message: errorMessage,
      },
      { status: 500 }
    )
  }
}

/**
 * GET endpoint to check suspension status for an agent
 */
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const agent_id = searchParams.get('agent_id')

  try {
    if (agent_id) {
      // Get suspension requests for specific agent
      const requests = await queryMany<any>(`
        SELECT
          action_id,
          action_type,
          entity_id as agent_id,
          requested_by,
          request_reason,
          status,
          metadata,
          created_at,
          resolved_at,
          resolved_by
        FROM fhq_governance.governance_actions_log
        WHERE entity_type = 'AGENT'
          AND entity_id = $1
          AND action_type = 'AGENT_SUSPENSION'
        ORDER BY created_at DESC
        LIMIT 10
      `, [agent_id])

      return NextResponse.json({
        success: true,
        timestamp: new Date().toISOString(),
        agent_id,
        data: requests,
      })
    } else {
      // Get all pending suspension requests
      const requests = await queryMany<any>(`
        SELECT
          action_id,
          action_type,
          entity_id as agent_id,
          requested_by,
          request_reason,
          status,
          metadata,
          created_at
        FROM fhq_governance.governance_actions_log
        WHERE entity_type = 'AGENT'
          AND action_type = 'AGENT_SUSPENSION'
          AND status = 'PENDING_CEO_APPROVAL'
        ORDER BY created_at DESC
      `)

      return NextResponse.json({
        success: true,
        timestamp: new Date().toISOString(),
        pending_count: requests.length,
        data: requests,
      })
    }
  } catch (error) {
    console.error('AOL Suspend Status API Error:', error)
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to fetch suspension status',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    )
  }
}
