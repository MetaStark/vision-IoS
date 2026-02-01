'use client'

import { Activity, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'

interface ResearchTrinityData {
  finnE: { count: number; share: number }
  finnT: { count: number; share: number }
  gnS: { count: number; share: number }
  totalHypotheses: number
  tier1DeathRate: number
  errorConversionRate: number
  avgCausalDepth: number
  learningHealth: 'GREEN' | 'AMBER' | 'RED'
}

interface Props {
  data: ResearchTrinityData | null
}

export function ResearchTrinityPanel({ data }: Props) {
  if (!data) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-gray-800 rounded w-1/3" />
          <div className="h-20 bg-gray-800 rounded" />
        </div>
      </div>
    )
  }

  const healthColor = {
    GREEN: 'text-green-400 bg-green-500/10 border-green-500/30',
    AMBER: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
    RED: 'text-red-400 bg-red-500/10 border-red-500/30',
  }[data.learningHealth]

  const healthIcon = {
    GREEN: <CheckCircle className="h-5 w-5" />,
    AMBER: <AlertTriangle className="h-5 w-5" />,
    RED: <XCircle className="h-5 w-5" />,
  }[data.learningHealth]

  const deathRateColor =
    data.tier1DeathRate >= 0.6 && data.tier1DeathRate <= 0.9 ? 'text-green-400' :
    data.tier1DeathRate >= 0.5 && data.tier1DeathRate <= 0.95 ? 'text-amber-400' : 'text-red-400'

  const conversionColor = data.errorConversionRate >= 0.25 ? 'text-green-400' : 'text-red-400'

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      {/* Header with Health Indicator */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-blue-400" />
          <h3 className="text-lg font-semibold text-white">Research Trinity</h3>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border ${healthColor}`}>
          {healthIcon}
          <span className="text-sm font-medium">Learning {data.learningHealth}</span>
        </div>
      </div>

      {/* Generator Distribution */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-gray-800/50 rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">FINN-E</div>
          <div className="text-2xl font-bold text-blue-400">{data.finnE.count}</div>
          <div className="text-xs text-gray-600">{(data.finnE.share * 100).toFixed(1)}% share</div>
          <div className="text-xs text-gray-500 mt-1">Error Repair</div>
        </div>
        <div className="bg-gray-800/50 rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">FINN-T</div>
          <div className="text-2xl font-bold text-purple-400">{data.finnT.count}</div>
          <div className="text-xs text-gray-600">{(data.finnT.share * 100).toFixed(1)}% share</div>
          <div className="text-xs text-gray-500 mt-1">World-Model</div>
        </div>
        <div className="bg-gray-800/50 rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">GN-S</div>
          <div className="text-2xl font-bold text-cyan-400">{data.gnS.count}</div>
          <div className="text-xs text-gray-600">{(data.gnS.share * 100).toFixed(1)}% share</div>
          <div className="text-xs text-gray-500 mt-1">Shadow Discovery</div>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 gap-4">
        {/* Tier-1 Death Rate Gauge */}
        <div className="bg-gray-800/50 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-gray-500 uppercase tracking-wider">Tier-1 Death Rate</span>
            <span className="text-xs text-gray-600">Target: 60-90%</span>
          </div>
          <div className={`text-3xl font-bold ${deathRateColor}`}>
            {(data.tier1DeathRate * 100).toFixed(1)}%
          </div>
          {/* Visual gauge */}
          <div className="mt-2 h-2 bg-gray-700 rounded-full overflow-hidden">
            <div className="h-full flex">
              <div className="h-full bg-red-500/30" style={{ width: '60%' }} />
              <div className="h-full bg-green-500/30" style={{ width: '30%' }} />
              <div className="h-full bg-red-500/30" style={{ width: '10%' }} />
            </div>
          </div>
          <div className="flex justify-between text-xs text-gray-600 mt-1">
            <span>0%</span>
            <span className="text-green-500">60-90%</span>
            <span>100%</span>
          </div>
        </div>

        {/* Error Conversion Rate */}
        <div className="bg-gray-800/50 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-gray-500 uppercase tracking-wider">Error Conversion</span>
            <span className="text-xs text-gray-600">Target: &gt;25%</span>
          </div>
          <div className={`text-3xl font-bold ${conversionColor}`}>
            {(data.errorConversionRate * 100).toFixed(1)}%
          </div>
          <div className="mt-2 h-2 bg-gray-700 rounded-full overflow-hidden">
            <div
              className={`h-full ${data.errorConversionRate >= 0.25 ? 'bg-green-500' : 'bg-red-500'}`}
              style={{ width: `${Math.min(data.errorConversionRate * 100, 100)}%` }}
            />
          </div>
          <div className="text-xs text-gray-600 mt-1">
            Avg Causal Depth: {data.avgCausalDepth.toFixed(2)}
          </div>
        </div>
      </div>

      {/* Total */}
      <div className="mt-4 pt-4 border-t border-gray-800 flex justify-between text-sm">
        <span className="text-gray-500">Total Hypotheses: <span className="text-white font-medium">{data.totalHypotheses}</span></span>
        <span className="text-gray-500">
          {data.learningHealth === 'RED' && 'Brutality enforced - awaiting statistical evidence'}
          {data.learningHealth === 'AMBER' && 'Learning in progress'}
          {data.learningHealth === 'GREEN' && 'Healthy learning velocity'}
        </span>
      </div>
    </div>
  )
}
