/**
 * Direct SQL Query API Endpoint
 * POST /api/engine/query
 *
 * Executes read-only SQL queries with safety checks
 * Authority: ADR-019, ceo_read_only role
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

// Forbidden SQL patterns
const FORBIDDEN_PATTERNS = [
  /\bINSERT\b/i,
  /\bUPDATE\b/i,
  /\bDELETE\b/i,
  /\bDROP\b/i,
  /\bCREATE\b/i,
  /\bALTER\b/i,
  /\bTRUNCATE\b/i,
  /\bGRANT\b/i,
  /\bREVOKE\b/i,
  /\bEXECUTE\b/i,
  /\bCALL\b/i,
]

function isSafeQuery(sql: string): boolean {
  for (const pattern of FORBIDDEN_PATTERNS) {
    if (pattern.test(sql)) {
      return false
    }
  }
  return true
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { sql } = body

    if (!sql) {
      return NextResponse.json(
        { success: false, error: 'SQL query is required' },
        { status: 400 }
      )
    }

    if (!isSafeQuery(sql)) {
      return NextResponse.json(
        { success: false, error: 'SAFETY VIOLATION: Only SELECT queries are permitted.' },
        { status: 403 }
      )
    }

    const client = await pool.connect()
    try {
      const startTime = Date.now()
      const result = await client.query(sql)
      const duration = Date.now() - startTime

      // Log query to governance
      try {
        await client.query(
          `INSERT INTO fhq_governance.governance_actions_log (
            action_type, action_target, action_target_type, initiated_by,
            decision, decision_rationale, hash_chain_id
          ) VALUES ($1, $2, $3, $4, $5, $6, $7)`,
          [
            'DIRECT_SQL_QUERY',
            'engine/query',
            'CEO_QUERY',
            'CEO',
            'EXECUTED',
            `SQL: ${sql.substring(0, 200)}... | Rows: ${result.rowCount} | Duration: ${duration}ms`,
            `HC-QUERY-${new Date().toISOString().split('T')[0]}`,
          ]
        )
      } catch (logError) {
        console.error('Failed to log query:', logError)
      }

      return NextResponse.json({
        success: true,
        rows: result.rows,
        rowCount: result.rowCount,
        duration,
      })
    } finally {
      client.release()
    }
  } catch (error) {
    console.error('Query error:', error)
    return NextResponse.json(
      {
        success: false,
        error: error instanceof Error ? error.message : 'Query failed',
      },
      { status: 500 }
    )
  }
}
