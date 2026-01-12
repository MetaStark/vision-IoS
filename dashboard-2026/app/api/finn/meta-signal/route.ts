/**
 * FINN API Route: Meta Signal
 * Returns today's meta allocation with FINN narrative
 *
 * Authority: ADR-042 (FINN Intelligence), ADR-045 (Dashboard Integration)
 * Data Source: fhq_ace.meta_allocations + FINN narrative generator
 *
 * CEO-DIR-2026-TRUTH-SYNC-P1: Re-wired regime source from fhq_hmm.regime_predictions
 * to fhq_perception.sovereign_regime_state_v4 (canonical truth source)
 * Change Record: CHANGE_RECORD_META_SIGNAL_REWIRE.json
 */

import { NextRequest, NextResponse } from 'next/server'
import { queryOne, query } from '@/lib/db'

export const dynamic = 'force-dynamic' // Disable caching for real-time data

interface MetaSignalResponse {
  signal_date: string
  listing_id: string

  // Meta allocation
  allocation_pct: number
  direction: 'LONG' | 'SHORT' | 'NEUTRAL'
  signal_strength: number

  // Regime context (CEO-DIR-2026-TRUTH-SYNC-P1: from fhq_perception.sovereign_regime_state_v4)
  regime_label: 'BULL' | 'NEUTRAL' | 'BEAR' | 'STRESS' | null
  regime_confidence: number | null
  technical_regime: 'BULL' | 'NEUTRAL' | 'BEAR' | 'STRESS' | null
  crio_dominant_driver: string | null
  regime_date: string | null

  // Risk gates
  risk_gates_passed: boolean
  risk_block_reason: string | null

  // FINN narrative (3-layer framework)
  finn_narrative: string

  // Integrity (REGIME_LIVE_SIGNAL_STALE = regime is fresh but ACE signal is stale)
  integrity_status: 'VERIFIED' | 'UNVERIFIED' | 'STALE' | 'REGIME_LIVE_SIGNAL_STALE'

