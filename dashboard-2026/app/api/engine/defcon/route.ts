/**
 * DEFCON Level API Endpoint
 * GET /api/engine/defcon
 *
 * Returns current system DEFCON level from shared_state_snapshots
 * Authority: ADR-016 DEFCON & Circuit Breaker Protocol
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
      // Get latest valid shared state snapshot
      const result = await client.query(`
        SELECT
          defcon_level,
          btc_regime_label as current_regime,
          state_vector_hash as snapshot_hash,
          created_at
        FROM fhq_governance.shared_state_snapshots
        WHERE is_valid = TRUE
        ORDER BY created_at DESC
        LIMIT 1
      `)

      if (result.rows.length === 0) {
        return NextResponse.json({
          level: 'GREEN',
          regime: 'UNKNOWN',
          source: 'default',
          timestamp: new Date().toISOString(),
        })
      }

      const snapshot = result.rows[0]

      return NextResponse.json({
        level: snapshot.defcon_level || 'GREEN',
        regime: snapshot.current_regime || 'UNKNOWN',
        source: 'shared_state_snapshots',
        hash: snapshot.snapshot_hash,
        timestamp: snapshot.created_at,
      })
    } finally {
      client.release()
    }
  } catch (error) {
    console.error('DEFCON fetch error:', error)
    // Return safe default on error
    return NextResponse.json({
      level: 'GREEN',
      regime: 'UNKNOWN',
      source: 'fallback',
      timestamp: new Date().toISOString(),
    })
  }
}
