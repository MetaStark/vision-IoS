/**
 * Alpaca Positions API Route
 * ==========================
 * Fetches live positions from Alpaca Paper Trading
 */

import { NextResponse } from 'next/server'

const ALPACA_API_KEY = process.env.ALPACA_API_KEY || ''
const ALPACA_SECRET = process.env.ALPACA_SECRET || process.env.ALPACA_SECRET_KEY || ''
const ALPACA_BASE_URL = 'https://paper-api.alpaca.markets'

// Disable Next.js caching for this route
export const dynamic = 'force-dynamic'
export const revalidate = 0

export async function GET() {
  try {
    if (!ALPACA_API_KEY || !ALPACA_SECRET) {
      return NextResponse.json({ error: 'Alpaca not configured', positions: [] })
    }

    // Fetch positions from Alpaca with no-cache
    const positionsRes = await fetch(`${ALPACA_BASE_URL}/v2/positions`, {
      headers: {
        'APCA-API-KEY-ID': ALPACA_API_KEY,
        'APCA-API-SECRET-KEY': ALPACA_SECRET,
      },
      cache: 'no-store',
    })

    if (!positionsRes.ok) {
      throw new Error(`Alpaca API error: ${positionsRes.status}`)
    }

    const positions = await positionsRes.json()

    // Fetch account info with no-cache
    const accountRes = await fetch(`${ALPACA_BASE_URL}/v2/account`, {
      headers: {
        'APCA-API-KEY-ID': ALPACA_API_KEY,
        'APCA-API-SECRET-KEY': ALPACA_SECRET,
      },
      cache: 'no-store',
    })

    const account = await accountRes.json()

    // Transform to our format
    const transformedPositions = positions.map((pos: any) => ({
      symbol: pos.symbol,
      qty: parseFloat(pos.qty),
      avgEntryPrice: parseFloat(pos.avg_entry_price),
      currentPrice: parseFloat(pos.current_price),
      marketValue: parseFloat(pos.market_value),
      unrealizedPl: parseFloat(pos.unrealized_pl),
      unrealizedPlPct: parseFloat(pos.unrealized_plpc) * 100,
      side: pos.side,
      changeToday: parseFloat(pos.change_today) * 100,
    }))

    const response = NextResponse.json({
      positions: transformedPositions,
      account: {
        portfolioValue: parseFloat(account.portfolio_value),
        cash: parseFloat(account.cash),
        buyingPower: parseFloat(account.buying_power),
        dayPl: parseFloat(account.equity) - parseFloat(account.last_equity),
        dayPlPct: ((parseFloat(account.equity) - parseFloat(account.last_equity)) / parseFloat(account.last_equity)) * 100,
      },
      timestamp: new Date().toISOString(),
    })

    // Prevent any caching
    response.headers.set('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
    response.headers.set('Pragma', 'no-cache')

    return response
  } catch (error) {
    console.error('Alpaca Positions API error:', error)
    return NextResponse.json(
      { error: String(error), positions: [], timestamp: new Date().toISOString() },
      { status: 500 }
    )
  }
}
