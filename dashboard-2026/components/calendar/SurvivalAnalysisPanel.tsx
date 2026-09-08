'use client'

/**
 * G1.5 SURVIVAL ANALYSIS PANEL
 * ============================
 * CEO-DIR-2026-G1.5-GENERATION-VARIANCE-001 Section 5
 *
 * Read-only observational tooling for G1.5 calibration experiment.
 * Displays Kaplan-Meier survival curves by pre_tier_score quartiles.
 *
 * EXPERIMENTAL – OBSERVATION ONLY – NO ACTION PERMITTED
 */

import { useState, useEffect } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  ReferenceLine
} from 'recharts'

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

interface SurvivalData {
  status: string
  experimental_warning: string
  timestamp: string
  experiment: {
    id: string
    status: string
    deathProgress: string
    daysElapsed: number
    daysRemaining: number
  }
  summary: {
    totalHypotheses: number
    totalDeaths: number
    totalAlive: number
    highCausalPressure: number
    standardRegime: number
    depthDistribution: Record<number, number>
  }
  quartileBoundaries: {
    q1: { max: number }
    q2: { min: number; max: number }
    q3: { min: number; max: number }
    q4: { min: number }
  }
  quartileStats: QuartileStats[]
  survivalCurves: SurvivalPoint[]
  scatterData: ScatterPoint[]
  correlation: {
    spearman: number | null
    pValueIndicator: string | null
    interpretation: string
  }
}

const QUARTILE_COLORS = {
  q1: '#ef4444', // red - lowest scores
  q2: '#f97316', // orange
  q3: '#22c55e', // green
  q4: '#3b82f6'  // blue - highest scores
}

