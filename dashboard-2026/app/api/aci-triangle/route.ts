/**
 * ACI Triangle Shadow Evaluation API Route
 * =========================================
 * CEO Directive CEO-ACI-TRIANGLE-2025-12-21
 *
 * Exposes shadow evaluation telemetry for:
 * - EC-020 SitC: Reasoning chain integrity metrics
 * - EC-021 InForage: API budget discipline metrics
 * - EC-022 IKEA: Hallucination firewall metrics
 *
 * Mode: SHADOW/AUDIT-ONLY (crypto assets only)
 * Classification: Tier-3 Application Layer
 */

import { NextResponse } from 'next/server'
import { Pool } from 'pg'

const pool = new Pool({
  host: process.env.PGHOST || '127.0.0.1',
  port: parseInt(process.env.PGPORT || '54322'),
  database: process.env.PGDATABASE || 'postgres',
  user: process.env.PGUSER || 'postgres',
  password: process.env.PGPASSWORD || 'postgres',
})

// DeepSeek API configuration for live balance
const DEEPSEEK_BALANCE_URL = 'https://api.deepseek.com/user/balance'

function getDeepSeekApiKey(): string {
  return process.env.DEEPSEEK_API_KEY || 'sk-14afe9362fbb42deb0e62e0ef89535c1'
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

async function fetchLiveDeepSeekBalance(): Promise<DeepSeekBalanceResponse | null> {
  const apiKey = getDeepSeekApiKey()
  if (!apiKey) return null

  try {
    const response = await fetch(DEEPSEEK_BALANCE_URL, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    })

    if (!response.ok) return null
    return await response.json()
  } catch (error) {
    console.error('[ACI-Triangle] Failed to fetch live DeepSeek balance:', error)
    return null
  }
}

interface ACITriangleTelemetry {
  sitc: {
    totalEvaluated: number
    brokenChains: number
    brokenChainRate: number
    avgScore: number
    reasonDistribution: Record<string, number>
    lastEvaluatedAt: string | null
  }
  inforage: {
    totalCostUsd: number
    avgCostPerNeedle: number
    budgetCapUsd: number
    budgetPressurePct: number
    avgBudgetPressure: number
    totalApiCalls: number
    lastEvaluatedAt: string | null
    currentBalance?: number
    toppedUpBalance?: number
  }
  ikea: {
    totalEvaluated: number
    fabricationCount: number
    staleDataCount: number
    unverifiableCount: number
    flaggedTotal: number
    fabricationRate: number
    avgScore: number
    lastEvaluatedAt: string | null
  }
  summary: {
    mode: 'SHADOW'
    assetFilter: 'CRYPTO_ONLY'
    totalNeedlesEvaluated: number
    totalNeedlesInDatabase: number
    needlesWithChainHash: number
    chainHashCoverage: number
    lastFullScanAt: string | null
  }
  recentEvaluations: Array<{
    needleId: string
    targetAsset: string | null
    sitcScore: number
    sitcBroken: boolean
    sitcFailure: string | null
    ikeaScore: number
    ikeaFlagged: boolean
    inforageCostUsd: number
    evaluatedAt: string
  }>
}

