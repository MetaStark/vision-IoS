/**
 * LVI (Learning Velocity Index) API
 * CEO-DIR-2026-META-ANALYSIS Phase 4
 *
 * Endpoints:
 * - GET: Fetch LVI history and current status
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
  const days = parseInt(searchParams.get('days') || '30')
  const limit = parseInt(searchParams.get('limit') || '100')

  try {
    const client = await pool.connect()
    try {
      // Get LVI history
      const historyResult = await client.query(`
        SELECT
          lvi_id,
          computed_at,
          lvi_score,
          completed_experiments,
          median_evaluation_time_hours,
          coverage_rate,
          integrity_rate,
          time_factor,
          brier_component,
          computation_method
        FROM fhq_ops.control_room_lvi
        WHERE computed_at >= NOW() - INTERVAL '${days} days'
        ORDER BY computed_at DESC
        LIMIT $1
      `, [limit])

      // Get current LVI
      const currentResult = await client.query(`
        SELECT
          lvi_score,
          completed_experiments,
          coverage_rate,
          integrity_rate,
          brier_component,
          computed_at,
          drivers
        FROM fhq_ops.control_room_lvi
        ORDER BY computed_at DESC
        LIMIT 1
      `)

      // Get LVI grade
      const current = currentResult.rows[0]
      let grade = 'F'
      let gradeColor = 'red'
      if (current) {
        const score = parseFloat(current.lvi_score)
        if (score >= 0.8) { grade = 'A'; gradeColor = 'green' }
        else if (score >= 0.6) { grade = 'B'; gradeColor = 'blue' }
        else if (score >= 0.4) { grade = 'C'; gradeColor = 'yellow' }
        else if (score >= 0.2) { grade = 'D'; gradeColor = 'orange' }
        else { grade = 'F'; gradeColor = 'red' }
      }

      // Calculate trend (compare last 2 readings)
      const history = historyResult.rows
      let trend = 'STABLE'
      let trendPct = 0
      if (history.length >= 2) {
        const latest = parseFloat(history[0].lvi_score)
        const previous = parseFloat(history[1].lvi_score)
        if (previous > 0) {
          trendPct = ((latest - previous) / previous) * 100
          if (trendPct > 5) trend = 'IMPROVING'
          else if (trendPct < -5) trend = 'DECLINING'
        }
      }

      return NextResponse.json({
        current: current ? {
          lvi_score: parseFloat(current.lvi_score),
          completed_experiments: current.completed_experiments,
          coverage_rate: parseFloat(current.coverage_rate),
          integrity_rate: parseFloat(current.integrity_rate),
          brier_component: parseFloat(current.brier_component || '0'),
          computed_at: current.computed_at,
          drivers: current.drivers,
          grade,
          gradeColor,
          trend,
          trendPct: Math.round(trendPct * 10) / 10
        } : null,
        history: history.map(row => ({
          computed_at: row.computed_at,
          lvi_score: parseFloat(row.lvi_score),
          completed_experiments: row.completed_experiments,
          coverage_rate: parseFloat(row.coverage_rate),
          integrity_rate: parseFloat(row.integrity_rate),
          brier_component: parseFloat(row.brier_component || '0')
        })),
        timestamp: new Date().toISOString()
      })
    } finally {
      client.release()
    }
  } catch (error) {
    console.error('[LVI API] Error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch LVI data' },
      { status: 500 }
    )
  }
}
