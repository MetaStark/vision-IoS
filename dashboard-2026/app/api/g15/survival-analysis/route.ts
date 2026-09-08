/**
 * G1.5 SURVIVAL ANALYSIS API
 * ===========================
 * CEO-DIR-2026-G1.5-GENERATION-VARIANCE-001 Section 5
 *
 * READ-ONLY observational tooling for G1.5 calibration experiment.
 * Provides Kaplan-Meier survival data by pre_tier_score quartiles.
 *
 * EXPERIMENTAL – OBSERVATION ONLY – NO ACTION PERMITTED
 */

import { NextRequest, NextResponse } from 'next/server'
import { Pool } from 'pg'

const pool = new Pool({
  host: process.env.PGHOST || '127.0.0.1',
  port: parseInt(process.env.PGPORT || '54322'),
  database: process.env.PGDATABASE || 'postgres',
  user: process.env.PGUSER || 'postgres',
  password: process.env.PGPASSWORD || 'postgres',
})

interface HypothesisData {
  canon_id: string
  hypothesis_code: string
  pre_tier_score_at_birth: number
  status: string
  created_at: Date
  falsified_at: Date | null
  time_to_falsification_hours: number | null
  generation_regime: string
  causal_graph_depth: number
}

interface QuartileStats {
  quartile: string
  label: string
  count: number
  deaths: number
  survivalRate: number
  medianTTF: number | null
  avgScore: number
  minScore: number
  maxScore: number
}

interface SurvivalPoint {
  time: number
  q1: number
  q2: number
  q3: number
  q4: number
}

interface ScatterPoint {
  score: number
  ttf: number
  status: string
  hypothesis_code: string
  generation_regime: string
}

