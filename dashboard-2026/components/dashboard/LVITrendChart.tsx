/**
 * LVI Trend Chart Component
 * CEO-DIR-2026-META-ANALYSIS Phase 4
 *
 * Displays Learning Velocity Index history with:
 * - Current score with grade
 * - Trend visualization (SVG sparkline)
 * - Component breakdown
 * - Historical context
 *
 * Authority: Dashboard UX Specification 2026 v2.0
 */

'use client'

import { useEffect, useState, useCallback } from 'react'
import { cn } from '@/lib/utils/cn'
import {
  Activity,
  TrendingUp,
  TrendingDown,
  Minus,
  RefreshCw,
  XCircle,
  Target,
  CheckCircle,
  Clock,
  BarChart3
} from 'lucide-react'

interface LVIDataPoint {
  computed_at: string
  lvi_score: number
  completed_experiments: number
  coverage_rate: number
  integrity_rate: number
  brier_component: number
}

interface LVICurrent {
  lvi_score: number
  completed_experiments: number
  coverage_rate: number
  integrity_rate: number
  brier_component: number
  computed_at: string
  drivers: any
  grade: string
  gradeColor: string
  trend: 'IMPROVING' | 'STABLE' | 'DECLINING'
  trendPct: number
}

interface LVITrendChartProps {
  className?: string
  refreshKey?: number
  days?: number
}

