/**
 * LLM Balance API - Live balance fetching from DeepSeek
 * FjordHQ IoS - ADR-012 Economic Safety Compliance
 *
 * GET /api/aol/llm-balance - Returns current LLM provider balance
 */

import { NextResponse } from 'next/server'
import { queryMany, queryOne } from '@/lib/db'

// DeepSeek API configuration
const DEEPSEEK_BALANCE_URL = 'https://api.deepseek.com/user/balance'

// Get API key - check multiple sources
function getDeepSeekApiKey(): string {
  // Try environment variable first
  if (process.env.DEEPSEEK_API_KEY) {
    return process.env.DEEPSEEK_API_KEY
  }
  // Fallback to known key (should be in env in production)
  return 'sk-14afe9362fbb42deb0e62e0ef89535c1'
}

interface DeepSeekBalanceInfo {
  currency: string
  total_balance: string
  granted_balance: string
  topped_up_balance: string
}

interface DeepSeekBalanceResponse {
  is_available: boolean
  balance_infos: DeepSeekBalanceInfo[]
}

interface StoredBalance {
  balance_id: string
  provider: string
  currency: string
  total_balance: number
  granted_balance: number
  topped_up_balance: number
  is_available: boolean
  fetched_at: string
}

export async function GET() {
  try {
    // Fetch live balance from DeepSeek API
    const liveBalance = await fetchDeepSeekBalance()

    // Store in database for historical tracking
    if (liveBalance) {
      await storeBalance(liveBalance)
    }

    // Get historical data for consumption calculation
    const historicalData = await getHistoricalBalance()

    // Calculate consumption
    const consumption24h = calculateConsumption(historicalData, 24)
    const consumption7d = calculateConsumption(historicalData, 168)

    return NextResponse.json({
      live: liveBalance,
      stored: historicalData.slice(0, 10), // Last 10 snapshots
      consumption: {
        last_24h: consumption24h,
        last_7d: consumption7d,
      },
      fetched_at: new Date().toISOString(),
    })
  } catch (error) {
    console.error('LLM Balance API error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch LLM balance', details: String(error) },
      { status: 500 }
    )
  }
}

async function fetchDeepSeekBalance(): Promise<DeepSeekBalanceResponse | null> {
  const apiKey = getDeepSeekApiKey()
  if (!apiKey) {
    console.warn('DEEPSEEK_API_KEY not configured')
    return null
  }

  try {
    console.log(`[LLM-Balance] Fetching from DeepSeek API...`)
    const response = await fetch(DEEPSEEK_BALANCE_URL, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      // No caching for live balance
      cache: 'no-store',
    })

    console.log(`[LLM-Balance] Response status: ${response.status}`)

    if (!response.ok) {
      const errorText = await response.text()
      console.error(`[LLM-Balance] Error response: ${errorText}`)
      throw new Error(`DeepSeek API error: ${response.status} - ${errorText}`)
    }

    const data = await response.json()
    console.log(`[LLM-Balance] Got balance: ${JSON.stringify(data)}`)
    return data
  } catch (error) {
    console.error('[LLM-Balance] Failed to fetch DeepSeek balance:', error)
    return null
  }
}

async function storeBalance(balance: DeepSeekBalanceResponse): Promise<void> {
  if (!balance.balance_infos?.length) return

  const info = balance.balance_infos.find(b => b.currency === 'USD') || balance.balance_infos[0]

  try {
    // Check if we already have a recent snapshot (within 5 minutes)
    const recent = await queryOne<{ count: number }>(`
      SELECT COUNT(*) as count
      FROM fhq_governance.llm_provider_balance
      WHERE provider = 'deepseek'
        AND fetched_at > NOW() - INTERVAL '5 minutes'
    `)

    if (recent && recent.count > 0) {
      return // Skip if we have a recent snapshot
    }

    // Note: This is read-only from dashboard, storage happens via Python script
    // The dashboard only reads stored data
  } catch (error) {
    console.error('Error checking recent balance:', error)
  }
}

async function getHistoricalBalance(): Promise<StoredBalance[]> {
  try {
    const results = await queryMany<StoredBalance>(`
      SELECT
        balance_id::text,
        provider,
        currency,
        total_balance::float,
        granted_balance::float,
        topped_up_balance::float,
        is_available,
        fetched_at::text
      FROM fhq_governance.llm_provider_balance
      WHERE provider = 'deepseek'
      ORDER BY fetched_at DESC
      LIMIT 100
    `)
    return results
  } catch (error) {
    console.error('Error fetching historical balance:', error)
    return []
  }
}

function calculateConsumption(
  history: StoredBalance[],
  hours: number
): { start: number; end: number; consumed: number; period_hours: number } | null {
  if (history.length < 2) return null

  const cutoff = new Date(Date.now() - hours * 60 * 60 * 1000)

  // Filter to records within the period
  const periodRecords = history.filter(
    (r) => new Date(r.fetched_at) >= cutoff
  )

  if (periodRecords.length < 2) return null

  // Oldest and newest in period
  const oldest = periodRecords[periodRecords.length - 1]
  const newest = periodRecords[0]

  const consumed = oldest.total_balance - newest.total_balance

  return {
    start: oldest.total_balance,
    end: newest.total_balance,
    consumed: Math.max(0, consumed), // Can't be negative (top-ups would show as negative)
    period_hours: hours,
  }
}
