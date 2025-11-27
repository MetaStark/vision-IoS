/**
 * FINN API Route: Strategy Families
 * Returns all 4 ACE family signals with drivers and confidence
 *
 * Authority: ADR-042 (FINN Intelligence), Phase 2 (Family Consensus)
 * Data Source: fhq_ace.family_consensus + strategy signals
 */

import { NextRequest, NextResponse } from 'next/server'
import { queryMany } from '@/lib/db'

export const dynamic = 'force-dynamic'

interface FamilySignal {
  family_id: string
  family_name: 'TREND_FOLLOWING' | 'MEAN_REVERSION' | 'VOLATILITY' | 'BREAKOUT'
  signal_direction: 'LONG' | 'SHORT' | 'NEUTRAL'
  allocation_pct: number
  confidence_score: number
  conviction_strength: number

  // Drivers (which strategies drive this family signal)
  primary_driver: string | null
  driver_strategies: string[] // Array of strategy names
  strategy_count: number // How many strategies in this family

  // Contribution to meta
  meta_weight: number | null
  meta_contribution_pct: number | null

  // UI metadata
  family_color: string // Semantic color for UI
  family_icon: string // Icon identifier
}

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const listingId = searchParams.get('listing_id') || 'LST_BTC_XCRYPTO'
    const signalDate = searchParams.get('signal_date') // Optional, defaults to latest

    // Query all 4 family signals with their driver strategies
    const query = `
      WITH latest_families AS (
        SELECT
          family_id,
          signal_date,
          listing_id,
          family_name,
          signal_direction,
          allocation_pct,
          confidence_score,
          conviction_strength,
          meta_weight,
          (allocation_pct * meta_weight) AS meta_contribution_pct
        FROM fhq_ace.family_consensus
        WHERE listing_id = $1
          ${signalDate ? 'AND signal_date = $2' : ''}
          AND signal_date = (
            SELECT MAX(signal_date)
            FROM fhq_ace.family_consensus
            WHERE listing_id = $1
              ${signalDate ? 'AND signal_date = $2' : ''}
          )
      ),
      family_drivers AS (
        SELECT
          s.strategy_family,
          s.signal_direction,
          s.strategy_name,
          s.allocation_pct,
          s.confidence_score,
          ROW_NUMBER() OVER (
            PARTITION BY s.strategy_family
            ORDER BY ABS(s.allocation_pct) DESC, s.confidence_score DESC
          ) AS driver_rank
        FROM fhq_ace.strategy_signals s
        WHERE s.listing_id = $1
          AND s.signal_date = (
            SELECT MAX(signal_date)
            FROM fhq_ace.family_consensus
            WHERE listing_id = $1
              ${signalDate ? 'AND signal_date = $2' : ''}
          )
      )
      SELECT
        f.family_id,
        f.family_name,
        f.signal_direction,
        f.allocation_pct,
        f.confidence_score,
        f.conviction_strength,
        f.meta_weight,
        f.meta_contribution_pct,

        -- Primary driver (strongest strategy in family)
        (
          SELECT d.strategy_name
          FROM family_drivers d
          WHERE d.strategy_family = f.family_name AND d.driver_rank = 1
        ) AS primary_driver,

        -- All driver strategies (array)
        ARRAY(
          SELECT d.strategy_name
          FROM family_drivers d
          WHERE d.strategy_family = f.family_name
          ORDER BY d.driver_rank
        ) AS driver_strategies,

        -- Strategy count
        (
          SELECT COUNT(*)
          FROM family_drivers d
          WHERE d.strategy_family = f.family_name
        )::INT AS strategy_count,

        -- UI metadata (semantic colors per family)
        CASE f.family_name
          WHEN 'TREND_FOLLOWING' THEN 'blue'
          WHEN 'MEAN_REVERSION' THEN 'green'
          WHEN 'VOLATILITY' THEN 'yellow'
          WHEN 'BREAKOUT' THEN 'purple'
          ELSE 'gray'
        END AS family_color,

        CASE f.family_name
          WHEN 'TREND_FOLLOWING' THEN 'trend-up'
          WHEN 'MEAN_REVERSION' THEN 'refresh-cw'
          WHEN 'VOLATILITY' THEN 'activity'
          WHEN 'BREAKOUT' THEN 'zap'
          ELSE 'circle'
        END AS family_icon

      FROM latest_families f
      ORDER BY
        CASE f.family_name
          WHEN 'TREND_FOLLOWING' THEN 1
          WHEN 'MEAN_REVERSION' THEN 2
          WHEN 'VOLATILITY' THEN 3
          WHEN 'BREAKOUT' THEN 4
        END
    `

    const params = signalDate ? [listingId, signalDate] : [listingId]
    const results = await queryMany<FamilySignal>(query, params)

    if (results.length === 0) {
      return NextResponse.json(
        {
          error: 'No family signals found',
          listing_id: listingId,
          signal_date: signalDate || 'latest'
        },
        { status: 404 }
      )
    }

    // Add consensus analysis
    const longCount = results.filter(f => f.signal_direction === 'LONG').length
    const shortCount = results.filter(f => f.signal_direction === 'SHORT').length
    const neutralCount = results.filter(f => f.signal_direction === 'NEUTRAL').length

    return NextResponse.json({
      families: results,
      consensus: {
        total: results.length,
        long: longCount,
        short: shortCount,
        neutral: neutralCount,
        alignment: longCount === 4 ? 'STRONG_LONG' :
                   shortCount === 4 ? 'STRONG_SHORT' :
                   longCount > 2 ? 'MODERATE_LONG' :
                   shortCount > 2 ? 'MODERATE_SHORT' :
                   'CONFLICTED',
        finn_interpretation:
          longCount === 4 ? 'All four strategy families align on LONG signals - rare consensus.' :
          shortCount === 4 ? 'All four strategy families align on SHORT signals - rare consensus.' :
          longCount > shortCount ? 'Families lean LONG, but not unanimous.' :
          shortCount > longCount ? 'Families lean SHORT, but not unanimous.' :
          'Strategies are conflicted - typical of transition weeks.'
      }
    })

  } catch (error) {
    console.error('[FINN API] Families error:', error)
    return NextResponse.json(
      {
        error: 'Failed to fetch family signals',
        message: error instanceof Error ? error.message : String(error)
      },
      { status: 500 }
    )
  }
}