  // Hash-of-Truth attestation (CEO-DIR-2026-TRUTH-SYNC-P1, ADR-019 Dumb Glass)
  _truth_attestation?: {
    attestation_id: string
    truth_hash: string
    canonical_json: string
    attestation_date: string
    source_table: string
    verification_url: string
  }
}

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const listingId = searchParams.get('listing_id') || 'LST_BTC_XCRYPTO'
    const signalDate = searchParams.get('signal_date') // Optional, defaults to latest

    // Query meta allocation with regime context
    const metaSignalQuery = `
      WITH latest_meta AS (
        SELECT
          meta_id,
          signal_date,
          listing_id,
          allocation_pct,
          CASE
            WHEN allocation_pct > 5 THEN 'LONG'
            WHEN allocation_pct < -5 THEN 'SHORT'
            ELSE 'NEUTRAL'
          END AS direction,
          signal_strength,
          confidence_score,
          risk_gates_passed,
          risk_block_reason,
          created_at
        FROM fhq_ace.meta_allocations
        WHERE listing_id = $1
          ${signalDate ? 'AND signal_date = $2' : ''}
        ORDER BY signal_date DESC, created_at DESC
        LIMIT 1
      ),
      -- CEO-DIR-2026-TRUTH-SYNC-P1: Canonical regime source (was fhq_hmm.regime_predictions)
      regime_context AS (
        SELECT
          sovereign_regime AS regime_label,
          GREATEST(
            COALESCE((state_probabilities->>'BULL')::numeric, 0),
            COALESCE((state_probabilities->>'NEUTRAL')::numeric, 0),
            COALESCE((state_probabilities->>'BEAR')::numeric, 0),
            COALESCE((state_probabilities->>'STRESS')::numeric, 0)
          ) AS confidence,
          technical_regime,
          crio_dominant_driver,
          timestamp AS regime_date
        FROM fhq_perception.sovereign_regime_state_v4
        WHERE asset_id = (
          CASE
            WHEN $1 LIKE 'LST_%_XCRYPTO' THEN SPLIT_PART($1, '_', 2) || '-USD'
            WHEN $1 LIKE 'LST_%' THEN SPLIT_PART($1, '_', 2)
            ELSE $1
          END
        )
          ${signalDate ? 'AND timestamp = $2::date' : ''}
        ORDER BY timestamp DESC, created_at DESC
        LIMIT 1
      ),
      family_signals AS (
        SELECT
          family_name,
          signal_direction
        FROM fhq_ace.family_consensus
        WHERE listing_id = $1
          AND signal_date = (SELECT signal_date FROM latest_meta)
      )
      SELECT
        m.signal_date,
        m.listing_id,
        m.allocation_pct,
        m.direction,
        m.signal_strength,
        r.regime_label,
        r.confidence AS regime_confidence,
        m.risk_gates_passed,
        m.risk_block_reason,

        -- Generate FINN narrative (3-layer framework)
        CASE
          WHEN m.risk_gates_passed = FALSE THEN
            format(
              'BTC is in a %s regime. Due to %s, I''m keeping you defensive today.',
              COALESCE(LOWER(r.regime_label), 'uncertain'),
              COALESCE(LOWER(m.risk_block_reason), 'risk constraints')
            )
          WHEN m.allocation_pct > 50 THEN
            format(
              'BTC is in a %s regime with strong upside momentum. All strategy families align on LONG signals - rare consensus. I''m positioning %s%% long with high conviction.',
              COALESCE(LOWER(r.regime_label), 'bull'),
              ROUND(m.allocation_pct)::TEXT
            )
          WHEN m.allocation_pct < -50 THEN
            format(
              'BTC is in a %s regime with strong downside momentum. All strategy families align on SHORT signals - rare consensus. I''m positioning %s%% short with high conviction.',
              COALESCE(LOWER(r.regime_label), 'bear'),
              ROUND(ABS(m.allocation_pct))::TEXT
            )
          WHEN m.allocation_pct > 20 THEN
            format(
              'BTC is in a %s regime with upside bias. Strategy families show moderate consensus. I''m leaning %s%% long.',
              COALESCE(LOWER(r.regime_label), 'neutral'),
              ROUND(m.allocation_pct)::TEXT
            )
          WHEN m.allocation_pct < -20 THEN
            format(
              'BTC is in a %s regime with downside bias. Strategy families show moderate consensus. I''m leaning %s%% short.',
              COALESCE(LOWER(r.regime_label), 'neutral'),
              ROUND(ABS(m.allocation_pct))::TEXT
            )
          ELSE
            format(
              'BTC is in a %s phase with weak directional bias. Strategies are conflicted - typical of transition weeks. Staying neutral until signals align.',
              COALESCE(LOWER(r.regime_label), 'neutral')
            )
        END AS finn_narrative,

        -- Integrity check (data freshness) - considers both signal and regime
        CASE
          WHEN m.signal_date >= CURRENT_DATE - INTERVAL '2 days'
               AND r.regime_date >= CURRENT_DATE - INTERVAL '2 days' THEN 'VERIFIED'
          WHEN m.signal_date >= CURRENT_DATE - INTERVAL '7 days'
               AND r.regime_date >= CURRENT_DATE - INTERVAL '7 days' THEN 'STALE'
          WHEN r.regime_date >= CURRENT_DATE - INTERVAL '2 days' THEN 'REGIME_LIVE_SIGNAL_STALE'
          ELSE 'UNVERIFIED'
        END AS integrity_status,

        -- Additional regime context (CEO-DIR-2026-TRUTH-SYNC-P1)
        r.technical_regime,
        r.crio_dominant_driver,
        r.regime_date

      FROM latest_meta m
      LEFT JOIN regime_context r ON TRUE
    `

    const params = signalDate ? [listingId, signalDate] : [listingId]
    const result = await queryOne<MetaSignalResponse>(metaSignalQuery, params)

    if (!result) {
      return NextResponse.json(
        {
          error: 'No meta signal found',
          listing_id: listingId,
          signal_date: signalDate || 'latest'
        },
        { status: 404 }
      )
    }

    // CEO-DIR-2026-TRUTH-SYNC-P1: Create Hash-of-Truth attestation (ADR-019 Dumb Glass)
    // This provides cryptographic proof that displayed data was computed server-side
    let truthAttestation = null
    try {
      // Normalize listing_id to asset_id for attestation
      const assetId = listingId.startsWith('LST_') && listingId.includes('_XCRYPTO')
        ? listingId.split('_')[1] + '-USD'
        : listingId.startsWith('LST_')
        ? listingId.split('_')[1]
        : listingId

      // Create attestation using the database function (two-step for visibility)
      // Step 1: Create attestation and get ID
      const createQuery = `
        SELECT vision_verification.create_truth_attestation(
          '/api/finn/meta-signal',
          $1,
          $2,
          $3::date,
          $4::numeric,
          $5::numeric,
          'fhq_perception.sovereign_regime_state_v4',
          'SELECT * FROM fhq_perception.sovereign_regime_state_v4 WHERE asset_id = ''' || $1 || ''' ORDER BY timestamp DESC LIMIT 1',
          NULL
        ) AS attestation_id
      `
      const createResult = await queryOne<{ attestation_id: string }>(createQuery, [
        assetId,
        result.regime_label,
        result.regime_date,
        result.allocation_pct || 0,
        result.signal_strength || 0
      ])

      // Step 2: Fetch attestation details
      let attestationResult = null
      if (createResult?.attestation_id) {
        const fetchQuery = `
          SELECT
            attestation_id::text,
            truth_hash,
            canonical_json,
            attestation_date::text,
            source_table
          FROM vision_verification.dashboard_truth_attestation
          WHERE attestation_id = $1::uuid
        `
        attestationResult = await queryOne<{
          attestation_id: string
          truth_hash: string
          canonical_json: string
          attestation_date: string
          source_table: string
        }>(fetchQuery, [createResult.attestation_id])
      }

      if (attestationResult) {
        truthAttestation = {
          ...attestationResult,
          verification_url: `/api/finn/verify-attestation?id=${attestationResult.attestation_id}`
        }
      }
    } catch (attestationError) {
      // Log but don't fail the request if attestation creation fails
      console.warn('[FINN API] Attestation creation warning:', attestationError)
    }

    return NextResponse.json({
      ...result,
      _truth_attestation: truthAttestation
    })

  } catch (error) {
    console.error('[FINN API] Meta signal error:', error)
    return NextResponse.json(
      {
        error: 'Failed to fetch meta signal',
        message: error instanceof Error ? error.message : String(error)
      },
      { status: 500 }
    )
  }
}
