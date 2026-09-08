/**
 * Control Room Alerts API
 * CEO-DIR-2026-META-ANALYSIS Phase 4
 *
 * Endpoints:
 * - GET: Fetch all alerts with optional filters
 * - PATCH: Update alert resolution status
 */

import { NextRequest, NextResponse } from 'next/server'
import { Pool } from 'pg'

const pool = new Pool({
  host: process.env.PGHOST || '127.0.0.1',
  port: parseInt(process.env.PGPORT || '54322'),
  database: process.env.PGDATABASE || 'postgres',
  user: process.env.PGUSER || 'postgres',
  password: process.env.PGPASSWORD || 'postgres',
})

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const severity = searchParams.get('severity')
  const resolved = searchParams.get('resolved')
  const limit = parseInt(searchParams.get('limit') || '50')

  try {
    let query = `
      SELECT
        alert_id,
        alert_type,
        alert_severity,
        alert_message,
        alert_source,
        is_resolved,
        created_at,
        resolved_at,
        resolved_by,
        resolution_notes,
        auto_generated,
        EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600 as hours_since_created
      FROM fhq_ops.control_room_alerts
      WHERE 1=1
    `
    const params: any[] = []
    let paramIndex = 1

    if (severity) {
      query += ` AND alert_severity = $${paramIndex++}`
      params.push(severity.toUpperCase())
    }

    if (resolved !== null) {
      query += ` AND is_resolved = $${paramIndex++}`
      params.push(resolved === 'true')
    }

    query += ` ORDER BY
      CASE alert_severity
        WHEN 'CRITICAL' THEN 1
        WHEN 'WARNING' THEN 2
        WHEN 'INFO' THEN 3
        ELSE 4
      END,
      created_at DESC
      LIMIT $${paramIndex}`
    params.push(limit)

    const client = await pool.connect()
    try {
      const result = await client.query(query, params)

      // Get summary stats
      const statsResult = await client.query(`
        SELECT
          COUNT(*) FILTER (WHERE NOT is_resolved) as active_count,
          COUNT(*) FILTER (WHERE alert_severity = 'CRITICAL' AND NOT is_resolved) as critical_count,
          COUNT(*) FILTER (WHERE alert_severity = 'WARNING' AND NOT is_resolved) as warning_count,
          COUNT(*) FILTER (WHERE is_resolved) as resolved_count,
          COUNT(*) as total_count
        FROM fhq_ops.control_room_alerts
      `)

      return NextResponse.json({
        alerts: result.rows,
        summary: statsResult.rows[0],
        timestamp: new Date().toISOString()
      })
    } finally {
      client.release()
    }
  } catch (error) {
    console.error('[Alerts API] Error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch alerts' },
      { status: 500 }
    )
  }
}

export async function PATCH(request: NextRequest) {
  try {
    const body = await request.json()
    const { alert_id, is_resolved, resolved_by, resolution_notes } = body

    if (!alert_id) {
      return NextResponse.json(
        { error: 'alert_id is required' },
        { status: 400 }
      )
    }

    const client = await pool.connect()
    try {
      const result = await client.query(
        `UPDATE fhq_ops.control_room_alerts
         SET is_resolved = $1,
             resolved_at = CASE WHEN $1 THEN NOW() ELSE NULL END,
             resolved_by = $2,
             resolution_notes = $3
         WHERE alert_id = $4
         RETURNING *`,
        [is_resolved, resolved_by || 'DASHBOARD_USER', resolution_notes, alert_id]
      )

      if (result.rowCount === 0) {
        return NextResponse.json(
          { error: 'Alert not found' },
          { status: 404 }
        )
      }

      return NextResponse.json({
        success: true,
        alert: result.rows[0]
      })
    } finally {
      client.release()
    }
  } catch (error) {
    console.error('[Alerts API] Update error:', error)
    return NextResponse.json(
      { error: 'Failed to update alert' },
      { status: 500 }
    )
  }
}
