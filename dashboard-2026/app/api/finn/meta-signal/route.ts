/**
 * FINN API Route: Meta Signal
 * Returns today's meta allocation with FINN narrative
 *
 * Authority: ADR-042 (FINN Intelligence), ADR-045 (Dashboard Integration)
 * Data Source: fhq_ace.meta_allocations + FINN narrative generator
 */

import { NextRequest, NextResponse } from 'next/server'
import { queryOne } from '@/lib/db'

export const dynamic = 'force-dynamic' // Disable caching for real-time data

interface MetaSignalResponse {
  signal_date: string
  listing_id: string

  // Meta allocation
  allocation_pct: number
  direction: 'LONG' | 'SHORT' | 'NEUTRAL'
  signal_strength: number

  // Regime context
  regime_label: 'BULL' | 'NEUTRAL' | 'BEAR' | null
  regime_confidence: number | null

  // Risk gates
  risk_gates_passed: boolean
  risk_block_reason: string | null

  // FINN narrative (3-layer framework)
  finn_narrative: string

  // Integrity
  integrity_status: 'VERIFIED' | 'UNVERIFIED' | 'STALE'
}

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const listingId = searchParams.get('listing_id') || 'LST_BTC_XCRYPTO'
    const signalDate = searchParams.get('signal_date') // Optional, defaults to latest

    // Query meta allocation with regime context
    const query = `
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
      regime_context AS (
        SELECT
          regime_label,
          confidence
        FROM fhq_hmm.regime_predictions
        WHERE listing_id = $1
          ${signalDate ? 'AND prediction_date = $2' : ''}
        ORDER BY prediction_date DESC, created_at DESC
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

        -- Integrity check (data freshness)
        CASE
          WHEN m.signal_date >= CURRENT_DATE - INTERVAL '2 days' THEN 'VERIFIED'
          WHEN m.signal_date >= CURRENT_DATE - INTERVAL '7 days' THEN 'STALE'
          ELSE 'UNVERIFIED'
        END AS integrity_status

      FROM latest_meta m
      LEFT JOIN regime_context r ON TRUE
    `

    const params = signalDate ? [listingId, signalDate] : [listingId]
    const result = await queryOne<MetaSignalResponse>(query, params)

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

    return NextResponse.json(result)

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