export async function GET(request: NextRequest) {
  const client = await pool.connect()

  try {
    // Get all hypotheses with pre_tier_score_at_birth for G1.5 analysis
    const result = await client.query<HypothesisData>(`
      SELECT
        canon_id,
        hypothesis_code,
        pre_tier_score_at_birth::float,
        status,
        created_at,
        falsified_at,
        time_to_falsification_hours::float,
        COALESCE(generation_regime, 'STANDARD') as generation_regime,
        COALESCE(causal_graph_depth, 2) as causal_graph_depth
      FROM fhq_learning.hypothesis_canon
      WHERE pre_tier_score_at_birth IS NOT NULL
      ORDER BY pre_tier_score_at_birth ASC
    `)

    const hypotheses = result.rows

    if (hypotheses.length === 0) {
      return NextResponse.json({
        status: 'INSUFFICIENT_DATA',
        message: 'No hypotheses with pre_tier_score_at_birth found',
        data: null
      })
    }

    // Calculate quartile boundaries
    const scores = hypotheses.map(h => h.pre_tier_score_at_birth).sort((a, b) => a - b)
    const q1Threshold = scores[Math.floor(scores.length * 0.25)]
    const q2Threshold = scores[Math.floor(scores.length * 0.50)]
    const q3Threshold = scores[Math.floor(scores.length * 0.75)]

    // Assign quartiles
    const assignQuartile = (score: number): string => {
      if (score <= q1Threshold) return 'Q1'
      if (score <= q2Threshold) return 'Q2'
      if (score <= q3Threshold) return 'Q3'
      return 'Q4'
    }

    // Group by quartile
    const quartileGroups: Record<string, HypothesisData[]> = { Q1: [], Q2: [], Q3: [], Q4: [] }
    hypotheses.forEach(h => {
      const q = assignQuartile(h.pre_tier_score_at_birth)
      quartileGroups[q].push(h)
    })

    // Calculate quartile statistics
    const quartileStats: QuartileStats[] = Object.entries(quartileGroups).map(([quartile, group]) => {
      const deaths = group.filter(h => h.status === 'FALSIFIED')
      const ttfValues = deaths
        .map(h => h.time_to_falsification_hours)
        .filter((v): v is number => v !== null)
        .sort((a, b) => a - b)

      const scores = group.map(h => h.pre_tier_score_at_birth)

      return {
        quartile,
        label: quartile === 'Q1' ? 'Q1 (Lowest)' :
               quartile === 'Q4' ? 'Q4 (Highest)' : quartile,
        count: group.length,
        deaths: deaths.length,
        survivalRate: group.length > 0 ? (group.length - deaths.length) / group.length : 1,
        medianTTF: ttfValues.length > 0 ? ttfValues[Math.floor(ttfValues.length / 2)] : null,
        avgScore: scores.reduce((a, b) => a + b, 0) / scores.length,
        minScore: Math.min(...scores),
        maxScore: Math.max(...scores)
      }
    })

    // Build Kaplan-Meier survival curves
    // Time points from 0 to max observed time
    const allTTF = hypotheses
      .filter(h => h.time_to_falsification_hours !== null)
      .map(h => h.time_to_falsification_hours as number)

    const maxTime = allTTF.length > 0 ? Math.max(...allTTF) : 72
    const timePoints = Array.from({ length: 25 }, (_, i) => (i / 24) * maxTime)

    // Calculate survival at each time point for each quartile
    const survivalCurves: SurvivalPoint[] = timePoints.map(time => {
      const point: SurvivalPoint = { time: Math.round(time * 10) / 10, q1: 100, q2: 100, q3: 100, q4: 100 }

      for (const [quartile, group] of Object.entries(quartileGroups)) {
        if (group.length === 0) continue

        // Count deaths before this time point
        const deathsBefore = group.filter(h =>
          h.status === 'FALSIFIED' &&
          h.time_to_falsification_hours !== null &&
          h.time_to_falsification_hours <= time
        ).length

        const survivalPct = ((group.length - deathsBefore) / group.length) * 100
        const key = quartile.toLowerCase() as 'q1' | 'q2' | 'q3' | 'q4'
        point[key] = Math.round(survivalPct * 10) / 10
      }

      return point
    })

    // Build scatter plot data (score vs TTF)
    const scatterData: ScatterPoint[] = hypotheses
      .filter(h => h.status === 'FALSIFIED' && h.time_to_falsification_hours !== null)
      .map(h => ({
        score: Math.round(h.pre_tier_score_at_birth * 100) / 100,
        ttf: Math.round((h.time_to_falsification_hours as number) * 10) / 10,
        status: h.status,
        hypothesis_code: h.hypothesis_code,
        generation_regime: h.generation_regime
      }))

    // Calculate Spearman correlation if enough data
    let spearmanCorrelation: number | null = null
    let spearmanPValue: string | null = null

    if (scatterData.length >= 10) {
      // Simple Spearman calculation (rank correlation)
      const n = scatterData.length
      const scoreRanks = rankData(scatterData.map(d => d.score))
      const ttfRanks = rankData(scatterData.map(d => d.ttf))

      let sumD2 = 0
      for (let i = 0; i < n; i++) {
        const d = scoreRanks[i] - ttfRanks[i]
        sumD2 += d * d
      }

      spearmanCorrelation = Math.round((1 - (6 * sumD2) / (n * (n * n - 1))) * 1000) / 1000

      // Approximate p-value indicator
      if (Math.abs(spearmanCorrelation) > 0.5 && n >= 30) {
        spearmanPValue = 'LIKELY_SIGNIFICANT'
      } else if (n < 30) {
        spearmanPValue = 'INSUFFICIENT_N'
      } else {
        spearmanPValue = 'NOT_SIGNIFICANT'
      }
    }

    // Get experiment metadata
    const expResult = await client.query(`
      SELECT * FROM fhq_learning.v_g1_5_throughput_tracker LIMIT 1
    `)
    const experiment = expResult.rows[0] || {}

    // High causal pressure statistics
    const highPressureCount = hypotheses.filter(h => h.generation_regime === 'HIGH_CAUSAL_PRESSURE').length
    const depthDistribution = hypotheses.reduce((acc, h) => {
      const depth = h.causal_graph_depth || 2
      acc[depth] = (acc[depth] || 0) + 1
      return acc
    }, {} as Record<number, number>)

    return NextResponse.json({
      status: 'OK',
      experimental_warning: 'EXPERIMENTAL – OBSERVATION ONLY – NO ACTION PERMITTED',
      timestamp: new Date().toISOString(),
      experiment: {
        id: experiment.experiment_id || 'FHQ-EXP-PRETIER-G1.5',
        status: experiment.experiment_status || 'ACTIVE',
        deathProgress: `${experiment.deaths_with_score || 0}/30`,
        daysElapsed: experiment.days_elapsed || 0,
        daysRemaining: experiment.days_remaining || 14
      },
      summary: {
        totalHypotheses: hypotheses.length,
        totalDeaths: hypotheses.filter(h => h.status === 'FALSIFIED').length,
        totalAlive: hypotheses.filter(h => h.status !== 'FALSIFIED').length,
        highCausalPressure: highPressureCount,
        standardRegime: hypotheses.length - highPressureCount,
        depthDistribution
      },
      quartileBoundaries: {
        q1: { max: q1Threshold },
        q2: { min: q1Threshold, max: q2Threshold },
        q3: { min: q2Threshold, max: q3Threshold },
        q4: { min: q3Threshold }
      },
      quartileStats,
      survivalCurves,
      scatterData,
      correlation: {
        spearman: spearmanCorrelation,
        pValueIndicator: spearmanPValue,
        interpretation: spearmanCorrelation !== null
          ? spearmanCorrelation > 0.3
            ? 'POSITIVE: Higher scores associated with longer survival'
            : spearmanCorrelation < -0.3
              ? 'NEGATIVE: Higher scores associated with shorter survival'
              : 'WEAK: No clear relationship detected'
          : 'INSUFFICIENT_DATA'
      }
    })

  } catch (error) {
    console.error('Survival analysis error:', error)
    return NextResponse.json(
      { status: 'ERROR', message: String(error) },
      { status: 500 }
    )
  } finally {
    client.release()
  }
}

// Helper function to rank data
function rankData(values: number[]): number[] {
  const sorted = values
    .map((v, i) => ({ value: v, index: i }))
    .sort((a, b) => a.value - b.value)

  const ranks = new Array(values.length)
  let rank = 1

  for (let i = 0; i < sorted.length; i++) {
    // Handle ties by averaging ranks
    let j = i
    while (j < sorted.length - 1 && sorted[j].value === sorted[j + 1].value) {
      j++
    }
    const avgRank = (rank + (rank + j - i)) / 2
    for (let k = i; k <= j; k++) {
      ranks[sorted[k].index] = avgRank
    }
    rank += j - i + 1
    i = j
  }

  return ranks
}