export async function GET() {
  const client = await pool.connect()

  try {
    // Check if the shadow evaluations table exists
    const tableCheck = await client.query(`
      SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'fhq_canonical'
        AND table_name = 'aci_shadow_evaluations'
      )
    `)

    const tableExists = tableCheck.rows[0].exists

    if (!tableExists) {
      return NextResponse.json({
        sitc: {
          totalEvaluated: 0,
          brokenChains: 0,
          brokenChainRate: 0,
          avgScore: 0,
          reasonDistribution: {},
          lastEvaluatedAt: null
        },
        inforage: {
          totalCostUsd: 0,
          avgCostPerNeedle: 0,
          budgetCapUsd: 50.0,
          budgetPressurePct: 0,
          avgBudgetPressure: 0,
          totalApiCalls: 0,
          lastEvaluatedAt: null
        },
        ikea: {
          totalEvaluated: 0,
          fabricationCount: 0,
          staleDataCount: 0,
          unverifiableCount: 0,
          flaggedTotal: 0,
          fabricationRate: 0,
          avgScore: 1.0,
          lastEvaluatedAt: null
        },
        summary: {
          mode: 'SHADOW',
          assetFilter: 'CRYPTO_ONLY',
          totalNeedlesEvaluated: 0,
          totalNeedlesInDatabase: 0,
          needlesWithChainHash: 0,
          chainHashCoverage: 0,
          lastFullScanAt: null,
          tableStatus: 'NOT_CREATED'
        },
        recentEvaluations: [],
        timestamp: new Date().toISOString()
      })
    }

    // EC-020 SitC metrics
    const sitcResult = await client.query(`
      SELECT
        COUNT(*) as total_evaluated,
        COUNT(*) FILTER (WHERE sitc_has_broken_chain = TRUE) as broken_chains,
        COALESCE(AVG(sitc_score), 0) as avg_score,
        MAX(evaluated_at) as last_eval
      FROM fhq_canonical.aci_shadow_evaluations
    `)

    // SitC failure reason distribution
    const sitcReasonsResult = await client.query(`
      SELECT
        sitc_failure_type,
        COUNT(*) as count
      FROM fhq_canonical.aci_shadow_evaluations
      WHERE sitc_failure_type IS NOT NULL
      GROUP BY sitc_failure_type
    `)

    const sitcData = sitcResult.rows[0] || { total_evaluated: 0, broken_chains: 0, avg_score: 0, last_eval: null }
    const reasonDistribution: Record<string, number> = {}
    for (const row of sitcReasonsResult.rows) {
      if (row.sitc_failure_type) {
        reasonDistribution[row.sitc_failure_type] = parseInt(row.count)
      }
    }

    // EC-021 InForage metrics - fetch LIVE DeepSeek balance from API
    let currentBalance = 0
    let fetchedAt: Date | null = null

    // Try to get LIVE balance from DeepSeek API
    const liveBalance = await fetchLiveDeepSeekBalance()
    if (liveBalance && liveBalance.balance_infos?.length > 0) {
      const usdBalance = liveBalance.balance_infos.find(b => b.currency === 'USD') || liveBalance.balance_infos[0]
      currentBalance = parseFloat(usdBalance.total_balance) || 0
      fetchedAt = new Date()
      console.log(`[ACI-Triangle] Live DeepSeek balance: $${currentBalance}`)
    } else {
      // Fallback to cached database value if API fails
      const realBalanceResult = await client.query(`
        SELECT
          total_balance,
          topped_up_balance,
          fetched_at
        FROM fhq_governance.llm_provider_balance
        WHERE provider = 'deepseek'
        ORDER BY fetched_at DESC
        LIMIT 1
      `)
      const realBalance = realBalanceResult.rows[0] || { total_balance: 0, topped_up_balance: 0 }
      currentBalance = parseFloat(realBalance.total_balance) || 0
      fetchedAt = realBalance.fetched_at ? new Date(realBalance.fetched_at) : null
      console.log(`[ACI-Triangle] Using cached balance: $${currentBalance}`)
    }

    // Calculate monthly spending: Initial topped-up was $20, current is remaining balance
    const initialToppedUp = 20.0  // Known initial topped-up amount
    const monthlySpent = Math.max(0, initialToppedUp - currentBalance)

    const budgetCapUsd = 50.0
    const budgetPressurePct = monthlySpent > 0 ? (monthlySpent / budgetCapUsd) * 100 : 0

    // Also get evaluation stats
    const inforageResult = await client.query(`
      SELECT
        COUNT(*) as total_evaluated,
        COALESCE(AVG(inforage_budget_pressure), 0) as avg_pressure,
        MAX(evaluated_at) as last_eval
      FROM fhq_canonical.aci_shadow_evaluations
    `)

    const inforageData = inforageResult.rows[0] || {
      total_evaluated: 0, avg_pressure: 0, last_eval: null
    }

    // EC-022 IKEA metrics
    const ikeaResult = await client.query(`
      SELECT
        COUNT(*) as total_evaluated,
        COUNT(*) FILTER (WHERE ikea_has_fabrication = TRUE) as fabrication_count,
        COUNT(*) FILTER (WHERE ikea_has_stale_data = TRUE) as stale_data_count,
        COUNT(*) FILTER (WHERE ikea_has_unverifiable = TRUE) as unverifiable_count,
        COUNT(*) FILTER (WHERE ikea_has_fabrication = TRUE OR ikea_has_stale_data = TRUE OR ikea_has_unverifiable = TRUE) as flagged_total,
        COALESCE(AVG(ikea_score), 1.0) as avg_score,
        MAX(evaluated_at) as last_eval
      FROM fhq_canonical.aci_shadow_evaluations
    `)

    const ikeaData = ikeaResult.rows[0] || {
      total_evaluated: 0, fabrication_count: 0, stale_data_count: 0,
      unverifiable_count: 0, flagged_total: 0, avg_score: 1.0, last_eval: null
    }

    // Database-wide needle statistics (all 740+)
    const needleStatsResult = await client.query(`
      SELECT
        COUNT(*) as total_needles,
        COUNT(*) FILTER (WHERE chain_of_query_hash IS NOT NULL) as with_chain_hash
      FROM fhq_canonical.golden_needles
      WHERE is_current = TRUE
    `)
    const needleStats = needleStatsResult.rows[0] || { total_needles: 0, with_chain_hash: 0 }
    const totalNeedlesInDatabase = parseInt(needleStats.total_needles) || 0
    const needlesWithChainHash = parseInt(needleStats.with_chain_hash) || 0
    const chainHashCoverage = totalNeedlesInDatabase > 0
      ? (needlesWithChainHash / totalNeedlesInDatabase) * 100
      : 0

    // Recent evaluations (last 20)
    const recentResult = await client.query(`
      SELECT
        e.needle_id,
        n.target_asset,
        e.sitc_score,
        e.sitc_has_broken_chain,
        e.sitc_failure_type,
        e.ikea_score,
        (e.ikea_has_fabrication OR e.ikea_has_stale_data OR e.ikea_has_unverifiable) as ikea_flagged,
        e.inforage_api_cost_usd,
        e.evaluated_at
      FROM fhq_canonical.aci_shadow_evaluations e
      LEFT JOIN fhq_canonical.golden_needles n ON e.needle_id = n.needle_id
      ORDER BY e.evaluated_at DESC
      LIMIT 20
    `)

    // Calculate rates
    const totalEvaluated = parseInt(sitcData.total_evaluated) || 0
    const brokenChains = parseInt(sitcData.broken_chains) || 0
    const brokenChainRate = totalEvaluated > 0 ? (brokenChains / totalEvaluated) * 100 : 0

    const flaggedTotal = parseInt(ikeaData.flagged_total) || 0
    const fabricationRate = totalEvaluated > 0 ? (flaggedTotal / totalEvaluated) * 100 : 0

    const telemetry: ACITriangleTelemetry = {
      sitc: {
        totalEvaluated,
        brokenChains,
        brokenChainRate: Math.round(brokenChainRate * 100) / 100,
        avgScore: Math.round(parseFloat(sitcData.avg_score) * 1000) / 1000,
        reasonDistribution,
        lastEvaluatedAt: sitcData.last_eval ? new Date(sitcData.last_eval).toISOString() : null
      },
      inforage: {
        totalCostUsd: Math.round(monthlySpent * 100) / 100,  // Monthly spend = initial - current
        avgCostPerNeedle: totalNeedlesInDatabase > 0 ? Math.round((monthlySpent / totalNeedlesInDatabase) * 10000) / 10000 : 0,
        budgetCapUsd,
        budgetPressurePct: Math.round(budgetPressurePct * 100) / 100,
        avgBudgetPressure: Math.round(parseFloat(inforageData.avg_pressure) * 10000) / 100,
        totalApiCalls: 0,  // Not tracked per-call, using balance instead
        lastEvaluatedAt: fetchedAt ? fetchedAt.toISOString() : null,
        // Real balance data
        currentBalance: Math.round(currentBalance * 100) / 100,
        initialBalance: initialToppedUp,
        monthlySpent: Math.round(monthlySpent * 100) / 100
      },
      ikea: {
        totalEvaluated: parseInt(ikeaData.total_evaluated) || 0,
        fabricationCount: parseInt(ikeaData.fabrication_count) || 0,
        staleDataCount: parseInt(ikeaData.stale_data_count) || 0,
        unverifiableCount: parseInt(ikeaData.unverifiable_count) || 0,
        flaggedTotal,
        fabricationRate: Math.round(fabricationRate * 100) / 100,
        avgScore: Math.round(parseFloat(ikeaData.avg_score) * 1000) / 1000,
        lastEvaluatedAt: ikeaData.last_eval ? new Date(ikeaData.last_eval).toISOString() : null
      },
      summary: {
        mode: 'SHADOW',
        assetFilter: 'CRYPTO_ONLY',
        totalNeedlesEvaluated: totalEvaluated,
        totalNeedlesInDatabase,
        needlesWithChainHash,
        chainHashCoverage: Math.round(chainHashCoverage * 100) / 100,
        lastFullScanAt: sitcData.last_eval ? new Date(sitcData.last_eval).toISOString() : null
      },
      recentEvaluations: recentResult.rows.map(row => ({
        needleId: row.needle_id,
        targetAsset: row.target_asset || null,
        sitcScore: parseFloat(row.sitc_score) || 0,
        sitcBroken: row.sitc_has_broken_chain || false,
        sitcFailure: row.sitc_failure_type || null,
        ikeaScore: parseFloat(row.ikea_score) || 1.0,
        ikeaFlagged: row.ikea_flagged || false,
        inforageCostUsd: parseFloat(row.inforage_api_cost_usd) || 0,
        evaluatedAt: new Date(row.evaluated_at).toISOString()
      }))
    }

    return NextResponse.json({
      ...telemetry,
      timestamp: new Date().toISOString()
    })

  } catch (error) {
    console.error('ACI Triangle API error:', error)
    return NextResponse.json(
      {
        error: String(error),
        timestamp: new Date().toISOString(),
        note: 'Run: python 03_FUNCTIONS/aci_triangle_shadow.py --evaluate'
      },
      { status: 500 }
    )
  } finally {
    client.release()
  }
}

// API info endpoint
export async function POST() {
  return NextResponse.json({
    endpoint: '/api/aci-triangle',
    version: '1.0.0',
    directive: 'CEO-ACI-TRIANGLE-2025-12-21',
    mode: 'SHADOW/AUDIT-ONLY',
    scope: 'CRYPTO_ONLY',
    engines: {
      'EC-020': 'SitC - Reasoning Chain Integrity',
      'EC-021': 'InForage - API Budget Discipline',
      'EC-022': 'IKEA - Hallucination Firewall'
    },
    usage: {
      evaluate: 'python 03_FUNCTIONS/aci_triangle_shadow.py --evaluate',
      telemetry: 'GET /api/aci-triangle'
    }
  })
}
