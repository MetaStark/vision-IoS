/**
 * Oracle Staging API Endpoint
 * POST /api/oracle/staging
 *
 * Submits narrative vectors to staging table for VEGA review
 * Does NOT write directly to narrative_vectors (G0 -> G1 governance)
 *
 * Authority: G1 UI Governance Patch, IoS-009
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

interface StagingSubmission {
  domain: string
  narrative: string
  probability: number
  confidence: number
  halfLifeHours: number
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as StagingSubmission
    const { domain, narrative, probability, confidence, halfLifeHours } = body

    // Validate inputs
    if (!domain || !narrative) {
      return NextResponse.json(
        { success: false, error: 'Domain and narrative are required' },
        { status: 400 }
      )
    }

    if (probability < 0 || probability > 1) {
      return NextResponse.json(
        { success: false, error: 'Probability must be between 0 and 1' },
        { status: 400 }
      )
    }

    if (confidence < 0 || confidence > 1) {
      return NextResponse.json(
        { success: false, error: 'Confidence must be between 0 and 1' },
        { status: 400 }
      )
    }

    const client = await pool.connect()
    try {
      // Check if oracle_staging table exists, create if not
      await client.query(`
        CREATE TABLE IF NOT EXISTS fhq_governance.oracle_staging (
          submission_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          domain TEXT NOT NULL,
          narrative TEXT NOT NULL,
          probability NUMERIC(4,3) NOT NULL CHECK (probability >= 0 AND probability <= 1),
          confidence NUMERIC(4,3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
          half_life_hours INTEGER NOT NULL DEFAULT 24,
          submitted_by TEXT NOT NULL DEFAULT 'CEO',
          submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          review_status TEXT NOT NULL DEFAULT 'PENDING',
          reviewed_by TEXT,
          reviewed_at TIMESTAMPTZ,
          rejection_reason TEXT,
          promoted_to_vector_id UUID,
          CONSTRAINT valid_review_status CHECK (review_status IN ('PENDING', 'APPROVED', 'REJECTED', 'PROMOTED'))
        )
      `)

      // Insert the submission
      const result = await client.query(
        `INSERT INTO fhq_governance.oracle_staging (
          domain, narrative, probability, confidence, half_life_hours, submitted_by
        ) VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING submission_id, submitted_at`,
        [domain, narrative, probability, confidence, halfLifeHours, 'CEO']
      )

      const submission = result.rows[0]

      // Log to governance
      await client.query(
        `INSERT INTO fhq_governance.governance_actions_log (
          action_type, action_target, action_target_type, initiated_by,
          decision, decision_rationale, hash_chain_id
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)`,
        [
          'G0_NARRATIVE_SUBMISSION',
          submission.submission_id,
          'ORACLE_STAGING',
          'CEO',
          'PENDING_REVIEW',
          `Domain: ${domain} | Probability: ${probability} | Confidence: ${confidence} | Half-Life: ${halfLifeHours}h`,
          `HC-G0-${new Date().toISOString().split('T')[0]}`,
        ]
      )

      return NextResponse.json({
        success: true,
        submissionId: submission.submission_id,
        submittedAt: submission.submitted_at,
        status: 'PENDING',
        message: 'Submission routed to oracle_staging for VEGA G1 review',
      })
    } finally {
      client.release()
    }
  } catch (error) {
    console.error('Oracle staging error:', error)
    return NextResponse.json(
      {
        success: false,
        error: error instanceof Error ? error.message : 'Submission failed',
      },
      { status: 500 }
    )
  }
}

/**
 * GET /api/oracle/staging
 * List pending submissions
 */
export async function GET() {
  try {
    const client = await pool.connect()
    try {
      const result = await client.query(`
        SELECT
          submission_id,
          domain,
          narrative,
          probability,
          confidence,
          half_life_hours,
          submitted_by,
          submitted_at,
          review_status,
          reviewed_by,
          reviewed_at
        FROM fhq_governance.oracle_staging
        ORDER BY submitted_at DESC
        LIMIT 50
      `)

      return NextResponse.json({
        success: true,
        submissions: result.rows,
        count: result.rowCount,
      })
    } finally {
      client.release()
    }
  } catch (error) {
    console.error('Oracle staging fetch error:', error)
    return NextResponse.json(
      {
        success: false,
        error: error instanceof Error ? error.message : 'Fetch failed',
        submissions: [],
      },
      { status: 500 }
    )
  }
}
