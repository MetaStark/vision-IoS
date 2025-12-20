/**
 * IoS Registry API Route
 * Fetches all Intelligence Operating System modules from fhq_meta.ios_registry
 */

import { NextResponse } from 'next/server'
import { queryMany } from '@/lib/db'

interface IosModule {
  ios_id: string
  title: string
  description: string
  status: string
  owner_role: string
  governance_state: string
}

// Human-readable role explanations (max 2 sentences)
const IOS_ROLES: Record<string, string> = {
  'IoS-001': 'Master registry of all tradeable assets, exchanges, and market contexts. The foundation layer that defines what the system can see and trade.',
  'IoS-002': 'Computes technical indicators (RSI, MACD, Bollinger Bands) from raw price data. The sensory layer that transforms candles into quantitative signals.',
  'IoS-003': 'Hidden Markov Model that classifies market regimes (Bull/Bear/Neutral). The brain that perceives whether markets are risk-on or risk-off.',
  'IoS-004': 'Converts regime classifications into portfolio allocation weights. Determines how much capital to deploy based on current market state.',
  'IoS-005': 'Statistical validation engine that tests if strategies have real predictive power. Guards against overfitting by requiring p < 0.02 significance.',
  'IoS-006': 'Integrates macro-economic factors (M2, VIX, yield curves) into the signal pipeline. Tests which global variables actually predict crypto prices.',
  'IoS-007': 'Causal reasoning graph that models cross-asset relationships. Maps how macro factors flow through regimes to drive asset returns.',
  'IoS-008': 'Real-time decision engine that combines all signals into trade recommendations. The moment-by-moment brain that decides to buy, hold, or sell.',
  'IoS-009': 'Advanced perception layer for market intent, stress detection, and reflexivity. Detects when markets are acting abnormally or showing herd behavior.',
  'IoS-010': 'Audit ledger that records all forecasts and tracks their accuracy over time. Measures if the system is actually getting predictions right.',
  'IoS-011': 'Technical analysis pipeline for chart patterns and trend detection. Classical TA methods as a sanity check against quantitative signals.',
  'IoS-012': 'Order execution engine that interfaces with exchanges via APIs. Translates portfolio decisions into actual buy/sell orders with proper sizing.',
  'IoS-013.HCP-LAB': 'High-convexity options laboratory for asymmetric bets. Paper trading environment for testing leveraged and derivatives strategies.',
}

export async function GET() {
  try {
    const modules = await queryMany<IosModule>(`
      SELECT
        ios_id,
        title,
        description,
        status,
        owner_role,
        governance_state
      FROM fhq_meta.ios_registry
      ORDER BY ios_id
    `)

    // Add human-readable roles
    const enrichedModules = modules?.map(m => ({
      ...m,
      human_role: IOS_ROLES[m.ios_id] || 'No description available.',
    })) || []

    return NextResponse.json(enrichedModules, {
      headers: {
        'Cache-Control': 'public, s-maxage=600, stale-while-revalidate=1200',
      },
    })
  } catch (error) {
    console.error('Error fetching IoS registry:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
