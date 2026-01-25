/**
 * Learning Visibility Panel - CEO-DIR-2026-DAY25
 *
 * Visual Truth for Learning Metrics:
 * 1. Tier-1 Death Rate vs target band (60-90%)
 * 2. Hypotheses/day time series
 * 3. Generator distribution (FINN-E / FINN-T / GN-S)
 * 4. Average causal depth trend
 *
 * Each graph includes status sentence: ahead/on-track/behind
 */

'use client'

import { useMemo } from 'react'
import {
  Brain,
  Skull,
  TrendingUp,
  TrendingDown,
  Target,
  AlertTriangle,
  CheckCircle,
  XCircle,
  BarChart3,
  Activity,
} from 'lucide-react'

interface LearningMetric {
  date: string
  hypothesesTotal: number
  hypothesesFalsified: number
  deathRatePct: number
  fromErrors: number
  avgCausalDepth: number
  genFinnE: number
  genFinnT: number
  genGnS: number
  genOther: number
}

interface LearningSummary {
  totalHypotheses: number
  totalFalsified: number
  totalActive: number
  deathRatePct: number
  deathRateStatus: string
  avgCausalDepth: number
  finnECount: number
  finnTCount: number
  gnSCount: number
  lastHypothesisTime: string | null
  todayCount: number
  statusSentence: string
}

interface GeneratorPerf {
  name: string
  totalGenerated: number
  falsified: number
  surviving: number
  deathRatePct: number
  avgDepth: number
}

interface LearningVisibilityPanelProps {
  metrics: LearningMetric[]
  summary: LearningSummary
  generators: GeneratorPerf[]
}

// Simple bar chart component
function MiniBarChart({
  data,
  maxValue,
  color,
  label,
}: {
  data: number[]
  maxValue: number
  color: string
  label: string
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-end gap-0.5 h-16">
        {data.map((value, i) => (
          <div
            key={i}
            className={`flex-1 ${color} rounded-t transition-all`}
            style={{ height: `${Math.max((value / maxValue) * 100, 2)}%` }}
            title={`${value}`}
          />
        ))}
      </div>
      <p className="text-xs text-gray-500 text-center">{label}</p>
    </div>
  )
}

// Death rate gauge with target band
function DeathRateGauge({ rate, status }: { rate: number; status: string }) {
  const getStatusColor = () => {
    switch (status) {
      case 'ON_TRACK':
        return 'text-green-400'
      case 'TOO_BRUTAL':
        return 'text-red-400'
      case 'TOO_LENIENT':
        return 'text-yellow-400'
      default:
        return 'text-gray-400'
    }
  }

  const getStatusIcon = () => {
    switch (status) {
      case 'ON_TRACK':
        return <CheckCircle className="h-4 w-4" />
      case 'TOO_BRUTAL':
        return <AlertTriangle className="h-4 w-4" />
      case 'TOO_LENIENT':
        return <XCircle className="h-4 w-4" />
      default:
        return <Target className="h-4 w-4" />
    }
  }

  return (
    <div className="bg-gray-800/50 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Skull className="h-4 w-4 text-red-400" />
          <span className="text-sm text-gray-400">Tier-1 Death Rate</span>
        </div>
        <div className={`flex items-center gap-1 ${getStatusColor()}`}>
          {getStatusIcon()}
          <span className="text-xs font-medium">{status.replace('_', ' ')}</span>
        </div>
      </div>

      {/* Gauge visualization */}
      <div className="relative h-4 bg-gray-700 rounded-full overflow-hidden mb-2">
        {/* Target band (60-90%) */}
        <div
          className="absolute h-full bg-green-500/20 border-l border-r border-green-500/50"
          style={{ left: '60%', width: '30%' }}
        />
        {/* Current rate indicator */}
        <div
          className={`absolute h-full w-1 ${
            rate >= 60 && rate <= 90 ? 'bg-green-500' : rate > 90 ? 'bg-red-500' : 'bg-yellow-500'
          }`}
          style={{ left: `${Math.min(rate, 100)}%` }}
        />
      </div>

      <div className="flex justify-between text-xs text-gray-500">
        <span>0%</span>
        <span className="text-green-400">60-90% target</span>
        <span>100%</span>
      </div>

      <p className="text-2xl font-bold text-white mt-2">{rate.toFixed(1)}%</p>
    </div>
  )
}