export function LVITrendChart({
  className,
  refreshKey = 0,
  days = 30
}: LVITrendChartProps) {
  const [current, setCurrent] = useState<LVICurrent | null>(null)
  const [history, setHistory] = useState<LVIDataPoint[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await fetch(`/api/lvi?days=${days}`)

      if (!response.ok) {
        throw new Error('Failed to fetch LVI data')
      }

      const data = await response.json()
      setCurrent(data.current)
      setHistory(data.history)
    } catch (err) {
      console.error('[LVITrendChart] Fetch error:', err)
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setIsLoading(false)
    }
  }, [days])

  useEffect(() => {
    fetchData()
  }, [fetchData, refreshKey])

  const getGradeColor = (grade: string) => {
    switch (grade) {
      case 'A': return 'text-green-400 bg-green-900/30 border-green-700'
      case 'B': return 'text-blue-400 bg-blue-900/30 border-blue-700'
      case 'C': return 'text-yellow-400 bg-yellow-900/30 border-yellow-700'
      case 'D': return 'text-orange-400 bg-orange-900/30 border-orange-700'
      case 'F':
      default: return 'text-red-400 bg-red-900/30 border-red-700'
    }
  }

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'IMPROVING': return <TrendingUp className="h-4 w-4 text-green-400" />
      case 'DECLINING': return <TrendingDown className="h-4 w-4 text-red-400" />
      default: return <Minus className="h-4 w-4 text-gray-400" />
    }
  }

  const renderSparkline = () => {
    if (history.length < 2) {
      return (
        <div className="h-20 flex items-center justify-center text-gray-500 text-sm">
          Insufficient data for trend
        </div>
      )
    }

    // Reverse to show oldest to newest
    const data = [...history].reverse()
    const width = 300
    const height = 60
    const padding = 4

    const scores = data.map(d => d.lvi_score)
    const minScore = Math.min(...scores, 0)
    const maxScore = Math.max(...scores, 1)
    const range = maxScore - minScore || 1

    // Generate path
    const points = data.map((d, i) => {
      const x = padding + (i / (data.length - 1)) * (width - 2 * padding)
      const y = height - padding - ((d.lvi_score - minScore) / range) * (height - 2 * padding)
      return `${x},${y}`
    })

    const pathD = `M ${points.join(' L ')}`

    // Fill area
    const fillPoints = [
      `${padding},${height - padding}`,
      ...points,
      `${width - padding},${height - padding}`
    ].join(' ')

    // Gradient color based on current score
    const currentScore = current?.lvi_score || 0
    let gradientColor = '#ef4444' // red
    if (currentScore >= 0.6) gradientColor = '#22c55e' // green
    else if (currentScore >= 0.4) gradientColor = '#eab308' // yellow
    else if (currentScore >= 0.2) gradientColor = '#f97316' // orange

    return (
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full h-20"
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="lvi-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={gradientColor} stopOpacity="0.3" />
            <stop offset="100%" stopColor={gradientColor} stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        <line
          x1={padding}
          y1={height / 2}
          x2={width - padding}
          y2={height / 2}
          stroke="#374151"
          strokeDasharray="4,4"
        />

        {/* Fill area */}
        <polygon
          points={fillPoints}
          fill="url(#lvi-gradient)"
        />

        {/* Line */}
        <path
          d={pathD}
          fill="none"
          stroke={gradientColor}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Current point */}
        <circle
          cx={width - padding}
          cy={height - padding - ((currentScore - minScore) / range) * (height - 2 * padding)}
          r="4"
          fill={gradientColor}
        />
      </svg>
    )
  }

  if (isLoading) {
    return (
      <div className={cn('border border-gray-800 rounded-lg p-6 bg-gray-900/50', className)}>
        <div className="flex items-center justify-center gap-2 text-gray-500">
          <RefreshCw className="h-4 w-4 animate-spin" />
          <span>Loading LVI data...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={cn('border border-red-800 rounded-lg p-6 bg-red-950/30', className)}>
        <div className="flex items-center gap-2 text-red-400">
          <XCircle className="h-5 w-5" />
          <span>{error}</span>
        </div>
      </div>
    )
  }

  return (
    <div className={cn('border border-gray-800 rounded-lg bg-gray-900/50', className)}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-800">
        <div className="flex items-center gap-3">
          <Activity className="h-5 w-5 text-blue-400" />
          <h3 className="font-semibold text-white">Learning Velocity Index</h3>
        </div>
        <div className="text-xs text-gray-500">
          Last {days} days
        </div>
      </div>

      {/* Main content */}
      <div className="p-4 space-y-4">
        {/* Current score display */}
        {current && (
          <div className="flex items-center justify-between">
            {/* Score and grade */}
            <div className="flex items-center gap-4">
              <div className={cn(
                'w-16 h-16 rounded-lg border-2 flex items-center justify-center text-2xl font-bold',
                getGradeColor(current.grade)
              )}>
                {current.grade}
              </div>
              <div>
                <div className="text-3xl font-bold text-white">
                  {(current.lvi_score * 100).toFixed(1)}%
                </div>
                <div className="flex items-center gap-2 text-sm text-gray-400">
                  {getTrendIcon(current.trend)}
                  <span>
                    {current.trend === 'STABLE' ? 'Stable' :
                     current.trend === 'IMPROVING' ? `+${current.trendPct}%` :
                     `${current.trendPct}%`}
                  </span>
                </div>
              </div>
            </div>

            {/* Target indicator */}
            <div className="text-right">
              <div className="text-xs text-gray-500 mb-1">Target: 50%</div>
              <div className="flex items-center gap-2">
                <Target className="h-4 w-4 text-gray-500" />
                <span className={cn(
                  'text-sm font-medium',
                  current.lvi_score >= 0.5 ? 'text-green-400' : 'text-yellow-400'
                )}>
                  {current.lvi_score >= 0.5 ? 'On Target' : `${((0.5 - current.lvi_score) * 100).toFixed(0)}% to go`}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Sparkline chart */}
        <div className="bg-gray-950/50 rounded-lg p-3">
          {renderSparkline()}
        </div>

        {/* Component breakdown */}
        {current && (
          <div className="grid grid-cols-4 gap-3">
            <div className="bg-gray-950/50 rounded p-3 text-center">
              <div className="text-xs text-gray-500 mb-1">Experiments</div>
              <div className="text-lg font-semibold text-white">
                {current.completed_experiments}
              </div>
            </div>
            <div className="bg-gray-950/50 rounded p-3 text-center">
              <div className="text-xs text-gray-500 mb-1">Coverage</div>
              <div className={cn(
                'text-lg font-semibold',
                current.coverage_rate >= 0.5 ? 'text-green-400' : 'text-red-400'
              )}>
                {(current.coverage_rate * 100).toFixed(0)}%
              </div>
            </div>
            <div className="bg-gray-950/50 rounded p-3 text-center">
              <div className="text-xs text-gray-500 mb-1">Integrity</div>
              <div className={cn(
                'text-lg font-semibold',
                current.integrity_rate >= 0.9 ? 'text-green-400' : 'text-yellow-400'
              )}>
                {(current.integrity_rate * 100).toFixed(0)}%
              </div>
            </div>
            <div className="bg-gray-950/50 rounded p-3 text-center">
              <div className="text-xs text-gray-500 mb-1">Brier</div>
              <div className={cn(
                'text-lg font-semibold',
                current.brier_component <= 0.25 ? 'text-green-400' : 'text-yellow-400'
              )}>
                {current.brier_component.toFixed(2)}
              </div>
            </div>
          </div>
        )}

        {/* Status message */}
        {current && current.lvi_score === 0 && (
          <div className="bg-yellow-950/30 border border-yellow-800 rounded p-3 text-sm">
            <div className="flex items-center gap-2 text-yellow-400 mb-1">
              <Clock className="h-4 w-4" />
              <span className="font-medium">Learning Loop Primed</span>
            </div>
            <p className="text-gray-400 text-xs">
              LVI will increase after economic event outcomes are captured and hypotheses validated.
              Coverage rate of 0% indicates no completed experiments yet.
            </p>
          </div>
        )}
      </div>

      {/* Footer */}
      {current && (
        <div className="p-3 border-t border-gray-800 text-xs text-gray-500 text-center">
          Last computed: {new Date(current.computed_at).toLocaleString()}
        </div>
      )}
    </div>
  )
}
