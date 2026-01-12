/**
 * FINN API Route: Verify Attestation
 * Verifies a Hash-of-Truth attestation for dashboard metrics
 *
 * Authority: CEO-DIR-2026-TRUTH-SYNC-P1, ADR-019 (Dumb Glass)
 * Purpose: Provides cryptographic proof verification that displayed data was computed server-side
 */

import { NextRequest, NextResponse } from 'next/server'
import { queryOne } from '@/lib/db'

export const dynamic = 'force-dynamic'

interface VerificationResult {
  attestation_id: string
  is_valid: boolean
  computed_hash: string
  stored_hash: string
  mismatch_reason: string | null
  attestation_details: {
    route_path: string
    listing_id: string
    attestation_date: string
    regime_label: string | null
    regime_date: string | null
    allocation_pct: number | null
    signal_strength: number | null
    canonical_json: string
    source_table: string
    created_at: string
  } | null
}

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const attestationId = searchParams.get('id')

    if (!attestationId) {
      return NextResponse.json(
        {
          error: 'Missing attestation ID',
          usage: '/api/finn/verify-attestation?id=<attestation_uuid>'
        },
        { status: 400 }
      )
    }

    // Verify the attestation using the database function
    const verificationQuery = `
      WITH verification AS (
        SELECT * FROM vision_verification.verify_truth_attestation($1::uuid)
      ),
      attestation_details AS (
        SELECT
          route_path,
          listing_id,
          attestation_date::text,
          regime_label,
          regime_date::text,
          allocation_pct,
          signal_strength,
          canonical_json,
          source_table,
          created_at::text
        FROM vision_verification.dashboard_truth_attestation
        WHERE attestation_id = $1::uuid
      )
      SELECT
        $1::text AS attestation_id,
        v.is_valid,
        v.computed_hash,
        v.stored_hash,
        v.mismatch_reason,
        jsonb_build_object(
          'route_path', a.route_path,
          'listing_id', a.listing_id,
          'attestation_date', a.attestation_date,
          'regime_label', a.regime_label,
          'regime_date', a.regime_date,
          'allocation_pct', a.allocation_pct,
          'signal_strength', a.signal_strength,
          'canonical_json', a.canonical_json,
          'source_table', a.source_table,
          'created_at', a.created_at
        ) AS attestation_details
      FROM verification v
      LEFT JOIN attestation_details a ON TRUE
    `

    const result = await queryOne<{
      attestation_id: string
      is_valid: boolean
      computed_hash: string
      stored_hash: string
      mismatch_reason: string | null
      attestation_details: object | null
    }>(verificationQuery, [attestationId])

    if (!result) {
      return NextResponse.json(
        {
          error: 'Attestation not found',
          attestation_id: attestationId
        },
        { status: 404 }
      )
    }

    return NextResponse.json({
      attestation_id: result.attestation_id,
      verification_status: result.is_valid ? 'VALID' : 'INVALID',
      is_valid: result.is_valid,
      computed_hash: result.computed_hash,
      stored_hash: result.stored_hash,
      mismatch_reason: result.mismatch_reason,
      attestation_details: result.attestation_details,
      _meta: {
        verified_at: new Date().toISOString(),
        verification_method: 'SHA-256 hash recomputation',
        authority: 'CEO-DIR-2026-TRUTH-SYNC-P1, ADR-019'
      }
    })

  } catch (error) {
    console.error('[FINN API] Verify attestation error:', error)
    return NextResponse.json(
      {
        error: 'Failed to verify attestation',
        message: error instanceof Error ? error.message : String(error)
      },
      { status: 500 }
    )
  }
}