// Generator distribution pie chart (simplified as bars)
function GeneratorDistribution({ generators }: { generators: GeneratorPerf[] }) {
  const total = generators.reduce((sum, g) => sum + g.totalGenerated, 0)

  const getColor = (name: string) => {
    switch (name) {
      case 'FINN-E':
        return 'bg-blue-500'
      case 'FINN-T':
        return 'bg-purple-500'
      case 'GN-S':
        return 'bg-amber-500'
      default:
        return 'bg-gray-500'
    }
  }

  return (
    <div className="bg-gray-800/50 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-3">
        <BarChart3 className="h-4 w-4 text-blue-400" />
        <span className="text-sm text-gray-400">Generator Distribution</span>
      </div>

      {/* Stacked bar */}
      <div className="h-6 flex rounded-full overflow-hidden mb-3">
        {generators.map((g) => (
          <div
            key={g.name}
            className={`${getColor(g.name)} transition-all`}
            style={{ width: `${(g.totalGenerated / total) * 100}%` }}
            title={`${g.name}: ${g.totalGenerated}`}
          />
        ))}
      </div>

      {/* Legend */}
      <div className="grid grid-cols-2 gap-2">
        {generators.map((g) => (
          <div key={g.name} className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded ${getColor(g.name)}`} />
            <span className="text-xs text-gray-400">{g.name}</span>
            <span className="text-xs text-white font-medium ml-auto">{g.totalGenerated}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function LearningVisibilityPanel({
  metrics,
  summary,
  generators,
}: LearningVisibilityPanelProps) {
  // Prepare time series data
  const timeSeriesData = useMemo(() => {
    const last7 = metrics.slice(-7)
    return {
      hypotheses: last7.map((m) => m.hypothesesTotal),
      deathRates: last7.map((m) => m.deathRatePct),
      causalDepth: last7.map((m) => m.avgCausalDepth),
      dates: last7.map((m) => new Date(m.date).toLocaleDateString('en-US', { weekday: 'short' })),
    }
  }, [metrics])

  const maxHypotheses = Math.max(...timeSeriesData.hypotheses, 1)
  const maxDepth = Math.max(...timeSeriesData.causalDepth, 1)

  return (
    <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-6">
      {/* Header with status sentence */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Brain className="h-5 w-5 text-purple-400" />
          <h3 className="text-lg font-semibold text-white">Learning Visibility</h3>
        </div>
        <span className="text-xs text-gray-500">CEO-DIR-2026-DAY25</span>
      </div>

      {/* Status sentence - the CEO answer */}
      <div
        className={`mb-6 p-3 rounded-lg border ${
          summary.deathRateStatus === 'ON_TRACK'
            ? 'bg-green-500/10 border-green-500/30'
            : summary.deathRateStatus === 'TOO_BRUTAL'
            ? 'bg-red-500/10 border-red-500/30'
            : 'bg-yellow-500/10 border-yellow-500/30'
        }`}
      >
        <p
          className={`text-sm font-medium ${
            summary.deathRateStatus === 'ON_TRACK'
              ? 'text-green-400'
              : summary.deathRateStatus === 'TOO_BRUTAL'
              ? 'text-red-400'
              : 'text-yellow-400'
          }`}
        >
          {summary.statusSentence}
        </p>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="text-center">
          <p className="text-2xl font-bold text-white">{summary.totalHypotheses}</p>
          <p className="text-xs text-gray-500">Total Tested</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-red-400">{summary.totalFalsified}</p>
          <p className="text-xs text-gray-500">Falsified</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-green-400">{summary.totalActive}</p>
          <p className="text-xs text-gray-500">Active</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-amber-400">{summary.todayCount}</p>
          <p className="text-xs text-gray-500">Today</p>
        </div>
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        {/* Death Rate Gauge */}
        <DeathRateGauge rate={summary.deathRatePct} status={summary.deathRateStatus} />

        {/* Generator Distribution */}
        <GeneratorDistribution generators={generators} />
      </div>

      {/* Time series charts */}
      <div className="grid grid-cols-2 gap-4">
        {/* Hypotheses/day */}
        <div className="bg-gray-800/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <Activity className="h-4 w-4 text-blue-400" />
            <span className="text-sm text-gray-400">Hypotheses/Day (7d)</span>
          </div>
          <MiniBarChart
            data={timeSeriesData.hypotheses}
            maxValue={maxHypotheses}
            color="bg-blue-500"
            label={timeSeriesData.dates.join(' ')}
          />
        </div>

        {/* Causal Depth Trend */}
        <div className="bg-gray-800/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="h-4 w-4 text-purple-400" />
            <span className="text-sm text-gray-400">Avg Causal Depth (7d)</span>
          </div>
          <MiniBarChart
            data={timeSeriesData.causalDepth}
            maxValue={Math.max(maxDepth, 3)}
            color="bg-purple-500"
            label={`Current: ${summary.avgCausalDepth.toFixed(2)}`}
          />
        </div>
      </div>

      {/* Last activity */}
      {summary.lastHypothesisTime && (
        <div className="mt-4 pt-4 border-t border-gray-800">
          <p className="text-xs text-gray-500">
            Last hypothesis: {new Date(summary.lastHypothesisTime).toLocaleString()}
          </p>
        </div>
      )}
    </div>
  )
}
