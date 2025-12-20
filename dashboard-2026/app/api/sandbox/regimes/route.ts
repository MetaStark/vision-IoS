/**
 * HMM Regime Data API Route
 * Fetches latest regime classification from fhq_perception.regime_daily
 */

import { NextResponse } from 'next/server'
import { queryMany } from '@/lib/db'

interface RegimeData {
  asset_id: string
  date: string
  regime_classification: string
  regime_confidence: number
  regime_stability_flag: boolean
  consecutive_confirms: number
}

export async function GET() {
  try {
    // Get latest regime for each asset
    const regimes = await queryMany<RegimeData>(`
      WITH latest_regimes AS (
        SELECT
          asset_id,
          timestamp::date::text as date,
          regime_classification,
          regime_confidence,
          regime_stability_flag,
          consecutive_confirms,
          ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY timestamp DESC) as rn
        FROM fhq_perception.regime_daily
      )
      SELECT
        asset_id,
        date,
        regime_classification,
        regime_confidence,
        regime_stability_flag,
        consecutive_confirms
      FROM latest_regimes
      WHERE rn = 1
      ORDER BY asset_id
    `)

    return NextResponse.json(regimes || [], {
      headers: {
        'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600',
      },
    })
  } catch (error) {
    console.error('Error fetching regime data:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
