/**
 * Market Data API Route (Sprint 1.3)
 * Fetch OHLCV price series data
 * Supports: asset selection, resolution, date range
 */

import { NextRequest, NextResponse } from 'next/server'
import { getPriceSeries } from '@/lib/data/market'
import type { Asset } from '@/components/controls/AssetSelector'
import type { Resolution } from '@/components/controls/ResolutionSelector'

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams

  const ticker = searchParams.get('ticker') as Asset
  const resolution = searchParams.get('resolution') as Resolution
  const startDateStr = searchParams.get('startDate')
  const endDateStr = searchParams.get('endDate')

  // Validation
  if (!ticker || !resolution || !startDateStr || !endDateStr) {
    return NextResponse.json(
      { error: 'Missing required parameters: ticker, resolution, startDate, endDate' },
      { status: 400 }
    )
  }

  if (!['BTC-USD', 'ETH-USD', 'GSPC'].includes(ticker)) {
    return NextResponse.json({ error: 'Invalid ticker' }, { status: 400 })
  }

  if (!['1h', '1d'].includes(resolution)) {
    return NextResponse.json({ error: 'Invalid resolution' }, { status: 400 })
  }

  try {
    const startDate = new Date(startDateStr)
    const endDate = new Date(endDateStr)

    if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
      return NextResponse.json({ error: 'Invalid date format' }, { status: 400 })
    }

    // Fetch data
    const data = await getPriceSeries(ticker, resolution, startDate, endDate)

    return NextResponse.json(data, {
      headers: {
        'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600',
      },
    })
  } catch (error) {
    console.error('Error in price-series API route:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