export default function SurvivalAnalysisPanel() {
  const [data, setData] = useState<SurvivalData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeView, setActiveView] = useState<'survival' | 'scatter' | 'quartiles'>('survival')

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch('/api/g15/survival-analysis')
        const result = await response.json()

        if (result.status === 'OK') {
          setData(result)
        } else {
          setError(result.message || 'Failed to load data')
        }
      } catch (err) {
        setError(String(err))
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 60000) // Refresh every minute
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div className="bg-gray-900 rounded-lg p-6 border border-gray-800">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-800 rounded w-1/3 mb-4"></div>
          <div className="h-64 bg-gray-800 rounded"></div>
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="bg-gray-900 rounded-lg p-6 border border-red-900">
        <h3 className="text-red-400 font-semibold">Survival Analysis Error</h3>
        <p className="text-gray-400 text-sm mt-2">{error || 'No data available'}</p>
      </div>
    )
  }

  const hasDeaths = data.summary.totalDeaths > 0

  return (
    <div className="bg-gray-900 rounded-lg border border-amber-900/50">
      {/* Warning Banner */}
      <div className="bg-amber-900/30 border-b border-amber-900/50 px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="text-amber-400 text-lg">⚠️</span>
          <span className="text-amber-400 font-mono text-xs tracking-wider">
            {data.experimental_warning}
          </span>
        </div>
      </div>

      {/* Header */}
      <div className="p-4 border-b border-gray-800">
        <div className="flex justify-between items-center">
          <div>
            <h3 className="text-white font-semibold flex items-center gap-2">
              <span className="text-purple-400">📊</span>
              G1.5 Survival Analysis
            </h3>
            <p className="text-gray-500 text-xs mt-1">
              Kaplan-Meier curves by pre_tier_score quartile
            </p>
          </div>
          <div className="text-right">
            <div className="text-gray-400 text-xs">Experiment</div>
            <div className="text-white font-mono text-sm">{data.experiment.id}</div>
            <div className="text-gray-500 text-xs">
              Deaths: {data.experiment.deathProgress}
            </div>
          </div>
        </div>

        {/* View Tabs */}
        <div className="flex gap-2 mt-4">
          {(['survival', 'scatter', 'quartiles'] as const).map(view => (
            <button
              key={view}
              onClick={() => setActiveView(view)}
              className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                activeView === view
                  ? 'bg-purple-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {view === 'survival' ? 'Survival Curves' :
               view === 'scatter' ? 'Score vs TTF' : 'Quartile Stats'}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        {activeView === 'survival' && (
          <div>
            {!hasDeaths ? (
              <div className="h-64 flex items-center justify-center">
                <div className="text-center">
                  <div className="text-gray-500 text-4xl mb-2">⏳</div>
                  <div className="text-gray-400">Awaiting first deaths for survival analysis</div>
                  <div className="text-gray-500 text-sm mt-1">
                    {data.summary.totalHypotheses} hypotheses tracked, 0 falsified
                  </div>
                </div>
              </div>
            ) : (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data.survivalCurves}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis
                      dataKey="time"
                      stroke="#9ca3af"
                      label={{ value: 'Time (hours)', position: 'bottom', fill: '#9ca3af' }}
                    />
                    <YAxis
                      stroke="#9ca3af"
                      domain={[0, 100]}
                      label={{ value: 'Survival %', angle: -90, position: 'insideLeft', fill: '#9ca3af' }}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1f2937',
                        border: '1px solid #374151',
                        borderRadius: '6px'
                      }}
                      labelFormatter={(value) => `Time: ${value}h`}
                    />
                    <Legend />
                    <Line
                      type="stepAfter"
                      dataKey="q1"
                      name="Q1 (Lowest)"
                      stroke={QUARTILE_COLORS.q1}
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="stepAfter"
                      dataKey="q2"
                      name="Q2"
                      stroke={QUARTILE_COLORS.q2}
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="stepAfter"
                      dataKey="q3"
                      name="Q3"
                      stroke={QUARTILE_COLORS.q3}
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="stepAfter"
                      dataKey="q4"
                      name="Q4 (Highest)"
                      stroke={QUARTILE_COLORS.q4}
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Correlation Summary */}
            <div className="mt-4 p-3 bg-gray-800/50 rounded-lg">
              <div className="flex justify-between items-center">
                <div>
                  <span className="text-gray-400 text-xs">Spearman Correlation (Score vs TTF)</span>
                  <div className="text-white font-mono text-lg">
                    {data.correlation.spearman !== null
                      ? data.correlation.spearman.toFixed(3)
                      : '—'}
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-gray-400 text-xs">Interpretation</span>
                  <div className={`text-sm font-medium ${
                    data.correlation.interpretation.includes('POSITIVE') ? 'text-green-400' :
                    data.correlation.interpretation.includes('NEGATIVE') ? 'text-red-400' :
                    'text-gray-400'
                  }`}>
                    {data.correlation.interpretation}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeView === 'scatter' && (
          <div>
            {!hasDeaths ? (
              <div className="h-64 flex items-center justify-center">
                <div className="text-center">
                  <div className="text-gray-500 text-4xl mb-2">📈</div>
                  <div className="text-gray-400">Scatter plot requires falsified hypotheses</div>
                </div>
              </div>
            ) : (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ bottom: 20, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis
                      dataKey="score"
                      name="Score"
                      stroke="#9ca3af"
                      label={{ value: 'Pre-Tier Score at Birth', position: 'bottom', fill: '#9ca3af' }}
                      domain={['dataMin - 5', 'dataMax + 5']}
                    />
                    <YAxis
                      dataKey="ttf"
                      name="TTF"
                      stroke="#9ca3af"
                      label={{ value: 'Time to Falsification (h)', angle: -90, position: 'insideLeft', fill: '#9ca3af' }}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1f2937',
                        border: '1px solid #374151',
                        borderRadius: '6px'
                      }}
                      formatter={(value: number, name: string) => [
                        name === 'score' ? value.toFixed(2) : `${value.toFixed(1)}h`,
                        name === 'score' ? 'Score' : 'TTF'
                      ]}
                      labelFormatter={(_, payload) => {
                        if (payload && payload[0]) {
                          const d = payload[0].payload as ScatterPoint
                          return `${d.hypothesis_code} [${d.generation_regime}]`
                        }
                        return ''
                      }}
                    />
                    <Scatter
                      name="Falsified Hypotheses"
                      data={data.scatterData}
                      fill="#8b5cf6"
                    />
                    {data.correlation.spearman !== null && (
                      <ReferenceLine
                        stroke="#6b7280"
                        strokeDasharray="5 5"
                        label={{
                          value: `ρ = ${data.correlation.spearman.toFixed(3)}`,
                          fill: '#9ca3af',
                          fontSize: 12
                        }}
                      />
                    )}
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Data Points Info */}
            <div className="mt-4 grid grid-cols-3 gap-3">
              <div className="p-2 bg-gray-800/50 rounded text-center">
                <div className="text-gray-400 text-xs">Data Points</div>
                <div className="text-white font-mono">{data.scatterData.length}</div>
              </div>
              <div className="p-2 bg-gray-800/50 rounded text-center">
                <div className="text-gray-400 text-xs">High Pressure</div>
                <div className="text-purple-400 font-mono">
                  {data.scatterData.filter(d => d.generation_regime === 'HIGH_CAUSAL_PRESSURE').length}
                </div>
              </div>
              <div className="p-2 bg-gray-800/50 rounded text-center">
                <div className="text-gray-400 text-xs">Standard</div>
                <div className="text-white font-mono">
                  {data.scatterData.filter(d => d.generation_regime === 'STANDARD').length}
                </div>
              </div>
            </div>
          </div>
        )}

        {activeView === 'quartiles' && (
          <div>
            <div className="grid grid-cols-4 gap-3">
              {data.quartileStats.map((q) => (
                <div
                  key={q.quartile}
                  className="p-3 rounded-lg border"
                  style={{
                    borderColor: QUARTILE_COLORS[q.quartile.toLowerCase() as keyof typeof QUARTILE_COLORS] + '40',
                    backgroundColor: QUARTILE_COLORS[q.quartile.toLowerCase() as keyof typeof QUARTILE_COLORS] + '10'
                  }}
                >
                  <div
                    className="font-semibold text-sm"
                    style={{ color: QUARTILE_COLORS[q.quartile.toLowerCase() as keyof typeof QUARTILE_COLORS] }}
                  >
                    {q.label}
                  </div>
                  <div className="text-gray-400 text-xs mt-1">
                    Score: {q.minScore.toFixed(1)} - {q.maxScore.toFixed(1)}
                  </div>

                  <div className="mt-3 space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-500">Count</span>
                      <span className="text-white font-mono">{q.count}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-500">Deaths</span>
                      <span className="text-white font-mono">{q.deaths}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-500">Survival</span>
                      <span className="text-white font-mono">{(q.survivalRate * 100).toFixed(0)}%</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-500">Median TTF</span>
                      <span className="text-white font-mono">
                        {q.medianTTF !== null ? `${q.medianTTF.toFixed(1)}h` : '—'}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Depth Distribution */}
            <div className="mt-4 p-3 bg-gray-800/50 rounded-lg">
              <div className="text-gray-400 text-xs mb-2">Causal Depth Distribution</div>
              <div className="flex gap-2">
                {Object.entries(data.summary.depthDistribution)
                  .sort(([a], [b]) => Number(a) - Number(b))
                  .map(([depth, count]) => (
                    <div key={depth} className="px-2 py-1 bg-gray-800 rounded text-xs">
                      <span className="text-gray-400">D{depth}:</span>
                      <span className="text-white ml-1 font-mono">{count}</span>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-gray-800 bg-gray-950/50">
        <div className="flex justify-between text-xs text-gray-500">
          <span>
            {data.summary.totalHypotheses} hypotheses | {data.summary.totalDeaths} deaths |
            {data.summary.highCausalPressure} high-pressure
          </span>
          <span>Last updated: {new Date(data.timestamp).toLocaleTimeString()}</span>
        </div>
      </div>
    </div>
  )
}
