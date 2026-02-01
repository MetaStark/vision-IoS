'use client'

import { useMemo } from 'react'
import { TrendingUp, TrendingDown, Minus, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'

// Types for time series data
interface TimeSeriesPoint {
  date: string
  value: number | null
}

interface DeathRateData {
  timeSeries: TimeSeriesPoint[]
  current: number | null
  targetMin: number
  targetMax: number
  healthStatus: string
  dayNumber: number
}

interface ConversionData {
  timeSeries: TimeSeriesPoint[]
  current: number | null
  targetMin: number
  healthStatus: string
}

interface GeneratorData {
  timeSeries: {
    date: string
    finnE: number
    finnT: number
    gnS: number
  }[]
  current: {
    finnE: number
    finnT: number
    gnS: number
    dominant: string | null
    dominantPct: number
  }
  monocultureThreshold: number
  healthStatus: string
}

interface CausalDepthData {
  timeSeries: TimeSeriesPoint[]
  current: number | null
  targetMin: number
  healthStatus: string
  trend: string | null
}

interface LearningTrajectoryData {
  deathRate: DeathRateData | null
  conversion: ConversionData | null
  generators: GeneratorData | null
  causalDepth: CausalDepthData | null
  lastRefresh: string
}

interface Props {
  data: LearningTrajectoryData | null
}

// Mini sparkline component
function Sparkline({
  data,
  targetMin,
  targetMax,
  color = '#3b82f6',
  height = 60
}: {
  data: TimeSeriesPoint[]
  targetMin?: number
  targetMax?: number
  color?: string
  height?: number
}) {
  const validData = data.filter(d => d.value !== null)
  if (validData.length === 0) return <div className="h-[60px] flex items-center justify-center text-gray-600 text-xs">No data</div>

  const values = validData.map(d => d.value as number)
  const min = Math.min(...values, targetMin ?? Infinity) * 0.9
  const max = Math.max(...values, targetMax ?? -Infinity) * 1.1
  const range = max - min || 1

  const width = 200
  const points = validData.map((d, i) => {
    const x = (i / (validData.length - 1 || 1)) * width
    const y = height - ((d.value as number) - min) / range * height
    return `${x},${y}`
  }).join(' ')

  const targetMinY = targetMin !== undefined ? height - (targetMin - min) / range * height : null
  const targetMaxY = targetMax !== undefined ? height - (targetMax - min) / range * height : null

  return (
    <svg width={width} height={height} className="overflow-visible">
      {/* Target band */}
      {targetMinY !== null && targetMaxY !== null && (
        <rect
          x={0}
          y={Math.min(targetMinY, targetMaxY)}
          width={width}
          height={Math.abs(targetMaxY - targetMinY)}
          fill="#22c55e"
          opacity={0.1}
        />
      )}
      {/* Target line (single) */}
      {targetMinY !== null && targetMaxY === null && (
        <line x1={0} y1={targetMinY} x2={width} y2={targetMinY} stroke="#22c55e" strokeDasharray="4" opacity={0.5} />
      )}
      {/* Data line */}
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={2}
      />
      {/* Current point */}
      {validData.length > 0 && (
        <circle
          cx={width}
          cy={height - ((validData[validData.length - 1].value as number) - min) / range * height}
          r={4}
          fill={color}
        />
      )}
    </svg>
  )
}

// Stacked bar for generator distribution
function GeneratorBar({ finnE, finnT, gnS }: { finnE: number; finnT: number; gnS: number }) {
  const total = finnE + finnT + gnS
  if (total === 0) return <div className="h-4 bg-gray-800 rounded text-xs text-gray-600 flex items-center justify-center">No data</div>

  const finnEPct = (finnE / total) * 100
  const finnTPct = (finnT / total) * 100
  const gnSPct = (gnS / total) * 100

  return (
    <div className="h-4 flex rounded overflow-hidden">
      <div style={{ width: `${finnEPct}%` }} className="bg-blue-500" title={`FINN-E: ${finnEPct.toFixed(1)}%`} />
      <div style={{ width: `${finnTPct}%` }} className="bg-purple-500" title={`FINN-T: ${finnTPct.toFixed(1)}%`} />
      <div style={{ width: `${gnSPct}%` }} className="bg-cyan-500" title={`GN-S: ${gnSPct.toFixed(1)}%`} />
    </div>
  )
}

// Health status badge
function HealthBadge({ status }: { status: string }) {
  const config: Record<string, { color: string; icon: React.ReactNode }> = {
    'HEALTHY': { color: 'text-green-400 bg-green-500/10 border-green-500/30', icon: <CheckCircle className="h-3 w-3" /> },
    'BALANCED': { color: 'text-green-400 bg-green-500/10 border-green-500/30', icon: <CheckCircle className="h-3 w-3" /> },
    'METABOLIZING': { color: 'text-green-400 bg-green-500/10 border-green-500/30', icon: <CheckCircle className="h-3 w-3" /> },
    'STRUCTURAL UNDERSTANDING': { color: 'text-green-400 bg-green-500/10 border-green-500/30', icon: <CheckCircle className="h-3 w-3" /> },
    'IMPROVING': { color: 'text-amber-400 bg-amber-500/10 border-amber-500/30', icon: <TrendingUp className="h-3 w-3" /> },
    'OVER-ANNIHILATION': { color: 'text-red-400 bg-red-500/10 border-red-500/30', icon: <AlertTriangle className="h-3 w-3" /> },
    'EPISTEMIC SOFTNESS': { color: 'text-amber-400 bg-amber-500/10 border-amber-500/30', icon: <AlertTriangle className="h-3 w-3" /> },
    'MONOCULTURE RISK': { color: 'text-amber-400 bg-amber-500/10 border-amber-500/30', icon: <AlertTriangle className="h-3 w-3" /> },
    'WASTING CAPACITY': { color: 'text-red-400 bg-red-500/10 border-red-500/30', icon: <XCircle className="h-3 w-3" /> },
    'SHALLOW': { color: 'text-red-400 bg-red-500/10 border-red-500/30', icon: <XCircle className="h-3 w-3" /> },
    'SIGNAL-LEVEL GUESSING': { color: 'text-amber-400 bg-amber-500/10 border-amber-500/30', icon: <AlertTriangle className="h-3 w-3" /> },
    'NO DATA': { color: 'text-gray-400 bg-gray-500/10 border-gray-500/30', icon: <Minus className="h-3 w-3" /> },
    'NO ERRORS': { color: 'text-gray-400 bg-gray-500/10 border-gray-500/30', icon: <Minus className="h-3 w-3" /> },
  }

  const { color, icon } = config[status] || config['NO DATA']

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded border ${color}`}>
      {icon}
      {status}
    </span>
  )
}

export function LearningTrajectoryCharts({ data }: Props) {
  if (!data) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-4 animate-pulse">
            <div className="h-4 bg-gray-800 rounded w-1/3 mb-4" />
            <div className="h-[60px] bg-gray-800 rounded mb-4" />
            <div className="h-3 bg-gray-800 rounded w-2/3" />
          </div>
        ))}
      </div>
    )
  }

  // Generate executive sentences
  const deathRateSentence = useMemo(() => {
    if (!data.deathRate || data.deathRate.current === null) return 'No Tier-1 evaluation data available.'
    const pct = data.deathRate.current
    const status = pct >= 60 && pct <= 90 ? 'within' : pct > 90 ? 'above' : 'below'
    const meaning = pct > 90 ? 'over-annihilation' : pct >= 60 ? 'healthy filtering' : 'epistemic softness'
    return `Tier-1 falsification pressure is currently ${pct.toFixed(1)}%, which is ${status} the survivable learning band, indicating ${meaning} at Day ${data.deathRate.dayNumber} of calibration.`
  }, [data.deathRate])

  const conversionSentence = useMemo(() => {
    if (!data.conversion || data.conversion.current === null) return 'No error conversion data available.'
    const pct = data.conversion.current
    const status = pct >= 25 ? 'above' : 'below'
    const meaning = pct >= 25 ? 'errors are being metabolized' : 'learning capacity is being wasted'
    return `The system is converting ${pct.toFixed(1)}% of high-priority errors into hypotheses, ${status} the institutional minimum, meaning ${meaning}.`
  }, [data.conversion])

  const generatorSentence = useMemo(() => {
    if (!data.generators || !data.generators.current.dominant) return 'No generator distribution data available.'
    const balanced = data.generators.healthStatus === 'BALANCED'
    const dominant = data.generators.current.dominant
    const pct = data.generators.current.dominantPct
    return `Learning input is currently ${balanced ? 'balanced' : 'skewed'}, with ${dominant} contributing ${pct.toFixed(1)}%, implying ${balanced ? 'healthy diversity' : 'renewed monoculture risk'}.`
  }, [data.generators])

  const depthSentence = useMemo(() => {
    if (!data.causalDepth || data.causalDepth.current === null) return 'No causal depth data available.'
    const depth = data.causalDepth.current
    const trend = data.causalDepth.trend || 'stable'
    const trendWord = trend === 'IMPROVING' ? 'improving' : trend === 'REGRESSING' ? 'regressing' : 'stagnating'
    const meaning = depth >= 2.5 ? 'structural understanding' : 'signal-level guessing'
    return `Average causal depth is ${depth.toFixed(2)}, which is ${trendWord}, indicating ${meaning} at this stage of learning.`
  }, [data.causalDepth])

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Chart 1: Tier-1 Death Rate */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-white">Tier-1 Death Rate Trajectory</h4>
            <HealthBadge status={data.deathRate?.healthStatus || 'NO DATA'} />
          </div>
          <div className="flex items-center gap-4 mb-3">
            <Sparkline
              data={data.deathRate?.timeSeries || []}
              targetMin={60}
              targetMax={90}
              color={data.deathRate?.healthStatus === 'HEALTHY' ? '#22c55e' : '#ef4444'}
            />
            <div className="text-right">
              <div className="text-2xl font-bold text-white">
                {data.deathRate?.current !== null ? `${data.deathRate.current.toFixed(1)}%` : '—'}
              </div>
              <div className="text-xs text-gray-500">Target: 60-90%</div>
            </div>
          </div>
          <p className="text-xs text-gray-400 leading-relaxed">{deathRateSentence}</p>
        </div>

        {/* Chart 2: Error Conversion */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-white">Error → Hypothesis Conversion</h4>
            <HealthBadge status={data.conversion?.healthStatus || 'NO DATA'} />
          </div>
          <div className="flex items-center gap-4 mb-3">
            <Sparkline
              data={data.conversion?.timeSeries || []}
              targetMin={25}
              color={data.conversion?.healthStatus === 'METABOLIZING' ? '#22c55e' : '#ef4444'}
            />
            <div className="text-right">
              <div className="text-2xl font-bold text-white">
                {data.conversion?.current !== null ? `${data.conversion.current.toFixed(1)}%` : '—'}
              </div>
              <div className="text-xs text-gray-500">Target: &gt;25%</div>
            </div>
          </div>
          <p className="text-xs text-gray-400 leading-relaxed">{conversionSentence}</p>
        </div>

        {/* Chart 3: Generator Mix */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-white">Research Trinity Balance</h4>
            <HealthBadge status={data.generators?.healthStatus || 'NO DATA'} />
          </div>
          <div className="mb-3">
            <GeneratorBar
              finnE={data.generators?.current.finnE || 0}
              finnT={data.generators?.current.finnT || 0}
              gnS={data.generators?.current.gnS || 0}
            />
            <div className="flex justify-between mt-2 text-xs">
              <span className="text-blue-400">FINN-E: {data.generators?.current.finnE || 0}</span>
              <span className="text-purple-400">FINN-T: {data.generators?.current.finnT || 0}</span>
              <span className="text-cyan-400">GN-S: {data.generators?.current.gnS || 0}</span>
            </div>
          </div>
          <p className="text-xs text-gray-400 leading-relaxed">{generatorSentence}</p>
        </div>

        {/* Chart 4: Causal Depth */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-white">Causal Depth Trend</h4>
            <HealthBadge status={data.causalDepth?.healthStatus || 'NO DATA'} />
          </div>
          <div className="flex items-center gap-4 mb-3">
            <Sparkline
              data={data.causalDepth?.timeSeries || []}
              targetMin={2.5}
              color={data.causalDepth?.healthStatus === 'STRUCTURAL UNDERSTANDING' ? '#22c55e' : '#f59e0b'}
            />
            <div className="text-right">
              <div className="text-2xl font-bold text-white">
                {data.causalDepth?.current !== null ? data.causalDepth.current.toFixed(2) : '—'}
              </div>
              <div className="text-xs text-gray-500">Target: &gt;2.5</div>
            </div>
          </div>
          <p className="text-xs text-gray-400 leading-relaxed">{depthSentence}</p>
        </div>
      </div>

      {/* Data source footer */}
      <div className="text-xs text-gray-600 text-right">
        Data source: PostgreSQL views | Last refresh: {data.lastRefresh ? new Date(data.lastRefresh).toLocaleTimeString() : 'Unknown'}
      </div>
    </div>
  )
}

export type { LearningTrajectoryData, DeathRateData, ConversionData, GeneratorData, CausalDepthData }
